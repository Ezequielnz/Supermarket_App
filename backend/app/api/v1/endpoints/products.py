from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.product import (
    CategoryListResponse,
    ProductListResponse,
    ProductPricesResponse,
)
from app.services.product_service import (
    PRODUCT_SORTS,
    SORT_NAME,
    get_product_prices,
    list_categories,
    list_products,
)

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=ProductListResponse)
def search_products(
    q: str | None = Query(default=None, max_length=120),
    category: str | None = Query(default=None, max_length=80),
    sort: str = Query(default=SORT_NAME, pattern=f"^({'|'.join(PRODUCT_SORTS)})$"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Busca productos del catálogo, con el mejor precio de cada uno y en cuántos
    supermercados se consigue. Requiere autenticación de consumidor: los
    precios son un dato Interno, nunca se sirven a un anónimo
    (docs/SEGURIDAD.md §2.2).

    `per_page` tiene tope duro de 100 — es una de las mitigaciones de scraping
    de §11.2.
    """
    return list_products(q, page, per_page, category, sort)


@router.get("/categories", response_model=CategoryListResponse)
def get_categories(current_user: CurrentUser = Depends(get_current_user)):
    """Categorías del catálogo, para el filtro de la pantalla de explorar."""
    return list_categories()


@router.get("/{product_id}/prices", response_model=ProductPricesResponse)
def get_prices(product_id: UUID, current_user: CurrentUser = Depends(get_current_user)):
    """Devuelve el precio de un producto en todos los supermercados que lo tienen. Requiere autenticación de consumidor."""
    return get_product_prices(product_id)
