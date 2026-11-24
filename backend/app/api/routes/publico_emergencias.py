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
    NO clasifica triage: elige del catalogo del vecino -mig 145- y describe)
  - id_usuario_alta = NULL (no es un usuario interno)
  - log CREACION con id_usuario=NULL y el vecino identificado en payload_json

Catalogo del vecino (mig 145, PLAN_CATALOGO_EMERGENCIAS_VECINO.md): grupos y
opciones por municipio; cada opcion apunta a un tipo (y subtipo) del COM. Los
botones SOS se resuelven aca por su opcion, no buscando palabras en la app.
"""
from __future__ import annotations

import json
from typing import Any, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_ciudadano
from app.core.database import get_db
from app.core.municipio import municipio_vecino
from app.middleware.rate_limit import check_rate_limit
from app.services.notificaciones import notificar_alerta_panico
from app.utils.request_helpers import get_real_ip

router = APIRouter(prefix="/api/v1/publico/emergencias", tags=["publico-emergencias"])

CANAL_VECINO = "APP_VECINO"

# Prefijo con el que la PWA arma la descripcion del boton "Seguridad".
# La comparacion normaliza (strip + upper + sin tildes) porque el texto puede
# venir con tilde y casing variable. es_panico lo setea SOLO el backend: el
# body publico no tiene ese campo (mig 97).
_PREFIJO_PANICO = "ALERTA DE PANICO"
_SIN_TILDES = str.maketrans("ÁÉÍÓÚ", "AEIOU")


def _es_alerta_panico(descripcion: Optional[str]) -> bool:
    if not descripcion:
        return False
    normalizado = descripcion.strip().upper().translate(_SIN_TILDES)
    return normalizado.startswith(_PREFIJO_PANICO)


BOTON_PANICO = "seguridad"
# El panico nunca se rechaza por configuracion: sin su opcion, estos tipos en orden.
_TIPOS_PANICO = ("ALERTA_PANICO", "PEDIDO_GENERICO_AUXILIO")
_NOMBRE_PANICO = "Alerta de pánico"
OPCION_INEXISTENTE = "Opción de emergencia inexistente o inactiva"
FALTA_DESCRIPCION = "Contanos qué está pasando para poder ayudarte"


class EmergenciaPublicaCreate(BaseModel):
    """La clasificacion va por UNA de tres vias: `id_opcion` (catalogo del vecino), `boton_sos` (boton del
    abanico) o `id_tipo` (versiones anteriores de la app)."""
    id_opcion: Optional[int] = Field(None, ge=1, le=2_147_483_647)
    boton_sos: Optional[Literal["seguridad", "incendio", "asistencia", "accidente", "tormenta"]] = None
    id_tipo: Optional[int] = Field(None, ge=1, le=2_147_483_647)
    id_subtipo: Optional[int] = Field(None, ge=1, le=2_147_483_647)
    direccion_evento: str = Field(..., min_length=3, max_length=300)
    descripcion: Optional[str] = Field(None, max_length=2000)
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    referencia_ubicacion: Optional[str] = Field(None, max_length=300)

    @model_validator(mode="after")
    def _una_clasificacion(self):
        if sum(x is not None for x in (self.id_opcion, self.boton_sos, self.id_tipo)) != 1:
            raise ValueError("Indicá qué está pasando: una sola opción, un botón SOS o un tipo")
        return self


# ─── Catalogo del vecino (mig 145) ───────────────────────────────────────────

_FROM_OPCION = """
    FROM emergencia_opcion_vecino o
    JOIN emergencia_tipo t ON t.id_emergencia_tipo = o.id_tipo AND t.activo
    LEFT JOIN emergencia_grupo_vecino g ON g.id_emergencia_grupo_vecino = o.id_grupo
    WHERE o.activo AND o.id_municipio = :mun
      AND (o.id_grupo IS NULL OR g.activo OR o.boton_sos IS NOT NULL)
"""


@router.get("/catalogo")
async def catalogo_vecino(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
    id_municipio: int = Depends(municipio_vecino),
) -> Any:
    """Lo que el vecino elige: grupos con sus opciones, y la opcion de cada boton SOS. Sin datos del triage
    (tipo, prioridad, 911, gestion). Una opcion cuyo tipo se dio de baja no se ofrece."""
    filas = (await db.execute(text(f"""
        SELECT o.id_emergencia_opcion_vecino AS id_opcion, o.nombre, o.texto_ayuda, o.descripcion_obligatoria,
               o.boton_sos, g.id_emergencia_grupo_vecino AS id_grupo, g.nombre AS grupo, g.icono,
               g.activo AS grupo_activo
        {_FROM_OPCION}
        ORDER BY g.orden, g.id_emergencia_grupo_vecino, o.orden, o.id_emergencia_opcion_vecino
    """), {"mun": id_municipio})).mappings().all()
    grupos: dict[int, dict] = {}
    botones: dict[str, dict] = {}
    for f in filas:
        opcion = {"id_opcion": f["id_opcion"], "nombre": f["nombre"], "texto_ayuda": f["texto_ayuda"],
                  "descripcion_obligatoria": f["descripcion_obligatoria"]}
        if f["boton_sos"]:
            botones[f["boton_sos"]] = opcion
        if f["id_grupo"] is not None and f["grupo_activo"]:
            grupos.setdefault(f["id_grupo"], {
                "id_grupo": f["id_grupo"], "nombre": f["grupo"], "icono": f["icono"], "opciones": [],
            })["opciones"].append(opcion)
    return {"grupos": list(grupos.values()), "botones_sos": botones}


async def _clasificar(db: AsyncSession, body: EmergenciaPublicaCreate, id_municipio: int) -> dict:
    """{id_tipo, id_subtipo, nombre, descripcion_obligatoria, panico} de lo que eligio el vecino."""
    if body.id_tipo is not None:
        return {"id_tipo": body.id_tipo, "id_subtipo": body.id_subtipo, "nombre": None,
                "descripcion_obligatoria": False, "panico": False}
    panico = body.boton_sos == BOTON_PANICO
    campo, valor = ("o.id_emergencia_opcion_vecino", body.id_opcion) if body.id_opcion is not None \
        else ("o.boton_sos", body.boton_sos)
    op = (await db.execute(text(f"""
        SELECT o.id_tipo, o.nombre, o.descripcion_obligatoria,
               (SELECT st.id_emergencia_subtipo FROM emergencia_subtipo st
                 WHERE st.id_emergencia_subtipo = o.id_subtipo AND st.id_tipo = o.id_tipo AND st.activo) AS id_subtipo
        {_FROM_OPCION} AND {campo} = :v
    """), {"mun": id_municipio, "v": valor})).mappings().first()
    if op:
        # Un SOS no pide nada mas: se toca en la urgencia.
        return {**op, "panico": panico,
                "descripcion_obligatoria": op["descripcion_obligatoria"] and body.boton_sos is None}
    if panico:
        for codigo in _TIPOS_PANICO:
            id_tipo = await db.scalar(text(
                "SELECT id_emergencia_tipo FROM emergencia_tipo WHERE codigo = :c AND activo AND id_municipio = :mun "
                "ORDER BY id_emergencia_tipo LIMIT 1"), {"c": codigo, "mun": id_municipio})
            if id_tipo:
                return {"id_tipo": id_tipo, "id_subtipo": None, "nombre": _NOMBRE_PANICO,
                        "descripcion_obligatoria": False, "panico": True}
    raise HTTPException(422, OPCION_INEXISTENTE)


# ─── Catalogo del COM (versiones anteriores de la app) para el form del vecino ─────────────────────────────────

@router.get("/tipos")
async def tipos_publico(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
    id_municipio: int = Depends(municipio_vecino),
) -> Any:
    """Tipos de emergencia activos para que el vecino clasifique su reporte.
    Solo datos no sensibles (sin prioridades/organismos del triage interno)."""
    rows = (await db.execute(text("""
        SELECT t.id_emergencia_tipo, t.codigo, t.nombre, t.descripcion,
               t.id_subarea, s.nombre AS subarea_nombre, t.es_emergencia
        FROM emergencia_tipo t
        JOIN subarea s ON s.id_subarea = t.id_subarea
        WHERE t.activo AND t.id_municipio = :mun
        ORDER BY s.nombre, t.nombre
    """), {"mun": id_municipio})).mappings().all()
    return [dict(r) for r in rows]


@router.get("/tipos/{id_tipo}/subtipos")
async def subtipos_publico(
    id_tipo: int,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
    id_municipio: int = Depends(municipio_vecino),
) -> Any:
    rows = (await db.execute(text("""
        SELECT id_emergencia_subtipo, id_tipo, codigo, nombre, descripcion
        FROM emergencia_subtipo
        WHERE id_tipo = :t AND activo AND id_municipio = :mun
        ORDER BY nombre
    """), {"t": id_tipo, "mun": id_municipio})).mappings().all()
    return [dict(r) for r in rows]


# ─── GET /publico/emergencias/eventos — mis reportes ─────────────────────────

@router.get("/eventos")
async def listar_mis_emergencias(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
    id_municipio: int = Depends(municipio_vecino),
) -> Any:
    """Lista SOLO los eventos del vecino logueado (id_ciudadano del token).
    Sin datos del triage interno (operador, organismo, prioridad). Si reporto
    desde el catalogo, ve la opcion que eligio aunque el COM reclasifique."""
    rows = (await db.execute(text("""
        SELECT e.id_emergencia_evento, e.numero_operativo,
               COALESCE(e.clasificacion_vecino, t.nombre) AS tipo_nombre,
               CASE WHEN e.clasificacion_vecino IS NULL THEN st.nombre END AS subtipo_nombre,
               est.codigo AS estado_codigo, est.nombre AS estado_nombre,
               est.es_terminal,
               e.direccion_evento, e.referencia_ubicacion,
               e.fecha_hora_recepcion, e.fecha_hora_cierre
        FROM emergencia_evento e
        JOIN emergencia_tipo t ON t.id_emergencia_tipo = e.id_tipo
        LEFT JOIN emergencia_subtipo st ON st.id_emergencia_subtipo = e.id_subtipo
        JOIN emergencia_estado est ON est.id_emergencia_estado = e.id_estado
        WHERE e.activo AND e.id_ciudadano_buc = :c AND e.id_municipio = :mun
        ORDER BY e.fecha_hora_recepcion DESC
        LIMIT :limit OFFSET :offset
    """), {"c": current["id_ciudadano"], "limit": limit, "offset": offset, "mun": id_municipio})).mappings().all()
    return [dict(r) for r in rows]


# ─── POST /publico/emergencias/eventos — reportar emergencia ─────────────────

@router.post("/eventos", status_code=201, responses={422: {
    "description": f"{OPCION_INEXISTENTE} · {FALTA_DESCRIPCION}"}})
async def reportar_emergencia(
    body: EmergenciaPublicaCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_ciudadano),
    id_municipio: int = Depends(municipio_vecino),
) -> Any:
    """El vecino reporta una emergencia desde la App Vecinos. Devuelve el
    numero_operativo para seguimiento (lo genera el trigger de la DB)."""
    check_rate_limit(f"emergpub:{get_real_ip(request)}", max_requests=5, window_seconds=60)

    elegido = await _clasificar(db, body, id_municipio)
    id_tipo, id_subtipo = elegido["id_tipo"], elegido["id_subtipo"]
    descripcion = (body.descripcion or "").strip() or None
    if elegido["descripcion_obligatoria"] and not descripcion:
        raise HTTPException(422, FALTA_DESCRIPCION)

    tipo = (await db.execute(text("""
        SELECT id_emergencia_tipo, id_subarea, id_prioridad_default,
               id_organismo_derivacion_default
        FROM emergencia_tipo WHERE id_emergencia_tipo = :id AND activo AND id_municipio = :mun
    """), {"id": id_tipo, "mun": id_municipio})).mappings().first()
    if not tipo:
        raise HTTPException(422, "Tipo de emergencia inexistente o inactivo")

    id_prioridad = None
    if id_subtipo is not None:
        subtipo = (await db.execute(text("""
            SELECT id_prioridad_override FROM emergencia_subtipo
            WHERE id_emergencia_subtipo = :id AND id_tipo = :t AND activo
        """), {"id": id_subtipo, "t": id_tipo})).mappings().first()
        if not subtipo:
            raise HTTPException(422, "El subtipo no pertenece al tipo indicado o está inactivo")
        id_prioridad = subtipo["id_prioridad_override"]
    if id_prioridad is None:
        id_prioridad = tipo["id_prioridad_default"]

    canal = (await db.execute(text("""
        SELECT id_emergencia_canal_ingreso FROM emergencia_canal_ingreso
        WHERE codigo = :c AND activo AND id_municipio = :mun
    """), {"c": CANAL_VECINO, "mun": id_municipio})).scalar()
    if not canal:
        raise HTTPException(503, "Canal APP_VECINO no configurado")

    estado = (await db.execute(text("""
        SELECT id_emergencia_estado FROM emergencia_estado
        WHERE codigo = 'PENDIENTE' AND activo
    """))).scalar()
    if not estado:
        raise HTTPException(503, "Estado PENDIENTE no configurado")

    # Alerta de panico (mig 97): el boton «Seguridad» (mig 145) o, en versiones
    # anteriores de la app, el prefijo de la descripcion.
    es_panico = elegido["panico"] or _es_alerta_panico(body.descripcion)

    id_evento = (await db.execute(text("""
        INSERT INTO emergencia_evento
            (id_subarea, id_tipo, id_subtipo, id_prioridad, id_estado,
             id_canal_ingreso, id_organismo_derivacion, id_operador_receptor,
             denunciante_anonimo, id_ciudadano_buc, id_contacto_eventual,
             direccion_evento, latitud, longitud, referencia_ubicacion,
             observaciones_recepcion, es_panico, clasificacion_vecino, activo, id_municipio)
        VALUES (:sub, :tipo, :stipo, :prio, :est, :canal, :org, NULL,
                FALSE, :ciu, NULL, :dir, :lat, :lon, :ref, :obs, :panico, :clasif, TRUE, :mun)
        RETURNING id_emergencia_evento
    """), {
        "sub": tipo["id_subarea"], "tipo": id_tipo, "stipo": id_subtipo,
        "prio": id_prioridad, "est": estado, "canal": canal,
        "org": tipo["id_organismo_derivacion_default"],
        "ciu": current["id_ciudadano"],
        "dir": body.direccion_evento.strip(), "lat": body.latitud,
        "lon": body.longitud, "ref": body.referencia_ubicacion,
        "obs": descripcion, "clasif": elegido["nombre"],
        "panico": es_panico, "mun": id_municipio,
    })).scalar()

    # log CREACION: id_usuario NULL (no es usuario interno); el vecino emisor
    # queda identificado en payload_json (plan Fase 5 punto 3).
    await db.execute(text("""
        INSERT INTO emergencia_log
            (id_evento, id_usuario, tipo_accion, estado_nuevo, payload_json, observaciones, id_municipio)
        VALUES (:e, NULL, 'CREACION', 'PENDIENTE', CAST(:p AS jsonb), :o, :mun)
    """), {
        "e": id_evento, "mun": id_municipio,
        "p": json.dumps({
            "origen": "app_vecinos",
            "id_ciudadano": current["id_ciudadano"],
            "canal": CANAL_VECINO,
            "opcion": elegido["nombre"],
        }),
        "o": descripcion,
    })
    await db.commit()

    # Alerta de panico: aviso in-app + email al COM de la subarea, best-effort
    # post-commit (patron del hook de encuestas en turnos.py — la creacion del
    # evento NUNCA falla por la notificacion). El service abre su propia
    # sesion SQL (feedback_background_tasks_sesion_nueva).
    if es_panico:
        try:
            await notificar_alerta_panico(id_evento, background_tasks)
        except Exception:
            pass

    row = (await db.execute(text("""
        SELECT e.id_emergencia_evento, e.numero_operativo,
               est.codigo AS estado_codigo, e.fecha_hora_recepcion
        FROM emergencia_evento e
        JOIN emergencia_estado est ON est.id_emergencia_estado = e.id_estado
        WHERE e.id_emergencia_evento = :id
    """), {"id": id_evento})).mappings().first()
    return dict(row)
