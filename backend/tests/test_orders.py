from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import FakeResult, chain_mock

client = TestClient(app)


def _now():
    return datetime.now(timezone.utc).isoformat()


def test_create_order_success(auth_override):
    list_id = uuid4()
    supermarket_id = uuid4()
    product_id = str(uuid4())
    order_id = str(uuid4())

    tables = {
        "shopping_lists": chain_mock(
            FakeResult(data={"id": str(list_id), "user_id": str(auth_override.id),
                              "name": "Mi lista", "created_at": _now(), "updated_at": _now()})
        ),
        "supermarkets": chain_mock(
            FakeResult(data={"id": str(supermarket_id), "name": "Vital",
                              "address": None, "logo_url": None, "is_active": True,
                              "chains": {"status": "approved"}})
        ),
        "shopping_list_items": chain_mock(
            FakeResult(data=[{"product_id": product_id, "quantity": 2}])
        ),
        "supermarket_products": chain_mock(
            FakeResult(data=[{"product_id": product_id, "price": 1000, "currency": "ARS"}])
        ),
        "orders": chain_mock(
            FakeResult(data={"id": order_id, "status": "pending", "pickup_scheduled": _now(),
                              "total_price": 2000, "created_at": _now()})
        ),
    }
    rpc_mock = chain_mock(FakeResult(data=order_id))

    class FakeClient:
        def table(self, name):
            return tables[name]

        def rpc(self, name, params):
            assert name == "create_order_with_items"
            return rpc_mock

    fake_client = FakeClient()

    with patch("app.services.order_service.get_supabase", return_value=fake_client), \
         patch("app.services.list_service.get_supabase", return_value=fake_client):
        response = client.post(
            "/api/v1/orders",
            json={
                "list_id": str(list_id),
                "supermarket_id": str(supermarket_id),
                "pickup_scheduled": "2026-08-25T10:00:00Z",
            },
        )

    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    assert response.json()["total_price"] == 2000


def test_create_order_incomplete_stock(auth_override):
    """
    Si el supermercado elegido no tiene stock de todos los productos de la
    lista, debe devolver 409 en vez de crear un pedido parcial.
    """
    list_id = uuid4()
    supermarket_id = uuid4()
    product_id = str(uuid4())

    tables = {
        "shopping_lists": chain_mock(
            FakeResult(data={"id": str(list_id), "user_id": str(auth_override.id),
                              "name": "Mi lista", "created_at": _now(), "updated_at": _now()})
        ),
        "supermarkets": chain_mock(
            FakeResult(data={"id": str(supermarket_id), "name": "Jaguar",
                              "address": None, "logo_url": None, "is_active": True,
                              "chains": {"status": "approved"}})
        ),
        "shopping_list_items": chain_mock(
            FakeResult(data=[{"product_id": product_id, "quantity": 1}])
        ),
        "supermarket_products": chain_mock(FakeResult(data=[])),  # sin stock
    }

    class FakeClient:
        def table(self, name):
            return tables[name]

    fake_client = FakeClient()

    with patch("app.services.order_service.get_supabase", return_value=fake_client), \
         patch("app.services.list_service.get_supabase", return_value=fake_client):
        response = client.post(
            "/api/v1/orders",
            json={
                "list_id": str(list_id),
                "supermarket_id": str(supermarket_id),
                "pickup_scheduled": "2026-08-25T10:00:00Z",
            },
        )

    assert response.status_code == 409


def test_cancel_order_already_cancelled(auth_override):
    order_id = uuid4()
    orders_mock = chain_mock(
        FakeResult(data={"id": str(order_id), "user_id": str(auth_override.id), "status": "cancelled"})
    )
    fake_client = type("Client", (), {"table": lambda self, name: orders_mock})()

    with patch("app.services.order_service.get_supabase", return_value=fake_client):
        response = client.post(f"/api/v1/orders/{order_id}/cancel")

    assert response.status_code == 409


def test_get_order_not_found_for_other_user(auth_override):
    order_id = uuid4()
    orders_mock = chain_mock(FakeResult(data=None))
    fake_client = type("Client", (), {"table": lambda self, name: orders_mock})()

    with patch("app.services.order_service.get_supabase", return_value=fake_client):
        response = client.get(f"/api/v1/orders/{order_id}/status")

    assert response.status_code == 404
