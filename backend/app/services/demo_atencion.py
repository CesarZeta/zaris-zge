# -*- coding: utf-8 -*-
"""Generador de datos demo de ATENCION (turnos + colero + Guardia + eventos).

Hermano de demo_datos.py (reclamos), pedido por Cesar el 2026-09-19 para que el
tablero Datos -> Atencion (bi_atencion.py, proyecto ATENCION F6) tenga volumen:
  - MISMO usuario 'generador.demo' (inactivo) como id_usuario_alta de todo lo
    insertado -> identificar / borrar / migrar a un tenant = filtrar por el.
  - MISMOS vecinos demo (@vecinos-demo.zaris.com.ar) como ciudadanos de los
    turnos, reservas y denunciantes. Nunca ciudadanos reales.
  - MISMO endpoint (POST /api/v1/demo/poblar, body.modulos incluye 'atencion')
    y MISMO cron semanal (.github/workflows/demo-datos.yml).
  - Catalogos resueltos POR NOMBRE / CODIGO en runtime (prestaciones activas,
    Guardia por clave de config, estados por `codigo`, plantilla por `tipo`):
    los ids divergen entre local y prod (estado_evento 1/2/3 vs 5/6/7).

Que genera por dia del rango [desde, hasta] (+ `dias_futuro` hacia adelante
cuando el rango llega a hoy, para que la Mesa del dia y el colero tengan
turnos reservados):
  - TURNOS sobre cada prestacion activa, dentro de la disponibilidad EFECTIVA
    del recurso (feriados y novedades incluidos, via disponibilidad_efectiva_
    batch — la misma que valida la reserva real), sin pisar ocupaciones ni
    turnos existentes, ocupando un 35-65 % de los slots libres. Con su
    OCUPACION espejo en la grilla de Agenda (como crear_turno), origen
    backoffice/autoservicio, y para los dias ya pasados el desenlace:
    cumplido / ausente / cancelado, numero de colero (prefijo del espacio +
    correlativo diario, continuando el MAX existente), log turno_llamado
    (espera realista, re-llamados), turno_atencion si la prestacion registra
    atencion, y encuesta CSAT de turnos (plantilla tipo='turnos').
  - GUARDIA: eventos de Emergencias (tipo de salud/accidente, numerados por el
    trigger de la DB) cerrados como RESUELTO con su log, derivados a la Guardia
    (emergencia_atencion) y atendidos por los medicos vinculados al espacio
    Guardia (espacio_agentes). Si no hay Guardia configurada o no tiene
    medicos, se omite (queda en el resultado).
  - EVENTOS con reservas en los espacios con capacidad (Auditorio, Teatro...):
    asistio / reservada / cancelada, origen, QR nominal, estado finalizado si
    ya pasaron.

`avanzar_pendientes_atencion` (cron): resuelve los turnos demo ya vencidos que
siguen reservados, cierra derivaciones demo pendientes y finaliza eventos demo
pasados. Las encuestas demo (de reclamos Y de turnos) las madura
demo_datos.avanzar_pendientes (filtra por el usuario generador, no por origen).

REGLAS HEREDADAS de demo_datos.py: jamas crear encuesta_envio 'pendiente' (el
dispatcher mandaria mail); alcance SOLO municipio demo (pre IT-01); el
generador NO es idempotente — pero los turnos y eventos evitan colisiones
(slots ocupados, mismo espacio/hora), asi que repetir un rango agrega poco.
"""
from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import demo_datos
from app.services.agenda import disponibilidad_efectiva_batch
from app.services.guardia import espacio_guardia
from app.utils.fechas import TZ_MUNICIPIO, ahora_local, hoy_local

logger = logging.getLogger(__name__)

UTC = timezone.utc

# Fraccion de slots LIBRES que se reservan por recurso y dia.
OCUPACION = (0.35, 0.65)
ORIGENES = [("backoffice", 70), ("autoservicio", 30)]
# Desenlace de un turno cuyo horario ya paso.
DESENLACES = [("cumplido", 77), ("ausente", 11), ("cancelado", 12)]
# Espera real (minutos entre la hora del turno y el primer llamado): mezcla de
# "a tiempo" (incluye llamados antes de hora), demoras cortas, medias y largas.
ESPERA_TRAMOS = [((-4, 5), 55), ((5, 25), 30), ((25, 60), 12), ((60, 120), 3)]
# Derivaciones a la Guardia por dia (distribucion discreta, media ~1).
GUARDIA_POR_DIA = [(0, 35), (1, 40), (2, 18), (3, 7)]
# Eventos por mes (se escala por la fraccion de mes del rango).
EVENTOS_MENSUAL = (6, 10)
DIAS_FUTURO_DEFAULT = 7

INTERVENCIONES = [
    "Control clínico de rutina. Signos vitales dentro de parámetros normales.",
    "Consulta por cuadro de vías aéreas superiores. Se indica tratamiento sintomático.",
    "Control de presión arterial. Se ajusta medicación y se cita a control en 30 días.",
    "Control odontológico: limpieza, fluorización y revisión de piezas.",
    "Consulta por dolor lumbar mecánico. Se indican ejercicios y analgesia.",
    "Control de niño sano. Percentiles adecuados, vacunación al día.",
    "Curación de herida superficial. Sin signos de infección.",
    "Consulta por cefalea tensional. Se descartan signos de alarma.",
    "Control de glucemia y lípidos. Se refuerzan pautas de alimentación.",
    "Obturación de pieza dental. Sin complicaciones.",
    "Consulta por alergia estacional. Se indica antihistamínico.",
    "Control post tratamiento. Evolución favorable, alta de seguimiento.",
]
RECOMENDACIONES = [
    "Reposo relativo e hidratación. Volver ante fiebre persistente.",
    "Control en 30 días con estudios de laboratorio.",
    "Continuar medicación indicada. Actividad física moderada.",
    "Higiene bucal tres veces por día. Control semestral.",
    "Aplicar frío local 15 minutos, tres veces por día.",
    "Consultar por guardia ante dificultad respiratoria.",
    None, None, None, None,
]
MOTIVOS_DERIVACION = [
    "Traumatismo leve en vía pública, requiere evaluación.",
    "Crisis hipertensiva referida por el vecino.",
    "Caída en la vía pública con dolor en miembro superior.",
    "Cuadro de deshidratación, se traslada a la Guardia.",
    "Reacción alérgica moderada.",
    "Dolor torácico atípico, se deriva para evaluación.",
    "Herida cortante que requiere sutura.",
    "Cuadro febril en menor, control pediátrico.",
]
INTERVENCIONES_GUARDIA = [
    "Evaluación en Guardia. Signos vitales estables. Se administra analgesia y se otorga el alta.",
    "Sutura de herida cortante, profilaxis antitetánica. Control en 7 días.",
    "Inmovilización de miembro superior. Se indica radiografía ambulatoria.",
    "Control de tensión arterial, medicación sublingual. Alta con seguimiento por su médico de cabecera.",
    "Hidratación oral, antitérmico. Se indica reposo y control en 48 horas.",
    "Antihistamínico y corticoide. Observación una hora, alta sin complicaciones.",
]
EVENTOS_NOMBRES = [
    "Ciclo de cine en el {espacio}", "Concierto de la Banda Municipal",
    "Taller de huerta urbana", "Charla abierta: prevención en salud",
    "Feria de emprendedores locales", "Obra de teatro infantil",
    "Clase abierta de folklore", "Encuentro coral de primavera",
    "Muestra fotográfica del municipio", "Torneo abierto de ajedrez",
    "Festival de música joven", "Jornada de reciclado y compostaje",
    "Presentación del libro de historia local", "Recital de tango",
    "Taller de primeros auxilios para vecinos", "Noche de museos",
]
EVENTOS_DESCRIPCION = "Actividad abierta a la comunidad. Entrada libre con reserva previa."
CAPACIDADES = [30, 50, 80, 120, 200, 300]


def _elegir(rnd: random.Random, pares):
    return demo_datos._elegir(rnd, pares)


def _a_utc(d: date, t: time) -> datetime:
    """Fecha + hora LOCAL del municipio (naive) -> datetime aware en UTC."""
    return datetime.combine(d, t, tzinfo=TZ_MUNICIPIO).astimezone(UTC)


def _clamp(dt: datetime, tope: datetime) -> datetime:
    return dt if dt <= tope else tope


def _sumar(t: time, minutos: int) -> Optional[time]:
    base = datetime(2000, 1, 1, t.hour, t.minute, t.second) + timedelta(minutes=minutos)
    if base.date() != date(2000, 1, 1):
        return None
    return base.time()


# ── Catalogos ────────────────────────────────────────────────────────────────

@dataclass
class _Prestacion:
    id: int
    nombre: str
    tipo_recurso: str
    id_recurso: int
    id_ubicacion: Optional[int]
    duracion_min: int
    registra_atencion: bool
    id_subarea: Optional[int]
    atendido: Optional[bool]


@dataclass
class _Catalogos:
    uid: int = 0
    pool: list[tuple[int, str]] = field(default_factory=list)
    prestaciones: list[_Prestacion] = field(default_factory=list)
    prefijos: dict[int, str] = field(default_factory=dict)           # id_espacio -> prefijo colero
    guardia: Optional[dict] = None
    medicos: list[int] = field(default_factory=list)
    tipos_emergencia: list[dict] = field(default_factory=list)
    estados_emergencia: dict[str, int] = field(default_factory=dict)
    canales: list[int] = field(default_factory=list)
    espacios_eventos: list[dict] = field(default_factory=list)
    estado_evento: dict[str, int] = field(default_factory=dict)
    estado_reserva: dict[str, int] = field(default_factory=dict)
    id_plantilla_turnos: Optional[int] = None
    cat_reclamos: Any = None                                         # localidades para lat/lon


_CODIGOS_GUARDIA_PREFERIDOS = ("EMERGENCIA_SALUD", "ACCIDENTE_VIA_PUBLICA", "CAIDA_ARBOL",
                               "INCENDIO", "CAIDA_TENDIDO")


async def _cargar_catalogos(db: AsyncSession, rnd: random.Random) -> _Catalogos:
    cat = _Catalogos()
    cat.uid = await demo_datos._usuario_generador(db)
    cat.cat_reclamos = await demo_datos._cargar_catalogos(db)

    # Vecinos demo (solo ellos: los turnos demo nunca cuelgan de un vecino real).
    r = await db.execute(text(
        "SELECT id_ciudadano, email FROM ciudadanos WHERE activo AND email LIKE :d ORDER BY id_ciudadano"),
        {"d": f"%@{demo_datos.DOMINIO_VECINO_DEMO}"})
    cat.pool = [(f.id_ciudadano, f.email) for f in r.fetchall()]
    if len(cat.pool) < 50 and cat.cat_reclamos.poblacion_localidades:
        await demo_datos._asegurar_vecinos(db, cat.cat_reclamos, cat.uid, 250, rnd)
        r = await db.execute(text(
            "SELECT id_ciudadano, email FROM ciudadanos WHERE activo AND email LIKE :d ORDER BY id_ciudadano"),
            {"d": f"%@{demo_datos.DOMINIO_VECINO_DEMO}"})
        cat.pool = [(f.id_ciudadano, f.email) for f in r.fetchall()]

    r = await db.execute(text("""
        SELECT tp.id_tipo_prestacion, tp.nombre, tp.tipo_recurso, tp.id_agente, tp.id_espacio,
               COALESCE(tp.id_espacio_ubicacion, tp.id_espacio) AS id_ubicacion,
               tp.duracion_min, tp.registra_atencion, tp.id_subarea,
               e.atendido
          FROM tipo_prestacion tp
          LEFT JOIN espacios_agenda e ON e.id_espacio = tp.id_espacio
         WHERE tp.activo = TRUE AND tp.tipo_recurso IN ('agente', 'espacio')
           AND COALESCE(tp.id_agente, tp.id_espacio) IS NOT NULL
         ORDER BY tp.id_tipo_prestacion
    """))
    for f in r.fetchall():
        cat.prestaciones.append(_Prestacion(
            id=f.id_tipo_prestacion, nombre=f.nombre, tipo_recurso=f.tipo_recurso,
            id_recurso=int(f.id_agente if f.tipo_recurso == "agente" else f.id_espacio),
            id_ubicacion=f.id_ubicacion, duracion_min=int(f.duracion_min or 30),
            registra_atencion=bool(f.registra_atencion), id_subarea=f.id_subarea,
            atendido=(bool(f.atendido) if f.tipo_recurso == "espacio" else None),
        ))

    r = await db.execute(text(
        "SELECT id_espacio, COALESCE(NULLIF(TRIM(prefijo_colero), ''), '') AS p FROM espacios_agenda WHERE activo"))
    cat.prefijos = {f.id_espacio: f.p for f in r.fetchall()}

    cat.guardia = await espacio_guardia(db)
    if cat.guardia:
        r = await db.execute(text("""
            SELECT ea.id_agente FROM espacio_agentes ea JOIN agentes a ON a.id_agente = ea.id_agente
             WHERE ea.activo AND a.activo AND ea.id_espacio = :e ORDER BY ea.id_agente
        """), {"e": cat.guardia["id_espacio"]})
        cat.medicos = [f.id_agente for f in r.fetchall()]

    r = await db.execute(text("""
        SELECT id_emergencia_tipo, codigo, id_subarea, id_prioridad_default
          FROM emergencia_tipo WHERE activo AND es_emergencia AND id_prioridad_default IS NOT NULL
    """))
    tipos = [dict(f._mapping) for f in r.fetchall()]
    pref = [t for t in tipos if t["codigo"] in _CODIGOS_GUARDIA_PREFERIDOS]
    cat.tipos_emergencia = pref or tipos
    r = await db.execute(text("SELECT id_emergencia_estado, codigo FROM emergencia_estado WHERE activo"))
    cat.estados_emergencia = {f.codigo: f.id_emergencia_estado for f in r.fetchall()}
    r = await db.execute(text("SELECT id_emergencia_canal_ingreso FROM emergencia_canal_ingreso WHERE activo ORDER BY 1"))
    cat.canales = [f.id_emergencia_canal_ingreso for f in r.fetchall()]

    # Espacios para eventos: con capacidad de publico (>= 20) y subarea; si el
    # municipio no cargo capacidades, los dos espacios mas grandes.
    r = await db.execute(text("""
        SELECT id_espacio, nombre, COALESCE(capacidad_personas, 0) AS cap, id_subarea
          FROM espacios_agenda WHERE activo AND id_subarea IS NOT NULL
         ORDER BY COALESCE(capacidad_personas, 0) DESC, id_espacio
    """))
    todos = [dict(f._mapping) for f in r.fetchall()]
    if cat.guardia:
        todos = [e for e in todos if e["id_espacio"] != cat.guardia["id_espacio"]]
    grandes = [e for e in todos if e["cap"] >= 20]
    cat.espacios_eventos = grandes or todos[:2]
    r = await db.execute(text("SELECT id_estado_evento, codigo FROM estado_evento WHERE activo"))
    cat.estado_evento = {f.codigo: f.id_estado_evento for f in r.fetchall()}
    r = await db.execute(text("SELECT id_estado_reserva, codigo FROM estado_reserva WHERE activo"))
    cat.estado_reserva = {f.codigo: f.id_estado_reserva for f in r.fetchall()}

    r = await db.execute(text(
        "SELECT id_encuesta_plantilla FROM encuesta_plantilla WHERE tipo = 'turnos' AND activo "
        "ORDER BY id_encuesta_plantilla LIMIT 1"))
    fila = r.fetchone()
    cat.id_plantilla_turnos = fila.id_encuesta_plantilla if fila else None
    return cat


# ── Turnos ───────────────────────────────────────────────────────────────────

def _slots(rangos: list[dict], dur: int) -> list[time]:
    out: list[time] = []
    for r in rangos:
        hi, hf = r["hora_inicio"], r["hora_fin"]
        t = hi
        while True:
            fin = _sumar(t, dur)
            if fin is None or fin > hf:
                break
            out.append(t)
            t = fin
    return out


def _solapa(intervalos: list[tuple[time, time]], hi: time, hf: time) -> bool:
    return any(a < hf and b > hi for a, b in intervalos)


async def _ocupado(db: AsyncSession, prestaciones: list[_Prestacion],
                   desde: date, hasta: date) -> dict[tuple[str, int, date], list[tuple[time, time]]]:
    """Intervalos ya tomados por recurso y dia: ocupaciones activas + turnos
    vigentes sin ocupacion (legacy). Evita solapes y el UNIQUE de slot (mig 95)."""
    pares = {(p.tipo_recurso, p.id_recurso) for p in prestaciones}
    agentes = [i for t, i in pares if t == "agente"] or [-1]
    espacios = [i for t, i in pares if t == "espacio"] or [-1]
    out: dict[tuple[str, int, date], list[tuple[time, time]]] = {}
    r = await db.execute(text("""
        SELECT tipo_recurso, id_recurso, fecha, hora_inicio, hora_fin FROM ocupaciones
         WHERE activo = TRUE AND fecha BETWEEN :d AND :h
           AND ((tipo_recurso = 'agente' AND id_recurso = ANY(:ag))
             OR (tipo_recurso = 'espacio' AND id_recurso = ANY(:es)))
        UNION ALL
        SELECT CASE WHEN id_agente IS NOT NULL THEN 'agente' ELSE 'espacio' END,
               COALESCE(id_agente, id_espacio), fecha, hora_inicio, hora_fin
          FROM turnos
         WHERE activo = TRUE AND estado <> 'cancelado' AND fecha BETWEEN :d AND :h
           AND (id_agente = ANY(:ag) OR id_espacio = ANY(:es))
    """), {"d": desde, "h": hasta, "ag": agentes, "es": espacios})
    for f in r.fetchall():
        out.setdefault((f.tipo_recurso, int(f.id_recurso), f.fecha), []).append((f.hora_inicio, f.hora_fin))
    return out


async def _max_numeros(db: AsyncSession, desde: date, hasta: date) -> dict[tuple[int, date], int]:
    r = await db.execute(text("""
        SELECT id_espacio_ubicacion AS u, fecha AS f,
               MAX(SUBSTRING(numero_diario FROM '[0-9]+$')::int) AS m
          FROM turnos
         WHERE numero_diario IS NOT NULL AND id_espacio_ubicacion IS NOT NULL
           AND fecha BETWEEN :d AND :h
         GROUP BY 1, 2
    """), {"d": desde, "h": hasta})
    return {(int(f.u), f.f): int(f.m or 0) for f in r.fetchall()}


def _espera_min(rnd: random.Random) -> float:
    lo, hi = _elegir(rnd, ESPERA_TRAMOS)
    return rnd.uniform(lo, hi)


def _desenlace(rnd: random.Random, cat: _Catalogos, t: dict, ahora: datetime) -> None:
    """Completa un turno YA vencido: estado final, llamados, atencion, encuesta.
    `t` trae fecha/hora_inicio/hora_fin/slot_utc/prestacion/id_ciudadano/email/fecha_alta."""
    estado = _elegir(rnd, DESENLACES)
    t["estado"] = estado
    t["llamados"] = []
    t["atencion"] = None
    t["envio"] = None
    t["respuesta"] = None
    if estado == "cancelado":
        # Se cancela entre el alta y unas horas antes del turno.
        cancel = t["slot_utc"] - timedelta(hours=rnd.uniform(2, 120))
        t["fecha_modificacion"] = max(cancel, t["fecha_alta"] + timedelta(hours=1))
        return
    primer = t["slot_utc"] + timedelta(minutes=_espera_min(rnd))
    primer = _clamp(primer, ahora - timedelta(minutes=5))
    t["llamados"].append(primer)
    re_llama = rnd.random() < (0.60 if estado == "ausente" else 0.08)
    if re_llama:
        t["llamados"].append(_clamp(primer + timedelta(minutes=rnd.uniform(3, 9)), ahora - timedelta(minutes=4)))
    ultimo = t["llamados"][-1]
    if estado == "ausente":
        t["fecha_modificacion"] = ultimo + timedelta(minutes=rnd.uniform(5, 15))
        return
    p: _Prestacion = t["prestacion"]
    fin_atencion = ultimo + timedelta(minutes=rnd.uniform(8, p.duracion_min + 15))
    fin_atencion = _clamp(fin_atencion, ahora - timedelta(minutes=1))
    t["fecha_modificacion"] = fin_atencion
    if p.registra_atencion:
        t["atencion"] = {"intervencion": rnd.choice(INTERVENCIONES),
                         "recomendaciones": rnd.choice(RECOMENDACIONES), "fecha": fin_atencion}
    if cat.id_plantilla_turnos and rnd.random() < 0.85:
        fecha_envio = fin_atencion + timedelta(days=1, hours=rnd.uniform(0, 6))
        if fecha_envio > ahora - timedelta(hours=1):
            return  # todavia no salio (el dispatcher real tambien espera 24 h)
        expiracion = fecha_envio + timedelta(days=15)
        reciente = expiracion > ahora
        envio = {"id_plantilla": cat.id_plantilla_turnos, "id_ciudadano": t["id_ciudadano"],
                 "email": t["email"], "fecha_envio": fecha_envio, "fecha_apertura": None,
                 "fecha_completada": None, "fecha_expiracion": expiracion,
                 "estado": "enviada" if reciente else "expirada", "id_subarea": p.id_subarea, "uid": cat.uid}
        if rnd.random() < (0.30 if not reciente else 0.25):
            apertura = _clamp(fecha_envio + timedelta(hours=rnd.uniform(1, 72)), ahora - timedelta(minutes=30))
            completada = _clamp(apertura + timedelta(minutes=rnd.uniform(2, 25)), ahora)
            clasificacion = _elegir(rnd, demo_datos.SCORES)
            envio.update({"estado": "completada", "fecha_apertura": apertura, "fecha_completada": completada})
            t["respuesta"] = {"clasificacion": clasificacion, "rama": demo_datos._rama(clasificacion),
                              "tiempo": rnd.randint(45, 420), "id_subarea": p.id_subarea,
                              "fecha": completada, "uid": cat.uid}
        t["envio"] = envio


async def _recursos_ya_demo(db: AsyncSession, uid: int, desde: date, hasta: date) -> set[tuple[str, int, date]]:
    """(recurso, dia) que ya tienen turnos demo: se saltean al re-generar un
    rango (idempotencia por dia — sin esto cada corrida vuelve a ocupar el
    35-65 % de lo que quedo libre y la ocupacion tiende al 100 %)."""
    r = await db.execute(text("""
        SELECT DISTINCT CASE WHEN id_agente IS NOT NULL THEN 'agente' ELSE 'espacio' END AS tr,
               COALESCE(id_agente, id_espacio) AS ir, fecha
          FROM turnos WHERE id_usuario_alta = :uid AND fecha BETWEEN :d AND :h
    """), {"uid": uid, "d": desde, "h": hasta})
    return {(f.tr, int(f.ir), f.fecha) for f in r.fetchall()}


def _armar_turnos_dia(rnd: random.Random, cat: _Catalogos, dia: date,
                      disp: dict, ocupado: dict, ahora: datetime, ahora_loc: datetime,
                      ya_demo: set[tuple[str, int, date]], omitidos: dict) -> list[dict]:
    turnos: list[dict] = []
    for p in cat.prestaciones:
        rangos = disp.get((p.tipo_recurso, p.id_recurso, dia)) or []
        if not rangos:
            continue
        clave = (p.tipo_recurso, p.id_recurso, dia)
        if clave in ya_demo:
            omitidos["recurso_dia_ya_demo"] = omitidos.get("recurso_dia_ya_demo", 0) + 1
            continue
        ya_demo.add(clave)  # dos prestaciones del mismo recurso comparten el dia
        tomados = ocupado.setdefault(clave, [])
        libres = [s for s in _slots(rangos, p.duracion_min)
                  if not _solapa(tomados, s, _sumar(s, p.duracion_min))]
        if not libres:
            continue
        n = round(len(libres) * rnd.uniform(*OCUPACION))
        for hi in sorted(rnd.sample(libres, min(n, len(libres)))):
            hf = _sumar(hi, p.duracion_min)
            tomados.append((hi, hf))
            id_c, email = rnd.choice(cat.pool)
            slot_utc = _a_utc(dia, hi)
            alta = slot_utc - timedelta(days=rnd.uniform(1, 21), hours=rnd.uniform(0, 8))
            alta = _clamp(alta, ahora - timedelta(minutes=2))
            t = {"prestacion": p, "fecha": dia, "hora_inicio": hi, "hora_fin": hf, "slot_utc": slot_utc,
                 "id_ciudadano": id_c, "email": email, "origen": _elegir(rnd, ORIGENES),
                 "fecha_alta": alta, "fecha_modificacion": alta, "estado": "reservado",
                 "numero": None, "llamados": [], "atencion": None, "envio": None, "respuesta": None}
            if datetime.combine(dia, hi) < ahora_loc - timedelta(hours=1):
                _desenlace(rnd, cat, t, ahora)
            turnos.append(t)
    return turnos


def _numerar(turnos: list[dict], cat: _Catalogos, maximos: dict[tuple[int, date], int]) -> None:
    """Numero de colero por ubicacion y dia, en orden de primer llamado,
    continuando el correlativo que ya exista en la DB (mismo formato que
    PATCH /turnos/{id}/llamar: '<PREFIJO>-001' o '001')."""
    llamados = [t for t in turnos if t["llamados"] and t["prestacion"].id_ubicacion]
    llamados.sort(key=lambda t: t["llamados"][0])
    for t in llamados:
        u = int(t["prestacion"].id_ubicacion)
        k = (u, t["fecha"])
        maximos[k] = maximos.get(k, 0) + 1
        pref = cat.prefijos.get(u, "")
        t["numero"] = f"{pref}-{maximos[k]:03d}" if pref else f"{maximos[k]:03d}"


# Tipo SQL de cada columna de los VALUES masivos. Sin CAST, Postgres tipa como
# `text` los parametros de un VALUES compuesto solo por parametros y el INSERT
# falla ("column is of type date but expression is of type text").
_TIPOS = {
    "tr": "text", "ir": "int", "f": "date", "hi": "time", "hf": "time", "ic": "int", "act": "boolean",
    "fa": "timestamptz", "fm": "timestamptz", "uid": "int", "ia": "int", "ie": "int", "iu": "int",
    "itp": "int", "io": "int", "es": "text", "num": "text", "ori": "text", "isa": "int",
    "id_plantilla": "int", "id_ciudadano": "int", "it": "int", "email": "text",
    "fecha_envio": "timestamptz", "fecha_apertura": "timestamptz", "fecha_completada": "timestamptz",
    "fecha_expiracion": "timestamptz", "estado": "text", "id_subarea": "int",
    "ev": "int", "er": "int", "tok": "boolean",
}


def _values(rows: list[dict], cols: list[str], prefix: str) -> tuple[str, dict]:
    """VALUES (...),(...) con parametros numerados y CAST por columna para un
    INSERT masivo (una sola sentencia por lote, con RETURNING)."""
    partes, params = [], {}
    for i, row in enumerate(rows):
        partes.append("(" + ", ".join(f"CAST(:{prefix}{c}_{i} AS {_TIPOS[c]})" for c in cols) + ")")
        for c in cols:
            params[f"{prefix}{c}_{i}"] = row[c]
    return ", ".join(partes), params


async def _insertar_turnos(db: AsyncSession, cat: _Catalogos, turnos: list[dict]) -> dict:
    """Inserta en bloque (por lotes de 300): ocupaciones -> turnos -> llamados,
    atenciones, encuestas y respuestas. Devuelve conteos."""
    n = {"turnos": 0, "cumplidos": 0, "ausentes": 0, "cancelados": 0, "reservados": 0,
         "llamados": 0, "atenciones": 0, "encuestas": 0, "respuestas": 0}
    for i in range(0, len(turnos), 300):
        lote = turnos[i:i + 300]
        # 1) ocupaciones espejo (una por turno, tambien para los cancelados: la
        #    cancelacion real la deja activo=FALSE, ver abajo).
        filas = [{"tr": t["prestacion"].tipo_recurso, "ir": t["prestacion"].id_recurso, "f": t["fecha"],
                  "hi": t["hora_inicio"], "hf": t["hora_fin"], "ic": t["id_ciudadano"],
                  "act": t["estado"] != "cancelado", "fa": t["fecha_alta"], "fm": t["fecha_modificacion"],
                  "uid": cat.uid} for t in lote]
        vals, params = _values(filas, ["tr", "ir", "f", "hi", "hf", "ic", "act", "fa", "fm", "uid"], "o")
        r = await db.execute(text(f"""
            INSERT INTO ocupaciones (tipo, tipo_recurso, id_recurso, fecha, hora_inicio, hora_fin,
                                     id_ciudadano, activo, fecha_alta, fecha_modificacion, id_usuario_alta, motivo)
            SELECT 'turno', v.tr, v.ir, v.f, v.hi, v.hf, v.ic, v.act, v.fa, v.fm, v.uid, 'Turno'
              FROM (VALUES {vals}) AS v(tr, ir, f, hi, hf, ic, act, fa, fm, uid)
            RETURNING id_ocupacion, tipo_recurso, id_recurso, fecha, hora_inicio
        """), params)
        ocup = {(f.tipo_recurso, int(f.id_recurso), f.fecha, f.hora_inicio): int(f.id_ocupacion) for f in r.fetchall()}
        # 2) turnos
        filas = []
        for t in lote:
            p = t["prestacion"]
            filas.append({
                "ic": t["id_ciudadano"], "ia": p.id_recurso if p.tipo_recurso == "agente" else None,
                "ie": p.id_recurso if p.tipo_recurso == "espacio" else None, "iu": p.id_ubicacion,
                "itp": p.id, "io": ocup[(p.tipo_recurso, p.id_recurso, t["fecha"], t["hora_inicio"])],
                "f": t["fecha"], "hi": t["hora_inicio"], "hf": t["hora_fin"], "es": t["estado"],
                "num": t["numero"], "ori": t["origen"], "isa": p.id_subarea,
                "fa": t["fecha_alta"], "fm": t["fecha_modificacion"], "uid": cat.uid,
            })
        cols = ["ic", "ia", "ie", "iu", "itp", "io", "f", "hi", "hf", "es", "num", "ori", "isa", "fa", "fm", "uid"]
        vals, params = _values(filas, cols, "t")
        r = await db.execute(text(f"""
            INSERT INTO turnos (id_ciudadano, id_agente, id_espacio, id_espacio_ubicacion, id_tipo_prestacion,
                                id_ocupacion, fecha, hora_inicio, hora_fin, estado, numero_diario, origen,
                                id_subarea, fecha_alta, fecha_modificacion, id_usuario_alta, id_usuario_modificacion)
            SELECT v.ic, v.ia, v.ie, v.iu, v.itp, v.io, v.f, v.hi, v.hf, v.es, v.num, v.ori,
                   v.isa, v.fa, v.fm, v.uid, v.uid
              FROM (VALUES {vals}) AS v({', '.join(cols)})
            RETURNING id_turno, id_ocupacion
        """), params)
        por_ocup = {int(f.id_ocupacion): int(f.id_turno) for f in r.fetchall()}
        for t in lote:
            p = t["prestacion"]
            t["id_turno"] = por_ocup[ocup[(p.tipo_recurso, p.id_recurso, t["fecha"], t["hora_inicio"])]]
            n["turnos"] += 1
            n[{"cumplido": "cumplidos", "ausente": "ausentes", "cancelado": "cancelados",
               "reservado": "reservados", "llamado": "reservados"}[t["estado"]]] += 1
        # 3) llamados / atenciones / encuestas
        llam = [{"it": t["id_turno"], "en": ll, "uid": cat.uid} for t in lote for ll in t["llamados"]]
        if llam:
            await db.execute(text("""
                INSERT INTO turno_llamado (id_turno, puesto, llamado_en, id_usuario_llama,
                                           fecha_alta, fecha_modificacion, id_usuario_alta, id_usuario_modificacion)
                VALUES (:it, NULL, :en, :uid, :en, :en, :uid, :uid)
            """), llam)
            n["llamados"] += len(llam)
        aten = [{"it": t["id_turno"], "ic": t["id_ciudadano"], "inter": t["atencion"]["intervencion"],
                 "reco": t["atencion"]["recomendaciones"], "isa": t["prestacion"].id_subarea,
                 "f": t["atencion"]["fecha"], "uid": cat.uid} for t in lote if t["atencion"]]
        if aten:
            await db.execute(text("""
                INSERT INTO turno_atencion (id_turno, id_ciudadano, intervencion, recomendaciones,
                                            id_subarea, fecha_alta, fecha_modificacion, id_usuario_alta, id_usuario_modificacion)
                VALUES (:it, :ic, :inter, :reco, :isa, :f, :f, :uid, :uid)
                ON CONFLICT (id_turno) DO NOTHING
            """), aten)
            n["atenciones"] += len(aten)
        con_envio = [t for t in lote if t["envio"]]
        if con_envio:
            filas = [{**t["envio"], "it": t["id_turno"]} for t in con_envio]
            cols = ["id_plantilla", "id_ciudadano", "it", "email", "fecha_envio", "fecha_apertura",
                    "fecha_completada", "fecha_expiracion", "estado", "id_subarea", "uid"]
            vals, params = _values(filas, cols, "e")
            r = await db.execute(text(f"""
                INSERT INTO encuesta_envio (id_plantilla, id_ciudadano, id_turno, email_destino_snapshot,
                                            fecha_envio, fecha_apertura, fecha_completada, fecha_expiracion,
                                            estado, id_subarea, fecha_alta, fecha_modificacion, id_usuario_alta)
                SELECT v.id_plantilla, v.id_ciudadano, v.it, v.email, v.fecha_envio, v.fecha_apertura,
                       v.fecha_completada, v.fecha_expiracion, v.estado, v.id_subarea, v.fecha_envio, v.fecha_envio, v.uid
                  FROM (VALUES {vals}) AS v({', '.join(cols)})
                RETURNING id_encuesta_envio, id_turno
            """), params)
            env_por_turno = {int(f.id_turno): int(f.id_encuesta_envio) for f in r.fetchall()}
            n["encuestas"] += len(env_por_turno)
            resp = [{**t["respuesta"], "id_envio": env_por_turno[t["id_turno"]]}
                    for t in con_envio if t["respuesta"]]
            if resp:
                await db.execute(demo_datos._SQL_INSERT_RESPUESTA, resp)
                n["respuestas"] += len(resp)
    return n


# ── Guardia (Emergencias -> emergencia_atencion) ─────────────────────────────

async def _generar_guardia(db: AsyncSession, cat: _Catalogos, rnd: random.Random,
                           dias: list[date], ahora: datetime, hoy: date) -> dict:
    n = {"eventos": 0, "derivaciones": 0, "atendidas": 0, "ausentes": 0, "pendientes": 0}
    if not cat.guardia or not cat.medicos or not cat.tipos_emergencia or not cat.canales:
        n["omitido"] = ("sin Guardia configurada" if not cat.guardia else
                        "la Guardia no tiene medicos vinculados (espacio_agentes)" if not cat.medicos else
                        "sin tipos/canales de emergencia activos")
        return n
    est = cat.estados_emergencia
    # Idempotencia por dia: si un dia ya tiene derivaciones demo (backfill +
    # cron solapados, o cron demorado + dispatch manual), no se le agrega otra
    # capa. Los turnos ya lo resuelven por slot; la guardia no tiene slot.
    r = await db.execute(text("""
        SELECT DISTINCT ((derivado_en AT TIME ZONE 'UTC') - INTERVAL '3 hours')::date AS d
          FROM emergencia_atencion
         WHERE id_usuario_alta = :uid AND activo IS DISTINCT FROM FALSE
           AND derivado_en >= :d0 AND derivado_en < :d1
    """), {"uid": cat.uid, "d0": _a_utc(min(dias), time(0, 0)), "d1": _a_utc(max(dias) + timedelta(days=1), time(0, 0))})
    ya_con_demo = {f.d for f in r.fetchall()}
    n["dias_omitidos_con_demo"] = 0
    for dia in dias:
        if dia > hoy:
            continue
        if dia in ya_con_demo:
            n["dias_omitidos_con_demo"] += 1
            continue
        for _ in range(_elegir(rnd, GUARDIA_POR_DIA)):
            tipo = rnd.choice(cat.tipos_emergencia)
            recepcion = _a_utc(dia, time(rnd.randint(7, 22), rnd.randint(0, 59), rnd.randint(0, 59)))
            if recepcion > ahora - timedelta(minutes=30):
                continue
            if cat.cat_reclamos.poblacion_localidades:
                _id_loc, loc_nombre, lat0, lon0, radio = demo_datos._elegir_localidad(rnd, cat.cat_reclamos)
                lat, lon = demo_datos._jitter(rnd, lat0, lon0, radio)
                direccion = f"{rnd.choice(demo_datos.CALLES)} {rnd.randint(100, 5900)}, {loc_nombre}"
            else:
                lat = lon = None
                direccion = f"{rnd.choice(demo_datos.CALLES)} {rnd.randint(100, 5900)}"
            anonimo = rnd.random() < 0.35
            id_c = None if anonimo else rnd.choice(cat.pool)[0]
            en_camino = recepcion + timedelta(minutes=rnd.uniform(4, 15))
            en_sitio = en_camino + timedelta(minutes=rnd.uniform(8, 25))
            derivado = en_sitio + timedelta(minutes=rnd.uniform(5, 40))
            cierra = derivado + timedelta(minutes=rnd.uniform(10, 90))
            pendiente_hoy = dia == hoy and cierra > ahora - timedelta(minutes=10)
            if pendiente_hoy:
                estado_final, cierre_dt = "EN_SITIO", None
            else:
                estado_final, cierre_dt = "RESUELTO", _clamp(cierra, ahora - timedelta(minutes=5))
            id_ev = await db.scalar(text("""
                INSERT INTO emergencia_evento
                    (id_subarea, id_tipo, id_prioridad, id_estado, id_canal_ingreso, id_operador_receptor,
                     denunciante_anonimo, id_ciudadano_buc, direccion_evento, latitud, longitud,
                     observaciones_recepcion, veracidad, observaciones_cierre,
                     fecha_hora_recepcion, fecha_hora_despacho, fecha_hora_arribo, fecha_hora_cierre,
                     activo, fecha_alta, fecha_modificacion, id_usuario_alta)
                VALUES (:sub, :tipo, :prio, :est, :canal, :uid, :anon, :ciu, :dir, :lat, :lon,
                        :obs, :ver, :oc, :rec, :desp, :arr, :cierre, TRUE, :rec, :fm, :uid)
                RETURNING id_emergencia_evento
            """), {
                "sub": tipo["id_subarea"], "tipo": tipo["id_emergencia_tipo"], "prio": tipo["id_prioridad_default"],
                "est": est[estado_final], "canal": rnd.choice(cat.canales), "uid": cat.uid,
                "anon": anonimo, "ciu": id_c, "dir": direccion, "lat": lat, "lon": lon,
                "obs": "Llamado recibido en el COM (demo).",
                "ver": "CONFIRMADA" if cierre_dt else None,
                "oc": "Vecino derivado a la Guardia (demo)." if cierre_dt else None,
                "rec": recepcion, "desp": en_camino, "arr": en_sitio, "cierre": cierre_dt,
                "fm": cierre_dt or derivado,
            })
            n["eventos"] += 1
            # Atencion en la Guardia
            if pendiente_hoy:
                estado_at = "pendiente"
            else:
                estado_at = "atendida" if rnd.random() < 0.85 else "ausente"
            atendido = derivado + timedelta(minutes=rnd.uniform(8, 75)) if estado_at == "atendida" else None
            if atendido and cierre_dt and atendido > cierre_dt:
                atendido = cierre_dt - timedelta(minutes=2)
            medico = rnd.choice(cat.medicos) if estado_at == "atendida" else None
            id_at = await db.scalar(text("""
                INSERT INTO emergencia_atencion
                    (id_emergencia_evento, id_espacio_ubicacion, id_ciudadano, paciente_nombre,
                     motivo_derivacion, estado, derivado_en, id_usuario_deriva, id_agente_atiende,
                     intervencion, recomendaciones, atendido_en, id_subarea,
                     fecha_alta, fecha_modificacion, id_usuario_alta, id_usuario_modificacion)
                VALUES (:ev, :g, :c, :pn, :m, :es, :der, :uid, :ag, :inter, :reco, :at, :sa,
                        :der, :fm, :uid, :uid)
                RETURNING id_emergencia_atencion
            """), {
                "ev": id_ev, "g": cat.guardia["id_espacio"], "c": id_c,
                "pn": None if id_c else "Vecino sin identificar",
                "m": rnd.choice(MOTIVOS_DERIVACION), "es": estado_at, "der": derivado, "uid": cat.uid,
                "ag": medico, "inter": rnd.choice(INTERVENCIONES_GUARDIA) if estado_at == "atendida" else None,
                "reco": rnd.choice(RECOMENDACIONES) if estado_at == "atendida" else None,
                "at": atendido, "sa": cat.guardia.get("id_subarea"),
                "fm": atendido or (derivado + timedelta(minutes=30) if estado_at == "ausente" else derivado),
            })
            n["derivaciones"] += 1
            n[{"atendida": "atendidas", "ausente": "ausentes", "pendiente": "pendientes"}[estado_at]] += 1
            # Log del evento (mismo shape que emergencias.py / guardia.py).
            logs = [
                ("CREACION", None, "PENDIENTE", recepcion, {"id_canal_ingreso": None}, None),
                ("CAMBIO_ESTADO", "PENDIENTE", "EN_CAMINO", en_camino, None, None),
                ("CAMBIO_ESTADO", "EN_CAMINO", "EN_SITIO", en_sitio, None, None),
                ("DERIVACION_GUARDIA", "EN_SITIO", "EN_SITIO", derivado,
                 {"id_emergencia_atencion": int(id_at), "id_espacio_guardia": cat.guardia["id_espacio"],
                  "guardia": cat.guardia["nombre"], "id_ciudadano": id_c}, "Derivado a la Guardia (demo)"),
            ]
            if estado_at != "pendiente":
                logs.append(("ATENCION_GUARDIA", "EN_SITIO", "EN_SITIO",
                             atendido or (derivado + timedelta(minutes=30)),
                             {"id_emergencia_atencion": int(id_at), "resultado": estado_at,
                              "id_agente_atiende": medico},
                             "Atendido en la Guardia" if estado_at == "atendida" else "No se presento en la Guardia"))
            if cierre_dt:
                logs.append(("CIERRE", "EN_SITIO", "RESUELTO", cierre_dt,
                             {"veracidad": "CONFIRMADA", "terminal_positivo": True}, "Vecino derivado a la Guardia (demo)."))
            await db.execute(text("""
                INSERT INTO emergencia_log (id_evento, id_usuario, fecha_hora, tipo_accion, estado_anterior,
                                            estado_nuevo, payload_json, observaciones)
                VALUES (:e, :u, :fh, :t, :ea, :en, CAST(:p AS jsonb), :o)
            """), [{"e": id_ev, "u": cat.uid, "fh": fh, "t": t, "ea": ea, "en": en,
                    "p": json.dumps(p) if p is not None else None, "o": o}
                   for t, ea, en, fh, p, o in logs])
    return n


# ── Eventos y reservas ───────────────────────────────────────────────────────

async def _generar_eventos(db: AsyncSession, cat: _Catalogos, rnd: random.Random,
                           desde: date, hasta_futuro: date, ahora: datetime, hoy: date) -> dict:
    n = {"eventos": 0, "reservas": 0, "asistieron": 0, "canceladas": 0}
    if not cat.espacios_eventos or not cat.estado_evento or not cat.estado_reserva:
        n["omitido"] = "sin espacios con capacidad o sin estados de evento/reserva"
        return n
    dias = (hasta_futuro - desde).days + 1
    objetivo = max(1, round(rnd.randint(*EVENTOS_MENSUAL) * dias / 30.44))
    r = await db.execute(text("""
        SELECT id_espacio, fecha, hora_inicio, hora_fin, (id_usuario_alta = :uid) AS demo FROM eventos
         WHERE activo AND id_espacio IS NOT NULL AND fecha BETWEEN :d AND :h
    """), {"d": desde, "h": hasta_futuro, "uid": cat.uid})
    ocupado: dict[tuple[int, date], list[tuple[time, time]]] = {}
    ya_demo = 0
    for f in r.fetchall():
        ocupado.setdefault((int(f.id_espacio), f.fecha), []).append((f.hora_inicio, f.hora_fin))
        ya_demo += 1 if f.demo else 0
    # Idempotencia: los eventos demo que ya hay en el rango descuentan del objetivo.
    n["ya_existian"] = ya_demo
    objetivo = max(0, objetivo - ya_demo)
    est_activo, est_final = cat.estado_evento.get("activo"), cat.estado_evento.get("finalizado")
    er = cat.estado_reserva
    intentos = 0
    while n["eventos"] < objetivo and intentos < objetivo * 4:
        intentos += 1
        esp = rnd.choice(cat.espacios_eventos)
        dia = desde + timedelta(days=rnd.randrange(dias))
        hi = time(rnd.randint(10, 20), rnd.choice((0, 30)))
        hf = _sumar(hi, rnd.choice((90, 120, 150, 180)))
        if hf is None or _solapa(ocupado.setdefault((esp["id_espacio"], dia), []), hi, hf):
            continue
        ocupado[(esp["id_espacio"], dia)].append((hi, hf))
        pasado = dia < hoy
        capacidad = min(esp["cap"], rnd.choice(CAPACIDADES)) if esp["cap"] else rnd.choice(CAPACIDADES[:3])
        tipo_qr = "nominal" if rnd.random() < 0.5 else "ninguno"
        autoservicio = rnd.random() < 0.7
        nombre = rnd.choice(EVENTOS_NOMBRES).format(espacio=esp["nombre"])
        inicio_utc = _a_utc(dia, hi)
        alta = _clamp(inicio_utc - timedelta(days=rnd.uniform(15, 45)), ahora - timedelta(minutes=2))
        id_ev = await db.scalar(text("""
            INSERT INTO eventos (nombre, descripcion, id_subarea, fecha, hora_inicio, hora_fin,
                                 capacidad_ciudadanos, cantidad_encargados, tipo_qr, admite_autoservicio,
                                 token_publico, id_espacio, id_estado_evento, fecha_alta, fecha_modificacion, id_usuario_alta)
            VALUES (:n, :d, :sa, :f, :hi, :hf, :cap, 0, :qr, :auto,
                    CASE WHEN :auto = TRUE THEN gen_random_uuid() ELSE NULL END, :esp, :es, :fa, :fm, :uid)
            RETURNING id_evento
        """), {"n": nombre, "d": EVENTOS_DESCRIPCION, "sa": esp["id_subarea"], "f": dia, "hi": hi, "hf": hf,
               "cap": capacidad, "qr": tipo_qr, "auto": autoservicio, "esp": esp["id_espacio"],
               "es": est_final if pasado and est_final else est_activo, "fa": alta,
               "fm": _clamp(inicio_utc + timedelta(hours=4), ahora) if pasado else alta, "uid": cat.uid})
        n["eventos"] += 1
        k = round(capacidad * rnd.uniform(0.3, 0.95))
        ciudadanos = rnd.sample(cat.pool, min(k, len(cat.pool)))
        filas = []
        for id_c, _email in ciudadanos:
            if pasado:
                estado = rnd.choices(["asistio", "reservada", "cancelada"], weights=[60, 25, 15], k=1)[0]
            else:
                estado = rnd.choices(["reservada", "cancelada"], weights=[88, 12], k=1)[0]
            ori = "autoservicio" if (autoservicio and rnd.random() < 0.65) else "backoffice"
            fa = _clamp(inicio_utc - timedelta(days=rnd.uniform(0.5, 25)), ahora - timedelta(minutes=1))
            fa = max(fa, alta + timedelta(hours=1))
            fm = fa
            if estado == "asistio":
                fm = inicio_utc + timedelta(minutes=rnd.uniform(-20, 40))
            elif estado == "cancelada":
                fm = _clamp(fa + timedelta(hours=rnd.uniform(2, 96)), ahora)
            filas.append({"ev": id_ev, "ic": id_c, "er": er[estado], "ori": ori, "tok": ori == "autoservicio",
                          "fa": fa, "fm": fm, "uid": cat.uid, "estado": estado})
        if filas:
            cols = ["ev", "ic", "er", "ori", "tok", "fa", "fm", "uid"]
            vals, params = _values(filas, cols, "r")
            r = await db.execute(text(f"""
                INSERT INTO evento_reservas (id_evento, id_ciudadano, id_estado_reserva, origen, token_reserva,
                                             fecha_alta, fecha_modificacion, id_usuario_alta)
                SELECT v.ev, v.ic, v.er, v.ori, CASE WHEN v.tok THEN gen_random_uuid() ELSE NULL END,
                       v.fa, v.fm, v.uid
                  FROM (VALUES {vals}) AS v({', '.join(cols)})
                RETURNING id_evento_reserva
            """), params)
            ids = [int(f.id_evento_reserva) for f in r.fetchall()]
            if tipo_qr != "ninguno":
                ts = int(alta.timestamp())
                await db.execute(text("UPDATE evento_reservas SET qr_codigo = :q WHERE id_evento_reserva = :i"),
                                 [{"q": f"EVT{id_ev}-RES{i}-{ts}", "i": i} for i in ids])
            n["reservas"] += len(filas)
            n["asistieron"] += sum(1 for f in filas if f["estado"] == "asistio")
            n["canceladas"] += sum(1 for f in filas if f["estado"] == "cancelada")
    return n


# ── API del modulo ───────────────────────────────────────────────────────────

async def generar_periodo_atencion(db: AsyncSession, desde: date, hasta: date,
                                   semilla: Optional[int] = None,
                                   dias_futuro: int = DIAS_FUTURO_DEFAULT) -> dict:
    """Genera turnos + Guardia + eventos demo en [desde, hasta]. Si el rango
    llega a hoy, tambien reserva los `dias_futuro` siguientes (turnos y eventos
    futuros, sin desenlace). Commitea al final."""
    rnd = random.Random(semilla)
    ahora = datetime.now(UTC)
    ahora_loc = ahora_local()
    hoy = hoy_local()
    cat = await _cargar_catalogos(db, rnd)
    if not cat.pool:
        raise RuntimeError("Sin vecinos demo: no se puede generar atencion demo")

    hasta_futuro = hasta + timedelta(days=dias_futuro) if hasta >= hoy and dias_futuro else hasta
    dias = [desde + timedelta(days=i) for i in range((hasta_futuro - desde).days + 1)]

    resultado: dict = {"desde": str(desde), "hasta": str(hasta), "hasta_futuro": str(hasta_futuro),
                       "prestaciones": len(cat.prestaciones), "pool_vecinos": len(cat.pool)}

    # Turnos
    if cat.prestaciones:
        recursos = list({(p.tipo_recurso, p.id_recurso, p.atendido) for p in cat.prestaciones})
        disp = await disponibilidad_efectiva_batch(db, recursos, dias)
        ocupado = await _ocupado(db, cat.prestaciones, desde, hasta_futuro)
        maximos = await _max_numeros(db, desde, hasta_futuro)
        ya_demo = await _recursos_ya_demo(db, cat.uid, desde, hasta_futuro)
        omitidos: dict = {}
        turnos: list[dict] = []
        for dia in dias:
            del_dia = _armar_turnos_dia(rnd, cat, dia, disp, ocupado, ahora, ahora_loc, ya_demo, omitidos)
            _numerar(del_dia, cat, maximos)
            turnos.extend(del_dia)
        resultado["turnos"] = {**(await _insertar_turnos(db, cat, turnos)), **omitidos}
    else:
        resultado["turnos"] = {"omitido": "sin prestaciones activas"}

    resultado["guardia"] = await _generar_guardia(db, cat, rnd, dias, ahora, hoy)
    resultado["eventos"] = await _generar_eventos(db, cat, rnd, desde, hasta_futuro, ahora, hoy)
    await db.commit()
    return resultado


async def avanzar_pendientes_atencion(db: AsyncSession, semilla: Optional[int] = None) -> dict:
    """Envejece SOLO lo demo (id_usuario_alta = generador): turnos vencidos que
    siguen reservados -> desenlace completo; derivaciones pendientes de mas de
    un dia -> atendida/ausente; eventos pasados -> finalizado (y sus reservas
    'reservada' -> asistio ~65 %)."""
    rnd = random.Random(semilla)
    ahora = datetime.now(UTC)
    ahora_loc = ahora_local()
    hoy = hoy_local()
    uid = await demo_datos._usuario_generador(db, crear=False)
    if uid is None:
        return {"detalle": "sin usuario generador: nada que avanzar"}
    cat = await _cargar_catalogos(db, rnd)
    out: dict = {"turnos": {"resueltos": 0, "cumplidos": 0, "ausentes": 0, "cancelados": 0},
                 "guardia": {"cerradas": 0}, "eventos": {"finalizados": 0, "asistencias": 0}}

    # 1) Turnos demo vencidos sin desenlace.
    r = await db.execute(text("""
        SELECT t.id_turno, t.fecha, t.hora_inicio, t.hora_fin, t.id_ciudadano, t.id_tipo_prestacion,
               t.id_espacio_ubicacion, t.fecha_alta, t.numero_diario, c.email
          FROM turnos t JOIN ciudadanos c ON c.id_ciudadano = t.id_ciudadano
         WHERE t.activo AND t.id_usuario_alta = :uid AND t.estado IN ('reservado', 'llamado')
           AND (t.fecha + t.hora_inicio) < :limite
         ORDER BY t.fecha, t.hora_inicio
    """), {"uid": uid, "limite": ahora_loc - timedelta(hours=1)})
    filas = r.fetchall()
    if filas:
        prest = {p.id: p for p in cat.prestaciones}
        fechas = sorted({f.fecha for f in filas})
        maximos = await _max_numeros(db, fechas[0], fechas[-1])
        pend: list[dict] = []
        for f in filas:
            p = prest.get(f.id_tipo_prestacion)
            if not p:
                continue
            t = {"id_turno": f.id_turno, "prestacion": p, "fecha": f.fecha, "hora_inicio": f.hora_inicio,
                 "hora_fin": f.hora_fin, "slot_utc": _a_utc(f.fecha, f.hora_inicio), "id_ciudadano": f.id_ciudadano,
                 "email": f.email, "fecha_alta": f.fecha_alta, "numero": f.numero_diario}
            _desenlace(rnd, cat, t, ahora)
            pend.append(t)
        _numerar([t for t in pend if not t["numero"]], cat, maximos)
        await db.execute(text("""
            UPDATE turnos SET estado = :es, numero_diario = COALESCE(numero_diario, :num),
                   fecha_modificacion = :fm, id_usuario_modificacion = :uid
             WHERE id_turno = :id AND estado IN ('reservado', 'llamado')
        """), [{"es": t["estado"], "num": t["numero"], "fm": t["fecha_modificacion"], "uid": uid, "id": t["id_turno"]}
               for t in pend])
        canc = [t["id_turno"] for t in pend if t["estado"] == "cancelado"]
        if canc:
            await db.execute(text("""
                UPDATE ocupaciones o SET activo = FALSE, fecha_modificacion = :fm
                  FROM turnos t WHERE t.id_ocupacion = o.id_ocupacion AND t.id_turno = ANY(:ids)
            """), {"fm": ahora, "ids": canc})
        llam = [{"it": t["id_turno"], "en": ll, "uid": uid} for t in pend for ll in t["llamados"]]
        if llam:
            await db.execute(text("""
                INSERT INTO turno_llamado (id_turno, puesto, llamado_en, id_usuario_llama,
                                           fecha_alta, fecha_modificacion, id_usuario_alta, id_usuario_modificacion)
                VALUES (:it, NULL, :en, :uid, :en, :en, :uid, :uid)
            """), llam)
        aten = [{"it": t["id_turno"], "ic": t["id_ciudadano"], "inter": t["atencion"]["intervencion"],
                 "reco": t["atencion"]["recomendaciones"], "isa": t["prestacion"].id_subarea,
                 "f": t["atencion"]["fecha"], "uid": uid} for t in pend if t["atencion"]]
        if aten:
            await db.execute(text("""
                INSERT INTO turno_atencion (id_turno, id_ciudadano, intervencion, recomendaciones,
                                            id_subarea, fecha_alta, fecha_modificacion, id_usuario_alta, id_usuario_modificacion)
                VALUES (:it, :ic, :inter, :reco, :isa, :f, :f, :uid, :uid)
                ON CONFLICT (id_turno) DO NOTHING
            """), aten)
        for t in pend:
            if t["envio"]:
                id_env = await db.scalar(text("""
                    INSERT INTO encuesta_envio (id_plantilla, id_ciudadano, id_turno, email_destino_snapshot,
                                                fecha_envio, fecha_apertura, fecha_completada, fecha_expiracion,
                                                estado, id_subarea, fecha_alta, fecha_modificacion, id_usuario_alta)
                    VALUES (:id_plantilla, :id_ciudadano, :it, :email, :fecha_envio, :fecha_apertura,
                            :fecha_completada, :fecha_expiracion, :estado, :id_subarea, :fecha_envio, :fecha_envio, :uid)
                    RETURNING id_encuesta_envio
                """), {**t["envio"], "it": t["id_turno"]})
                if t["respuesta"]:
                    await db.execute(demo_datos._SQL_INSERT_RESPUESTA, {**t["respuesta"], "id_envio": id_env})
        out["turnos"] = {"resueltos": len(pend),
                         "cumplidos": sum(1 for t in pend if t["estado"] == "cumplido"),
                         "ausentes": sum(1 for t in pend if t["estado"] == "ausente"),
                         "cancelados": len(canc)}

    # 2) Derivaciones demo pendientes de mas de un dia.
    r = await db.execute(text("""
        SELECT id_emergencia_atencion, id_emergencia_evento, derivado_en FROM emergencia_atencion
         WHERE activo IS DISTINCT FROM FALSE AND estado = 'pendiente' AND id_usuario_alta = :uid
           AND derivado_en < :lim
    """), {"uid": uid, "lim": ahora - timedelta(days=1)})
    for f in r.fetchall():
        atendida = rnd.random() < 0.85 and bool(cat.medicos)
        atendido = f.derivado_en + timedelta(minutes=rnd.uniform(8, 75))
        medico = rnd.choice(cat.medicos) if atendida else None
        await db.execute(text("""
            UPDATE emergencia_atencion
               SET estado = :es, intervencion = :i, recomendaciones = :r, id_agente_atiende = :ag,
                   atendido_en = :at, fecha_modificacion = :fm, id_usuario_modificacion = :uid
             WHERE id_emergencia_atencion = :id AND estado = 'pendiente'
        """), {"es": "atendida" if atendida else "ausente",
               "i": rnd.choice(INTERVENCIONES_GUARDIA) if atendida else None,
               "r": rnd.choice(RECOMENDACIONES) if atendida else None, "ag": medico,
               "at": atendido if atendida else None, "fm": atendido, "uid": uid, "id": f.id_emergencia_atencion})
        await db.execute(text("""
            INSERT INTO emergencia_log (id_evento, id_usuario, fecha_hora, tipo_accion, estado_anterior,
                                        estado_nuevo, payload_json, observaciones)
            VALUES (:e, :u, :fh, 'ATENCION_GUARDIA', 'EN_SITIO', 'EN_SITIO', CAST(:p AS jsonb), :o)
        """), {"e": f.id_emergencia_evento, "u": uid, "fh": atendido,
               "p": json.dumps({"id_emergencia_atencion": f.id_emergencia_atencion,
                                "resultado": "atendida" if atendida else "ausente", "id_agente_atiende": medico}),
               "o": "Atendido en la Guardia" if atendida else "No se presento en la Guardia"})
        est = cat.estados_emergencia
        if est.get("RESUELTO"):
            await db.execute(text("""
                UPDATE emergencia_evento SET id_estado = :es, fecha_hora_cierre = :c, veracidad = 'CONFIRMADA',
                       observaciones_cierre = 'Vecino derivado a la Guardia (demo).', fecha_modificacion = :c
                 WHERE id_emergencia_evento = :id AND id_usuario_alta = :uid AND fecha_hora_cierre IS NULL
            """), {"es": est["RESUELTO"], "c": atendido + timedelta(minutes=10), "id": f.id_emergencia_evento, "uid": uid})
        out["guardia"]["cerradas"] += 1

    # 3) Eventos demo pasados todavia 'activo' -> finalizado; reservas -> asistio.
    if cat.estado_evento.get("finalizado") and cat.estado_reserva.get("asistio"):
        r = await db.execute(text("""
            SELECT id_evento FROM eventos
             WHERE activo AND id_usuario_alta = :uid AND fecha < :hoy AND id_estado_evento = :act
        """), {"uid": uid, "hoy": hoy, "act": cat.estado_evento.get("activo")})
        ids = [f.id_evento for f in r.fetchall()]
        if ids:
            await db.execute(text("""
                UPDATE eventos SET id_estado_evento = :fin, fecha_modificacion = :ahora WHERE id_evento = ANY(:ids)
            """), {"fin": cat.estado_evento["finalizado"], "ahora": ahora, "ids": ids})
            r = await db.execute(text("""
                SELECT id_evento_reserva FROM evento_reservas
                 WHERE activo AND id_evento = ANY(:ids) AND id_estado_reserva = :res
            """), {"ids": ids, "res": cat.estado_reserva["reservada"]})
            asist = [f.id_evento_reserva for f in r.fetchall() if rnd.random() < 0.65]
            if asist:
                await db.execute(text("""
                    UPDATE evento_reservas SET id_estado_reserva = :a, fecha_modificacion = :ahora
                     WHERE id_evento_reserva = ANY(:ids)
                """), {"a": cat.estado_reserva["asistio"], "ahora": ahora, "ids": asist})
            out["eventos"] = {"finalizados": len(ids), "asistencias": len(asist)}

    await db.commit()
    return out
