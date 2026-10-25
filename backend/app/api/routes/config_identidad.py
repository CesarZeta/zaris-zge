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

Municipio (IT-01): el GET es publico y toma el municipio de la direccion
(municipio_de_origen); el PUT y la subida del logo, el del administrador
(municipio_actual). Lectura con leer_configs (la fila del municipio o la global) y
guardado con guardar_config (solo la fila del municipio). Sin nombre propio, el
nombre es el de la tabla municipios.
"""
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.config_municipio import guardar_config, leer_configs
from app.core.database import get_db
from app.core.municipio import municipio_actual, municipio_de_origen
from app.core import storage
from app.core.urls import url_publica as _url_publica  # fuente única con publico_alta (Portal del Ciudadano)

router = APIRouter(prefix="/api/v1/config/identidad", tags=["Config - Identidad"])

BUCKET = "config-assets"
# `app_nombre` ('GESTION ESTADO') es hardcoded del producto, no editable.
# Solo persistimos lo que el municipio puede personalizar.
APP_NOMBRE = "GESTION ESTADO"
# Identidad completa del municipio (2026-07-16): nombre/logo del topbar +
# descripcion y colores de marca de la App Vecinos (antes se editaban en
# Config -> Sistema; se unificaron aca — las claves existen desde mig 52).
CLAVES = (
    "municipio_nombre",
    "municipio_logo_url",
    "municipio_descripcion",
    "municipio_color_primary",
    "municipio_color_accent",
)
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
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
    app_nombre: str  # constante del producto, devuelto por compat con shell vanilla
    municipio_nombre: str
    municipio_logo_url: str
    municipio_descripcion: str
    municipio_color_primary: str
    municipio_color_accent: str
    # Slug (codigo_corto) del municipio. Lo usa Config -> Identidad para previsualizar
    # las URLs publicas del municipio (ej. el alta de vecinos:
    # .../frontend/alta-vecino.html?m=<slug>). None si no hay.
    municipio_slug: Optional[str] = None
    # URL publica de la App Vecinos (PWA). La consume la app de agentes (tenant) y
    # queda por compat; desde el 2026-09-27 "Mi perfil" ya NO la muestra: el vecino
    # instala su app desde el portal del vecino (decision de Cesar).
    # Fuente unica con los mails de activacion: settings.APP_VECINOS_FRONTEND_URL
    # (env var en Railway). Cuando llegue IT-01 (multi-municipio) se mueve a
    # configuracion_general sin tocar la vista.
    app_vecinos_url: str = ""
    # URL publica de la App de agentes (PWA zaris-agentes). La muestra la vista
    # "Mi perfil" del backoffice (QR + link para que el funcionario la instale en su
    # celular). Fuente: settings.APP_AGENTES_FRONTEND_URL (env var en Railway).
    app_agentes_url: str = ""


class IdentidadUpdate(BaseModel):
    municipio_nombre: Optional[str] = Field(default=None, max_length=120)
    municipio_logo_url: Optional[str] = Field(default=None, max_length=500)
    municipio_descripcion: Optional[str] = Field(default=None, max_length=300)
    municipio_color_primary: Optional[str] = Field(default=None, max_length=7)
    municipio_color_accent: Optional[str] = Field(default=None, max_length=7)

    @field_validator("municipio_color_primary", "municipio_color_accent")
    @classmethod
    def _hex_valido(cls, v: Optional[str]) -> Optional[str]:
        # '' es valido (= quitar el color, la PWA cae a su default).
        if v is None or v == "":
            return v
        if not HEX_RE.match(v):
            raise ValueError("Color invalido: usar formato #RRGGBB")
        return v


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

async def _leer_claves(db: AsyncSession, id_municipio: int) -> dict[str, str]:
    data = await leer_configs(db, list(CLAVES), id_municipio)
    muni = (await db.execute(text(
        "SELECT nombre, codigo_corto FROM municipios WHERE id_municipio = :m"
    ), {"m": id_municipio})).fetchone()
    slug = muni.codigo_corto if muni else None
    # Sin nombre propio cargado, el de la tabla municipios.
    nombre = (data.get("municipio_nombre") or "").strip() or (muni.nombre if muni else "") or "MUNICIPALIDAD"
    return {
        "app_nombre": APP_NOMBRE,
        "municipio_nombre": nombre,
        "municipio_logo_url": data.get("municipio_logo_url", ""),
        "municipio_descripcion": data.get("municipio_descripcion", ""),
        "municipio_color_primary": data.get("municipio_color_primary", ""),
        "municipio_color_accent": data.get("municipio_color_accent", ""),
        "municipio_slug": slug,
        "app_vecinos_url": _url_publica(settings.APP_VECINOS_FRONTEND_URL),
        "app_agentes_url": _url_publica(settings.APP_AGENTES_FRONTEND_URL),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=IdentidadOut)
async def get_identidad(
    db: AsyncSession = Depends(get_db),
    id_municipio: int = Depends(municipio_de_origen),
):
    """Publico. Lo lee el shell vanilla al cargar para renderizar el topbar."""
    return await _leer_claves(db, id_municipio)


@router.put("", response_model=IdentidadOut, responses={409: {"description": "El municipio no tiene esa clave"}})
async def update_identidad(
    payload: IdentidadUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
    id_municipio: int = Depends(municipio_actual),
):
    """Actualiza una o mas claves del municipio. Solo nivel administrador."""
    actualizables = payload.model_dump(exclude_none=True)
    if not actualizables:
        raise HTTPException(422, "Body vacio: incluir al menos una clave")
    for clave, valor in actualizables.items():
        if not await guardar_config(db, clave, valor, id_municipio):
            # Hasta el lote de limpieza (UNIQUE(clave) global) no se puede crear la fila.
            await db.rollback()
            raise HTTPException(409, f"El municipio no tiene la clave {clave} cargada")
    await db.commit()
    return await _leer_claves(db, id_municipio)


@router.post("/logo-upload-url", response_model=LogoUploadResponse)
async def crear_upload_url_logo(
    payload: LogoUploadRequest,
    _admin: dict = Depends(require_admin),
    id_municipio: int = Depends(municipio_actual),
):
    """Devuelve URL firmada para que el cliente haga PUT del binario del logo
    directo a Supabase Storage. El backend NO recibe el binario."""
    if payload.mime_type not in MIME_OK:
        raise HTTPException(422, f"MIME no permitido: {payload.mime_type}. Aceptados: {sorted(MIME_OK)}")
    if payload.tamano_bytes > MAX_BYTES:
        raise HTTPException(422, f"Archivo excede 2MB ({payload.tamano_bytes} bytes)")
    ext = MIME_EXT[payload.mime_type]
    path = f"municipio/{id_municipio}/logo-{uuid.uuid4()}.{ext}"
    signed = await storage.crear_signed_upload_url(path, bucket=BUCKET)
    return LogoUploadResponse(
        upload_url=signed["upload_url"],
        public_url=storage.url_publica(path, BUCKET),
        path=path,
        bucket=BUCKET,
    )
