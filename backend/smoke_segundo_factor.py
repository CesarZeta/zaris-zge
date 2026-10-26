# -*- coding: utf-8 -*-
"""
Smoke in-process — segundo factor de los niveles 0 y 1 (IT-01 F3b, PLAN_MULTI_MUNICIPIO_F3B.md).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_segundo_factor.py

SOLO LOCAL. Mail en MOCK. Prende el segundo factor IN-PROCESS (el .env.local lo tiene apagado
para el resto de los smokes) con una clave Fernet generada en el momento. Crea (y conserva) sus
cuentas de prueba en el municipio 1; usa el super administrador local de seed_super_admin.py.
"""
import asyncio
import os
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
from app.middleware import rate_limit as _rate_limit  # noqa: E402

EMAIL_SUPER = "super.admin@prueba-aislamiento.com.ar"
CLAVE = "123456"
RES: list[tuple[str, bool, str]] = []
CTX: dict = {}


def check(nombre: str, ok: bool, detalle: str = "") -> None:
    RES.append((nombre, ok, detalle))
    print(f"  {'OK  ' if ok else 'FAIL'} {nombre}{(' — ' + detalle) if detalle and not ok else ''}")


async def _falla_por(db, sql: str, params: dict, texto: str) -> tuple[bool, str]:
    """Corre `sql` en un savepoint y dice si falló con `texto` en el error."""
    try:
        async with db.begin_nested():
            await db.execute(text(sql), params)
        return False, "no falló"
    except DBAPIError as e:
        msg = str(e.orig)
        return texto in msg, msg[:160]


def _cliente() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _id_super(db) -> int:
    return (await db.execute(text(
        "SELECT id_usuario FROM usuarios WHERE lower(email) = :e AND nivel_acceso = 0"),
        {"e": EMAIL_SUPER})).scalar_one()


# ── Tarea 1 ──────────────────────────────────────────────────────────────────

async def test_tablas_segundo_factor() -> None:
    print("\n1. Base del segundo factor (migs 128 y 128b)")
    async with AsyncSessionLocal() as db:
        for t in ("usuario_segundo_factor", "usuario_codigo_emergencia", "usuario_segundo_factor_evento"):
            existe = (await db.execute(text("SELECT to_regclass(:t)"), {"t": f"public.{t}"})).scalar()
            check(f"existe {t}", existe is not None)
        col = (await db.execute(text(
            "SELECT 1 FROM information_schema.columns WHERE table_name = 'usuarios' "
            "AND column_name = 'sesiones_validas_desde'"))).scalar()
        check("usuarios.sesiones_validas_desde existe", col == 1)
        id_super = await _id_super(db)
    async with AsyncSessionLocal() as db:
        async with db.begin():
            await db.execute(text(
                "INSERT INTO usuario_segundo_factor_evento (id_usuario, evento) VALUES (:u, 'ingreso')"),
                {"u": id_super})
            ok, det = await _falla_por(db, "UPDATE usuario_segundo_factor_evento SET evento = 'fallido'", {},
                                       "append-only")
            check("UPDATE de eventos rechazado (append-only)", ok, det)
            ok, det = await _falla_por(db, "DELETE FROM usuario_segundo_factor_evento", {}, "append-only")
            check("DELETE de eventos rechazado (append-only)", ok, det)
            ok, det = await _falla_por(
                db, "INSERT INTO usuario_segundo_factor_evento (id_usuario, evento) VALUES (:u, 'otro')",
                {"u": id_super}, "ck_usuario_segundo_factor_evento_evento")
            check("evento 'otro' rechazado por el CHECK", ok, det)
            await db.rollback()
    from app.services.accesos_super import registrar_acceso_super
    async with AsyncSessionLocal() as db:
        id_super = await _id_super(db)
        antes = (await db.execute(text(
            "SELECT count(*) FROM super_admin_acceso WHERE id_usuario = :u AND accion = 'segundo_factor'"),
            {"u": id_super})).scalar()
    try:
        await registrar_acceso_super(id_usuario=id_super, accion="segundo_factor", id_municipio=1,
                                     detalle="smoke F3b: acción nueva del registro")
        ok = True
    except Exception as e:  # noqa: BLE001
        ok, det = False, str(e)[:160]
    async with AsyncSessionLocal() as db:
        despues = (await db.execute(text(
            "SELECT count(*) FROM super_admin_acceso WHERE id_usuario = :u AND accion = 'segundo_factor'"),
            {"u": id_super})).scalar()
    check("registrar_acceso_super acepta la acción 'segundo_factor'", ok and despues == antes + 1,
          f"antes={antes} después={despues}")


TESTS = [test_tablas_segundo_factor]


async def main() -> int:
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
