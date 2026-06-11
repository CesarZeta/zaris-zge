"""
ZARIS API - EMERGENCIAS del vecino (App Vecinos, Fase 5 del plan COM).

Bajo /api/v1/publico/emergencias/*. Guard get_current_ciudadano (JWT scope
'publico') — el guard rechaza tokens scope 'agente' y viceversa (s38).

El vecino reporta una emergencia A SU PROPIO NOMBRE: id_ciudadano_buc SIEMPRE
sale del token, nunca del body (project_usuario_vs_ciudadano_modelo). Reglas
fijas del canal (plan seccion 4.5, no negociables desde el body):
  - id_canal_ingreso = APP_VECINO (el body no puede elegir canal)
  - id_operador_receptor = NULL (no hubo operador)
  - id_estado = PENDIENTE
  - id_subarea / prioridad / organismo default derivados del tipo (el vecino
    NO clasifica triage: elige tipo + subtipo y describe)
  - id_usuario_alta = NULL (no es un usuario interno)
  - log CREACION con id_usuario=NULL y el vecino identificado en payload_json

Sin migracion: reusa las tablas de las migs 82-83.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_ciudadano
from app.core.database import get_db
from app.middleware.rate_limit import check_rate_limit
from app.utils.request_helpers import get_real_ip

router = APIRouter(prefix="/api/v1/publico/emergencias", tags=["publico-emergencias"])

CANAL_VECINO = "APP_VECINO"


class EmergenciaPublicaCreate(BaseModel):
    id_tipo: int
    id_subtipo: Optional[int] = None
    direccion_evento: str = Field(..., min_length=3, max_length=300)
    descripcion: Optional[str] = Field(None, max_length=2000)
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    referencia_ubicacion: Optional[str] = Field(None, max_length=300)


# ─── Catalogo minimo para el form del vecino ─────────────────────────────────

@router.get("/tipos")
async def tipos_publico(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
) -> Any:
    """Tipos de emergencia activos para que el vecino clasifique su reporte.
    Solo datos no sensibles (sin prioridades/organismos del triage interno)."""
    rows = (await db.execute(text("""
        SELECT t.id_emergencia_tipo, t.codigo, t.nombre, t.descripcion,
               t.id_subarea, s.nombre AS subarea_nombre, t.es_emergencia
        FROM emergencia_tipo t
        JOIN subarea s ON s.id_subarea = t.id_subarea
        WHERE t.activo
        ORDER BY s.nombre, t.nombre
    """))).mappings().all()
    return [dict(r) for r in rows]


@router.get("/tipos/{id_tipo}/subtipos")
async def subtipos_publico(
    id_tipo: int,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
) -> Any:
    rows = (await db.execute(text("""
        SELECT id_emergencia_subtipo, id_tipo, codigo, nombre, descripcion
        FROM emergencia_subtipo
        WHERE id_tipo = :t AND activo
        ORDER BY nombre
    """), {"t": id_tipo})).mappings().all()
    return [dict(r) for r in rows]


# ─── GET /publico/emergencias/eventos — mis reportes ─────────────────────────

@router.get("/eventos")
async def listar_mis_emergencias(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
) -> Any:
    """Lista SOLO los eventos del vecino logueado (id_ciudadano del token).
    Sin datos del triage interno (operador, organismo, prioridad)."""
    rows = (await db.execute(text("""
        SELECT e.id_emergencia_evento, e.numero_operativo,
               t.nombre AS tipo_nombre, st.nombre AS subtipo_nombre,
               est.codigo AS estado_codigo, est.nombre AS estado_nombre,
               est.es_terminal,
               e.direccion_evento, e.referencia_ubicacion,
               e.fecha_hora_recepcion, e.fecha_hora_cierre
        FROM emergencia_evento e
        JOIN emergencia_tipo t ON t.id_emergencia_tipo = e.id_tipo
        LEFT JOIN emergencia_subtipo st ON st.id_emergencia_subtipo = e.id_subtipo
        JOIN emergencia_estado est ON est.id_emergencia_estado = e.id_estado
        WHERE e.activo AND e.id_ciudadano_buc = :c
        ORDER BY e.fecha_hora_recepcion DESC
        LIMIT :limit OFFSET :offset
    """), {"c": current["id_ciudadano"], "limit": limit, "offset": offset})).mappings().all()
    return [dict(r) for r in rows]


# ─── POST /publico/emergencias/eventos — reportar emergencia ─────────────────

@router.post("/eventos", status_code=201)
async def reportar_emergencia(
    body: EmergenciaPublicaCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
) -> Any:
    """El vecino reporta una emergencia desde la App Vecinos. Devuelve el
    numero_operativo para seguimiento (lo genera el trigger de la DB)."""
    check_rate_limit(get_real_ip(request), max_requests=5, window_seconds=60)

    tipo = (await db.execute(text("""
        SELECT id_emergencia_tipo, id_subarea, id_prioridad_default,
               id_organismo_derivacion_default
        FROM emergencia_tipo WHERE id_emergencia_tipo = :id AND activo
    """), {"id": body.id_tipo})).mappings().first()
    if not tipo:
        raise HTTPException(422, "Tipo de emergencia inexistente o inactivo")

    id_prioridad = None
    if body.id_subtipo is not None:
        subtipo = (await db.execute(text("""
            SELECT id_prioridad_override FROM emergencia_subtipo
            WHERE id_emergencia_subtipo = :id AND id_tipo = :t AND activo
        """), {"id": body.id_subtipo, "t": body.id_tipo})).mappings().first()
        if not subtipo:
            raise HTTPException(422, "El subtipo no pertenece al tipo indicado o esta inactivo")
        id_prioridad = subtipo["id_prioridad_override"]
    if id_prioridad is None:
        id_prioridad = tipo["id_prioridad_default"]

    canal = (await db.execute(text("""
        SELECT id_emergencia_canal_ingreso FROM emergencia_canal_ingreso
        WHERE codigo = :c AND activo
    """), {"c": CANAL_VECINO})).scalar()
    if not canal:
        raise HTTPException(503, "Canal APP_VECINO no configurado")

    estado = (await db.execute(text("""
        SELECT id_emergencia_estado FROM emergencia_estado
        WHERE codigo = 'PENDIENTE' AND activo
    """))).scalar()
    if not estado:
        raise HTTPException(503, "Estado PENDIENTE no configurado")

    id_evento = (await db.execute(text("""
        INSERT INTO emergencia_evento
            (id_subarea, id_tipo, id_subtipo, id_prioridad, id_estado,
             id_canal_ingreso, id_organismo_derivacion, id_operador_receptor,
             denunciante_anonimo, id_ciudadano_buc, id_contacto_eventual,
             direccion_evento, latitud, longitud, referencia_ubicacion,
             observaciones_recepcion, activo)
        VALUES (:sub, :tipo, :stipo, :prio, :est, :canal, :org, NULL,
                FALSE, :ciu, NULL, :dir, :lat, :lon, :ref, :obs, TRUE)
        RETURNING id_emergencia_evento
    """), {
        "sub": tipo["id_subarea"], "tipo": body.id_tipo, "stipo": body.id_subtipo,
        "prio": id_prioridad, "est": estado, "canal": canal,
        "org": tipo["id_organismo_derivacion_default"],
        "ciu": current["id_ciudadano"],
        "dir": body.direccion_evento.strip(), "lat": body.latitud,
        "lon": body.longitud, "ref": body.referencia_ubicacion,
        "obs": (body.descripcion or "").strip() or None,
    })).scalar()

    # log CREACION: id_usuario NULL (no es usuario interno); el vecino emisor
    # queda identificado en payload_json (plan Fase 5 punto 3).
    await db.execute(text("""
        INSERT INTO emergencia_log
            (id_evento, id_usuario, tipo_accion, estado_nuevo, payload_json, observaciones)
        VALUES (:e, NULL, 'CREACION', 'PENDIENTE', CAST(:p AS jsonb), :o)
    """), {
        "e": id_evento,
        "p": json.dumps({
            "origen": "app_vecinos",
            "id_ciudadano": current["id_ciudadano"],
            "canal": CANAL_VECINO,
        }),
        "o": (body.descripcion or "").strip() or None,
    })
    await db.commit()

    row = (await db.execute(text("""
        SELECT e.id_emergencia_evento, e.numero_operativo,
               est.codigo AS estado_codigo, e.fecha_hora_recepcion
        FROM emergencia_evento e
        JOIN emergencia_estado est ON est.id_emergencia_estado = e.id_estado
        WHERE e.id_emergencia_evento = :id
    """), {"id": id_evento})).mappings().first()
    return dict(row)
