"""
seed_catalogos_emergencias.py - Seed de catalogos del modulo Emergencias.

Lee los 6 CSVs de "Tablas Iniciales/" (emergencia_*.csv) y genera SQL
idempotente y COMPACTO (un INSERT ... SELECT FROM (VALUES ...) ON CONFLICT
por tabla) donde TODAS las FKs se resuelven por codigo o nombre normalizado,
nunca por ID hardcodeado (los IDs difieren entre local y prod).

Requiere migraciones 81 (subareas de Seguridad) y 82 (tablas emergencia_*).

Uso:
    cd backend
    # Local (default 127.0.0.1/zaris_dev):
    $env:PYTHONIOENCODING="utf-8"; python seed_catalogos_emergencias.py

    # Emitir el SQL para aplicar en prod via MCP (sin conectarse a ninguna DB):
    python seed_catalogos_emergencias.py --emit-sql seed_emergencias.sql

    # Contra otra DB (pide --confirm-prod si es Supabase):
    $env:DATABASE_URL="postgresql+asyncpg://..."; python seed_catalogos_emergencias.py --confirm-prod
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import os
import sys
from pathlib import Path

TABLAS_DIR = Path(__file__).parent.parent / "Tablas Iniciales"

# clave CSV -> nombre normalizado en subarea (sin tildes, lowercase)
SUBAREAS = {
    "POLICIA_MUNICIPAL": "policia municipal",
    "DEFENSA_CIVIL": "defensa civil",
}

# fold de tildes para comparar nombres en SQL (mismo criterio que mig 81)
FOLD = "translate(lower(nombre), 'áéíóú', 'aeiou')"


def leer_csv(nombre: str) -> list[dict]:
    path = TABLAS_DIR / nombre
    with open(path, encoding="utf-8-sig") as f:
        return [{k.strip(): (v or "").strip() for k, v in row.items()}
                for row in csv.DictReader(f, delimiter=";")]


def q(s: str) -> str:
    """Literal SQL (escapa comillas). Vacio -> NULL."""
    if s is None or s == "":
        return "NULL"
    return "'" + s.replace("'", "''") + "'"


def b(s: str) -> str:
    return "TRUE" if (s or "").strip().lower() in ("true", "1", "t", "si") else "FALSE"


def n(s: str) -> str:
    """Entero o NULL."""
    s = (s or "").strip()
    return s if s else "NULL"


def subarea_subq(clave_csv: str) -> str:
    return ("(SELECT id_subarea FROM subarea WHERE " + FOLD +
            " = '" + SUBAREAS[clave_csv] + "' AND activo ORDER BY id_subarea LIMIT 1)")


# CTE que mapea la clave del CSV al id_subarea real del entorno
CTE_SA = (
    "WITH sa AS (\n"
    "  SELECT 'POLICIA_MUNICIPAL' AS k, " + subarea_subq("POLICIA_MUNICIPAL") + " AS id_subarea\n"
    "  UNION ALL\n"
    "  SELECT 'DEFENSA_CIVIL', " + subarea_subq("DEFENSA_CIVIL") + "\n"
    ")\n"
)


def _values(filas: list[str]) -> str:
    return ",\n  ".join(filas)


def generar_sql() -> str:
    stmts: list[str] = []

    # Guard: las subareas de Seguridad deben existir (mig 81)
    stmts.append(
        "DO $$\nBEGIN\n"
        "  IF " + subarea_subq("POLICIA_MUNICIPAL") + " IS NULL\n"
        "     OR " + subarea_subq("DEFENSA_CIVIL") + " IS NULL THEN\n"
        "    RAISE EXCEPTION 'Subareas Policia Municipal / Defensa Civil no encontradas (aplicar mig 81)';\n"
        "  END IF;\nEND $$;"
    )

    # 1. canal_ingreso
    filas = [f"({q(r['codigo'])}, {q(r['nombre'])}, {q(r['descripcion'])}, {b(r['requiere_operador'])})"
             for r in leer_csv("emergencia_canal_ingreso.csv")]
    stmts.append(
        "INSERT INTO emergencia_canal_ingreso (codigo, nombre, descripcion, requiere_operador, activo)\n"
        "SELECT v.codigo, v.nombre, v.descripcion, v.requiere_operador, TRUE\n"
        "FROM (VALUES\n  " + _values(filas) + "\n) AS v(codigo, nombre, descripcion, requiere_operador)\n"
        "ON CONFLICT (codigo) DO UPDATE SET nombre = EXCLUDED.nombre,\n"
        "  descripcion = EXCLUDED.descripcion, requiere_operador = EXCLUDED.requiere_operador,\n"
        "  activo = TRUE, fecha_modificacion = NOW();"
    )

    # 2. prioridad
    filas = [f"({q(r['codigo'])}, {q(r['nombre'])}, {q(r['descripcion'])}, {n(r['sla_minutos_arribo'])}, {q(r['color_token'])}, {n(r['orden_visual'])})"
             for r in leer_csv("emergencia_prioridad.csv")]
    stmts.append(
        "INSERT INTO emergencia_prioridad (codigo, nombre, descripcion, sla_minutos_arribo, color_token, orden_visual, activo)\n"
        "SELECT v.codigo, v.nombre, v.descripcion, v.sla, v.color_token, v.orden, TRUE\n"
        "FROM (VALUES\n  " + _values(filas) + "\n) AS v(codigo, nombre, descripcion, sla, color_token, orden)\n"
        "ON CONFLICT (codigo) DO UPDATE SET nombre = EXCLUDED.nombre,\n"
        "  descripcion = EXCLUDED.descripcion, sla_minutos_arribo = EXCLUDED.sla_minutos_arribo,\n"
        "  color_token = EXCLUDED.color_token, orden_visual = EXCLUDED.orden_visual,\n"
        "  activo = TRUE, fecha_modificacion = NOW();"
    )

    # 3. estado
    filas = [f"({q(r['codigo'])}, {q(r['nombre'])}, {q(r['descripcion'])}, {b(r['es_inicial'])}, {b(r['es_terminal'])}, {b(r['es_terminal_positivo'])}, {n(r['orden_visual'])})"
             for r in leer_csv("emergencia_estado.csv")]
    stmts.append(
        "INSERT INTO emergencia_estado (codigo, nombre, descripcion, es_inicial, es_terminal, es_terminal_positivo, orden_visual, activo)\n"
        "SELECT v.codigo, v.nombre, v.descripcion, v.es_inicial, v.es_terminal, v.es_terminal_positivo, v.orden, TRUE\n"
        "FROM (VALUES\n  " + _values(filas) + "\n) AS v(codigo, nombre, descripcion, es_inicial, es_terminal, es_terminal_positivo, orden)\n"
        "ON CONFLICT (codigo) DO UPDATE SET nombre = EXCLUDED.nombre,\n"
        "  descripcion = EXCLUDED.descripcion, es_inicial = EXCLUDED.es_inicial,\n"
        "  es_terminal = EXCLUDED.es_terminal, es_terminal_positivo = EXCLUDED.es_terminal_positivo,\n"
        "  orden_visual = EXCLUDED.orden_visual, activo = TRUE, fecha_modificacion = NOW();"
    )

    # 4. organismo_derivacion
    filas = [f"({q(r['codigo'])}, {q(r['nombre'])}, {q(r['descripcion'])}, {q(r['telefono_contacto'])}, {b(r['es_municipal'])})"
             for r in leer_csv("emergencia_organismo_derivacion.csv")]
    stmts.append(
        "INSERT INTO emergencia_organismo_derivacion (codigo, nombre, descripcion, telefono_contacto, es_municipal, activo)\n"
        "SELECT v.codigo, v.nombre, CAST(v.descripcion AS text), v.telefono, v.es_municipal, TRUE\n"
        "FROM (VALUES\n  " + _values(filas) + "\n) AS v(codigo, nombre, descripcion, telefono, es_municipal)\n"
        "ON CONFLICT (codigo) DO UPDATE SET nombre = EXCLUDED.nombre,\n"
        "  descripcion = EXCLUDED.descripcion, telefono_contacto = EXCLUDED.telefono_contacto,\n"
        "  es_municipal = EXCLUDED.es_municipal, activo = TRUE, fecha_modificacion = NOW();"
    )

    # 5. tipo (FKs: subarea por nombre normalizado via CTE, prioridad/organismo por codigo)
    tipos = leer_csv("emergencia_tipo.csv")
    for r in tipos:
        if r["subarea"] not in SUBAREAS:
            raise ValueError(f"Subarea desconocida en emergencia_tipo.csv: {r['subarea']}")
    filas = [f"({q(r['subarea'])}, {n(r['codigo_oficial'])}, {q(r['codigo'])}, {q(r['nombre'])}, {q(r['prioridad'])}, {q(r['organismo_default'])}, {b(r['requiere_911'])}, {b(r['es_emergencia'])})"
             for r in tipos]
    stmts.append(
        CTE_SA +
        "INSERT INTO emergencia_tipo (id_subarea, codigo_oficial, codigo, nombre, id_prioridad_default,\n"
        "  id_organismo_derivacion_default, requiere_911, es_emergencia, activo)\n"
        "SELECT sa.id_subarea, v.codigo_oficial, v.codigo, v.nombre,\n"
        "  p.id_emergencia_prioridad, o.id_emergencia_organismo_derivacion, v.req911, v.es_emergencia, TRUE\n"
        "FROM (VALUES\n  " + _values(filas) + "\n) AS v(sub, codigo_oficial, codigo, nombre, prio, org, req911, es_emergencia)\n"
        "JOIN sa ON sa.k = v.sub\n"
        "JOIN emergencia_prioridad p ON p.codigo = v.prio\n"
        "LEFT JOIN emergencia_organismo_derivacion o ON o.codigo = v.org\n"
        "ON CONFLICT (id_subarea, codigo) DO UPDATE SET nombre = EXCLUDED.nombre,\n"
        "  codigo_oficial = EXCLUDED.codigo_oficial, id_prioridad_default = EXCLUDED.id_prioridad_default,\n"
        "  id_organismo_derivacion_default = EXCLUDED.id_organismo_derivacion_default,\n"
        "  requiere_911 = EXCLUDED.requiere_911, es_emergencia = EXCLUDED.es_emergencia,\n"
        "  activo = TRUE, fecha_modificacion = NOW();"
    )

    # 6. subtipo (FK al tipo por (subarea, codigo))
    subtipos = leer_csv("emergencia_subtipo.csv")
    for r in subtipos:
        if r["subarea"] not in SUBAREAS:
            raise ValueError(f"Subarea desconocida en emergencia_subtipo.csv: {r['subarea']}")
    filas = [f"({q(r['subarea'])}, {q(r['tipo_codigo'])}, {q(r['codigo'])}, {q(r['nombre'])})"
             for r in subtipos]
    stmts.append(
        CTE_SA +
        "INSERT INTO emergencia_subtipo (id_tipo, codigo, nombre, activo)\n"
        "SELECT t.id_emergencia_tipo, v.codigo, v.nombre, TRUE\n"
        "FROM (VALUES\n  " + _values(filas) + "\n) AS v(sub, tipo_codigo, codigo, nombre)\n"
        "JOIN sa ON sa.k = v.sub\n"
        "JOIN emergencia_tipo t ON t.codigo = v.tipo_codigo AND t.id_subarea = sa.id_subarea\n"
        "ON CONFLICT (id_tipo, codigo) DO UPDATE SET nombre = EXCLUDED.nombre,\n"
        "  activo = TRUE, fecha_modificacion = NOW();"
    )

    return "\n\n".join(stmts) + "\n"


async def ejecutar(sql: str, db_url: str) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(db_url)
    try:
        async with engine.connect() as conn:
            raw = await conn.get_raw_connection()
            # asyncpg acepta scripts multi-statement por la conexion cruda (CLAUDE.md s5)
            await raw.driver_connection.execute("BEGIN;\n" + sql + "\nCOMMIT;")
    finally:
        await engine.dispose()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit-sql", metavar="ARCHIVO",
                        help="No ejecuta: escribe el SQL generado (para aplicar en prod via MCP).")
    parser.add_argument("--confirm-prod", action="store_true",
                        help="Necesario si DATABASE_URL apunta a Supabase.")
    args = parser.parse_args()

    sql = generar_sql()

    if args.emit_sql:
        out = Path(args.emit_sql)
        out.write_text(sql, encoding="utf-8")
        print(f"SQL emitido a {out} ({len(sql)} bytes)")
        return

    db_url = os.environ.get("DATABASE_URL",
                            "postgresql+asyncpg://postgres:145236@127.0.0.1:5432/zaris_dev")
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if "supabase.co" in db_url and not args.confirm_prod:
        print("ERROR: DATABASE_URL apunta a Supabase prod. Re-correr con --confirm-prod.")
        sys.exit(2)

    print(f"DB: {db_url.split('@')[1] if '@' in db_url else db_url}")
    await ejecutar(sql, db_url)
    print("[OK] Seed de catalogos de Emergencias aplicado.")


if __name__ == "__main__":
    asyncio.run(main())
