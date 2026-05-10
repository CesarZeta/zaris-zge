"""
ZARIS API — Adjuntos de reclamos.
Prefijo: /api/v1/reclamos/{id_reclamo}/adjuntos

Flujo:
- POST /upload-url      → backend valida reclamo + crea fila pre-upload + URL firmada PUT
- POST /{id_adjunto}/confirm → frontend confirma que subió OK (marca activo=TRUE definitivo)
- GET  ""                → lista adjuntos con URLs firmadas GET (TTL 1h)
- DELETE /{id_adjunto}  → soft-delete + borra binario del bucket
"""
import logging
import re
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user
from app.core import storage

router = APIRouter(prefix="/api/v1/reclamos/{id_reclamo}/adjuntos", tags=["Reclamos · Adjuntos"])
logger = logging.getLogger("zaris.adjuntos")

MIME_PERMITIDOS = {
    "image/jpeg", "image/png", "image/webp",
    "image/gif", "image/heic", "image/heif",
}
EXT_POR_MIME = {
    "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp",
    "image/gif": "gif", "image/heic": "heic", "image/heif": "heif",
}
MAX_BYTES = 10 * 1024 * 1024  # 10 MB


def _safe_filename(nombre: str) -> str:
    nombre = (nombre or "").strip() or "archivo"
    return re.sub(r"[^\w\.\-]+", "_", nombre)[:120]


async def _existe_reclamo(db: AsyncSession, id_reclamo: int) -> None:
    r = await db.execute(text(
        "SELECT 1 FROM reclamos WHERE id_reclamo = :id AND activo = TRUE"
    ), {"id": id_reclamo})
    if not r.fetchone():
        raise HTTPException(status_code=404, detail=f"Reclamo {id_reclamo} no encontrado")


# ── POST /upload-url ─────────────────────────────────────────────────────────

@router.post("/upload-url", status_code=201)
async def crear_upload_url(
    id_reclamo: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    nombre_archivo = _safe_filename(body.get("nombre_archivo", ""))
    mime_type = (body.get("mime_type") or "").lower()
    tamano = int(body.get("tamano_bytes") or 0)
    descripcion = body.get("descripcion", "")

    if mime_type not in MIME_PERMITIDOS:
        raise HTTPException(status_code=422,
            detail=f"Tipo de archivo no permitido: {mime_type or 'sin tipo'}")
    if tamano <= 0 or tamano > MAX_BYTES:
        raise HTTPException(status_code=422,
            detail=f"Tamaño inválido (máx {MAX_BYTES // (1024*1024)} MB)")

    await _existe_reclamo(db, id_reclamo)

    ext = EXT_POR_MIME.get(mime_type, "bin")
    storage_path = f"reclamos/{id_reclamo}/{uuid.uuid4()}.{ext}"

    signed = await storage.crear_signed_upload_url(storage_path)

    # Insertar fila en estado "pendiente de confirmación" (activo=FALSE)
    result = await db.execute(text("""
        INSERT INTO reclamo_adjuntos
            (id_reclamo, storage_bucket, storage_path, nombre_archivo,
             mime_type, tamano_bytes, descripcion, activo,
             fecha_alta, fecha_modificacion, id_usuario_alta, id_usuario_modificacion)
        VALUES
            (:id_r, :bucket, :path, :nombre, :mime, :size, :desc, FALSE,
             NOW(), NOW(), :uid, :uid)
        RETURNING id_adjunto
    """), {
        "id_r": id_reclamo, "bucket": signed["bucket"], "path": storage_path,
        "nombre": nombre_archivo, "mime": mime_type, "size": tamano,
        "desc": descripcion, "uid": current_user["id_usuario"],
    })
    id_adjunto = result.scalar_one()
    await db.commit()

    return {
        "id_adjunto": id_adjunto,
        "upload_url": signed["upload_url"],
        "token": signed["token"],
        "storage_path": storage_path,
        "bucket": signed["bucket"],
    }


# ── POST /{id_adjunto}/confirm ───────────────────────────────────────────────

@router.post("/{id_adjunto}/confirm")
async def confirmar_subida(
    id_reclamo: int,
    id_adjunto: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    r = await db.execute(text("""
        SELECT id_adjunto, activo FROM reclamo_adjuntos
        WHERE id_adjunto = :id AND id_reclamo = :id_r
    """), {"id": id_adjunto, "id_r": id_reclamo})
    row = r.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Adjunto no encontrado")
    if row.activo:
        return {"ok": True, "id_adjunto": id_adjunto, "ya_confirmado": True}

    await db.execute(text("""
        UPDATE reclamo_adjuntos
        SET activo = TRUE, fecha_modificacion = NOW(), id_usuario_modificacion = :uid
        WHERE id_adjunto = :id
    """), {"id": id_adjunto, "uid": current_user["id_usuario"]})
    await db.commit()
    return {"ok": True, "id_adjunto": id_adjunto}


# ── GET "" — lista con URLs firmadas ─────────────────────────────────────────

@router.get("")
async def listar_adjuntos(
    id_reclamo: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await _existe_reclamo(db, id_reclamo)
    r = await db.execute(text("""
        SELECT id_adjunto, storage_path, nombre_archivo, mime_type,
               tamano_bytes, descripcion, fecha_alta
        FROM reclamo_adjuntos
        WHERE id_reclamo = :id AND activo = TRUE
        ORDER BY fecha_alta ASC
    """), {"id": id_reclamo})
    adjuntos = []
    for row in r.fetchall():
        d = dict(row._mapping)
        if hasattr(d["fecha_alta"], "isoformat"):
            d["fecha_alta"] = d["fecha_alta"].isoformat()
        try:
            d["url"] = await storage.crear_signed_download_url(d["storage_path"])
        except HTTPException as e:
            logger.warning("No se pudo firmar URL de %s: %s", d["storage_path"], e.detail)
            d["url"] = None
        adjuntos.append(d)
    return adjuntos


# ── DELETE /{id_adjunto} — soft-delete + remove del bucket ───────────────────

@router.delete("/{id_adjunto}")
async def borrar_adjunto(
    id_reclamo: int,
    id_adjunto: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    r = await db.execute(text("""
        SELECT storage_path, activo FROM reclamo_adjuntos
        WHERE id_adjunto = :id AND id_reclamo = :id_r
    """), {"id": id_adjunto, "id_r": id_reclamo})
    row = r.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Adjunto no encontrado")

    await db.execute(text("""
        UPDATE reclamo_adjuntos
        SET activo = FALSE, fecha_modificacion = NOW(), id_usuario_modificacion = :uid
        WHERE id_adjunto = :id
    """), {"id": id_adjunto, "uid": current_user["id_usuario"]})
    await db.commit()

    # Best-effort delete del binario
    try:
        await storage.borrar_objeto(row.storage_path)
    except Exception as e:
        logger.warning("No se pudo borrar %s del bucket: %s", row.storage_path, e)

    return {"ok": True, "id_adjunto": id_adjunto}
