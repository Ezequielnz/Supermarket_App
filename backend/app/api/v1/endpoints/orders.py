from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.security import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.order import (
    OrderCancelRequest,
    OrderCreate,
    OrderDetailResponse,
    OrderListResponse,
    OrderResponse,
    OrderStatusResponse,
    SplitOrderCreate,
    SplitOrderResponse,
)
from app.services import order_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(payload: OrderCreate, current_user: CurrentUser = Depends(get_current_user)):
    """Crea un pedido a partir de una lista propia y un supermercado activo."""
    return order_service.create_order(payload, current_user.id)


@router.post("/split", response_model=SplitOrderResponse, status_code=status.HTTP_201_CREATED)
def create_split_order(payload: SplitOrderCreate, current_user: CurrentUser = Depends(get_current_user)):
    """
    Confirma un plan de compra dividida: crea un pedido por supermercado, todos
    en la misma transacción.

    Va declarado antes de las rutas /{order_id} por la misma razón que las del
    carrito en lists.py: FastAPI resuelve por orden de registro.
    """
    return order_service.create_split_order(payload, current_user.id)


@router.get("", response_model=OrderListResponse)
def get_orders(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Lista los pedidos del consumidor autenticado."""
    return order_service.list_orders(current_user.id, page, per_page)


@router.get("/{order_id}", response_model=OrderDetailResponse)
def get_order(order_id: UUID, current_user: CurrentUser = Depends(get_current_user)):
    """Devuelve el detalle de un pedido propio, con sus items y supermercado."""
    return order_service.get_order_detail(order_id, current_user.id)


@router.get("/{order_id}/status", response_model=OrderStatusResponse)
def get_order_status(order_id: UUID, current_user: CurrentUser = Depends(get_current_user)):
    """Devuelve el estado actual de un pedido propio (para polling desde el tracking)."""
    return order_service.get_order_status(order_id, current_user.id)


@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: UUID,
    payload: OrderCancelRequest = OrderCancelRequest(),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Cancela un pedido propio. No está listado textualmente en la tabla de
    endpoints de docs/ARQUITECTURA.md §6.3, pero está justificado por §7.2: la
    transición a 'cancelled' puede dispararla "Cualquiera", lo que incluye al
    consumidor dueño del pedido, no solo al supermercado.
    """
    return order_service.cancel_order(order_id, current_user.id, payload)
