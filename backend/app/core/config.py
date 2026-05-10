"""
ZARIS API — Configuracion central (Pydantic Settings).
Soporta tanto variables POSTGRES_* individuales como DATABASE_URL de Railway.
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "ZARIS API"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "postgres"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    CORS_ORIGINS: list[str] = ["*"]
    DATABASE_URL: str = ""

    # Supabase Storage (adjuntos de reclamos)
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_ADJUNTOS_BUCKET: str = "reclamos-adjuntos"

    @property
    def ASYNC_DATABASE_URI(self) -> str:
        # Si existe DATABASE_URL (Railway la provee), usarla
        db_url = self.DATABASE_URL or os.environ.get("DATABASE_URL", "")
        if db_url:
            # Convertir postgres:// a postgresql+asyncpg://
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return db_url
        # Fallback a variables individuales
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    class Config:
        # Permite seleccionar el archivo de entorno con la variable ENV_FILE
        # (ej: ENV_FILE=.env.local para desarrollo local). Default: .env
        env_file = os.getenv("ENV_FILE", ".env")


settings = Settings()

