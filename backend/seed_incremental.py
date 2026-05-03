"""
seed_incremental.py — Seed incremental desde CSVs (no borra datos existentes).
Inserta cargos, areas, subareas, tipos_reclamo y ciudadanos que no existan aún.
"""
import asyncio
import csv
import re
import os
import sys
from pathlib import Path
from datetime import date, datetime

env_file = os.environ.get("ENV_FILE", ".env.local")
env_path = Path(__file__).parent / env_file
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://postgres:145236@127.0.0.1:5432/zaris_dev")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

CSV_DIR = Path(__file__).parent.parent / "Tablas Iniciales"
UID = 1


def leer_csv(path, delimitador=";"):
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=delimitador)
        for row in reader:
            rows.append({k.strip(): v.strip() for k, v in row.items()})
    return rows


AREAS_SEED = [
    "Secretaria de Planeamiento y Obras Publicas",
    "Secretaria de Salud",
    "Secretaria de Seguridad",
    "Secretaria de Servicios Publicos",
    "Secretaria de Transformacion Digital",
    "Secretaria de Comunicacion",
    "Secretaria de Cultura",
    "Secretaria de Educacion y Empleo",
    "Secretaria de Deportes",
    "Secretaria de Gobierno y Legal Tecnica",
    "Secretaria General",
    "Subsecretaria de Transito",
    "Subsecretaria de Defensa Civil",
    "Subsecretaria de Produccion y Desarrollo Economico",
    "Subsecretaria de Recursos Humanos",
]

PALABRAS_AREA = {
    "salud":    ["salud", "medic", "hospital", "epidem", "vacun", "sanitari", "bromatol"],
    "obras":    ["obra", "vered", "bache", "calle", "pavim", "pluvial", "construc"],
    "transito": ["transit", "vehic", "licencia", "conduc", "senal vial", "semaforo"],
}


def parse_fecha(s):
    if not s or not s.strip():
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


async def main():
    print("=== ZARIS - Seed incremental ===")

    async with AsyncSessionLocal() as db:
        # Verificar usuario seed
        r = await db.execute(text("SELECT id_usuario FROM usuarios WHERE id_usuario = :id"), {"id": UID})
        if not r.fetchone():
            print(f"ERROR: No existe usuario con id_usuario={UID}. Ejecutar seed_auth.py primero.")
            sys.exit(1)

        # ── AREAS ───────────────────────────────────��────────────────────────────
        print("\n--- Areas ---")
        for nombre in AREAS_SEED:
            r = await db.execute(text("SELECT id_area FROM area WHERE nombre = :n"), {"n": nombre})
            if not r.fetchone():
                await db.execute(text("""
                    INSERT INTO area (nombre, descripcion, activo, fecha_alta, fecha_modificacion, id_usuario_alta)
                    VALUES (:nombre, :desc, TRUE, NOW(), NOW(), :uid)
                """), {"nombre": nombre, "desc": "Organismo municipal", "uid": UID})
                print(f"  + {nombre}")
        await db.commit()

        areas_r = await db.execute(text("SELECT id_area, nombre FROM area WHERE activo=TRUE"))
        areas_map = {r.nombre: r.id_area for r in areas_r.fetchall()}
        print(f"Total areas: {len(areas_map)}")

        # ── CARGOS ────────────────────────────────────────────────────────────────
        print("\n--- Cargos ---")
        cargo_rows = leer_csv(CSV_DIR / "cargo.csv")
        cargos_ok = 0
        for r in cargo_rows:
            nombre = (r.get("descripcion") or "").strip()
            if not nombre:
                continue
            ex = await db.execute(text("SELECT id_cargo FROM cargos WHERE nombre = :n"), {"n": nombre})
            if not ex.fetchone():
                await db.execute(text("""
                    INSERT INTO cargos (nombre, activo, fecha_alta, fecha_modificacion, id_usuario_alta)
                    VALUES (:n, TRUE, NOW(), NOW(), :uid)
                """), {"n": nombre, "uid": UID})
                cargos_ok += 1
        await db.commit()
        total_cargos = (await db.execute(text("SELECT COUNT(*) FROM cargos"))).scalar()
        print(f"  +{cargos_ok} nuevos, total={total_cargos}")

        # ── SUBAREAS ─────────────────────────────────────────────────────────────
        print("\n--- Subareas ---")
        sub_rows = leer_csv(CSV_DIR / "subarea.csv")
        id_area_default = (
            areas_map.get("Secretaria de Servicios Publicos")
            or list(areas_map.values())[0]
        )
        subs_ok = 0
        for r in sub_rows:
            # El CSV tiene la columna con tilde en el header
            nombre = r.get("Area de Servicio") or r.get("\xc1rea de Servicio") or r.get("Área de Servicio", "")
            # Intentar todas las variantes posibles de la columna
            if not nombre:
                for k in r:
                    if "servicio" in k.lower() or "area" in k.lower():
                        nombre = r[k]
                        break
            if not nombre:
                continue
            ex = await db.execute(text("SELECT id_subarea FROM subarea WHERE nombre = :n"), {"n": nombre})
            if not ex.fetchone():
                await db.execute(text("""
                    INSERT INTO subarea (nombre, id_area, activo, fecha_alta, fecha_modificacion, id_usuario_alta)
                    VALUES (:nombre, :id_area, TRUE, NOW(), NOW(), :uid)
                """), {"nombre": nombre, "id_area": id_area_default, "uid": UID})
                subs_ok += 1
        await db.commit()
        total_subs = (await db.execute(text("SELECT COUNT(*) FROM subarea"))).scalar()
        print(f"  +{subs_ok} nuevos, total={total_subs}")

        # ── TIPO RECLAMO ─────────────────────────────────────────────────────────
        print("\n--- Tipos de reclamo ---")
        tipo_rows = leer_csv(CSV_DIR / "tipo_reclamo.csv")
        id_area_servicios = areas_map.get("Secretaria de Servicios Publicos")
        id_area_salud     = areas_map.get("Secretaria de Salud")
        id_area_obras     = areas_map.get("Secretaria de Planeamiento y Obras Publicas")
        id_area_transito  = areas_map.get("Subsecretaria de Transito")
        id_a_default      = id_area_servicios or list(areas_map.values())[0]

        def inferir_area(nombre):
            n = nombre.lower()
            if id_area_salud and any(p in n for p in PALABRAS_AREA["salud"]):
                return id_area_salud
            if id_area_obras and any(p in n for p in PALABRAS_AREA["obras"]):
                return id_area_obras
            if id_area_transito and any(p in n for p in PALABRAS_AREA["transito"]):
                return id_area_transito
            return id_a_default

        tipos_ok = 0
        for r in tipo_rows:
            nombre = r.get("Tipo") or r.get("nombre", "")
            if not nombre:
                continue
            sla = 5
            try:
                sla = int(r.get("SLA", "5") or "5")
            except (ValueError, TypeError):
                sla = 5
            id_area = inferir_area(nombre)
            nombre_corto = nombre[:200]
            ex = await db.execute(text("SELECT id_tipo_reclamo FROM tipo_reclamo WHERE nombre = :n"), {"n": nombre_corto})
            if not ex.fetchone():
                await db.execute(text("""
                    INSERT INTO tipo_reclamo (nombre, id_area, sla_dias, activo, fecha_alta, fecha_modificacion, id_usuario_alta)
                    VALUES (:n, :id_area, :sla, TRUE, NOW(), NOW(), :uid)
                """), {"n": nombre_corto, "id_area": id_area, "sla": sla, "uid": UID})
                tipos_ok += 1
        await db.commit()
        total_tipos = (await db.execute(text("SELECT COUNT(*) FROM tipo_reclamo"))).scalar()
        print(f"  +{tipos_ok} nuevos, total={total_tipos}")

        # ── CIUDADANOS ───────────────────────────────────────────────────────────
        print("\n--- Ciudadanos ---")
        nac_r = await db.execute(text("SELECT id FROM nacionalidades WHERE pais ILIKE 'Argentina' LIMIT 1"))
        nac_row = nac_r.fetchone()
        id_nac = nac_row[0] if nac_row else 1

        cit_rows = leer_csv(CSV_DIR / "ciudadano.csv")
        LIMITE = 500

        # Pre-cargar docs/cuils/emails existentes para deduplicar
        doc_vistos = set()
        cuil_vistos = set()
        email_vistos = set()
        ex_docs = await db.execute(text("SELECT doc_nro FROM ciudadanos"))
        for row in ex_docs.fetchall():
            doc_vistos.add(row[0])
        ex_cuils = await db.execute(text("SELECT cuil FROM ciudadanos"))
        for row in ex_cuils.fetchall():
            cuil_vistos.add(row[0])
        ex_emails = await db.execute(text("SELECT email FROM ciudadanos"))
        for row in ex_emails.fetchall():
            email_vistos.add(row[0])

        inserted = 0
        skipped = 0

        for r in cit_rows[:LIMITE]:
            nombre   = (r.get("nombre") or "").strip()
            apellido = (r.get("apellido") or "").strip()
            doc_nro  = re.sub(r"[^\d]", "", r.get("doc_nro") or "")
            cuil_raw = re.sub(r"[^\d]", "", r.get("cuil") or "")
            email    = (r.get("email") or "").strip().lower()
            telefono = re.sub(r"[^\d+\-\s]", "", r.get("telefono") or "")[:15]
            sexo_raw = r.get("sexo", "")
            sexo     = "masculino" if sexo_raw == "1" else "femenino" if sexo_raw == "0" else "otro"
            fecha_nac = parse_fecha(r.get("fecha_nacimiento") or "")
            calle    = (r.get("calle") or "")[:200]
            altura   = (r.get("calleAltura") or "")[:20]

            if not nombre or not apellido or not doc_nro or len(doc_nro) < 7:
                skipped += 1
                continue
            if fecha_nac is None:
                fecha_nac = date(1990, 1, 1)
            if not telefono:
                telefono = "00000000"
            if doc_nro in doc_vistos:
                skipped += 1
                continue
            doc_vistos.add(doc_nro)

            if not cuil_raw or len(cuil_raw) < 11:
                sufijo = "5" if sexo == "femenino" else "7"
                cuil_raw = "20" + doc_nro + sufijo
            cuil_fmt = cuil_raw[:2] + "-" + cuil_raw[2:10] + "-" + cuil_raw[10:] if len(cuil_raw) >= 11 else cuil_raw
            if cuil_fmt in cuil_vistos:
                skipped += 1
                continue
            cuil_vistos.add(cuil_fmt)

            if not email or "@" not in email or email in email_vistos:
                email = nombre.lower().replace(" ", ".") + "." + doc_nro + "@vecino.gob.ar"
            email_vistos.add(email)

            try:
                await db.execute(text("""
                    INSERT INTO ciudadanos
                        (doc_tipo, doc_nro, cuil, nombre, apellido, sexo, fecha_nac,
                         id_nacionalidad, calle, altura, localidad, provincia,
                         telefono, email, activo, ren_chk, email_chk, emp_chk, fecha_alta, id_usuario_alta)
                    VALUES
                        ('DNI', :doc_nro, :cuil, :nombre, :apellido, :sexo, :fecha_nac,
                         :id_nac, :calle, :altura, 'Vicente Lopez', 'Buenos Aires',
                         :telefono, :email, TRUE, FALSE, FALSE, FALSE, NOW(), :uid)
                    ON CONFLICT DO NOTHING
                """), {
                    "doc_nro": doc_nro, "cuil": cuil_fmt, "nombre": nombre[:100],
                    "apellido": apellido[:100], "sexo": sexo, "fecha_nac": fecha_nac,
                    "id_nac": id_nac, "calle": calle, "altura": altura,
                    "telefono": telefono, "email": email[:150], "uid": UID,
                })
                inserted += 1
            except Exception:
                skipped += 1
                await db.rollback()
                continue

            if inserted % 100 == 0:
                await db.commit()
                print(f"  ...{inserted} ciudadanos insertados")

        await db.commit()
        total_cit = (await db.execute(text("SELECT COUNT(*) FROM ciudadanos"))).scalar()
        print(f"  +{inserted} nuevos, {skipped} omitidos, total={total_cit}")

    print("\n=== Seed incremental completado ===")


if __name__ == "__main__":
    asyncio.run(main())
