from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.security import get_current_user
from app.main import app
from app.schemas.auth import CurrentUser


@pytest.fixture
def auth_override():
    """
    Los endpoints de products/lists/orders exigen un JWT válido vía
    get_current_user. Para testear la lógica de negocio sin depender de un
    token real de Supabase, se sobreescribe la dependencia de FastAPI con un
    usuario fijo.
    """
    fake_user = CurrentUser(id=uuid4(), email="consumer@example.com")
    app.dependency_overrides[get_current_user] = lambda: fake_user
    yield fake_user
    app.dependency_overrides.pop(get_current_user, None)


class FakeResult:
    """Simula el objeto que devuelve .execute() de postgrest-py."""

    def __init__(self, data=None, count=None):
        self.data = data
        self.count = count


def chain_mock(execute_result):
    """
    supabase-py encadena métodos (.select().eq().order()...) antes de llamar
    .execute(). Este mock hace que cualquier método encadenable devuelva el
    mismo mock (así no importa cuántos .eq()/.order()/.range() se llamen), y
    .execute() devuelve el resultado indicado (un FakeResult, o una lista de
    FakeResult para simular llamados sucesivos con .side_effect).
    """
    mock = MagicMock()
    chainable = [
        "select", "insert", "update", "delete", "eq", "neq", "in_", "ilike",
        "order", "range", "limit", "filter", "is_",
    ]
    for method in chainable:
        getattr(mock, method).return_value = mock
    if isinstance(execute_result, list):
        mock.execute.side_effect = execute_result
    else:
        mock.execute.return_value = execute_result
    mock.maybe_single.return_value = mock
    mock.single.return_value = mock
    # `.not_` es una propiedad en postgrest-py, no un metodo: se usa como
    # `.not_.is_("category", "null")`.
    mock.not_ = mock
    return mock


# `.maybe_single().execute()` devuelve None —la respuesta entera, no un objeto
# con .data = None— cuando no hay fila. Los tests tienen que simular eso y no
# FakeResult(data=None), o dejan pasar el AttributeError que en produccion sale
# como 500 en vez de 404. Ver core/supabase_client.single_row.
NO_ROW = None


def table_router(tables: dict):
    """
    tables: {"nombre_tabla": chain_mock(...)}. Devuelve una función apta para
    client.table.side_effect, que rutea cada tabla a su mock dedicado.
    """
    def _route(name):
        return tables[name]
    return _route
