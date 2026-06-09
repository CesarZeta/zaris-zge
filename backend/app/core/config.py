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

    # Email via Resend (API HTTP, puerto 443). Migrado desde SMTP Zoho porque Railway
    # bloquea el egress SMTP saliente (587/465 dan timeout). Si RESEND_API_KEY queda vacia,
    # el sender corre en modo MOCK (log a stdout, no envia). Ver app/services/email.py.
    RESEND_API_KEY: str = ""         # API key de Resend (empieza con "re_"). Set via env var; NO commitear.
    RESEND_FROM: str = "no-reply@zaris.com.ar"  # Remitente por defecto. Debe usar el dominio VERIFICADO en Resend (zaris.com.ar raíz, NO el subdominio send.*). Override via env var en Railway.
    APP_BASE_URL: str = "https://zge.zaris.com.ar"  # URL para links en mails (apunta al shell vanilla en prod)

    # App Vecinos (PWA publica de ciudadanos)
    APP_VECINOS_FRONTEND_URL: str = "http://localhost:5174"  # URL del frontend PWA para links de activacion/recovery
    JWT_PUBLICO_EXPIRA_DIAS: int = 30  # Vigencia del JWT scope=publico (mas largo que el de agente)

    # Encuestas (CSAT) — mig 57
    # Base del frontend del producto (shell vanilla) para armar el link publico de la encuesta.
    # En prod apunta al dominio real (§6). El form publico vive en /frontend/encuesta.html.
    FRONTEND_BASE_URL: str = "https://zge.zaris.com.ar"
    # Token compartido para autenticar el job dispatcher de encuestas (cron externo que
    # dispara procesar_envios_pendientes/expirar_envios_vencidos). Set via env var en Railway;
    # NO commitear el valor real. Vacio => el endpoint dispatcher debe rechazar (cuando exista).
    DISPATCHER_TOKEN: str = ""

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
        # Ignorar env vars desconocidas (ej. las SMTP_* deprecadas que aun viven en
        # .env.local y Railway tras migrar a Resend). Sin esto, pydantic-settings rechaza
        # extras y el backend no arranca hasta limpiar las vars en TODOS los entornos.
        extra = "ignore"


settings = Settings()

