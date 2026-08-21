from uuid import UUID

from fastapi import HTTPException, status

from app.core.supabase_client import get_supabase
from app.schemas.supermarket import (
    ChainAdminListResponse,
    ChainAdminOut,
    ChainOut,
    ChainReviewRequest,
    SupermarketRegisterRequest,
    SupermarketRegisterResponse,
)

# Mensajes que levantan las funciones plpgsql de 014 con RAISE EXCEPTION,
# mapeados al código HTTP que corresponde. Igual que en order_service:
# supabase-py no expone un tipo de excepción estable para errores de RPC, así
# que se distingue por el texto que la propia función define.
_RPC_ERRORS = {
    "chain_tax_id_taken": (status.HTTP_409_CONFLICT, "Ya existe una cadena registrada con ese CUIT."),
    "user_already_staff": (status.HTTP_409_CONFLICT, "Esta cuenta ya pertenece a un supermercado."),
    "chain_not_found": (status.HTTP_404_NOT_FOUND, "Cadena no encontrada."),
    "not_platform_admin": (status.HTTP_403_FORBIDDEN, "Se requieren permisos de administrador."),
    "rejection_reason_required": (status.HTTP_400_BAD_REQUEST, "Hay que indicar el motivo del rechazo."),
    "invalid_review_status": (status.HTTP_400_BAD_REQUEST, "Estado de revisión inválido."),
    "chain_already_in_status": (status.HTTP_409_CONFLICT, "La cadena ya se encuentra en ese estado."),
}


def _raise_for_rpc_error(exc: Exception, fallback: str) -> None:
    message = str(exc).lower()
    for token, (code, detail) in _RPC_ERRORS.items():
        if token in message:
            raise HTTPException(status_code=code, detail=detail)
    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=fallback)


def register_chain(payload: SupermarketRegisterRequest) -> SupermarketRegisterResponse:
    """
    Alta de una cadena. Dos pasos:

    1. Crear el usuario en Supabase Auth con `account_type: supermarket_staff`.
       Ese flag hace que el trigger `handle_new_user` (012) NO le cree una fila
       en `profiles`: el staff de un supermercado no es un consumidor.
    2. Llamar a `register_supermarket_chain`, que persiste cadena, sucursal,
       horarios, el usuario owner y el log de verificación en una sola
       transacción.

    A diferencia del registro de consumidor, `email_confirm` es False: el
    supermercado tiene que confirmar su correo de verdad antes de operar.
    Publica precios y recibe pedidos, así que la cuenta debe ser suya
    (docs/SEGURIDAD.md §3.3).
    """
    client = get_supabase()

    # Chequeo temprano del CUIT: crear el usuario en Auth y recién después
    # descubrir que el CUIT está tomado deja una cuenta huérfana que ya no se
    # puede reusar (el segundo intento choca con "email ya registrado").
    existing = (
        client.table("chains").select("id").eq("tax_id", payload.tax_id).limit(1).execute()
    )
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una cadena registrada con ese CUIT.",
        )

    try:
        result = client.auth.admin.create_user(
            {
                "email": payload.email,
                "password": payload.password,
                "email_confirm": False,
                "user_metadata": {
                    "account_type": "supermarket_staff",
                    "full_name": payload.owner_full_name,
                    "phone": payload.owner_phone,
                },
            }
        )
    except Exception as exc:
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

    user_id = result.user.id

    try:
        rpc_result = client.rpc(
            "register_supermarket_chain",
            {
                "p_user_id": str(user_id),
                "p_legal_name": payload.legal_name,
                "p_trade_name": payload.trade_name,
                "p_tax_id": payload.tax_id,
                "p_contact_email": payload.contact_email,
                "p_contact_phone": payload.contact_phone,
                "p_owner_full_name": payload.owner_full_name,
                "p_owner_phone": payload.owner_phone,
                "p_store": {
                    "name": payload.store.name,
                    "street": payload.store.street,
                    "city": payload.store.city,
                    "province": payload.store.province,
                    "postal_code": payload.store.postal_code,
                    "phone": payload.store.phone,
                },
                "p_hours": [
                    {
                        "weekday": h.weekday,
                        "opens_at": h.opens_at.isoformat(),
                        "closes_at": h.closes_at.isoformat(),
                    }
                    for h in payload.store.hours
                ],
            },
        ).execute()
    except Exception as exc:
        # La RPC es atómica, pero el usuario de Auth se creó FUERA de esa
        # transacción: si la cadena falla, hay que borrarlo o queda una cuenta
        # que puede loguearse y para la que get_current_staff no encuentra nada.
        try:
            client.auth.admin.delete_user(str(user_id))
        except Exception:
            # Si tampoco se puede borrar, se sigue adelante con el error
            # original: es el que le sirve al usuario. La cuenta huérfana queda
            # registrada en los logs de Supabase Auth.
            pass
        _raise_for_rpc_error(exc, "No se pudo registrar el supermercado. Intenta nuevamente.")

    return SupermarketRegisterResponse(
        chain_id=rpc_result.data,
        trade_name=payload.trade_name,
        status="pending_review",
        email_confirmation_required=True,
    )


def list_chains_for_review(
    status_filter: str | None, page: int, per_page: int
) -> ChainAdminListResponse:
    """Cola de moderación de la plataforma."""
    client = get_supabase()
    offset = (page - 1) * per_page

    query = client.table("chains").select("*, supermarkets(id)", count="exact")
    if status_filter:
        query = query.eq("status", status_filter)
    result = query.order("created_at", desc=False).range(offset, offset + per_page - 1).execute()

    chain_ids = [row["id"] for row in result.data]
    owners: dict[str, str] = {}
    if chain_ids:
        owner_rows = (
            client.table("supermarket_users")
            .select("chain_id, full_name")
            .in_("chain_id", chain_ids)
            .eq("role", "owner")
            .execute()
        ).data
        owners = {row["chain_id"]: row["full_name"] for row in owner_rows}

    return ChainAdminListResponse(
        data=[
            ChainAdminOut(
                **{k: v for k, v in row.items() if k != "supermarkets"},
                owner_full_name=owners.get(row["id"]),
                stores_count=len(row.get("supermarkets") or []),
            )
            for row in result.data
        ],
        total=result.count or 0,
        page=page,
        per_page=per_page,
    )


def review_chain(chain_id: UUID, admin_id: UUID, payload: ChainReviewRequest) -> ChainOut:
    """
    Aprueba, rechaza o suspende una cadena. La función `review_chain` de 014
    revalida el rol de administrador dentro de la transacción, además de la
    dependencia `get_current_platform_admin` del endpoint: defensa en
    profundidad (docs/SEGURIDAD.md §4.4).
    """
    client = get_supabase()
    try:
        result = client.rpc(
            "review_chain",
            {
                "p_chain_id": str(chain_id),
                "p_admin_id": str(admin_id),
                "p_status": payload.status,
                "p_note": payload.note,
            },
        ).execute()
    except Exception as exc:
        _raise_for_rpc_error(exc, "No se pudo actualizar el estado de la cadena.")

    return ChainOut.model_validate(result.data)
