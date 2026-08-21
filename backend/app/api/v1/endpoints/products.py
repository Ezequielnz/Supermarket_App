from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.product import ProductListResponse, ProductPricesResponse
from app.services.product_service import get_product_prices, list_products

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=ProductListResponse)
def search_products(
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Busca productos del catálogo por nombre. Requiere autenticación de consumidor."""
    return list_products(q, page, per_page)


@router.get("/{product_id}/prices", response_model=ProductPricesResponse)
def get_prices(product_id: UUID, current_user: CurrentUser = Depends(get_current_user)):
    """Devuelve el precio de un producto en todos los supermercados que lo tienen. Requiere autenticación de consumidor."""
    return get_product_prices(product_id)
