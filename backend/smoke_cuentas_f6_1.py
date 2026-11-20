# -*- coding: utf-8 -*-
"""
Smoke in-process — IT-01 F6.1, ajustes de las cuentas internas (PLAN_MULTI_MUNICIPIO_F6_1.md).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_cuentas_f6_1.py

SOLO LOCAL (aborta si la DB no es zaris_dev). El app FastAPI real con httpx.ASGITransport, mail en
MOCK y capturado. Crea por SQL cuentas de prueba propias (email único `f61-…`), que quedan como demo.

Cubre:
  - caso_clave_temporal: con clave temporal, solo /auth/me y /auth/cambiar-password; el resto 403.
"""
import asyncio
import os
import secrets
import sys
from typing import Optional

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

from app.core import auth as core_auth  # noqa: E402
from app.core.auth import hash_password  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.services import email as svc_email  # noqa: E402


async def _capturar(*a, **k):
    return True


svc_email.enviar_mail = _capturar

OK = FAIL = 0


def check(cond: bool, nombre: str, detalle: str = "") -> None:
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  OK   {nombre}")
    else:
        FAIL += 1
        print(f"  FAIL {nombre} {detalle}")


async def crear_cuenta(nivel: int, clave: str, *, temporal: bool = False, municipio: Optional[int] = 1) -> str:
    """Cuenta de prueba propia; devuelve su email."""
    email = f"f61-{secrets.token_hex(4)}@municipio.gob.ar"
    async with AsyncSessionLocal() as s:
        await s.execute(text("""
            INSERT INTO usuarios (nombre, nivel_acceso, username, email, password_hash, id_municipio,
                                  activo, buc_acceso, debe_cambiar_password, password_actualizada_en)
            VALUES ('Smoke F6.1', :n, :e, :e, :h, :m, TRUE, FALSE, :t, NOW())"""),
            {"n": nivel, "e": email, "h": hash_password(clave), "m": municipio, "t": temporal})
        await s.commit()
    return email


def hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def login(c: httpx.AsyncClient, email: str, clave: str) -> dict:
    r = await c.post("/api/v1/auth/login", json={"identificador": email, "password": clave})
    assert r.status_code == 200 and "access_token" in r.json(), f"login {email}: {r.status_code} {r.text[:200]}"
    return r.json()


async def caso_clave_temporal(c: httpx.AsyncClient) -> None:
    print("[caso_clave_temporal]")
    email = await crear_cuenta(3, "Temporal-123", temporal=True)
    d = await login(c, email, "Temporal-123")
    check(d["user"]["debe_cambiar_password"] is True, "el login avisa la clave temporal")
    tok = d["access_token"]
    r = await c.get("/api/v1/reclamos", headers=hdr(tok))
    check(r.status_code == 403 and r.json().get("detail") == getattr(core_auth, "CLAVE_TEMPORAL", "?"),
          "otra ruta con clave temporal → 403", f"{r.status_code} {r.text[:120]}")
    r = await c.get("/api/v1/auth/me", headers=hdr(tok))
    check(r.status_code == 200, "/auth/me con clave temporal → 200", str(r.status_code))
    r = await c.post("/api/v1/auth/cambiar-password", headers=hdr(tok), json={"password_nueva": "Nueva-12345"})
    check(r.status_code == 200, "cambio de clave → 200", f"{r.status_code} {r.text[:120]}")
    tok = r.json().get("access_token") or tok
    r = await c.get("/api/v1/reclamos", headers=hdr(tok))
    check(r.status_code == 200, "después del cambio opera → 200", str(r.status_code))


async def main() -> int:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://smoke.local", timeout=90) as c:
        await caso_clave_temporal(c)
    print(f"\n== {OK} OK · {FAIL} FAIL ==")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
