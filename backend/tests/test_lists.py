from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import FakeResult, chain_mock, table_router

client = TestClient(app)


def _now():
    return datetime.now(timezone.utc).isoformat()


def test_create_list_success(auth_override):
    list_id = uuid4()
    lists_mock = chain_mock(
        FakeResult(data=[{"id": str(list_id), "name": "Mi lista",
                          "created_at": _now(), "updated_at": _now()}])
    )
    fake_client = type("Client", (), {"table": lambda self, name: lists_mock})()

    with patch("app.services.list_service.get_supabase", return_value=fake_client):
        response = client.post("/api/v1/lists", json={"name": "Mi lista"})

    assert response.status_code == 201
    assert response.json()["name"] == "Mi lista"
    assert response.json()["items_count"] == 0


def test_get_list_not_found_for_other_user(auth_override):
    """
    Simula que la lista pedida no es del usuario autenticado: get_list_or_404
    debe devolver 404 (no 403, para no revelar que el recurso existe), porque
    el filtro .eq("user_id", ...) no matchea ninguna fila.
    """
    other_list_id = uuid4()
    lists_mock = chain_mock(FakeResult(data=None))
    fake_client = type("Client", (), {"table": lambda self, name: lists_mock})()

    with patch("app.services.list_service.get_supabase", return_value=fake_client):
        response = client.get(f"/api/v1/lists/{other_list_id}")

    assert response.status_code == 404


def test_add_item_product_not_found(auth_override):
    list_id = uuid4()
    tables = {
        "shopping_lists": chain_mock(
            FakeResult(data={"id": str(list_id), "user_id": str(auth_override.id),
                              "name": "Mi lista", "created_at": _now(), "updated_at": _now()})
        ),
        "products": chain_mock(FakeResult(data=None)),
    }
    fake_client = type("Client", (), {"table": lambda self, name: table_router(tables)(name)})()

    with patch("app.services.list_service.get_supabase", return_value=fake_client):
        response = client.post(
            f"/api/v1/lists/{list_id}/items",
            json={"product_id": str(uuid4()), "quantity": 2},
        )

    assert response.status_code == 404
