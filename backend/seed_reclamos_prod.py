"""
seed_reclamos_prod.py — Inserta 20 reclamos demo en prod si la tabla está vacía.
Detecta el constraint de estado vigente y usa los valores correctos.
"""
import asyncio
import os
import random
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:145236@127.0.0.1:5432/zaris_dev"
)
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Estados con y sin tilde — se auto-detecta cuál acepta el constraint
ESTADOS_CON_TILDE    = ["Ingresado", "En revisión", "En gestión", "Resuelto", "Rechazado", "Cerrado"]
ESTADOS_SIN_TILDE    = ["Ingresado", "En revision", "En gestion", "Resuelto", "Rechazado", "Cerrado"]

RECLAMOS_DEMO = [
    ("En gestion",   "Alta",  "Bache profundo en calzada frente al 1240, peligroso para vehiculos y peatones."),
    ("Ingresado",    "Media", "Tres luminarias apagadas en el bloque entre Mitre y Belgrano desde las 20hs."),
    ("En revision",  "Alta",  "Paciente cronica no puede obtener turno con especialista hace tres semanas."),
    ("Resuelto",     "Alta",  "Ciudadano con cert. discapacidad solicita subsidio de transporte rechazado por error."),
    ("Resuelto",     "Alta",  "Arbol caido sobre vereda bloqueando paso tras tormenta del 25/04, riesgo electrico."),
    ("En revision",  "Baja",  "Renovacion de licencia de conducir solicitada hace 45 dias sin respuesta."),
    ("Cerrado",      "Media", "Hace dos semanas no pasa el camion recolector. Bolsas acumuladas en vereda."),
    ("Ingresado",    "Alta",  "Falta de materiales en obra de centro comunitario Norte, paralizada hace 3 dias."),
    ("En gestion",   "Media", "Semaforo en esquina de Av. Maipu y Tucuman sin funcionar hace 4 dias."),
    ("Ingresado",    "Baja",  "Solicitud de poda de arbol en vereda que obstruye la visibilidad."),
    ("Resuelto",     "Media", "Perdida de agua en la via publica frente al 578, calle anegada permanentemente."),
    ("En gestion",   "Alta",  "Perro abandonado en parque Municipal agresivo, requiere intervencion urgente."),
    ("En revision",  "Alta",  "Ruidos molestos de obra en horario nocturno, incumplimiento ordenanza."),
    ("Ingresado",    "Media", "Contenedor de residuos volcado en Av. del Libertador obstruye la calzada."),
    ("Resuelto",     "Baja",  "Tramite de habilitacion comercial sin respuesta despues de 60 dias habiles."),
    ("Cerrado",      "Alta",  "Inundacion de sotano por desborde de pluvial en tormenta del 10/04."),
    ("En gestion",   "Media", "Pintada de graffitis en monumento historico de la plaza central."),
    ("Ingresado",    "Alta",  "Desconexion irregular del servicio de alumbrado en B Residencial Norte."),
    ("En revision",  "Media", "Vehiculo abandonado hace mas de 30 dias obstruye estacionamiento en Calle 9."),
    ("Resuelto",     "Baja",  "Solicitud de instalacion de nuevo contenedor de reciclado en Barrio Sur."),
]

DOMICILIOS = [
    "Av. San Martin 1240", "Calle 9 de Julio 456", "Centro de Salud No 3",
    "Bv. Illia 890", "Laprida 234 esq. Paso", "Direccion de Transito",
    "Rivadavia 567 B Centro", "Hospital Municipal", "Av. Maipu y Tucuman",
    "Parque Municipal", "Av. del Libertador 1500", "Calle Mitre 890",
    "B Residencial Norte", "Plaza Central", "Calle 9 esq. Rivadavia",
    "Av. Colon 2345", "San Lorenzo 123", "Belgrano 450",
    "Lavalle 678", "Urquiza 999",
]


async def detectar_estados(db: AsyncSession) -> list:
    """Prueba cuál set de estados acepta el constraint."""
    # Primero intentar con tilde
    for estados in [ESTADOS_CON_TILDE, ESTADOS_SIN_TILDE]:
        try:
            await db.execute(text("""
                INSERT INTO reclamos
                    (id_ciudadano, id_tipo_reclamo, id_area, descripcion, domicilio_reclamo,
                     prioridad, estado, activo, fecha_alta, fecha_modificacion, id_usuario_alta)
                SELECT 1, 1, 1, 'TEST', 'TEST', 'Media', :estado, FALSE, NOW(), NOW(), 1
                WHERE FALSE
            """), {"estado": estados[0]})
            # Si llegó aquí sin error, estos son los estados válidos
            print(f"  Usando estados: {estados[:3]}...")
            return estados
        except Exception:
            await db.rollback()
            continue
    # Fallback: usar sin tilde
    return ESTADOS_SIN_TILDE


async def main():
    print("=== seed_reclamos_prod ===")
    async with AsyncSessionLocal() as db:
        # Verificar reclamos existentes
        n = (await db.execute(text("SELECT COUNT(*) FROM reclamos"))).scalar()
        if n > 0:
            print(f"reclamos: ya tiene {n} registros, omitiendo")
            return

        # Obtener ciudadanos
        r = await db.execute(text("SELECT id_ciudadano FROM ciudadanos WHERE activo=TRUE ORDER BY id_ciudadano LIMIT 20"))
        ciudadanos = [row[0] for row in r.fetchall()]
        if not ciudadanos:
            print("ERROR: no hay ciudadanos en la base. Ejecutar seed_incremental primero.")
            return
        print(f"Ciudadanos disponibles: {len(ciudadanos)}")

        # Obtener tipos de reclamo
        r = await db.execute(text("SELECT id_tipo_reclamo, id_area FROM tipo_reclamo WHERE activo=TRUE ORDER BY id_tipo_reclamo LIMIT 50"))
        tipos = r.fetchall()
        if not tipos:
            print("ERROR: no hay tipos de reclamo. Ejecutar seed_incremental primero.")
            return
        print(f"Tipos disponibles: {len(tipos)}")

        # Detectar qué estados acepta el constraint
        estados = await detectar_estados(db)

        # Mapear estados de los datos demo a los válidos
        def mapear_estado(e):
            if "gestion" in e.lower() or "gestión" in e.lower():
                return next(s for s in estados if "gesti" in s.lower())
            if "revision" in e.lower() or "revisión" in e.lower():
                return next(s for s in estados if "revisi" in s.lower())
            return e

        random.seed(42)
        base_date = datetime(2026, 4, 3)
        inserted = 0

        for i, (estado_raw, prioridad, descripcion) in enumerate(RECLAMOS_DEMO):
            id_cit = ciudadanos[i % len(ciudadanos)]
            tipo = tipos[i % len(tipos)]
            id_area = tipo[1]
            dias = random.randint(0, 30)
            fecha = base_date + timedelta(days=dias)
            domicilio = DOMICILIOS[i]
            estado = mapear_estado(estado_raw)

            try:
                r2 = await db.execute(text("""
                    INSERT INTO reclamos
                        (id_ciudadano, id_tipo_reclamo, id_area, descripcion, domicilio_reclamo,
                         prioridad, estado, activo, fecha_alta, fecha_modificacion, id_usuario_alta)
                    VALUES
                        (:id_cit, :id_tipo, :id_area, :desc, :dom,
                         :prio, :estado, TRUE, :fecha, :fecha, 1)
                    RETURNING id_reclamo
                """), {
                    "id_cit": id_cit, "id_tipo": tipo[0], "id_area": id_area,
                    "desc": descripcion, "dom": domicilio,
                    "prio": prioridad, "estado": estado, "fecha": fecha,
                })
                row = r2.fetchone()
                id_r = row[0]

                await db.execute(text("""
                    UPDATE reclamos SET nro_reclamo = :nro WHERE id_reclamo = :id AND nro_reclamo IS NULL
                """), {"nro": f"REC-2026-{id_r:06d}", "id": id_r})

                await db.execute(text("""
                    INSERT INTO reclamo_historial
                        (id_reclamo, accion, estado_anterior, estado_nuevo, nota, fecha_alta, id_usuario_alta)
                    VALUES (:id_r, 'Ingresado', NULL, 'Ingresado', 'Reclamo registrado', :fecha, 1)
                """), {"id_r": id_r, "fecha": fecha})

                inserted += 1
            except Exception as e:
                print(f"  ERROR en reclamo {i+1}: {e}")
                await db.rollback()
                continue

        await db.commit()
        total = (await db.execute(text("SELECT COUNT(*) FROM reclamos"))).scalar()
        print(f"reclamos: +{inserted} insertados, total={total}")

    print("=== Completado ===")


if __name__ == "__main__":
    asyncio.run(main())
