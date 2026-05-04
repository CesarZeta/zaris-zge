"""
ZARIS API — Endpoints del módulo Órdenes de Trabajo (v1.2).
Prefijo: /api/v1/ot/

IMPORTANTE: rutas con segmentos fijos (/catalogo/*, /mesa/*) van ANTES de /{id_ot}
para que FastAPI no las interprete como path param.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user

router = APIRouter(prefix="/api/v1/ot", tags=["Órdenes de Trabajo"])
logger = logging.getLogger("zaris.ordenes_trabajo")


def _to_dict(row) -> dict:
    d = dict(row._mapping)
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


async def _id_estado_ot(db: AsyncSession, nombre: str) -> int:
    r = await db.execute(text(
        "SELECT id_estado_ot FROM estado_ot WHERE nombre = :n AND activo = TRUE"
    ), {"n": nombre})
    row = r.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail=f"Estado OT '{nombre}' no encontrado en BD")
    return row.id_estado_ot


async def _insertar_historial_reclamo(db: AsyncSession, id_reclamo: int, accion: str,
                                       estado_anterior: Optional[str], estado_nuevo: Optional[str],
                                       nota: str, id_usuario: int):
    await db.execute(text("""
        INSERT INTO reclamo_historial
            (id_reclamo, accion, estado_anterior, estado_nuevo, nota, fecha_alta, id_usuario_alta)
        VALUES (:id_r, :accion, :ant, :nuevo, :nota, NOW(), :uid)
    """), {"id_r": id_reclamo, "accion": accion, "ant": estado_anterior,
           "nuevo": estado_nuevo, "nota": nota, "uid": id_usuario})


# ── GET /ot/catalogo/estados ─────────────────────────────────────────────────

@router.get("/catalogo/estados")
async def catalogo_estados_ot(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text(
        "SELECT id_estado_ot, nombre, color, es_final FROM estado_ot WHERE activo = TRUE ORDER BY orden"
    ))
    return [dict(r._mapping) for r in result.fetchall()]


# ── GET /ot/mesa/supervisor ──────────────────────────────────────────────────

@router.get("/mesa/supervisor")
async def mesa_supervisor(
    id_subarea: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Vista del supervisor: reclamos activos (Sin asignar, En gestión, En espera, En auditoría)."""
    conds = ["r.activo = TRUE", "r.estado NOT IN ('Resuelto','Cancelado')"]
    params: dict = {}
    if id_subarea:
        conds.append("r.id_subarea = :id_subarea")
        params["id_subarea"] = id_subarea

    result = await db.execute(text(f"""
        SELECT
            r.id_reclamo, r.nro_reclamo, r.estado, r.prioridad,
            r.descripcion, r.domicilio_reclamo, r.fecha_alta,
            r.id_reclamo_padre,
            c.nombre AS ciudadano_nombre, c.apellido AS ciudadano_apellido, c.doc_nro,
            tr.nombre AS tipo_nombre, tr.sla_dias, tr.audit AS tipo_audit,
            a.nombre AS area_nombre,
            COUNT(ot.id_ot) FILTER (WHERE ot.activo = TRUE) AS cant_ots
        FROM reclamos r
        LEFT JOIN ciudadanos c ON c.id_ciudadano = r.id_ciudadano
        LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
        LEFT JOIN area a ON a.id_area = r.id_area
        LEFT JOIN ordenes_trabajo ot ON ot.id_reclamo = r.id_reclamo
        WHERE {" AND ".join(conds)}
        GROUP BY r.id_reclamo, c.nombre, c.apellido, c.doc_nro,
                 tr.nombre, tr.sla_dias, tr.audit, a.nombre
        ORDER BY
            CASE r.prioridad WHEN 'Alta' THEN 1 WHEN 'Media' THEN 2 ELSE 3 END,
            r.fecha_alta ASC
    """), params)

    return [_to_dict(row) for row in result.fetchall()]


# ── GET /ot/mesa/agente ──────────────────────────────────────────────────────

@router.get("/mesa/agente")
async def mesa_agente(
    id_agente: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """OTs en gestión, en espera o pendiente asignadas al agente o a sus equipos."""
    result = await db.execute(text("""
        SELECT
            ot.id_ot, ot.nro_ot, ot.es_auditoria,
            ot.fecha_creacion, ot.observaciones,
            eot.nombre AS estado_nombre, eot.color AS estado_color,
            r.id_reclamo, r.nro_reclamo, r.prioridad AS reclamo_prioridad,
            r.descripcion AS reclamo_descripcion,
            tr.nombre AS tipo_nombre, tr.sla_dias,
            eq.nombre AS equipo_nombre,
            ot.id_agente
        FROM ordenes_trabajo ot
        JOIN estado_ot eot ON eot.id_estado_ot = ot.id_estado
        JOIN reclamos r ON r.id_reclamo = ot.id_reclamo
        LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
        LEFT JOIN equipos eq ON eq.id_equipo = ot.id_equipo
        WHERE ot.activo = TRUE
          AND eot.nombre IN ('En gestión','En espera','Pendiente')
          AND ot.es_auditoria = FALSE
          AND (
              ot.id_agente = :id_agente
              OR (
                  ot.id_agente IS NULL
                  AND ot.id_equipo IN (
                      SELECT id_equipo FROM equipo_agentes
                      WHERE id_agente = :id_agente AND activo = TRUE
                  )
              )
          )
        ORDER BY
            CASE r.prioridad WHEN 'Alta' THEN 1 WHEN 'Media' THEN 2 ELSE 3 END,
            ot.fecha_creacion ASC
    """), {"id_agente": id_agente})

    return [_to_dict(row) for row in result.fetchall()]


# ── GET /ot/mesa/auditoria ───────────────────────────────────────────────────

@router.get("/mesa/auditoria")
async def mesa_auditoria(
    id_agente: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """OTs de auditoría disponibles para el auditor, respetando regla de subárea."""
    cfg = await db.execute(text(
        "SELECT valor FROM configuracion_general WHERE clave = 'auditor_misma_subarea_permitido'"
    ))
    cfg_row = cfg.fetchone()
    misma_subarea_ok = (cfg_row.valor.lower() == "true") if cfg_row else False

    subarea_filter = ""
    if not misma_subarea_ok:
        subarea_filter = """
            AND (r.id_subarea IS NULL OR r.id_subarea NOT IN (
                SELECT id_subarea FROM agentes WHERE id_agente = :id_agente
                UNION
                SELECT eq.id_subarea FROM equipo_agentes ea
                JOIN equipos eq ON eq.id_equipo = ea.id_equipo
                WHERE ea.id_agente = :id_agente AND ea.activo = TRUE
            ))
        """

    result = await db.execute(text(f"""
        SELECT
            ot.id_ot, ot.nro_ot, ot.fecha_creacion,
            eot.nombre AS estado_nombre, eot.color AS estado_color,
            r.id_reclamo, r.nro_reclamo, r.prioridad AS reclamo_prioridad,
            r.descripcion AS reclamo_descripcion, r.id_subarea,
            tr.nombre AS tipo_nombre,
            ot.id_agente, ag.nombre AS agente_nombre, ag.apellido AS agente_apellido
        FROM ordenes_trabajo ot
        JOIN estado_ot eot ON eot.id_estado_ot = ot.id_estado
        JOIN reclamos r ON r.id_reclamo = ot.id_reclamo
        LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
        LEFT JOIN agentes ag ON ag.id_agente = ot.id_agente
        WHERE ot.activo = TRUE
          AND ot.es_auditoria = TRUE
          AND eot.nombre NOT IN ('Terminada','Cancelada')
          AND (ot.id_agente IS NULL OR ot.id_agente = :id_agente)
          {subarea_filter}
        ORDER BY ot.fecha_creacion ASC
    """), {"id_agente": id_agente})

    return [_to_dict(row) for row in result.fetchall()]


# ── GET /ot — listar OTs con filtros ─────────────────────────────────────────

@router.get("")
async def listar_ots(
    id_reclamo: Optional[int] = Query(None),
    id_agente: Optional[int] = Query(None),
    id_equipo: Optional[int] = Query(None),
    es_auditoria: Optional[bool] = Query(None),
    estado: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    conds = ["ot.activo = TRUE"]
    params: dict = {"limit": limit, "offset": offset}

    if id_reclamo:
        conds.append("ot.id_reclamo = :id_reclamo")
        params["id_reclamo"] = id_reclamo
    if id_agente:
        conds.append("ot.id_agente = :id_agente")
        params["id_agente"] = id_agente
    if id_equipo:
        conds.append("ot.id_equipo = :id_equipo")
        params["id_equipo"] = id_equipo
    if es_auditoria is not None:
        conds.append("ot.es_auditoria = :es_audit")
        params["es_audit"] = es_auditoria
    if estado:
        conds.append("eot.nombre = :estado")
        params["estado"] = estado

    where = " AND ".join(conds)
    result = await db.execute(text(f"""
        SELECT
            ot.id_ot, ot.nro_ot, ot.es_auditoria, ot.resultado_auditoria,
            ot.observaciones, ot.observaciones_auditoria,
            ot.fecha_creacion, ot.fecha_cierre,
            eot.nombre AS estado_nombre, eot.color AS estado_color, eot.es_final,
            ot.id_reclamo, r.nro_reclamo, r.descripcion AS reclamo_descripcion,
            r.prioridad AS reclamo_prioridad,
            ot.id_agente, ag.nombre AS agente_nombre, ag.apellido AS agente_apellido,
            ot.id_equipo, eq.nombre AS equipo_nombre,
            ot.id_ot_origen,
            tr.sla_dias, tr.audit AS tipo_audit
        FROM ordenes_trabajo ot
        JOIN estado_ot eot ON eot.id_estado_ot = ot.id_estado
        JOIN reclamos r ON r.id_reclamo = ot.id_reclamo
        LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
        LEFT JOIN agentes ag ON ag.id_agente = ot.id_agente
        LEFT JOIN equipos eq ON eq.id_equipo = ot.id_equipo
        WHERE {where}
        ORDER BY ot.fecha_creacion DESC
        LIMIT :limit OFFSET :offset
    """), params)

    return [_to_dict(r) for r in result.fetchall()]


# ── GET /ot/{id} — detalle ───────────────────────────────────────────────────

@router.get("/{id_ot}")
async def obtener_ot(
    id_ot: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT
            ot.id_ot, ot.nro_ot, ot.es_auditoria, ot.resultado_auditoria,
            ot.observaciones, ot.observaciones_auditoria,
            ot.fecha_creacion, ot.fecha_cierre, ot.id_ot_origen,
            eot.nombre AS estado_nombre, eot.color AS estado_color,
            ot.id_reclamo, r.nro_reclamo, r.descripcion AS reclamo_descripcion,
            r.estado AS reclamo_estado, r.prioridad AS reclamo_prioridad,
            r.id_tipo_reclamo, tr.nombre AS tipo_nombre, tr.sla_dias, tr.audit AS tipo_audit,
            ot.id_agente, ag.nombre AS agente_nombre, ag.apellido AS agente_apellido,
            ot.id_equipo, eq.nombre AS equipo_nombre,
            ot.id_supervisor_asigna,
            us.nombre AS supervisor_nombre
        FROM ordenes_trabajo ot
        JOIN estado_ot eot ON eot.id_estado_ot = ot.id_estado
        JOIN reclamos r ON r.id_reclamo = ot.id_reclamo
        LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
        LEFT JOIN agentes ag ON ag.id_agente = ot.id_agente
        LEFT JOIN equipos eq ON eq.id_equipo = ot.id_equipo
        LEFT JOIN usuarios us ON us.id_usuario = ot.id_supervisor_asigna
        WHERE ot.id_ot = :id AND ot.activo = TRUE
    """), {"id": id_ot})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"OT {id_ot} no encontrada")
    return _to_dict(row)


# ── POST /ot — crear OT ───────────────────────────────────────────────────────

@router.post("", status_code=201)
async def crear_ot(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if not body.get("id_reclamo"):
        raise HTTPException(status_code=422, detail="Campo requerido: id_reclamo")
    if not body.get("id_agente") and not body.get("id_equipo"):
        raise HTTPException(status_code=422, detail="Se requiere id_agente o id_equipo")

    id_reclamo = body["id_reclamo"]

    r = await db.execute(text(
        "SELECT estado FROM reclamos WHERE id_reclamo = :id AND activo = TRUE"
    ), {"id": id_reclamo})
    reclamo = r.fetchone()
    if not reclamo:
        raise HTTPException(status_code=404, detail=f"Reclamo {id_reclamo} no encontrado")
    if reclamo.estado in ("Cancelado", "Resuelto"):
        raise HTTPException(status_code=422, detail=f"No se puede asignar OT a un reclamo {reclamo.estado}")

    id_estado_en_gestion = await _id_estado_ot(db, "En gestión")

    try:
        result = await db.execute(text("""
            INSERT INTO ordenes_trabajo
                (id_reclamo, id_estado, id_agente, id_equipo, es_auditoria,
                 id_supervisor_asigna, activo, fecha_alta, fecha_modificacion,
                 id_usuario_alta, id_usuario_modificacion)
            VALUES
                (:id_reclamo, :id_estado, :id_agente, :id_equipo, FALSE,
                 :id_super, TRUE, NOW(), NOW(), :id_super, :id_super)
            RETURNING id_ot, nro_ot
        """), {
            "id_reclamo": id_reclamo,
            "id_estado": id_estado_en_gestion,
            "id_agente": body.get("id_agente"),
            "id_equipo": body.get("id_equipo"),
            "id_super": current_user["id_usuario"],
        })
        await db.commit()
        row = result.fetchone()
        id_ot = row.id_ot
        nro_ot = row.nro_ot or f"OT-{id_ot}"

        estado_ant = reclamo.estado
        await db.execute(text("""
            UPDATE reclamos SET estado = 'En gestión', fecha_modificacion = NOW(),
                id_usuario_modificacion = :uid
            WHERE id_reclamo = :id AND estado NOT IN ('Cancelado','Resuelto')
        """), {"id": id_reclamo, "uid": current_user["id_usuario"]})

        await _insertar_historial_reclamo(db, id_reclamo, f"OT {nro_ot} generada",
                                           estado_ant, "En gestión",
                                           body.get("observaciones", ""),
                                           current_user["id_usuario"])
        await db.commit()

        return {"id_ot": id_ot, "nro_ot": nro_ot, "id_reclamo": id_reclamo}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Error al crear OT: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


# ── PUT /ot/{id}/tomar ────────────────────────────────────────────────────────

@router.put("/{id_ot}/tomar")
async def tomar_ot(
    id_ot: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    id_agente = body.get("id_agente")
    if not id_agente:
        raise HTTPException(status_code=422, detail="Campo requerido: id_agente")

    r = await db.execute(text(
        "SELECT id_agente, id_equipo FROM ordenes_trabajo WHERE id_ot = :id AND activo = TRUE"
    ), {"id": id_ot})
    ot = r.fetchone()
    if not ot:
        raise HTTPException(status_code=404, detail=f"OT {id_ot} no encontrada")
    if ot.id_agente is not None:
        raise HTTPException(status_code=422, detail="La OT ya tiene agente asignado")

    await db.execute(text("""
        UPDATE ordenes_trabajo
        SET id_agente = :id_agente, fecha_modificacion = NOW(), id_usuario_modificacion = :uid
        WHERE id_ot = :id
    """), {"id_agente": id_agente, "id": id_ot, "uid": current_user["id_usuario"]})
    await db.commit()
    return {"ok": True, "id_ot": id_ot, "id_agente": id_agente}


# ── PUT /ot/{id}/estado ───────────────────────────────────────────────────────

@router.put("/{id_ot}/estado")
async def cambiar_estado_ot(
    id_ot: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    nuevo_estado = body.get("estado")
    if not nuevo_estado:
        raise HTTPException(status_code=422, detail="Campo 'estado' requerido")

    r_estado = await db.execute(text(
        "SELECT id_estado_ot, es_final FROM estado_ot WHERE nombre = :n AND activo = TRUE"
    ), {"n": nuevo_estado})
    estado_row = r_estado.fetchone()
    if not estado_row:
        raise HTTPException(status_code=422, detail=f"Estado OT inválido: {nuevo_estado}")

    r = await db.execute(text("""
        SELECT ot.id_estado, eot.nombre AS estado_actual, ot.id_reclamo,
               ot.es_auditoria, r.id_tipo_reclamo, r.estado AS reclamo_estado
        FROM ordenes_trabajo ot
        JOIN estado_ot eot ON eot.id_estado_ot = ot.id_estado
        JOIN reclamos r ON r.id_reclamo = ot.id_reclamo
        WHERE ot.id_ot = :id AND ot.activo = TRUE
    """), {"id": id_ot})
    ot = r.fetchone()
    if not ot:
        raise HTTPException(status_code=404, detail=f"OT {id_ot} no encontrada")

    observaciones = body.get("observaciones", "")

    try:
        cierre_sql = ", fecha_cierre = NOW()" if nuevo_estado == "Terminada" else ""
        await db.execute(text(f"""
            UPDATE ordenes_trabajo
            SET id_estado = :id_est, fecha_modificacion = NOW(),
                observaciones = COALESCE(:obs, observaciones){cierre_sql},
                id_usuario_modificacion = :uid
            WHERE id_ot = :id
        """), {"id_est": estado_row.id_estado_ot, "obs": observaciones or None,
               "uid": current_user["id_usuario"], "id": id_ot})

        if nuevo_estado == "Terminada" and not ot.es_auditoria:
            await _post_cierre_ot_operativa(db, id_ot, ot, current_user["id_usuario"])

        await db.commit()
        return {"ok": True, "id_ot": id_ot, "estado": nuevo_estado}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Error al cambiar estado OT: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


async def _post_cierre_ot_operativa(db: AsyncSession, id_ot: int, ot, id_usuario: int):
    """Al cerrar OT operativa: si tipo_reclamo.audit → reclamo a En auditoría + OT auditoría."""
    if not ot.id_tipo_reclamo:
        await _resolver_reclamo(db, ot.id_reclamo, id_usuario)
        return

    r_tipo = await db.execute(text(
        "SELECT audit FROM tipo_reclamo WHERE id_tipo_reclamo = :id"
    ), {"id": ot.id_tipo_reclamo})
    tipo = r_tipo.fetchone()

    if tipo and tipo.audit:
        await db.execute(text("""
            UPDATE reclamos SET estado = 'En auditoría', fecha_modificacion = NOW(),
                id_usuario_modificacion = :uid
            WHERE id_reclamo = :id
        """), {"id": ot.id_reclamo, "uid": id_usuario})

        await _insertar_historial_reclamo(db, ot.id_reclamo,
                                           "OT operativa cerrada, pasa a auditoría",
                                           ot.reclamo_estado, "En auditoría",
                                           "Cierre automático por audit=true", id_usuario)

        id_estado_en_gestion = await _id_estado_ot(db, "En gestión")
        sup_row = await db.execute(text(
            "SELECT id_supervisor_asigna FROM ordenes_trabajo WHERE id_ot = :id"
        ), {"id": id_ot})
        id_super = sup_row.fetchone().id_supervisor_asigna

        await db.execute(text("""
            INSERT INTO ordenes_trabajo
                (id_reclamo, id_estado, es_auditoria, id_ot_origen, id_supervisor_asigna,
                 activo, fecha_alta, fecha_modificacion, id_usuario_alta, id_usuario_modificacion)
            VALUES (:id_r, :id_est, TRUE, :id_orig, :id_super,
                    TRUE, NOW(), NOW(), :id_super, :id_super)
        """), {"id_r": ot.id_reclamo, "id_est": id_estado_en_gestion,
               "id_orig": id_ot, "id_super": id_super})
    else:
        await _resolver_reclamo(db, ot.id_reclamo, id_usuario)


async def _resolver_reclamo(db: AsyncSession, id_reclamo: int, id_usuario: int):
    r = await db.execute(text(
        "SELECT estado FROM reclamos WHERE id_reclamo = :id"
    ), {"id": id_reclamo})
    estado_ant = r.fetchone().estado
    await db.execute(text("""
        UPDATE reclamos SET estado = 'Resuelto', fecha_modificacion = NOW(),
            id_usuario_modificacion = :uid
        WHERE id_reclamo = :id
    """), {"id": id_reclamo, "uid": id_usuario})
    await _insertar_historial_reclamo(db, id_reclamo, "Reclamo resuelto",
                                       estado_ant, "Resuelto", "OT cerrada sin auditoría", id_usuario)


# ── PUT /ot/{id}/aprobar ──────────────────────────────────────────────────────

@router.put("/{id_ot}/aprobar")
async def aprobar_ot(
    id_ot: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    r = await db.execute(text("""
        SELECT ot.id_reclamo, ot.es_auditoria, ot.id_estado,
               eot.nombre AS estado_actual, r.estado AS reclamo_estado
        FROM ordenes_trabajo ot
        JOIN estado_ot eot ON eot.id_estado_ot = ot.id_estado
        JOIN reclamos r ON r.id_reclamo = ot.id_reclamo
        WHERE ot.id_ot = :id AND ot.activo = TRUE
    """), {"id": id_ot})
    ot = r.fetchone()
    if not ot:
        raise HTTPException(status_code=404, detail=f"OT {id_ot} no encontrada")
    if not ot.es_auditoria:
        raise HTTPException(status_code=422, detail="Esta OT no es de auditoría")

    id_terminada = await _id_estado_ot(db, "Terminada")
    observaciones = body.get("observaciones", "")

    try:
        await db.execute(text("""
            UPDATE ordenes_trabajo
            SET id_estado = :id_est, resultado_auditoria = 'aprobada',
                observaciones_auditoria = :obs, fecha_cierre = NOW(),
                fecha_modificacion = NOW(), id_usuario_modificacion = :uid
            WHERE id_ot = :id
        """), {"id_est": id_terminada, "obs": observaciones,
               "uid": current_user["id_usuario"], "id": id_ot})

        await _resolver_reclamo(db, ot.id_reclamo, current_user["id_usuario"])
        await db.commit()
        return {"ok": True, "id_ot": id_ot, "resultado": "aprobada"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Error al aprobar OT: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


# ── PUT /ot/{id}/rechazar ─────────────────────────────────────────────────────

@router.put("/{id_ot}/rechazar")
async def rechazar_ot(
    id_ot: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    observaciones = (body.get("observaciones") or "").strip()
    if not observaciones:
        raise HTTPException(status_code=422, detail="Campo 'observaciones' obligatorio en rechazo")

    r = await db.execute(text("""
        SELECT ot.id_reclamo, ot.es_auditoria, ot.id_ot_origen,
               r.estado AS reclamo_estado, ot.id_supervisor_asigna
        FROM ordenes_trabajo ot
        JOIN reclamos r ON r.id_reclamo = ot.id_reclamo
        WHERE ot.id_ot = :id AND ot.activo = TRUE
    """), {"id": id_ot})
    ot = r.fetchone()
    if not ot:
        raise HTTPException(status_code=404, detail=f"OT {id_ot} no encontrada")
    if not ot.es_auditoria:
        raise HTTPException(status_code=422, detail="Esta OT no es de auditoría")

    id_terminada = await _id_estado_ot(db, "Terminada")
    id_pendiente  = await _id_estado_ot(db, "Pendiente")

    try:
        await db.execute(text("""
            UPDATE ordenes_trabajo
            SET id_estado = :id_est, resultado_auditoria = 'rechazada',
                observaciones_auditoria = :obs, fecha_cierre = NOW(),
                fecha_modificacion = NOW(), id_usuario_modificacion = :uid
            WHERE id_ot = :id
        """), {"id_est": id_terminada, "obs": observaciones,
               "uid": current_user["id_usuario"], "id": id_ot})

        id_origen = ot.id_ot_origen or id_ot
        await db.execute(text("""
            INSERT INTO ordenes_trabajo
                (id_reclamo, id_estado, es_auditoria, id_ot_origen, id_supervisor_asigna,
                 activo, fecha_alta, fecha_modificacion, id_usuario_alta, id_usuario_modificacion)
            VALUES (:id_r, :id_est, FALSE, :id_orig, :id_super,
                    TRUE, NOW(), NOW(), :uid, :uid)
        """), {"id_r": ot.id_reclamo, "id_est": id_pendiente, "id_orig": id_origen,
               "id_super": ot.id_supervisor_asigna, "uid": current_user["id_usuario"]})

        await db.execute(text("""
            UPDATE reclamos SET estado = 'En gestión', fecha_modificacion = NOW(),
                id_usuario_modificacion = :uid
            WHERE id_reclamo = :id
        """), {"id": ot.id_reclamo, "uid": current_user["id_usuario"]})

        await _insertar_historial_reclamo(db, ot.id_reclamo,
                                           "Auditoría rechazada — retrabajo generado",
                                           ot.reclamo_estado, "En gestión",
                                           observaciones, current_user["id_usuario"])
        await db.commit()
        return {"ok": True, "id_ot": id_ot, "resultado": "rechazada"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Error al rechazar OT: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
