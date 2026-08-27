"""
Qué significa cada columna de la planilla, y qué dice cada celda.

Es la mitad del importador que traduce el vocabulario del ERP al del catálogo:
`COD.BARRA`, `EAN13` y `Código de barras` son todos `ean`; `PRECIO VTA`,
`P.V.P.` e `Importe` son todos `price`. Sin esto, cada supermercado tendría que
reformatear su export a mano, que es exactamente el trabajo que el importador
existe para evitar.

Dos reglas gobiernan el módulo:

  * Reconocer de más es peor que no reconocer. Mapear `PRECIO COSTO` como
    precio de venta publica el costo del supermercado a sus competidores. Ante
    la duda, la columna queda sin mapear y el panel la pide a mano.
  * Nada se inventa. Una celda que no se entiende es un error de esa fila con
    su motivo, nunca un valor por default silencioso.
"""

import re
import unicodedata
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

# Campos canónicos. Espejan las columnas de `products` y
# `supermarket_products`; son las claves de todo el importador.
FIELD_EAN = "ean"
FIELD_NAME = "name"
FIELD_BRAND = "brand"
FIELD_PRICE = "price"
FIELD_STOCK = "stock_quantity"
FIELD_IN_STOCK = "in_stock"
FIELD_UNIT = "unit"
FIELD_SIZE_VALUE = "size_value"
FIELD_SIZE_UNIT = "size_unit"
FIELD_CATEGORY = "category"
FIELD_IMAGE_URL = "image_url"

IMPORT_FIELDS = (
    FIELD_EAN, FIELD_NAME, FIELD_BRAND, FIELD_PRICE, FIELD_STOCK, FIELD_IN_STOCK,
    FIELD_UNIT, FIELD_SIZE_VALUE, FIELD_SIZE_UNIT, FIELD_CATEGORY, FIELD_IMAGE_URL,
)

# Sin al menos uno de estos dos no hay forma de saber de qué producto habla la
# fila. El EAN es identidad (PLAN §5.1); el nombre, el último recurso.
IDENTITY_FIELDS = (FIELD_EAN, FIELD_NAME)

# Cuántas filas del principio se miran buscando el encabezado. Un export con
# logo, título y fecha arriba de la tabla es lo normal, no la excepción.
HEADER_SCAN_ROWS = 15

# Espeja el enum product_unit de la migración 008.
PRODUCT_UNITS = ("kg", "g", "L", "ml", "un")


# ── Sinónimos ─────────────────────────────────────────────────────────────
# El orden dentro de cada tupla no importa; lo que importa es que sean frases
# NORMALIZADAS (sin acentos, en minúscula, sin puntuación). Agregar un sinónimo
# es la forma prevista de soportar el ERP de un supermercado nuevo.
FIELD_SYNONYMS: dict[str, tuple[str, ...]] = {
    FIELD_EAN: (
        "ean", "ean13", "ean 13", "codigo de barras", "codigo barras", "cod barras",
        "cod barra", "codbarra", "codigo ean", "barcode", "bar code", "gtin", "upc",
        "codigo de barra", "cbarra",
    ),
    FIELD_NAME: (
        "nombre", "nombre del producto", "producto", "descripcion",
        "descripcion del producto", "descripcion articulo", "detalle", "articulo",
        "denominacion", "name", "product", "product name", "description", "item",
    ),
    FIELD_BRAND: ("marca", "brand", "fabricante", "manufacturer"),
    FIELD_PRICE: (
        "precio", "precio de venta", "precio venta", "precio vta", "precio publico",
        "precio al publico", "precio unitario", "precio lista", "precio de lista",
        "pvp", "p v p", "importe", "valor", "price", "sale price", "retail price",
        "unit price", "precio final",
    ),
    FIELD_STOCK: (
        "stock", "stock actual", "stock disponible", "existencia", "existencias",
        "cantidad", "cant", "cantidad disponible", "inventario", "saldo",
        "quantity", "qty", "on hand", "stock on hand",
    ),
    FIELD_IN_STOCK: (
        "activo", "publicado", "habilitado", "disponible", "en venta", "vigente",
        "estado", "active", "enabled", "available", "published",
    ),
    FIELD_UNIT: (
        "unidad", "unidad de medida", "um", "u m", "unidad medida", "medida",
        "unit", "uom", "unit of measure",
    ),
    FIELD_SIZE_VALUE: (
        "contenido", "contenido neto", "peso", "peso neto", "volumen", "tamano",
        "capacidad", "size", "net weight", "content", "gramaje",
    ),
    FIELD_SIZE_UNIT: (
        "unidad de contenido", "unidad contenido", "unidad de tamano",
        "unidad de peso", "size unit", "unidad envase",
    ),
    FIELD_CATEGORY: (
        "categoria", "rubro", "familia", "seccion", "departamento", "grupo",
        "linea", "category", "department", "aisle",
    ),
    FIELD_IMAGE_URL: (
        "imagen", "foto", "url imagen", "url de imagen", "link imagen", "image",
        "image url", "picture", "photo",
    ),
}

# Palabras que DESCALIFICAN una columna para un campo, aunque el resto del
# encabezado coincida. `PRECIO COSTO` y `PRECIO ANTERIOR` matchean "precio"
# igual de bien que `PRECIO VENTA`, y publicar cualquiera de los dos como
# precio de venta es un error caro: el primero filtra el margen del
# supermercado, el segundo desactualiza toda la góndola.
FIELD_NEGATIVE_HINTS: dict[str, tuple[str, ...]] = {
    FIELD_PRICE: (
        "costo", "compra", "cost", "proveedor", "anterior", "viejo", "old",
        "sin iva", "neto", "descuento", "oferta", "promo", "mayorista",
    ),
    FIELD_STOCK: ("minimo", "maximo", "min", "max", "reposicion", "comprometido", "pedido"),
    FIELD_NAME: ("corto", "abreviado", "interno"),
}

# Valores de verdad que aparecen en la columna "activo" de un export.
_TRUE_WORDS = {
    "1", "si", "s", "sí", "true", "t", "verdadero", "x", "yes", "y", "activo",
    "activa", "habilitado", "disponible", "en venta", "vigente", "alta", "ok",
}
_FALSE_WORDS = {
    "0", "no", "n", "false", "f", "falso", "inactivo", "inactiva", "deshabilitado",
    "no disponible", "baja", "suspendido", "discontinuado",
}

# Sinónimos de unidad -> valor del enum. La clave va normalizada.
_UNIT_WORDS: dict[str, str] = {
    "kg": "kg", "kgs": "kg", "kilo": "kg", "kilos": "kg", "kilogramo": "kg",
    "kilogramos": "kg", "k": "kg",
    "g": "g", "gr": "g", "grs": "g", "gramo": "g", "gramos": "g", "grm": "g",
    "l": "L", "lt": "L", "lts": "L", "litro": "L", "litros": "L", "ltr": "L",
    "ml": "ml", "mililitro": "ml", "mililitros": "ml", "cc": "ml", "cm3": "ml",
    "un": "un", "u": "un", "uni": "un", "unid": "un", "unidad": "un",
    "unidades": "un", "c u": "un", "cu": "un", "pza": "un", "pieza": "un",
    "each": "un", "ea": "un", "paquete": "un", "pack": "un", "bulto": "un",
}

# El importador escribe precios en centavos (NORMAS.md §4.3) y stock con dos
# decimales, igual que supermarket_products.stock_quantity.
_CENTS_PER_UNIT = Decimal(100)
_STOCK_QUANTUM = Decimal("0.01")

# Tope defensivo: `price` es INTEGER en Postgres. Un export con el precio en
# una celda equivocada (un teléfono, un CUIT) reventaría el INSERT con un error
# de rango que sale como 500. Se corta acá, con un mensaje que dice la fila.
MAX_PRICE_CENTS = 2_000_000_000
MAX_STOCK = Decimal("99999999.99")

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_DIGITS = re.compile(r"\d+")


def normalize_header(text) -> str:
    """
    `«  Precio de Venta ($) »` -> `precio de venta`.

    Saca acentos, mayúsculas y toda la puntuación, que es donde está la mayor
    parte de la variación entre un ERP y otro. Lo que queda son palabras
    separadas por un espacio, que es contra lo que matchean los sinónimos.
    """
    if text is None:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(text)).lower()
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _NON_ALNUM.sub(" ", without_accents).strip()


def _score_column(header: str, field: str) -> int:
    """
    Cuánto se parece este encabezado a este campo. 0 = no lo es.

    Tres niveles, y la distancia entre ellos es deliberada: una coincidencia
    exacta le gana siempre a una parcial, y entre parciales gana la del
    sinónimo más largo (`precio de venta` describe mejor a `PRECIO DE VENTA
    UNITARIO` que el genérico `precio`).
    """
    if not header:
        return 0

    for hint in FIELD_NEGATIVE_HINTS.get(field, ()):
        if hint in header:
            return 0

    synonyms = FIELD_SYNONYMS[field]
    if header in synonyms:
        return 1000

    best = 0
    for synonym in synonyms:
        if header.startswith(synonym + " ") or header.endswith(" " + synonym):
            best = max(best, 500 + len(synonym))
        elif f" {synonym} " in f" {header} ":
            best = max(best, 200 + len(synonym))
    return best


def map_columns(header_cells: list) -> dict[str, int]:
    """
    Encabezados -> {campo canónico: índice de columna}.

    Asignación golosa por puntaje: se ordenan todos los pares (columna, campo)
    con puntaje > 0 de mayor a menor y se va tomando el mejor que deje libres a
    los dos lados. Así, con `PRECIO COSTO` y `PRECIO VENTA` en la misma
    planilla, `price` se lleva la segunda —la primera ni siquiera compite,
    porque los hints negativos la dejaron en 0— y ninguna columna queda
    representando a dos campos.
    """
    headers = [normalize_header(cell) for cell in header_cells]

    scored = []
    for index, header in enumerate(headers):
        for field in IMPORT_FIELDS:
            score = _score_column(header, field)
            if score > 0:
                scored.append((score, index, field))
    scored.sort(key=lambda item: (-item[0], item[1]))

    mapping: dict[str, int] = {}
    used_columns: set[int] = set()
    for _, index, field in scored:
        if field in mapping or index in used_columns:
            continue
        mapping[field] = index
        used_columns.add(index)
    return mapping


def detect_header_row(rows: list[list]) -> tuple[int, dict[str, int]]:
    """
    Encuentra la fila de encabezado y su mapeo, o (-1, {}) si no hay ninguna.

    Un export de ERP casi nunca arranca en A1: arriba suele haber un título, la
    fecha del reporte, el nombre de la sucursal. En vez de pedirle al usuario
    que diga en qué fila empieza la tabla, se prueban las primeras
    `HEADER_SCAN_ROWS` y gana la que reconoce más campos.

    El criterio de "es un encabezado válido" no es el puntaje: es tener con qué
    identificar al producto (EAN o nombre) Y el precio o el stock. Una fila con
    solo `CATEGORIA` reconocido no es la tabla, es ruido.
    """
    best_index = -1
    best_mapping: dict[str, int] = {}
    best_score = 0

    for index, row in enumerate(rows[:HEADER_SCAN_ROWS]):
        mapping = map_columns(row)
        if not any(field in mapping for field in IDENTITY_FIELDS):
            continue
        if FIELD_PRICE not in mapping and FIELD_STOCK not in mapping:
            continue
        score = len(mapping)
        if score > best_score:
            best_index, best_mapping, best_score = index, mapping, score

    return best_index, best_mapping


# ── Lectura de celdas ─────────────────────────────────────────────────────


class CellError(ValueError):
    """
    Una celda que no se pudo interpretar. El servicio la convierte en un issue
    con su número de fila y su columna; nunca en un valor por default.
    """


def _to_decimal(value) -> Decimal:
    """
    Una celda -> Decimal, resolviendo el problema de los separadores.

    Excel entrega números como float y ahí no hay nada que decidir. El caso
    difícil es el texto, porque `1.234` significa mil doscientos treinta y
    cuatro en un export en español y uno con veinticuatro centésimos en uno en
    inglés, y el archivo no dice cuál es cuál. Las reglas, en orden:

      1. Si están los dos separadores, el ÚLTIMO es el decimal: `1.234,56` es
         español y `1,234.56` es inglés. Esto no falla nunca.
      2. Con un solo separador y exactamente 3 dígitos detrás (`1.234`,
         `1,234`), es separador de miles. Los precios y los stocks reales no
         se escriben con tres decimales, y en ARS un producto de $1.234 es
         muchísimo más probable que uno de $1,234.
      3. Con un solo separador y otra cantidad de dígitos (`1234,5`,
         `19.99`), es decimal.
    """
    if isinstance(value, bool):
        raise CellError("Se esperaba un número.")
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))

    text = str(value).strip()
    if not text:
        raise CellError("Se esperaba un número.")

    # Símbolos de moneda, espacios finos, el signo de porcentaje que dejan
    # algunos exports, y los espacios que se usan como separador de miles.
    text = re.sub(r"[^0-9,.\-]", "", text.replace(" ", ""))
    if not text or text in ("-", ".", ","):
        raise CellError("Se esperaba un número.")

    has_dot, has_comma = "." in text, "," in text
    if has_dot and has_comma:
        decimal_sep = "," if text.rfind(",") > text.rfind(".") else "."
        thousands_sep = "." if decimal_sep == "," else ","
        text = text.replace(thousands_sep, "").replace(decimal_sep, ".")
    elif has_dot or has_comma:
        separator = "." if has_dot else ","
        head, _, tail = text.rpartition(separator)
        if len(tail) == 3 and head:
            text = text.replace(separator, "")
        else:
            text = text.replace(separator, ".")

    try:
        return Decimal(text)
    except InvalidOperation:
        raise CellError("Se esperaba un número.")


def parse_price_cents(value) -> int:
    """El precio de la planilla, en centavos. Siempre entero (NORMAS.md §4.3)."""
    amount = _to_decimal(value)
    if amount <= 0:
        raise CellError("El precio tiene que ser mayor a cero.")

    cents = int((amount * _CENTS_PER_UNIT).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    if cents <= 0:
        raise CellError("El precio tiene que ser mayor a cero.")
    if cents > MAX_PRICE_CENTS:
        raise CellError("El precio es demasiado grande. ¿La columna es la correcta?")
    return cents


def parse_stock(value) -> Decimal:
    """
    El stock de la planilla. Se permite 0 (es "no hay"), no se permite negativo.

    Un stock negativo existe de verdad en los ERP —es un descalce de
    inventario— pero en el comparador significaría vender lo que no hay. Entra
    como 0, que es lo que el CHECK de la 024 acepta y lo que el trigger traduce
    a `in_stock = false`.
    """
    quantity = _to_decimal(value)
    if quantity < 0:
        quantity = Decimal(0)
    if quantity > MAX_STOCK:
        raise CellError("La cantidad es demasiado grande. ¿La columna es la correcta?")
    return quantity.quantize(_STOCK_QUANTUM, rounding=ROUND_HALF_UP)


def parse_size_value(value) -> float:
    size = _to_decimal(value)
    if size <= 0:
        raise CellError("El contenido tiene que ser mayor a cero.")
    return float(size)


def parse_ean(value) -> str:
    """
    El código de barras, tal como lo dejó Excel.

    El caso que hay que resolver sí o sí: una columna de EAN sin formato de
    texto se guarda como número y sale como `7.79E+12` o como `7790001000017.0`.
    Recuperar los dígitos de ahí es la diferencia entre matchear con el catálogo
    global y crear un producto duplicado por cada fila.

    Los ceros a la izquierda que Excel se comió no se reponen: un EAN-13 sin su
    cero inicial son 12 dígitos, que el CHECK `ean_format` de la 016 acepta
    (8 a 14), y rellenarlo a ciegas inventaría un código que apunta a otro
    producto.
    """
    if isinstance(value, bool):
        raise CellError("El código de barras no es válido.")

    if isinstance(value, float):
        if value != int(value):
            raise CellError("El código de barras no es válido.")
        text = str(int(value))
    elif isinstance(value, (int, Decimal)):
        text = str(int(value))
    else:
        text = str(value).strip().lstrip("'").replace(" ", "").replace("-", "")
        if re.fullmatch(r"\d+(\.\d+)?[eE][+-]?\d+", text):
            # Notación científica: `7.79E+12`. Convertirlo a entero da
            # 7790000000000, que es un EAN perfectamente formado y de otro
            # producto: el export guardó lo que MOSTRABA la celda, no el
            # número, y los dígitos que faltan no están en ninguna parte. Se
            # rechaza con la instrucción concreta para arreglarlo.
            mantissa_digits = len(re.sub(r"[^0-9]", "", text.split("e")[0].split("E")[0]))
            if mantissa_digits < 8:
                raise CellError(
                    "El código de barras se guardó redondeado (notación científica). "
                    "Exportá esa columna con formato de texto y volvé a subir el archivo."
                )
            try:
                text = str(int(Decimal(text)))
            except InvalidOperation:
                raise CellError("El código de barras no es válido.")
        elif re.fullmatch(r"\d+\.0*", text):
            # `7790001000017.0`: la parte decimal es el ruido que deja Excel al
            # guardar el código como número. Se corta en el punto y no se
            # borran los ceros, que en un EAN son dígitos como cualquier otro.
            text = text.split(".")[0]

    if not text.isdigit():
        raise CellError("El código de barras tiene caracteres que no son dígitos.")
    if not 8 <= len(text) <= 14:
        raise CellError(
            f"El código de barras tiene {len(text)} dígitos; se esperaban entre 8 y 14."
        )
    return text


def parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        return value != 0

    word = normalize_header(value)
    if word in _TRUE_WORDS:
        return True
    if word in _FALSE_WORDS:
        return False
    raise CellError("No se entiende si el producto está activo o no.")


def parse_unit(value) -> str:
    """
    La unidad, mapeada al enum `product_unit` de la 008.

    Se acepta lo que escribe la gente (`Kg.`, `LITROS`, `c/u`) y también las
    formas que vienen pegadas al contenido en una sola celda (`500 gr`), porque
    la misma columna de un export a veces trae `900` y a veces `900 ml`.
    """
    word = normalize_header(value)
    if not word:
        raise CellError("Falta la unidad.")

    if word in _UNIT_WORDS:
        return _UNIT_WORDS[word]

    # `500 gr` -> se queda con la parte no numérica.
    letters = _DIGITS.sub(" ", word).strip()
    if letters in _UNIT_WORDS:
        return _UNIT_WORDS[letters]

    raise CellError(f"Unidad «{value}» desconocida. Usá {', '.join(PRODUCT_UNITS)}.")


def parse_text(value, max_length: int) -> str:
    """
    Texto libre acotado. El tope no es cosmético: `products.name` alimenta
    `ProductDraft`, que declara `max_length=200`, y una celda de 10 KB es un
    422 evitable o un dato basura en el catálogo compartido (SEGURIDAD.md §9.1).
    """
    text = str(value).strip()
    if not text:
        raise CellError("La celda está vacía.")
    return text[:max_length]
