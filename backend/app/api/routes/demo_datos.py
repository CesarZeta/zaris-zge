# -*- coding: utf-8 -*-
"""Poblado periodico de datos demo para los tableros BI (municipio San Andres).

POST /api/v1/demo/poblar — genera reclamos/historial/encuestas demo en un rango
y/o avanza el ciclo de vida de los pendientes demo existentes (servicio
app/services/demo_datos.py). Lo llama el cron semanal de GitHub Actions
(.github/workflows/demo-datos.yml) y sirve para la carga inicial por meses.

Auth dual (a diferencia de los otros mantenimientos, tambien lo dispara un
humano para la carga inicial):
  - header X-Dispatcher-Token == settings.DISPATCHER_TOKEN (maquina), o
  - JWT de agente con nivel_acceso 1 (admin).
"""
from __future__ import annotations

import logging
import secrets as stdlib_secrets
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import ALGORITHM
from app.core.config import settings
from app.core.database import get_db
from app.services import demo_datos
from app.utils.request_helpers import get_real_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/demo", tags=["demo-datos"])


class PoblarIn(BaseModel):
    desde: date | None = None
    hasta: date | None = None
    min_mensual: int = Field(300, ge=1, le=1500)
    max_mensual: int = Field(500, ge=1, le=1500)
    vecinos_nuevos: int = Field(250, ge=0, le=1000)
    generar: bool = True
    avanzar: bool = True
    semilla: int | None = None


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


@router.post(
    "/poblar",
    summary="Genera/avanza datos demo para los tableros BI",
    description="Cron semanal o carga inicial. Auth: X-Dispatcher-Token o JWT admin.",
    responses={409: {"description": "Rango invalido (desde > hasta o mayor a 45 dias)"}},
)
async def poblar_demo(
    request: Request,
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

    resultado: dict = {"ejecutado_por": quien, "desde": str(desde), "hasta": str(hasta)}
    if body.generar:
        resultado["generado"] = await demo_datos.generar_periodo(
            db, desde, hasta,
            min_mensual=body.min_mensual, max_mensual=body.max_mensual,
            vecinos_nuevos=body.vecinos_nuevos, semilla=body.semilla,
        )
    if body.avanzar:
        resultado["avanzado"] = await demo_datos.avanzar_pendientes(db, semilla=body.semilla)

    logger.info("demo/poblar OK (%s): %s", quien, {k: v for k, v in resultado.items() if k != "ejecutado_por"})
    return resultado
