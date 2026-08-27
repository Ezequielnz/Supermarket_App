from datetime import datetime

from pydantic import BaseModel, Field, UUID4

from app.schemas.product import SupermarketOut


class OrderCreate(BaseModel):
    list_id: UUID4
    supermarket_id: UUID4
    pickup_scheduled: datetime
    notes: str | None = None


class OrderResponse(BaseModel):
    id: UUID4
    status: str
    pickup_scheduled: datetime
    total_price: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderItemOut(BaseModel):
    product_id: UUID4
    product_name: str
    quantity: float
    unit_price: int
    subtotal: int


class OrderDetailResponse(OrderResponse):
    list_id: UUID4 | None
    supermarket: SupermarketOut
    notes: str | None
    items: list[OrderItemOut]


class OrderListResponse(BaseModel):
    data: list[OrderResponse]
    total: int
    page: int
    per_page: int


class OrderStatusResponse(BaseModel):
    id: UUID4
    status: str
    updated_at: datetime


class OrderCancelRequest(BaseModel):
    reason: str | None = None


# ── Compra dividida entre varios supermercados ────────────────────────────
# Un plan de GET /lists/{id}/compare/split se confirma como VARIOS pedidos, uno
# por supermercado. Ver ARQUITECTURA.md §9.1.


class SplitOrderGroupCreate(BaseModel):
    """Qué productos de la lista se compran en ESTE supermercado."""

    supermarket_id: UUID4
    product_ids: list[UUID4] = Field(min_length=1)


class SplitOrderCreate(BaseModel):
    """
    El plan completo. `groups` arranca en 2: comprar todo en un solo
    supermercado ya lo resuelve POST /orders, y tener dos caminos para el mismo
    pedido es la clase de bifurcación que se desincroniza sola.

    El precio no viaja en el request. Lo recalcula el backend contra los
    precios de hoy: aceptar el total que manda el cliente es dejar que el
    cliente elija cuánto paga.
    """

    list_id: UUID4
    pickup_scheduled: datetime
    notes: str | None = None
    groups: list[SplitOrderGroupCreate] = Field(min_length=2)


class SplitOrderResponse(BaseModel):
    """
    Los pedidos creados, uno por supermercado, con el total de la compra
    entera: es el número que el usuario venía mirando en el plan.
    """

    orders: list[OrderResponse]
    total_price: int
    supermarkets_count: int
