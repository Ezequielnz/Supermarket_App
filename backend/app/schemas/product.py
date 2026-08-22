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

    # Contexto de precio para la pantalla de explorar. Una lista de productos
    # sin precios no sirve para decidir qué comprar.
    #
    # `best_price` es el MÍNIMO entre supermercados visibles, no "el precio":
    # por eso la UI dice "desde $X". `available_in` cuenta en cuántos se
    # consigue, que es lo que dice si el producto es comparable o no.
    #
    # Ambos son null/0 cuando ningún supermercado visible lo vende — por
    # ejemplo si la única cadena que lo cargaba quedó suspendida. El producto
    # sigue en el catálogo global (es compartido), lo que desaparece es su
    # precio.
    best_price: int | None = None
    best_price_supermarket: SupermarketOut | None = None
    available_in: int = 0

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


class CategoryOut(BaseModel):
    name: str
    products_count: int


class CategoryListResponse(BaseModel):
    data: list[CategoryOut]
