# -*- coding: utf-8 -*-
"""
Smoke in-process — alta de municipios y estado del municipio (IT-01 F4+F5,
PLAN_MULTI_MUNICIPIO_F4_F5.md). Crece tarea a tarea.

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_alta_municipio.py [prueba ...]

SOLO LOCAL. Mail en MOCK. Sin argumentos corre todas las pruebas; con nombres, solo esas.
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

from app.core.auth import (  # noqa: E402
    create_access_token, crear_token_ciudadano, crear_token_super_admin, hash_password)
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.core.municipio import invalidar_cache_municipios  # noqa: E402
from app.main import app  # noqa: E402

SUB_C = "c-prueba"
ORIGEN_C_ZGE = f"https://{SUB_C}.zge.zaris.com.ar"
ORIGEN_C_VECINOS = f"https://{SUB_C}.vecinos.zaris.com.ar"
EMAIL_C_N2 = "supervisor.c@prueba-aislamiento.com.ar"
EMAIL_C_N1 = "admin.c@prueba-aislamiento.com.ar"
EMAIL_C_N4 = "gestion.c@prueba-aislamiento.com.ar"
CLAVE = "123456"

RES: list[tuple[str, bool, str]] = []


def check(nombre: str, ok: bool, detalle: str = "") -> None:
    RES.append((nombre, ok, detalle))
    print(f"  {'OK  ' if ok else 'FAIL'} {nombre}{(' — ' + str(detalle)) if detalle and not ok else ''}")


async def _falla(db, sql: str, params: dict | None = None, texto: str = "") -> tuple[bool, str]:
    """Corre `sql` en un savepoint; True si falló (y, si se da `texto`, si el error lo contiene)."""
    try:
        async with db.begin_nested():
            await db.execute(text(sql), params or {})
        return False, "no falló"
    except DBAPIError as e:
        msg = str(e.orig)
        return (texto in msg) if texto else True, msg[:200]


async def _escalar(db, sql: str, params: dict | None = None):
    return (await db.execute(text(sql), params or {})).scalar()


def _cliente() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _estado(id_municipio: int, estado: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(text("UPDATE municipios SET estado = :e WHERE id_municipio = :m"),
                         {"e": estado, "m": id_municipio})
        await db.commit()
    invalidar_cache_municipios()


async def _municipio_c() -> dict:
    """Municipio de prueba C (local, se conserva): puesta_en_marcha, subdominio c-prueba, con sus
    módulos y dos cuentas (nivel 2 y nivel 1). Idempotente: deja C en puesta_en_marcha."""
    async with AsyncSessionLocal() as db:
        mid = await _escalar(db, "SELECT id_municipio FROM municipios WHERE subdominio = :s", {"s": SUB_C})
        if mid is None:
            mid = await _escalar(db, """
                INSERT INTO municipios (nombre, codigo_corto, subdominio, codigo_pais, pais, provincia,
                                        id_provincia, estado)
                VALUES ('Municipio de prueba C', 'CPR', :s, 'AR', 'Argentina', 'Buenos Aires',
                        (SELECT id_provincia FROM provincias WHERE codigo_pais = 'AR' AND nombre = 'Buenos Aires'),
                        'puesta_en_marcha')
                RETURNING id_municipio""", {"s": SUB_C})
        await db.execute(text("UPDATE municipios SET estado = 'puesta_en_marcha' WHERE id_municipio = :m "
                              "AND estado <> 'puesta_en_marcha'"), {"m": mid})
        await db.execute(text("""
            INSERT INTO municipio_modulo (id_municipio, modulo_codigo, habilitado, min_nivel_acceso)
            SELECT :m, modulo_codigo, TRUE, min_nivel_acceso FROM modulos WHERE activo
            ON CONFLICT (id_municipio, modulo_codigo) DO NOTHING"""), {"m": mid})
        ids = {}
        for email, nivel in ((EMAIL_C_N2, 2), (EMAIL_C_N1, 1), (EMAIL_C_N4, 4)):
            uid = await _escalar(db, "SELECT id_usuario FROM usuarios WHERE email = :e AND id_municipio = :m",
                                 {"e": email, "m": mid})
            if uid is None:
                uid = await _escalar(db, """
                    INSERT INTO usuarios (nombre, nivel_acceso, username, password_hash, id_municipio, activo,
                                          buc_acceso, email)
                    VALUES (:n, :nivel, :e, :h, :m, TRUE, FALSE, :e) RETURNING id_usuario""",
                    {"n": f"Prueba C nivel {nivel}", "nivel": nivel, "e": email, "h": hash_password(CLAVE),
                     "m": mid})
            ids[nivel] = uid
        await db.commit()
    invalidar_cache_municipios()
    return {"id": mid, "n2": ids[2], "n1": ids[1], "n4": ids[4]}


def _token(id_usuario: int, id_municipio: int) -> dict:
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": str(id_usuario), "mun": id_municipio, "sf": True})}


# ── Tarea 4 ───────────────────────────────────────────────────────────────────────────────────

async def test_base_f4() -> None:
    print("\ntest_base_f4")
    async with AsyncSessionLocal() as db:
        for tabla in ("paises", "municipio_modulo", "usuario_invitacion", "municipio_tarea"):
            check(f"existe la tabla {tabla}", await _escalar(db, "SELECT to_regclass(:t) IS NOT NULL",
                                                             {"t": f"public.{tabla}"}))
        cols = {r[0] for r in (await db.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'municipios'"))).all()}
        for c in ("estado", "fue_produccion", "estado_antes_baja", "max_usuarios_activos", "id_provincia",
                  "id_partido"):
            check(f"municipios.{c}", c in cols)
        check("area.es_sistema", await _escalar(db,
              "SELECT count(*) FROM information_schema.columns WHERE table_name = 'area' AND column_name = 'es_sistema'") == 1)
        check("municipio_tabla_clase.grupo", await _escalar(db,
              "SELECT count(*) FROM information_schema.columns WHERE table_name = 'municipio_tabla_clase' "
              "AND column_name = 'grupo'") == 1)
        if "estado" not in cols:
            return
        base = (await db.execute(text(
            "SELECT m.estado, p.nombre FROM municipios m LEFT JOIN provincias p USING (id_provincia) "
            "WHERE m.direccion_base"))).one()
        check("el municipio base está en demo con provincia Buenos Aires", tuple(base) == ("demo", "Buenos Aires"), base)
        malos = (await db.execute(text(
            "SELECT id_municipio, estado, activo FROM municipios WHERE NOT activo AND estado <> 'baja' "
            "OR estado = 'baja' AND activo"))).all()
        check("inactivo <=> baja", not malos, malos)
        check("6 áreas de sistema en el municipio base", await _escalar(db,
              "SELECT count(*) FROM area a JOIN municipios m USING (id_municipio) "
              "WHERE m.direccion_base AND a.es_sistema AND a.activo") == 6)
        n_mod = await _escalar(db, "SELECT count(*) FROM modulos WHERE activo")
        n_mm = await _escalar(db, "SELECT count(*) FROM municipio_modulo mm JOIN municipios m USING (id_municipio) "
                                  "WHERE m.direccion_base AND mm.habilitado")
        check("municipio_modulo del base = módulos activos", n_mod == n_mm, f"{n_mm} de {n_mod}")
        sin = (await db.execute(text(
            "SELECT tabla FROM municipio_tabla_clase WHERE clase <> 'global' AND grupo IS NULL"))).scalars().all()
        check("toda tabla no global tiene grupo", not sin, sin)
        check("paises: AR habilitado, VE no", await _escalar(db,
              "SELECT string_agg(codigo_pais || ':' || habilitado_para_alta, ',' ORDER BY codigo_pais) FROM paises")
              == "AR:true,VE:false")


async def test_triggers_f4() -> None:
    print("\ntest_triggers_f4")
    async with AsyncSessionLocal() as db:
        if await _escalar(db, "SELECT to_regclass('public.paises') IS NULL"):
            check("las tablas de F4 existen", False)
            return
        try:
            area = await _escalar(db, "SELECT id_area FROM area WHERE es_sistema LIMIT 1")
            ok, d = await _falla(db, "UPDATE area SET activo = false WHERE id_area = :a", {"a": area},
                                 "Es un área fija del sistema")
            check("un área de sistema no se da de baja", ok, d)
            prov = await _escalar(db, "SELECT id_provincia FROM provincias WHERE nombre = 'Buenos Aires'")
            ok, d = await _falla(db, "INSERT INTO municipios (nombre, codigo_pais, estado) VALUES ('M1','AR','modelo'),"
                                     "('M2','AR','modelo')", texto="uq_municipio_modelo")
            check("un solo municipio modelo", ok, d)
            ok, d = await _falla(db, "INSERT INTO municipios (nombre, codigo_pais, estado) "
                                     "VALUES ('Sin prov', 'AR', 'puesta_en_marcha')")
            check("puesta_en_marcha sin provincia falla", ok, d)
            mid = await _escalar(db, "INSERT INTO municipios (nombre, codigo_pais, estado, id_provincia, codigo_corto, "
                                     "subdominio) VALUES ('Prueba triggers', 'AR', 'puesta_en_marcha', :p, 'PTR', "
                                     "'prueba-triggers') RETURNING id_municipio", {"p": prov})
            await db.execute(text("UPDATE municipios SET estado = 'produccion' WHERE id_municipio = :m"), {"m": mid})
            check("pasar a produccion marca fue_produccion", await _escalar(db,
                  "SELECT fue_produccion FROM municipios WHERE id_municipio = :m", {"m": mid}) is True)
            await db.execute(text("UPDATE municipios SET estado = 'puesta_en_marcha', fue_produccion = false "
                                  "WHERE id_municipio = :m"), {"m": mid})
            check("fue_produccion no vuelve a false", await _escalar(db,
                  "SELECT fue_produccion FROM municipios WHERE id_municipio = :m", {"m": mid}) is True)
            await db.execute(text("UPDATE municipios SET estado = 'baja' WHERE id_municipio = :m"), {"m": mid})
            fila = (await db.execute(text("SELECT activo, estado_antes_baja FROM municipios WHERE id_municipio = :m"),
                                     {"m": mid})).one()
            check("baja pone activo = false y recuerda el estado anterior",
                  tuple(fila) == (False, "puesta_en_marcha"), fila)
            await db.execute(text("UPDATE municipios SET estado = 'puesta_en_marcha' WHERE id_municipio = :m"),
                             {"m": mid})
            check("reactivar pone activo = true", await _escalar(db,
                  "SELECT activo FROM municipios WHERE id_municipio = :m", {"m": mid}) is True)
            ok, d = await _falla(db, "UPDATE municipios SET codigo_pais = 'VE' WHERE id_municipio = :m", {"m": mid},
                                 "provincia")
            check("la provincia tiene que ser del país del municipio", ok, d)
        finally:
            await db.rollback()


async def test_acciones_super() -> None:
    print("\ntest_acciones_super")
    from app.services.accesos_super import ACCIONES, registrar_acceso_super
    nuevas = {"municipio_alta", "municipio_estado", "municipio_modulos", "exportacion", "vaciado",
              "super_alta", "super_baja"}
    check("ACCIONES incluye las de F4", nuevas <= set(ACCIONES), nuevas - set(ACCIONES))
    async with AsyncSessionLocal() as db:
        uid = await _escalar(db, "SELECT id_usuario FROM usuarios ORDER BY nivel_acceso, id_usuario LIMIT 1")
        antes = await _escalar(db, "SELECT coalesce(max(id_super_admin_acceso), 0) FROM super_admin_acceso")
    try:
        await registrar_acceso_super(id_usuario=uid, accion="vaciado", id_municipio=None, detalle="smoke F4")
    except Exception as e:  # el 503 de la API, si el CHECK lo rechaza
        check("registrar_acceso_super acepta vaciado", False, repr(e)[:200])
        return
    async with AsyncSessionLocal() as db:
        check("registrar_acceso_super acepta vaciado", await _escalar(db,
              "SELECT count(*) FROM super_admin_acceso WHERE id_super_admin_acceso > :a AND accion = 'vaciado'",
              {"a": antes}) == 1)


# ── Tarea 5 ───────────────────────────────────────────────────────────────────────────────────

async def test_estado_baja() -> None:
    print("\ntest_estado_baja")
    C = await _municipio_c()
    async with _cliente() as c:
        def login():
            return c.post("/api/v1/auth/login", json={"identificador": EMAIL_C_N2, "password": CLAVE},
                          headers={"Origin": ORIGEN_C_ZGE})
        r = await login()
        check("C en puesta_en_marcha: login 200", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
        h = {"Origin": ORIGEN_C_ZGE}
        if r.status_code == 200:
            h["Authorization"] = f"Bearer {r.json()['access_token']}"
        await _estado(C["id"], "baja")
        try:
            r = await login()
            check("C en baja: login desde su subdominio 404 (como uno inexistente)", r.status_code == 404,
                  f"{r.status_code} {r.text[:120]}")
            r = await c.get("/api/v1/auth/me", headers=h)
            check("C en baja: el token vigente da 401", r.status_code == 401, f"{r.status_code} {r.text[:120]}")
            r = await c.get("/api/v1/auth/me", headers=_token(C["n2"], C["id"]))
            check("C en baja: token sin Origin también 401", r.status_code == 401, f"{r.status_code}")
            r = await c.get("/api/v1/publico/identidad-municipio", headers={"Origin": ORIGEN_C_VECINOS})
            check("C en baja: identidad pública por origen 404", r.status_code == 404, f"{r.status_code}")
            r = await c.get("/api/v1/publico/alta/identidad", params={"m": "CPR"})
            check("C en baja: alta-vecino con ?m= 404", r.status_code == 404, f"{r.status_code}")
        finally:
            await _estado(C["id"], "puesta_en_marcha")
        r = await login()
        check("C reactivado: login 200", r.status_code == 200, f"{r.status_code}")
        r = await c.get("/api/v1/publico/identidad-municipio", headers={"Origin": ORIGEN_C_VECINOS})
        check("C reactivado: identidad pública 200", r.status_code == 200, f"{r.status_code}")
        r = await c.get("/api/v1/publico/alta/identidad", params={"m": "CPR"})
        check("C reactivado: alta-vecino con ?m= 200", r.status_code == 200, f"{r.status_code}")


async def test_modelo_no_operable() -> None:
    print("\ntest_modelo_no_operable")
    async with AsyncSessionLocal() as db:
        modelo = (await db.execute(text(
            "SELECT id_municipio, subdominio, codigo_corto FROM municipios WHERE estado = 'modelo'"))).first()
        propio = modelo is None
        if propio:
            # Sin el modelo real (Tarea 12): uno de prueba con subdominio, para probar también el origen.
            mid = await _escalar(db, "SELECT id_municipio FROM municipios WHERE subdominio = 'modelo-smoke'")
            if mid is None:
                mid = await _escalar(db, """
                    INSERT INTO municipios (nombre, codigo_corto, subdominio, codigo_pais, estado)
                    VALUES ('Modelo de prueba (smoke)', 'MSM', 'modelo-smoke', 'AR', 'modelo')
                    RETURNING id_municipio""")
            else:
                await db.execute(text("UPDATE municipios SET estado = 'modelo' WHERE id_municipio = :m"), {"m": mid})
            if not await _escalar(db, "SELECT 1 FROM area WHERE id_municipio = :m", {"m": mid}):
                await db.execute(text("INSERT INTO area (nombre, activo, id_municipio) "
                                      "VALUES ('Área del modelo (smoke)', TRUE, :m)"), {"m": mid})
            await db.commit()
            modelo = (await db.execute(text(
                "SELECT id_municipio, subdominio, codigo_corto FROM municipios WHERE id_municipio = :m"),
                {"m": mid})).first()
        super_id = await _escalar(db, "SELECT id_usuario FROM usuarios WHERE nivel_acceso = 0 "
                                      "AND id_municipio IS NULL AND activo ORDER BY id_usuario LIMIT 1")
    invalidar_cache_municipios()
    try:
        async with _cliente() as c:
            if modelo.subdominio:
                r = await c.get("/api/v1/publico/identidad-municipio",
                                headers={"Origin": f"https://{modelo.subdominio}.vecinos.zaris.com.ar"})
                check("el modelo no resuelve por origen (404)", r.status_code == 404, f"{r.status_code}")
            r = await c.get("/api/v1/publico/alta/identidad", params={"m": modelo.codigo_corto})
            check("el modelo no resuelve por slug (404)", r.status_code == 404, f"{r.status_code}")
            if super_id is None:
                check("hay un super administrador local (correr smoke_super_admin.py)", False)
                return
            h = {"Authorization": "Bearer " + crear_token_super_admin(super_id, segundo_factor=True),
                 "X-Municipio": str(modelo.id_municipio)}
            r = await c.get("/api/v1/admin/area", headers=h)
            check("el super con X-Municipio del modelo lista sus áreas",
                  r.status_code == 200 and len(r.json()) > 0, f"{r.status_code} {r.text[:120]}")
    finally:
        if propio:
            await _estado(modelo.id_municipio, "baja")


async def test_demo_por_estado() -> None:
    print("\ntest_demo_por_estado")
    C = await _municipio_c()
    async with AsyncSessionLocal() as db:
        demo = (await db.execute(text(
            "SELECT u.id_usuario, u.id_municipio FROM usuarios u JOIN municipios m USING (id_municipio) "
            "WHERE m.estado = 'demo' AND m.direccion_base AND u.nivel_acceso = 1 AND u.activo "
            "ORDER BY u.id_usuario LIMIT 1"))).first()
    url = "/api/v1/demo/poblar/abcdef012345"  # corrida inexistente: autorizado = 404, no autorizado = 401
    async with _cliente() as c:
        r = await c.get(url, headers=_token(demo.id_usuario, demo.id_municipio))
        check("el administrador del municipio demo sigue autorizado", r.status_code == 404, f"{r.status_code}")
        r = await c.get(url, headers=_token(C["n1"], C["id"]))
        check("el administrador de C (puesta_en_marcha) no", r.status_code == 401, f"{r.status_code}")


# ── Tarea 6 ───────────────────────────────────────────────────────────────────────────────────

async def _super_headers(db) -> dict:
    sid = await _escalar(db, "SELECT id_usuario FROM usuarios WHERE nivel_acceso = 0 AND id_municipio IS NULL "
                             "AND activo ORDER BY id_usuario LIMIT 1")
    return {"Authorization": "Bearer " + crear_token_super_admin(sid, segundo_factor=True)}


async def test_geo_catalogo() -> None:
    print("\ntest_geo_catalogo")
    C = await _municipio_c()
    h = _token(C["n2"], C["id"])
    async with _cliente() as c:
        r = await c.get("/api/v1/geo/paises", params={"para_alta": "true"}, headers=h)
        check("paises para el alta = solo AR", r.status_code == 200 and [p["codigo_pais"] for p in r.json()] == ["AR"],
              f"{r.status_code} {r.text[:160]}")
        if r.status_code == 200 and r.json():
            p = r.json()[0]
            check("el país trae sus etiquetas de nivel", p.get("etiqueta_nivel_1") == "Provincia"
                  and p.get("etiqueta_nivel_2") == "Partido", p)
        r = await c.get("/api/v1/geo/paises", headers=h)
        check("paises sin filtro incluye VE", r.status_code == 200 and "VE" in [p["codigo_pais"] for p in r.json()],
              f"{r.status_code}")
        r = await c.get("/api/v1/geo/provincias", params={"codigo_pais": "AR"}, headers=h)
        check("provincias de AR = 24", r.status_code == 200 and len(r.json()) == 24, f"{r.status_code} {len(r.json())}")
        r = await c.get("/api/v1/geo/provincias", params={"codigo_pais": "VE"}, headers=h)
        check("provincias de VE = 0 (todavía no se cargaron)", r.status_code == 200 and r.json() == [], f"{r.status_code}")


async def test_municipio_provincia() -> None:
    print("\ntest_municipio_provincia")
    C = await _municipio_c()
    async with AsyncSessionLocal() as db:
        h = await _super_headers(db)
        ba = await _escalar(db, "SELECT id_provincia FROM provincias WHERE codigo_pais = 'AR' AND nombre = 'Buenos Aires'")
        cba = await _escalar(db, "SELECT id_provincia FROM provincias WHERE codigo_pais = 'AR' AND nombre ILIKE 'C_rdoba'")
        partido_cba = await _escalar(db, "SELECT id_partido FROM partidos WHERE id_provincia = :p LIMIT 1", {"p": cba})
    base = {"nombre": "Municipio de prueba C", "subdominio": SUB_C, "codigo_pais": "AR",
            "zona_horaria": "America/Argentina/Buenos_Aires", "id_provincia": ba, "id_partido": None}
    async with _cliente() as c:
        r = await c.put(f"/api/v1/super/municipios/{C['id']}", json={**base, "codigo_pais": "VE"}, headers=h)
        check("PUT con una provincia que no es del país → 422", r.status_code == 422, f"{r.status_code} {r.text[:160]}")
        r = await c.put(f"/api/v1/super/municipios/{C['id']}", json={**base, "id_partido": partido_cba}, headers=h)
        check("PUT con un partido de otra provincia → 422", r.status_code == 422, f"{r.status_code} {r.text[:160]}")
        r = await c.put(f"/api/v1/super/municipios/{C['id']}", json={**base, "id_provincia": cba}, headers=h)
        j = r.json() if r.status_code == 200 else {}
        check("PUT con Córdoba → 200 y provincia_nombre", r.status_code == 200
              and j.get("provincia_nombre", "").startswith("C") and j.get("pais_nombre") == "Argentina",
              f"{r.status_code} {r.text[:200]}")
        check("la salida trae estado, etiquetas y cuentas activas",
              j.get("estado") == "puesta_en_marcha" and j.get("etiqueta_nivel_1") == "Provincia"
              and j.get("cuentas_activas", 0) >= 2, j)
        r = await c.get("/api/v1/super/municipios", params={"id_provincia": cba}, headers=h)
        check("filtro por provincia", r.status_code == 200 and [m["id_municipio"] for m in r.json()] == [C["id"]],
              f"{r.status_code} {r.text[:160]}")
        r = await c.get("/api/v1/super/municipios", params={"estado": "demo"}, headers=h)
        check("filtro por estado", r.status_code == 200 and all(m["estado"] == "demo" for m in r.json())
              and len(r.json()) >= 1, f"{r.status_code}")
        r = await c.put(f"/api/v1/super/municipios/{C['id']}", json=base, headers=h)
        check("vuelve a Buenos Aires", r.status_code == 200 and r.json().get("provincia_nombre") == "Buenos Aires",
              f"{r.status_code}")
        async with AsyncSessionLocal() as db:
            texto = (await db.execute(text("SELECT pais, provincia FROM municipios WHERE id_municipio = :m"),
                                      {"m": C["id"]})).one()
        check("el texto de país y provincia se deriva del catálogo", tuple(texto) == ("Argentina", "Buenos Aires"),
              texto)


# ── Tarea 7 ───────────────────────────────────────────────────────────────────────────────────

async def _modulos(id_municipio: int, **estado: bool) -> None:
    """Fija `habilitado` de los módulos dados en el municipio (y el resto, habilitado) e invalida la caché."""
    from app.services.municipios.modulos import invalidar_modulos
    async with AsyncSessionLocal() as db:
        await db.execute(text("UPDATE municipio_modulo SET habilitado = TRUE, min_nivel_acceso = m.min_nivel_acceso "
                              "FROM modulos m WHERE m.modulo_codigo = municipio_modulo.modulo_codigo "
                              "AND id_municipio = :mun"), {"mun": id_municipio})
        for codigo, hab in estado.items():
            await db.execute(text("UPDATE municipio_modulo SET habilitado = :h WHERE id_municipio = :mun "
                                  "AND modulo_codigo = :c"), {"h": hab, "mun": id_municipio, "c": codigo})
        await db.commit()
    invalidar_modulos(id_municipio)


async def _admin_base(db) -> tuple[int, int]:
    r = (await db.execute(text(
        "SELECT u.id_usuario, u.id_municipio FROM usuarios u JOIN municipios m USING (id_municipio) "
        "WHERE m.direccion_base AND u.nivel_acceso = 1 AND u.activo ORDER BY u.id_usuario LIMIT 1"))).first()
    return r.id_usuario, r.id_municipio


async def test_modulo_404() -> None:
    print("\ntest_modulo_404")
    C = await _municipio_c()
    await _modulos(C["id"], reclamos=False, encuestas=False)
    async with AsyncSessionLocal() as db:
        uid_base, mun_base = await _admin_base(db)
    try:
        async with _cliente() as c:
            r = await c.get("/api/v1/reclamos", headers=_token(C["n1"], C["id"]))
            check("admin de C: GET /reclamos 404", r.status_code == 404, f"{r.status_code} {r.text[:100]}")
            r = await c.get("/api/v1/admin/encuestas/plantillas", headers=_token(C["n1"], C["id"]))
            check("admin de C: encuestas 404", r.status_code == 404, f"{r.status_code}")
            h_vec = {"Authorization": "Bearer " + crear_token_ciudadano(1, C["id"]), "Origin": ORIGEN_C_VECINOS}
            r = await c.get("/api/v1/publico/reclamos", headers=h_vec)
            check("vecino de C: GET /publico/reclamos 404", r.status_code == 404, f"{r.status_code} {r.text[:100]}")
            r = await c.get("/api/v1/publico/identidad-municipio", headers={"Origin": ORIGEN_C_VECINOS})
            mods = r.json().get("modulos_habilitados") if r.status_code == 200 else None
            check("identidad de C sin reclamos ni encuestas", isinstance(mods, list) and "reclamos" not in mods
                  and "encuestas" not in mods and "turnos" in mods, f"{r.status_code} {mods}")
            r = await c.get("/api/v1/reclamos", headers=_token(uid_base, mun_base))
            check("admin del municipio base: GET /reclamos 200", r.status_code == 200, f"{r.status_code}")
            r = await c.get("/api/v1/publico/identidad-municipio")
            mods = r.json().get("modulos_habilitados") if r.status_code == 200 else None
            check("identidad del municipio base con reclamos", isinstance(mods, list) and "reclamos" in mods, mods)
            r = await c.get("/api/v1/config/identidad", headers={"Origin": ORIGEN_C_ZGE})
            mods = r.json().get("modulos_habilitados") if r.status_code == 200 else None
            check("/config/identidad trae los módulos habilitados", isinstance(mods, list) and "reclamos" not in mods,
                  f"{r.status_code} {mods}")
    finally:
        await _modulos(C["id"])


async def test_modulos_permitidos_municipio() -> None:
    print("\ntest_modulos_permitidos_municipio")
    C = await _municipio_c()
    await _modulos(C["id"], reclamos=False)
    async with AsyncSessionLocal() as db:
        await db.execute(text("""
            INSERT INTO usuario_modulos (id_usuario, modulo_codigo, permitido, motivo, id_municipio)
            SELECT :u, 'reclamos', TRUE, 'smoke F4', :m
             WHERE NOT EXISTS (SELECT 1 FROM usuario_modulos WHERE id_usuario = :u AND modulo_codigo = 'reclamos')
        """), {"u": C["n4"], "m": C["id"]})
        await db.execute(text("UPDATE usuario_modulos SET permitido = TRUE, activo = TRUE "
                              "WHERE id_usuario = :u AND modulo_codigo = 'reclamos'"), {"u": C["n4"]})
        await db.commit()
    try:
        async with _cliente() as c:
            r = await c.get("/api/v1/auth/me", headers=_token(C["n4"], C["id"]))
            mods = r.json().get("modulos_permitidos") if r.status_code == 200 else None
            check("un override no habilita un módulo apagado", isinstance(mods, list) and "reclamos" not in mods
                  and "turnos" in mods, f"{r.status_code} {mods}")
    finally:
        await _modulos(C["id"])
    async with _cliente() as c:
        r = await c.get("/api/v1/auth/me", headers=_token(C["n4"], C["id"]))
        check("con el módulo prendido, el override vuelve a valer",
              "reclamos" in (r.json().get("modulos_permitidos") or []), r.status_code)


async def test_nivel_por_municipio() -> None:
    print("\ntest_nivel_por_municipio")
    C = await _municipio_c()
    await _modulos(C["id"])
    async with AsyncSessionLocal() as db:
        n4_base = (await db.execute(text(
            "SELECT u.id_usuario, u.id_municipio FROM usuarios u JOIN municipios m USING (id_municipio) "
            "WHERE m.direccion_base AND u.nivel_acceso = 4 AND u.activo AND NOT EXISTS (SELECT 1 FROM usuario_modulos um "
            "WHERE um.id_usuario = u.id_usuario AND um.modulo_codigo = 'turnos' AND um.activo) "
            "ORDER BY u.id_usuario LIMIT 1"))).first()
    try:
        async with _cliente() as c:
            r = await c.put("/api/v1/admin/permisos/modulos/turnos", json={"min_nivel_acceso": 2},
                            headers=_token(C["n1"], C["id"]))
            check("el admin de C sube turnos a nivel 2", r.status_code == 200 and r.json().get("min_nivel_acceso") == 2,
                  f"{r.status_code} {r.text[:160]}")
            r = await c.get("/api/v1/auth/me", headers=_token(C["n4"], C["id"]))
            check("un nivel 4 de C ya no ve turnos", "turnos" not in (r.json().get("modulos_permitidos") or ["turnos"]),
                  r.status_code)
            r = await c.get("/api/v1/auth/me", headers=_token(n4_base.id_usuario, n4_base.id_municipio))
            check("un nivel 4 del municipio base lo sigue viendo", "turnos" in (r.json().get("modulos_permitidos") or []),
                  r.status_code)
            r = await c.put("/api/v1/admin/permisos/modulos/turnos", json={"habilitado": False},
                            headers=_token(C["n1"], C["id"]))
            check("el admin no habilita ni deshabilita (solo el super)", r.status_code == 403, f"{r.status_code}")
            r = await c.put("/api/v1/admin/permisos/modulos/municipios", json={"min_nivel_acceso": 1},
                            headers=_token(C["n1"], C["id"]))
            check("los módulos de nivel 0 no existen para el admin", r.status_code == 404, f"{r.status_code}")
    finally:
        await _modulos(C["id"])


async def test_dependencias() -> None:
    print("\ntest_dependencias")
    C = await _municipio_c()
    async with AsyncSessionLocal() as db:
        h = {**await _super_headers(db), "X-Municipio": str(C["id"])}
    try:
        await _modulos(C["id"], agenda=False, turnos=False, entradas=False)
        async with _cliente() as c:
            r = await c.put("/api/v1/admin/permisos/modulos/turnos", json={"habilitado": True}, headers=h)
            check("habilitar turnos con agenda apagado → 422", r.status_code == 422
                  and "turnos necesita agenda habilitado" in r.text, f"{r.status_code} {r.text[:160]}")
        await _modulos(C["id"])
        async with _cliente() as c:
            r = await c.put("/api/v1/admin/permisos/modulos/agenda", json={"habilitado": False}, headers=h)
            check("deshabilitar agenda con turnos prendido → 422", r.status_code == 422, f"{r.status_code} {r.text[:160]}")
            r = await c.put("/api/v1/admin/permisos/modulos/usuarios", json={"habilitado": False}, headers=h)
            check("un módulo fijo no se deshabilita → 422", r.status_code == 422, f"{r.status_code}")
            r = await c.put("/api/v1/admin/permisos/modulos/bi", json={"habilitado": False}, headers=h)
            check("el super deshabilita bi → 200", r.status_code == 200 and r.json().get("habilitado") is False,
                  f"{r.status_code} {r.text[:160]}")
            async with AsyncSessionLocal() as db:
                n = await _escalar(db, "SELECT count(*) FROM super_admin_acceso WHERE accion = 'municipio_modulos' "
                                       "AND id_municipio = :m AND fecha_hora > NOW() - INTERVAL '1 minute'", {"m": C["id"]})
            check("queda registrado como municipio_modulos", n >= 1, n)
    finally:
        await _modulos(C["id"])


async def test_efectos_apagados() -> None:
    print("\ntest_efectos_apagados")
    from app.services.encuestas_service import encuestas_estan_activas
    C = await _municipio_c()
    async with AsyncSessionLocal() as db:
        await db.execute(text("""
            INSERT INTO configuracion_general (clave, valor, tipo, descripcion, activo, id_municipio)
            VALUES ('encuestas_activas', 'true', 'boolean', 'smoke F4', TRUE, :m)
            ON CONFLICT DO NOTHING"""), {"m": C["id"]})
        await db.execute(text("UPDATE configuracion_general SET valor = 'true' WHERE clave = 'encuestas_activas' "
                              "AND id_municipio = :m"), {"m": C["id"]})
        await db.commit()
    try:
        await _modulos(C["id"])
        async with AsyncSessionLocal() as db:
            check("con encuestas prendido, se encuesta", await encuestas_estan_activas(db, id_municipio=C["id"]))
        await _modulos(C["id"], encuestas=False, emergencias=False)
        async with AsyncSessionLocal() as db:
            check("con encuestas apagado no se crean envíos (guarda de todos los disparos)",
                  not await encuestas_estan_activas(db, id_municipio=C["id"]))
            antes = await _escalar(db, "SELECT count(*) FROM emergencia_atencion WHERE id_municipio = :m", {"m": C["id"]})
        async with _cliente() as c:
            r = await c.get("/api/v1/turnos/guardia/atenciones", headers=_token(C["n1"], C["id"]))
            check("con emergencias apagado, la Guardia responde 404", r.status_code == 404, f"{r.status_code}")
            r = await c.patch("/api/v1/turnos/guardia/atenciones/1/atender", json={}, headers=_token(C["n1"], C["id"]))
            check("y no atiende (404)", r.status_code == 404, f"{r.status_code}")
        async with AsyncSessionLocal() as db:
            check("no se escribió emergencia_atencion", antes == await _escalar(
                db, "SELECT count(*) FROM emergencia_atencion WHERE id_municipio = :m", {"m": C["id"]}))
    finally:
        await _modulos(C["id"])


# ── Tarea 9 ───────────────────────────────────────────────────────────────────────────────────

async def test_links_por_municipio() -> None:
    print("\ntest_links_por_municipio")
    import re
    import app.services.email as em
    from app.core.urls import base_app, url_alta_publica, url_publica
    from app.services.notificaciones import _url_absoluta_tramite
    C = await _municipio_c()
    async with AsyncSessionLocal() as db:
        B = await _escalar(db, "SELECT id_municipio FROM municipios WHERE subdominio = 'aislamiento'")
        base, cod_base = (await db.execute(text(
            "SELECT id_municipio, codigo_corto FROM municipios WHERE direccion_base"))).one()
        email_base = await _escalar(db, "SELECT email FROM usuarios WHERE id_municipio = :m AND nivel_acceso = 2 "
                                        "AND activo AND email LIKE '%@%' ORDER BY id_usuario LIMIT 1", {"m": base})
        await db.execute(text("UPDATE usuarios SET fecha_ultimo_email_recovery = NULL WHERE email IN (:a, :b)"),
                         {"a": EMAIL_C_N2, "b": email_base})
        await db.execute(text("UPDATE ciudadano_credencial SET fecha_ultimo_email_recovery = NULL "
                              "WHERE id_ciudadano IN (SELECT id_ciudadano FROM ciudadanos WHERE doc_nro IN "
                              "('97000001', '28547123'))"))
        await db.commit()
    zge_c, vec_b = f"https://{SUB_C}.zge.zaris.com.ar", "https://aislamiento.vecinos.zaris.com.ar"
    zge_base, vec_base = url_publica(settings.FRONTEND_BASE_URL), url_publica(settings.APP_VECINOS_FRONTEND_URL)

    capturados: list[str] = []

    async def captura(to, subject, body_html, body_text=None, from_override=None):
        capturados.append(body_html or "")
        return True

    def links() -> list[str]:
        return [h for html in capturados for h in re.findall(r'href="(https?://[^"]+)"', html)]

    original = em.enviar_mail
    em.enviar_mail = captura
    try:
        async with _cliente() as c:
            casos = [
                ("recuperar clave del funcionario de C", "/api/v1/auth/recuperar-password",
                 {"email": EMAIL_C_N2}, {"Origin": ORIGEN_C_ZGE}, zge_c, zge_base),
                ("recuperar clave del funcionario del base", "/api/v1/auth/recuperar-password",
                 {"email": email_base}, {}, zge_base, zge_c),
                ("recuperar clave del vecino de B", "/api/v1/publico/auth/recuperar-password",
                 {"dni": "97000001"}, {"Origin": "https://aislamiento.vecinos.zaris.com.ar"}, vec_b, vec_base),
                ("recuperar clave del vecino del base", "/api/v1/publico/auth/recuperar-password",
                 {"dni": "28547123"}, {}, vec_base, vec_b),
            ]
            for nombre, ruta, body, h, esperado, ajeno in casos:
                capturados.clear()
                r = await c.post(ruta, json=body, headers=h)
                ls = links()
                check(f"{nombre}: los links van a {esperado}", r.status_code == 200 and bool(ls)
                      and any(x.startswith(esperado) for x in ls) and not any(x.startswith(ajeno) for x in ls),
                      f"{r.status_code} {ls[:3]}")
    finally:
        em.enviar_mail = original

    async with AsyncSessionLocal() as db:
        check("base_app de C para agentes", await base_app(db, C["id"], "agentes") == f"https://{SUB_C}.agentes.zaris.com.ar")
        check("base_app del base = la setting de siempre", await base_app(db, base, "zge") == zge_base)
        check("base_app api = una sola API", await base_app(db, C["id"], "api") == url_publica(settings.API_PUBLIC_BASE_URL))
        check("alta pública de C sin ?m=", await url_alta_publica(db, C["id"]) == f"{zge_c}/frontend/alta-vecino.html",
              await url_alta_publica(db, C["id"]))
        check("alta pública del base con ?m=", (await url_alta_publica(db, base) or "").endswith(f"?m={cod_base.lower()}"),
              await url_alta_publica(db, base))
        check("link de trámite de C", (await _url_absoluta_tramite(db, C["id"], "EXP-1")).startswith(f"{zge_c}/#/tramites/"))
        mid = await _escalar(db, "SELECT id_municipio FROM municipios WHERE subdominio IS NULL AND NOT direccion_base "
                                 "ORDER BY id_municipio LIMIT 1")
        if mid:
            check("municipio sin subdominio: sin link", await base_app(db, mid, "vecinos") == "")


# ── Tarea 10 ──────────────────────────────────────────────────────────────────────────────────

def _cuil(dni: str) -> str:
    base = "27" + dni.zfill(8)
    dv = 11 - sum(int(d) * f for d, f in zip(base, (5, 4, 3, 2, 7, 6, 5, 4, 3, 2))) % 11
    return base + ("0" if dv == 11 else "9" if dv == 10 else str(dv))


async def test_alta_por_origen() -> None:
    print("\ntest_alta_por_origen")
    import random
    C = await _municipio_c()
    async with AsyncSessionLocal() as db:
        base, cod_base = (await db.execute(text(
            "SELECT id_municipio, codigo_corto FROM municipios WHERE direccion_base"))).one()
    async with _cliente() as c:
        r = await c.get("/api/v1/publico/alta/identidad", headers={"Origin": ORIGEN_C_ZGE})
        check("identidad sin ?m= desde el subdominio de C → C",
              r.status_code == 200 and r.json().get("municipio_slug") == "CPR", f"{r.status_code} {r.text[:120]}")
        r = await c.get("/api/v1/publico/alta/identidad", params={"m": cod_base}, headers={"Origin": ORIGEN_C_ZGE})
        check("con ?m= del base desde el subdominio de C → gana el slug",
              r.status_code == 200 and r.json().get("municipio_slug") == cod_base, f"{r.status_code} {r.text[:120]}")
        r = await c.get("/api/v1/publico/alta/identidad")
        check("sin ?m= y sin Origin → el municipio base",
              r.status_code == 200 and r.json().get("municipio_slug") == cod_base, f"{r.status_code} {r.text[:120]}")
        r = await c.get("/api/v1/publico/alta/nacionalidades", headers={"Origin": ORIGEN_C_ZGE})
        check("nacionalidades sin ?m= desde C", r.status_code == 200, f"{r.status_code}")
        dni = str(random.randint(46_000_000, 46_999_999))
        ficha = {"doc_nro": dni, "cuil": _cuil(dni), "nombre": "Vecina", "apellido": f"OrigenC{dni[-4:]}",
                 "sexo": "MUJER", "fecha_nac": "1990-05-10", "id_nacionalidad": 1, "calle": "Av. Maipú 950",
                 "localidad": "Vicente López", "provincia": "Buenos Aires", "latitud": -34.5263,
                 "longitud": -58.4727, "telefono": "11 4444 5566",
                 "email": f"alta.origen.{dni}@prueba-aislamiento.com.ar", "password": "demoalta123"}
        r = await c.post("/api/v1/publico/alta/cuenta", json=ficha, headers={"Origin": ORIGEN_C_ZGE})
        check("alta en un paso sin municipio_slug desde C → 201", r.status_code == 201, f"{r.status_code} {r.text[:160]}")
    async with AsyncSessionLocal() as db:
        mun = await _escalar(db, "SELECT id_municipio FROM ciudadanos WHERE doc_nro = :d", {"d": dni})
    check("la ficha queda en C", mun == C["id"], mun)


# ── Tarea 11 ──────────────────────────────────────────────────────────────────────────────────

AREAS_FIJAS = ("Secretaría de Gobierno", "Secretaría de Planeamiento y Obras Públicas", "Secretaría de Salud",
               "Secretaría de Seguridad", "Secretaría de Servicios Públicos", "Subsecretaría de Tránsito")


async def _modelo_minimo() -> tuple[int, bool]:
    """El municipio modelo: el real si existe; si no, 'modelo-smoke' armado con lo mínimo (6 áreas fijas,
    una subárea de Gobierno, un tipo de reclamo y las claves de configuración del base). Devuelve
    (id, propio): si es propio, al terminar vuelve a baja (para no bloquear la Tarea 12)."""
    async with AsyncSessionLocal() as db:
        mid = await _escalar(db, "SELECT id_municipio FROM municipios WHERE estado = 'modelo'")
        if mid:
            return mid, False
        mid = await _escalar(db, "SELECT id_municipio FROM municipios WHERE subdominio = 'modelo-smoke'")
        if mid is None:
            mid = await _escalar(db, "INSERT INTO municipios (nombre, codigo_corto, subdominio, codigo_pais, estado) "
                                     "VALUES ('Modelo de prueba (smoke)', 'MSM', 'modelo-smoke', 'AR', 'modelo') "
                                     "RETURNING id_municipio")
        await db.execute(text("UPDATE municipios SET estado = 'modelo' WHERE id_municipio = :m"), {"m": mid})
        for nombre in AREAS_FIJAS:
            if not await _escalar(db, "SELECT 1 FROM area WHERE id_municipio = :m AND nombre = :n", {"m": mid, "n": nombre}):
                await db.execute(text("INSERT INTO area (nombre, activo, es_sistema, id_municipio) VALUES (:n, TRUE, TRUE, :m)"),
                                 {"n": nombre, "m": mid})
        gob = await _escalar(db, "SELECT id_area FROM area WHERE id_municipio = :m AND nombre = 'Secretaría de Gobierno'", {"m": mid})
        if not await _escalar(db, "SELECT 1 FROM subarea WHERE id_municipio = :m", {"m": mid}):
            await db.execute(text("INSERT INTO subarea (nombre, id_area, activo, id_municipio) "
                                  "VALUES ('Mesa de Entradas', :a, TRUE, :m)"), {"a": gob, "m": mid})
        sub = await _escalar(db, "SELECT id_subarea FROM subarea WHERE id_municipio = :m LIMIT 1", {"m": mid})
        if not await _escalar(db, "SELECT 1 FROM tipo_reclamo WHERE id_municipio = :m", {"m": mid}):
            await db.execute(text("""
                INSERT INTO tipo_reclamo (nombre, id_subarea, activo, id_municipio)
                VALUES ('Bache en la calzada', :s, TRUE, :m)"""), {"s": sub, "m": mid})
        await db.execute(text("""
            INSERT INTO configuracion_general (clave, valor, tipo, descripcion, activo, id_municipio)
            SELECT clave, valor, tipo, descripcion, TRUE, :m FROM configuracion_general c
             WHERE c.id_municipio = (SELECT id_municipio FROM municipios WHERE direccion_base) AND c.activo
            ON CONFLICT DO NOTHING"""), {"m": mid})
        await db.commit()
    invalidar_cache_municipios()
    return mid, True


def _alta_body(sufijo: str, codigo: str, **extra) -> dict:
    dni = str(30_000_000 + int(sufijo, 36) % 9_000_000)
    return {"nombre": f"Municipio de prueba D {sufijo}", "codigo_pais": "AR", "id_provincia": extra.pop("id_provincia"),
            "codigo_corto": codigo, "subdominio": f"d-{sufijo}", "ficticio": True,
            "identidad": {"color": "#1F8A65"},
            "copiar": ["areas_subareas", "tipos_reclamo"],
            "modulos": ["usuarios", "admin_tablas", "padrones", "municipios", "reclamos", "agenda", "turnos"],
            "max_usuarios_activos": None,
            "administrador": {"nombre": "Ana", "apellido": f"Prueba{sufijo}", "dni": dni, "cuil": _cuil(dni),
                              "sexo": "MUJER", "fecha_nac": "1985-04-02", "telefono": "1144445555",
                              "email": f"admin.{sufijo}@prueba-aislamiento.com.ar"},
            **extra}


CODIGOS_USADOS: set[str] = set()  # los carga main(): con cientos de municipios de prueba, uno al azar choca


def _sufijo() -> tuple[str, str]:
    import random
    import string
    while True:
        cod = "".join(random.choices(string.ascii_uppercase, k=4))
        if cod not in CODIGOS_USADOS:
            CODIGOS_USADOS.add(cod)
            return "".join(random.choices(string.ascii_lowercase + string.digits, k=5)), cod


async def _contexto_alta() -> dict:
    modelo, propio = await _modelo_minimo()
    async with AsyncSessionLocal() as db:
        h = await _super_headers(db)
        ba = await _escalar(db, "SELECT id_provincia FROM provincias WHERE codigo_pais = 'AR' AND nombre = 'Buenos Aires'")
        cod_base, sub_base = (await db.execute(text(
            "SELECT codigo_corto, subdominio FROM municipios WHERE direccion_base"))).one()
    return {"modelo": modelo, "propio": propio, "h": h, "ba": ba, "cod_base": cod_base, "sub_base": sub_base}


def _minutos(desfase: str) -> int:
    signo = -1 if desfase.startswith("-") else 1
    h, m = desfase.lstrip("+-").split(":")
    return signo * (int(h) * 60 + int(m))


async def _partido_libre(id_provincia: int) -> int:
    async with AsyncSessionLocal() as db:
        return await _escalar(db, """
            SELECT p.id_partido FROM partidos p WHERE p.id_provincia = :pr AND NOT EXISTS (
              SELECT 1 FROM municipios m WHERE m.id_partido = p.id_partido AND m.estado <> 'baja')
             ORDER BY p.id_partido LIMIT 1""", {"pr": id_provincia})


async def test_alta_partido_zona_codigo() -> None:
    """Corte B (César, 2026-10-27): municipio = partido (obligatorio salvo ficticio, uno vigente por
    partido), zonas horarias precargadas con su desfase, código corto de 4 letras y disponibilidad
    del código, el subdominio y el partido mientras se escribe."""
    print("\ntest_alta_partido_zona_codigo")
    ctx = await _contexto_alta()
    partido = await _partido_libre(ctx["ba"])
    creados: list[int] = []
    async with _cliente() as c:
        r = await c.get("/api/v1/super/alta/opciones", headers=ctx["h"])
        lista = r.json().get("zonas", []) if r.status_code == 200 else []
        zonas = {z["nombre"]: z["desfase"] for z in lista}
        check("opciones trae las zonas con su desfase", zonas.get("America/Argentina/Buenos_Aires") == "-03:00",
              f"{len(zonas)} zonas")
        check("zonas con nombre de región (sin posix/, Etc/ ni abreviaturas)", bool(zonas) and all(
            "/" in z and not z.startswith(("posix/", "Etc/")) for z in zonas))
        check("zonas ordenadas por desfase", [_minutos(z["desfase"]) for z in lista]
              == sorted(_minutos(z["desfase"]) for z in lista))

        suf, cod = _sufijo()
        real = {**_alta_body(suf, cod, id_provincia=ctx["ba"]), "ficticio": False}
        r = await c.post("/api/v1/super/municipios", json=real, headers=ctx["h"])
        check("sin partido ni ficticio → 422", r.status_code == 422 and "partido" in r.text, f"{r.status_code} {r.text[:120]}")
        r = await c.post("/api/v1/super/municipios", headers=ctx["h"],
                         json={**_alta_body(suf, cod, id_provincia=ctx["ba"]), "id_partido": partido})
        check("ficticio con partido → 422", r.status_code == 422, f"{r.status_code} {r.text[:120]}")

        params = {"codigo_corto": cod, "subdominio": f"d-{suf}", "id_partido": partido}
        r = await c.get("/api/v1/super/alta/disponibilidad", params=params, headers=ctx["h"])
        d = r.json() if r.status_code == 200 else {}
        check("disponibilidad: libres", r.status_code == 200 and all(
            d.get(k, {}).get("disponible") is True for k in ("codigo_corto", "subdominio", "id_partido")),
            f"{r.status_code} {r.text[:200]}")

        r = await c.post("/api/v1/super/municipios", json={**real, "id_partido": partido}, headers=ctx["h"])
        check("con partido → 201", r.status_code == 201, f"{r.status_code} {r.text[:160]}")
        if r.status_code == 201:
            creados.append(r.json()["id_municipio"])

        r = await c.get("/api/v1/super/alta/disponibilidad", params=params, headers=ctx["h"])
        d = r.json() if r.status_code == 200 else {}
        check("disponibilidad: ocupados, con motivo", r.status_code == 200 and all(
            d.get(k, {}).get("disponible") is False and d[k].get("motivo") for k in ("codigo_corto", "subdominio", "id_partido")),
            f"{r.status_code} {r.text[:240]}")
        r = await c.get("/api/v1/super/alta/disponibilidad", params={"codigo_corto": "AB", "subdominio": "api"},
                        headers=ctx["h"])
        d = r.json() if r.status_code == 200 else {}
        check("disponibilidad: formato y reservados", r.status_code == 200
              and "4 letras" in (d.get("codigo_corto", {}).get("motivo") or "")
              and "reservado" in (d.get("subdominio", {}).get("motivo") or ""), f"{r.status_code} {r.text[:240]}")

        suf2, cod2 = _sufijo()
        r = await c.post("/api/v1/super/municipios", headers=ctx["h"],
                         json={**_alta_body(suf2, cod2, id_provincia=ctx["ba"]), "ficticio": False, "id_partido": partido})
        check("otro municipio con el mismo partido → 409", r.status_code == 409 and "partido" in r.text,
              f"{r.status_code} {r.text[:120]}")

        fict, nombre_fict = await _municipio_sql("puesta_en_marcha")
        creados.append(fict)
        r = await c.post(f"/api/v1/super/municipios/{fict}/estado", json={"estado": "produccion", "confirmacion": nombre_fict},
                         headers=ctx["h"])
        check("un ficticio no pasa a producción → 422", r.status_code == 422 and "partido" in r.text,
              f"{r.status_code} {r.text[:120]}")
        r = await c.put(f"/api/v1/super/municipios/{fict}", headers=ctx["h"], json={
            "nombre": nombre_fict, "codigo_pais": "AR", "id_provincia": ctx["ba"], "id_partido": partido,
            "zona_horaria": "America/Argentina/Buenos_Aires"})
        check("editar poniendo un partido ya tomado → 409", r.status_code == 409 and "partido" in r.text,
              f"{r.status_code} {r.text[:120]}")
    for mid in creados:
        await _estado(mid, "baja")


async def _cantidad_municipios() -> int:
    async with AsyncSessionLocal() as db:
        return await _escalar(db, "SELECT count(*) FROM municipios")


async def test_alta_validaciones() -> None:
    print("\ntest_alta_validaciones")
    ctx = await _contexto_alta()
    suf, cod = _sufijo()
    antes = await _cantidad_municipios()
    casos = [
        ("subdominio con mayúsculas", {"subdominio": "Vicente-Lopez"}, 422),
        ("subdominio con tilde", {"subdominio": "córdoba"}, 422),
        ("subdominio reservado", {"subdominio": "api"}, 422),
        ("subdominio de San Andrés", {"subdominio": ctx["sub_base"]}, 409),
        ("código en minúsculas", {"codigo_corto": "sa"}, 422),
        # San Andrés conserva su código de 3 letras; un alta nueva exige 4 (César, 2026-10-27).
        ("código de 3 letras", {"codigo_corto": ctx["cod_base"]}, 422),
        ("país no habilitado", {"codigo_pais": "VE"}, 422),
        ("turnos sin agenda", {"modulos": ["usuarios", "admin_tablas", "padrones", "municipios", "turnos"]}, 422),
    ]
    async with _cliente() as c:
        for nombre, cambio, esperado in casos:
            body = {**_alta_body(suf, cod, id_provincia=ctx["ba"]), **cambio}
            r = await c.post("/api/v1/super/municipios", json=body, headers=ctx["h"])
            check(f"{nombre} → {esperado}", r.status_code == esperado, f"{r.status_code} {r.text[:140]}")
    check("no se creó ningún municipio", await _cantidad_municipios() == antes)
    if ctx["propio"]:
        await _estado(ctx["modelo"], "baja")


async def test_alta_ok() -> None:
    print("\ntest_alta_ok")
    import re
    import app.services.email as em
    ctx = await _contexto_alta()
    suf, cod = _sufijo()
    capturados: list[str] = []

    async def captura(to, subject, body_html, body_text=None, from_override=None):
        capturados.append(body_html or "")
        return True

    original = em.enviar_mail
    em.enviar_mail = captura
    try:
        async with _cliente() as c:
            r = await c.post("/api/v1/super/municipios", json=_alta_body(suf, cod, id_provincia=ctx["ba"]),
                             headers=ctx["h"])
    finally:
        em.enviar_mail = original
    check("alta → 201", r.status_code == 201, f"{r.status_code} {r.text[:200]}")
    if r.status_code != 201:
        return
    D = r.json()["id_municipio"]
    async with AsyncSessionLocal() as db:
        estado = await _escalar(db, "SELECT estado FROM municipios WHERE id_municipio = :m", {"m": D})
        check("D en puesta_en_marcha", estado == "puesta_en_marcha", estado)
        check("6 áreas fijas con es_sistema", await _escalar(
            db, "SELECT count(*) FROM area WHERE id_municipio = :m AND es_sistema AND activo", {"m": D}) == 6)
        # El contorno del modelo no se copia (es de un lugar: PLAN_CONTORNO_MUNICIPIO, revisión final).
        n_mod = await _escalar(db, "SELECT count(*) FROM configuracion_general WHERE id_municipio = :m "
                                   "AND clave NOT IN ('geo_limite_geojson', 'geo_limite_origen')", {"m": ctx["modelo"]})
        n_d = await _escalar(db, "SELECT count(*) FROM configuracion_general WHERE id_municipio = :m", {"m": D})
        check("claves de configuración = las del modelo", n_d == n_mod and n_d > 0, f"{n_d} de {n_mod}")
        salud = await _escalar(db, "SELECT valor FROM configuracion_general WHERE id_municipio = :m AND clave = 'id_area_salud'",
                               {"m": D})
        check("id_area_salud apunta a un área de D", salud is not None and await _escalar(
            db, "SELECT 1 FROM area WHERE id_area::text = :a AND id_municipio = :m", {"a": salud, "m": D}) == 1, salud)
        admin = (await db.execute(text("""
            SELECT u.id_usuario, u.nivel_acceso, a.id_agente, a.id_subarea, u.id_ciudadano
              FROM usuarios u JOIN agentes a ON a.id_usuario = u.id_usuario
             WHERE u.id_municipio = :m"""), {"m": D})).first()
        check("admin nivel 1 con agente, subárea y ficha", admin is not None and admin.nivel_acceso == 1
              and admin.id_subarea is not None and admin.id_ciudadano is not None, admin)
        check("el alta no crea la invitación (sale desde la ficha)", await _escalar(db, """
            SELECT count(*) FROM usuario_invitacion WHERE id_usuario = :u""",
            {"u": admin.id_usuario if admin else 0}) == 0)
        check("registro municipio_alta", await _escalar(db, "SELECT count(*) FROM super_admin_acceso "
              "WHERE accion = 'municipio_alta' AND id_municipio = :m", {"m": D}) == 1)
        check("módulos = los elegidos", await _escalar(db, "SELECT count(*) FROM municipio_modulo WHERE id_municipio = :m "
              "AND habilitado", {"m": D}) == 7)
        check("no copió ninguna persona", await _escalar(db, "SELECT count(*) FROM ciudadanos WHERE id_municipio = :m",
                                                         {"m": D}) == 1)
    links = [h for html in capturados for h in re.findall(r'href="(https?://[^"]+)"', html)]
    check("el alta no manda el mail de invitación", not any("invitacion.html" in x for x in links), links[:3])
    # Envío desde la ficha: con alguna dirección sin responder, 409 y nada creado; con las tres, 200.
    uid = admin.id_usuario if admin else 0
    em.enviar_mail = captura
    try:
        async with _cliente() as c:
            restaurar = _dominios_simulados(ok=False)
            try:
                r = await c.post(f"/api/v1/super/usuarios/{uid}/invitacion", headers=ctx["h"])
            finally:
                restaurar()
            check("enviar con direcciones caídas → 409", r.status_code == 409
                  and "tienen que responder" in r.text, f"{r.status_code} {r.text[:160]}")
            async with AsyncSessionLocal() as db:
                check("y no crea la invitación", await _escalar(
                    db, "SELECT count(*) FROM usuario_invitacion WHERE id_usuario = :u", {"u": uid}) == 0)
            restaurar = _dominios_simulados(ok=True)
            try:
                r = await c.post(f"/api/v1/super/usuarios/{uid}/invitacion", headers=ctx["h"])
            finally:
                restaurar()
            check("enviar con las tres direcciones en verde → 200 con la fecha",
                  r.status_code == 200 and bool(r.json().get("enviada_en")), f"{r.status_code} {r.text[:160]}")
            f = (await c.get(f"/api/v1/super/municipios/{D}", headers=ctx["h"])).json()
            a = next((x for x in f.get("administradores", []) if x["id_usuario"] == uid), {})
            check("la ficha muestra el envío", bool(a.get("invitacion_enviada_en")) and a.get("invitacion_pendiente")
                  and a.get("invitacion_aceptada_en") is None and bool(a.get("invitacion_vence_en")), str(a)[:200])
    finally:
        em.enviar_mail = original
    links = [h for html in capturados for h in re.findall(r'href="(https?://[^"]+)"', html)]
    check("el mail de invitación lleva al subdominio de D",
          any(x.startswith(f"https://d-{suf}.zge.zaris.com.ar/frontend/invitacion.html?t=") for x in links), links[:3])
    await _estado(D, "baja")
    if ctx["propio"]:
        await _estado(ctx["modelo"], "baja")


def _dominios_simulados(ok: bool):
    """Simula el resultado de «Verificar» (las tres direcciones responden o no) sin salir a la red.
    Devuelve la función que restaura el original."""
    from app.api.routes import super_admin as rutas

    async def falso(db, id_municipio):
        return [{"app": a, "host": f"{a}.prueba.invalido", "dns": ok, "https": 200 if ok else None}
                for a in ("zge", "vecinos", "agentes")]

    original = rutas.estado_dominios
    rutas.estado_dominios = falso
    return lambda: setattr(rutas, "estado_dominios", original)


async def test_alta_atomica() -> None:
    print("\ntest_alta_atomica")
    from app.services.municipios import clonado
    ctx = await _contexto_alta()
    suf, cod = _sufijo()
    original = clonado.Clonador.clonar
    llamadas = {"n": 0}

    async def falla(self, tabla, id_origen, cambios=None, copia_nueva=False):
        llamadas["n"] += 1
        if llamadas["n"] == 3:
            raise RuntimeError("falla forzada por el smoke")
        return await original(self, tabla, id_origen, cambios, copia_nueva)

    clonado.Clonador.clonar = falla
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                                     base_url="http://test") as c:
            r = await c.post("/api/v1/super/municipios", json=_alta_body(suf, cod, id_provincia=ctx["ba"]),
                             headers=ctx["h"])
    finally:
        clonado.Clonador.clonar = original
    check("el alta falla", r.status_code >= 500 or r.status_code == 409, r.status_code)
    async with AsyncSessionLocal() as db:
        check("no quedó el municipio", not await _escalar(db, "SELECT 1 FROM municipios WHERE subdominio = :s",
                                                         {"s": f"d-{suf}"}))
        check("no quedó la ficha del administrador", not await _escalar(
            db, "SELECT 1 FROM ciudadanos WHERE email = :e", {"e": f"admin.{suf}@prueba-aislamiento.com.ar"}))
    if ctx["propio"]:
        await _estado(ctx["modelo"], "baja")


async def test_alta_agrega_fijos() -> None:
    """El asistente no muestra los módulos fijos que no son de un municipio (Municipios, nivel 0): el
    alta los habilita igual."""
    print("\ntest_alta_agrega_fijos")
    ctx = await _contexto_alta()
    suf, cod = _sufijo()
    body = _alta_body(suf, cod, id_provincia=ctx["ba"])
    body["modulos"] = ["reclamos"]
    async with _cliente() as c:
        r = await c.post("/api/v1/super/municipios", json=body, headers=ctx["h"])
    check("alta sin los módulos fijos → 201", r.status_code == 201, f"{r.status_code} {r.text[:160]}")
    if r.status_code == 201:
        async with AsyncSessionLocal() as db:
            hab = {x[0] for x in (await db.execute(text(
                "SELECT modulo_codigo FROM municipio_modulo WHERE id_municipio = :m AND habilitado"),
                {"m": r.json()["id_municipio"]})).all()}
        check("quedan habilitados los fijos y los elegidos",
              hab == {"usuarios", "admin_tablas", "padrones", "municipios", "reclamos"}, str(sorted(hab)))
        await _estado(r.json()["id_municipio"], "baja")


async def test_alta_concurrente() -> None:
    print("\ntest_alta_concurrente")
    ctx = await _contexto_alta()
    suf, cod = _sufijo()
    body = _alta_body(suf, cod, id_provincia=ctx["ba"])
    async with _cliente() as c1, _cliente() as c2:
        r1, r2 = await asyncio.gather(c1.post("/api/v1/super/municipios", json=body, headers=ctx["h"]),
                                      c2.post("/api/v1/super/municipios", json=body, headers=ctx["h"]))
    codigos = sorted([r1.status_code, r2.status_code])
    check("dos altas iguales a la vez: una 201 y una 409", codigos == [201, 409], f"{codigos} {r1.text[:80]} {r2.text[:80]}")
    async with AsyncSessionLocal() as db:
        D = await _escalar(db, "SELECT id_municipio FROM municipios WHERE subdominio = :s", {"s": f"d-{suf}"})
        check("queda uno solo", await _escalar(db, "SELECT count(*) FROM municipios WHERE subdominio = :s",
                                              {"s": f"d-{suf}"}) == 1)
    if D:
        await _estado(D, "baja")
    if ctx["propio"]:
        await _estado(ctx["modelo"], "baja")


async def test_invitacion() -> None:
    print("\ntest_invitacion")
    import re
    import app.services.email as em
    ctx = await _contexto_alta()
    suf, cod = _sufijo()
    capturados: list[str] = []

    async def captura(to, subject, body_html, body_text=None, from_override=None):
        capturados.append(body_html or "")
        return True

    def ultimo_token() -> str:
        for html in reversed(capturados):
            m = re.search(r"invitacion\.html\?t=([A-Za-z0-9_-]+)", html)
            if m:
                return m.group(1)
        return ""

    original = em.enviar_mail
    em.enviar_mail = captura
    restaurar = lambda: None  # noqa: E731
    try:
        async with _cliente() as c:
            r = await c.post("/api/v1/super/municipios", json=_alta_body(suf, cod, id_provincia=ctx["ba"]),
                             headers=ctx["h"])
            D = r.json().get("id_municipio") if r.status_code == 201 else None
            async with AsyncSessionLocal() as db:
                uid = await _escalar(db, "SELECT id_usuario FROM usuarios WHERE id_municipio = :m AND nivel_acceso = 1", {"m": D})
            restaurar = _dominios_simulados(ok=True)
            r = await c.post(f"/api/v1/super/usuarios/{uid}/invitacion", headers=ctx["h"])
            check("enviar la invitación desde la ficha → 200", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
            tok = ultimo_token()
            check("el mail trae el token", bool(tok))
            r = await c.post("/api/v1/auth/invitacion/aceptar", json={"token": tok, "password": "corta"})
            check("clave corta → 422", r.status_code == 422, f"{r.status_code}")
            # Con el segundo factor obligatorio (como en prod), aceptar lleva a vincular la app y el
            # desafío sirve para el paso siguiente.
            obligatorio = settings.SEGUNDO_FACTOR_OBLIGATORIO
            settings.SEGUNDO_FACTOR_OBLIGATORIO = True
            try:
                r = await c.post("/api/v1/auth/invitacion/aceptar", json={"token": tok, "password": "clave-segura-123"},
                                 headers={"Origin": f"https://d-{suf}.zge.zaris.com.ar"})
                check("aceptar → 200 con vinculación", r.status_code == 200 and r.json().get("estado") == "vincular"
                      and bool(r.json().get("desafio")), f"{r.status_code} {r.text[:160]}")
                r2 = await c.post("/api/v1/auth/segundo-factor/vinculacion", json={"desafio": r.json().get("desafio")},
                                  headers={"Origin": f"https://d-{suf}.zge.zaris.com.ar"})
                check("y el desafío sirve para vincular la app", r2.status_code == 200 and bool(r2.json().get("secreto")),
                      f"{r2.status_code} {r2.text[:160]}")
            finally:
                settings.SEGUNDO_FACTOR_OBLIGATORIO = obligatorio
            r = await c.post("/api/v1/auth/invitacion/aceptar", json={"token": tok, "password": "clave-segura-123"})
            check("el mismo token otra vez → 401 texto fijo", r.status_code == 401
                  and "El enlace venció o ya se usó" in r.text, f"{r.status_code} {r.text[:120]}")
            async with AsyncSessionLocal() as db:
                uid = await _escalar(db, "SELECT id_usuario FROM usuarios WHERE id_municipio = :m AND nivel_acceso = 1", {"m": D})
            r = await c.post(f"/api/v1/super/usuarios/{uid}/invitacion", headers=ctx["h"])
            check("reenviar → 200", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
            tok2 = ultimo_token()
            async with AsyncSessionLocal() as db:
                await db.execute(text("UPDATE usuario_invitacion SET vence_en = NOW() - INTERVAL '1 hour' "
                                      "WHERE id_usuario = :u AND usada_en IS NULL"), {"u": uid})
                await db.commit()
            r = await c.post("/api/v1/auth/invitacion/aceptar", json={"token": tok2, "password": "clave-segura-456"})
            check("token vencido → 401", r.status_code == 401, f"{r.status_code}")
            # Sin segundo factor obligatorio (local): aceptar deja la clave y avisa que ya puede ingresar.
            r = await c.post(f"/api/v1/super/usuarios/{uid}/invitacion", headers=ctx["h"])
            tok3 = ultimo_token()
            obligatorio = settings.SEGUNDO_FACTOR_OBLIGATORIO
            settings.SEGUNDO_FACTOR_OBLIGATORIO = False
            try:
                r = await c.post("/api/v1/auth/invitacion/aceptar", json={"token": tok3, "password": "clave-segura-789"})
                check("sin segundo factor obligatorio: 200 sin desafío", r.status_code == 200
                      and r.json().get("requiere_segundo_factor") is False, f"{r.status_code} {r.text[:160]}")
            finally:
                settings.SEGUNDO_FACTOR_OBLIGATORIO = obligatorio
    finally:
        em.enviar_mail = original
        restaurar()
    if D:
        await _estado(D, "baja")
    if ctx["propio"]:
        await _estado(ctx["modelo"], "baja")


async def test_invitacion_token_malformado() -> None:
    """Un link cortado por el cliente de mail da el texto fijo (401), no un 422 de validación."""
    from app.services.municipios.invitacion import INVITACION_INVALIDA
    print("\ntest_invitacion_token_malformado")
    async with _cliente() as c:
        for tok in ("corto", "x" * 300, ""):
            r = await c.post("/api/v1/auth/invitacion/aceptar", json={"token": tok, "password": "ClaveDePrueba2026!"})
            check(f"token de {len(tok)} caracteres → 401 con el texto fijo",
                  r.status_code == 401 and r.json().get("detail") == INVITACION_INVALIDA, f"{r.status_code} {r.text[:120]}")


async def test_estados() -> None:
    print("\ntest_estados")
    ctx = await _contexto_alta()
    suf, cod = _sufijo()
    async with _cliente() as c:
        # Pasa a producción: tiene que ser un municipio real, con su partido.
        body = {**_alta_body(suf, cod, id_provincia=ctx["ba"]), "ficticio": False,
                "id_partido": await _partido_libre(ctx["ba"])}
        r = await c.post("/api/v1/super/municipios", json=body, headers=ctx["h"])
        D = r.json().get("id_municipio") if r.status_code == 201 else None
        nombre = f"Municipio de prueba D {suf}"
        url = f"/api/v1/super/municipios/{D}/estado"
        r = await c.post(url, json={"estado": "produccion"}, headers=ctx["h"])
        check("produccion sin confirmación → 422", r.status_code == 422, f"{r.status_code}")
        r = await c.post(url, json={"estado": "produccion", "confirmacion": nombre}, headers=ctx["h"])
        check("produccion con confirmación → 200 y fue_produccion", r.status_code == 200
              and r.json().get("fue_produccion") is True, f"{r.status_code} {r.text[:120]}")
        r = await c.post(url, json={"estado": "puesta_en_marcha"}, headers=ctx["h"])
        check("de produccion no se vuelve a puesta_en_marcha → 422", r.status_code == 422, f"{r.status_code}")
        r = await c.post(url, json={"estado": "baja"}, headers=ctx["h"])
        check("baja → 200", r.status_code == 200 and r.json().get("estado") == "baja", f"{r.status_code}")
        r = await c.post(url, json={"estado": "reactivar"}, headers=ctx["h"])
        check("reactivar → vuelve a produccion", r.status_code == 200 and r.json().get("estado") == "produccion",
              f"{r.status_code} {r.text[:120]}")
        async with AsyncSessionLocal() as db:
            check("registro municipio_estado", await _escalar(db, "SELECT count(*) FROM super_admin_acceso "
                  "WHERE accion = 'municipio_estado' AND id_municipio = :m", {"m": D}) == 3)
        await c.post(url, json={"estado": "baja"}, headers=ctx["h"])
    if ctx["propio"]:
        await _estado(ctx["modelo"], "baja")


# ── Tarea 12 ──────────────────────────────────────────────────────────────────────────────────

async def test_modelo() -> None:
    print("\ntest_modelo")
    async with AsyncSessionLocal() as db:
        m = (await db.execute(text(
            "SELECT id_municipio, nombre, subdominio, codigo_corto FROM municipios WHERE estado = 'modelo'"))).first()
        check("existe el municipio modelo (Modelo ZARIS)", m is not None and m.nombre == "Modelo ZARIS", m)
        if m is None:
            return
        check("sin subdominio y con código MOD", m.subdominio is None and m.codigo_corto == "MOD", m)
        tablas = (await db.execute(text(
            "SELECT tabla FROM municipio_tabla_clase WHERE grupo IN ('contactos', 'usuarios', 'operativo') "
            "AND clase <> 'global'"))).scalars().all()
        con_filas = []
        for t in tablas:
            if await _escalar(db, "SELECT to_regclass(:t) IS NOT NULL", {"t": f"public.{t}"}) and                     await _escalar(db, f'SELECT count(*) FROM "{t}" WHERE id_municipio = :m', {"m": m.id_municipio}):
                con_filas.append(t)
        check("sin filas de contactos, usuarios ni operativo", not con_filas, con_filas)
        check("6 áreas fijas", await _escalar(db, "SELECT count(*) FROM area WHERE id_municipio = :m AND es_sistema "
                                              "AND activo", {"m": m.id_municipio}) == 6)
        base = await _escalar(db, "SELECT id_municipio FROM municipios WHERE direccion_base")
        faltan = (await db.execute(text(
            "SELECT clave FROM configuracion_general WHERE id_municipio = :b AND activo EXCEPT "
            "SELECT clave FROM configuracion_general WHERE id_municipio = :m"), {"b": base, "m": m.id_municipio})).scalars().all()
        check("todas las claves de configuración", not faltan, faltan)
        for t in ("espacios_agenda", "lugares_atencion", "servicios", "tipo_prestacion", "equipos"):
            check(f"sin {t} (decisión de César)", not await _escalar(
                db, f'SELECT count(*) FROM "{t}" WHERE id_municipio = :m', {"m": m.id_municipio}))
        check("sin nombres de prueba en los tipos de reclamo", not await _escalar(db, """
            SELECT count(*) FROM tipo_reclamo WHERE id_municipio = :m
               AND nombre ~* '(\m(test|prueba|qa|demo|borrar)\M|smoke|aislab)'""", {"m": m.id_municipio}))
        check("identidad de San Andrés en blanco", not await _escalar(db, """
            SELECT count(*) FROM configuracion_general WHERE id_municipio = :m AND coalesce(valor, '') <> ''
               AND clave IN ('municipio_logo_url', 'municipio_color_primary', 'geo_limite_geojson')""",
            {"m": m.id_municipio}))


# ── Tarea 13 ──────────────────────────────────────────────────────────────────────────────────

async def test_area_fija_api() -> None:
    print("\ntest_area_fija_api")
    texto = "Es un área fija del sistema: se puede renombrar, no dar de baja."
    async with AsyncSessionLocal() as db:
        uid, mun = await _admin_base(db)
        area = (await db.execute(text("SELECT id_area, nombre FROM area WHERE id_municipio = :m AND es_sistema "
                                      "ORDER BY id_area LIMIT 1"), {"m": mun})).first()
    h = _token(uid, mun)
    async with _cliente() as c:
        r = await c.put(f"/api/v1/admin/area/{area.id_area}", json={"nombre": area.nombre, "activo": False}, headers=h)
        check("PUT de baja sobre un área fija → 422 texto fijo", r.status_code == 422 and texto in r.text,
              f"{r.status_code} {r.text[:140]}")
        r = await c.delete(f"/api/v1/admin/area/{area.id_area}", headers=h)
        check("DELETE sobre un área fija → 422 texto fijo", r.status_code == 422 and texto in r.text,
              f"{r.status_code} {r.text[:140]}")
        r = await c.put(f"/api/v1/admin/area/{area.id_area}", json={"nombre": area.nombre + " (renombrada)"}, headers=h)
        check("renombrarla → 200", r.status_code == 200, f"{r.status_code} {r.text[:140]}")
        await c.put(f"/api/v1/admin/area/{area.id_area}", json={"nombre": area.nombre}, headers=h)
    async with AsyncSessionLocal() as db:
        check("sigue activa y con su nombre", tuple((await db.execute(text(
            "SELECT activo, nombre FROM area WHERE id_area = :a"), {"a": area.id_area})).one()) == (True, area.nombre))


# ── Tarea 14 ──────────────────────────────────────────────────────────────────────────────────

TOPE_TEXTO = "llegó al tope de"


async def _subarea_c(mid: int) -> int:
    """Una subárea de C para las cuentas internas de prueba (idempotente)."""
    async with AsyncSessionLocal() as db:
        sub = await _escalar(db, "SELECT id_subarea FROM subarea WHERE id_municipio = :m AND nombre = 'Prueba tope'",
                             {"m": mid})
        if sub is None:
            area = await _escalar(db, "SELECT id_area FROM area WHERE id_municipio = :m ORDER BY id_area LIMIT 1",
                                  {"m": mid}) or await _escalar(db, """
                INSERT INTO area (nombre, id_municipio, activo) VALUES ('Área prueba tope', :m, TRUE)
                RETURNING id_area""", {"m": mid})
            sub = await _escalar(db, """
                INSERT INTO subarea (nombre, id_area, id_municipio, activo) VALUES ('Prueba tope', :a, :m, TRUE)
                RETURNING id_subarea""", {"a": area, "m": mid})
        await db.commit()
    return sub


async def _tope(mid: int, maximo) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(text("UPDATE municipios SET max_usuarios_activos = :t WHERE id_municipio = :m"),
                         {"t": maximo, "m": mid})
        await db.commit()


async def _activas(mid: int) -> int:
    async with AsyncSessionLocal() as db:
        return await _escalar(db, "SELECT count(*) FROM usuarios WHERE id_municipio = :m AND activo "
                                  "AND nivel_acceso BETWEEN 1 AND 5", {"m": mid})


async def _ficha_funcionario_c(mid: int, sufijo: str) -> int:
    dni = "97" + sufijo[-6:].rjust(6, "0")
    async with AsyncSessionLocal() as db:
        cid = await _escalar(db, """
            INSERT INTO ciudadanos (doc_tipo, doc_nro, cuil, nombre, apellido, sexo, fecha_nac, id_nacionalidad, telefono, email, email_chk, emp_chk,
                                    ren_chk, activo, es_funcionario, id_municipio)
            VALUES ('DNI', :dni, :cuil, 'Tope', 'Prueba', 'OTROS', '1990-01-01', (SELECT min(id) FROM nacionalidades), '1100000000', :e, FALSE, FALSE, FALSE, TRUE, TRUE, :m)
            RETURNING id_ciudadano""", {"dni": dni, "cuil": _cuil(dni), "e": f"tope.ficha.{sufijo}@prueba-aislamiento.com.ar",
                                        "m": mid})
        await db.commit()
    return cid


async def test_tope() -> None:
    import uuid
    print("\ntest_tope")
    C = await _municipio_c()
    mid = C["id"]
    sub = await _subarea_c(mid)
    h = _token(C["n1"], mid)
    creadas: list[int] = []

    def alta(s: str) -> dict:
        return {"username": f"tope.{s}", "email": f"tope.{s}@prueba-aislamiento.com.ar", "nivel_acceso": 4,
                "id_subarea": sub}

    async with _cliente() as c:
        try:
            activas = await _activas(mid)
            await _tope(mid, activas)
            s = uuid.uuid4().hex[:8]
            r = await c.post("/api/v1/buc/usuarios", json=alta(s), headers=h)
            check("tope lleno: POST /buc/usuarios → 409", r.status_code == 409 and TOPE_TEXTO in r.text,
                  f"{r.status_code} {r.text[:160]}")
            cid = await _ficha_funcionario_c(mid, str(int(s, 16) % 1_000_000))
            r = await c.post(f"/api/v1/buc/ciudadanos/{cid}/cuenta-zaris",
                             json={"nivel_acceso": 4, "id_subarea": sub, "username": f"tope.f{s}"}, headers=h)
            check("tope lleno: cuenta ZARIS desde la ficha → 409", r.status_code == 409 and TOPE_TEXTO in r.text,
                  f"{r.status_code} {r.text[:160]}")
            check("no se creó ninguna cuenta", await _activas(mid) == activas)

            r = await c.put(f"/api/v1/buc/usuarios/{C['n4']}/estado", params={"activo": "false"}, headers=h)
            check("dar de baja una cuenta con el tope lleno → 200", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
            r = await c.post("/api/v1/buc/usuarios", json=alta(s), headers=h)
            check("con un lugar libre, crear → 201", r.status_code == 201, f"{r.status_code} {r.text[:160]}")
            if r.status_code == 201:
                creadas.append(r.json()["id_usuario"])
            r = await c.put(f"/api/v1/buc/usuarios/{C['n4']}/estado", params={"activo": "true"}, headers=h)
            check("reactivar con el tope lleno → 409", r.status_code == 409 and TOPE_TEXTO in r.text,
                  f"{r.status_code} {r.text[:160]}")

            r = await c.get("/api/v1/buc/usuarios/cupo", headers=h)
            cupo = r.json() if r.status_code == 200 else {}
            check("GET /buc/usuarios/cupo → activas, maximo y aviso",
                  cupo == {"activas": activas, "maximo": activas, "aviso": True}, f"{r.status_code} {r.text[:160]}")

            antes = await _activas(mid)
            await _tope(mid, 1)
            check("bajar el tope por debajo de las activas no desactiva a nadie", await _activas(mid) == antes)

            await _tope(mid, antes + 1)
            s1, s2 = uuid.uuid4().hex[:8], uuid.uuid4().hex[:8]
            r1, r2 = await asyncio.gather(c.post("/api/v1/buc/usuarios", json=alta(s1), headers=h),
                                          c.post("/api/v1/buc/usuarios", json=alta(s2), headers=h))
            codigos = sorted((r1.status_code, r2.status_code))
            check("dos altas simultáneas con un lugar: una 201 y una 409", codigos == [201, 409], str(codigos))
            creadas += [r.json()["id_usuario"] for r in (r1, r2) if r.status_code == 201]

            await _tope(mid, None)
            r = await c.get("/api/v1/buc/usuarios/cupo", headers=h)
            check("sin tope: maximo null y sin aviso", r.status_code == 200 and r.json()["maximo"] is None
                  and r.json()["aviso"] is False, f"{r.status_code} {r.text[:160]}")
        finally:
            await _tope(mid, None)
            async with AsyncSessionLocal() as db:
                await db.execute(text("UPDATE usuarios SET activo = (id_usuario = :n4) WHERE id_usuario = ANY(:ids)"),
                                 {"n4": C["n4"], "ids": creadas + [C["n4"]]})
                await db.execute(text("UPDATE usuarios SET activo = FALSE WHERE id_municipio = :m "
                                      "AND username LIKE 'tope.%'"), {"m": mid})
                await db.commit()


# ── Tarea 15 ──────────────────────────────────────────────────────────────────────────────────

async def test_super_admins() -> None:
    import uuid
    from fastapi import HTTPException
    from app.services.municipios.super_admins import dar_de_baja_super
    print("\ntest_super_admins")
    async with AsyncSessionLocal() as db:
        h = await _super_headers(db)
        yo = await _escalar(db, "SELECT id_usuario FROM usuarios WHERE nivel_acceso = 0 AND id_municipio IS NULL "
                                "AND activo ORDER BY id_usuario LIMIT 1")
        email_mun = await _escalar(db, "SELECT email FROM usuarios WHERE id_municipio IS NOT NULL AND activo "
                                       "AND email IS NOT NULL ORDER BY id_usuario LIMIT 1")
    email = f"super.{uuid.uuid4().hex[:8]}@prueba-aislamiento.com.ar"
    async with _cliente() as c:
        r = await c.post("/api/v1/super/administradores", json={"nombre": "Prueba", "apellido": "Super", "email": email},
                         headers=h)
        check("alta de un super → 201", r.status_code == 201, f"{r.status_code} {r.text[:160]}")
        nuevo = r.json().get("id_usuario") if r.status_code == 201 else None
        async with AsyncSessionLocal() as db:
            fila = (await db.execute(text("SELECT nivel_acceso, id_municipio, activo FROM usuarios WHERE id_usuario = :u"),
                                     {"u": nuevo})).first() if nuevo else None
            check("nivel 0, sin municipio, activa", fila is not None and tuple(fila) == (0, None, True), str(fila))
            check("con una invitación vigente", bool(nuevo) and await _escalar(db, """
                SELECT count(*) FROM usuario_invitacion WHERE id_usuario = :u AND activo AND usada_en IS NULL
                   AND vence_en > NOW()""", {"u": nuevo}) == 1)
            check("registra super_alta", bool(nuevo) and await _escalar(db, """
                SELECT count(*) FROM super_admin_acceso WHERE accion = 'super_alta' AND id_usuario = :y
                   AND detalle LIKE :d""", {"y": yo, "d": f"%{email}%"}) >= 1)
        r = await c.post("/api/v1/super/administradores", json={"nombre": "Otra", "apellido": "Vez", "email": email.upper()},
                         headers=h)
        check("el mismo email otra vez → 409", r.status_code == 409, f"{r.status_code} {r.text[:120]}")
        r = await c.post("/api/v1/super/administradores", json={"nombre": "De", "apellido": "Municipio", "email": email_mun},
                         headers=h)
        check("el email de una cuenta de un municipio → 409", r.status_code == 409, f"{r.status_code} {r.text[:120]}")
        r = await c.get("/api/v1/super/administradores", headers=h)
        check("GET lista al nuevo", r.status_code == 200 and any(s["id_usuario"] == nuevo for s in r.json()),
              f"{r.status_code} {r.text[:120]}")

        r = await c.post(f"/api/v1/super/administradores/{yo}/baja", headers=h)
        check("darse de baja a sí mismo → 409", r.status_code == 409, f"{r.status_code} {r.text[:120]}")
        if nuevo:
            r = await c.post(f"/api/v1/super/administradores/{nuevo}/baja", headers=h)
            check("baja de otro super → 200", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
    async with AsyncSessionLocal() as db:
        if nuevo:
            check("quedó inactivo y registra super_baja",
                  await _escalar(db, "SELECT activo FROM usuarios WHERE id_usuario = :u", {"u": nuevo}) is False
                  and await _escalar(db, "SELECT count(*) FROM super_admin_acceso WHERE accion = 'super_baja' "
                                         "AND detalle LIKE :d", {"d": f"%{nuevo}%"}) >= 1)
        # El último super activo: por la API no se llega (el que la pide es otro super activo); el servicio
        # lo frena igual. Se prueba en una transacción que se descarta.
        await db.execute(text("UPDATE usuarios SET activo = FALSE WHERE id_municipio IS NULL AND nivel_acceso = 0 "
                              "AND id_usuario <> :y"), {"y": yo})
        try:
            await dar_de_baja_super(db, id_usuario=yo, id_actor=nuevo or 0)
            check("baja del último super activo → 409", False, "no falló")
        except HTTPException as e:
            check("baja del último super activo → 409", e.status_code == 409, f"{e.status_code} {e.detail}")
        await db.rollback()


async def test_ficha_municipio() -> None:
    print("\ntest_ficha_municipio")
    C = await _municipio_c()
    async with AsyncSessionLocal() as db:
        h = await _super_headers(db)
    async with _cliente() as c:
        r = await c.get("/api/v1/super/alta/opciones", headers=h)
        op = r.json() if r.status_code == 200 else {}
        cats = {x["codigo"]: x["nombre"] for x in op.get("catalogos", [])}
        check("opciones del alta: catálogos con nombre visible", r.status_code == 200 and cats.get("tramites") == "Trámites"
              and cats.get("tipos_reclamo") == "Tipos de reclamo", f"{r.status_code} {str(cats)[:160]}")
        mods = {x["codigo"]: x for x in op.get("modulos", [])}
        check("opciones del alta: módulos con fijo y dependencias", mods.get("usuarios", {}).get("fijo") is True
              and mods.get("turnos", {}).get("dependencias") == ["agenda"] and "municipios" not in mods,
              str(list(mods.items())[:3])[:200])
        r = await c.get(f"/api/v1/super/municipios/{C['id']}", headers=h)
        f = r.json() if r.status_code == 200 else {}
        check("ficha → 200 con el municipio", r.status_code == 200 and f.get("municipio", {}).get("id_municipio") == C["id"],
              f"{r.status_code} {r.text[:160]}")
        check("ficha: módulos con habilitado", any(m["codigo"] == "reclamos" and "habilitado" in m for m in f.get("modulos", [])),
              str(f.get("modulos"))[:160])
        check("ficha: administradores con invitación pendiente",
              any(a["id_usuario"] == C["n1"] and "invitacion_pendiente" in a for a in f.get("administradores", [])),
              str(f.get("administradores"))[:160])
        check("ficha: cupo", set(f.get("cupo", {})) == {"activas", "maximo", "aviso"}, str(f.get("cupo")))
        check("ficha: advierte que no tiene la zona de búsqueda",
              any("zona de búsqueda" in a for a in f.get("advertencias", [])), str(f.get("advertencias")))
        r = await c.get("/api/v1/super/municipios/2000000000", headers=h)
        check("ficha de un municipio inexistente → 404", r.status_code == 404, f"{r.status_code}")
        r = await c.put(f"/api/v1/super/municipios/{C['id']}/tope", json={"maximo": 50}, headers=h)
        check("cambiar el tope → 200", r.status_code == 200 and r.json().get("max_usuarios_activos") == 50,
              f"{r.status_code} {r.text[:120]}")
        r = await c.put(f"/api/v1/super/municipios/{C['id']}/tope", json={"maximo": 0}, headers=h)
        check("tope 0 → 422", r.status_code == 422, f"{r.status_code}")
        r = await c.put(f"/api/v1/super/municipios/{C['id']}/tope", json={"maximo": None}, headers=h)
        check("quitar el tope → 200 sin máximo", r.status_code == 200 and r.json().get("max_usuarios_activos") is None,
              f"{r.status_code} {r.text[:120]}")
    async with AsyncSessionLocal() as db:
        check("el cambio de tope queda registrado", await _escalar(db, """
            SELECT count(*) FROM super_admin_acceso WHERE accion = 'municipio_editar' AND id_municipio = :m
               AND detalle LIKE 'tope%'""", {"m": C["id"]}) >= 2)


# ── Tarea 16 ──────────────────────────────────────────────────────────────────────────────────

class _StorageMock:
    """Storage en memoria: en local las credenciales apuntan al proyecto de prod, así que el smoke nunca
    sube ni borra objetos reales."""

    def __init__(self):
        self.objetos: dict[tuple[str, str], bytes] = {}
        self.borrados: list[tuple[str, str]] = []
        self.demora = 0.0  # segundos que tarda una subida (para que dos pedidos se superpongan)

    def instalar(self):
        from app.core import storage
        from app.core.config import settings as s

        async def subir(path, contenido, content_type, bucket=None):
            await asyncio.sleep(self.demora)
            self.objetos[(bucket or s.SUPABASE_ADJUNTOS_BUCKET, path)] = contenido

        async def borrar(path, bucket=None):
            clave = (bucket or s.SUPABASE_ADJUNTOS_BUCKET, path)
            self.borrados.append(clave)
            self.objetos.pop(clave, None)

        async def firmada(path, ttl_sec=3600, bucket=None):
            return f"https://mock/{bucket or s.SUPABASE_ADJUNTOS_BUCKET}/{path}?ttl={ttl_sec}"

        async def descargar(path, bucket=None):
            return self.objetos[(bucket or s.SUPABASE_ADJUNTOS_BUCKET, path)]

        storage.subir_objeto, storage.borrar_objeto = subir, borrar
        storage.crear_signed_download_url, storage.descargar_objeto = firmada, descargar
        return self


STORAGE = _StorageMock()
GRUPOS_VACIABLES = ["operativo", "contactos", "maestros", "usuarios"]


async def _municipio_v() -> dict:
    """Municipio V para vaciar (local, se conserva en baja al terminar): alta completa por la API y
    filas operativas reales clonadas del municipio base (un reclamo con adjunto, un turno, un trámite
    con documento, una OT y una ficha con foto)."""
    from app.services.municipios.clonado import Clonador, conexion_asyncpg
    ctx = await _contexto_alta()
    suf, cod = _sufijo()
    body = _alta_body(suf, cod, id_provincia=ctx["ba"])
    body["nombre"] = f"Municipio de prueba V {suf}"
    body["subdominio"] = f"v-{suf}"
    # Los tipos de reclamo, de trámite y las prestaciones los trae el clonado de las filas operativas
    # (copiarlos también chocaría con sus únicos por municipio).
    body["copiar"] = ["areas_subareas", "cargos", "encuestas", "agenda"]
    body["modulos"] = ["reclamos", "agenda", "turnos", "tramites", "ot_supervisor", "ot_agente", "encuestas"]
    async with _cliente() as c:
        r = await c.post("/api/v1/super/municipios", json=body, headers=ctx["h"])
    assert r.status_code == 201, r.text
    mid, admin = r.json()["id_municipio"], r.json()["id_administrador"]
    async with AsyncSessionLocal() as db:
        base = await _escalar(db, "SELECT id_municipio FROM municipios WHERE direccion_base")
        conn = await conexion_asyncpg(db)
        cl = Clonador(conn, mid, id_usuario_alta=admin)
        await cl.cargar_clases()
        cl.anclas["usuarios"] = admin
        cl.anclas["agentes"] = await _escalar(db, "SELECT id_agente FROM agentes WHERE id_usuario = :u", {"u": admin})
        for sql in (
            "SELECT id_adjunto FROM reclamo_adjuntos WHERE id_municipio = :b ORDER BY 1 DESC LIMIT 1",
            "SELECT id_turno FROM turnos WHERE id_municipio = :b ORDER BY 1 DESC LIMIT 1",
            "SELECT id_tramite_documento FROM tramite_documento WHERE id_municipio = :b ORDER BY 1 DESC LIMIT 1",
            "SELECT id_ot FROM ordenes_trabajo WHERE id_municipio = :b ORDER BY 1 DESC LIMIT 1",
            "SELECT id_ciudadano FROM ciudadanos WHERE id_municipio = :b AND foto_path IS NOT NULL ORDER BY 1 LIMIT 1",
            "SELECT id_empresa FROM empresas WHERE id_municipio = :b ORDER BY 1 DESC LIMIT 1",
        ):
            tabla = sql.split(" FROM ")[1].split()[0]
            pk = sql.split("SELECT ")[1].split()[0]
            fila = await _escalar(db, sql, {"b": base})
            if fila is not None:
                await cl.clonar(tabla, fila)
        # El adjunto clonado comparte la ruta con el del municipio base: se le da una propia para ver que
        # el vaciado la borra. Un segundo adjunto queda compartido: el vaciado no debe tocar ese archivo.
        await db.execute(text("UPDATE reclamo_adjuntos SET storage_path = 'prueba-vaciado/' || id_adjunto || '.png' "
                              "WHERE id_municipio = :m"), {"m": mid})
        otro = await _escalar(db, "SELECT id_adjunto FROM reclamo_adjuntos WHERE id_municipio = :b "
                                  "ORDER BY 1 DESC OFFSET 1 LIMIT 1", {"b": base})
        if otro is not None:
            await cl.clonar("reclamo_adjuntos", otro)
        await db.commit()
    return {"id": mid, "admin": admin, "nombre": body["nombre"], "h": ctx["h"]}


async def test_clonado_excluidas() -> None:
    """Corte B: una fila excluida por nombre (un tipo de trámite) no vuelve a entrar arrastrada por
    sus hijas (versión, aprobaciones): las hijas que la necesitan se omiten."""
    print("\ntest_clonado_excluidas")
    from app.services.municipios.clonado import Clonador, FilaOmitida, conexion_asyncpg
    mid, _ = await _municipio_sql("puesta_en_marcha")
    async with AsyncSessionLocal() as db:
        base = await _escalar(db, "SELECT id_municipio FROM municipios WHERE direccion_base")
        tt, ver = (await db.execute(text(
            "SELECT v.id_tipo_tramite, v.id_tipo_tramite_version FROM tipo_tramite_version v "
            "WHERE v.id_municipio = :b ORDER BY 2 LIMIT 1"), {"b": base})).one()
        conn = await conexion_asyncpg(db)
        cl = Clonador(conn, mid, permitidas={"tipo_tramite", "tipo_tramite_version"},
                      excluidas={("tipo_tramite", tt)})
        await cl.cargar_clases()
        for tabla, ident in (("tipo_tramite", tt), ("tipo_tramite_version", ver)):
            try:
                await cl.clonar(tabla, ident)
                omitida = False
            except FilaOmitida:
                omitida = True
            check(f"{tabla} de un tipo excluido → se omite", omitida)
        check("no entró ningún tipo de trámite", await _escalar(
            db, "SELECT count(*) FROM tipo_tramite WHERE id_municipio = :m", {"m": mid}) == 0)
        # solo_activas: una versión activa de un tipo dado de baja no lo trae de vuelta.
        fila = (await db.execute(text(
            "SELECT v.id_tipo_tramite_version FROM tipo_tramite_version v JOIN tipo_tramite t USING (id_tipo_tramite) "
            "WHERE v.id_municipio = :b AND v.activo AND NOT t.activo LIMIT 1"), {"b": base})).first()
        if fila is None:
            check("hay una versión activa de un tipo inactivo para probar", False)
        else:
            cl2 = Clonador(conn, mid, permitidas={"tipo_tramite", "tipo_tramite_version"}, solo_activas=True)
            await cl2.cargar_clases()
            try:
                await cl2.clonar("tipo_tramite_version", fila[0])
                omitida = False
            except FilaOmitida:
                omitida = True
            check("versión de un tipo inactivo (solo_activas) → se omite", omitida)
            check("no entró el tipo inactivo", await _escalar(
                db, "SELECT count(*) FROM tipo_tramite WHERE id_municipio = :m", {"m": mid}) == 0)
        await db.rollback()
    await _estado(mid, "baja")


async def _tarea(c, h, id_tarea: str) -> dict:
    r = await c.get(f"/api/v1/super/tareas/{id_tarea}", headers=h)
    return r.json() if r.status_code == 200 else {"estado": f"HTTP {r.status_code}"}


async def _filas_por_grupo(mid: int) -> dict[str, int]:
    async with AsyncSessionLocal() as db:
        tablas = (await db.execute(text(
            "SELECT tabla, grupo FROM municipio_tabla_clase WHERE clase IN ('catalogo', 'operativo', 'mixta')"))).all()
        out: dict[str, int] = {}
        for t, g in tablas:
            if await _escalar(db, "SELECT 1 FROM information_schema.columns WHERE table_name = :t "
                                  "AND column_name = 'id_municipio'", {"t": t}):
                out[g] = out.get(g, 0) + await _escalar(db, f'SELECT count(*) FROM "{t}" WHERE id_municipio = :m',
                                                        {"m": mid})
        return out


async def _municipio_sql(estado: str) -> tuple[int, str]:
    import uuid
    nombre = f"Municipio de prueba G {uuid.uuid4().hex[:6]}"
    async with AsyncSessionLocal() as db:
        mid = await _escalar(db, """
            INSERT INTO municipios (nombre, codigo_pais, pais, provincia, id_provincia, estado)
            VALUES (:n, 'AR', 'Argentina', 'Buenos Aires',
                    (SELECT id_provincia FROM provincias WHERE codigo_pais = 'AR' AND nombre = 'Buenos Aires'), :e)
            RETURNING id_municipio""", {"n": nombre, "e": estado})
        await db.commit()
    invalidar_cache_municipios()
    return mid, nombre


async def test_vaciado_guardas() -> None:
    print("\ntest_vaciado_guardas")
    async with AsyncSessionLocal() as db:
        h = await _super_headers(db)
    prod, nombre_prod = await _municipio_sql("produccion")
    pem, nombre_pem = await _municipio_sql("puesta_en_marcha")
    async with _cliente() as c:
        r = await c.post(f"/api/v1/super/municipios/{prod}/vaciado",
                         json={"grupos": ["operativo"], "confirmacion": nombre_prod}, headers=h)
        check("en producción → 409 texto fijo", r.status_code == 409 and "estuvo en producción" in r.text,
              f"{r.status_code} {r.text[:120]}")
        await c.post(f"/api/v1/super/municipios/{prod}/estado", json={"estado": "baja"}, headers=h)
        r = await c.post(f"/api/v1/super/municipios/{prod}/estado", json={"estado": "reactivar"}, headers=h)
        check("de baja y reactivado vuelve a producción", r.status_code == 200 and r.json()["estado"] == "produccion",
              f"{r.status_code} {r.text[:120]}")
        r = await c.post(f"/api/v1/super/municipios/{prod}/vaciado",
                         json={"grupos": ["operativo"], "confirmacion": nombre_prod}, headers=h)
        check("reactivado después de producción → 409", r.status_code == 409, f"{r.status_code} {r.text[:120]}")
        r = await c.post(f"/api/v1/super/municipios/{pem}/vaciado",
                         json={"grupos": ["operativo"], "confirmacion": "otro nombre"}, headers=h)
        check("confirmación incorrecta → 422", r.status_code == 422 and "Escribí el nombre" in r.text,
              f"{r.status_code} {r.text[:120]}")
        r = await c.post(f"/api/v1/super/municipios/{pem}/vaciado",
                         json={"grupos": ["configuracion"], "confirmacion": nombre_pem}, headers=h)
        check("el grupo configuración no se vacía → 422", r.status_code == 422, f"{r.status_code} {r.text[:120]}")
        async with AsyncSessionLocal() as db:
            base = (await db.execute(text(
                "SELECT id_municipio, nombre FROM municipios WHERE direccion_base LIMIT 1"))).first()
        # Confirmación equivocada a propósito: si la guarda falta, da 422 y no vacía (sin efectos).
        for sufijo, body in (("/plan", {"grupos": ["operativo"]}),
                             ("", {"grupos": ["operativo"], "confirmacion": f"no-es-{base.nombre}"})):
            r = await c.post(f"/api/v1/super/municipios/{base.id_municipio}/vaciado{sufijo}", json=body, headers=h)
            check(f"municipio de las direcciones sin prefijo{sufijo or ''} → 409",
                  r.status_code == 409 and "sin prefijo" in r.text, f"{r.status_code} {r.text[:120]}")
    for mid in (prod, pem):
        await _estado(mid, "baja")


async def test_vaciado_operativo_y_todo() -> None:
    print("\ntest_vaciado_operativo_y_todo")
    STORAGE.instalar()
    V = await _municipio_v()
    antes = await _filas_por_grupo(V["id"])
    async with AsyncSessionLocal() as db:
        cfg_antes = await _escalar(db, "SELECT count(*) FROM configuracion_general WHERE id_municipio = :m", {"m": V["id"]})
        fijas = await _escalar(db, "SELECT count(*) FROM area WHERE id_municipio = :m AND es_sistema", {"m": V["id"]})
        compartidos = {tuple(x) for x in (await db.execute(text("""
            SELECT a.storage_bucket, a.storage_path FROM reclamo_adjuntos a WHERE a.id_municipio = :m AND EXISTS (
              SELECT 1 FROM reclamo_adjuntos b WHERE b.storage_path = a.storage_path AND b.id_municipio <> :m)"""),
            {"m": V["id"]})).all()}
        adjuntos = {tuple(x) for x in (await db.execute(text(
            "SELECT storage_bucket, storage_path FROM reclamo_adjuntos WHERE id_municipio = :m"), {"m": V["id"]})).all()}
        adjuntos -= compartidos
    check("V tiene datos operativos y contactos", antes.get("operativo", 0) > 0 and antes.get("contactos", 0) > 0, str(antes))
    async with _cliente() as c:
        r = await c.post(f"/api/v1/super/municipios/{V['id']}/vaciado/plan", json={"grupos": ["operativo"]}, headers=V["h"])
        plan = r.json() if r.status_code == 200 else []
        check("plan sin escribir: lista tablas y filas", r.status_code == 200 and any(p["tabla"] == "reclamos" and p["filas"] >= 1
              for p in plan), f"{r.status_code} {r.text[:160]}")
        check("el plan no borró nada", (await _filas_por_grupo(V["id"])) == antes)
        r = await c.post(f"/api/v1/super/municipios/{V['id']}/vaciado",
                         json={"grupos": ["operativo"], "confirmacion": V["nombre"]}, headers=V["h"])
        check("vaciar operativo → 202", r.status_code == 202, f"{r.status_code} {r.text[:160]}")
        t = await _tarea(c, V["h"], r.json()["id_tarea"]) if r.status_code == 202 else {}
        check("la tarea terminó ok", t.get("estado") == "ok", str(t)[:200])
        despues = await _filas_por_grupo(V["id"])
        check("0 filas operativas", despues.get("operativo") == 0, str(despues))
        check("los contactos siguen", despues.get("contactos") == antes.get("contactos"), f"{antes} → {despues}")
        check("los adjuntos de Storage se borraron", adjuntos and adjuntos <= set(STORAGE.borrados), str(adjuntos)[:160])
        check("un archivo que usa otro municipio no se borra", compartidos and not (compartidos & set(STORAGE.borrados)),
              str(compartidos)[:160])
        async with AsyncSessionLocal() as db:
            check("la configuración sigue", await _escalar(db, "SELECT count(*) FROM configuracion_general "
                                                               "WHERE id_municipio = :m", {"m": V["id"]}) == cfg_antes)
            check("hay una exportación previa ok", await _escalar(db, """
                SELECT count(*) FROM municipio_tarea WHERE id_municipio = :m AND tipo = 'exportacion' AND estado = 'ok'""",
                {"m": V["id"]}) >= 1)

        r = await c.post(f"/api/v1/super/municipios/{V['id']}/vaciado",
                         json={"grupos": GRUPOS_VACIABLES, "confirmacion": V["nombre"]}, headers=V["h"])
        t = await _tarea(c, V["h"], r.json()["id_tarea"]) if r.status_code == 202 else {}
        check("vaciar los 4 grupos → ok", r.status_code == 202 and t.get("estado") == "ok", f"{r.status_code} {str(t)[:200]}")
        async with AsyncSessionLocal() as db:
            q = lambda sql: _escalar(db, sql, {"m": V["id"]})  # noqa: E731
            check("queda solo el administrador principal", await q(
                "SELECT count(*) FROM usuarios WHERE id_municipio = :m") == 1 and await q(
                f"SELECT id_usuario FROM usuarios WHERE id_municipio = :m") == V["admin"])
            check("su agente y su ficha siguen", await q("SELECT count(*) FROM agentes WHERE id_municipio = :m") == 1
                  and await q("SELECT count(*) FROM ciudadanos WHERE id_municipio = :m") == 1)
            check("sus áreas fijas siguen", await q("SELECT count(*) FROM area WHERE id_municipio = :m AND es_sistema") == fijas
                  and await q("SELECT count(*) FROM area WHERE id_municipio = :m AND NOT es_sistema") == 0)
            check("solo queda la subárea del administrador", await q("SELECT count(*) FROM subarea WHERE id_municipio = :m") == 1)
            check("la configuración y los módulos siguen", await q(
                "SELECT count(*) FROM configuracion_general WHERE id_municipio = :m") == cfg_antes and await q(
                "SELECT count(*) FROM municipio_modulo WHERE id_municipio = :m") > 0)
            rotas = await q("""
                SELECT count(*) FROM configuracion_general cg WHERE cg.id_municipio = :m AND cg.valor ~ '^[0-9]+$' AND (
                  (cg.clave = 'id_area_salud' AND NOT EXISTS (SELECT 1 FROM area a WHERE a.id_area = cg.valor::int AND a.id_municipio = :m))
                  OR (cg.clave = 'id_espacio_guardia' AND NOT EXISTS (SELECT 1 FROM espacios_agenda e
                                                                     WHERE e.id_espacio = cg.valor::int AND e.id_municipio = :m)))""")
            check("las claves por id apuntan a filas existentes", rotas == 0, str(rotas))
        h_admin = _token(V["admin"], V["id"])
        quinientos = []
        for ruta in ("/api/v1/buc/ciudadanos", "/api/v1/buc/empresas", "/api/v1/buc/usuarios", "/api/v1/reclamos",
                     "/api/v1/turnos", "/api/v1/tramites", "/api/v1/admin/area", "/api/v1/admin/subarea",
                     "/api/v1/admin/tipo_reclamo", "/api/v1/dashboard/resumen", "/api/v1/ordenes-trabajo",
                     "/api/v1/agenda/espacios", "/api/v1/config/identidad/actual"):
            r = await c.get(ruta, headers=h_admin)
            if r.status_code >= 500:
                quinientos.append(f"{ruta} {r.status_code}")
        check("los listados de V no dan 500", not quinientos, str(quinientos))

        STORAGE.demora = 1.0
        r1, r2 = await asyncio.gather(
            c.post(f"/api/v1/super/municipios/{V['id']}/vaciado", json={"grupos": ["operativo"], "confirmacion": V["nombre"]},
                   headers=V["h"]),
            c.post(f"/api/v1/super/municipios/{V['id']}/vaciado", json={"grupos": ["operativo"], "confirmacion": V["nombre"]},
                   headers=V["h"]))
        codigos = sorted((r1.status_code, r2.status_code))
        STORAGE.demora = 0.0
        check("dos vaciados a la vez: uno 202, el otro 409", codigos == [202, 409]
              and "ya hay un vaciado en curso" in (r1.text + r2.text).lower(), f"{codigos} {(r1.text + r2.text)[:160]}")
    await _estado(V["id"], "baja")


async def test_exportacion_retencion() -> None:
    import io
    import json
    import zipfile
    print("\ntest_exportacion_retencion")
    STORAGE.instalar()
    V = await _municipio_v()
    async with _cliente() as c:
        r = await c.post(f"/api/v1/super/municipios/{V['id']}/exportaciones", headers=V["h"])
        check("exportar → 202", r.status_code == 202, f"{r.status_code} {r.text[:160]}")
        id_tarea = r.json().get("id_tarea") if r.status_code == 202 else None
        t = await _tarea(c, V["h"], id_tarea) if id_tarea else {}
        check("la exportación terminó ok, con archivo y vencimiento", t.get("estado") == "ok" and t.get("archivo")
              and t.get("vence_en"), str(t)[:200])
        contenido = STORAGE.objetos.get(("exportaciones", t.get("archivo") or ""))
        check("el zip está en el bucket exportaciones", contenido is not None)
        if contenido:
            z = zipfile.ZipFile(io.BytesIO(contenido))
            nombres = z.namelist()
            ajenas = []
            for n in nombres:
                filas = json.loads(z.read(n))
                ajenas += [n for f in filas if "id_municipio" in f and f["id_municipio"] != V["id"]]
            check("un JSON por tabla, con reclamos y ciudadanos", "reclamos.json" in nombres and "ciudadanos.json" in nombres,
                  str(nombres[:8]))
            check("ninguna fila de otro municipio", not ajenas, str(ajenas[:5]))
        r = await c.get(f"/api/v1/super/municipios/{V['id']}/exportaciones", headers=V["h"])
        check("aparece en la lista vigente", r.status_code == 200 and any(e["id_tarea"] == id_tarea for e in r.json()),
              f"{r.status_code} {r.text[:120]}")
        r = await c.get(f"/api/v1/super/municipios/{V['id']}/exportaciones/{id_tarea}/descarga", headers=V["h"])
        check("descarga: URL firmada de 10 minutos", r.status_code == 200 and "ttl=600" in r.json().get("url", ""),
              f"{r.status_code} {r.text[:120]}")
        async with AsyncSessionLocal() as db:
            check("la descarga queda registrada", await _escalar(db, """
                SELECT count(*) FROM super_admin_acceso WHERE accion = 'exportacion' AND id_municipio = :m
                   AND detalle LIKE 'descarga%'""", {"m": V["id"]}) >= 1)
            await db.execute(text("UPDATE municipio_tarea SET vence_en = NOW() - interval '1 day' WHERE id_tarea = :t"),
                             {"t": id_tarea})
            await db.commit()
        r = await c.post("/api/v1/municipios/mantenimiento/purgar-exportaciones",
                         headers={"X-Dispatcher-Token": settings.DISPATCHER_TOKEN})
        check("purga → 200", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
        check("el objeto vencido se borró", ("exportaciones", t.get("archivo")) not in STORAGE.objetos)
        r = await c.get(f"/api/v1/super/municipios/{V['id']}/exportaciones", headers=V["h"])
        check("ya no aparece en la lista", r.status_code == 200 and not any(e["id_tarea"] == id_tarea for e in r.json()))
        r = await c.post("/api/v1/municipios/mantenimiento/purgar-exportaciones", headers={"X-Dispatcher-Token": "x"})
        check("purga sin token → 401", r.status_code == 401, str(r.status_code))
    await _estado(V["id"], "baja")


# ── Tarea 17 ──────────────────────────────────────────────────────────────────────────────────

async def test_municipio_vacio() -> None:
    """Un municipio recién dado de alta sin copiar catálogos: las pantallas no dan 500 y lo que falta
    da un error con mensaje (guía de arranque, R3-R10)."""
    from fastapi import HTTPException
    from app.services.estados_ot import id_estado_ot
    from app.services.municipios.defectos import id_nacionalidad_defecto, id_tipo_representacion_defecto
    print("\ntest_municipio_vacio")
    ctx = await _contexto_alta()
    suf, cod = _sufijo()
    body = _alta_body(suf, cod, id_provincia=ctx["ba"])
    body["nombre"] = f"Municipio de prueba W {suf}"
    body["subdominio"] = f"w-{suf}"
    body["copiar"] = []
    body["modulos"] = ["reclamos", "agenda", "turnos", "tramites", "ot_supervisor", "ot_agente", "ot_auditoria",
                       "emergencias", "encuestas", "entradas", "bi", "agentes_gestion"]
    async with _cliente() as c:
        r = await c.post("/api/v1/super/municipios", json=body, headers=ctx["h"])
        assert r.status_code == 201, r.text
        W, admin = r.json()["id_municipio"], r.json()["id_administrador"]
        h = _token(admin, W)

        quinientos = []
        for ruta in ("/api/v1/buc/ciudadanos", "/api/v1/buc/empresas", "/api/v1/buc/usuarios", "/api/v1/buc/usuarios/cupo",
                     "/api/v1/reclamos", "/api/v1/reclamos/catalogo/tipos", "/api/v1/ordenes-trabajo", "/api/v1/turnos",
                     "/api/v1/turnos/prestaciones", "/api/v1/tramites", "/api/v1/tramites/tipos", "/api/v1/emergencias/eventos",
                     "/api/v1/admin/area", "/api/v1/admin/subarea", "/api/v1/admin/tipo_reclamo", "/api/v1/admin/agentes",
                     "/api/v1/admin/equipos", "/api/v1/admin/configuracion_general", "/api/v1/agenda/espacios",
                     "/api/v1/dashboard/resumen", "/api/v1/config/identidad/actual", "/api/v1/encuestas/plantillas",
                     "/api/v1/bi/operativo/resumen", "/api/v1/notificaciones"):
            r = await c.get(ruta, headers=h)
            if r.status_code >= 500:
                quinientos.append(f"{ruta} {r.status_code}")
        check("los listados del municipio vacío no dan 500", not quinientos, str(quinientos))

        async with AsyncSessionLocal() as db:
            await db.execute(text("DELETE FROM configuracion_general WHERE id_municipio = :m AND clave = 'municipio_descripcion'"),
                             {"m": W})
            await db.commit()
        r = await c.put("/api/v1/config/identidad", json={"municipio_descripcion": "Prueba W"}, headers=h)
        check("R3: Identidad crea la clave que falta", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
        async with AsyncSessionLocal() as db:
            check("R3: la clave quedó con tipo y activa", tuple((await db.execute(text(
                "SELECT valor, tipo, activo FROM configuracion_general WHERE id_municipio = :m AND clave = 'municipio_descripcion'"),
                {"m": W})).one()) == ("Prueba W", "string", True))

        r = await c.get("/api/v1/geo/buscar", params={"q": "Calle Falsa 123"}, headers=h)
        check("R4: sin zona de búsqueda → 409 con mensaje", r.status_code == 409 and "zona de búsqueda" in r.text,
              f"{r.status_code} {r.text[:120]}")

        for i in range(5):
            await c.post("/api/v1/auth/login", json={"identificador": "repetido.tope@prueba-aislamiento.com.ar",
                                                     "password": "incorrecta"},
                         headers={"Origin": f"https://w-{suf}.zge.zaris.com.ar"})
        r = await c.post("/api/v1/auth/login", json={"identificador": "repetido.tope@prueba-aislamiento.com.ar",
                                                     "password": "incorrecta"})
        check("límite de intentos por mail separado por municipio", r.status_code != 429, str(r.status_code))

    async with AsyncSessionLocal() as db:
        nac = await id_nacionalidad_defecto(db, W)
        rep = await id_tipo_representacion_defecto(db, W)
        check("R9: nacionalidad por defecto del municipio (la de su país)", await _escalar(
            db, "SELECT pais FROM nacionalidades WHERE id = :i", {"i": nac}) == "Argentina", str(nac))
        check("R10: tipo de representación por defecto", await _escalar(
            db, "SELECT tipo FROM tipo_representacion WHERE id = :i", {"i": rep}) == "Representante Legal", str(rep))
        check("R9/R10: claves sembradas por el alta", await _escalar(db, """
            SELECT count(*) FROM configuracion_general WHERE id_municipio = :m
               AND clave IN ('id_nacionalidad_defecto', 'id_tipo_representacion_defecto') AND valor ~ '^[0-9]+$'""",
            {"m": W}) == 2)
        await db.execute(text("UPDATE estado_ot SET nombre = 'Terminada (prueba)' WHERE nombre = 'Terminada'"))
        try:
            await id_estado_ot(db, "Terminada")
            check("R7: estado de OT faltante → 409", False, "no falló")
        except HTTPException as e:
            check("R7: estado de OT faltante → 409", e.status_code == 409 and "Terminada" in e.detail, f"{e.status_code} {e.detail}")
        await db.rollback()
    await _estado(W, "baja")


# ── Tarea 18 ──────────────────────────────────────────────────────────────────────────────────

async def test_aislamiento_modelo() -> None:
    """El municipio modelo no aparece en ninguna respuesta de un municipio: ni en los listados de
    catálogos ni por id (404), para el administrador del municipio base y el de uno dado de alta."""
    print("\ntest_aislamiento_modelo")
    ctx = await _contexto_alta()
    suf, cod = _sufijo()
    async with _cliente() as c:
        r = await c.post("/api/v1/super/municipios", json=_alta_body(suf, cod, id_provincia=ctx["ba"]), headers=ctx["h"])
        assert r.status_code == 201, r.text
        nuevo, admin_nuevo = r.json()["id_municipio"], r.json()["id_administrador"]
    async with AsyncSessionLocal() as db:
        modelo = await _escalar(db, "SELECT id_municipio FROM municipios WHERE estado = 'modelo'")
        uid_base, base = await _admin_base(db)
        ids_modelo = {}
        for tabla, pk in (("area", "id_area"), ("subarea", "id_subarea"), ("tipo_reclamo", "id_tipo_reclamo"),
                          ("cargos", "id_cargo"), ("tipo_tramite", "id_tipo_tramite")):
            ids_modelo[(tabla, pk)] = {x[0] for x in (await db.execute(text(
                f"SELECT {pk} FROM {tabla} WHERE id_municipio = :m"), {"m": modelo})).all()}
    check("el modelo tiene catálogos para probar", sum(len(v) for v in ids_modelo.values()) > 0)
    async with _cliente() as c:
        for quien, h in (("base", _token(uid_base, base)), ("dado de alta", _token(admin_nuevo, nuevo))):
            vistos, por_id = [], []
            for (tabla, pk), ids in ids_modelo.items():
                r = await c.get(f"/api/v1/admin/{tabla}", headers=h)
                filas = r.json() if r.status_code == 200 else []
                filas = filas.get("items", filas) if isinstance(filas, dict) else filas
                vistos += [f"{tabla}:{f[pk]}" for f in filas if isinstance(f, dict) and f.get(pk) in ids]
                for i in list(ids)[:3]:
                    r = await c.get(f"/api/v1/admin/{tabla}/{i}", headers=h)
                    if r.status_code != 404:
                        por_id.append(f"{tabla}/{i} {r.status_code}")
            check(f"admin {quien}: ningún catálogo del modelo en los listados", not vistos, str(vistos[:5]))
            check(f"admin {quien}: el modelo por id → 404", not por_id, str(por_id[:5]))
        r = await c.get("/api/v1/config/identidad", params={"m": "modelo"})
        check("el modelo no tiene identidad pública", r.status_code in (404, 200) and "Modelo ZARIS" not in r.text,
              f"{r.status_code} {r.text[:120]}")
    await _estado(nuevo, "baja")


# ── Revisión final del branch ──────────────────────────────────────────────────────────────────

async def test_revision_final() -> None:
    """Arreglos de la revisión final: foto de usuario fuera de su ruta, módulo deshabilitado con un
    token basura, claves por id que no se pisan, exportación sin secretos y administrador principal
    activo."""
    import uuid
    from app.core import storage
    from app.services.municipios import vaciado
    from app.services.municipios.exportacion import armar_zip
    print("\ntest_revision_final")
    C = await _municipio_c()
    async with AsyncSessionLocal() as db:
        uid, mun = await _admin_base(db)
        foto_antes = await _escalar(db, "SELECT foto_url FROM usuarios WHERE id_usuario = :u", {"u": uid})
    h = _token(uid, mun)

    # #1 La foto de un usuario solo puede ser su propio avatar en config-assets.
    async with _cliente() as c:
        ajena = storage.url_publica("usuarios/1/avatar-x.png", "config-assets").replace(
            "/config-assets/", "/config-assets/../exportaciones/m1/")
        r = await c.put("/api/v1/auth/me/foto", json={"foto_url": ajena}, headers=h)
        check("#1 foto_url con ruta ajena → 422", r.status_code == 422, f"{r.status_code} {r.text[:100]}")
        r = await c.put("/api/v1/auth/me/foto", json={"foto_url": "https://otro.sitio/x.png"}, headers=h)
        check("#1 foto_url de otro sitio → 422", r.status_code == 422, f"{r.status_code}")
        propia = storage.url_publica(f"usuarios/{uid}/avatar-{uuid.uuid4()}.png", "config-assets")
        r = await c.put("/api/v1/auth/me/foto", json={"foto_url": propia}, headers=h)
        check("#1 su propio avatar → 200", r.status_code == 200, f"{r.status_code} {r.text[:100]}")
        await c.put("/api/v1/auth/me/foto", json={"foto_url": foto_antes or ""}, headers=h)
    check("#1 Storage rechaza rutas con '..'", not storage.ruta_valida("usuarios/1/../../exportaciones/a.zip")
          and not storage.ruta_valida("a/%2e%2e/b") and storage.ruta_valida("usuarios/1/avatar-a.png"))
    async with AsyncSessionLocal() as db:
        _, pks, _ = await vaciado._metadatos(db)
        await db.execute(text("UPDATE usuarios SET foto_url = :f WHERE id_usuario = :u"),
                         {"f": ajena, "u": C["n4"]})
        archivos = await vaciado._archivos(db, vaciado.Plan(borrar={"usuarios": {C["n4"]}}), pks)
        check("#1 el vaciado no borra una foto fuera de la ruta del usuario", archivos == [], str(archivos))
        await db.rollback()

    # #2 Un módulo deshabilitado da 404 aunque venga un token basura.
    await _modulos(C["id"], turnos=False)
    try:
        async with _cliente() as c:
            r = await c.get("/api/v1/turnos/publico/prestaciones",
                            headers={"Origin": ORIGEN_C_VECINOS, "Authorization": "Bearer basura"})
            check("#2 público con token basura y módulo apagado → 404", r.status_code == 404, f"{r.status_code}")
    finally:
        await _modulos(C["id"])

    # #3 El vaciado solo re-siembra una clave por id si ya no apunta a una fila activa.
    async with AsyncSessionLocal() as db:
        antes = await _escalar(db, "SELECT valor FROM configuracion_general WHERE id_municipio = :m "
                                   "AND clave = 'id_area_salud'", {"m": mun})
        await db.execute(text("UPDATE area SET nombre = 'Salud' WHERE id_area::text = :a"), {"a": antes})
        await vaciado.resembrar_claves_rotas(db, mun)
        despues = await _escalar(db, "SELECT valor FROM configuracion_general WHERE id_municipio = :m "
                                     "AND clave = 'id_area_salud'", {"m": mun})
        check("#3 un área renombrada no pierde la clave", despues == antes, f"{antes} → {despues}")
        await db.rollback()

    # #4 La exportación no lleva secretos de cuentas.
    async with AsyncSessionLocal() as db:
        import io
        import json
        import zipfile
        contenido, _ = await armar_zip(db, C["id"])
    z = zipfile.ZipFile(io.BytesIO(contenido))
    usuarios = json.loads(z.read("usuarios.json"))
    check("#4 la exportación no trae password_hash", usuarios and all("password_hash" not in u for u in usuarios),
          str(list(usuarios[0])[:12]) if usuarios else "sin filas")

    # #11 El administrador principal protegido es el primer nivel 1 ACTIVO.
    async with AsyncSessionLocal() as db:
        otro = await _escalar(db, """
            INSERT INTO usuarios (nombre, nivel_acceso, username, password_hash, id_municipio, activo, buc_acceso, email)
            VALUES ('Prueba C nivel 1 bis', 1, :e, 'x', :m, TRUE, FALSE, :e) RETURNING id_usuario""",
            {"e": f"admin.bis.{uuid.uuid4().hex[:6]}@prueba-aislamiento.com.ar", "m": C["id"]})
        await db.execute(text("UPDATE usuarios SET activo = FALSE WHERE id_usuario = :u"), {"u": C["n1"]})
        grupos, pks, fks = await vaciado._metadatos(db)
        prot = await vaciado._protegidos(db, C["id"], grupos, pks, fks)
        check("#11 se protege al administrador activo, no al dado de baja", prot.get("usuarios") == {otro},
              str(prot.get("usuarios")))
        await db.rollback()


async def test_zona_busqueda() -> None:
    """Prueba de cierre 2026-10-28: «lat, lon» pegado en la latitud se guardaba y el buscador de
    direcciones respondía 409 sin aviso. La API rechaza la zona inválida y la ficha avisa mientras
    falte alguna de las tres claves."""
    print("\ntest_zona_busqueda")
    C = await _municipio_c()
    claves = ("geo_bbox_centro_lat", "geo_bbox_centro_lon", "geo_bbox_delta_grados")

    async def borrar() -> None:
        async with AsyncSessionLocal() as db:
            await db.execute(text("DELETE FROM configuracion_general WHERE id_municipio = :m AND clave = ANY(:c)"),
                             {"m": C["id"], "c": list(claves)})
            await db.commit()

    await borrar()
    h = _token(C["n1"], C["id"])
    base = "/api/v1/admin/configuracion_general"
    nueva = lambda clave, valor: {"clave": clave, "valor": valor, "tipo": "string", "descripcion": clave,  # noqa: E731
                                  "activo": True}
    try:
        async with _cliente() as c:
            r = await c.post(base, json=nueva("geo_bbox_centro_lat", "-33.6948, -60.6339"), headers=h)
            check("«lat, lon» en la latitud → 422", r.status_code == 422, f"{r.status_code} {r.text[:120]}")
            r = await c.post(base, json=nueva("geo_bbox_centro_lat", "-33.6948"), headers=h)
            check("latitud válida → 201", r.status_code == 201, f"{r.status_code} {r.text[:120]}")
            id_lat = r.json().get("id_config") if r.status_code == 201 else None
            for valor, esperado in (("abc", 422), ("-91", 422), ("", 200), ("-33.6948", 200)):
                r = await c.put(f"{base}/{id_lat}", json={"valor": valor}, headers=h)
                check(f"PUT latitud «{valor}» → {esperado}", r.status_code == esperado, f"{r.status_code} {r.text[:120]}")
            r = await c.post(base, json=nueva("geo_bbox_centro_lon", "-181"), headers=h)
            check("longitud -181 → 422", r.status_code == 422, f"{r.status_code}")
            r = await c.post(base, json=nueva("geo_bbox_centro_lon", "-60.6339"), headers=h)
            check("longitud válida → 201", r.status_code == 201, f"{r.status_code}")
            hs = {**await _super_headers_sin_db(), "X-Municipio": str(C["id"])}
            r = await c.get(f"/api/v1/super/municipios/{C['id']}", headers=hs)
            check("ficha: sin radio, avisa que la zona no está completa",
                  any("zona de búsqueda" in a for a in r.json().get("advertencias", [])), r.text[:200])
            r = await c.post(base, json=nueva("geo_bbox_delta_grados", "0"), headers=h)
            check("radio 0 → 422", r.status_code == 422, f"{r.status_code}")
            r = await c.post(base, json=nueva("geo_bbox_delta_grados", "0.1"), headers=h)
            check("radio 0.1 → 201", r.status_code == 201, f"{r.status_code}")
            r = await c.get(f"/api/v1/super/municipios/{C['id']}", headers=hs)
            check("ficha: con la zona completa, sin aviso", r.json().get("advertencias") == [], r.text[:200])
            r = await c.post(base, json=nueva("encuestas_activas_prueba_zona", "lo que sea"), headers=h)
            check("otra clave con texto libre no se valida → 201", r.status_code == 201, f"{r.status_code}")
    finally:
        await borrar()
        async with AsyncSessionLocal() as db:
            await db.execute(text("DELETE FROM configuracion_general WHERE id_municipio = :m "
                                  "AND clave = 'encuestas_activas_prueba_zona'"), {"m": C["id"]})
            await db.commit()


async def test_encuadre_mapas() -> None:
    """Los mapas arrancan en el contorno, la zona de búsqueda o el país, nunca en un municipio fijo
    (César, 2026-10-28)."""
    print("\ntest_encuadre_mapas")
    C = await _municipio_c()
    claves = ("geo_bbox_centro_lat", "geo_bbox_centro_lon", "geo_bbox_delta_grados", "geo_limite_geojson")

    async def poner(valores: dict) -> None:
        async with AsyncSessionLocal() as db:
            await db.execute(text("DELETE FROM configuracion_general WHERE id_municipio = :m AND clave = ANY(:c)"),
                             {"m": C["id"], "c": list(claves)})
            for clave, valor in valores.items():
                await db.execute(text("""
                    INSERT INTO configuracion_general (clave, valor, tipo, descripcion, activo, id_municipio)
                    VALUES (:c, :v, 'string', :d, TRUE, :m)"""), {"c": clave, "v": valor, "d": clave, "m": C["id"]})
            await db.commit()

    h = _token(C["n2"], C["id"])
    try:
        async with _cliente() as c:
            await poner({})
            r = await c.get("/api/v1/geo/encuadre", headers=h)
            e = r.json() if r.status_code == 200 else {}
            check("sin contorno ni zona → el país (Argentina)", e.get("origen") == "pais" and e.get("sur") == -55.1
                  and e.get("norte") == -21.7, f"{r.status_code} {r.text[:160]}")
            await poner({"geo_bbox_centro_lat": "-33.7", "geo_bbox_centro_lon": "-60.6"})
            r = await c.get("/api/v1/geo/encuadre", headers=h)
            check("zona incompleta (sin radio) → el país", r.json().get("origen") == "pais", r.text[:160])
            await poner({"geo_bbox_centro_lat": "-33.7", "geo_bbox_centro_lon": "-60.6", "geo_bbox_delta_grados": "0.1"})
            r = await c.get("/api/v1/geo/encuadre", headers=h)
            e = r.json()
            check("zona completa → la zona", e.get("origen") == "zona" and abs(e["sur"] + 33.8) < 1e-9
                  and abs(e["este"] + 60.5) < 1e-9, r.text[:160])
            poligono = '{"type":"Polygon","coordinates":[[[-60.7,-33.8],[-60.5,-33.8],[-60.5,-33.6],[-60.7,-33.6],[-60.7,-33.8]]]}'
            await poner({"geo_bbox_centro_lat": "-33.7", "geo_bbox_centro_lon": "-60.6", "geo_bbox_delta_grados": "0.5",
                         "geo_limite_geojson": poligono})
            r = await c.get("/api/v1/geo/encuadre", headers=h)
            e = r.json()
            check("con contorno → el contorno, aunque haya zona", e.get("origen") == "contorno" and e.get("sur") == -33.8
                  and e.get("oeste") == -60.7 and e.get("norte") == -33.6 and e.get("este") == -60.5, r.text[:160])
            r = await c.get("/api/v1/geo/encuadre")
            check("sin token → 401", r.status_code == 401, f"{r.status_code}")
    finally:
        await poner({})


async def _super_headers_sin_db() -> dict:
    async with AsyncSessionLocal() as db:
        return await _super_headers(db)


PRUEBAS = {f.__name__: f for f in (test_base_f4, test_triggers_f4, test_acciones_super, test_links_por_municipio,
                                     test_modelo, test_area_fija_api, test_tope, test_super_admins, test_ficha_municipio,
                                     test_vaciado_guardas, test_clonado_excluidas, test_vaciado_operativo_y_todo, test_exportacion_retencion, test_municipio_vacio, test_aislamiento_modelo, test_revision_final,
                                     test_alta_validaciones, test_alta_partido_zona_codigo, test_alta_ok, test_alta_atomica, test_alta_agrega_fijos, test_alta_concurrente,
                                     test_invitacion, test_invitacion_token_malformado, test_estados,
                                     test_alta_por_origen,
                                     test_estado_baja, test_modelo_no_operable, test_demo_por_estado,
                                     test_geo_catalogo, test_municipio_provincia,
                                     test_modulo_404, test_modulos_permitidos_municipio, test_nivel_por_municipio,
                                     test_dependencias, test_efectos_apagados, test_zona_busqueda,
                                     test_encuadre_mapas)}


async def main(nombres: list[str]) -> int:
    async with AsyncSessionLocal() as db:
        CODIGOS_USADOS.update(r[0] for r in (await db.execute(text(
            "SELECT codigo_corto FROM municipios WHERE codigo_corto IS NOT NULL"))).all())
    for nombre in nombres or PRUEBAS:
        await PRUEBAS[nombre]()
    fallas = [r for r in RES if not r[1]]
    print(f"\nRESULTADO: {len(RES) - len(fallas)} OK / {len(fallas)} FAIL")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
