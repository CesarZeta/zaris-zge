"""
ZARIS API — Endpoints del módulo Reclamos (v1.2).
Prefijo: /api/v1/reclamos/
"""
import logging
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user
from app.services import encuestas_service as svc_encuestas
from app.services import notificaciones as svc_notif
from app.services import push as svc_push
from app.services.autoasignacion import autoasignar_reclamo
from app.services.tramites.auth import resolver_agente_desde_usuario
from app.api.routes.geo import localidad_desde_coords

router = APIRouter(prefix="/api/v1/reclamos", tags=["Reclamos"])
logger = logging.getLogger("zaris.reclamos")

ESTADOS_VALIDOS = {"Sin asignar", "En gestión", "En espera", "En auditoría", "Resuelto", "Cancelado", "Auditado"}

# Auditoría POSTERIOR al cierre (mig 112, PLAN_AUDITORIA_RECLAMOS.md): 'En auditoría'
# es un reclamo Resuelto reabierto para que lo revise un auditor; 'Auditado' es el
# cierre de esa revisión (aprobado | observado). Ninguno reabre la gestión: fecha_cierre
# no cambia y los tiempos se miden hasta el primer cierre. Se entra por
# POST /{id}/auditoria y se sale por PUT /ot/{id}/aprobar | /observar — nunca por /estado.
ESTADOS_AUDITORIA = {"En auditoría", "Auditado"}
# Estados que NO admiten gestión (editar, OT, subreclamo, aviso al supervisor).
ESTADOS_CERRADOS = {"Resuelto", "Cancelado", "En auditoría", "Auditado"}
# «Ver pendientes» del listado (decisión de César 2026-10-20): la gestión abierta
# más 'En auditoría', que todavía espera al auditor.
ESTADOS_PENDIENTES = ["Sin asignar", "En gestión", "En espera", "En auditoría"]

# Grafo de transiciones permitidas del ciclo de vida del reclamo (CLAUDE.md §18).
# Flujo nominal: Sin asignar -> En gestión -> (En espera) -> Resuelto.
# - "Cancelado" es alcanzable desde cualquier estado vivo (vía PUT /cancelar, no por acá,
#   pero lo dejamos permitido para no romper si llega por /estado).
# - "En gestión" <-> "En espera" es bidireccional: un reclamo en espera (subreclamo,
#   insumos, etc.) puede volver a gestión cuando se desbloquea.
# - "Resuelto" y "Cancelado" son finales para la gestión: no salen por acá (se reabre
#   creando OT/subreclamo, no por cambio directo de estado). Desde 'Resuelto' solo se
#   sale a 'En auditoría' por POST /{id}/auditoria (mig 112).
# - "En auditoría" y "Auditado" no salen por /estado: la auditoría la cierra el auditor.
TRANSICIONES_PERMITIDAS: dict[str, set[str]] = {
    "Sin asignar":  {"En gestión", "Cancelado"},
    "En gestión":   {"En espera", "Resuelto", "Cancelado"},
    "En espera":    {"En gestión", "Cancelado"},
    "En auditoría": set(),
    "Auditado":     set(),
    "Resuelto":     set(),
    "Cancelado":    set(),
}

# Niveles (mig 92): 1=Admin, 2=Supervisor, 3=Atención (ve todo, crea/edita),
# 4=Gestión (agente de OT, scopeado a su subárea), 5=Consultor (solo lectura).
NIVELES_GESTION = {1, 2, 3}  # crear/editar reclamos: Admin, Supervisor, Atención
NIVELES_AVISO = {1, 2, 3, 4}  # avisar al supervisor: también Gestión
# Niveles cuyo LISTADO de reclamos queda scopeado a la subárea de su agente
# (Fase 3 roles — Atención ve todo para consultas de vecinos; admin ve todo).
NIVELES_SCOPE_SUBAREA = {2, 4}


def _require_gestion(current_user: dict):
    if current_user.get("nivel_acceso") not in NIVELES_GESTION:
        raise HTTPException(status_code=403,
            detail="No tenés permisos para esta acción (requiere nivel Operador o superior)")


NIVELES_SUPERVISOR = {1, 2}  # Admin, Supervisor


def _require_supervisor(current_user: dict):
    """Acciones que cambian el ESTADO de un reclamo (cambiar estado, cancelar,
    desglosar en subreclamo) son exclusivas de Supervisión (CLAUDE.md §30).

    El operador (nivel 3 / Atención) genera y consulta reclamos, edita datos y
    deja observaciones, pero NO cambia su estado: toma nota o avisa al supervisor
    para que lo haga. La gestión del reclamo es Órdenes de Trabajo (supervisor).
    El guard de UI (sidebar/botones) NO alcanza — esto cierra la vía por curl
    (trampa recurrente §30: ocultar en UI ≠ proteger el endpoint).
    """
    if current_user.get("nivel_acceso") not in NIVELES_SUPERVISOR:
        raise HTTPException(
            status_code=403,
            detail="Cambiar el estado de un reclamo requiere nivel Supervisor o "
                   "Administrador. Tomá nota o avisá a tu supervisor para que lo gestione.",
        )


async def _validar_cierre_directo_sin_ot(db, id_reclamo: int, id_tipo_reclamo, current_user: dict):
    """Reglas para resolver un reclamo 'Sin asignar' sin generar OT:

    1. El usuario debe ser supervisor (nivel ≤ 2; admin nivel 1 incluido).
    2. El reclamo no debe tener una OT activa (coherencia: si tiene OT, debe
       seguir el flujo normal de gestión/auditoría).
    3. La subárea del usuario debe coincidir con la subárea del tipo de reclamo.
    """
    if current_user.get("nivel_acceso") not in NIVELES_SUPERVISOR:
        raise HTTPException(
            status_code=403,
            detail="Resolver un reclamo sin OT requiere nivel Supervisor o Administrador.",
        )

    # No debe existir OT activa para este reclamo.
    ot = await db.execute(text(
        "SELECT 1 FROM ordenes_trabajo WHERE id_reclamo = :id AND activo = TRUE LIMIT 1"
    ), {"id": id_reclamo})
    if ot.fetchone():
        raise HTTPException(
            status_code=422,
            detail="El reclamo ya tiene una OT asignada; no puede resolverse por cierre directo.",
        )

    # Subárea del tipo de reclamo (fuente única; reclamos.id_subarea puede ser NULL).
    sub_tipo = None
    if id_tipo_reclamo is not None:
        rt = await db.execute(text(
            "SELECT id_subarea FROM tipo_reclamo WHERE id_tipo_reclamo = :id"
        ), {"id": id_tipo_reclamo})
        rtr = rt.fetchone()
        sub_tipo = rtr.id_subarea if rtr else None

    if sub_tipo is None:
        raise HTTPException(
            status_code=422,
            detail="El tipo de reclamo no tiene subárea asociada; no se puede validar el cierre directo.",
        )

    # Subárea del usuario logueado: la de su AGENTE (regla 1:1 §3/§39), no
    # usuarios.id_subarea, que estaba desalineada en 75/93 cuentas (2026-10-21).
    perfil = await resolver_agente_desde_usuario(current_user["id_usuario"], db)
    sub_usuario = perfil.get("id_subarea") if perfil else None

    if sub_usuario is None or sub_usuario != sub_tipo:
        raise HTTPException(
            status_code=403,
            detail="Solo un supervisor de la misma subárea del reclamo puede resolverlo sin OT.",
        )


async def _require_misma_subarea(db, id_tipo_reclamo, current_user: dict, accion: str):
    """Impide el cierre cross-subárea por la vía manual del FSM.

    Un usuario solo puede llevar un reclamo a 'Resuelto' si la subárea de su
    agente (regla 1:1, §3) coincide con la subárea del tipo de reclamo
    (fuente única; `reclamos.id_subarea` puede ser NULL — §27). El admin
    (nivel 1) está exento (acceso total). El cierre vía OT no pasa por acá:
    el endpoint de OT actualiza `reclamos.estado` directamente, y el agente que
    cierra ya pertenece a la subárea por construcción.
    """
    if current_user.get("nivel_acceso") == 1:  # admin: acceso total
        return

    sub_tipo = None
    if id_tipo_reclamo is not None:
        rt = await db.execute(text(
            "SELECT id_subarea FROM tipo_reclamo WHERE id_tipo_reclamo = :id"
        ), {"id": id_tipo_reclamo})
        rtr = rt.fetchone()
        sub_tipo = rtr.id_subarea if rtr else None

    if sub_tipo is None:
        raise HTTPException(
            status_code=422,
            detail=f"El tipo de reclamo no tiene subárea asociada; no se puede validar el pase a '{accion}'.",
        )

    perfil = await resolver_agente_desde_usuario(current_user["id_usuario"], db)
    sub_usuario = perfil.get("id_subarea") if perfil else None

    if sub_usuario is None or sub_usuario != sub_tipo:
        raise HTTPException(
            status_code=403,
            detail=f"Solo un usuario de la misma subárea del reclamo puede pasarlo a '{accion}'.",
        )


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


async def _subarea_scope_listado(db: AsyncSession, current_user: dict) -> Optional[int]:
    """Fase 3 roles: Supervisor (2) y Gestión (4) ven el LISTADO de reclamos
    scopeado a la subárea de su agente vinculado. Devuelve esa id_subarea, o
    None si el nivel no scopea (1 admin, 3 atención, 5 consultor). El DETALLE
    por id queda sin scope a propósito (subreclamos cross-área, consultas por
    número). Si el usuario scopeado no tiene agente/subárea → 403 accionable."""
    if current_user.get("nivel_acceso") not in NIVELES_SCOPE_SUBAREA:
        return None
    perfil = await resolver_agente_desde_usuario(current_user["id_usuario"], db)
    if not perfil or not perfil.get("id_subarea"):
        raise HTTPException(
            status_code=403,
            detail="Tu usuario no tiene una subárea asignada en su perfil de agente. "
                   "Pedile a un administrador que la configure desde Maestros → Usuarios.",
        )
    return perfil["id_subarea"]


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


async def desbloquear_padre_si_corresponde(db: AsyncSession, id_hijo: int, id_usuario: int):
    """Devuelve el reclamo padre de 'En espera' a 'En gestión' cuando se cierra el
    último subreclamo vivo.

    Se llama tras cerrar un hijo (Resuelto/Cancelado) por cualquiera de las 3 vías:
    cambio manual de estado, cancelación, o cierre vía OT. Si el reclamo recibido no
    es subreclamo, o el padre no está 'En espera', o todavía quedan hermanos vivos,
    no hace nada. NO commitea: lo hace el caller dentro de su misma transacción.
    """
    fila = (await db.execute(text(
        "SELECT id_reclamo_padre FROM reclamos WHERE id_reclamo = :id AND activo = TRUE"
    ), {"id": id_hijo})).fetchone()
    if not fila or fila.id_reclamo_padre is None:
        return  # no es subreclamo
    id_padre = fila.id_reclamo_padre

    padre = (await db.execute(text(
        "SELECT estado FROM reclamos WHERE id_reclamo = :id AND activo = TRUE"
    ), {"id": id_padre})).fetchone()
    if not padre or padre.estado != "En espera":
        return  # el padre no está esperando este desbloqueo

    # ¿Quedan hermanos vivos (no resueltos ni cancelados)?
    vivos = (await db.execute(text("""
        SELECT 1 FROM reclamos
        WHERE id_reclamo_padre = :id_padre AND activo = TRUE
          AND estado NOT IN ('Resuelto', 'Cancelado', 'En auditoría', 'Auditado')
        LIMIT 1
    """), {"id_padre": id_padre})).fetchone()
    if vivos:
        return  # todavía hay subreclamos abiertos

    await db.execute(text("""
        UPDATE reclamos SET estado = 'En gestión', fecha_modificacion = NOW(),
            id_usuario_modificacion = :uid
        WHERE id_reclamo = :id AND estado = 'En espera'
    """), {"id": id_padre, "uid": id_usuario})
    await _insertar_historial(
        db, id_padre, "Reclamo reactivado",
        "En espera", "En gestión",
        "Todos los subreclamos fueron resueltos o cancelados", id_usuario,
    )


# ── Tomar / resolver desde Reclamos (César 2026-10-21) ──────────────────────
# En un municipio chico el agente de Gestión (4) se autogestiona: entra a
# Reclamos, toma los pendientes de su gestión y los resuelve escribiendo la
# resolución que ve el vecino. El supervisor (2) también toma y resuelve desde
# acá. Gestión = la del AGENTE (§3). El admin (1) opera sobre cualquiera.
NIVELES_TOMAN = {1, 2, 4}


async def _subarea_tipo(db: AsyncSession, id_tipo_reclamo) -> Optional[int]:
    if id_tipo_reclamo is None:
        return None
    return await db.scalar(text(
        "SELECT id_subarea FROM tipo_reclamo WHERE id_tipo_reclamo = :t"), {"t": id_tipo_reclamo})


async def _ots_operativas_abiertas(db: AsyncSession, id_reclamo: int) -> list:
    return (await db.execute(text("""
        SELECT ot.id_ot, ot.nro_ot, ot.id_agente, ot.id_equipo, eo.nombre AS estado
        FROM ordenes_trabajo ot
        JOIN estado_ot eo ON eo.id_estado_ot = ot.id_estado
        WHERE ot.id_reclamo = :id AND ot.activo = TRUE AND NOT ot.es_auditoria
          AND NOT eo.es_final
        ORDER BY ot.id_ot
    """), {"id": id_reclamo})).fetchall()


async def _acciones_reclamo(db: AsyncSession, r, current_user: dict) -> dict:
    """Qué puede hacer el usuario con este reclamo desde Reclamos: `tomar` y
    `resolver`, con el motivo si no. Las mismas reglas que imponen los endpoints
    (la UI solo las refleja). `r` trae estado, id_tipo_reclamo e id_reclamo."""
    nivel = current_user.get("nivel_acceso", 99)
    if nivel not in NIVELES_TOMAN:
        return {"tomar": False, "resolver": False}
    perfil = await resolver_agente_desde_usuario(current_user["id_usuario"], db)
    mi_agente = perfil.get("id_agente") if perfil else None
    mi_sub = perfil.get("id_subarea") if perfil else None
    sub_tipo = await _subarea_tipo(db, r.id_tipo_reclamo)
    misma_gestion = nivel == 1 or (mi_sub is not None and mi_sub == sub_tipo)
    ots = await _ots_operativas_abiertas(db, r.id_reclamo)

    tomar = (r.estado == "Sin asignar" and not ots and mi_agente is not None and misma_gestion)

    resolver = False
    if r.estado == "Sin asignar" and not ots:
        # Cierre directo sin OT: supervisión de la gestión (o admin).
        resolver = nivel in (1, 2) and misma_gestion
    elif r.estado == "En gestión":
        if nivel in (1, 2):
            resolver = misma_gestion
        elif mi_agente is not None and ots:
            mis_equipos = {x.id_equipo for x in (await db.execute(text(
                "SELECT id_equipo FROM equipo_agentes WHERE id_agente = :a AND activo = TRUE"),
                {"a": mi_agente})).fetchall()}
            resolver = any(o.id_agente == mi_agente or (o.id_agente is None and o.id_equipo in mis_equipos)
                           for o in ots)
    return {"tomar": tomar, "resolver": resolver}


async def _terminar_ots_operativas(db: AsyncSession, id_reclamo: int,
                                   resolucion: Optional[str], id_usuario: int) -> None:
    """Al resolver el reclamo, sus OT operativas abiertas pasan a Terminada (antes
    el reclamo podía quedar Resuelto con la OT 'En gestión'). NO commitea."""
    await db.execute(text("""
        UPDATE ordenes_trabajo ot
        SET id_estado = (SELECT id_estado_ot FROM estado_ot WHERE nombre = 'Terminada' AND activo = TRUE LIMIT 1),
            fecha_cierre = NOW(), fecha_modificacion = NOW(),
            observaciones = COALESCE(:res, ot.observaciones),
            id_usuario_modificacion = :uid
        WHERE ot.id_reclamo = :id AND ot.activo = TRUE AND NOT ot.es_auditoria
          AND ot.id_estado IN (SELECT id_estado_ot FROM estado_ot WHERE NOT es_final)
    """), {"id": id_reclamo, "res": resolucion, "uid": id_usuario})


# ── GET /reclamos/stats ──────────────────────────────────────────────────────

@router.get("/stats")
async def stats_reclamos(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # Mismo scope que el listado (Fase 3): Supervisor/Gestión cuentan solo su
    # subárea (derivada del tipo, §27); Atención/Admin cuentan todo.
    sub_scope = await _subarea_scope_listado(db, current_user)
    if sub_scope is not None:
        result = await db.execute(text("""
            SELECT r.estado, COUNT(*) AS total
            FROM reclamos r
            JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
            WHERE r.activo = TRUE AND tr.id_subarea = :sub
            GROUP BY r.estado
        """), {"sub": sub_scope})
    else:
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


# ── GET /reclamos/catalogo/subareas ──────────────────────────────────────────

@router.get("/catalogo/subareas")
async def catalogo_subareas(
    id_area: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    cond = ["s.activo = TRUE"]
    params: dict = {}
    if id_area:
        cond.append("s.id_area = :id_area")
        params["id_area"] = id_area
    result = await db.execute(text(f"""
        SELECT s.id_subarea, s.nombre, s.id_area, a.nombre AS area_nombre
        FROM subarea s
        LEFT JOIN area a ON a.id_area = s.id_area
        WHERE {' AND '.join(cond)}
        ORDER BY s.nombre
    """), params)
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

# Columnas por las que se puede ordenar el listado (lista cerrada: el valor va
# interpolado en el ORDER BY, nunca el texto del query param).
_ORDEN_LISTADO = {
    "nro": "r.id_reclamo",
    "fecha": "r.fecha_alta",
    "estado": "r.estado",
    "prioridad": "CASE r.prioridad WHEN 'Alta' THEN 1 WHEN 'Media' THEN 2 WHEN 'Baja' THEN 3 END",
    "ciudadano": "lower(c.apellido || ' ' || c.nombre)",
    "tipo": "lower(tr.nombre)",
    "subarea": "lower(s.nombre)",
    "area": "lower(a.nombre)",
    "agente": "lower(u.nombre)",
}

@router.get("")
async def listar_reclamos(
    estado: Optional[str] = Query(None),
    id_area: Optional[int] = Query(None),
    id_subarea: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    texto: Optional[str] = Query(None),
    pendientes: bool = Query(
        False,
        description="Solo los pendientes de resolver (Sin asignar, En gestión, En espera, "
                    "En auditoría), del más antiguo al más nuevo. Se combina con los demás filtros.",
    ),
    orden: Optional[str] = Query(
        None,
        description="Columna de orden: " + ", ".join(sorted(_ORDEN_LISTADO)) +
                    ". Sin valor: fecha de alta (los pendientes, del más antiguo al más nuevo).",
    ),
    dir: str = Query("asc", pattern="^(asc|desc)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    conds = ["r.activo = TRUE"]
    params: dict = {}
    # El orden se resuelve ACÁ y no en pantalla: el listado tiene tope (limit) y
    # ordenar solo lo cargado escondería filas (2026-10-20: el reclamo del día
    # quedaba en la fila 192 de «Ver pendientes» sin forma de traerlo arriba).
    if orden:
        if orden not in _ORDEN_LISTADO:
            raise HTTPException(422, f"orden inválido: {orden}")
        sentido = "DESC" if dir == "desc" else "ASC"
        orden_sql = f"{_ORDEN_LISTADO[orden]} {sentido} NULLS LAST, r.id_reclamo {sentido}"
    else:
        orden_sql = "r.fecha_alta ASC" if pendientes else "r.fecha_alta DESC"

    # Supervisor (2) y Gestión (4): el backend fuerza la subárea de su agente
    # y pisa cualquier filtro que venga por query (Fase 3 roles).
    sub_scope = await _subarea_scope_listado(db, current_user)
    if sub_scope is not None:
        id_subarea = sub_scope
        id_area = None

    if estado:
        conds.append("r.estado = :estado")
        params["estado"] = estado
    if pendientes:
        conds.append("r.estado = ANY(:estados_pendientes)")
        params["estados_pendientes"] = ESTADOS_PENDIENTES
    if id_area:
        # Fuente unica del area: s.id_area derivada del tipo (mig 27). r.id_area
        # puede estar NULL en reclamos viejos. Ver feedback_area_via_subarea_no_via_r_id_area.
        conds.append("s.id_area = :id_area")
        params["id_area"] = id_area
    if id_subarea:
        # Subárea fuente única: tr.id_subarea derivada del tipo (§27). r.id_subarea
        # puede estar NULL en reclamos viejos.
        conds.append("tr.id_subarea = :id_subarea")
        params["id_subarea"] = id_subarea
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
            r.fecha_alta, r.fecha_modificacion, r.fecha_cierre,
            r.id_reclamo_padre,
            r.resultado_auditoria, r.id_reclamo_origen_auditoria,
            r.latitud, r.longitud,
            r.id_ciudadano, c.nombre AS ciudadano_nombre, c.apellido AS ciudadano_apellido, c.doc_nro,
            r.id_tipo_reclamo, tr.nombre AS tipo_nombre, tr.sla_dias, tr.audit AS tipo_audit,
            s.id_area, a.nombre AS area_nombre,
            tr.id_subarea, s.nombre AS subarea_nombre,
            r.id_agente_asignado,
            COALESCE(u.nombre, '—') AS agente_nombre
        FROM reclamos r
        LEFT JOIN ciudadanos c ON c.id_ciudadano = r.id_ciudadano
        LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
        LEFT JOIN subarea s ON s.id_subarea = tr.id_subarea
        LEFT JOIN area a ON a.id_area = s.id_area
        LEFT JOIN usuarios u ON u.id_usuario = r.id_agente_asignado
        WHERE {where}
        ORDER BY {orden_sql}
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
            r.descripcion, r.domicilio_reclamo, r.direccion, r.observaciones, r.resolucion,
            r.fecha_alta, r.fecha_modificacion,
            r.fecha_primer_asignacion, r.fecha_cierre, r.sla_vencimiento,
            r.fecha_inicio_auditoria, r.fecha_fin_auditoria, r.resultado_auditoria,
            r.id_reclamo_origen_auditoria, ro.nro_reclamo AS origen_auditoria_nro,
            rt.id_reclamo AS retrabajo_auditoria_id, rt.nro_reclamo AS retrabajo_auditoria_nro,
            rt.estado AS retrabajo_auditoria_estado,
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
            tr.id_subarea, s.nombre AS subarea_nombre,
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
        -- Auditoría posterior (mig 112): el reclamo auditado del que nace este
        -- retrabajo, y el retrabajo que nació de la auditoría observada de este.
        LEFT JOIN reclamos ro ON ro.id_reclamo = r.id_reclamo_origen_auditoria
        LEFT JOIN reclamos rt ON rt.id_reclamo_origen_auditoria = r.id_reclamo AND rt.activo = TRUE
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
               ot.fecha_creacion, ot.fecha_cierre, ot.observaciones, ot.id_agente, ot.id_equipo,
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

    # Botones Tomar / Resolver del detalle (2026-10-21): mismas reglas que los endpoints.
    d["acciones"] = await _acciones_reclamo(db, row, current_user)

    return d


# ── POST /reclamos — crear reclamo ───────────────────────────────────────────

@router.post("", status_code=201, responses={
    201: {"description": "Reclamo creado. Si su gestión tiene asignación automática (mig 114), "
                         "la OT se asigna y agenda sola después de responder."}})
async def crear_reclamo(
    body: dict,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # Crear reclamos es Atención/Supervisión/Admin (niveles 1-3). Gestión (4)
    # trabaja OTs y Consultor (5) solo lee. Cazado 2026-07-02: este POST no
    # tenía guard de nivel (cualquier autenticado creaba).
    _require_gestion(current_user)
    # id_tipo_reclamo obligatorio (cazado 2026-07-02): un reclamo sin tipo no
    # tiene subárea → queda fuera del scoping del supervisor y del ruteo del
    # aviso (Fase 3). El form React ya lo exige; esto cierra la vía por API.
    for f in ["id_ciudadano", "descripcion", "id_tipo_reclamo"]:
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

    # Derivación automática de localidad (2026-08-30): si vienen coordenadas y no
    # vino id_localidad, matchear contra el catálogo (best-effort, nunca falla).
    if data["id_localidad"] is None and data["latitud"] is not None and data["longitud"] is not None:
        loc = await localidad_desde_coords(db, data["latitud"], data["longitud"])
        if loc:
            data["id_localidad"] = loc["id_localidad"]

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
        # Gestión con asignación automática (mig 114): se asigna solo, después de responder.
        background_tasks.add_task(autoasignar_reclamo, id_reclamo)

        return {"id_reclamo": id_reclamo, "nro_reclamo": nro_reclamo, "estado": "Sin asignar"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Error al crear reclamo: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


# ── PUT /reclamos/{id}/estado — cambiar estado ───────────────────────────────

@router.put("/{id_reclamo}/estado", responses={403: {
    "description": "Pase a Resuelto de un reclamo de otra gestión (se compara con la gestión del agente del usuario)"}})
async def cambiar_estado(
    id_reclamo: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _require_supervisor(current_user)  # cambio de estado = supervisión (§30)

    nuevo_estado = body.get("estado")
    if not nuevo_estado:
        raise HTTPException(status_code=422, detail="Campo 'estado' requerido")

    # Cancelar tiene su propio endpoint (PUT /{id}/cancelar) que exige motivo y
    # hace cascade a las OTs activas. Por /estado se colaba un cancelar SIN motivo
    # (puerta de atrás). Redirigir.
    if nuevo_estado == "Cancelado":
        raise HTTPException(status_code=422,
            detail="Para cancelar un reclamo usá el endpoint dedicado (requiere motivo).")
    # Auditoría posterior al cierre (mig 112): se entra por POST /{id}/auditoria y
    # la cierra el auditor desde su mesa (aprobar/observar). Por /estado no.
    if nuevo_estado in ESTADOS_AUDITORIA:
        raise HTTPException(status_code=422,
            detail="La auditoría no se maneja por cambio de estado: un supervisor envía "
                   "el reclamo Resuelto a auditoría y el auditor la cierra desde su mesa.")

    estados_validos = await _estados_desde_db(db)
    if nuevo_estado not in estados_validos:
        raise HTTPException(status_code=422, detail=f"Estado inválido: {nuevo_estado}")

    r = await db.execute(text(
        "SELECT estado, id_reclamo_padre, id_tipo_reclamo FROM reclamos WHERE id_reclamo = :id AND activo = TRUE"
    ), {"id": id_reclamo})
    row = r.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Reclamo {id_reclamo} no encontrado")

    estado_anterior = row.estado

    # Cierre directo sin OT: un reclamo "Sin asignar" (todavía sin OT) puede
    # resolverse directamente, SOLO por un supervisor (nivel ≤ 2) que pertenezca
    # a la misma subárea que el tipo de reclamo. No pasa por el grafo normal del
    # FSM (que solo permitiría 'En gestión'/'Cancelado' desde 'Sin asignar').
    es_cierre_directo = estado_anterior == "Sin asignar" and nuevo_estado == "Resuelto"
    if es_cierre_directo:
        await _validar_cierre_directo_sin_ot(db, id_reclamo, row.id_tipo_reclamo, current_user)

    # #3 — Validación secuencial del FSM: no permitir saltos no contemplados.
    # No-op (mismo estado) se acepta sin chequear el grafo.
    # El cierre directo ya fue validado arriba y queda exento del grafo.
    elif nuevo_estado != estado_anterior:
        permitidos = TRANSICIONES_PERMITIDAS.get(estado_anterior, set())
        if nuevo_estado not in permitidos:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Transición no permitida: '{estado_anterior}' → '{nuevo_estado}'. "
                    f"Desde '{estado_anterior}' solo se puede pasar a: "
                    f"{sorted(permitidos) if permitidos else 'ningún estado (es final)'}."
                ),
            )
        # Bloqueo de cierre cross-subárea por la vía manual del FSM: un no-admin
        # solo puede llevar el reclamo a Resuelto si su subárea coincide con la del
        # tipo de reclamo. (El cierre vía OT no pasa por este endpoint — lo hace
        # ordenes_trabajo.py directamente.)
        if nuevo_estado == "Resuelto":
            await _require_misma_subarea(db, row.id_tipo_reclamo, current_user, nuevo_estado)

    # #1 — Integridad referencial padre/hijo: no cerrar un reclamo padre si tiene
    # subreclamos activos sin resolver. Solo aplica si NO es subreclamo.
    if nuevo_estado == "Resuelto" and row.id_reclamo_padre is None:
        hijos = await db.execute(text("""
            SELECT nro_reclamo, estado
            FROM reclamos
            WHERE id_reclamo_padre = :id AND activo = TRUE
              AND estado NOT IN ('Resuelto', 'Cancelado', 'En auditoría', 'Auditado')
            ORDER BY id_reclamo
        """), {"id": id_reclamo})
        pendientes = hijos.fetchall()
        if pendientes:
            detalle = ", ".join(f"{h.nro_reclamo} ({h.estado})" for h in pendientes)
            raise HTTPException(
                status_code=422,
                detail=(
                    f"No se puede pasar a '{nuevo_estado}': hay {len(pendientes)} "
                    f"subreclamo(s) sin resolver: {detalle}. "
                    "Resolvé o cancelá los subreclamos primero."
                ),
            )

    nota = body.get("nota", "")
    # Resolución (mig 117): la ve el vecino. La nota del cambio de estado es
    # interna y queda solo en el historial — hasta el 2026-10-21 PISABA las
    # observaciones del alta, que además le llegaban al vecino.
    resolucion = (body.get("resolucion") or "").strip() or None
    if resolucion and nuevo_estado != "Resuelto":
        raise HTTPException(status_code=422, detail="La resolución solo se escribe al pasar a 'Resuelto'.")
    if resolucion and len(resolucion) > 2000:
        raise HTTPException(status_code=422, detail="La resolución no puede superar los 2000 caracteres.")

    # fecha_cierre se setea al pasar a un estado final (§22). Para estados no
    # finales queda en NULL (CASE evita pisarla en transiciones intermedias).
    es_final = nuevo_estado in ("Resuelto", "Cancelado")
    # fecha_primer_asignacion se setea la primera vez que el reclamo entra a
    # 'En gestión' (medición real del SLA de primera asignación, §22). El COALESCE
    # evita pisarla si vuelve a 'En gestión' desde 'En espera'.
    es_primera_gestion = nuevo_estado == "En gestión"
    await db.execute(text("""
        UPDATE reclamos
        SET estado = :estado, fecha_modificacion = NOW(),
            resolucion = COALESCE(:res, resolucion),
            id_usuario_modificacion = :uid,
            fecha_cierre = CASE WHEN :es_final THEN NOW() ELSE fecha_cierre END,
            fecha_primer_asignacion = CASE WHEN :es_gestion
                THEN COALESCE(fecha_primer_asignacion, NOW()) ELSE fecha_primer_asignacion END
        WHERE id_reclamo = :id
    """), {"estado": nuevo_estado, "id": id_reclamo, "res": resolucion,
           "uid": current_user["id_usuario"], "es_final": es_final,
           "es_gestion": es_primera_gestion})

    if nuevo_estado == "Resuelto":
        await _terminar_ots_operativas(db, id_reclamo, resolucion, current_user["id_usuario"])

    await _insertar_historial(db, id_reclamo, f"Cambio de estado a {nuevo_estado}",
                               estado_anterior, nuevo_estado, resolucion or nota,
                               current_user["id_usuario"])

    # Si este reclamo es un subreclamo y acaba de cerrarse, desbloquear el padre
    # 'En espera' cuando ya no quedan hermanos vivos (misma transacción — integridad).
    if nuevo_estado in ("Resuelto", "Cancelado"):
        await desbloquear_padre_si_corresponde(db, id_reclamo, current_user["id_usuario"])

    await db.commit()

    # Hook encuestas — disparo no-bloqueante (§42). El cierre del reclamo ya commiteó;
    # si encuestas falla, NO debe afectar el resultado del endpoint. Solo al pasar a
    # 'Resuelto' (no en 'Cancelado' ni transiciones intermedias).
    if nuevo_estado == "Resuelto":
        try:
            envio, _motivo = await svc_encuestas.crear_envio_para_reclamo(db, id_reclamo)
            if envio:
                logger.info("Encuesta CSAT creada (id_envio=%s) para reclamo %s",
                            envio["id_encuesta_envio"], id_reclamo)
        except Exception as e:
            logger.warning("No se pudo crear envío de encuesta para reclamo %s: %s",
                           id_reclamo, e)
            # NO re-raise — el cierre del reclamo ya pasó, encuestas es accesorio

    # Hook push App Vecinos (etapa E) — post-commit, best-effort (nunca levanta).
    await svc_push.notificar_estado_reclamo(id_reclamo)

    return {"ok": True, "id_reclamo": id_reclamo, "estado": nuevo_estado}


# ── POST /reclamos/{id}/tomar — el agente/supervisor toma el reclamo ─────────

@router.post("/{id_reclamo}/tomar", status_code=201,
             responses={403: {"description": "Toman reclamos Gestión, Supervisor y Admin, de su propia gestión"},
                        409: {"description": "El reclamo ya no está sin asignar (otro lo tomó)"}})
async def tomar_reclamo(
    id_reclamo: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Crea la OT del reclamo a nombre de quien lo toma (su agente) y lo pasa a
    'En gestión'. Para municipios chicos donde el agente se autogestiona
    (César 2026-10-21). Gestión (4) y Supervisor (2) solo de su gestión."""
    from app.api.routes.ordenes_trabajo import _id_estado_ot, _validar_destinatario_ot

    if current_user.get("nivel_acceso") not in NIVELES_TOMAN:
        raise HTTPException(status_code=403,
            detail="Tomar reclamos es para agentes de Gestión, supervisores y administradores.")

    # Lock del reclamo: dos personas que toman a la vez no crean dos OT.
    r = (await db.execute(text("""
        SELECT id_reclamo, estado, id_tipo_reclamo, nro_reclamo
        FROM reclamos WHERE id_reclamo = :id AND activo = TRUE FOR UPDATE
    """), {"id": id_reclamo})).fetchone()
    if not r:
        raise HTTPException(status_code=404, detail=f"Reclamo {id_reclamo} no encontrado")
    acciones = await _acciones_reclamo(db, r, current_user)
    if not acciones["tomar"]:
        if r.estado != "Sin asignar" or await _ots_operativas_abiertas(db, id_reclamo):
            raise HTTPException(status_code=409, detail="Este reclamo ya fue tomado o no está sin asignar.")
        raise HTTPException(status_code=403,
            detail="Solo podés tomar reclamos de tu gestión (y necesitás un perfil de agente).")

    perfil = await resolver_agente_desde_usuario(current_user["id_usuario"], db)
    id_agente = perfil["id_agente"]
    await _validar_destinatario_ot(db, id_agente=id_agente)
    id_estado = await _id_estado_ot(db, "En gestión")
    ot = (await db.execute(text("""
        INSERT INTO ordenes_trabajo
            (id_reclamo, id_estado, id_agente, id_equipo, es_auditoria, asignacion_automatica,
             id_supervisor_asigna, activo, fecha_alta, fecha_modificacion,
             id_usuario_alta, id_usuario_modificacion)
        VALUES (:r, :e, :ag, NULL, FALSE, FALSE, :sup, TRUE, NOW(), NOW(), :uid, :uid)
        RETURNING id_ot, nro_ot
    """), {"r": id_reclamo, "e": id_estado, "ag": id_agente, "uid": current_user["id_usuario"],
           # Quien asigna es un supervisor/admin solo si el que toma lo es.
           "sup": current_user["id_usuario"] if current_user.get("nivel_acceso") in (1, 2) else None})).fetchone()
    nro_ot = ot.nro_ot or f"OT-{ot.id_ot}"
    await db.execute(text("""
        UPDATE reclamos SET estado = 'En gestión', fecha_modificacion = NOW(),
            id_usuario_modificacion = :uid,
            fecha_primer_asignacion = COALESCE(fecha_primer_asignacion, NOW())
        WHERE id_reclamo = :id
    """), {"id": id_reclamo, "uid": current_user["id_usuario"]})
    quien = (await db.execute(text(
        "SELECT apellido, nombre FROM agentes WHERE id_agente = :a"), {"a": id_agente})).fetchone()
    await _insertar_historial(db, id_reclamo, f"OT {nro_ot} generada",
                               r.estado, "En gestión",
                               f"Reclamo tomado por {quien.apellido}, {quien.nombre}" if quien else "Reclamo tomado",
                               current_user["id_usuario"])
    await db.commit()
    # El vecino se entera del cambio de estado; quien tomó no necesita aviso.
    await svc_push.notificar_estado_reclamo(id_reclamo)
    return {"ok": True, "id_reclamo": id_reclamo, "id_ot": ot.id_ot, "nro_ot": nro_ot}


# ── POST /reclamos/{id}/resolver — cerrar con la resolución que ve el vecino ─

@router.post("/{id_reclamo}/resolver",
             responses={403: {"description": "Resuelve quien tiene la OT, la supervisión de la gestión o el admin"},
                        422: {"description": "Falta la resolución, o hay subreclamos sin resolver"}})
async def resolver_reclamo(
    id_reclamo: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Resuelve el reclamo con un texto de resolución (obligatorio, lo ve el
    vecino en su app y en el aviso de cierre). Si tiene OT operativa abierta, la
    termina con ese texto; si está 'Sin asignar', es el cierre directo sin OT de
    la supervisión (§18). Dispara encuesta y aviso como cualquier cierre."""
    from app.api.routes.ordenes_trabajo import _disparar_encuesta, _resolver_reclamo

    resolucion = (body.get("resolucion") or "").strip()
    if len(resolucion) < 5:
        raise HTTPException(status_code=422, detail="Escribí la resolución (al menos 5 caracteres): la ve el vecino.")
    if len(resolucion) > 2000:
        raise HTTPException(status_code=422, detail="La resolución no puede superar los 2000 caracteres.")

    r = (await db.execute(text("""
        SELECT id_reclamo, estado, id_tipo_reclamo, id_reclamo_padre
        FROM reclamos WHERE id_reclamo = :id AND activo = TRUE FOR UPDATE
    """), {"id": id_reclamo})).fetchone()
    if not r:
        raise HTTPException(status_code=404, detail=f"Reclamo {id_reclamo} no encontrado")
    if r.estado not in ("Sin asignar", "En gestión"):
        raise HTTPException(status_code=422, detail=f"Un reclamo '{r.estado}' no se puede resolver desde acá.")
    acciones = await _acciones_reclamo(db, r, current_user)
    if not acciones["resolver"]:
        raise HTTPException(status_code=403,
            detail="Resuelve quien tiene la orden de trabajo, la supervisión de la gestión o un administrador.")

    if r.id_reclamo_padre is None:
        pendientes = (await db.execute(text("""
            SELECT nro_reclamo, estado FROM reclamos
            WHERE id_reclamo_padre = :id AND activo = TRUE
              AND estado NOT IN ('Resuelto', 'Cancelado', 'En auditoría', 'Auditado')
            ORDER BY id_reclamo
        """), {"id": id_reclamo})).fetchall()
        if pendientes:
            detalle = ", ".join(f"{h.nro_reclamo} ({h.estado})" for h in pendientes)
            raise HTTPException(status_code=422,
                detail=f"Hay subreclamo(s) sin resolver: {detalle}. Resolvelos o cancelalos primero.")

    await _terminar_ots_operativas(db, id_reclamo, resolucion, current_user["id_usuario"])
    await _resolver_reclamo(db, id_reclamo, current_user["id_usuario"], resolucion)
    await db.commit()

    await _disparar_encuesta(db, id_reclamo)
    await svc_push.notificar_estado_reclamo(id_reclamo)
    return {"ok": True, "id_reclamo": id_reclamo, "estado": "Resuelto"}


# ── POST /reclamos/{id}/auditoria — enviar un reclamo Resuelto a auditoría ───

@router.post("/{id_reclamo}/auditoria", status_code=201,
             responses={422: {"description": "El reclamo no está Resuelto o ya tiene una auditoría abierta"},
                        403: {"description": "Requiere nivel Supervisor de la subárea del reclamo, o Administrador"}})
async def enviar_a_auditoria(
    id_reclamo: int,
    body: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Auditoría POSTERIOR al cierre (mig 112, PLAN_AUDITORIA_RECLAMOS.md).

    Un supervisor de la subárea del reclamo (o un admin) elige un reclamo
    'Resuelto' y lo manda a 'En auditoría': se crea una OT de auditoría que un
    auditor habilitado toma desde su mesa, y el reclamo queda pendiente de él.
    fecha_cierre NO cambia: la gestión ya terminó y los tiempos se miden hasta
    ese primer cierre. El vecino no se entera (ni push ni encuesta): para él el
    reclamo sigue 'Resuelto'.

    Body opcional: `observaciones` (motivo del envío) e `id_agente_auditor`
    (auditor puntual, `agentes.es_auditor`); sin este último la auditoría queda
    libre para cualquier auditor habilitado (regla de subárea cruzada de la mesa).
    """
    _require_supervisor(current_user)
    body = body or {}

    r = (await db.execute(text("""
        SELECT r.estado, r.nro_reclamo, tr.id_subarea
        FROM reclamos r
        LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
        WHERE r.id_reclamo = :id AND r.activo = TRUE
    """), {"id": id_reclamo})).fetchone()
    if not r:
        raise HTTPException(status_code=404, detail=f"Reclamo {id_reclamo} no encontrado")
    if r.estado != "Resuelto":
        raise HTTPException(status_code=422,
            detail=f"Solo se envía a auditoría un reclamo 'Resuelto' (actual: {r.estado}).")

    # Nivel 2: solo reclamos de su subárea. Fuente: agentes.id_subarea vía la
    # regla 1:1 (§3), igual que las mesas de OT. Admin (1) sin restricción.
    if current_user.get("nivel_acceso") == 2:
        perfil = await resolver_agente_desde_usuario(current_user["id_usuario"], db)
        sub_sup = perfil.get("id_subarea") if perfil else None
        if not sub_sup:
            raise HTTPException(status_code=403,
                detail="Tu usuario supervisor no tiene una subárea asignada en su perfil "
                       "de agente. Pedile a un administrador que la configure desde Maestros → Usuarios.")
        if r.id_subarea != sub_sup:
            raise HTTPException(status_code=403,
                detail="El reclamo pertenece a otra subárea. Solo podés enviar a auditoría reclamos de tu subárea.")

    # Una sola auditoría abierta por reclamo (el estado ya lo garantiza; el EXISTS
    # cubre datos viejos del modelo anterior).
    abierta = (await db.execute(text("""
        SELECT 1 FROM ordenes_trabajo ot
        JOIN estado_ot e ON e.id_estado_ot = ot.id_estado
        WHERE ot.id_reclamo = :id AND ot.activo = TRUE AND ot.es_auditoria = TRUE
          AND e.nombre NOT IN ('Terminada', 'Cancelada')
        LIMIT 1
    """), {"id": id_reclamo})).fetchone()
    if abierta:
        raise HTTPException(status_code=422, detail="El reclamo ya tiene una auditoría abierta.")

    id_auditor = body.get("id_agente_auditor")
    if id_auditor is not None:
        ag = (await db.execute(text(
            "SELECT es_auditor FROM agentes WHERE id_agente = :id AND activo = TRUE"
        ), {"id": id_auditor})).fetchone()
        if not ag or not ag.es_auditor:
            raise HTTPException(status_code=422,
                detail=f"El agente {id_auditor} no es un auditor habilitado (agentes.es_auditor).")

    est = (await db.execute(text(
        "SELECT id_estado_ot FROM estado_ot WHERE nombre = 'En gestión' AND activo = TRUE"
    ))).fetchone()
    if not est:
        raise HTTPException(status_code=500, detail="Estado OT 'En gestión' no encontrado en BD")

    # La OT operativa que cerró la gestión (si la hubo) queda como origen: la mesa
    # del auditor muestra quién hizo el trabajo y sus observaciones.
    ot_origen = (await db.execute(text("""
        SELECT ot.id_ot FROM ordenes_trabajo ot
        JOIN estado_ot e ON e.id_estado_ot = ot.id_estado
        WHERE ot.id_reclamo = :id AND ot.activo = TRUE AND ot.es_auditoria = FALSE
          AND e.nombre = 'Terminada'
        ORDER BY ot.fecha_cierre DESC NULLS LAST, ot.id_ot DESC
        LIMIT 1
    """), {"id": id_reclamo})).fetchone()

    observaciones = (body.get("observaciones") or "").strip() or None
    uid = current_user["id_usuario"]
    ot_row = (await db.execute(text("""
        INSERT INTO ordenes_trabajo
            (id_reclamo, id_estado, id_agente, es_auditoria, id_ot_origen, id_supervisor_asigna,
             observaciones, activo, fecha_alta, fecha_modificacion, id_usuario_alta, id_usuario_modificacion)
        VALUES (:id_r, :id_est, :id_ag, TRUE, :id_orig, :uid,
                :obs, TRUE, NOW(), NOW(), :uid, :uid)
        RETURNING id_ot, nro_ot
    """), {"id_r": id_reclamo, "id_est": est.id_estado_ot, "id_ag": id_auditor,
           "id_orig": ot_origen.id_ot if ot_origen else None, "uid": uid,
           "obs": observaciones})).fetchone()

    await db.execute(text("""
        UPDATE reclamos
        SET estado = 'En auditoría', fecha_inicio_auditoria = NOW(),
            fecha_fin_auditoria = NULL, resultado_auditoria = NULL,
            fecha_modificacion = NOW(), id_usuario_modificacion = :uid
        WHERE id_reclamo = :id
    """), {"id": id_reclamo, "uid": uid})

    nro_ot = ot_row.nro_ot or f"OT-{ot_row.id_ot}"
    await _insertar_historial(db, id_reclamo, "Enviado a auditoría",
                               "Resuelto", "En auditoría",
                               observaciones or f"Auditoría {nro_ot} creada", uid)
    await db.commit()
    # Sin push al vecino ni encuesta: la auditoría es interna (César, 2026-10-19).
    return {"ok": True, "id_reclamo": id_reclamo, "estado": "En auditoría",
            "id_ot": ot_row.id_ot, "nro_ot": nro_ot}


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
    if row.estado in ESTADOS_CERRADOS:
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
    _require_supervisor(current_user)  # cancelar = cambio de estado a final (§30)
    motivo = body.get("motivo", "").strip()
    if not motivo:
        raise HTTPException(status_code=422, detail="Campo 'motivo' requerido")

    r = await db.execute(text(
        "SELECT estado, id_reclamo_padre FROM reclamos WHERE id_reclamo = :id AND activo = TRUE"
    ), {"id": id_reclamo})
    row = r.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Reclamo {id_reclamo} no encontrado")
    if row.estado == "Cancelado":
        raise HTTPException(status_code=422, detail="El reclamo ya está cancelado")
    if row.estado in ESTADOS_AUDITORIA:
        raise HTTPException(status_code=422,
            detail=f"El reclamo está {row.estado}: la gestión ya cerró y la auditoría "
                   "la resuelve el auditor desde su mesa (no se cancela).")

    # Integridad padre/hijo (REC-001): no cancelar un reclamo padre si tiene
    # subreclamos activos sin resolver — quedarían huérfanos vivos (el cancelar
    # NO cascadea a los hijos, solo a las OTs). Mismo criterio que el guard de
    # 'Resuelto'/'En auditoría' en cambiar_estado. Solo aplica si NO es subreclamo.
    if row.id_reclamo_padre is None:
        hijos = await db.execute(text("""
            SELECT nro_reclamo, estado
            FROM reclamos
            WHERE id_reclamo_padre = :id AND activo = TRUE
              AND estado NOT IN ('Resuelto', 'Cancelado', 'En auditoría', 'Auditado')
            ORDER BY id_reclamo
        """), {"id": id_reclamo})
        pendientes = hijos.fetchall()
        if pendientes:
            detalle = ", ".join(f"{h.nro_reclamo} ({h.estado})" for h in pendientes)
            raise HTTPException(
                status_code=422,
                detail=(
                    f"No se puede cancelar: hay {len(pendientes)} "
                    f"subreclamo(s) activo(s): {detalle}. "
                    "Resolvé o cancelá los subreclamos primero."
                ),
            )

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

    # fecha_cierre se setea al pasar a estado final, Resuelto O Cancelado (§22).
    # Antes solo se seteaba en las OTs en cascada y en el pase a Resuelto via
    # cambiar_estado; el cancelar dejaba reclamos.fecha_cierre en NULL, rompiendo
    # las metricas de cierre/SLA. COALESCE para no pisar si ya estaba seteada.
    await db.execute(text("""
        UPDATE reclamos
        SET estado = 'Cancelado', fecha_modificacion = NOW(),
            fecha_cierre = COALESCE(fecha_cierre, NOW()),
            observaciones = :motivo, id_usuario_modificacion = :uid
        WHERE id_reclamo = :id
    """), {"motivo": motivo, "id": id_reclamo, "uid": current_user["id_usuario"]})

    await _insertar_historial(db, id_reclamo, "Reclamo cancelado",
                               estado_anterior, "Cancelado", motivo,
                               current_user["id_usuario"])

    # Si este reclamo es un subreclamo, desbloquear el padre 'En espera' cuando ya
    # no quedan hermanos vivos (misma transacción — integridad).
    await desbloquear_padre_si_corresponde(db, id_reclamo, current_user["id_usuario"])

    await db.commit()
    # Hook push App Vecinos (etapa E) — post-commit, best-effort.
    await svc_push.notificar_estado_reclamo(id_reclamo)
    return {"ok": True, "id_reclamo": id_reclamo, "estado": "Cancelado"}


# ── POST /reclamos/{id}/avisar-supervisor — aviso del operador (Fase 3) ──────

# Acciones que el operador puede pedirle al supervisor. El supervisor decide;
# esto solo estructura el pedido. El frontend (AvisarSupervisorModal) espeja
# esta lista — si la modificás, tocá los DOS lugares.
ACCIONES_AVISO_SUPERVISOR = {
    "Generar OT", "Pasar a En espera", "Resolver", "Cancelar", "Revisar",
}


@router.post("/{id_reclamo}/avisar-supervisor", status_code=201)
async def avisar_supervisor(
    id_reclamo: int,
    body: dict,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Fase 3 roles: el operador (nivel 3) NO cambia estados — genera un aviso
    a los supervisores (nivel 2) de la subárea del reclamo con la acción que
    pide + comentario opcional. Si la subárea no tiene supervisor, el aviso va
    a los admins (fallback, decisión 2026-07-02). Queda registrado en
    reclamo_historial y llega por notificación in-app + mail (mig 51).

    Body: {accion_sugerida: str, comentario?: str}."""
    # Avisar pueden Atención (3) Y Gestión (4) — Consultor (5) no (mig 92).
    if current_user.get("nivel_acceso") not in NIVELES_AVISO:
        raise HTTPException(status_code=403,
            detail="No tenés permisos para avisar al supervisor (requiere nivel Gestión o superior)")

    accion = (body.get("accion_sugerida") or "").strip()
    comentario = (body.get("comentario") or "").strip()
    if accion not in ACCIONES_AVISO_SUPERVISOR:
        raise HTTPException(422, "accion_sugerida invalida. Validas: "
                                 + ", ".join(sorted(ACCIONES_AVISO_SUPERVISOR)))
    if len(comentario) > 500:
        raise HTTPException(422, "comentario: maximo 500 caracteres")

    r = (await db.execute(text(
        "SELECT estado, nro_reclamo FROM reclamos WHERE id_reclamo = :id AND activo = TRUE"
    ), {"id": id_reclamo})).fetchone()
    if not r:
        raise HTTPException(404, f"Reclamo {id_reclamo} no encontrado")
    if r.estado in ESTADOS_CERRADOS:
        raise HTTPException(422, f"El reclamo está {r.estado}; no admite avisos")

    # Anti-spam: un aviso por usuario+reclamo cada 30 minutos.
    reciente = (await db.execute(text("""
        SELECT 1 FROM reclamo_historial
        WHERE id_reclamo = :id AND accion = 'Aviso al supervisor'
          AND id_usuario_alta = :uid
          AND fecha_alta > NOW() - INTERVAL '30 minutes'
        LIMIT 1
    """), {"id": id_reclamo, "uid": current_user["id_usuario"]})).fetchone()
    if reciente:
        raise HTTPException(422, "Ya enviaste un aviso por este reclamo hace menos "
                                 "de 30 minutos. El supervisor ya fue notificado.")

    nota = f"Pide: {accion}." + (f" {comentario}" if comentario else "")
    await _insertar_historial(db, id_reclamo, "Aviso al supervisor",
                              r.estado, r.estado, nota, current_user["id_usuario"])
    await db.commit()

    # Fail-safe: si la notificación falla, el aviso igual quedó en el historial.
    notificadas = await svc_notif.notificar_aviso_reclamo_a_supervision(
        db, id_reclamo, current_user["id_usuario"], accion, comentario,
        background_tasks=background_tasks,
    )
    return {"ok": True, "nro_reclamo": r.nro_reclamo,
            "notificaciones_creadas": notificadas}


# ── POST /reclamos/{id}/subreclamo — crear subreclamo (nivel 1) ──────────────

@router.post("/{id_reclamo}/subreclamo", status_code=201)
async def crear_subreclamo(
    id_reclamo: int,
    body: dict,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # Crear subreclamo desglosa el reclamo y pasa el padre a 'En espera' — es un
    # cambio de estado, exclusivo de Supervisión (§30). El operador toma nota o
    # avisa al supervisor. El backend es la fuente de verdad (§30, no solo la UI).
    _require_supervisor(current_user)

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
    if padre.estado in ESTADOS_CERRADOS:
        raise HTTPException(status_code=422, detail=f"No se puede subreclamo a un reclamo en estado {padre.estado}")

    for f in ["descripcion", "id_tipo_reclamo"]:
        if not body.get(f):
            raise HTTPException(status_code=422, detail=f"Campo requerido: {f}")

    direccion = body.get("direccion") or body.get("domicilio_reclamo") or ""

    # id_area: derivar de tipo_reclamo → subarea → area (igual que crear_reclamo).
    # No tomar body.get("id_area") crudo: el subreclamo debe nacer con el área
    # coherente con su tipo (fuente única: subarea.id_area, §27).
    id_area_sub = body.get("id_area")
    if not id_area_sub and body.get("id_tipo_reclamo"):
        r_area = await db.execute(text("""
            SELECT s.id_area
            FROM tipo_reclamo tr
            LEFT JOIN subarea s ON s.id_subarea = tr.id_subarea
            WHERE tr.id_tipo_reclamo = :id_tr
        """), {"id_tr": body["id_tipo_reclamo"]})
        row_area = r_area.fetchone()
        if row_area:
            id_area_sub = row_area.id_area

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
        "id_area":          id_area_sub,
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

    # Derivación automática de localidad (2026-08-30), igual que el alta principal.
    if data["id_localidad"] is None and data["latitud"] is not None and data["longitud"] is not None:
        loc = await localidad_desde_coords(db, data["latitud"], data["longitud"])
        if loc:
            data["id_localidad"] = loc["id_localidad"]

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
            WHERE id_reclamo = :id AND estado NOT IN ('Cancelado','Resuelto','En auditoría','Auditado')
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
        background_tasks.add_task(autoasignar_reclamo, id_sub)

        return {"id_reclamo": id_sub, "nro_reclamo": nro_sub, "id_reclamo_padre": id_reclamo}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Error al crear subreclamo: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
