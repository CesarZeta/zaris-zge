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


# ── Tarea 3: login, token y municipio por header ──────────────────────────────────────────────
from jose import jwt  # noqa: E402

from app.middleware import rate_limit as _rate_limit  # noqa: E402

ORIGEN_B = "https://aislamiento.zge.zaris.com.ar"
SESION_VENCIDA = "Sesión vencida. Volvé a ingresar."
CTX: dict = {}  # ids y tokens de la corrida


def _cliente() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _login(c: httpx.AsyncClient, ident: str, origen: str | None = None,
                 clave: str = CLAVE) -> httpx.Response:
    # El límite de intentos es en memoria y no es lo que se prueba acá: se vacía antes de cada login.
    _rate_limit._buckets.clear()
    h = {"Origin": origen} if origen else {}
    return await c.post("/api/v1/auth/login", json={"identificador": ident, "password": clave}, headers=h)


async def _token(c: httpx.AsyncClient, ident: str) -> str:
    """Token cacheado por corrida. Las cuentas de B (`*.b@aislamiento.test`) entran desde su dirección."""
    clave = f"tok:{ident}"
    if clave not in CTX:
        r = await _login(c, ident, ORIGEN_B if ident.endswith(".b@aislamiento.test") or
                         ident == "admin.b@aislamiento.test" else None)
        if r.status_code != 200:
            raise RuntimeError(f"login de {ident}: {r.status_code} {r.text[:120]}")
        CTX[clave] = r.json()["access_token"]
    return CTX[clave]


def _h(tok: str, mun=None) -> dict:
    h = {"Authorization": f"Bearer {tok}"}
    if mun is not None:
        h["X-Municipio"] = str(mun)
    return h


async def _contexto() -> None:
    if "B" in CTX:
        return
    from seed_municipio_aislamiento import ids_aislamiento
    async with AsyncSessionLocal() as db:
        ids = await ids_aislamiento(db)
        CTX["B"] = ids["municipio"]
        CTX["rec_B"] = ids["reclamos"]
        CTX["rec_1"] = (await db.execute(text(
            "SELECT id_reclamo FROM reclamos WHERE id_municipio = 1 AND activo ORDER BY id_reclamo LIMIT 1"))).scalar()
        CTX["admin_1"] = (await db.execute(text(
            "SELECT email FROM usuarios WHERE id_municipio = 1 AND nivel_acceso = 1 AND activo AND email LIKE '%@%' "
            "ORDER BY id_usuario LIMIT 1"))).scalar()
        CTX["id_super"] = (await db.execute(text(
            "SELECT id_usuario FROM usuarios WHERE lower(email) = :e AND nivel_acceso = 0"), {"e": EMAIL_SUPER})).scalar()


async def test_login_super() -> None:
    print("\n6. Login del super administrador")
    await _contexto()
    async with AsyncSessionLocal() as db:
        logs_antes = (await db.execute(text("SELECT count(*) FROM usuario_login_log WHERE id_usuario = :u"),
                                       {"u": CTX["id_super"]})).scalar()
    desde = await _ultimo_acceso()
    async with _cliente() as c:
        r1 = await _login(c, EMAIL_SUPER)
        r2 = await _login(c, EMAIL_SUPER, ORIGEN_B)
    check("login sin Origin → 200", r1.status_code == 200, f"{r1.status_code} {r1.text[:120]}")
    check("login desde el subdominio de B → 200", r2.status_code == 200, f"{r2.status_code} {r2.text[:120]}")
    if r1.status_code != 200:
        return
    CTX[f"tok:{EMAIL_SUPER}"] = r1.json()["access_token"]
    cl = jwt.get_unverified_claims(r1.json()["access_token"])
    check("el token tiene sa=True y no tiene mun", cl.get("sa") is True and "mun" not in cl, str(cl))
    u = r1.json()["user"]
    check("user: nivel 0, sin municipio, es_super_admin",
          u.get("nivel_acceso") == 0 and u.get("id_municipio") is None and u.get("es_super_admin") is True,
          str({k: u.get(k) for k in ("nivel_acceso", "id_municipio", "es_super_admin")}))
    filas = await _accesos_desde(desde)
    check("dos filas login, globales", [(f.accion, f.id_municipio) for f in filas] == [("login", None)] * 2,
          str(filas))
    async with AsyncSessionLocal() as db:
        logs = (await db.execute(text("SELECT count(*) FROM usuario_login_log WHERE id_usuario = :u"),
                                 {"u": CTX["id_super"]})).scalar()
    check("no escribe usuario_login_log", logs == logs_antes, f"{logs_antes} → {logs}")


async def test_header_super() -> None:
    print("\n7. Municipio por header (super administrador)")
    await _contexto()
    desde = await _ultimo_acceso()
    async with _cliente() as c:
        tok = await _token(c, EMAIL_SUPER)
        rb = await c.get(f"/api/v1/reclamos/{CTX['rec_B']}", headers=_h(tok, CTX["B"]))
        r1 = await c.get(f"/api/v1/reclamos/{CTX['rec_B']}", headers=_h(tok, 1))
    check("con X-Municipio B ve el reclamo de B", rb.status_code == 200 and "AISLAB" in rb.text,
          f"{rb.status_code} {rb.text[:120]}")
    check("con X-Municipio 1 el reclamo de B da 404", r1.status_code == 404, f"{r1.status_code}")
    filas = await _accesos_desde(desde)
    check("una fila request por request, con su municipio",
          [(f.accion, f.id_municipio, f.metodo, f.ruta) for f in filas]
          == [("request", CTX["B"], "GET", f"/api/v1/reclamos/{CTX['rec_B']}"),
              ("request", 1, "GET", f"/api/v1/reclamos/{CTX['rec_B']}")], str(filas))


async def test_header_invalido() -> None:
    print("\n8. X-Municipio inválido")
    await _contexto()
    desde = await _ultimo_acceso()
    casos = [(None, 400, "Elegí un municipio en el selector"), ("", 400, "Elegí un municipio en el selector"),
             ("abc", 400, "Municipio inválido"), ("-1", 400, "Municipio inválido"),
             ("1,2", 400, "Municipio inválido"), ("1234567890", 400, "Municipio inválido"),
             ("2", 404, "Municipio no encontrado"), ("999999", 404, "Municipio no encontrado")]
    async with _cliente() as c:
        tok = await _token(c, EMAIL_SUPER)
        for valor, status, detalle in casos:
            r = await c.get(f"/api/v1/reclamos/{CTX['rec_B']}", headers=_h(tok, valor))
            check(f"X-Municipio={valor!r} → {status} «{detalle}»",
                  r.status_code == status and r.json().get("detail") == detalle, f"{r.status_code} {r.text[:120]}")
    check("ninguno deja una fila request", await _accesos_desde(desde) == [])


async def test_header_ignorado_para_comunes() -> None:
    print("\n9. X-Municipio ignorado para las demás cuentas")
    await _contexto()
    async with _cliente() as c:
        tb = await _token(c, "admin.b@aislamiento.test")
        t1 = await _token(c, CTX["admin_1"])
        r = await c.get(f"/api/v1/reclamos/{CTX['rec_B']}", headers=_h(tb, 1))
        check("admin.b con X-Municipio 1 sigue viendo B", r.status_code == 200 and "AISLAB" in r.text,
              f"{r.status_code}")
        r = await c.get(f"/api/v1/reclamos/{CTX['rec_1']}", headers=_h(tb, 1))
        check("admin.b con X-Municipio 1 no ve el municipio 1", r.status_code == 404, f"{r.status_code}")
        r = await c.get(f"/api/v1/reclamos/{CTX['rec_B']}", headers=_h(t1, CTX["B"]))
        check("admin del 1 con X-Municipio B no ve B", r.status_code == 404, f"{r.status_code}")
        r = await c.get(f"/api/v1/reclamos/{CTX['rec_1']}", headers=_h(t1, CTX["B"]))
        check("admin del 1 con X-Municipio B sigue viendo el 1", r.status_code == 200, f"{r.status_code}")


async def test_super_degradado() -> None:
    print("\n10. Super administrador que deja de serlo")
    await _contexto()
    sup = CTX["id_super"]

    async def _set(sql: str) -> None:
        async with AsyncSessionLocal() as db:
            await db.execute(text(sql), {"u": sup})
            await db.commit()

    async with _cliente() as c:
        tok = await _token(c, EMAIL_SUPER)
        try:
            r = await c.get("/api/v1/auth/me", headers=_h(tok))
            check("vigente: /auth/me → 200", r.status_code == 200, f"{r.status_code} {r.text[:100]}")
            await _set("UPDATE usuarios SET nivel_acceso = 1, id_municipio = 1 WHERE id_usuario = :u")
            r = await c.get("/api/v1/auth/me", headers=_h(tok))
            check("pasado a nivel 1 → 401 sesión vencida",
                  r.status_code == 401 and r.json().get("detail") == SESION_VENCIDA, f"{r.status_code} {r.text[:100]}")
            await _set("UPDATE usuarios SET nivel_acceso = 0, id_municipio = NULL WHERE id_usuario = :u")
            await _set("UPDATE usuarios SET activo = FALSE WHERE id_usuario = :u")
            r = await c.get("/api/v1/auth/me", headers=_h(tok))
            check("desactivado → 401", r.status_code == 401, f"{r.status_code}")
        finally:
            await _set("UPDATE usuarios SET nivel_acceso = 0, id_municipio = NULL, activo = TRUE WHERE id_usuario = :u")
        r = await c.get("/api/v1/auth/me", headers=_h(tok))
        check("restaurado → 200", r.status_code == 200, f"{r.status_code}")


async def test_nivel_efectivo() -> None:
    print("\n11. Nivel efectivo 1 y módulos del super administrador")
    await _contexto()
    async with _cliente() as c:
        tok = await _token(c, EMAIL_SUPER)
        r = await c.put("/api/v1/config/identidad", json={"municipio_nombre": "AISLAB no se guarda"},
                        headers=_h(tok, CTX["B"]))
        check("pasa el guard de nivel 1 (identidad de B → 409, no 403)", r.status_code == 409,
              f"{r.status_code} {r.text[:120]}")
        me = (await c.get("/api/v1/auth/me", headers=_h(tok))).json()
        check("/auth/me: nivel 0, es_super_admin y el módulo municipios",
              me.get("nivel_acceso") == 0 and me.get("es_super_admin") is True
              and "municipios" in (me.get("modulos_permitidos") or []),
              str({k: me.get(k) for k in ("nivel_acceso", "es_super_admin")}))
        t1 = await _token(c, CTX["admin_1"])
        me1 = (await c.get("/api/v1/auth/me", headers=_h(t1))).json()
        check("un admin de nivel 1 no tiene municipios", "municipios" not in (me1.get("modulos_permitidos") or []),
              str(me1.get("modulos_permitidos")))
        check("y no es super administrador", me1.get("es_super_admin") is False, str(me1.get("es_super_admin")))


async def test_recuperar_super() -> None:
    print("\n12. Olvidé mi contraseña del super administrador")
    await _contexto()
    sup = CTX["id_super"]
    async with AsyncSessionLocal() as db:  # sin la pausa de 5 min entre mails (corridas seguidas)
        await db.execute(text("UPDATE usuarios SET fecha_ultimo_email_recovery = NULL WHERE id_usuario = :u"),
                         {"u": sup})
        await db.commit()
    async with _cliente() as c:
        _rate_limit._buckets.clear()
        r = await c.post("/api/v1/auth/recuperar-password", json={"email": EMAIL_SUPER})
        check("recuperar-password → 200", r.status_code == 200, f"{r.status_code}")
        async with AsyncSessionLocal() as db:
            tok_rec = (await db.execute(text("SELECT token_recovery::text FROM usuarios WHERE id_usuario = :u"),
                                        {"u": sup})).scalar()
        check("deja un token de reseteo en la cuenta", tok_rec is not None)
        if tok_rec is None:
            return
        r = await c.post("/api/v1/auth/resetear-password", json={"token": tok_rec, "password_nueva": "ClaveSuper2026"})
        check("resetear-password → 200", r.status_code == 200, f"{r.status_code} {r.text[:100]}")
        r = await _login(c, EMAIL_SUPER, clave="ClaveSuper2026")
        check("entra con la clave nueva", r.status_code == 200, f"{r.status_code}")
    import bcrypt
    async with AsyncSessionLocal() as db:  # vuelve a la clave de desarrollo
        await db.execute(text("UPDATE usuarios SET password_hash = :h, debe_cambiar_password = FALSE "
                              "WHERE id_usuario = :u"),
                         {"h": bcrypt.hashpw(CLAVE.encode(), bcrypt.gensalt()).decode(), "u": sup})
        await db.commit()


# ── Tarea 4: lo exclusivo del super administrador y escaladas ────────────────────────────────

async def _uno(sql: str, params: dict | None = None):
    async with AsyncSessionLocal() as db:
        return (await db.execute(text(sql), params or {})).fetchone()


async def test_escaladas_admin() -> None:
    print("\n13. Un administrador de municipio no puede escalar")
    await _contexto()
    victima = (await _uno("SELECT id_usuario FROM usuarios WHERE email = 'doble@aislamiento.test' "
                          "AND id_municipio = 1")).id_usuario
    estado = await _uno("SELECT id_estado_reclamo, nombre FROM estado_reclamo ORDER BY 1 LIMIT 1")
    async with _cliente() as c:
        t1 = await _token(c, CTX["admin_1"])
        h = _h(t1)
        r = await c.post("/api/v1/buc/usuarios", headers=h, json={
            "nivel_acceso": 0, "username": "smoke.f3.n0", "email": "smoke.f3.n0@prueba-aislamiento.com.ar",
            "es_externo": True})
        check("crear una cuenta de nivel 0 → 422", r.status_code == 422, f"{r.status_code} {r.text[:100]}")
        r = await c.put(f"/api/v1/buc/usuarios/{victima}", headers=h, json={"nivel_acceso": 0})
        check("pasar una cuenta a nivel 0 → 422", r.status_code == 422, f"{r.status_code} {r.text[:100]}")
        try:
            r = await c.put(f"/api/v1/admin/permisos/usuarios/{victima}/modulos", headers=h,
                            json={"overrides": [{"modulo_codigo": "municipios", "permitido": True}]})
            check("dar el módulo municipios por permiso individual → 422",
                  r.status_code == 422 and "exclusivo del super administrador" in r.text,
                  f"{r.status_code} {r.text[:120]}")
        finally:
            async with AsyncSessionLocal() as db:  # si quedó (antes del fix), se desactiva
                await db.execute(text("UPDATE usuario_modulos SET activo = FALSE "
                                      "WHERE id_usuario = :u AND modulo_codigo = 'municipios'"), {"u": victima})
                await db.commit()
        r = await c.get(f"/api/v1/buc/usuarios/{CTX['id_super']}", headers=h)
        check("ver la cuenta del super administrador → 404", r.status_code == 404, f"{r.status_code}")
        r = await c.put(f"/api/v1/buc/usuarios/{CTX['id_super']}", headers=h, json={"nombre": "x"})
        check("editar la cuenta del super administrador → 404", r.status_code == 404, f"{r.status_code}")
        try:
            r = await c.post("/api/v1/buc/usuarios", headers=h, json={
                "nivel_acceso": 5, "username": "smoke.f3.reservado", "email": EMAIL_SUPER, "es_externo": True})
            check("una cuenta con el email del super administrador → 409 reservado",
                  r.status_code == 409 and "reservado" in r.text, f"{r.status_code} {r.text[:120]}")
        finally:
            async with AsyncSessionLocal() as db:  # si se creó (antes del fix), se borra: rompería el login del super
                await db.execute(text("DELETE FROM usuarios WHERE username = 'smoke.f3.reservado'"))
                await db.commit()
        r = await c.put("/api/v1/admin/permisos/modulos/reclamos", headers=h, json={"min_nivel_acceso": 4})
        check("cambiar el catálogo global de módulos → 403", r.status_code == 403, f"{r.status_code}")
        r = await c.put(f"/api/v1/admin/estado_reclamo/{estado.id_estado_reclamo}", headers=h,
                        json={"nombre": estado.nombre})
        check("editar un Maestro global (estado_reclamo) → 403", r.status_code == 403, f"{r.status_code}")
        r = await c.get("/api/v1/admin/municipios", headers=h)
        check("leer Maestros → municipios → 403", r.status_code == 403, f"{r.status_code}")
        r = await c.get("/api/v1/admin/permisos/modulos", headers=h)
        check("el catálogo de módulos no le muestra municipios",
              r.status_code == 200 and all(m["modulo_codigo"] != "municipios" for m in r.json()),
              f"{r.status_code}")


async def test_global_super() -> None:
    print("\n14. El super administrador edita lo global")
    await _contexto()
    nac = await _uno("SELECT id, pais FROM nacionalidades ORDER BY id LIMIT 1")
    rec = await _uno("SELECT min_nivel_acceso FROM modulos WHERE modulo_codigo = 'reclamos'")
    mun1 = await _uno("SELECT nombre FROM municipios WHERE id_municipio = 1")
    desde = await _ultimo_acceso()
    async with _cliente() as c:
        tok = await _token(c, EMAIL_SUPER)
        r = await c.put("/api/v1/admin/permisos/modulos/reclamos", headers=_h(tok, 1),
                        json={"min_nivel_acceso": rec.min_nivel_acceso})
        check("catálogo de módulos → 200", r.status_code == 200, f"{r.status_code} {r.text[:100]}")
        r = await c.put(f"/api/v1/admin/nacionalidades/{nac.id}", headers=_h(tok, 1), json={"pais": nac.pais})
        check("Maestro global (nacionalidades) → 200", r.status_code == 200, f"{r.status_code} {r.text[:100]}")
        r = await c.get("/api/v1/admin/municipios", headers=_h(tok, 1))
        check("lee Maestros → municipios", r.status_code == 200, f"{r.status_code}")
        r = await c.put("/api/v1/admin/municipios/1", headers=_h(tok, 1), json={"nombre": mun1.nombre})
        check("municipios por Maestros → 403 «se editan desde el módulo Municipios»",
              r.status_code == 403 and "módulo Municipios" in r.text, f"{r.status_code} {r.text[:120]}")
        r = await c.get("/api/v1/admin/permisos/modulos", headers=_h(tok, 1))
        check("el catálogo le muestra municipios",
              r.status_code == 200 and any(m["modulo_codigo"] == "municipios" for m in r.json()), f"{r.status_code}")
    acciones = [f.accion for f in await _accesos_desde(desde)]
    check("dos filas catalogo_global", acciones.count("catalogo_global") == 2, str(acciones))


TESTS = [test_constraints_nivel_0, test_seed_super_admin, test_password_renovacion_global,
         test_registrar_acceso_super, test_registro_falla_cierra,
         test_login_super, test_header_super, test_header_invalido, test_header_ignorado_para_comunes,
         test_super_degradado, test_nivel_efectivo, test_recuperar_super,
         test_escaladas_admin, test_global_super]


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
