from datetime import datetime

from pydantic import BaseModel, UUID4


class SupermarketOut(BaseModel):
    id: UUID4
    name: str
    address: str | None
    logo_url: str | None

    model_config = {"from_attributes": True}


class ProductOut(BaseModel):
    id: UUID4
    name: str
    brand: str | None
    unit: str | None
    category: str | None
    image_url: str | None

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    data: list[ProductOut]
    total: int
    page: int
    per_page: int


class ProductPriceOut(BaseModel):
    supermarket: SupermarketOut
    price: int
    currency: str
    in_stock: bool
    updated_at: datetime


class ProductPricesResponse(BaseModel):
    product_id: UUID4
    product_name: str
    prices: list[ProductPriceOut]
