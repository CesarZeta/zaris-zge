# -*- coding: utf-8 -*-
"""
Smoke — la segunda barrera (IT-01 F6.2, PLAN_MULTI_MUNICIPIO_F6_2.md).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_barrera.py

SOLO LOCAL (aborta si la DB no es zaris_dev). Conecta con asyncpg como `zaris_app`
(APP_DB_USER / APP_DB_PASSWORD de .env.local) y recorre las tablas desde
municipio_tabla_clase, no desde una lista a mano.

Parte 1 (base): sin municipio no se ve nada; con un municipio solo lo suyo; no se escribe en otro;
globales visibles; parámetros globales de solo lectura; cuentas del super invisibles; toda tabla
clasificada con política y ninguna para anon/authenticated; respaldos inaccesibles.
"""
import asyncio
import os
import sys

import asyncpg

os.environ.setdefault("ENV_FILE", ".env.local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from app.core.config import settings  # noqa: E402

if "zaris_dev" not in settings.ASYNC_DATABASE_URI:
    sys.exit("ABORT: este smoke es SOLO LOCAL (la DB configurada no es zaris_dev).")

OK = FAIL = 0


def check(cond: bool, nombre: str, detalle: str = "") -> None:
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  OK   {nombre}")
    else:
        FAIL += 1
        print(f"  FAIL {nombre} {detalle}")


def _dsn(usuario: str, clave: str) -> dict:
    return dict(user=usuario, password=clave, host=settings.POSTGRES_SERVER,
                port=int(settings.POSTGRES_PORT), database=settings.POSTGRES_DB)


async def conectar_app() -> asyncpg.Connection:
    usuario = getattr(settings, "APP_DB_USER", "") or os.environ.get("APP_DB_USER", "")
    clave = getattr(settings, "APP_DB_PASSWORD", "") or os.environ.get("APP_DB_PASSWORD", "")
    if not usuario:
        sys.exit("ABORT: falta APP_DB_USER en .env.local")
    return await asyncpg.connect(**_dsn(usuario, clave))


async def parte_base() -> None:
    dueno = await asyncpg.connect(**_dsn(settings.POSTGRES_USER, settings.POSTGRES_PASSWORD))
    # Solo las tablas que existen (una clasificada puede no existir en un entorno: tipos_representacion en local).
    clases = {r["tabla"]: r["clase"] for r in await dueno.fetch(
        "SELECT tabla, clase FROM municipio_tabla_clase WHERE to_regclass('public.' || quote_ident(tabla)) IS NOT NULL")}
    otro = await dueno.fetchval("SELECT id_municipio FROM municipios WHERE id_municipio <> 1 ORDER BY 1 LIMIT 1")
    un_reclamo = await dueno.fetchval("SELECT id_reclamo FROM reclamos WHERE id_municipio = 1 LIMIT 1")
    backup = await dueno.fetchval("SELECT tablename FROM pg_tables WHERE schemaname='public' "
                                  "AND tablename LIKE '\\_backup%' LIMIT 1")
    politicas = await dueno.fetch("SELECT tablename, roles FROM pg_policies WHERE schemaname='public'")
    await dueno.close()

    por_municipio = sorted(t for t, c in clases.items() if c != "global") + ["usuarios"]
    con_columna = sorted(set(por_municipio))

    app = await conectar_app()
    try:
        print("[sin_municipio_no_ve_nada]")
        # configuracion_general deja ver los parámetros globales (id_municipio NULL): se cuentan las demás.
        visibles = [t for t in con_columna
                    if await app.fetchval(f'SELECT count(*) FROM "{t}" WHERE id_municipio IS NOT NULL') > 0]
        check(not visibles, "sin municipio, ninguna tabla de municipio devuelve filas", str(visibles[:8]))

        print("[solo_ve_su_municipio]")
        await app.execute("SELECT set_config('app.id_municipio', '1', false)")
        ajenas = [t for t in con_columna
                  if await app.fetchval(f'SELECT count(*) FROM "{t}" WHERE id_municipio IS DISTINCT FROM 1') > 0
                  and t != "configuracion_general"]
        check(not ajenas, "con el municipio 1 no aparece ninguna fila de otro", str(ajenas[:8]))
        check(await app.fetchval("SELECT count(*) FROM reclamos") > 0, "y ve sus reclamos")

        print("[no_escribe_en_otro]")
        for nombre, sql in (("mover un reclamo a otro municipio",
                             f"UPDATE reclamos SET id_municipio = {otro} WHERE id_reclamo = {un_reclamo}"),
                            ("crear un área de otro municipio",
                             f"INSERT INTO area (nombre, activo, id_municipio) VALUES ('barrera', TRUE, {otro})")):
            tr = app.transaction()
            await tr.start()
            try:
                await app.execute(sql)
                check(False, nombre + " → rechazado", "se aplicó")
            except asyncpg.PostgresError as e:
                # 42501 = la fila nueva viola la política (el texto viene en el idioma del servidor).
                check(e.sqlstate == "42501", nombre + " → rechazado", f"{e.sqlstate} {str(e)[:120]}")
            finally:
                await tr.rollback()

        print("[globales_visibles]")
        await app.execute("SELECT set_config('app.id_municipio', '', false)")
        for t in ("municipios", "provincias", "modulos"):
            check(await app.fetchval(f"SELECT count(*) FROM {t}") > 0, f"{t} visible sin municipio")

        print("[config_global_solo_lectura]")
        await app.execute("SELECT set_config('app.id_municipio', '1', false)")
        check(await app.fetchval("SELECT count(*) FROM configuracion_general WHERE id_municipio IS NULL") > 0,
              "con el municipio 1 se ven los parámetros globales")
        tr = app.transaction()
        await tr.start()
        n = await app.execute("UPDATE configuracion_general SET valor = valor WHERE id_municipio IS NULL")
        await tr.rollback()
        check(n == "UPDATE 0", "pero no se modifican", n)

        print("[super_invisible]")
        check(await app.fetchval("SELECT count(*) FROM usuarios WHERE id_municipio IS NULL") == 0,
              "las cuentas del super no se ven")
    finally:
        await app.close()

    print("[todas_con_politica]")
    con_politica = {p["tablename"] for p in politicas if "zaris_app" in p["roles"]}
    sin = sorted(t for t in clases if t not in con_politica)
    check(not sin, "toda tabla clasificada tiene política para zaris_app", str(sin[:8]))
    abiertas = [p["tablename"] for p in politicas if {"anon", "authenticated", "public"} & set(p["roles"])]
    check(not abiertas, "ninguna política para anon/authenticated", str(abiertas[:8]))

    print("[sin_backups]")
    app = await conectar_app()
    try:
        await app.fetchval(f'SELECT count(*) FROM "{backup}"')
        check(False, "los respaldos no se pueden leer", backup)
    except asyncpg.InsufficientPrivilegeError:
        check(True, "los respaldos no se pueden leer")
    finally:
        await app.close()


async def main() -> int:
    await parte_base()
    print(f"\n== {OK} OK · {FAIL} FAIL ==")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
