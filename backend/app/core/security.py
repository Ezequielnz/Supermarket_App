import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.schemas.auth import CurrentUser

bearer_scheme = HTTPBearer()

# Los proyectos nuevos de Supabase firman los JWT de sesión con una clave
# asimétrica (ES256) por defecto, publicada vía JWKS — ya no con el "JWT
# Secret" compartido (HS256) que se usaba antes. Por eso la verificación se
# hace contra el JWKS público del proyecto, no con JWT_SECRET. PyJWKClient
# cachea las claves internamente, así que no se refetchea en cada request.
_jwks_client = jwt.PyJWKClient(f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json")


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
    """
    Verifica el JWT de sesión emitido por Supabase Auth y devuelve el usuario
    actual. Usado por todos los endpoints protegidos de consumidor (lists,
    orders, products).
    """
    token = credentials.credentials
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
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
    return CurrentUser(id=payload["sub"], email=payload.get("email", ""))
