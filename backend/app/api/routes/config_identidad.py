"""
ZARIS API - Identidad del producto en el topbar (nombre app + nombre/logo municipio).

GET    /api/v1/config/identidad                  publico (todos pueden leerla)
PUT    /api/v1/config/identidad                  admin (nivel 1) - actualiza nombre/url
POST   /api/v1/config/identidad/logo-upload-url  admin - signed URL para subir logo

Las 3 claves viven en `configuracion_general`:
  - app_nombre          (string, default 'GESTION ESTADO')
  - municipio_nombre    (string, default 'MUNICIPALIDAD')
  - municipio_logo_url  (string, default '' = sin logo)

El bucket es `config-assets` (publico, 2MB, image/png|jpeg|webp|svg+xml).
La URL persistida es la URL publica directa (no firmada) - el bucket es public.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core import storage

router = APIRouter(prefix="/api/v1/config/identidad", tags=["Config - Identidad"])

BUCKET = "config-assets"
CLAVES = ("app_nombre", "municipio_nombre", "municipio_logo_url")
MIME_OK = {"image/png", "image/jpeg", "image/webp", "image/svg+xml"}
MIME_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/svg+xml": "svg",
}
MAX_BYTES = 2 * 1024 * 1024  # 2 MB


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["nivel_acceso"] != 1:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Requiere nivel administrador")
    return current_user


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class IdentidadOut(BaseModel):
    app_nombre: str
    municipio_nombre: str
    municipio_logo_url: str


class IdentidadUpdate(BaseModel):
    app_nombre: Optional[str] = Field(default=None, max_length=80)
    municipio_nombre: Optional[str] = Field(default=None, max_length=120)
    municipio_logo_url: Optional[str] = Field(default=None, max_length=500)


class LogoUploadRequest(BaseModel):
    mime_type: str
    tamano_bytes: int = Field(ge=1)


class LogoUploadResponse(BaseModel):
    upload_url: str
    public_url: str
    path: str
    bucket: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _leer_claves(db: AsyncSession) -> dict[str, str]:
    rows = await db.execute(text(
        "SELECT clave, valor FROM configuracion_general WHERE clave = ANY(:claves)"
    ), {"claves": list(CLAVES)})
    data = {r.clave: r.valor for r in rows.fetchall()}
    # Defaults para claves faltantes (no deberian faltar tras seed, pero por las dudas)
    return {
        "app_nombre": data.get("app_nombre", "GESTION ESTADO"),
        "municipio_nombre": data.get("municipio_nombre", "MUNICIPALIDAD"),
        "municipio_logo_url": data.get("municipio_logo_url", ""),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=IdentidadOut)
async def get_identidad(db: AsyncSession = Depends(get_db)):
    """Publico. Lo lee el shell vanilla al cargar para renderizar el topbar."""
    return await _leer_claves(db)


@router.put("", response_model=IdentidadOut)
async def update_identidad(
    payload: IdentidadUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """Actualiza una o mas claves. Solo nivel administrador."""
    actualizables = payload.model_dump(exclude_none=True)
    if not actualizables:
        raise HTTPException(422, "Body vacio: incluir al menos una clave")
    for clave, valor in actualizables.items():
        await db.execute(text("""
            UPDATE configuracion_general
            SET valor = :v, fecha_modificacion = NOW()
            WHERE clave = :k
        """), {"k": clave, "v": valor})
    await db.commit()
    return await _leer_claves(db)


@router.post("/logo-upload-url", response_model=LogoUploadResponse)
async def crear_upload_url_logo(
    payload: LogoUploadRequest,
    _admin: dict = Depends(require_admin),
):
    """Devuelve URL firmada para que el cliente haga PUT del binario del logo
    directo a Supabase Storage. El backend NO recibe el binario."""
    if payload.mime_type not in MIME_OK:
        raise HTTPException(422, f"MIME no permitido: {payload.mime_type}. Aceptados: {sorted(MIME_OK)}")
    if payload.tamano_bytes > MAX_BYTES:
        raise HTTPException(422, f"Archivo excede 2MB ({payload.tamano_bytes} bytes)")
    ext = MIME_EXT[payload.mime_type]
    path = f"municipio/logo-{uuid.uuid4()}.{ext}"
    signed = await storage.crear_signed_upload_url(path, bucket=BUCKET)
    return LogoUploadResponse(
        upload_url=signed["upload_url"],
        public_url=storage.url_publica(path, BUCKET),
        path=path,
        bucket=BUCKET,
    )
