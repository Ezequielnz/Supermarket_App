"""
El importador de catálogo: una planilla del ERP -> precios y stock de una
sucursal.

Es la pieza que hace que cargar 4.000 productos no sea cargar 4.000
formularios. Su forma la define una sola decisión: **nunca escribe sin haber
podido mostrar antes qué va a escribir**. Por eso hay dos entradas —`preview` y
`run`— que comparten todo el análisis y se diferencian solo en si persisten.

Lo que el módulo NO hace, y es deliberado:

  * No adivina la identidad de un producto. Con código de barras matchea por
    código; sin él, solo por nombre completo —sin distinguir mayúsculas ni
    acentos, pero completo— y únicamente cuando ese nombre resuelve a un solo
    producto. Un nombre ambiguo se saltea con su motivo, porque vincular mal es
    peor que no vincular: el precio quedaría publicado sobre el producto de
    otra góndola (PLAN §5.1).
  * No edita el catálogo global. Si el EAN ya existe, se usa la fila que está y
    se descartan nombre y marca del archivo. Una cadena no reescribe la fila de
    la que cuelgan los precios de sus competidores (SEGURIDAD.md §4.2).
  * No confía en el `supermarket_id` que manda el cliente sin comprobarlo
    contra la cadena del JWT (SEGURIDAD.md §4.1).
"""

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status

from app.core.supabase_client import get_supabase
from app.schemas.auth import CurrentStaff
from app.schemas.catalog import DEFAULT_CURRENCY, ProductDraft
from app.schemas.product_import import (
    ACTION_CREATE,
    ACTION_ERROR,
    ACTION_SKIP,
    ACTION_UPDATE,
    MAX_ISSUES,
    PREVIEW_SAMPLE_SIZE,
    ImportColumnOut,
    ImportCounts,
    ImportIssue,
    ImportJobListResponse,
    ImportJobOut,
    ImportOptions,
    ImportPreviewResponse,
    ImportPreviewRow,
    ImportResultResponse,
)
from app.services import catalog_service, spreadsheet_reader
from app.services.import_mapping import (
    FIELD_BRAND,
    FIELD_CATEGORY,
    FIELD_EAN,
    FIELD_IMAGE_URL,
    FIELD_IN_STOCK,
    FIELD_NAME,
    FIELD_PRICE,
    FIELD_SIZE_UNIT,
    FIELD_SIZE_VALUE,
    FIELD_STOCK,
    FIELD_UNIT,
    IMPORT_FIELDS,
    CellError,
    detect_header_row,
    map_columns,
    normalize_header,
    parse_bool,
    parse_ean,
    parse_price_cents,
    parse_size_value,
    parse_stock,
    parse_text,
    parse_unit,
)
from app.services.supermarket_service import get_store_or_404

# PostgREST devuelve como máximo 1.000 filas por request: el catálogo de una
# sucursal grande se trae paginado o se trae incompleto (y un catálogo
# incompleto haría que el importador CREE lo que ya existe, chocando contra el
# UNIQUE de la 003).
_PAGE_SIZE = 1000

# Tamaño de los lotes contra Supabase. Ni una consulta por fila (N+1 con 4.000
# filas es inusable) ni todo junto (una URL con 4.000 EAN en un `in_` no entra).
_LOOKUP_CHUNK = 200
# El lote de nombres es más chico que el de EAN: cada condición ocupa mucho más
# en la URL (`name.ilike."Leche entera 1L"` contra 13 dígitos).
_NAME_LOOKUP_CHUNK = 50
_WRITE_CHUNK = 500

# Límites de los textos que van al catálogo global, iguales a los de
# ProductDraft: el importador entra por el mismo lugar que el formulario.
_MAX_NAME = 200
_MAX_BRAND = 120
_MAX_CATEGORY = 80
_MAX_IMAGE_URL = 500

_TEXT_LIMITS = {
    FIELD_NAME: _MAX_NAME,
    FIELD_BRAND: _MAX_BRAND,
    FIELD_CATEGORY: _MAX_CATEGORY,
    FIELD_IMAGE_URL: _MAX_IMAGE_URL,
}


@dataclass
class _Row:
    """Una fila del archivo, ya interpretada."""

    number: int  # 1-based, como la muestra Excel
    values: dict = field(default_factory=dict)
    errors: list[ImportIssue] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.values and not self.errors


@dataclass
class _PlannedRow:
    """Una fila con la decisión tomada, lista para ejecutarse o mostrarse."""

    row: _Row
    action: str
    product_id: str | None = None
    draft: dict | None = None       # producto global a crear, si hace falta
    listing: dict | None = None     # columnas de supermarket_products a escribir
    matched_name: str | None = None
    message: str | None = None


@dataclass
class _Plan:
    sheet_name: str
    sheet_names: list[str]
    header_index: int
    mapping: dict[str, int]
    headers: list[str]
    rows: list[_PlannedRow]
    issues: list[ImportIssue]
    truncated: bool
    # El catálogo de la sucursal tal como estaba al empezar. Se guarda porque
    # `deactivate_missing` lo necesita entero y volver a pedirlo sería traer
    # miles de filas dos veces por corrida.
    listings: list[dict]


# ── Lectura y mapeo ───────────────────────────────────────────────────────


def _resolve_mapping(sheet, options: ImportOptions) -> tuple[int, dict[str, int]]:
    """
    En qué fila está el encabezado y qué significa cada columna.

    El mapeo del usuario se aplica ENCIMA del automático y no en lugar de él:
    corregir una columna mal detectada no debería obligar a mapear las otras
    diez a mano.
    """
    if options.header_row is not None:
        header_index = options.header_row - 1
        if header_index >= len(sheet.rows):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La hoja «{sheet.name}» no tiene una fila {options.header_row}.",
            )
        mapping = map_columns(sheet.rows[header_index])
    else:
        header_index, mapping = detect_header_row(sheet.rows)

    column_count = max((len(row) for row in sheet.rows), default=0)
    for import_field, index in options.mapping.items():
        if import_field not in IMPORT_FIELDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"«{import_field}» no es un campo importable.",
            )
        if not 0 <= index < column_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La columna {index + 1} no existe en el archivo.",
            )
        # Una columna sirve para un solo campo: si el usuario reasigna la que
        # ya estaba usando otro, el otro se queda sin columna.
        for other in [f for f, i in mapping.items() if i == index and f != import_field]:
            mapping.pop(other)
        mapping[import_field] = index

    if header_index < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No encontramos la fila de encabezados. Revisá que el archivo tenga una "
                "columna con el nombre o el código de barras del producto y otra con el "
                "precio o el stock, o indicá a mano en qué fila están."
            ),
        )
    if FIELD_EAN not in mapping and FIELD_NAME not in mapping:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no tiene una columna de código de barras ni de nombre: no hay forma de saber de qué producto habla cada fila.",
        )
    if FIELD_PRICE not in mapping and FIELD_STOCK not in mapping:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no tiene una columna de precio ni de stock: no hay nada para actualizar.",
        )

    return header_index, mapping


_PARSERS = {
    FIELD_EAN: parse_ean,
    FIELD_PRICE: parse_price_cents,
    FIELD_STOCK: parse_stock,
    FIELD_IN_STOCK: parse_bool,
    FIELD_UNIT: parse_unit,
    FIELD_SIZE_UNIT: parse_unit,
    FIELD_SIZE_VALUE: parse_size_value,
}


def _parse_rows(sheet, header_index: int, mapping: dict[str, int]) -> list[_Row]:
    """
    Las filas de datos, celda por celda.

    Un error de celda NO corta la importación: se anota contra su fila y el
    resto del archivo sigue. Un export de 4.000 productos con 3 códigos de
    barras rotos tiene que entrar con 3.997, no fallar entero — y los 3 tienen
    que quedar dichos, con su número de fila.
    """
    headers = sheet.rows[header_index]
    rows: list[_Row] = []

    for offset, raw in enumerate(sheet.rows[header_index + 1 :]):
        row = _Row(number=header_index + offset + 2)  # +1 encabezado, +1 base 1
        if all(cell is None for cell in raw):
            rows.append(row)
            continue

        for import_field, index in mapping.items():
            value = raw[index] if index < len(raw) else None
            if value is None:
                continue
            try:
                if import_field in _PARSERS:
                    row.values[import_field] = _PARSERS[import_field](value)
                else:
                    row.values[import_field] = parse_text(
                        value, _TEXT_LIMITS.get(import_field, _MAX_NAME)
                    )
            except CellError as exc:
                row.errors.append(
                    ImportIssue(
                        row=row.number,
                        column=_header_label(headers, index),
                        field=import_field,
                        message=str(exc),
                    )
                )
        rows.append(row)

    return rows


def _header_label(headers: list, index: int) -> str:
    if index < len(headers) and headers[index] is not None:
        return str(headers[index])
    return f"Columna {index + 1}"


# ── Lo que ya está en la base ─────────────────────────────────────────────


def _load_store_listings(supermarket_id: UUID) -> list[dict]:
    """
    El catálogo actual de la sucursal, entero y paginado.

    Se trae una vez y sirve para las tres preguntas del importador: si la fila
    ya existe (crear vs. actualizar), qué valores conserva cuando el archivo no
    los trae, y qué productos NO estaban en el archivo (`deactivate_missing`).
    """
    client = get_supabase()
    listings: list[dict] = []
    offset = 0
    while True:
        page = (
            client.table("supermarket_products")
            .select("id, product_id, price, in_stock, stock_quantity, products(id, name, ean)")
            .eq("supermarket_id", str(supermarket_id))
            .range(offset, offset + _PAGE_SIZE - 1)
            .execute()
        ).data
        listings.extend(page)
        if len(page) < _PAGE_SIZE:
            return listings
        offset += _PAGE_SIZE


def _chunks(values: list, size: int):
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _load_products_by_ean(eans: list[str]) -> dict[str, dict]:
    if not eans:
        return {}
    client = get_supabase()
    found: dict[str, dict] = {}
    for chunk in _chunks(eans, _LOOKUP_CHUNK):
        rows = client.table("products").select("*").in_("ean", chunk).execute().data
        for row in rows:
            found[row["ean"]] = row
    return found


def _quote_filter_value(value: str) -> str:
    """
    Un valor de la planilla, listo para entrar en un filtro de PostgREST.

    Los nombres de producto traen comas, puntos y paréntesis, que en la sintaxis
    de PostgREST son separadores. Sin comillas, `Leche, entera (1L)` no es un
    valor: es el final de un filtro y el principio de otro que lo escribe quien
    sube el archivo. Se citan y se escapan la barra y la comilla, que es la
    regla que documenta PostgREST.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _load_products_by_name(names: list[str]) -> dict[str, list[dict]]:
    """
    Productos globales por nombre, agrupados por nombre normalizado.

    La búsqueda es `ilike` sin comodines —es decir, igualdad sin distinguir
    mayúsculas— y no `in_`, porque los ERP exportan los nombres EN MAYÚSCULAS:
    con una comparación exacta, `LECHE ENTERA 1L` no matchearía la fila `Leche
    entera 1L` que ya está en el catálogo y el importador la duplicaría.

    Un `%` dentro de un nombre real (`Leche 0% grasa`) sí es un comodín para
    ilike y puede traer filas de más. No hace falta escaparlo: el agrupamiento
    es por nombre NORMALIZADO, así que una fila que solo matcheó por el comodín
    cae bajo otra clave y nunca se usa para vincular.

    Se agrupa en vez de quedarse con el primero porque el resultado importa: si
    un nombre trae dos filas, el importador NO elige — saltea y lo dice. Elegir
    una al azar publicaría el precio sobre el producto equivocado.
    """
    if not names:
        return {}
    client = get_supabase()
    by_name: dict[str, list[dict]] = {}
    for chunk in _chunks(names, _NAME_LOOKUP_CHUNK):
        conditions = ",".join(f"name.ilike.{_quote_filter_value(name)}" for name in chunk)
        rows = client.table("products").select("*").or_(conditions).execute().data
        for row in rows:
            by_name.setdefault(normalize_header(row["name"]), []).append(row)
    return by_name


# ── El plan ───────────────────────────────────────────────────────────────


def _draft_from(row: _Row) -> dict:
    """Las columnas de `products` que propone una fila del archivo."""
    return {
        "name": row.values.get(FIELD_NAME),
        "ean": row.values.get(FIELD_EAN),
        "brand": row.values.get(FIELD_BRAND),
        "unit": row.values.get(FIELD_UNIT),
        "size_value": row.values.get(FIELD_SIZE_VALUE),
        "size_unit": row.values.get(FIELD_SIZE_UNIT),
        "category": row.values.get(FIELD_CATEGORY),
        "image_url": row.values.get(FIELD_IMAGE_URL),
    }


def _listing_columns(row: _Row, existing: dict | None, supermarket_id: UUID) -> dict:
    """
    Qué se va a escribir en `supermarket_products` para esta fila.

    Todas las filas llevan el MISMO juego de columnas, con los valores que no
    trae el archivo completados desde la fila que ya existe. Eso es lo que
    permite mandar altas y modificaciones juntas en un solo upsert, y es
    también lo que garantiza que un archivo de solo-stock no pise los precios
    con nulos.

    La regla del `in_stock` merece leerse dos veces:

      * Si el archivo tiene una columna de activo/inactivo, manda esa.
      * Si no, y el archivo trae stock: 0 apaga (lo fuerza igual el trigger de
        la 024) y un stock positivo sobre una fila que HOY está en 0 vuelve a
        publicar. Ese 0 solo pudo haberlo puesto una venta o un import
        anterior, nunca una decisión humana — con cantidad 0 el trigger no deja
        que `in_stock` quede en true. Reponer stock tiene que volver a poner el
        producto en la góndola; si no, cada producto agotado necesitaría que
        alguien se acuerde de reactivarlo a mano.
      * En cualquier otro caso se conserva lo que hay: un import de precios no
        despublica ni publica nada.
    """
    price = row.values.get(FIELD_PRICE)
    stock = row.values.get(FIELD_STOCK)

    if existing is not None:
        in_stock = existing["in_stock"]
        if stock is not None:
            existing_stock = existing.get("stock_quantity")
            if stock <= 0:
                in_stock = False
            elif existing_stock is not None and Decimal(str(existing_stock)) <= 0:
                in_stock = True
    else:
        in_stock = stock is None or stock > 0

    if FIELD_IN_STOCK in row.values:
        in_stock = row.values[FIELD_IN_STOCK]

    return {
        "supermarket_id": str(supermarket_id),
        "price": price if price is not None else (existing or {}).get("price"),
        "currency": DEFAULT_CURRENCY,
        "in_stock": in_stock,
        "stock_quantity": (
            float(stock) if stock is not None else (existing or {}).get("stock_quantity")
        ),
    }


def _build_plan(
    content: bytes, filename: str, supermarket_id: UUID, options: ImportOptions
) -> _Plan:
    """
    Lee el archivo y decide, fila por fila, qué correspondería hacer. No escribe
    nada: es lo mismo que ejecuta `preview` y lo que `run` después aplica.
    """
    sheet = spreadsheet_reader.read(content, filename, options.sheet_name)
    header_index, mapping = _resolve_mapping(sheet, options)
    rows = _parse_rows(sheet, header_index, mapping)

    listings = _load_store_listings(supermarket_id)
    listing_by_product = {row["product_id"]: row for row in listings}
    # Índice por nombre del catálogo PROPIO: es el matcheo que resuelve el caso
    # más común de un archivo sin código de barras, que es el ERP reexportando
    # los mismos productos que esta sucursal ya cargó.
    listing_by_name: dict[str, list[dict]] = {}
    for row in listings:
        product = row.get("products") or {}
        if product.get("name"):
            listing_by_name.setdefault(normalize_header(product["name"]), []).append(row)

    eans = [r.values[FIELD_EAN] for r in rows if FIELD_EAN in r.values]
    products_by_ean = _load_products_by_ean(sorted(set(eans)))

    unresolved_names = sorted(
        {
            r.values[FIELD_NAME]
            for r in rows
            if FIELD_NAME in r.values
            and FIELD_EAN not in r.values
            and normalize_header(r.values[FIELD_NAME]) not in listing_by_name
        }
    )
    products_by_name = _load_products_by_name(unresolved_names)

    planned: list[_PlannedRow] = []
    issues: list[ImportIssue] = []
    # Un mismo producto dos veces en el archivo: la segunda fila ya no es un
    # alta. Sin este set, las dos se planifican como alta y el upsert deja la
    # última en silencio; peor, `products_created` mentiría.
    seen_products: set[str] = set()
    seen_drafts: dict[str, _PlannedRow] = {}

    for row in rows:
        if row.is_empty:
            continue

        if row.errors:
            issues.extend(row.errors)
            planned.append(
                _PlannedRow(row=row, action=ACTION_ERROR, message=row.errors[0].message)
            )
            continue

        ean = row.values.get(FIELD_EAN)
        name = row.values.get(FIELD_NAME)
        if not ean and not name:
            planned.append(
                _PlannedRow(
                    row=row,
                    action=ACTION_ERROR,
                    message="La fila no tiene código de barras ni nombre.",
                )
            )
            issues.append(
                ImportIssue(row=row.number, message="La fila no tiene código de barras ni nombre.")
            )
            continue

        product = _match_product(row, ean, name, products_by_ean, listing_by_name, products_by_name)
        if isinstance(product, str):  # motivo por el que no se pudo resolver
            planned.append(_PlannedRow(row=row, action=ACTION_SKIP, message=product))
            issues.append(ImportIssue(row=row.number, message=product))
            continue

        planned.append(
            _plan_row(row, product, listing_by_product, supermarket_id, options, seen_products, seen_drafts)
        )

    return _Plan(
        sheet_name=sheet.name,
        sheet_names=[],
        header_index=header_index,
        mapping=mapping,
        headers=[
            "" if cell is None else str(cell) for cell in sheet.rows[header_index]
        ],
        rows=planned,
        issues=issues,
        truncated=sheet.truncated,
        listings=listings,
    )


def _match_product(
    row: _Row,
    ean: str | None,
    name: str | None,
    products_by_ean: dict[str, dict],
    listing_by_name: dict[str, list[dict]],
    products_by_name: dict[str, list[dict]],
) -> dict | None | str:
    """
    A qué producto global se refiere la fila.

    Devuelve la fila de `products` si lo encontró, `None` si hay que crearlo, o
    un string con el motivo si hay que saltearla. Los tres casos son
    resultados legítimos: saltear con motivo es mejor que vincular al azar.
    """
    if ean:
        found = products_by_ean.get(ean)
        if found is not None:
            return found
        if not name:
            return f"El código de barras {ean} no está en el catálogo y la fila no trae nombre para darlo de alta."
        return None  # se crea con este EAN

    key = normalize_header(name)

    own = listing_by_name.get(key, [])
    if len(own) == 1:
        return own[0]["products"]
    if len(own) > 1:
        return f"«{name}» aparece más de una vez en el catálogo de esta sucursal. Cargá el código de barras para distinguirlos."

    globals_found = products_by_name.get(key, [])
    if len(globals_found) == 1:
        return globals_found[0]
    if len(globals_found) > 1:
        return f"Hay {len(globals_found)} productos con el nombre «{name}». Agregá el código de barras a esa fila."

    return None  # producto nuevo, sin EAN


def _plan_row(
    row: _Row,
    product: dict | None,
    listing_by_product: dict[str, dict],
    supermarket_id: UUID,
    options: ImportOptions,
    seen_products: set[str],
    seen_drafts: dict[str, _PlannedRow],
) -> _PlannedRow:
    product_id = product["id"] if product else None
    existing = listing_by_product.get(product_id) if product_id else None

    if existing is not None:
        if not options.update_existing:
            return _PlannedRow(
                row=row, action=ACTION_SKIP, product_id=product_id,
                matched_name=(product or {}).get("name"),
                message="Ya estaba cargado y la importación no actualiza existentes.",
            )
        if product_id in seen_products:
            return _PlannedRow(
                row=row, action=ACTION_SKIP, product_id=product_id,
                matched_name=(product or {}).get("name"),
                message="El producto aparece más de una vez en el archivo; se toma la primera fila.",
            )
        seen_products.add(product_id)
        return _PlannedRow(
            row=row, action=ACTION_UPDATE, product_id=product_id,
            matched_name=(product or {}).get("name"),
            listing=_listing_columns(row, existing, supermarket_id),
        )

    if not options.create_missing:
        return _PlannedRow(
            row=row, action=ACTION_SKIP, product_id=product_id,
            matched_name=(product or {}).get("name"),
            message="No está en el catálogo de la sucursal y la importación no da de alta.",
        )

    # Un alta necesita precio sí o sí: `supermarket_products.price` es NOT NULL
    # y no hay ningún valor razonable para inventar. Un archivo de solo stock
    # actualiza lo que existe y reporta el resto.
    if row.values.get(FIELD_PRICE) is None:
        return _PlannedRow(
            row=row, action=ACTION_ERROR, product_id=product_id,
            matched_name=(product or {}).get("name"),
            message="Falta el precio y el producto todavía no está cargado en esta sucursal.",
        )

    if product_id is not None:
        if product_id in seen_products:
            return _PlannedRow(
                row=row, action=ACTION_SKIP, product_id=product_id,
                message="El producto aparece más de una vez en el archivo; se toma la primera fila.",
            )
        seen_products.add(product_id)
        return _PlannedRow(
            row=row, action=ACTION_CREATE, product_id=product_id,
            matched_name=(product or {}).get("name"),
            listing=_listing_columns(row, None, supermarket_id),
        )

    # Producto que tampoco existe en el catálogo global: hay que crearlo.
    draft = _draft_from(row)
    key = draft["ean"] or normalize_header(draft["name"])
    if key in seen_drafts:
        return _PlannedRow(
            row=row, action=ACTION_SKIP,
            message="El producto aparece más de una vez en el archivo; se toma la primera fila.",
        )

    planned = _PlannedRow(
        row=row, action=ACTION_CREATE, draft=draft,
        listing=_listing_columns(row, None, supermarket_id),
    )
    seen_drafts[key] = planned
    return planned


# ── Vista previa ──────────────────────────────────────────────────────────


def _counts(plan: _Plan) -> ImportCounts:
    counts = ImportCounts()
    for planned in plan.rows:
        counts.rows_total += 1
        if planned.action == ACTION_CREATE:
            counts.listings_created += 1
            if planned.draft is not None:
                counts.products_created += 1
        elif planned.action == ACTION_UPDATE:
            counts.listings_updated += 1
        elif planned.action == ACTION_SKIP:
            counts.rows_skipped += 1
        else:
            counts.rows_failed += 1
    return counts


def _to_preview_row(planned: _PlannedRow) -> ImportPreviewRow:
    listing = planned.listing or {}
    return ImportPreviewRow(
        row=planned.row.number,
        action=planned.action,
        ean=planned.row.values.get(FIELD_EAN),
        name=planned.row.values.get(FIELD_NAME),
        price=listing.get("price") if listing else planned.row.values.get(FIELD_PRICE),
        stock_quantity=listing.get("stock_quantity"),
        in_stock=listing.get("in_stock"),
        matched_product_name=planned.matched_name,
        message=planned.message,
    )


def _sample(plan: _Plan) -> list[ImportPreviewRow]:
    """
    Las filas de ejemplo, con los problemas adelante.

    Mostrar las primeras 15 del archivo sería mostrar 15 filas correctas y
    esconder los 40 errores que están más abajo. Lo que el encargado necesita
    ver antes de confirmar es justamente lo que no va a entrar.
    """
    priority = {ACTION_ERROR: 0, ACTION_SKIP: 1, ACTION_CREATE: 2, ACTION_UPDATE: 3}
    ordered = sorted(plan.rows, key=lambda p: (priority[p.action], p.row.number))
    return [_to_preview_row(planned) for planned in ordered[:PREVIEW_SAMPLE_SIZE]]


def preview(
    content: bytes, filename: str, supermarket_id: UUID, chain_id: UUID, options: ImportOptions
) -> ImportPreviewResponse:
    """
    Qué haría la importación, sin tocar la base.

    La validación de que la sucursal es de esta cadena va PRIMERO, antes de
    abrir el archivo: sin eso, el staff de la cadena A podría usar la vista
    previa para leer el catálogo de una sucursal de la B (los conteos de
    "actualiza N" y los nombres matcheados son información del catálogo ajeno).
    """
    get_store_or_404(supermarket_id, chain_id)
    plan = _build_plan(content, filename, supermarket_id, options)
    plan.sheet_names = spreadsheet_reader.list_sheet_names(content, filename)

    counts = _counts(plan)
    if options.deactivate_missing:
        counts.listings_deactivated = len(_missing_listing_ids(plan))

    mapped_columns = {index: name for name, index in plan.mapping.items()}
    columns = [
        ImportColumnOut(index=index, header=header, field=mapped_columns.get(index))
        for index, header in enumerate(plan.headers)
    ]

    return ImportPreviewResponse(
        file_name=filename,
        sheet_name=plan.sheet_name,
        sheet_names=plan.sheet_names,
        header_row=plan.header_index + 1,
        columns=columns,
        mapping=plan.mapping,
        unmapped_headers=[c.header for c in columns if c.field is None and c.header],
        truncated=plan.truncated,
        counts=counts,
        sample=_sample(plan),
        issues=plan.issues[:MAX_ISSUES],
    )


# ── Ejecución ─────────────────────────────────────────────────────────────


def _missing_listing_ids(plan: _Plan) -> list[str]:
    """
    Los productos que la sucursal tiene cargados y el archivo NO menciona.

    Solo se calcula cuando el usuario pidió `deactivate_missing`, y solo tiene
    sentido si el archivo es el catálogo completo. Por eso el flag es opt-in y
    la vista previa muestra el número antes de confirmar: "vas a despublicar
    3.812 productos" es la única forma de que un export filtrado no vacíe la
    góndola en silencio.
    """
    touched = {p.product_id for p in plan.rows if p.product_id and p.action != ACTION_ERROR}
    return [
        row["id"]
        for row in plan.listings
        if row["product_id"] not in touched and row["in_stock"]
    ]


def _create_products(plan: _Plan, chain_id: UUID) -> int:
    """
    Crea los productos globales que faltan y completa el `product_id` de las
    filas que los esperaban.

    Fila por fila y no en lote a propósito: `catalog_service.resolve_product` es
    la ÚNICA puerta de entrada al catálogo compartido, y es la que resuelve la
    carrera contra otra cadena cargando el mismo EAN entre el SELECT y el
    INSERT. Duplicar esa lógica acá para ahorrar viajes sería duplicar
    justamente lo que hay que no equivocarse (PLAN §5.1).
    """
    created = 0
    for planned in plan.rows:
        if planned.action != ACTION_CREATE or planned.draft is None:
            continue
        try:
            product = catalog_service.resolve_product(
                ProductDraft(**{k: v for k, v in planned.draft.items() if v is not None}),
                chain_id,
            )
        except HTTPException as exc:
            planned.action = ACTION_ERROR
            planned.message = exc.detail if isinstance(exc.detail, str) else "No se pudo crear el producto."
            plan.issues.append(ImportIssue(row=planned.row.number, message=planned.message))
            continue
        except ValueError as exc:
            # El draft no pasó la validación de ProductDraft (un nombre de 300
            # caracteres, un EAN que el CHECK rechaza). Es un problema de esa
            # fila, no de la corrida.
            planned.action = ACTION_ERROR
            planned.message = f"Los datos del producto no son válidos: {exc}"
            plan.issues.append(ImportIssue(row=planned.row.number, message=planned.message))
            continue

        planned.product_id = product["id"]
        created += 1
    return created


def _write_listings(plan: _Plan) -> None:
    """
    Precios y stock, en lotes, con un solo upsert para altas y modificaciones.

    Es posible porque `_listing_columns` completa todas las columnas para las
    dos: PostgREST exige que las filas de un mismo upsert tengan las mismas
    claves, y el UNIQUE(supermarket_id, product_id) de la 003 es el que
    convierte el INSERT en UPDATE donde corresponde. El trigger
    record_price_change (016) archiva el precio anterior de cada fila
    modificada sin que el importador tenga que hacer nada.
    """
    payload = [
        {**planned.listing, "product_id": planned.product_id}
        for planned in plan.rows
        if planned.action in (ACTION_CREATE, ACTION_UPDATE)
        and planned.listing is not None
        and planned.product_id is not None
    ]
    if not payload:
        return

    client = get_supabase()
    for chunk in _chunks(payload, _WRITE_CHUNK):
        try:
            client.table("supermarket_products").upsert(
                chunk, on_conflict="supermarket_id,product_id"
            ).execute()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="No se pudieron guardar todos los precios. Volvé a subir el archivo: las filas ya guardadas se actualizan, no se duplican.",
            )


def _deactivate(listing_ids: list[str]) -> int:
    if not listing_ids:
        return 0
    client = get_supabase()
    for chunk in _chunks(listing_ids, _WRITE_CHUNK):
        client.table("supermarket_products").update({"in_stock": False}).in_("id", chunk).execute()
    return len(listing_ids)


def _record_job(
    staff: CurrentStaff,
    supermarket_id: UUID,
    filename: str,
    plan: _Plan,
    counts: ImportCounts,
) -> str:
    client = get_supabase()
    result = (
        client.table("product_import_jobs")
        .insert(
            {
                "chain_id": str(staff.chain_id),
                "supermarket_id": str(supermarket_id),
                "created_by": str(staff.id),
                "file_name": filename[:200],
                "sheet_name": plan.sheet_name,
                "column_mapping": plan.mapping,
                "rows_total": counts.rows_total,
                "listings_created": counts.listings_created,
                "listings_updated": counts.listings_updated,
                "products_created": counts.products_created,
                "rows_skipped": counts.rows_skipped,
                "rows_failed": counts.rows_failed,
                "issues": [issue.model_dump() for issue in plan.issues[:MAX_ISSUES]],
            }
        )
        .execute()
    )
    return result.data[0]["id"]


def run(
    content: bytes,
    filename: str,
    supermarket_id: UUID,
    staff: CurrentStaff,
    options: ImportOptions,
) -> ImportResultResponse:
    """
    Aplica la importación: crea los productos que faltan, escribe precios y
    stock, y deja la corrida registrada en `product_import_jobs`.

    No es transaccional de punta a punta, y es una limitación consciente: son
    miles de filas contra PostgREST, no una función de Postgres. La escritura
    está ordenada para que una caída a mitad de camino deje datos coherentes y
    no basura — primero los productos globales (idempotentes por EAN), después
    los precios (idempotentes por el UNIQUE de la sucursal). Reintentar el
    mismo archivo converge al mismo estado.
    """
    get_store_or_404(supermarket_id, staff.chain_id)
    plan = _build_plan(content, filename, supermarket_id, options)

    to_deactivate = _missing_listing_ids(plan) if options.deactivate_missing else []

    products_created = _create_products(plan, staff.chain_id)
    _write_listings(plan)

    counts = _counts(plan)
    # El conteo sale de lo que se creó de verdad y no de `_counts`, que cuenta
    # intenciones: una fila cuyo producto no se pudo crear ya es un error.
    counts.products_created = products_created
    counts.listings_deactivated = _deactivate(to_deactivate)

    job_id = _record_job(staff, supermarket_id, filename, plan, counts)

    return ImportResultResponse(
        job_id=job_id,
        file_name=filename,
        sheet_name=plan.sheet_name,
        counts=counts,
        issues=plan.issues[:MAX_ISSUES],
    )


def list_jobs(chain_id: UUID, page: int, per_page: int) -> ImportJobListResponse:
    """El historial de importaciones de la cadena, de la más reciente a la más vieja."""
    client = get_supabase()
    offset = (page - 1) * per_page
    result = (
        client.table("product_import_jobs")
        .select("*", count="exact")
        .eq("chain_id", str(chain_id))
        .order("created_at", desc=True)
        .range(offset, offset + per_page - 1)
        .execute()
    )
    return ImportJobListResponse(
        data=[ImportJobOut(**row) for row in result.data],
        total=result.count or 0,
        page=page,
        per_page=per_page,
    )
