"""
seed_agenda.py - Aplica migraciones 30-34 (sub-fase 1.A del modulo Agenda) y
siembra datos demo idempotentes en zaris_dev.

Que hace:
  1) Aplica migraciones SQL en orden: 30 -> 31 -> 32 -> 33 -> 34.
  2) Verifica que existan los maestros: agentes, equipos, ciudadanos, ordenes_trabajo, subarea.
  3) Crea hasta 2 agentes demo adicionales si hay < 4 agentes activos en municipio 1.
  4) Crea 1 equipo demo + vincula 2 agentes via equipo_agentes (si no hay equipos).
  5) Crea 1 evento "Vacunacion antigripal" para el lunes proximo, 9:00-12:00.
  6) Crea 2 reservas (los 2 primeros ciudadanos activos).
  7) Crea 3 ocupaciones de prueba (1 ot, 1 evento, 1 turno).
  8) Reporta COUNT(*) por tabla nueva y un OK/ERROR final.

Uso (desde la raiz del repo, con el venv del backend activado):
    cd backend
    $env:ENV_FILE=".env.local"; python seed_agenda.py

Reglas: AsyncSessionLocal + text() explicito; sin acentos en codigo ni logs.
"""
import asyncio
import os
import sys
from pathlib import Path
from datetime import date, time, timedelta

# UTF-8 stdout en Windows para no romper si por error sale algo no-ASCII
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:145236@127.0.0.1:5432/zaris_dev",
)
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

MIG_DIR = Path(__file__).parent / "migrations"
MIG_FILES = [
    "30_agenda_municipios_y_tipo_reclamo.sql",
    "31_agenda_catalogos.sql",
    "32_agenda_eventos_y_reservas.sql",
    "33_agenda_ocupaciones.sql",
    "34_agenda_auditoria_y_conflictos.sql",
]

NUEVAS_TABLAS = [
    "municipios",
    "estado_evento",
    "estado_reserva",
    "eventos",
    "evento_encargados",
    "evento_reservas",
    "ocupaciones",
    "conflictos_log",
    "agenda_audit_log",
]


def proximo_lunes(hoy: date | None = None) -> date:
    """Lunes de la proxima semana respecto a hoy (si hoy es lunes, devuelve dentro de 7 dias)."""
    h = hoy or date.today()
    delta = (7 - h.weekday()) % 7
    if delta == 0:
        delta = 7
    return h + timedelta(days=delta)


async def aplicar_migraciones(engine) -> None:
    """asyncpg no acepta multi-statement vía sentencias preparadas, pero su
    conexion cruda si soporta scripts via `.execute(sql)` no-preparado. Usamos
    raw_connection() para correr los archivos completos tal cual estan escritos."""
    print("[1/4] Aplicando migraciones SQL...")
    for fname in MIG_FILES:
        fpath = MIG_DIR / fname
        if not fpath.exists():
            raise FileNotFoundError(f"No existe la migracion {fpath}")
        sql = fpath.read_text(encoding="utf-8")
        async with engine.connect() as conn:
            raw = await conn.get_raw_connection()
            # raw.driver_connection es la conexion asyncpg real
            asyncpg_conn = raw.driver_connection
            await asyncpg_conn.execute(sql)
        print(f"      OK  {fname}")


async def verificar_maestros(session: AsyncSession) -> dict[str, int]:
    print("[2/4] Verificando maestros requeridos...")
    counts = {}
    for tabla in ["agentes", "equipos", "ciudadanos", "ordenes_trabajo", "subarea"]:
        n = await session.scalar(text(f"SELECT COUNT(*) FROM {tabla}"))
        counts[tabla] = int(n or 0)
        marca = "OK" if counts[tabla] > 0 else "VACIO"
        print(f"      {marca:5s} {tabla:18s} {counts[tabla]:>5d} filas")
    if counts["ciudadanos"] < 2:
        raise RuntimeError("Faltan al menos 2 ciudadanos para crear reservas demo.")
    if counts["subarea"] < 1:
        raise RuntimeError("Falta al menos 1 subarea para asignar al evento demo.")
    return counts


async def seed_agentes_demo(session: AsyncSession) -> list[int]:
    """Devuelve la lista de id_agente activos en municipio 1 (o sin municipio).
    Si hay menos de 4, agrega hasta llegar a 4 con datos coherentes."""
    print("[3/4] Seeding demo...")
    rows = await session.execute(text(
        "SELECT id_agente FROM agentes "
        "WHERE activo=TRUE AND (id_municipio IS NULL OR id_municipio = 1) "
        "ORDER BY id_agente"
    ))
    agentes_existentes = [r[0] for r in rows.fetchall()]
    faltan = max(0, 4 - len(agentes_existentes))
    if faltan > 0:
        # Subarea cualquiera activa para asignarle
        id_subarea = await session.scalar(text(
            "SELECT id_subarea FROM subarea WHERE activo=TRUE ORDER BY id_subarea LIMIT 1"
        ))
        demos = [
            ("Carlos", "Demo",  "cdemo@municipio.gob.ar",  "LEG-D01"),
            ("Sofia",  "Demo",  "sdemo@municipio.gob.ar",  "LEG-D02"),
            ("Pedro",  "Demo",  "pdemo@municipio.gob.ar",  "LEG-D03"),
            ("Ana",    "Demo",  "ademo@municipio.gob.ar",  "LEG-D04"),
        ]
        for nombre, apellido, email, legajo in demos[:faltan]:
            ya = await session.scalar(text(
                "SELECT id_agente FROM agentes WHERE LOWER(email)=LOWER(:e)"
            ), {"e": email})
            if ya:
                # Reactivar si estaba inactivo
                await session.execute(text(
                    "UPDATE agentes SET activo=TRUE, id_municipio=1, id_subarea=COALESCE(id_subarea,:sa), "
                    "fecha_modificacion=NOW() WHERE id_agente=:id"
                ), {"sa": id_subarea, "id": ya})
                agentes_existentes.append(int(ya))
                print(f"      OK  agente reactivado {email}")
                continue
            new_id = await session.scalar(text(
                "INSERT INTO agentes (nombre, apellido, email, legajo, id_municipio, id_subarea, "
                "es_auditor, activo, fecha_alta, fecha_modificacion) "
                "VALUES (:n,:a,:e,:l,1,:sa,FALSE,TRUE,NOW(),NOW()) RETURNING id_agente"
            ), {"n": nombre, "a": apellido, "e": email, "l": legajo, "sa": id_subarea})
            agentes_existentes.append(int(new_id))
            print(f"      OK  agente creado    {email} (id={new_id})")
        await session.commit()
    print(f"      Agentes municipio 1 disponibles: {agentes_existentes}")
    return agentes_existentes


async def seed_equipo_demo(session: AsyncSession, agentes: list[int]) -> int:
    """Garantiza la existencia de 'Equipo Demo Mantenimiento' con 2 agentes via equipo_agentes."""
    if len(agentes) < 2:
        raise RuntimeError("Se requieren al menos 2 agentes para vincular al equipo demo.")
    nombre = "Equipo Demo Mantenimiento"
    id_eq = await session.scalar(text(
        "SELECT id_equipo FROM equipos WHERE LOWER(nombre)=LOWER(:n)"
    ), {"n": nombre})
    if not id_eq:
        id_subarea = await session.scalar(text(
            "SELECT id_subarea FROM subarea WHERE activo=TRUE ORDER BY id_subarea LIMIT 1"
        ))
        id_eq = await session.scalar(text(
            "INSERT INTO equipos (nombre, id_municipio, id_subarea, activo, fecha_alta, fecha_modificacion) "
            "VALUES (:n,1,:sa,TRUE,NOW(),NOW()) RETURNING id_equipo"
        ), {"n": nombre, "sa": id_subarea})
        print(f"      OK  equipo creado  '{nombre}' (id={id_eq})")
    else:
        await session.execute(text(
            "UPDATE equipos SET activo=TRUE, fecha_modificacion=NOW() WHERE id_equipo=:id"
        ), {"id": id_eq})
        print(f"      OK  equipo existente '{nombre}' (id={id_eq})")
    # Vincular 2 primeros agentes via equipo_agentes (idempotente)
    for id_ag in agentes[:2]:
        existe = await session.scalar(text(
            "SELECT id_equipo_agente FROM equipo_agentes WHERE id_equipo=:e AND id_agente=:a"
        ), {"e": id_eq, "a": id_ag})
        if existe:
            await session.execute(text(
                "UPDATE equipo_agentes SET activo=TRUE, fecha_modificacion=NOW() "
                "WHERE id_equipo_agente=:i"
            ), {"i": existe})
        else:
            await session.execute(text(
                "INSERT INTO equipo_agentes (id_equipo, id_agente, id_municipio, activo, fecha_alta, fecha_modificacion) "
                "VALUES (:e,:a,1,TRUE,NOW(),NOW())"
            ), {"e": id_eq, "a": id_ag})
    await session.commit()
    print(f"      OK  vinculados 2 agentes al equipo {id_eq}")
    return int(id_eq)


async def seed_evento_demo(session: AsyncSession) -> int:
    """Crea (o reutiliza) un evento 'Vacunacion antigripal' para el lunes proximo."""
    nombre = "Vacunacion antigripal"
    fecha = proximo_lunes()
    id_estado_activo = await session.scalar(text(
        "SELECT id_estado_evento FROM estado_evento WHERE codigo='activo'"
    ))
    if not id_estado_activo:
        raise RuntimeError("Falta seed de estado_evento (codigo='activo').")
    id_subarea = await session.scalar(text(
        "SELECT id_subarea FROM subarea WHERE activo=TRUE ORDER BY id_subarea LIMIT 1"
    ))
    existe = await session.scalar(text(
        "SELECT id_evento FROM eventos WHERE LOWER(nombre)=LOWER(:n) AND fecha=:f"
    ), {"n": nombre, "f": fecha})
    if existe:
        print(f"      OK  evento existente '{nombre}' fecha={fecha} (id={existe})")
        return int(existe)
    id_ev = await session.scalar(text(
        "INSERT INTO eventos (nombre, descripcion, id_subarea, fecha, hora_inicio, hora_fin, "
        "capacidad_ciudadanos, cantidad_encargados, tipo_qr, admite_autoservicio, "
        "id_estado_evento, id_municipio, activo) "
        "VALUES (:n,:d,:sa,:f,:hi,:hf,20,1,'nominal',TRUE,:es,1,TRUE) RETURNING id_evento"
    ), {
        "n": nombre,
        "d": "Campania de vacunacion antigripal - demo del modulo Agenda.",
        "sa": id_subarea,
        "f": fecha,
        "hi": time(9, 0),
        "hf": time(12, 0),
        "es": id_estado_activo,
    })
    await session.commit()
    print(f"      OK  evento creado    '{nombre}' fecha={fecha} (id={id_ev})")
    return int(id_ev)


async def seed_reservas_demo(session: AsyncSession, id_evento: int) -> int:
    """Crea hasta 2 reservas para el evento (idempotente: skip si ya hay 2+)."""
    actuales = await session.scalar(text(
        "SELECT COUNT(*) FROM evento_reservas WHERE id_evento=:e AND activo=TRUE"
    ), {"e": id_evento})
    if (actuales or 0) >= 2:
        print(f"      OK  evento {id_evento} ya tiene {actuales} reservas")
        return int(actuales)
    id_estado_reservada = await session.scalar(text(
        "SELECT id_estado_reserva FROM estado_reserva WHERE codigo='reservada'"
    ))
    rows = await session.execute(text(
        "SELECT id_ciudadano FROM ciudadanos WHERE activo=TRUE ORDER BY id_ciudadano LIMIT 2"
    ))
    ciudadanos = [r[0] for r in rows.fetchall()]
    creadas = 0
    for cid in ciudadanos:
        ya = await session.scalar(text(
            "SELECT id_evento_reserva FROM evento_reservas "
            "WHERE id_evento=:e AND id_ciudadano=:c AND activo=TRUE"
        ), {"e": id_evento, "c": cid})
        if ya:
            continue
        await session.execute(text(
            "INSERT INTO evento_reservas (id_evento, id_ciudadano, id_estado_reserva, origen, "
            "qr_codigo, id_municipio, activo) "
            "VALUES (:e,:c,:es,'backoffice',:q,1,TRUE)"
        ), {"e": id_evento, "c": cid, "es": id_estado_reservada, "q": f"QR-EV{id_evento}-C{cid}"})
        creadas += 1
    await session.commit()
    print(f"      OK  reservas creadas: {creadas}")
    return creadas


async def seed_ocupaciones_demo(
    session: AsyncSession,
    agentes: list[int],
    id_equipo: int,
    id_evento: int,
) -> int:
    """Crea 3 ocupaciones de prueba: 1 ot (agente), 1 evento (equipo), 1 turno (agente)."""
    if len(agentes) < 1:
        raise RuntimeError("No hay agentes para ocupaciones demo.")
    # Para 'ot' necesitamos una OT existente (o crearemos una minima si la tabla esta vacia).
    id_ot = await session.scalar(text(
        "SELECT id_ot FROM ordenes_trabajo ORDER BY id_ot DESC LIMIT 1"
    ))
    if not id_ot:
        # No creamos OTs aqui porque tienen FKs duras (id_reclamo, id_supervisor_asigna).
        # Saltamos la ocupacion de tipo 'ot' si no hay OTs.
        print("      WARN  no hay OTs existentes - se omite ocupacion tipo='ot'")
    # Ciudadano para el turno
    id_cid = await session.scalar(text(
        "SELECT id_ciudadano FROM ciudadanos WHERE activo=TRUE ORDER BY id_ciudadano LIMIT 1"
    ))
    if not id_cid:
        raise RuntimeError("No hay ciudadanos activos para ocupacion tipo='turno'.")

    manana = date.today() + timedelta(days=1)
    fecha_evento = await session.scalar(text(
        "SELECT fecha FROM eventos WHERE id_evento=:e"
    ), {"e": id_evento})

    creadas = 0

    # (1) Ocupacion tipo 'ot' - solo si hay OT disponible
    if id_ot:
        ya = await session.scalar(text(
            "SELECT id_ocupacion FROM ocupaciones "
            "WHERE tipo='ot' AND tipo_recurso='agente' AND id_recurso=:r AND id_orden_trabajo=:ot"
        ), {"r": agentes[0], "ot": id_ot})
        if not ya:
            await session.execute(text(
                "INSERT INTO ocupaciones (tipo, tipo_recurso, id_recurso, fecha, hora_inicio, hora_fin, "
                "id_orden_trabajo, duracion_aplicada_min, motivo, id_municipio, activo) "
                "VALUES ('ot','agente',:r,:f,:hi,:hf,:ot,60,'OT demo - seed',1,TRUE)"
            ), {"r": agentes[0], "f": manana, "hi": time(10, 0), "hf": time(11, 0), "ot": id_ot})
            creadas += 1

    # (2) Ocupacion tipo 'evento' - sobre el equipo, fecha del evento, FK al evento
    ya = await session.scalar(text(
        "SELECT id_ocupacion FROM ocupaciones "
        "WHERE tipo='evento' AND tipo_recurso='equipo' AND id_recurso=:r AND id_evento=:e"
    ), {"r": id_equipo, "e": id_evento})
    if not ya:
        await session.execute(text(
            "INSERT INTO ocupaciones (tipo, tipo_recurso, id_recurso, fecha, hora_inicio, hora_fin, "
            "id_evento, rol_en_evento, id_municipio, activo) "
            "VALUES ('evento','equipo',:r,:f,:hi,:hf,:e,'encargado',1,TRUE)"
        ), {"r": id_equipo, "f": fecha_evento, "hi": time(9, 0), "hf": time(12, 0), "e": id_evento})
        creadas += 1

    # (3) Ocupacion tipo 'turno' - sobre un agente, fecha manana, FK al ciudadano
    ya = await session.scalar(text(
        "SELECT id_ocupacion FROM ocupaciones "
        "WHERE tipo='turno' AND tipo_recurso='agente' AND id_recurso=:r AND id_ciudadano=:c "
        "AND fecha=:f"
    ), {"r": agentes[0], "c": id_cid, "f": manana})
    if not ya:
        await session.execute(text(
            "INSERT INTO ocupaciones (tipo, tipo_recurso, id_recurso, fecha, hora_inicio, hora_fin, "
            "id_ciudadano, duracion_aplicada_min, motivo, id_municipio, activo) "
            "VALUES ('turno','agente',:r,:f,:hi,:hf,:c,30,'Turno demo - seed',1,TRUE)"
        ), {"r": agentes[0], "f": manana, "hi": time(14, 0), "hf": time(14, 30), "c": id_cid})
        creadas += 1

    await session.commit()
    print(f"      OK  ocupaciones creadas en esta corrida: {creadas}")
    return creadas


async def reporte_final(session: AsyncSession) -> None:
    print("[4/4] COUNTs por tabla nueva:")
    for t in NUEVAS_TABLAS:
        n = await session.scalar(text(f"SELECT COUNT(*) FROM {t}"))
        print(f"      {t:20s} {int(n or 0):>5d} filas")
    # tipo_reclamo: confirmar columnas nuevas
    cols = await session.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='tipo_reclamo' "
        "AND column_name IN ('duracion_estimada_min','asignacion_a')"
    ))
    cols_nombres = sorted([r[0] for r in cols.fetchall()])
    print(f"      tipo_reclamo: columnas nuevas presentes = {cols_nombres}")


async def main() -> int:
    print(f"DB: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")
    engine = create_async_engine(DATABASE_URL, echo=False, future=True)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        await aplicar_migraciones(engine)
        async with Session() as session:
            await verificar_maestros(session)
            agentes = await seed_agentes_demo(session)
            id_equipo = await seed_equipo_demo(session, agentes)
            id_evento = await seed_evento_demo(session)
            await seed_reservas_demo(session, id_evento)
            await seed_ocupaciones_demo(session, agentes, id_equipo, id_evento)
            await reporte_final(session)
        print()
        print("Fase 1.A completada sin errores")
        return 0
    except Exception as e:
        print()
        print(f"ERROR: {type(e).__name__}: {e}")
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
