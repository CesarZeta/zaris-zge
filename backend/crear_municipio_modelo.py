# -*- coding: utf-8 -*-
"""
Municipio modelo (IT-01 F4+F5, PLAN_MULTI_MUNICIPIO_F4_F5.md, Tarea 12).

    python crear_municipio_modelo.py --inventario
        Por cada tabla de grupo `maestros` y `configuracion` del municipio de las direcciones sin
        prefijo: filas activas, cuántas se copiarían y cuáles se proponen descartar (nombres de
        prueba). Sin datos personales: solo catálogos. Con --salida <archivo> lo escribe ahí (la
        decisión de César vive en docs/municipio_modelo_inventario.md y no se pisa).

    python crear_municipio_modelo.py --aplicar --excluir <archivo>
        Crea «Modelo ZARIS» (estado modelo) y copia los catálogos aprobados (Tarea 12, paso 2).

Corre contra la base de ENV_FILE (local por defecto). Nunca copia tablas de grupo contactos,
usuarios ni operativo.
"""
import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("ENV_FILE", ".env.local")
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402

DE_PRUEBA = re.compile(r"(?i)\b(test|prueba|qa|demo|borrar)\b|smoke|aislab")
COLUMNAS_NOMBRE = ("nombre", "descripcion", "titulo", "etiqueta", "texto", "pregunta", "clave")


async def _columnas(db, tabla: str) -> set[str]:
    return {r[0] for r in (await db.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = :t"),
        {"t": tabla})).all()}


async def inventario(salida: Path | None) -> int:
    async with AsyncSessionLocal() as db:
        base, nombre_base = (await db.execute(text(
            "SELECT id_municipio, nombre FROM municipios WHERE direccion_base"))).one()
        tablas = (await db.execute(text(
            "SELECT tabla, grupo FROM municipio_tabla_clase WHERE grupo IN ('maestros', 'configuracion') "
            "AND (clase = 'catalogo' OR tabla = 'configuracion_general') ORDER BY grupo DESC, tabla"))).all()
        filas_md = []
        for tabla, grupo in tablas:
            cols = await _columnas(db, tabla)
            if not cols or "id_municipio" not in cols:
                continue
            activas_sql = " AND activo" if "activo" in cols else ""
            total = await db.scalar(text(f'SELECT count(*) FROM "{tabla}" WHERE id_municipio = :m{activas_sql}'),
                                    {"m": base})
            inactivas = (await db.scalar(text(
                f'SELECT count(*) FROM "{tabla}" WHERE id_municipio = :m AND NOT activo'), {"m": base})
                if "activo" in cols else 0)
            col = next((c for c in COLUMNAS_NOMBRE if c in cols), None)
            descartes: list[str] = []
            if col and grupo == "maestros":
                nombres = (await db.execute(text(
                    f'SELECT DISTINCT "{col}"::text FROM "{tabla}" WHERE id_municipio = :m{activas_sql}'),
                    {"m": base})).scalars().all()
                descartes = sorted(n for n in nombres if n and DE_PRUEBA.search(n))
            if tabla == "configuracion_general":
                nota = "se copia siempre (todas las claves, pisadas por la identidad del alta)"
            elif tabla == "area":
                nota = "las 6 áreas fijas se copian siempre"
            else:
                nota = ""
            filas_md.append((tabla, grupo, total, inactivas, total - len(descartes), descartes, nota))

    lineas = [
        "# Inventario para el municipio modelo",
        "",
        f"Generado por `backend/crear_municipio_modelo.py --inventario` sobre el municipio base ({nombre_base}).",
        "Solo catálogos (grupos `maestros` y `configuracion`): no hay datos personales. Las filas inactivas",
        "nunca se copian. Se proponen descartar los nombres que parecen de prueba "
        "(test, prueba, qa, demo, borrar, smoke).",
        "",
        "| Tabla | Grupo | Activas | Inactivas (no se copian) | A copiar | A descartar | Nota |",
        "|---|---|---|---|---|---|---|",
    ]
    for tabla, grupo, total, inactivas, copiar, descartes, nota in filas_md:
        desc = "; ".join(f"«{d}»" for d in descartes[:12]) + (f" (y {len(descartes) - 12} más)" if len(descartes) > 12 else "")
        lineas.append(f"| `{tabla}` | {grupo} | {total} | {inactivas} | {copiar} | {desc or '—'} | {nota} |")
    print("\n".join(lineas))
    if salida:
        salida.write_text("\n".join(lineas) + "\n", encoding="utf-8")
        print(f"\nEscrito: {salida}")
    return 0


# Identidad de San Andrés que el modelo no hereda: cada alta pone la suya (o queda la de por defecto).
IDENTIDAD_EN_BLANCO = ("municipio_logo_url", "municipio_descripcion", "municipio_color_primary",
                       "municipio_color_accent", "geo_limite_geojson", "geo_bbox_centro_lat",
                       "geo_bbox_centro_lon", "geo_bbox_delta_grados", "id_espacio_guardia")


async def aplicar(excluir: Path) -> int:
    import json
    from app.services.municipios.alta import CATALOGOS_COPIABLES
    from app.services.municipios.clonado import Clonador, FilaOmitida, conexion_asyncpg
    ex = json.loads(excluir.read_text(encoding="utf-8"))
    tablas_fuera = set(ex.get("tablas", []))
    nombres_fuera = {t: set(ns) for t, ns in ex.get("nombres", {}).items()}
    local = "zaris_dev" in settings.ASYNC_DATABASE_URI
    if not local and input("Esto escribe en una base que NO es zaris_dev. Escribí MODELO para seguir: ") != "MODELO":
        sys.exit("Cancelado.")
    async with AsyncSessionLocal() as db:
        if await db.scalar(text("SELECT 1 FROM municipios WHERE estado = 'modelo'")):
            sys.exit("Ya existe un municipio modelo: no se crea otro.")
        base = await db.scalar(text("SELECT id_municipio FROM municipios WHERE direccion_base"))
        prov = await db.scalar(text(
            "SELECT id_provincia FROM provincias WHERE codigo_pais = 'AR' AND nombre = 'Buenos Aires'"))
        modelo = await db.scalar(text("""
            INSERT INTO municipios (nombre, codigo_corto, codigo_pais, pais, id_provincia, provincia, estado)
            VALUES ('Modelo ZARIS', 'MOD', 'AR', 'Argentina', :p, 'Buenos Aires', 'modelo')
            RETURNING id_municipio"""), {"p": prov})
        conn = await conexion_asyncpg(db)
        permitidas = {t for ts in CATALOGOS_COPIABLES.values() for t in ts} - tablas_fuera
        c = Clonador(conn, modelo, permitidas=permitidas)
        await c.cargar_clases()
        copiadas: dict[str, int] = {}
        omitidas = 0
        for tablas in CATALOGOS_COPIABLES.values():
            for tabla in tablas:
                if tabla in tablas_fuera:
                    continue
                m = await c.meta(tabla)
                if not m["cols"] or len(m["pk"]) != 1:
                    continue
                pk = m["pk"][0]
                col = next((x for x in COLUMNAS_NOMBRE if x in m["cols"]), None)
                filtro = " AND activo" if "activo" in m["cols"] else ""
                filas = await conn.fetch(
                    f'SELECT "{pk}" AS id{", " + chr(34) + col + chr(34) + "::text AS nombre" if col else ""} '
                    f'FROM "{tabla}" WHERE id_municipio = $1{filtro} ORDER BY "{pk}"', base)
                for f in filas:
                    nombre = f["nombre"] if col else None
                    if nombre and (nombre in nombres_fuera.get(tabla, set()) or DE_PRUEBA.search(nombre)):
                        continue
                    try:
                        await c.clonar(tabla, f["id"])
                    except FilaOmitida:
                        omitidas += 1
        for (tabla, _), _ in c.mapa.items():
            copiadas[tabla] = copiadas.get(tabla, 0) + 1
        await db.execute(text("""
            INSERT INTO configuracion_general (clave, valor, tipo, descripcion, activo, id_municipio)
            SELECT clave, valor, COALESCE(tipo, 'string'), descripcion, TRUE, :mod
              FROM configuracion_general WHERE id_municipio = :b AND activo"""), {"mod": modelo, "b": base})
        await db.execute(text("""
            UPDATE configuracion_general SET valor = '' WHERE id_municipio = :mod AND clave = ANY(:claves)"""),
            {"mod": modelo, "claves": list(IDENTIDAD_EN_BLANCO)})
        await db.execute(text("""
            UPDATE configuracion_general SET valor = 'Modelo ZARIS' WHERE id_municipio = :mod AND clave = 'municipio_nombre'"""),
            {"mod": modelo})
        salud = await db.scalar(text("""
            SELECT id_area FROM area WHERE id_municipio = :m AND activo AND es_sistema
               AND lower(translate(nombre, 'ÁÉÍÓÚáéíóú', 'AEIOUaeiou')) LIKE 'secretaria de salud%'"""), {"m": modelo})
        await db.execute(text(
            "UPDATE configuracion_general SET valor = :v WHERE id_municipio = :mod AND clave = 'id_area_salud'"),
            {"v": str(salud) if salud else "", "mod": modelo})
        await db.execute(text("""
            INSERT INTO municipio_modulo (id_municipio, modulo_codigo, habilitado, min_nivel_acceso)
            SELECT :mod, modulo_codigo, TRUE, min_nivel_acceso FROM modulos WHERE activo"""), {"mod": modelo})
        await db.commit()
    print(f"Modelo ZARIS creado (id {modelo}).")
    for tabla in sorted(copiadas):
        print(f"  {tabla}: {copiadas[tabla]}")
    if omitidas:
        print(f"  filas omitidas (dependen de tablas que no se copian): {omitidas}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventario", action="store_true")
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--excluir", type=Path)
    ap.add_argument("--salida", type=Path)
    args = ap.parse_args()
    if args.inventario:
        return asyncio.run(inventario(args.salida))
    if args.aplicar:
        if not args.excluir or not args.excluir.is_file():
            sys.exit("--aplicar necesita --excluir <archivo> (municipio_modelo_exclusiones.json)")
        return asyncio.run(aplicar(args.excluir))
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
