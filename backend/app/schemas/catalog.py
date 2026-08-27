from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, UUID4, model_validator

from app.schemas.product import SupermarketOut

# Espeja el enum product_unit de la migración 008. `products.unit` y
# `products.size_unit` son de ese tipo, no TEXT: un valor fuera de la lista
# explota en Postgres con 22P02 y sale como 500. Se valida acá para que sea un
# 422 con el detalle del campo, como cualquier otra entrada (NORMAS.md §4.4).
ProductUnit = Literal["kg", "g", "L", "ml", "un"]

# CHECK ean_format de la 016: 8 a 14 dígitos.
EAN_PATTERN = r"^[0-9]{8,14}$"

# supermarket_products.currency es CHAR(3) con default 'ARS'. No se acepta del
# cliente: el proyecto opera en una sola moneda y dejarla elegir sería aceptar
# un precio cuya unidad decide quien lo carga.
DEFAULT_CURRENCY = "ARS"

# Tope de candidatos que devuelve el lookup por nombre. Suficiente para elegir,
# corto para no convertir el buscador en un volcado del catálogo ajeno.
LOOKUP_LIMIT = 10

# supermarket_products.stock_quantity es NUMERIC(10,2): el tope evita que un
# 999999999 se coma el CHECK con un error de rango de Postgres (que sale como
# 500) en vez de un 422 con el campo.
MAX_STOCK_QUANTITY = 99_999_999.99


class ProductDraft(BaseModel):
    """
    Un producto del catálogo GLOBAL, tal como lo propone un supermercado.

    Se llama draft y no Create porque puede no crear nada: si el EAN ya existe,
    catalog_service.resolve_product vincula con la fila que está y descarta el
    resto de estos campos. Ver docs/PLAN_CATALOGO_Y_CARRITO.md §5.1.
    """

    name: str = Field(min_length=1, max_length=200)
    ean: str | None = Field(default=None, pattern=EAN_PATTERN)
    brand: str | None = Field(default=None, max_length=120)
    unit: ProductUnit | None = None
    size_value: float | None = Field(default=None, gt=0)
    size_unit: ProductUnit | None = None
    category: str | None = Field(default=None, max_length=80)
    image_url: str | None = Field(default=None, max_length=500)


class SupermarketProductCreate(BaseModel):
    """
    Alta de un precio. O apunta a un producto global que ya existe
    (`product_id`), o propone uno (`product`). Exactamente uno de los dos.
    """

    supermarket_id: UUID4
    price: int = Field(gt=0, description="Centavos. Nunca float (NORMAS.md §4.3).")
    in_stock: bool = True
    # None = esta sucursal no lleva control unitario de este producto (granel).
    # Es distinto de 0, que significa "no queda ninguno" y lo saca de la venta.
    # Ver la migración 024.
    stock_quantity: float | None = Field(default=None, ge=0, le=MAX_STOCK_QUANTITY)
    product_id: UUID4 | None = None
    product: ProductDraft | None = None

    @model_validator(mode="after")
    def exactly_one_product_source(self):
        if (self.product_id is None) == (self.product is None):
            raise ValueError(
                "Enviá 'product_id' para vincular a un producto existente, o 'product' para crear uno nuevo."
            )
        return self


class SupermarketProductUpdate(BaseModel):
    """
    Solo precio y stock. El producto global no se edita desde acá: una cadena
    no puede alterar la fila de la que cuelgan los precios de sus competidores
    (docs/SEGURIDAD.md §4.2, PLAN §5.2).
    """

    price: int | None = Field(default=None, gt=0)
    in_stock: bool | None = None
    stock_quantity: float | None = Field(default=None, ge=0, le=MAX_STOCK_QUANTITY)

    @model_validator(mode="after")
    def at_least_one_field(self):
        # `model_fields_set` y no `is None`: mandar `stock_quantity: null` es una
        # orden legítima —"dejá de contar unidades de este producto"— y con la
        # comprobación por None sería indistinguible de no haberlo mandado.
        if not self.model_fields_set:
            raise ValueError("No hay campos para actualizar.")
        return self


class CatalogProductOut(BaseModel):
    """El producto global, sin datos de precio."""

    id: UUID4
    name: str
    ean: str | None = None
    brand: str | None = None
    unit: str | None = None
    size_value: float | None = None
    size_unit: str | None = None
    category: str | None = None
    image_url: str | None = None

    model_config = {"from_attributes": True}


class SupermarketProductOut(BaseModel):
    """Una fila del catálogo propio: el producto global más MI precio."""

    id: UUID4
    product: CatalogProductOut
    supermarket: SupermarketOut
    price: int
    currency: str
    in_stock: bool
    stock_quantity: float | None = None
    updated_at: datetime


class SupermarketProductListResponse(BaseModel):
    data: list[SupermarketProductOut]
    total: int
    page: int
    per_page: int


class ProductMatchOut(CatalogProductOut):
    """
    Candidato del lookup. `already_listed` evita el 409 evitable: si la cadena
    ya vende ese producto en esa sucursal, el panel lo dice antes de intentar
    el alta.
    """

    already_listed: bool = False


class ProductLookupResponse(BaseModel):
    """
    `exact_match` es la coincidencia por EAN, que es identidad y no parecido:
    el panel la trata como el camino rápido (solo pedir el precio).
    `candidates` son coincidencias por nombre, que el staff elige a mano —
    nunca se adivina (PLAN §5.1).
    """

    exact_match: ProductMatchOut | None = None
    candidates: list[ProductMatchOut] = Field(default_factory=list)
