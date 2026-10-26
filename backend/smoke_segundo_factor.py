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


# ── Cuentas y entorno de prueba ──────────────────────────────────────────────

SF_ADMIN = "sf.admin@prueba-aislamiento.com.ar"
SF_NIVEL2 = "sf.nivel2@prueba-aislamiento.com.ar"


def _prender() -> None:
    """Segundo factor prendido in-process, con una clave Fernet propia de la corrida."""
    from cryptography.fernet import Fernet
    if "clave" not in CTX:
        CTX["clave"] = Fernet.generate_key().decode()
    settings.SEGUNDO_FACTOR_OBLIGATORIO = True
    settings.SEGUNDO_FACTOR_CLAVE = CTX["clave"]


async def _cuenta(email: str, nivel: int, mun: int = 1) -> int:
    """Cuenta de prueba (idempotente): activa, con la clave de la corrida y sin clave temporal."""
    from app.core.auth import hash_password
    async with AsyncSessionLocal() as db:
        await db.execute(text("""
            INSERT INTO usuarios (nombre, nivel_acceso, username, password_hash, id_municipio, activo,
                                  buc_acceso, email)
            SELECT :n, :nivel, CAST(:e AS VARCHAR), 'x', :mun, TRUE, FALSE, CAST(:e AS VARCHAR)
             WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE lower(email) = CAST(:e AS VARCHAR))"""),
            {"n": f"Smoke F3b {email.split('@')[0]}", "nivel": nivel, "e": email, "mun": mun})
        id_u = (await db.execute(text(
            """UPDATE usuarios SET nivel_acceso = :nivel, id_municipio = :mun, activo = TRUE,
                      password_hash = :h, debe_cambiar_password = FALSE
                WHERE lower(email) = :e RETURNING id_usuario"""),
            {"nivel": nivel, "mun": mun, "h": hash_password(CLAVE), "e": email})).scalar_one()
        await db.commit()
    return id_u


async def _sql(sql: str, params: dict | None = None) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(text(sql), params or {})
        await db.commit()


# ── Tarea 2 ──────────────────────────────────────────────────────────────────

async def test_cifrado() -> None:
    print("\n2a. Cifrado del secreto")
    from app.services import segundo_factor as sf
    _prender()
    check("descifrar(cifrar(x)) == x", sf.descifrar(sf.cifrar("ABC")) == "ABC")
    for valor, nombre in (("", "vacía"), ("basura", "inválida")):
        settings.SEGUNDO_FACTOR_CLAVE = valor
        try:
            sf.cifrar("ABC")
            check(f"clave {nombre} → SegundoFactorNoConfigurado", False, "no lanzó")
        except sf.SegundoFactorNoConfigurado:
            check(f"clave {nombre} → SegundoFactorNoConfigurado", True)
    _prender()


async def test_vinculacion() -> None:
    print("\n2b. Habilitación y vinculación")
    import re
    import time
    import pyotp
    from app.services import segundo_factor as sf
    _prender()
    id_u = await _cuenta(SF_ADMIN, 1)
    CTX["id_admin"] = id_u
    async with AsyncSessionLocal() as db:
        await sf.habilitar(db, id_usuario=id_u, id_municipio=1, id_actor=None)
        await db.commit()
        est = await sf.estado_cuenta(db, id_u)
        check("habilitar → habilitada y sin vincular", est.habilitada and not est.vinculada, str(est))
        r = await sf.iniciar_vinculacion(db, id_usuario=id_u, id_municipio=1, etiqueta=f"{SF_ADMIN} · SAN")
        await db.commit()
        check("el QR es un data URI SVG", r["qr"].startswith("data:image/svg+xml"), r["qr"][:40])
        check("el secreto es base32 de 32", bool(re.fullmatch(r"[A-Z2-7]{32}", r["secreto"])), r["secreto"])
        totp = pyotp.TOTP(r["secreto"])
        mal = await sf.confirmar_vinculacion(db, id_usuario=id_u, codigo=totp.at(time.time() - 3600))
        check("confirmar con un código mal → None", mal is None)
        codigos = await sf.confirmar_vinculacion(db, id_usuario=id_u, codigo=totp.now())
        await db.commit()
        check("confirmar con el código vigente → 10 códigos de emergencia",
              codigos is not None and len(codigos) == 10
              and all(re.fullmatch(r"[A-Z2-9]{5}-[A-Z2-9]{5}", c) for c in codigos), str(codigos)[:80])
        est = await sf.estado_cuenta(db, id_u)
        check("después de confirmar: vinculada", est.vinculada and est.confirmado_en is not None, str(est))
        marca = (await db.execute(text("SELECT sesiones_validas_desde FROM usuarios WHERE id_usuario = :u"),
                                  {"u": id_u})).scalar()
        check("la confirmación fija sesiones_validas_desde", marca is not None)
    CTX["secreto_admin"], CTX["codigos_admin"] = r["secreto"], codigos or []


async def test_reintento_vinculacion() -> None:
    print("\n2c. Vinculación retomada: el QR nuevo reemplaza al pendiente")
    import pyotp
    from app.services import segundo_factor as sf
    _prender()
    id_u = CTX["id_admin"]
    async with AsyncSessionLocal() as db:
        await sf.habilitar(db, id_usuario=id_u, id_municipio=1, id_actor=None)
        r1 = await sf.iniciar_vinculacion(db, id_usuario=id_u, id_municipio=1, etiqueta="x")
        r2 = await sf.iniciar_vinculacion(db, id_usuario=id_u, id_municipio=1, etiqueta="x")
        await db.commit()
        viejo = await sf.confirmar_vinculacion(db, id_usuario=id_u, codigo=pyotp.TOTP(r1["secreto"]).now())
        check("un código del primer QR ya no confirma", viejo is None)
        codigos = await sf.confirmar_vinculacion(db, id_usuario=id_u, codigo=pyotp.TOTP(r2["secreto"]).now())
        await db.commit()
        check("el código del QR nuevo confirma", codigos is not None and len(codigos) == 10)
    CTX["secreto_admin"], CTX["codigos_admin"] = r2["secreto"], codigos or []


async def test_codigo_y_repeticion() -> None:
    print("\n2d. Código vigente, repetición y ventana ±1")
    import time
    import pyotp
    from app.services import segundo_factor as sf
    _prender()
    id_u, totp = CTX["id_admin"], pyotp.TOTP(CTX["secreto_admin"])
    await _sql("UPDATE usuario_segundo_factor SET ultimo_paso = NULL WHERE id_usuario = :u", {"u": id_u})
    async with AsyncSessionLocal() as db:
        c = totp.now()
        check("código vigente → True", await sf.verificar_codigo(db, id_usuario=id_u, codigo=c))
        await db.commit()
        check("el mismo código otra vez → False", not await sf.verificar_codigo(db, id_usuario=id_u, codigo=c))
        c1 = totp.at(time.time() + 30)
        check("código del paso siguiente (ventana +1) → True",
              await sf.verificar_codigo(db, id_usuario=id_u, codigo=c1))
        await db.commit()
    await _sql("UPDATE usuario_segundo_factor SET ultimo_paso = NULL WHERE id_usuario = :u", {"u": id_u})
    async with AsyncSessionLocal() as db:
        c = totp.now()
        check("código con espacio ('123 456') → True",
              await sf.verificar_codigo(db, id_usuario=id_u, codigo=f"{c[:3]} {c[3:]}"))
        await db.commit()


async def test_codigo_concurrente() -> None:
    print("\n2e. El mismo código dos veces a la vez: un solo éxito")
    import pyotp
    from app.services import segundo_factor as sf
    _prender()
    id_u = CTX["id_admin"]
    await _sql("UPDATE usuario_segundo_factor SET ultimo_paso = NULL WHERE id_usuario = :u", {"u": id_u})
    c = pyotp.TOTP(CTX["secreto_admin"]).now()

    async def una() -> bool:
        async with AsyncSessionLocal() as db:
            ok = await sf.verificar_codigo(db, id_usuario=id_u, codigo=c)
            await db.commit()
            return ok

    r = await asyncio.gather(una(), una())
    check("exactamente uno de los dos da True", sum(r) == 1, str(r))


async def test_emergencia() -> None:
    print("\n2f. Códigos de emergencia")
    from app.services import segundo_factor as sf
    _prender()
    id_u, codigos = CTX["id_admin"], CTX["codigos_admin"]
    async with AsyncSessionLocal() as db:
        cod = codigos[0].lower().replace("-", "")
        check("código en minúsculas y sin guion → True", await sf.usar_codigo_emergencia(db, id_usuario=id_u, codigo=cod))
        await db.commit()
        check("el mismo código otra vez → False", not await sf.usar_codigo_emergencia(db, id_usuario=id_u, codigo=cod))
        check("un código inventado → False",
              not await sf.usar_codigo_emergencia(db, id_usuario=id_u, codigo="ZZZZZ-ZZZZZ"))


async def test_bloqueo() -> None:
    print("\n2g. Bloqueo por fallos consecutivos")
    from app.services import segundo_factor as sf
    _prender()
    id_u = CTX["id_admin"]
    await _sql("UPDATE usuario_segundo_factor SET intentos_fallidos = 0, bloqueado_hasta = NULL "
               "WHERE id_usuario = :u", {"u": id_u})
    async with AsyncSessionLocal() as db:
        antes = (await db.execute(text("SELECT count(*) FROM usuario_segundo_factor_evento "
                                       "WHERE id_usuario = :u AND evento = 'bloqueo'"), {"u": id_u})).scalar()
        r = []
        for _ in range(5):
            r.append(await sf.registrar_fallo(db, id_usuario=id_u))
            await db.commit()
        check("los 4 primeros fallos no bloquean y el quinto sí", r == [False] * 4 + [True], str(r))
        check("bloqueada() → True", await sf.bloqueada(db, id_u))
        despues = (await db.execute(text("SELECT count(*) FROM usuario_segundo_factor_evento "
                                         "WHERE id_usuario = :u AND evento = 'bloqueo'"), {"u": id_u})).scalar()
        check("queda un evento 'bloqueo'", despues == antes + 1, f"{antes} → {despues}")
    await _sql("UPDATE usuario_segundo_factor SET intentos_fallidos = 0, bloqueado_hasta = NULL "
               "WHERE id_usuario = :u", {"u": id_u})


TESTS = [test_tablas_segundo_factor,
         test_cifrado, test_vinculacion, test_reintento_vinculacion, test_codigo_y_repeticion,
         test_codigo_concurrente, test_emergencia, test_bloqueo]


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
