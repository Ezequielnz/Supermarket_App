from uuid import UUID

from app.core.supabase_client import get_supabase
from app.schemas.shopping_list import CompareItemOut, CompareResponse, CompareResultOut
from app.services.list_service import get_list_or_404


def compare_list(list_id: UUID, user_id: UUID) -> CompareResponse:
    """
    Implementa el algoritmo de docs/ARQUITECTURA.md §9:
    1. Obtener los items de la lista.
    2. Para cada product_id, consultar supermarket_products.
    3. Agrupar por supermercado y sumar totales.
    4. Si un supermercado no tiene algún producto (o está sin stock), marcarlo
       incompleto y omitir ese ítem de su detalle (nunca inventar un precio).
    5. Devolver resultados ordenados de menor a mayor total.
    """
    get_list_or_404(list_id, user_id)
    client = get_supabase()

    items = (
        client.table("shopping_list_items")
        .select("product_id, quantity, products(name)")
        .eq("list_id", str(list_id))
        .execute()
    ).data

    if not items:
        return CompareResponse(list_id=list_id, items_count=0, results=[])

    product_ids = [item["product_id"] for item in items]
    quantity_by_product = {item["product_id"]: item["quantity"] for item in items}
    name_by_product = {item["product_id"]: item["products"]["name"] for item in items}

    prices = (
        client.table("supermarket_products")
        .select("*, supermarkets(*)")
        .in_("product_id", product_ids)
        .eq("in_stock", True)
        .execute()
    ).data

    by_supermarket: dict[str, dict] = {}
    for row in prices:
        supermarket = row["supermarkets"]
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
        matched_ids = {item.product_id for item in entry["items"]}
        total = sum(
            item.price * quantity_by_product[str(item.product_id)] for item in entry["items"]
        )
        results.append(
            CompareResultOut(
                supermarket=entry["supermarket"],
                total=round(total),
                currency=entry["currency"],
                is_complete=matched_ids == {UUID(pid) for pid in product_ids},
                items=entry["items"],
            )
        )

    results.sort(key=lambda r: r.total)

    return CompareResponse(list_id=list_id, items_count=len(items), results=results)
