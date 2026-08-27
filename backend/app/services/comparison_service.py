from datetime import datetime, timezone
from itertools import combinations
from uuid import UUID

from app.core.supabase_client import get_supabase
from app.schemas.shopping_list import (
    CompareItemOut,
    CompareMissingItemOut,
    CompareResponse,
    CompareResultOut,
    SplitCompareResponse,
    SplitPlanGroupOut,
    SplitPlanItemOut,
)
from app.services.list_service import get_list_or_404
from app.services.product_service import is_supermarket_visible

# Tope duro de supermercados que puede proponer un plan dividido. Cuatro
# paradas para hacer una compra ya es más molestia que ahorro, y además acota
# la búsqueda exacta de _best_combination.
MAX_SPLIT_SUPERMARKETS = 4

# Cuántos supermercados entran a esa búsqueda. Elegir el mejor subconjunto de
# tamaño k es un problema de cobertura: no hay atajo exacto, se prueban las
# combinaciones. Con 15 candidatos y k <= 4 son 1365 combinaciones, que se
# calculan en milisegundos; sin tope, un país entero de supermercados haría
# explotar el endpoint. Los candidatos se rankean por utilidad
# (_rank_candidates), así que lo que queda afuera es la cola larga.
MAX_SPLIT_CANDIDATES = 15


def _list_items(client, list_id: UUID) -> list[dict]:
    """
    Los items de la lista en orden estable, con el nombre del producto. El
    mismo orden que get_list_detail: el usuario ve los faltantes en el orden en
    que armó la lista, no en uno arbitrario.
    """
    return (
        client.table("shopping_list_items")
        .select("product_id, quantity, products(name)")
        .eq("list_id", str(list_id))
        .order("created_at")
        .order("id")
        .execute()
    ).data


def _visible_prices(client, product_ids: list[str]) -> list[dict]:
    """
    Precios con stock de esos productos, ya filtrados por visibilidad.

    El filtro de is_supermarket_visible tiene que estar acá, en Python: el
    backend usa service_role y bypasea RLS, así que las policies de la
    migración 015 no descartan ni una fila (docs/SEGURIDAD.md §5.1).
    """
    rows = (
        client.table("supermarket_products")
        .select("*, supermarkets(*, chains(status))")
        .in_("product_id", product_ids)
        .eq("in_stock", True)
        .execute()
    ).data
    return [row for row in rows if is_supermarket_visible(row["supermarkets"])]


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

    items = _list_items(client, list_id)

    if not items:
        return CompareResponse(
            list_id=list_id, items_count=0, generated_at=generated_at, results=[]
        )

    product_ids = [item["product_id"] for item in items]
    quantity_by_product = {item["product_id"]: item["quantity"] for item in items}
    name_by_product = {item["product_id"]: item["products"]["name"] for item in items}

    prices = _visible_prices(client, product_ids)

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


# ── Compra dividida entre varios supermercados ────────────────────────────
# docs/ARQUITECTURA.md §9.1. compare_list responde "¿dónde compro TODO?";
# split_list responde la otra pregunta que se hace el usuario parado frente a
# su lista: "¿y si compro cada cosa donde está más barata?".


def _rank_candidates(cost_by_product: dict[str, dict[str, int]], product_ids: list[str]) -> list[str]:
    """
    Ordena los supermercados por utilidad para un plan dividido y devuelve los
    primeros MAX_SPLIT_CANDIDATES.

    Se rankea por dos cosas, en ese orden: en cuántos productos es el más
    barato —los que forman el óptimo cuando no hay tope de paradas— y cuántos
    productos cubre —los que sirven justamente cuando el tope aprieta y hay que
    resolver media lista en una sola parada—. Después, el total de lo que cubre
    y el id, para que dos llamadas seguidas devuelvan el mismo plan.
    """
    cheapest_count: dict[str, int] = {}
    coverage: dict[str, int] = {}
    covered_cost: dict[str, int] = {}

    for pid in product_ids:
        offers = cost_by_product.get(pid) or {}
        if not offers:
            continue
        best = min(offers.values())
        for supermarket_id, cost in offers.items():
            coverage[supermarket_id] = coverage.get(supermarket_id, 0) + 1
            covered_cost[supermarket_id] = covered_cost.get(supermarket_id, 0) + cost
            if cost == best:
                cheapest_count[supermarket_id] = cheapest_count.get(supermarket_id, 0) + 1

    ranked = sorted(
        coverage,
        key=lambda sm: (-cheapest_count.get(sm, 0), -coverage[sm], covered_cost[sm], sm),
    )
    return ranked[:MAX_SPLIT_CANDIDATES]


def _best_combination(
    cost_by_product: dict[str, dict[str, int]],
    product_ids: list[str],
    candidates: list[str],
    size: int,
) -> set[str]:
    """
    Busca el subconjunto de `size` supermercados que cubre MÁS productos y, a
    igual cobertura, sale más barato.

    La cobertura va primero por la misma razón que en compare_list: un plan más
    barato al que le falta media lista no es más barato, es incompleto.

    Se prueban todas las combinaciones porque no hay atajo exacto —elegir k
    tiendas que minimicen el costo total es un problema de cobertura—, y por
    eso los candidatos vienen acotados. Solo se prueban combinaciones del
    tamaño máximo: agregar un supermercado nunca empeora un plan (los precios
    se toman por mínimo), y los que terminan sin nada asignado no llegan a la
    respuesta.
    """
    best_key: tuple | None = None
    best_combo: tuple[str, ...] = ()

    for combo in combinations(candidates, size):
        covered = 0
        total = 0
        for pid in product_ids:
            offers = cost_by_product.get(pid) or {}
            costs = [offers[sm] for sm in combo if sm in offers]
            if costs:
                covered += 1
                total += min(costs)
        # El `<` estricto cierra el desempate: `candidates` viene rankeado y
        # combinations() lo respeta, así que ante igualdad de cobertura y precio
        # gana la primera, que es la de los supermercados más útiles. Y ante los
        # mismos datos, siempre la misma: dos llamadas seguidas no pueden
        # devolver planes distintos.
        key = (-covered, total)
        if best_key is None or key < best_key:
            best_key, best_combo = key, combo

    return set(best_combo)


def _assign_products(
    product_ids: list[str], cost_by_product: dict[str, dict[str, int]], chosen: set[str]
) -> dict[str, str]:
    """
    Asigna cada producto al supermercado más barato DENTRO del plan elegido.

    El empate se rompe a favor del supermercado que ya tiene productos
    asignados: al mismo precio, una parada menos. Por eso se recorre en el
    orden de la lista y no sobre un set.
    """
    assigned: dict[str, str] = {}
    load = {supermarket_id: 0 for supermarket_id in chosen}

    for pid in product_ids:
        offers = {sm: cost for sm, cost in (cost_by_product.get(pid) or {}).items() if sm in chosen}
        if not offers:
            continue
        supermarket_id = min(offers, key=lambda sm: (offers[sm], -load[sm], sm))
        assigned[pid] = supermarket_id
        load[supermarket_id] += 1

    return assigned


def _best_single_total(
    cost_by_product: dict[str, dict[str, int]], covered_ids: list[str], supermarket_ids: list[str]
) -> int | None:
    """
    El mejor total de comprar en UN solo supermercado, medido sobre los mismos
    productos que cubre el plan dividido.

    Se compara contra los mismos productos y no contra la lista entera a
    propósito: si un producto no lo vende nadie, ningún supermercado lo tiene
    tampoco, y descontarlo de los dos lados es lo único que hace comparable el
    ahorro. Null si ningún supermercado los cubre a todos: ahí dividir no es la
    opción más barata, es la única.
    """
    if not covered_ids:
        return None

    totals = [
        sum(cost_by_product[pid][supermarket_id] for pid in covered_ids)
        for supermarket_id in supermarket_ids
        if all(supermarket_id in cost_by_product[pid] for pid in covered_ids)
    ]
    return min(totals) if totals else None


def split_list(list_id: UUID, user_id: UUID, max_supermarkets: int) -> SplitCompareResponse:
    """
    Arma el plan de compra más barato repartiendo la lista entre hasta
    `max_supermarkets` supermercados.

    1. Mismos datos y mismos filtros que compare_list: items en orden estable,
       precios con stock de supermercados activos de cadenas aprobadas.
    2. Costo por item redondeado (`round(price * quantity)`), igual que el
       comparador y que order_service. El total que promete el plan tiene que
       ser el que cobra el pedido.
    3. Si comprar cada producto donde está más barato usa como mucho
       `max_supermarkets` supermercados, ese ES el mínimo posible y no hay nada
       que buscar. Si usa más, se busca la mejor combinación acotada.
    4. Los productos que quedan sin cubrir —porque no los vende ningún
       supermercado visible, o porque no entran en el tope— se nombran en
       `missing`. Nunca se inventa un precio.
    """
    get_list_or_404(list_id, user_id)
    client = get_supabase()
    generated_at = datetime.now(timezone.utc)
    # El endpoint ya acota el rango; acá se vuelve a acotar porque el servicio
    # también se llama desde los tests y desde otros servicios a futuro.
    max_supermarkets = max(1, min(max_supermarkets, MAX_SPLIT_SUPERMARKETS))

    items = _list_items(client, list_id)
    if not items:
        return SplitCompareResponse(
            list_id=list_id,
            items_count=0,
            generated_at=generated_at,
            max_supermarkets=max_supermarkets,
            supermarkets_count=0,
            total=0,
            is_complete=False,
        )

    product_ids = [item["product_id"] for item in items]
    quantity_by_product = {item["product_id"]: item["quantity"] for item in items}
    name_by_product = {item["product_id"]: item["products"]["name"] for item in items}

    cost_by_product: dict[str, dict[str, int]] = {}
    price_by_product: dict[str, dict[str, int]] = {}
    supermarkets: dict[str, dict] = {}
    currency_by_supermarket: dict[str, str] = {}

    for row in _visible_prices(client, product_ids):
        supermarket = row["supermarkets"]
        supermarket_id = supermarket["id"]
        pid = row["product_id"]
        supermarkets[supermarket_id] = supermarket
        currency_by_supermarket[supermarket_id] = row["currency"]
        price_by_product.setdefault(pid, {})[supermarket_id] = row["price"]
        cost_by_product.setdefault(pid, {})[supermarket_id] = round(
            row["price"] * quantity_by_product[pid]
        )

    cheapest_anywhere = {
        pid: min(offers, key=lambda sm: (offers[sm], sm))
        for pid, offers in cost_by_product.items()
        if offers
    }
    unbounded_plan = set(cheapest_anywhere.values())

    if len(unbounded_plan) <= max_supermarkets:
        chosen = unbounded_plan
    else:
        candidates = _rank_candidates(cost_by_product, product_ids)
        chosen = _best_combination(
            cost_by_product, product_ids, candidates, min(max_supermarkets, len(candidates))
        )

    assigned = _assign_products(product_ids, cost_by_product, chosen)

    # Se recorre product_ids y no `assigned`: dentro de cada supermercado, los
    # productos salen en el orden en que el usuario armó la lista.
    items_by_supermarket: dict[str, list[SplitPlanItemOut]] = {}
    for pid in product_ids:
        supermarket_id = assigned.get(pid)
        if supermarket_id is None:
            continue
        items_by_supermarket.setdefault(supermarket_id, []).append(
            SplitPlanItemOut(
                product_id=pid,
                product_name=name_by_product[pid],
                quantity=quantity_by_product[pid],
                price=price_by_product[pid][supermarket_id],
                subtotal=cost_by_product[pid][supermarket_id],
            )
        )

    groups = [
        SplitPlanGroupOut(
            supermarket=supermarkets[supermarket_id],
            subtotal=sum(item.subtotal for item in plan_items),
            currency=currency_by_supermarket[supermarket_id],
            items=plan_items,
        )
        for supermarket_id, plan_items in items_by_supermarket.items()
    ]
    # La parada más grande primero: es la que define si el plan vale la pena.
    groups.sort(key=lambda g: (-g.subtotal, g.supermarket.name))

    missing = [
        CompareMissingItemOut(product_id=pid, product_name=name_by_product[pid])
        for pid in product_ids
        if pid not in assigned
    ]
    total = sum(group.subtotal for group in groups)
    best_single = _best_single_total(
        cost_by_product, [pid for pid in product_ids if pid in assigned], list(supermarkets)
    )
    # Clamp a 0: la búsqueda es exacta sobre los candidatos rankeados, no sobre
    # todos los supermercados del país, así que un ahorro negativo es posible
    # en teoría y es un número que no significa nada para el usuario.
    savings = max(0, best_single - total) if best_single is not None else 0

    return SplitCompareResponse(
        list_id=list_id,
        items_count=len(items),
        generated_at=generated_at,
        max_supermarkets=max_supermarkets,
        supermarkets_count=len(groups),
        total=total,
        currency=groups[0].currency if groups else None,
        is_complete=bool(groups) and not missing,
        missing=missing,
        best_single_total=best_single,
        savings=savings,
        groups=groups,
    )
