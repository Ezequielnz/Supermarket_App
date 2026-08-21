from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status

from app.core.supabase_client import get_supabase
from app.schemas.shopping_list import (
    ShoppingListCreate,
    ShoppingListDetailOut,
    ShoppingListItemCreate,
    ShoppingListItemOut,
    ShoppingListListResponse,
    ShoppingListOut,
    ShoppingListUpdate,
)


def get_list_or_404(list_id: UUID, user_id: UUID) -> dict:
    """
    El cliente de Supabase del backend usa service_role_key, que bypasea RLS
    por completo: la policy `shopping_lists_select_own` NO protege esta
    consulta. El filtro .eq("user_id", user_id) es la única barrera real. Si
    la lista existe pero es de otro usuario, se devuelve 404 (no 403) para no
    revelar que el recurso existe.
    """
    client = get_supabase()
    result = (
        client.table("shopping_lists")
        .select("*")
        .eq("id", str(list_id))
        .eq("user_id", str(user_id))
        .maybe_single()
        .execute()
    )
    if result.data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lista no encontrada.")
    return result.data


def _touch_list(client, list_id: UUID) -> None:
    client.table("shopping_lists").update(
        {"updated_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", str(list_id)).execute()


def _count_items(client, list_id: UUID) -> int:
    result = (
        client.table("shopping_list_items")
        .select("id", count="exact")
        .eq("list_id", str(list_id))
        .execute()
    )
    return result.count or 0


def list_lists(user_id: UUID, page: int, per_page: int) -> ShoppingListListResponse:
    client = get_supabase()
    offset = (page - 1) * per_page

    result = (
        client.table("shopping_lists")
        .select("*, shopping_list_items(count)", count="exact")
        .eq("user_id", str(user_id))
        .order("updated_at", desc=True)
        .range(offset, offset + per_page - 1)
        .execute()
    )

    data = []
    for row in result.data:
        items_count = row["shopping_list_items"][0]["count"] if row["shopping_list_items"] else 0
        data.append(ShoppingListOut(**{**row, "items_count": items_count}))

    return ShoppingListListResponse(data=data, total=result.count or 0, page=page, per_page=per_page)


def create_list(payload: ShoppingListCreate, user_id: UUID) -> ShoppingListOut:
    client = get_supabase()
    result = (
        client.table("shopping_lists")
        .insert({"user_id": str(user_id), "name": payload.name})
        .execute()
    )
    return ShoppingListOut(**{**result.data[0], "items_count": 0})


def rename_list(list_id: UUID, payload: ShoppingListUpdate, user_id: UUID) -> ShoppingListOut:
    get_list_or_404(list_id, user_id)
    client = get_supabase()
    result = (
        client.table("shopping_lists")
        .update({"name": payload.name, "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", str(list_id))
        .eq("user_id", str(user_id))
        .execute()
    )
    items_count = _count_items(client, list_id)
    return ShoppingListOut(**{**result.data[0], "items_count": items_count})


def delete_list(list_id: UUID, user_id: UUID) -> None:
    get_list_or_404(list_id, user_id)
    client = get_supabase()
    client.table("shopping_lists").delete().eq("id", str(list_id)).eq("user_id", str(user_id)).execute()


def get_list_detail(list_id: UUID, user_id: UUID) -> ShoppingListDetailOut:
    list_row = get_list_or_404(list_id, user_id)
    client = get_supabase()
    items = (
        client.table("shopping_list_items")
        .select("*, products(name)")
        .eq("list_id", str(list_id))
        .execute()
    )
    return ShoppingListDetailOut(
        id=list_row["id"],
        name=list_row["name"],
        created_at=list_row["created_at"],
        updated_at=list_row["updated_at"],
        items=[
            ShoppingListItemOut(
                id=item["id"],
                product_id=item["product_id"],
                product_name=item["products"]["name"],
                quantity=item["quantity"],
                note=item["note"],
            )
            for item in items.data
        ],
    )


def add_item(list_id: UUID, payload: ShoppingListItemCreate, user_id: UUID) -> ShoppingListItemOut:
    get_list_or_404(list_id, user_id)
    client = get_supabase()

    product = (
        client.table("products")
        .select("name")
        .eq("id", str(payload.product_id))
        .maybe_single()
        .execute()
    )
    if product.data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado.")

    result = (
        client.table("shopping_list_items")
        .insert(
            {
                "list_id": str(list_id),
                "product_id": str(payload.product_id),
                "quantity": payload.quantity,
                "note": payload.note,
            }
        )
        .execute()
    )
    _touch_list(client, list_id)

    item = result.data[0]
    return ShoppingListItemOut(
        id=item["id"],
        product_id=item["product_id"],
        product_name=product.data["name"],
        quantity=item["quantity"],
        note=item["note"],
    )


def remove_item(list_id: UUID, item_id: UUID, user_id: UUID) -> None:
    get_list_or_404(list_id, user_id)
    client = get_supabase()
    result = (
        client.table("shopping_list_items")
        .delete()
        .eq("id", str(item_id))
        .eq("list_id", str(list_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado en la lista.")
    _touch_list(client, list_id)
