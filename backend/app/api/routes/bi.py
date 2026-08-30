# -*- coding: utf-8 -*-
"""
ZARIS API - Modulo BI (Analisis de datos de gestion).
Fase 1: Resumen. Fase 2: Resueltos / SLA (tiempos de cierre). Fase 3: Pendientes.
Fase 4: Subreclamos (reclamos con id_reclamo_padre — "intervenciones").

Endpoints de AGREGACION sobre la tabla `reclamos` (y subreclamos = reclamos con
id_reclamo_padre, ver fase 4). Todo el trabajo pesado se hace en SQL (GROUP BY,
date_trunc, width_bucket); el frontend solo dibuja. Disenado para escalar a miles
de filas sin traer datos crudos.

Auth: router con guard JWT (§39). Lectura para cualquier usuario autenticado;
la UI ademas gatea el modulo a nivel <= 2 (supervisores/admin).

Convenciones:
  - El AREA se deriva SIEMPRE via subarea (mig 27 dropeo tipo_reclamo.id_area;
    reclamos.id_area legacy puede ser NULL). JOIN: reclamos -> tipo_reclamo ->
    subarea -> area. Ver §27 y memoria feedback_area_via_subarea_no_via_r_id_area.
  - Mono-municipio (§38): filtro por query param id_municipio (default 1).
  - Estados (CHECK ck_reclamo_estado): Sin asignar / En gestion / En espera /
    En auditoria / Resuelto / Cancelado.

Registrar en main.py: /api/v1/bi/* no colisiona con otros prefijos.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db

router = APIRouter(
    prefix="/api/v1/bi",
    tags=["BI"],
    dependencies=[Depends(get_current_user)],
)

# Estados finales / agrupaciones reutilizadas
ESTADOS_RESUELTO = ("Resuelto",)
ESTADOS_CANCELADO = ("Cancelado",)
ESTADOS_PENDIENTES = ("Sin asignar", "En gestión", "En espera", "En auditoría")


def _filtros_comunes(
    desde: Optional[date],
    hasta: Optional[date],
    id_area: Optional[int],
    prioridad: Optional[str],
    id_municipio: int,
    *,
    alias: str = "r",
    incluye_subreclamos: bool = True,
    estado: Optional[str] = None,
    id_tipo_reclamo: Optional[int] = None,
    canal: Optional[str] = None,
    anio: Optional[int] = None,
    meses: Optional[list[int]] = None,
) -> tuple[list[str], dict]:
    """
    Arma las condiciones WHERE compartidas por los endpoints de BI.
    Devuelve (lista_condiciones, params).

    `incluye_subreclamos`: si False, excluye reclamos hijo (id_reclamo_padre NOT NULL).
    El area se filtra contra subarea.id_area (la query que llame debe tener el JOIN).

    Nota mono-municipio (§38): los reclamos reales tienen id_municipio NULL (el alta
    no lo setea; verificado en prod 2026-05-26). ZARIS es un deploy por municipio,
    asi que tratamos NULL como "el municipio por defecto" e incluimos esas filas
    junto al id_municipio pedido. Sin esto, el BI mostraria vacio en produccion.
    """
    cond = [
        f"{alias}.activo = TRUE",
        f"({alias}.id_municipio = :id_municipio OR {alias}.id_municipio IS NULL)",
    ]
    params: dict = {"id_municipio": id_municipio}

    if desde:
        cond.append(f"{alias}.fecha_alta >= :desde")
        params["desde"] = desde
    if hasta:
        # hasta inclusivo: comparamos < hasta+1 dia (evita el ::date que rompe asyncpg)
        cond.append(f"{alias}.fecha_alta < :hasta_excl")
        from datetime import timedelta
        params["hasta_excl"] = hasta + timedelta(days=1)
    if id_area:
        cond.append("s.id_area = :id_area")
        params["id_area"] = id_area
    if prioridad:
        cond.append(f"{alias}.prioridad = :prioridad")
        params["prioridad"] = prioridad
    if not incluye_subreclamos:
        cond.append(f"{alias}.id_reclamo_padre IS NULL")
    _aplicar_extras(cond, params, estado, id_tipo_reclamo, canal, alias=alias, anio=anio, meses=meses)

    return cond, params


# Fragmento de JOIN para derivar el area via subarea (§27).
_JOIN_AREA = """
    LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
    LEFT JOIN subarea s       ON s.id_subarea = tr.id_subarea
    LEFT JOIN area a          ON a.id_area = s.id_area
"""


# Canal "sin dato" del filtro global: los reclamos del seed y muchos reales
# tienen canal_origen NULL (verificado en prod 2026-08-30: 34 de 59).
CANAL_SIN_DATO = "sin_dato"


def _parse_meses(meses: Optional[str]) -> Optional[list[int]]:
    """'1,3,12' -> [1, 3, 12]. Ignora basura; None si queda vacio."""
    if not meses:
        return None
    out = []
    for tok in str(meses).split(","):
        tok = tok.strip()
        if tok.isdigit() and 1 <= int(tok) <= 12:
            out.append(int(tok))
    return sorted(set(out)) or None


def _aplicar_extras(
    cond: list[str], params: dict,
    estado: Optional[str], id_tipo_reclamo: Optional[int], canal: Optional[str],
    *, alias: str = "r",
    anio: Optional[int] = None, meses: Optional[list[int]] = None,
    campo_fecha: str = "fecha_alta",
) -> None:
    """Filtros GLOBALES del Operativo (2026-08-30): estado, tipo de reclamo y
    canal de origen. Se suman a TODAS las secciones y a las exportaciones —
    una seccion cuyo universo choca con el filtro (ej. Pendientes con
    estado=Resuelto) simplemente queda vacia, como en Power BI."""
    if estado:
        cond.append(f"{alias}.estado = :estado")
        params["estado"] = estado
    if id_tipo_reclamo:
        cond.append(f"{alias}.id_tipo_reclamo = :id_tipo_reclamo")
        params["id_tipo_reclamo"] = id_tipo_reclamo
    if canal:
        if canal == CANAL_SIN_DATO:
            cond.append(f"{alias}.canal_origen IS NULL")
        else:
            cond.append(f"{alias}.canal_origen = :canal")
            params["canal"] = canal
    # Chips de anio + tildes de meses (2026-08-30): se combinan con desde/hasta
    # por AND. En la seccion Respuesta el campo es fecha_cierre.
    if anio:
        cond.append(f"EXTRACT(YEAR FROM {alias}.{campo_fecha})::int = :anio")
        params["anio"] = int(anio)
    if meses:
        cond.append(f"EXTRACT(MONTH FROM {alias}.{campo_fecha})::int = ANY(CAST(:meses AS int[]))")
        params["meses"] = [int(m) for m in meses]


# ── GET /bi/resumen ───────────────────────────────────────────────────────────
@router.get("/resumen")
async def bi_resumen(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """KPIs de cabecera: totales, resueltos, pendientes, cancelados, % cumplido."""
    cond, params = _filtros_comunes(desde, hasta, id_area, prioridad, id_municipio, estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))
    where = " AND ".join(cond)

    result = await db.execute(text(f"""
        SELECT
          COUNT(*)                                                  AS total,
          COUNT(*) FILTER (WHERE r.estado = 'Resuelto')             AS resueltos,
          COUNT(*) FILTER (WHERE r.estado = 'Cancelado')            AS cancelados,
          COUNT(*) FILTER (WHERE r.estado IN
              ('Sin asignar','En gestión','En espera','En auditoría')) AS pendientes,
          COUNT(*) FILTER (WHERE r.id_reclamo_padre IS NOT NULL)    AS subreclamos
        FROM reclamos r
        {_JOIN_AREA}
        WHERE {where}
    """), params)
    row = result.fetchone()
    total = row.total or 0
    cerrados = (row.resueltos or 0) + (row.cancelados or 0)
    pct_cumplido = round((row.resueltos or 0) / cerrados * 100, 2) if cerrados else 0.0

    return {
        "total": total,
        "resueltos": row.resueltos or 0,
        "cancelados": row.cancelados or 0,
        "pendientes": row.pendientes or 0,
        "subreclamos": row.subreclamos or 0,
        "pct_cumplido": pct_cumplido,
    }


# ── GET /bi/por-estado ────────────────────────────────────────────────────────
@router.get("/por-estado")
async def bi_por_estado(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Composicion por estado (dona). [{estado, total}]"""
    cond, params = _filtros_comunes(desde, hasta, id_area, prioridad, id_municipio, estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))
    where = " AND ".join(cond)
    result = await db.execute(text(f"""
        SELECT r.estado, COUNT(*) AS total
        FROM reclamos r
        {_JOIN_AREA}
        WHERE {where}
        GROUP BY r.estado
        ORDER BY total DESC
    """), params)
    return [{"estado": r.estado, "total": r.total} for r in result.fetchall()]


# ── GET /bi/por-canal ─────────────────────────────────────────────────────────
@router.get("/por-canal")
async def bi_por_canal(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Reclamos por canal de origen (dona). NULL se reporta como 'sin_dato'."""
    cond, params = _filtros_comunes(desde, hasta, id_area, prioridad, id_municipio, estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))
    where = " AND ".join(cond)
    result = await db.execute(text(f"""
        SELECT COALESCE(r.canal_origen, 'sin_dato') AS canal, COUNT(*) AS total
        FROM reclamos r
        {_JOIN_AREA}
        WHERE {where}
        GROUP BY COALESCE(r.canal_origen, 'sin_dato')
        ORDER BY total DESC
    """), params)
    return [{"canal": r.canal, "total": r.total} for r in result.fetchall()]


# ── GET /bi/por-area ──────────────────────────────────────────────────────────
@router.get("/por-area")
async def bi_por_area(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """
    Conteo por area, desglosado por estado (barras horizontales apiladas).
    [{id_area, area, total, resueltos, cancelados, pendientes}]
    Areas sin reclamos no aparecen. Reclamos sin area derivable -> 'Sin area'.
    """
    cond, params = _filtros_comunes(desde, hasta, id_area, prioridad, id_municipio, estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))
    where = " AND ".join(cond)
    result = await db.execute(text(f"""
        SELECT
          s.id_area                                                 AS id_area,
          COALESCE(a.nombre, 'Sin área')                            AS area,
          COUNT(*)                                                  AS total,
          COUNT(*) FILTER (WHERE r.estado = 'Resuelto')             AS resueltos,
          COUNT(*) FILTER (WHERE r.estado = 'Cancelado')            AS cancelados,
          COUNT(*) FILTER (WHERE r.estado IN
              ('Sin asignar','En gestión','En espera','En auditoría')) AS pendientes
        FROM reclamos r
        {_JOIN_AREA}
        WHERE {where}
        GROUP BY s.id_area, a.nombre
        ORDER BY total DESC
    """), params)
    return [
        {
            "id_area": r.id_area,
            "area": r.area,
            "total": r.total,
            "resueltos": r.resueltos,
            "cancelados": r.cancelados,
            "pendientes": r.pendientes,
        }
        for r in result.fetchall()
    ]


# ── GET /bi/mensual ───────────────────────────────────────────────────────────
@router.get("/mensual")
async def bi_mensual(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """
    Serie mensual de reclamos ingresados, desglosada por estado.
    [{mes: 'YYYY-MM', total, resueltos, cancelados, pendientes}]
    Ordenado cronologico ascendente. El frontend dibuja barras apiladas.
    """
    cond, params = _filtros_comunes(desde, hasta, id_area, prioridad, id_municipio, estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))
    where = " AND ".join(cond)
    result = await db.execute(text(f"""
        SELECT
          to_char(date_trunc('month', r.fecha_alta), 'YYYY-MM')     AS mes,
          COUNT(*)                                                  AS total,
          COUNT(*) FILTER (WHERE r.estado = 'Resuelto')             AS resueltos,
          COUNT(*) FILTER (WHERE r.estado = 'Cancelado')            AS cancelados,
          COUNT(*) FILTER (WHERE r.estado IN
              ('Sin asignar','En gestión','En espera','En auditoría')) AS pendientes
        FROM reclamos r
        {_JOIN_AREA}
        WHERE {where}
        GROUP BY date_trunc('month', r.fecha_alta)
        ORDER BY date_trunc('month', r.fecha_alta)
    """), params)
    return [
        {
            "mes": r.mes,
            "total": r.total,
            "resueltos": r.resueltos,
            "cancelados": r.cancelados,
            "pendientes": r.pendientes,
        }
        for r in result.fetchall()
    ]


# ── GET /bi/diario ────────────────────────────────────────────────────────────
@router.get("/diario")
async def bi_diario(
    mes: Optional[str] = Query(None, description="Mes a desglosar, formato 'YYYY-MM'. Si se pasa, acota a ese mes y tiene prioridad sobre desde/hasta."),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """
    Serie DIARIA de reclamos ingresados, desglosada por estado.
    [{dia: 'YYYY-MM-DD', total, resueltos, cancelados, pendientes}]
    Solo aparecen los días con al menos un reclamo.

    Dos modos:
      - `mes=YYYY-MM`: drill-down a un mes concreto (clic en barra mensual).
      - `desde`/`hasta` (o sin filtro): modo "Día" global del período filtrado.
    `mes` tiene prioridad si se pasa.
    """
    from datetime import datetime, timedelta

    cond = [
        "r.activo = TRUE",
        "(r.id_municipio = :id_municipio OR r.id_municipio IS NULL)",
    ]
    params: dict = {"id_municipio": id_municipio}

    if mes:
        # Drill-down a un mes: rango [primer dia .. primer dia mes siguiente).
        try:
            ini = datetime.strptime(mes + "-01", "%Y-%m-%d").date()
        except ValueError:
            from fastapi import HTTPException
            raise HTTPException(422, "Parámetro 'mes' inválido. Formato esperado: YYYY-MM.")
        fin = (ini.replace(day=28) + timedelta(days=4)).replace(day=1)
        cond.append("r.fecha_alta >= :ini")
        cond.append("r.fecha_alta < :fin")
        params["ini"] = ini
        params["fin"] = fin
    else:
        # Modo Día global: usa el rango desde/hasta del filtro (opcional).
        if desde:
            cond.append("r.fecha_alta >= :desde")
            params["desde"] = desde
        if hasta:
            cond.append("r.fecha_alta < :hasta_excl")
            params["hasta_excl"] = hasta + timedelta(days=1)

    if id_area:
        cond.append("s.id_area = :id_area")
        params["id_area"] = id_area
    if prioridad:
        cond.append("r.prioridad = :prioridad")
        params["prioridad"] = prioridad
    _aplicar_extras(cond, params, estado, id_tipo_reclamo, canal, anio=anio, meses=_parse_meses(meses))
    where = " AND ".join(cond)

    result = await db.execute(text(f"""
        SELECT
          to_char(date_trunc('day', r.fecha_alta), 'YYYY-MM-DD')    AS dia,
          COUNT(*)                                                  AS total,
          COUNT(*) FILTER (WHERE r.estado = 'Resuelto')             AS resueltos,
          COUNT(*) FILTER (WHERE r.estado = 'Cancelado')            AS cancelados,
          COUNT(*) FILTER (WHERE r.estado IN
              ('Sin asignar','En gestión','En espera','En auditoría')) AS pendientes
        FROM reclamos r
        {_JOIN_AREA}
        WHERE {where}
        GROUP BY date_trunc('day', r.fecha_alta)
        ORDER BY date_trunc('day', r.fecha_alta)
    """), params)
    return [
        {
            "dia": r.dia,
            "total": r.total,
            "resueltos": r.resueltos,
            "cancelados": r.cancelados,
            "pendientes": r.pendientes,
        }
        for r in result.fetchall()
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# FASE 2 — Resueltos / SLA (tiempos de cierre)
# ═══════════════════════════════════════════════════════════════════════════════
#
# Tiempo de cierre = fecha_cierre - fecha_alta (en dias). Solo se consideran los
# reclamos RESUELTOS con fecha_cierre poblada (no se inventan tiempos para los que
# no la tienen — §"no backfill sobre datos sinteticos"). Tramos de demora:
#   0-3 dias | 4-7 dias | +7 dias  (espeja el tablero de referencia de VL).
# Dias enteros via floor del delta en dias.
_DIAS_CIERRE = "FLOOR(EXTRACT(EPOCH FROM (r.fecha_cierre - r.fecha_alta)) / 86400.0)"
_TRAMO = f"""
    CASE
      WHEN {_DIAS_CIERRE} <= 3 THEN '0-3'
      WHEN {_DIAS_CIERRE} <= 7 THEN '4-7'
      ELSE '+7'
    END
"""


def _filtros_resueltos(
    desde: Optional[date], hasta: Optional[date],
    id_area: Optional[int], prioridad: Optional[str], id_municipio: int,
    *, estado: Optional[str] = None, id_tipo_reclamo: Optional[int] = None,
    canal: Optional[str] = None,
    anio: Optional[int] = None, meses: Optional[list[int]] = None,
) -> tuple[str, dict]:
    """WHERE para reclamos resueltos con fecha_cierre (base de los tiempos)."""
    cond = [
        "r.activo = TRUE",
        "(r.id_municipio = :id_municipio OR r.id_municipio IS NULL)",
        "r.estado = 'Resuelto'",
        "r.fecha_cierre IS NOT NULL",
    ]
    params: dict = {"id_municipio": id_municipio}
    if desde:
        cond.append("r.fecha_cierre >= :desde")
        params["desde"] = desde
    if hasta:
        from datetime import timedelta
        cond.append("r.fecha_cierre < :hasta_excl")
        params["hasta_excl"] = hasta + timedelta(days=1)
    if id_area:
        cond.append("s.id_area = :id_area")
        params["id_area"] = id_area
    if prioridad:
        cond.append("r.prioridad = :prioridad")
        params["prioridad"] = prioridad
    _aplicar_extras(cond, params, estado, id_tipo_reclamo, canal, anio=anio, meses=meses, campo_fecha="fecha_cierre")
    return " AND ".join(cond), params


# ── GET /bi/sla-resumen ───────────────────────────────────────────────────────
@router.get("/sla-resumen")
async def bi_sla_resumen(
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """
    KPIs de la vista Resueltos/SLA (sin filtro de fecha — usa el mes calendario):
      - resueltos_mes_actual / resueltos_mes_anterior / dif_pct
      - dias_cierre_promedio (sobre todos los resueltos con fecha_cierre)
      - pct_dentro_sla (dias_cierre <= tipo_reclamo.sla_dias)
    """
    base_where, base_params = _filtros_resueltos(None, None, id_area, prioridad, id_municipio, estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))

    # Resueltos del mes actual y del anterior (por fecha_cierre).
    result = await db.execute(text(f"""
        SELECT
          COUNT(*) FILTER (WHERE date_trunc('month', r.fecha_cierre) = date_trunc('month', CURRENT_DATE))
                                                                       AS mes_actual,
          COUNT(*) FILTER (WHERE date_trunc('month', r.fecha_cierre) = date_trunc('month', CURRENT_DATE - INTERVAL '1 month'))
                                                                       AS mes_anterior,
          ROUND(AVG({_DIAS_CIERRE})::numeric, 1)                       AS dias_prom,
          COUNT(*)                                                     AS total_resueltos,
          COUNT(*) FILTER (WHERE tr.sla_dias IS NOT NULL AND {_DIAS_CIERRE} <= tr.sla_dias)
                                                                       AS dentro_sla,
          COUNT(*) FILTER (WHERE tr.sla_dias IS NOT NULL)              AS con_sla
        FROM reclamos r
        {_JOIN_AREA}
        WHERE {base_where}
    """), base_params)
    row = result.fetchone()
    ma = row.mes_actual or 0
    man = row.mes_anterior or 0
    dif_pct = round((ma - man) / man * 100, 1) if man else (100.0 if ma else 0.0)
    pct_sla = round((row.dentro_sla or 0) / row.con_sla * 100, 1) if row.con_sla else None

    return {
        "resueltos_mes_actual": ma,
        "resueltos_mes_anterior": man,
        "dif_pct": dif_pct,
        "dias_cierre_promedio": float(row.dias_prom) if row.dias_prom is not None else None,
        "total_resueltos": row.total_resueltos or 0,
        "pct_dentro_sla": pct_sla,
    }


# ── GET /bi/tiempos-mensual ───────────────────────────────────────────────────
@router.get("/tiempos-mensual")
async def bi_tiempos_mensual(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """
    Por mes de cierre, conteo de resueltos en cada tramo de demora.
    [{mes, t0_3, t4_7, tmas7, total}]
    """
    where, params = _filtros_resueltos(desde, hasta, id_area, prioridad, id_municipio, estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))
    result = await db.execute(text(f"""
        SELECT
          to_char(date_trunc('month', r.fecha_cierre), 'YYYY-MM')     AS mes,
          COUNT(*) FILTER (WHERE {_DIAS_CIERRE} <= 3)                 AS t0_3,
          COUNT(*) FILTER (WHERE {_DIAS_CIERRE} > 3 AND {_DIAS_CIERRE} <= 7) AS t4_7,
          COUNT(*) FILTER (WHERE {_DIAS_CIERRE} > 7)                  AS tmas7,
          COUNT(*)                                                    AS total
        FROM reclamos r
        {_JOIN_AREA}
        WHERE {where}
        GROUP BY date_trunc('month', r.fecha_cierre)
        ORDER BY date_trunc('month', r.fecha_cierre)
    """), params)
    return [
        {"mes": r.mes, "t0_3": r.t0_3, "t4_7": r.t4_7, "tmas7": r.tmas7, "total": r.total}
        for r in result.fetchall()
    ]


# ── GET /bi/tiempos-por-tipo ──────────────────────────────────────────────────
@router.get("/tiempos-por-tipo")
async def bi_tiempos_por_tipo(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    limit: int = Query(10, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """
    Por tipo de reclamo, conteo de resueltos en cada tramo de demora.
    Top `limit` tipos por total. [{tipo, t0_3, t4_7, tmas7, total}]
    """
    where, params = _filtros_resueltos(desde, hasta, id_area, prioridad, id_municipio, estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))
    params["lim"] = limit
    result = await db.execute(text(f"""
        SELECT
          COALESCE(tr.nombre, 'Sin tipo')                             AS tipo,
          COUNT(*) FILTER (WHERE {_DIAS_CIERRE} <= 3)                 AS t0_3,
          COUNT(*) FILTER (WHERE {_DIAS_CIERRE} > 3 AND {_DIAS_CIERRE} <= 7) AS t4_7,
          COUNT(*) FILTER (WHERE {_DIAS_CIERRE} > 7)                  AS tmas7,
          COUNT(*)                                                    AS total
        FROM reclamos r
        {_JOIN_AREA}
        WHERE {where}
        GROUP BY tr.nombre
        ORDER BY total DESC
        LIMIT :lim
    """), params)
    return [
        {"tipo": r.tipo, "t0_3": r.t0_3, "t4_7": r.t4_7, "tmas7": r.tmas7, "total": r.total}
        for r in result.fetchall()
    ]


# ── GET /bi/evolucion-dias ────────────────────────────────────────────────────
@router.get("/evolucion-dias")
async def bi_evolucion_dias(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Dias promedio de cierre por mes (linea). [{mes, dias_prom, total}]"""
    where, params = _filtros_resueltos(desde, hasta, id_area, prioridad, id_municipio, estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))
    result = await db.execute(text(f"""
        SELECT
          to_char(date_trunc('month', r.fecha_cierre), 'YYYY-MM')     AS mes,
          ROUND(AVG({_DIAS_CIERRE})::numeric, 1)                      AS dias_prom,
          COUNT(*)                                                    AS total
        FROM reclamos r
        {_JOIN_AREA}
        WHERE {where}
        GROUP BY date_trunc('month', r.fecha_cierre)
        ORDER BY date_trunc('month', r.fecha_cierre)
    """), params)
    return [
        {"mes": r.mes, "dias_prom": float(r.dias_prom) if r.dias_prom is not None else 0.0, "total": r.total}
        for r in result.fetchall()
    ]


# ── GET /bi/resueltos-detalle ─────────────────────────────────────────────────
@router.get("/resueltos-detalle")
async def bi_resueltos_detalle(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    limit: int = Query(50, ge=1, le=10000),  # tope alto para soportar exportacion CSV
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    response: Response = None,  # type: ignore[assignment]
):
    """
    Tabla detalle de reclamos resueltos con su tiempo de cierre (dias).
    [{nro_reclamo, fecha_cierre, tipo, prioridad, dias, canal, area}]
    Header X-Total-Count para paginacion del frontend.
    """
    where, params = _filtros_resueltos(desde, hasta, id_area, prioridad, id_municipio, estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))

    total_res = await db.execute(text(f"""
        SELECT COUNT(*) FROM reclamos r {_JOIN_AREA} WHERE {where}
    """), params)
    total = total_res.scalar() or 0

    params["lim"] = limit
    params["off"] = offset
    result = await db.execute(text(f"""
        SELECT
          r.nro_reclamo,
          r.fecha_cierre,
          COALESCE(tr.nombre, 'Sin tipo')   AS tipo,
          r.prioridad,
          {_DIAS_CIERRE}::int               AS dias,
          COALESCE(r.canal_origen, 'sin_dato') AS canal,
          COALESCE(a.nombre, 'Sin área')    AS area
        FROM reclamos r
        {_JOIN_AREA}
        WHERE {where}
        ORDER BY r.fecha_cierre DESC
        LIMIT :lim OFFSET :off
    """), params)
    rows = [
        {
            "nro_reclamo": r.nro_reclamo,
            "fecha_cierre": r.fecha_cierre.isoformat() if r.fecha_cierre else None,
            "tipo": r.tipo,
            "prioridad": r.prioridad,
            "dias": r.dias,
            "canal": r.canal,
            "area": r.area,
        }
        for r in result.fetchall()
    ]
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
        response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return rows


# ═══════════════════════════════════════════════════════════════════════════════
# FASE 3 — Pendientes (reclamos en estados no finales)
# ═══════════════════════════════════════════════════════════════════════════════
#
# Pendiente = estado IN ('Sin asignar','En gestión','En espera','En auditoría').
# Demora = NOW() - fecha_alta (dias), porque el reclamo sigue abierto. Tramos:
#   0-3 | 4-7 | +7 dias (espeja la "Composicion tiempo" del tablero de referencia).
_DIAS_DEMORA = "FLOOR(EXTRACT(EPOCH FROM (NOW() - r.fecha_alta)) / 86400.0)"
_ESTADOS_PEND_SQL = "('Sin asignar','En gestión','En espera','En auditoría')"


def _filtros_pendientes(
    desde: Optional[date], hasta: Optional[date],
    id_area: Optional[int], prioridad: Optional[str], id_municipio: int,
    *, estado: Optional[str] = None, id_tipo_reclamo: Optional[int] = None,
    canal: Optional[str] = None,
    anio: Optional[int] = None, meses: Optional[list[int]] = None,
) -> tuple[str, dict]:
    """WHERE para reclamos pendientes (estados no finales)."""
    cond = [
        "r.activo = TRUE",
        "(r.id_municipio = :id_municipio OR r.id_municipio IS NULL)",
        f"r.estado IN {_ESTADOS_PEND_SQL}",
    ]
    params: dict = {"id_municipio": id_municipio}
    if desde:
        cond.append("r.fecha_alta >= :desde")
        params["desde"] = desde
    if hasta:
        from datetime import timedelta
        cond.append("r.fecha_alta < :hasta_excl")
        params["hasta_excl"] = hasta + timedelta(days=1)
    if id_area:
        cond.append("s.id_area = :id_area")
        params["id_area"] = id_area
    if prioridad:
        cond.append("r.prioridad = :prioridad")
        params["prioridad"] = prioridad
    _aplicar_extras(cond, params, estado, id_tipo_reclamo, canal, anio=anio, meses=meses)
    return " AND ".join(cond), params


# ── GET /bi/pendientes-resumen ────────────────────────────────────────────────
@router.get("/pendientes-resumen")
async def bi_pendientes_resumen(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """
    KPIs de pendientes: total, demora promedio, y conteo por tramo de demora.
    Tambien la composicion por estado (para la dona).
    """
    where, params = _filtros_pendientes(desde, hasta, id_area, prioridad, id_municipio, estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))
    result = await db.execute(text(f"""
        SELECT
          COUNT(*)                                            AS total,
          ROUND(AVG({_DIAS_DEMORA})::numeric, 1)              AS dias_demora_prom,
          COUNT(*) FILTER (WHERE {_DIAS_DEMORA} <= 3)         AS t0_3,
          COUNT(*) FILTER (WHERE {_DIAS_DEMORA} > 3 AND {_DIAS_DEMORA} <= 7) AS t4_7,
          COUNT(*) FILTER (WHERE {_DIAS_DEMORA} > 7)          AS tmas7
        FROM reclamos r
        {_JOIN_AREA}
        WHERE {where}
    """), params)
    row = result.fetchone()

    est = await db.execute(text(f"""
        SELECT r.estado, COUNT(*) AS total
        FROM reclamos r {_JOIN_AREA}
        WHERE {where}
        GROUP BY r.estado ORDER BY total DESC
    """), params)

    return {
        "total": row.total or 0,
        "dias_demora_promedio": float(row.dias_demora_prom) if row.dias_demora_prom is not None else None,
        "t0_3": row.t0_3 or 0,
        "t4_7": row.t4_7 or 0,
        "tmas7": row.tmas7 or 0,
        "por_estado": [{"estado": r.estado, "total": r.total} for r in est.fetchall()],
    }


# ── GET /bi/pendientes-por-mes ────────────────────────────────────────────────
@router.get("/pendientes-por-mes")
async def bi_pendientes_por_mes(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Pendientes por mes de alta, desglosados por estado. [{mes, <estado>:n, total}]"""
    where, params = _filtros_pendientes(desde, hasta, id_area, prioridad, id_municipio, estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))
    result = await db.execute(text(f"""
        SELECT
          to_char(date_trunc('month', r.fecha_alta), 'YYYY-MM') AS mes,
          COUNT(*) FILTER (WHERE r.estado = 'Sin asignar')      AS sin_asignar,
          COUNT(*) FILTER (WHERE r.estado = 'En gestión')       AS en_gestion,
          COUNT(*) FILTER (WHERE r.estado = 'En espera')        AS en_espera,
          COUNT(*) FILTER (WHERE r.estado = 'En auditoría')     AS en_auditoria,
          COUNT(*)                                              AS total
        FROM reclamos r {_JOIN_AREA}
        WHERE {where}
        GROUP BY date_trunc('month', r.fecha_alta)
        ORDER BY date_trunc('month', r.fecha_alta)
    """), params)
    return [
        {
            "mes": r.mes,
            "sin_asignar": r.sin_asignar, "en_gestion": r.en_gestion,
            "en_espera": r.en_espera, "en_auditoria": r.en_auditoria,
            "total": r.total,
        }
        for r in result.fetchall()
    ]


# ── GET /bi/pendientes-mensual ────────────────────────────────────────────────
@router.get("/pendientes-mensual")
async def bi_pendientes_mensual(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """
    Pendientes por mes de alta, desglosados por estado (para el histograma temporal
    con toggle Mes/Día + total). [{mes, sin_asignar, en_gestion, en_espera, en_auditoria, total}]
    """
    where, params = _filtros_pendientes(desde, hasta, id_area, prioridad, id_municipio, estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))
    result = await db.execute(text(f"""
        SELECT
          to_char(date_trunc('month', r.fecha_alta), 'YYYY-MM') AS mes,
          COUNT(*) FILTER (WHERE r.estado = 'Sin asignar')      AS sin_asignar,
          COUNT(*) FILTER (WHERE r.estado = 'En gestión')       AS en_gestion,
          COUNT(*) FILTER (WHERE r.estado = 'En espera')        AS en_espera,
          COUNT(*) FILTER (WHERE r.estado = 'En auditoría')     AS en_auditoria,
          COUNT(*)                                              AS total
        FROM reclamos r {_JOIN_AREA}
        WHERE {where}
        GROUP BY date_trunc('month', r.fecha_alta)
        ORDER BY date_trunc('month', r.fecha_alta)
    """), params)
    return [
        {"mes": r.mes, "sin_asignar": r.sin_asignar, "en_gestion": r.en_gestion,
         "en_espera": r.en_espera, "en_auditoria": r.en_auditoria, "total": r.total}
        for r in result.fetchall()
    ]


# ── GET /bi/pendientes-diario ─────────────────────────────────────────────────
@router.get("/pendientes-diario")
async def bi_pendientes_diario(
    mes: Optional[str] = Query(None, description="Mes a desglosar 'YYYY-MM' (drill). Prioridad sobre desde/hasta."),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Pendientes por día de alta, desglosados por estado. Modo drill (mes) o global."""
    from datetime import datetime, timedelta
    where, params = _filtros_pendientes(None, None, id_area, prioridad, id_municipio, estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))
    # _filtros_pendientes ya armó activo+municipio+estado+area+prioridad; agregamos rango.
    if mes:
        try:
            ini = datetime.strptime(mes + "-01", "%Y-%m-%d").date()
        except ValueError:
            from fastapi import HTTPException
            raise HTTPException(422, "Parámetro 'mes' inválido. Formato esperado: YYYY-MM.")
        fin = (ini.replace(day=28) + timedelta(days=4)).replace(day=1)
        where += " AND r.fecha_alta >= :ini AND r.fecha_alta < :fin"
        params["ini"] = ini
        params["fin"] = fin
    else:
        if desde:
            where += " AND r.fecha_alta >= :desde"
            params["desde"] = desde
        if hasta:
            where += " AND r.fecha_alta < :hasta_excl"
            params["hasta_excl"] = hasta + timedelta(days=1)
    result = await db.execute(text(f"""
        SELECT
          to_char(date_trunc('day', r.fecha_alta), 'YYYY-MM-DD') AS dia,
          COUNT(*) FILTER (WHERE r.estado = 'Sin asignar')      AS sin_asignar,
          COUNT(*) FILTER (WHERE r.estado = 'En gestión')       AS en_gestion,
          COUNT(*) FILTER (WHERE r.estado = 'En espera')        AS en_espera,
          COUNT(*) FILTER (WHERE r.estado = 'En auditoría')     AS en_auditoria,
          COUNT(*)                                              AS total
        FROM reclamos r {_JOIN_AREA}
        WHERE {where}
        GROUP BY date_trunc('day', r.fecha_alta)
        ORDER BY date_trunc('day', r.fecha_alta)
    """), params)
    return [
        {"dia": r.dia, "sin_asignar": r.sin_asignar, "en_gestion": r.en_gestion,
         "en_espera": r.en_espera, "en_auditoria": r.en_auditoria, "total": r.total}
        for r in result.fetchall()
    ]


# ── GET /bi/pendientes-por-tipo ───────────────────────────────────────────────
@router.get("/pendientes-por-tipo")
async def bi_pendientes_por_tipo(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    limit: int = Query(10, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """Ranking de pendientes por tipo. [{tipo, total}]"""
    where, params = _filtros_pendientes(desde, hasta, id_area, prioridad, id_municipio, estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))
    params["lim"] = limit
    result = await db.execute(text(f"""
        SELECT COALESCE(tr.nombre, 'Sin tipo') AS tipo, COUNT(*) AS total
        FROM reclamos r {_JOIN_AREA}
        WHERE {where}
        GROUP BY tr.nombre ORDER BY total DESC LIMIT :lim
    """), params)
    return [{"tipo": r.tipo, "total": r.total} for r in result.fetchall()]


# ── GET /bi/pendientes-geo ────────────────────────────────────────────────────
@router.get("/pendientes-geo")
async def bi_pendientes_geo(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """
    Pendientes con lat/lon para el mapa de geoposicionamiento. Solo los que tienen
    coordenadas. Shape compatible con el DashboardMap (reclamos).
    [{id_reclamo, nro_reclamo, tipo_nombre, estado, prioridad, descripcion, latitud, longitud}]
    """
    where, params = _filtros_pendientes(desde, hasta, id_area, prioridad, id_municipio, estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))
    where += " AND r.latitud IS NOT NULL AND r.longitud IS NOT NULL"
    result = await db.execute(text(f"""
        SELECT
          r.id_reclamo, r.nro_reclamo,
          COALESCE(tr.nombre, 'Sin tipo') AS tipo_nombre,
          r.estado, r.prioridad, r.descripcion,
          r.latitud::float8  AS latitud,
          r.longitud::float8 AS longitud,
          {_DIAS_DEMORA}::int AS dias_demora
        FROM reclamos r {_JOIN_AREA}
        WHERE {where}
        ORDER BY r.fecha_alta DESC
    """), params)
    return [
        {
            "id_reclamo": r.id_reclamo,
            "nro_reclamo": r.nro_reclamo,
            "tipo_nombre": r.tipo_nombre,
            "estado": r.estado,
            "prioridad": r.prioridad,
            "descripcion": r.descripcion,
            "latitud": r.latitud,
            "longitud": r.longitud,
            "dias_demora": r.dias_demora,
        }
        for r in result.fetchall()
    ]


# ── GET /bi/pendientes-detalle ────────────────────────────────────────────────
@router.get("/pendientes-detalle")
async def bi_pendientes_detalle(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    limit: int = Query(50, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    response: Response = None,  # type: ignore[assignment]
):
    """
    Tabla detalle de pendientes con su demora (dias desde el alta).
    [{nro_reclamo, fecha_alta, tipo, prioridad, estado, dias_demora, canal, area}]
    """
    where, params = _filtros_pendientes(desde, hasta, id_area, prioridad, id_municipio, estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))

    total_res = await db.execute(text(f"SELECT COUNT(*) FROM reclamos r {_JOIN_AREA} WHERE {where}"), params)
    total = total_res.scalar() or 0

    params["lim"] = limit
    params["off"] = offset
    result = await db.execute(text(f"""
        SELECT
          r.nro_reclamo,
          r.fecha_alta,
          COALESCE(tr.nombre, 'Sin tipo')   AS tipo,
          r.prioridad,
          r.estado,
          {_DIAS_DEMORA}::int               AS dias_demora,
          COALESCE(r.canal_origen, 'sin_dato') AS canal,
          COALESCE(a.nombre, 'Sin área')    AS area
        FROM reclamos r {_JOIN_AREA}
        WHERE {where}
        ORDER BY {_DIAS_DEMORA} DESC
        LIMIT :lim OFFSET :off
    """), params)
    rows = [
        {
            "nro_reclamo": r.nro_reclamo,
            "fecha_alta": r.fecha_alta.isoformat() if r.fecha_alta else None,
            "tipo": r.tipo, "prioridad": r.prioridad, "estado": r.estado,
            "dias_demora": r.dias_demora,
            "canal": r.canal, "area": r.area,
        }
        for r in result.fetchall()
    ]
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
        response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return rows


# ═══════════════════════════════════════════════════════════════════════════════
# FASE 4 — Subreclamos (reclamos con id_reclamo_padre; "intervenciones")
# ═══════════════════════════════════════════════════════════════════════════════
#
# Un subreclamo es un reclamo con id_reclamo_padre NOT NULL (profundidad máx 1, §22).
# En los tableros de referencia de VL se llaman "intervenciones".


def _filtros_subreclamos(
    desde: Optional[date], hasta: Optional[date],
    id_area: Optional[int], prioridad: Optional[str], id_municipio: int,
    *, estado: Optional[str] = None, id_tipo_reclamo: Optional[int] = None,
    canal: Optional[str] = None,
    anio: Optional[int] = None, meses: Optional[list[int]] = None,
) -> tuple[str, dict]:
    """WHERE para subreclamos (id_reclamo_padre NOT NULL)."""
    cond = [
        "r.activo = TRUE",
        "(r.id_municipio = :id_municipio OR r.id_municipio IS NULL)",
        "r.id_reclamo_padre IS NOT NULL",
    ]
    params: dict = {"id_municipio": id_municipio}
    if desde:
        cond.append("r.fecha_alta >= :desde")
        params["desde"] = desde
    if hasta:
        from datetime import timedelta
        cond.append("r.fecha_alta < :hasta_excl")
        params["hasta_excl"] = hasta + timedelta(days=1)
    if id_area:
        cond.append("s.id_area = :id_area")
        params["id_area"] = id_area
    if prioridad:
        cond.append("r.prioridad = :prioridad")
        params["prioridad"] = prioridad
    _aplicar_extras(cond, params, estado, id_tipo_reclamo, canal, anio=anio, meses=meses)
    return " AND ".join(cond), params


# ── GET /bi/subreclamos-resumen ───────────────────────────────────────────────
@router.get("/subreclamos-resumen")
async def bi_subreclamos_resumen(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """
    KPIs de subreclamos: total, padres distintos con subreclamos, composición por
    estado (de los subreclamos) y por estado de los padres.
    """
    where, params = _filtros_subreclamos(desde, hasta, id_area, prioridad, id_municipio, estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))

    tot = await db.execute(text(f"""
        SELECT COUNT(*) AS total,
               COUNT(DISTINCT r.id_reclamo_padre) AS padres
        FROM reclamos r {_JOIN_AREA}
        WHERE {where}
    """), params)
    trow = tot.fetchone()

    por_estado = await db.execute(text(f"""
        SELECT r.estado, COUNT(*) AS total
        FROM reclamos r {_JOIN_AREA}
        WHERE {where}
        GROUP BY r.estado ORDER BY total DESC
    """), params)

    # Estado de los reclamos PADRE que tienen subreclamos en este filtro.
    por_estado_padre = await db.execute(text(f"""
        SELECT p.estado, COUNT(DISTINCT p.id_reclamo) AS total
        FROM reclamos p
        WHERE p.activo AND p.id_reclamo IN (
          SELECT DISTINCT r.id_reclamo_padre
          FROM reclamos r {_JOIN_AREA}
          WHERE {where}
        )
        GROUP BY p.estado ORDER BY total DESC
    """), params)

    return {
        "total": trow.total or 0,
        "padres": trow.padres or 0,
        "por_estado": [{"estado": r.estado, "total": r.total} for r in por_estado.fetchall()],
        "por_estado_padre": [{"estado": r.estado, "total": r.total} for r in por_estado_padre.fetchall()],
    }


# ── GET /bi/subreclamos-mensual ───────────────────────────────────────────────
@router.get("/subreclamos-mensual")
async def bi_subreclamos_mensual(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Subreclamos por mes de alta, desglosados por estado (para histograma)."""
    where, params = _filtros_subreclamos(desde, hasta, id_area, prioridad, id_municipio, estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))
    result = await db.execute(text(f"""
        SELECT
          to_char(date_trunc('month', r.fecha_alta), 'YYYY-MM') AS mes,
          COUNT(*) FILTER (WHERE r.estado = 'Sin asignar')      AS sin_asignar,
          COUNT(*) FILTER (WHERE r.estado = 'En gestión')       AS en_gestion,
          COUNT(*) FILTER (WHERE r.estado = 'En espera')        AS en_espera,
          COUNT(*) FILTER (WHERE r.estado = 'En auditoría')     AS en_auditoria,
          COUNT(*) FILTER (WHERE r.estado = 'Resuelto')         AS resuelto,
          COUNT(*) FILTER (WHERE r.estado = 'Cancelado')        AS cancelado,
          COUNT(*)                                              AS total
        FROM reclamos r {_JOIN_AREA}
        WHERE {where}
        GROUP BY date_trunc('month', r.fecha_alta)
        ORDER BY date_trunc('month', r.fecha_alta)
    """), params)
    return [dict(row._mapping) for row in result.fetchall()]


# ── GET /bi/subreclamos-diario ────────────────────────────────────────────────
@router.get("/subreclamos-diario")
async def bi_subreclamos_diario(
    mes: Optional[str] = Query(None),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Subreclamos por día de alta, desglosados por estado. Drill (mes) o global."""
    from datetime import datetime, timedelta
    where, params = _filtros_subreclamos(None, None, id_area, prioridad, id_municipio, estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))
    if mes:
        try:
            ini = datetime.strptime(mes + "-01", "%Y-%m-%d").date()
        except ValueError:
            from fastapi import HTTPException
            raise HTTPException(422, "Parámetro 'mes' inválido. Formato esperado: YYYY-MM.")
        fin = (ini.replace(day=28) + timedelta(days=4)).replace(day=1)
        where += " AND r.fecha_alta >= :ini AND r.fecha_alta < :fin"
        params["ini"] = ini
        params["fin"] = fin
    else:
        if desde:
            where += " AND r.fecha_alta >= :desde"
            params["desde"] = desde
        if hasta:
            where += " AND r.fecha_alta < :hasta_excl"
            params["hasta_excl"] = hasta + timedelta(days=1)
    result = await db.execute(text(f"""
        SELECT
          to_char(date_trunc('day', r.fecha_alta), 'YYYY-MM-DD') AS dia,
          COUNT(*) FILTER (WHERE r.estado = 'Sin asignar')      AS sin_asignar,
          COUNT(*) FILTER (WHERE r.estado = 'En gestión')       AS en_gestion,
          COUNT(*) FILTER (WHERE r.estado = 'En espera')        AS en_espera,
          COUNT(*) FILTER (WHERE r.estado = 'En auditoría')     AS en_auditoria,
          COUNT(*) FILTER (WHERE r.estado = 'Resuelto')         AS resuelto,
          COUNT(*) FILTER (WHERE r.estado = 'Cancelado')        AS cancelado,
          COUNT(*)                                              AS total
        FROM reclamos r {_JOIN_AREA}
        WHERE {where}
        GROUP BY date_trunc('day', r.fecha_alta)
        ORDER BY date_trunc('day', r.fecha_alta)
    """), params)
    return [dict(row._mapping) for row in result.fetchall()]


# ── GET /bi/subreclamos-por-tipo ──────────────────────────────────────────────
@router.get("/subreclamos-por-tipo")
async def bi_subreclamos_por_tipo(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    limit: int = Query(10, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """Ranking de subreclamos por tipo. [{tipo, total}]"""
    where, params = _filtros_subreclamos(desde, hasta, id_area, prioridad, id_municipio, estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))
    params["lim"] = limit
    result = await db.execute(text(f"""
        SELECT COALESCE(tr.nombre, 'Sin tipo') AS tipo, COUNT(*) AS total
        FROM reclamos r {_JOIN_AREA}
        WHERE {where}
        GROUP BY tr.nombre ORDER BY total DESC LIMIT :lim
    """), params)
    return [{"tipo": r.tipo, "total": r.total} for r in result.fetchall()]


# ── GET /bi/subreclamos-detalle ───────────────────────────────────────────────
@router.get("/subreclamos-detalle")
async def bi_subreclamos_detalle(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtro global de estado (CHECK ck_reclamo_estado)"),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None, description="canal_origen; 'sin_dato' = sin canal (NULL)"),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    limit: int = Query(50, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    response: Response = None,  # type: ignore[assignment]
):
    """
    Tabla detalle de subreclamos con su reclamo padre.
    [{nro_reclamo, fecha_alta, tipo, prioridad, estado, area, nro_padre, estado_padre}]
    """
    where, params = _filtros_subreclamos(desde, hasta, id_area, prioridad, id_municipio, estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))

    total_res = await db.execute(text(f"SELECT COUNT(*) FROM reclamos r {_JOIN_AREA} WHERE {where}"), params)
    total = total_res.scalar() or 0

    params["lim"] = limit
    params["off"] = offset
    result = await db.execute(text(f"""
        SELECT
          r.nro_reclamo,
          r.fecha_alta,
          COALESCE(tr.nombre, 'Sin tipo')   AS tipo,
          r.prioridad, r.estado,
          COALESCE(a.nombre, 'Sin área')    AS area,
          p.nro_reclamo                     AS nro_padre,
          p.estado                          AS estado_padre
        FROM reclamos r
        {_JOIN_AREA}
        LEFT JOIN reclamos p ON p.id_reclamo = r.id_reclamo_padre
        WHERE {where}
        ORDER BY r.fecha_alta DESC
        LIMIT :lim OFFSET :off
    """), params)
    rows = [
        {
            "nro_reclamo": r.nro_reclamo,
            "fecha_alta": r.fecha_alta.isoformat() if r.fecha_alta else None,
            "tipo": r.tipo, "prioridad": r.prioridad, "estado": r.estado,
            "area": r.area, "nro_padre": r.nro_padre, "estado_padre": r.estado_padre,
        }
        for r in result.fetchall()
    ]
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
        response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return rows


# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIVO EN UNA PAGINA (2026-08-30) — histograma por TIPO, export del universo,
# area por defecto del usuario.
# ═══════════════════════════════════════════════════════════════════════════════

_TOP_TIPOS = 6


async def _histograma_por_tipo(db: AsyncSession, gran: str, where: str, params: dict) -> dict:
    """Serie temporal apilada por TIPO de reclamo (los `_TOP_TIPOS` mas frecuentes
    del universo filtrado + 'Otros'), como el "Historico de reclamos" de Power BI.
    Devuelve {series: [{key, name}], items: [{mes|dia, total, <key>: n, ...}]}.
    El pivot se hace en Python sobre un GROUP BY periodo x tipo (agregado en SQL)."""
    trunc = "month" if gran == "mes" else "day"
    fmt = "YYYY-MM" if gran == "mes" else "YYYY-MM-DD"
    top = (await db.execute(text(f"""
        SELECT COALESCE(tr.id_tipo_reclamo, 0) AS id_tipo, COALESCE(tr.nombre, 'Sin tipo') AS nombre,
               COUNT(*) AS n
        FROM reclamos r {_JOIN_AREA}
        WHERE {where}
        GROUP BY tr.id_tipo_reclamo, tr.nombre
        ORDER BY n DESC, nombre
        LIMIT {_TOP_TIPOS}
    """), params)).fetchall()
    top_ids = [int(t.id_tipo) for t in top]
    series = [{"key": f"t_{t.id_tipo}", "name": t.nombre} for t in top]
    rows = (await db.execute(text(f"""
        SELECT to_char(date_trunc('{trunc}', r.fecha_alta), '{fmt}') AS periodo,
               COALESCE(tr.id_tipo_reclamo, 0) AS id_tipo,
               COUNT(*) AS n
        FROM reclamos r {_JOIN_AREA}
        WHERE {where}
        GROUP BY date_trunc('{trunc}', r.fecha_alta), tr.id_tipo_reclamo
        ORDER BY date_trunc('{trunc}', r.fecha_alta)
    """), params)).fetchall()
    items: dict[str, dict] = {}
    hay_otros = False
    for r in rows:
        it = items.setdefault(r.periodo, {gran: r.periodo, "total": 0, **{sr["key"]: 0 for sr in series}, "otros": 0})
        it["total"] += r.n
        if int(r.id_tipo) in top_ids:
            it[f"t_{int(r.id_tipo)}"] += r.n
        else:
            it["otros"] += r.n
            hay_otros = True
    if hay_otros:
        series.append({"key": "otros", "name": "Otros"})
    else:
        for it in items.values():
            it.pop("otros", None)
    return {"series": series, "items": list(items.values())}


# ── GET /bi/mensual-por-tipo ──────────────────────────────────────────────────
@router.get("/mensual-por-tipo")
async def bi_mensual_por_tipo(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Reclamos ingresados por mes apilados por tipo (top 6 + Otros)."""
    cond, params = _filtros_comunes(desde, hasta, id_area, prioridad, id_municipio,
                                    estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))
    return await _histograma_por_tipo(db, "mes", " AND ".join(cond), params)


# ── GET /bi/diario-por-tipo ───────────────────────────────────────────────────
@router.get("/diario-por-tipo")
async def bi_diario_por_tipo(
    mes: Optional[str] = Query(None, description="Drill a un mes 'YYYY-MM' (prioridad sobre desde/hasta)"),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Reclamos ingresados por dia apilados por tipo. Modo drill (mes) o global."""
    from datetime import datetime, timedelta
    if mes:
        try:
            ini = datetime.strptime(mes + "-01", "%Y-%m-%d").date()
        except ValueError:
            from fastapi import HTTPException
            raise HTTPException(422, "Parámetro 'mes' inválido. Formato esperado: YYYY-MM.")
        fin = (ini.replace(day=28) + timedelta(days=4)).replace(day=1)
        desde, hasta = ini, fin - timedelta(days=1)
    cond, params = _filtros_comunes(desde, hasta, id_area, prioridad, id_municipio,
                                    estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))
    return await _histograma_por_tipo(db, "dia", " AND ".join(cond), params)


# ── GET /bi/reclamos-detalle ──────────────────────────────────────────────────
@router.get("/reclamos-detalle")
async def bi_reclamos_detalle(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None),
    anio: Optional[int] = Query(None, description="Anio calendario (chip). Se combina con `meses`."),
    meses: Optional[str] = Query(None, description="Meses 1-12 separados por coma (tildes)"),
    id_municipio: int = Query(1),
    limit: int = Query(50, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    response: Response = None,  # type: ignore[assignment]
):
    """Detalle del UNIVERSO filtrado (todos los estados) — es lo que exporta la
    seccion Resumen. [{nro_reclamo, fecha_alta, tipo, prioridad, estado, canal,
    area, subarea, direccion, fecha_cierre, dias, es_subreclamo}] (dias = cierre
    si cerro, demora si sigue abierto)."""
    cond, params = _filtros_comunes(desde, hasta, id_area, prioridad, id_municipio,
                                    estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal, anio=anio, meses=_parse_meses(meses))
    where = " AND ".join(cond)
    total = (await db.execute(text(f"SELECT COUNT(*) FROM reclamos r {_JOIN_AREA} WHERE {where}"), params)).scalar() or 0
    params["lim"] = limit
    params["off"] = offset
    result = await db.execute(text(f"""
        SELECT r.nro_reclamo, r.fecha_alta, r.fecha_cierre,
               COALESCE(tr.nombre, 'Sin tipo') AS tipo,
               r.prioridad, r.estado,
               COALESCE(r.canal_origen, 'sin_dato') AS canal,
               COALESCE(a.nombre, 'Sin área') AS area,
               COALESCE(s.nombre, '') AS subarea,
               COALESCE(r.direccion, r.domicilio_reclamo, '') AS direccion,
               CASE WHEN r.fecha_cierre IS NOT NULL THEN {_DIAS_CIERRE}::int ELSE {_DIAS_DEMORA}::int END AS dias,
               (r.id_reclamo_padre IS NOT NULL) AS es_subreclamo
        FROM reclamos r {_JOIN_AREA}
        WHERE {where}
        ORDER BY r.fecha_alta DESC
        LIMIT :lim OFFSET :off
    """), params)
    rows = [
        {
            "nro_reclamo": r.nro_reclamo,
            "fecha_alta": r.fecha_alta.isoformat() if r.fecha_alta else None,
            "fecha_cierre": r.fecha_cierre.isoformat() if r.fecha_cierre else None,
            "tipo": r.tipo, "prioridad": r.prioridad, "estado": r.estado,
            "canal": r.canal, "area": r.area, "subarea": r.subarea,
            "direccion": r.direccion, "dias": r.dias, "es_subreclamo": bool(r.es_subreclamo),
        }
        for r in result.fetchall()
    ]
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
        response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return rows


# ── GET /bi/mi-area ───────────────────────────────────────────────────────────
@router.get("/mi-area")
async def bi_mi_area(
    id_municipio: int = Query(1),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Area de servicio por defecto del usuario para el Operativo (Cesar 2026-08-30:
    "estas vistas son para cada area"). Fuente: el AGENTE vinculado
    (agentes.id_subarea -> subarea.id_area, regla §3 — NO usuarios.id_subarea).
    Sin agente/subarea -> se sugiere el area con mas reclamos (origen 'sugerida').
    {id_area, nombre, origen: 'agente'|'sugerida'|null}"""
    row = (await db.execute(text("""
        SELECT a.id_area, a.nombre
          FROM agentes ag
          JOIN subarea s ON s.id_subarea = ag.id_subarea
          JOIN area a ON a.id_area = s.id_area
         WHERE ag.id_usuario = :uid AND ag.activo = TRUE AND a.activo = TRUE
         ORDER BY ag.id_agente LIMIT 1
    """), {"uid": current_user["id_usuario"]})).fetchone()
    if row:
        return {"id_area": row.id_area, "nombre": row.nombre, "origen": "agente"}
    row = (await db.execute(text(f"""
        SELECT a.id_area, a.nombre, COUNT(*) AS n
          FROM reclamos r {_JOIN_AREA}
         WHERE r.activo = TRUE AND (r.id_municipio = :m OR r.id_municipio IS NULL) AND a.id_area IS NOT NULL AND a.activo = TRUE
         GROUP BY a.id_area, a.nombre ORDER BY n DESC LIMIT 1
    """), {"m": id_municipio})).fetchone()
    if row:
        return {"id_area": row.id_area, "nombre": row.nombre, "origen": "sugerida"}
    return {"id_area": None, "nombre": None, "origen": None}


# ── GET /bi/comparativo ───────────────────────────────────────────────────────
def _hace_anios(d: date, n: int) -> date:
    """Misma fecha n anios antes (29/02 -> 28/02)."""
    try:
        return d.replace(year=d.year - n)
    except ValueError:
        return d.replace(year=d.year - n, day=28)


def _hace_meses(d: date, n: int) -> date:
    """Primer dia del mes, n meses antes de `d`."""
    y, m = d.year, d.month - n
    while m <= 0:
        y -= 1
        m += 12
    return date(y, m, 1)


@router.get("/comparativo")
async def bi_comparativo(
    seccion: str = Query("resumen", description="resumen | respuesta | pendientes | subreclamos"),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    estado: Optional[str] = Query(None),
    id_tipo_reclamo: Optional[int] = Query(None),
    canal: Optional[str] = Query(None),
    anio: Optional[int] = Query(None),
    meses: Optional[str] = Query(None),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """KPIs comparativos de la fila unica de cada seccion (Cesar 2026-08-30):
      - total: el totalizador de lo que se esta viendo (todos los filtros).
      - prom_mensual_12m: promedio mensual del ultimo anio (12 meses calendario
        cerrados hasta hoy), con los filtros NO temporales.
      - anio_anterior: el mismo valor en el mismo periodo del anio anterior
        (anio-1 con los mismos meses; o desde/hasta corridos un anio; sin filtro
        temporal: los 12 meses previos a los ultimos 12), y var_pct.
    Universo por seccion: resumen = todos los reclamos (fecha_alta) · respuesta =
    resueltos con fecha_cierre (fecha_cierre) · pendientes = estados no finales
    (fecha_alta) · subreclamos = con padre (fecha_alta)."""
    meses_l = _parse_meses(meses)
    extras = dict(estado=estado, id_tipo_reclamo=id_tipo_reclamo, canal=canal)

    def where_de(d: Optional[date], h: Optional[date], a: Optional[int], m: Optional[list[int]]) -> tuple[str, dict]:
        if seccion == "respuesta":
            return _filtros_resueltos(d, h, id_area, prioridad, id_municipio, anio=a, meses=m, **extras)
        if seccion == "pendientes":
            return _filtros_pendientes(d, h, id_area, prioridad, id_municipio, anio=a, meses=m, **extras)
        if seccion == "subreclamos":
            return _filtros_subreclamos(d, h, id_area, prioridad, id_municipio, anio=a, meses=m, **extras)
        cond, params = _filtros_comunes(d, h, id_area, prioridad, id_municipio, anio=a, meses=m, **extras)
        return " AND ".join(cond), params

    async def contar(d, h, a, m) -> int:
        where, params = where_de(d, h, a, m)
        return int((await db.execute(text(f"SELECT COUNT(*) FROM reclamos r {_JOIN_AREA} WHERE {where}"), params)).scalar() or 0)

    hoy = date.today()
    ini_12 = _hace_meses(hoy, 11)          # 12 meses calendario incluyendo el actual
    ini_24 = _hace_meses(hoy, 23)
    fin_prev = ini_12 - timedelta(days=1)

    total = await contar(desde, hasta, anio, meses_l)
    n_12 = await contar(ini_12, hoy, None, None)
    prom_12 = round(n_12 / 12.0, 1)

    if anio:
        anterior = await contar(None, None, anio - 1, meses_l)
        comparable = total
        lbl_act, lbl_ant = str(anio), str(anio - 1)
        if meses_l:
            lbl_act += f" · meses {','.join(map(str, meses_l))}"
            lbl_ant += f" · meses {','.join(map(str, meses_l))}"
    elif desde or hasta:
        d2 = _hace_anios(desde, 1) if desde else None
        h2 = _hace_anios(hasta, 1) if hasta else None
        anterior = await contar(d2, h2, None, meses_l)
        comparable = total
        lbl_act = f"{desde or '…'} a {hasta or '…'}"
        lbl_ant = f"{d2 or '…'} a {h2 or '…'}"
    else:
        anterior = await contar(ini_24, fin_prev, None, None)
        comparable = n_12
        lbl_act = f"últimos 12 meses ({ini_12.strftime('%m/%Y')}–{hoy.strftime('%m/%Y')})"
        lbl_ant = f"12 meses previos ({ini_24.strftime('%m/%Y')}–{fin_prev.strftime('%m/%Y')})"

    var_pct = round((comparable - anterior) / anterior * 100, 1) if anterior else (100.0 if comparable else 0.0)
    return {
        "seccion": seccion,
        "total": total,
        "prom_mensual_12m": prom_12,
        "total_12m": n_12,
        "anio_anterior": anterior,
        "comparable_actual": comparable,
        "var_pct": var_pct,
        "periodo_actual": lbl_act,
        "periodo_anterior": lbl_ant,
    }


# ── GET /bi/catalogo/areas ────────────────────────────────────────────────────
@router.get("/catalogo/areas")
async def bi_catalogo_areas(
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Areas activas (para el filtro de la UI)."""
    result = await db.execute(text(
        "SELECT id_area, nombre FROM area WHERE activo = TRUE ORDER BY nombre"
    ))
    return [{"id_area": r.id_area, "nombre": r.nombre} for r in result.fetchall()]
