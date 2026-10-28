# -*- coding: utf-8 -*-
"""
Smoke in-process — contorno del municipio y catálogo de gobiernos locales
(PLAN_CONTORNO_MUNICIPIO.md). Crece tarea a tarea.

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_contorno.py [prueba ...]

SOLO LOCAL. Sin argumentos corre todas las pruebas; con nombres, solo esas.
"""
import asyncio
import os
import sys

os.environ.setdefault("ENV_FILE", ".env.local")
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402

if "zaris_dev" not in settings.ASYNC_DATABASE_URI:
    sys.exit("ABORT: este smoke es SOLO LOCAL (la DB configurada no es zaris_dev).")
settings.RESEND_API_KEY = ""

from app.core.database import AsyncSessionLocal  # noqa: E402
from smoke_alta_municipio import _cliente, _municipio_c, _super_headers, _token  # noqa: E402

RES: list[tuple[str, bool, str]] = []


def check(nombre: str, ok: bool, detalle: str = "") -> None:
    RES.append((nombre, ok, detalle))
    print(f"  {'OK  ' if ok else 'FAIL'} {nombre}{(' — ' + str(detalle)) if detalle and not ok else ''}")


async def _escalar(db, sql: str, params: dict | None = None):
    return (await db.execute(text(sql), params or {})).scalar()


# ── Tarea 1: catálogo de gobiernos locales ───────────────────────────────────

async def test_catalogo_completo() -> None:
    async with AsyncSessionLocal() as db:
        n = await _escalar(db, "SELECT count(*) FROM partidos WHERE codigo_georef IS NOT NULL")
        check("2082 gobiernos locales con código", n == 2082, n)
        n = await _escalar(db, "SELECT count(*) FROM provincias WHERE codigo_georef IS NOT NULL")
        check("24 provincias con código", n == 24, n)


async def test_catalogo_codigos() -> None:
    async with AsyncSessionLocal() as db:
        for nombre, prov, codigo in (("Pergamino", "06", "060623"), ("Vicente López", "06", "060861"),
                                     ("Comuna 3", "02", "022021")):
            got = await _escalar(db, """
                SELECT pa.codigo_georef FROM partidos pa JOIN provincias pr ON pr.id_provincia = pa.id_provincia
                 WHERE pa.nombre = :n AND pr.codigo_georef = :p AND pa.activo""", {"n": nombre, "p": prov})
            check(f"{nombre} tiene el código {codigo}", got == codigo, got)
        cat = await _escalar(db, "SELECT categoria FROM partidos WHERE codigo_georef = '060623'")
        check("Pergamino trae su categoría", bool(cat), cat)


async def test_catalogo_sin_huerfanos_de_reclamos() -> None:
    async with AsyncSessionLocal() as db:
        n = await _escalar(db, """
            SELECT count(*) FROM reclamos r JOIN localidades l ON l.id_localidad = r.id_localidad
              JOIN partidos pa ON pa.id_partido = l.id_partido WHERE NOT pa.activo""")
        check("ningún reclamo queda con su localidad en un partido de baja", n == 0, n)


async def test_catalogo_bajas_sin_municipio() -> None:
    async with AsyncSessionLocal() as db:
        n = await _escalar(db, """
            SELECT count(*) FROM municipios m JOIN partidos pa ON pa.id_partido = m.id_partido
             WHERE NOT pa.activo AND m.estado <> 'baja'""")
        check("ningún municipio vigente apunta a un partido de baja", n == 0, n)


# ── Tarea 2: /geo/partidos con búsqueda ──────────────────────────────────────

async def test_geo_partidos_q() -> None:
    C = await _municipio_c()
    h = _token(C["n2"], C["id"])
    async with AsyncSessionLocal() as db:
        ba = await _escalar(db, "SELECT id_provincia FROM provincias WHERE codigo_georef = '06'")
        cba = await _escalar(db, "SELECT id_provincia FROM provincias WHERE codigo_georef = '14'")
        baja = await _escalar(db, "SELECT nombre FROM partidos WHERE NOT activo AND id_provincia = :p LIMIT 1",
                              {"p": cba})
    async with _cliente() as c:
        r = await c.get("/api/v1/geo/partidos", params={"id_provincia": ba, "q": "perga"}, headers=h)
        filas = r.json() if r.status_code == 200 else []
        check("q=perga en Buenos Aires trae solo Pergamino con su código",
              [f.get("codigo_georef") for f in filas] == ["060623"], f"{r.status_code} {str(filas)[:200]}")
        check("la fila trae categoría y nombre completo",
              bool(filas and filas[0].get("categoria") and filas[0].get("nombre_completo")), filas[:1])
        r = await c.get("/api/v1/geo/partidos", params={"id_provincia": cba, "q": "villa sarm"}, headers=h)
        nombres = [f["nombre"] for f in r.json()] if r.status_code == 200 else []
        check("q con dos palabras en Córdoba: los dos Villa Sarmiento, con nombres distintos",
              len(nombres) == 2 and len(set(nombres)) == 2, f"{r.status_code} {nombres}")
        r = await c.get("/api/v1/geo/partidos", params={"id_provincia": cba, "q": "rio cuarto"}, headers=h)
        check("sin tildes encuentra con tildes (rio cuarto → Río Cuarto)",
              r.status_code == 200 and "Río Cuarto" in [f["nombre"] for f in r.json()], r.text[:200])
        r = await c.get("/api/v1/geo/partidos", params={"id_provincia": cba, "q": baja}, headers=h)
        check("una fila de baja no se ofrece", r.status_code == 200 and baja not in [f["nombre"] for f in r.json()],
              f"{baja} {r.text[:200]}")
        r = await c.get("/api/v1/geo/partidos", params={"id_provincia": cba, "q": "a", "limit": 5}, headers=h)
        check("limit acota la respuesta", r.status_code == 200 and len(r.json()) == 5, f"{r.status_code}")
        r = await c.get("/api/v1/geo/partidos", params={"id_provincia": ba}, headers=h)
        check("sin q sigue trayendo la provincia entera", r.status_code == 200 and len(r.json()) == 135,
              f"{r.status_code} {len(r.json())}")


PRUEBAS = {f.__name__.removeprefix("test_"): f for f in (
    test_catalogo_completo, test_catalogo_codigos, test_catalogo_sin_huerfanos_de_reclamos,
    test_catalogo_bajas_sin_municipio, test_geo_partidos_q,
)}


async def main(nombres: list[str]) -> int:
    for nombre in nombres or list(PRUEBAS):
        print(f"\n[{nombre}]")
        await PRUEBAS[nombre]()
    fallas = [r for r in RES if not r[1]]
    print(f"\n{len(RES) - len(fallas)} OK / {len(fallas)} FAIL")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
