from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import (
    get_current_platform_admin,
    get_current_staff,
    require_manager,
    require_owner,
)
from app.main import app
from app.schemas.auth import CurrentPlatformAdmin, CurrentStaff

from .conftest import FakeResult, chain_mock, table_router

client = TestClient(app)


def _staff(role="owner", chain_status="approved", chain_id=None):
    return CurrentStaff(
        id=uuid4(),
        email="owner@super.com",
        chain_id=chain_id or uuid4(),
        supermarket_id=None,
        role=role,
        chain_status=chain_status,
    )


@pytest.fixture
def staff_override():
    """
    Sobreescribe las cuatro dependencias de staff con el mismo usuario. Hay que
    cubrir require_manager y require_owner además de get_current_staff porque
    FastAPI resuelve cada una por separado, no a través de la otra.
    """
    def _apply(current):
        for dep in (get_current_staff, require_manager, require_owner):
            app.dependency_overrides[dep] = lambda c=current: c
        return current

    yield _apply

    for dep in (get_current_staff, require_manager, require_owner):
        app.dependency_overrides.pop(dep, None)


@pytest.fixture
def admin_override():
    admin = CurrentPlatformAdmin(id=uuid4(), email="admin@freshmart.com", full_name="Ana Admin")
    app.dependency_overrides[get_current_platform_admin] = lambda: admin
    yield admin
    app.dependency_overrides.pop(get_current_platform_admin, None)


def _register_payload(**overrides):
    payload = {
        "email": "owner@super.com",
        "password": "unaClaveSegura1",
        "owner_full_name": "Marta Gómez",
        "owner_phone": "1122334455",
        "legal_name": "Supermercados del Sur S.A.",
        "trade_name": "SurMarket",
        "tax_id": "30-71234567-8",
        "contact_email": "contacto@surmarket.com",
        "contact_phone": "1155667788",
        "store": {
            "name": "SurMarket Centro",
            "street": "Av. Siempreviva 742",
            "city": "CABA",
            "province": "CABA",
            "postal_code": "1414",
            "hours": [{"weekday": 1, "opens_at": "08:00", "closes_at": "21:00"}],
        },
        "accepts_terms": True,
    }
    payload.update(overrides)
    return payload


# ── Registro ──────────────────────────────────────────────────────────────

def test_register_creates_chain_pending_review():
    chain_id = str(uuid4())
    user_id = str(uuid4())

    fake_client = MagicMock()
    fake_client.table.side_effect = table_router(
        {"chains": chain_mock(FakeResult(data=[]))}  # el CUIT está libre
    )
    fake_client.auth.admin.create_user.return_value = MagicMock(user=MagicMock(id=user_id))
    fake_client.rpc.return_value.execute.return_value = FakeResult(data=chain_id)

    with patch("app.services.supermarket_auth_service.get_supabase", return_value=fake_client):
        response = client.post("/api/v1/supermarkets/register", json=_register_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["chain_id"] == chain_id
    assert body["status"] == "pending_review"
    # TEMPORAL: REQUIRE_EMAIL_CONFIRMATION está en False en
    # supermarket_auth_service mientras no hay SMTP propio configurado (ver el
    # comentario junto a esa constante). Cuando se revierta, este assert y el
    # de mas abajo vuelven a ser True / False.
    assert body["email_confirmation_required"] is False

    # El staff de un supermercado NO es un consumidor: el flag account_type es
    # lo que evita que el trigger handle_new_user le cree una fila en profiles.
    created = fake_client.auth.admin.create_user.call_args[0][0]
    assert created["user_metadata"]["account_type"] == "supermarket_staff"
    # email_confirm = not REQUIRE_EMAIL_CONFIRMATION: con el chequeo apagado la
    # cuenta nace ya confirmada.
    assert created["email_confirm"] is True

    # El CUIT llega normalizado a 11 dígitos, como exige el CHECK de la 010.
    assert fake_client.rpc.call_args[0][1]["p_tax_id"] == "30712345678"


def test_register_rejects_duplicate_tax_id():
    fake_client = MagicMock()
    fake_client.table.side_effect = table_router(
        {"chains": chain_mock(FakeResult(data=[{"id": str(uuid4())}]))}
    )

    with patch("app.services.supermarket_auth_service.get_supabase", return_value=fake_client):
        response = client.post("/api/v1/supermarkets/register", json=_register_payload())

    assert response.status_code == 409
    # Se corta antes de crear el usuario en Auth: si no, quedaría una cuenta
    # huérfana que ya no se puede reusar.
    fake_client.auth.admin.create_user.assert_not_called()


def test_register_rejects_invalid_tax_id():
    response = client.post("/api/v1/supermarkets/register", json=_register_payload(tax_id="123"))
    assert response.status_code == 422


def test_register_requires_accepting_terms():
    response = client.post(
        "/api/v1/supermarkets/register", json=_register_payload(accepts_terms=False)
    )
    assert response.status_code == 422


def test_register_rejects_duplicate_weekday_hours():
    payload = _register_payload()
    payload["store"]["hours"] = [
        {"weekday": 1, "opens_at": "08:00", "closes_at": "13:00"},
        {"weekday": 1, "opens_at": "16:00", "closes_at": "21:00"},
    ]
    response = client.post("/api/v1/supermarkets/register", json=payload)
    assert response.status_code == 422


def test_register_deletes_auth_user_when_rpc_fails():
    user_id = str(uuid4())
    fake_client = MagicMock()
    fake_client.table.side_effect = table_router({"chains": chain_mock(FakeResult(data=[]))})
    fake_client.auth.admin.create_user.return_value = MagicMock(user=MagicMock(id=user_id))
    fake_client.rpc.return_value.execute.side_effect = Exception("chain_tax_id_taken")

    with patch("app.services.supermarket_auth_service.get_supabase", return_value=fake_client):
        response = client.post("/api/v1/supermarkets/register", json=_register_payload())

    assert response.status_code == 409
    # El usuario de Auth se crea FUERA de la transacción de la RPC: si la RPC
    # falla hay que borrarlo o queda una cuenta sin cadena asociada.
    fake_client.auth.admin.delete_user.assert_called_once_with(user_id)


# ── Perfil y sucursales ───────────────────────────────────────────────────

def test_get_me_returns_pending_status(staff_override):
    current = staff_override(_staff(chain_status="pending_review"))
    chain_row = {
        "id": str(current.chain_id),
        "legal_name": "Supermercados del Sur S.A.",
        "trade_name": "SurMarket",
        "tax_id": "30712345678",
        "contact_email": "contacto@surmarket.com",
        "contact_phone": None,
        "logo_url": None,
        "status": "pending_review",
        "rejection_reason": None,
        "reviewed_at": None,
        "created_at": "2026-08-21T10:00:00Z",
    }

    fake_client = MagicMock()
    fake_client.table.side_effect = table_router(
        {
            "chains": chain_mock(FakeResult(data=chain_row)),
            "supermarkets": chain_mock(FakeResult(data=[{"id": str(uuid4())}], count=1)),
        }
    )

    with patch("app.services.supermarket_service.get_supabase", return_value=fake_client):
        response = client.get("/api/v1/supermarkets/me")

    assert response.status_code == 200
    body = response.json()
    assert body["chain"]["status"] == "pending_review"
    assert body["role"] == "owner"
    assert body["stores_count"] == 1


def test_get_store_of_another_chain_returns_404(staff_override):
    """
    El backend usa service_role y bypasea RLS: el filtro por chain_id es la
    única barrera. Se devuelve 404 y no 403 para no confirmar que la sucursal
    existe (docs/SEGURIDAD.md §4.3).
    """
    staff_override(_staff())

    fake_client = MagicMock()
    fake_client.table.side_effect = table_router(
        {"supermarkets": chain_mock(FakeResult(data=None))}
    )

    with patch("app.services.supermarket_service.get_supabase", return_value=fake_client):
        response = client.get(f"/api/v1/supermarkets/me/stores/{uuid4()}")

    assert response.status_code == 404


def test_update_chain_ignores_tax_id(staff_override):
    """
    tax_id no está en ChainUpdate: es la identidad fiscal sobre la que se
    aprobó la cadena. Pydantic lo descarta y nunca llega al UPDATE.
    """
    current = staff_override(_staff())
    updated = {
        "id": str(current.chain_id),
        "legal_name": "Supermercados del Sur S.A.",
        "trade_name": "SurMarket Premium",
        "tax_id": "30712345678",
        "contact_email": "contacto@surmarket.com",
        "contact_phone": None,
        "logo_url": None,
        "status": "approved",
        "rejection_reason": None,
        "reviewed_at": None,
        "created_at": "2026-08-21T10:00:00Z",
    }

    chains_mock = chain_mock(FakeResult(data=[updated]))
    fake_client = MagicMock()
    fake_client.table.side_effect = table_router({"chains": chains_mock})

    with patch("app.services.supermarket_service.get_supabase", return_value=fake_client):
        response = client.patch(
            "/api/v1/supermarkets/me",
            json={"trade_name": "SurMarket Premium", "tax_id": "99999999999"},
        )

    assert response.status_code == 200
    assert chains_mock.update.call_args[0][0] == {"trade_name": "SurMarket Premium"}


def test_staff_role_cannot_create_store():
    """require_manager rechaza el rol 'staff' con 403, no con 404."""
    app.dependency_overrides[get_current_staff] = lambda: _staff(role="staff")
    try:
        response = client.post(
            "/api/v1/supermarkets/me/stores",
            json={"name": "Sucursal Norte", "street": "Av. Cabildo 1000", "city": "CABA"},
        )
    finally:
        app.dependency_overrides.pop(get_current_staff, None)

    assert response.status_code == 403


def test_invite_staff_rejects_owner_role(staff_override):
    """Hay un único owner por cadena (índice parcial de 012): no es asignable."""
    staff_override(_staff())
    response = client.post(
        "/api/v1/supermarkets/me/users",
        json={"email": "nuevo@super.com", "full_name": "Juan Pérez", "role": "owner"},
    )
    assert response.status_code == 422


# ── Moderación ────────────────────────────────────────────────────────────

def test_review_chain_approves(admin_override):
    chain_id = uuid4()
    approved = {
        "id": str(chain_id),
        "legal_name": "Supermercados del Sur S.A.",
        "trade_name": "SurMarket",
        "tax_id": "30712345678",
        "contact_email": "contacto@surmarket.com",
        "contact_phone": None,
        "logo_url": None,
        "status": "approved",
        "rejection_reason": None,
        "reviewed_at": "2026-08-21T12:00:00Z",
        "created_at": "2026-08-21T10:00:00Z",
    }

    fake_client = MagicMock()
    fake_client.rpc.return_value.execute.return_value = FakeResult(data=approved)

    with patch("app.services.supermarket_auth_service.get_supabase", return_value=fake_client):
        response = client.post(
            f"/api/v1/admin/chains/{chain_id}/review", json={"status": "approved"}
        )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_review_chain_rejects_invalid_status(admin_override):
    response = client.post(
        f"/api/v1/admin/chains/{uuid4()}/review", json={"status": "pending_review"}
    )
    assert response.status_code == 422


def test_review_chain_requires_reason_when_rejecting(admin_override):
    fake_client = MagicMock()
    fake_client.rpc.return_value.execute.side_effect = Exception("rejection_reason_required")

    with patch("app.services.supermarket_auth_service.get_supabase", return_value=fake_client):
        response = client.post(
            f"/api/v1/admin/chains/{uuid4()}/review", json={"status": "rejected"}
        )

    assert response.status_code == 400
