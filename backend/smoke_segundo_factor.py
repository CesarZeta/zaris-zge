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


# ── Tarea 3 ──────────────────────────────────────────────────────────────────

def _h(tok: str, mun=None) -> dict:
    h = {"Authorization": f"Bearer {tok}"}
    if mun is not None:
        h["X-Municipio"] = str(mun)
    return h


async def _me(tok: str) -> int:
    async with _cliente() as c:
        return (await c.get("/api/v1/auth/me", headers=_h(tok))).status_code


async def test_token_sin_sf() -> None:
    print("\n3a. Token de nivel 1 sin el claim del segundo factor")
    from app.core.auth import create_access_token
    _prender()
    id_u = CTX["id_admin"]
    check("sin sf → 401", await _me(create_access_token({"sub": str(id_u), "mun": 1})) == 401)
    check("con sf → 200", await _me(create_access_token({"sub": str(id_u), "mun": 1, "sf": True})) == 200)


async def test_ascenso() -> None:
    print("\n3b. Ascenso de nivel 2 a 1 con un token vigente")
    from app.core.auth import create_access_token
    _prender()
    id_2 = await _cuenta(SF_NIVEL2, 2)
    tok = create_access_token({"sub": str(id_2), "mun": 1})
    check("nivel 2 sin sf → 200", await _me(tok) == 200)
    await _sql("UPDATE usuarios SET nivel_acceso = 1 WHERE id_usuario = :u", {"u": id_2})
    try:
        check("el mismo token, ya en nivel 1 → 401", await _me(tok) == 401)
    finally:
        await _sql("UPDATE usuarios SET nivel_acceso = 2 WHERE id_usuario = :u", {"u": id_2})


async def test_marca() -> None:
    print("\n3c. Revocación por sesiones_validas_desde")
    from app.core.auth import create_access_token
    _prender()
    id_u = CTX["id_admin"]
    await _sql("UPDATE usuarios SET sesiones_validas_desde = NULL WHERE id_usuario = :u", {"u": id_u})
    tok = create_access_token({"sub": str(id_u), "mun": 1, "sf": True})
    check("token con sf → 200", await _me(tok) == 200)
    await asyncio.sleep(1.1)
    await _sql("UPDATE usuarios SET sesiones_validas_desde = date_trunc('second', NOW()) WHERE id_usuario = :u",
               {"u": id_u})
    check("el mismo token después de la marca → 401", await _me(tok) == 401)
    nuevo = create_access_token({"sub": str(id_u), "mun": 1, "sf": True})
    check("un token nuevo → 200", await _me(nuevo) == 200)


async def test_super_sin_sf() -> None:
    print("\n3d. Token del super sin el claim")
    from app.core.auth import crear_token_super_admin
    _prender()
    async with AsyncSessionLocal() as db:
        id_super = await _id_super(db)
    check("super sin sf → 401", await _me(crear_token_super_admin(id_super, segundo_factor=False)) == 401)
    check("super con sf → 200", await _me(crear_token_super_admin(id_super, segundo_factor=True)) == 200)


async def test_interruptor_apagado() -> None:
    print("\n3e. Con el segundo factor apagado")
    from app.core.auth import create_access_token
    _prender()
    settings.SEGUNDO_FACTOR_OBLIGATORIO = False
    try:
        check("nivel 1 sin sf → 200",
              await _me(create_access_token({"sub": str(CTX["id_admin"]), "mun": 1})) == 200)
    finally:
        _prender()


async def test_demo_poblar_sin_sf() -> None:
    print("\n3f. /demo/poblar valida el token con el guard central")
    from app.core.auth import create_access_token
    _prender()
    tok = create_access_token({"sub": str(CTX["id_admin"]), "mun": 1})
    async with _cliente() as c:
        # cerrar_atraso sin aplicar = dry-run: si el guard dejara pasar, no escribe nada.
        r = await c.post("/api/v1/demo/poblar", headers=_h(tok), json={"modo": "cerrar_atraso", "aplicar": False})
    check("nivel 1 del municipio demo sin sf → 401", r.status_code == 401, f"{r.status_code} {r.text[:120]}")


# ── Tarea 4 ──────────────────────────────────────────────────────────────────

SF_NUEVO = "sf.nuevo@prueba-aislamiento.com.ar"
T_SIN_HABILITAR = "Tu cuenta necesita que el soporte de ZARIS habilite la vinculación de la app de códigos."
T_CODIGO_INVALIDO = "El código no es válido. Revisá la app y probá de nuevo."
T_BLOQUEO = "Demasiados códigos incorrectos. Probá de nuevo en 15 minutos."
T_DESAFIO = "Pasaron más de 5 minutos. Volvé a ingresar tu clave."
T_NO_CONFIGURADO = "El ingreso con segundo factor no está configurado en el servidor. Avisá al soporte de ZARIS."


async def _login(c: httpx.AsyncClient, ident: str) -> httpx.Response:
    # El límite de intentos es en memoria y no es lo que se prueba acá: se vacía antes de cada llamada.
    _rate_limit._buckets.clear()
    return await c.post("/api/v1/auth/login", json={"identificador": ident, "password": CLAVE})


async def _paso(c: httpx.AsyncClient, ruta: str, body: dict) -> httpx.Response:
    _rate_limit._buckets.clear()
    return await c.post(f"/api/v1/auth/segundo-factor/{ruta}", json=body)


async def _contar(sql: str, params: dict) -> int:
    async with AsyncSessionLocal() as db:
        return (await db.execute(text(sql), params)).scalar()


async def _sin_repeticion(id_u: int) -> None:
    """El anti-repetición no es lo que prueban estos tests: libera el paso de 30 s ya usado."""
    await _sql("UPDATE usuario_segundo_factor SET ultimo_paso = NULL, intentos_fallidos = 0, "
               "bloqueado_hasta = NULL WHERE id_usuario = :u", {"u": id_u})


async def test_login_pide_codigo() -> None:
    print("\n4a. Login de una cuenta vinculada: clave y después código")
    import pyotp
    _prender()
    id_u = CTX["id_admin"]
    await _sin_repeticion(id_u)
    async with _cliente() as c:
        r = await _login(c, SF_ADMIN)
        j = r.json()
        check("login → 200 sin access_token y con estado 'codigo'",
              r.status_code == 200 and "access_token" not in j and j.get("estado") == "codigo"
              and isinstance(j.get("desafio"), str), f"{r.status_code} {r.text[:160]}")
        check("el desafío no sirve como token", await _me(j.get("desafio") or "x") == 401)
        logs = await _contar("SELECT count(*) FROM usuario_login_log WHERE id_usuario = :u", {"u": id_u})
        ingresos = await _contar("SELECT count(*) FROM usuario_segundo_factor_evento "
                                 "WHERE id_usuario = :u AND evento = 'ingreso'", {"u": id_u})
        r2 = await _paso(c, "verificar", {"desafio": j.get("desafio"),
                                          "codigo": pyotp.TOTP(CTX["secreto_admin"]).now()})
        tok = r2.json().get("access_token") if r2.status_code == 200 else None
        check("/verificar con el código vigente → access_token", tok is not None, f"{r2.status_code} {r2.text[:160]}")
        check("ese token sirve", tok is not None and await _me(tok) == 200)
    check("queda la fila de usuario_login_log",
          await _contar("SELECT count(*) FROM usuario_login_log WHERE id_usuario = :u", {"u": id_u}) == logs + 1)
    check("queda un evento 'ingreso'",
          await _contar("SELECT count(*) FROM usuario_segundo_factor_evento WHERE id_usuario = :u "
                        "AND evento = 'ingreso'", {"u": id_u}) == ingresos + 1)


async def test_nivel_2_sin_cambios() -> None:
    print("\n4b. Nivel 2: el login de siempre")
    _prender()
    await _cuenta(SF_NIVEL2, 2)
    async with _cliente() as c:
        r = await _login(c, SF_NIVEL2)
    check("nivel 2 → access_token directo", r.status_code == 200 and "access_token" in r.json(),
          f"{r.status_code} {r.text[:120]}")


async def test_sin_habilitar() -> None:
    print("\n4c. Cuenta sin habilitar o con la habilitación vencida")
    from app.api.routes.segundo_factor import crear_desafio
    _prender()
    id_n = await _cuenta(SF_NUEVO, 1)
    CTX["id_nuevo"] = id_n
    await _sql("""INSERT INTO usuario_segundo_factor (id_usuario, id_municipio) VALUES (:u, 1)
                  ON CONFLICT (id_usuario) DO UPDATE SET secreto_cifrado = NULL, secreto_pendiente_cifrado = NULL,
                         habilitado_hasta = NULL, intentos_fallidos = 0, bloqueado_hasta = NULL""", {"u": id_n})
    async with _cliente() as c:
        j = (await _login(c, SF_NUEVO)).json()
        check("sin habilitar → estado 'sin_habilitar', sin desafío y con el texto fijo",
              j.get("estado") == "sin_habilitar" and j.get("desafio") is None and j.get("mensaje") == T_SIN_HABILITAR,
              str(j)[:200])
        await _sql("UPDATE usuario_segundo_factor SET habilitado_hasta = NOW() - interval '1 minute' "
                   "WHERE id_usuario = :u", {"u": id_n})
        j = (await _login(c, SF_NUEVO)).json()
        check("habilitación vencida → 'sin_habilitar'", j.get("estado") == "sin_habilitar", str(j)[:160])
        r = await _paso(c, "vinculacion", {"desafio": crear_desafio(id_n, fin="vincular", id_municipio=1)})
        check("/vinculacion con un desafío fabricado y sin habilitar → 403", r.status_code == 403,
              f"{r.status_code} {r.text[:120]}")


async def test_vinculacion_por_login() -> None:
    print("\n4d. Vinculación desde el login")
    import pyotp
    from app.services import segundo_factor as sf
    _prender()
    id_n = CTX["id_nuevo"]
    async with AsyncSessionLocal() as db:
        await sf.habilitar(db, id_usuario=id_n, id_municipio=1, id_actor=None)
        await db.commit()
    async with _cliente() as c:
        j = (await _login(c, SF_NUEVO)).json()
        check("habilitada → estado 'vincular'", j.get("estado") == "vincular" and j.get("desafio"), str(j)[:160])
        r = await _paso(c, "vinculacion", {"desafio": j.get("desafio")})
        q = r.json() if r.status_code == 200 else {}
        check("/vinculacion → QR y secreto", str(q.get("qr", "")).startswith("data:image/svg+xml")
              and q.get("secreto"), f"{r.status_code} {r.text[:120]}")
        r = await _paso(c, "vinculacion/confirmar",
                        {"desafio": j.get("desafio"), "codigo": pyotp.TOTP(q.get("secreto", "A" * 32)).now()})
        k = r.json() if r.status_code == 200 else {}
        check("/vinculacion/confirmar → 10 códigos y access_token",
              len(k.get("codigos_emergencia") or []) == 10 and k.get("access_token"), f"{r.status_code} {r.text[:160]}")
        check("ese token sirve", bool(k.get("access_token")) and await _me(k["access_token"]) == 200)
        j = (await _login(c, SF_NUEVO)).json()
        check("el login siguiente pide el código", j.get("estado") == "codigo", str(j)[:120])


async def test_emergencia_revincula() -> None:
    print("\n4e. Código de emergencia: obliga a vincular, sin perder la app vieja hasta confirmar")
    import pyotp
    _prender()
    id_u, viejos = CTX["id_admin"], CTX["codigos_admin"]
    totp_viejo = pyotp.TOTP(CTX["secreto_admin"])
    await _sin_repeticion(id_u)
    async with _cliente() as c:
        d = (await _login(c, SF_ADMIN)).json().get("desafio")
        r = await _paso(c, "emergencia", {"desafio": d, "codigo": viejos[1]})
        e = r.json() if r.status_code == 200 else {}
        check("/emergencia → desafío nuevo y sin token", bool(e.get("desafio")) and "access_token" not in e,
              f"{r.status_code} {r.text[:120]}")
        r = await _paso(c, "vinculacion", {"desafio": e.get("desafio")})
        check("con ese desafío, /vinculacion da un QR", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
        # La persona abandona acá: la app vieja sigue valiendo.
        j = (await _login(c, SF_ADMIN)).json()
        check("abandonada la vinculación, el login sigue en 'codigo'", j.get("estado") == "codigo", str(j)[:120])
        r = await _paso(c, "verificar", {"desafio": j.get("desafio"), "codigo": totp_viejo.now()})
        check("el código de la app vieja sigue entrando", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
        d = (await _login(c, SF_ADMIN)).json().get("desafio")
        e = (await _paso(c, "emergencia", {"desafio": d, "codigo": viejos[2]})).json()
        q = (await _paso(c, "vinculacion", {"desafio": e.get("desafio")})).json()
        r = await _paso(c, "vinculacion/confirmar",
                        {"desafio": e.get("desafio"), "codigo": pyotp.TOTP(q.get("secreto", "A" * 32)).now()})
        k = r.json() if r.status_code == 200 else {}
        check("confirmar la vinculación nueva → 10 códigos nuevos", len(k.get("codigos_emergencia") or []) == 10,
              f"{r.status_code} {r.text[:120]}")
        if k.get("codigos_emergencia"):
            CTX["secreto_admin"], CTX["codigos_admin"] = q["secreto"], k["codigos_emergencia"]
        d = (await _login(c, SF_ADMIN)).json().get("desafio")
        r = await _paso(c, "emergencia", {"desafio": d, "codigo": viejos[3]})
        check("un código de emergencia anterior ya no sirve → 401", r.status_code == 401, f"{r.status_code} {r.text[:120]}")


async def test_bloqueo_http() -> None:
    print("\n4f. Bloqueo por códigos mal puestos")
    import pyotp
    _prender()
    id_u = CTX["id_admin"]
    await _sin_repeticion(id_u)
    async with _cliente() as c:
        d = (await _login(c, SF_ADMIN)).json().get("desafio")
        codigos = []
        for _ in range(5):
            r = await _paso(c, "verificar", {"desafio": d, "codigo": "000000"})
            codigos.append((r.status_code, r.json().get("detail")))
        check("4 fallos → 401 con el texto fijo",
              all(x == (401, T_CODIGO_INVALIDO) for x in codigos[:4]), str(codigos))
        check("el quinto → 429 con el texto fijo", codigos[4] == (429, T_BLOQUEO), str(codigos[4]))
        bueno = pyotp.TOTP(CTX["secreto_admin"]).now()
        r = await _paso(c, "verificar", {"desafio": d, "codigo": bueno})
        check("el código correcto durante el bloqueo → 429", r.status_code == 429, f"{r.status_code}")
        await _sql("UPDATE usuario_segundo_factor SET bloqueado_hasta = NOW() - interval '1 minute' "
                   "WHERE id_usuario = :u", {"u": id_u})
        r = await _paso(c, "verificar", {"desafio": d, "codigo": bueno})
        check("vencido el bloqueo, entra", r.status_code == 200, f"{r.status_code} {r.text[:120]}")


async def test_desafio() -> None:
    print("\n4g. Desafío vencido, de otro paso o de una cuenta que cambió")
    from datetime import datetime, timedelta, timezone
    import pyotp
    from jose import jwt
    from app.core.auth import ALGORITHM
    _prender()
    id_u = CTX["id_admin"]
    await _sin_repeticion(id_u)
    vencido = jwt.encode({"sub": str(id_u), "scope": "segundo_factor", "fin": "codigo", "mun": 1,
                          "exp": datetime.now(timezone.utc) - timedelta(seconds=10)},
                         settings.SECRET_KEY, algorithm=ALGORITHM)
    async with _cliente() as c:
        r = await _paso(c, "verificar", {"desafio": vencido, "codigo": "123456"})
        check("desafío vencido → 401 con el texto fijo", (r.status_code, r.json().get("detail")) == (401, T_DESAFIO),
              f"{r.status_code} {r.text[:120]}")
        d = (await _login(c, SF_ADMIN)).json().get("desafio")
        r = await _paso(c, "vinculacion/confirmar", {"desafio": d, "codigo": "123456"})
        check("desafío 'codigo' en /vinculacion/confirmar → 401", r.status_code == 401, f"{r.status_code}")
        bueno = pyotp.TOTP(CTX["secreto_admin"]).now()
        for cambio, deshacer, nombre in (
                ("activo = FALSE", "activo = TRUE", "desactivada"),
                ("nivel_acceso = 2", "nivel_acceso = 1", "bajada a nivel 2")):
            d = (await _login(c, SF_ADMIN)).json().get("desafio")
            await _sql(f"UPDATE usuarios SET {cambio} WHERE id_usuario = :u", {"u": id_u})
            try:
                r = await _paso(c, "verificar", {"desafio": d, "codigo": bueno})
                check(f"cuenta {nombre} entre los dos pasos → 401", r.status_code == 401, f"{r.status_code}")
            finally:
                await _sql(f"UPDATE usuarios SET {deshacer} WHERE id_usuario = :u", {"u": id_u})


async def test_clave_temporal() -> None:
    print("\n4h. Clave temporal: el cambio forzado viene después del código")
    import pyotp
    _prender()
    id_u = CTX["id_admin"]
    await _sin_repeticion(id_u)
    await _sql("UPDATE usuarios SET debe_cambiar_password = TRUE WHERE id_usuario = :u", {"u": id_u})
    try:
        async with _cliente() as c:
            d = (await _login(c, SF_ADMIN)).json().get("desafio")
            r = await _paso(c, "verificar", {"desafio": d, "codigo": pyotp.TOTP(CTX["secreto_admin"]).now()})
        u = r.json().get("user", {}) if r.status_code == 200 else {}
        check("/verificar devuelve debe_cambiar_password = true", u.get("debe_cambiar_password") is True,
              f"{r.status_code} {r.text[:120]}")
    finally:
        await _sql("UPDATE usuarios SET debe_cambiar_password = FALSE WHERE id_usuario = :u", {"u": id_u})


async def test_super() -> None:
    print("\n4i. Super administrador: la fila 'login' recién después del código")
    import pyotp
    from jose import jwt
    from app.core.auth import ALGORITHM
    from app.services import segundo_factor as sf
    _prender()
    async with AsyncSessionLocal() as db:
        id_s = await _id_super(db)
        await sf.habilitar(db, id_usuario=id_s, id_municipio=None, id_actor=None)
        await db.commit()
    contar = ("SELECT count(*) FROM super_admin_acceso WHERE id_usuario = :u AND accion = 'login'", {"u": id_s})
    async with _cliente() as c:
        j = (await _login(c, EMAIL_SUPER)).json()
        q = (await _paso(c, "vinculacion", {"desafio": j.get("desafio")})).json()
        r = await _paso(c, "vinculacion/confirmar",
                        {"desafio": j.get("desafio"), "codigo": pyotp.TOTP(q.get("secreto", "A" * 32)).now()})
        check("el super vincula desde el login", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
        CTX["secreto_super"] = q.get("secreto")
        await _sin_repeticion(id_s)
        antes = await _contar(*contar)
        j = (await _login(c, EMAIL_SUPER)).json()
        check("el login del super pide el código", j.get("estado") == "codigo", str(j)[:120])
        check("después de la clave no hay fila 'login'", await _contar(*contar) == antes)
        r = await _paso(c, "verificar", {"desafio": j.get("desafio"), "codigo": pyotp.TOTP(CTX["secreto_super"]).now()})
        check("después del código sí", await _contar(*contar) == antes + 1, f"{r.status_code} {r.text[:120]}")
        claims = jwt.decode(r.json()["access_token"], settings.SECRET_KEY, algorithms=[ALGORITHM]) \
            if r.status_code == 200 else {}
        check("el token del super trae sa y sf", claims.get("sa") is True and claims.get("sf") is True, str(claims))


async def test_sin_clave_503() -> None:
    print("\n4j. Sin SEGUNDO_FACTOR_CLAVE")
    _prender()
    settings.SEGUNDO_FACTOR_CLAVE = ""
    try:
        async with _cliente() as c:
            r = await _login(c, SF_ADMIN)
            check("nivel 1 → 503 con el texto fijo", (r.status_code, r.json().get("detail")) == (503, T_NO_CONFIGURADO),
                  f"{r.status_code} {r.text[:120]}")
            r = await _login(c, SF_NIVEL2)
            check("nivel 2 → access_token", r.status_code == 200 and "access_token" in r.json(), f"{r.status_code}")
    finally:
        _prender()


TESTS = [test_tablas_segundo_factor,
         test_cifrado, test_vinculacion, test_reintento_vinculacion, test_codigo_y_repeticion,
         test_codigo_concurrente, test_emergencia, test_bloqueo,
         test_token_sin_sf, test_ascenso, test_marca, test_super_sin_sf, test_interruptor_apagado,
         test_demo_poblar_sin_sf,
         test_login_pide_codigo, test_nivel_2_sin_cambios, test_sin_habilitar, test_vinculacion_por_login,
         test_emergencia_revincula, test_bloqueo_http, test_desafio, test_clave_temporal, test_super,
         test_sin_clave_503]


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
