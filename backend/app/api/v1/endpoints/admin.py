from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_platform_admin
from app.schemas.auth import CurrentPlatformAdmin
from app.schemas.supermarket import (
    CHAIN_STATUSES,
    ChainAdminListResponse,
    ChainOut,
    ChainReviewRequest,
)
from app.services import supermarket_auth_service

router = APIRouter(prefix="/admin", tags=["admin"])

# Moderación de la plataforma. Todo acá exige estar en `platform_admins`, tabla
# que se puebla exclusivamente por SQL: no hay endpoint para darse de alta como
# administrador, ni debe haberlo (docs/SEGURIDAD.md §4.2).


@router.get("/chains", response_model=ChainAdminListResponse)
def list_chains(
    status: str | None = Query(default=None, description=f"Uno de: {', '.join(CHAIN_STATUSES)}"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    _admin: CurrentPlatformAdmin = Depends(get_current_platform_admin),
):
    """
    Cola de moderación: cadenas registradas, filtrables por estado. Ordenadas de
    la más antigua a la más nueva para que se revisen por orden de llegada.
    """
    return supermarket_auth_service.list_chains_for_review(status, page, per_page)


@router.post("/chains/{chain_id}/review", response_model=ChainOut)
def review_chain(
    chain_id: UUID,
    payload: ChainReviewRequest,
    admin: CurrentPlatformAdmin = Depends(get_current_platform_admin),
):
    """
    Aprueba, rechaza o suspende una cadena. Rechazar exige un motivo, que el
    supermercado ve en su panel para poder corregir y volver a enviar.

    Aprobar es lo que hace visibles sus sucursales y precios en el comparador
    del consumidor.
    """
    return supermarket_auth_service.review_chain(chain_id, admin.id, payload)
