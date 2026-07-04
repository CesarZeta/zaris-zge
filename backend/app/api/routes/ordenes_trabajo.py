"""
ZARIS API — Endpoints del módulo Órdenes de Trabajo (v1.2).
Prefijo: /api/v1/ot/

IMPORTANTE: rutas con segmentos fijos (/catalogo/*, /mesa/*) van ANTES de /{id_ot}
para que FastAPI no las interprete como path param.
"""
import logging
from datetime import date, datetime, time, timedelta
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user
from app.services.agenda import disponibilidad_efectiva
from app.services import encuestas_service as svc_encuestas
from app.services import push as svc_push
from app.services.tramites.auth import resolver_agente_desde_usuario

router = APIRouter(prefix="/api/v1/ot", tags=["Órdenes de Trabajo"])
logger = logging.getLogger("zaris.ordenes_trabajo")

# Grafo de transiciones permitidas del estado de una OT operativa (estados reales
# de estado_ot en prod). Las transiciones de auditoría (Terminada via aprobar/
# rechazar) van por endpoints dedicados (/aprobar, /rechazar), no por /estado.
# - Pendiente: retrabajo tras rechazo de auditoría; debe re-tomarse (-> En gestión).
# - Terminada / Cancelada: finales.
TRANSICIONES_OT: dict[str, set[str]] = {
    "En gestión": {"En espera", "Pendiente", "Terminada", "Cancelada"},
    "En espera":  {"En gestión", "Terminada", "Cancelada"},
    "Pendiente":  {"En gestión", "Cancelada"},
    "Terminada":  set(),
    "Cancelada":  set(),
}


# ── Helpers de slots (planificacion de OT sobre la agenda) ───────────────────
def _slots_de_rango(rango_ini: time, rango_fin: time, duracion_min: int) -> list[tuple[time, time]]:
    """Parte un rango horario en slots consecutivos de `duracion_min`.
    Descarta el ultimo si no entra completo."""
    out: list[tuple[time, time]] = []
    cursor = datetime.combine(date.min, rango_ini)
    fin = datetime.combine(date.min, rango_fin)
    paso = timedelta(minutes=duracion_min)
    while cursor + paso <= fin:
        out.append((cursor.time(), (cursor + paso).time()))
        cursor += paso
    return out


def _solapa(a_ini: time, a_fin: time, b_ini: time, b_fin: time) -> bool:
    return a_ini < b_fin and a_fin > b_ini


def _merge_rangos(rangos: list[tuple[time, time]]) -> list[tuple[time, time]]:
    """Une rangos solapados o contiguos. Usado para la disponibilidad de un
    equipo = union de las disponibilidades de sus agentes."""
    if not rangos:
        return []
    ordenados = sorted(rangos, key=lambda r: r[0])
    out = [ordenados[0]]
    for ini, fin in ordenados[1:]:
        last_ini, last_fin = out[-1]
        if ini <= last_fin:
            out[-1] = (last_ini, max(last_fin, fin))
        else:
            out.append((ini, fin))
    return out


async def _slots_libres_recurso(
    db: AsyncSession, tipo_recurso: str, id_recurso: int, fecha: date, duracion_min: int,
) -> list[dict[str, Any]]:
    """Slots libres de un agente o equipo para una fecha.

    - agente: disponibilidad efectiva del agente menos sus ocupaciones.
    - equipo: union de las disponibilidades de los agentes del equipo
      (equipo_agentes) menos la union de ocupaciones de todos ellos. Si el
      equipo no tiene agentes con agenda cargada, devuelve [] (no disponible).
    """
    if tipo_recurso == "agente":
        rangos_raw = await disponibilidad_efectiva(db, "agente", id_recurso, fecha)
        rangos = [(r["hora_inicio"], r["hora_fin"]) for r in rangos_raw]
        ocup = (await db.execute(text("""
            SELECT hora_inicio, hora_fin FROM ocupaciones
            WHERE activo = TRUE AND tipo_recurso = 'agente' AND id_recurso = :ir AND fecha = :f
        """), {"ir": id_recurso, "f": fecha})).mappings().all()
        ocupadas = [(o["hora_inicio"], o["hora_fin"]) for o in ocup]
    elif tipo_recurso == "equipo":
        # Disponibilidad del equipo = union de sus agentes + override de equipo
        # sin agentes (mig 91). Delegamos en disponibilidad_efectiva para NO
        # duplicar la logica (esta duplicacion era la que hacia divergir la
        # grilla de Agenda del planificador de OT). Equipo sin agentes y sin
        # override -> [] (lo resuelve disponibilidad_efectiva).
        rangos_raw = await disponibilidad_efectiva(db, "equipo", id_recurso, fecha)
        rangos = [(r["hora_inicio"], r["hora_fin"]) for r in rangos_raw]
        if not rangos:
            return []
        # Agentes del equipo, para sumar sus ocupaciones individuales.
        agentes = (await db.execute(text("""
            SELECT id_agente FROM equipo_agentes
            WHERE id_equipo = :ie AND activo = TRUE
        """), {"ie": id_recurso})).scalars().all()
        # Ocupaciones: las del equipo + las de cualquiera de sus agentes.
        ocup = (await db.execute(text("""
            SELECT hora_inicio, hora_fin FROM ocupaciones
            WHERE activo = TRUE AND fecha = :f
              AND (
                (tipo_recurso = 'equipo' AND id_recurso = :ie)
                OR (tipo_recurso = 'agente' AND id_recurso = ANY(:ags))
              )
        """), {"f": fecha, "ie": id_recurso, "ags": list(agentes) or [-1]})).mappings().all()
        ocupadas = [(o["hora_inicio"], o["hora_fin"]) for o in ocup]
    else:
        raise HTTPException(422, "tipo_recurso debe ser 'agente' o 'equipo'")

    out: list[dict[str, Any]] = []
    for r_ini, r_fin in rangos:
        for s_ini, s_fin in _slots_de_rango(r_ini, r_fin, duracion_min):
            if any(_solapa(s_ini, s_fin, o_ini, o_fin) for o_ini, o_fin in ocupadas):
                continue
            out.append({
                "hora_inicio": s_ini.strftime("%H:%M:%S"),
                "hora_fin": s_fin.strftime("%H:%M:%S"),
            })
    return out


def _to_dict(row) -> dict:
    d = dict(row._mapping)
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


def _require_supervisor(current_user: dict):
    """#2 — La asignación de OT y la Mesa del Supervisor son exclusivas de
    Administrador (1) y Supervisor (2). Un Operador (3) o Consultor (4) no puede
    crear/asignar/reasignar OTs ni ver la bandeja del supervisor.
    Espeja la regla del módulo de permisos: ot_supervisor exige min_nivel_acceso=2."""
    if current_user.get("nivel_acceso", 99) > 2:
        raise HTTPException(
            status_code=403,
            detail="Acción exclusiva de Supervisor o Administrador (Mesa del Supervisor).",
        )


async def _subarea_forzada_supervisor(db: AsyncSession, current_user: dict) -> Optional[int]:
    """Fase 3 roles — modelo "subárea compartida": el Supervisor (nivel 2) queda
    SIEMPRE restringido a la subárea de su agente vinculado (regla 1:1 §39).
    Devuelve esa id_subarea para nivel 2, o None para nivel 1 (admin ve todo).
    403 accionable si el supervisor no tiene agente o subárea (cuenta a medias)."""
    if current_user.get("nivel_acceso", 99) != 2:
        return None
    perfil = await resolver_agente_desde_usuario(current_user["id_usuario"], db)
    if not perfil or not perfil.get("id_subarea"):
        raise HTTPException(
            status_code=403,
            detail=(
                "Tu usuario supervisor no tiene una subárea asignada en su perfil "
                "de agente. Pedile a un administrador que la configure desde "
                "Maestros → Usuarios."
            ),
        )
    return perfil["id_subarea"]


async def _validar_scope_supervisor_ot(
    db: AsyncSession,
    current_user: dict,
    *,
    id_reclamo: Optional[int] = None,
    id_agente: Optional[int] = None,
    id_equipo: Optional[int] = None,
):
    """Fase 3 roles — un Supervisor (nivel 2) solo gestiona reclamos de su subárea
    y solo asigna recursos (agentes/equipos) de su subárea. Admin pasa sin
    restricción. La subárea del reclamo es tr.id_subarea derivada del tipo (§27).
    Si el reclamo no existe, no corta acá: el 404 lo da el handler."""
    sub = await _subarea_forzada_supervisor(db, current_user)
    if sub is None:
        return
    if id_reclamo is not None:
        row = (await db.execute(text("""
            SELECT tr.id_subarea
            FROM reclamos r
            LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
            WHERE r.id_reclamo = :id AND r.activo = TRUE
        """), {"id": id_reclamo})).fetchone()
        if row is not None and row.id_subarea != sub:
            raise HTTPException(
                status_code=403,
                detail="El reclamo pertenece a otra subárea. Solo podés gestionar reclamos de tu subárea.",
            )
    if id_agente is not None:
        row = (await db.execute(text(
            "SELECT id_subarea FROM agentes WHERE id_agente = :id AND activo = TRUE"
        ), {"id": id_agente})).fetchone()
        if not row:
            raise HTTPException(status_code=422, detail=f"Agente {id_agente} inexistente o inactivo")
        if row.id_subarea != sub:
            raise HTTPException(
                status_code=403,
                detail="El agente pertenece a otra subárea. Solo podés asignar agentes de tu subárea.",
            )
    if id_equipo is not None:
        row = (await db.execute(text(
            "SELECT id_subarea FROM equipos WHERE id_equipo = :id AND activo = TRUE"
        ), {"id": id_equipo})).fetchone()
        if not row:
            raise HTTPException(status_code=422, detail=f"Equipo {id_equipo} inexistente o inactivo")
        if row.id_subarea != sub:
            raise HTTPException(
                status_code=403,
                detail="El equipo pertenece a otra subárea. Solo podés asignar equipos de tu subárea.",
            )


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
    nro: Optional[str] = Query(None, max_length=30, description="Número de reclamo, parcial o completo (ILIKE)"),
    nro_desde: Optional[int] = Query(None, ge=0, description="Parte secuencial del nro (ej. 56 para REC-2026-000056)"),
    nro_hasta: Optional[int] = Query(None, ge=0),
    fecha_desde: Optional[date] = Query(None, description="fecha_alta del reclamo >= (YYYY-MM-DD)"),
    fecha_hasta: Optional[date] = Query(None, description="fecha_alta del reclamo <= (YYYY-MM-DD, inclusivo)"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Vista del supervisor: reclamos activos (Sin asignar, En gestión, En espera, En auditoría)."""
    _require_supervisor(current_user)
    # Nivel 2: la subárea del supervisor pisa cualquier query param (Fase 3 roles).
    # Nivel 1 (admin) sigue filtrando libre.
    sub_forzada = await _subarea_forzada_supervisor(db, current_user)
    if sub_forzada is not None:
        id_subarea = sub_forzada
    conds = ["r.activo = TRUE", "r.estado NOT IN ('Resuelto','Cancelado')"]
    params: dict = {}
    if id_subarea:
        # Subarea fuente unica: tr.id_subarea derivada del tipo (§27). r.id_subarea
        # esta NULL en el 100% de los reclamos (filtrar por ahi vaciaba la bandeja
        # en silencio — feedback_filtro_igual_null_vacia_listado).
        conds.append("tr.id_subarea = :id_subarea")
        params["id_subarea"] = id_subarea
    if nro:
        conds.append("r.nro_reclamo ILIKE :nro")
        params["nro"] = f"%{nro.strip()}%"
    # Rango por la parte secuencial del nro (formato REC-YYYY-NNNNNN, verificado
    # 57/57 en prod). El CASE con regex evita un 500 si aparece un formato raro.
    _nro_seq = r"(CASE WHEN r.nro_reclamo ~ '^REC-\d{4}-\d{6}$' THEN split_part(r.nro_reclamo, '-', 3)::int END)"
    if nro_desde is not None:
        conds.append(f"{_nro_seq} >= :nro_desde")
        params["nro_desde"] = nro_desde
    if nro_hasta is not None:
        conds.append(f"{_nro_seq} <= :nro_hasta")
        params["nro_hasta"] = nro_hasta
    if fecha_desde is not None:
        conds.append("r.fecha_alta >= CAST(:fecha_desde AS date)")
        params["fecha_desde"] = fecha_desde
    if fecha_hasta is not None:
        # Inclusivo: < día siguiente (fecha_alta es TIMESTAMPTZ).
        conds.append("r.fecha_alta < CAST(:fecha_hasta AS date) + 1")
        params["fecha_hasta"] = fecha_hasta

    result = await db.execute(text(f"""
        WITH ot_activa AS (
            SELECT DISTINCT ON (ot.id_reclamo)
                ot.id_reclamo, ot.id_ot, ot.nro_ot,
                ot.id_agente, ot.id_equipo,
                eot.nombre AS ot_estado_nombre,
                EXISTS (
                    SELECT 1 FROM ocupaciones oc
                    WHERE oc.id_orden_trabajo = ot.id_ot
                      AND oc.tipo = 'ot' AND oc.activo = TRUE
                ) AS ot_agendada
            FROM ordenes_trabajo ot
            JOIN estado_ot eot ON eot.id_estado_ot = ot.id_estado
            WHERE ot.activo = TRUE
              AND ot.es_auditoria = FALSE
              AND eot.nombre IN ('En gestión','En espera','Pendiente')
            ORDER BY ot.id_reclamo, ot.fecha_alta DESC
        ),
        ot_counts AS (
            SELECT id_reclamo, COUNT(*) AS cant_ots
            FROM ordenes_trabajo
            WHERE activo = TRUE
            GROUP BY id_reclamo
        )
        SELECT
            r.id_reclamo, r.nro_reclamo, r.estado, r.prioridad,
            r.descripcion, r.domicilio_reclamo, r.fecha_alta,
            r.sla_vencimiento,
            r.id_reclamo_padre,
            c.nombre AS ciudadano_nombre, c.apellido AS ciudadano_apellido, c.doc_nro,
            tr.nombre AS tipo_nombre, tr.sla_dias, tr.audit AS tipo_audit,
            a.nombre AS area_nombre,
            s.id_subarea, s.nombre AS subarea_nombre,
            COALESCE(otc.cant_ots, 0) AS cant_ots,
            ota.id_ot AS ot_activa_id,
            ota.nro_ot AS ot_activa_nro,
            ota.ot_estado_nombre AS ot_activa_estado,
            ota.ot_agendada AS ot_activa_agendada,
            ota.id_agente AS ot_id_agente,
            (ag.apellido || ', ' || ag.nombre) AS ot_agente_nombre,
            ota.id_equipo AS ot_id_equipo,
            eq.nombre AS ot_equipo_nombre
        FROM reclamos r
        LEFT JOIN ciudadanos c ON c.id_ciudadano = r.id_ciudadano
        LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
        -- Subarea y area se derivan del tipo (mig 27 dropeo tipo_reclamo.id_area;
        -- reclamos.id_area y id_subarea pueden estar NULL en filas viejas).
        LEFT JOIN subarea s ON s.id_subarea = tr.id_subarea
        LEFT JOIN area a ON a.id_area = s.id_area
        LEFT JOIN ot_counts otc ON otc.id_reclamo = r.id_reclamo
        LEFT JOIN ot_activa ota ON ota.id_reclamo = r.id_reclamo
        LEFT JOIN agentes ag ON ag.id_agente = ota.id_agente
        LEFT JOIN equipos eq ON eq.id_equipo = ota.id_equipo
        WHERE {" AND ".join(conds)}
        ORDER BY
            CASE r.prioridad WHEN 'Alta' THEN 1 WHEN 'Media' THEN 2 ELSE 3 END,
            r.sla_vencimiento ASC NULLS LAST,
            r.fecha_alta ASC
    """), params)

    return [_to_dict(row) for row in result.fetchall()]


# ── GET /ot/mesa/agente ──────────────────────────────────────────────────────

async def _mesa_agente_query(db: AsyncSession, id_agente: int):
    """SQL compartido por /mesa/agente y /agente/me."""
    result = await db.execute(text("""
        SELECT
            ot.id_ot, ot.nro_ot, ot.es_auditoria,
            ot.fecha_creacion, ot.observaciones,
            eot.nombre AS estado_nombre, eot.color AS estado_color,
            r.id_reclamo, r.nro_reclamo,
            r.estado AS reclamo_estado,
            r.prioridad AS reclamo_prioridad,
            r.descripcion AS reclamo_descripcion,
            r.fecha_alta AS reclamo_fecha_alta,
            r.sla_vencimiento,
            r.direccion AS reclamo_direccion,
            tr.nombre AS tipo_nombre, tr.sla_dias, tr.audit AS tipo_audit,
            s.id_subarea, s.nombre AS subarea_nombre,
            ot.id_equipo, eq.nombre AS equipo_nombre,
            ot.id_agente,
            CASE
              WHEN ot.id_agente = :id_agente THEN 'mia'
              WHEN ot.id_agente IS NULL AND ot.id_equipo IS NOT NULL THEN 'disponible_equipo'
              ELSE 'otro'
            END AS scope,
            c.nombre AS ciudadano_nombre, c.apellido AS ciudadano_apellido
        FROM ordenes_trabajo ot
        JOIN estado_ot eot ON eot.id_estado_ot = ot.id_estado
        JOIN reclamos r ON r.id_reclamo = ot.id_reclamo
        LEFT JOIN ciudadanos c ON c.id_ciudadano = r.id_ciudadano
        LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
        -- Subarea cosmetica: derivada del tipo porque r.id_subarea puede estar NULL
        -- en reclamos viejos. NO afecta el scope (WHERE r.id_subarea...) si lo hay.
        LEFT JOIN subarea s ON s.id_subarea = tr.id_subarea
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
            r.sla_vencimiento ASC NULLS LAST,
            ot.fecha_creacion ASC
    """), {"id_agente": id_agente})
    return [_to_dict(row) for row in result.fetchall()]


async def _resolver_id_agente_por_usuario(db: AsyncSession, id_usuario: int) -> Optional[int]:
    """Mig 28: vínculo formal por id, no por email. Ver memoria feedback_vincular_por_id."""
    r = await db.execute(text(
        "SELECT id_agente FROM agentes WHERE id_usuario = :uid AND activo = TRUE LIMIT 1"
    ), {"uid": id_usuario})
    row = r.fetchone()
    return row.id_agente if row else None


@router.get("/mesa/agente")
async def mesa_agente(
    id_agente: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """OTs en gestión, en espera o pendiente asignadas al agente o a sus equipos."""
    return await _mesa_agente_query(db, id_agente)


@router.get("/agente/me")
async def mesa_agente_me(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Mesa del agente logueado. Resuelve via agentes.id_usuario = current_user.id_usuario (mig 28)."""
    id_usuario = current_user.get("id_usuario")
    if not id_usuario:
        raise HTTPException(status_code=422, detail="Usuario sin id_usuario en el token")
    id_agente = await _resolver_id_agente_por_usuario(db, id_usuario)
    if id_agente is None:
        raise HTTPException(
            status_code=404,
            detail="Tu usuario no está vinculado a ningún agente activo. Pedile al administrador que asocie tu cuenta al registro de Agentes."
        )
    rows = await _mesa_agente_query(db, id_agente)
    return {"id_agente": id_agente, "ots": rows}


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
            AND (tr.id_subarea IS NULL OR tr.id_subarea NOT IN (
                SELECT id_subarea FROM agentes WHERE id_agente = :id_agente
                UNION
                SELECT eq.id_subarea FROM equipo_agentes ea
                JOIN equipos eq ON eq.id_equipo = ea.id_equipo
                WHERE ea.id_agente = :id_agente AND ea.activo = TRUE
            ))
        """

    result = await db.execute(text(f"""
        SELECT
            ot.id_ot, ot.nro_ot, ot.fecha_creacion, ot.observaciones,
            eot.nombre AS estado_nombre, eot.color AS estado_color,
            r.id_reclamo, r.nro_reclamo,
            r.prioridad AS reclamo_prioridad,
            r.descripcion AS reclamo_descripcion,
            r.id_subarea, s.nombre AS subarea_nombre,
            r.sla_vencimiento,
            tr.nombre AS tipo_nombre, tr.sla_dias,
            ot.id_agente, ag.nombre AS agente_nombre, ag.apellido AS agente_apellido,
            c.nombre AS ciudadano_nombre, c.apellido AS ciudadano_apellido,
            ot.id_ot_origen,
            ot_orig.nro_ot AS ot_origen_nro,
            ot_orig.observaciones AS ot_origen_obs,
            ag_orig.apellido AS ot_origen_agente_apellido,
            ag_orig.nombre AS ot_origen_agente_nombre
        FROM ordenes_trabajo ot
        JOIN estado_ot eot ON eot.id_estado_ot = ot.id_estado
        JOIN reclamos r ON r.id_reclamo = ot.id_reclamo
        LEFT JOIN ciudadanos c ON c.id_ciudadano = r.id_ciudadano
        LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
        -- Subarea cosmetica: derivada del tipo porque r.id_subarea puede estar NULL
        -- en reclamos viejos. NO afecta el scope (WHERE r.id_subarea...) si lo hay.
        LEFT JOIN subarea s ON s.id_subarea = tr.id_subarea
        LEFT JOIN agentes ag ON ag.id_agente = ot.id_agente
        LEFT JOIN ordenes_trabajo ot_orig ON ot_orig.id_ot = ot.id_ot_origen
        LEFT JOIN agentes ag_orig ON ag_orig.id_agente = ot_orig.id_agente
        WHERE ot.activo = TRUE
          AND ot.es_auditoria = TRUE
          AND eot.nombre NOT IN ('Terminada','Cancelada')
          AND (ot.id_agente IS NULL OR ot.id_agente = :id_agente)
          {subarea_filter}
        ORDER BY ot.fecha_creacion ASC
    """), {"id_agente": id_agente})

    return [_to_dict(row) for row in result.fetchall()]


# ── GET /ot/auditor/me ───────────────────────────────────────────────────────

async def _verificar_es_auditor(db: AsyncSession, id_agente: int) -> bool:
    r = await db.execute(text("SELECT es_auditor FROM agentes WHERE id_agente = :id AND activo = TRUE"), {"id": id_agente})
    row = r.fetchone()
    return bool(row and row.es_auditor)


@router.get("/auditor/me")
async def mesa_auditor_me(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Mesa del auditor logueado. Verifica que el usuario sea agente con es_auditor=TRUE.

    Resuelve via agentes.id_usuario = current_user.id_usuario (mig 28).
    Aplica filtro de subárea según configuracion_general.auditor_misma_subarea_permitido.

    Admin (nivel_acceso=1) bypassea el check de es_auditor: por definicion tiene
    acceso total. La regla "no auditar lo propio" sigue garantizada por el filtro
    `ot.id_agente IS NULL OR ot.id_agente = :id_agente` que ya excluye OTs operativas
    propias del listado de auditoria.
    """
    id_usuario = current_user.get("id_usuario")
    if not id_usuario:
        raise HTTPException(status_code=422, detail="Usuario sin id_usuario en el token")
    id_agente = await _resolver_id_agente_por_usuario(db, id_usuario)
    if id_agente is None:
        raise HTTPException(
            status_code=404,
            detail="Tu usuario no está vinculado a ningún agente activo. Pedile al administrador que asocie tu cuenta."
        )
    es_admin = (current_user.get("nivel_acceso") or 99) <= 1
    if not es_admin and not await _verificar_es_auditor(db, id_agente):
        raise HTTPException(
            status_code=403,
            detail="No tenés permisos de auditor. Pedile al administrador que active es_auditor en tu registro de agente."
        )

    # reusa la lógica de mesa_auditoria
    cfg = await db.execute(text(
        "SELECT valor FROM configuracion_general WHERE clave = 'auditor_misma_subarea_permitido'"
    ))
    cfg_row = cfg.fetchone()
    misma_subarea_ok = (cfg_row.valor.lower() == "true") if cfg_row else False

    subarea_filter = ""
    if not misma_subarea_ok:
        subarea_filter = """
            AND (tr.id_subarea IS NULL OR tr.id_subarea NOT IN (
                SELECT id_subarea FROM agentes WHERE id_agente = :id_agente
                UNION
                SELECT eq.id_subarea FROM equipo_agentes ea
                JOIN equipos eq ON eq.id_equipo = ea.id_equipo
                WHERE ea.id_agente = :id_agente AND ea.activo = TRUE
            ))
        """

    result = await db.execute(text(f"""
        SELECT
            ot.id_ot, ot.nro_ot, ot.fecha_creacion, ot.observaciones,
            eot.nombre AS estado_nombre, eot.color AS estado_color,
            r.id_reclamo, r.nro_reclamo,
            r.prioridad AS reclamo_prioridad,
            r.descripcion AS reclamo_descripcion,
            r.id_subarea, s.nombre AS subarea_nombre,
            r.sla_vencimiento,
            tr.nombre AS tipo_nombre, tr.sla_dias,
            ot.id_agente, ag.nombre AS agente_nombre, ag.apellido AS agente_apellido,
            c.nombre AS ciudadano_nombre, c.apellido AS ciudadano_apellido,
            ot.id_ot_origen,
            ot_orig.nro_ot AS ot_origen_nro,
            ot_orig.observaciones AS ot_origen_obs,
            ag_orig.apellido AS ot_origen_agente_apellido,
            ag_orig.nombre AS ot_origen_agente_nombre
        FROM ordenes_trabajo ot
        JOIN estado_ot eot ON eot.id_estado_ot = ot.id_estado
        JOIN reclamos r ON r.id_reclamo = ot.id_reclamo
        LEFT JOIN ciudadanos c ON c.id_ciudadano = r.id_ciudadano
        LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
        -- Subarea cosmetica: derivada del tipo porque r.id_subarea puede estar NULL
        -- en reclamos viejos. NO afecta el scope (WHERE r.id_subarea...) si lo hay.
        LEFT JOIN subarea s ON s.id_subarea = tr.id_subarea
        LEFT JOIN agentes ag ON ag.id_agente = ot.id_agente
        LEFT JOIN ordenes_trabajo ot_orig ON ot_orig.id_ot = ot.id_ot_origen
        LEFT JOIN agentes ag_orig ON ag_orig.id_agente = ot_orig.id_agente
        WHERE ot.activo = TRUE
          AND ot.es_auditoria = TRUE
          AND eot.nombre NOT IN ('Terminada','Cancelada')
          AND (ot.id_agente IS NULL OR ot.id_agente = :id_agente)
          {subarea_filter}
        ORDER BY
            CASE r.prioridad WHEN 'Alta' THEN 1 WHEN 'Media' THEN 2 ELSE 3 END,
            r.sla_vencimiento ASC NULLS LAST,
            ot.fecha_creacion ASC
    """), {"id_agente": id_agente})

    return {"id_agente": id_agente, "ots": [_to_dict(row) for row in result.fetchall()]}


# ── GET /ot/slots-recurso — slots libres de un agente/equipo ─────────────────
# Segmento fijo: DEBE ir antes de GET /{id_ot}.

@router.get("/slots-recurso")
async def slots_recurso(
    tipo_recurso: str = Query(..., description="agente | equipo"),
    id_recurso: int = Query(...),
    fecha: date = Query(...),
    duracion_min: int = Query(60, ge=15, le=480),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Huecos libres de un recurso para una fecha, en bloques de `duracion_min`.
    Para equipo: union de las disponibilidades de sus agentes (equipo_agentes)
    menos las ocupaciones de todos ellos. Equipo sin agentes con agenda -> []."""
    if tipo_recurso not in ("agente", "equipo"):
        raise HTTPException(422, "tipo_recurso debe ser 'agente' o 'equipo'")
    slots = await _slots_libres_recurso(db, tipo_recurso, id_recurso, fecha, duracion_min)
    return {"tipo_recurso": tipo_recurso, "id_recurso": id_recurso,
            "fecha": fecha.isoformat(), "duracion_min": duracion_min, "slots": slots}


# ── GET /ot/auto-asignar-sugerencia — primer recurso disponible de la subarea ─
# Segmento fijo: DEBE ir antes de GET /{id_ot}.

@router.get("/auto-asignar-sugerencia")
async def auto_asignar_sugerencia(
    id_reclamo: int = Query(...),
    fecha: date = Query(...),
    duracion_min: int = Query(60, ge=15, le=480),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Recorre los recursos de la subarea del reclamo (cuadrillas de trabajo +
    agentes) y devuelve el PRIMERO con un slot libre en la fecha, para que el
    supervisor confirme. Prioriza equipos (cuadrillas) sobre agentes; dentro de
    cada grupo, el slot mas temprano. Si ninguno tiene hueco, devuelve null.

    Solo supervisor/admin (es la accion de asignacion de la Mesa del Supervisor)."""
    _require_supervisor(current_user)
    # Nivel 2: solo sobre reclamos de su subárea (Fase 3 roles).
    await _validar_scope_supervisor_ot(db, current_user, id_reclamo=id_reclamo)

    # Subarea del reclamo: derivada del tipo (fuente unica, r.id_subarea suele ser NULL).
    sub = (await db.execute(text("""
        SELECT tr.id_subarea
        FROM reclamos r
        LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
        WHERE r.id_reclamo = :id AND r.activo = TRUE
    """), {"id": id_reclamo})).fetchone()
    if not sub:
        raise HTTPException(404, f"Reclamo {id_reclamo} no encontrado")
    id_subarea = sub.id_subarea

    # Candidatos: cuadrillas de trabajo de la subarea + agentes de la subarea.
    # Si el reclamo no tiene subarea (tipo sin subarea), no podemos acotar:
    # devolvemos sin sugerencia para no recorrer todo el padron.
    if id_subarea is None:
        return {"sugerencia": None, "motivo": "El tipo de reclamo no tiene subarea asociada."}

    equipos = [(int(r.id_equipo), r.nombre) for r in (await db.execute(text("""
        SELECT id_equipo, nombre FROM equipos
        WHERE activo = TRUE AND tipo_grupo = 'trabajo_reclamos' AND id_subarea = :s
        ORDER BY id_equipo
    """), {"s": id_subarea})).fetchall()]
    agentes = [(int(r.id_agente), (r.apellido or "") + ", " + (r.nombre or "")) for r in (await db.execute(text("""
        SELECT id_agente, nombre, apellido FROM agentes
        WHERE activo = TRUE AND id_subarea = :s
        ORDER BY apellido, nombre
    """), {"s": id_subarea})).fetchall()]

    # Prioriza equipos, luego agentes. Primer recurso con slot libre.
    for (tipo, candidatos) in (("equipo", equipos), ("agente", agentes)):
        for (id_rec, nombre) in candidatos:
            slots = await _slots_libres_recurso(db, tipo, id_rec, fecha, duracion_min)
            if slots:
                return {"sugerencia": {
                    "tipo_recurso": tipo, "id_recurso": id_rec, "nombre": nombre.strip(", "),
                    "slot": slots[0],
                }}
    return {"sugerencia": None,
            "motivo": "Ningun equipo ni agente de la subarea tiene horario libre ese dia."}


# ── POST /ot/con-agenda — crear OT + ocupacion en una transaccion ────────────

@router.post("/con-agenda", status_code=201)
async def crear_ot_con_agenda(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Crea la OT y, en la misma transaccion, su ocupacion en la agenda.
    Body: {id_reclamo, tipo_recurso, id_recurso, fecha, hora_inicio, hora_fin,
    observaciones?}. El supervisor queda registrado en id_supervisor_asigna.
    Si la ocupacion entra en conflicto de horario, igual se crea (se reporta)."""
    _require_supervisor(current_user)
    for campo in ("id_reclamo", "tipo_recurso", "id_recurso", "fecha", "hora_inicio", "hora_fin"):
        if body.get(campo) in (None, ""):
            raise HTTPException(422, f"Campo requerido: {campo}")
    tipo_recurso = body["tipo_recurso"]
    if tipo_recurso not in ("agente", "equipo"):
        raise HTTPException(422, "tipo_recurso debe ser 'agente' o 'equipo'")

    id_reclamo = body["id_reclamo"]
    r = (await db.execute(text(
        "SELECT estado FROM reclamos WHERE id_reclamo = :id AND activo = TRUE"
    ), {"id": id_reclamo})).fetchone()
    if not r:
        raise HTTPException(404, f"Reclamo {id_reclamo} no encontrado")
    if r.estado in ("Cancelado", "Resuelto"):
        raise HTTPException(422, f"No se puede asignar OT a un reclamo {r.estado}")

    id_estado_en_gestion = await _id_estado_ot(db, "En gestión")
    uid = current_user["id_usuario"]
    id_recurso = body["id_recurso"]
    id_agente = id_recurso if tipo_recurso == "agente" else None
    id_equipo = id_recurso if tipo_recurso == "equipo" else None
    await _validar_scope_supervisor_ot(db, current_user, id_reclamo=id_reclamo,
                                       id_agente=id_agente, id_equipo=id_equipo)

    # asyncpg requiere objetos date/time, no strings. El body llega como dict crudo.
    try:
        f_ocup = date.fromisoformat(str(body["fecha"]))
        hi_ocup = time.fromisoformat(str(body["hora_inicio"]))
        hf_ocup = time.fromisoformat(str(body["hora_fin"]))
    except ValueError as e:
        raise HTTPException(422, f"Formato de fecha/hora invalido: {e}")
    if hf_ocup <= hi_ocup:
        raise HTTPException(422, "hora_fin debe ser mayor que hora_inicio")

    try:
        # 1. Crear la OT.
        row = (await db.execute(text("""
            INSERT INTO ordenes_trabajo
                (id_reclamo, id_estado, id_agente, id_equipo, es_auditoria,
                 id_supervisor_asigna, activo, fecha_alta, fecha_modificacion,
                 id_usuario_alta, id_usuario_modificacion)
            VALUES
                (:id_reclamo, :id_estado, :id_agente, :id_equipo, FALSE,
                 :uid, TRUE, NOW(), NOW(), :uid, :uid)
            RETURNING id_ot, nro_ot
        """), {
            "id_reclamo": id_reclamo, "id_estado": id_estado_en_gestion,
            "id_agente": id_agente, "id_equipo": id_equipo, "uid": uid,
        })).fetchone()
        id_ot = row.id_ot
        nro_ot = row.nro_ot or f"OT-{id_ot}"

        estado_ant = r.estado
        await db.execute(text("""
            UPDATE reclamos SET estado = 'En gestión', fecha_modificacion = NOW(),
                id_usuario_modificacion = :uid,
                fecha_primer_asignacion = COALESCE(fecha_primer_asignacion, NOW())
            WHERE id_reclamo = :id AND estado NOT IN ('Cancelado','Resuelto')
        """), {"id": id_reclamo, "uid": uid})
        await _insertar_historial_reclamo(db, id_reclamo, f"OT {nro_ot} generada",
                                           estado_ant, "En gestión",
                                           body.get("observaciones", ""), uid)

        # 2. Crear la ocupacion espejo en la agenda.
        ocup = (await db.execute(text("""
            INSERT INTO ocupaciones
                (tipo, tipo_recurso, id_recurso, fecha, hora_inicio, hora_fin,
                 id_orden_trabajo, id_municipio, activo, fecha_alta, fecha_modificacion,
                 id_usuario_alta, id_usuario_modificacion)
            VALUES
                ('ot', :tr, :ir, :f, :hi, :hf, :id_ot, :mun, TRUE, NOW(), NOW(), :uid, :uid)
            RETURNING id_ocupacion
        """), {
            "tr": tipo_recurso, "ir": id_recurso, "f": f_ocup,
            "hi": hi_ocup, "hf": hf_ocup, "id_ot": id_ot,
            "mun": body.get("id_municipio", 1), "uid": uid,
        })).fetchone()
        id_ocupacion = ocup.id_ocupacion

        # 3. Detectar conflictos de solapamiento con otras ocupaciones del recurso.
        conflictos = (await db.execute(text("""
            SELECT id_ocupacion, tipo, hora_inicio, hora_fin
            FROM ocupaciones
            WHERE activo = TRUE AND tipo_recurso = :tr AND id_recurso = :ir
              AND fecha = :f AND id_ocupacion <> :self
              AND hora_inicio < :hf AND hora_fin > :hi
        """), {
            "tr": tipo_recurso, "ir": id_recurso, "f": f_ocup,
            "self": id_ocupacion, "hi": hi_ocup, "hf": hf_ocup,
        })).mappings().all()

        await db.commit()
        # Hook push App Vecinos (etapa E) — post-commit, best-effort.
        await svc_push.notificar_estado_reclamo(id_reclamo)
        return {
            "id_ot": id_ot, "nro_ot": nro_ot, "id_reclamo": id_reclamo,
            "id_ocupacion": id_ocupacion,
            "conflictos": [dict(c) for c in conflictos],
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Error al crear OT con agenda: %s", e)
        raise HTTPException(400, str(e))


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
    _require_supervisor(current_user)
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

    await _validar_scope_supervisor_ot(db, current_user, id_reclamo=id_reclamo,
                                       id_agente=body.get("id_agente"),
                                       id_equipo=body.get("id_equipo"))
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
                id_usuario_modificacion = :uid,
                fecha_primer_asignacion = COALESCE(fecha_primer_asignacion, NOW())
            WHERE id_reclamo = :id AND estado NOT IN ('Cancelado','Resuelto')
        """), {"id": id_reclamo, "uid": current_user["id_usuario"]})

        await _insertar_historial_reclamo(db, id_reclamo, f"OT {nro_ot} generada",
                                           estado_ant, "En gestión",
                                           body.get("observaciones", ""),
                                           current_user["id_usuario"])
        await db.commit()

        # Hook push App Vecinos (etapa E) — post-commit, best-effort.
        await svc_push.notificar_estado_reclamo(id_reclamo)

        return {"id_ot": id_ot, "nro_ot": nro_ot, "id_reclamo": id_reclamo}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Error al crear OT: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


# ── PUT /ot/{id}/reasignar ────────────────────────────────────────────────────

@router.put("/{id_ot}/reasignar")
async def reasignar_ot(
    id_ot: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Supervisor reasigna una OT activa a otro agente o equipo. Requiere nota."""
    if current_user.get("nivel_acceso", 99) > 2:
        raise HTTPException(status_code=403, detail="Solo administrador o supervisor")

    nuevo_id_agente = body.get("id_agente")
    nuevo_id_equipo = body.get("id_equipo")
    nota = (body.get("nota") or "").strip()

    if not nuevo_id_agente and not nuevo_id_equipo:
        raise HTTPException(status_code=422, detail="Se requiere id_agente o id_equipo")
    if not nota:
        raise HTTPException(status_code=422, detail="Campo requerido: nota")

    r = await db.execute(text("""
        SELECT ot.id_reclamo, ot.id_agente, ot.id_equipo,
               eot.nombre AS estado_actual, eot.es_final,
               ag.apellido AS ag_apellido, ag.nombre AS ag_nombre,
               eq.nombre AS eq_nombre
        FROM ordenes_trabajo ot
        JOIN estado_ot eot ON eot.id_estado_ot = ot.id_estado
        LEFT JOIN agentes ag ON ag.id_agente = ot.id_agente
        LEFT JOIN equipos eq ON eq.id_equipo = ot.id_equipo
        WHERE ot.id_ot = :id AND ot.activo = TRUE
    """), {"id": id_ot})
    ot = r.fetchone()
    if not ot:
        raise HTTPException(status_code=404, detail=f"OT {id_ot} no encontrada")
    if ot.es_final:
        raise HTTPException(status_code=422, detail=f"OT en estado final ({ot.estado_actual}) no se puede reasignar")

    await _validar_scope_supervisor_ot(db, current_user, id_reclamo=ot.id_reclamo,
                                       id_agente=nuevo_id_agente,
                                       id_equipo=nuevo_id_equipo)
    asignado_antes = (
        f"agente {ot.ag_apellido}, {ot.ag_nombre}" if ot.id_agente
        else (f"equipo {ot.eq_nombre}" if ot.id_equipo else "sin asignar")
    )

    await db.execute(text("""
        UPDATE ordenes_trabajo
        SET id_agente = :id_agente,
            id_equipo = :id_equipo,
            fecha_modificacion = NOW(),
            id_usuario_modificacion = :uid
        WHERE id_ot = :id
    """), {
        "id_agente": nuevo_id_agente, "id_equipo": nuevo_id_equipo,
        "id": id_ot, "uid": current_user["id_usuario"],
    })

    # nombre nuevo destinatario
    if nuevo_id_agente:
        rn = await db.execute(text("SELECT apellido, nombre FROM agentes WHERE id_agente = :id"), {"id": nuevo_id_agente})
        a = rn.fetchone()
        asignado_despues = f"agente {a.apellido}, {a.nombre}" if a else f"agente #{nuevo_id_agente}"
    else:
        rn = await db.execute(text("SELECT nombre FROM equipos WHERE id_equipo = :id"), {"id": nuevo_id_equipo})
        e = rn.fetchone()
        asignado_despues = f"equipo {e.nombre}" if e else f"equipo #{nuevo_id_equipo}"

    await _insertar_historial_reclamo(
        db, ot.id_reclamo,
        f"OT reasignada",
        ot.estado_actual, ot.estado_actual,
        f"Reasignada de {asignado_antes} → {asignado_despues}. {nota}",
        current_user["id_usuario"]
    )
    await db.commit()
    return {"ok": True, "id_ot": id_ot, "asignado_a": asignado_despues}


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

    # Guard de nivel: tomar una OT es operar (nivel ≤ 4, incluye Gestión mig 92).
    # El Consultor (5) no opera.
    if current_user.get("nivel_acceso", 99) > 4:
        raise HTTPException(status_code=403,
            detail="No tenés permisos para tomar OTs (requiere nivel Gestión o superior).")

    # Identidad: un agente solo puede tomar una OT PARA SÍ MISMO. Admin/supervisor
    # (nivel ≤ 2) pueden tomar en nombre de otro agente (delegación). Sin esto, el
    # id_agente del body permitía tomar OTs en nombre de cualquiera vía API
    # (guard_nivel_endpoint_no_solo_ui).
    if current_user.get("nivel_acceso", 99) > 2:
        id_agente_propio = await _resolver_id_agente_por_usuario(db, current_user["id_usuario"])
        if id_agente_propio is None:
            raise HTTPException(status_code=404,
                detail="Tu usuario no está vinculado a ningún agente activo.")
        if int(id_agente) != int(id_agente_propio):
            raise HTTPException(status_code=403,
                detail="Solo podés tomar una OT para vos mismo.")

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
    # Guard de nivel: cambiar el estado de una OT es operar (nivel ≤ 4, incluye
    # Gestión mig 92). El Consultor (5) no opera (guard_nivel_endpoint_no_solo_ui).
    if current_user.get("nivel_acceso", 99) > 4:
        raise HTTPException(status_code=403,
            detail="No tenés permisos para cambiar el estado de OTs (requiere nivel Gestión o superior).")

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

    # Validación del grafo FSM de la OT: no permitir saltos arbitrarios (ej.
    # reactivar una OT Terminada). No-op (mismo estado) se acepta sin chequear.
    if nuevo_estado != ot.estado_actual:
        permitidos = TRANSICIONES_OT.get(ot.estado_actual, set())
        if nuevo_estado not in permitidos:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Transición de OT no permitida: '{ot.estado_actual}' → '{nuevo_estado}'. "
                    f"Desde '{ot.estado_actual}' solo se puede pasar a: "
                    f"{sorted(permitidos) if permitidos else 'ningún estado (es final)'}."
                ),
            )

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

        # Hook encuestas tras el commit. Solo si el cierre operativo resolvió el
        # reclamo (no si pasó a 'En auditoría' por audit=true — el service lo filtra).
        if nuevo_estado == "Terminada" and not ot.es_auditoria:
            await _disparar_encuesta(db, ot.id_reclamo)
            # Hook push App Vecinos (etapa E) — el reclamo cambió de estado
            # (Resuelto o En auditoría según audit del tipo). Best-effort.
            await svc_push.notificar_estado_reclamo(ot.id_reclamo)

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
            fecha_cierre = NOW(),
            id_usuario_modificacion = :uid
        WHERE id_reclamo = :id
    """), {"id": id_reclamo, "uid": id_usuario})
    await _insertar_historial_reclamo(db, id_reclamo, "Reclamo resuelto",
                                       estado_ant, "Resuelto", "OT cerrada sin auditoría", id_usuario)

    # Si este reclamo es un subreclamo, desbloquear el padre 'En espera' cuando ya
    # no quedan hermanos vivos. Import local para evitar acoplamiento de módulo
    # (reclamos.py y ordenes_trabajo.py solo se cruzan acá). Misma transacción que
    # el cierre — el caller commitea.
    from app.api.routes.reclamos import desbloquear_padre_si_corresponde
    await desbloquear_padre_si_corresponde(db, id_reclamo, id_usuario)


async def _disparar_encuesta(db: AsyncSession, id_reclamo: int):
    """Hook encuestas — disparo no-bloqueante (§42). Se llama DESPUÉS del commit
    que cierra el reclamo. El service valida internamente que el reclamo esté en
    'Resuelto' (devuelve MOTIVO_NO_RESUELTO si no), así que es seguro llamarlo tras
    cualquier cierre de OT: si el reclamo quedó en 'En auditoría' no crea nada.
    Si encuestas falla, NO debe afectar el resultado del endpoint."""
    try:
        envio, _motivo = await svc_encuestas.crear_envio_para_reclamo(db, id_reclamo)
        if envio:
            logger.info("Encuesta CSAT creada (id_envio=%s) para reclamo %s",
                        envio["id_encuesta_envio"], id_reclamo)
    except Exception as e:
        logger.warning("No se pudo crear envío de encuesta para reclamo %s: %s",
                       id_reclamo, e)
        # NO re-raise — el cierre del reclamo ya pasó, encuestas es accesorio


# ── PUT /ot/{id}/aprobar ──────────────────────────────────────────────────────

@router.put("/{id_ot}/aprobar")
async def aprobar_ot(
    id_ot: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # Guard: solo auditor (o admin) resuelve auditorías. Sin esto, cualquier
    # agente autenticado (incluido Consultor read-only) cerraba reclamos ajenos
    # y disparaba la encuesta CSAT. Espeja el check de mesa_auditor_me.
    _id_agente = await _resolver_id_agente_por_usuario(db, current_user["id_usuario"])
    _es_admin = (current_user.get("nivel_acceso") or 99) <= 1
    if not _es_admin and (_id_agente is None or not await _verificar_es_auditor(db, _id_agente)):
        raise HTTPException(status_code=403, detail="No tenés permisos de auditor.")

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

        # Hook encuestas tras el commit — la aprobación siempre resuelve el reclamo.
        await _disparar_encuesta(db, ot.id_reclamo)
        # Hook push App Vecinos (etapa E) — reclamo pasó a Resuelto. Best-effort.
        await svc_push.notificar_estado_reclamo(ot.id_reclamo)

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
    # Guard: solo auditor (o admin) rechaza auditorías. Sin esto, cualquier
    # agente autenticado reabría reclamos ajenos generando retrabajo espurio.
    _id_agente = await _resolver_id_agente_por_usuario(db, current_user["id_usuario"])
    _es_admin = (current_user.get("nivel_acceso") or 99) <= 1
    if not _es_admin and (_id_agente is None or not await _verificar_es_auditor(db, _id_agente)):
        raise HTTPException(status_code=403, detail="No tenés permisos de auditor.")

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
        # Hook push App Vecinos (etapa E) — reclamo volvió a En gestión. Best-effort.
        await svc_push.notificar_estado_reclamo(ot.id_reclamo)
        return {"ok": True, "id_ot": id_ot, "resultado": "rechazada"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Error al rechazar OT: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
