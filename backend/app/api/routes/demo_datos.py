# -*- coding: utf-8 -*-
"""Poblado periodico de datos demo para los tableros BI (municipio San Andres).

POST /api/v1/demo/poblar — encola la generacion de reclamos/historial/OT/encuestas
demo (y, desde 2026-09-19, turnos/colero/Guardia/eventos demo via
demo_atencion.py; desde 2026-10-21, expedientes via demo_tramites.py) en un
rango y/o el avance del ciclo de vida de los pendientes demo existentes. Lo
llama el cron DIARIO de GitHub Actions (.github/workflows/demo-datos.yml) y
sirve para la carga inicial por meses.

Desde 2026-10-21 (pedido de Cesar):
  - cierres SLA-aware (cada mes 60-85 % dentro del SLA, app/services/demo_sla.py);
  - reclamos y tramites IDEMPOTENTES POR DIA (un dia ya generado se saltea), asi
    que el rango por defecto son los 7 dias COMPLETOS hasta ayer: el cron diario
    agrega ayer y recupera los dias que se haya salteado, sin duplicar;
  - `modo = 'cerrar_atraso'`: cierra de forma plausible lo viejo que quedo abierto
    (reclamos, tramites y eventos de emergencia de mas de `dias_atraso` dias, con
    sus OT) — por default en DRY-RUN (`aplicar=false` devuelve los conteos de lo
    que tocaria); `incluir_no_demo` suma los datos de QA/seed que no son del
    generador.

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
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.services import demo_atencion, demo_datos, demo_tramites
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
    # Que generar/avanzar: 'reclamos' = demo_datos.py, 'atencion' = demo_atencion.py
    # (turnos + colero + Guardia + eventos, 2026-09-19), 'tramites' = demo_tramites.py
    # (expedientes, 2026-10-21). En modo cerrar_atraso, 'atencion' = eventos de Emergencias.
    modulos: list[Literal["reclamos", "atencion", "tramites"]] = ["reclamos", "atencion", "tramites"]
    # Atencion: dias hacia adelante con turnos/eventos reservados (Mesa del dia, colero).
    dias_futuro: int = Field(7, ge=0, le=30)
    # Tramites: banda del volumen mensual de expedientes.
    tramites_min_mensual: int = Field(60, ge=1, le=600)
    tramites_max_mensual: int = Field(120, ge=1, le=600)
    # 'poblar' (generar + avanzar) | 'cerrar_atraso' (cierra lo viejo abierto; ignora desde/hasta).
    modo: Literal["poblar", "cerrar_atraso"] = "poblar"
    # cerrar_atraso: False = dry-run (solo conteos). True = escribe.
    aplicar: bool = False
    dias_atraso: int = Field(21, ge=7, le=365)
    # cerrar_atraso: incluir los datos que NO son del generador (QA, seed_tramites.py).
    incluir_no_demo: bool = False
    # cerrar_atraso: OT operativa para los reclamos demo ya cerrados que no la tienen.
    completar_ot: bool = True
    # cerrar_atraso (OPT-IN, decision de Cesar): llevar los meses viejos de reclamos demo
    # que quedaron por debajo del 60 % dentro del SLA a su objetivo, adelantando cierres.
    rebalancear_sla: bool = False


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
        # El JWT pasa por el guard central (IT-01 F3b): scope, cuenta activa, municipio, segundo
        # factor y revocación, igual que en cualquier otro endpoint. Nada de decodificarlo acá.
        try:
            usuario = await get_current_user(
                request, HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:]), db)
        except HTTPException:
            usuario = None
        if usuario is not None:
            # Solo un administrador del municipio demo (IT-01): el generador escribe ahi.
            id_demo = await db.scalar(text(
                "SELECT id_municipio FROM municipios WHERE direccion_base AND activo"))
            if (not usuario["es_super_admin"] and usuario["nivel_real"] == 1
                    and usuario["id_municipio"] == id_demo):
                return f"admin:{usuario['id_usuario']}"

    logger.warning("demo/poblar: acceso no autorizado desde IP %s", get_real_ip(request))
    raise HTTPException(401, "No autorizado")


async def _correr_poblar(db: AsyncSession, body: PoblarIn, desde: date, hasta: date,
                         modulos: set[str], resultado: dict) -> None:
    """Generar [desde, hasta] y avanzar lo pendiente. Cada servicio commitea su paso:
    `resultado` va guardando lo ya aplicado (si un paso falla queda el parcial)."""
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
    if body.generar and "tramites" in modulos:
        resultado["generado_tramites"] = await demo_tramites.generar_periodo_tramites(
            db, desde, hasta, min_mensual=body.tramites_min_mensual,
            max_mensual=body.tramites_max_mensual, semilla=body.semilla,
        )
    if body.avanzar and "reclamos" in modulos:
        resultado["avanzado"] = await demo_datos.avanzar_pendientes(db, semilla=body.semilla)
    if body.avanzar and "atencion" in modulos:
        resultado["avanzado_atencion"] = await demo_atencion.avanzar_pendientes_atencion(
            db, semilla=body.semilla)
    if body.avanzar and "tramites" in modulos:
        resultado["avanzado_tramites"] = await demo_tramites.avanzar_pendientes_tramites(
            db, semilla=body.semilla)


async def _correr_atraso(db: AsyncSession, body: PoblarIn, modulos: set[str], resultado: dict) -> None:
    """Cierre del atraso (dry-run salvo body.aplicar). Tramites y emergencias primero;
    los reclamos al final (su paso completa ademas las OT historicas, el mas pesado)."""
    resultado["aplicado"] = body.aplicar
    if "tramites" in modulos:
        resultado["atraso_tramites"] = await demo_tramites.cerrar_atraso_tramites(
            db, dias=body.dias_atraso, aplicar=body.aplicar,
            incluir_no_demo=body.incluir_no_demo, semilla=body.semilla)
    if "atencion" in modulos:
        resultado["atraso_emergencias"] = await demo_atencion.cerrar_atraso_emergencias(
            db, dias=body.dias_atraso, aplicar=body.aplicar, incluir_no_demo=body.incluir_no_demo)
    if "reclamos" in modulos:
        resultado["atraso_reclamos"] = await demo_datos.cerrar_atraso_reclamos(
            db, dias=body.dias_atraso, aplicar=body.aplicar,
            incluir_no_demo=body.incluir_no_demo, completar_ot=body.completar_ot,
            rebalancear_sla=body.rebalancear_sla, semilla=body.semilla)


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
            if body.modo == "cerrar_atraso":
                await _correr_atraso(db, body, modulos, resultado)
            else:
                await _correr_poblar(db, body, desde, hasta, modulos, resultado)
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
    summary="Encola la generacion/avance de datos demo para los tableros BI (reclamos + atencion + tramites)",
    description=(
        "Cron diario o carga inicial. Valida y encola la corrida; responde 202 con `id_corrida` "
        "y el resultado se consulta en GET /api/v1/demo/poblar/{id_corrida}. "
        "Sin desde/hasta: los 7 dias COMPLETOS hasta ayer (los dias ya generados se saltean). "
        "`modo='cerrar_atraso'` cierra lo viejo abierto (dry-run salvo `aplicar=true`). "
        "Auth: X-Dispatcher-Token o JWT admin."
    ),
    responses={
        202: {"description": "Corrida encolada (id_corrida, estado='en_curso', consulta). "
                             "Desde la mig 112 el generador sortea auditorías posteriores al cierre "
                             "(En auditoría / Auditado + retrabajos) y las envejece en 'avanzar'. "
                             "Desde 2026-10-21: cierres SLA-aware (60-85 % dentro del SLA por mes), "
                             "OT operativas, modulo 'tramites' y modo 'cerrar_atraso'."},
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

    # Default: los 7 dias COMPLETOS hasta ayer. Reclamos y tramites saltean los dias ya
    # generados, asi que el cron diario agrega ayer (y recupera los que se haya salteado)
    # sin duplicar. Un rango que incluye hoy genera solo hasta "ahora" y ese dia queda
    # marcado como generado (parcial).
    hoy = date.today()
    desde = body.desde or (hoy - timedelta(days=7))
    hasta = body.hasta or (hoy - timedelta(days=1))
    if body.modo == "poblar":
        if desde > hasta or (hasta - desde).days > 45:
            raise HTTPException(409, "Rango invalido: desde <= hasta y maximo 45 dias por llamada")
        if body.min_mensual > body.max_mensual or body.tramites_min_mensual > body.tramites_max_mensual:
            raise HTTPException(409, "min_mensual no puede superar a max_mensual")

    modulos = set(body.modulos or ["reclamos", "atencion", "tramites"])

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
        "modo": body.modo,
        "desde": str(desde) if body.modo == "poblar" else None,
        "hasta": str(hasta) if body.modo == "poblar" else None,
        "modulos": sorted(modulos),
        "generar": body.generar,
        "avanzar": body.avanzar,
        "aplicar": body.aplicar if body.modo == "cerrar_atraso" else None,
        "consulta": f"/api/v1/demo/poblar/{id_corrida}",
        "resultado": None,
        "error": None,
    }
    _registrar(corrida)
    background_tasks.add_task(_ejecutar_corrida, id_corrida, body, desde, hasta, modulos)
    logger.info("demo/poblar encolada (%s): corrida %s modo=%s %s..%s modulos=%s generar=%s avanzar=%s aplicar=%s",
                quien, id_corrida, body.modo, desde, hasta, sorted(modulos), body.generar, body.avanzar,
                body.aplicar)
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
