from datetime import datetime

from pydantic import BaseModel, UUID4

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
