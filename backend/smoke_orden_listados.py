# -*- coding: utf-8 -*-
"""
Smoke in-process — orden por columnas F2 (CLAUDE.md §23): bandejas de Trámites,
listado de Turnos y eventos (Entradas), más el filtro por tipo de la bandeja.

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_orden_listados.py

SOLO LOCAL: aborta si la DB no es zaris_dev. Solo lectura (no crea datos). Corre el
app FastAPI real con httpx.ASGITransport (memoria feedback_smoke_authz_asgi_in_process).
Cubre: cada columna de la lista cerrada en asc y desc → 200; el orden REAL de las
filas en las columnas comparables (fechas, días, estado, capacidad); `orden` fuera de
la lista y `dir` inválido → 422; `id_tipo_tramite` filtra; marcadores OpenAPI.
"""
import asyncio
import logging
import os
import sys
from typing import Any, Callable

import httpx

os.environ.setdefault("ENV_FILE", ".env.local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402

if "zaris_dev" not in settings.ASYNC_DATABASE_URI:
    sys.exit("ABORT: este smoke es SOLO LOCAL (la DB configurada no es zaris_dev).")

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402

logging.getLogger("httpx").setLevel(logging.WARNING)

PWD_DEV = os.environ.get("ZARIS_QA_PASS") or "123456"
ADMIN_EMAIL = "ciudadanovl@municipio.gob.ar"

ok_count = 0
fail_count = 0
fallidos: list[str] = []


def check(nombre: str, cond: bool, extra: str = "") -> bool:
    global ok_count, fail_count
    if cond:
        ok_count += 1
        print(f"  OK   {nombre} {extra}")
    else:
        fail_count += 1
        print(f"  FAIL {nombre} {extra}")
        fallidos.append(f"{nombre}: {extra}")
    return cond


def short(r: httpx.Response, n: int = 140) -> str:
    return f"{r.status_code} {r.text[:n]}"


def monotono(valores: list[Any], desc: bool) -> bool:
    """Ordenado (no estricto), con los vacíos al final en ambas direcciones."""
    llenos = [v for v in valores if v is not None]
    if valores[len(llenos):] != [None] * (len(valores) - len(llenos)):
        return False  # un vacío en el medio
    pares = zip(llenos, llenos[1:])
    return all((a >= b) if desc else (a <= b) for a, b in pares)


async def q1(sql: str, **params) -> dict | None:
    async with AsyncSessionLocal() as s:
        row = (await s.execute(text(sql), params)).mappings().first()
        return dict(row) if row else None


async def probar_columnas(c: httpx.AsyncClient, H: dict, etiqueta: str, path: str, columnas: list[str],
                          filas: Callable[[Any], list], extra: dict | None = None,
                          comparables: dict[str, Callable[[dict], Any]] | None = None) -> None:
    for col in columnas:
        for d in ("asc", "desc"):
            r = await c.get(path, params={**(extra or {}), "orden": col, "dir": d, "limit": 200}, headers=H)
            ok = r.status_code == 200
            rows = filas(r.json()) if ok else []
            detalle = f"({len(rows)} filas)"
            if ok and comparables and col in comparables and len(rows) > 1:
                vals = [comparables[col](x) for x in rows]
                ok = monotono(vals, d == "desc")
                detalle += " orden real verificado" if ok else f" DESORDENADO: {vals[:8]}"
            check(f"{etiqueta} orden={col} dir={d}", ok, detalle if r.status_code == 200 else short(r))


async def main() -> int:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://smoke.local", timeout=60) as c:
        r = await c.post("/api/v1/auth/login", json={"identificador": ADMIN_EMAIL, "password": PWD_DEV})
        if not check("0. login admin local", r.status_code == 200, short(r)):
            return 1
        H = {"Authorization": f"Bearer {r.json()['access_token']}"}

        # ── 1. Trámites: bandeja general ─────────────────────────────────────
        cols_tram = ["numero", "tipo", "estado", "iniciador", "ubicacion", "tomado", "fecha", "dias"]
        await probar_columnas(
            c, H, "1. /tramites", "/api/v1/tramites", cols_tram, lambda j: j["items"],
            comparables={"fecha": lambda x: x["fecha_alta"], "dias": lambda x: x["dias_en_estado_actual"]},
        )
        r = await c.get("/api/v1/tramites", params={"limit": 200}, headers=H)
        fechas = [x["fecha_alta"] for x in r.json()["items"]] if r.status_code == 200 else []
        check("1b. sin orden: fecha de alta, la más nueva primero", r.status_code == 200 and monotono(fechas, True),
              f"({len(fechas)} filas)")
        r = await c.get("/api/v1/tramites", params={"orden": "id_tramite; DROP TABLE x"}, headers=H)
        check("1c. orden fuera de la lista → 422", r.status_code == 422, short(r))
        r = await c.get("/api/v1/tramites", params={"orden": "fecha", "dir": "arriba"}, headers=H)
        check("1d. dir inválido → 422", r.status_code == 422, short(r))

        tipo = await q1("""
            SELECT tt.id_tipo_tramite, tt.codigo, COUNT(*) AS n
              FROM tramite t
              JOIN tipo_tramite_version ttv ON ttv.id_tipo_tramite_version = t.id_tipo_tramite_version
              JOIN tipo_tramite tt ON tt.id_tipo_tramite = ttv.id_tipo_tramite
             WHERE t.activo = TRUE AND t.id_municipio = 1
             GROUP BY tt.id_tipo_tramite, tt.codigo ORDER BY n DESC LIMIT 1
        """)
        total = await q1("SELECT COUNT(*) AS n FROM tramite WHERE activo = TRUE AND id_municipio = 1")
        if tipo and total and tipo["n"] < total["n"]:
            r = await c.get("/api/v1/tramites", params={"id_tipo_tramite": tipo["id_tipo_tramite"], "limit": 200}, headers=H)
            j = r.json() if r.status_code == 200 else {}
            check("1e. id_tipo_tramite filtra: el total es el del tipo y todas las filas son de ese tipo",
                  r.status_code == 200 and j.get("total") == tipo["n"]
                  and all(x["tipo_codigo"] == tipo["codigo"] for x in j.get("items", [])),
                  f"total={j.get('total')} esperado={tipo['n']} (de {total['n']})")
        else:
            print("       (1e salteado: hace falta más de un tipo con trámites en local)")

        # ── 2. Trámites: mi bandeja ──────────────────────────────────────────
        r = await c.get("/api/v1/tramites/mi-bandeja", params={"limit": 5}, headers=H)
        if r.status_code == 200:
            await probar_columnas(
                c, H, "2. /mi-bandeja", "/api/v1/tramites/mi-bandeja", cols_tram, lambda j: j["items"],
                comparables={"fecha": lambda x: x["fecha_alta"], "dias": lambda x: x["dias_en_estado_actual"]},
            )
            r = await c.get("/api/v1/tramites/mi-bandeja", params={"orden": "x"}, headers=H)
            check("2b. mi-bandeja: orden fuera de la lista → 422", r.status_code == 422, short(r))
        else:
            check("2. mi-bandeja accesible para el admin local (tiene agente)", False, short(r))

        # ── 3. Turnos ────────────────────────────────────────────────────────
        rank = {"reservado": 1, "llamado": 2, "cumplido": 3, "ausente": 4, "cancelado": 5}
        await probar_columnas(
            c, H, "3. /turnos", "/api/v1/turnos", ["fecha", "ciudadano", "atiende", "prestacion", "estado"],
            lambda j: j,
            comparables={"fecha": lambda x: (x["fecha"], x["hora_inicio"]), "estado": lambda x: rank.get(x["estado"])},
        )
        r = await c.get("/api/v1/turnos", params={"limit": 300}, headers=H)
        fh = [(x["fecha"], x["hora_inicio"]) for x in r.json()] if r.status_code == 200 else []
        check("3b. sin orden: la fecha más nueva primero", r.status_code == 200 and monotono([f for f, _ in fh], True),
              f"({len(fh)} filas)")
        r = await c.get("/api/v1/turnos", params={"orden": "hora_inicio"}, headers=H)
        check("3c. orden fuera de la lista → 422", r.status_code == 422, short(r))

        # ── 4. Eventos (Entradas) ────────────────────────────────────────────
        await probar_columnas(
            c, H, "4. /agenda/eventos", "/api/v1/agenda/eventos", ["fecha", "nombre", "espacio", "capacidad"],
            lambda j: j, extra={"con_espacio": "true"},
            comparables={"fecha": lambda x: (x["fecha"], x["hora_inicio"]), "capacidad": lambda x: x["capacidad_ciudadanos"]},
        )
        r = await c.get("/api/v1/agenda/eventos", params={"orden": "token_publico"}, headers=H)
        check("4b. orden fuera de la lista → 422", r.status_code == 422, short(r))

        # ── 5. Marcadores OpenAPI ────────────────────────────────────────────
        spec = (await c.get("/openapi.json")).json()

        def params_de(path: str) -> set[str]:
            return {p["name"] for p in spec["paths"].get(path, {}).get("get", {}).get("parameters", [])}

        for path in ("/api/v1/tramites", "/api/v1/tramites/mi-bandeja", "/api/v1/turnos", "/api/v1/agenda/eventos"):
            check(f"5. OpenAPI: orden + dir en GET {path}", {"orden", "dir"} <= params_de(path))
        check("5b. OpenAPI: id_tipo_tramite en GET /api/v1/tramites", "id_tipo_tramite" in params_de("/api/v1/tramites"))

    print(f"\nRESULTADO: {ok_count} OK, {fail_count} FAIL")
    for f in fallidos:
        print(f"  - {f}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
