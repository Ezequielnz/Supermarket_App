from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.security import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.shopping_list import (
    CartSaveRequest,
    CompareResponse,
    ShoppingListCreate,
    ShoppingListDetailOut,
    ShoppingListItemCreate,
    ShoppingListItemOut,
    ShoppingListItemUpdate,
    ShoppingListListResponse,
    ShoppingListOut,
    ShoppingListUpdate,
    SplitCompareResponse,
)
from app.services import comparison_service, list_service

router = APIRouter(prefix="/lists", tags=["lists"])

# Dividir la compra en dos supermercados es el caso que pide el usuario que
# quiere ahorrar sin convertir la compra en una excursión. Puede pedir más, con
# el tope de comparison_service.MAX_SPLIT_SUPERMARKETS.
DEFAULT_SPLIT_SUPERMARKETS = 2


@router.get("", response_model=ShoppingListListResponse)
def get_lists(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Lista las listas de compra del consumidor autenticado."""
    return list_service.list_lists(current_user.id, page, per_page)


@router.post("", response_model=ShoppingListOut, status_code=status.HTTP_201_CREATED)
def create_list(payload: ShoppingListCreate, current_user: CurrentUser = Depends(get_current_user)):
    """Crea una nueva lista de compra para el consumidor autenticado."""
    return list_service.create_list(payload, current_user.id)


# ── Carrito ───────────────────────────────────────────────────────────────
# Estas rutas van declaradas ANTES de /lists/{list_id}: FastAPI resuelve por
# orden de registro, así que con /lists/{list_id} primero intentaría parsear
# "cart" como UUID y devolvería 422 en vez de entrar acá.


@router.get("/cart", response_model=ShoppingListDetailOut)
def get_cart(current_user: CurrentUser = Depends(get_current_user)):
    """Devuelve el carrito activo con sus items. Lo crea vacío si no existe."""
    return list_service.get_cart(current_user.id)


@router.post("/cart/items", response_model=ShoppingListItemOut, status_code=status.HTTP_201_CREATED)
def add_cart_item(
    payload: ShoppingListItemCreate,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Agrega un producto al carrito activo, sin tener que conocer su id."""
    return list_service.add_cart_item(payload, current_user.id)


@router.post("/cart/save", response_model=ShoppingListOut)
def save_cart(
    payload: CartSaveRequest = CartSaveRequest(),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Convierte el carrito activo en una lista guardada. El próximo producto que
    se agregue abre un carrito nuevo y vacío.
    """
    return list_service.save_cart(payload, current_user.id)


@router.get("/{list_id}", response_model=ShoppingListDetailOut)
def get_list(list_id: UUID, current_user: CurrentUser = Depends(get_current_user)):
    """Devuelve el detalle de una lista propia, con sus productos."""
    return list_service.get_list_detail(list_id, current_user.id)


@router.put("/{list_id}", response_model=ShoppingListOut)
def rename_list(list_id: UUID, payload: ShoppingListUpdate, current_user: CurrentUser = Depends(get_current_user)):
    """Renombra una lista propia."""
    return list_service.rename_list(list_id, payload, current_user.id)


@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_list(list_id: UUID, current_user: CurrentUser = Depends(get_current_user)):
    """Elimina una lista propia (y sus items, en cascada)."""
    list_service.delete_list(list_id, current_user.id)


@router.post("/{list_id}/items", response_model=ShoppingListItemOut, status_code=status.HTTP_201_CREATED)
def add_item(list_id: UUID, payload: ShoppingListItemCreate, current_user: CurrentUser = Depends(get_current_user)):
    """Agrega un producto a una lista propia."""
    return list_service.add_item(list_id, payload, current_user.id)


@router.patch("/{list_id}/items/{item_id}", response_model=ShoppingListItemOut)
def set_item_quantity(
    list_id: UUID,
    item_id: UUID,
    payload: ShoppingListItemUpdate,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Fija la cantidad de un producto de una lista propia. Es el control - / +
    del carrito: fija, no suma. Para sacar el ítem está DELETE.
    """
    return list_service.set_item_quantity(list_id, item_id, payload, current_user.id)


@router.delete("/{list_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_item(list_id: UUID, item_id: UUID, current_user: CurrentUser = Depends(get_current_user)):
    """Quita un producto de una lista propia."""
    list_service.remove_item(list_id, item_id, current_user.id)


@router.get("/{list_id}/compare", response_model=CompareResponse)
def compare_list(list_id: UUID, current_user: CurrentUser = Depends(get_current_user)):
    """Compara el precio total de una lista propia entre todos los supermercados."""
    return comparison_service.compare_list(list_id, current_user.id)


@router.get("/{list_id}/compare/split", response_model=SplitCompareResponse)
def split_list(
    list_id: UUID,
    max_supermarkets: int = Query(
        default=DEFAULT_SPLIT_SUPERMARKETS, ge=2, le=comparison_service.MAX_SPLIT_SUPERMARKETS
    ),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Arma el plan de compra más barato repartiendo la lista entre hasta
    `max_supermarkets` supermercados distintos.

    Es la otra mitad de `/compare`: aquel responde "¿dónde compro todo?", este
    responde "¿y si compro cada cosa donde está más barata?". El mínimo es 2
    porque con uno solo la respuesta ya la da `/compare`.
    """
    return comparison_service.split_list(list_id, current_user.id, max_supermarkets)
