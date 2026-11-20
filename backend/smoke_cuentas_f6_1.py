# -*- coding: utf-8 -*-
"""
Smoke in-process — IT-01 F6.1, ajustes de las cuentas internas (PLAN_MULTI_MUNICIPIO_F6_1.md).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_cuentas_f6_1.py

SOLO LOCAL (aborta si la DB no es zaris_dev). El app FastAPI real con httpx.ASGITransport, mail en
MOCK y capturado. Crea por SQL cuentas de prueba propias (email único `f61-…`), que quedan como demo.

Cubre:
  - caso_clave_temporal: con clave temporal, solo /auth/me y /auth/cambiar-password; el resto 403.
  - caso_cambio_voluntario_corta_otra_sesion: cambiar la clave corta todas las sesiones y devuelve una nueva.
  - caso_admin_cambia_clave / caso_recovery_corta_sesion: el admin o el link del mail cortan la sesión abierta.
  - caso_super_cambia_clave: la sesión nueva del super sigue siendo de super.
  - caso_sin_marca_sigue_igual: una cuenta sin marca opera como siempre.
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
# Preparación y verificación como dueño de la base: no pasa por la barrera (IT-01 F6).
from app.core.sistema import SesionSistema as AsyncSessionLocal  # noqa: E402
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


async def me(c: httpx.AsyncClient, tok: str) -> int:
    return (await c.get("/api/v1/auth/me", headers=hdr(tok))).status_code


async def caso_cambio_voluntario_corta_otra_sesion(c: httpx.AsyncClient) -> None:
    print("[caso_cambio_voluntario_corta_otra_sesion]")
    email = await crear_cuenta(3, "Actual-12345")
    a = (await login(c, email, "Actual-12345"))["access_token"]
    await asyncio.sleep(1.1)  # los iat son segundos enteros: la marca tiene que caer después de B
    b = (await login(c, email, "Actual-12345"))["access_token"]
    await asyncio.sleep(1.1)
    r = await c.post("/api/v1/auth/cambiar-password", headers=hdr(a),
                     json={"password_actual": "Actual-12345", "password_nueva": "Nueva-12345"})
    nuevo = r.json().get("access_token") if r.status_code == 200 else None
    check(bool(nuevo), "el cambio devuelve una sesión nueva", f"{r.status_code} {r.text[:120]}")
    check(await me(c, b) == 401, "la otra sesión queda cortada")
    check(await me(c, a) == 401, "la sesión desde la que se cambió también")
    check(bool(nuevo) and await me(c, nuevo) == 200, "la sesión nueva opera")


async def caso_admin_cambia_clave(c: httpx.AsyncClient, admin_tok: str) -> None:
    print("[caso_admin_cambia_clave]")
    email = await crear_cuenta(3, "Actual-12345")
    a = (await login(c, email, "Actual-12345"))["access_token"]
    async with AsyncSessionLocal() as s:
        id_u = (await s.execute(text("SELECT id_usuario FROM usuarios WHERE email = :e"), {"e": email})).scalar()
    await asyncio.sleep(1.1)
    r = await c.put(f"/api/v1/buc/usuarios/{id_u}", headers=hdr(admin_tok), json={"password": "OtraClave-123"})
    check(r.status_code == 200, "el admin cambia la clave → 200", f"{r.status_code} {r.text[:120]}")
    check(await me(c, a) == 401, "la sesión abierta queda cortada")


async def caso_recovery_corta_sesion(c: httpx.AsyncClient) -> None:
    print("[caso_recovery_corta_sesion]")
    email = await crear_cuenta(3, "Actual-12345")
    a = (await login(c, email, "Actual-12345"))["access_token"]
    async with AsyncSessionLocal() as s:
        token = (await s.execute(text("""
            UPDATE usuarios SET token_recovery = gen_random_uuid(),
                   token_recovery_expira = NOW() + interval '1 hour'
             WHERE email = :e RETURNING token_recovery"""), {"e": email})).scalar()
        await s.commit()
    await asyncio.sleep(1.1)
    r = await c.post("/api/v1/auth/resetear-password", json={"token": str(token), "password_nueva": "Nueva-12345"})
    check(r.status_code == 200, "restablecer por el link → 200", f"{r.status_code} {r.text[:120]}")
    check(await me(c, a) == 401, "la sesión abierta queda cortada")


async def caso_super_cambia_clave(c: httpx.AsyncClient) -> None:
    print("[caso_super_cambia_clave]")
    email = await crear_cuenta(0, "Actual-12345", municipio=None)
    a = (await login(c, email, "Actual-12345"))["access_token"]
    r = await c.post("/api/v1/auth/cambiar-password", headers=hdr(a),
                     json={"password_actual": "Actual-12345", "password_nueva": "Nueva-12345"})
    nuevo = r.json().get("access_token") if r.status_code == 200 else None
    check(bool(nuevo), "el super recibe una sesión nueva", f"{r.status_code} {r.text[:120]}")
    if nuevo:
        claims = core_auth.jwt.decode(nuevo, settings.SECRET_KEY, algorithms=[core_auth.ALGORITHM])
        check(claims.get("sa") is True and "mun" not in claims, "la sesión nueva sigue siendo de super", str(claims))
        check(await me(c, nuevo) == 200, "la sesión nueva del super opera")


async def caso_clave_vencida_corta_otra_sesion(c: httpx.AsyncClient) -> None:
    """Revisión final: la renovación periódica marca el cambio obligatorio en el login; la otra sesión
    abierta (p. ej. la app de agentes) tiene que volver al login (401), no quedar en 403 en todo."""
    print("[caso_clave_vencida_corta_otra_sesion]")
    email = await crear_cuenta(4, "Actual-12345")
    a = (await login(c, email, "Actual-12345"))["access_token"]
    async with AsyncSessionLocal() as s:
        await s.execute(text("UPDATE usuarios SET password_actualizada_en = NOW() - interval '400 days' "
                             "WHERE email = :e"), {"e": email})
        await s.commit()
    await asyncio.sleep(1.1)
    d = await login(c, email, "Actual-12345")
    check(d["user"]["debe_cambiar_password"] is True, "el login marca la clave vencida")
    r = await c.get("/api/v1/reclamos", headers=hdr(a))
    check(r.status_code == 401, "la otra sesión vuelve al login (401)", f"{r.status_code} {r.text[:100]}")
    r = await c.get("/api/v1/reclamos", headers=hdr(d["access_token"]))
    check(r.status_code == 403, "la sesión nueva solo sirve para cambiar la clave (403)", str(r.status_code))


async def caso_sin_marca_sigue_igual(c: httpx.AsyncClient) -> None:
    print("[caso_sin_marca_sigue_igual]")
    email = await crear_cuenta(4, "Actual-12345")
    a = (await login(c, email, "Actual-12345"))["access_token"]
    check(await me(c, a) == 200, "una cuenta sin marca opera como siempre")


async def main() -> int:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://smoke.local", timeout=90) as c:
        await caso_clave_temporal(c)
        admin = (await login(c, "ciudadanovl@municipio.gob.ar", os.environ.get("ZARIS_QA_PASS") or "123456"))
        await caso_cambio_voluntario_corta_otra_sesion(c)
        await caso_admin_cambia_clave(c, admin["access_token"])
        await caso_recovery_corta_sesion(c)
        await caso_super_cambia_clave(c)
        await caso_clave_vencida_corta_otra_sesion(c)
        await caso_sin_marca_sigue_igual(c)
    print(f"\n== {OK} OK · {FAIL} FAIL ==")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
