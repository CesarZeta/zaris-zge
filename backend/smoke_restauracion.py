# -*- coding: utf-8 -*-
"""
Smoke de la restauración (IT-01 F6.5, PLAN_MULTI_MUNICIPIO_F6_5.md Task 2).

Arma la exportación de San Andrés con el código de la aplicación (armar_zip), vuelca estructura y
globales de zaris_dev, la restaura en una base nueva y verifica: conteos iguales al zip, integridad
(post-data), secuencias, que una base no vacía no se toca y que ninguna clave viaja. Después levanta el
backend en proceso contra la base restaurada (con la barrera apagada y prendida) y compara el inicio y
el listado de reclamos con los de zaris_dev.

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_restauracion.py

SOLO LOCAL. Crea y borra la base zaris_restaurada_smoke. Necesita pg_dump/psql 17 (PG_BIN si no
están en el PATH).
"""
import asyncio
import json
import os
import subprocess
import sys
import tempfile

os.environ.setdefault("ENV_FILE", ".env.local")
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

HERRAMIENTA = os.path.join(os.path.dirname(AQUI), "tools", "restaurar_exportacion.py")
DESTINO = "zaris_restaurada_smoke"
CLAVE = "123456"
RES: list[tuple[str, bool, str]] = []


def check(nombre: str, ok: bool, detalle: str = "") -> None:
    RES.append((nombre, ok, detalle))
    print(f"  {'OK  ' if ok else 'FAIL'} {nombre}{(' — ' + detalle) if detalle and not ok else ''}")


# ── Modo hijo: el backend en proceso contra la base de POSTGRES_DB ─────────────

async def backend() -> None:
    import httpx
    from sqlalchemy import text
    from app.core.config import settings
    settings.RESEND_API_KEY = ""
    from app.core.sistema import SesionSistema
    from app.main import app

    async with SesionSistema() as db:
        email = (await db.execute(text(
            "SELECT email FROM usuarios WHERE id_municipio = 1 AND nivel_acceso = 1 AND activo AND email IS NOT NULL "
            "ORDER BY id_usuario LIMIT 1"))).scalar()
    out: dict = {"base": settings.POSTGRES_DB, "barrera": settings.DB_BARRERA, "email": email}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=120) as c:
        r = await c.post("/api/v1/auth/login", json={"identificador": email, "password": CLAVE})
        out["login"] = r.status_code
        tok = r.json().get("access_token") if r.status_code == 200 else None
        if tok:
            h = {"Authorization": f"Bearer {tok}"}
            r = await c.get("/api/v1/dashboard/resumen", headers=h)
            out["resumen"] = r.status_code
            out["resumen_json"] = r.json() if r.status_code == 200 else r.text[:300]
            r = await c.get("/api/v1/reclamos", params={"limit": 20}, headers=h)
            out["reclamos"] = r.status_code
            out["reclamos_total"] = r.headers.get("X-Total-Count")
            out["reclamos_ids"] = [x.get("id_reclamo") for x in r.json()] if r.status_code == 200 else None
    print("RESULTADO " + json.dumps(out, ensure_ascii=False, default=str))


def correr_backend(base: str, barrera: bool) -> dict:
    env = {**os.environ, "POSTGRES_DB": base, "DB_BARRERA": "true" if barrera else "false", "PYTHONPATH": AQUI}
    r = subprocess.run([sys.executable, os.path.abspath(__file__), "--backend"], env=env, cwd=AQUI,
                       capture_output=True, text=True, encoding="utf-8")
    linea = next((l for l in r.stdout.splitlines() if l.startswith("RESULTADO ")), None)
    if not linea:
        return {"error": (r.stderr or r.stdout)[-1500:]}
    return json.loads(linea[len("RESULTADO "):])


# ── Orquestador ───────────────────────────────────────────────────────────────

def herramienta(args: list[str], **env) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, HERRAMIENTA, *args], env={**os.environ, **env},
                          capture_output=True, text=True, encoding="utf-8")


async def main() -> int:
    import asyncpg
    import bcrypt
    from app.core.config import settings
    if settings.POSTGRES_DB != "zaris_dev" or settings.POSTGRES_SERVER not in ("127.0.0.1", "localhost"):
        sys.exit("ABORT: este smoke es SOLO LOCAL (la base configurada no es zaris_dev).")
    from app.core.database import sesion_municipio
    from app.services.municipios.exportacion import armar_zip

    u, p, h, pt = settings.POSTGRES_USER, settings.POSTGRES_PASSWORD, settings.POSTGRES_SERVER, settings.POSTGRES_PORT
    url = lambda db: f"postgresql://{u}:{p}@{h}:{pt}/{db}"  # noqa: E731
    tmp = tempfile.mkdtemp(prefix="smoke_restauracion_")

    print("1. Exportación, volcado y base nueva")
    async with sesion_municipio(1) as db:
        contenido, cantidades = await armar_zip(db, 1)
    ruta_zip = os.path.join(tmp, "san_andres.zip")
    with open(ruta_zip, "wb") as f:
        f.write(contenido)
    print(f"  zip: {sum(cantidades.values())} filas en {len(cantidades)} tablas")
    r = herramienta(["volcar", "--salida", os.path.join(tmp, "base")], ORIGEN_URL=url("zaris_dev"))
    check("volcar", r.returncode == 0, r.stderr[-500:])
    check("volcar_sin_clave_en_la_salida", p not in r.stdout and p not in open(
        os.path.join(tmp, "base", "manifiesto.json"), encoding="utf-8").read())

    adm = await asyncpg.connect(url("postgres"))
    await adm.execute(f'DROP DATABASE IF EXISTS "{DESTINO}"')
    await adm.execute(f'CREATE DATABASE "{DESTINO}"')

    print("\n2. Base no vacía")
    c = await asyncpg.connect(url(DESTINO))
    await c.execute("CREATE TABLE public.ya_estaba (x int)")
    await c.close()
    r = herramienta(["restaurar", "--base", os.path.join(tmp, "base"), "--zip", ruta_zip], DESTINO_URL=url(DESTINO))
    c = await asyncpg.connect(url(DESTINO))
    sigue = await c.fetchval("SELECT to_regclass('public.ya_estaba') IS NOT NULL")
    tablas = await c.fetchval("SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")
    await c.close()
    check("destino_no_vacio", r.returncode != 0 and sigue and tablas == 1, f"rc={r.returncode} tablas={tablas}")
    await adm.execute(f'DROP DATABASE "{DESTINO}"')
    await adm.execute(f'CREATE DATABASE "{DESTINO}"')

    print("\n3. Restauración")
    r = herramienta(["restaurar", "--base", os.path.join(tmp, "base"), "--zip", ruta_zip], DESTINO_URL=url(DESTINO))
    try:
        inf = json.loads(r.stdout)
    except ValueError:
        inf = {}
    check("restaurar_ok", r.returncode == 0 and inf.get("ok"), (r.stderr or r.stdout)[-800:])
    check("post_data_ok", inf.get("post_data") == "ok", str(inf.get("error", ""))[:300])
    omitidas = sum(inf.get("omitidas_sin_secreto", {}).values())
    check("conteos_iguales", inf.get("conteos_distintos") == {} and inf.get("filas", 0) + omitidas == sum(
        cantidades.values()), f"{inf.get('conteos_distintos')} filas={inf.get('filas')}+{omitidas}")
    check("barrera_aplicada", inf.get("barrera") == "ok")
    print(f"  {inf.get('tablas')} tablas, {inf.get('filas')} filas, sin secreto {inf.get('omitidas_sin_secreto')}, "
          f"cuentas no exportadas {inf.get('cuentas_no_exportadas')}")

    c = await asyncpg.connect(url(DESTINO))
    o = await asyncpg.connect(url("zaris_dev"))
    try:
        malas = []
        for s in await c.fetch("""
                SELECT s.relname AS seq, t.relname AS tabla, a.attname AS col
                  FROM pg_class s JOIN pg_depend d ON d.objid = s.oid AND d.deptype IN ('a', 'i')
                  JOIN pg_class t ON t.oid = d.refobjid
                  JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid
                 WHERE s.relkind = 'S' AND s.relnamespace = 'public'::regnamespace"""):
            maximo = await c.fetchval(f'SELECT max("{s["col"]}") FROM "{s["tabla"]}"')
            fila = await c.fetchrow(f'SELECT last_value, is_called FROM "{s["seq"]}"')
            proximo = fila["last_value"] + (1 if fila["is_called"] else 0)
            if maximo is not None and proximo <= maximo:
                malas.append(f"{s['seq']}: próximo {proximo} <= {maximo}")
        check("secuencias", not malas, "; ".join(malas[:5]))
        nuevo = await c.fetchval("SELECT nextval(pg_get_serial_sequence('reclamos', 'id_reclamo'))")
        existe = await c.fetchval("SELECT count(*) FROM reclamos WHERE id_reclamo = $1", nuevo)
        check("secuencia_reclamos_no_choca", existe == 0, f"id {nuevo}")

        destino = {x["id_usuario"]: x["password_hash"] for x in await c.fetch("SELECT id_usuario, password_hash FROM usuarios")}
        origen = {x["id_usuario"]: x["password_hash"] for x in await o.fetch("SELECT id_usuario, password_hash FROM usuarios")}
        iguales = [i for i, hsh in destino.items() if origen.get(i) == hsh]
        check("sin_claves", not iguales, f"{len(iguales)} cuentas con la clave de origen")
        vecinos = await c.fetchval("SELECT count(*) FROM ciudadano_credencial WHERE password_hash IS NOT NULL")
        check("sin_claves_de_vecinos", vecinos == 0, f"{vecinos}")

        # Clave conocida para un administrador, solo para entrar en la prueba del backend.
        admin = await c.fetchval("SELECT id_usuario FROM usuarios WHERE id_municipio = 1 AND nivel_acceso = 1 AND activo "
                                 "AND email IS NOT NULL ORDER BY id_usuario LIMIT 1")
        await c.execute("UPDATE usuarios SET password_hash = $1 WHERE id_usuario = $2",
                        bcrypt.hashpw(CLAVE.encode(), bcrypt.gensalt()).decode(), admin)
    finally:
        await c.close()
        await o.close()

    print("\n4. Backend contra la base restaurada")
    ref = correr_backend("zaris_dev", False)
    check("referencia_zaris_dev", ref.get("login") == 200 and ref.get("resumen") == 200 and bool(ref.get("reclamos_ids")),
          str(ref)[:400])
    for barrera in (False, True):
        res = correr_backend(DESTINO, barrera)
        sufijo = "_con_barrera" if barrera else ""
        check(f"login{sufijo}", res.get("login") == 200, str(res)[:400])
        check(f"inicio{sufijo}", res.get("resumen") == 200 and res.get("resumen_json") == ref.get("resumen_json"),
              f"status={res.get('resumen')}")
        check(f"reclamos{sufijo}", res.get("reclamos") == 200 and res.get("reclamos_ids") == ref.get("reclamos_ids")
              and res.get("reclamos_total") == ref.get("reclamos_total"),
              f"total {res.get('reclamos_total')} vs {ref.get('reclamos_total')}")

    await adm.execute(f'DROP DATABASE IF EXISTS "{DESTINO}" WITH (FORCE)')
    await adm.close()

    fallas = [n for n, ok, _ in RES if not ok]
    print(f"\n{len(RES) - len(fallas)}/{len(RES)} OK" + (f" — FALLARON: {', '.join(fallas)}" if fallas else ""))
    return 1 if fallas else 0


if __name__ == "__main__":
    if "--backend" in sys.argv:
        asyncio.run(backend())
    else:
        sys.exit(asyncio.run(main()))
