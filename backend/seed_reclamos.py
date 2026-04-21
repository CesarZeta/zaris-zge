"""
ZARIS — Seed del módulo Reclamos.
Puebla reclamos_area, reclamos_subarea y reclamos_tipo.

Uso:
    cd backend
    python seed_reclamos.py

El archivo tipo_reclamo.csv debe estar en la raíz del proyecto (ZGE/).
Columnas: id_tipo;Tipo;id_subarea  (separador: punto y coma, con encabezado).
"""
import asyncio
import csv
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Agregar el directorio backend al path para importar app.*
sys.path.insert(0, os.path.dirname(__file__))
from app.core.config import settings  # noqa: E402
from app.core.database import Base, engine as _app_engine
from app.models import reclamos as _reclamos_models  # noqa: F401 — registra tablas

# ── Datos de referencia ────────────────────────────────────────

AREAS = [
    (101, "Sec. Atencion Ciudadana"),
    (102, "Sec. Cultura"),
    (103, "Sec. Deportes"),
    (104, "Sec. Fiscalizacion y Control"),
    (105, "Sec. Hacienda"),
    (106, "Sec. Obras y Planeamiento"),
    (107, "Sec. Salud"),
    (108, "Sec. Seguridad"),
    (109, "Sec. Serv. Públicos"),
    (110, "Sec. Tránsito"),
]

SUBAREAS = [
    (101, "Alumbrado",                                        109),
    (102, "Arbolado",                                         109),
    (103, "Asesoramiento",                                    101),
    (104, "Calles y veredas",                                 109),
    (105, "Comercio",                                         104),
    (106, "Consulta sobre habilitación comercial",            104),
    (107, "Contaminación por derrames tóxicos",               104),
    (108, "Control de incidentes",                            109),
    (109, "Control de norma de seguridad – comercio",         104),
    (110, "Emergencia Climática",                             108),
    (111, "Espacios verdes y plazas",                         109),
    (112, "Habilitación Comercial",                           104),
    (113, "Higiene y seguridad – comercio/industria",         104),
    (114, "Inconveniente con olores y plagas en comercio",    104),
    (115, "Inconveniente con plagas en vía pública",          104),
    (116, "Inconvenientes con empresa de servicio publicos",  104),
    (117, "Inconvenientes con olores en vía pública",         104),
    (118, "Inconvenientes con ruidos molestos",               104),
    (119, "Inspecciones",                                     105),
    (120, "Irregularidades en Actividades Comercial",         104),
    (121, "Licencia de Conducir",                             110),
    (122, "Mant. general",                                    104),
    (123, "Obras Municipales - Pluviales",                    106),
    (124, "Ocupación Irregular del Espacio Público",          104),
    (125, "Recol.residuos reciclables",                       109),
    (126, "Recol.residuos y limpieza",                        109),
    (127, "Recol.residuos y limpieza en espacios públicos",   109),
    (128, "Relevamiento Comercios",                           104),
    (129, "Relevamiento Luminaria",                           109),
    (130, "Retiro de animales muertos",                       109),
    (131, "Seguridad e Higiene",                              104),
    (132, "Señalamiento Vial",                                110),
    (134, "Tránsito",                                         110),
    (135, "Vehículo abandonado",                              110),
]

# ── Helpers ───────────────────────────────────────────────────

def load_tipos_from_csv(csv_path: str) -> list[tuple[int, str, int]]:
    """Lee id_tipo, nombre, id_subarea del CSV separado por ';'."""
    rows = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            id_tipo = row.get("id_tipo", "").strip()
            nombre  = row.get("Tipo", "").strip()
            id_sub  = row.get("id_subarea", "").strip()
            if not id_tipo or not nombre or not id_sub:
                continue
            rows.append((int(id_tipo), nombre, int(id_sub)))
    return rows


async def seed(session: AsyncSession, csv_path: str) -> None:
    print("Insertando áreas...")
    for id_area, nombre in AREAS:
        await session.execute(
            text(
                "INSERT INTO reclamos_area (id_area, nombre, activo) "
                "VALUES (:id, :nombre, true) "
                "ON CONFLICT DO NOTHING"
            ),
            {"id": id_area, "nombre": nombre},
        )

    print("Insertando subáreas...")
    for id_subarea, nombre, id_area in SUBAREAS:
        await session.execute(
            text(
                "INSERT INTO reclamos_subarea (id_subarea, nombre, id_area, activo) "
                "VALUES (:id, :nombre, :id_area, true) "
                "ON CONFLICT DO NOTHING"
            ),
            {"id": id_subarea, "nombre": nombre, "id_area": id_area},
        )

    print(f"Leyendo tipos desde {csv_path}...")
    tipos = load_tipos_from_csv(csv_path)
    print(f"Insertando {len(tipos)} tipos de reclamo...")
    for id_tipo, nombre, id_subarea in tipos:
        await session.execute(
            text(
                "INSERT INTO reclamos_tipo (id_tipo, nombre, id_subarea, activo) "
                "VALUES (:id, :nombre, :id_subarea, true) "
                "ON CONFLICT DO NOTHING"
            ),
            {"id": id_tipo, "nombre": nombre, "id_subarea": id_subarea},
        )

    await session.commit()
    print("Seed completado.")


async def main() -> None:
    csv_path = os.path.join(os.path.dirname(__file__), "..", "tipo_reclamo.csv")
    csv_path = os.path.abspath(csv_path)

    if not os.path.exists(csv_path):
        print(f"ERROR: No se encontró {csv_path}")
        print("Coloca tipo_reclamo.csv en la raíz del proyecto (ZGE/) y volvé a ejecutar.")
        sys.exit(1)

    engine = create_async_engine(settings.ASYNC_DATABASE_URI, echo=False)

    print("Creando tablas si no existen...")
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                Base.metadata.tables["reclamos_area"],
                Base.metadata.tables["reclamos_subarea"],
                Base.metadata.tables["reclamos_tipo"],
            ],
        )

    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as session:
        await seed(session, csv_path)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
