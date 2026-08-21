from fastapi import APIRouter, status

from app.schemas.auth import RegisterRequest, RegisterResponse
from app.services.auth_service import register_consumer

router = APIRouter(prefix="/auth", tags=["auth"])

# POST /auth/login NO se implementa acá: el login del consumidor se hace directo
# desde el frontend contra Supabase (signInWithPassword), que es la excepción
# explícita de docs/NORMAS.md sección 2 ("Supabase Auth puede usarse directamente
# desde el frontend solo para login/logout/refresh de sesión"). Si en el futuro
# hace falta un salto por el backend (rate-limiting propio, cookies httpOnly,
# auditoría, etc.) se agrega acá.


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest):
    """
    Registra un nuevo consumidor: crea el usuario en Supabase Auth (service_role)
    y dispara la creación automática de su fila en `profiles` vía trigger de DB.
    Público, no requiere autenticación.
    """
    return register_consumer(payload)
