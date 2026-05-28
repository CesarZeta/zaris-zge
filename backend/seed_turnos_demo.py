"""
Seed demo de Turnos + capacidad (disponibilidad de agentes, lugares de atencion
atendidos/desatendidos) + turnos demo. Idempotente.

Siembra lo necesario para demostrar:
  - Disponibilidad horaria de varios agentes (L-V 08-16).
  - Un lugar de atencion ATENDIDO (capacidad = union de sus agentes vinculados).
  - Un lugar de atencion DESATENDIDO (horario propio).
  - Turnos demo contra agente y contra lugar, repartidos en varios ciudadanos,
    incluyendo al ciudadano modelo (Juan Perez, id 1) para la vista 360.

Uso:
  Local: $env:ENV_FILE=".env.local"; python seed_turnos_demo.py
  Prod : $env:ENV_FILE=".env.prod";  python seed_turnos_demo.py --confirm-prod

No usar acentos en strings (consistente con el resto de scripts del repo).
"""
from __future__ import annotations

import argparse
import asyncio
import os
from datetime import date, datetime, time, timedelta

from sqlalchemy import text
from app.core.database import AsyncSessionLocal

ID_MUNICIPIO = 1
CIUDADANO_MODELO = 1  # Juan Perez, DNI 12345678
DIAS_LV = 31  # bitmask Lun-Vie (§27)

# Lugares demo (resueltos por nombre, idempotente).
LUGAR_ATENDIDO = "Mesa de Atencion Municipal"
LUGAR_DESATENDIDO = "Sala de Tramites Express"


def proximo_dia_habil(desde: date, offset_dias: int = 0) -> date:
    """Devuelve un dia habil (lun-vie) a partir de 'desde' saltando offset dias habiles."""
    d = desde
    saltos = 0
    while True:
        if d.weekday() < 5:  # lun-vie
            if saltos == offset_dias:
                return d
            saltos += 1
        d += timedelta(days=1)


def _t(hhmm: str) -> time:
    """'08:00' -> time(8,0). asyncpg requiere objeto time, no string (§5)."""
    h, m = hhmm.split(":")
    return time(int(h), int(m))


async def asegurar_disponibilidad(db, tipo_recurso: str, id_recurso: int, hi: str, hf: str) -> None:
    """Crea una fila de disponibilidad L-V si el recurso no tiene ninguna activa."""
    existe = await db.scalar(text("""
        SELECT 1 FROM disponibilidad_recurso
        WHERE tipo_recurso = :tr AND id_recurso = :ir AND activo = TRUE LIMIT 1
    """), {"tr": tipo_recurso, "ir": id_recurso})
    if existe:
        return
    await db.execute(text("""
        INSERT INTO disponibilidad_recurso
            (tipo_recurso, id_recurso, dias_semana, hora_inicio, hora_fin,
             etiqueta, activo, id_municipio, fecha_alta, fecha_modificacion)
        VALUES (:tr, :ir, :ds, :hi, :hf, 'Horario de atencion (demo)', TRUE, :m, NOW(), NOW())
    """), {"tr": tipo_recurso, "ir": id_recurso, "ds": DIAS_LV, "hi": _t(hi), "hf": _t(hf), "m": ID_MUNICIPIO})


async def asegurar_espacio(db, nombre: str, atendido: bool, direccion: str) -> int:
    row = (await db.execute(text("""
        SELECT id_espacio FROM espacios_agenda WHERE nombre = :n AND activo = TRUE LIMIT 1
    """), {"n": nombre})).first()
    if row:
        return int(row[0])
    new_id = await db.scalar(text("""
        INSERT INTO espacios_agenda (nombre, descripcion, direccion, capacidad_personas, atendido,
                                     activo, id_municipio, id_subarea, fecha_alta, fecha_modificacion)
        VALUES (:n, :d, :dir, 1, :at, TRUE, :m, NULL, NOW(), NOW())
        RETURNING id_espacio
    """), {"n": nombre, "d": f"Lugar de atencion demo ({'atendido' if atendido else 'desatendido'})",
           "dir": direccion, "at": atendido, "m": ID_MUNICIPIO})
    return int(new_id)


async def vincular_agente(db, id_espacio: int, id_agente: int) -> None:
    existe = await db.scalar(text("""
        SELECT 1 FROM espacio_agentes WHERE id_espacio = :e AND id_agente = :a AND activo = TRUE LIMIT 1
    """), {"e": id_espacio, "a": id_agente})
    if existe:
        return
    await db.execute(text("""
        INSERT INTO espacio_agentes (id_espacio, id_agente, activo, id_municipio, fecha_alta, fecha_modificacion)
        VALUES (:e, :a, TRUE, :m, NOW(), NOW())
    """), {"e": id_espacio, "a": id_agente, "m": ID_MUNICIPIO})


async def crear_turno_demo(db, id_ciudadano: int, tipo_recurso: str, id_recurso: int,
                           id_tipo_servicio: int, dur_min: int, fecha: date, hora_inicio: time) -> bool:
    """Crea un turno demo + ocupacion espejo si el ciudadano no tiene ya un turno
    no-cancelado ese dia (idempotencia razonable). Devuelve True si lo creo."""
    dup = await db.scalar(text("""
        SELECT 1 FROM turnos
        WHERE id_ciudadano = :ic AND fecha = :f AND activo = TRUE AND estado <> 'cancelado' LIMIT 1
    """), {"ic": id_ciudadano, "f": fecha})
    if dup:
        return False
    hora_fin = (datetime.combine(fecha, hora_inicio) + timedelta(minutes=dur_min)).time()
    id_ocup = await db.scalar(text("""
        INSERT INTO ocupaciones (tipo, tipo_recurso, id_recurso, fecha, hora_inicio, hora_fin,
                                 id_ciudadano, motivo, id_municipio, fecha_alta, fecha_modificacion)
        VALUES ('turno', :tr, :ir, :f, :hi, :hf, :ic, 'Turno (demo)', :m, NOW(), NOW())
        RETURNING id_ocupacion
    """), {"tr": tipo_recurso, "ir": id_recurso, "f": fecha, "hi": hora_inicio, "hf": hora_fin,
           "ic": id_ciudadano, "m": ID_MUNICIPIO})
    await db.execute(text("""
        INSERT INTO turnos (id_ciudadano, id_agente, id_espacio, id_tipo_servicio_turno, id_ocupacion,
                            fecha, hora_inicio, hora_fin, estado, observaciones, origen,
                            id_municipio, fecha_alta, fecha_modificacion)
        VALUES (:ic, :ia, :ie, :its, :iocup, :f, :hi, :hf, 'reservado', 'Turno demo', 'backoffice',
                :m, NOW(), NOW())
    """), {
        "ic": id_ciudadano,
        "ia": id_recurso if tipo_recurso == "agente" else None,
        "ie": id_recurso if tipo_recurso == "espacio" else None,
        "its": id_tipo_servicio, "iocup": id_ocup,
        "f": fecha, "hi": hora_inicio, "hf": hora_fin, "m": ID_MUNICIPIO,
    })
    return True


async def main(confirm_prod: bool) -> None:
    env = os.environ.get("ENV_FILE", "")
    es_prod = "prod" in env.lower()
    if es_prod and not confirm_prod:
        print("ENV apunta a prod pero falta --confirm-prod. Abortando.")
        return

    async with AsyncSessionLocal() as db:
        # --- 1) Agentes demo con disponibilidad L-V ---------------------------
        # Tomamos los primeros 4 agentes activos (id estable) y les aseguramos horario.
        agentes = [int(r[0]) for r in (await db.execute(text("""
            SELECT id_agente FROM agentes WHERE activo = TRUE ORDER BY id_agente LIMIT 4
        """))).all()]
        if len(agentes) < 2:
            print("No hay suficientes agentes activos. Abortando.")
            return
        for ia in agentes:
            await asegurar_disponibilidad(db, "agente", ia, "08:00", "16:00")
        print(f"Disponibilidad asegurada para agentes: {agentes}")

        # --- 2) Lugares de atencion ------------------------------------------
        id_atendido = await asegurar_espacio(db, LUGAR_ATENDIDO, True, "Av. Mitre 100")
        # Vinculamos 2 agentes al lugar atendido (su capacidad sale de ellos).
        for ia in agentes[:2]:
            await vincular_agente(db, id_atendido, ia)
        print(f"Lugar atendido id={id_atendido} con agentes {agentes[:2]}")

        id_desatendido = await asegurar_espacio(db, LUGAR_DESATENDIDO, False, "Av. Mitre 250")
        # Desatendido: horario propio del espacio.
        await asegurar_disponibilidad(db, "espacio", id_desatendido, "09:00", "15:00")
        print(f"Lugar desatendido id={id_desatendido} con horario propio")

        # --- 3) Tipo de servicio + ciudadanos --------------------------------
        tipo = (await db.execute(text("""
            SELECT id_tipo_servicio_turno, duracion_min FROM tipo_servicio_turno
            WHERE activo = TRUE ORDER BY id_tipo_servicio_turno LIMIT 1
        """))).first()
        if not tipo:
            print("No hay tipo_servicio_turno activo. Abortando turnos demo.")
            await db.commit()
            return
        id_tipo, dur = int(tipo[0]), int(tipo[1])

        # Ciudadanos: el modelo (id 1) + 3 mas distintos.
        otros = [int(r[0]) for r in (await db.execute(text("""
            SELECT id_ciudadano FROM ciudadanos WHERE activo = TRUE AND id_ciudadano <> :m
            ORDER BY id_ciudadano LIMIT 3
        """), {"m": CIUDADANO_MODELO})).all()]
        ciudadanos = [CIUDADANO_MODELO] + otros

        # --- 4) Turnos demo: mezcla agente / lugar, dias habiles proximos -----
        hoy = date.today()
        # Plan: (ciudadano, recurso_tipo, id_recurso, offset_dia_habil, hora)
        plan = [
            (ciudadanos[0], "agente",  agentes[0],     0, time(9, 0)),   # modelo -> agente
            (ciudadanos[0], "espacio", id_atendido,    1, time(10, 0)),  # modelo -> lugar atendido
            (ciudadanos[1], "agente",  agentes[1],     0, time(11, 0)),
            (ciudadanos[1], "espacio", id_desatendido, 2, time(9, 30)),
            (ciudadanos[2], "espacio", id_atendido,    0, time(12, 0)),
            (ciudadanos[2], "agente",  agentes[2] if len(agentes) > 2 else agentes[0], 1, time(13, 0)),
            (ciudadanos[3] if len(ciudadanos) > 3 else ciudadanos[1], "espacio", id_desatendido, 3, time(10, 30)),
        ]
        creados = 0
        for (ic, tr, ir, off, hi) in plan:
            f = proximo_dia_habil(hoy, off)
            if await crear_turno_demo(db, ic, tr, ir, id_tipo, dur, f, hi):
                creados += 1
        print(f"Turnos demo creados: {creados} (sobre {len(plan)} planeados; el resto ya existian)")

        await db.commit()
    print("OK seed_turnos_demo")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm-prod", action="store_true")
    args = ap.parse_args()
    asyncio.run(main(args.confirm_prod))
