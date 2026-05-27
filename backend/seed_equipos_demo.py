"""
Seed de grupos/mesas demo para testing de Trámites.

Crea equipos de ejemplo (tabla `equipos`) y los puebla con los agentes que tienen
usuario vinculado (pueden loguearse y tomar trámites desde "Mi bandeja") de la
subárea correspondiente, en `equipo_agentes`.

Cuando un trámite se pasa a uno de estos equipos (destinatario tipo 'equipo'),
todos sus integrantes lo ven en su bandeja y cualquiera puede tomarlo (Trámites §35).

IDEMPOTENTE (§24): resuelve subáreas y agentes POR NOMBRE/subárea, nunca por ID
hardcodeado (local y prod tienen IDs distintos). Re-correrlo no duplica:
- el equipo se busca por nombre (case-insensitive); si existe se reactiva.
- las relaciones equipo_agentes se buscan por (id_equipo, id_agente).

Uso:
  Local:  cd backend; $env:ENV_FILE=".env.local"; python seed_equipos_demo.py
  Prod:   cd backend; $env:ENV_FILE=".env.prod";  python seed_equipos_demo.py --confirm-prod
"""
import asyncio
import os
import sys

from sqlalchemy import text

from app.core.database import engine

# Grupos demo: (nombre_equipo, keyword_subarea, descripcion).
# keyword_subarea se matchea con ILIKE sobre subarea.nombre (case-insensitive).
GRUPOS = [
    ("Mesa Habilitaciones Comerciales", "Habilitaciones Comerciales",
     "Mesa que recibe y gestiona los trámites de habilitación comercial."),
    ("Mesa Obras Particulares", "Obras Particulares",
     "Mesa de Obras Particulares: planos, permisos y expedientes de obra."),
    ("Mesa Bromatología", "Bromatologia e Inspecciones",
     "Mesa de Bromatología e Inspecciones para trámites de control sanitario."),
    ("Cuadrilla Mantenimiento General", "Mantenimiento general",
     "Cuadrilla operativa de mantenimiento general del municipio."),
    ("Mesa Tránsito", "Tránsito",
     "Mesa de Tránsito para trámites y expedientes de circulación y licencias."),
]


async def seed():
    async with engine.connect() as conn:
        raw = await conn.get_raw_connection()
        db = raw.driver_connection  # conexión asyncpg real

        total_equipos = 0
        total_rels = 0

        for nombre_equipo, kw_subarea, descripcion in GRUPOS:
            # 1) resolver subárea por keyword (activa)
            sub = await db.fetchrow(
                "SELECT id_subarea, nombre FROM subarea "
                "WHERE activo AND nombre ILIKE $1 "
                "ORDER BY id_subarea LIMIT 1",
                f"%{kw_subarea}%",
            )
            if not sub:
                print(f"[SKIP] subarea '{kw_subarea}' no encontrada -> no creo '{nombre_equipo}'")
                continue
            id_subarea = sub["id_subarea"]

            # 2) buscar equipo por nombre (case-insensitive); crear o reactivar
            eq = await db.fetchrow(
                "SELECT id_equipo, activo FROM equipos WHERE LOWER(nombre)=LOWER($1) "
                "ORDER BY activo DESC, id_equipo LIMIT 1",
                nombre_equipo,
            )
            if eq:
                id_equipo = eq["id_equipo"]
                await db.execute(
                    "UPDATE equipos SET activo=TRUE, descripcion=$2, id_subarea=$3, "
                    "fecha_modificacion=NOW() WHERE id_equipo=$1",
                    id_equipo, descripcion, id_subarea,
                )
                print(f"[OK]  equipo existente reactivado: '{nombre_equipo}' (id={id_equipo})")
            else:
                row = await db.fetchrow(
                    "INSERT INTO equipos (nombre, descripcion, id_subarea, activo) "
                    "VALUES ($1, $2, $3, TRUE) RETURNING id_equipo",
                    nombre_equipo, descripcion, id_subarea,
                )
                id_equipo = row["id_equipo"]
                total_equipos += 1
                print(f"[NEW] equipo creado: '{nombre_equipo}' (id={id_equipo}, subarea={sub['nombre']})")

            # 3) agentes con usuario de esa subárea (pueden loguearse y tomar trámites)
            agentes = await db.fetch(
                "SELECT id_agente, apellido, nombre FROM agentes "
                "WHERE activo AND id_usuario IS NOT NULL AND id_subarea=$1 "
                "ORDER BY apellido",
                id_subarea,
            )
            if not agentes:
                print(f"      (sin agentes con usuario en subarea {id_subarea} -> grupo vacío)")
                continue

            for a in agentes:
                ya = await db.fetchrow(
                    "SELECT id_equipo_agente, activo FROM equipo_agentes "
                    "WHERE id_equipo=$1 AND id_agente=$2 "
                    "ORDER BY activo DESC, id_equipo_agente LIMIT 1",
                    id_equipo, a["id_agente"],
                )
                if ya:
                    if not ya["activo"]:
                        await db.execute(
                            "UPDATE equipo_agentes SET activo=TRUE, fecha_modificacion=NOW() "
                            "WHERE id_equipo_agente=$1",
                            ya["id_equipo_agente"],
                        )
                        print(f"      + reactivado: {a['apellido']}, {a['nombre']}")
                else:
                    await db.execute(
                        "INSERT INTO equipo_agentes (id_equipo, id_agente, activo) "
                        "VALUES ($1, $2, TRUE)",
                        id_equipo, a["id_agente"],
                    )
                    total_rels += 1
                    print(f"      + agregado:   {a['apellido']}, {a['nombre']}")

        print(f"\nListo. Equipos nuevos: {total_equipos}. Relaciones nuevas: {total_rels}.")

    await engine.dispose()


if __name__ == "__main__":
    env_file = os.environ.get("ENV_FILE", "")
    apunta_prod = "prod" in env_file.lower()
    if apunta_prod and "--confirm-prod" not in sys.argv:
        print("ENV_FILE apunta a prod. Re-ejecutar con --confirm-prod para confirmar.")
        sys.exit(1)
    asyncio.run(seed())
