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


PRUEBAS = {f.__name__: f for f in (test_base_f4, test_triggers_f4, test_acciones_super,
                                     test_estado_baja, test_modelo_no_operable, test_demo_por_estado,
                                     test_geo_catalogo, test_municipio_provincia,
                                     test_modulo_404, test_modulos_permitidos_municipio, test_nivel_por_municipio,
                                     test_dependencias, test_efectos_apagados)}


async def main(nombres: list[str]) -> int:
    for nombre in nombres or PRUEBAS:
        await PRUEBAS[nombre]()
    fallas = [r for r in RES if not r[1]]
    print(f"\nRESULTADO: {len(RES) - len(fallas)} OK / {len(fallas)} FAIL")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
