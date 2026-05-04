"""
ZARIS API — Endpoints del módulo Reclamos (v1.2).
Prefijo: /api/v1/reclamos/
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user

router = APIRouter(prefix="/api/v1/reclamos", tags=["Reclamos"])
logger = logging.getLogger("zaris.reclamos")

ESTADOS_VALIDOS = {"Sin asignar", "En gestión", "En espera", "En auditoría", "Resuelto", "Cancelado"}


def _to_dict(row) -> dict:
    d = dict(row._mapping)
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


async def _estados_desde_db(db: AsyncSession) -> set:
    r = await db.execute(text("SELECT nombre FROM estado_reclamo WHERE activo = TRUE"))
    rows = r.fetchall()
    return {row.nombre for row in rows} if rows else ESTADOS_VALIDOS


async def _insertar_historial(db: AsyncSession, id_reclamo: int, accion: str,
                               estado_anterior: Optional[str], estado_nuevo: Optional[str],
                               nota: str, id_usuario: int):
    await db.execute(text("""
        INSERT INTO reclamo_historial
            (id_reclamo, accion, estado_anterior, estado_nuevo, nota, fecha_alta, id_usuario_alta)
        VALUES (:id_r, :accion, :ant, :nuevo, :nota, NOW(), :uid)
    """), {
        "id_r": id_reclamo, "accion": accion,
        "ant": estado_anterior, "nuevo": estado_nuevo,
        "nota": nota, "uid": id_usuario,
    })


# ── GET /reclamos/stats ──────────────────────────────────────────────────────

@router.get("/stats")
async def stats_reclamos(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT estado, COUNT(*) AS total
        FROM reclamos
        WHERE activo = TRUE
        GROUP BY estado
    """))
    return {r.estado: r.total for r in result.fetchall()}


# ── GET /reclamos/catalogo/areas ─────────────────────────────────────────────

@router.get("/catalogo/areas")
async def catalogo_areas(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text(
        "SELECT id_area, nombre FROM area WHERE activo = TRUE ORDER BY nombre"
    ))
    return [dict(r._mapping) for r in result.fetchall()]


# ── GET /reclamos/catalogo/tipos ─────────────────────────────────────────────

@router.get("/catalogo/tipos")
async def catalogo_tipos(
    id_area: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    cond = "tr.activo = TRUE"
    params = {}
    if id_area:
        cond += " AND tr.id_area = :id_area"
        params["id_area"] = id_area

    result = await db.execute(text(f"""
        SELECT tr.id_tipo_reclamo, tr.nombre, tr.sla_dias, tr.audit,
               tr.id_area, a.nombre AS area_nombre,
               tr.id_subarea, s.nombre AS subarea_nombre
        FROM tipo_reclamo tr
        LEFT JOIN area a ON a.id_area = tr.id_area
        LEFT JOIN subarea s ON s.id_subarea = tr.id_subarea
        WHERE {cond}
        ORDER BY tr.nombre
    """), params)
    return [dict(r._mapping) for r in result.fetchall()]


# ── GET /reclamos — listar con filtros ───────────────────────────────────────

@router.get("")
async def listar_reclamos(
    estado: Optional[str] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    texto: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    conds = ["r.activo = TRUE"]
    params: dict = {}

    if estado:
        conds.append("r.estado = :estado")
        params["estado"] = estado
    if id_area:
        conds.append("r.id_area = :id_area")
        params["id_area"] = id_area
    if prioridad:
        conds.append("r.prioridad = :prioridad")
        params["prioridad"] = prioridad
    if texto:
        conds.append("(r.descripcion ILIKE :txt OR r.nro_reclamo ILIKE :txt OR c.nombre ILIKE :txt OR c.apellido ILIKE :txt OR c.doc_nro ILIKE :txt)")
        params["txt"] = f"%{texto}%"

    where = " AND ".join(conds)
    params["limit"] = limit
    params["offset"] = offset

    result = await db.execute(text(f"""
        SELECT
            r.id_reclamo, r.nro_reclamo, r.prioridad, r.estado,
            r.descripcion, r.domicilio_reclamo, r.observaciones,
            r.fecha_alta, r.fecha_modificacion,
            r.id_reclamo_padre,
            r.id_ciudadano, c.nombre AS ciudadano_nombre, c.apellido AS ciudadano_apellido, c.doc_nro,
            r.id_tipo_reclamo, tr.nombre AS tipo_nombre, tr.sla_dias, tr.audit AS tipo_audit,
            r.id_area, a.nombre AS area_nombre,
            r.id_agente_asignado,
            COALESCE(u.nombre, '—') AS agente_nombre
        FROM reclamos r
        LEFT JOIN ciudadanos c ON c.id_ciudadano = r.id_ciudadano
        LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
        LEFT JOIN area a ON a.id_area = r.id_area
        LEFT JOIN usuarios u ON u.id_usuario = r.id_agente_asignado
        WHERE {where}
        ORDER BY r.fecha_alta DESC
        LIMIT :limit OFFSET :offset
    """), params)

    return [_to_dict(r) for r in result.fetchall()]


# ── GET /reclamos/{id} — detalle con historial y OTs ─────────────────────────

@router.get("/{id_reclamo}")
async def obtener_reclamo(
    id_reclamo: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT
            r.id_reclamo, r.nro_reclamo, r.prioridad, r.estado,
            r.descripcion, r.domicilio_reclamo, r.observaciones,
            r.fecha_alta, r.fecha_modificacion,
            r.id_reclamo_padre,
            r.id_ciudadano, c.nombre AS ciudadano_nombre, c.apellido AS ciudadano_apellido,
            c.doc_nro, c.cuil, c.telefono, c.email AS ciudadano_email,
            r.id_tipo_reclamo, tr.nombre AS tipo_nombre, tr.sla_dias, tr.audit AS tipo_audit,
            r.id_area, a.nombre AS area_nombre,
            r.id_agente_asignado,
            COALESCE(u.nombre, '—') AS agente_nombre
        FROM reclamos r
        LEFT JOIN ciudadanos c ON c.id_ciudadano = r.id_ciudadano
        LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
        LEFT JOIN area a ON a.id_area = r.id_area
        LEFT JOIN usuarios u ON u.id_usuario = r.id_agente_asignado
        WHERE r.id_reclamo = :id AND r.activo = TRUE
    """), {"id": id_reclamo})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Reclamo {id_reclamo} no encontrado")

    d = _to_dict(row)

    hist_result = await db.execute(text("""
        SELECT h.id_historial, h.accion, h.estado_anterior, h.estado_nuevo,
               h.nota, h.fecha_alta,
               COALESCE(u.nombre, 'Sistema') AS usuario_nombre
        FROM reclamo_historial h
        LEFT JOIN usuarios u ON u.id_usuario = h.id_usuario_alta
        WHERE h.id_reclamo = :id
        ORDER BY h.fecha_alta ASC
    """), {"id": id_reclamo})
    d["historial"] = [_to_dict(h) for h in hist_result.fetchall()]

    # OTs activas del reclamo
    ot_result = await db.execute(text("""
        SELECT ot.id_ot, ot.nro_ot, ot.es_auditoria, ot.resultado_auditoria,
               ot.fecha_creacion, ot.fecha_cierre, ot.observaciones,
               eot.nombre AS estado_nombre, eot.color AS estado_color,
               ag.nombre AS agente_nombre, ag.apellido AS agente_apellido,
               eq.nombre AS equipo_nombre
        FROM ordenes_trabajo ot
        JOIN estado_ot eot ON eot.id_estado_ot = ot.id_estado
        LEFT JOIN agentes ag ON ag.id_agente = ot.id_agente
        LEFT JOIN equipos eq ON eq.id_equipo = ot.id_equipo
        WHERE ot.id_reclamo = :id AND ot.activo = TRUE
        ORDER BY ot.fecha_creacion ASC
    """), {"id": id_reclamo})
    d["ordenes_trabajo"] = [_to_dict(r) for r in ot_result.fetchall()]

    # Subreclamos (hijos)
    sub_result = await db.execute(text("""
        SELECT id_reclamo, nro_reclamo, estado, descripcion, fecha_alta
        FROM reclamos
        WHERE id_reclamo_padre = :id AND activo = TRUE
        ORDER BY fecha_alta ASC
    """), {"id": id_reclamo})
    d["subreclamos"] = [_to_dict(r) for r in sub_result.fetchall()]

    return d


# ── POST /reclamos — crear reclamo ───────────────────────────────────────────

@router.post("", status_code=201)
async def crear_reclamo(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    for f in ["id_ciudadano", "descripcion"]:
        if not body.get(f):
            raise HTTPException(status_code=422, detail=f"Campo requerido: {f}")

    data = {
        "id_ciudadano":     body["id_ciudadano"],
        "id_tipo_reclamo":  body.get("id_tipo_reclamo"),
        "id_area":          body.get("id_area"),
        "descripcion":      body["descripcion"],
        "domicilio_reclamo": body.get("domicilio_reclamo", ""),
        "prioridad":        body.get("prioridad", "Media"),
        "observaciones":    body.get("observaciones", ""),
        "id_usuario_alta":  current_user["id_usuario"],
    }

    try:
        result = await db.execute(text("""
            INSERT INTO reclamos
                (id_ciudadano, id_tipo_reclamo, id_area, descripcion, domicilio_reclamo,
                 prioridad, estado, observaciones, activo, fecha_alta, fecha_modificacion,
                 id_usuario_alta, id_usuario_modificacion)
            VALUES
                (:id_ciudadano, :id_tipo_reclamo, :id_area, :descripcion, :domicilio_reclamo,
                 :prioridad, 'Sin asignar', :observaciones, TRUE, NOW(), NOW(),
                 :id_usuario_alta, :id_usuario_alta)
            RETURNING id_reclamo, nro_reclamo
        """), data)
        await db.commit()
        row = result.fetchone()
        id_reclamo = row.id_reclamo
        nro_reclamo = row.nro_reclamo or f"REC-{id_reclamo}"

        await _insertar_historial(db, id_reclamo, "Reclamo ingresado",
                                   None, "Sin asignar", "Reclamo registrado",
                                   current_user["id_usuario"])
        await db.commit()

        return {"id_reclamo": id_reclamo, "nro_reclamo": nro_reclamo, "estado": "Sin asignar"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Error al crear reclamo: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


# ── PUT /reclamos/{id}/estado — cambiar estado ───────────────────────────────

@router.put("/{id_reclamo}/estado")
async def cambiar_estado(
    id_reclamo: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    nuevo_estado = body.get("estado")
    if not nuevo_estado:
        raise HTTPException(status_code=422, detail="Campo 'estado' requerido")

    estados_validos = await _estados_desde_db(db)
    if nuevo_estado not in estados_validos:
        raise HTTPException(status_code=422, detail=f"Estado inválido: {nuevo_estado}")

    r = await db.execute(text(
        "SELECT estado FROM reclamos WHERE id_reclamo = :id AND activo = TRUE"
    ), {"id": id_reclamo})
    row = r.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Reclamo {id_reclamo} no encontrado")

    estado_anterior = row.estado
    nota = body.get("nota", "")

    await db.execute(text("""
        UPDATE reclamos
        SET estado = :estado, fecha_modificacion = NOW(),
            observaciones = COALESCE(:obs, observaciones),
            id_usuario_modificacion = :uid
        WHERE id_reclamo = :id
    """), {"estado": nuevo_estado, "id": id_reclamo, "obs": nota or None,
           "uid": current_user["id_usuario"]})

    await _insertar_historial(db, id_reclamo, f"Cambio de estado a {nuevo_estado}",
                               estado_anterior, nuevo_estado, nota,
                               current_user["id_usuario"])
    await db.commit()
    return {"ok": True, "id_reclamo": id_reclamo, "estado": nuevo_estado}


# ── PUT /reclamos/{id}/cancelar — cancelar con cascade a OTs ─────────────────

@router.put("/{id_reclamo}/cancelar")
async def cancelar_reclamo(
    id_reclamo: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    motivo = body.get("motivo", "").strip()
    if not motivo:
        raise HTTPException(status_code=422, detail="Campo 'motivo' requerido")

    r = await db.execute(text(
        "SELECT estado FROM reclamos WHERE id_reclamo = :id AND activo = TRUE"
    ), {"id": id_reclamo})
    row = r.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Reclamo {id_reclamo} no encontrado")
    if row.estado == "Cancelado":
        raise HTTPException(status_code=422, detail="El reclamo ya está cancelado")

    estado_anterior = row.estado

    # Cancelar OTs activas en cascada
    estado_cancelada = await db.execute(text(
        "SELECT id_estado_ot FROM estado_ot WHERE nombre = 'Cancelada' AND activo = TRUE"
    ))
    fila_estado = estado_cancelada.fetchone()
    if not fila_estado:
        raise HTTPException(status_code=500, detail="Estado 'Cancelada' de OT no encontrado")
    id_estado_cancelada = fila_estado.id_estado_ot

    await db.execute(text("""
        UPDATE ordenes_trabajo
        SET id_estado = :id_est, fecha_modificacion = NOW(),
            fecha_cierre = NOW(), id_usuario_modificacion = :uid
        WHERE id_reclamo = :id_r AND activo = TRUE
          AND id_estado IN (
              SELECT id_estado_ot FROM estado_ot
              WHERE nombre IN ('En gestión','En espera','Pendiente') AND activo = TRUE
          )
    """), {"id_est": id_estado_cancelada, "id_r": id_reclamo,
           "uid": current_user["id_usuario"]})

    await db.execute(text("""
        UPDATE reclamos
        SET estado = 'Cancelado', fecha_modificacion = NOW(),
            observaciones = :motivo, id_usuario_modificacion = :uid
        WHERE id_reclamo = :id
    """), {"motivo": motivo, "id": id_reclamo, "uid": current_user["id_usuario"]})

    await _insertar_historial(db, id_reclamo, "Reclamo cancelado",
                               estado_anterior, "Cancelado", motivo,
                               current_user["id_usuario"])
    await db.commit()
    return {"ok": True, "id_reclamo": id_reclamo, "estado": "Cancelado"}


# ── POST /reclamos/{id}/subreclamo — crear subreclamo (nivel 1) ──────────────

@router.post("/{id_reclamo}/subreclamo", status_code=201)
async def crear_subreclamo(
    id_reclamo: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # Validar que el padre existe y no es él mismo un subreclamo
    r = await db.execute(text("""
        SELECT id_reclamo, id_ciudadano, id_reclamo_padre, estado
        FROM reclamos WHERE id_reclamo = :id AND activo = TRUE
    """), {"id": id_reclamo})
    padre = r.fetchone()
    if not padre:
        raise HTTPException(status_code=404, detail=f"Reclamo {id_reclamo} no encontrado")
    if padre.id_reclamo_padre is not None:
        raise HTTPException(status_code=422, detail="No se permite anidar subreclamos (el padre ya es un subreclamo)")
    if padre.estado in ("Cancelado", "Resuelto"):
        raise HTTPException(status_code=422, detail=f"No se puede subreclamo a un reclamo en estado {padre.estado}")

    for f in ["descripcion", "id_tipo_reclamo"]:
        if not body.get(f):
            raise HTTPException(status_code=422, detail=f"Campo requerido: {f}")

    data = {
        "id_ciudadano":     body.get("id_ciudadano") or padre.id_ciudadano,
        "id_tipo_reclamo":  body["id_tipo_reclamo"],
        "id_area":          body.get("id_area"),
        "descripcion":      body["descripcion"],
        "domicilio_reclamo": body.get("domicilio_reclamo", ""),
        "prioridad":        body.get("prioridad", "Media"),
        "observaciones":    body.get("observaciones", ""),
        "id_reclamo_padre": id_reclamo,
        "id_usuario_alta":  current_user["id_usuario"],
    }

    try:
        result = await db.execute(text("""
            INSERT INTO reclamos
                (id_ciudadano, id_tipo_reclamo, id_area, descripcion, domicilio_reclamo,
                 prioridad, estado, observaciones, id_reclamo_padre, activo,
                 fecha_alta, fecha_modificacion, id_usuario_alta, id_usuario_modificacion)
            VALUES
                (:id_ciudadano, :id_tipo_reclamo, :id_area, :descripcion, :domicilio_reclamo,
                 :prioridad, 'Sin asignar', :observaciones, :id_reclamo_padre, TRUE,
                 NOW(), NOW(), :id_usuario_alta, :id_usuario_alta)
            RETURNING id_reclamo, nro_reclamo
        """), data)
        await db.commit()
        row = result.fetchone()
        id_sub = row.id_reclamo
        nro_sub = row.nro_reclamo or f"REC-{id_sub}"

        # Insertar historial del subreclamo
        await _insertar_historial(db, id_sub, "Subreclamo ingresado",
                                   None, "Sin asignar",
                                   f"Subreclamo de {padre.id_reclamo}", current_user["id_usuario"])

        # Poner el padre En espera
        await db.execute(text("""
            UPDATE reclamos SET estado = 'En espera', fecha_modificacion = NOW(),
                id_usuario_modificacion = :uid
            WHERE id_reclamo = :id AND estado NOT IN ('Cancelado','Resuelto')
        """), {"id": id_reclamo, "uid": current_user["id_usuario"]})

        # Poner OTs activas del padre En espera
        estado_espera = await db.execute(text(
            "SELECT id_estado_ot FROM estado_ot WHERE nombre = 'En espera' AND activo = TRUE"
        ))
        fila_espera = estado_espera.fetchone()
        if fila_espera:
            await db.execute(text("""
                UPDATE ordenes_trabajo
                SET id_estado = :id_est, fecha_modificacion = NOW(), id_usuario_modificacion = :uid
                WHERE id_reclamo = :id_r AND activo = TRUE
                  AND id_estado IN (
                      SELECT id_estado_ot FROM estado_ot WHERE nombre = 'En gestión' AND activo = TRUE
                  )
            """), {"id_est": fila_espera.id_estado_ot, "id_r": id_reclamo,
                   "uid": current_user["id_usuario"]})

        await _insertar_historial(db, id_reclamo, "Reclamo en espera por subreclamo",
                                   padre.estado, "En espera",
                                   f"Se generó subreclamo {nro_sub}", current_user["id_usuario"])
        await db.commit()

        return {"id_reclamo": id_sub, "nro_reclamo": nro_sub, "id_reclamo_padre": id_reclamo}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Error al crear subreclamo: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
