from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.security import (
    get_current_staff,
    require_approved_chain,
    require_approved_manager,
    require_manager,
    require_owner,
)
from app.schemas.auth import CurrentStaff
from app.schemas.catalog import (
    ProductLookupResponse,
    SupermarketProductCreate,
    SupermarketProductListResponse,
    SupermarketProductOut,
    SupermarketProductUpdate,
)
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
from app.services import (
    supermarket_auth_service,
    supermarket_product_service,
    supermarket_service,
)

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


# ── Catálogo y precios ────────────────────────────────────────────────────
# Los primeros endpoints que usan `require_approved_chain`: publicar precios es
# operar, y una cadena en revisión, rechazada o suspendida no opera
# (docs/SEGURIDAD.md §4.2). Leer el catálogo propio lo puede hacer cualquier
# staff; escribirlo, solo owner o manager — igual que las sucursales.


@router.get("/me/products", response_model=SupermarketProductListResponse)
def get_my_products(
    supermarket_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_staff: CurrentStaff = Depends(require_approved_chain),
):
    """
    Catálogo propio con precios, paginado. Filtrable por sucursal (`supermarket_id`)
    y por nombre (`q`). Solo devuelve precios de sucursales de la propia cadena.
    """
    return supermarket_product_service.list_my_products(
        current_staff.chain_id, supermarket_id, q, page, per_page
    )


@router.get("/me/products/lookup", response_model=ProductLookupResponse)
def lookup_catalog_product(
    ean: str | None = Query(default=None, max_length=14),
    q: str | None = Query(default=None, max_length=120),
    supermarket_id: UUID | None = Query(default=None),
    current_staff: CurrentStaff = Depends(require_approved_chain),
):
    """
    Busca en el catálogo global antes de crear un producto: por EAN (identidad
    exacta) o por nombre (candidatos a elegir a mano). Es el paso que evita que
    cada cadena duplique el mismo producto y vacíe el comparador.
    """
    return supermarket_product_service.lookup(
        current_staff.chain_id, supermarket_id, ean, q
    )


@router.post(
    "/me/products",
    response_model=SupermarketProductOut,
    status_code=status.HTTP_201_CREATED,
)
def create_my_product(
    payload: SupermarketProductCreate,
    current_staff: CurrentStaff = Depends(require_approved_manager),
):
    """
    Empieza a vender un producto en una sucursal propia: resuelve el producto
    del catálogo global (por EAN, o creándolo) y carga el precio.
    Requiere rol de encargado o responsable, y cadena aprobada.
    """
    return supermarket_product_service.add_product(payload, current_staff.chain_id)


@router.patch("/me/products/{listing_id}", response_model=SupermarketProductOut)
def update_my_product(
    listing_id: UUID,
    payload: SupermarketProductUpdate,
    current_staff: CurrentStaff = Depends(require_approved_manager),
):
    """
    Cambia el precio o el stock de un producto propio. `listing_id` es el id de
    la fila de `supermarket_products` (el precio), no el del producto global.
    """
    return supermarket_product_service.update_product(
        listing_id, payload, current_staff.chain_id
    )


@router.delete("/me/products/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_product(
    listing_id: UUID,
    current_staff: CurrentStaff = Depends(require_approved_manager),
):
    """
    Deja de vender ese producto en esa sucursal. Borra la fila de precio; el
    producto del catálogo global no se toca, porque es compartido.
    """
    supermarket_product_service.remove_product(listing_id, current_staff.chain_id)
