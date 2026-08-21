from fastapi import HTTPException, status

from app.core.supabase_client import get_supabase
from app.schemas.auth import RegisterRequest, RegisterResponse


def register_consumer(payload: RegisterRequest) -> RegisterResponse:
    """
    Crea el usuario en Supabase Auth vía la API admin (service_role). La fila
    correspondiente en `profiles` se crea automáticamente por el trigger de DB
    `on_auth_user_created` (ver backend/migrations/002_create_profile_trigger.sql),
    en la misma transacción — si el trigger falla, Supabase revierte también la
    creación del usuario, así que no hace falta un segundo INSERT explícito acá.
    """
    client = get_supabase()
    try:
        result = client.auth.admin.create_user(
            {
                "email": payload.email,
                "password": payload.password,
                "email_confirm": True,
                "user_metadata": {
                    "full_name": payload.full_name,
                    "phone": payload.phone,
                },
            }
        )
    except Exception as exc:
        # supabase-py no expone un tipo de excepción estable entre versiones para
        # errores de la API admin; se distingue por el mensaje.
        message = str(exc).lower()
        if "already" in message or "exists" in message or "registered" in message:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El correo ya está registrado.",
            )
        if "password" in message or "invalid" in message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Datos de registro inválidos.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo completar el registro. Intenta nuevamente.",
        )

    user = result.user
    return RegisterResponse(
        id=user.id,
        email=payload.email,
        full_name=payload.full_name,
        created_at=user.created_at,
    )
