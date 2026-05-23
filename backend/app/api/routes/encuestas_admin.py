# -*- coding: utf-8 -*-
"""
ZARIS API - Router admin del modulo Encuestas (CSAT). Fase 2C.

Listados, dashboard y acciones para el backoffice. NO incluye el form publico
del ciudadano (fase 2D) ni el dispatcher (fase 2E).

Auth: todo el router exige JWT via dependencies=[Depends(get_current_user)] (§39).
Permisos finos:
  - Lectura (listados/dashboard): cualquier usuario autenticado.
  - PATCH /respuestas/{id}/atender: nivel_acceso <= 2 (admin/supervisor).

Mono-municipio (§38): ZARIS es un deploy por municipio, todo es id_municipio=1.
`get_current_user` NO expone id_municipio; se filtra por el query param `id_municipio`
(default 1), mismo patron que tramites.py. NO se filtra por un user.id_municipio
inexistente.

Registrar en main.py ANTES de admin_tablas_router (evita el {tabla} greedy, §5).
"""
from __future__ import annotations

import logging
import secrets as stdlib_secrets
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.utils.request_helpers import get_real_ip
from app.schemas.encuestas import (
    DashboardComentarioItem,
    DashboardDistribucionItem,
    DashboardEvolucionItem,
    DashboardPeriodoOut,
    DashboardPorAreaItem,
    DashboardResumenOut,
    DispararEncuestaIn,
    EncuestaEnvioConRespuestaOut,
    EncuestaEnvioOut,
    EncuestaPlantillaDetalleOut,
    EncuestaPlantillaOut,
    EncuestaRespuestaOut,
    RespuestaPendienteContactoOut,
)
from app.services import encuestas_service as svc

router = APIRouter(
    prefix="/api/v1/admin/encuestas",
    tags=["Encuestas Admin"],
    dependencies=[Depends(get_current_user)],
)

# Router SEPARADO para el dispatcher: NO lleva el guard JWT del router admin.
# FastAPI aplica las dependencies del APIRouter a TODAS sus rutas de forma aditiva;
# `dependencies=[]` en el decorador del path NO las anula. Por eso el dispatcher
# (autenticado por header X-Dispatcher-Token, no JWT) vive en su propio router sin
# guard global. Mismo prefix para mantener la URL /api/v1/admin/encuestas/dispatcher.
dispatcher_router = APIRouter(
    prefix="/api/v1/admin/encuestas",
    tags=["Encuestas Dispatcher"],
)

logger = logging.getLogger("zaris.encuestas.admin")

ESTADOS_ENVIO = {"pendiente", "enviada", "abierta", "completada", "expirada", "error_envio"}
ID_MUNICIPIO_DEFAULT = 1


def _require_supervisor(current_user: dict) -> None:
    """Dashboards y atención de respuestas: exclusivos de Admin (1) y Supervisor (2).
    Espeja el patrón de ordenes_trabajo._require_supervisor (§3)."""
    if current_user.get("nivel_acceso", 99) > 2:
        raise HTTPException(403, "Acceso restringido a administrador o supervisor")


# ===========================================================================
# Listados
# ===========================================================================

@router.get("/plantillas", response_model=list[EncuestaPlantillaOut])
async def listar_plantillas(
    id_municipio: int = Query(ID_MUNICIPIO_DEFAULT),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(text("""
        SELECT id_encuesta_plantilla, nombre, descripcion, version, tipo,
               activo, id_municipio, id_subarea, fecha_alta, fecha_modificacion
          FROM encuesta_plantilla
         WHERE activo = TRUE AND (id_municipio = :mun OR id_municipio IS NULL)
         ORDER BY id_encuesta_plantilla
    """), {"mun": id_municipio})).fetchall()
    return [EncuestaPlantillaOut.model_validate(r._mapping) for r in rows]


@router.get("/plantillas/{id_plantilla}", response_model=EncuestaPlantillaDetalleOut)
async def detalle_plantilla(
    id_plantilla: int,
    id_municipio: int = Query(ID_MUNICIPIO_DEFAULT),
    db: AsyncSession = Depends(get_db),
):
    plantilla = (await db.execute(text("""
        SELECT id_encuesta_plantilla, nombre, descripcion, version, tipo,
               activo, id_municipio, id_subarea, fecha_alta, fecha_modificacion
          FROM encuesta_plantilla
         WHERE id_encuesta_plantilla = :id AND activo = TRUE
           AND (id_municipio = :mun OR id_municipio IS NULL)
         LIMIT 1
    """), {"id": id_plantilla, "mun": id_municipio})).fetchone()
    if plantilla is None:
        raise HTTPException(404, "Plantilla no encontrada")

    preguntas = (await db.execute(text("""
        SELECT id_encuesta_pregunta, id_plantilla, texto, tipo, orden, rama,
               obligatoria, activo, fecha_alta, fecha_modificacion
          FROM encuesta_pregunta
         WHERE id_plantilla = :id AND activo = TRUE
         ORDER BY rama, orden
    """), {"id": id_plantilla})).fetchall()

    opciones = (await db.execute(text("""
        SELECT o.id_encuesta_opcion, o.id_pregunta, o.texto, o.valor, o.orden,
               o.activo, o.fecha_alta, o.fecha_modificacion
          FROM encuesta_opcion o
          JOIN encuesta_pregunta p ON p.id_encuesta_pregunta = o.id_pregunta
         WHERE p.id_plantilla = :id AND o.activo = TRUE
         ORDER BY o.id_pregunta, o.orden
    """), {"id": id_plantilla})).fetchall()

    opciones_por_pregunta: dict[int, list] = {}
    for o in opciones:
        opciones_por_pregunta.setdefault(o._mapping["id_pregunta"], []).append(dict(o._mapping))

    preguntas_out = []
    for p in preguntas:
        pm = dict(p._mapping)
        pm["opciones"] = opciones_por_pregunta.get(pm["id_encuesta_pregunta"], [])
        preguntas_out.append(pm)

    detalle = dict(plantilla._mapping)
    detalle["preguntas"] = preguntas_out
    return EncuestaPlantillaDetalleOut.model_validate(detalle)


@router.get("/envios", response_model=list[EncuestaEnvioOut])
async def listar_envios(
    response: Response,
    id_reclamo: Optional[int] = Query(None),
    estado: Optional[str] = Query(None),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    id_municipio: int = Query(ID_MUNICIPIO_DEFAULT),
    db: AsyncSession = Depends(get_db),
):
    if estado is not None and estado not in ESTADOS_ENVIO:
        raise HTTPException(422, f"estado inválido. Valores: {sorted(ESTADOS_ENVIO)}")

    conds = ["ee.activo = TRUE", "(ee.id_municipio = :mun OR ee.id_municipio IS NULL)"]
    params: dict = {"mun": id_municipio, "limit": limit, "offset": offset}
    if id_reclamo is not None:
        conds.append("ee.id_reclamo = :rid"); params["rid"] = id_reclamo
    if estado is not None:
        conds.append("ee.estado = :est"); params["est"] = estado
    if desde is not None:
        conds.append("ee.fecha_envio >= :desde"); params["desde"] = desde
    if hasta is not None:
        conds.append("ee.fecha_envio < :hasta_excl"); params["hasta_excl"] = hasta + timedelta(days=1)
    where = " AND ".join(conds)

    total = (await db.execute(text(
        f"SELECT COUNT(*) FROM encuesta_envio ee WHERE {where}"), params)).scalar() or 0

    rows = (await db.execute(text(f"""
        SELECT ee.id_encuesta_envio, ee.id_plantilla, ee.id_ciudadano, ee.id_reclamo,
               ee.token_unico, ee.email_destino_snapshot, ee.fecha_envio, ee.fecha_apertura,
               ee.fecha_completada, ee.fecha_expiracion, ee.estado, ee.intentos_envio,
               ee.ultimo_error_envio, ee.activo, ee.fecha_alta, ee.fecha_modificacion
          FROM encuesta_envio ee
         WHERE {where}
         ORDER BY ee.fecha_alta DESC
         LIMIT :limit OFFSET :offset
    """), params)).fetchall()

    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return [EncuestaEnvioOut.model_validate(r._mapping) for r in rows]


@router.get("/envios/{id_encuesta_envio}", response_model=EncuestaEnvioConRespuestaOut)
async def detalle_envio(
    id_encuesta_envio: int,
    id_municipio: int = Query(ID_MUNICIPIO_DEFAULT),
    db: AsyncSession = Depends(get_db),
):
    env = (await db.execute(text("""
        SELECT ee.id_encuesta_envio, ee.id_plantilla, ee.id_ciudadano, ee.id_reclamo,
               ee.token_unico, ee.email_destino_snapshot, ee.fecha_envio, ee.fecha_apertura,
               ee.fecha_completada, ee.fecha_expiracion, ee.estado, ee.intentos_envio,
               ee.ultimo_error_envio, ee.activo, ee.fecha_alta, ee.fecha_modificacion
          FROM encuesta_envio ee
         WHERE ee.id_encuesta_envio = :id AND ee.activo = TRUE
           AND (ee.id_municipio = :mun OR ee.id_municipio IS NULL)
         LIMIT 1
    """), {"id": id_encuesta_envio, "mun": id_municipio})).fetchone()
    if env is None:
        raise HTTPException(404, "Envío no encontrado")

    out = dict(env._mapping)
    resp = (await db.execute(text("""
        SELECT id_encuesta_respuesta, id_envio, clasificacion_inicial, rama_seguida,
               tiempo_completado_seg, solicita_contacto, ip_origen, atendida,
               atendida_por, fecha_atendida, activo, fecha_alta, fecha_modificacion
          FROM encuesta_respuesta
         WHERE id_envio = :id AND activo = TRUE
         LIMIT 1
    """), {"id": id_encuesta_envio})).fetchone()
    if resp is not None:
        out["respuesta"] = dict(resp._mapping)
        detalles = (await db.execute(text("""
            SELECT id_encuesta_respuesta_detalle, id_respuesta, id_pregunta,
                   valor_numerico, valor_texto, id_opcion_seleccionada,
                   activo, fecha_alta, fecha_modificacion
              FROM encuesta_respuesta_detalle
             WHERE id_respuesta = :rid AND activo = TRUE
             ORDER BY id_encuesta_respuesta_detalle
        """), {"rid": resp._mapping["id_encuesta_respuesta"]})).fetchall()
        out["detalles_respuesta"] = [dict(d._mapping) for d in detalles]
    return EncuestaEnvioConRespuestaOut.model_validate(out)


@router.get("/respuestas/pendientes-contacto",
            response_model=list[RespuestaPendienteContactoOut])
async def pendientes_contacto(
    response: Response,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    id_municipio: int = Query(ID_MUNICIPIO_DEFAULT),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_supervisor(user)
    where = """
        rsp.solicita_contacto = TRUE AND rsp.atendida = FALSE AND rsp.activo = TRUE
        AND (rsp.id_municipio = :mun OR rsp.id_municipio IS NULL)
    """
    params: dict = {"mun": id_municipio, "limit": limit, "offset": offset}

    total = (await db.execute(text(
        f"SELECT COUNT(*) FROM encuesta_respuesta rsp WHERE {where}"), params)).scalar() or 0

    rows = (await db.execute(text(f"""
        SELECT rsp.id_encuesta_respuesta, rsp.id_envio AS id_encuesta_envio,
               rsp.clasificacion_inicial, rsp.rama_seguida,
               rsp.fecha_alta AS fecha_respuesta, rsp.atendida,
               ee.id_reclamo, r.nro_reclamo,
               c.id_ciudadano, c.nombre AS ciudadano_nombre,
               c.apellido AS ciudadano_apellido, c.email AS ciudadano_email,
               c.telefono AS ciudadano_telefono
          FROM encuesta_respuesta rsp
          JOIN encuesta_envio ee ON ee.id_encuesta_envio = rsp.id_envio
          JOIN reclamos r        ON r.id_reclamo = ee.id_reclamo
          JOIN ciudadanos c      ON c.id_ciudadano = ee.id_ciudadano
         WHERE {where}
         ORDER BY rsp.fecha_alta ASC
         LIMIT :limit OFFSET :offset
    """), params)).fetchall()

    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return [RespuestaPendienteContactoOut.model_validate(r._mapping) for r in rows]


# ===========================================================================
# Dashboard
# ===========================================================================

@router.get("/dashboard/resumen", response_model=DashboardResumenOut)
async def dashboard_resumen(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    id_area: Optional[int] = Query(None),
    id_municipio: int = Query(ID_MUNICIPIO_DEFAULT),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_supervisor(user)
    hasta = hasta or date.today()
    desde = desde or (hasta - timedelta(days=30))

    params: dict = {"mun": id_municipio, "desde": desde,
                    "hasta_excl": hasta + timedelta(days=1), "id_area": id_area}
    # filtro de area opcional, via tipo_reclamo -> subarea -> area
    join_area = ""
    cond_area = ""
    if id_area is not None:
        join_area = """
            JOIN reclamos r        ON r.id_reclamo = ee.id_reclamo
            LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
            LEFT JOIN subarea s    ON s.id_subarea = COALESCE(tr.id_subarea, r.id_subarea)
        """
        cond_area = " AND s.id_area = :id_area"

    # total enviadas en el periodo (por fecha_envio)
    total_enviadas = (await db.execute(text(f"""
        SELECT COUNT(*)
          FROM encuesta_envio ee
          {join_area}
         WHERE ee.activo = TRUE
           AND (ee.id_municipio = :mun OR ee.id_municipio IS NULL)
           AND ee.fecha_envio >= :desde AND ee.fecha_envio < :hasta_excl
           {cond_area}
    """), params)).scalar() or 0

    # metricas de respuestas completadas en el periodo (por fecha de respuesta)
    agg = (await db.execute(text(f"""
        SELECT COUNT(*) AS total_completadas,
               COALESCE(AVG(rsp.clasificacion_inicial), 0) AS csat,
               COALESCE(SUM(CASE WHEN rsp.clasificacion_inicial <= 2 THEN 1 ELSE 0 END), 0) AS insat
          FROM encuesta_respuesta rsp
          JOIN encuesta_envio ee ON ee.id_encuesta_envio = rsp.id_envio
          {join_area}
         WHERE rsp.activo = TRUE
           AND (rsp.id_municipio = :mun OR rsp.id_municipio IS NULL)
           AND rsp.fecha_alta >= :desde AND rsp.fecha_alta < :hasta_excl
           {cond_area}
    """), params)).fetchone()._mapping

    total_completadas = int(agg["total_completadas"])
    csat = round(float(agg["csat"]), 2) if total_completadas else 0.0
    insat = int(agg["insat"])
    tasa_resp = round(total_completadas * 100.0 / total_enviadas, 1) if total_enviadas else 0.0
    pct_insat = round(insat * 100.0 / total_completadas, 1) if total_completadas else 0.0

    # distribucion 1..5
    dist_rows = (await db.execute(text(f"""
        SELECT rsp.clasificacion_inicial AS clasificacion, COUNT(*) AS count
          FROM encuesta_respuesta rsp
          JOIN encuesta_envio ee ON ee.id_encuesta_envio = rsp.id_envio
          {join_area}
         WHERE rsp.activo = TRUE
           AND (rsp.id_municipio = :mun OR rsp.id_municipio IS NULL)
           AND rsp.fecha_alta >= :desde AND rsp.fecha_alta < :hasta_excl
           {cond_area}
         GROUP BY rsp.clasificacion_inicial
    """), params)).fetchall()
    dist_map = {int(r._mapping["clasificacion"]): int(r._mapping["count"]) for r in dist_rows}
    distribucion = [
        DashboardDistribucionItem(clasificacion=i, count=dist_map.get(i, 0))
        for i in range(1, 6)
    ]

    # alertas de contacto pendientes (no acotadas al periodo: son una cola viva)
    alertas = (await db.execute(text("""
        SELECT COUNT(*) FROM encuesta_respuesta rsp
         WHERE rsp.activo = TRUE AND rsp.solicita_contacto = TRUE AND rsp.atendida = FALSE
           AND (rsp.id_municipio = :mun OR rsp.id_municipio IS NULL)
    """), {"mun": id_municipio})).scalar() or 0

    return DashboardResumenOut(
        periodo=DashboardPeriodoOut(desde=desde, hasta=hasta),
        csat_promedio=csat,
        tasa_respuesta_pct=tasa_resp,
        pct_insatisfechos=pct_insat,
        alertas_contacto_pendientes=int(alertas),
        total_enviadas=int(total_enviadas),
        total_completadas=total_completadas,
        distribucion=distribucion,
    )


@router.get("/dashboard/por-area", response_model=list[DashboardPorAreaItem])
async def dashboard_por_area(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    id_municipio: int = Query(ID_MUNICIPIO_DEFAULT),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_supervisor(user)
    hasta = hasta or date.today()
    desde = desde or (hasta - timedelta(days=30))
    rows = (await db.execute(text("""
        SELECT a.id_area, a.nombre AS nombre_area,
               COUNT(*) AS total_respuestas,
               ROUND(AVG(rsp.clasificacion_inicial)::numeric, 2) AS csat_promedio
          FROM encuesta_respuesta rsp
          JOIN encuesta_envio ee ON ee.id_encuesta_envio = rsp.id_envio
          JOIN reclamos r        ON r.id_reclamo = ee.id_reclamo
          LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
          LEFT JOIN subarea s    ON s.id_subarea = COALESCE(tr.id_subarea, r.id_subarea)
          LEFT JOIN area a       ON a.id_area = s.id_area
         WHERE rsp.activo = TRUE
           AND (rsp.id_municipio = :mun OR rsp.id_municipio IS NULL)
           AND rsp.fecha_alta >= :desde AND rsp.fecha_alta < :hasta_excl
         GROUP BY a.id_area, a.nombre
         ORDER BY csat_promedio DESC NULLS LAST
         LIMIT :limit
    """), {"mun": id_municipio, "desde": desde,
           "hasta_excl": hasta + timedelta(days=1), "limit": limit})).fetchall()
    return [
        DashboardPorAreaItem(
            id_area=r._mapping["id_area"],
            nombre_area=r._mapping["nombre_area"],
            total_respuestas=int(r._mapping["total_respuestas"]),
            csat_promedio=float(r._mapping["csat_promedio"] or 0),
        )
        for r in rows
    ]


@router.get("/dashboard/evolucion", response_model=list[DashboardEvolucionItem])
async def dashboard_evolucion(
    meses: int = Query(6, ge=1, le=24),
    id_municipio: int = Query(ID_MUNICIPIO_DEFAULT),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_supervisor(user)
    rows = (await db.execute(text("""
        SELECT TO_CHAR(rsp.fecha_alta, 'YYYY-MM') AS anio_mes,
               ROUND(AVG(rsp.clasificacion_inicial)::numeric, 2) AS csat_promedio,
               COUNT(*) AS total_respuestas
          FROM encuesta_respuesta rsp
         WHERE rsp.activo = TRUE
           AND (rsp.id_municipio = :mun OR rsp.id_municipio IS NULL)
           AND rsp.fecha_alta >= date_trunc('month', NOW()) - make_interval(months => :meses)
         GROUP BY TO_CHAR(rsp.fecha_alta, 'YYYY-MM')
         ORDER BY anio_mes ASC
    """), {"mun": id_municipio, "meses": meses})).fetchall()
    return [
        DashboardEvolucionItem(
            anio_mes=r._mapping["anio_mes"],
            csat_promedio=float(r._mapping["csat_promedio"] or 0),
            total_respuestas=int(r._mapping["total_respuestas"]),
        )
        for r in rows
    ]


@router.get("/dashboard/comentarios", response_model=list[DashboardComentarioItem])
async def dashboard_comentarios(
    response: Response,
    clasificacion: Optional[int] = Query(None, ge=1, le=5),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    id_municipio: int = Query(ID_MUNICIPIO_DEFAULT),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_supervisor(user)
    # El comentario es el detalle de la pregunta texto_libre (P8).
    conds = [
        "p.tipo = 'texto_libre'",
        "d.valor_texto IS NOT NULL",
        "d.valor_texto <> ''",
        "rsp.activo = TRUE",
        "(rsp.id_municipio = :mun OR rsp.id_municipio IS NULL)",
    ]
    params: dict = {"mun": id_municipio, "limit": limit, "offset": offset}
    if clasificacion is not None:
        conds.append("rsp.clasificacion_inicial = :clf"); params["clf"] = clasificacion
    where = " AND ".join(conds)

    total = (await db.execute(text(f"""
        SELECT COUNT(*)
          FROM encuesta_respuesta_detalle d
          JOIN encuesta_pregunta p  ON p.id_encuesta_pregunta = d.id_pregunta
          JOIN encuesta_respuesta rsp ON rsp.id_encuesta_respuesta = d.id_respuesta
         WHERE {where}
    """), params)).scalar() or 0

    rows = (await db.execute(text(f"""
        SELECT rsp.id_envio AS id_envio, rsp.fecha_alta AS fecha_respuesta,
               rsp.clasificacion_inicial, d.valor_texto AS comentario
          FROM encuesta_respuesta_detalle d
          JOIN encuesta_pregunta p  ON p.id_encuesta_pregunta = d.id_pregunta
          JOIN encuesta_respuesta rsp ON rsp.id_encuesta_respuesta = d.id_respuesta
         WHERE {where}
         ORDER BY rsp.fecha_alta DESC
         LIMIT :limit OFFSET :offset
    """), params)).fetchall()

    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return [
        DashboardComentarioItem(
            id_envio=int(r._mapping["id_envio"]),
            fecha_respuesta=r._mapping["fecha_respuesta"],
            clasificacion_inicial=int(r._mapping["clasificacion_inicial"]),
            comentario=r._mapping["comentario"],
        )
        for r in rows
    ]


# ===========================================================================
# Acciones
# ===========================================================================

@router.post("/disparar", status_code=201, response_model=EncuestaEnvioOut)
async def disparar_encuesta(
    body: DispararEncuestaIn,
    db: AsyncSession = Depends(get_db),
):
    envio, motivo = await svc.crear_envio_para_reclamo(db, body.id_reclamo)
    if envio is None:
        # 422 con el motivo concreto. MOTIVO_ERROR -> 500.
        if motivo == svc.MOTIVO_ERROR:
            raise HTTPException(500, motivo)
        raise HTTPException(422, motivo)
    # crear_envio_para_reclamo devuelve solo algunas columnas (RETURNING acotado);
    # releer la fila completa para el response.
    row = (await db.execute(text("""
        SELECT id_encuesta_envio, id_plantilla, id_ciudadano, id_reclamo,
               token_unico, email_destino_snapshot, fecha_envio, fecha_apertura,
               fecha_completada, fecha_expiracion, estado, intentos_envio,
               ultimo_error_envio, activo, fecha_alta, fecha_modificacion
          FROM encuesta_envio WHERE id_encuesta_envio = :id
    """), {"id": envio["id_encuesta_envio"]})).fetchone()
    return EncuestaEnvioOut.model_validate(row._mapping)


@router.patch("/respuestas/{id_respuesta}/atender", response_model=EncuestaRespuestaOut)
async def atender_respuesta(
    id_respuesta: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.get("nivel_acceso", 99) > 2:
        raise HTTPException(403, "Solo Admin o Supervisor pueden marcar una respuesta como atendida")

    resp = (await db.execute(text("""
        SELECT id_encuesta_respuesta, atendida, solicita_contacto
          FROM encuesta_respuesta
         WHERE id_encuesta_respuesta = :id AND activo = TRUE
         LIMIT 1
    """), {"id": id_respuesta})).fetchone()
    if resp is None:
        raise HTTPException(404, "Respuesta no encontrada")
    if resp._mapping["atendida"]:
        raise HTTPException(422, "Ya marcada como atendida")

    await db.execute(text("""
        UPDATE encuesta_respuesta
           SET atendida = TRUE, atendida_por = :uid, fecha_atendida = NOW(),
               fecha_modificacion = NOW()
         WHERE id_encuesta_respuesta = :id
    """), {"id": id_respuesta, "uid": user["id_usuario"]})
    await db.commit()

    row = (await db.execute(text("""
        SELECT id_encuesta_respuesta, id_envio, clasificacion_inicial, rama_seguida,
               tiempo_completado_seg, solicita_contacto, ip_origen, atendida,
               atendida_por, fecha_atendida, activo, fecha_alta, fecha_modificacion
          FROM encuesta_respuesta WHERE id_encuesta_respuesta = :id
    """), {"id": id_respuesta})).fetchone()
    return EncuestaRespuestaOut.model_validate(row._mapping)


# ===========================================================================
# Dispatcher (fase 2E) — llamado por cron (GitHub Actions)
# ===========================================================================

@dispatcher_router.post(
    "/dispatcher/ejecutar",
    summary="Procesa envíos pendientes y expiraciones de encuestas",
    description="Endpoint llamado por cron. Auth via header X-Dispatcher-Token (no JWT — es máquina).",
)
async def ejecutar_dispatcher(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Procesa la cola de encuestas:
      1. Envíos 'pendiente' con fecha_alta < NOW() - 24h → envía email.
      2. Envíos 'enviada'/'abierta' con fecha_expiracion < NOW() → marca 'expirada'.
    Típicamente cada hora por GitHub Actions.
    """
    expected = settings.DISPATCHER_TOKEN
    if not expected:
        # Token no configurado en el entorno → endpoint deshabilitado (no abrir sin auth).
        raise HTTPException(503, "Dispatcher no configurado")

    token = request.headers.get("X-Dispatcher-Token", "")
    if not stdlib_secrets.compare_digest(token, expected):
        logger.warning("Dispatcher: acceso no autorizado desde IP %s", get_real_ip(request))
        raise HTTPException(401, "No autorizado")

    try:
        resultado_envios = await svc.procesar_envios_pendientes(db, limite=50)
        cantidad_expirados = await svc.expirar_envios_vencidos(db)
        logger.info(
            "Dispatcher OK: procesados=%s exitosos=%s fallidos=%s expirados=%s",
            resultado_envios.get("procesados", 0),
            resultado_envios.get("exitosos", 0),
            resultado_envios.get("fallidos", 0),
            cantidad_expirados,
        )
        return {
            "envios": resultado_envios,
            "expirados": cantidad_expirados,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Dispatcher: error inesperado")
        raise HTTPException(500, "Error procesando dispatcher")
