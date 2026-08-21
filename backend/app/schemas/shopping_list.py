from datetime import datetime

from pydantic import BaseModel, Field, UUID4

from app.schemas.product import SupermarketOut


class ShoppingListCreate(BaseModel):
    name: str = Field(default="Mi lista", max_length=120)


class ShoppingListUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ShoppingListOut(BaseModel):
    id: UUID4
    name: str
    created_at: datetime
    updated_at: datetime
    items_count: int = 0

    model_config = {"from_attributes": True}


class ShoppingListListResponse(BaseModel):
    data: list[ShoppingListOut]
    total: int
    page: int
    per_page: int


class ShoppingListItemCreate(BaseModel):
    product_id: UUID4
    quantity: float = Field(default=1, gt=0)
    note: str | None = Field(default=None, max_length=250)


class ShoppingListItemOut(BaseModel):
    id: UUID4
    product_id: UUID4
    product_name: str
    quantity: float
    note: str | None


class ShoppingListDetailOut(BaseModel):
    id: UUID4
    name: str
    created_at: datetime
    updated_at: datetime
    items: list[ShoppingListItemOut]


class CompareItemOut(BaseModel):
    product_id: UUID4
    product_name: str
    price: int
    in_stock: bool


class CompareResultOut(BaseModel):
    supermarket: SupermarketOut
    total: int
    currency: str
    is_complete: bool
    items: list[CompareItemOut]


class CompareResponse(BaseModel):
    list_id: UUID4
    items_count: int
    results: list[CompareResultOut]
