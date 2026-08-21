from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.security import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.shopping_list import (
    CompareResponse,
    ShoppingListCreate,
    ShoppingListDetailOut,
    ShoppingListItemCreate,
    ShoppingListItemOut,
    ShoppingListListResponse,
    ShoppingListOut,
    ShoppingListUpdate,
)
from app.services import comparison_service, list_service

router = APIRouter(prefix="/lists", tags=["lists"])


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


@router.delete("/{list_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_item(list_id: UUID, item_id: UUID, current_user: CurrentUser = Depends(get_current_user)):
    """Quita un producto de una lista propia."""
    list_service.remove_item(list_id, item_id, current_user.id)


@router.get("/{list_id}/compare", response_model=CompareResponse)
def compare_list(list_id: UUID, current_user: CurrentUser = Depends(get_current_user)):
    """Compara el precio total de una lista propia entre todos los supermercados."""
    return comparison_service.compare_list(list_id, current_user.id)
