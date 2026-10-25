# -*- coding: utf-8 -*-
"""
Smoke in-process — super administrador (IT-01 F3, PLAN_MULTI_MUNICIPIO_F3.md).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_super_admin.py

SOLO LOCAL. Requiere el municipio de aislamiento (seed_municipio_aislamiento.py). Mail en MOCK.
Crea (y conserva) la cuenta local del super administrador con seed_super_admin.py.
"""
import asyncio
import os
import subprocess
import sys

import httpx

os.environ.setdefault("ENV_FILE", ".env.local")
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import DBAPIError  # noqa: E402

from app.core.config import settings  # noqa: E402

if "zaris_dev" not in settings.ASYNC_DATABASE_URI:
    sys.exit("ABORT: este smoke es SOLO LOCAL (la DB configurada no es zaris_dev).")
settings.RESEND_API_KEY = ""

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402

EMAIL_SUPER = "super.admin@prueba-aislamiento.com.ar"
CLAVE = "123456"
RES: list[tuple[str, bool, str]] = []


def check(nombre: str, ok: bool, detalle: str = "") -> None:
    RES.append((nombre, ok, detalle))
    print(f"  {'OK  ' if ok else 'FAIL'} {nombre}{(' — ' + detalle) if detalle and not ok else ''}")


async def _falla_por(db, sql: str, params: dict, constraint: str) -> tuple[bool, str]:
    """Corre `sql` en un savepoint y dice si falló por `constraint` (texto del error)."""
    try:
        async with db.begin_nested():
            await db.execute(text(sql), params)
        return False, "no falló"
    except DBAPIError as e:
        msg = str(e.orig)
        return constraint in msg, msg[:160]


_INSERT_USUARIO = """
    INSERT INTO usuarios (nombre, nivel_acceso, username, password_hash, id_municipio, activo,
                          buc_acceso, email)
    VALUES ('Smoke F3', :nivel, :u, 'x', :mun, TRUE, FALSE, :u)"""


async def test_constraints_nivel_0() -> None:
    print("\n1. Restricciones de la base (migs 127 y 127b)")
    async with AsyncSessionLocal() as db:
        async with db.begin():
            ok, det = await _falla_por(db, _INSERT_USUARIO,
                                       {"nivel": 0, "u": "smoke.f3.a@prueba-aislamiento.com.ar", "mun": 1},
                                       "ck_usuarios_municipio_nivel")
            check("nivel 0 con municipio falla por ck_usuarios_municipio_nivel", ok, det)
            ok, det = await _falla_por(db, _INSERT_USUARIO,
                                       {"nivel": 1, "u": "smoke.f3.b@prueba-aislamiento.com.ar", "mun": None},
                                       "ck_usuarios_municipio_nivel")
            check("nivel 1 sin municipio falla por ck_usuarios_municipio_nivel", ok, det)
            try:
                async with db.begin_nested():
                    await db.execute(text(_INSERT_USUARIO),
                                     {"nivel": 0, "u": "smoke.f3.c@prueba-aislamiento.com.ar", "mun": None})
                    raise RuntimeError("revertir")
            except RuntimeError:
                check("nivel 0 sin municipio se acepta", True)
            except DBAPIError as e:
                check("nivel 0 sin municipio se acepta", False, str(e.orig)[:160])
            ok, det = await _falla_por(db, "UPDATE super_admin_acceso SET detalle = 'x'", {}, "append-only")
            check("UPDATE de super_admin_acceso lanza append-only", ok, det)
            ok, det = await _falla_por(db, "DELETE FROM super_admin_acceso", {}, "append-only")
            check("DELETE de super_admin_acceso lanza append-only", ok, det)
            await db.rollback()


def _seed(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, os.path.join(AQUI, "seed_super_admin.py"), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env={**os.environ, "PYTHONPATH": AQUI}, cwd=AQUI)


async def test_seed_super_admin() -> None:
    print("\n2. seed_super_admin.py")
    p = _seed("--email", EMAIL_SUPER, "--nombre", "Super Prueba", "--password-dev", CLAVE)
    check("el script corre", p.returncode == 0, (p.stdout + p.stderr)[-300:])
    p2 = _seed("--email", EMAIL_SUPER, "--nombre", "Super Prueba", "--password-dev", CLAVE)
    check("la segunda corrida tampoco falla", p2.returncode == 0, (p2.stdout + p2.stderr)[-300:])
    async with AsyncSessionLocal() as db:
        filas = (await db.execute(text(
            "SELECT nivel_acceso, id_municipio FROM usuarios WHERE lower(email) = :e"),
            {"e": EMAIL_SUPER})).fetchall()
        email_mun1 = (await db.execute(text(
            "SELECT email FROM usuarios WHERE id_municipio = 1 AND email IS NOT NULL "
            "AND email LIKE '%@%' ORDER BY id_usuario LIMIT 1"))).scalar()
    check("queda UNA fila de nivel 0 sin municipio",
          len(filas) == 1 and filas[0].nivel_acceso == 0 and filas[0].id_municipio is None, str(filas))
    p3 = _seed("--email", email_mun1, "--nombre", "Choque")
    check("con el email de una cuenta del municipio 1 sale con error", p3.returncode != 0,
          (p3.stdout + p3.stderr)[-200:])


async def test_password_renovacion_global() -> None:
    print("\n3. password_renovacion_dias global")
    from app.core.config_municipio import leer_config
    async with AsyncSessionLocal() as db:
        filas = (await db.execute(text(
            "SELECT id_municipio FROM configuracion_general WHERE clave = 'password_renovacion_dias'"))).fetchall()
        valor = await leer_config(db, "password_renovacion_dias", 1)
    check("la clave existe solo como global", [f.id_municipio for f in filas] == [None], str(filas))
    check("el municipio 1 la lee (valor global)", valor is not None, repr(valor))


async def _id_super() -> int:
    async with AsyncSessionLocal() as db:
        return (await db.execute(text(
            "SELECT id_usuario FROM usuarios WHERE lower(email) = :e AND nivel_acceso = 0"),
            {"e": EMAIL_SUPER})).scalar()


async def _ultimo_acceso() -> int:
    async with AsyncSessionLocal() as db:
        return (await db.execute(text(
            "SELECT COALESCE(max(id_super_admin_acceso), 0) FROM super_admin_acceso"))).scalar()


async def _accesos_desde(desde: int) -> list:
    async with AsyncSessionLocal() as db:
        return (await db.execute(text(
            "SELECT accion, id_municipio, metodo, ruta, detalle FROM super_admin_acceso "
            "WHERE id_super_admin_acceso > :d ORDER BY id_super_admin_acceso"), {"d": desde})).fetchall()


async def test_registrar_acceso_super() -> None:
    print("\n4. registrar_acceso_super")
    from app.services.accesos_super import registrar_acceso_super
    sup, desde = await _id_super(), await _ultimo_acceso()
    await registrar_acceso_super(id_usuario=sup, accion="seleccion", id_municipio=1, metodo="POST",
                                 ruta="/api/v1/super/seleccion", detalle="smoke T2", ip="127.0.0.1",
                                 user_agent="smoke")
    filas = await _accesos_desde(desde)
    check("deja la fila y se ve desde otra sesión",
          [(f.accion, f.id_municipio, f.detalle) for f in filas] == [("seleccion", 1, "smoke T2")], str(filas))


async def test_registro_falla_cierra() -> None:
    print("\n5. registro que falla = acceso negado")
    from fastapi import HTTPException

    from app.services.accesos_super import registrar_acceso_super
    sup, desde = await _id_super(), await _ultimo_acceso()
    try:
        await registrar_acceso_super(id_usuario=sup, accion="inexistente", id_municipio=1)
        check("una acción fuera del CHECK lanza 503", False, "no lanzó")
    except HTTPException as e:
        check("una acción fuera del CHECK lanza 503", e.status_code == 503, f"{e.status_code} {e.detail}")
    check("y no deja fila", await _accesos_desde(desde) == [])


TESTS = [test_constraints_nivel_0, test_seed_super_admin, test_password_renovacion_global,
         test_registrar_acceso_super, test_registro_falla_cierra]


async def main() -> int:
    async with AsyncSessionLocal() as db:
        B = (await db.execute(text("SELECT id_municipio FROM municipios WHERE subdominio = 'aislamiento'"))).scalar()
    if B is None:
        sys.exit("Falta el municipio de aislamiento: correr seed_municipio_aislamiento.py")
    print(f"Municipio de aislamiento: {B}")
    for t in TESTS:
        try:
            await t()
        except Exception as e:  # noqa: BLE001 — un test roto no frena a los demás
            check(f"{t.__name__} sin excepción", False, f"{type(e).__name__}: {e}"[:200])
    fallas = [r for r in RES if not r[1]]
    print(f"\nRESULTADO: {len(RES) - len(fallas)} OK / {len(fallas)} FAIL")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
