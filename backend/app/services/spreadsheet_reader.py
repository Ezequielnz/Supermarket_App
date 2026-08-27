"""
Un archivo subido -> una grilla de celdas. Nada más.

Este módulo NO sabe qué es un precio ni qué es un EAN: su única
responsabilidad es convertir los formatos que exporta un ERP (xlsx, xls, csv)
en `list[list]` de valores de Python. Interpretar esas celdas es de
`import_mapping.py`, y decidir qué hacer con ellas es de
`product_import_service.py` (NORMAS.md §1.2).

Separarlo importa porque los tres formatos fallan distinto y todos fallan: un
xls de 2003, un csv exportado en latin-1 con punto y coma, una hoja de tapa
antes de los datos. Que todo eso muera acá deja al importador leyendo una
grilla y nada más.
"""

import csv
import io

from fastapi import HTTPException, status

# 5 MB. Un catálogo de 20.000 productos en xlsx pesa alrededor de 1 MB; el
# límite deja margen de sobra y a la vez acota lo que un cliente puede hacer
# entrar en memoria (SEGURIDAD.md §9.1: sin tope de longitud, un archivo de 10
# MB es un DoS barato).
MAX_FILE_BYTES = 5 * 1024 * 1024

# Filas de datos que se leen como máximo. Se corta la lectura, no se rechaza el
# archivo: el importador informa el truncado y el supermercado sube el resto.
MAX_ROWS = 20_000

# Un export de ERP rara vez pasa de 40 columnas. El tope evita que una hoja con
# un rango sucio de 16.000 columnas (openpyxl las reporta si hay formato
# aplicado) multiplique la memoria por celda vacía.
MAX_COLUMNS = 60

FORMAT_XLSX = "xlsx"
FORMAT_XLS = "xls"
FORMAT_CSV = "csv"

# Magic bytes, no la extensión ni el Content-Type que manda el cliente
# (SEGURIDAD.md §9.4). Un .xlsx es un ZIP; un .xls es un contenedor OLE2.
_ZIP_MAGIC = b"PK\x03\x04"
_OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

# Separadores candidatos para csv, en orden de probabilidad en exports locales:
# Excel en español guarda con punto y coma.
_CSV_DELIMITERS = ";,\t|"

# El encoding que usan los ERP viejos de Windows cuando no usan UTF-8.
_CSV_ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


class Sheet:
    """Una hoja leída: su nombre, sus filas y si se cortó por el tope."""

    def __init__(self, name: str, rows: list[list], truncated: bool = False):
        self.name = name
        self.rows = rows
        self.truncated = truncated


def detect_format(content: bytes, filename: str) -> str:
    """
    El formato real del archivo, por sus primeros bytes.

    La extensión es una sugerencia del cliente: un `.xlsx` renombrado sigue
    siendo un csv, y un csv renombrado a `.xlsx` haría explotar a openpyxl con
    un error ilegible. Solo se cae en la extensión cuando los magic bytes no
    dicen nada, que es el caso legítimo del texto plano.
    """
    if content.startswith(_ZIP_MAGIC):
        return FORMAT_XLSX
    if content.startswith(_OLE2_MAGIC):
        return FORMAT_XLS

    name = filename.lower()
    if name.endswith((".csv", ".txt", ".tsv")):
        return FORMAT_CSV

    # Sin magic bytes reconocidos y sin extensión de texto: si decodifica como
    # texto es un csv con otro nombre, y si no, no es una planilla.
    try:
        content[:4096].decode("utf-8")
        return FORMAT_CSV
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no es una planilla de Excel (.xlsx, .xls) ni un CSV.",
        )


def read(content: bytes, filename: str, sheet_name: str | None = None) -> Sheet:
    """
    Punto de entrada único: bytes -> `Sheet`.

    `sheet_name` deja elegir la hoja a mano; sin él se elige la que más datos
    tiene (ver `_pick_sheet`).
    """
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo está vacío."
        )
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"El archivo supera los {MAX_FILE_BYTES // (1024 * 1024)} MB. Subilo partido en varios.",
        )

    file_format = detect_format(content, filename)
    if file_format == FORMAT_XLSX:
        return _read_xlsx(content, sheet_name)
    if file_format == FORMAT_XLS:
        return _read_xls(content, sheet_name)
    return _read_csv(content)


def list_sheet_names(content: bytes, filename: str) -> list[str]:
    """Las hojas del archivo, para que el panel deje elegir otra."""
    if detect_format(content, filename) != FORMAT_XLSX:
        return []
    workbook = _load_xlsx(content)
    try:
        return list(workbook.sheetnames)
    finally:
        workbook.close()


# ── xlsx / xlsm ───────────────────────────────────────────────────────────


def _load_xlsx(content: bytes):
    try:
        import openpyxl
    except ImportError:  # pragma: no cover - dependencia declarada en requirements
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El servidor no puede leer archivos .xlsx en este momento.",
        )

    try:
        # read_only: no carga la hoja entera en memoria, la recorre en streaming.
        # data_only: devuelve el ÚLTIMO VALOR CALCULADO de las fórmulas en vez
        # de la fórmula. Un export con "=B2*1.21" en la columna de precio sale
        # como número; si el ERP guardó el archivo sin cachear resultados, sale
        # como None y el importador lo reporta como celda vacía, que es lo
        # correcto: adivinar el resultado de una fórmula sería inventar precios.
        return openpyxl.load_workbook(
            io.BytesIO(content), read_only=True, data_only=True
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pudimos abrir el archivo. ¿Está dañado o protegido con contraseña?",
        )


def _read_xlsx(content: bytes, sheet_name: str | None) -> Sheet:
    workbook = _load_xlsx(content)
    try:
        if sheet_name is not None:
            if sheet_name not in workbook.sheetnames:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El archivo no tiene una hoja llamada «{sheet_name}».",
                )
            names = [sheet_name]
        else:
            names = list(workbook.sheetnames)

        candidates = []
        for name in names:
            rows, truncated = _rows_from_openpyxl(workbook[name])
            candidates.append(Sheet(name, rows, truncated))

        return _pick_sheet(candidates)
    finally:
        workbook.close()


def _rows_from_openpyxl(worksheet) -> tuple[list[list], bool]:
    rows: list[list] = []
    truncated = False
    for index, row in enumerate(worksheet.iter_rows(values_only=True)):
        if index >= MAX_ROWS:
            truncated = True
            break
        rows.append([_clean_cell(value) for value in row[:MAX_COLUMNS]])
    return _drop_trailing_empty(rows), truncated


# ── xls (Excel 97-2003) ───────────────────────────────────────────────────


def _read_xls(content: bytes, sheet_name: str | None) -> Sheet:
    try:
        import xlrd
    except ImportError:
        # Import perezoso y no arriba del módulo: xlrd solo sirve para el
        # formato viejo. Si un despliegue no lo tiene instalado, el resto del
        # importador tiene que seguir funcionando, y el supermercado necesita
        # un mensaje que le diga qué hacer — no un 500 al arrancar la app.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este servidor no lee el formato .xls antiguo. Guardá el archivo como .xlsx o .csv y volvé a subirlo.",
        )

    try:
        book = xlrd.open_workbook(file_contents=content)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pudimos abrir el archivo. ¿Está dañado o protegido con contraseña?",
        )

    names = book.sheet_names()
    if sheet_name is not None:
        if sheet_name not in names:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El archivo no tiene una hoja llamada «{sheet_name}».",
            )
        names = [sheet_name]

    candidates = []
    for name in names:
        worksheet = book.sheet_by_name(name)
        truncated = worksheet.nrows > MAX_ROWS
        rows = [
            [_clean_cell(value) for value in worksheet.row_values(index)[:MAX_COLUMNS]]
            for index in range(min(worksheet.nrows, MAX_ROWS))
        ]
        candidates.append(Sheet(name, _drop_trailing_empty(rows), truncated))

    return _pick_sheet(candidates)


# ── csv ───────────────────────────────────────────────────────────────────


def _read_csv(content: bytes) -> Sheet:
    text = None
    for encoding in _CSV_ENCODINGS:
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:  # pragma: no cover - latin-1 decodifica cualquier byte
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pudimos leer el archivo: la codificación no es reconocible.",
        )

    sample = text[:8192]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=_CSV_DELIMITERS).delimiter
    except csv.Error:
        # Sniffer falla con una sola columna o con muestras raras. El punto y
        # coma es lo que exporta Excel en español, así que es el default menos
        # sorprendente acá.
        delimiter = ";" if sample.count(";") > sample.count(",") else ","

    rows: list[list] = []
    truncated = False
    for index, row in enumerate(csv.reader(io.StringIO(text), delimiter=delimiter)):
        if index >= MAX_ROWS:
            truncated = True
            break
        rows.append([_clean_cell(value) for value in row[:MAX_COLUMNS]])

    return Sheet("CSV", _drop_trailing_empty(rows), truncated)


# ── Helpers ───────────────────────────────────────────────────────────────


def _clean_cell(value):
    """
    Normaliza el valor de una celda sin interpretarlo.

    Los espacios sobrantes son la basura más común de un export y arruinan
    tanto el matcheo de encabezados ("  PRECIO ") como el de datos. Una celda
    que queda vacía después de limpiar es None y no "": el resto del importador
    pregunta por `is None` una sola vez.
    """
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _drop_trailing_empty(rows: list[list]) -> list[list]:
    """
    Saca las filas totalmente vacías del final.

    Excel arrastra filas fantasma con formato aplicado y sin contenido; sin
    esto, un archivo de 300 productos reporta 1.048.576 filas con 1.048.276
    errores de "fila vacía".
    """
    while rows and all(cell is None for cell in rows[-1]):
        rows.pop()
    return rows


def _pick_sheet(candidates: list[Sheet]) -> Sheet:
    """
    La hoja con más celdas con datos.

    Los exports de ERP suelen traer una hoja de portada ("Reporte generado
    el..."), o dejan hojas vacías atrás. Elegir siempre la primera haría que el
    importador viera dos filas de encabezado de una carátula. El panel igual
    deja cambiar de hoja a mano si la heurística elige mal.
    """
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo no tiene hojas."
        )

    def weight(sheet: Sheet) -> int:
        return sum(1 for row in sheet.rows for cell in row if cell is not None)

    best = max(candidates, key=weight)
    if not best.rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La planilla no tiene datos.",
        )
    return best
