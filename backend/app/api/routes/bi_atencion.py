# -*- coding: utf-8 -*-
"""
ZARIS API — BI de ATENCION por gestion (proyecto ATENCION F6, 2026-09-19).
Prefijo: /api/v1/bi/atencion/*

Tablero analitico de la atencion al vecino (Turnos + colero + Guardia + eventos),
tercer tablero del modulo DATOS junto al Operativo y al Ejecutivo (reclamos).
Plan: PLAN_MODULO_ATENCION.md §F6. Metricas pedidas: otorgados / cumplidos /
ausentes / cancelados, tasa de ausentismo, tiempo de espera real (primer llamado
vs hora del turno), atenciones por agente, ocupacion por ubicacion (turnos y
horas atendidas), origen (backoffice / autoservicio), atenciones de guardia por
emergencia, CSAT de turnos (§42) y reservas/asistencia de eventos (Cultura).

Jerarquia (decision 2026-09-01): GESTION (area) -> UBICACION (espacios_agenda)
-> agentes que atienden ahi -> turnos. La gestion de un turno se deriva de su
UBICACION (espacio -> subarea -> area); los turnos legacy sin ubicacion (previos
a la mig 103) caen a la subarea de la prestacion y, si tampoco, a "Sin gestion"
(leccion de los filtros legacy de la mig 27: nada desaparece en silencio).

Convenciones (espejo de bi.py / bi_ejecutivo.py):
  - Agregacion 100% en SQL (GROUP BY posicional: los alias AS no valen en GROUP BY).
  - Mono-municipio: id_municipio NULL cuenta como el municipio por defecto.
  - Universo de turnos = `t.activo = TRUE`. Cancelar un turno (turnos.py) deja
    activo=TRUE y estado='cancelado'; las filas cancelado+activo=false que hay en
    local y prod son la limpieza de un smoke del 2026-05-28 (sin usuario
    modificador), NO cancelaciones reales, y quedan fuera a proposito.
  - Hora del turno como timestamptz: fecha DATE + hora_inicio TIME son hora LOCAL
    naive (UTC-3 fijo, app/utils/fechas.py) -> +3h e interpretar como UTC (mismo
    criterio que services/historia_clinica.py). Espera real = primer llamado
    (turno_llamado, mig 105) - hora del turno; negativa = llamado antes de hora.
  - Periodo anterior: _rango_anterior del Ejecutivo (agosto se compara con julio).
  - CSAT: encuesta_envio.id_turno + encuesta_respuesta.clasificacion_inicial;
    satisfecho = >= 4 (regla del modulo Encuestas).
Auth: guard JWT a nivel router (§39); la UI gatea nivel <= 2 como el resto de DATOS.
Sin migracion: el tablero es solo lectura sobre las tablas de F1-F5.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.api.routes.bi import _parse_meses
from app.api.routes.bi_ejecutivo import _pct, _rango_anterior, _var_pct
from app.utils.fechas import hoy_local

router = APIRouter(
    prefix="/api/v1/bi/atencion",
    tags=["BI Atencion"],
    dependencies=[Depends(get_current_user)],
)

# Tolerancia para considerar un llamado "a tiempo" (minutos despues de la hora del turno).
TOLERANCIA_MIN = 5

# Hora del turno como timestamptz (ver docstring del modulo).
_TS_TURNO = "(((t.fecha + t.hora_inicio) + INTERVAL '3 hours') AT TIME ZONE 'UTC')"
_ESPERA_MIN = f"(EXTRACT(EPOCH FROM (ll.primer_llamado - {_TS_TURNO})) / 60.0)"
_DUR_HS = "(EXTRACT(EPOCH FROM (t.hora_fin - t.hora_inicio)) / 3600.0)"
_AGENTE_NOMBRE = "(COALESCE(ag.apellido, '') || ', ' || COALESCE(ag.nombre, ''))"

# Universo de turnos + dimensiones (una fila por turno: los LATERAL con LIMIT/agregado
# garantizan que ni los llamados ni las encuestas dupliquen filas).
# Llamados: solo los del MISMO dia local del turno. Un llamado de otro dia es una
# regularizacion tardia (o un artefacto de prueba: en local hay un turno del 02/09
# llamado el 06/09 = 6.300 min) y no mide espera real.
_JOIN_TURNOS = """
    LEFT JOIN tipo_prestacion tp ON tp.id_tipo_prestacion = t.id_tipo_prestacion
    LEFT JOIN espacios_agenda ub ON ub.id_espacio = COALESCE(t.id_espacio_ubicacion, tp.id_espacio_ubicacion, t.id_espacio)
    LEFT JOIN subarea s ON s.id_subarea = COALESCE(ub.id_subarea, tp.id_subarea)
    LEFT JOIN area a ON a.id_area = s.id_area
    LEFT JOIN agentes ag ON ag.id_agente = t.id_agente
    LEFT JOIN LATERAL (
        SELECT MIN(l.llamado_en) AS primer_llamado, COUNT(*) AS n_llamados
          FROM turno_llamado l
         WHERE l.id_turno = t.id_turno AND l.activo IS DISTINCT FROM FALSE
           AND ((l.llamado_en AT TIME ZONE 'UTC') - INTERVAL '3 hours')::date = t.fecha
    ) ll ON TRUE
    LEFT JOIN LATERAL (
        SELECT ta.id_turno_atencion
          FROM turno_atencion ta
         WHERE ta.id_turno = t.id_turno AND ta.activo IS DISTINCT FROM FALSE
         ORDER BY ta.id_turno_atencion LIMIT 1
    ) ta ON TRUE
    LEFT JOIN LATERAL (
        SELECT ev.id_encuesta_envio, resp.clasificacion_inicial
          FROM encuesta_envio ev
          LEFT JOIN encuesta_respuesta resp ON resp.id_envio = ev.id_encuesta_envio
         WHERE ev.id_turno = t.id_turno AND ev.activo = TRUE
         ORDER BY ev.id_encuesta_envio DESC LIMIT 1
    ) enc ON TRUE
"""

# Agregados estandar de un grupo de turnos (score, matriz, ubicaciones, agentes).
_AGG_TURNOS = f"""
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE t.estado = 'cumplido') AS cumplidos,
    COUNT(*) FILTER (WHERE t.estado = 'ausente') AS ausentes,
    COUNT(*) FILTER (WHERE t.estado = 'cancelado') AS cancelados,
    COUNT(*) FILTER (WHERE t.estado IN ('reservado', 'llamado')) AS pendientes,
    COUNT(*) FILTER (WHERE t.origen = 'autoservicio') AS autoservicio,
    COUNT(ll.primer_llamado) AS llamados,
    COUNT(*) FILTER (WHERE ll.n_llamados > 1) AS re_llamados,
    COUNT(*) FILTER (WHERE ll.primer_llamado IS NOT NULL AND {_ESPERA_MIN} <= {TOLERANCIA_MIN}) AS a_tiempo,
    ROUND((AVG(GREATEST(0, {_ESPERA_MIN})) FILTER (WHERE ll.primer_llamado IS NOT NULL))::numeric, 1)::float AS espera_prom_min,
    ROUND((MAX({_ESPERA_MIN}))::numeric, 0)::float AS espera_max_min,
    COUNT(ta.id_turno_atencion) AS atenciones_registradas,
    ROUND((SUM({_DUR_HS}) FILTER (WHERE t.estado = 'cumplido'))::numeric, 1)::float AS horas_atendidas,
    COUNT(enc.id_encuesta_envio) AS enviadas,
    COUNT(enc.clasificacion_inicial) AS respuestas,
    COUNT(*) FILTER (WHERE enc.clasificacion_inicial >= 4) AS satisfechos
"""
_AGG_KEYS = (
    "total", "cumplidos", "ausentes", "cancelados", "pendientes", "autoservicio",
    "llamados", "re_llamados", "a_tiempo", "espera_prom_min", "espera_max_min",
    "atenciones_registradas", "horas_atendidas", "enviadas", "respuestas", "satisfechos",
)


# ── Filtros ──────────────────────────────────────────────────────────────────

def _rango_mes(mes: str) -> tuple[date, date]:
    """'YYYY-MM' -> [primer dia, primer dia del mes siguiente). 422 si es basura."""
    try:
        ini = datetime.strptime(mes + "-01", "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(422, "Parámetro 'mes' inválido. Formato esperado: YYYY-MM.")
    fin = (ini.replace(day=28) + timedelta(days=4)).replace(day=1)
    return ini, fin


def _where_fecha(
    cond: list[str], params: dict, campo: str,
    desde: Optional[date], hasta: Optional[date],
    anio: Optional[int], meses: Optional[list[int]],
    *, pares: Optional[list[int]] = None, mes: Optional[str] = None,
) -> None:
    """Condiciones temporales sobre `campo` (expresion DATE). `mes` (drill) tiene
    prioridad sobre desde/hasta; anio/meses/pares se combinan por AND."""
    if mes:
        ini, fin = _rango_mes(mes)
        cond.append(f"{campo} >= :mes_ini")
        cond.append(f"{campo} < :mes_fin")
        params["mes_ini"], params["mes_fin"] = ini, fin
    else:
        if desde:
            cond.append(f"{campo} >= :desde")
            params["desde"] = desde
        if hasta:
            cond.append(f"{campo} <= :hasta")
            params["hasta"] = hasta
    if anio:
        cond.append(f"EXTRACT(YEAR FROM {campo})::int = :anio")
        params["anio"] = int(anio)
    if meses:
        cond.append(f"EXTRACT(MONTH FROM {campo})::int = ANY(CAST(:meses AS int[]))")
        params["meses"] = [int(m) for m in meses]
    if pares:
        cond.append(
            f"(EXTRACT(YEAR FROM {campo})::int * 100 + EXTRACT(MONTH FROM {campo})::int)"
            " = ANY(CAST(:pares AS int[]))")
        params["pares"] = [int(p) for p in pares]


def _where_turnos(
    desde: Optional[date], hasta: Optional[date],
    anio: Optional[int], meses: Optional[list[int]],
    id_area: Optional[int], id_espacio_ubicacion: Optional[int],
    id_tipo_prestacion: Optional[int], id_municipio: int,
    *, pares: Optional[list[int]] = None, mes: Optional[str] = None,
) -> tuple[list[str], dict]:
    """WHERE del universo de turnos (la query debe incluir _JOIN_TURNOS)."""
    cond = [
        "t.activo = TRUE",
        "(t.id_municipio = :id_municipio OR t.id_municipio IS NULL)",
    ]
    params: dict = {"id_municipio": id_municipio}
    _where_fecha(cond, params, "t.fecha", desde, hasta, anio, meses, pares=pares, mes=mes)
    if id_area:
        cond.append("a.id_area = :id_area")
        params["id_area"] = id_area
    if id_espacio_ubicacion:
        cond.append("ub.id_espacio = :id_espacio_ubicacion")
        params["id_espacio_ubicacion"] = id_espacio_ubicacion
    if id_tipo_prestacion:
        cond.append("t.id_tipo_prestacion = :id_tipo_prestacion")
        params["id_tipo_prestacion"] = id_tipo_prestacion
    return cond, params


def _periodo_anterior_kwargs(
    desde: Optional[date], hasta: Optional[date],
    anio: Optional[int], meses: Optional[list[int]],
) -> Optional[dict]:
    """Traduce _rango_anterior a kwargs de _where_* (None = sin comparacion)."""
    ant = _rango_anterior(desde, hasta, anio, meses)
    if not ant:
        return None
    return {
        "desde": ant.get("desde"), "hasta": ant.get("hasta"),
        "anio": ant.get("anio"), "meses": meses if ant.get("anio") else None,
        "pares": ant.get("pares"),
    }


# ── Indicadores ──────────────────────────────────────────────────────────────

def _indicadores(r: dict) -> dict:
    """Indicadores derivados de un agregado _AGG_TURNOS.
      - pct_cumplimiento = cumplidos / otorgados con desenlace (sin pendientes)
      - pct_ausentismo   = ausentes / (cumplidos + ausentes): de los turnos que
                           llegaron a su hora, cuantos se cayeron (KPI del plan)
      - pct_cancelacion  = cancelados / otorgados
      - pct_a_tiempo     = llamados dentro de la tolerancia / turnos llamados
      - pct_sat          = satisfechos / respuestas · tasa_respuesta = respuestas / enviadas"""
    out = {k: r.get(k) for k in _AGG_KEYS}
    total, cumpl, aus = r["total"], r["cumplidos"], r["ausentes"]
    definidos = total - r["pendientes"]
    out.update({
        "pct_cumplimiento": _pct(cumpl, definidos),
        "pct_ausentismo": _pct(aus, cumpl + aus),
        "pct_cancelacion": _pct(r["cancelados"], total),
        "pct_a_tiempo": _pct(r["a_tiempo"], r["llamados"]),
        "pct_autoservicio": _pct(r["autoservicio"], total),
        "pct_sat": _pct(r["satisfechos"], r["respuestas"]),
        "tasa_respuesta": _pct(r["respuestas"], r["enviadas"]),
    })
    return out


def _vacio() -> dict:
    base = {k: 0 for k in _AGG_KEYS}
    base["espera_prom_min"] = None
    base["espera_max_min"] = None
    base["horas_atendidas"] = None
    return _indicadores(base)


async def _agregado_turnos(
    db: AsyncSession, grp_sql: str, n_grp: int, cond: list[str], params: dict,
    *, extra_sql: str = "", order: str = "", limit: Optional[int] = None,
) -> list[dict]:
    """Universo de turnos agrupado por las primeras `n_grp` columnas (GROUP BY
    posicional). `grp_sql` vacio = un solo agregado total."""
    sel = f"{grp_sql}, {_AGG_TURNOS}" if grp_sql else _AGG_TURNOS
    grp = f"GROUP BY {', '.join(str(i + 1) for i in range(n_grp))}" if n_grp else ""
    lim = f"LIMIT {int(limit)}" if limit else ""
    r = await db.execute(text(f"""
        SELECT {sel} {extra_sql}
          FROM turnos t {_JOIN_TURNOS}
         WHERE {' AND '.join(cond)}
         {grp} {order} {lim}
    """), params)
    return [dict(row._mapping) for row in r.fetchall()]


def _params_comunes(
    desde: Optional[date] = Query(None), hasta: Optional[date] = Query(None),
    anio: Optional[int] = Query(None), meses: Optional[str] = Query(None),
    id_area: Optional[int] = Query(None, description="Gestion (area)"),
    id_espacio_ubicacion: Optional[int] = Query(None, description="Ubicacion (espacio)"),
    id_tipo_prestacion: Optional[int] = Query(None),
    id_municipio: int = Query(1),
) -> dict:
    return {
        "desde": desde, "hasta": hasta, "anio": anio, "meses": _parse_meses(meses),
        "id_area": id_area, "id_espacio_ubicacion": id_espacio_ubicacion,
        "id_tipo_prestacion": id_tipo_prestacion, "id_municipio": id_municipio,
    }


# ── 1. Score del periodo ─────────────────────────────────────────────────────

@router.get("/score", responses={422: {"description": "Parámetros de período inválidos"}})  # marker OpenAPI §9
async def at_score(
    f: dict = Depends(_params_comunes),
    db: AsyncSession = Depends(get_db),
):
    """KPIs del periodo (universo de turnos): otorgados, cumplidos, ausentes,
    cancelados, pendientes, espera real, CSAT, atenciones registradas + los mismos
    indicadores del periodo INMEDIATAMENTE anterior (var_pct sobre otorgados) +
    composicion por estado / origen y niveles de satisfaccion 1-5."""
    cond, params = _where_turnos(**f)
    base = (await _agregado_turnos(db, "", 0, cond, params))[0]
    actual = _indicadores(base)

    anterior = None
    ant_kw = _periodo_anterior_kwargs(f["desde"], f["hasta"], f["anio"], f["meses"])
    if ant_kw:
        cond_a, params_a = _where_turnos(
            id_area=f["id_area"], id_espacio_ubicacion=f["id_espacio_ubicacion"],
            id_tipo_prestacion=f["id_tipo_prestacion"], id_municipio=f["id_municipio"], **ant_kw)
        anterior = _indicadores((await _agregado_turnos(db, "", 0, cond_a, params_a))[0])

    por_estado = await db.execute(text(f"""
        SELECT t.estado, COUNT(*) AS total
          FROM turnos t {_JOIN_TURNOS} WHERE {' AND '.join(cond)}
         GROUP BY 1 ORDER BY 2 DESC
    """), params)
    por_origen = await db.execute(text(f"""
        SELECT t.origen, COUNT(*) AS total
          FROM turnos t {_JOIN_TURNOS} WHERE {' AND '.join(cond)}
         GROUP BY 1 ORDER BY 2 DESC
    """), params)
    niveles = await db.execute(text(f"""
        SELECT enc.clasificacion_inicial AS clasificacion, COUNT(*) AS total
          FROM turnos t {_JOIN_TURNOS}
         WHERE {' AND '.join(cond)} AND enc.clasificacion_inicial IS NOT NULL
         GROUP BY 1 ORDER BY 1
    """), params)
    return {
        **actual,
        "var_pct": _var_pct(actual["total"], (anterior or {}).get("total")),
        "anterior": anterior,
        "por_estado": [dict(r._mapping) for r in por_estado.fetchall()],
        "por_origen": [dict(r._mapping) for r in por_origen.fetchall()],
        "niveles": [dict(r._mapping) for r in niveles.fetchall()],
    }


# ── 2. Matriz ubicacion -> prestacion ────────────────────────────────────────

_GRP_UBIC = "ub.id_espacio AS id_espacio, COALESCE(ub.nombre, 'Sin ubicación') AS ubicacion, COALESCE(a.nombre, 'Sin gestión') AS gestion"
_GRP_PREST = _GRP_UBIC + ", tp.id_tipo_prestacion AS id_tipo_prestacion, COALESCE(tp.nombre, 'Sin prestación') AS prestacion"


def _fila(base: dict, ant: Optional[dict]) -> dict:
    ind = _indicadores(base)
    return {**ind, "var_pct": _var_pct(ind["total"], (ant or {}).get("total")), "ant": ant}


@router.get("/matriz")
async def at_matriz(
    f: dict = Depends(_params_comunes),
    db: AsyncSession = Depends(get_db),
):
    """Matriz UBICACION -> PRESTACION (la tabla central del tablero): indicadores
    por ubicacion (con su gestion) y, expandible, por prestacion; `ant` trae los
    indicadores del periodo anterior para los triangulitos de variacion."""
    cond, params = _where_turnos(**f)
    ubic = await _agregado_turnos(db, _GRP_UBIC, 3, cond, params, order="ORDER BY 3, 2")
    prest = await _agregado_turnos(db, _GRP_PREST, 5, cond, params, order="ORDER BY 3, 2, 5")
    total = (await _agregado_turnos(db, "", 0, cond, params))[0]

    ant_u: dict[Any, dict] = {}
    ant_p: dict[Any, dict] = {}
    ant_t: Optional[dict] = None
    ant_kw = _periodo_anterior_kwargs(f["desde"], f["hasta"], f["anio"], f["meses"])
    if ant_kw:
        cond_a, params_a = _where_turnos(
            id_area=f["id_area"], id_espacio_ubicacion=f["id_espacio_ubicacion"],
            id_tipo_prestacion=f["id_tipo_prestacion"], id_municipio=f["id_municipio"], **ant_kw)
        ant_u = {r["id_espacio"]: _indicadores(r) for r in await _agregado_turnos(db, _GRP_UBIC, 3, cond_a, params_a)}
        ant_p = {(r["id_espacio"], r["id_tipo_prestacion"]): _indicadores(r)
                 for r in await _agregado_turnos(db, _GRP_PREST, 5, cond_a, params_a)}
        ant_t = _indicadores((await _agregado_turnos(db, "", 0, cond_a, params_a))[0])

    filas = []
    for u in ubic:
        hijos = [
            {"id_tipo_prestacion": p["id_tipo_prestacion"], "prestacion": p["prestacion"],
             **_fila(p, ant_p.get((p["id_espacio"], p["id_tipo_prestacion"])))}
            for p in prest if p["id_espacio"] == u["id_espacio"]
        ]
        filas.append({
            "id_espacio": u["id_espacio"], "ubicacion": u["ubicacion"], "gestion": u["gestion"],
            **_fila(u, ant_u.get(u["id_espacio"])),
            "prestaciones": hijos,
        })
    return {"filas": filas, "total": _fila(total, ant_t)}


# ── 3. Series temporales ─────────────────────────────────────────────────────

_SERIE_ESTADOS = """
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE t.estado = 'cumplido') AS cumplido,
    COUNT(*) FILTER (WHERE t.estado = 'ausente') AS ausente,
    COUNT(*) FILTER (WHERE t.estado = 'cancelado') AS cancelado,
    COUNT(*) FILTER (WHERE t.estado IN ('reservado', 'llamado')) AS pendiente
"""


@router.get("/mensual")
async def at_mensual(
    f: dict = Depends(_params_comunes),
    db: AsyncSession = Depends(get_db),
):
    """Serie mensual de turnos por estado: [{mes 'YYYY-MM', total, cumplido, ausente,
    cancelado, pendiente}] (shape ItemTemporal del HistogramaTemporal)."""
    cond, params = _where_turnos(**f)
    r = await db.execute(text(f"""
        SELECT to_char(t.fecha, 'YYYY-MM') AS mes, {_SERIE_ESTADOS}
          FROM turnos t {_JOIN_TURNOS} WHERE {' AND '.join(cond)}
         GROUP BY 1 ORDER BY 1
    """), params)
    return [dict(row._mapping) for row in r.fetchall()]


@router.get("/diario")
async def at_diario(
    mes: Optional[str] = Query(None, description="Drill a un mes 'YYYY-MM' (prioridad sobre desde/hasta)"),
    f: dict = Depends(_params_comunes),
    db: AsyncSession = Depends(get_db),
):
    """Serie diaria de turnos por estado (modo Dia o drill de un mes)."""
    cond, params = _where_turnos(**f, mes=mes)
    r = await db.execute(text(f"""
        SELECT to_char(t.fecha, 'YYYY-MM-DD') AS dia, {_SERIE_ESTADOS}
          FROM turnos t {_JOIN_TURNOS} WHERE {' AND '.join(cond)}
         GROUP BY 1 ORDER BY 1
    """), params)
    return [dict(row._mapping) for row in r.fetchall()]


@router.get("/evolucion")
async def at_evolucion(
    f: dict = Depends(_params_comunes),
    db: AsyncSession = Depends(get_db),
):
    """Indicadores mensuales: [{mes, total, cumplidos, ausentes, pct_cumplimiento,
    pct_ausentismo, espera_prom_min, pct_sat}]. El front lo pide con la ventana
    fija de 12 meses (regla del Ejecutivo)."""
    cond, params = _where_turnos(**f)
    rows = await _agregado_turnos(db, "to_char(t.fecha, 'YYYY-MM') AS mes", 1, cond, params, order="ORDER BY 1")
    out = []
    for r in rows:
        ind = _indicadores(r)
        out.append({
            "mes": r["mes"], "total": ind["total"], "cumplidos": ind["cumplidos"],
            "ausentes": ind["ausentes"], "cancelados": ind["cancelados"],
            "pct_cumplimiento": ind["pct_cumplimiento"], "pct_ausentismo": ind["pct_ausentismo"],
            "espera_prom_min": ind["espera_prom_min"], "pct_sat": ind["pct_sat"],
        })
    return out


# ── 4. Ubicaciones y agentes ─────────────────────────────────────────────────

@router.get("/por-ubicacion")
async def at_por_ubicacion(
    f: dict = Depends(_params_comunes),
    db: AsyncSession = Depends(get_db),
):
    """Indicadores por UBICACION (ocupacion: turnos otorgados + horas atendidas)."""
    cond, params = _where_turnos(**f)
    rows = await _agregado_turnos(db, _GRP_UBIC, 3, cond, params, order="ORDER BY total DESC, 2")
    return [{"id_espacio": r["id_espacio"], "ubicacion": r["ubicacion"], "gestion": r["gestion"], **_indicadores(r)} for r in rows]


@router.get("/por-agente")
async def at_por_agente(
    limit: int = Query(15, ge=1, le=100),
    f: dict = Depends(_params_comunes),
    db: AsyncSession = Depends(get_db),
):
    """Atencion por AGENTE (turnos cuyo recurso es un agente): otorgados, cumplidos,
    ausentes, espera, atenciones registradas y las ubicaciones donde atendio."""
    cond, params = _where_turnos(**f)
    cond = cond + ["t.id_agente IS NOT NULL"]
    rows = await _agregado_turnos(
        db, f"ag.id_agente AS id_agente, {_AGENTE_NOMBRE} AS agente", 2, cond, params,
        extra_sql=", string_agg(DISTINCT ub.nombre, ', ') AS ubicaciones",
        order="ORDER BY total DESC, 2", limit=limit)
    return [{"id_agente": r["id_agente"], "agente": r["agente"], "ubicaciones": r["ubicaciones"], **_indicadores(r)} for r in rows]


# ── 5. Espera y llamados ─────────────────────────────────────────────────────

_TRAMOS = [("A tiempo", None, TOLERANCIA_MIN), ("5-15 min", TOLERANCIA_MIN, 15),
           ("15-30 min", 15, 30), ("30-60 min", 30, 60), ("Más de 60 min", 60, None)]


@router.get("/espera")
async def at_espera(
    f: dict = Depends(_params_comunes),
    db: AsyncSession = Depends(get_db),
):
    """Tiempo de espera real (turnos con al menos un llamado): tramos, promedio,
    maximo, re-llamados y el detalle por ubicacion."""
    cond, params = _where_turnos(**f)
    cond = cond + ["ll.primer_llamado IS NOT NULL"]
    casos = []
    for nombre, lo, hi in _TRAMOS:
        if lo is None:
            c = f"{_ESPERA_MIN} <= {hi}"
        elif hi is None:
            c = f"{_ESPERA_MIN} > {lo}"
        else:
            c = f"{_ESPERA_MIN} > {lo} AND {_ESPERA_MIN} <= {hi}"
        casos.append(f"WHEN {c} THEN '{nombre}'")
    r = await db.execute(text(f"""
        SELECT CASE {' '.join(casos)} END AS tramo, COUNT(*) AS total
          FROM turnos t {_JOIN_TURNOS} WHERE {' AND '.join(cond)}
         GROUP BY 1
    """), params)
    por_tramo = {row.tramo: row.total for row in r.fetchall()}
    tramos = [{"tramo": nombre, "total": por_tramo.get(nombre, 0)} for nombre, _, _ in _TRAMOS]

    total = (await _agregado_turnos(db, "", 0, cond, params))[0]
    ubic = await _agregado_turnos(db, _GRP_UBIC, 3, cond, params, order="ORDER BY llamados DESC, 2")
    ind = _indicadores(total)
    return {
        "llamados": ind["llamados"], "re_llamados": ind["re_llamados"],
        "a_tiempo": ind["a_tiempo"], "pct_a_tiempo": ind["pct_a_tiempo"],
        "espera_prom_min": ind["espera_prom_min"], "espera_max_min": ind["espera_max_min"],
        "tolerancia_min": TOLERANCIA_MIN,
        "tramos": tramos,
        "por_ubicacion": [
            {"id_espacio": u["id_espacio"], "ubicacion": u["ubicacion"], "gestion": u["gestion"],
             **{k: v for k, v in _indicadores(u).items()
                if k in ("llamados", "re_llamados", "a_tiempo", "pct_a_tiempo", "espera_prom_min", "espera_max_min")}}
            for u in ubic
        ],
    }


# ── 6. Guardia (atenciones por emergencia, mig 106) ──────────────────────────

_FECHA_GUARDIA = "((x.derivado_en AT TIME ZONE 'UTC') - INTERVAL '3 hours')::date"
_DEMORA_MIN = "(EXTRACT(EPOCH FROM (x.atendido_en - x.derivado_en)) / 60.0)"
_JOIN_GUARDIA = """
    LEFT JOIN espacios_agenda ub ON ub.id_espacio = x.id_espacio_ubicacion
    LEFT JOIN subarea s ON s.id_subarea = ub.id_subarea
    LEFT JOIN area a ON a.id_area = s.id_area
    LEFT JOIN agentes ag ON ag.id_agente = x.id_agente_atiende
    LEFT JOIN emergencia_evento ev ON ev.id_emergencia_evento = x.id_emergencia_evento
    LEFT JOIN emergencia_tipo et ON et.id_emergencia_tipo = ev.id_tipo
    LEFT JOIN emergencia_prioridad ep ON ep.id_emergencia_prioridad = ev.id_prioridad
"""
_AGG_GUARDIA = f"""
    COUNT(*) AS derivaciones,
    COUNT(*) FILTER (WHERE x.estado = 'atendida') AS atendidas,
    COUNT(*) FILTER (WHERE x.estado = 'ausente') AS ausentes,
    COUNT(*) FILTER (WHERE x.estado = 'pendiente') AS pendientes,
    COUNT(*) FILTER (WHERE x.id_ciudadano IS NOT NULL) AS con_ciudadano,
    ROUND((AVG({_DEMORA_MIN}) FILTER (WHERE x.estado = 'atendida' AND x.atendido_en IS NOT NULL))::numeric, 1)::float AS demora_prom_min,
    ROUND((MAX({_DEMORA_MIN}) FILTER (WHERE x.estado = 'atendida' AND x.atendido_en IS NOT NULL))::numeric, 0)::float AS demora_max_min
"""


def _where_guardia(
    desde, hasta, anio, meses, id_area, id_espacio_ubicacion, id_tipo_prestacion, id_municipio,
    *, pares=None, mes=None,
) -> tuple[list[str], dict]:
    """WHERE de emergencia_atencion. El filtro de PRESTACION no aplica (la guardia no
    va con turno, decision de Cesar 2026-09-01) y se ignora a proposito."""
    cond = [
        "x.activo IS DISTINCT FROM FALSE",
        "(x.id_municipio = :id_municipio OR x.id_municipio IS NULL)",
    ]
    params: dict = {"id_municipio": id_municipio}
    _where_fecha(cond, params, _FECHA_GUARDIA, desde, hasta, anio, meses, pares=pares, mes=mes)
    if id_area:
        cond.append("a.id_area = :id_area")
        params["id_area"] = id_area
    if id_espacio_ubicacion:
        cond.append("ub.id_espacio = :id_espacio_ubicacion")
        params["id_espacio_ubicacion"] = id_espacio_ubicacion
    return cond, params


def _ind_guardia(r: dict) -> dict:
    return {
        "derivaciones": r["derivaciones"], "atendidas": r["atendidas"], "ausentes": r["ausentes"],
        "pendientes": r["pendientes"], "con_ciudadano": r["con_ciudadano"],
        "pct_atendidas": _pct(r["atendidas"], r["atendidas"] + r["ausentes"]),
        "pct_ausentes": _pct(r["ausentes"], r["atendidas"] + r["ausentes"]),
        "demora_prom_min": r["demora_prom_min"], "demora_max_min": r["demora_max_min"],
    }


async def _agregado_guardia(db, grp_sql: str, n_grp: int, cond, params, *, order: str = "", limit=None) -> list[dict]:
    sel = f"{grp_sql}, {_AGG_GUARDIA}" if grp_sql else _AGG_GUARDIA
    grp = f"GROUP BY {', '.join(str(i + 1) for i in range(n_grp))}" if n_grp else ""
    lim = f"LIMIT {int(limit)}" if limit else ""
    r = await db.execute(text(f"""
        SELECT {sel} FROM emergencia_atencion x {_JOIN_GUARDIA}
         WHERE {' AND '.join(cond)} {grp} {order} {lim}
    """), params)
    return [dict(row._mapping) for row in r.fetchall()]


@router.get("/guardia")
async def at_guardia(
    f: dict = Depends(_params_comunes),
    db: AsyncSession = Depends(get_db),
):
    """Atenciones de GUARDIA derivadas desde Emergencias: derivaciones, atendidas,
    ausentes, pendientes, demora derivacion->atencion, periodo anterior, y el
    desglose por medico (agente), tipo de emergencia y prioridad."""
    cond, params = _where_guardia(**f)
    base = (await _agregado_guardia(db, "", 0, cond, params))[0]
    actual = _ind_guardia(base)
    anterior = None
    ant_kw = _periodo_anterior_kwargs(f["desde"], f["hasta"], f["anio"], f["meses"])
    if ant_kw:
        cond_a, params_a = _where_guardia(
            id_area=f["id_area"], id_espacio_ubicacion=f["id_espacio_ubicacion"],
            id_tipo_prestacion=None, id_municipio=f["id_municipio"], **ant_kw)
        anterior = _ind_guardia((await _agregado_guardia(db, "", 0, cond_a, params_a))[0])

    por_agente = await _agregado_guardia(
        db, f"ag.id_agente AS id_agente, {_AGENTE_NOMBRE} AS agente", 2,
        cond + ["x.id_agente_atiende IS NOT NULL"], params, order="ORDER BY atendidas DESC, 2", limit=15)
    por_tipo = await _agregado_guardia(
        db, "et.id_emergencia_tipo AS id_tipo, COALESCE(et.nombre, 'Sin tipo') AS tipo", 2,
        cond, params, order="ORDER BY derivaciones DESC, 2", limit=10)
    por_prioridad = await _agregado_guardia(
        db, "ep.id_emergencia_prioridad AS id_prioridad, COALESCE(ep.nombre, 'Sin prioridad') AS prioridad, ep.orden_visual AS orden", 3,
        cond, params, order="ORDER BY 3 NULLS LAST, 2")
    return {
        **actual,
        "var_pct": _var_pct(actual["derivaciones"], (anterior or {}).get("derivaciones")),
        "anterior": anterior,
        "por_estado": [
            {"estado": e, "total": actual[k]}
            for e, k in (("atendida", "atendidas"), ("ausente", "ausentes"), ("pendiente", "pendientes"))
            if actual[k]
        ],
        "por_agente": [{"id_agente": r["id_agente"], "agente": r["agente"], **_ind_guardia(r)} for r in por_agente],
        "por_tipo": [{"id_tipo": r["id_tipo"], "tipo": r["tipo"], **_ind_guardia(r)} for r in por_tipo],
        "por_prioridad": [{"id_prioridad": r["id_prioridad"], "prioridad": r["prioridad"], **_ind_guardia(r)} for r in por_prioridad],
    }


_SERIE_GUARDIA = """
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE x.estado = 'atendida') AS atendida,
    COUNT(*) FILTER (WHERE x.estado = 'ausente') AS ausente,
    COUNT(*) FILTER (WHERE x.estado = 'pendiente') AS pendiente
"""


@router.get("/guardia/mensual")
async def at_guardia_mensual(
    f: dict = Depends(_params_comunes),
    db: AsyncSession = Depends(get_db),
):
    cond, params = _where_guardia(**f)
    r = await db.execute(text(f"""
        SELECT to_char({_FECHA_GUARDIA}, 'YYYY-MM') AS mes, {_SERIE_GUARDIA}
          FROM emergencia_atencion x {_JOIN_GUARDIA} WHERE {' AND '.join(cond)}
         GROUP BY 1 ORDER BY 1
    """), params)
    return [dict(row._mapping) for row in r.fetchall()]


@router.get("/guardia/diario")
async def at_guardia_diario(
    mes: Optional[str] = Query(None),
    f: dict = Depends(_params_comunes),
    db: AsyncSession = Depends(get_db),
):
    cond, params = _where_guardia(**f, mes=mes)
    r = await db.execute(text(f"""
        SELECT to_char({_FECHA_GUARDIA}, 'YYYY-MM-DD') AS dia, {_SERIE_GUARDIA}
          FROM emergencia_atencion x {_JOIN_GUARDIA} WHERE {' AND '.join(cond)}
         GROUP BY 1 ORDER BY 1
    """), params)
    return [dict(row._mapping) for row in r.fetchall()]


# ── 7. Eventos y reservas (Cultura: Entradas + Agenda) ───────────────────────

_JOIN_EVENTOS = """
    LEFT JOIN espacios_agenda ub ON ub.id_espacio = ev.id_espacio
    LEFT JOIN subarea s ON s.id_subarea = COALESCE(ev.id_subarea, ub.id_subarea)
    LEFT JOIN area a ON a.id_area = s.id_area
    LEFT JOIN estado_evento ee ON ee.id_estado_evento = ev.id_estado_evento
"""
# Reservas de cada evento (LATERAL: una fila por evento, sin multiplicar el cupo).
_LATERAL_RESERVAS = """
    LEFT JOIN LATERAL (
        SELECT COUNT(*) AS reservas,
               COUNT(*) FILTER (WHERE er.codigo IN ('reservada', 'asistio')) AS vigentes,
               COUNT(*) FILTER (WHERE er.codigo = 'asistio') AS asistieron,
               COUNT(*) FILTER (WHERE er.codigo = 'reservada') AS sin_asistencia,
               COUNT(*) FILTER (WHERE er.codigo = 'cancelada') AS canceladas,
               COUNT(*) FILTER (WHERE r.origen = 'autoservicio') AS autoservicio
          FROM evento_reservas r
          LEFT JOIN estado_reserva er ON er.id_estado_reserva = r.id_estado_reserva
         WHERE r.id_evento = ev.id_evento AND r.activo = TRUE
    ) rs ON TRUE
"""


def _where_eventos(
    desde, hasta, anio, meses, id_area, id_espacio_ubicacion, id_tipo_prestacion, id_municipio,
    *, pares=None, mes=None,
) -> tuple[list[str], dict]:
    """WHERE de eventos (fecha del evento). Prestacion no aplica (se ignora)."""
    cond = [
        "ev.activo = TRUE",
        "(ev.id_municipio = :id_municipio OR ev.id_municipio IS NULL)",
    ]
    params: dict = {"id_municipio": id_municipio}
    _where_fecha(cond, params, "ev.fecha", desde, hasta, anio, meses, pares=pares, mes=mes)
    if id_area:
        cond.append("a.id_area = :id_area")
        params["id_area"] = id_area
    if id_espacio_ubicacion:
        cond.append("ub.id_espacio = :id_espacio_ubicacion")
        params["id_espacio_ubicacion"] = id_espacio_ubicacion
    return cond, params


async def _agregado_eventos(db, cond, params) -> dict:
    """Agregado de eventos + reservas del universo. `% asistencia` se mide SOLO
    sobre eventos ya realizados (fecha < hoy local): asistieron / vigentes."""
    r = await db.execute(text(f"""
        SELECT COUNT(*) AS eventos,
               COUNT(*) FILTER (WHERE ev.fecha < :hoy AND COALESCE(ee.codigo, '') <> 'cancelado') AS eventos_realizados,
               COUNT(*) FILTER (WHERE COALESCE(ee.codigo, '') = 'cancelado') AS eventos_cancelados,
               COALESCE(SUM(ev.capacidad_ciudadanos), 0) AS cupo_total,
               COALESCE(SUM(rs.reservas), 0) AS reservas,
               COALESCE(SUM(rs.vigentes), 0) AS vigentes,
               COALESCE(SUM(rs.asistieron), 0) AS asistieron,
               COALESCE(SUM(rs.canceladas), 0) AS canceladas,
               COALESCE(SUM(rs.autoservicio), 0) AS autoservicio,
               COALESCE(SUM(rs.vigentes) FILTER (WHERE ev.fecha < :hoy), 0) AS vigentes_realizados,
               COALESCE(SUM(rs.asistieron) FILTER (WHERE ev.fecha < :hoy), 0) AS asistieron_realizados
          FROM eventos ev {_JOIN_EVENTOS} {_LATERAL_RESERVAS}
         WHERE {' AND '.join(cond)}
    """), {**params, "hoy": hoy_local()})
    base = dict(r.fetchone()._mapping)
    return {
        **{k: int(v) for k, v in base.items()},
        "pct_asistencia": _pct(base["asistieron_realizados"], base["vigentes_realizados"]),
        "pct_cupo": _pct(base["vigentes"], base["cupo_total"]),
        "pct_autoservicio": _pct(base["autoservicio"], base["reservas"]),
    }


@router.get("/eventos")
async def at_eventos(
    limit: int = Query(20, ge=1, le=200),
    f: dict = Depends(_params_comunes),
    db: AsyncSession = Depends(get_db),
):
    """Eventos y reservas (Entradas + Agenda): eventos del periodo, cupo, reservas
    vigentes / asistencias / cancelaciones, % asistencia (eventos realizados),
    % cupo utilizado, origen; periodo anterior; y la tabla por evento."""
    cond, params = _where_eventos(**f)
    actual = await _agregado_eventos(db, cond, params)
    anterior = None
    ant_kw = _periodo_anterior_kwargs(f["desde"], f["hasta"], f["anio"], f["meses"])
    if ant_kw:
        cond_a, params_a = _where_eventos(
            id_area=f["id_area"], id_espacio_ubicacion=f["id_espacio_ubicacion"],
            id_tipo_prestacion=None, id_municipio=f["id_municipio"], **ant_kw)
        anterior = await _agregado_eventos(db, cond_a, params_a)

    r = await db.execute(text(f"""
        SELECT ev.id_evento, ev.nombre AS evento, ev.fecha, ev.hora_inicio,
               COALESCE(ee.codigo, 'activo') AS estado,
               COALESCE(ub.nombre, 'Sin ubicación') AS ubicacion,
               COALESCE(a.nombre, 'Sin gestión') AS gestion,
               ev.capacidad_ciudadanos AS cupo,
               rs.reservas, rs.vigentes, rs.asistieron, rs.canceladas, rs.autoservicio,
               (ev.fecha < :hoy) AS realizado
          FROM eventos ev {_JOIN_EVENTOS} {_LATERAL_RESERVAS}
         WHERE {' AND '.join(cond)}
         ORDER BY ev.fecha DESC, ev.hora_inicio DESC
         LIMIT :limit
    """), {**params, "hoy": hoy_local(), "limit": limit})
    por_evento = []
    for row in r.fetchall():
        m = dict(row._mapping)
        m["pct_cupo"] = _pct(m["vigentes"], m["cupo"] or 0)
        m["pct_asistencia"] = _pct(m["asistieron"], m["vigentes"]) if m["realizado"] else None
        por_evento.append(m)
    sin_asistencia = actual["vigentes"] - actual["asistieron"]
    por_estado = [
        {"estado": "asistio", "total": actual["asistieron"]},
        {"estado": "reservada", "total": sin_asistencia},
        {"estado": "cancelada", "total": actual["canceladas"]},
    ]
    return {
        **actual,
        "var_pct": _var_pct(actual["reservas"], (anterior or {}).get("reservas")),
        "anterior": anterior,
        "por_estado": [x for x in por_estado if x["total"]],
        "por_evento": por_evento,
    }


_SERIE_RESERVAS = """
    COALESCE(SUM(rs.reservas), 0)::int AS total,
    COALESCE(SUM(rs.asistieron), 0)::int AS asistio,
    COALESCE(SUM(rs.sin_asistencia), 0)::int AS reservada,
    COALESCE(SUM(rs.canceladas), 0)::int AS cancelada
"""


@router.get("/eventos/mensual")
async def at_eventos_mensual(
    f: dict = Depends(_params_comunes),
    db: AsyncSession = Depends(get_db),
):
    """Reservas por mes del evento, apiladas por estado (asistio / reservada / cancelada)."""
    cond, params = _where_eventos(**f)
    r = await db.execute(text(f"""
        SELECT to_char(ev.fecha, 'YYYY-MM') AS mes, {_SERIE_RESERVAS}
          FROM eventos ev {_JOIN_EVENTOS} {_LATERAL_RESERVAS} WHERE {' AND '.join(cond)}
         GROUP BY 1 HAVING COALESCE(SUM(rs.reservas), 0) > 0 ORDER BY 1
    """), params)
    return [dict(row._mapping) for row in r.fetchall()]


@router.get("/eventos/diario")
async def at_eventos_diario(
    mes: Optional[str] = Query(None),
    f: dict = Depends(_params_comunes),
    db: AsyncSession = Depends(get_db),
):
    cond, params = _where_eventos(**f, mes=mes)
    r = await db.execute(text(f"""
        SELECT to_char(ev.fecha, 'YYYY-MM-DD') AS dia, {_SERIE_RESERVAS}
          FROM eventos ev {_JOIN_EVENTOS} {_LATERAL_RESERVAS} WHERE {' AND '.join(cond)}
         GROUP BY 1 HAVING COALESCE(SUM(rs.reservas), 0) > 0 ORDER BY 1
    """), params)
    return [dict(row._mapping) for row in r.fetchall()]


# ── 8. Exportaciones (sin datos personales: el tablero es de gestion) ────────

@router.get("/turnos-detalle")
async def at_turnos_detalle(
    response: Response,
    limit: int = Query(50, ge=1, le=10000),
    offset: int = Query(0, ge=0, le=1_000_000),
    f: dict = Depends(_params_comunes),
    db: AsyncSession = Depends(get_db),
):
    """Turnos del universo filtrado para exportar (CSV en el front). Sin nombre ni
    DNI del vecino (Ley 25.326: el analisis es de gestion, no de personas).
    Header X-Total-Count con el total."""
    cond, params = _where_turnos(**f)
    r = await db.execute(text(f"""
        SELECT t.id_turno, t.fecha, t.hora_inicio, t.hora_fin, t.numero_diario, t.estado, t.origen,
               COALESCE(a.nombre, 'Sin gestión') AS gestion,
               COALESCE(ub.nombre, 'Sin ubicación') AS ubicacion,
               COALESCE(tp.nombre, 'Sin prestación') AS prestacion,
               CASE WHEN ag.id_agente IS NOT NULL THEN {_AGENTE_NOMBRE} END AS agente,
               ll.primer_llamado, ll.n_llamados,
               ROUND(({_ESPERA_MIN})::numeric, 0)::float AS espera_min,
               (ta.id_turno_atencion IS NOT NULL) AS atencion_registrada,
               enc.clasificacion_inicial AS csat,
               COUNT(*) OVER () AS total_count
          FROM turnos t {_JOIN_TURNOS}
         WHERE {' AND '.join(cond)}
         ORDER BY t.fecha DESC, t.hora_inicio DESC, t.id_turno DESC
         LIMIT :limit OFFSET :offset
    """), {**params, "limit": limit, "offset": offset})
    rows = [dict(row._mapping) for row in r.fetchall()]
    total = int(rows[0]["total_count"]) if rows else 0
    for m in rows:
        m.pop("total_count", None)
        m["n_llamados"] = int(m["n_llamados"] or 0)
    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return rows


@router.get("/guardia-detalle")
async def at_guardia_detalle(
    response: Response,
    limit: int = Query(50, ge=1, le=10000),
    offset: int = Query(0, ge=0, le=1_000_000),
    f: dict = Depends(_params_comunes),
    db: AsyncSession = Depends(get_db),
):
    """Derivaciones a la Guardia del periodo (sin datos del paciente)."""
    cond, params = _where_guardia(**f)
    r = await db.execute(text(f"""
        SELECT x.id_emergencia_atencion, ev.numero_operativo, x.estado,
               x.derivado_en, x.atendido_en,
               ROUND(({_DEMORA_MIN})::numeric, 0)::float AS demora_min,
               COALESCE(et.nombre, 'Sin tipo') AS tipo,
               COALESCE(ep.nombre, 'Sin prioridad') AS prioridad,
               COALESCE(ub.nombre, 'Sin ubicación') AS ubicacion,
               CASE WHEN ag.id_agente IS NOT NULL THEN {_AGENTE_NOMBRE} END AS agente,
               (x.id_ciudadano IS NOT NULL) AS con_ciudadano,
               COUNT(*) OVER () AS total_count
          FROM emergencia_atencion x {_JOIN_GUARDIA}
         WHERE {' AND '.join(cond)}
         ORDER BY x.derivado_en DESC
         LIMIT :limit OFFSET :offset
    """), {**params, "limit": limit, "offset": offset})
    rows = [dict(row._mapping) for row in r.fetchall()]
    total = int(rows[0]["total_count"]) if rows else 0
    for m in rows:
        m.pop("total_count", None)
    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return rows


# ── 9. Catalogos de los filtros ──────────────────────────────────────────────

@router.get("/catalogo/gestiones")
async def at_catalogo_gestiones(db: AsyncSession = Depends(get_db)):
    """Gestiones = areas activas con alguna ubicacion activa, prestacion o evento
    (las areas que solo tienen reclamos no son gestiones de atencion)."""
    r = await db.execute(text("""
        SELECT a.id_area, a.nombre
          FROM area a
         WHERE a.activo = TRUE AND (
               EXISTS (SELECT 1 FROM espacios_agenda e JOIN subarea s ON s.id_subarea = e.id_subarea
                        WHERE s.id_area = a.id_area AND e.activo = TRUE)
            OR EXISTS (SELECT 1 FROM tipo_prestacion tp JOIN subarea s ON s.id_subarea = tp.id_subarea
                        WHERE s.id_area = a.id_area)
            OR EXISTS (SELECT 1 FROM eventos ev JOIN subarea s ON s.id_subarea = ev.id_subarea
                        WHERE s.id_area = a.id_area AND ev.activo = TRUE))
         ORDER BY a.nombre
    """))
    return [{"id_area": row.id_area, "nombre": row.nombre} for row in r.fetchall()]


@router.get("/catalogo/ubicaciones")
async def at_catalogo_ubicaciones(
    id_area: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Ubicaciones (espacios activos) con su gestion, opcionalmente de un area."""
    cond = ["e.activo = TRUE"]
    params: dict = {}
    if id_area:
        cond.append("a.id_area = :id_area")
        params["id_area"] = id_area
    r = await db.execute(text(f"""
        SELECT e.id_espacio, e.nombre, a.id_area, COALESCE(a.nombre, 'Sin gestión') AS gestion
          FROM espacios_agenda e
          LEFT JOIN subarea s ON s.id_subarea = e.id_subarea
          LEFT JOIN area a ON a.id_area = s.id_area
         WHERE {' AND '.join(cond)}
         ORDER BY a.nombre NULLS LAST, e.nombre
    """), params)
    return [dict(row._mapping) for row in r.fetchall()]


@router.get("/catalogo/prestaciones")
async def at_catalogo_prestaciones(
    id_area: Optional[int] = Query(None),
    id_espacio_ubicacion: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Prestaciones (activas o con turnos) de una gestion / ubicacion."""
    cond = ["(tp.activo = TRUE OR EXISTS (SELECT 1 FROM turnos t WHERE t.id_tipo_prestacion = tp.id_tipo_prestacion))"]
    params: dict = {}
    if id_area:
        cond.append("a.id_area = :id_area")
        params["id_area"] = id_area
    if id_espacio_ubicacion:
        cond.append("COALESCE(tp.id_espacio_ubicacion, tp.id_espacio) = :ie")
        params["ie"] = id_espacio_ubicacion
    r = await db.execute(text(f"""
        SELECT tp.id_tipo_prestacion, tp.nombre, tp.activo,
               COALESCE(tp.id_espacio_ubicacion, tp.id_espacio) AS id_espacio_ubicacion
          FROM tipo_prestacion tp
          LEFT JOIN espacios_agenda ub ON ub.id_espacio = COALESCE(tp.id_espacio_ubicacion, tp.id_espacio)
          LEFT JOIN subarea s ON s.id_subarea = COALESCE(ub.id_subarea, tp.id_subarea)
          LEFT JOIN area a ON a.id_area = s.id_area
         WHERE {' AND '.join(cond)}
         ORDER BY tp.activo DESC, tp.nombre
    """), params)
    return [dict(row._mapping) for row in r.fetchall()]
