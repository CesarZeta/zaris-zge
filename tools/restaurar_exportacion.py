"""
Restaurar la exportación de un municipio en una base Postgres vacía (IT-01 F6.5).

Herramienta fuera de la aplicación (PLAN_MULTI_MUNICIPIO_F6_DISENO.md §4.7, plan en
PLAN_MULTI_MUNICIPIO_F6_5.md). Dos pasos:

1. volcar: de la base de ZARIS en uso (ORIGEN_URL) saca la estructura del esquema public en dos
   partes (pre-data: tablas sin restricciones; post-data: claves, índices, FK, CHECK NOT VALID,
   triggers y políticas) y las tablas globales (más los parámetros globales), que el zip no trae.

       ORIGEN_URL=postgresql://usuario:clave@host:5432/base \
         python tools/restaurar_exportacion.py volcar --salida <carpeta>

2. restaurar: en una base vacía (DESTINO_URL) crea la estructura, carga globales y zip, aplica el
   post-data (las FK se validan al crearse), ajusta las secuencias, aplica los permisos de la barrera
   (migración 138) y compara los conteos con el zip.

       DESTINO_URL=postgresql://postgres:clave@127.0.0.1:5432/nueva \
         python tools/restaurar_exportacion.py restaurar --base <carpeta> --zip <exportacion.zip>

La exportación no trae secretos: después de restaurar, nadie entra hasta restablecer su clave, y los
niveles 0/1 vuelven a vincular la app del segundo factor. Los archivos de Storage no viajan.
Las claves de conexión salen solo de las variables de entorno y nunca se imprimen.
"""
import argparse
import asyncio
import io
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRACION_BARRERA = os.path.join(RAIZ, "backend", "migrations", "138_barrera_municipio.sql")

# Tablas que no se pueden cargar sin su secreto (NOT NULL) y que sin él no sirven.
SIN_SECRETO = {"ciudadano_push_subscription", "usuario_push_subscription",
               "usuario_codigo_emergencia", "usuario_invitacion"}
LOTE = 5000

_RE_FK_USUARIOS = re.compile(
    r"ALTER TABLE ONLY public\.(\w+)\s+ADD CONSTRAINT \w+ FOREIGN KEY \((\w+)\) "
    r"REFERENCES public\.usuarios\(id_usuario\)")


# ── Funciones puras ─────────────────────────────────────────────────────────

def preparar_filas(tabla: str, filas: list[dict], hash_cuentas: str,
                   id_municipio: int | None = None) -> list[dict] | None:
    """Filas listas para cargar, o None si la tabla no se carga."""
    if tabla in SIN_SECRETO:
        return None
    if tabla == "usuarios":
        return [{**f, "password_hash": hash_cuentas} for f in filas]
    if tabla == "municipios" and id_municipio is not None:
        return [f for f in filas if f.get("id_municipio") == id_municipio]
    return filas


def referencias_a_usuarios(post_data: str) -> list[tuple[str, str]]:
    """(tabla, columna) de cada FK simple a usuarios(id_usuario) del post-data de pg_dump."""
    return _RE_FK_USUARIOS.findall(post_data)


def municipio_del_zip(contenido: bytes) -> int:
    """El id_municipio de las filas del zip; ValueError si hay ninguno o más de uno."""
    ids: set = set()
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        for n in z.namelist():
            ids |= {f.get("id_municipio") for f in json.loads(z.read(n))}
    ids.discard(None)
    if len(ids) != 1:
        raise ValueError(f"el zip tiene que ser de un solo municipio y trae {sorted(ids) or 'ninguno'}")
    return ids.pop()


def sin_clave(url: str) -> str:
    p = urlsplit(url)
    if p.password is None:
        return url
    return url.replace(f":{p.password}@", "@", 1)


# ── Conexiones ──────────────────────────────────────────────────────────────

def _url(variable: str) -> str:
    url = os.environ.get(variable)
    if not url:
        sys.exit(f"Falta la variable de entorno {variable} (postgresql://usuario:clave@host:puerto/base).")
    return url


def _env_pg(url: str) -> dict:
    """Variables PG* para pg_dump/psql: la clave no va en la línea de comandos."""
    p = urlsplit(url)
    env = {**os.environ, "PGCLIENTENCODING": "UTF8", "PGHOST": p.hostname or "", "PGPORT": str(p.port or 5432),
           "PGDATABASE": unquote(p.path.lstrip("/"))}
    if p.username:
        env["PGUSER"] = unquote(p.username)
    if p.password is not None:
        env["PGPASSWORD"] = unquote(p.password)
    return env


def _binario(nombre: str) -> str:
    for carpeta in filter(None, [os.environ.get("PG_BIN")]):
        for cand in (os.path.join(carpeta, nombre), os.path.join(carpeta, nombre + ".exe")):
            if os.path.exists(cand):
                return cand
    if shutil.which(nombre):
        return shutil.which(nombre)
    for v in ("17", "18"):
        cand = rf"C:/Program Files/PostgreSQL/{v}/bin/{nombre}.exe"
        if os.path.exists(cand):
            return cand
    sys.exit(f"No encuentro {nombre} (versión 17 o más). Indicá la carpeta en PG_BIN.")


def _correr(args: list[str], env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(args, env=env, capture_output=True, text=True, encoding="utf-8")


async def _conectar(url: str):
    import asyncpg
    c = await asyncpg.connect(url)
    for tipo in ("json", "jsonb"):
        await c.set_type_codec(tipo, encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
    return c


# ── volcar ──────────────────────────────────────────────────────────────────

async def volcar(salida: str) -> dict:
    url = _url("ORIGEN_URL")
    os.makedirs(salida, exist_ok=True)
    env = _env_pg(url)
    pg_dump = _binario("pg_dump")
    for seccion in ("pre-data", "post-data"):
        r = _correr([pg_dump, "--schema=public", "--exclude-table=public._backup_*", "--no-owner",
                     "--no-privileges", f"--section={seccion}", "-f", os.path.join(salida, f"{seccion}.sql")], env)
        if r.returncode:
            sys.exit(f"pg_dump {seccion}: {r.stderr[-1500:]}")

    c = await _conectar(url)
    try:
        globales = [x["tabla"] for x in await c.fetch(
            "SELECT tabla FROM municipio_tabla_clase WHERE clase = 'global' "
            "AND to_regclass('public.' || quote_ident(tabla)) IS NOT NULL ORDER BY tabla")]
        cantidades = {}
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for t in globales:
                filas = [dict(f) for f in await c.fetch(f'SELECT * FROM "{t}"')]
                cantidades[t] = len(filas)
                z.writestr(f"{t}.json", json.dumps(filas, default=str, ensure_ascii=False))
            # Parámetros globales: filas sin municipio de configuracion_general (el zip trae solo las del municipio).
            filas = [dict(f) for f in await c.fetch("SELECT * FROM configuracion_general WHERE id_municipio IS NULL")]
            cantidades["configuracion_general (globales)"] = len(filas)
            z.writestr("configuracion_general.json", json.dumps(filas, default=str, ensure_ascii=False))
        version = await c.fetchval("SHOW server_version")
    finally:
        await c.close()
    with open(os.path.join(salida, "globales.zip"), "wb") as f:
        f.write(buf.getvalue())
    manifiesto = {"origen": sin_clave(url), "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "version_servidor": version, "globales": cantidades}
    with open(os.path.join(salida, "manifiesto.json"), "w", encoding="utf-8") as f:
        json.dump(manifiesto, f, ensure_ascii=False, indent=2)
    return manifiesto


# ── restaurar ───────────────────────────────────────────────────────────────

async def _cargar(c, tabla: str, filas: list[dict]) -> None:
    # La lista va tal cual: el codec json de la conexión la serializa (ver _conectar).
    for i in range(0, len(filas), LOTE):
        await c.execute(f'INSERT INTO "{tabla}" SELECT * FROM json_populate_recordset(NULL::"{tabla}", $1::json)',
                        filas[i:i + LOTE])


def _hash_al_azar() -> str:
    import bcrypt
    return bcrypt.hashpw(secrets.token_urlsafe(32).encode(), bcrypt.gensalt()).decode()


async def restaurar(base: str, ruta_zip: str) -> dict:
    url = _url("DESTINO_URL")
    env = _env_pg(url)
    psql = [_binario("psql"), "-v", "ON_ERROR_STOP=1", "-q", "-f"]
    with open(ruta_zip, "rb") as f:
        contenido = f.read()
    id_municipio = municipio_del_zip(contenido)
    informe: dict = {"destino": sin_clave(url), "id_municipio": id_municipio, "ok": False}

    c = await _conectar(url)
    try:
        tablas = await c.fetchval("SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")
        if tablas:
            raise SystemExit(f"La base destino no está vacía ({tablas} tablas en public): no se tocó nada.")
        # Las políticas nombran a zaris_app; sin login: la clave la pone quien opera este servidor.
        await c.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'zaris_app') "
                        "THEN CREATE ROLE zaris_app NOLOGIN; END IF; END $$")
        await c.execute("DROP SCHEMA IF EXISTS public CASCADE")
    finally:
        await c.close()

    r = _correr(psql + [os.path.join(base, "pre-data.sql")], env)
    if r.returncode:
        raise SystemExit(f"pre-data: {r.stderr[-1500:]}")

    hash_cuentas = _hash_al_azar()
    esperado: dict[str, int] = {}
    omitidas: dict[str, int] = {}
    c = await _conectar(url)
    try:
        with zipfile.ZipFile(os.path.join(base, "globales.zip")) as z:
            for n in z.namelist():
                t = n[:-5]
                filas = preparar_filas(t, json.loads(z.read(n)), hash_cuentas, id_municipio=id_municipio)
                await _cargar(c, t, filas)
        with zipfile.ZipFile(io.BytesIO(contenido)) as z:
            for n in sorted(z.namelist()):
                t = n[:-5]
                filas = json.loads(z.read(n))
                listas = preparar_filas(t, filas, hash_cuentas)
                if listas is None:
                    if filas:
                        omitidas[t] = len(filas)
                    continue
                esperado[t] = len(listas)
                if listas:
                    await _cargar(c, t, listas)

        # Cuentas a las que apuntan filas del municipio y que no vinieron (el super, o borradas).
        with open(os.path.join(base, "post-data.sql"), encoding="utf-8") as f:
            post = f.read()
        faltantes: set[int] = set()
        for t, col in referencias_a_usuarios(post):
            if not await c.fetchval("SELECT to_regclass('public.' || quote_ident($1)) IS NOT NULL", t):
                continue
            faltantes |= {x[0] for x in await c.fetch(
                f'SELECT DISTINCT s."{col}" FROM "{t}" s WHERE s."{col}" IS NOT NULL '
                f'AND NOT EXISTS (SELECT 1 FROM usuarios u WHERE u.id_usuario = s."{col}")')}
        for i in sorted(faltantes):
            await c.execute(
                "INSERT INTO usuarios (id_usuario, username, nombre, nivel_acceso, password_hash, activo, buc_acceso, "
                "id_municipio) VALUES ($1::int, 'no-exportada-' || $1::int::text, 'Cuenta no exportada', 0, $2, "
                "FALSE, FALSE, NULL)", i, hash_cuentas)
        informe["cuentas_no_exportadas"] = len(faltantes)
    finally:
        await c.close()

    r = _correr(psql + [os.path.join(base, "post-data.sql")], env)
    if r.returncode:
        informe["error"] = f"post-data (integridad): {r.stderr[-1500:]}"
        return informe
    informe["post_data"] = "ok"

    c = await _conectar(url)
    try:
        secuencias = await c.fetch("""
            SELECT s.relname AS seq, t.relname AS tabla, a.attname AS col
              FROM pg_class s
              JOIN pg_depend d ON d.objid = s.oid AND d.deptype IN ('a', 'i')
              JOIN pg_class t ON t.oid = d.refobjid
              JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid
             WHERE s.relkind = 'S' AND s.relnamespace = 'public'::regnamespace""")
        for s in secuencias:
            await c.execute(f"SELECT setval('public.\"{s['seq']}\"', COALESCE(MAX(\"{s['col']}\"), 0) + 1, false) "
                            f"FROM \"{s['tabla']}\"")
        informe["secuencias"] = len(secuencias)

        distintos = {}
        for t, n in esperado.items():
            # Toda tabla del zip tiene id_municipio; el filtro deja afuera los parámetros globales
            # (configuracion_general) y las cuentas no exportadas (usuarios sin municipio).
            got = await c.fetchval(f'SELECT count(*) FROM "{t}" WHERE id_municipio = $1', id_municipio)
            if got != n:
                distintos[t] = {"zip": n, "base": got}
        informe.update({"tablas": len(esperado), "filas": sum(esperado.values()), "omitidas_sin_secreto": omitidas,
                        "conteos_distintos": distintos})
    finally:
        await c.close()

    r = _correr(psql + [MIGRACION_BARRERA], env)
    if r.returncode:
        informe["error"] = f"permisos de la barrera (138): {r.stderr[-800:]}"
        return informe
    informe["barrera"] = "ok"
    informe["ok"] = not distintos
    return informe


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="comando", required=True)
    v = sub.add_parser("volcar", help="estructura y globales de la base en uso (ORIGEN_URL)")
    v.add_argument("--salida", required=True)
    rr = sub.add_parser("restaurar", help="en una base vacía (DESTINO_URL)")
    rr.add_argument("--base", required=True, help="carpeta que dejó 'volcar'")
    rr.add_argument("--zip", required=True, help="exportación del municipio")
    a = ap.parse_args()
    if a.comando == "volcar":
        print(json.dumps(asyncio.run(volcar(a.salida)), ensure_ascii=False, indent=2))
        return
    informe = asyncio.run(restaurar(a.base, a.zip))
    print(json.dumps(informe, ensure_ascii=False, indent=2))
    sys.exit(0 if informe.get("ok") else 1)


if __name__ == "__main__":
    main()
