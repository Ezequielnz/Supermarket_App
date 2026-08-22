from datetime import datetime, timezone
from uuid import UUID

from app.core.supabase_client import get_supabase
from app.schemas.shopping_list import (
    CompareItemOut,
    CompareMissingItemOut,
    CompareResponse,
    CompareResultOut,
)
from app.services.list_service import get_list_or_404
from app.services.product_service import is_supermarket_visible


def compare_list(list_id: UUID, user_id: UUID) -> CompareResponse:
    """
    Implementa el algoritmo de docs/ARQUITECTURA.md §9:
    1. Obtener los items de la lista, en orden estable.
    2. Para cada product_id, consultar supermarket_products.
    3. Agrupar por supermercado y sumar totales, redondeando POR ITEM.
    4. Si un supermercado no tiene algún producto (o está sin stock), nombrar
       ese producto en `missing` y omitirlo de su total (nunca inventar un
       precio).
    5. Devolver los completos primero y, dentro de cada grupo, de menor a mayor
       total.

    Solo entran supermercados activos de cadenas aprobadas: ver
    is_supermarket_visible. El backend bypasea RLS, así que el filtro tiene que
    estar acá aunque las policies de 015 digan lo mismo.

    Un supermercado que no tiene NINGÚN producto de la lista no aparece. Con
    catálogo grande, una fila "0 de 10" por cada supermercado del país es ruido,
    no información.
    """
    get_list_or_404(list_id, user_id)
    client = get_supabase()
    generated_at = datetime.now(timezone.utc)

    # El mismo orden que get_list_detail: el usuario ve los faltantes en el
    # orden en que armó la lista, no en uno arbitrario.
    items = (
        client.table("shopping_list_items")
        .select("product_id, quantity, products(name)")
        .eq("list_id", str(list_id))
        .order("created_at")
        .order("id")
        .execute()
    ).data

    if not items:
        return CompareResponse(
            list_id=list_id, items_count=0, generated_at=generated_at, results=[]
        )

    product_ids = [item["product_id"] for item in items]
    quantity_by_product = {item["product_id"]: item["quantity"] for item in items}
    name_by_product = {item["product_id"]: item["products"]["name"] for item in items}

    prices = (
        client.table("supermarket_products")
        .select("*, supermarkets(*, chains(status))")
        .in_("product_id", product_ids)
        .eq("in_stock", True)
        .execute()
    ).data

    by_supermarket: dict[str, dict] = {}
    for row in prices:
        supermarket = row["supermarkets"]
        if not is_supermarket_visible(supermarket):
            continue
        entry = by_supermarket.setdefault(
            supermarket["id"],
            {"supermarket": supermarket, "currency": row["currency"], "items": []},
        )
        entry["items"].append(
            CompareItemOut(
                product_id=row["product_id"],
                product_name=name_by_product[row["product_id"]],
                price=row["price"],
                in_stock=row["in_stock"],
            )
        )

    results = []
    for entry in by_supermarket.values():
        covered = {str(item.product_id) for item in entry["items"]}
        # Se recorre product_ids y no el set: los faltantes salen en el orden
        # de la lista.
        missing = [
            CompareMissingItemOut(product_id=pid, product_name=name_by_product[pid])
            for pid in product_ids
            if pid not in covered
        ]
        # Redondeo POR ITEM, no sobre la suma. Es lo que hace order_service al
        # crear el pedido (subtotal = round(unit_price * quantity)); redondear
        # una sola vez al final hacía que el comparador prometiera un número y
        # el pedido cobrara otro cuando las cantidades son decimales.
        total = sum(
            round(item.price * quantity_by_product[str(item.product_id)])
            for item in entry["items"]
        )
        results.append(
            CompareResultOut(
                supermarket=entry["supermarket"],
                total=total,
                currency=entry["currency"],
                is_complete=not missing,
                items_covered=len(entry["items"]),
                items_total=len(product_ids),
                missing=missing,
                items=entry["items"],
            )
        )

    # Completos primero, después por total. Un total parcial no es comparable
    # con uno completo: ordenar todo junto por precio pondría arriba al
    # supermercado al que le faltan la mitad de los productos, que es
    # exactamente el dato equivocado.
    results.sort(key=lambda r: (not r.is_complete, r.total))

    return CompareResponse(
        list_id=list_id,
        items_count=len(items),
        generated_at=generated_at,
        results=results,
    )
