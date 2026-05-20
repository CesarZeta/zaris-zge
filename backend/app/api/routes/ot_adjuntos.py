"""
ZARIS API — Adjuntos de Órdenes de Trabajo (hallazgo QA Royman #4).
Prefijo: /api/v1/ot/{id_ot}/adjuntos

Evidencia del trabajo realizado. Espeja reclamo_adjuntos pero apunta a
ordenes_trabajo. Reusa app.core.storage (mismo bucket privado).

Flujo:
- POST /upload-url            → backend valida OT + permiso + crea fila pre-upload + URL firmada PUT
- POST /{id_adjunto}/confirm  → frontend confirma que subió OK (marca activo=TRUE)
- GET  ""                     → lista adjuntos con URLs firmadas GET (TTL 1h)
- DELETE /{id_adjunto}        → soft-delete + borra binario del bucket

Permisos:
- SUBIR / BORRAR: agente asignado a la OT, o nivel <= 2 (admin/supervisor).
- VER (listar): cualquier usuario autenticado (todas las mesas ven la evidencia).
"""
import logging
import re
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user
from app.core import storage

router = APIRouter(prefix="/api/v1/ot/{id_ot}/adjuntos", tags=["OT · Adjuntos"])
logger = logging.getLogger("zaris.ot_adjuntos")

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


async def _ot_id_agente(db: AsyncSession, id_ot: int) -> int:
    """Devuelve el id_agente asignado a la OT activa, o lanza 404 si no existe.
    NULL (sin asignar a un agente) se devuelve como -1 (nunca matchea un agente)."""
    r = await db.execute(text(
        "SELECT id_agente FROM ordenes_trabajo WHERE id_ot = :id AND activo = TRUE"
    ), {"id": id_ot})
    row = r.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"OT {id_ot} no encontrada")
    return row.id_agente if row.id_agente is not None else -1


async def _require_puede_gestionar(db: AsyncSession, id_ot: int, current_user: dict) -> None:
    """Permite subir/borrar evidencia si es supervisor (nivel <= 2) o el agente
    asignado a la OT. Lanza 404 si la OT no existe, 403 si no tiene permiso."""
    id_agente_ot = await _ot_id_agente(db, id_ot)
    if current_user.get("nivel_acceso", 99) <= 2:
        return
    # Operador: debe ser el agente asignado a esta OT.
    id_usuario = current_user.get("id_usuario")
    r = await db.execute(text(
        "SELECT id_agente FROM agentes WHERE id_usuario = :uid AND activo = TRUE LIMIT 1"
    ), {"uid": id_usuario})
    row = r.fetchone()
    id_agente_usuario: Optional[int] = row.id_agente if row else None
    if id_agente_usuario is None or id_agente_usuario != id_agente_ot:
        raise HTTPException(
            status_code=403,
            detail="Solo el agente asignado a la OT o un supervisor pueden gestionar adjuntos.",
        )


async def _existe_ot(db: AsyncSession, id_ot: int) -> None:
    r = await db.execute(text(
        "SELECT 1 FROM ordenes_trabajo WHERE id_ot = :id AND activo = TRUE"
    ), {"id": id_ot})
    if not r.fetchone():
        raise HTTPException(status_code=404, detail=f"OT {id_ot} no encontrada")


# ── POST /upload-url ─────────────────────────────────────────────────────────

@router.post("/upload-url", status_code=201)
async def crear_upload_url(
    id_ot: int,
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

    await _require_puede_gestionar(db, id_ot, current_user)

    ext = EXT_POR_MIME.get(mime_type, "bin")
    storage_path = f"ot/{id_ot}/{uuid.uuid4()}.{ext}"

    signed = await storage.crear_signed_upload_url(storage_path)

    result = await db.execute(text("""
        INSERT INTO ot_adjuntos
            (id_ot, storage_bucket, storage_path, nombre_archivo,
             mime_type, tamano_bytes, descripcion, activo,
             fecha_alta, fecha_modificacion, id_usuario_alta, id_usuario_modificacion)
        VALUES
            (:id_ot, :bucket, :path, :nombre, :mime, :size, :desc, FALSE,
             NOW(), NOW(), :uid, :uid)
        RETURNING id_adjunto
    """), {
        "id_ot": id_ot, "bucket": signed["bucket"], "path": storage_path,
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
    id_ot: int,
    id_adjunto: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await _require_puede_gestionar(db, id_ot, current_user)
    r = await db.execute(text("""
        SELECT id_adjunto, activo FROM ot_adjuntos
        WHERE id_adjunto = :id AND id_ot = :id_ot
    """), {"id": id_adjunto, "id_ot": id_ot})
    row = r.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Adjunto no encontrado")
    if row.activo:
        return {"ok": True, "id_adjunto": id_adjunto, "ya_confirmado": True}

    await db.execute(text("""
        UPDATE ot_adjuntos
        SET activo = TRUE, fecha_modificacion = NOW(), id_usuario_modificacion = :uid
        WHERE id_adjunto = :id
    """), {"id": id_adjunto, "uid": current_user["id_usuario"]})
    await db.commit()
    return {"ok": True, "id_adjunto": id_adjunto}


# ── GET "" — lista con URLs firmadas ─────────────────────────────────────────

@router.get("")
async def listar_adjuntos(
    id_ot: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await _existe_ot(db, id_ot)
    r = await db.execute(text("""
        SELECT id_adjunto, storage_path, nombre_archivo, mime_type,
               tamano_bytes, descripcion, fecha_alta
        FROM ot_adjuntos
        WHERE id_ot = :id AND activo = TRUE
        ORDER BY fecha_alta ASC
    """), {"id": id_ot})
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
    id_ot: int,
    id_adjunto: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await _require_puede_gestionar(db, id_ot, current_user)
    r = await db.execute(text("""
        SELECT storage_path, activo FROM ot_adjuntos
        WHERE id_adjunto = :id AND id_ot = :id_ot
    """), {"id": id_adjunto, "id_ot": id_ot})
    row = r.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Adjunto no encontrado")

    await db.execute(text("""
        UPDATE ot_adjuntos
        SET activo = FALSE, fecha_modificacion = NOW(), id_usuario_modificacion = :uid
        WHERE id_adjunto = :id
    """), {"id": id_adjunto, "uid": current_user["id_usuario"]})
    await db.commit()

    try:
        await storage.borrar_objeto(row.storage_path)
    except Exception as e:
        logger.warning("No se pudo borrar %s del bucket: %s", row.storage_path, e)

    return {"ok": True, "id_adjunto": id_adjunto}
