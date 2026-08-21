from datetime import datetime, time
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, UUID4, field_validator

# Días de la semana como en EXTRACT(DOW) de Postgres y en el CHECK weekday_range
# de la migración 010: 0 = domingo, 6 = sábado.
WEEKDAY_MIN = 0
WEEKDAY_MAX = 6

CHAIN_STATUSES = ("pending_review", "approved", "rejected", "suspended")

# Única cadena visible para el consumidor. Una cadena en revisión, rechazada o
# suspendida no aparece en el comparador ni puede recibir pedidos.
APPROVED_CHAIN_STATUS = "approved"
REVIEWABLE_STATUSES = ("approved", "rejected", "suspended")


class StoreHoursIn(BaseModel):
    weekday: int = Field(ge=WEEKDAY_MIN, le=WEEKDAY_MAX)
    opens_at: time
    closes_at: time

    @field_validator("closes_at")
    @classmethod
    def closes_after_opens(cls, v: time, info):
        opens_at = info.data.get("opens_at")
        if opens_at is not None and v <= opens_at:
            raise ValueError("El horario de cierre debe ser posterior al de apertura.")
        return v


class StoreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    street: str = Field(min_length=1, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    province: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=30)
    hours: list[StoreHoursIn] = Field(default_factory=list, max_length=7)

    @field_validator("hours")
    @classmethod
    def unique_weekdays(cls, v: list[StoreHoursIn]) -> list[StoreHoursIn]:
        # Refleja el UNIQUE (supermarket_id, weekday) de 010: mejor un 422 claro
        # que un error de constraint traducido a 502.
        weekdays = [h.weekday for h in v]
        if len(weekdays) != len(set(weekdays)):
            raise ValueError("Hay días de la semana repetidos en los horarios.")
        return v


class StoreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    street: str | None = Field(default=None, min_length=1, max_length=200)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    province: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=30)
    is_active: bool | None = None
    hours: list[StoreHoursIn] | None = Field(default=None, max_length=7)


class SupermarketRegisterRequest(BaseModel):
    """
    Alta pública de una cadena. Un solo request con todo: cuenta del responsable,
    datos de la cadena y primera sucursal. El wizard del front acumula los pasos
    en memoria y envía esto al final.
    """

    # Cuenta del responsable
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    owner_full_name: str = Field(min_length=1, max_length=120)
    owner_phone: str | None = Field(default=None, max_length=30)

    # Datos de la cadena
    legal_name: str = Field(min_length=1, max_length=200)
    trade_name: str = Field(min_length=1, max_length=120)
    tax_id: Annotated[str, Field(min_length=11, max_length=13)]
    contact_email: EmailStr
    contact_phone: str | None = Field(default=None, max_length=30)

    # Primera sucursal
    store: StoreCreate

    accepts_terms: bool

    @field_validator("tax_id")
    @classmethod
    def normalize_tax_id(cls, v: str) -> str:
        # El usuario escribe "30-71234567-8"; la base espera 11 dígitos
        # (CHECK tax_id_format de 010).
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) != 11:
            raise ValueError("El CUIT debe tener 11 dígitos.")
        return digits

    @field_validator("accepts_terms")
    @classmethod
    def must_accept_terms(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Debés aceptar los términos para registrar tu supermercado.")
        return v


class SupermarketRegisterResponse(BaseModel):
    chain_id: UUID4
    trade_name: str
    status: str
    email_confirmation_required: bool


class ChainOut(BaseModel):
    id: UUID4
    legal_name: str
    trade_name: str
    tax_id: str
    contact_email: EmailStr
    contact_phone: str | None = None
    logo_url: str | None = None
    status: str
    rejection_reason: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChainUpdate(BaseModel):
    legal_name: str | None = Field(default=None, min_length=1, max_length=200)
    trade_name: str | None = Field(default=None, min_length=1, max_length=120)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=30)
    logo_url: str | None = Field(default=None, max_length=500)
    # tax_id NO es editable: es la identidad fiscal sobre la que se aprobó la
    # cadena. Cambiarlo equivale a ser otra empresa y exige una nueva revisión.


class StoreHoursOut(BaseModel):
    weekday: int
    opens_at: time
    closes_at: time

    model_config = {"from_attributes": True}


class StoreOut(BaseModel):
    id: UUID4
    name: str
    address: str | None = None
    street: str | None = None
    city: str | None = None
    province: str | None = None
    postal_code: str | None = None
    phone: str | None = None
    is_active: bool
    hours: list[StoreHoursOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class StoreListResponse(BaseModel):
    data: list[StoreOut]
    total: int
    page: int
    per_page: int


class StaffOut(BaseModel):
    id: UUID4
    full_name: str
    role: str
    phone: str | None = None
    supermarket_id: UUID4 | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class StaffListResponse(BaseModel):
    data: list[StaffOut]
    total: int
    page: int
    per_page: int


class StaffInvite(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    role: str = Field(default="staff")
    phone: str | None = Field(default=None, max_length=30)
    supermarket_id: UUID4 | None = None

    @field_validator("role")
    @classmethod
    def role_is_assignable(cls, v: str) -> str:
        # 'owner' queda fuera a propósito: hay un índice único parcial que
        # permite uno solo por cadena, y se asigna en el registro.
        if v not in ("manager", "staff"):
            raise ValueError("El rol debe ser 'manager' o 'staff'.")
        return v


class ChainProfileResponse(BaseModel):
    """Lo que ve el panel del supermercado al abrir sesión."""

    chain: ChainOut
    role: str
    stores_count: int


class ChainReviewRequest(BaseModel):
    status: str
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("status")
    @classmethod
    def status_is_reviewable(cls, v: str) -> str:
        if v not in REVIEWABLE_STATUSES:
            raise ValueError(f"El estado debe ser uno de: {', '.join(REVIEWABLE_STATUSES)}.")
        return v


class ChainAdminOut(ChainOut):
    """Vista de la cola de moderación: agrega el contacto responsable."""

    owner_full_name: str | None = None
    stores_count: int = 0


class ChainAdminListResponse(BaseModel):
    data: list[ChainAdminOut]
    total: int
    page: int
    per_page: int
