"""
ZARIS API - AVISOS del vecino logueado (bandeja "Alertas" de la App Vecinos).

Bajo /api/v1/publico/avisos. Guard get_current_ciudadano (JWT scope 'publico').

Mig 99 (`ciudadano_aviso`). Los avisos los escribe el backend en los hooks
post-commit de negocio (services/push.py → services/avisos.py) — el mismo
punto donde sale el push, asi la bandeja y la notificacion nunca divergen. Este
router SOLO lee y marca leido: el vecino no crea ni borra avisos.

Todo scopeado al id_ciudadano del token. Un aviso ajeno → 404 identico al
"no existe" (no filtra terceros, mismo criterio que publico_reclamos).
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_ciudadano
from app.core.database import get_db

logger = logging.getLogger("zaris.publico_avisos")

router = APIRouter(prefix="/api/v1/publico/avisos", tags=["publico-avisos"])


def _aviso_out(r) -> dict:
    d = dict(r)
    return {
        "id_aviso": d["id_ciudadano_aviso"],
        "tipo": d["tipo"],
        "titulo": d["titulo"],
        "mensaje": d["mensaje"],
        "url": d["url_destino"],
        "recurso_tipo": d["recurso_tipo"],
        "recurso_id": d["recurso_id"],
        "leido": bool(d["leido"]),
        "leido_en": d["leido_en"].isoformat() if d["leido_en"] else None,
        "fecha": d["fecha_alta"].isoformat() if d["fecha_alta"] else None,
    }


async def _contadores(db: AsyncSession, id_c: int) -> tuple[int, int]:
    row = (await db.execute(text("""
        SELECT COUNT(*) FILTER (WHERE leido = FALSE) AS no_leidos,
               COUNT(*)                              AS total
          FROM ciudadano_aviso
         WHERE id_ciudadano = :c AND activo = TRUE
    """), {"c": id_c})).fetchone()
    return int(row.no_leidos or 0), int(row.total or 0)


@router.get("")
async def listar_mis_avisos(
    solo_no_leidos: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
):
    """Bandeja del vecino, del mas nuevo al mas viejo. Devuelve ademas los
    contadores para el badge (`no_leidos`) y el paginado (`total`)."""
    id_c = current["id_ciudadano"]
    cond = "id_ciudadano = :c AND activo = TRUE" + (" AND leido = FALSE" if solo_no_leidos else "")
    rows = (await db.execute(text(f"""
        SELECT id_ciudadano_aviso, tipo, titulo, mensaje, url_destino,
               recurso_tipo, recurso_id, leido, leido_en, fecha_alta
          FROM ciudadano_aviso
         WHERE {cond}
         ORDER BY fecha_alta DESC, id_ciudadano_aviso DESC
         LIMIT :lim OFFSET :off
    """), {"c": id_c, "lim": limit, "off": offset})).mappings().all()
    no_leidos, total = await _contadores(db, id_c)
    return {"avisos": [_aviso_out(r) for r in rows], "no_leidos": no_leidos, "total": total}


@router.post("/leer-todos")
async def marcar_todos_leidos(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
):
    """Marca leidos TODOS los avisos pendientes del vecino. Idempotente."""
    res = await db.execute(text("""
        UPDATE ciudadano_aviso
           SET leido = TRUE, leido_en = NOW(), fecha_modificacion = NOW()
         WHERE id_ciudadano = :c AND activo = TRUE AND leido = FALSE
    """), {"c": current["id_ciudadano"]})
    await db.commit()
    return {"ok": True, "marcados": int(res.rowcount or 0), "no_leidos": 0}


@router.patch("/{id_aviso}/leer",
              responses={404: {"description": "El aviso no existe o no es del vecino"}})
async def marcar_leido(
    id_aviso: int,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
):
    """Marca UN aviso como leido. Idempotente (repetir no falla).
    404 si no existe o pertenece a otro ciudadano (mismo cuerpo)."""
    id_c = current["id_ciudadano"]
    row = (await db.execute(text("""
        UPDATE ciudadano_aviso
           SET leido = TRUE,
               leido_en = COALESCE(leido_en, NOW()),
               fecha_modificacion = NOW()
         WHERE id_ciudadano_aviso = :id AND id_ciudadano = :c AND activo = TRUE
        RETURNING id_ciudadano_aviso, leido_en
    """), {"id": id_aviso, "c": id_c})).fetchone()
    if not row:
        await db.rollback()
        raise HTTPException(404, "Aviso no encontrado")
    await db.commit()
    no_leidos, _ = await _contadores(db, id_c)
    return {
        "ok": True,
        "id_aviso": int(row.id_ciudadano_aviso),
        "leido": True,
        "leido_en": row.leido_en.isoformat() if row.leido_en else None,
        "no_leidos": no_leidos,
    }
