from datetime import datetime

from pydantic import BaseModel, Field, UUID4

from app.schemas.product import SupermarketOut


class ShoppingListCreate(BaseModel):
    name: str = Field(default="Mi lista", max_length=120)


class ShoppingListUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class CartSaveRequest(BaseModel):
    """
    Guardar el carrito como lista. El nombre es opcional: si no viene, la lista
    conserva el que ya tenía ("Mi carrito").
    """

    name: str | None = Field(default=None, min_length=1, max_length=120)


class ShoppingListOut(BaseModel):
    id: UUID4
    name: str
    created_at: datetime
    updated_at: datetime
    items_count: int = 0
    # El carrito ES una lista con is_cart = true (docs/PLAN_CATALOGO_Y_CARRITO.md
    # §2.1). Se expone para que el front pueda distinguirlo de una lista guardada.
    is_cart: bool = False

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


class ShoppingListItemUpdate(BaseModel):
    """
    Fija la cantidad de un ítem, no la suma: es el control - / + del carrito.
    Para sacar el ítem está DELETE, no un quantity = 0 (de ahí el gt=0, que
    además espeja el CHECK list_item_quantity_positive de la migración 009).
    """

    quantity: float = Field(gt=0)


class ShoppingListItemOut(BaseModel):
    id: UUID4
    product_id: UUID4
    product_name: str
    quantity: float
    note: str | None
    # Mejor precio visible del producto, en centavos, o null si ningun
    # supermercado aprobado lo vende hoy. Es informativo: el total en firme
    # sale del comparador, cuando se elige donde comprar.
    best_price: int | None = None


class ShoppingListDetailOut(BaseModel):
    id: UUID4
    name: str
    created_at: datetime
    updated_at: datetime
    is_cart: bool = False
    items: list[ShoppingListItemOut]


class CompareItemOut(BaseModel):
    product_id: UUID4
    product_name: str
    price: int
    in_stock: bool


class CompareMissingItemOut(BaseModel):
    """
    Un producto de la lista que ESTE supermercado no vende (o tiene sin stock).
    Se nombra, no se cuenta nada más: "faltan 3" no le sirve a nadie para
    decidir si igual conviene comprar ahí.
    """

    product_id: UUID4
    product_name: str


class CompareResultOut(BaseModel):
    supermarket: SupermarketOut
    # Suma de los items que este supermercado SÍ tiene. Si is_complete es
    # False, es un total parcial: no es comparable con el de un supermercado
    # completo, y por eso los parciales van al final de results.
    total: int
    currency: str
    is_complete: bool
    items_covered: int
    items_total: int
    missing: list[CompareMissingItemOut] = []
    items: list[CompareItemOut]


class CompareResponse(BaseModel):
    list_id: UUID4
    items_count: int
    # Momento del cálculo. El front lo muestra ("actualizado hace X") y lo usa
    # para vencer su caché: la comparación se dispara sola al abrir la lista,
    # así que el usuario tiene que poder ver qué tan fresco es el número.
    generated_at: datetime
    results: list[CompareResultOut]


# ── Compra dividida entre varios supermercados ────────────────────────────
# El comparador de arriba responde "¿dónde compro TODO?". Estos schemas
# responden la otra pregunta: "¿y si compro cada cosa donde está más barata?".
# Ver docs/ARQUITECTURA.md §9.1.


class SplitPlanItemOut(BaseModel):
    """Un producto de la lista, asignado al supermercado que lo cubre."""

    product_id: UUID4
    product_name: str
    quantity: float
    price: int
    # round(price * quantity), igual que el comparador y que order_service:
    # el número que promete el plan tiene que ser el que cobra el pedido.
    subtotal: int


class SplitPlanGroupOut(BaseModel):
    """Todo lo que hay que comprar en UN supermercado del plan."""

    supermarket: SupermarketOut
    subtotal: int
    currency: str
    items: list[SplitPlanItemOut]


class SplitCompareResponse(BaseModel):
    list_id: UUID4
    items_count: int
    generated_at: datetime
    # El tope de supermercados que pidió el usuario, y cuántos usa el plan.
    # No siempre coinciden: si con dos alcanza para el mínimo, el plan no
    # inventa un tercer viaje para llenar el cupo.
    max_supermarkets: int
    supermarkets_count: int
    total: int
    # Null cuando no hay nada que comprar: la moneda sale de los precios, no se
    # inventa un default.
    currency: str | None = None
    is_complete: bool
    # Productos que el plan NO cubre: o no los vende ningún supermercado
    # visible, o no entran en el tope de supermercados elegido.
    missing: list[CompareMissingItemOut] = []
    # El mejor total de comprar TODO en un solo supermercado, comparado sobre
    # los mismos productos que cubre el plan. Null si ningún supermercado los
    # cubre todos: ahí dividir no es una opción más barata, es la única.
    best_single_total: int | None = None
    # best_single_total - total, nunca negativo. Es el número que justifica el
    # segundo viaje: si es 0, no vale la pena dividir.
    savings: int = 0
    groups: list[SplitPlanGroupOut] = []
