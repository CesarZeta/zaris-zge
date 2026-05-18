"""
ZARIS - Endpoints de notificaciones in-app del usuario logueado.

Las notificaciones son personales: cada query/mutacion implicita el usuario del JWT.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db

router = APIRouter(prefix="/api/v1/notificaciones", tags=["notificaciones"])


@router.get("")
async def listar(
    response: Response,
    leida: bool | None = Query(None, description="True = solo leidas, False = solo no leidas, omitir = todas"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista las notificaciones del usuario logueado, mas recientes primero."""
    where = ["id_usuario = :uid", "activo = TRUE"]
    params: dict = {"uid": current_user["id_usuario"], "limit": limit, "offset": offset}
    if leida is not None:
        where.append("leida = :leida")
        params["leida"] = leida

    sql = f"""
        SELECT id_notificacion, tipo, titulo, mensaje, url_destino,
               recurso_tipo, recurso_id, leida, leida_en, fecha_alta
          FROM notificacion
         WHERE {' AND '.join(where)}
         ORDER BY fecha_alta DESC
         LIMIT :limit OFFSET :offset
    """
    rows = (await db.execute(text(sql), params)).fetchall()

    # X-Total-Count para paginacion
    where_count = ["id_usuario = :uid", "activo = TRUE"]
    params_count = {"uid": current_user["id_usuario"]}
    if leida is not None:
        where_count.append("leida = :leida")
        params_count["leida"] = leida
    total = (await db.execute(
        text(f"SELECT COUNT(*) AS c FROM notificacion WHERE {' AND '.join(where_count)}"),
        params_count,
    )).scalar_one()

    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"

    return {
        "items": [dict(r._mapping) for r in rows],
        "total": total,
    }


@router.get("/count")
async def contar_no_leidas(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Devuelve {no_leidas: N} para el badge del topbar."""
    n = (await db.execute(
        text("SELECT COUNT(*) AS c FROM notificacion WHERE id_usuario=:uid AND leida=FALSE AND activo=TRUE"),
        {"uid": current_user["id_usuario"]},
    )).scalar_one()
    return {"no_leidas": int(n)}


@router.patch("/{id_notificacion}/leer")
async def marcar_leida(
    id_notificacion: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Marca una notificacion como leida. Solo el dueño puede."""
    res = await db.execute(
        text("""
            UPDATE notificacion
               SET leida = TRUE, leida_en = NOW(), fecha_modificacion = NOW()
             WHERE id_notificacion = :id
               AND id_usuario = :uid
               AND activo = TRUE
               AND leida = FALSE
         RETURNING id_notificacion
        """),
        {"id": id_notificacion, "uid": current_user["id_usuario"]},
    )
    row = res.fetchone()
    if not row:
        # No encontrada O no es del usuario O ya estaba leida — devolver 404 sin distinguir
        raise HTTPException(404, "Notificacion no encontrada o ya leida")
    await db.commit()
    return {"id_notificacion": row.id_notificacion, "leida": True}


@router.patch("/leer-todas")
async def marcar_todas_leidas(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Marca como leidas todas las notificaciones no-leidas del usuario."""
    res = await db.execute(
        text("""
            UPDATE notificacion
               SET leida = TRUE, leida_en = NOW(), fecha_modificacion = NOW()
             WHERE id_usuario = :uid AND leida = FALSE AND activo = TRUE
        """),
        {"uid": current_user["id_usuario"]},
    )
    await db.commit()
    return {"marcadas": res.rowcount or 0}
