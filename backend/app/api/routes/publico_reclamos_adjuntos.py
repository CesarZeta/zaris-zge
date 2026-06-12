"""
ZARIS API — Adjuntos de reclamos del VECINO (App Vecinos, scope publico).
Prefijo: /api/v1/publico/reclamos/{id_reclamo}/adjuntos

Espejo del flujo de reclamo_adjuntos.py (§26) pero con guard get_current_ciudadano:
- POST /upload-url           → valida que el reclamo sea DEL vecino + crea fila pre-upload + URL firmada PUT
- POST /{id_adjunto}/confirm → marca activo=TRUE tras la subida
- GET  ""                    → lista adjuntos propios con URLs firmadas GET (TTL 1h)

Reglas propias del canal público (no aplican al backoffice):
- Guard duro de pertenencia: reclamo ajeno → 404 con el mismo cuerpo que "no existe"
  (no se filtra existencia de reclamos de terceros).
- Máx. ADJUNTOS_MAX_POR_RECLAMO fotos activas por reclamo (anti-abuso).
- Solo sobre reclamos en estado NO final (a un Resuelto/Cancelado no se le suman fotos).
- Sin DELETE en v1: el vecino no edita lo enviado (paridad con no poder cancelar).
- id_usuario_alta = NULL (el vecino no es un `usuarios` interno).
- Rate-limit por IP con clave prefijada "adjpub:" para no compartir bucket con los
  otros endpoints públicos (el rate_limit in-memory clavea por string).
"""
import logging
import re
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_ciudadano
from app.core import storage
from app.middleware.rate_limit import check_rate_limit
from app.utils.request_helpers import get_real_ip

router = APIRouter(
    prefix="/api/v1/publico/reclamos/{id_reclamo}/adjuntos",
    tags=["publico-reclamos-adjuntos"],
)
logger = logging.getLogger("zaris.publico_adjuntos")

MIME_PERMITIDOS = {
    "image/jpeg", "image/png", "image/webp",
    "image/gif", "image/heic", "image/heif",
}
EXT_POR_MIME = {
    "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp",
    "image/gif": "gif", "image/heic": "heic", "image/heif": "heif",
}
MAX_BYTES = 10 * 1024 * 1024  # 10 MB (= límite del bucket reclamos-adjuntos)
ADJUNTOS_MAX_POR_RECLAMO = 5
ESTADOS_FINALES = ("Resuelto", "Cancelado")


def _safe_filename(nombre: str) -> str:
    nombre = (nombre or "").strip() or "archivo"
    return re.sub(r"[^\w\.\-]+", "_", nombre)[:120]


async def _reclamo_propio(db: AsyncSession, id_reclamo: int, id_ciudadano: int):
    """Devuelve la fila si el reclamo existe, está activo y es DEL vecino.
    404 con cuerpo genérico en cualquier otro caso (no filtrar terceros)."""
    r = await db.execute(text("""
        SELECT id_reclamo, estado FROM reclamos
        WHERE id_reclamo = :id AND activo = TRUE AND id_ciudadano = :id_c
    """), {"id": id_reclamo, "id_c": id_ciudadano})
    row = r.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Reclamo no encontrado")
    return row


# ── POST /upload-url ─────────────────────────────────────────────────────────

@router.post("/upload-url", status_code=201)
async def crear_upload_url_publico(
    id_reclamo: int,
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
):
    # 20/min por IP: subir 5 fotos son 10 POSTs (upload-url + confirm); 5/min cortaría
    # el flujo legítimo. El cap real anti-abuso es ADJUNTOS_MAX_POR_RECLAMO.
    check_rate_limit(f"adjpub:{get_real_ip(request)}", max_requests=20, window_seconds=60)

    nombre_archivo = _safe_filename(body.get("nombre_archivo", ""))
    mime_type = (body.get("mime_type") or "").lower()
    tamano = int(body.get("tamano_bytes") or 0)

    if mime_type not in MIME_PERMITIDOS:
        raise HTTPException(status_code=422,
            detail=f"Tipo de archivo no permitido: {mime_type or 'sin tipo'}. Solo imágenes.")
    if tamano <= 0 or tamano > MAX_BYTES:
        raise HTTPException(status_code=422,
            detail=f"Tamaño inválido (máx {MAX_BYTES // (1024*1024)} MB)")

    reclamo = await _reclamo_propio(db, id_reclamo, current["id_ciudadano"])
    if reclamo.estado in ESTADOS_FINALES:
        raise HTTPException(status_code=422,
            detail="El reclamo ya está cerrado; no admite nuevas fotos")

    r_count = await db.execute(text("""
        SELECT COUNT(*) FROM reclamo_adjuntos
        WHERE id_reclamo = :id AND activo = TRUE
    """), {"id": id_reclamo})
    if (r_count.scalar_one() or 0) >= ADJUNTOS_MAX_POR_RECLAMO:
        raise HTTPException(status_code=422,
            detail=f"Máximo {ADJUNTOS_MAX_POR_RECLAMO} fotos por reclamo")

    ext = EXT_POR_MIME.get(mime_type, "bin")
    storage_path = f"reclamos/{id_reclamo}/{uuid.uuid4()}.{ext}"

    signed = await storage.crear_signed_upload_url(storage_path)

    # Fila pre-upload (activo=FALSE hasta el confirm). id_usuario_alta NULL: vecino.
    result = await db.execute(text("""
        INSERT INTO reclamo_adjuntos
            (id_reclamo, storage_bucket, storage_path, nombre_archivo,
             mime_type, tamano_bytes, descripcion, activo,
             fecha_alta, fecha_modificacion, id_usuario_alta, id_usuario_modificacion)
        VALUES
            (:id_r, :bucket, :path, :nombre, :mime, :size, '', FALSE,
             NOW(), NOW(), NULL, NULL)
        RETURNING id_adjunto
    """), {
        "id_r": id_reclamo, "bucket": signed["bucket"], "path": storage_path,
        "nombre": nombre_archivo, "mime": mime_type, "size": tamano,
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
async def confirmar_subida_publico(
    id_reclamo: int,
    id_adjunto: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
):
    check_rate_limit(f"adjpub:{get_real_ip(request)}", max_requests=20, window_seconds=60)
    await _reclamo_propio(db, id_reclamo, current["id_ciudadano"])

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
        SET activo = TRUE, fecha_modificacion = NOW()
        WHERE id_adjunto = :id
    """), {"id": id_adjunto})
    await db.commit()
    return {"ok": True, "id_adjunto": id_adjunto}


# ── GET "" — lista con URLs firmadas ─────────────────────────────────────────

@router.get("")
async def listar_adjuntos_publico(
    id_reclamo: int,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
):
    await _reclamo_propio(db, id_reclamo, current["id_ciudadano"])
    r = await db.execute(text("""
        SELECT id_adjunto, storage_path, nombre_archivo, mime_type,
               tamano_bytes, fecha_alta
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
