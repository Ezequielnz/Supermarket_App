import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.supabase_client import get_supabase
from app.schemas.auth import CurrentPlatformAdmin, CurrentStaff, CurrentUser

bearer_scheme = HTTPBearer()

# Los proyectos nuevos de Supabase firman los JWT de sesión con una clave
# asimétrica (ES256) por defecto, publicada vía JWKS — ya no con el "JWT
# Secret" compartido (HS256) que se usaba antes. Por eso la verificación se
# hace contra el JWKS público del proyecto. PyJWKClient cachea las claves
# internamente, así que no se refetchea en cada request.
_jwks_client = jwt.PyJWKClient(f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json")

# Roles que pueden administrar sucursales y catálogo. 'staff' solo lee.
MANAGER_ROLES = ("owner", "manager")


def _decode_token(token: str) -> dict:
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
    """
    Verifica el JWT de sesión emitido por Supabase Auth y devuelve el usuario
    actual. Usado por todos los endpoints protegidos de consumidor (lists,
    orders, products).
    """
    payload = _decode_token(credentials.credentials)
    return CurrentUser(id=payload["sub"], email=payload.get("email", ""))


def get_current_staff(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentStaff:
    """
    Verifica el JWT y resuelve a qué cadena pertenece el usuario consultando
    `supermarket_users` por el `sub` del token.

    La pertenencia se deriva SIEMPRE de la base, nunca de un header como el
    `X-Supermarket-ID` que proponía ARQUITECTURA.md §8: un identificador de
    cadena elegido por el cliente deja que el staff de la cadena A opere sobre
    la B. Ver docs/SEGURIDAD.md §4.1.

    No exige que la cadena esté aprobada — el panel necesita dejar entrar a un
    supermercado en `pending_review` para que vea el estado de su solicitud. Los
    endpoints que sí lo requieran usan `require_approved_chain`.
    """
    payload = _decode_token(credentials.credentials)
    user_id = payload["sub"]

    client = get_supabase()
    result = (
        client.table("supermarket_users")
        .select("*, chains(status)")
        .eq("id", user_id)
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    # .maybe_single() devuelve None como respuesta completa cuando no hay fila.
    if result is None or result.data is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta cuenta no pertenece a ningún supermercado.",
        )

    row = result.data
    return CurrentStaff(
        id=row["id"],
        email=payload.get("email", ""),
        chain_id=row["chain_id"],
        supermarket_id=row["supermarket_id"],
        role=row["role"],
        chain_status=row["chains"]["status"],
    )


def require_manager(current_staff: CurrentStaff = Depends(get_current_staff)) -> CurrentStaff:
    """Exige rol 'owner' o 'manager'. Para altas y ediciones de sucursales."""
    if current_staff.role not in MANAGER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de encargado o responsable.",
        )
    return current_staff


def require_owner(current_staff: CurrentStaff = Depends(get_current_staff)) -> CurrentStaff:
    """
    Exige rol 'owner'. Para el perfil fiscal de la cadena y la gestión del
    equipo: son las dos cosas que definen quién responde por el supermercado.
    """
    if current_staff.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el responsable de la cadena puede realizar esta acción.",
        )
    return current_staff


def require_approved_chain(
    current_staff: CurrentStaff = Depends(get_current_staff),
) -> CurrentStaff:
    """
    Exige que la cadena esté aprobada. Se aplica a todo lo operativo (pedidos,
    precios): una cadena en revisión, rechazada o suspendida no opera.
    """
    if current_staff.chain_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cadena todavía no está aprobada para operar.",
        )
    return current_staff


def require_approved_manager(
    current_staff: CurrentStaff = Depends(require_approved_chain),
) -> CurrentStaff:
    """
    Cadena aprobada Y rol de encargado o responsable. Es la combinación que
    exige toda escritura del catálogo: publicar precios es operar (de ahí lo
    aprobado) y la matriz de docs/SEGURIDAD.md §4.2 le da al rol 'staff' solo
    lectura sobre los precios de su cadena.

    Va como dependencia propia y no anidando require_manager dentro de
    require_approved_chain porque FastAPI resuelve cada dependencia por
    separado: encadenarlas a mano es lo que garantiza que se evalúen las dos.
    """
    if current_staff.role not in MANAGER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de encargado o responsable.",
        )
    return current_staff


def get_current_platform_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentPlatformAdmin:
    """
    Operador de FreshMart. `platform_admins` se puebla exclusivamente por SQL:
    no existe, ni debe existir, un endpoint para darse de alta como admin.
    """
    payload = _decode_token(credentials.credentials)

    client = get_supabase()
    result = (
        client.table("platform_admins")
        .select("*")
        .eq("id", payload["sub"])
        .maybe_single()
        .execute()
    )
    if result is None or result.data is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador de la plataforma.",
        )

    return CurrentPlatformAdmin(
        id=result.data["id"],
        email=payload.get("email", ""),
        full_name=result.data["full_name"],
    )
