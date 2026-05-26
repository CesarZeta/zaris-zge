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

from datetime import date
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

    return cond, params


# Fragmento de JOIN para derivar el area via subarea (§27).
_JOIN_AREA = """
    LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
    LEFT JOIN subarea s       ON s.id_subarea = tr.id_subarea
    LEFT JOIN area a          ON a.id_area = s.id_area
"""


# ── GET /bi/resumen ───────────────────────────────────────────────────────────
@router.get("/resumen")
async def bi_resumen(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """KPIs de cabecera: totales, resueltos, pendientes, cancelados, % cumplido."""
    cond, params = _filtros_comunes(desde, hasta, id_area, prioridad, id_municipio)
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
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Composicion por estado (dona). [{estado, total}]"""
    cond, params = _filtros_comunes(desde, hasta, id_area, prioridad, id_municipio)
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
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Reclamos por canal de origen (dona). NULL se reporta como 'sin_dato'."""
    cond, params = _filtros_comunes(desde, hasta, id_area, prioridad, id_municipio)
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
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """
    Conteo por area, desglosado por estado (barras horizontales apiladas).
    [{id_area, area, total, resueltos, cancelados, pendientes}]
    Areas sin reclamos no aparecen. Reclamos sin area derivable -> 'Sin area'.
    """
    cond, params = _filtros_comunes(desde, hasta, id_area, prioridad, id_municipio)
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
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """
    Serie mensual de reclamos ingresados, desglosada por estado.
    [{mes: 'YYYY-MM', total, resueltos, cancelados, pendientes}]
    Ordenado cronologico ascendente. El frontend dibuja barras apiladas.
    """
    cond, params = _filtros_comunes(desde, hasta, id_area, prioridad, id_municipio)
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
    return " AND ".join(cond), params


# ── GET /bi/sla-resumen ───────────────────────────────────────────────────────
@router.get("/sla-resumen")
async def bi_sla_resumen(
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """
    KPIs de la vista Resueltos/SLA (sin filtro de fecha — usa el mes calendario):
      - resueltos_mes_actual / resueltos_mes_anterior / dif_pct
      - dias_cierre_promedio (sobre todos los resueltos con fecha_cierre)
      - pct_dentro_sla (dias_cierre <= tipo_reclamo.sla_dias)
    """
    base_where, base_params = _filtros_resueltos(None, None, id_area, prioridad, id_municipio)

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
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """
    Por mes de cierre, conteo de resueltos en cada tramo de demora.
    [{mes, t0_3, t4_7, tmas7, total}]
    """
    where, params = _filtros_resueltos(desde, hasta, id_area, prioridad, id_municipio)
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
    id_municipio: int = Query(1),
    limit: int = Query(10, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """
    Por tipo de reclamo, conteo de resueltos en cada tramo de demora.
    Top `limit` tipos por total. [{tipo, t0_3, t4_7, tmas7, total}]
    """
    where, params = _filtros_resueltos(desde, hasta, id_area, prioridad, id_municipio)
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
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Dias promedio de cierre por mes (linea). [{mes, dias_prom, total}]"""
    where, params = _filtros_resueltos(desde, hasta, id_area, prioridad, id_municipio)
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
    where, params = _filtros_resueltos(desde, hasta, id_area, prioridad, id_municipio)

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
    return " AND ".join(cond), params


# ── GET /bi/pendientes-resumen ────────────────────────────────────────────────
@router.get("/pendientes-resumen")
async def bi_pendientes_resumen(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """
    KPIs de pendientes: total, demora promedio, y conteo por tramo de demora.
    Tambien la composicion por estado (para la dona).
    """
    where, params = _filtros_pendientes(desde, hasta, id_area, prioridad, id_municipio)
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
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Pendientes por mes de alta, desglosados por estado. [{mes, <estado>:n, total}]"""
    where, params = _filtros_pendientes(desde, hasta, id_area, prioridad, id_municipio)
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
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """
    Pendientes por mes de alta, desglosados por estado (para el histograma temporal
    con toggle Mes/Día + total). [{mes, sin_asignar, en_gestion, en_espera, en_auditoria, total}]
    """
    where, params = _filtros_pendientes(desde, hasta, id_area, prioridad, id_municipio)
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
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Pendientes por día de alta, desglosados por estado. Modo drill (mes) o global."""
    from datetime import datetime, timedelta
    where, params = _filtros_pendientes(None, None, id_area, prioridad, id_municipio)
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
    id_municipio: int = Query(1),
    limit: int = Query(10, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """Ranking de pendientes por tipo. [{tipo, total}]"""
    where, params = _filtros_pendientes(desde, hasta, id_area, prioridad, id_municipio)
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
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """
    Pendientes con lat/lon para el mapa de geoposicionamiento. Solo los que tienen
    coordenadas. Shape compatible con el DashboardMap (reclamos).
    [{id_reclamo, nro_reclamo, tipo_nombre, estado, prioridad, descripcion, latitud, longitud}]
    """
    where, params = _filtros_pendientes(desde, hasta, id_area, prioridad, id_municipio)
    where += " AND r.latitud IS NOT NULL AND r.longitud IS NOT NULL"
    result = await db.execute(text(f"""
        SELECT
          r.id_reclamo, r.nro_reclamo,
          COALESCE(tr.nombre, 'Sin tipo') AS tipo_nombre,
          r.estado, r.prioridad, r.descripcion,
          r.latitud::float8  AS latitud,
          r.longitud::float8 AS longitud
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
    where, params = _filtros_pendientes(desde, hasta, id_area, prioridad, id_municipio)

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
    return " AND ".join(cond), params


# ── GET /bi/subreclamos-resumen ───────────────────────────────────────────────
@router.get("/subreclamos-resumen")
async def bi_subreclamos_resumen(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    prioridad: Optional[str] = Query(None),
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """
    KPIs de subreclamos: total, padres distintos con subreclamos, composición por
    estado (de los subreclamos) y por estado de los padres.
    """
    where, params = _filtros_subreclamos(desde, hasta, id_area, prioridad, id_municipio)

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
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Subreclamos por mes de alta, desglosados por estado (para histograma)."""
    where, params = _filtros_subreclamos(desde, hasta, id_area, prioridad, id_municipio)
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
    id_municipio: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Subreclamos por día de alta, desglosados por estado. Drill (mes) o global."""
    from datetime import datetime, timedelta
    where, params = _filtros_subreclamos(None, None, id_area, prioridad, id_municipio)
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
    id_municipio: int = Query(1),
    limit: int = Query(10, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """Ranking de subreclamos por tipo. [{tipo, total}]"""
    where, params = _filtros_subreclamos(desde, hasta, id_area, prioridad, id_municipio)
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
    where, params = _filtros_subreclamos(desde, hasta, id_area, prioridad, id_municipio)

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
