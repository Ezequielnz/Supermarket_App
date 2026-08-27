from uuid import UUID

from fastapi import HTTPException, status

from app.core.supabase_client import get_supabase, single_row
from app.schemas.catalog import (
    DEFAULT_CURRENCY,
    CatalogProductOut,
    ProductLookupResponse,
    SupermarketProductCreate,
    SupermarketProductListResponse,
    SupermarketProductOut,
    SupermarketProductUpdate,
)
from app.services import catalog_service
from app.services.supermarket_service import get_store_or_404

# Lo que hace falta para armar SupermarketProductOut de una sola consulta.
_ROW_SELECT = "*, products(*), supermarkets(id, name, address, logo_url, chain_id)"

# Con `?q=` el filtro va sobre la tabla embebida, y para que filtre de verdad
# el join tiene que ser INNER: con el embebido normal (LEFT), PostgREST
# devuelve igual la fila de precio con products en null en vez de descartarla.
_ROW_SELECT_SEARCH = "*, products!inner(*), supermarkets(id, name, address, logo_url, chain_id)"


def _chain_store_ids(chain_id: UUID) -> list[str]:
    client = get_supabase()
    rows = (
        client.table("supermarkets")
        .select("id")
        .eq("chain_id", str(chain_id))
        .execute()
    ).data
    return [row["id"] for row in rows]


def _to_out(row: dict) -> SupermarketProductOut:
    return SupermarketProductOut(
        id=row["id"],
        product=CatalogProductOut(**row["products"]),
        supermarket=row["supermarkets"],
        price=row["price"],
        currency=row["currency"],
        in_stock=row["in_stock"],
        stock_quantity=row.get("stock_quantity"),
        updated_at=row["updated_at"],
    )


def get_listing_or_404(listing_id: UUID, chain_id: UUID) -> dict:
    """
    Una fila de supermarket_products de MI cadena, o 404.

    El backend usa service_role y bypasea RLS, así que la policy
    `supermarket_products_select_approved` no filtra nada acá: la comprobación
    de que la sucursal pertenece a la cadena del JWT es la única barrera real
    (docs/SEGURIDAD.md §5.1). 404 y no 403 para no confirmar que la fila existe
    — mismo criterio que list_service y supermarket_service (§4.3).
    """
    client = get_supabase()
    result = (
        client.table("supermarket_products")
        .select(_ROW_SELECT)
        .eq("id", str(listing_id))
        .maybe_single()
        .execute()
    )
    row = single_row(result)
    if row is None or row["supermarkets"]["chain_id"] != str(chain_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado."
        )
    return row


def list_my_products(
    chain_id: UUID,
    supermarket_id: UUID | None,
    q: str | None,
    page: int,
    per_page: int,
) -> SupermarketProductListResponse:
    """
    El catálogo propio con precios. Filtrable por sucursal y por nombre.

    El filtro por cadena no es opcional ni implícito: se resuelven primero las
    sucursales de la cadena y se consulta solo sobre esas. Una cadena nunca ve
    el precio de otra por este endpoint — para eso está la app del consumidor,
    que es donde los precios son públicos entre competidores por diseño
    (docs/SEGURIDAD.md §11.3).
    """
    client = get_supabase()
    offset = (page - 1) * per_page

    if supermarket_id is not None:
        # Valida que la sucursal sea de esta cadena antes de usarla como filtro.
        get_store_or_404(supermarket_id, chain_id)
        store_ids = [str(supermarket_id)]
    else:
        store_ids = _chain_store_ids(chain_id)

    if not store_ids:
        return SupermarketProductListResponse(data=[], total=0, page=page, per_page=per_page)

    query = (
        client.table("supermarket_products")
        .select(_ROW_SELECT_SEARCH if q else _ROW_SELECT, count="exact")
        .in_("supermarket_id", store_ids)
    )
    if q:
        query = query.ilike("products.name", f"%{q}%")

    result = query.order("updated_at", desc=True).range(offset, offset + per_page - 1).execute()

    return SupermarketProductListResponse(
        data=[_to_out(row) for row in result.data],
        total=result.count or 0,
        page=page,
        per_page=per_page,
    )


def lookup(
    chain_id: UUID, supermarket_id: UUID | None, ean: str | None, q: str | None
) -> ProductLookupResponse:
    """
    Busca en el catálogo GLOBAL antes de crear. Es el paso que evita que cada
    cadena cargue su propia versión del mismo producto y deje el comparador
    vacío (PLAN §10, el riesgo central del sprint).
    """
    if supermarket_id is not None:
        get_store_or_404(supermarket_id, chain_id)
    return catalog_service.search_candidates(ean, q, supermarket_id)


def add_product(payload: SupermarketProductCreate, chain_id: UUID) -> SupermarketProductOut:
    """
    Alta de un precio: resuelve el producto global y crea la fila de precio.

    El `supermarket_id` llega del cliente, así que lo primero es comprobar que
    esa sucursal sea de la cadena del JWT. Sin eso, el staff de la cadena A
    publicaría precios en una sucursal de la B pasando su UUID.
    """
    get_store_or_404(payload.supermarket_id, chain_id)

    if payload.product_id is not None:
        product = catalog_service.get_product_or_404(payload.product_id)
    else:
        product = catalog_service.resolve_product(payload.product, chain_id)

    client = get_supabase()
    try:
        created = (
            client.table("supermarket_products")
            .insert(
                {
                    "supermarket_id": str(payload.supermarket_id),
                    "product_id": product["id"],
                    "price": payload.price,
                    "currency": DEFAULT_CURRENCY,
                    "in_stock": payload.in_stock,
                    "stock_quantity": payload.stock_quantity,
                }
            )
            .execute()
        )
    except Exception:
        # UNIQUE(supermarket_id, product_id) de la 003: la sucursal ya vende
        # este producto. Es un conflicto del cliente, no un fallo del servidor;
        # para cambiar el precio está el PATCH.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta sucursal ya tiene cargado ese producto. Editá su precio desde la lista.",
        )

    return get_product(UUID(created.data[0]["id"]), chain_id)


def get_product(listing_id: UUID, chain_id: UUID) -> SupermarketProductOut:
    return _to_out(get_listing_or_404(listing_id, chain_id))


def update_product(
    listing_id: UUID, payload: SupermarketProductUpdate, chain_id: UUID
) -> SupermarketProductOut:
    """
    Cambia precio, disponibilidad o unidades. El trigger record_price_change
    (016) archiva el precio anterior en price_history por su cuenta, y el de la
    024 baja `in_stock` solo si las unidades llegan a cero: no hay que hacer
    nada extra por ninguno de los dos.
    """
    get_listing_or_404(listing_id, chain_id)

    # exclude_unset y no exclude_none: `{"stock_quantity": null}` significa
    # "dejá de contar unidades de este producto" y tiene que llegar a la base
    # como NULL. Con exclude_none esa orden se perdía en silencio.
    updates = payload.model_dump(exclude_unset=True)
    client = get_supabase()
    client.table("supermarket_products").update(updates).eq("id", str(listing_id)).execute()

    return get_product(listing_id, chain_id)


def remove_product(listing_id: UUID, chain_id: UUID) -> None:
    """
    Deja de vender ese producto en esa sucursal. Borra la fila de precio, no el
    producto global: esa fila es de todos (PLAN §5.2).
    """
    get_listing_or_404(listing_id, chain_id)
    client = get_supabase()
    client.table("supermarket_products").delete().eq("id", str(listing_id)).execute()
