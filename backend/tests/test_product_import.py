"""
El importador de catálogo: desde cómo se lee una celda hasta qué escribe la
corrida.

Los tests están ordenados de adentro hacia afuera —parseo, detección de
columnas, vista previa, importación— porque así falla el que dice la causa y no
solo el que dice el síntoma.
"""

import io
from unittest.mock import MagicMock, patch
from uuid import uuid4

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.core.security import (
    get_current_staff,
    require_approved_chain,
    require_approved_manager,
    require_manager,
    require_owner,
)
from app.main import app
from app.schemas.auth import CurrentStaff
from app.services import import_mapping as mapping
from app.services.import_mapping import CellError

from .conftest import FakeResult, chain_mock, table_router

client = TestClient(app)

CHAIN_ID = uuid4()
STORE_ID = uuid4()
PRODUCT_ID = str(uuid4())

STAFF_DEPS = (
    get_current_staff,
    require_manager,
    require_owner,
    require_approved_chain,
    require_approved_manager,
)


def _staff(role="owner", chain_status="approved", chain_id=None):
    return CurrentStaff(
        id=uuid4(),
        email="owner@super.com",
        chain_id=chain_id or CHAIN_ID,
        supermarket_id=STORE_ID,
        role=role,
        chain_status=chain_status,
    )


@pytest.fixture
def staff_override():
    def _apply(current):
        for dep in STAFF_DEPS:
            app.dependency_overrides[dep] = lambda c=current: c
        return current

    yield _apply

    for dep in STAFF_DEPS:
        app.dependency_overrides.pop(dep, None)


def _xlsx(rows: list[list]) -> bytes:
    """Una planilla en memoria, como la que sube el supermercado."""
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Listado"
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _upload(content: bytes, name="catalogo.xlsx", **form):
    data = {"supermarket_id": str(STORE_ID), **{k: str(v) for k, v in form.items()}}
    return {
        "files": {"file": (name, content, "application/vnd.ms-excel")},
        "data": data,
    }


def _store_row(chain_id=None):
    return {"id": str(STORE_ID), "chain_id": str(chain_id or CHAIN_ID), "name": "SurMarket Centro"}


def _listing(product_id=PRODUCT_ID, price=120000, in_stock=True, stock=None, name="Leche entera 1L", ean="7790001000017"):
    return {
        "id": str(uuid4()),
        "product_id": product_id,
        "price": price,
        "in_stock": in_stock,
        "stock_quantity": stock,
        "products": {"id": product_id, "name": name, "ean": ean},
    }


# ── Lectura de celdas ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,cents",
    [
        ("1.234,56", 123456),   # español: punto de miles, coma decimal
        ("1,234.56", 123456),   # inglés: al revés
        ("$ 1.234,56", 123456), # con símbolo de moneda
        ("19.99", 1999),        # un solo punto con dos decimales: es decimal
        ("1.234", 123400),      # un solo punto con TRES: es separador de miles
        ("1234,5", 123450),
        (1234.56, 123456),      # lo que entrega Excel cuando la celda es número
        (1250, 125000),
    ],
)
def test_price_parsing_survives_both_conventions(raw, cents):
    """
    El mismo archivo puede venir en formato español o inglés y la planilla no
    dice cuál es. Si esto se equivoca, el supermercado publica un precio mil
    veces más caro o más barato: es la celda de mayor consecuencia del archivo.
    """
    assert mapping.parse_price_cents(raw) == cents


def test_price_zero_or_negative_is_rejected():
    with pytest.raises(CellError):
        mapping.parse_price_cents(0)
    with pytest.raises(CellError):
        mapping.parse_price_cents("-100")


def test_ean_survives_excel_turning_it_into_a_number():
    """
    Una columna de códigos de barras sin formato de texto se guarda como número
    y vuelve como float. Si no se recupera el entero, el matcheo por EAN falla
    para TODAS las filas y el importador duplica el catálogo global entero.
    """
    assert mapping.parse_ean(7790001000017) == "7790001000017"
    assert mapping.parse_ean("7790001000017.0") == "7790001000017"
    assert mapping.parse_ean("7790001000010.0") == "7790001000010"
    assert mapping.parse_ean("779-0001-000017") == "7790001000017"


def test_ean_rounded_to_scientific_notation_is_rejected_not_guessed():
    """
    `7.79E+12` convertido a entero da un EAN válido de OTRO producto. Los
    dígitos que faltan no están en el archivo: se rechaza con la instrucción
    para arreglarlo, nunca se completa con ceros.
    """
    with pytest.raises(CellError):
        mapping.parse_ean("7.79E+12")


def test_units_accept_what_people_actually_write():
    assert mapping.parse_unit("Kg.") == "kg"
    assert mapping.parse_unit("LITROS") == "L"
    assert mapping.parse_unit("c/u") == "un"
    assert mapping.parse_unit("500 gr") == "g"


def test_negative_stock_becomes_zero_instead_of_failing():
    """Un descalce de inventario del ERP es 'no hay', no un error de la fila."""
    assert float(mapping.parse_stock(-3)) == 0.0


# ── Detección de columnas ─────────────────────────────────────────────────


def test_header_is_found_below_the_report_title():
    """Un export de ERP casi nunca arranca en A1."""
    index, detected = mapping.detect_header_row(
        [
            ["LISTADO DE PRECIOS", None, None],
            ["Generado el 27/08/2026", None, None],
            [None, None, None],
            ["Cod.Barra", "Descripción", "Precio Venta"],
            ["7790001000017", "Leche entera 1L", "1234,56"],
        ]
    )
    assert index == 3
    assert detected == {"ean": 0, "name": 1, "price": 2}


def test_different_erps_map_to_the_same_fields():
    assert mapping.map_columns(["EAN13", "Producto", "Importe", "Existencia"]) == {
        "ean": 0, "name": 1, "price": 2, "stock_quantity": 3,
    }
    assert mapping.map_columns(["Barcode", "Description", "Sale Price", "Qty", "Brand"]) == {
        "ean": 0, "name": 1, "price": 2, "stock_quantity": 3, "brand": 4,
    }


def test_cost_price_is_never_taken_as_the_sale_price():
    """
    Publicar el costo como precio de venta le regala el margen del supermercado
    a sus competidores, que ven ese precio en el comparador. Ante dos columnas
    que dicen "precio", la de costo no compite.
    """
    detected = mapping.map_columns(["EAN", "Producto", "PRECIO COSTO", "PRECIO VENTA"])
    assert detected["price"] == 3

    solo_costo = mapping.map_columns(["EAN", "Producto", "Precio de costo"])
    assert "price" not in solo_costo


# ── Vista previa ──────────────────────────────────────────────────────────


def _preview_client(listings, products_by_ean, store_chain_id=None):
    fake = MagicMock()
    fake.table.side_effect = table_router(
        {
            "supermarkets": chain_mock(FakeResult(data=_store_row(store_chain_id))),
            "supermarket_products": chain_mock(FakeResult(data=listings)),
            "products": chain_mock(FakeResult(data=products_by_ean)),
        }
    )
    return fake


def test_preview_says_what_it_would_do_without_writing(staff_override):
    staff_override(_staff())
    content = _xlsx(
        [
            ["Cod.Barra", "Descripcion", "Precio Venta", "Stock"],
            ["7790001000017", "Leche entera 1L", "1.500,00", 12],       # ya cargado -> update
            ["7790009999998", "Yerba mate 500g", "3.200,50", 4],        # nuevo -> create
        ]
    )
    sp_mock = chain_mock(FakeResult(data=[_listing()]))
    fake = MagicMock()
    fake.table.side_effect = table_router(
        {
            "supermarkets": chain_mock(FakeResult(data=_store_row())),
            "supermarket_products": sp_mock,
            "products": chain_mock(FakeResult(data=[{"id": PRODUCT_ID, "name": "Leche entera 1L", "ean": "7790001000017"}])),
        }
    )

    upload = _upload(content)
    with patch("app.services.supermarket_service.get_supabase", return_value=fake), \
         patch("app.services.product_import_service.get_supabase", return_value=fake):
        response = client.post(
            "/api/v1/supermarkets/me/products/import/preview", **upload
        )

    assert response.status_code == 200
    body = response.json()
    assert body["mapping"] == {"ean": 0, "name": 1, "price": 2, "stock_quantity": 3}
    assert body["counts"]["listings_updated"] == 1
    assert body["counts"]["listings_created"] == 1
    assert body["counts"]["products_created"] == 1
    # Lo decisivo: la vista previa no escribe.
    sp_mock.upsert.assert_not_called()
    sp_mock.insert.assert_not_called()
    sp_mock.update.assert_not_called()


def test_preview_reports_the_broken_rows_with_their_row_number(staff_override):
    """
    Un archivo con tres celdas rotas tiene que entrar igual, y las tres tienen
    que quedar dichas con el número de fila que muestra Excel. Sin eso, el
    encargado no sabe dónde mirar.
    """
    staff_override(_staff())
    content = _xlsx(
        [
            ["EAN", "Producto", "Precio"],
            ["7790001000017", "Leche entera 1L", "1500"],
            ["123", "Fideos", "800"],                       # EAN corto
            ["7790009999998", "Arroz", "cero pesos"],       # precio ilegible
        ]
    )
    fake = _preview_client([_listing()], [{"id": PRODUCT_ID, "name": "Leche entera 1L", "ean": "7790001000017"}])

    with patch("app.services.supermarket_service.get_supabase", return_value=fake), \
         patch("app.services.product_import_service.get_supabase", return_value=fake):
        response = client.post("/api/v1/supermarkets/me/products/import/preview", **_upload(content))

    body = response.json()
    assert body["counts"]["rows_failed"] == 2
    assert {issue["row"] for issue in body["issues"]} == {3, 4}


def test_file_without_price_or_stock_column_is_rejected(staff_override):
    staff_override(_staff())
    content = _xlsx([["EAN", "Producto", "Rubro"], ["7790001000017", "Leche", "Lacteos"]])
    fake = _preview_client([], [])

    with patch("app.services.supermarket_service.get_supabase", return_value=fake), \
         patch("app.services.product_import_service.get_supabase", return_value=fake):
        response = client.post("/api/v1/supermarkets/me/products/import/preview", **_upload(content))

    assert response.status_code == 400


def test_csv_with_semicolons_and_latin1_is_read(staff_override):
    """Excel en español exporta csv con punto y coma y, a veces, en cp1252."""
    staff_override(_staff())
    content = "EAN;Descripción;Precio\n7790001000017;Leche entera 1L;1.500,00\n".encode("cp1252")
    fake = _preview_client([_listing()], [{"id": PRODUCT_ID, "name": "Leche entera 1L", "ean": "7790001000017"}])

    with patch("app.services.supermarket_service.get_supabase", return_value=fake), \
         patch("app.services.product_import_service.get_supabase", return_value=fake):
        response = client.post(
            "/api/v1/supermarkets/me/products/import/preview",
            **_upload(content, name="catalogo.csv"),
        )

    assert response.status_code == 200
    assert response.json()["counts"]["listings_updated"] == 1


# ── Identidad del producto ────────────────────────────────────────────────


def test_ambiguous_name_without_ean_is_skipped_not_guessed(staff_override):
    """
    Sin código de barras, dos productos globales con el mismo nombre no se
    desempatan: vincular al azar publicaría el precio sobre el producto
    equivocado, que es peor que no importar la fila (PLAN §5.1).
    """
    staff_override(_staff())
    content = _xlsx([["Producto", "Precio"], ["Leche entera 1L", "1500"]])
    duplicates = [
        {"id": str(uuid4()), "name": "Leche entera 1L", "ean": "7790001000017"},
        {"id": str(uuid4()), "name": "Leche Entera 1L", "ean": "7790001000024"},
    ]
    fake = MagicMock()
    fake.table.side_effect = table_router(
        {
            "supermarkets": chain_mock(FakeResult(data=_store_row())),
            "supermarket_products": chain_mock(FakeResult(data=[])),
            "products": chain_mock(FakeResult(data=duplicates)),
        }
    )

    with patch("app.services.supermarket_service.get_supabase", return_value=fake), \
         patch("app.services.product_import_service.get_supabase", return_value=fake):
        response = client.post("/api/v1/supermarkets/me/products/import/preview", **_upload(content))

    body = response.json()
    assert body["counts"]["rows_skipped"] == 1
    assert "código de barras" in body["issues"][0]["message"]


def test_new_product_without_price_cannot_be_created(staff_override):
    """
    `supermarket_products.price` es NOT NULL y no hay ningún precio razonable
    para inventar. Un archivo de solo stock actualiza lo que ya está cargado y
    reporta el resto.
    """
    staff_override(_staff())
    content = _xlsx(
        [
            ["EAN", "Producto", "Stock"],
            ["7790001000017", "Leche entera 1L", 8],    # ya cargado -> se actualiza
            ["7790009999998", "Yerba mate 500g", 3],    # no cargado -> error
        ]
    )
    fake = _preview_client([_listing()], [{"id": PRODUCT_ID, "name": "Leche entera 1L", "ean": "7790001000017"}])

    with patch("app.services.supermarket_service.get_supabase", return_value=fake), \
         patch("app.services.product_import_service.get_supabase", return_value=fake):
        response = client.post("/api/v1/supermarkets/me/products/import/preview", **_upload(content))

    body = response.json()
    assert body["counts"]["listings_updated"] == 1
    assert body["counts"]["rows_failed"] == 1


# ── La corrida que escribe ────────────────────────────────────────────────


def test_import_writes_price_and_stock_of_existing_listings(staff_override):
    staff_override(_staff())
    content = _xlsx([["EAN", "Producto", "Precio", "Stock"], ["7790001000017", "Leche entera 1L", "1.500,00", 7]])

    sp_mock = chain_mock(FakeResult(data=[_listing(price=120000, stock=2)]))
    jobs_mock = chain_mock(FakeResult(data=[{"id": str(uuid4())}]))
    fake = MagicMock()
    fake.table.side_effect = table_router(
        {
            "supermarkets": chain_mock(FakeResult(data=_store_row())),
            "supermarket_products": sp_mock,
            "products": chain_mock(FakeResult(data=[{"id": PRODUCT_ID, "name": "Leche entera 1L", "ean": "7790001000017"}])),
            "product_import_jobs": jobs_mock,
        }
    )

    with patch("app.services.supermarket_service.get_supabase", return_value=fake), \
         patch("app.services.catalog_service.get_supabase", return_value=fake), \
         patch("app.services.product_import_service.get_supabase", return_value=fake):
        response = client.post("/api/v1/supermarkets/me/products/import", **_upload(content))

    assert response.status_code == 201
    written = sp_mock.upsert.call_args[0][0]
    assert written == [
        {
            "supermarket_id": str(STORE_ID),
            "price": 150000,
            "currency": "ARS",
            "in_stock": True,
            "stock_quantity": 7.0,
            "product_id": PRODUCT_ID,
        }
    ]
    # La corrida queda registrada: es la respuesta a "por que cambio este precio".
    assert jobs_mock.insert.called


def test_restocking_republishes_a_product_that_had_run_out(staff_override):
    """
    Un producto que llegó a 0 quedó despublicado por el trigger de la 024. Si
    reponer stock no lo vuelve a publicar, cada agotado necesita que alguien se
    acuerde de reactivarlo a mano y la góndola se vacía sola.
    """
    staff_override(_staff())
    content = _xlsx([["EAN", "Producto", "Stock"], ["7790001000017", "Leche entera 1L", 20]])

    sp_mock = chain_mock(FakeResult(data=[_listing(in_stock=False, stock=0)]))
    fake = MagicMock()
    fake.table.side_effect = table_router(
        {
            "supermarkets": chain_mock(FakeResult(data=_store_row())),
            "supermarket_products": sp_mock,
            "products": chain_mock(FakeResult(data=[{"id": PRODUCT_ID, "name": "Leche entera 1L", "ean": "7790001000017"}])),
            "product_import_jobs": chain_mock(FakeResult(data=[{"id": str(uuid4())}])),
        }
    )

    with patch("app.services.supermarket_service.get_supabase", return_value=fake), \
         patch("app.services.catalog_service.get_supabase", return_value=fake), \
         patch("app.services.product_import_service.get_supabase", return_value=fake):
        client.post("/api/v1/supermarkets/me/products/import", **_upload(content))

    written = sp_mock.upsert.call_args[0][0][0]
    assert written["in_stock"] is True
    assert written["stock_quantity"] == 20.0
    # El precio no viene en el archivo: se conserva el que estaba, no se anula.
    assert written["price"] == 120000


def test_a_price_only_file_does_not_touch_availability(staff_override):
    staff_override(_staff())
    content = _xlsx([["EAN", "Producto", "Precio"], ["7790001000017", "Leche entera 1L", "1500"]])

    sp_mock = chain_mock(FakeResult(data=[_listing(in_stock=False, stock=5)]))
    fake = MagicMock()
    fake.table.side_effect = table_router(
        {
            "supermarkets": chain_mock(FakeResult(data=_store_row())),
            "supermarket_products": sp_mock,
            "products": chain_mock(FakeResult(data=[{"id": PRODUCT_ID, "name": "Leche entera 1L", "ean": "7790001000017"}])),
            "product_import_jobs": chain_mock(FakeResult(data=[{"id": str(uuid4())}])),
        }
    )

    with patch("app.services.supermarket_service.get_supabase", return_value=fake), \
         patch("app.services.catalog_service.get_supabase", return_value=fake), \
         patch("app.services.product_import_service.get_supabase", return_value=fake):
        client.post("/api/v1/supermarkets/me/products/import", **_upload(content))

    written = sp_mock.upsert.call_args[0][0][0]
    assert written["in_stock"] is False
    assert written["stock_quantity"] == 5


def test_deactivate_missing_only_runs_when_asked(staff_override):
    """
    El flag despublica lo que el archivo no menciona. Con un export parcial eso
    vacía la góndola, así que viene apagado y hay que pedirlo.
    """
    staff_override(_staff())
    content = _xlsx([["EAN", "Producto", "Precio"], ["7790001000017", "Leche entera 1L", "1500"]])
    otro = _listing(product_id=str(uuid4()), name="Fideos 500g", ean="7790002000028")

    def _run(deactivate):
        sp_mock = chain_mock(FakeResult(data=[_listing(), otro]))
        fake = MagicMock()
        fake.table.side_effect = table_router(
            {
                "supermarkets": chain_mock(FakeResult(data=_store_row())),
                "supermarket_products": sp_mock,
                "products": chain_mock(FakeResult(data=[{"id": PRODUCT_ID, "name": "Leche entera 1L", "ean": "7790001000017"}])),
                "product_import_jobs": chain_mock(FakeResult(data=[{"id": str(uuid4())}])),
            }
        )
        with patch("app.services.supermarket_service.get_supabase", return_value=fake), \
             patch("app.services.catalog_service.get_supabase", return_value=fake), \
             patch("app.services.product_import_service.get_supabase", return_value=fake):
            response = client.post(
                "/api/v1/supermarkets/me/products/import",
                **_upload(content, deactivate_missing=deactivate),
            )
        return response.json(), sp_mock

    body, sp_mock = _run("false")
    assert body["counts"]["listings_deactivated"] == 0
    sp_mock.update.assert_not_called()

    body, sp_mock = _run("true")
    assert body["counts"]["listings_deactivated"] == 1
    sp_mock.update.assert_called_once_with({"in_stock": False})


# ── Puertas de acceso ─────────────────────────────────────────────────────


def test_importing_into_another_chains_store_is_404(staff_override):
    """
    El `supermarket_id` lo elige el cliente: sin comprobarlo contra la cadena
    del JWT, el staff de la cadena A escribiría precios en una sucursal de la B
    (SEGURIDAD.md §4.1). 404 y no 403 para no confirmar que la sucursal existe.
    """
    staff_override(_staff())
    fake = MagicMock()
    fake.table.side_effect = table_router({"supermarkets": chain_mock(None)})

    with patch("app.services.supermarket_service.get_supabase", return_value=fake):
        response = client.post(
            "/api/v1/supermarkets/me/products/import",
            **_upload(_xlsx([["EAN", "Precio"], ["7790001000017", "1500"]])),
        )

    assert response.status_code == 404


def test_staff_role_cannot_import():
    """Importar es escribir precios: la matriz de SEGURIDAD.md §4.2 lo reserva a manager y owner."""
    app.dependency_overrides[get_current_staff] = lambda: _staff(role="staff")
    try:
        response = client.post(
            "/api/v1/supermarkets/me/products/import",
            **_upload(_xlsx([["EAN", "Precio"], ["7790001000017", "1500"]])),
        )
    finally:
        app.dependency_overrides.pop(get_current_staff, None)

    assert response.status_code == 403


def test_pending_chain_cannot_import():
    app.dependency_overrides[get_current_staff] = lambda: _staff(chain_status="pending_review")
    try:
        response = client.post(
            "/api/v1/supermarkets/me/products/import",
            **_upload(_xlsx([["EAN", "Precio"], ["7790001000017", "1500"]])),
        )
    finally:
        app.dependency_overrides.pop(get_current_staff, None)

    assert response.status_code == 403


def test_a_file_that_is_not_a_spreadsheet_is_rejected(staff_override):
    staff_override(_staff())
    fake = MagicMock()
    fake.table.side_effect = table_router({"supermarkets": chain_mock(FakeResult(data=_store_row()))})

    with patch("app.services.supermarket_service.get_supabase", return_value=fake):
        response = client.post(
            "/api/v1/supermarkets/me/products/import/preview",
            **_upload(b"\x89PNG\r\n\x1a\n\x00\x00binario", name="logo.png"),
        )

    assert response.status_code == 400


def test_names_in_uppercase_still_match_the_global_catalog(staff_override):
    """
    Los ERP exportan los nombres EN MAYÚSCULAS. Con una comparación exacta,
    `LECHE ENTERA 1L` no matchearía la fila `Leche entera 1L` del catálogo y el
    importador crearía un duplicado, que es justo lo que vacía el comparador.
    """
    staff_override(_staff())
    content = _xlsx([["Producto", "Precio"], ["LECHE ENTERA 1L", "1500"]])
    products_mock = chain_mock(
        FakeResult(data=[{"id": PRODUCT_ID, "name": "Leche entera 1L", "ean": "7790001000017"}])
    )
    fake = MagicMock()
    fake.table.side_effect = table_router(
        {
            "supermarkets": chain_mock(FakeResult(data=_store_row())),
            "supermarket_products": chain_mock(FakeResult(data=[])),
            "products": products_mock,
        }
    )

    with patch("app.services.supermarket_service.get_supabase", return_value=fake), \
         patch("app.services.product_import_service.get_supabase", return_value=fake):
        response = client.post("/api/v1/supermarkets/me/products/import/preview", **_upload(content))

    body = response.json()
    # Se vincula al producto que ya existe: es un alta de PRECIO, no de producto.
    assert body["counts"]["listings_created"] == 1
    assert body["counts"]["products_created"] == 0
    assert body["sample"][0]["matched_product_name"] == "Leche entera 1L"
    # La búsqueda es case-insensitive y con el valor citado, no interpolado.
    condition = products_mock.or_.call_args[0][0]
    assert condition == 'name.ilike."LECHE ENTERA 1L"'


def test_product_names_cannot_inject_postgrest_filters(staff_override):
    """
    El nombre sale de un archivo que sube el usuario y termina dentro de un
    filtro `or=`. Sin comillas, una coma en el nombre cierra ese filtro y abre
    otro que elige quien armó la planilla.
    """
    staff_override(_staff())
    content = _xlsx([["Producto", "Precio"], ["Leche, entera (1L)", "1500"]])
    products_mock = chain_mock(FakeResult(data=[]))
    fake = MagicMock()
    fake.table.side_effect = table_router(
        {
            "supermarkets": chain_mock(FakeResult(data=_store_row())),
            "supermarket_products": chain_mock(FakeResult(data=[])),
            "products": products_mock,
        }
    )

    with patch("app.services.supermarket_service.get_supabase", return_value=fake), \
         patch("app.services.product_import_service.get_supabase", return_value=fake):
        client.post("/api/v1/supermarkets/me/products/import/preview", **_upload(content))

    assert products_mock.or_.call_args[0][0] == 'name.ilike."Leche, entera (1L)"'
