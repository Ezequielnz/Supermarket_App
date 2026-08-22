from uuid import UUID

from fastapi import HTTPException, status

from app.core.supabase_client import get_supabase, single_row
from app.schemas.product import (
    CategoryListResponse,
    CategoryOut,
    ProductListResponse,
    ProductOut,
    ProductPriceOut,
    ProductPricesResponse,
)
from app.schemas.supermarket import APPROVED_CHAIN_STATUS

# Orden permitido en GET /products. Constante nombrada y no un string suelto en
# el endpoint (NORMAS.md §9: nada de strings mágicos).
SORT_NAME = "name"
SORT_PRICE = "price"
PRODUCT_SORTS = (SORT_NAME, SORT_PRICE)


def is_supermarket_visible(supermarket: dict) -> bool:
    """
    Un supermercado es visible para el consumidor si está activo Y su cadena
    está aprobada.

    Hace falta comprobarlo en Python, no alcanza con las policies de la
    migración 015: el backend usa service_role_key y bypasea RLS por completo
    (docs/SEGURIDAD.md §5.1). Sin esto, una cadena recién registrada aparecería
    en el comparador apenas cargue precios, sin pasar por la moderación.

    Espera la fila de `supermarkets` con `chains(status)` embebido.
    """
    if not supermarket.get("is_active", True):
        return False
    chain = supermarket.get("chains") or {}
    return chain.get("status") == APPROVED_CHAIN_STATUS


def price_context(client, product_ids: list[str]) -> dict[str, dict]:
    """
    Resume, para cada producto de la página, el mejor precio visible y en
    cuántos supermercados se consigue.

    UNA sola consulta para toda la página, no una por producto: con `per_page`
    topeado en 100 (le=100 en el endpoint) el volumen queda acotado y no hay
    N+1. El índice idx_sp_product_id de la 009 cubre el .in_().

    El filtro de visibilidad es obligatorio y se hace en Python: el backend usa
    service_role y bypasea RLS, así que las policies de la 015 no descartan ni
    una fila acá (docs/SEGURIDAD.md §5.1). Se reusa is_supermarket_visible —la
    misma función que usan compare_list y get_product_prices— para que las tres
    pantallas no puedan divergir sobre qué supermercado es visible.

    El cliente llega por parámetro y no de get_supabase(): list_service también
    la usa, y resolverlo adentro ataría la consulta al cliente de ESTE módulo.
    """
    if not product_ids:
        return {}

    rows = (
        client.table("supermarket_products")
        .select("product_id, price, supermarkets(*, chains(status))")
        .in_("product_id", product_ids)
        .eq("in_stock", True)
        .execute()
    ).data

    context: dict[str, dict] = {}
    for row in rows:
        supermarket = row["supermarkets"]
        if not is_supermarket_visible(supermarket):
            continue
        entry = context.setdefault(
            row["product_id"], {"best_price": None, "best_price_supermarket": None, "available_in": 0}
        )
        entry["available_in"] += 1
        if entry["best_price"] is None or row["price"] < entry["best_price"]:
            entry["best_price"] = row["price"]
            entry["best_price_supermarket"] = supermarket

    return context


def list_products(
    q: str | None,
    page: int,
    per_page: int,
    category: str | None = None,
    sort: str = SORT_NAME,
) -> ProductListResponse:
    """
    Catálogo con contexto de precio. Dos consultas fijas: la página de
    productos y, sobre esos ids, el resumen de precios.

    `sort=price` ordena por el mejor precio de la página ya traída, no en la
    base: el precio no vive en `products`, y ordenar en Postgres exigiría un
    join con agregación por el que habría que paginar. Es una limitación
    consciente y acotada al tamaño de página.
    """
    client = get_supabase()
    offset = (page - 1) * per_page

    query = client.table("products").select("*", count="exact")
    if q:
        query = query.ilike("name", f"%{q}%")
    if category:
        query = query.eq("category", category)
    result = query.order("name").range(offset, offset + per_page - 1).execute()

    context = price_context(client, [row["id"] for row in result.data])

    data = [
        ProductOut(**{**row, **context.get(row["id"], {})})
        for row in result.data
    ]

    if sort == SORT_PRICE:
        # Los que no tienen precio visible van al final: "desde —" no compite
        # con un precio real.
        data.sort(key=lambda p: (p.best_price is None, p.best_price or 0))

    return ProductListResponse(
        data=data,
        total=result.count or 0,
        page=page,
        per_page=per_page,
    )


def list_categories() -> CategoryListResponse:
    """
    Categorías con productos en el catálogo, para el filtro de la pantalla de
    explorar. Se cuenta sobre `products` y no sobre los precios visibles: es un
    filtro de navegación, y una categoría que aparece vacía por stock es menos
    confuso que una que desaparece y vuelve.
    """
    client = get_supabase()
    rows = (
        client.table("products")
        .select("category")
        .not_.is_("category", "null")
        .execute()
    ).data

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["category"]] = counts.get(row["category"], 0) + 1

    return CategoryListResponse(
        data=[
            CategoryOut(name=name, products_count=count)
            for name, count in sorted(counts.items())
        ]
    )


def get_product_prices(product_id: UUID) -> ProductPricesResponse:
    client = get_supabase()

    product = single_row(
        client.table("products")
        .select("*")
        .eq("id", str(product_id))
        .maybe_single()
        .execute()
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado.")

    prices = (
        client.table("supermarket_products")
        .select("*, supermarkets(*, chains(status))")
        .eq("product_id", str(product_id))
        .order("price")
        .execute()
    )

    return ProductPricesResponse(
        product_id=product_id,
        product_name=product["name"],
        prices=[
            ProductPriceOut(
                supermarket=row["supermarkets"],
                price=row["price"],
                currency=row["currency"],
                in_stock=row["in_stock"],
                updated_at=row["updated_at"],
            )
            for row in prices.data
            if is_supermarket_visible(row["supermarkets"])
        ],
    )
