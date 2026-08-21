from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import FakeResult, chain_mock, table_router

client = TestClient(app)


def test_search_products_requires_auth():
    response = client.get("/api/v1/products")
    assert response.status_code == 401  # sin Authorization header, HTTPBearer corta antes


def test_search_products_success(auth_override):
    products_mock = chain_mock(
        FakeResult(data=[{"id": str(uuid4()), "name": "Leche entera 1L", "brand": None,
                          "unit": "L", "category": "lácteos", "image_url": None}], count=1)
    )
    fake_client = type("Client", (), {"table": lambda self, name: products_mock})()

    with patch("app.services.product_service.get_supabase", return_value=fake_client):
        response = client.get("/api/v1/products", params={"q": "leche"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["data"][0]["name"] == "Leche entera 1L"


def test_get_prices_not_found(auth_override):
    product_id = uuid4()
    products_mock = chain_mock(FakeResult(data=None))
    fake_client = type("Client", (), {"table": lambda self, name: products_mock})()

    with patch("app.services.product_service.get_supabase", return_value=fake_client):
        response = client.get(f"/api/v1/products/{product_id}/prices")

    assert response.status_code == 404
