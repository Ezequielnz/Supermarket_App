import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, UUID4

# Qué se hizo (o se haría) con cada fila del archivo.
ACTION_CREATE = "create"
ACTION_UPDATE = "update"
ACTION_SKIP = "skip"
ACTION_ERROR = "error"

ImportAction = Literal["create", "update", "skip", "error"]

# Cuántas filas de ejemplo devuelve la vista previa. Suficiente para que el
# encargado reconozca su archivo; corto para que la respuesta no sea el archivo
# entero de vuelta.
PREVIEW_SAMPLE_SIZE = 15

# Tope de problemas que se devuelven y se guardan en product_import_jobs. Un
# archivo con la columna equivocada genera un error por fila: sin tope, la
# respuesta y la fila de auditoría crecen con el tamaño del archivo.
MAX_ISSUES = 100


class ImportIssue(BaseModel):
    """
    Un problema concreto y ubicable. `row` es el número de fila TAL COMO LO
    MUESTRA EXCEL (1-based, contando el encabezado), porque el encargado lo va
    a buscar en su planilla, no en nuestro índice.
    """

    row: int | None = None
    column: str | None = None
    field: str | None = None
    message: str


class ImportColumnOut(BaseModel):
    """Una columna del archivo y a qué campo del catálogo se la asoció."""

    index: int
    header: str
    field: str | None = None


class ImportPreviewRow(BaseModel):
    """Una fila leída, con lo que el importador haría con ella."""

    row: int
    action: ImportAction
    ean: str | None = None
    name: str | None = None
    price: int | None = None
    stock_quantity: float | None = None
    in_stock: bool | None = None
    matched_product_name: str | None = None
    message: str | None = None


class ImportCounts(BaseModel):
    """El resumen que decide si vale la pena confirmar la importación."""

    rows_total: int = 0
    listings_created: int = 0
    listings_updated: int = 0
    products_created: int = 0
    rows_skipped: int = 0
    rows_failed: int = 0
    listings_deactivated: int = 0


class ImportPreviewResponse(BaseModel):
    """
    Todo lo que el panel necesita para mostrar "esto entendí de tu archivo"
    antes de tocar la base. Ninguna importación escribe sin que esto se haya
    podido ver primero.
    """

    file_name: str
    sheet_name: str
    sheet_names: list[str] = Field(default_factory=list)
    header_row: int
    columns: list[ImportColumnOut] = Field(default_factory=list)
    mapping: dict[str, int] = Field(default_factory=dict)
    unmapped_headers: list[str] = Field(default_factory=list)
    truncated: bool = False
    counts: ImportCounts
    sample: list[ImportPreviewRow] = Field(default_factory=list)
    issues: list[ImportIssue] = Field(default_factory=list)


class ImportResultResponse(BaseModel):
    """El resultado de la corrida que sí escribió."""

    job_id: UUID4
    file_name: str
    sheet_name: str
    counts: ImportCounts
    issues: list[ImportIssue] = Field(default_factory=list)


class ImportJobOut(BaseModel):
    """Una corrida del historial."""

    id: UUID4
    supermarket_id: UUID4
    file_name: str
    sheet_name: str | None = None
    column_mapping: dict[str, int] = Field(default_factory=dict)
    rows_total: int
    listings_created: int
    listings_updated: int
    products_created: int
    rows_skipped: int
    rows_failed: int
    issues: list[ImportIssue] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class ImportJobListResponse(BaseModel):
    data: list[ImportJobOut]
    total: int
    page: int
    per_page: int


class ImportOptions(BaseModel):
    """
    Cómo leer el archivo y qué se permite escribir.

    Los tres flags de escritura tienen defaults asimétricos a propósito: crear
    y actualizar es lo que el usuario vino a hacer, pero `deactivate_missing`
    apaga productos que el archivo NO menciona, y un export parcial (una
    categoría, una sucursal, un filtro que quedó puesto) vaciaría la góndola
    entera. Se pide explícito, siempre.
    """

    sheet_name: str | None = Field(default=None, max_length=120)
    # 1-based, como lo muestra Excel. None = lo detecta el importador.
    header_row: int | None = Field(default=None, ge=1, le=100)
    # Correcciones del usuario sobre el mapeo automático: {campo: índice de columna}.
    mapping: dict[str, int] = Field(default_factory=dict)

    create_missing: bool = True
    update_existing: bool = True
    deactivate_missing: bool = False


    @classmethod
    def from_form(
        cls,
        sheet_name: str | None,
        header_row: int | None,
        mapping: str | None,
        create_missing: bool,
        update_existing: bool,
        deactivate_missing: bool,
    ) -> "ImportOptions":
        """
        Arma las opciones desde un formulario multipart.

        Existe porque la subida de un archivo no puede viajar como JSON: cada
        campo llega como texto suelto, incluido `mapping`, que es un objeto.
        Deserializarlo acá y no en el endpoint mantiene la regla de que el
        endpoint valida y delega, y deja el 400 con un mensaje entendible en
        vez del error crudo de json.
        """
        parsed: dict[str, int] = {}
        if mapping:
            try:
                parsed = json.loads(mapping)
            except json.JSONDecodeError:
                raise ValueError("El mapeo de columnas no es un JSON válido.")
            if not isinstance(parsed, dict):
                raise ValueError("El mapeo de columnas tiene que ser un objeto {campo: columna}.")

        return cls(
            sheet_name=sheet_name,
            header_row=header_row,
            mapping=parsed,
            create_missing=create_missing,
            update_existing=update_existing,
            deactivate_missing=deactivate_missing,
        )
