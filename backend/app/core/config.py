from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    JWT_SECRET: str
    # NoDecode: sin esto, pydantic-settings intenta interpretar el valor del .env
    # como JSON antes de llegar al validator (falla porque ALLOWED_ORIGINS es un
    # CSV plano, no una lista JSON).
    ALLOWED_ORIGINS: Annotated[list[str], NoDecode] = []

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def split_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


settings = Settings()
