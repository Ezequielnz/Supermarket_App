from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import (
    get_current_staff,
    require_approved_chain,
    require_approved_manager,
    require_manager,
    require_owner,
)
from app.main import app
from app.schemas.auth import CurrentStaff

from .conftest import NO_ROW, FakeResult, chain_mock, table_router

client = TestClient(app)

CHAIN_ID = uuid4()
STORE_ID = uuid4()

STAFF_DEPS = (
    get_current_staff,
    require_manager,
    require_owner,
    require_approved_chain,
    require_approved_manager,
)


def _staff(role="owner", chain_status="approved", chain_id=None):
    return CurrentStaff(
        id=uuid4(),
        email="owner@super.com",
        chain_id=chain_id or CHAIN_ID,
        supermarket_id=STORE_ID,
        role=role,
        chain_status=chain_status,
    )


@pytest.fixture
def staff_override():
    """
    Sobreescribe TODAS las dependencias de staff con el mismo usuario. Hay que
    cubrir require_approved_chain y require_approved_manager ademas de las
    otras tres porque FastAPI resuelve cada una por separado, no a traves de
    las demas: si falta una, el endpoint que la usa sigue pegandole a Supabase.
    """
    def _apply(current):
        for dep in STAFF_DEPS:
            app.dependency_overrides[dep] = lambda c=current: c
        return current

    yield _apply

    for dep in STAFF_DEPS:
        app.dependency_overrides.pop(dep, None)


def _store_row(chain_id=None):
    return {
        "id": str(STORE_ID),
        "chain_id": str(chain_id or CHAIN_ID),
        "name": "SurMarket Centro",
        "address": "Av. Siempreviva 742, CABA",
        "street": "Av. Siempreviva 742",
        "city": "CABA",
        "province": "CABA",
        "postal_code": "1414",
        "phone": None,
        "is_active": True,
        "logo_url": None,
    }


def _product_row(product_id=None, name="Leche entera 1L", ean="7790001000017"):
    return {
        "id": str(product_id or uuid4()),
        "name": name,
        "ean": ean,
        "brand": None,
        "unit": "L",
        "size_value": None,
        "size_unit": None,
        "category": "lacteos",
        "image_url": None,
        "created_at": "2026-08-21T10:00:00Z",
        "updated_at": "2026-08-21T10:00:00Z",
        "created_by_chain_id": None,
    }


def _listing_row(listing_id, product, chain_id=None, price=125000):
    return {
        "id": str(listing_id),
        "supermarket_id": str(STORE_ID),
        "product_id": product["id"],
        "price": price,
        "currency": "ARS",
        "in_stock": True,
        "updated_at": "2026-08-21T10:00:00Z",
        "products": product,
        "supermarkets": _store_row(chain_id),
    }


# -- Resolucion de identidad del producto (el riesgo central del sprint) ----


def test_existing_ean_links_instead_of_duplicating(staff_override):
    """
    Si cada cadena crea su propia fila "Leche entera 1L", compare_list —que
    agrupa por product_id— ve dos productos que nunca se comparan entre si y el
    comparador queda vacio. El EAN es la clave de identidad: si ya existe, se
    vincula y NO se inserta nada en products.
    """
    staff_override(_staff())
    existing = _product_row()
    listing_id = uuid4()

    products_mock = chain_mock(FakeResult(data=existing))
    sp_mock = chain_mock(
        [
            FakeResult(data=[{"id": str(listing_id)}]),                  # el INSERT del precio
            FakeResult(data=_listing_row(listing_id, existing)),          # la relectura
        ]
    )
    fake_client = MagicMock()
    fake_client.table.side_effect = table_router(
        {
            "supermarkets": chain_mock(FakeResult(data=_store_row())),
            "products": products_mock,
            "supermarket_products": sp_mock,
        }
    )

    with patch("app.services.supermarket_service.get_supabase", return_value=fake_client), \
         patch("app.services.catalog_service.get_supabase", return_value=fake_client), \
         patch("app.services.supermarket_product_service.get_supabase", return_value=fake_client):
        response = client.post(
            "/api/v1/supermarkets/me/products",
            json={
                "supermarket_id": str(STORE_ID),
                "price": 130000,
                "product": {"ean": "7790001000017", "name": "Leche Entera Larga Vida 1 Litro"},
            },
        )

    assert response.status_code == 201
    assert response.json()["product"]["id"] == existing["id"]
    # Lo decisivo: no se creo una fila paralela en el catalogo global.
    products_mock.insert.assert_not_called()


def test_new_ean_creates_the_global_product_with_its_chain(staff_override):
    """
    EAN nuevo: se crea la fila global y queda registrado quien la introdujo, que
    es lo que permite auditar el catalogo compartido (PLAN 5.2).
    """
    staff_override(_staff())
    created = _product_row(ean="7790009999998", name="Yerba mate 500g")
    listing_id = uuid4()

    products_mock = chain_mock(
        [
            NO_ROW,                          # el EAN no existe
            FakeResult(data=[created]),      # el INSERT
        ]
    )
    sp_mock = chain_mock(
        [
            FakeResult(data=[{"id": str(listing_id)}]),
            FakeResult(data=_listing_row(listing_id, created)),
        ]
    )
    fake_client = MagicMock()
    fake_client.table.side_effect = table_router(
        {
            "supermarkets": chain_mock(FakeResult(data=_store_row())),
            "products": products_mock,
            "supermarket_products": sp_mock,
        }
    )

    with patch("app.services.supermarket_service.get_supabase", return_value=fake_client), \
         patch("app.services.catalog_service.get_supabase", return_value=fake_client), \
         patch("app.services.supermarket_product_service.get_supabase", return_value=fake_client):
        response = client.post(
            "/api/v1/supermarkets/me/products",
            json={
                "supermarket_id": str(STORE_ID),
                "price": 480000,
                "product": {"ean": "7790009999998", "name": "Yerba mate 500g", "unit": "g"},
            },
        )

    assert response.status_code == 201
    inserted = products_mock.insert.call_args[0][0]
    assert inserted["ean"] == "7790009999998"
    assert inserted["created_by_chain_id"] == str(CHAIN_ID)


# -- Aislamiento entre cadenas ---------------------------------------------


def test_cannot_publish_a_price_in_another_chains_store(staff_override):
    """
    El supermarket_id llega del cliente. Sin comprobar que la sucursal es de la
    cadena del JWT, el staff de la cadena A publicaria precios en una sucursal
    de la B pasando su UUID (docs/SEGURIDAD.md 4.1). 404 y no 403 para no
    confirmar que la sucursal existe (4.3).
    """
    staff_override(_staff())

    fake_client = MagicMock()
    fake_client.table.side_effect = table_router({"supermarkets": chain_mock(NO_ROW)})

    with patch("app.services.supermarket_service.get_supabase", return_value=fake_client):
        response = client.post(
            "/api/v1/supermarkets/me/products",
            json={
                "supermarket_id": str(uuid4()),
                "price": 100000,
                "product": {"name": "Producto ajeno"},
            },
        )

    assert response.status_code == 404


def test_cannot_edit_a_price_of_another_chain(staff_override):
    """
    get_listing_or_404 compara la cadena de la sucursal embebida contra la del
    JWT. El backend usa service_role y bypasea RLS: esa comparacion es la unica
    barrera real.
    """
    staff_override(_staff())
    other_chain_listing = _listing_row(uuid4(), _product_row(), chain_id=uuid4())

    fake_client = MagicMock()
    fake_client.table.side_effect = table_router(
        {"supermarket_products": chain_mock(FakeResult(data=other_chain_listing))}
    )

    with patch("app.services.supermarket_product_service.get_supabase", return_value=fake_client):
        response = client.patch(
            f"/api/v1/supermarkets/me/products/{other_chain_listing['id']}",
            json={"price": 1},
        )

    assert response.status_code == 404


def test_list_my_products_only_queries_own_stores(staff_override):
    staff_override(_staff())
    sp_mock = chain_mock(FakeResult(data=[], count=0))

    fake_client = MagicMock()
    fake_client.table.side_effect = table_router(
        {
            "supermarkets": chain_mock(FakeResult(data=[{"id": str(STORE_ID)}])),
            "supermarket_products": sp_mock,
        }
    )

    with patch("app.services.supermarket_product_service.get_supabase", return_value=fake_client):
        response = client.get("/api/v1/supermarkets/me/products")

    assert response.status_code == 200
    sp_mock.in_.assert_called_once_with("supermarket_id", [str(STORE_ID)])


def test_list_my_products_is_empty_when_the_chain_has_no_stores(staff_override):
    staff_override(_staff())

    fake_client = MagicMock()
    fake_client.table.side_effect = table_router(
        {"supermarkets": chain_mock(FakeResult(data=[]))}
    )

    with patch("app.services.supermarket_product_service.get_supabase", return_value=fake_client):
        response = client.get("/api/v1/supermarkets/me/products")

    assert response.status_code == 200
    assert response.json() == {"data": [], "total": 0, "page": 1, "per_page": 20}


# -- Puertas de rol y de estado de la cadena -------------------------------


def test_staff_role_cannot_create_a_product():
    """
    La matriz de docs/SEGURIDAD.md 4.2 le da al rol 'staff' solo LECTURA sobre
    los precios de su cadena. 403 y no 404: tiene acceso legitimo al recurso,
    le falta el rol.
    """
    app.dependency_overrides[get_current_staff] = lambda: _staff(role="staff")
    try:
        response = client.post(
            "/api/v1/supermarkets/me/products",
            json={"supermarket_id": str(STORE_ID), "price": 100000,
                  "product": {"name": "Leche entera 1L"}},
        )
    finally:
        app.dependency_overrides.pop(get_current_staff, None)

    assert response.status_code == 403


def test_pending_chain_cannot_create_a_product():
    """
    Publicar precios es operar, y una cadena en revision no opera. Es el primer
    uso real de require_approved_chain, que estaba implementada y sin usar.
    """
    app.dependency_overrides[get_current_staff] = lambda: _staff(chain_status="pending_review")
    try:
        response = client.post(
            "/api/v1/supermarkets/me/products",
            json={"supermarket_id": str(STORE_ID), "price": 100000,
                  "product": {"name": "Leche entera 1L"}},
        )
    finally:
        app.dependency_overrides.pop(get_current_staff, None)

    assert response.status_code == 403


def test_pending_chain_cannot_even_read_its_products():
    app.dependency_overrides[get_current_staff] = lambda: _staff(
        role="staff", chain_status="suspended"
    )
    try:
        response = client.get("/api/v1/supermarkets/me/products")
    finally:
        app.dependency_overrides.pop(get_current_staff, None)

    assert response.status_code == 403


# -- Validacion de entrada -------------------------------------------------


def test_unit_outside_the_enum_is_rejected(staff_override):
    """
    products.unit es el enum product_unit {kg,g,L,ml,un}, no TEXT. Un valor
    fuera de la lista explota en Postgres con 22P02 y saldria como 500; el
    Literal del schema lo convierte en un 422 con el campo señalado.
    """
    staff_override(_staff())
    response = client.post(
        "/api/v1/supermarkets/me/products",
        json={"supermarket_id": str(STORE_ID), "price": 100000,
              "product": {"name": "Leche entera 1L", "unit": "litros"}},
    )
    assert response.status_code == 422


def test_malformed_ean_is_rejected(staff_override):
    """CHECK ean_format de la 016: 8 a 14 digitos."""
    staff_override(_staff())
    response = client.post(
        "/api/v1/supermarkets/me/products",
        json={"supermarket_id": str(STORE_ID), "price": 100000,
              "product": {"name": "Leche entera 1L", "ean": "77900-ABC"}},
    )
    assert response.status_code == 422


def test_price_must_be_a_positive_int(staff_override):
    """CHECK price_positive de la 009, y centavos como int (NORMAS 4.3)."""
    staff_override(_staff())
    response = client.post(
        "/api/v1/supermarkets/me/products",
        json={"supermarket_id": str(STORE_ID), "price": 0,
              "product": {"name": "Leche entera 1L"}},
    )
    assert response.status_code == 422


def test_product_and_product_id_are_mutually_exclusive(staff_override):
    """O se vincula a uno existente, o se propone uno nuevo. Nunca los dos."""
    staff_override(_staff())
    response = client.post(
        "/api/v1/supermarkets/me/products",
        json={
            "supermarket_id": str(STORE_ID),
            "price": 100000,
            "product_id": str(uuid4()),
            "product": {"name": "Leche entera 1L"},
        },
    )
    assert response.status_code == 422


def test_neither_product_nor_product_id_is_rejected(staff_override):
    staff_override(_staff())
    response = client.post(
        "/api/v1/supermarkets/me/products",
        json={"supermarket_id": str(STORE_ID), "price": 100000},
    )
    assert response.status_code == 422


def test_update_with_no_fields_is_rejected(staff_override):
    staff_override(_staff())
    response = client.patch(
        f"/api/v1/supermarkets/me/products/{uuid4()}", json={}
    )
    assert response.status_code == 422


# -- Lookup ----------------------------------------------------------------


def test_lookup_separates_the_exact_ean_match_from_the_name_candidates(staff_override):
    """
    El EAN es identidad; el nombre es parecido. El panel los trata distinto: el
    exacto es el camino rapido, los candidatos se eligen a mano. Por eso el
    exacto no se repite entre los candidatos.
    """
    staff_override(_staff())
    exact = _product_row(name="Leche entera 1L")
    similar = _product_row(name="Leche descremada 1L", ean="7790001000123")

    products_mock = chain_mock(
        [
            FakeResult(data=exact),                    # find_by_ean
            FakeResult(data=[exact, similar]),         # ilike por nombre
        ]
    )
    fake_client = MagicMock()
    fake_client.table.side_effect = table_router({"products": products_mock})

    with patch("app.services.catalog_service.get_supabase", return_value=fake_client):
        response = client.get(
            "/api/v1/supermarkets/me/products/lookup",
            params={"ean": "7790001000017", "q": "leche"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["exact_match"]["id"] == exact["id"]
    assert [c["id"] for c in body["candidates"]] == [similar["id"]]


def test_lookup_marks_products_already_listed_in_the_store(staff_override):
    """Evita el 409 evitable: el panel avisa antes de intentar el alta."""
    staff_override(_staff())
    listed = _product_row(name="Leche entera 1L")

    fake_client = MagicMock()
    fake_client.table.side_effect = table_router(
        {
            "supermarkets": chain_mock(FakeResult(data=_store_row())),
            "products": chain_mock([FakeResult(data=listed)]),
            "supermarket_products": chain_mock(
                FakeResult(data=[{"product_id": listed["id"]}])
            ),
        }
    )

    with patch("app.services.supermarket_service.get_supabase", return_value=fake_client), \
         patch("app.services.catalog_service.get_supabase", return_value=fake_client):
        response = client.get(
            "/api/v1/supermarkets/me/products/lookup",
            params={"ean": "7790001000017", "supermarket_id": str(STORE_ID)},
        )

    assert response.status_code == 200
    assert response.json()["exact_match"]["already_listed"] is True


# -- Conflicto de alta duplicada -------------------------------------------


def test_listing_the_same_product_twice_is_a_409(staff_override):
    """
    UNIQUE(supermarket_id, product_id) de la 003. Es un conflicto del cliente,
    no un fallo del servidor: para cambiar el precio esta el PATCH.
    """
    staff_override(_staff())
    existing = _product_row()

    sp_mock = chain_mock(FakeResult(data=[]))
    sp_mock.execute.side_effect = Exception("duplicate key value violates unique constraint")

    fake_client = MagicMock()
    fake_client.table.side_effect = table_router(
        {
            "supermarkets": chain_mock(FakeResult(data=_store_row())),
            "products": chain_mock(FakeResult(data=existing)),
            "supermarket_products": sp_mock,
        }
    )

    with patch("app.services.supermarket_service.get_supabase", return_value=fake_client), \
         patch("app.services.catalog_service.get_supabase", return_value=fake_client), \
         patch("app.services.supermarket_product_service.get_supabase", return_value=fake_client):
        response = client.post(
            "/api/v1/supermarkets/me/products",
            json={
                "supermarket_id": str(STORE_ID),
                "price": 130000,
                "product": {"ean": "7790001000017", "name": "Leche entera 1L"},
            },
        )

    assert response.status_code == 409
