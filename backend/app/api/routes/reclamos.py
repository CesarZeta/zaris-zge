"""
ZARIS API — Endpoints del módulo Reclamos.
Prefijo: /api/v1/reclamos/
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user

router = APIRouter(prefix="/api/v1/reclamos", tags=["Reclamos"])
logger = logging.getLogger("zaris.reclamos")


# ── GET /reclamos — listar con filtros ───────────────────────────────────────

@router.get("")
async def listar_reclamos(
    estado: Optional[str] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    texto: Optional[str] = Query(None, description="Busca en descripción o nro_reclamo"),
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

    sql = text(f"""
        SELECT
            r.id_reclamo, r.nro_reclamo, r.prioridad, r.estado,
            r.descripcion, r.domicilio_reclamo, r.observaciones,
            r.fecha_alta, r.fecha_modificacion,
            r.id_ciudadano, c.nombre AS ciudadano_nombre, c.apellido AS ciudadano_apellido, c.doc_nro,
            r.id_tipo_reclamo, tr.nombre AS tipo_nombre,
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
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    def _row(r):
        d = dict(r._mapping)
        for k, v in d.items():
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        return d

    return [_row(r) for r in rows]


# ── GET /reclamos/stats — contadores por estado ──────────────────────────────

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
    rows = result.fetchall()
    return {r.estado: r.total for r in rows}


# ── GET /reclamos/{id} — detalle con historial ────────────────────────────────

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
            r.id_ciudadano, c.nombre AS ciudadano_nombre, c.apellido AS ciudadano_apellido,
            c.doc_nro, c.cuil, c.telefono, c.email AS ciudadano_email,
            r.id_tipo_reclamo, tr.nombre AS tipo_nombre,
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

    d = dict(row._mapping)
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()

    # Historial
    hist_result = await db.execute(text("""
        SELECT h.id_historial, h.accion, h.estado_anterior, h.estado_nuevo,
               h.nota, h.fecha_alta,
               COALESCE(u.nombre, 'Sistema') AS usuario_nombre
        FROM reclamo_historial h
        LEFT JOIN usuarios u ON u.id_usuario = h.id_usuario_alta
        WHERE h.id_reclamo = :id
        ORDER BY h.fecha_alta ASC
    """), {"id": id_reclamo})
    hist_rows = hist_result.fetchall()

    def _hist(r):
        dh = dict(r._mapping)
        for k, v in dh.items():
            if hasattr(v, "isoformat"):
                dh[k] = v.isoformat()
        return dh

    d["historial"] = [_hist(h) for h in hist_rows]
    return d


# ── POST /reclamos — crear reclamo ───────────────────────────────────────────

@router.post("", status_code=201)
async def crear_reclamo(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    required = ["id_ciudadano", "descripcion"]
    for f in required:
        if not body.get(f):
            raise HTTPException(status_code=422, detail=f"Campo requerido: {f}")

    data = {
        "id_ciudadano":    body["id_ciudadano"],
        "id_tipo_reclamo": body.get("id_tipo_reclamo"),
        "id_area":         body.get("id_area"),
        "descripcion":     body["descripcion"],
        "domicilio_reclamo": body.get("domicilio_reclamo", ""),
        "prioridad":       body.get("prioridad", "Media"),
        "estado":          "Ingresado",
        "observaciones":   body.get("observaciones", ""),
        "id_usuario_alta": current_user["id_usuario"],
    }

    try:
        result = await db.execute(text("""
            INSERT INTO reclamos
                (id_ciudadano, id_tipo_reclamo, id_area, descripcion, domicilio_reclamo,
                 prioridad, estado, observaciones, activo, fecha_alta, fecha_modificacion,
                 id_usuario_alta, id_usuario_modificacion)
            VALUES
                (:id_ciudadano, :id_tipo_reclamo, :id_area, :descripcion, :domicilio_reclamo,
                 :prioridad, :estado, :observaciones, TRUE, NOW(), NOW(),
                 :id_usuario_alta, :id_usuario_alta)
            RETURNING id_reclamo, nro_reclamo
        """), data)
        await db.commit()
        row = result.fetchone()
        id_reclamo = row.id_reclamo
        nro_reclamo = row.nro_reclamo or f"REC-{id_reclamo}"

        # Insertar entrada inicial en historial
        await db.execute(text("""
            INSERT INTO reclamo_historial
                (id_reclamo, accion, estado_anterior, estado_nuevo, nota, fecha_alta, id_usuario_alta)
            VALUES (:id_r, 'Ingresado', NULL, 'Ingresado', 'Reclamo registrado', NOW(), :uid)
        """), {"id_r": id_reclamo, "uid": current_user["id_usuario"]})
        await db.commit()

        return {"id_reclamo": id_reclamo, "nro_reclamo": nro_reclamo, "estado": "Ingresado"}
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

    # Validar contra tabla estado_reclamo; fallback a lista hardcoded si la tabla está vacía
    r_estados = await db.execute(text(
        "SELECT nombre FROM estado_reclamo WHERE activo = TRUE"
    ))
    estados_rows = r_estados.fetchall()
    if estados_rows:
        estados_validos = {row.nombre for row in estados_rows}
    else:
        estados_validos = {"Ingresado", "En revisión", "En gestión", "Resuelto", "Rechazado", "Cerrado"}

    if nuevo_estado not in estados_validos:
        raise HTTPException(status_code=422, detail=f"Estado inválido: {nuevo_estado}")

    # Obtener estado actual
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
    """), {
        "estado": nuevo_estado, "id": id_reclamo,
        "obs": nota or None,
        "uid": current_user["id_usuario"],
    })

    await db.execute(text("""
        INSERT INTO reclamo_historial
            (id_reclamo, accion, estado_anterior, estado_nuevo, nota, fecha_alta, id_usuario_alta)
        VALUES (:id_r, :accion, :ant, :nuevo, :nota, NOW(), :uid)
    """), {
        "id_r": id_reclamo,
        "accion": f"Cambio de estado a {nuevo_estado}",
        "ant": estado_anterior,
        "nuevo": nuevo_estado,
        "nota": nota,
        "uid": current_user["id_usuario"],
    })

    await db.commit()
    return {"ok": True, "id_reclamo": id_reclamo, "estado": nuevo_estado}


# ── GET /reclamos/catalogo/areas — áreas disponibles para filtros ─────────────

@router.get("/catalogo/areas")
async def catalogo_areas(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text(
        "SELECT id_area, nombre FROM area WHERE activo = TRUE ORDER BY nombre"
    ))
    return [dict(r._mapping) for r in result.fetchall()]


# ── GET /reclamos/catalogo/tipos — tipos de reclamo con su área ───────────────

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
        SELECT tr.id_tipo_reclamo, tr.nombre, tr.sla_dias,
               tr.id_area, a.nombre AS area_nombre
        FROM tipo_reclamo tr
        LEFT JOIN area a ON a.id_area = tr.id_area
        WHERE {cond}
        ORDER BY tr.nombre
    """), params)
    return [dict(r._mapping) for r in result.fetchall()]
