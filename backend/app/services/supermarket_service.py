from uuid import UUID

from fastapi import HTTPException, status

from app.core.supabase_client import get_supabase
from app.schemas.auth import CurrentStaff
from app.schemas.supermarket import (
    ChainOut,
    ChainProfileResponse,
    ChainUpdate,
    StaffInvite,
    StaffListResponse,
    StaffOut,
    StoreCreate,
    StoreHoursIn,
    StoreListResponse,
    StoreOut,
    StoreUpdate,
)


def get_store_or_404(store_id: UUID, chain_id: UUID) -> dict:
    """
    El backend usa service_role_key y bypasea RLS, así que la policy
    `supermarkets_select_approved` NO protege esta consulta: el filtro
    .eq("chain_id", chain_id) es la única barrera real (docs/SEGURIDAD.md §5.1).

    Si la sucursal existe pero es de otra cadena se devuelve 404, no 403, para
    no confirmar que el recurso existe — mismo criterio que list_service.
    """
    client = get_supabase()
    result = (
        client.table("supermarkets")
        .select("*")
        .eq("id", str(store_id))
        .eq("chain_id", str(chain_id))
        .maybe_single()
        .execute()
    )
    if result is None or result.data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sucursal no encontrada.")
    return result.data


def _display_address(street: str | None, city: str | None) -> str:
    """`supermarkets.address` se conserva como texto para mostrar; lo arma el
    backend a partir de los campos estructurados, igual que la RPC de 014."""
    return ", ".join(part for part in (street, city) if part)


def _replace_hours(store_id: UUID, hours: list[StoreHoursIn]) -> None:
    """
    Los horarios se reemplazan enteros, no se hace merge: el panel manda la
    semana completa. Borrar e insertar evita tener que razonar sobre altas,
    bajas y modificaciones día por día.
    """
    client = get_supabase()
    client.table("store_hours").delete().eq("supermarket_id", str(store_id)).execute()
    if not hours:
        return
    client.table("store_hours").insert(
        [
            {
                "supermarket_id": str(store_id),
                "weekday": h.weekday,
                "opens_at": h.opens_at.isoformat(),
                "closes_at": h.closes_at.isoformat(),
            }
            for h in hours
        ]
    ).execute()


def _hours_by_store(store_ids: list[str]) -> dict[str, list[dict]]:
    if not store_ids:
        return {}
    client = get_supabase()
    rows = (
        client.table("store_hours")
        .select("supermarket_id, weekday, opens_at, closes_at")
        .in_("supermarket_id", store_ids)
        .order("weekday")
        .execute()
    ).data
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["supermarket_id"], []).append(row)
    return grouped


def get_my_chain(current_staff: CurrentStaff) -> ChainProfileResponse:
    """Perfil de la cadena del staff autenticado, con su estado de revisión."""
    client = get_supabase()

    chain = (
        client.table("chains")
        .select("*")
        .eq("id", str(current_staff.chain_id))
        .single()
        .execute()
    ).data

    stores = (
        client.table("supermarkets")
        .select("id", count="exact")
        .eq("chain_id", str(current_staff.chain_id))
        .execute()
    )

    return ChainProfileResponse(
        chain=ChainOut.model_validate(chain),
        role=current_staff.role,
        stores_count=stores.count or 0,
    )


def update_my_chain(payload: ChainUpdate, chain_id: UUID) -> ChainOut:
    """
    Actualiza el perfil de la cadena. `tax_id` no es editable ni por el owner:
    es la identidad fiscal sobre la que se aprobó la cadena (ver ChainUpdate).
    """
    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay campos para actualizar.",
        )

    client = get_supabase()
    result = (
        client.table("chains")
        .update(updates)
        .eq("id", str(chain_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cadena no encontrada.")
    return ChainOut.model_validate(result.data[0])


def list_my_stores(chain_id: UUID, page: int, per_page: int) -> StoreListResponse:
    client = get_supabase()
    offset = (page - 1) * per_page

    result = (
        client.table("supermarkets")
        .select("*", count="exact")
        .eq("chain_id", str(chain_id))
        .order("name")
        .range(offset, offset + per_page - 1)
        .execute()
    )

    hours = _hours_by_store([row["id"] for row in result.data])

    return StoreListResponse(
        data=[StoreOut(**row, hours=hours.get(row["id"], [])) for row in result.data],
        total=result.count or 0,
        page=page,
        per_page=per_page,
    )


def get_store(store_id: UUID, chain_id: UUID) -> StoreOut:
    store = get_store_or_404(store_id, chain_id)
    hours = _hours_by_store([str(store_id)])
    return StoreOut(**store, hours=hours.get(str(store_id), []))


def create_store(payload: StoreCreate, chain_id: UUID) -> StoreOut:
    client = get_supabase()

    result = (
        client.table("supermarkets")
        .insert(
            {
                "chain_id": str(chain_id),
                "name": payload.name,
                "address": _display_address(payload.street, payload.city),
                "street": payload.street,
                "city": payload.city,
                "province": payload.province,
                "postal_code": payload.postal_code,
                "phone": payload.phone,
                "is_active": True,
            }
        )
        .execute()
    )
    store_id = UUID(result.data[0]["id"])
    _replace_hours(store_id, payload.hours)

    return get_store(store_id, chain_id)


def update_store(store_id: UUID, payload: StoreUpdate, chain_id: UUID) -> StoreOut:
    store = get_store_or_404(store_id, chain_id)

    updates = payload.model_dump(exclude_unset=True, exclude={"hours"})
    updates = {k: v for k, v in updates.items() if v is not None}

    if "street" in updates or "city" in updates:
        updates["address"] = _display_address(
            updates.get("street", store["street"]),
            updates.get("city", store["city"]),
        )

    client = get_supabase()
    if updates:
        client.table("supermarkets").update(updates).eq("id", str(store_id)).execute()

    if payload.hours is not None:
        _replace_hours(store_id, payload.hours)

    return get_store(store_id, chain_id)


def list_staff(chain_id: UUID, page: int, per_page: int) -> StaffListResponse:
    client = get_supabase()
    offset = (page - 1) * per_page

    result = (
        client.table("supermarket_users")
        .select("*", count="exact")
        .eq("chain_id", str(chain_id))
        .order("created_at")
        .range(offset, offset + per_page - 1)
        .execute()
    )

    return StaffListResponse(
        data=[StaffOut.model_validate(row) for row in result.data],
        total=result.count or 0,
        page=page,
        per_page=per_page,
    )


def invite_staff(payload: StaffInvite, chain_id: UUID) -> StaffOut:
    """
    Alta de un empleado. Crea el usuario en Supabase Auth sin contraseña y le
    manda un correo de invitación para que la defina: así el owner nunca conoce
    la contraseña de su equipo.

    El rol 'owner' no es asignable por acá (ver StaffInvite.role_is_assignable):
    hay un índice único parcial que permite uno solo por cadena.
    """
    client = get_supabase()

    if payload.supermarket_id is not None:
        # Sin esto, el owner de una cadena podría asignar a su empleado a una
        # sucursal de otra cadena pasando un UUID ajeno.
        get_store_or_404(payload.supermarket_id, chain_id)

    try:
        result = client.auth.admin.invite_user_by_email(
            payload.email,
            {
                "data": {
                    "account_type": "supermarket_staff",
                    "full_name": payload.full_name,
                    "phone": payload.phone,
                }
            },
        )
    except Exception as exc:
        message = str(exc).lower()
        if "already" in message or "exists" in message or "registered" in message:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ese correo ya tiene una cuenta en FreshMart.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo enviar la invitación. Intenta nuevamente.",
        )

    user_id = result.user.id

    try:
        inserted = (
            client.table("supermarket_users")
            .insert(
                {
                    "id": str(user_id),
                    "chain_id": str(chain_id),
                    "supermarket_id": str(payload.supermarket_id) if payload.supermarket_id else None,
                    "role": payload.role,
                    "full_name": payload.full_name,
                    "phone": payload.phone,
                }
            )
            .execute()
        )
    except Exception:
        # Mismo criterio que register_chain: el usuario de Auth se creó fuera de
        # la transacción, así que si la fila de staff falla hay que revertirlo.
        try:
            client.auth.admin.delete_user(str(user_id))
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo dar de alta al empleado. Intenta nuevamente.",
        )

    return StaffOut.model_validate(inserted.data[0])
