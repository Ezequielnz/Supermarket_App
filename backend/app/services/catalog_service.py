from uuid import UUID

from fastapi import HTTPException, status

from app.core.supabase_client import get_supabase, single_row
from app.schemas.catalog import (
    LOOKUP_LIMIT,
    ProductDraft,
    ProductLookupResponse,
    ProductMatchOut,
)


def _draft_columns(draft: ProductDraft) -> dict:
    return {
        "name": draft.name,
        "ean": draft.ean,
        "brand": draft.brand,
        "unit": draft.unit,
        "size_value": draft.size_value,
        "size_unit": draft.size_unit,
        "category": draft.category,
        "image_url": draft.image_url,
    }


def find_by_ean(ean: str) -> dict | None:
    """El EAN es identidad, no parecido: idx_products_ean es UNIQUE (016)."""
    client = get_supabase()
    return single_row(
        client.table("products").select("*").eq("ean", ean).maybe_single().execute()
    )


def get_product_or_404(product_id: UUID) -> dict:
    client = get_supabase()
    product = single_row(
        client.table("products")
        .select("*")
        .eq("id", str(product_id))
        .maybe_single()
        .execute()
    )
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado."
        )
    return product


def resolve_product(draft: ProductDraft, chain_id: UUID) -> dict:
    """
    Devuelve la fila de `products` que corresponde a este draft, creándola solo
    si hace falta. Es la pieza de la que depende que el comparador siga
    funcionando cuando entren supermercados reales.

    Si cada cadena crea su propia fila "Leche entera 1L", compare_list —que
    agrupa por product_id— ve dos productos distintos que nunca se comparan
    entre sí. La clave de identidad es el código de barras:

        ¿existe products.ean = X?  ->  sí: usá ese product_id
                                   ->  no: creá el producto global

    Cuando el EAN matchea, el resto del draft se DESCARTA a propósito: la
    cadena no edita la fila global (docs/SEGURIDAD.md §4.2). Si el nombre que
    manda difiere del que está, gana el que está — corregirlo es tarea de un
    admin de plataforma, no de un competidor.

    Sin EAN no hay matcheo automático: el nombre no es confiable como
    identidad. En ese caso se crea, y es el panel el que ofrece los candidatos
    (search_candidates) para que el staff elija explícitamente antes de llegar
    acá. Nunca se adivina.
    """
    if draft.ean:
        existing = find_by_ean(draft.ean)
        if existing is not None:
            return existing

    client = get_supabase()
    columns = _draft_columns(draft)
    columns["created_by_chain_id"] = str(chain_id)

    try:
        created = client.table("products").insert(columns).execute()
    except Exception:
        # Carrera contra otra cadena cargando el mismo EAN entre el SELECT y el
        # INSERT: el UNIQUE parcial es la red. Se reintenta la lectura en vez de
        # devolver 500, porque el resultado correcto es justamente vincular.
        if draft.ean:
            existing = find_by_ean(draft.ean)
            if existing is not None:
                return existing
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo crear el producto. Intenta nuevamente.",
        )

    return created.data[0]


def search_candidates(
    ean: str | None, q: str | None, supermarket_id: UUID | None
) -> ProductLookupResponse:
    """
    Lo que el panel consulta ANTES de crear un producto, para que la cadena
    vincule con lo que ya existe en vez de duplicarlo.

    `supermarket_id` es opcional y solo sirve para marcar `already_listed`: qué
    productos ya vende esa sucursal. Se valida como propio en el endpoint.
    """
    client = get_supabase()

    exact = find_by_ean(ean) if ean else None

    candidates: list[dict] = []
    if q:
        # ilike sobre el índice trigram de la 009 (idx_products_name_trgm): sin
        # él, un LIKE con comodín inicial es un seq scan del catálogo entero.
        candidates = (
            client.table("products")
            .select("*")
            .ilike("name", f"%{q}%")
            .order("name")
            .limit(LOOKUP_LIMIT)
            .execute()
        ).data

    # El exacto no se repite entre los candidatos: es otra cosa (identidad, no
    # parecido) y el panel lo muestra por separado.
    if exact is not None:
        candidates = [row for row in candidates if row["id"] != exact["id"]]

    listed = _already_listed_ids(
        supermarket_id,
        [row["id"] for row in candidates] + ([exact["id"]] if exact else []),
    )

    return ProductLookupResponse(
        exact_match=(
            ProductMatchOut(**exact, already_listed=exact["id"] in listed) if exact else None
        ),
        candidates=[
            ProductMatchOut(**row, already_listed=row["id"] in listed) for row in candidates
        ],
    )


def _already_listed_ids(supermarket_id: UUID | None, product_ids: list[str]) -> set[str]:
    if supermarket_id is None or not product_ids:
        return set()
    client = get_supabase()
    rows = (
        client.table("supermarket_products")
        .select("product_id")
        .eq("supermarket_id", str(supermarket_id))
        .in_("product_id", product_ids)
        .execute()
    ).data
    return {row["product_id"] for row in rows}
