from uuid import UUID

from fastapi import HTTPException, status

from app.core.supabase_client import get_supabase
from app.schemas.product import (
    ProductListResponse,
    ProductOut,
    ProductPriceOut,
    ProductPricesResponse,
)


def list_products(q: str | None, page: int, per_page: int) -> ProductListResponse:
    client = get_supabase()
    offset = (page - 1) * per_page

    query = client.table("products").select("*", count="exact")
    if q:
        query = query.ilike("name", f"%{q}%")
    result = query.order("name").range(offset, offset + per_page - 1).execute()

    return ProductListResponse(
        data=[ProductOut.model_validate(row) for row in result.data],
        total=result.count or 0,
        page=page,
        per_page=per_page,
    )


def get_product_prices(product_id: UUID) -> ProductPricesResponse:
    client = get_supabase()

    product = (
        client.table("products")
        .select("*")
        .eq("id", str(product_id))
        .maybe_single()
        .execute()
    )
    if product.data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado.")

    prices = (
        client.table("supermarket_products")
        .select("*, supermarkets(*)")
        .eq("product_id", str(product_id))
        .order("price")
        .execute()
    )

    return ProductPricesResponse(
        product_id=product_id,
        product_name=product.data["name"],
        prices=[
            ProductPriceOut(
                supermarket=row["supermarkets"],
                price=row["price"],
                currency=row["currency"],
                in_stock=row["in_stock"],
                updated_at=row["updated_at"],
            )
            for row in prices.data
        ],
    )
