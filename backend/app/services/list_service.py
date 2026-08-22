from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status

from app.core.supabase_client import get_supabase, single_row
from app.schemas.shopping_list import (
    CartSaveRequest,
    ShoppingListCreate,
    ShoppingListDetailOut,
    ShoppingListItemCreate,
    ShoppingListItemOut,
    ShoppingListItemUpdate,
    ShoppingListListResponse,
    ShoppingListOut,
    ShoppingListUpdate,
)
from app.services.product_service import price_context

# Nombre del carrito recién creado. No lo elige el usuario: el carrito aparece
# solo, sin que tenga que crear nada a mano.
CART_NAME = "Mi carrito"


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
    row = single_row(result)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lista no encontrada.")
    return row


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


def _product_name_or_404(client, product_id: UUID) -> str:
    product = (
        client.table("products")
        .select("name")
        .eq("id", str(product_id))
        .maybe_single()
        .execute()
    )
    row = single_row(product)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado.")
    return row["name"]


def _item_out(client, item: dict, product_name: str | None = None) -> ShoppingListItemOut:
    """
    Un item con su nombre y su mejor precio. El best_price viaja en todas las
    respuestas de item, no solo en el detalle de la lista: un PATCH que
    devolviera null donde hay precio es un dato equivocado, aunque el drawer
    hoy recargue el carrito despues de cada cambio y no lo note.
    """
    prices = price_context(client, [item["product_id"]])
    return ShoppingListItemOut(
        id=item["id"],
        product_id=item["product_id"],
        product_name=product_name or _product_name_or_404(client, item["product_id"]),
        quantity=item["quantity"],
        note=item["note"],
        best_price=prices.get(item["product_id"], {}).get("best_price"),
    )


def list_lists(user_id: UUID, page: int, per_page: int) -> ShoppingListListResponse:
    """
    Solo listas guardadas. El carrito es una fila de esta misma tabla
    (is_cart = true) y se excluye a propósito: aparece en el drawer del
    carrito, no mezclado entre "Mis listas". Se llega a él por /lists/cart.
    """
    client = get_supabase()
    offset = (page - 1) * per_page

    result = (
        client.table("shopping_lists")
        .select("*, shopping_list_items(count)", count="exact")
        .eq("user_id", str(user_id))
        .eq("is_cart", False)
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
    # Orden estable. Sin ORDER BY, PostgREST devuelve los items en el orden que
    # se le da la gana y la lista guardada se ve distinta en cada visita, como
    # si cambiara sola. El id desempata: las filas anteriores a la migración
    # 023 comparten el created_at del ALTER TABLE.
    items = (
        client.table("shopping_list_items")
        .select("*, products(name)")
        .eq("list_id", str(list_id))
        .order("created_at")
        .order("id")
        .execute()
    )

    # Una consulta mas para toda la lista, no una por item: el drawer del
    # carrito muestra "estimado desde", que es la suma de los mejores precios.
    # Es un dato informativo — el total en firme lo da el comparador, porque el
    # carrito no esta atado a un supermercado.
    prices = price_context(client, [item["product_id"] for item in items.data])

    return ShoppingListDetailOut(
        id=list_row["id"],
        name=list_row["name"],
        created_at=list_row["created_at"],
        updated_at=list_row["updated_at"],
        is_cart=list_row.get("is_cart", False),
        items=[
            ShoppingListItemOut(
                id=item["id"],
                product_id=item["product_id"],
                product_name=item["products"]["name"],
                quantity=item["quantity"],
                note=item["note"],
                best_price=prices.get(item["product_id"], {}).get("best_price"),
            )
            for item in items.data
        ],
    )


def add_item(list_id: UUID, payload: ShoppingListItemCreate, user_id: UUID) -> ShoppingListItemOut:
    """
    Idempotente por producto: agregar dos veces el mismo producto SUMA la
    cantidad en vez de fallar.

    La migración 009 agregó `unique_product_per_list UNIQUE (list_id,
    product_id)` para que un repetido no se contara dos veces en la
    comparación, pero add_item seguía haciendo un .insert() plano: el segundo
    agregado violaba el constraint y salía como 500. Y agregar dos veces el
    mismo producto es exactamente lo que hace un carrito todo el tiempo.

    No sirve el upsert de PostgREST: pisaría la cantidad en vez de sumarla.
    """
    get_list_or_404(list_id, user_id)
    client = get_supabase()

    product_name = _product_name_or_404(client, payload.product_id)

    existing = single_row(
        client.table("shopping_list_items")
        .select("*")
        .eq("list_id", str(list_id))
        .eq("product_id", str(payload.product_id))
        .maybe_single()
        .execute()
    )

    if existing is not None:
        updates = {"quantity": float(existing["quantity"]) + payload.quantity}
        # Una nota nueva pisa la anterior; sin nota, se conserva la que había.
        if payload.note is not None:
            updates["note"] = payload.note
        result = (
            client.table("shopping_list_items")
            .update(updates)
            .eq("id", existing["id"])
            .eq("list_id", str(list_id))
            .execute()
        )
    else:
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

    return _item_out(client, result.data[0], product_name)


def set_item_quantity(
    list_id: UUID, item_id: UUID, payload: ShoppingListItemUpdate, user_id: UUID
) -> ShoppingListItemOut:
    """
    Fija la cantidad de un ítem (no la suma): es el control - / + del carrito.
    El filtro por list_id, sumado al get_list_or_404, es lo que impide tocar el
    ítem de la lista de otro usuario pasando su UUID.
    """
    get_list_or_404(list_id, user_id)
    client = get_supabase()

    result = (
        client.table("shopping_list_items")
        .update({"quantity": payload.quantity})
        .eq("id", str(item_id))
        .eq("list_id", str(list_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado en la lista."
        )
    _touch_list(client, list_id)

    item = result.data[0]
    return _item_out(client, item)


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


# ── Carrito ───────────────────────────────────────────────────────────────
# El carrito no es una tabla propia: es una shopping_list con is_cart = true
# (migración 020). Así el camino al checkout que ya funciona de punta a punta
# —lista → /lists/{id}/compare → checkout → orders— sirve igual para el
# carrito, en vez de forkearse en dos.


def get_or_create_cart(user_id: UUID) -> dict:
    """
    Devuelve la fila del carrito activo del usuario, creándola si no existe.
    Se llama en cada operación de carrito: el consumidor nunca crea uno a mano.

    El índice único parcial idx_one_cart_per_user garantiza uno solo por
    usuario. Si dos pestañas piden el carrito a la vez, una de las dos pierde
    el INSERT contra ese índice; se reintenta el SELECT en vez de devolver 500.
    """
    client = get_supabase()

    def _current():
        return single_row(
            client.table("shopping_lists")
            .select("*")
            .eq("user_id", str(user_id))
            .eq("is_cart", True)
            .maybe_single()
            .execute()
        )

    cart = _current()
    if cart is not None:
        return cart

    try:
        created = (
            client.table("shopping_lists")
            .insert({"user_id": str(user_id), "name": CART_NAME, "is_cart": True})
            .execute()
        )
        return created.data[0]
    except Exception:
        cart = _current()
        if cart is None:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="No se pudo abrir tu carrito. Intenta nuevamente.",
            )
        return cart


def get_cart(user_id: UUID) -> ShoppingListDetailOut:
    cart = get_or_create_cart(user_id)
    return get_list_detail(UUID(cart["id"]), user_id)


def add_cart_item(payload: ShoppingListItemCreate, user_id: UUID) -> ShoppingListItemOut:
    """Atajo de POST /lists/{cart_id}/items sin tener que saber el id del carrito."""
    cart = get_or_create_cart(user_id)
    return add_item(UUID(cart["id"]), payload, user_id)


def save_cart(payload: CartSaveRequest | None, user_id: UUID) -> ShoppingListOut:
    """
    Convierte el carrito en una lista guardada (is_cart = false). El próximo
    agregado crea un carrito nuevo y vacío, porque get_or_create_cart ya no
    encuentra ninguno con el flag puesto.
    """
    cart = get_or_create_cart(user_id)
    client = get_supabase()

    updates = {"is_cart": False, "updated_at": datetime.now(timezone.utc).isoformat()}
    if payload is not None and payload.name:
        updates["name"] = payload.name

    result = (
        client.table("shopping_lists")
        .update(updates)
        .eq("id", cart["id"])
        .eq("user_id", str(user_id))
        .execute()
    )
    items_count = _count_items(client, UUID(cart["id"]))
    return ShoppingListOut(**{**result.data[0], "items_count": items_count})
