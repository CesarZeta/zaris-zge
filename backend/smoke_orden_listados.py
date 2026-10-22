# -*- coding: utf-8 -*-
"""
Smoke in-process — orden por columnas F2 + F3 (CLAUDE.md §23): bandejas de Trámites,
listado de Turnos y eventos (Entradas/Agenda), más el filtro por tipo de la bandeja;
F3 suma el padrón de ciudadanos y empresas (texto, fechas, orden y paginado en el SQL)
y los envíos de encuestas (orden + filtro por tipo de trámites).

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

        # ── 4. Eventos (Entradas + Agenda → Eventos, F3 suma horario y estado) ─
        await probar_columnas(
            c, H, "4. /agenda/eventos", "/api/v1/agenda/eventos",
            ["fecha", "horario", "nombre", "espacio", "capacidad", "estado"],
            lambda j: j, extra={"con_espacio": "true"},
            comparables={"fecha": lambda x: (x["fecha"], x["hora_inicio"]),
                         "horario": lambda x: (x["hora_inicio"], x["hora_fin"]),
                         "capacidad": lambda x: x["capacidad_ciudadanos"]},
        )
        r = await c.get("/api/v1/agenda/eventos", params={"orden": "token_publico"}, headers=H)
        check("4b. orden fuera de la lista → 422", r.status_code == 422, short(r))

        # ── 6. F3: padrón de ciudadanos (texto, fechas, orden y paginado en el SQL) ─
        P_CIU = "/api/v1/buc/ciudadanos"
        base_ciu = {"solo_activos": "false"}
        await probar_columnas(
            c, H, "6. /buc/ciudadanos", P_CIU, ["nombre", "documento", "cuil", "email", "estado", "alta"],
            lambda j: j, extra=base_ciu,
            comparables={"alta": lambda x: x["fecha_alta"], "estado": lambda x: x["activo"],
                         "cuil": lambda x: x["cuil"], "documento": lambda x: x["doc_nro"].rjust(12, "0")},
        )
        n_ciu = await q1("SELECT COUNT(*) AS n FROM ciudadanos")
        r = await c.get(P_CIU, params={**base_ciu, "limit": 50}, headers=H)
        ids = [x["id_ciudadano"] for x in r.json()] if r.status_code == 200 else []
        check("6b. sin orden: el más reciente primero + X-Total-Count = total de la tabla",
              r.status_code == 200 and monotono(ids, True) and r.headers.get("x-total-count") == str(n_ciu["n"]),
              f"total={r.headers.get('x-total-count')} esperado={n_ciu['n']}")
        r1 = await c.get(P_CIU, params={**base_ciu, "orden": "alta", "limit": 20, "offset": 0}, headers=H)
        r2 = await c.get(P_CIU, params={**base_ciu, "orden": "alta", "limit": 20, "offset": 20}, headers=H)
        p1 = {x["id_ciudadano"] for x in r1.json()} if r1.status_code == 200 else set()
        p2 = {x["id_ciudadano"] for x in r2.json()} if r2.status_code == 200 else set()
        check("6c. paginado: la página 2 no repite filas de la 1", len(p1) == 20 and len(p2) > 0 and not (p1 & p2),
              f"p1={len(p1)} p2={len(p2)} repetidas={len(p1 & p2)}")

        muestra = await q1("""SELECT apellido, nombre, fecha_alta::date AS dia FROM ciudadanos
                               WHERE length(apellido) >= 4 AND apellido !~ '[%_ ]'
                                 AND length(nombre) >= 3 AND nombre !~ '[%_]'
                               ORDER BY id_ciudadano DESC LIMIT 1""")
        if muestra:
            tok = muestra["apellido"][:4]
            esperado = await q1("""SELECT COUNT(*) AS n FROM ciudadanos
                                    WHERE apellido ILIKE :t OR nombre ILIKE :t OR email ILIKE :t
                                       OR doc_nro ILIKE :t OR cuil ILIKE :t""", t=f"%{tok}%")
            r = await c.get(P_CIU, params={**base_ciu, "q": tok, "limit": 1000}, headers=H)
            filas_q = r.json() if r.status_code == 200 else []
            campos = ("apellido", "nombre", "email", "doc_nro", "cuil")
            check("6d. q filtra en el SQL: total = el de la DB y toda fila contiene el texto",
                  r.status_code == 200 and r.headers.get("x-total-count") == str(esperado["n"])
                  and all(any(tok.lower() in (x.get(k) or "").lower() for k in campos) for x in filas_q),
                  f"q={tok!r} total={r.headers.get('x-total-count')} esperado={esperado['n']}")
            primer_nombre = muestra["nombre"].split()[0]
            r = await c.get(P_CIU, params={**base_ciu, "q": f"{muestra['apellido']} {primer_nombre}", "limit": 1000}, headers=H)
            filas_q = r.json() if r.status_code == 200 else []
            toks = [muestra["apellido"].lower(), primer_nombre.lower()]
            check("6e. q con dos palabras = AND (cada una en algún campo)",
                  r.status_code == 200 and len(filas_q) >= 1
                  and all(all(any(t in (x.get(k) or "").lower() for k in campos) for t in toks) for x in filas_q),
                  f"({len(filas_q)} filas)")
            dia = muestra["dia"].isoformat()
            esperado = await q1("SELECT COUNT(*) AS n FROM ciudadanos WHERE fecha_alta::date = :d", d=muestra["dia"])
            r = await c.get(P_CIU, params={**base_ciu, "desde": dia, "hasta": dia, "limit": 1000}, headers=H)
            filas_d = r.json() if r.status_code == 200 else []
            check("6f. desde/hasta (mismo día): solo altas de ese día, total = el de la DB",
                  r.status_code == 200 and r.headers.get("x-total-count") == str(esperado["n"])
                  and all(x["fecha_alta"][:10] == dia for x in filas_d),
                  f"día={dia} total={r.headers.get('x-total-count')} esperado={esperado['n']}")
        else:
            print("       (6d-6f salteados: no hay ciudadanos de muestra en local)")
        r = await c.get(P_CIU, params={"orden": "id_ciudadano; DROP TABLE x"}, headers=H)
        check("6g. orden fuera de la lista → 422", r.status_code == 422, short(r))
        r = await c.get(P_CIU, params={"orden": "alta", "dir": "arriba"}, headers=H)
        check("6h. dir inválido → 422", r.status_code == 422, short(r))

        # ── 7. F3: padrón de empresas ────────────────────────────────────────
        P_EMP = "/api/v1/buc/empresas"
        await probar_columnas(
            c, H, "7. /buc/empresas", P_EMP, ["nombre", "cuit", "localidad", "provincia", "estado", "alta"],
            lambda j: j, extra=base_ciu,
            comparables={"alta": lambda x: x["fecha_alta"], "estado": lambda x: x["activo"]},
        )
        emp = await q1("SELECT id_empresa, cuit FROM empresas WHERE cuit ~ '-' ORDER BY id_empresa DESC LIMIT 1")
        if emp:
            digitos = "".join(ch for ch in emp["cuit"] if ch.isdigit())
            r = await c.get(P_EMP, params={**base_ciu, "q": digitos, "limit": 1000}, headers=H)
            ids_e = [x["id_empresa"] for x in r.json()] if r.status_code == 200 else []
            check("7b. q con el CUIT sin guiones encuentra la empresa", emp["id_empresa"] in ids_e,
                  f"cuit={emp['cuit']} ({len(ids_e)} filas)")
        else:
            print("       (7b salteado: no hay empresas con CUIT con guiones en local)")
        r = await c.get(P_EMP, params={"orden": "id_actividad"}, headers=H)
        check("7c. orden fuera de la lista → 422", r.status_code == 422, short(r))

        # ── 8. F3: envíos de encuestas ───────────────────────────────────────
        P_ENV = "/api/v1/admin/encuestas/envios"
        await probar_columnas(
            c, H, "8. /encuestas/envios", P_ENV,
            ["envio", "tipo", "referencia", "email", "estado", "enviada", "completada", "vence"],
            lambda j: j,
            comparables={"envio": lambda x: x["id_encuesta_envio"], "enviada": lambda x: x["fecha_envio"],
                         "completada": lambda x: x["fecha_completada"], "vence": lambda x: x["fecha_expiracion"],
                         "estado": lambda x: x["estado"]},
        )
        n_tram = await q1("""SELECT COUNT(*) AS n FROM encuesta_envio ee
                              JOIN encuesta_plantilla pl ON pl.id_encuesta_plantilla = ee.id_plantilla
                             WHERE ee.activo AND pl.tipo = 'tramites'
                               AND (ee.id_municipio = 1 OR ee.id_municipio IS NULL)""")
        r = await c.get(P_ENV, params={"tipo": "tramites", "limit": 200}, headers=H)
        filas_t = r.json() if r.status_code == 200 else []
        check("8b. tipo=tramites filtra (el filtro nuevo del front) y X-Total-Count = el de la DB",
              r.status_code == 200 and r.headers.get("x-total-count") == str(n_tram["n"])
              and all(x["tipo"] == "tramites" for x in filas_t),
              f"total={r.headers.get('x-total-count')} esperado={n_tram['n']}")
        r = await c.get(P_ENV, params={"orden": "token_unico"}, headers=H)
        check("8c. orden fuera de la lista → 422", r.status_code == 422, short(r))

        # ── 5. Marcadores OpenAPI ────────────────────────────────────────────
        spec = (await c.get("/openapi.json")).json()

        def params_de(path: str) -> set[str]:
            return {p["name"] for p in spec["paths"].get(path, {}).get("get", {}).get("parameters", [])}

        for path in ("/api/v1/tramites", "/api/v1/tramites/mi-bandeja", "/api/v1/turnos", "/api/v1/agenda/eventos",
                     "/api/v1/admin/encuestas/envios"):
            check(f"5. OpenAPI: orden + dir en GET {path}", {"orden", "dir"} <= params_de(path))
        check("5b. OpenAPI: id_tipo_tramite en GET /api/v1/tramites", "id_tipo_tramite" in params_de("/api/v1/tramites"))
        for path in ("/api/v1/buc/ciudadanos", "/api/v1/buc/empresas"):
            check(f"5c. OpenAPI: q + desde + hasta + orden + dir en GET {path}",
                  {"q", "desde", "hasta", "orden", "dir"} <= params_de(path))

    print(f"\nRESULTADO: {ok_count} OK, {fail_count} FAIL")
    for f in fallidos:
        print(f"  - {f}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
