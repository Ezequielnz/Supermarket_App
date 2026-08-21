from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.security import get_current_staff, require_manager, require_owner
from app.schemas.auth import CurrentStaff
from app.schemas.supermarket import (
    ChainProfileResponse,
    ChainOut,
    ChainUpdate,
    StaffInvite,
    StaffListResponse,
    StaffOut,
    StoreCreate,
    StoreListResponse,
    StoreOut,
    StoreUpdate,
    SupermarketRegisterRequest,
    SupermarketRegisterResponse,
)
from app.services import supermarket_auth_service, supermarket_service

router = APIRouter(prefix="/supermarkets", tags=["supermarkets"])

# El login del staff NO se implementa acá: va directo contra Supabase
# (signInWithPassword) desde supermarket_admin, igual que el del consumidor.
# Es la excepción de docs/NORMAS.md sección 2.


@router.post(
    "/register",
    response_model=SupermarketRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_supermarket(payload: SupermarketRegisterRequest):
    """
    Registra una cadena de supermercados: crea la cuenta del responsable, la
    cadena en estado 'pending_review', su primera sucursal y los horarios.
    Público, no requiere autenticación.

    La cadena no aparece en el comparador hasta que un administrador de la
    plataforma la aprueba (POST /admin/chains/{id}/review).
    """
    return supermarket_auth_service.register_chain(payload)


@router.get("/me", response_model=ChainProfileResponse)
def get_my_supermarket(current_staff: CurrentStaff = Depends(get_current_staff)):
    """
    Perfil de la cadena del staff autenticado, con su estado de verificación y
    el motivo del rechazo si corresponde.

    Deliberadamente NO exige cadena aprobada: es el endpoint que el panel
    consulta para saber si mostrar el dashboard o la pantalla de "en revisión".
    """
    return supermarket_service.get_my_chain(current_staff)


@router.patch("/me", response_model=ChainOut)
def update_my_supermarket(
    payload: ChainUpdate,
    current_staff: CurrentStaff = Depends(require_owner),
):
    """Actualiza el perfil de la cadena. Solo el responsable (owner)."""
    return supermarket_service.update_my_chain(payload, current_staff.chain_id)


@router.get("/me/stores", response_model=StoreListResponse)
def get_my_stores(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_staff: CurrentStaff = Depends(get_current_staff),
):
    """Lista las sucursales de la cadena del staff autenticado."""
    return supermarket_service.list_my_stores(current_staff.chain_id, page, per_page)


@router.post("/me/stores", response_model=StoreOut, status_code=status.HTTP_201_CREATED)
def create_my_store(
    payload: StoreCreate,
    current_staff: CurrentStaff = Depends(require_manager),
):
    """Agrega una sucursal a la cadena. Requiere rol de encargado o responsable."""
    return supermarket_service.create_store(payload, current_staff.chain_id)


@router.get("/me/stores/{store_id}", response_model=StoreOut)
def get_my_store(
    store_id: UUID,
    current_staff: CurrentStaff = Depends(get_current_staff),
):
    """Detalle de una sucursal propia, con sus horarios."""
    return supermarket_service.get_store(store_id, current_staff.chain_id)


@router.patch("/me/stores/{store_id}", response_model=StoreOut)
def update_my_store(
    store_id: UUID,
    payload: StoreUpdate,
    current_staff: CurrentStaff = Depends(require_manager),
):
    """Edita una sucursal propia y sus horarios. Los horarios se reemplazan enteros."""
    return supermarket_service.update_store(store_id, payload, current_staff.chain_id)


@router.get("/me/users", response_model=StaffListResponse)
def get_my_staff(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_staff: CurrentStaff = Depends(require_owner),
):
    """Lista el equipo de la cadena. Solo el responsable."""
    return supermarket_service.list_staff(current_staff.chain_id, page, per_page)


@router.post("/me/users", response_model=StaffOut, status_code=status.HTTP_201_CREATED)
def invite_my_staff(
    payload: StaffInvite,
    current_staff: CurrentStaff = Depends(require_owner),
):
    """
    Invita a un empleado por correo. Solo el responsable. El rol 'owner' no es
    asignable: hay uno solo por cadena y se define en el registro.
    """
    return supermarket_service.invite_staff(payload, current_staff.chain_id)
