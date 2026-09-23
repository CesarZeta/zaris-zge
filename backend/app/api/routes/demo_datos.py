# -*- coding: utf-8 -*-
"""Poblado periodico de datos demo para los tableros BI (municipio San Andres).

POST /api/v1/demo/poblar — encola la generacion de reclamos/historial/encuestas
demo (y, desde 2026-09-19, turnos/colero/Guardia/eventos demo via
demo_atencion.py) en un rango y/o el avance del ciclo de vida de los pendientes
demo existentes (servicios app/services/demo_datos.py y demo_atencion.py). Lo
llama el cron semanal de GitHub Actions (.github/workflows/demo-datos.yml) y
sirve para la carga inicial por meses.

Desde 2026-09-22 la corrida es ASINCRONA: el endpoint valida, la encola en un
BackgroundTask y responde 202 con `id_corrida`; el resultado (los conteos por
modulo) se consulta en GET /api/v1/demo/poblar/{id_corrida}. Motivo: el edge de
Railway corta toda respuesta a los ~300 s y una semana con reclamos+atencion
tardo 14,5 min (run del 2026-09-21: 502 "upstream error" con el backend
terminando igual). Las corridas viven en memoria de la instancia (una sola en
Railway; con replicas habria que persistirlas): si el proceso se reinicia a
mitad, el GET da 404 y hay que verificar la DB antes de re-disparar (el
generador de reclamos NO es idempotente). Mientras hay una corrida en curso, un
segundo POST devuelve 409 (anti doble capa, incidente 2026-08-31).

Auth dual (a diferencia de los otros mantenimientos, tambien lo dispara un
humano para la carga inicial):
  - header X-Dispatcher-Token == settings.DISPATCHER_TOKEN (maquina), o
  - JWT de agente con nivel_acceso 1 (admin).
"""
from __future__ import annotations

import logging
import secrets as stdlib_secrets
import time
import uuid
from collections import OrderedDict
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Request
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import ALGORITHM
from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.services import demo_atencion, demo_datos
from app.utils.request_helpers import get_real_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/demo", tags=["demo-datos"])

# Corridas de ESTA instancia (id_corrida -> registro), las ultimas MAX_CORRIDAS.
# Un solo event loop: no hace falta lock para leer/escribir el dict.
MAX_CORRIDAS = 20
_corridas: "OrderedDict[str, dict]" = OrderedDict()


class PoblarIn(BaseModel):
    desde: date | None = None
    hasta: date | None = None
    min_mensual: int = Field(300, ge=1, le=1500)
    max_mensual: int = Field(500, ge=1, le=1500)
    vecinos_nuevos: int = Field(250, ge=0, le=1000)
    generar: bool = True
    avanzar: bool = True
    semilla: int | None = None
    # Que generar/avanzar (2026-09-19): 'reclamos' = demo_datos.py, 'atencion' =
    # demo_atencion.py (turnos + colero + Guardia + eventos, tablero Datos -> Atencion).
    # El cron manda los dos; la carga inicial de atencion se dispara con ['atencion'].
    modulos: list[Literal["reclamos", "atencion"]] = ["reclamos", "atencion"]
    # Atencion: dias hacia adelante con turnos/eventos reservados (Mesa del dia, colero).
    dias_futuro: int = Field(7, ge=0, le=30)


def _ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _registrar(corrida: dict) -> None:
    _corridas[corrida["id_corrida"]] = corrida
    while len(_corridas) > MAX_CORRIDAS:
        _corridas.popitem(last=False)


def _corrida_en_curso() -> dict | None:
    for c in _corridas.values():
        if c.get("estado") == "en_curso":
            return c
    return None


async def _autorizar(request: Request, db: AsyncSession) -> str:
    """Dispatcher token (maquina) o JWT admin nivel 1. 401 si ninguno."""
    expected = settings.DISPATCHER_TOKEN
    token = request.headers.get("X-Dispatcher-Token", "")
    if expected and token and stdlib_secrets.compare_digest(token, expected):
        return "dispatcher"

    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = jwt.decode(auth[7:], settings.SECRET_KEY, algorithms=[ALGORITHM])
            if payload.get("scope", "agente") == "agente" and payload.get("sub"):
                fila = (await db.execute(
                    text("SELECT id_usuario, nivel_acceso, activo FROM usuarios WHERE id_usuario = :id"),
                    {"id": int(payload["sub"])})).fetchone()
                if fila and fila.activo and fila.nivel_acceso == 1:
                    return f"admin:{fila.id_usuario}"
        except (JWTError, ValueError):
            pass

    logger.warning("demo/poblar: acceso no autorizado desde IP %s", get_real_ip(request))
    raise HTTPException(401, "No autorizado")


async def _ejecutar_corrida(id_corrida: str, body: PoblarIn, desde: date, hasta: date,
                            modulos: set[str]) -> None:
    """Corre en BackgroundTasks, DESPUES de enviado el 202: sesion SQL propia (la del
    request ya esta cerrada) y try/except global (nadie mas la atrapa). Cada servicio
    commitea al terminar su paso, asi que un fallo deja los pasos previos aplicados —
    el registro guarda el resultado parcial para saber que entro."""
    corrida = _corridas.get(id_corrida)
    if corrida is None:  # desalojada por MAX_CORRIDAS antes de arrancar (no deberia pasar)
        corrida = {"id_corrida": id_corrida, "estado": "en_curso", "ejecutado_por": "?",
                   "inicio": _ahora_iso()}
        _registrar(corrida)
    t0 = time.monotonic()
    resultado: dict = {}
    try:
        async with AsyncSessionLocal() as db:
            if body.generar and "reclamos" in modulos:
                resultado["generado"] = await demo_datos.generar_periodo(
                    db, desde, hasta,
                    min_mensual=body.min_mensual, max_mensual=body.max_mensual,
                    vecinos_nuevos=body.vecinos_nuevos, semilla=body.semilla,
                )
            if body.generar and "atencion" in modulos:
                resultado["generado_atencion"] = await demo_atencion.generar_periodo_atencion(
                    db, desde, hasta, semilla=body.semilla, dias_futuro=body.dias_futuro,
                )
            if body.avanzar and "reclamos" in modulos:
                resultado["avanzado"] = await demo_datos.avanzar_pendientes(db, semilla=body.semilla)
            if body.avanzar and "atencion" in modulos:
                resultado["avanzado_atencion"] = await demo_atencion.avanzar_pendientes_atencion(
                    db, semilla=body.semilla)
        corrida["estado"] = "ok"
        corrida["resultado"] = resultado
        logger.info("demo/poblar OK (%s, corrida %s, %.0f s): %s", corrida.get("ejecutado_por"),
                    id_corrida, time.monotonic() - t0, resultado)
    except Exception as e:  # noqa: BLE001 — fail-safe: el log es el unico testigo
        corrida["estado"] = "error"
        corrida["error"] = f"{type(e).__name__}: {e}"
        corrida["resultado"] = resultado or None
        logger.error("demo/poblar FALLO (corrida %s, %.0f s, pasos aplicados=%s): %s",
                     id_corrida, time.monotonic() - t0, sorted(resultado), e, exc_info=True)
    finally:
        corrida["fin"] = _ahora_iso()
        corrida["duracion_s"] = round(time.monotonic() - t0)


@router.post(
    "/poblar",
    status_code=202,
    summary="Encola la generacion/avance de datos demo para los tableros BI (reclamos + atencion)",
    description=(
        "Cron semanal o carga inicial. Valida y encola la corrida; responde 202 con `id_corrida` "
        "y el resultado se consulta en GET /api/v1/demo/poblar/{id_corrida}. "
        "Auth: X-Dispatcher-Token o JWT admin."
    ),
    responses={
        202: {"description": "Corrida encolada (id_corrida, estado='en_curso', consulta)"},
        409: {"description": "Rango invalido (desde > hasta o mayor a 45 dias), o ya hay una "
                             "corrida en curso en esta instancia"},
    },
)
async def poblar_demo(
    request: Request,
    background_tasks: BackgroundTasks,
    body: PoblarIn | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    quien = await _autorizar(request, db)
    body = body or PoblarIn()

    hoy = date.today()
    desde = body.desde or (hoy - timedelta(days=6))
    hasta = body.hasta or hoy
    if desde > hasta or (hasta - desde).days > 45:
        raise HTTPException(409, "Rango invalido: desde <= hasta y maximo 45 dias por llamada")
    if body.min_mensual > body.max_mensual:
        raise HTTPException(409, "min_mensual no puede superar a max_mensual")

    modulos = set(body.modulos or ["reclamos", "atencion"])

    en_curso = _corrida_en_curso()
    if en_curso is not None:
        raise HTTPException(
            409,
            f"Ya hay una corrida en curso ({en_curso['id_corrida']}, desde {en_curso.get('inicio')}): "
            "esperar a que termine antes de disparar otra (dos corridas del mismo rango duplican "
            "los reclamos demo)",
        )

    id_corrida = uuid.uuid4().hex[:12]
    corrida = {
        "id_corrida": id_corrida,
        "estado": "en_curso",
        "ejecutado_por": quien,
        "inicio": _ahora_iso(),
        "fin": None,
        "duracion_s": None,
        "desde": str(desde),
        "hasta": str(hasta),
        "modulos": sorted(modulos),
        "generar": body.generar,
        "avanzar": body.avanzar,
        "consulta": f"/api/v1/demo/poblar/{id_corrida}",
        "resultado": None,
        "error": None,
    }
    _registrar(corrida)
    background_tasks.add_task(_ejecutar_corrida, id_corrida, body, desde, hasta, modulos)
    logger.info("demo/poblar encolada (%s): corrida %s %s..%s modulos=%s generar=%s avanzar=%s",
                quien, id_corrida, desde, hasta, sorted(modulos), body.generar, body.avanzar)
    return dict(corrida)


@router.get(
    "/poblar/{id_corrida}",
    summary="Estado y resultado de una corrida de datos demo (el 202 del POST)",
    responses={
        404: {"description": "Corrida desconocida en esta instancia: id invalido o el proceso se "
                             "reinicio a mitad (verificar la DB antes de re-disparar)"},
    },
)
async def estado_corrida(
    request: Request,
    id_corrida: str = Path(..., pattern=r"^[0-9a-f]{12}$"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _autorizar(request, db)
    corrida = _corridas.get(id_corrida)
    if corrida is None:
        raise HTTPException(
            404,
            "Corrida desconocida en esta instancia: id invalido o el proceso se reinicio a mitad. "
            "Verificar los conteos por dia en la DB antes de re-disparar.",
        )
    return dict(corrida)
