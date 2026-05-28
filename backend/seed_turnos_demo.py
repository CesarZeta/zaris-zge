"""
Seed demo de Turnos (replanteado mig 71: prestaciones con recurso embebido).

Siembra lo necesario para demostrar el modelo de PRESTACIONES:
  - Disponibilidad horaria de varios agentes (L-V 08-16).
  - Un lugar de atencion ATENDIDO (capacidad = union de sus agentes vinculados).
  - Un lugar de atencion DESATENDIDO (horario propio).
  - Prestaciones de ejemplo con recurso fijo (agente o espacio) y clase
    (atencion | reserva_espacio). El recurso se resuelve por nombre (§24).
  - Soft-delete de los tipos viejos sin recurso (las 3-4 filas planas previas a
    la mig 71 quedan invalidas porque no tienen recurso; se desactivan).
  - Turnos demo contra agente y contra lugar, repartidos en varios ciudadanos,
    incluyendo al ciudadano modelo (Juan Perez, id 1) para la vista 360. El
    recurso del turno sale de la prestacion elegida.

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

LUGAR_ATENDIDO = "Sala Municipal de Odontologia"
LUGAR_DESATENDIDO = "Salon de Usos Multiples"


def proximo_dia_habil(desde: date, offset_dias: int = 0) -> date:
    d = desde
    saltos = 0
    while True:
        if d.weekday() < 5:  # lun-vie
            if saltos == offset_dias:
                return d
            saltos += 1
        d += timedelta(days=1)


def _t(hhmm: str) -> time:
    h, m = hhmm.split(":")
    return time(int(h), int(m))


async def asegurar_disponibilidad(db, tipo_recurso: str, id_recurso: int, hi: str, hf: str) -> None:
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


async def asegurar_prestacion(db, nombre: str, clase: str, tipo_recurso: str,
                              id_recurso: int, dur_min: int, descripcion: str) -> int:
    """Crea (o reactiva con recurso correcto) una prestacion por nombre. Idempotente."""
    row = (await db.execute(text("""
        SELECT id_tipo_prestacion FROM tipo_prestacion WHERE LOWER(nombre) = LOWER(:n) LIMIT 1
    """), {"n": nombre})).first()
    ia = id_recurso if tipo_recurso == "agente" else None
    ie = id_recurso if tipo_recurso == "espacio" else None
    if row:
        pid = int(row[0])
        await db.execute(text("""
            UPDATE tipo_prestacion SET
                descripcion = :d, clase = :c, duracion_min = :dur,
                tipo_recurso = :tr, id_agente = :ia, id_espacio = :ie,
                activo = TRUE, fecha_modificacion = NOW()
            WHERE id_tipo_prestacion = :id
        """), {"d": descripcion, "c": clase, "dur": dur_min, "tr": tipo_recurso,
               "ia": ia, "ie": ie, "id": pid})
        return pid
    new_id = await db.scalar(text("""
        INSERT INTO tipo_prestacion (nombre, descripcion, clase, duracion_min, tipo_recurso,
                                     id_agente, id_espacio, activo, id_municipio, fecha_alta, fecha_modificacion)
        VALUES (:n, :d, :c, :dur, :tr, :ia, :ie, TRUE, :m, NOW(), NOW())
        RETURNING id_tipo_prestacion
    """), {"n": nombre, "d": descripcion, "c": clase, "dur": dur_min, "tr": tipo_recurso,
           "ia": ia, "ie": ie, "m": ID_MUNICIPIO})
    return int(new_id)


async def crear_turno_demo(db, id_ciudadano: int, id_tipo_prestacion: int,
                           tipo_recurso: str, id_recurso: int, dur_min: int,
                           fecha: date, hora_inicio: time) -> bool:
    """Crea un turno demo + ocupacion espejo (recurso copiado de la prestacion)
    si el ciudadano no tiene ya un turno no-cancelado ese dia."""
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
        INSERT INTO turnos (id_ciudadano, id_agente, id_espacio, id_tipo_prestacion, id_ocupacion,
                            fecha, hora_inicio, hora_fin, estado, observaciones, origen,
                            id_municipio, fecha_alta, fecha_modificacion)
        VALUES (:ic, :ia, :ie, :itp, :iocup, :f, :hi, :hf, 'reservado', 'Turno demo', 'backoffice',
                :m, NOW(), NOW())
    """), {
        "ic": id_ciudadano,
        "ia": id_recurso if tipo_recurso == "agente" else None,
        "ie": id_recurso if tipo_recurso == "espacio" else None,
        "itp": id_tipo_prestacion, "iocup": id_ocup,
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
        for ia in agentes[:2]:
            await vincular_agente(db, id_atendido, ia)
        print(f"Lugar atendido id={id_atendido} (Odontologia) con agentes {agentes[:2]}")

        id_desatendido = await asegurar_espacio(db, LUGAR_DESATENDIDO, False, "Av. Mitre 250")
        await asegurar_disponibilidad(db, "espacio", id_desatendido, "09:00", "15:00")
        print(f"Lugar desatendido id={id_desatendido} (SUM) con horario propio")

        # --- 3) Soft-delete de tipos viejos sin recurso (planos pre-mig71) ----
        # El CHECK ck_tipo_prestacion_recurso (NOT VALID) igual se evalua al
        # tocar la fila, asi que al desactivarlas hay que dejarlas cumpliendo:
        # les asignamos un recurso placeholder (agente[0]) y las marcamos
        # inactivas en el mismo UPDATE.
        res = await db.execute(text("""
            UPDATE tipo_prestacion
            SET activo = FALSE, tipo_recurso = 'agente', id_agente = :ph,
                fecha_modificacion = NOW()
            WHERE activo = TRUE AND id_agente IS NULL AND id_espacio IS NULL
        """), {"ph": agentes[0]})
        if res.rowcount:
            print(f"Tipos viejos sin recurso desactivados: {res.rowcount}")

        # --- 4) Prestaciones de ejemplo con recurso real ---------------------
        p_odonto_ag = await asegurar_prestacion(
            db, "Atencion medica - Odontologia", "atencion", "agente", agentes[0], 30,
            "Consulta odontologica con profesional asignado")
        p_clinica = await asegurar_prestacion(
            db, "Atencion medica - Clinica general", "atencion", "agente", agentes[1], 30,
            "Consulta clinica general")
        p_odonto_sala = await asegurar_prestacion(
            db, "Atencion - Sala de Odontologia", "atencion", "espacio", id_atendido, 45,
            "Atencion odontologica en la sala municipal (varios profesionales)")
        p_sum = await asegurar_prestacion(
            db, "Reserva - Salon de Usos Multiples", "reserva_espacio", "espacio", id_desatendido, 60,
            "Reserva del salon para actividades comunitarias")
        prestaciones = {
            "odonto_ag": (p_odonto_ag, "agente", agentes[0], 30),
            "clinica": (p_clinica, "agente", agentes[1], 30),
            "odonto_sala": (p_odonto_sala, "espacio", id_atendido, 45),
            "sum": (p_sum, "espacio", id_desatendido, 60),
        }
        print(f"Prestaciones aseguradas: {[v[0] for v in prestaciones.values()]}")

        # --- 5) Ciudadanos ----------------------------------------------------
        otros = [int(r[0]) for r in (await db.execute(text("""
            SELECT id_ciudadano FROM ciudadanos WHERE activo = TRUE AND id_ciudadano <> :m
            ORDER BY id_ciudadano LIMIT 3
        """), {"m": CIUDADANO_MODELO})).all()]
        ciudadanos = [CIUDADANO_MODELO] + otros

        # --- 6) Limpiar turnos demo viejos (apuntaban a tipos planos) ---------
        # Soft-delete de turnos demo previos + sus ocupaciones espejo, para
        # recrearlos contra las prestaciones nuevas sin duplicar por dia.
        await db.execute(text("""
            UPDATE ocupaciones SET activo = FALSE, fecha_modificacion = NOW()
            WHERE activo = TRUE AND tipo = 'turno' AND id_ocupacion IN (
                SELECT id_ocupacion FROM turnos
                WHERE observaciones = 'Turno demo' AND id_ocupacion IS NOT NULL
            )
        """))
        res_t = await db.execute(text("""
            UPDATE turnos SET activo = FALSE, estado = 'cancelado', fecha_modificacion = NOW()
            WHERE activo = TRUE AND observaciones = 'Turno demo'
        """))
        if res_t.rowcount:
            print(f"Turnos demo viejos desactivados: {res_t.rowcount}")

        # --- 7) Turnos demo: eligiendo prestacion (recurso sale de ella) ------
        hoy = date.today()
        # (ciudadano, clave_prestacion, offset_dia_habil, hora)
        plan = [
            (ciudadanos[0], "odonto_ag",   0, time(9, 0)),    # modelo -> odontologia (agente)
            (ciudadanos[0], "odonto_sala", 1, time(10, 0)),   # modelo -> sala odonto (espacio)
            (ciudadanos[1] if len(ciudadanos) > 1 else ciudadanos[0], "clinica", 0, time(11, 0)),
            (ciudadanos[1] if len(ciudadanos) > 1 else ciudadanos[0], "sum",     2, time(9, 0)),
            (ciudadanos[2] if len(ciudadanos) > 2 else ciudadanos[0], "odonto_sala", 0, time(12, 0)),
            (ciudadanos[2] if len(ciudadanos) > 2 else ciudadanos[0], "clinica", 1, time(13, 0)),
            (ciudadanos[3] if len(ciudadanos) > 3 else ciudadanos[0], "sum",     3, time(10, 0)),
        ]
        creados = 0
        for (ic, clave, off, hi) in plan:
            pid, tr, ir, dur = prestaciones[clave]
            f = proximo_dia_habil(hoy, off)
            if await crear_turno_demo(db, ic, pid, tr, ir, dur, f, hi):
                creados += 1
        print(f"Turnos demo creados: {creados} (sobre {len(plan)} planeados; el resto ya existian)")

        await db.commit()
    print("OK seed_turnos_demo")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm-prod", action="store_true")
    args = ap.parse_args()
    asyncio.run(main(args.confirm_prod))
