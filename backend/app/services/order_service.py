from uuid import UUID

from fastapi import HTTPException, status

from app.core.supabase_client import get_supabase
from app.schemas.order import (
    OrderCancelRequest,
    OrderCreate,
    OrderDetailResponse,
    OrderItemOut,
    OrderListResponse,
    OrderResponse,
    OrderStatusResponse,
    SplitOrderCreate,
    SplitOrderResponse,
)
from app.services.list_service import get_list_or_404
from app.services.product_service import is_supermarket_visible


def get_order_or_404(order_id: UUID, user_id: UUID) -> dict:
    """
    Igual que get_list_or_404: el backend usa service_role_key (bypasea RLS),
    así que el filtro .eq("user_id", user_id) es la única barrera real de
    autorización para este recurso.
    """
    client = get_supabase()
    result = (
        client.table("orders")
        .select("*")
        .eq("id", str(order_id))
        .eq("user_id", str(user_id))
        .maybe_single()
        .execute()
    )
    if result.data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado.")
    return result.data


def _visible_supermarket_or_404(client, supermarket_id: UUID) -> dict:
    """
    No alcanza con is_active: además la cadena tiene que estar aprobada. Sin
    esto, un supermercado en revisión (o suspendido) seguiría aceptando
    pedidos, porque el backend bypasea las policies de 015.
    """
    supermarket = (
        client.table("supermarkets")
        .select("*, chains(status)")
        .eq("id", str(supermarket_id))
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    if supermarket is None or supermarket.data is None or not is_supermarket_visible(supermarket.data):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supermercado no encontrado.")
    return supermarket.data


def _list_items_or_400(client, list_id: UUID) -> list[dict]:
    list_items = (
        client.table("shopping_list_items")
        .select("product_id, quantity")
        .eq("list_id", str(list_id))
        .execute()
    ).data
    if not list_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La lista no tiene productos.")
    return list_items


def _priced_items_or_409(client, supermarket_id: UUID, items: list[dict], detail: str) -> tuple[list[dict], int]:
    """
    Convierte items de la lista en items de pedido, a los precios de HOY, y
    devuelve también el total.

    El precio nunca viene del cliente ni del comparador: se relee acá. Entre
    que el usuario miró el plan y confirmó, el supermercado pudo cambiar el
    precio o quedarse sin stock.

    Si falta el precio de alguno, es 409 y no un pedido parcial: el usuario
    pidió una lista, no "lo que haya".
    """
    product_ids = [item["product_id"] for item in items]
    prices = (
        client.table("supermarket_products")
        .select("product_id, price, currency")
        .eq("supermarket_id", str(supermarket_id))
        .in_("product_id", product_ids)
        .eq("in_stock", True)
        .execute()
    ).data
    price_by_product = {row["product_id"]: row["price"] for row in prices}

    if len(price_by_product) != len(product_ids):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    items_payload = []
    total_price = 0
    for item in items:
        unit_price = price_by_product[item["product_id"]]
        # Redondeo POR ITEM, igual que el comparador: el total que promete la
        # comparación tiene que ser el que cobra el pedido.
        subtotal = round(unit_price * item["quantity"])
        total_price += subtotal
        items_payload.append(
            {
                "product_id": item["product_id"],
                "quantity": item["quantity"],
                "unit_price": unit_price,
                "subtotal": subtotal,
            }
        )
    return items_payload, total_price


def create_order(payload: OrderCreate, user_id: UUID) -> OrderResponse:
    client = get_supabase()

    get_list_or_404(payload.list_id, user_id)
    _visible_supermarket_or_404(client, payload.supermarket_id)
    list_items = _list_items_or_400(client, payload.list_id)

    items_payload, total_price = _priced_items_or_409(
        client,
        payload.supermarket_id,
        list_items,
        "El supermercado seleccionado no tiene stock de todos los productos de la lista.",
    )

    rpc_result = client.rpc(
        "create_order_with_items",
        {
            "p_user_id": str(user_id),
            "p_supermarket_id": str(payload.supermarket_id),
            "p_list_id": str(payload.list_id),
            "p_pickup_scheduled": payload.pickup_scheduled.isoformat(),
            "p_notes": payload.notes,
            "p_total_price": total_price,
            "p_items": items_payload,
        },
    ).execute()
    order_id = rpc_result.data

    order = client.table("orders").select("*").eq("id", order_id).single().execute()
    return OrderResponse.model_validate(order.data)


def create_split_order(payload: SplitOrderCreate, user_id: UUID) -> SplitOrderResponse:
    """
    Confirma un plan de compra dividida: un pedido por supermercado, todos en
    la misma transacción (RPC create_orders_with_items, migración 024).

    Se valida acá, no en la base:

    1. La lista es del usuario (get_list_or_404) y tiene productos.
    2. Ningún supermercado se repite. Dos grupos del mismo supermercado son dos
       pedidos al mismo lugar por la misma compra: es un plan mal armado, no
       una compra dividida.
    3. Los grupos cubren la lista entera, cada producto exactamente una vez. Un
       plan parcial dejaría productos sin comprar sin que el usuario se entere,
       y el mismo producto dos veces se lo cobraría dos veces.
    4. Cada supermercado es visible y tiene stock de lo que le tocó, a los
       precios de hoy.

    El total lo recalcula el backend: el request no trae precios.
    """
    client = get_supabase()

    get_list_or_404(payload.list_id, user_id)
    list_items = _list_items_or_400(client, payload.list_id)
    quantity_by_product = {item["product_id"]: item["quantity"] for item in list_items}

    supermarket_ids = [str(group.supermarket_id) for group in payload.groups]
    if len(set(supermarket_ids)) != len(supermarket_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El plan repite un supermercado. Cada supermercado va una sola vez.",
        )

    planned: list[str] = [
        str(product_id) for group in payload.groups for product_id in group.product_ids
    ]
    if len(set(planned)) != len(planned):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El plan asigna un mismo producto a más de un supermercado.",
        )
    if set(planned) != set(quantity_by_product):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El plan no cubre exactamente los productos de la lista.",
        )

    orders_payload = []
    total_price = 0
    for group in payload.groups:
        supermarket = _visible_supermarket_or_404(client, group.supermarket_id)
        items = [
            {"product_id": str(product_id), "quantity": quantity_by_product[str(product_id)]}
            for product_id in group.product_ids
        ]
        items_payload, group_total = _priced_items_or_409(
            client,
            group.supermarket_id,
            items,
            f"{supermarket['name']} ya no tiene stock de todos los productos que le asignaste.",
        )
        total_price += group_total
        orders_payload.append(
            {
                "supermarket_id": str(group.supermarket_id),
                "total_price": group_total,
                "items": items_payload,
            }
        )

    rpc_result = client.rpc(
        "create_orders_with_items",
        {
            "p_user_id": str(user_id),
            "p_list_id": str(payload.list_id),
            "p_pickup_scheduled": payload.pickup_scheduled.isoformat(),
            "p_notes": payload.notes,
            "p_orders": orders_payload,
        },
    ).execute()
    order_ids = rpc_result.data or []

    orders = (
        client.table("orders")
        .select("*")
        .in_("id", order_ids)
        .order("created_at")
        .execute()
    ).data

    return SplitOrderResponse(
        orders=[OrderResponse.model_validate(row) for row in orders],
        total_price=total_price,
        supermarkets_count=len(orders_payload),
    )


def list_orders(user_id: UUID, page: int, per_page: int) -> OrderListResponse:
    client = get_supabase()
    offset = (page - 1) * per_page

    result = (
        client.table("orders")
        .select("*", count="exact")
        .eq("user_id", str(user_id))
        .order("created_at", desc=True)
        .range(offset, offset + per_page - 1)
        .execute()
    )

    return OrderListResponse(
        data=[OrderResponse.model_validate(row) for row in result.data],
        total=result.count or 0,
        page=page,
        per_page=per_page,
    )


def get_order_detail(order_id: UUID, user_id: UUID) -> OrderDetailResponse:
    order = get_order_or_404(order_id, user_id)
    client = get_supabase()

    supermarket = (
        client.table("supermarkets")
        .select("*")
        .eq("id", order["supermarket_id"])
        .single()
        .execute()
    ).data

    items = (
        client.table("order_items")
        .select("*, products(name)")
        .eq("order_id", str(order_id))
        .execute()
    ).data

    return OrderDetailResponse(
        id=order["id"],
        status=order["status"],
        pickup_scheduled=order["pickup_scheduled"],
        total_price=order["total_price"],
        created_at=order["created_at"],
        list_id=order["list_id"],
        supermarket=supermarket,
        notes=order["notes"],
        items=[
            OrderItemOut(
                product_id=item["product_id"],
                product_name=item["products"]["name"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                subtotal=item["subtotal"],
            )
            for item in items
        ],
    )


def get_order_status(order_id: UUID, user_id: UUID) -> OrderStatusResponse:
    order = get_order_or_404(order_id, user_id)
    return OrderStatusResponse(id=order["id"], status=order["status"], updated_at=order["updated_at"])


def cancel_order(order_id: UUID, user_id: UUID, payload: OrderCancelRequest) -> OrderResponse:
    order = get_order_or_404(order_id, user_id)
    if order["status"] in ("completed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El pedido ya está en estado '{order['status']}' y no se puede cancelar.",
        )

    client = get_supabase()
    try:
        result = client.rpc(
            "cancel_order",
            {
                "p_order_id": str(order_id),
                "p_user_id": str(user_id),
                "p_note": payload.reason,
            },
        ).execute()
    except Exception as exc:
        # Igual que auth_service.py: supabase-py no expone un tipo de
        # excepción estable para errores de funciones RPC; se distingue por
        # el mensaje que la propia función Postgres levanta con RAISE EXCEPTION.
        message = str(exc).lower()
        if "order_not_found" in message:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado.")
        if "order_not_cancellable" in message:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El pedido ya no se puede cancelar.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="No se pudo cancelar el pedido.")

    return OrderResponse.model_validate(result.data)
