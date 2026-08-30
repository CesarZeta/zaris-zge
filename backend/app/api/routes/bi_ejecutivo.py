"""
ZARIS API — BI Ejecutivo ("Análisis de demanda ciudadana", 2026-08-30).
Prefijo: /api/v1/bi/ejecutivo/*

Replica los 5 tableros Power BI de referencia (VL) sobre los datos reales:
  1. Resumen del período (score cierre/SLA/satisfacción + matriz subárea→tipo)
  2. Evolución de indicadores (altas vs cierres, %cierre/%SLA/%sat mensual)
  3. Histórico por subárea / canal / localidad
  4. Mayores incidentes (por cantidad y por demora)
  5. Satisfacción vs cierre (+ mapas)

Decisiones de César (2026-08-30):
  - El filtro global es PERÍODO + ÁREA; el desglose de todas las vistas es por
    SUBÁREA (las "áreas de servicio" de los tableros VL son nuestras subáreas).
  - La dimensión LOCALIDAD sale de reclamos.id_localidad (backfill desde lat/lon
    + derivación automática en los creates, misma fecha).

Convenciones (espejo de bi.py):
  - Área vía subárea (§27): JOIN tipo_reclamo → subarea → area.
  - Mono-municipio: id_municipio NULL cuenta como el municipio por defecto.
  - Agregación 100% en SQL; el frontend solo dibuja.
  - Satisfacción: encuesta_envio (id_reclamo) + encuesta_respuesta.
    clasificacion_inicial 1-5; satisfecho = >=4 (regla del módulo Encuestas).
    %Rep = respuestas/enviadas · %Sat = satisfechos/respuestas.
Auth: guard JWT a nivel router (§39); la UI gatea nivel <= 2 como el resto de DATOS.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.api.routes.bi import _DIAS_CIERRE, _JOIN_AREA, _parse_meses

router = APIRouter(
    prefix="/api/v1/bi/ejecutivo",
    tags=["BI Ejecutivo"],
    dependencies=[Depends(get_current_user)],
)

# Join de encuestas de reclamos: un envío por fila (contar envíos = correcto para
# %Rep); la respuesta existe solo si el vecino completó.
_JOIN_ENC = """
    JOIN encuesta_envio ev ON ev.id_reclamo = r.id_reclamo AND ev.activo = TRUE
    LEFT JOIN encuesta_respuesta resp ON resp.id_envio = ev.id_encuesta_envio
"""

_ESTADOS_ABIERTOS = "('Sin asignar','En gestión','En espera','En auditoría')"


# ── Filtros ──────────────────────────────────────────────────────────────────

def _where_ej(
    desde: Optional[date], hasta: Optional[date],
    id_area: Optional[int], prioridad: Optional[str],
    id_localidad: Optional[int], id_municipio: int,
    *, anio: Optional[int] = None, meses: Optional[list[int]] = None,
    campo_fecha: str = "fecha_alta",
) -> tuple[list[str], dict]:
    """Condiciones WHERE del Ejecutivo. El área via s.id_area (la query debe
    incluir _JOIN_AREA). Mismo criterio mono-municipio que bi.py."""
    cond = [
        "r.activo = TRUE",
        "(r.id_municipio = :id_municipio OR r.id_municipio IS NULL)",
    ]
    params: dict = {"id_municipio": id_municipio}
    if desde:
        cond.append(f"r.{campo_fecha} >= :desde")
        params["desde"] = desde
    if hasta:
        cond.append(f"r.{campo_fecha} < :hasta_excl")
        params["hasta_excl"] = hasta + timedelta(days=1)
    if anio:
        cond.append(f"EXTRACT(YEAR FROM r.{campo_fecha})::int = :anio")
        params["anio"] = int(anio)
    if meses:
        cond.append(f"EXTRACT(MONTH FROM r.{campo_fecha})::int = ANY(CAST(:meses AS int[]))")
        params["meses"] = [int(m) for m in meses]
    if id_area:
        cond.append("s.id_area = :id_area")
        params["id_area"] = id_area
    if prioridad:
        cond.append("r.prioridad = :prioridad")
        params["prioridad"] = prioridad
    if id_localidad:
        cond.append("r.id_localidad = :id_localidad")
        params["id_localidad"] = id_localidad
    return cond, params


def _rango_anterior(
    desde: Optional[date], hasta: Optional[date],
    anio: Optional[int], meses: Optional[list[int]],
) -> Optional[dict]:
    """Período anterior equivalente para el % Var (como el "% Var M" de VL pero
    generalizado al filtro elegido): mismo largo inmediatamente anterior para un
    rango manual; mismos meses del año anterior para chips. Sin filtro temporal
    no hay comparación (None)."""
    if anio:
        return {"anio": anio - 1, "meses": meses}
    if desde and hasta:
        largo = (hasta - desde) + timedelta(days=1)
        return {"desde": desde - largo, "hasta": desde - timedelta(days=1)}
    return None


def _pct(num, den, nd=1):
    return round(num / den * 100, nd) if den else None


def _var_pct(actual, anterior):
    if anterior in (None, 0):
        return None
    return round((actual - anterior) / anterior * 100, 1)


_Q = dict  # alias corto para armar filas de respuesta


# ── Agregados compartidos (matriz + top-tipos) ───────────────────────────────

async def _agregado(
    db: AsyncSession, grp_sql: str, n_grp: int,
    cond: list[str], params: dict,
) -> list[dict]:
    """Universo (fecha_alta) agrupado por `grp_sql` (las primeras `n_grp`
    columnas del SELECT — GROUP BY posicional porque los alias `AS` no son
    válidos en GROUP BY): total, resueltos, prom días de cierre, dentro/con SLA.
    Base de la matriz y de los tops."""
    r = await db.execute(text(f"""
        SELECT {grp_sql},
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE r.estado = 'Resuelto') AS resueltos,
               ROUND(AVG({_DIAS_CIERRE}) FILTER (WHERE r.estado = 'Resuelto' AND r.fecha_cierre IS NOT NULL), 1)::float AS prom_dias,
               COUNT(*) FILTER (WHERE r.estado = 'Resuelto' AND r.fecha_cierre IS NOT NULL
                                AND tr.sla_dias IS NOT NULL AND {_DIAS_CIERRE} <= tr.sla_dias) AS dentro_sla,
               COUNT(*) FILTER (WHERE r.estado = 'Resuelto' AND r.fecha_cierre IS NOT NULL
                                AND tr.sla_dias IS NOT NULL) AS con_sla
        FROM reclamos r {_JOIN_AREA}
        WHERE {' AND '.join(cond)}
        GROUP BY {', '.join(str(i + 1) for i in range(n_grp))}
    """), params)
    return [dict(row._mapping) for row in r.fetchall()]


async def _encuestas(
    db: AsyncSession, grp_sql: str, n_grp: int,
    cond: list[str], params: dict,
) -> dict[tuple, dict]:
    """Encuestas del universo agrupadas: enviadas / respuestas / satisfechos.
    GROUP BY posicional (mismo motivo que _agregado)."""
    r = await db.execute(text(f"""
        SELECT {grp_sql},
               COUNT(*) AS enviadas,
               COUNT(resp.id_encuesta_respuesta) AS respuestas,
               COUNT(resp.id_encuesta_respuesta) FILTER (WHERE resp.clasificacion_inicial >= 4) AS satisfechos
        FROM reclamos r {_JOIN_AREA} {_JOIN_ENC}
        WHERE {' AND '.join(cond)}
        GROUP BY {', '.join(str(i + 1) for i in range(n_grp))}
    """), params)
    out = {}
    for row in r.fetchall():
        m = dict(row._mapping)
        clave = tuple(v for k, v in m.items() if k not in ("enviadas", "respuestas", "satisfechos"))
        out[clave] = m
    return out


def _fila(base: dict, enc: Optional[dict], total_ant: Optional[int]) -> dict:
    """Arma la fila estándar de la matriz/tops a partir de los agregados."""
    respuestas = (enc or {}).get("respuestas") or 0
    enviadas = (enc or {}).get("enviadas") or 0
    return {
        "total": base["total"],
        "var_pct": _var_pct(base["total"], total_ant),
        "prom_dias": base["prom_dias"],
        "pct_cierre": _pct(base["resueltos"], base["total"]),
        "pct_sla": _pct(base["dentro_sla"], base["con_sla"]),
        "pct_sat": _pct((enc or {}).get("satisfechos") or 0, respuestas),
        "pct_rep": _pct(respuestas, enviadas),
    }


# ── 1. Score del período ─────────────────────────────────────────────────────

@router.get("/score", responses={422: {"description": "Parámetros de período inválidos"}})  # marker OpenAPI §9
async def ej_score(
    desde: Optional[date] = Query(None), hasta: Optional[date] = Query(None),
    anio: Optional[int] = Query(None), meses: Optional[str] = Query(None),
    id_area: Optional[int] = Query(None), prioridad: Optional[str] = Query(None),
    id_localidad: Optional[int] = Query(None), id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Tarjetas de arriba: total vs período anterior, score (% cierre / % SLA /
    % satisfacción), tasa de respuesta de encuestas y niveles 1-5."""
    meses_l = _parse_meses(meses)
    cond, params = _where_ej(desde, hasta, id_area, prioridad, id_localidad, id_municipio, anio=anio, meses=meses_l)

    r = await db.execute(text(f"""
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE r.estado = 'Resuelto') AS resueltos,
               COUNT(*) FILTER (WHERE r.estado IN {_ESTADOS_ABIERTOS}) AS abiertos,
               ROUND(AVG({_DIAS_CIERRE}) FILTER (WHERE r.estado = 'Resuelto' AND r.fecha_cierre IS NOT NULL), 1)::float AS prom_dias,
               COUNT(*) FILTER (WHERE r.estado = 'Resuelto' AND r.fecha_cierre IS NOT NULL
                                AND tr.sla_dias IS NOT NULL AND {_DIAS_CIERRE} <= tr.sla_dias) AS dentro_sla,
               COUNT(*) FILTER (WHERE r.estado = 'Resuelto' AND r.fecha_cierre IS NOT NULL
                                AND tr.sla_dias IS NOT NULL) AS con_sla
        FROM reclamos r {_JOIN_AREA}
        WHERE {' AND '.join(cond)}
    """), params)
    u = r.fetchone()

    re_ = await db.execute(text(f"""
        SELECT COUNT(*) AS enviadas,
               COUNT(resp.id_encuesta_respuesta) AS respuestas,
               COUNT(resp.id_encuesta_respuesta) FILTER (WHERE resp.clasificacion_inicial >= 4) AS satisfechos
        FROM reclamos r {_JOIN_AREA} {_JOIN_ENC}
        WHERE {' AND '.join(cond)}
    """), params)
    e = re_.fetchone()

    rn = await db.execute(text(f"""
        SELECT resp.clasificacion_inicial AS clasificacion, COUNT(*) AS total
        FROM reclamos r {_JOIN_AREA} {_JOIN_ENC}
        WHERE {' AND '.join(cond)} AND resp.id_encuesta_respuesta IS NOT NULL
        GROUP BY resp.clasificacion_inicial
        ORDER BY resp.clasificacion_inicial
    """), params)
    niveles = [dict(row._mapping) for row in rn.fetchall()]

    total_ant = None
    ant = _rango_anterior(desde, hasta, anio, meses_l)
    if ant:
        cond_a, params_a = _where_ej(
            ant.get("desde"), ant.get("hasta"), id_area, prioridad, id_localidad,
            id_municipio, anio=ant.get("anio"), meses=ant.get("meses"))
        ra = await db.execute(text(
            f"SELECT COUNT(*) AS total FROM reclamos r {_JOIN_AREA} WHERE {' AND '.join(cond_a)}"), params_a)
        total_ant = int(ra.scalar() or 0)

    return {
        "total": u.total,
        "abiertos": u.abiertos,
        "total_anterior": total_ant,
        "var_pct": _var_pct(u.total, total_ant),
        "prom_dias": u.prom_dias,
        "pct_cierre": _pct(u.resueltos, u.total),
        "pct_sla": _pct(u.dentro_sla, u.con_sla),
        "pct_sat": _pct(e.satisfechos, e.respuestas),
        "tasa_respuesta": _pct(e.respuestas, e.enviadas),
        "encuestas_enviadas": e.enviadas,
        "encuestas_respondidas": e.respuestas,
        "niveles": niveles,
    }


# ── 2. Matriz subárea → tipo ─────────────────────────────────────────────────

@router.get("/matriz")
async def ej_matriz(
    desde: Optional[date] = Query(None), hasta: Optional[date] = Query(None),
    anio: Optional[int] = Query(None), meses: Optional[str] = Query(None),
    id_area: Optional[int] = Query(None), prioridad: Optional[str] = Query(None),
    id_localidad: Optional[int] = Query(None), id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """La tabla central del tablero VL: una fila por SUBÁREA (expandible a tipo)
    con Total · %Var · Prom días · %Cierre · %SLA · %Sat · %Rep."""
    meses_l = _parse_meses(meses)
    cond, params = _where_ej(desde, hasta, id_area, prioridad, id_localidad, id_municipio, anio=anio, meses=meses_l)

    g_sub = "s.id_subarea AS id_subarea, COALESCE(s.nombre, 'Sin subárea') AS subarea"
    g_tipo = ("s.id_subarea AS id_subarea, tr.id_tipo_reclamo AS id_tipo, "
              "COALESCE(tr.nombre, 'Sin tipo') AS tipo")
    base_sub = await _agregado(db, g_sub, 2, cond, params)
    base_tipo = await _agregado(db, g_tipo, 3, cond, params)
    enc_sub = await _encuestas(db, "s.id_subarea AS id_subarea, COALESCE(s.nombre,'') AS subarea", 2, cond, params)
    enc_tipo = await _encuestas(db, "s.id_subarea AS id_subarea, tr.id_tipo_reclamo AS id_tipo, COALESCE(tr.nombre,'') AS tipo", 3, cond, params)
    enc_sub = {k[0]: v for k, v in enc_sub.items()}
    enc_tipo = {(k[0], k[1]): v for k, v in enc_tipo.items()}

    ant_sub: dict = {}
    ant_tipo: dict = {}
    ant = _rango_anterior(desde, hasta, anio, meses_l)
    if ant:
        cond_a, params_a = _where_ej(
            ant.get("desde"), ant.get("hasta"), id_area, prioridad, id_localidad,
            id_municipio, anio=ant.get("anio"), meses=ant.get("meses"))
        for b in await _agregado(db, g_sub, 2, cond_a, params_a):
            ant_sub[b["id_subarea"]] = b["total"]
        for b in await _agregado(db, g_tipo, 3, cond_a, params_a):
            ant_tipo[(b["id_subarea"], b["id_tipo"])] = b["total"]

    tipos_por_sub: dict = {}
    for b in sorted(base_tipo, key=lambda x: -x["total"]):
        clave = (b["id_subarea"], b["id_tipo"])
        fila = _fila(b, enc_tipo.get(clave), ant_tipo.get(clave) if ant else None)
        fila.update({"id_tipo": b["id_tipo"], "tipo": b["tipo"]})
        tipos_por_sub.setdefault(b["id_subarea"], []).append(fila)

    filas = []
    for b in sorted(base_sub, key=lambda x: -x["total"]):
        fila = _fila(b, enc_sub.get(b["id_subarea"]), ant_sub.get(b["id_subarea"]) if ant else None)
        fila.update({
            "id_subarea": b["id_subarea"], "subarea": b["subarea"],
            "tipos": tipos_por_sub.get(b["id_subarea"], []),
        })
        filas.append(fila)

    # Fila total (ponderada desde los agregados, no promediando porcentajes).
    tot = {
        "total": sum(b["total"] for b in base_sub),
        "resueltos": sum(b["resueltos"] for b in base_sub),
        "dentro_sla": sum(b["dentro_sla"] for b in base_sub),
        "con_sla": sum(b["con_sla"] for b in base_sub),
        "prom_dias": None,
    }
    enc_tot = {
        "enviadas": sum((v.get("enviadas") or 0) for v in enc_sub.values()),
        "respuestas": sum((v.get("respuestas") or 0) for v in enc_sub.values()),
        "satisfechos": sum((v.get("satisfechos") or 0) for v in enc_sub.values()),
    }
    total_fila = _fila(tot, enc_tot, sum(ant_sub.values()) if ant_sub else None)

    return {"filas": filas, "total": total_fila}


# ── 3. Mayores incidentes (por cantidad / por demora) ────────────────────────

@router.get("/top-tipos")
async def ej_top_tipos(
    orden: str = Query("cantidad", description="cantidad | demora"),
    limit: int = Query(10, ge=1, le=50),
    desde: Optional[date] = Query(None), hasta: Optional[date] = Query(None),
    anio: Optional[int] = Query(None), meses: Optional[str] = Query(None),
    id_area: Optional[int] = Query(None), prioridad: Optional[str] = Query(None),
    id_localidad: Optional[int] = Query(None), id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Top de tipos por cantidad (mayores incidentes) o por promedio de días de
    cierre (mayores tiempos de respuesta), con la subárea de cada tipo."""
    if orden not in ("cantidad", "demora"):
        raise HTTPException(status_code=422, detail="orden debe ser cantidad|demora")
    meses_l = _parse_meses(meses)
    cond, params = _where_ej(desde, hasta, id_area, prioridad, id_localidad, id_municipio, anio=anio, meses=meses_l)

    g = ("tr.id_tipo_reclamo AS id_tipo, COALESCE(tr.nombre,'Sin tipo') AS tipo, "
         "COALESCE(s.nombre,'Sin subárea') AS subarea")
    base = await _agregado(db, g, 3, cond, params)
    enc = await _encuestas(db, "tr.id_tipo_reclamo AS id_tipo", 1, cond, params)
    enc = {k[0]: v for k, v in enc.items()}

    if orden == "demora":
        base = [b for b in base if b["prom_dias"] is not None]
        base.sort(key=lambda x: (-(x["prom_dias"] or 0), -x["total"]))
    else:
        base.sort(key=lambda x: -x["total"])

    out = []
    for b in base[:limit]:
        fila = _fila(b, enc.get(b["id_tipo"]), None)
        fila.update({"id_tipo": b["id_tipo"], "tipo": b["tipo"], "subarea": b["subarea"]})
        out.append(fila)
    return out


# ── 4. Series mensuales ──────────────────────────────────────────────────────

@router.get("/altas-cierres")
async def ej_altas_cierres(
    desde: Optional[date] = Query(None), hasta: Optional[date] = Query(None),
    anio: Optional[int] = Query(None), meses: Optional[str] = Query(None),
    id_area: Optional[int] = Query(None), prioridad: Optional[str] = Query(None),
    id_localidad: Optional[int] = Query(None), id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Relación incidentes y cierres: por mes, altas (fecha_alta) vs cerrados
    (fecha_cierre). Cada serie usa SU campo de fecha para el filtro temporal."""
    meses_l = _parse_meses(meses)

    async def serie(campo: str) -> dict[str, int]:
        cond, params = _where_ej(desde, hasta, id_area, prioridad, id_localidad,
                                 id_municipio, anio=anio, meses=meses_l, campo_fecha=campo)
        if campo == "fecha_cierre":
            cond.append("r.fecha_cierre IS NOT NULL")
            cond.append("r.estado = 'Resuelto'")
        r = await db.execute(text(f"""
            SELECT to_char(date_trunc('month', r.{campo}), 'YYYY-MM') AS mes, COUNT(*) AS total
            FROM reclamos r {_JOIN_AREA}
            WHERE {' AND '.join(cond)}
            GROUP BY 1 ORDER BY 1
        """), params)
        return {row.mes: row.total for row in r.fetchall()}

    altas = await serie("fecha_alta")
    cierres = await serie("fecha_cierre")
    meses_todos = sorted(set(altas) | set(cierres))
    return [{"mes": m, "altas": altas.get(m, 0), "cierres": cierres.get(m, 0)} for m in meses_todos]


@router.get("/evolucion-indicadores")
async def ej_evolucion_indicadores(
    desde: Optional[date] = Query(None), hasta: Optional[date] = Query(None),
    anio: Optional[int] = Query(None), meses: Optional[str] = Query(None),
    id_area: Optional[int] = Query(None), prioridad: Optional[str] = Query(None),
    id_localidad: Optional[int] = Query(None), id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """% Cierre, % SLA y % Satisfacción por mes (cohorte de ingreso: los reclamos
    de cada mes por fecha_alta, como la 'Evolución de indicadores' de VL)."""
    meses_l = _parse_meses(meses)
    cond, params = _where_ej(desde, hasta, id_area, prioridad, id_localidad, id_municipio, anio=anio, meses=meses_l)

    r = await db.execute(text(f"""
        SELECT to_char(date_trunc('month', r.fecha_alta), 'YYYY-MM') AS mes,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE r.estado = 'Resuelto') AS resueltos,
               COUNT(*) FILTER (WHERE r.estado = 'Resuelto' AND r.fecha_cierre IS NOT NULL
                                AND tr.sla_dias IS NOT NULL AND {_DIAS_CIERRE} <= tr.sla_dias) AS dentro_sla,
               COUNT(*) FILTER (WHERE r.estado = 'Resuelto' AND r.fecha_cierre IS NOT NULL
                                AND tr.sla_dias IS NOT NULL) AS con_sla
        FROM reclamos r {_JOIN_AREA}
        WHERE {' AND '.join(cond)}
        GROUP BY 1 ORDER BY 1
    """), params)
    universo = [dict(row._mapping) for row in r.fetchall()]

    re_ = await db.execute(text(f"""
        SELECT to_char(date_trunc('month', r.fecha_alta), 'YYYY-MM') AS mes,
               COUNT(resp.id_encuesta_respuesta) AS respuestas,
               COUNT(resp.id_encuesta_respuesta) FILTER (WHERE resp.clasificacion_inicial >= 4) AS satisfechos
        FROM reclamos r {_JOIN_AREA} {_JOIN_ENC}
        WHERE {' AND '.join(cond)}
        GROUP BY 1
    """), params)
    enc = {row.mes: row for row in re_.fetchall()}

    out = []
    for u in universo:
        e = enc.get(u["mes"])
        out.append({
            "mes": u["mes"],
            "total": u["total"],
            "pct_cierre": _pct(u["resueltos"], u["total"]),
            "pct_sla": _pct(u["dentro_sla"], u["con_sla"]),
            "pct_sat": _pct(e.satisfechos, e.respuestas) if e else None,
        })
    return out


@router.get("/cierres-por-estado")
async def ej_cierres_por_estado(
    desde: Optional[date] = Query(None), hasta: Optional[date] = Query(None),
    anio: Optional[int] = Query(None), meses: Optional[str] = Query(None),
    id_area: Optional[int] = Query(None), prioridad: Optional[str] = Query(None),
    id_localidad: Optional[int] = Query(None), id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Cierres del período: Auditado = el reclamo pasó por 'En auditoría' en su
    historial (espejo del 'Cumplido/Auditado' de VL)."""
    meses_l = _parse_meses(meses)
    cond, params = _where_ej(desde, hasta, id_area, prioridad, id_localidad, id_municipio, anio=anio, meses=meses_l)
    cond.append("r.estado = 'Resuelto'")
    r = await db.execute(text(f"""
        SELECT COUNT(*) FILTER (WHERE EXISTS (
                   SELECT 1 FROM reclamo_historial h
                   WHERE h.id_reclamo = r.id_reclamo AND h.estado_nuevo = 'En auditoría')) AS auditados,
               COUNT(*) AS total
        FROM reclamos r {_JOIN_AREA}
        WHERE {' AND '.join(cond)}
    """), params)
    row = r.fetchone()
    auditados = row.auditados or 0
    return [
        {"estado": "Cumplido", "total": (row.total or 0) - auditados},
        {"estado": "Auditado", "total": auditados},
    ]


# ── 5. Históricos por dimensión (subárea / canal / localidad) ────────────────

_DIMS = {
    "subarea": ("COALESCE(s.nombre, 'Sin subárea')", 8),
    "canal": ("COALESCE(r.canal_origen, 'sin_dato')", 8),
    "localidad": ("COALESCE(loc.nombre, 'Sin localidad')", 10),
}
_JOIN_LOC = "\n    LEFT JOIN localidades loc ON loc.id_localidad = r.id_localidad\n"


@router.get("/historico")
async def ej_historico(
    dim: str = Query("subarea", description="subarea | canal | localidad"),
    desde: Optional[date] = Query(None), hasta: Optional[date] = Query(None),
    anio: Optional[int] = Query(None), meses: Optional[str] = Query(None),
    id_area: Optional[int] = Query(None), prioridad: Optional[str] = Query(None),
    id_localidad: Optional[int] = Query(None), id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Serie mensual apilada por dimensión (top N + 'Otros'), shape
    {series, items} compatible con HistogramaTemporal (modo dinámico)."""
    if dim not in _DIMS:
        raise HTTPException(status_code=422, detail="dim debe ser subarea|canal|localidad")
    expr, top_n = _DIMS[dim]
    meses_l = _parse_meses(meses)
    cond, params = _where_ej(desde, hasta, id_area, prioridad, id_localidad, id_municipio, anio=anio, meses=meses_l)
    join = _JOIN_AREA + (_JOIN_LOC if dim == "localidad" else "")

    r = await db.execute(text(f"""
        SELECT to_char(date_trunc('month', r.fecha_alta), 'YYYY-MM') AS mes,
               {expr} AS grupo, COUNT(*) AS total
        FROM reclamos r {join}
        WHERE {' AND '.join(cond)}
        GROUP BY 1, 2 ORDER BY 1
    """), params)
    crudo = [dict(row._mapping) for row in r.fetchall()]

    # Pivot en Python (mismo patrón que /bi/mensual-por-tipo): top N + Otros.
    totales: dict[str, int] = {}
    for c in crudo:
        totales[c["grupo"]] = totales.get(c["grupo"], 0) + c["total"]
    tops = [g for g, _ in sorted(totales.items(), key=lambda kv: -kv[1])[:top_n]]
    hay_otros = len(totales) > len(tops)

    def clave(nombre: str) -> str:
        return "g_" + "".join(ch if ch.isalnum() else "_" for ch in nombre.lower())

    series = [{"key": clave(g), "name": g} for g in tops]
    if hay_otros:
        series.append({"key": "g_otros", "name": "Otros"})

    items: dict[str, dict] = {}
    for c in crudo:
        it = items.setdefault(c["mes"], {"mes": c["mes"], "total": 0})
        k = clave(c["grupo"]) if c["grupo"] in tops else "g_otros"
        it[k] = it.get(k, 0) + c["total"]
        it["total"] += c["total"]
    return {"series": series, "items": [items[m] for m in sorted(items)]}


@router.get("/por-localidad")
async def ej_por_localidad(
    desde: Optional[date] = Query(None), hasta: Optional[date] = Query(None),
    anio: Optional[int] = Query(None), meses: Optional[str] = Query(None),
    id_area: Optional[int] = Query(None), prioridad: Optional[str] = Query(None),
    id_localidad: Optional[int] = Query(None), id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Composición del período por localidad (dona)."""
    meses_l = _parse_meses(meses)
    cond, params = _where_ej(desde, hasta, id_area, prioridad, id_localidad, id_municipio, anio=anio, meses=meses_l)
    r = await db.execute(text(f"""
        SELECT r.id_localidad, COALESCE(loc.nombre, 'Sin localidad') AS localidad, COUNT(*) AS total
        FROM reclamos r {_JOIN_AREA} {_JOIN_LOC}
        WHERE {' AND '.join(cond)}
        GROUP BY 1, 2 ORDER BY 3 DESC
    """), params)
    return [dict(row._mapping) for row in r.fetchall()]


# ── 6. Satisfacción vs cierre ────────────────────────────────────────────────

@router.get("/sat-cierre")
async def ej_sat_cierre(
    por: str = Query("subarea", description="subarea | localidad"),
    desde: Optional[date] = Query(None), hasta: Optional[date] = Query(None),
    anio: Optional[int] = Query(None), meses: Optional[str] = Query(None),
    id_area: Optional[int] = Query(None), prioridad: Optional[str] = Query(None),
    id_localidad: Optional[int] = Query(None), id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Barras % Satisfacción vs % Cierre por subárea o por localidad."""
    if por not in ("subarea", "localidad"):
        raise HTTPException(status_code=422, detail="por debe ser subarea|localidad")
    expr = "COALESCE(s.nombre, 'Sin subárea')" if por == "subarea" else "COALESCE(loc.nombre, 'Sin localidad')"
    join = _JOIN_AREA + (_JOIN_LOC if por == "localidad" else "")
    meses_l = _parse_meses(meses)
    cond, params = _where_ej(desde, hasta, id_area, prioridad, id_localidad, id_municipio, anio=anio, meses=meses_l)

    r = await db.execute(text(f"""
        SELECT {expr} AS nombre, COUNT(*) AS total,
               COUNT(*) FILTER (WHERE r.estado = 'Resuelto') AS resueltos
        FROM reclamos r {join}
        WHERE {' AND '.join(cond)}
        GROUP BY 1
    """), params)
    base = {row.nombre: dict(row._mapping) for row in r.fetchall()}

    re_ = await db.execute(text(f"""
        SELECT {expr} AS nombre,
               COUNT(resp.id_encuesta_respuesta) AS respuestas,
               COUNT(resp.id_encuesta_respuesta) FILTER (WHERE resp.clasificacion_inicial >= 4) AS satisfechos
        FROM reclamos r {join} {_JOIN_ENC}
        WHERE {' AND '.join(cond)}
        GROUP BY 1
    """), params)
    enc = {row.nombre: row for row in re_.fetchall()}

    out = []
    for nombre, b in sorted(base.items(), key=lambda kv: -kv[1]["total"]):
        e = enc.get(nombre)
        out.append({
            "nombre": nombre,
            "total": b["total"],
            "pct_cierre": _pct(b["resueltos"], b["total"]),
            "pct_sat": _pct(e.satisfechos, e.respuestas) if e and e.respuestas else None,
        })
    return out


# ── 7. Geo (mapas de satisfacción y de cierres) ──────────────────────────────

@router.get("/geo")
async def ej_geo(
    desde: Optional[date] = Query(None), hasta: Optional[date] = Query(None),
    anio: Optional[int] = Query(None), meses: Optional[str] = Query(None),
    id_area: Optional[int] = Query(None), prioridad: Optional[str] = Query(None),
    id_localidad: Optional[int] = Query(None), id_municipio: int = Query(1),
    limit: int = Query(5000, ge=1, le=20000),
    db: AsyncSession = Depends(get_db),
):
    """Puntos del período con coordenadas: abierto/cerrado + clasificación CSAT
    (si el vecino respondió). Un dataset para los dos mapas del tablero."""
    meses_l = _parse_meses(meses)
    cond, params = _where_ej(desde, hasta, id_area, prioridad, id_localidad, id_municipio, anio=anio, meses=meses_l)
    cond.append("r.latitud IS NOT NULL AND r.longitud IS NOT NULL")
    params["lim"] = limit
    r = await db.execute(text(f"""
        SELECT r.id_reclamo, r.nro_reclamo, r.estado, r.prioridad,
               COALESCE(tr.nombre, '') AS tipo_nombre, r.descripcion,
               r.latitud::float AS latitud, r.longitud::float AS longitud,
               (r.estado IN ('Resuelto','Cancelado')) AS cerrado,
               (SELECT MAX(resp.clasificacion_inicial)
                FROM encuesta_envio ev
                JOIN encuesta_respuesta resp ON resp.id_envio = ev.id_encuesta_envio
                WHERE ev.id_reclamo = r.id_reclamo AND ev.activo = TRUE) AS clasificacion
        FROM reclamos r {_JOIN_AREA}
        WHERE {' AND '.join(cond)}
        ORDER BY r.fecha_alta DESC
        LIMIT :lim
    """), params)
    return [dict(row._mapping) for row in r.fetchall()]


# ── Catálogo de localidades con reclamos (para el filtro del tablero) ────────

@router.get("/catalogo/localidades")
async def ej_catalogo_localidades(
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Localidades que aparecen en reclamos (para poblar el filtro sin traer el
    catálogo nacional entero)."""
    r = await db.execute(text("""
        SELECT loc.id_localidad, loc.nombre, COUNT(*) AS total
        FROM reclamos r
        JOIN localidades loc ON loc.id_localidad = r.id_localidad
        WHERE r.activo = TRUE AND (r.id_municipio = :m OR r.id_municipio IS NULL)
        GROUP BY 1, 2 ORDER BY loc.nombre
    """), {"m": id_municipio})
    return [dict(row._mapping) for row in r.fetchall()]
