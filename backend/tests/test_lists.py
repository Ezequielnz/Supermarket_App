from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import NO_ROW, FakeResult, chain_mock, table_router

client = TestClient(app)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _list_row(list_id, user_id, is_cart=False, name="Mi lista"):
    return {
        "id": str(list_id), "user_id": str(user_id), "name": name,
        "is_cart": is_cart, "created_at": _now(), "updated_at": _now(),
    }


def _item_row(item_id, product_id, quantity, note=None):
    return {
        "id": str(item_id), "product_id": str(product_id),
        "quantity": quantity, "note": note,
    }


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

    NO_ROW y no FakeResult(data=None): .maybe_single() devuelve None entero
    cuando no hay fila. Con un FakeResult el test pasaba aunque el servicio
    reventara con AttributeError contra la base real — que es exactamente el
    500-en-vez-de-404 que este test cree estar cubriendo.
    """
    other_list_id = uuid4()
    lists_mock = chain_mock(NO_ROW)
    fake_client = type("Client", (), {"table": lambda self, name: lists_mock})()

    with patch("app.services.list_service.get_supabase", return_value=fake_client):
        response = client.get(f"/api/v1/lists/{other_list_id}")

    assert response.status_code == 404


def test_add_item_product_not_found(auth_override):
    list_id = uuid4()
    tables = {
        "shopping_lists": chain_mock(FakeResult(data=_list_row(list_id, auth_override.id))),
        "products": chain_mock(NO_ROW),
    }
    fake_client = type("Client", (), {"table": lambda self, name: table_router(tables)(name)})()

    with patch("app.services.list_service.get_supabase", return_value=fake_client):
        response = client.post(
            f"/api/v1/lists/{list_id}/items",
            json={"product_id": str(uuid4()), "quantity": 2},
        )

    assert response.status_code == 404


# -- Idempotencia por producto (regresion de la migracion 009) --------------


def test_add_item_twice_sums_quantity(auth_override):
    """
    La 009 agrego UNIQUE (list_id, product_id) y add_item hacia un .insert()
    plano: el segundo agregado del mismo producto violaba el constraint y salia
    como 500. Agregar dos veces lo mismo es lo que hace un carrito todo el
    tiempo, asi que ahora suma en vez de fallar.
    """
    list_id, product_id, item_id = uuid4(), uuid4(), uuid4()
    items_mock = chain_mock(
        [
            FakeResult(data=_item_row(item_id, product_id, 1)),      # el que ya esta
            FakeResult(data=[_item_row(item_id, product_id, 3)]),    # el UPDATE
        ]
    )
    tables = {
        "shopping_lists": chain_mock(FakeResult(data=_list_row(list_id, auth_override.id))),
        "products": chain_mock(FakeResult(data={"name": "Leche entera 1L"})),
        "shopping_list_items": items_mock,
        # _item_out resuelve el mejor precio del producto para el "estimado
        # desde" del carrito. Sin precios visibles, best_price queda en null.
        "supermarket_products": chain_mock(FakeResult(data=[])),
    }
    fake_client = type("Client", (), {"table": lambda self, name: table_router(tables)(name)})()

    with patch("app.services.list_service.get_supabase", return_value=fake_client):
        response = client.post(
            f"/api/v1/lists/{list_id}/items",
            json={"product_id": str(product_id), "quantity": 2},
        )

    assert response.status_code == 201
    assert response.json()["quantity"] == 3
    # Sumo sobre la fila existente; no intento un segundo INSERT.
    assert items_mock.update.call_args[0][0]["quantity"] == 3
    items_mock.insert.assert_not_called()


def test_add_item_first_time_inserts(auth_override):
    list_id, product_id, item_id = uuid4(), uuid4(), uuid4()
    items_mock = chain_mock(
        [
            NO_ROW,                                                 # no esta todavia
            FakeResult(data=[_item_row(item_id, product_id, 2)]),    # el INSERT
        ]
    )
    tables = {
        "shopping_lists": chain_mock(FakeResult(data=_list_row(list_id, auth_override.id))),
        "products": chain_mock(FakeResult(data={"name": "Leche entera 1L"})),
        "shopping_list_items": items_mock,
        # _item_out resuelve el mejor precio del producto para el "estimado
        # desde" del carrito. Sin precios visibles, best_price queda en null.
        "supermarket_products": chain_mock(FakeResult(data=[])),
    }
    fake_client = type("Client", (), {"table": lambda self, name: table_router(tables)(name)})()

    with patch("app.services.list_service.get_supabase", return_value=fake_client):
        response = client.post(
            f"/api/v1/lists/{list_id}/items",
            json={"product_id": str(product_id), "quantity": 2},
        )

    assert response.status_code == 201
    assert response.json()["quantity"] == 2
    items_mock.insert.assert_called_once()


# -- PATCH de cantidad ------------------------------------------------------


def test_patch_item_sets_quantity_without_summing(auth_override):
    """El control menos/mas del carrito FIJA la cantidad; sumar es add_item."""
    list_id, product_id, item_id = uuid4(), uuid4(), uuid4()
    items_mock = chain_mock(FakeResult(data=[_item_row(item_id, product_id, 5)]))
    tables = {
        "shopping_lists": chain_mock(FakeResult(data=_list_row(list_id, auth_override.id))),
        "products": chain_mock(FakeResult(data={"name": "Leche entera 1L"})),
        "shopping_list_items": items_mock,
        # _item_out resuelve el mejor precio del producto para el "estimado
        # desde" del carrito. Sin precios visibles, best_price queda en null.
        "supermarket_products": chain_mock(FakeResult(data=[])),
    }
    fake_client = type("Client", (), {"table": lambda self, name: table_router(tables)(name)})()

    with patch("app.services.list_service.get_supabase", return_value=fake_client):
        response = client.patch(
            f"/api/v1/lists/{list_id}/items/{item_id}", json={"quantity": 5}
        )

    assert response.status_code == 200
    assert response.json()["quantity"] == 5
    assert items_mock.update.call_args[0][0] == {"quantity": 5}


def test_patch_item_rejects_zero_quantity(auth_override):
    """
    gt=0 en el schema, espejando el CHECK list_item_quantity_positive (009).
    Para sacar el item esta DELETE, no una cantidad cero.
    """
    response = client.patch(
        f"/api/v1/lists/{uuid4()}/items/{uuid4()}", json={"quantity": 0}
    )
    assert response.status_code == 422


def test_patch_item_of_another_list_returns_404(auth_override):
    list_id, item_id = uuid4(), uuid4()
    tables = {
        "shopping_lists": chain_mock(FakeResult(data=_list_row(list_id, auth_override.id))),
        # El filtro por list_id no matchea: el item es de otra lista.
        "shopping_list_items": chain_mock(FakeResult(data=[])),
    }
    fake_client = type("Client", (), {"table": lambda self, name: table_router(tables)(name)})()

    with patch("app.services.list_service.get_supabase", return_value=fake_client):
        response = client.patch(
            f"/api/v1/lists/{list_id}/items/{item_id}", json={"quantity": 2}
        )

    assert response.status_code == 404


# -- Carrito ----------------------------------------------------------------


def test_get_cart_creates_it_when_missing(auth_override):
    """El consumidor nunca crea el carrito a mano: aparece solo."""
    cart_id = uuid4()
    cart = _list_row(cart_id, auth_override.id, is_cart=True, name="Mi carrito")
    lists_mock = chain_mock(
        [
            NO_ROW,                    # todavia no hay carrito
            FakeResult(data=[cart]),   # el INSERT
            FakeResult(data=cart),     # la relectura de get_list_detail
        ]
    )
    tables = {
        "shopping_lists": lists_mock,
        "shopping_list_items": chain_mock(FakeResult(data=[])),
    }
    fake_client = type("Client", (), {"table": lambda self, name: table_router(tables)(name)})()

    with patch("app.services.list_service.get_supabase", return_value=fake_client):
        response = client.get("/api/v1/lists/cart")

    assert response.status_code == 200
    body = response.json()
    assert body["is_cart"] is True
    assert body["name"] == "Mi carrito"
    assert lists_mock.insert.call_args[0][0]["is_cart"] is True


def test_get_cart_reuses_the_existing_one(auth_override):
    """Indice unico parcial idx_one_cart_per_user: uno solo por usuario."""
    cart_id = uuid4()
    lists_mock = chain_mock(
        FakeResult(data=_list_row(cart_id, auth_override.id, is_cart=True, name="Mi carrito"))
    )
    tables = {
        "shopping_lists": lists_mock,
        "shopping_list_items": chain_mock(FakeResult(data=[])),
    }
    fake_client = type("Client", (), {"table": lambda self, name: table_router(tables)(name)})()

    with patch("app.services.list_service.get_supabase", return_value=fake_client):
        response = client.get("/api/v1/lists/cart")

    assert response.status_code == 200
    assert response.json()["id"] == str(cart_id)
    lists_mock.insert.assert_not_called()


def test_cart_route_is_not_parsed_as_a_uuid(auth_override):
    """
    /lists/cart va declarada ANTES de /lists/{list_id}. Si se invirtiera el
    orden, FastAPI intentaria parsear "cart" como UUID y devolveria 422.
    """
    lists_mock = chain_mock(
        FakeResult(data=_list_row(uuid4(), auth_override.id, is_cart=True))
    )
    tables = {
        "shopping_lists": lists_mock,
        "shopping_list_items": chain_mock(FakeResult(data=[])),
    }
    fake_client = type("Client", (), {"table": lambda self, name: table_router(tables)(name)})()

    with patch("app.services.list_service.get_supabase", return_value=fake_client):
        response = client.get("/api/v1/lists/cart")

    assert response.status_code != 422


def test_save_cart_clears_the_flag(auth_override):
    """
    Guardar el carrito lo pasa a is_cart = false: queda como lista normal y el
    proximo agregado abre uno nuevo, porque get_or_create_cart ya no encuentra
    ninguno con el flag puesto.
    """
    cart_id = uuid4()
    saved = _list_row(cart_id, auth_override.id, is_cart=False, name="Compra del sabado")
    lists_mock = chain_mock(
        [
            FakeResult(data=_list_row(cart_id, auth_override.id, is_cart=True)),  # el carrito
            FakeResult(data=[saved]),                                             # el UPDATE
        ]
    )
    tables = {
        "shopping_lists": lists_mock,
        "shopping_list_items": chain_mock(FakeResult(data=[], count=3)),
    }
    fake_client = type("Client", (), {"table": lambda self, name: table_router(tables)(name)})()

    with patch("app.services.list_service.get_supabase", return_value=fake_client):
        response = client.post("/api/v1/lists/cart/save", json={"name": "Compra del sabado"})

    assert response.status_code == 200
    body = response.json()
    assert body["is_cart"] is False
    assert body["name"] == "Compra del sabado"
    assert lists_mock.update.call_args[0][0]["is_cart"] is False


def test_get_lists_excludes_the_cart(auth_override):
    """
    El carrito es una fila de shopping_lists, pero no se mezcla entre "Mis
    listas": se llega a el por /lists/cart.
    """
    lists_mock = chain_mock(FakeResult(data=[], count=0))
    fake_client = type("Client", (), {"table": lambda self, name: lists_mock})()

    with patch("app.services.list_service.get_supabase", return_value=fake_client):
        response = client.get("/api/v1/lists")

    assert response.status_code == 200
    lists_mock.eq.assert_any_call("is_cart", False)


# ── Comparador ────────────────────────────────────────────────────────────
# compare_list atraviesa dos servicios: get_list_or_404 vive en list_service y
# el resto en comparison_service. Como el patch es por modulo, hay que parchear
# los dos o la validacion de ownership le pega a Supabase de verdad.


def _supermarket(sm_id, name, status="approved", is_active=True):
    return {
        "id": str(sm_id), "name": name, "address": "Av. Siempreviva 742",
        "logo_url": None, "is_active": is_active, "chains": {"status": status},
    }


def _price_row(product_id, supermarket, price, in_stock=True):
    return {
        "id": str(uuid4()), "product_id": str(product_id), "price": price,
        "currency": "ARS", "in_stock": in_stock, "supermarkets": supermarket,
    }


def _compare_client(list_row, item_rows, price_rows):
    """Arma el cliente falso que comparten los tests del comparador."""
    lists_mock = chain_mock(FakeResult(data=list_row))
    tables = {
        "shopping_lists": lists_mock,
        "shopping_list_items": chain_mock(FakeResult(data=item_rows)),
        "supermarket_products": chain_mock(FakeResult(data=price_rows)),
    }
    return type("Client", (), {"table": lambda self, name: table_router(tables)(name)})()


def _compare(fake_client, list_id):
    with patch("app.services.list_service.get_supabase", return_value=fake_client), \
         patch("app.services.comparison_service.get_supabase", return_value=fake_client):
        return client.get(f"/api/v1/lists/{list_id}/compare")


def test_compare_names_the_missing_products(auth_override):
    """
    is_complete = False dice QUE faltan productos; `missing` dice CUALES. Sin
    los nombres, el usuario no puede decidir si igual le conviene ese super.
    """
    list_id, leche, pan = uuid4(), uuid4(), uuid4()
    completo = _supermarket(uuid4(), "Carrefour")
    parcial = _supermarket(uuid4(), "Jaguar")

    fake_client = _compare_client(
        _list_row(list_id, auth_override.id),
        [
            {"product_id": str(leche), "quantity": 1, "products": {"name": "Leche"}},
            {"product_id": str(pan), "quantity": 1, "products": {"name": "Pan"}},
        ],
        [
            _price_row(leche, completo, 100000),
            _price_row(pan, completo, 50000),
            _price_row(leche, parcial, 90000),  # a Jaguar le falta el pan
        ],
    )

    response = _compare(fake_client, list_id)

    assert response.status_code == 200
    body = response.json()
    assert body["generated_at"] is not None
    by_name = {r["supermarket"]["name"]: r for r in body["results"]}

    assert by_name["Carrefour"]["is_complete"] is True
    assert by_name["Carrefour"]["items_covered"] == 2
    assert by_name["Carrefour"]["items_total"] == 2
    assert by_name["Carrefour"]["missing"] == []

    assert by_name["Jaguar"]["is_complete"] is False
    assert by_name["Jaguar"]["items_covered"] == 1
    assert by_name["Jaguar"]["items_total"] == 2
    assert [m["product_name"] for m in by_name["Jaguar"]["missing"]] == ["Pan"]


def test_compare_puts_complete_supermarkets_before_cheaper_partial_ones(auth_override):
    """
    Un total parcial no es comparable con uno completo. Ordenar todo junto por
    precio pondria arriba al super al que le falta la mitad de la lista, que es
    exactamente el dato equivocado.
    """
    list_id, leche, pan = uuid4(), uuid4(), uuid4()
    caro_completo = _supermarket(uuid4(), "Vital")
    barato_parcial = _supermarket(uuid4(), "Jaguar")

    fake_client = _compare_client(
        _list_row(list_id, auth_override.id),
        [
            {"product_id": str(leche), "quantity": 1, "products": {"name": "Leche"}},
            {"product_id": str(pan), "quantity": 1, "products": {"name": "Pan"}},
        ],
        [
            _price_row(leche, caro_completo, 100000),
            _price_row(pan, caro_completo, 50000),   # total 150000
            _price_row(leche, barato_parcial, 10000),  # total parcial 10000
        ],
    )

    body = _compare(fake_client, list_id).json()

    assert [r["supermarket"]["name"] for r in body["results"]] == ["Vital", "Jaguar"]
    assert body["results"][0]["total"] == 150000
    assert body["results"][1]["total"] == 10000


def test_compare_rounds_per_item_like_the_order_does(auth_override):
    """
    order_service calcula subtotal = round(unit_price * quantity) POR ITEM. Si
    el comparador redondea una sola vez sobre la suma, promete un total y el
    pedido cobra otro.

    Dos items a 0.5 x 12345: por item da round(6172.5) * 2 = 12344 (banker's
    rounding), sobre la suma daria round(12345.0) = 12345.
    """
    list_id, a, b = uuid4(), uuid4(), uuid4()
    supermercado = _supermarket(uuid4(), "Carrefour")

    fake_client = _compare_client(
        _list_row(list_id, auth_override.id),
        [
            {"product_id": str(a), "quantity": 0.5, "products": {"name": "Queso"}},
            {"product_id": str(b), "quantity": 0.5, "products": {"name": "Jamon"}},
        ],
        [_price_row(a, supermercado, 12345), _price_row(b, supermercado, 12345)],
    )

    body = _compare(fake_client, list_id).json()

    esperado = round(12345 * 0.5) + round(12345 * 0.5)
    assert body["results"][0]["total"] == esperado


def test_compare_hides_supermarkets_of_unapproved_chains(auth_override):
    """
    El backend usa service_role y bypasea RLS, asi que las policies de la 015
    no descartan ni una fila: el filtro de is_supermarket_visible es la unica
    barrera. Una cadena sin aprobar no puede colarse al comparador.
    """
    list_id, leche = uuid4(), uuid4()
    aprobado = _supermarket(uuid4(), "Carrefour")
    sin_aprobar = _supermarket(uuid4(), "Trucho", status="pending_review")
    inactivo = _supermarket(uuid4(), "Cerrado", is_active=False)

    fake_client = _compare_client(
        _list_row(list_id, auth_override.id),
        [{"product_id": str(leche), "quantity": 1, "products": {"name": "Leche"}}],
        [
            _price_row(leche, aprobado, 100000),
            _price_row(leche, sin_aprobar, 1),
            _price_row(leche, inactivo, 2),
        ],
    )

    body = _compare(fake_client, list_id).json()

    assert [r["supermarket"]["name"] for r in body["results"]] == ["Carrefour"]


def test_compare_of_empty_list_still_reports_generated_at(auth_override):
    """Lista sin productos: no hay nada que comparar, pero la respuesta es valida."""
    list_id = uuid4()
    fake_client = _compare_client(_list_row(list_id, auth_override.id), [], [])

    response = _compare(fake_client, list_id)

    assert response.status_code == 200
    body = response.json()
    assert body["items_count"] == 0
    assert body["results"] == []
    assert body["generated_at"] is not None


def test_compare_of_another_users_list_is_404(auth_override):
    """Lista ajena: 404, no 403 — no se revela que el recurso existe."""
    list_id = uuid4()
    fake_client = _compare_client(NO_ROW, [], [])

    assert _compare(fake_client, list_id).status_code == 404
