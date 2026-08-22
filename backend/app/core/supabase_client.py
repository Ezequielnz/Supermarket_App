from supabase import create_client, Client

from app.core.config import settings

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    return _client


def single_row(result) -> dict | None:
    """
    Normaliza el resultado de `.maybe_single().execute()`.

    postgrest-py devuelve **None como respuesta completa** cuando la consulta no
    trae ninguna fila, no un objeto con `.data = None`. Leer `result.data`
    directamente es un AttributeError, es decir un 500 donde correspondía un
    404 — que para un recurso ajeno es exactamente lo que docs/SEGURIDAD.md
    §4.3 prohíbe.

    Está acá y no en un servicio porque es una particularidad del cliente, y
    porque tenerla en un solo lugar documentado es lo que evita que el próximo
    servicio la vuelva a pisar.
    """
    if result is None:
        return None
    return result.data
