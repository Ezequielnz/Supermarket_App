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


def create_order(payload: OrderCreate, user_id: UUID) -> OrderResponse:
    client = get_supabase()

    get_list_or_404(payload.list_id, user_id)

    # No alcanza con is_active: además la cadena tiene que estar aprobada. Sin
    # esto, un supermercado en revisión (o suspendido) seguiría aceptando
    # pedidos, porque el backend bypasea las policies de 015.
    supermarket = (
        client.table("supermarkets")
        .select("*, chains(status)")
        .eq("id", str(payload.supermarket_id))
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    if supermarket is None or supermarket.data is None or not is_supermarket_visible(supermarket.data):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supermercado no encontrado.")

    list_items = (
        client.table("shopping_list_items")
        .select("product_id, quantity")
        .eq("list_id", str(payload.list_id))
        .execute()
    ).data
    if not list_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La lista no tiene productos.")

    product_ids = [item["product_id"] for item in list_items]
    prices = (
        client.table("supermarket_products")
        .select("product_id, price, currency")
        .eq("supermarket_id", str(payload.supermarket_id))
        .in_("product_id", product_ids)
        .eq("in_stock", True)
        .execute()
    ).data
    price_by_product = {row["product_id"]: row["price"] for row in prices}

    if len(price_by_product) != len(product_ids):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El supermercado seleccionado no tiene stock de todos los productos de la lista.",
        )

    items_payload = []
    total_price = 0
    for item in list_items:
        unit_price = price_by_product[item["product_id"]]
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
