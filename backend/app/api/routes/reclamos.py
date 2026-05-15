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

NIVELES_GESTION = {1, 2, 3}  # Admin, Supervisor, Operador (CLAUDE.md §3)


def _require_gestion(current_user: dict):
    if current_user.get("nivel_acceso") not in NIVELES_GESTION:
        raise HTTPException(status_code=403,
            detail="No tenés permisos para esta acción (requiere nivel Operador o superior)")


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
    q: Optional[str] = Query(None, description="Filtro por nombre (ILIKE)"),
    limit: int = Query(500, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Lista tipos de reclamo. El área se deriva siempre de subarea.id_area
    (mig 27 eliminó la columna redundante tipo_reclamo.id_area).
    """
    cond = ["tr.activo = TRUE"]
    params: dict = {"lim": limit}
    if id_area:
        cond.append("s.id_area = :id_area")
        params["id_area"] = id_area
    if q and q.strip():
        cond.append("tr.nombre ILIKE :q")
        params["q"] = f"%{q.strip()}%"

    result = await db.execute(text(f"""
        SELECT tr.id_tipo_reclamo, tr.nombre, tr.sla_dias, tr.audit,
               s.id_area, a.nombre AS area_nombre,
               tr.id_subarea, s.nombre AS subarea_nombre
        FROM tipo_reclamo tr
        LEFT JOIN subarea s ON s.id_subarea = tr.id_subarea
        LEFT JOIN area a ON a.id_area = s.id_area
        WHERE {' AND '.join(cond)}
        ORDER BY tr.nombre
        LIMIT :lim
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
        conds.append("(r.descripcion ILIKE :txt OR r.nro_reclamo ILIKE :txt OR c.nombre ILIKE :txt OR c.apellido ILIKE :txt OR c.doc_nro ILIKE :txt OR tr.nombre ILIKE :txt)")
        params["txt"] = f"%{texto}%"

    where = " AND ".join(conds)
    params["limit"] = limit
    params["offset"] = offset

    # Area: fuente unica es subarea.id_area (mig 27 dropeo tipo_reclamo.id_area).
    # r.id_area puede estar NULL en reclamos viejos; usar el area derivada del tipo.
    result = await db.execute(text(f"""
        SELECT
            r.id_reclamo, r.nro_reclamo, r.prioridad, r.estado,
            r.descripcion, r.domicilio_reclamo, r.observaciones,
            r.fecha_alta, r.fecha_modificacion,
            r.id_reclamo_padre,
            r.latitud, r.longitud,
            r.id_ciudadano, c.nombre AS ciudadano_nombre, c.apellido AS ciudadano_apellido, c.doc_nro,
            r.id_tipo_reclamo, tr.nombre AS tipo_nombre, tr.sla_dias, tr.audit AS tipo_audit,
            s.id_area, a.nombre AS area_nombre,
            r.id_agente_asignado,
            COALESCE(u.nombre, '—') AS agente_nombre
        FROM reclamos r
        LEFT JOIN ciudadanos c ON c.id_ciudadano = r.id_ciudadano
        LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
        LEFT JOIN subarea s ON s.id_subarea = tr.id_subarea
        LEFT JOIN area a ON a.id_area = s.id_area
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
            r.descripcion, r.domicilio_reclamo, r.direccion, r.observaciones,
            r.fecha_alta, r.fecha_modificacion,
            r.fecha_primer_asignacion, r.fecha_cierre, r.sla_vencimiento,
            r.canal_origen, r.fuente_geolocalizacion,
            r.latitud, r.longitud,
            r.id_localidad, loc.nombre AS localidad_nombre,
            par.id_partido, par.nombre AS partido_nombre,
            prov.id_provincia, prov.nombre AS provincia_nombre,
            r.id_activo, act.codigo_unico AS activo_codigo,
            ta.id_tipo_activo, ta.nombre AS activo_tipo_nombre,
            r.id_empresa, emp.nombre AS empresa_nombre, emp.cuit AS empresa_cuit,
            r.id_reclamo_padre,
            r.id_ciudadano, c.nombre AS ciudadano_nombre, c.apellido AS ciudadano_apellido,
            c.doc_nro, c.cuil, c.telefono, c.email AS ciudadano_email,
            r.id_tipo_reclamo, tr.nombre AS tipo_nombre, tr.sla_dias, tr.audit AS tipo_audit,
            s.id_area, a.nombre AS area_nombre,
            r.id_agente_asignado,
            COALESCE(u.nombre, '—') AS agente_nombre
        FROM reclamos r
        LEFT JOIN ciudadanos c ON c.id_ciudadano = r.id_ciudadano
        LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
        LEFT JOIN subarea s ON s.id_subarea = tr.id_subarea
        LEFT JOIN area a ON a.id_area = s.id_area
        LEFT JOIN usuarios u ON u.id_usuario = r.id_agente_asignado
        LEFT JOIN localidades loc ON loc.id_localidad = r.id_localidad
        LEFT JOIN partidos par ON par.id_partido = loc.id_partido
        LEFT JOIN provincias prov ON prov.id_provincia = par.id_provincia
        LEFT JOIN activos act ON act.id_activo = r.id_activo
        LEFT JOIN tipos_activo ta ON ta.id_tipo_activo = act.id_tipo_activo
        LEFT JOIN empresas emp ON emp.id_empresa = r.id_empresa
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

    # direccion es el campo nuevo (§22); domicilio_reclamo se mantiene como alias entrante
    direccion = body.get("direccion") or body.get("domicilio_reclamo") or ""

    # id_area: si no viene en el body, derivar de tipo_reclamo → subarea → area.
    # Fuente única: subarea.id_area (mig 27 eliminó tipo_reclamo.id_area).
    id_area = body.get("id_area")
    id_tipo = body.get("id_tipo_reclamo")
    if not id_area and id_tipo:
        r_area = await db.execute(text("""
            SELECT s.id_area
            FROM tipo_reclamo tr
            LEFT JOIN subarea s ON s.id_subarea = tr.id_subarea
            WHERE tr.id_tipo_reclamo = :id_tr
        """), {"id_tr": id_tipo})
        row_area = r_area.fetchone()
        if row_area:
            id_area = row_area.id_area

    id_empresa = body.get("id_empresa")
    if id_empresa:
        rep = await db.execute(text("""
            SELECT 1 FROM ciudadano_empresa
            WHERE id_ciudadano = :id_c AND id_empresa = :id_e AND activo = TRUE
        """), {"id_c": body["id_ciudadano"], "id_e": id_empresa})
        if not rep.fetchone():
            raise HTTPException(status_code=422,
                detail="El ciudadano no representa a esa empresa")

    data = {
        "id_ciudadano":     body["id_ciudadano"],
        "id_tipo_reclamo":  id_tipo,
        "id_area":          id_area,
        "descripcion":      body["descripcion"],
        "direccion":        direccion,
        "prioridad":        body.get("prioridad", "Media"),
        "observaciones":    body.get("observaciones", ""),
        "latitud":          body.get("latitud"),
        "longitud":         body.get("longitud"),
        "id_localidad":     body.get("id_localidad"),
        "id_activo":        body.get("id_activo"),
        "id_empresa":       id_empresa,
        "canal_origen":     body.get("canal_origen"),
        "fuente_geolocalizacion": body.get("fuente_geolocalizacion"),
        "id_usuario_alta":  current_user["id_usuario"],
    }

    try:
        # Resolver id_estado_fk de "Sin asignar" para nuevos reclamos
        r_est = await db.execute(text(
            "SELECT id_estado_reclamo FROM estado_reclamo WHERE nombre = 'Sin asignar' AND activo = TRUE LIMIT 1"
        ))
        est_row = r_est.fetchone()
        data["id_estado_fk"] = est_row.id_estado_reclamo if est_row else None

        result = await db.execute(text("""
            INSERT INTO reclamos
                (id_ciudadano, id_tipo_reclamo, id_area, descripcion, direccion,
                 domicilio_reclamo, prioridad, estado, id_estado_fk, observaciones,
                 latitud, longitud, id_localidad, id_activo, id_empresa, canal_origen,
                 fuente_geolocalizacion, activo, fecha_alta, fecha_modificacion,
                 id_usuario_alta, id_usuario_modificacion)
            VALUES
                (:id_ciudadano, :id_tipo_reclamo, :id_area, :descripcion, :direccion,
                 :direccion, :prioridad, 'Sin asignar', :id_estado_fk, :observaciones,
                 :latitud, :longitud, :id_localidad, :id_activo, :id_empresa, :canal_origen,
                 :fuente_geolocalizacion, TRUE, NOW(), NOW(),
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


# ── PUT /reclamos/{id} — editar (alcance según estado) ───────────────────────

# Campos editables sólo cuando el reclamo está "Sin asignar" (alta corregible).
EDITABLE_FIELDS_FULL = {
    "id_ciudadano", "id_tipo_reclamo", "descripcion", "direccion",
    "prioridad", "latitud", "longitud",
    "id_localidad", "id_activo", "id_empresa", "canal_origen",
    "fuente_geolocalizacion",
}
# Campos editables en cualquier estado vivo (notas operativas durante la gestión).
EDITABLE_FIELDS_ALWAYS = {"observaciones"}


@router.put("/{id_reclamo}")
async def editar_reclamo(
    id_reclamo: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _require_gestion(current_user)

    r = await db.execute(text("""
        SELECT id_ciudadano, estado FROM reclamos
        WHERE id_reclamo = :id AND activo = TRUE
    """), {"id": id_reclamo})
    row = r.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Reclamo {id_reclamo} no encontrado")
    if row.estado in ("Resuelto", "Cancelado"):
        raise HTTPException(status_code=422,
            detail=f"No se puede editar un reclamo cerrado (actual: {row.estado})")

    permitidos = EDITABLE_FIELDS_ALWAYS | (EDITABLE_FIELDS_FULL if row.estado == "Sin asignar" else set())
    rechazados = [k for k in body.keys() if k in EDITABLE_FIELDS_FULL and k not in permitidos]
    if rechazados:
        raise HTTPException(status_code=422,
            detail=f"En estado '{row.estado}' solo se pueden editar: {sorted(permitidos)}. Rechazados: {rechazados}")

    updates = {k: v for k, v in body.items() if k in permitidos}
    if not updates:
        raise HTTPException(status_code=422, detail="No hay campos editables en el body")

    # Si cambia el tipo, re-derivar id_area desde subarea.id_area (fuente de verdad)
    if "id_tipo_reclamo" in updates and updates["id_tipo_reclamo"]:
        r_area = await db.execute(text("""
            SELECT s.id_area
            FROM tipo_reclamo tr
            LEFT JOIN subarea s ON s.id_subarea = tr.id_subarea
            WHERE tr.id_tipo_reclamo = :id_tr
        """), {"id_tr": updates["id_tipo_reclamo"]})
        row_area = r_area.fetchone()
        if row_area and row_area.id_area:
            updates["id_area"] = row_area.id_area

    # Validar vínculo ciudadano-empresa si cambia alguno de los dos
    id_ciudadano_final = updates.get("id_ciudadano", row.id_ciudadano)
    id_empresa_final = updates.get("id_empresa")
    if id_empresa_final:
        rep = await db.execute(text("""
            SELECT 1 FROM ciudadano_empresa
            WHERE id_ciudadano = :id_c AND id_empresa = :id_e AND activo = TRUE
        """), {"id_c": id_ciudadano_final, "id_e": id_empresa_final})
        if not rep.fetchone():
            raise HTTPException(status_code=422,
                detail="El ciudadano no representa a esa empresa")

    # Mantener domicilio_reclamo sincronizado con direccion (columna legacy)
    if "direccion" in updates:
        updates["domicilio_reclamo"] = updates["direccion"]

    set_clauses = [f"{k} = :{k}" for k in updates.keys()]
    set_clauses.append("fecha_modificacion = NOW()")
    set_clauses.append("id_usuario_modificacion = :uid")
    params = dict(updates)
    params["id"] = id_reclamo
    params["uid"] = current_user["id_usuario"]

    try:
        await db.execute(text(f"""
            UPDATE reclamos SET {', '.join(set_clauses)}
            WHERE id_reclamo = :id
        """), params)
        nota_hist = body.get("nota_historial") or f"Campos modificados: {', '.join(updates.keys())}"
        await _insertar_historial(db, id_reclamo, "Reclamo editado",
                                   row.estado, row.estado,
                                   nota_hist,
                                   current_user["id_usuario"])
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Error al editar reclamo %s: %s", id_reclamo, e)
        raise HTTPException(status_code=400, detail=str(e))

    return {"ok": True, "id_reclamo": id_reclamo, "campos": list(updates.keys())}


# ── PUT /reclamos/{id}/cancelar — cancelar con cascade a OTs ─────────────────

@router.put("/{id_reclamo}/cancelar")
async def cancelar_reclamo(
    id_reclamo: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _require_gestion(current_user)
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
        SELECT id_reclamo, id_ciudadano, id_empresa, id_reclamo_padre, estado
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

    direccion = body.get("direccion") or body.get("domicilio_reclamo") or ""

    # id_empresa: por defecto hereda del padre. Si el body lo trae, valida.
    id_ciudadano_sub = body.get("id_ciudadano") or padre.id_ciudadano
    if "id_empresa" in body:
        id_empresa = body.get("id_empresa")
        if id_empresa:
            rep = await db.execute(text("""
                SELECT 1 FROM ciudadano_empresa
                WHERE id_ciudadano = :id_c AND id_empresa = :id_e AND activo = TRUE
            """), {"id_c": id_ciudadano_sub, "id_e": id_empresa})
            if not rep.fetchone():
                raise HTTPException(status_code=422,
                    detail="El ciudadano no representa a esa empresa")
    else:
        id_empresa = padre.id_empresa

    data = {
        "id_ciudadano":     id_ciudadano_sub,
        "id_tipo_reclamo":  body["id_tipo_reclamo"],
        "id_area":          body.get("id_area"),
        "descripcion":      body["descripcion"],
        "direccion":        direccion,
        "prioridad":        body.get("prioridad", "Media"),
        "observaciones":    body.get("observaciones", ""),
        "latitud":          body.get("latitud"),
        "longitud":         body.get("longitud"),
        "id_localidad":     body.get("id_localidad"),
        "id_activo":        body.get("id_activo"),
        "id_empresa":       id_empresa,
        "canal_origen":     body.get("canal_origen"),
        "fuente_geolocalizacion": body.get("fuente_geolocalizacion"),
        "id_reclamo_padre": id_reclamo,
        "id_usuario_alta":  current_user["id_usuario"],
    }

    try:
        r_est = await db.execute(text(
            "SELECT id_estado_reclamo FROM estado_reclamo WHERE nombre = 'Sin asignar' AND activo = TRUE LIMIT 1"
        ))
        est_row = r_est.fetchone()
        data["id_estado_fk"] = est_row.id_estado_reclamo if est_row else None

        result = await db.execute(text("""
            INSERT INTO reclamos
                (id_ciudadano, id_tipo_reclamo, id_area, descripcion, direccion,
                 domicilio_reclamo, prioridad, estado, id_estado_fk, observaciones,
                 latitud, longitud, id_localidad, id_activo, id_empresa, canal_origen,
                 fuente_geolocalizacion, id_reclamo_padre, activo,
                 fecha_alta, fecha_modificacion, id_usuario_alta, id_usuario_modificacion)
            VALUES
                (:id_ciudadano, :id_tipo_reclamo, :id_area, :descripcion, :direccion,
                 :direccion, :prioridad, 'Sin asignar', :id_estado_fk, :observaciones,
                 :latitud, :longitud, :id_localidad, :id_activo, :id_empresa, :canal_origen,
                 :fuente_geolocalizacion, :id_reclamo_padre, TRUE,
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
