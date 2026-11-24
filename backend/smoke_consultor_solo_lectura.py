# -*- coding: utf-8 -*-
"""
Smoke in-process — el Consultor (nivel 5) es de solo lectura también en el padrón y en Encuestas.

Las altas, cambios y bajas de ciudadanos y empresas pedían solo sesión; el disparo y la lista de
envíos de encuestas (que trae el enlace personal de cada vecino), también.

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_consultor_solo_lectura.py

SOLO LOCAL. Da de baja y repone un vecino de prueba (`@registro-previo.test`); lo demás usa ids
inexistentes: a un nivel 1 a 4 le responde 404 o 422, nunca 403.
"""
import asyncio
import os
import sys

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
settings.RESEND_API_KEY = ""

from app.core.auth import create_access_token  # noqa: E402
from app.core.sistema import SesionSistema  # noqa: E402
from app.main import app  # noqa: E402

RES: list[bool] = []
NO_EXISTE = 2_000_000_000


def check(nombre: str, ok: bool, detalle: str = "") -> None:
    RES.append(ok)
    print(f"  {'OK  ' if ok else 'FAIL'} {nombre}{(' — ' + detalle) if detalle and not ok else ''}")


# (método, ruta, cuerpo) de cada mutación del padrón.
PADRON = [
    ("POST", "/ciudadanos", {}),
    ("PUT", f"/ciudadanos/{NO_EXISTE}", {}),
    ("PUT", f"/ciudadanos/{NO_EXISTE}/estado?activo=false", None),
    ("POST", f"/ciudadanos/{NO_EXISTE}/cuenta-vecino", None),
    ("POST", "/empresas", {}),
    ("PUT", f"/empresas/{NO_EXISTE}", {}),
    ("PUT", f"/empresas/{NO_EXISTE}/estado?activo=false", None),
    ("POST", "/ciudadano-empresa", {}),
]
ENCUESTAS = [
    ("POST", "/disparar", {"id_reclamo": NO_EXISTE}),
    ("GET", "/envios", None),
    ("GET", f"/envios/{NO_EXISTE}", None),
]


async def main() -> int:
    async with SesionSistema() as db:
        async def uno(nivel: int) -> str:
            idu = await db.scalar(text(
                "SELECT id_usuario FROM usuarios WHERE id_municipio = 1 AND nivel_acceso = :n AND activo "
                "AND NOT COALESCE(debe_cambiar_password, FALSE) ORDER BY id_usuario LIMIT 1"), {"n": nivel})
            if not idu:
                sys.exit(f"Falta una cuenta de nivel {nivel} en zaris_dev.")
            return create_access_token({"sub": str(idu), "mun": 1, "sf": True})
        tok = {n: await uno(n) for n in (2, 3, 4, 5)}
        vecino = (await db.execute(text(
            "SELECT id_ciudadano, activo FROM ciudadanos WHERE id_municipio = 1 AND email LIKE '%@registro-previo.test' "
            "ORDER BY id_ciudadano LIMIT 1"))).first()
        if not vecino:
            sys.exit("Falta el vecino de prueba (correr antes smoke_registro_previo.py).")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=60) as c:
        async def pedir(nivel: int, metodo: str, url: str, cuerpo) -> httpx.Response:
            return await c.request(metodo, url, json=cuerpo, headers={"Authorization": f"Bearer {tok[nivel]}"})

        print("1. Padrón: el Consultor no escribe, el nivel 4 sí")
        for metodo, ruta, cuerpo in PADRON:
            r = await pedir(5, metodo, "/api/v1/buc" + ruta, cuerpo)
            check(f"Consultor {metodo} {ruta.split('?')[0]} → 403",
                  r.status_code == 403 and "solo lectura" in r.text, f"{r.status_code} {r.text[:120]}")
            r = await pedir(4, metodo, "/api/v1/buc" + ruta, cuerpo)
            check(f"Nivel 4   {metodo} {ruta.split('?')[0]} → 404/422", r.status_code in (404, 422),
                  f"{r.status_code} {r.text[:120]}")

        print("2. Padrón: un vecino real")
        url = f"/api/v1/buc/ciudadanos/{vecino.id_ciudadano}/estado"
        r = await pedir(5, "PUT", f"{url}?activo={'false' if vecino.activo else 'true'}", None)
        async with SesionSistema() as db:
            ahora = await db.scalar(text("SELECT activo FROM ciudadanos WHERE id_ciudadano = :i"),
                                    {"i": vecino.id_ciudadano})
            check("el Consultor no cambió su estado", r.status_code == 403 and ahora == vecino.activo,
                  f"{r.status_code} activo={ahora}")
            await db.execute(text("UPDATE ciudadanos SET activo = :a WHERE id_ciudadano = :i"),
                             {"a": vecino.activo, "i": vecino.id_ciudadano})
            await db.commit()

        print("3. Padrón: el Consultor sigue leyendo")
        for ruta in ("/ciudadanos?limit=1", "/empresas?limit=1", "/ciudadanos/buscar?q=registro"):
            r = await pedir(5, "GET", "/api/v1/buc" + ruta, None)
            check(f"Consultor GET {ruta} → 200", r.status_code == 200, f"{r.status_code}")

        print("4. Encuestas: disparo y envíos, solo niveles 1 y 2")
        for metodo, ruta, cuerpo in ENCUESTAS:
            for nivel in (3, 4, 5):
                r = await pedir(nivel, metodo, "/api/v1/admin/encuestas" + ruta, cuerpo)
                check(f"Nivel {nivel} {metodo} {ruta} → 403", r.status_code == 403, f"{r.status_code}")
            r = await pedir(2, metodo, "/api/v1/admin/encuestas" + ruta, cuerpo)
            check(f"Nivel 2 {metodo} {ruta} pasa el control", r.status_code in (200, 404, 422), f"{r.status_code}")

    print(f"\n{sum(RES)} OK · {len(RES) - sum(RES)} FAIL")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
