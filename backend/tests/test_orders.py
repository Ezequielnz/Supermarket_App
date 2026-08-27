from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
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
            FakeResult(data=[{"product_id": product_id, "price": 1000, "currency": "ARS",
                              "stock_quantity": None}])
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


def _order_client(list_id, supermarket_id, listing_rows, auth_user, rpc=None):
    """Las cuatro consultas que hace create_order, con el precio y el stock que se le indiquen."""
    tables = {
        "shopping_lists": chain_mock(
            FakeResult(data={"id": str(list_id), "user_id": str(auth_user.id),
                              "name": "Mi lista", "created_at": _now(), "updated_at": _now()})
        ),
        "supermarkets": chain_mock(
            FakeResult(data={"id": str(supermarket_id), "name": "Vital", "address": None,
                              "logo_url": None, "is_active": True, "chains": {"status": "approved"}})
        ),
        "shopping_list_items": chain_mock(
            FakeResult(data=[{"product_id": row["product_id"], "quantity": 3} for row in listing_rows])
        ),
        "supermarket_products": chain_mock(FakeResult(data=listing_rows)),
        "orders": chain_mock(
            FakeResult(data={"id": str(uuid4()), "status": "pending", "pickup_scheduled": _now(),
                              "total_price": 3000, "created_at": _now()})
        ),
    }

    class FakeClient:
        def table(self, name):
            return tables[name]

        def rpc(self, name, params):
            if rpc is not None:
                return rpc
            return chain_mock(FakeResult(data=str(uuid4())))

    return FakeClient()


def _post_order(fake_client, list_id, supermarket_id):
    with patch("app.services.order_service.get_supabase", return_value=fake_client), \
         patch("app.services.list_service.get_supabase", return_value=fake_client):
        return client.post(
            "/api/v1/orders",
            json={
                "list_id": str(list_id),
                "supermarket_id": str(supermarket_id),
                "pickup_scheduled": "2026-08-25T10:00:00Z",
            },
        )


def test_create_order_rejects_when_there_are_not_enough_units(auth_override):
    """
    `in_stock = true` con 1 unidad no alcanza para un pedido de 3. Antes de la
    migración 024 este pedido se creaba igual y el faltante aparecía recién en
    el mostrador.
    """
    list_id, supermarket_id = uuid4(), uuid4()
    listing = {"product_id": str(uuid4()), "price": 1000, "currency": "ARS", "stock_quantity": 1}

    response = _post_order(
        _order_client(list_id, supermarket_id, [listing], auth_override), list_id, supermarket_id
    )

    assert response.status_code == 409


def test_products_without_unit_tracking_are_still_orderable(auth_override):
    """
    `stock_quantity = NULL` es el producto a granel: no se cuenta, alcanza con
    `in_stock`. Si el chequeo de unidades lo tratara como 0, la frutería
    quedaría sin poder vender.
    """
    list_id, supermarket_id = uuid4(), uuid4()
    listing = {"product_id": str(uuid4()), "price": 1000, "currency": "ARS", "stock_quantity": None}

    response = _post_order(
        _order_client(list_id, supermarket_id, [listing], auth_override), list_id, supermarket_id
    )

    assert response.status_code == 201


def test_stock_lost_in_a_race_comes_back_as_409_not_500(auth_override):
    """
    Entre la validación en Python y la transacción puede entrar otro pedido por
    las últimas unidades: ahí la que rechaza es la función de Postgres. Ese
    `insufficient_stock` es un conflicto del cliente, no un error del servidor.
    """
    list_id, supermarket_id = uuid4(), uuid4()
    listing = {"product_id": str(uuid4()), "price": 1000, "currency": "ARS", "stock_quantity": 50}

    failing_rpc = MagicMock()
    failing_rpc.execute.side_effect = Exception(
        '{"code":"P0001","message":"insufficient_stock"}'
    )

    response = _post_order(
        _order_client(list_id, supermarket_id, [listing], auth_override, rpc=failing_rpc),
        list_id,
        supermarket_id,
    )

    assert response.status_code == 409
