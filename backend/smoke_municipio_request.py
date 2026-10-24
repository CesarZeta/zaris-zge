# -*- coding: utf-8 -*-
"""
Smoke in-process — municipio de la request (IT-01 F2, Tarea 6): claim `mun` en el JWT, municipio
por origen (subdominio) y configuración por municipio.

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_municipio_request.py

SOLO LOCAL. Requiere el municipio de aislamiento (seed_municipio_aislamiento.py). Mail en MOCK.
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

import httpx

os.environ.setdefault("ENV_FILE", ".env.local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from jose import jwt  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402

if "zaris_dev" not in settings.ASYNC_DATABASE_URI:
    sys.exit("ABORT: este smoke es SOLO LOCAL (la DB configurada no es zaris_dev).")
settings.RESEND_API_KEY = ""

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402

ORIGEN_B_ZGE = "https://aislamiento.zge.zaris.com.ar"
ORIGEN_B_VECINOS = "https://aislamiento.vecinos.zaris.com.ar"
ORIGEN_BASE = "https://zge.zaris.com.ar"
CLAVE = "123456"
RES: list[tuple[str, bool, str]] = []


def check(nombre: str, ok: bool, detalle: str = "") -> None:
    RES.append((nombre, ok, detalle))
    print(f"  {'OK  ' if ok else 'FAIL'} {nombre}{(' — ' + detalle) if detalle and not ok else ''}")


def mun_de(token: str):
    return jwt.get_unverified_claims(token).get("mun")


async def login(c: httpx.AsyncClient, ident: str, origen: str | None = None) -> httpx.Response:
    h = {"Origin": origen} if origen else {}
    return await c.post("/api/v1/auth/login", json={"identificador": ident, "password": CLAVE}, headers=h)


async def main() -> int:
    async with AsyncSessionLocal() as db:
        B = (await db.execute(text("SELECT id_municipio FROM municipios WHERE subdominio = 'aislamiento'"))).scalar()
        admin_1 = (await db.execute(text(
            "SELECT id_usuario FROM usuarios WHERE id_municipio = 1 AND nivel_acceso = 1 AND activo "
            "ORDER BY id_usuario LIMIT 1"))).scalar()
    if B is None:
        sys.exit("Falta el municipio de aislamiento: correr seed_municipio_aislamiento.py")
    print(f"Municipio de aislamiento: {B}")

    # 1. subdominio_de_origen (función pura)
    print("\n1. subdominio_de_origen")
    try:
        from app.core.municipio import subdominio_de_origen
        casos = {
            "https://aislamiento.zge.zaris.com.ar": "aislamiento",
            "https://AISLAMIENTO.vecinos.zaris.com.ar": "aislamiento",
            "https://vicente-lopez.agentes.zaris.com.ar": "vicente-lopez",
            "https://zge.zaris.com.ar": None,
            "https://cesarzeta.github.io": None,
            "http://localhost:8080": None,
            None: None,
            "basura": None,
            "https://x.zge.zaris.com.ar.evil.com": None,
        }
        for origen, esperado in casos.items():
            got = subdominio_de_origen(origen)
            check(f"subdominio_de_origen({origen!r}) == {esperado!r}", got == esperado, f"devolvió {got!r}")
    except ImportError as exc:
        check("app.core.municipio existe", False, str(exc))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        # 2. token sin claim mun → 401 con mensaje de sesión vencida
        print("\n2. token sin `mun`")
        viejo = jwt.encode({"sub": str(admin_1), "scope": "agente",
                            "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                           settings.SECRET_KEY, algorithm="HS256")
        r = await c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {viejo}"})
        check("token sin mun → 401", r.status_code == 401, f"{r.status_code}")
        check("detail de sesión vencida", r.status_code == 401 and r.json().get("detail") == "Sesión vencida. Volvé a ingresar.",
              r.text[:120])

        # 3. mismo email en dos municipios: el origen decide la cuenta
        print("\n3. login con el mismo email en dos municipios")
        r1 = await login(c, "doble@aislamiento.test")
        check("login doble sin Origin → 200", r1.status_code == 200, f"{r1.status_code} {r1.text[:120]}")
        if r1.status_code == 200:
            t1 = r1.json()["access_token"]
            check("token sin Origin con mun = 1", mun_de(t1) == 1, f"mun={mun_de(t1)}")
            me = await c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t1}"})
            check("/me del municipio 1 → id_municipio 1", me.status_code == 200 and me.json().get("id_municipio") == 1,
                  f"{me.status_code} {me.text[:120]}")
        r2 = await login(c, "doble@aislamiento.test", ORIGEN_B_ZGE)
        check("login doble con Origin de B → 200", r2.status_code == 200, f"{r2.status_code} {r2.text[:120]}")
        if r2.status_code == 200:
            t2 = r2.json()["access_token"]
            check("token con Origin de B con mun = B", mun_de(t2) == B, f"mun={mun_de(t2)}")
            me = await c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t2}", "Origin": ORIGEN_B_ZGE})
            check("/me de B → id_municipio B", me.status_code == 200 and me.json().get("id_municipio") == B,
                  f"{me.status_code} {me.text[:120]}")

        # 4. token de B usado desde el origen base
        print("\n4. token de B con otro origen")
        r = await login(c, "admin.b@aislamiento.test", ORIGEN_B_ZGE)
        check("login admin.b con Origin de B → 200", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
        if r.status_code == 200:
            tb = r.json()["access_token"]
            me = await c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tb}", "Origin": ORIGEN_BASE})
            check("token de B con Origin base → 401", me.status_code == 401, f"{me.status_code}")
            me = await c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tb}"})
            check("token de B sin Origin → 200", me.status_code == 200, f"{me.status_code}")
        r = await login(c, "admin.b@aislamiento.test")
        check("login admin.b sin Origin (municipio base) → 401", r.status_code == 401, f"{r.status_code}")

        # 5. subdominio desconocido
        print("\n5. subdominio desconocido")
        r = await login(c, "doble@aislamiento.test", "https://noexiste.zge.zaris.com.ar")
        check("login con subdominio inexistente → 404", r.status_code == 404, f"{r.status_code}")
        check("detail 'Municipio no encontrado'", r.status_code == 404 and r.json().get("detail") == "Municipio no encontrado",
              r.text[:120])

        # 6. vecino: el DNI se busca en el municipio del origen
        print("\n6. vecino")
        body = {"dni": "97000001", "password": CLAVE}
        r = await c.post("/api/v1/publico/auth/login", json=body)
        check("vecino de B sin Origin → 401", r.status_code == 401, f"{r.status_code}")
        r = await c.post("/api/v1/publico/auth/login", json=body, headers={"Origin": ORIGEN_B_VECINOS})
        check("vecino de B con Origin de B → 200", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
        if r.status_code == 200:
            tv = r.json()["access_token"]
            check("token del vecino con mun = B", mun_de(tv) == B, f"mun={mun_de(tv)}")
            me = await c.get("/api/v1/publico/auth/me", headers={"Authorization": f"Bearer {tv}", "Origin": ORIGEN_B_VECINOS})
            check("/publico/auth/me del vecino de B → 200", me.status_code == 200, f"{me.status_code}")
            me = await c.get("/api/v1/publico/auth/me", headers={"Authorization": f"Bearer {tv}", "Origin": "https://vecinos.zaris.com.ar"})
            check("token del vecino de B con Origin base → 401", me.status_code == 401, f"{me.status_code}")

    # 7. configuración por municipio
    print("\n7. leer_config")
    try:
        from app.core.config_municipio import leer_config
        async with AsyncSessionLocal() as db:
            v = await leer_config(db, "vapid_public_key", B)
            check("clave global (vapid) se lee desde B", bool(v))
            v = await leer_config(db, "municipio_nombre", B)
            check("clave del municipio 1 no se lee desde B", v is None, f"devolvió {v!r}")
            v = await leer_config(db, "municipio_nombre", 1)
            check("clave del municipio 1 se lee desde 1", bool(v), f"devolvió {v!r}")
    except ImportError as exc:
        check("app.core.config_municipio existe", False, str(exc))

    fallas = [r for r in RES if not r[1]]
    print(f"\nRESULTADO: {len(RES) - len(fallas)} OK / {len(fallas)} FAIL")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
