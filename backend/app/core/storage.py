"""
ZARIS API — Cliente Supabase Storage para adjuntos de reclamos.
Usa httpx + service_role key. Bypassa RLS — toda autorización vive en
el backend (validación de JWT + scope de reclamo).
"""
import httpx
from fastapi import HTTPException

from app.core.config import settings

UPLOAD_TTL_SEC = 300  # 5 min para subir
DOWNLOAD_TTL_SEC = 3600  # 1 h para visualizar


def _check_config() -> None:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        raise HTTPException(
            status_code=503,
            detail="Supabase Storage no configurado (SUPABASE_URL/SUPABASE_SERVICE_KEY ausentes)",
        )


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
        "apikey": settings.SUPABASE_SERVICE_KEY,
    }


async def crear_signed_upload_url(path: str) -> dict:
    """
    Devuelve `{ url, token, path }` para que el cliente haga PUT del binario.
    El path es relativo al bucket (ej: 'reclamos/42/uuid.jpg').
    """
    _check_config()
    bucket = settings.SUPABASE_ADJUNTOS_BUCKET
    url = f"{settings.SUPABASE_URL}/storage/v1/object/upload/sign/{bucket}/{path}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, headers=_headers())
    if r.status_code != 200:
        raise HTTPException(status_code=502,
            detail=f"Storage signed upload error: {r.status_code} {r.text}")
    data = r.json()
    return {
        "upload_url": f"{settings.SUPABASE_URL}/storage/v1{data['url']}",
        "token": data.get("token"),
        "path": path,
        "bucket": bucket,
    }


async def crear_signed_download_url(path: str, ttl_sec: int = DOWNLOAD_TTL_SEC) -> str:
    """URL firmada para visualizar (GET) un objeto privado."""
    _check_config()
    bucket = settings.SUPABASE_ADJUNTOS_BUCKET
    url = f"{settings.SUPABASE_URL}/storage/v1/object/sign/{bucket}/{path}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, headers=_headers(), json={"expiresIn": ttl_sec})
    if r.status_code != 200:
        raise HTTPException(status_code=502,
            detail=f"Storage signed download error: {r.status_code} {r.text}")
    return f"{settings.SUPABASE_URL}/storage/v1{r.json()['signedURL']}"


async def borrar_objeto(path: str) -> None:
    """Borra el objeto del bucket. No-op silencioso si no existe."""
    _check_config()
    bucket = settings.SUPABASE_ADJUNTOS_BUCKET
    url = f"{settings.SUPABASE_URL}/storage/v1/object/{bucket}/{path}"
    async with httpx.AsyncClient(timeout=10) as client:
        await client.delete(url, headers=_headers())
