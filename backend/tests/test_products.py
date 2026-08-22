from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import NO_ROW, FakeResult, chain_mock, table_router

client = TestClient(app)


def _product(name="Leche entera 1L", **overrides):
    row = {
        "id": str(uuid4()),
        "name": name,
        "brand": None,
        "unit": "L",
        "category": "lácteos",
        "image_url": None,
    }
    row.update(overrides)
    return row


def _price_row(product_id, price, chain_status="approved", is_active=True, store_name="Vital"):
    """Fila de supermarket_products con el supermercado y su cadena embebidos,
    que es la forma en que la consulta real la trae."""
    return {
        "product_id": product_id,
        "price": price,
        "supermarkets": {
            "id": str(uuid4()),
            "name": store_name,
            "address": "Av. Siempreviva 742",
            "logo_url": None,
            "is_active": is_active,
            "chains": {"status": chain_status},
        },
    }


def test_search_products_requires_auth():
    response = client.get("/api/v1/products")
    assert response.status_code == 401  # sin Authorization header, HTTPBearer corta antes


def test_search_products_success(auth_override):
    product = _product()
    tables = {
        "products": chain_mock(FakeResult(data=[product], count=1)),
        "supermarket_products": chain_mock(FakeResult(data=[])),
    }
    fake_client = type("Client", (), {"table": lambda self, name: table_router(tables)(name)})()

    with patch("app.services.product_service.get_supabase", return_value=fake_client):
        response = client.get("/api/v1/products", params={"q": "leche"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["data"][0]["name"] == "Leche entera 1L"


def test_search_products_returns_best_price_and_availability(auth_override):
    """
    El "desde $X" de la pantalla de explorar es el MÍNIMO entre supermercados,
    y available_in dice en cuántos se consigue — que es lo que comunica si el
    producto es comparable o si está en uno solo.
    """
    product = _product()
    pid = product["id"]
    tables = {
        "products": chain_mock(FakeResult(data=[product], count=1)),
        "supermarket_products": chain_mock(
            FakeResult(
                data=[
                    _price_row(pid, 145000, store_name="Carrefour"),
                    _price_row(pid, 125000, store_name="Vital"),
                    _price_row(pid, 133000, store_name="Jaguar"),
                ]
            )
        ),
    }
    fake_client = type("Client", (), {"table": lambda self, name: table_router(tables)(name)})()

    with patch("app.services.product_service.get_supabase", return_value=fake_client):
        response = client.get("/api/v1/products")

    body = response.json()["data"][0]
    assert body["best_price"] == 125000
    assert body["best_price_supermarket"]["name"] == "Vital"
    assert body["available_in"] == 3


def test_search_products_hides_prices_of_unapproved_chains(auth_override):
    """
    El filtro de visibilidad está en Python porque el backend usa service_role
    y bypasea RLS: las policies de la 015 no descartan ninguna fila acá
    (docs/SEGURIDAD.md §5.1).

    El producto NO desaparece —`products` es un catálogo global compartido—,
    pero su precio sí: es la prueba de que suspender una cadena la saca del
    comparador.
    """
    product = _product()
    pid = product["id"]
    tables = {
        "products": chain_mock(FakeResult(data=[product], count=1)),
        "supermarket_products": chain_mock(
            FakeResult(
                data=[
                    _price_row(pid, 99000, chain_status="suspended"),
                    _price_row(pid, 98000, chain_status="pending_review"),
                    _price_row(pid, 97000, is_active=False),
                ]
            )
        ),
    }
    fake_client = type("Client", (), {"table": lambda self, name: table_router(tables)(name)})()

    with patch("app.services.product_service.get_supabase", return_value=fake_client):
        response = client.get("/api/v1/products")

    body = response.json()["data"][0]
    assert body["best_price"] is None
    assert body["best_price_supermarket"] is None
    assert body["available_in"] == 0


def test_search_products_sort_by_price_puts_priceless_last(auth_override):
    """"desde —" no compite con un precio real: va al final de la lista."""
    cheap, pricey, none_ = _product("Pan"), _product("Leche"), _product("Manteca")
    tables = {
        "products": chain_mock(FakeResult(data=[none_, pricey, cheap], count=3)),
        "supermarket_products": chain_mock(
            FakeResult(
                data=[_price_row(cheap["id"], 105000), _price_row(pricey["id"], 125000)]
            )
        ),
    }
    fake_client = type("Client", (), {"table": lambda self, name: table_router(tables)(name)})()

    with patch("app.services.product_service.get_supabase", return_value=fake_client):
        response = client.get("/api/v1/products", params={"sort": "price"})

    names = [p["name"] for p in response.json()["data"]]
    assert names == ["Pan", "Leche", "Manteca"]


def test_search_products_rejects_unknown_sort(auth_override):
    response = client.get("/api/v1/products", params={"sort": "precio_descendente"})
    assert response.status_code == 422


def test_list_categories(auth_override):
    products_mock = chain_mock(
        FakeResult(
            data=[
                {"category": "lácteos"},
                {"category": "lácteos"},
                {"category": "almacén"},
            ]
        )
    )
    fake_client = type("Client", (), {"table": lambda self, name: products_mock})()

    with patch("app.services.product_service.get_supabase", return_value=fake_client):
        response = client.get("/api/v1/products/categories")

    assert response.status_code == 200
    assert response.json()["data"] == [
        {"name": "almacén", "products_count": 1},
        {"name": "lácteos", "products_count": 2},
    ]


def test_get_prices_not_found(auth_override):
    product_id = uuid4()
    products_mock = chain_mock(NO_ROW)
    fake_client = type("Client", (), {"table": lambda self, name: products_mock})()

    with patch("app.services.product_service.get_supabase", return_value=fake_client):
        response = client.get(f"/api/v1/products/{product_id}/prices")

    assert response.status_code == 404
