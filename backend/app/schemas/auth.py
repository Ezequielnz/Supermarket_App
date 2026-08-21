from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, UUID4


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=30)


class RegisterResponse(BaseModel):
    id: UUID4
    email: EmailStr
    full_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CurrentUser(BaseModel):
    id: UUID4
    email: EmailStr


class CurrentStaff(BaseModel):
    """
    Staff de un supermercado. `chain_id` y `role` NO llegan por header ni por el
    body: se resuelven contra `supermarket_users` a partir del `sub` del JWT.
    Un identificador de cadena elegido por el cliente permitiría que el staff de
    una cadena opere sobre otra (ver docs/SEGURIDAD.md §4.1).
    """

    id: UUID4
    email: EmailStr
    chain_id: UUID4
    supermarket_id: UUID4 | None = None
    role: str
    chain_status: str


class CurrentPlatformAdmin(BaseModel):
    """Operador de FreshMart que aprueba o rechaza las altas de cadenas."""

    id: UUID4
    email: EmailStr
    full_name: str
