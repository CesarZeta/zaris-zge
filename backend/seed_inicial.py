"""
seed_inicial.py — Seed de tablas iniciales para ZARIS ZGE
Inserta: cargos, areas (Secretarías), subareas, tipo_reclamo, ciudadanos (desde CSV) y 20 reclamos demo.

Uso:
    cd backend
    $env:ENV_FILE=".env.local"; python seed_inicial.py          # local
    $env:ENV_FILE=".env.production"; python seed_inicial.py     # prod (confirmar antes)

Requisitos:
    - Migración 20_buc_audit_reclamos.sql ya aplicada.
    - Al menos un usuario con id_usuario=1 en la base.
"""
import asyncio
import csv
import os
import sys
import re
from pathlib import Path
from datetime import date, datetime

# ── Detectar .env ─────────────────────────────────────────────────────────────
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

# ── Rutas CSV ─────────────────────────────────────────────────────────────────
CSV_DIR = Path(__file__).parent.parent / "Tablas Iniciales"
CIUDADANO_CSV  = CSV_DIR / "ciudadano.csv"
TIPO_RECL_CSV  = CSV_DIR / "tipo_reclamo.csv"
CARGO_CSV      = CSV_DIR / "cargo.csv"
SUBAREA_CSV    = CSV_DIR / "subarea.csv"

ID_USUARIO_SEED = 1   # usuario que registra el seed


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _leer_csv(path: Path, delimitador=";"):
    """Lee CSV con BOM y retorna lista de dicts."""
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=delimitador)
        for row in reader:
            rows.append({k.strip(): v.strip() for k, v in row.items()})
    return rows


async def _count(db, tabla, condicion="1=1"):
    r = await db.execute(text(f"SELECT COUNT(*) FROM {tabla} WHERE {condicion}"))
    return r.scalar()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CARGOS (desde cargo.csv)
# ═══════════════════════════════════════════════════════════════════════════════

async def seed_cargos(db: AsyncSession):
    existing = await _count(db, "cargos")
    if existing > 0:
        print(f"  cargos: ya tiene {existing} registros — omitiendo")
        return

    rows = _leer_csv(CARGO_CSV)
    print(f"  cargos: insertando {len(rows)} registros...")
    for r in rows:
        if not r.get("descripcion"):
            continue
        await db.execute(text("""
            INSERT INTO cargos (nombre, activo, fecha_alta, fecha_modificacion, id_usuario_alta)
            VALUES (:nombre, TRUE, NOW(), NOW(), :uid)
            ON CONFLICT DO NOTHING
        """), {"nombre": r["descripcion"], "uid": ID_USUARIO_SEED})
    await db.commit()
    total = await _count(db, "cargos")
    print(f"  cargos: {total} registros en total")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. AREAS — Secretarías derivadas de cargos "Secretario/a de..."
# ═══════════════════════════════════════════════════════════════════════════════

AREAS_SEED = [
    "Secretaría de Planeamiento y Obras Públicas",
    "Secretaría de Salud",
    "Secretaría de Seguridad",
    "Secretaría de Servicios Públicos",
    "Secretaría de Transformación Digital",
    "Secretaría de Comunicación",
    "Secretaría de Cultura",
    "Secretaría de Educación y Empleo",
    "Secretaría de Deportes",
    "Secretaría de Gobierno y Legal Técnica",
    "Secretaría General",
    "Subsecretaría de Tránsito",
    "Subsecretaría de Defensa Civil",
    "Subsecretaría de Producción y Desarrollo Económico",
    "Subsecretaría de Recursos Humanos",
]


async def seed_areas(db: AsyncSession) -> dict:
    """Inserta areas y retorna {nombre: id_area}."""
    existing = await _count(db, "area")
    if existing > 0:
        print(f"  area: ya tiene {existing} registros — omitiendo inserción")
    else:
        print(f"  area: insertando {len(AREAS_SEED)} secretarías...")
        for nombre in AREAS_SEED:
            await db.execute(text("""
                INSERT INTO area (nombre, descripcion, activo, fecha_alta, fecha_modificacion, id_usuario_alta)
                VALUES (:nombre, :desc, TRUE, NOW(), NOW(), :uid)
                ON CONFLICT DO NOTHING
            """), {"nombre": nombre, "desc": f"Organismo municipal: {nombre}", "uid": ID_USUARIO_SEED})
        await db.commit()

    result = await db.execute(text("SELECT id_area, nombre FROM area WHERE activo = TRUE ORDER BY id_area"))
    rows = result.fetchall()
    mapa = {r.nombre: r.id_area for r in rows}
    print(f"  area: {len(mapa)} áreas disponibles")
    return mapa


# ═══════════════════════════════════════════════════════════════════════════════
# 3. SUBAREAS (desde subarea.csv)
# ═══════════════════════════════════════════════════════════════════════════════

async def seed_subareas(db: AsyncSession, areas_map: dict):
    existing = await _count(db, "subarea")
    if existing > 0:
        print(f"  subarea: ya tiene {existing} registros — omitiendo")
        return

    rows = _leer_csv(SUBAREA_CSV)
    print(f"  subarea: insertando {len(rows)} registros...")

    # El CSV tiene id_area=1 para todas — mapear a "Secretaría de Servicios Públicos" por defecto
    id_area_default = areas_map.get("Secretaría de Servicios Públicos") or list(areas_map.values())[0] if areas_map else None

    for r in rows:
        nombre = r.get("Área de Servicio") or r.get("nombre", "")
        if not nombre:
            continue
        await db.execute(text("""
            INSERT INTO subarea (nombre, id_area, activo, fecha_alta, fecha_modificacion, id_usuario_alta)
            VALUES (:nombre, :id_area, TRUE, NOW(), NOW(), :uid)
            ON CONFLICT DO NOTHING
        """), {"nombre": nombre, "id_area": id_area_default, "uid": ID_USUARIO_SEED})
    await db.commit()
    total = await _count(db, "subarea")
    print(f"  subarea: {total} registros en total")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. TIPO_RECLAMO (desde tipo_reclamo.csv)
# ═══════════════════════════════════════════════════════════════════════════════

async def seed_tipo_reclamo(db: AsyncSession, areas_map: dict):
    existing = await _count(db, "tipo_reclamo")
    if existing > 0:
        print(f"  tipo_reclamo: ya tiene {existing} registros — omitiendo")
        return

    rows = _leer_csv(TIPO_RECL_CSV)
    print(f"  tipo_reclamo: insertando {len(rows)} registros...")

    # Mapeo de id_area_servicio → area basado en nombre del tipo (heurístico simple)
    id_area_servicios = areas_map.get("Secretaría de Servicios Públicos")
    id_area_salud     = areas_map.get("Secretaría de Salud")
    id_area_obras     = areas_map.get("Secretaría de Planeamiento y Obras Públicas")
    id_area_transito  = areas_map.get("Subsecretaría de Tránsito")
    id_area_default   = id_area_servicios or (list(areas_map.values())[0] if areas_map else None)

    PALABRAS_AREA = {
        id_area_salud:    ["salud", "médico", "hospital", "epidem", "vacun", "sanitari", "bromatol"],
        id_area_obras:    ["obra", "vered", "bache", "calle", "pavim", "pluvial", "construc"],
        id_area_transito: ["tránsito", "transito", "vehic", "licencia", "conduc", "señal vial", "semáforo"],
    }

    def _inferir_area(nombre: str) -> int | None:
        n = nombre.lower()
        for id_a, palabras in PALABRAS_AREA.items():
            if id_a and any(p in n for p in palabras):
                return id_a
        return id_area_default

    inserted = 0
    for r in rows:
        nombre = r.get("Tipo") or r.get("nombre", "")
        if not nombre:
            continue
        sla = r.get("SLA", "5")
        try:
            sla_dias = int(sla) if sla else 5
        except ValueError:
            sla_dias = 5
        id_area = _inferir_area(nombre)
        await db.execute(text("""
            INSERT INTO tipo_reclamo
                (nombre, id_area, sla_dias, activo, fecha_alta, fecha_modificacion, id_usuario_alta)
            VALUES (:nombre, :id_area, :sla, TRUE, NOW(), NOW(), :uid)
        """), {"nombre": nombre[:200], "id_area": id_area, "sla": sla_dias, "uid": ID_USUARIO_SEED})
        inserted += 1

    await db.commit()
    print(f"  tipo_reclamo: {inserted} registros insertados")


# ═══════════════════════════════════════════════════════════════════════════════
# 5. CIUDADANOS (desde ciudadano.csv) — solo primeros 500 para demo
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_fecha(s: str) -> date | None:
    """Intenta parsear fechas en múltiples formatos."""
    if not s or s.strip() == "":
        return None
    s = s.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


async def seed_ciudadanos(db: AsyncSession):
    existing = await _count(db, "ciudadanos")
    if existing > 0:
        print(f"  ciudadanos: ya tiene {existing} registros — omitiendo")
        return

    # Obtener id_nacionalidad Argentina (id=1 o la primera disponible)
    r = await db.execute(text("SELECT id FROM nacionalidades WHERE pais ILIKE 'Argentina' LIMIT 1"))
    row = r.fetchone()
    id_nac_arg = row[0] if row else 1

    rows = _leer_csv(CIUDADANO_CSV)
    LIMITE = 500
    print(f"  ciudadanos: insertando hasta {LIMITE} registros del CSV ({len(rows)-1} disponibles)...")

    inserted = 0
    skipped  = 0
    doc_vistos = set()
    cuil_vistos = set()
    email_vistos = set()

    for r in rows[:LIMITE]:
        nombre   = (r.get("nombre") or "").strip()
        apellido = (r.get("apellido") or "").strip()
        doc_nro  = re.sub(r"[^\d]", "", r.get("doc_nro") or "")
        cuil_raw = re.sub(r"[^\d]", "", r.get("cuil") or "")
        email    = (r.get("email") or "").strip().lower()
        telefono = re.sub(r"[^\d+\-\s]", "", r.get("telefono") or "")[:15]
        sexo     = "masculino" if r.get("sexo") == "1" else "femenino" if r.get("sexo") == "0" else "otro"
        fecha_nac = _parse_fecha(r.get("fecha_nacimiento") or "")
        calle    = (r.get("calle") or "")[:200]
        altura   = (r.get("calleAltura") or "")[:20]
        localidad = "Vicente López"
        provincia = "Buenos Aires"
        cod_postal = (r.get("codigo_postal") or "")[:10]

        # Validaciones mínimas
        if not nombre or not apellido or not doc_nro or len(doc_nro) < 7:
            skipped += 1
            continue
        if fecha_nac is None:
            fecha_nac = date(1990, 1, 1)
        if not telefono:
            telefono = "00000000"

        # Deduplicar
        if doc_nro in doc_vistos:
            skipped += 1
            continue
        doc_vistos.add(doc_nro)

        # Construir cuil si no viene
        if not cuil_raw or len(cuil_raw) < 11:
            cuil_raw = f"20{doc_nro}{'5' if sexo == 'femenino' else '7'}"
        cuil_fmt = f"{cuil_raw[:2]}-{cuil_raw[2:10]}-{cuil_raw[10:]}" if len(cuil_raw) >= 11 else cuil_raw
        if cuil_fmt in cuil_vistos:
            skipped += 1
            continue
        cuil_vistos.add(cuil_fmt)

        # Email único
        if not email or "@" not in email or email in email_vistos:
            email = f"{nombre.lower().replace(' ','.')}.{doc_nro}@vecino.gob.ar"
        email_vistos.add(email)

        try:
            await db.execute(text("""
                INSERT INTO ciudadanos
                    (doc_tipo, doc_nro, cuil, nombre, apellido, sexo, fecha_nac,
                     id_nacionalidad, calle, altura, localidad, provincia,
                     telefono, email, activo, ren_chk, email_chk, emp_chk, fecha_alta,
                     id_usuario_alta)
                VALUES
                    ('DNI', :doc_nro, :cuil, :nombre, :apellido, :sexo, :fecha_nac,
                     :id_nac, :calle, :altura, :localidad, :provincia,
                     :telefono, :email, TRUE, FALSE, FALSE, FALSE, NOW(), :uid)
                ON CONFLICT DO NOTHING
            """), {
                "doc_nro": doc_nro, "cuil": cuil_fmt, "nombre": nombre[:100],
                "apellido": apellido[:100], "sexo": sexo, "fecha_nac": fecha_nac,
                "id_nac": id_nac_arg, "calle": calle, "altura": altura,
                "localidad": localidad, "provincia": provincia,
                "telefono": telefono, "email": email[:150],
                "uid": ID_USUARIO_SEED,
            })
            inserted += 1
        except Exception as e:
            skipped += 1
            await db.rollback()
            continue

        if inserted % 100 == 0:
            await db.commit()
            print(f"    ...{inserted} ciudadanos insertados")

    await db.commit()
    print(f"  ciudadanos: {inserted} insertados, {skipped} omitidos")
    return inserted


# ═══════════════════════════════════════════════════════════════════════════════
# 6. RECLAMOS DEMO (20 registros transaccionales)
# ═══════════════════════════════════════════════════════════════════════════════

RECLAMOS_DEMO = [
    ("En gestión",  "Alta",  "Bache profundo en calzada frente al 1240, peligroso para vehículos y peatones."),
    ("Ingresado",   "Media", "Tres luminarias apagadas en el bloque entre Mitre y Belgrano desde las 20hs."),
    ("En revisión", "Alta",  "Paciente crónica no puede obtener turno con especialista hace tres semanas."),
    ("Resuelto",    "Alta",  "Ciudadano con cert. discapacidad solicita subsidio de transporte rechazado por error."),
    ("Resuelto",    "Alta",  "Árbol caído sobre vereda bloqueando paso tras tormenta del 25/04, riesgo eléctrico."),
    ("En revisión", "Baja",  "Renovación de licencia de conducir solicitada hace 45 días sin respuesta."),
    ("Cerrado",     "Media", "Hace dos semanas no pasa el camión recolector. Bolsas acumuladas en vereda."),
    ("Ingresado",   "Alta",  "Falta de materiales en obra de centro comunitario Norte, paralizada hace 3 días."),
    ("En gestión",  "Media", "Semáforo en esquina de Av. Maipú y Tucumán sin funcionar hace 4 días."),
    ("Ingresado",   "Baja",  "Solicitud de poda de árbol en vereda que obstruye la visibilidad."),
    ("Resuelto",    "Media", "Pérdida de agua en la vía pública frente al 578, calle anegada permanentemente."),
    ("En gestión",  "Alta",  "Perro abandonado en parque Municipal agresivo, requiere intervención urgente."),
    ("En revisión", "Alta",  "Ruidos molestos de obra en horario nocturno, incumplimiento ordenanza."),
    ("Ingresado",   "Media", "Contenedor de residuos volcado en Av. del Libertador obstruye parte de la calzada."),
    ("Resuelto",    "Baja",  "Trámite de habilitación comercial sin respuesta después de 60 días hábiles."),
    ("Cerrado",     "Alta",  "Inundación de sótano por desborde de pluvial en tormenta del 10/04."),
    ("En gestión",  "Media", "Pintada de graffitis en monumento histórico de la plaza central."),
    ("Ingresado",   "Alta",  "Desconexión irregular del servicio de alumbrado en B° Residencial Norte."),
    ("En revisión", "Media", "Vehículo abandonado hace más de 30 días obstruye estacionamiento en Calle 9."),
    ("Resuelto",    "Baja",  "Solicitud de instalación de nuevo contenedor de reciclado en Barrio Sur."),
]


async def seed_reclamos(db: AsyncSession, areas_map: dict):
    existing = await _count(db, "reclamos")
    if existing > 0:
        print(f"  reclamos: ya tiene {existing} registros — omitiendo")
        return

    # Obtener ciudadanos disponibles
    r = await db.execute(text(
        "SELECT id_ciudadano, nombre, apellido FROM ciudadanos WHERE activo=TRUE ORDER BY id_ciudadano LIMIT 20"
    ))
    ciudadanos = r.fetchall()
    if not ciudadanos:
        print("  reclamos: no hay ciudadanos — ejecutar seed de ciudadanos primero")
        return

    # Obtener tipos de reclamo
    r = await db.execute(text(
        "SELECT id_tipo_reclamo, nombre, id_area FROM tipo_reclamo WHERE activo=TRUE LIMIT 50"
    ))
    tipos = r.fetchall()
    if not tipos:
        print("  reclamos: no hay tipos de reclamo — ejecutar seed de tipo_reclamo primero")
        return

    id_area_default = list(areas_map.values())[0] if areas_map else None

    # Fechas distribuidas en los últimos 30 días
    from datetime import timedelta
    import random
    random.seed(42)

    base_date = datetime(2026, 4, 3)
    domicilios = [
        "Av. San Martín 1240", "Calle 9 de Julio 456", "Centro de Salud Nº 3",
        "Bv. Illia 890", "Laprida 234 esq. Paso", "Dirección de Tránsito",
        "Rivadavia 567 B° Centro", "Hospital Municipal", "Av. Maipú y Tucumán",
        "Parque Municipal", "Av. del Libertador 1500", "Calle Mitre 890",
        "B° Residencial Norte", "Plaza Central", "Calle 9 esq. Rivadavia",
        "Av. Colón 2345", "San Lorenzo 123", "Belgrano 450",
        "Lavalle 678", "Urquiza 999",
    ]

    print(f"  reclamos: insertando {len(RECLAMOS_DEMO)} registros demo...")
    for i, (estado, prioridad, descripcion) in enumerate(RECLAMOS_DEMO):
        ciudadano = ciudadanos[i % len(ciudadanos)]
        tipo = tipos[i % len(tipos)]
        id_area = tipo.id_area or id_area_default
        dias_atras = random.randint(0, 30)
        fecha_ingreso = base_date + timedelta(days=dias_atras)
        domicilio = domicilios[i]

        r = await db.execute(text("""
            INSERT INTO reclamos
                (id_ciudadano, id_tipo_reclamo, id_area, descripcion, domicilio_reclamo,
                 prioridad, estado, activo, fecha_alta, fecha_modificacion, id_usuario_alta)
            VALUES
                (:id_cit, :id_tipo, :id_area, :desc, :domicilio,
                 :prioridad, :estado, TRUE, :fecha_alta, :fecha_alta, :uid)
            RETURNING id_reclamo
        """), {
            "id_cit": ciudadano.id_ciudadano,
            "id_tipo": tipo.id_tipo_reclamo,
            "id_area": id_area,
            "desc": descripcion,
            "domicilio": domicilio,
            "prioridad": prioridad,
            "estado": estado,
            "fecha_alta": fecha_ingreso,
            "uid": ID_USUARIO_SEED,
        })
        row = r.fetchone()
        id_reclamo = row[0]

        # Actualizar nro_reclamo (el trigger lo hace solo pero forzamos por si acaso)
        await db.execute(text("""
            UPDATE reclamos SET nro_reclamo = :nro WHERE id_reclamo = :id AND nro_reclamo IS NULL
        """), {"nro": f"REC-2026-{id_reclamo:06d}", "id": id_reclamo})

        # Insertar al menos una entrada en historial
        await db.execute(text("""
            INSERT INTO reclamo_historial
                (id_reclamo, accion, estado_anterior, estado_nuevo, nota, fecha_alta, id_usuario_alta)
            VALUES (:id_r, 'Ingresado', NULL, 'Ingresado', 'Reclamo registrado', :fecha, :uid)
        """), {"id_r": id_reclamo, "fecha": fecha_ingreso, "uid": ID_USUARIO_SEED})

        # Si está en gestión/resuelto/cerrado, agregar más historial
        if estado in ("En revisión", "En gestión", "Resuelto", "Cerrado"):
            fecha2 = fecha_ingreso + timedelta(days=1)
            await db.execute(text("""
                INSERT INTO reclamo_historial
                    (id_reclamo, accion, estado_anterior, estado_nuevo, nota, fecha_alta, id_usuario_alta)
                VALUES (:id_r, :accion, 'Ingresado', :estado, :nota, :fecha, :uid)
            """), {
                "id_r": id_reclamo, "accion": f"Derivado a {tipo.nombre[:50]}",
                "estado": estado, "nota": "Asignado para gestión",
                "fecha": fecha2, "uid": ID_USUARIO_SEED
            })

        if estado in ("Resuelto", "Cerrado"):
            fecha3 = fecha_ingreso + timedelta(days=random.randint(3, 10))
            await db.execute(text("""
                INSERT INTO reclamo_historial
                    (id_reclamo, accion, estado_anterior, estado_nuevo, nota, fecha_alta, id_usuario_alta)
                VALUES (:id_r, 'Resuelto', 'En gestión', :estado, :nota, :fecha, :uid)
            """), {
                "id_r": id_reclamo, "estado": estado,
                "nota": "Solución implementada y verificada.",
                "fecha": fecha3, "uid": ID_USUARIO_SEED
            })

    await db.commit()
    total = await _count(db, "reclamos")
    print(f"  reclamos: {total} registros en total")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

async def main():
    print("\n=== ZARIS - Seed Inicial ===")
    print(f"Base de datos: {DATABASE_URL[:60]}...")

    async with AsyncSessionLocal() as db:
        # Verificar usuario seed
        r = await db.execute(text("SELECT id_usuario FROM usuarios WHERE id_usuario = :id"), {"id": ID_USUARIO_SEED})
        if not r.fetchone():
            print(f"ERROR: No existe usuario con id_usuario={ID_USUARIO_SEED}. Ejecutar seed_auth.py primero.")
            sys.exit(1)

        print("\n--- Paso 1: Cargos ---")
        await seed_cargos(db)

        print("\n--- Paso 2: Areas (Secretarias) ---")
        areas_map = await seed_areas(db)

        print("\n--- Paso 3: Subareas ---")
        await seed_subareas(db, areas_map)

        print("\n--- Paso 4: Tipos de reclamo ---")
        await seed_tipo_reclamo(db, areas_map)

        print("\n--- Paso 5: Ciudadanos ---")
        await seed_ciudadanos(db)

        print("\n--- Paso 6: Reclamos demo ---")
        await seed_reclamos(db, areas_map)

    print("\n=== Seed completado ===")


if __name__ == "__main__":
    asyncio.run(main())
