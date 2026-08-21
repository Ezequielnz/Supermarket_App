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
