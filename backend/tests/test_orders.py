from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import NO_ROW, FakeResult, chain_mock

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


# ── Compra dividida ───────────────────────────────────────────────────────
# Un plan de /lists/{id}/compare/split se confirma como VARIOS pedidos, uno por
# supermercado, en una sola transacción (migración 024).


def _order_row(order_id, total_price):
    return {
        "id": order_id, "status": "pending", "pickup_scheduled": _now(),
        "total_price": total_price, "created_at": _now(),
    }


def _supermarket_row(supermarket_id, name, status="approved"):
    return {
        "id": str(supermarket_id), "name": name, "address": None, "logo_url": None,
        "is_active": True, "chains": {"status": status},
    }


class _SplitClient:
    """
    Cliente falso con .rpc, como el de test_create_order_success. Guarda los
    parámetros de la RPC para poder revisar qué se mandó a persistir.
    """

    def __init__(self, tables, rpc_result):
        self._tables = tables
        self.rpc_calls = []
        self._rpc_mock = chain_mock(rpc_result)

    def table(self, name):
        return self._tables[name]

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        return self._rpc_mock


def _post_split(fake_client, payload):
    with patch("app.services.order_service.get_supabase", return_value=fake_client), \
         patch("app.services.list_service.get_supabase", return_value=fake_client):
        return client.post("/api/v1/orders/split", json=payload)


def _split_payload(list_id, groups):
    return {
        "list_id": str(list_id),
        "pickup_scheduled": "2026-08-25T10:00:00Z",
        "groups": groups,
    }


def _split_client(user_id, list_id, list_items, supermarket_rows, price_rows, order_rows=None):
    """
    supermarket_rows y price_rows son listas: una entrada por grupo, en el orden
    en que create_split_order recorre los grupos (side_effect de .execute()).
    """
    order_rows = order_rows if order_rows is not None else []
    return _SplitClient(
        {
            "shopping_lists": chain_mock(
                FakeResult(data={"id": str(list_id), "user_id": str(user_id), "name": "Mi lista",
                                 "created_at": _now(), "updated_at": _now()})
            ),
            "shopping_list_items": chain_mock(FakeResult(data=list_items)),
            "supermarkets": chain_mock([FakeResult(data=row) for row in supermarket_rows]),
            "supermarket_products": chain_mock([FakeResult(data=rows) for rows in price_rows]),
            "orders": chain_mock(FakeResult(data=order_rows)),
        },
        FakeResult(data=[row["id"] for row in order_rows]),
    )


def test_create_split_order_creates_one_order_per_supermarket(auth_override):
    """
    Cada grupo del plan se convierte en un pedido con SUS productos, y el total
    de la respuesta es el de la compra entera: es el número que el usuario venía
    mirando en el plan.
    """
    list_id = uuid4()
    vital, jaguar = uuid4(), uuid4()
    leche, pan = str(uuid4()), str(uuid4())
    order_vital, order_jaguar = str(uuid4()), str(uuid4())

    fake_client = _split_client(
        auth_override.id,
        list_id,
        [{"product_id": leche, "quantity": 2}, {"product_id": pan, "quantity": 1}],
        [_supermarket_row(vital, "Vital"), _supermarket_row(jaguar, "Jaguar")],
        [
            [{"product_id": leche, "price": 1000, "currency": "ARS"}],
            [{"product_id": pan, "price": 500, "currency": "ARS"}],
        ],
        [_order_row(order_vital, 2000), _order_row(order_jaguar, 500)],
    )

    response = _post_split(fake_client, _split_payload(list_id, [
        {"supermarket_id": str(vital), "product_ids": [leche]},
        {"supermarket_id": str(jaguar), "product_ids": [pan]},
    ]))

    assert response.status_code == 201
    body = response.json()
    assert body["supermarkets_count"] == 2
    assert body["total_price"] == 2500  # 1000 x 2 en Vital + 500 en Jaguar
    assert len(body["orders"]) == 2

    # Una sola llamada RPC: los N pedidos se escriben en una transacción, no en
    # N llamadas que pueden fallar por la mitad.
    assert len(fake_client.rpc_calls) == 1
    name, params = fake_client.rpc_calls[0]
    assert name == "create_orders_with_items"
    assert [order["total_price"] for order in params["p_orders"]] == [2000, 500]
    assert params["p_orders"][0]["items"] == [
        {"product_id": leche, "quantity": 2, "unit_price": 1000, "subtotal": 2000}
    ]


def test_create_split_order_rejects_a_plan_that_leaves_products_out(auth_override):
    """
    Un plan parcial dejaría productos sin comprar sin que el usuario se entere.
    409, igual que un supermercado único sin stock de toda la lista.
    """
    list_id = uuid4()
    vital, jaguar = uuid4(), uuid4()
    leche, pan, queso = str(uuid4()), str(uuid4()), str(uuid4())

    fake_client = _split_client(
        auth_override.id,
        list_id,
        [{"product_id": leche, "quantity": 1}, {"product_id": pan, "quantity": 1},
         {"product_id": queso, "quantity": 1}],
        [], [],
    )

    response = _post_split(fake_client, _split_payload(list_id, [
        {"supermarket_id": str(vital), "product_ids": [leche]},
        {"supermarket_id": str(jaguar), "product_ids": [pan]},
    ]))

    assert response.status_code == 409


def test_create_split_order_rejects_the_same_product_twice(auth_override):
    """El mismo producto en dos grupos se cobraría dos veces: 400."""
    list_id = uuid4()
    vital, jaguar = uuid4(), uuid4()
    leche = str(uuid4())

    fake_client = _split_client(
        auth_override.id, list_id, [{"product_id": leche, "quantity": 1}], [], [],
    )

    response = _post_split(fake_client, _split_payload(list_id, [
        {"supermarket_id": str(vital), "product_ids": [leche]},
        {"supermarket_id": str(jaguar), "product_ids": [leche]},
    ]))

    assert response.status_code == 400


def test_create_split_order_rejects_a_repeated_supermarket(auth_override):
    """
    Dos grupos del mismo supermercado son dos pedidos al mismo lugar por la
    misma compra: es un plan mal armado, no una compra dividida.
    """
    list_id = uuid4()
    vital = uuid4()
    leche, pan = str(uuid4()), str(uuid4())

    fake_client = _split_client(
        auth_override.id,
        list_id,
        [{"product_id": leche, "quantity": 1}, {"product_id": pan, "quantity": 1}],
        [], [],
    )

    response = _post_split(fake_client, _split_payload(list_id, [
        {"supermarket_id": str(vital), "product_ids": [leche]},
        {"supermarket_id": str(vital), "product_ids": [pan]},
    ]))

    assert response.status_code == 400


def test_create_split_order_is_409_when_a_supermarket_lost_stock(auth_override):
    """
    Entre que el usuario miró el plan y confirmó, un supermercado pudo quedarse
    sin stock. El precio se relee al confirmar: 409, no un pedido incompleto.
    """
    list_id = uuid4()
    vital, jaguar = uuid4(), uuid4()
    leche, pan = str(uuid4()), str(uuid4())

    fake_client = _split_client(
        auth_override.id,
        list_id,
        [{"product_id": leche, "quantity": 1}, {"product_id": pan, "quantity": 1}],
        [_supermarket_row(vital, "Vital"), _supermarket_row(jaguar, "Jaguar")],
        [[{"product_id": leche, "price": 1000, "currency": "ARS"}], []],
    )

    response = _post_split(fake_client, _split_payload(list_id, [
        {"supermarket_id": str(vital), "product_ids": [leche]},
        {"supermarket_id": str(jaguar), "product_ids": [pan]},
    ]))

    assert response.status_code == 409
    assert "Jaguar" in response.json()["detail"]
    assert fake_client.rpc_calls == []


def test_create_split_order_rejects_an_unapproved_chain(auth_override):
    """
    Mismo filtro que el pedido único: una cadena sin aprobar no recibe pedidos,
    tampoco como una de las paradas de un plan dividido.
    """
    list_id = uuid4()
    vital, trucho = uuid4(), uuid4()
    leche, pan = str(uuid4()), str(uuid4())

    fake_client = _split_client(
        auth_override.id,
        list_id,
        [{"product_id": leche, "quantity": 1}, {"product_id": pan, "quantity": 1}],
        [_supermarket_row(vital, "Vital"), _supermarket_row(trucho, "Trucho", status="pending_review")],
        [[{"product_id": leche, "price": 1000, "currency": "ARS"}], []],
    )

    response = _post_split(fake_client, _split_payload(list_id, [
        {"supermarket_id": str(vital), "product_ids": [leche]},
        {"supermarket_id": str(trucho), "product_ids": [pan]},
    ]))

    assert response.status_code == 404
    assert fake_client.rpc_calls == []


def test_create_split_order_needs_at_least_two_supermarkets(auth_override):
    """
    Con un solo grupo el pedido ya lo hace POST /orders. Tener dos caminos para
    el mismo pedido es la clase de bifurcación que se desincroniza sola: 422.
    """
    list_id = uuid4()
    vital = uuid4()
    leche = str(uuid4())

    fake_client = _split_client(
        auth_override.id, list_id, [{"product_id": leche, "quantity": 1}], [], [],
    )

    response = _post_split(fake_client, _split_payload(list_id, [
        {"supermarket_id": str(vital), "product_ids": [leche]},
    ]))

    assert response.status_code == 422


def test_create_split_order_of_another_users_list_is_404(auth_override):
    """Lista ajena: 404 antes de tocar precios ni supermercados."""
    list_id = uuid4()
    vital, jaguar = uuid4(), uuid4()
    leche, pan = str(uuid4()), str(uuid4())

    fake_client = _SplitClient(
        {"shopping_lists": chain_mock(NO_ROW)}, FakeResult(data=[]),
    )

    response = _post_split(fake_client, _split_payload(list_id, [
        {"supermarket_id": str(vital), "product_ids": [leche]},
        {"supermarket_id": str(jaguar), "product_ids": [pan]},
    ]))

    assert response.status_code == 404
    assert fake_client.rpc_calls == []
