# -*- coding: utf-8 -*-
"""Smoke in-process del flujo ASINCRONO de POST /api/v1/demo/poblar (2026-09-22).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_demo_poblar.py

Corre la app FastAPI real con httpx.ASGITransport contra la DB LOCAL (.env.local,
DISPATCHER_TOKEN local). Casos: 401 sin auth, 404/422 de ids, 409 por rango y por
corrida en curso, 202 + GET con estado 'ok' y resultado, estado 'error' cuando un
generador explota, y los markers de OpenAPI.

Con ASGITransport el BackgroundTask termina ANTES de que el cliente reciba la
respuesta, asi que el GET siguiente ya ve el estado final; la latencia real del
202 se prueba con uvicorn + curl. Usa generar=false para NO insertar datos: solo
'avanzar' (envejece lo demo local, idempotente).
"""
from __future__ import annotations

import asyncio
import os
import sys

import httpx

os.environ.setdefault("ENV_FILE", ".env.local")

from app.api.routes import demo_datos as ruta  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.services import demo_datos as svc  # noqa: E402

OK = 0
FAIL = 0
BASE = "/api/v1/demo/poblar"


def check(nombre: str, cond: bool, detalle: str = "") -> None:
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  PASS  {nombre}")
    else:
        FAIL += 1
        print(f"  FAIL  {nombre}  {detalle}")


async def main() -> None:
    token = settings.DISPATCHER_TOKEN
    if not token:
        print("Falta DISPATCHER_TOKEN en .env.local")
        sys.exit(2)
    H = {"X-Dispatcher-Token": token}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        print("== auth ==")
        r = await c.post(BASE, json={"generar": False})
        check("POST sin auth -> 401", r.status_code == 401, r.text[:120])
        r = await c.get(f"{BASE}/abcdef012345")
        check("GET sin auth -> 401", r.status_code == 401, r.text[:120])

        print("== ids ==")
        r = await c.get(f"{BASE}/abcdef012345", headers=H)
        check("GET id desconocido -> 404 con aviso de reinicio",
              r.status_code == 404 and "reinicio" in r.text, f"{r.status_code} {r.text[:120]}")
        r = await c.get(f"{BASE}/NO-ES-HEX-12", headers=H)
        check("GET id con formato invalido -> 422", r.status_code == 422, str(r.status_code))

        print("== 409 ==")
        r = await c.post(BASE, json={"desde": "2026-01-01", "hasta": "2026-03-31"}, headers=H)
        check("rango > 45 dias -> 409", r.status_code == 409 and "45" in r.text, r.text[:120])
        ruta._registrar({"id_corrida": "ffffffffffff", "estado": "en_curso", "inicio": "test"})
        try:
            r = await c.post(BASE, json={"generar": False}, headers=H)
            check("otra corrida en curso -> 409 con su id",
                  r.status_code == 409 and "ffffffffffff" in r.text, f"{r.status_code} {r.text[:160]}")
        finally:
            ruta._corridas.pop("ffffffffffff", None)

        print("== flujo feliz (generar=false, avanzar=true) ==")
        r = await c.post(BASE, json={"generar": False, "avanzar": True,
                                     "modulos": ["reclamos", "atencion"]}, headers=H)
        check("POST valido -> 202", r.status_code == 202, f"{r.status_code} {r.text[:200]}")
        j = r.json() if r.status_code == 202 else {}
        idc = j.get("id_corrida", "")
        check("202 trae id_corrida (12 hex), estado en_curso y consulta",
              len(idc) == 12 and j.get("estado") == "en_curso"
              and j.get("consulta") == f"{BASE}/{idc}" and j.get("ejecutado_por") == "dispatcher",
              str(j)[:200])
        r = await c.get(f"{BASE}/{idc}", headers=H)
        j = r.json()
        check("GET corrida -> 200 con estado ok", r.status_code == 200 and j.get("estado") == "ok",
              f"{r.status_code} estado={j.get('estado')} error={j.get('error')}")
        res = j.get("resultado") or {}
        check("resultado con avanzado + avanzado_atencion y sin generado/generado_atencion",
              "avanzado" in res and "avanzado_atencion" in res
              and "generado" not in res and "generado_atencion" not in res, str(sorted(res)))
        check("fin y duracion_s registrados", bool(j.get("fin")) and isinstance(j.get("duracion_s"), int),
              f"fin={j.get('fin')} dur={j.get('duracion_s')}")

        print("== generador roto -> estado error ==")
        original = svc.avanzar_pendientes

        async def boom(*_a, **_k):
            raise RuntimeError("falla simulada del generador")

        svc.avanzar_pendientes = boom
        try:
            r = await c.post(BASE, json={"generar": False, "modulos": ["reclamos"]}, headers=H)
            check("POST con generador roto igual responde 202", r.status_code == 202, str(r.status_code))
            idc2 = r.json().get("id_corrida", "") if r.status_code == 202 else ""
            r = await c.get(f"{BASE}/{idc2}", headers=H)
            j = r.json()
            check("GET -> estado error con el detalle de la excepcion",
                  j.get("estado") == "error" and "falla simulada" in (j.get("error") or ""), str(j)[:200])
        finally:
            svc.avanzar_pendientes = original

        print("== openapi ==")
        spec = app.openapi()
        check("OpenAPI expone GET /api/v1/demo/poblar/{id_corrida}",
              f"{BASE}/{{id_corrida}}" in spec["paths"])
        check("OpenAPI: POST /demo/poblar documenta 202",
              "202" in spec["paths"][BASE]["post"]["responses"])

    print(f"\n{OK} OK / {FAIL} FAIL")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())
