"""App de agentes: relevamientos (mig 141) y control de entradas por QR.

Plan: PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md (decisiones de César del 2026-10-12 y 2026-11-22).

- **Relevamiento**: incidente que lleva a cabo un agente municipal. Mismo catálogo de tipos y mismo
  circuito que el reclamo (OT, asignación automática, auditoría), en la tabla `reclamos` con
  `es_relevamiento = TRUE` y numeración REL-. No tiene solicitante: sin ciudadano, sin avisos y sin
  encuesta (los disparos en `push.py` y `encuestas_service.py` lo cortan por la marca).
- **Control de entradas**: el agente lee el QR en la puerta; la entrada válida queda consumida
  (`asistio`). La respuesta es siempre 200 con un `resultado` para pintar verde o rojo.

Quién: toda cuenta interna con la app, niveles 1 a 4 (el Consultor, nivel 5, no). Cada grupo vive en
su propio router para que `modulo_habilitado` lo apague con su módulo (reclamos / entradas).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.agenda_v2 import acreditar_qr_en_puerta
from app.api.routes.geo import localidad_desde_coords
from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.municipio import municipio_actual
from app.schemas.agentes_app import (
    AcreditarQRPuertaIn, AcreditarQRPuertaOut, EventoHoyOut, RelevamientoCreadoOut,
    RelevamientoDetalleOut, RelevamientoIn, RelevamientoItemOut,
)
from app.services.autoasignacion import autoasignar_reclamo
from app.services.tramites.auth import resolver_agente_desde_usuario
from app.utils.fechas import hoy_local

logger = logging.getLogger(__name__)

relevamientos_router = APIRouter(prefix="/api/v1/agentes/relevamientos", tags=["App de agentes · Relevamientos"])
entradas_router = APIRouter(prefix="/api/v1/agentes/entradas", tags=["App de agentes · Control de entradas"])

NIVEL_MAXIMO_APP = 4  # Consultor (5) solo lee: no carga relevamientos ni controla entradas.


def _require_app(current_user: dict) -> None:
    if int(current_user.get("nivel_acceso") or 99) > NIVEL_MAXIMO_APP:
        raise HTTPException(403, "Tu cuenta es de solo consulta: no puede cargar relevamientos ni controlar entradas.")


# ─── Relevamientos ───────────────────────────────────────────────────────────

@relevamientos_router.post("", status_code=201, response_model=RelevamientoCreadoOut)
async def crear_relevamiento(
    body: RelevamientoIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    id_municipio: int = Depends(municipio_actual),
):
    """Carga un relevamiento a nombre del agente. Nace `Sin asignar` y sigue el circuito del reclamo."""
    _require_app(current_user)

    tipo = (await db.execute(text("""
        SELECT s.id_area
          FROM tipo_reclamo tr
          LEFT JOIN subarea s ON s.id_subarea = tr.id_subarea
         WHERE tr.id_tipo_reclamo = :t AND tr.activo = TRUE AND tr.id_municipio = :mun
    """), {"t": body.id_tipo_reclamo, "mun": id_municipio})).fetchone()
    if not tipo:
        raise HTTPException(422, "Tipo de reclamo inexistente")

    id_localidad = None
    if body.latitud is not None and body.longitud is not None:
        loc = await localidad_desde_coords(db, body.latitud, body.longitud)
        if loc:
            id_localidad = loc["id_localidad"]

    uid = current_user["id_usuario"]
    autor = (await db.execute(text("""
        SELECT COALESCE(NULLIF(TRIM(CONCAT_WS(' ', a.nombre, a.apellido)), ''), u.nombre, u.username) AS nombre
          FROM usuarios u
          LEFT JOIN agentes a ON a.id_usuario = u.id_usuario AND a.activo = TRUE
         WHERE u.id_usuario = :u
         LIMIT 1
    """), {"u": uid})).scalar() or "un agente"

    try:
        fila = (await db.execute(text("""
            INSERT INTO reclamos
                (id_ciudadano, id_tipo_reclamo, id_area, descripcion, direccion, domicilio_reclamo,
                 prioridad, estado, id_estado_fk, observaciones, latitud, longitud, id_localidad,
                 canal_origen, fuente_geolocalizacion, es_relevamiento, activo, fecha_alta,
                 fecha_modificacion, id_usuario_alta, id_usuario_modificacion, id_municipio)
            VALUES
                (NULL, :tipo, :area, :descripcion, :direccion, :direccion,
                 'Media', 'Sin asignar',
                 (SELECT id_estado_reclamo FROM estado_reclamo WHERE nombre = 'Sin asignar' AND activo = TRUE LIMIT 1),
                 '', :lat, :lon, :loc, 'app_agentes', :fuente, TRUE, TRUE, NOW(), NOW(), :u, :u, :mun)
            RETURNING id_reclamo, nro_reclamo
        """), {
            "tipo": body.id_tipo_reclamo, "area": tipo.id_area, "descripcion": body.descripcion,
            "direccion": body.direccion, "lat": body.latitud, "lon": body.longitud, "loc": id_localidad,
            "fuente": body.fuente_geolocalizacion, "u": uid, "mun": id_municipio,
        })).fetchone()
        await db.execute(text("""
            INSERT INTO reclamo_historial
                (id_reclamo, accion, estado_anterior, estado_nuevo, nota, fecha_alta, id_usuario_alta, id_municipio)
            VALUES (:r, 'Relevamiento ingresado', NULL, 'Sin asignar', :nota, NOW(), :u, :mun)
        """), {"r": fila.id_reclamo, "nota": f"Relevamiento cargado desde la app de agentes por {autor}",
               "u": uid, "mun": id_municipio})
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error("crear_relevamiento: %s", e)
        raise HTTPException(400, "No se pudo registrar el relevamiento") from e

    # Mismo circuito que el reclamo: la gestión con asignación automática lo asigna sola.
    background_tasks.add_task(autoasignar_reclamo, fila.id_reclamo)
    return RelevamientoCreadoOut(id_reclamo=fila.id_reclamo, nro_reclamo=fila.nro_reclamo, estado="Sin asignar")


_SELECT_RELEVAMIENTO = """
    SELECT r.id_reclamo, r.nro_reclamo, r.estado, tr.nombre AS tipo, r.descripcion, r.direccion,
           r.fecha_alta, s.nombre AS gestion, r.latitud, r.longitud, r.resolucion, r.fecha_cierre
      FROM reclamos r
      LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
      LEFT JOIN subarea s ON s.id_subarea = tr.id_subarea
     WHERE r.es_relevamiento AND r.activo = TRUE AND r.id_municipio = :mun AND r.id_usuario_alta = :u
"""


@relevamientos_router.get("", response_model=list[RelevamientoItemOut])
async def mis_relevamientos(
    response: Response,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=100_000),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    id_municipio: int = Depends(municipio_actual),
):
    """Los relevamientos que cargó la cuenta, el más reciente primero."""
    _require_app(current_user)
    params = {"mun": id_municipio, "u": current_user["id_usuario"]}
    total = (await db.execute(text(
        "SELECT COUNT(*) FROM reclamos r WHERE r.es_relevamiento AND r.activo = TRUE "
        "AND r.id_municipio = :mun AND r.id_usuario_alta = :u"), params)).scalar() or 0
    filas = (await db.execute(text(
        _SELECT_RELEVAMIENTO + " ORDER BY r.fecha_alta DESC, r.id_reclamo DESC LIMIT :lim OFFSET :off"),
        {**params, "lim": limit, "off": offset})).mappings().all()
    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return [RelevamientoItemOut(**{k: f[k] for k in RelevamientoItemOut.model_fields}) for f in filas]


@relevamientos_router.get("/{id_reclamo}", response_model=RelevamientoDetalleOut)
async def detalle_relevamiento(
    id_reclamo: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    id_municipio: int = Depends(municipio_actual),
):
    """Detalle de un relevamiento propio. Uno ajeno o inexistente da 404."""
    _require_app(current_user)
    if id_reclamo > 2_147_483_647:
        raise HTTPException(404, "Relevamiento no encontrado")
    f = (await db.execute(text(_SELECT_RELEVAMIENTO + " AND r.id_reclamo = :id"),
                          {"mun": id_municipio, "u": current_user["id_usuario"], "id": id_reclamo})).mappings().first()
    if not f:
        raise HTTPException(404, "Relevamiento no encontrado")
    hist = (await db.execute(text("""
        SELECT accion, estado_anterior, estado_nuevo, fecha_alta AS fecha
          FROM reclamo_historial WHERE id_reclamo = :id
         ORDER BY fecha_alta, id_historial
    """), {"id": id_reclamo})).mappings().all()
    return RelevamientoDetalleOut(**dict(f), historial=[dict(h) for h in hist])


# ─── Control de entradas ─────────────────────────────────────────────────────

@entradas_router.post("/acreditar-qr", response_model=AcreditarQRPuertaOut)
async def acreditar_qr(
    body: AcreditarQRPuertaIn,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    id_municipio: int = Depends(municipio_actual),
):
    """Lee el QR de una entrada en la puerta. Válida y de hoy → queda consumida («acreditada»)."""
    _require_app(current_user)
    return await acreditar_qr_en_puerta(db, body.qr_codigo, current_user["id_usuario"], id_municipio)


@entradas_router.get("/eventos-hoy", response_model=list[EventoHoyOut])
async def eventos_de_hoy(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    id_municipio: int = Depends(municipio_actual),
):
    """Eventos de hoy del municipio (no cancelados), los que tiene a cargo el agente primero."""
    _require_app(current_user)
    agente = await resolver_agente_desde_usuario(current_user["id_usuario"], db)
    filas = (await db.execute(text("""
        SELECT e.id_evento, e.nombre, e.fecha, e.hora_inicio, e.hora_fin, esp.nombre AS espacio,
               COUNT(r.id_evento_reserva) FILTER (WHERE er.codigo <> 'cancelada') AS reservas,
               COUNT(r.id_evento_reserva) FILTER (WHERE er.codigo = 'asistio') AS acreditadas,
               EXISTS (
                   SELECT 1 FROM evento_encargados ee
                    WHERE ee.id_evento = e.id_evento AND ee.activo = TRUE
                      AND ((ee.tipo_recurso = 'agente' AND ee.id_recurso = :ag)
                        OR (ee.tipo_recurso = 'equipo' AND ee.id_recurso = ANY (CAST(:eqs AS integer[]))))
               ) AS soy_encargado
          FROM eventos e
          LEFT JOIN estado_evento ev ON ev.id_estado_evento = e.id_estado_evento
          LEFT JOIN espacios_agenda esp ON esp.id_espacio = e.id_espacio
          LEFT JOIN evento_reservas r ON r.id_evento = e.id_evento AND r.activo = TRUE
          LEFT JOIN estado_reserva er ON er.id_estado_reserva = r.id_estado_reserva
         WHERE e.id_municipio = :mun AND e.activo = TRUE AND e.fecha = :hoy
           AND COALESCE(ev.codigo, 'activo') <> 'cancelado'
         GROUP BY e.id_evento, esp.nombre
         ORDER BY soy_encargado DESC, e.hora_inicio NULLS LAST, e.nombre
    """), {"mun": id_municipio, "hoy": hoy_local(),
           "ag": agente["id_agente"] if agente else 0,
           "eqs": agente["ids_equipos"] if agente else []})).mappings().all()
    return [EventoHoyOut(**dict(f)) for f in filas]
