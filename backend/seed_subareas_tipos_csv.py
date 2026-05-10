"""
ZARIS — Re-seed de subarea + tipo_reclamo desde CSVs oficiales.

Idempotente: soft-delete previo + reactivar/insert por nombre.
Resuelve áreas canónicas por keyword (case-insensitive) — funciona en cualquier
DB independientemente de los IDs de área.

Uso:
    # Local (zaris_dev):
    python seed_subareas_tipos_csv.py

    # Otro entorno:
    DATABASE_URL=postgresql://... python seed_subareas_tipos_csv.py
"""
import asyncio
import csv
import os
import unicodedata
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
SUB_CSV = ROOT / "Tablas Iniciales" / "subarea.csv"
TIPO_CSV = ROOT / "Tablas Iniciales" / "tipo_reclamo.csv"

# Claves simbólicas para áreas canónicas (resueltas por nombre en cada DB)
AREA_GOB, AREA_PL, AREA_SAL, AREA_SEG, AREA_SP, AREA_TR = (
    "_gob_", "_pl_", "_sal_", "_seg_", "_sp_", "_tr_"
)

AREAS_KEYWORDS = {
    AREA_GOB: ["gobierno"],
    AREA_PL:  ["planeamiento", "obras publicas", "obras públicas"],
    AREA_SAL: ["salud"],
    AREA_SEG: ["seguridad"],
    AREA_SP:  ["servicios publicos", "servicios públicos"],
    AREA_TR:  ["transito", "tránsito"],
}

AREAS_CANON_NAME = {
    AREA_GOB: "Gobierno",
    AREA_PL:  "Secretaria de Planeamiento y Obras Publicas",
    AREA_SAL: "Secretaria de Salud",
    AREA_SEG: "Secretaria de Seguridad",
    AREA_SP:  "Secretaria de Servicios Publicos",
    AREA_TR:  "Subsecretaria de Transito",
}

# Subáreas referenciadas en tipo_reclamo.csv pero no presentes en subarea.csv.
# Sus nombres se inferiron de los tipos que las usan (ver memoria).
HUERFANAS = {
    "7984": "Mantenimiento general",
    "7985": "Mantenimiento eléctrico",
    "7987": "Mantenimiento térmico",
    "7988": "Mantenimiento sanitario",
    "7989": "Carpintería y vidriería",
    "7990": "Higiene y seguridad - edificios municipales",
    "8013": "Instalación de aires",
    "8014": "Telefonía e informática",
    "8070": "Censos",
}


def norm(s: str) -> str:
    s = s.lower()
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def heur_area(nombre: str) -> str:
    """Asigna una clave de área canónica a una subárea según keywords del nombre."""
    n = norm(nombre)
    if any(k in n for k in ["transito", "licencia de conducir", "senalamiento", "vehiculo abandonado"]):
        return AREA_TR
    if any(k in n for k in ["salud", "medicament", "vacuna"]):
        return AREA_SAL
    if "seguro" in n and "punto" in n:
        return AREA_SEG
    if any(k in n for k in ["calles y veredas", "mant. vial", "obras municipales",
                            "permiso de obra", "inscripcion de profesionales", "vialidad"]):
        return AREA_PL
    if any(k in n for k in ["inspecciones", "cedulas de notif", "habilitacion comercial",
                            "asesoramiento", "censo"]):
        return AREA_GOB
    return AREA_SP


def cargar_subs():
    subs = []
    with SUB_CSV.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f, delimiter=";"):
            sid = row["id_area_servicio"].strip()
            nombre = row["Área de Servicio"].strip()
            if sid and nombre:
                subs.append({"csv_id": sid, "nombre": nombre, "key": heur_area(nombre)})
    for sid, nombre in HUERFANAS.items():
        subs.append({"csv_id": sid, "nombre": nombre, "key": heur_area(nombre)})
    return subs


def cargar_tipos():
    tipos = []
    with TIPO_CSV.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f, delimiter=";"):
            nombre = row["Tipo"].strip()
            if not nombre:
                continue
            try:
                sla = int(row.get("SLA") or 0)
            except ValueError:
                sla = 0
            audit = row.get("auditoria", "0").strip() in ("1", "true", "True")
            tipos.append({
                "nombre": nombre,
                "sla_dias": sla if sla > 0 else None,
                "audit": audit,
                "csv_subarea": row["id_area_servicio"].strip(),
            })
    return tipos


async def resolver_areas(conn) -> dict:
    """Resuelve cada clave a un id_area real. Reactiva inactiva o crea si no existe."""
    out = {}
    for clave, kws in AREAS_KEYWORDS.items():
        row = None
        for kw in kws:
            row = await conn.fetchrow(
                "SELECT id_area, activo FROM area WHERE LOWER(nombre) LIKE $1 "
                "ORDER BY activo DESC, id_area LIMIT 1",
                f"%{kw}%",
            )
            if row:
                break
        if row:
            if not row["activo"]:
                await conn.execute(
                    "UPDATE area SET activo=TRUE, fecha_modificacion=NOW() WHERE id_area=$1",
                    row["id_area"],
                )
            out[clave] = row["id_area"]
        else:
            new_id = await conn.fetchval(
                "INSERT INTO area (nombre, activo, fecha_alta, fecha_modificacion) "
                "VALUES ($1, TRUE, NOW(), NOW()) RETURNING id_area",
                AREAS_CANON_NAME[clave],
            )
            out[clave] = new_id
    return out


async def reseed(dsn: str, label: str):
    print(f"\n=== {label} ===")
    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction():
            area_ids = await resolver_areas(conn)
            print(f"  areas canonicas: {area_ids}")

            r1 = await conn.execute(
                "UPDATE tipo_reclamo SET activo=FALSE, fecha_modificacion=NOW() WHERE activo=TRUE"
            )
            r2 = await conn.execute(
                "UPDATE subarea SET activo=FALSE, fecha_modificacion=NOW() WHERE activo=TRUE"
            )
            print(f"  soft-delete: tipos={r1} subareas={r2}")

            subs = cargar_subs()
            for s in subs:
                s["id_area"] = area_ids[s["key"]]

            csv_to_db = {}
            for s in subs:
                row = await conn.fetchrow(
                    "SELECT id_subarea FROM subarea WHERE LOWER(TRIM(nombre))=LOWER(TRIM($1)) LIMIT 1",
                    s["nombre"],
                )
                if row:
                    await conn.execute(
                        "UPDATE subarea SET id_area=$1, activo=TRUE, fecha_modificacion=NOW() "
                        "WHERE id_subarea=$2",
                        s["id_area"], row["id_subarea"],
                    )
                    csv_to_db[s["csv_id"]] = row["id_subarea"]
                else:
                    new_id = await conn.fetchval(
                        "INSERT INTO subarea (nombre, id_area, activo, fecha_alta, fecha_modificacion) "
                        "VALUES ($1, $2, TRUE, NOW(), NOW()) RETURNING id_subarea",
                        s["nombre"], s["id_area"],
                    )
                    csv_to_db[s["csv_id"]] = new_id
            print(f"  subareas activas: {len(csv_to_db)}")

            tipos = cargar_tipos()
            ins = upd = sin_sub = 0
            for t in tipos:
                id_sub = csv_to_db.get(t["csv_subarea"])
                if not id_sub:
                    sin_sub += 1
                    continue
                id_area = await conn.fetchval(
                    "SELECT id_area FROM subarea WHERE id_subarea=$1", id_sub
                )
                row = await conn.fetchrow(
                    "SELECT id_tipo_reclamo FROM tipo_reclamo "
                    "WHERE LOWER(TRIM(nombre))=LOWER(TRIM($1)) LIMIT 1",
                    t["nombre"],
                )
                if row:
                    await conn.execute(
                        "UPDATE tipo_reclamo SET id_subarea=$1, id_area=$2, sla_dias=$3, "
                        "audit=$4, activo=TRUE, fecha_modificacion=NOW() WHERE id_tipo_reclamo=$5",
                        id_sub, id_area, t["sla_dias"], t["audit"], row["id_tipo_reclamo"],
                    )
                    upd += 1
                else:
                    await conn.execute(
                        "INSERT INTO tipo_reclamo (nombre, id_subarea, id_area, sla_dias, audit, "
                        "activo, fecha_alta, fecha_modificacion) "
                        "VALUES ($1, $2, $3, $4, $5, TRUE, NOW(), NOW())",
                        t["nombre"], id_sub, id_area, t["sla_dias"], t["audit"],
                    )
                    ins += 1
            print(f"  tipos: insertados={ins} actualizados={upd} sin_subarea={sin_sub}")

            r3 = await conn.execute("""
                UPDATE area SET activo=FALSE, fecha_modificacion=NOW()
                WHERE activo=TRUE AND id_area NOT IN (
                    SELECT DISTINCT id_area FROM subarea WHERE activo=TRUE AND id_area IS NOT NULL
                )
            """)
            print(f"  areas huerfanas soft-deleted: {r3}")

            tot_a = await conn.fetchval("SELECT COUNT(*) FROM area WHERE activo")
            tot_s = await conn.fetchval("SELECT COUNT(*) FROM subarea WHERE activo")
            tot_t = await conn.fetchval("SELECT COUNT(*) FROM tipo_reclamo WHERE activo")
            print(f"  TOTAL FINAL: areas={tot_a} subareas={tot_s} tipos={tot_t}")
    finally:
        await conn.close()


async def main():
    dsn = os.environ.get("DATABASE_URL") or "postgresql://postgres:145236@127.0.0.1:5432/zaris_dev"
    label = "PROD" if os.environ.get("DATABASE_URL") else "LOCAL"
    await reseed(dsn, label)


if __name__ == "__main__":
    asyncio.run(main())
