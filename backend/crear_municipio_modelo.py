# -*- coding: utf-8 -*-
"""
Municipio modelo (IT-01 F4+F5, PLAN_MULTI_MUNICIPIO_F4_F5.md, Tarea 12).

    python crear_municipio_modelo.py --inventario
        Por cada tabla de grupo `maestros` y `configuracion` del municipio de las direcciones sin
        prefijo: filas activas, cuántas se copiarían y cuáles se proponen descartar (nombres de
        prueba). Escribe docs/municipio_modelo_inventario.md (sin datos personales: solo catálogos).

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
SALIDA = AQUI.parent / "docs" / "municipio_modelo_inventario.md"


async def _columnas(db, tabla: str) -> set[str]:
    return {r[0] for r in (await db.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = :t"),
        {"t": tabla})).all()}


async def inventario() -> int:
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
    SALIDA.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))
    print(f"\nEscrito: {SALIDA}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventario", action="store_true")
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--excluir", type=Path)
    args = ap.parse_args()
    if args.inventario:
        return asyncio.run(inventario())
    if args.aplicar:
        sys.exit("--aplicar llega con la Tarea 12, paso 2 (después de la aprobación del inventario).")
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
