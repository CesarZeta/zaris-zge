"""
Seed de tipos_activo + activos en local desde CSVs en `Tablas Iniciales/`.

- Toma los 5 tipos relevantes (los mismos que ya hay en prod).
- Carga 1000 activos del CSV con coordenadas válidas dentro del bbox de Vicente López.
- Idempotente: usa UPSERT por codigo_unico para activos y por nombre para tipos.

Uso:
    cd backend && python seed_activos_local.py
"""
import asyncio
import csv
from pathlib import Path

import asyncpg

DSN = "postgresql://postgres:145236@127.0.0.1:5432/zaris_dev"
ROOT = Path(__file__).resolve().parents[1]
CSV_TIPOS = ROOT / "Tablas Iniciales" / "tipo_activos.csv"
CSV_ACTIVOS = ROOT / "Tablas Iniciales" / "Activos.csv"

# Mapeo del id_identificador_tipo del CSV → nombre que ya existe en prod.
# Solo seedeamos lo que prod tiene (5 tipos).
TIPOS_PROD = [
    ("Poste", False),
    ("Luminaria", False),
    ("Profesionales - Permiso de Obra", False),
    ("Vehículo", False),
    ("Permiso de obra nuevo", False),
]

# Mapeo CSV id_identificador_tipo → nombre.
# Inferido de descripciones del CSV: el tipo 214 corresponde a luminarias.
# El resto de tipos se mapean por palabra clave en la descripción del activo.
def tipo_para_descripcion(desc: str) -> str:
    d = (desc or "").lower()
    if "permiso de obra" in d or "obra nuevo" in d:
        return "Permiso de obra nuevo"
    if "profesional" in d:
        return "Profesionales - Permiso de Obra"
    if "vehic" in d or "vehíc" in d or "vehicl" in d:
        return "Vehículo"
    if "poste" in d:
        return "Poste"
    # Default — luminarias dominan el dataset
    return "Luminaria"


def parse_num(s: str) -> float | None:
    """CSV usa coma decimal."""
    if not s:
        return None
    s = s.strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


# Vicente López (bbox amplio, suficiente para el dataset real)
VL_BBOX = (-34.55, -58.55, -34.48, -58.45)


async def main():
    conn = await asyncpg.connect(DSN)
    try:
        # ── Tipos ────────────────────────────────────────────────────────
        tipos_id = {}
        for nombre, req_ciud in TIPOS_PROD:
            row = await conn.fetchrow(
                """
                INSERT INTO tipos_activo (nombre, requiere_ciudadano, activo)
                VALUES ($1, $2, TRUE)
                ON CONFLICT (nombre) DO UPDATE SET activo = TRUE
                RETURNING id_tipo_activo
                """,
                nombre, req_ciud,
            )
            tipos_id[nombre] = row["id_tipo_activo"]
        print(f"  tipos_activo: {len(tipos_id)} OK")

        # ── Localidad default: Vicente López ─────────────────────────────
        loc = await conn.fetchrow(
            "SELECT id_localidad FROM localidades WHERE nombre = 'Vicente López' LIMIT 1"
        )
        id_localidad_vl = loc["id_localidad"] if loc else None

        # ── Activos ──────────────────────────────────────────────────────
        if not CSV_ACTIVOS.exists():
            print(f"  ! CSV no encontrado: {CSV_ACTIVOS}")
            return

        target = 1000
        insertados = 0
        with CSV_ACTIVOS.open(encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                if insertados >= target:
                    break
                codigo = (row.get("codigo_unico") or "").strip()
                if not codigo:
                    continue
                lat = parse_num(row.get("latitud"))
                lon = parse_num(row.get("longitud"))
                if lat is None or lon is None:
                    continue
                if not (VL_BBOX[0] <= lat <= VL_BBOX[2]
                        and VL_BBOX[1] <= lon <= VL_BBOX[3]):
                    continue

                desc = (row.get("descripcion") or "").strip() or None
                direccion = (row.get("direccion") or "").strip() or None
                tipo_nombre = tipo_para_descripcion(desc or "")
                id_tipo = tipos_id[tipo_nombre]

                await conn.execute(
                    """
                    INSERT INTO activos
                        (codigo_unico, id_tipo_activo, descripcion, direccion,
                         id_localidad, latitud, longitud, activo)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE)
                    ON CONFLICT (codigo_unico) DO UPDATE
                       SET id_tipo_activo = EXCLUDED.id_tipo_activo,
                           descripcion = EXCLUDED.descripcion,
                           direccion = EXCLUDED.direccion,
                           id_localidad = EXCLUDED.id_localidad,
                           latitud = EXCLUDED.latitud,
                           longitud = EXCLUDED.longitud,
                           activo = TRUE
                    """,
                    codigo, id_tipo, desc, direccion,
                    id_localidad_vl, lat, lon,
                )
                insertados += 1

        print(f"  activos: {insertados} insertados/actualizados")

        total = await conn.fetchval("SELECT COUNT(*) FROM activos WHERE activo = TRUE")
        print(f"  total activos en DB: {total}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
