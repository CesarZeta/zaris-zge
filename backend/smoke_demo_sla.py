# -*- coding: utf-8 -*-
"""Smoke de los datos demo SLA-aware (2026-10-21): reclamos con OT operativas,
tramites, cron diario idempotente y cierre del atraso. SOLO LOCAL.

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_demo_sla.py

Dos partes:

A) Endpoint real (httpx.ASGITransport, sin escrituras): modulos con 'tramites',
   modo 'cerrar_atraso' en dry-run (202 -> GET ok con conteos y la DB intacta),
   validaciones y marcadores de OpenAPI.

B) Servicios dentro de UNA transaccion que al final se REVIERTE (la DB local queda
   como estaba; los services commitean savepoints): simula el cron diario sobre
   enero-febrero 2026 (meses sin datos demo en local) con un "ahora" simulado, y
   verifica con SQL:
     (a) % dentro del SLA por mes en [60, 85] (reclamos y tramites, meses cerrados);
     (b) ~10 % de lo de las ultimas 3 semanas queda pendiente;
     (c) cada reclamo que paso por En gestion tiene UNA OT operativa coherente y
         ninguna OT demo tiene ocupacion en la Agenda;
     (d) 0 encuesta_envio 'pendiente' nuevas;
     (e) el cierre del atraso (con el reloj real) deja 0 pendientes de mas de 21
         dias (reclamos, tramites, emergencias) y es idempotente.
   Ademas: idempotencia por dia, ningun alta en el futuro, ledger de tramites
   monotono y ningun tramite demo pendiente en un estado que espera al vecino.

Mail en MOCK: settings.RESEND_API_KEY = "" (el .env.local tiene una key REAL;
igual ningun paso del generador manda mails).
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone

import httpx

os.environ.setdefault("ENV_FILE", ".env.local")

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.config import settings  # noqa: E402

settings.RESEND_API_KEY = ""  # MOCK: jamas un mail real desde el smoke

from app.core.database import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services import demo_atencion, demo_datos, demo_sla, demo_tramites  # noqa: E402

OK = 0
FAIL = 0
BASE = "/api/v1/demo/poblar"
UTC = timezone.utc


def check(nombre: str, cond: bool, detalle: str = "") -> None:
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  PASS  {nombre}" + (f"  [{detalle}]" if detalle else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {nombre}  {detalle}")


async def _escalar(db, sql: str, **p):
    return (await db.execute(text(sql), p)).scalar()


async def _conteos_db(db) -> dict:
    return {
        "reclamos_pend": await _escalar(db, "SELECT COUNT(*) FROM reclamos WHERE estado IN ('Sin asignar','En gestión','En espera')"),
        "tramites_abiertos": await _escalar(db, "SELECT COUNT(*) FROM tramite WHERE resultado = 'pendiente'"),
        "emerg_abiertas": await _escalar(db, "SELECT COUNT(*) FROM emergencia_evento e JOIN emergencia_estado s "
                                             "ON s.id_emergencia_estado = e.id_estado WHERE NOT s.es_terminal"),
        "ot": await _escalar(db, "SELECT COUNT(*) FROM ordenes_trabajo"),
        "movs": await _escalar(db, "SELECT COUNT(*) FROM tramite_movimiento"),
        "envios_pend": await _escalar(db, "SELECT COUNT(*) FROM encuesta_envio WHERE estado = 'pendiente'"),
    }


# ── A) endpoint ─────────────────────────────────────────────────────────────

async def parte_a() -> None:
    print("== A) endpoint (sin escrituras) ==")
    token = settings.DISPATCHER_TOKEN
    if not token:
        print("Falta DISPATCHER_TOKEN en .env.local")
        sys.exit(2)
    H = {"X-Dispatcher-Token": token}
    async with engine.connect() as conn:
        antes = await _conteos_db(conn)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=600) as c:
        r = await c.post(BASE, json={"modo": "cerrar_atraso"})
        check("cerrar_atraso sin auth -> 401", r.status_code == 401, str(r.status_code))
        r = await c.post(BASE, json={"modulos": ["no_existe"]}, headers=H)
        check("modulo desconocido -> 422", r.status_code == 422, str(r.status_code))
        r = await c.post(BASE, json={"modo": "otro"}, headers=H)
        check("modo desconocido -> 422", r.status_code == 422, str(r.status_code))
        r = await c.post(BASE, json={"generar": False, "avanzar": False, "modulos": ["tramites"]}, headers=H)
        check("modulos=['tramites'] aceptado -> 202", r.status_code == 202, f"{r.status_code} {r.text[:150]}")
        j = r.json() if r.status_code == 202 else {}
        ayer = date.today() - timedelta(days=1)
        check("rango por defecto = 7 dias completos hasta ayer",
              j.get("hasta") == str(ayer) and j.get("desde") == str(ayer - timedelta(days=6)),
              f"{j.get('desde')}..{j.get('hasta')}")
        idc = j.get("id_corrida", "")
        r = await c.get(f"{BASE}/{idc}", headers=H)
        check("corrida vacia termina ok", r.status_code == 200 and r.json().get("estado") == "ok", r.text[:150])

        t0 = time.monotonic()
        r = await c.post(BASE, json={"modo": "cerrar_atraso", "incluir_no_demo": True}, headers=H)
        check("cerrar_atraso (dry-run) -> 202 con modo y aplicar=false",
              r.status_code == 202 and r.json().get("modo") == "cerrar_atraso" and r.json().get("aplicar") is False,
              f"{r.status_code} {r.text[:200]}")
        idc = r.json().get("id_corrida", "") if r.status_code == 202 else ""
        r = await c.get(f"{BASE}/{idc}", headers=H)
        j = r.json()
        res = j.get("resultado") or {}
        check("dry-run termina ok con los 3 bloques",
              j.get("estado") == "ok" and {"atraso_reclamos", "atraso_tramites", "atraso_emergencias"} <= set(res)
              and res.get("aplicado") is False,
              f"estado={j.get('estado')} error={j.get('error')} claves={sorted(res)} ({time.monotonic() - t0:.0f} s)")
        ar, at, ae = res.get("atraso_reclamos", {}), res.get("atraso_tramites", {}), res.get("atraso_emergencias", {})
        print(f"     dry-run: reclamos a cerrar={ar.get('a_resuelto', 0) + ar.get('a_cancelado', 0)} "
              f"(evaluados {ar.get('evaluados')}, no demo {ar.get('no_demo')}), OT historicas a crear="
              f"{(ar.get('ot_historicas') or {}).get('ot_creadas')}, tramites={at.get('evaluados')} "
              f"(no demo {at.get('no_demo')}), emergencias={ae.get('evaluados')}")
    async with engine.connect() as conn:
        despues = await _conteos_db(conn)
    check("el dry-run no escribio nada", antes == despues, f"antes={antes} despues={despues}")

    spec = app.openapi()
    props = spec["components"]["schemas"]["PoblarIn"]["properties"]
    check("OpenAPI: PoblarIn.modo + 'tramites' en modulos (lo que mira el preflight del workflow)",
          "modo" in props and "tramites" in str(props.get("modulos")))


# ── B) servicios en una transaccion revertida ───────────────────────────────

SQL_MIX_RECLAMOS = """
    SELECT to_char(r.fecha_alta, 'YYYY-MM') AS mes,
           COUNT(*) FILTER (WHERE r.estado IN ('Resuelto','En auditoría','Auditado') AND tr.sla_minutos IS NOT NULL) AS cerrados,
           COUNT(*) FILTER (WHERE r.estado IN ('Resuelto','En auditoría','Auditado') AND tr.sla_minutos IS NOT NULL
                AND r.fecha_cierre - r.fecha_alta <= make_interval(mins => tr.sla_minutos)) AS dentro,
           COUNT(*) FILTER (WHERE r.estado IN ('Sin asignar','En gestión','En espera')) AS pendientes
      FROM reclamos r JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
     WHERE r.id_usuario_alta = :uid AND r.fecha_alta >= '2026-01-01' AND r.fecha_alta < '2026-03-01'
     GROUP BY 1 ORDER BY 1
"""
SQL_MIX_TRAMITES = """
    SELECT to_char(t.fecha_alta, 'YYYY-MM') AS mes,
           COUNT(*) FILTER (WHERE e.es_final) AS cerrados,
           COUNT(*) FILTER (WHERE e.es_final AND FLOOR(EXTRACT(EPOCH FROM (t.fecha_entrada_estado_actual - t.fecha_alta))
                / 86400.0) <= COALESCE(NULLIF(tt.sla_dias, 0), 30)) AS dentro,
           COUNT(*) FILTER (WHERE NOT e.es_final) AS pendientes
      FROM tramite t
      JOIN tipo_tramite_estado e ON e.id_tipo_tramite_estado = t.id_tipo_tramite_estado_actual
      JOIN tipo_tramite_version v ON v.id_tipo_tramite_version = t.id_tipo_tramite_version
      JOIN tipo_tramite tt ON tt.id_tipo_tramite = v.id_tipo_tramite
     WHERE t.id_usuario_alta = :uid AND t.fecha_alta >= '2026-01-01' AND t.fecha_alta < '2026-03-01'
     GROUP BY 1 ORDER BY 1
"""


async def _cron(db, ahora: datetime, generar: bool = True) -> dict:
    """Lo que hace el cron diario: genera los 7 dias completos hasta ayer y avanza."""
    hoy = ahora.date()
    out = {}
    if generar:
        out["r"] = await demo_datos.generar_periodo(db, hoy - timedelta(days=7), hoy - timedelta(days=1), ahora=ahora)
        out["t"] = await demo_tramites.generar_periodo_tramites(db, hoy - timedelta(days=7), hoy - timedelta(days=1),
                                                                ahora=ahora)
    out["ar"] = await demo_datos.avanzar_pendientes(db, ahora=ahora)
    out["at"] = await demo_tramites.avanzar_pendientes_tramites(db, ahora=ahora)
    return out


async def _pendientes_recientes(db, uid: int, ahora: datetime) -> tuple[float, float, int, int]:
    d0 = ahora - timedelta(days=21)
    r = (await db.execute(text("""
        SELECT COUNT(*) AS tot, COUNT(*) FILTER (WHERE estado IN ('Sin asignar','En gestión','En espera')) AS pend
          FROM reclamos WHERE id_usuario_alta = :uid AND fecha_alta >= :d0 AND fecha_alta <= :a
    """), {"uid": uid, "d0": d0, "a": ahora})).fetchone()
    t = (await db.execute(text("""
        SELECT COUNT(*) AS tot, COUNT(*) FILTER (WHERE NOT e.es_final) AS pend FROM tramite tr
          JOIN tipo_tramite_estado e ON e.id_tipo_tramite_estado = tr.id_tipo_tramite_estado_actual
         WHERE tr.id_usuario_alta = :uid AND tr.fecha_alta >= :d0 AND tr.fecha_alta <= :a
    """), {"uid": uid, "d0": d0, "a": ahora})).fetchone()
    return (r.pend / r.tot if r.tot else 0.0, t.pend / t.tot if t.tot else 0.0, r.tot, t.tot)


async def parte_b() -> None:
    print("== B) servicios (transaccion revertida al final) ==")
    async with engine.connect() as conn:
        trans = await conn.begin()
        db = AsyncSession(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
        try:
            uid = await demo_datos._usuario_generador(db)
            previos = await _escalar(db, """
                SELECT (SELECT COUNT(*) FROM reclamos WHERE id_usuario_alta = :u AND fecha_alta >= '2026-01-01'
                         AND fecha_alta < '2026-03-01')
                     + (SELECT COUNT(*) FROM tramite WHERE id_usuario_alta = :u AND fecha_alta >= '2026-01-01'
                         AND fecha_alta < '2026-03-01')""", u=uid)
            check("precondicion: ene-feb 2026 sin datos demo en local", previos == 0, str(previos))
            envios_pend0 = await _escalar(db, "SELECT COUNT(*) FROM encuesta_envio WHERE estado = 'pendiente'")
            # Desorden de historial PREEXISTENTE en los datos demo viejos (pasos de la auditoria
            # previa al cierre, anteriores a la mig 112): el generador no debe agregar mas.
            sql_desorden = """
                SELECT COUNT(*) FROM (
                  SELECT h.fecha_alta, LAG(h.fecha_alta) OVER (PARTITION BY h.id_reclamo ORDER BY h.id_historial) AS prev
                    FROM reclamo_historial h JOIN reclamos r ON r.id_reclamo = h.id_reclamo
                   WHERE r.id_usuario_alta = :u) x WHERE prev IS NOT NULL AND fecha_alta < prev"""
            desorden0 = await _escalar(db, sql_desorden, u=uid)
            max_ot0 = await _escalar(db, "SELECT COALESCE(MAX(id_ot), 0) FROM ordenes_trabajo")
            max_rec0 = await _escalar(db, "SELECT COALESCE(MAX(id_reclamo), 0) FROM reclamos")
            t0 = time.monotonic()

            # 1) Carga inicial (catch-up) 1/1 .. 14/2 con el reloj del 15/2 08:20.
            ahora = datetime(2026, 2, 15, 8, 20, tzinfo=UTC)
            g1 = await demo_datos.generar_periodo(db, date(2026, 1, 1), date(2026, 2, 14), semilla=11, ahora=ahora)
            g2 = await demo_tramites.generar_periodo_tramites(db, date(2026, 1, 1), date(2026, 2, 14), semilla=11,
                                                              ahora=ahora)
            print(f"     carga inicial: {g1['reclamos']} reclamos ({g1['ot_operativas']} OT, origen {g1['ot_por_origen']}),"
                  f" {g2['tramites']} tramites ({g2['movimientos']} movimientos)")
            check("carga inicial genero reclamos y tramites", g1["reclamos"] > 300 and g2["tramites"] > 50,
                  f"{g1['reclamos']} / {g2['tramites']}")
            # 2) Cron diario 15/2 .. 28/2 (08:20 UTC): genera ayer + avanza.
            nuevos_por_dia = []
            for i in range(14):
                ahora = datetime(2026, 2, 15, 8, 20, tzinfo=UTC) + timedelta(days=i)
                out = await _cron(db, ahora)
                nuevos_por_dia.append(out["r"]["reclamos"])
            # Re-correr el ultimo dia: no agrega nada (idempotente por dia).
            rep = await _cron(db, ahora)
            check("cron repetido el mismo dia: 0 reclamos y 0 tramites nuevos",
                  rep["r"]["reclamos"] == 0 and rep["t"]["tramites"] == 0
                  and rep["r"]["dias_omitidos_con_demo"] == 7,
                  f"{rep['r']['reclamos']} / {rep['t']['tramites']} omitidos={rep['r']['dias_omitidos_con_demo']}")
            check("cada corrida diaria agrego un solo dia (sin duplicar)",
                  all(0 < n < 40 for n in nuevos_por_dia[1:]), str(nuevos_por_dia))
            futuro = await _escalar(db, """
                SELECT (SELECT COUNT(*) FROM reclamos WHERE id_usuario_alta = :u AND fecha_alta > :a AND fecha_alta < '2026-03-01')
                     + (SELECT COUNT(*) FROM tramite WHERE id_usuario_alta = :u AND fecha_alta > :a AND fecha_alta < '2026-03-01')
            """, u=uid, a=ahora)
            check("ningun alta posterior al 'ahora' simulado", futuro == 0, str(futuro))

            # (b) pendientes de las ultimas 3 semanas (al 28/2 08:20).
            pr, pt, nr, nt = await _pendientes_recientes(db, uid, ahora)
            check("(b) reclamos: ~10 % de lo de las ultimas 3 semanas pendiente (5-16 %)", 0.05 <= pr <= 0.16,
                  f"{pr:.1%} de {nr}")
            check("(b) tramites: pendientes de las ultimas 3 semanas (5-25 %)", 0.05 <= pt <= 0.25, f"{pt:.1%} de {nt}")
            viejos = await _escalar(db, """
                SELECT COUNT(*) FROM reclamos WHERE id_usuario_alta = :u AND fecha_alta < :d
                   AND fecha_alta >= '2026-01-01' AND estado IN ('Sin asignar','En gestión','En espera')""",
                                    u=uid, d=ahora - timedelta(days=21))
            check("lo de mas de 3 semanas ya esta cerrado (reclamos)", viejos == 0, str(viejos))
            espera_ini = await _escalar(db, """
                SELECT COUNT(*) FROM tramite t JOIN tipo_tramite_estado e
                    ON e.id_tipo_tramite_estado = t.id_tipo_tramite_estado_actual
                 WHERE t.id_usuario_alta = :u AND e.espera_iniciador AND NOT e.es_final""", u=uid)
            check("ningun tramite demo pendiente en un estado que espera al vecino (sin mails de desistimiento)",
                  espera_ini == 0, str(espera_ini))

            # 3) El cron sigue (sin generar) hasta el 20/3: enero y febrero quedan cerrados.
            for i in range(1, 21):
                await _cron(db, datetime(2026, 2, 28, 8, 20, tzinfo=UTC) + timedelta(days=i), generar=False)
            fin_sim = datetime(2026, 3, 20, 8, 20, tzinfo=UTC)

            # (a) mezcla de SLA por mes.
            for etiqueta, sql, modulo in (("reclamos", SQL_MIX_RECLAMOS, "reclamos"), ("tramites", SQL_MIX_TRAMITES, "tramites")):
                for f in (await db.execute(text(sql), {"uid": uid})).fetchall():
                    anio, mes = int(f.mes[:4]), int(f.mes[5:])
                    pct = f.dentro / f.cerrados if f.cerrados else 0
                    p = demo_sla.p_mes(modulo, anio, mes)
                    check(f"(a) {etiqueta} {f.mes}: % dentro del SLA en [60, 85]",
                          0.60 <= pct <= 0.85 and f.pendientes == 0,
                          f"{pct:.1%} ({f.dentro}/{f.cerrados}, objetivo {p:.1%}, pendientes {f.pendientes})")

            # (c) OT operativas coherentes y sin ocupaciones.
            inco = (await db.execute(text("""
                WITH ot AS (
                    SELECT o.id_reclamo, COUNT(*) AS n, MIN(eo.nombre) AS estado_ot, MIN(o.fecha_cierre) AS cierre_ot,
                           BOOL_AND(o.id_agente IS NOT NULL OR o.id_equipo IS NOT NULL) AS asignada,
                           BOOL_AND((o.id_supervisor_asigna IS NULL) = o.asignacion_automatica) AS sup_ok
                      FROM ordenes_trabajo o JOIN estado_ot eo ON eo.id_estado_ot = o.id_estado
                     WHERE o.activo AND NOT o.es_auditoria GROUP BY o.id_reclamo)
                SELECT
                  COUNT(*) FILTER (WHERE r.fecha_primer_asignacion IS NOT NULL AND ot.n IS NULL) AS sin_ot,
                  COUNT(*) FILTER (WHERE ot.n > 1) AS ot_duplicada,
                  COUNT(*) FILTER (WHERE ot.n = 1 AND NOT (
                       (r.estado IN ('Resuelto','En auditoría','Auditado') AND ot.estado_ot = 'Terminada' AND ot.cierre_ot = r.fecha_cierre)
                    OR (r.estado = 'Cancelado' AND ot.estado_ot = 'Cancelada')
                    OR (r.estado = 'En gestión' AND ot.estado_ot = 'En gestión' AND ot.cierre_ot IS NULL)
                    OR (r.estado = 'En espera' AND ot.estado_ot = 'En espera' AND ot.cierre_ot IS NULL))) AS estado_incoherente,
                  COUNT(*) FILTER (WHERE ot.n = 1 AND NOT ot.asignada) AS sin_destinatario,
                  COUNT(*) FILTER (WHERE ot.n = 1 AND NOT ot.sup_ok) AS supervisor_incoherente,
                  COUNT(*) FILTER (WHERE r.estado IN ('En gestión','En espera','Resuelto','En auditoría','Auditado')) AS con_gestion
                  FROM reclamos r LEFT JOIN ot ON ot.id_reclamo = r.id_reclamo
                 WHERE r.id_usuario_alta = :u AND r.id_reclamo > :m
            """), {"u": uid, "m": max_rec0})).fetchone()
            check("(c) todo reclamo que paso por En gestion tiene su OT operativa (una sola)",
                  inco.sin_ot == 0 and inco.ot_duplicada == 0,
                  f"sin_ot={inco.sin_ot} duplicadas={inco.ot_duplicada} de {inco.con_gestion}")
            check("(c) estado de la OT coherente con el reclamo (Terminada con su fecha de cierre, etc.)",
                  inco.estado_incoherente == 0, f"incoherentes={inco.estado_incoherente}")
            check("(c) OT con destinatario y supervisor/automatica coherentes",
                  inco.sin_destinatario == 0 and inco.supervisor_incoherente == 0,
                  f"sin destinatario={inco.sin_destinatario} supervisor={inco.supervisor_incoherente}")
            dest = (await db.execute(text("""
                SELECT COUNT(*) FILTER (WHERE o.id_agente IS NOT NULL AND (u.nivel_acceso NOT BETWEEN 2 AND 4
                                        OR NOT ag.activo OR ag.es_auditor)) AS invalidos,
                       COUNT(*) FILTER (WHERE o.id_agente IS NOT NULL AND u.nivel_acceso = 4
                                        AND ag.id_subarea = tr.id_subarea) AS de_la_gestion,
                       COUNT(*) AS total
                  FROM ordenes_trabajo o JOIN reclamos r ON r.id_reclamo = o.id_reclamo
                  JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
                  LEFT JOIN agentes ag ON ag.id_agente = o.id_agente
                  LEFT JOIN usuarios u ON u.id_usuario = ag.id_usuario
                 WHERE o.id_ot > :m AND NOT o.es_auditoria
            """), {"m": max_ot0})).fetchone()
            check("(c) las OT van a agentes operativos (nivel 2-4, activos, no auditores)", dest.invalidos == 0,
                  f"invalidos={dest.invalidos}; de nivel 4 de la gestion del tipo: {dest.de_la_gestion}/{dest.total}"
                  " (el resto: fallback, la DB local casi no tiene agentes)")
            ocup = await _escalar(db, """
                SELECT COUNT(*) FROM ocupaciones oc JOIN ordenes_trabajo o ON o.id_ot = oc.id_orden_trabajo
                 WHERE o.id_ot > :m""", m=max_ot0)
            check("(c) ninguna OT demo tiene ocupacion en la Agenda", ocup == 0, str(ocup))
            hist = await _escalar(db, """
                SELECT COUNT(*) FROM (
                  SELECT id_reclamo, fecha_alta, LAG(fecha_alta) OVER (PARTITION BY id_reclamo ORDER BY id_historial) AS prev
                    FROM reclamo_historial WHERE id_reclamo > :m) x WHERE prev IS NOT NULL AND fecha_alta < prev""", m=max_rec0)
            check("historial de cada reclamo en orden cronologico", hist == 0, str(hist))
            fechas = await _escalar(db, """
                SELECT COUNT(*) FROM reclamos WHERE id_reclamo > :m AND (
                       fecha_primer_asignacion < fecha_alta OR fecha_cierre < fecha_alta
                    OR fecha_cierre < fecha_primer_asignacion OR fecha_cierre > :f)""", m=max_rec0, f=fin_sim)
            check("fechas del reclamo coherentes (alta <= asignacion <= cierre <= ahora)", fechas == 0, str(fechas))
            ledger = await _escalar(db, """
                SELECT COUNT(*) FROM (
                  SELECT m.id_tramite, m.orden_secuencial, m.fecha_alta,
                         LAG(m.fecha_alta) OVER (PARTITION BY m.id_tramite ORDER BY m.orden_secuencial) AS prev,
                         LAG(m.orden_secuencial) OVER (PARTITION BY m.id_tramite ORDER BY m.orden_secuencial) AS prev_o
                    FROM tramite_movimiento m JOIN tramite t ON t.id_tramite = m.id_tramite
                   WHERE t.id_usuario_alta = :u AND t.fecha_alta < '2026-03-01') x
                 WHERE prev IS NOT NULL AND (fecha_alta < prev OR orden_secuencial <> prev_o + 1)""", u=uid)
            check("ledger de tramites append-only: orden 1..n y fechas monotonas", ledger == 0, str(ledger))
            sin_res = await _escalar(db, """
                SELECT COUNT(*) FROM tramite t JOIN tipo_tramite_estado e ON e.id_tipo_tramite_estado = t.id_tipo_tramite_estado_actual
                 WHERE t.id_usuario_alta = :u AND e.es_final AND t.resultado = 'pendiente' AND t.fecha_alta < '2026-03-01'""", u=uid)
            res = (await db.execute(text("""
                SELECT COUNT(*) FILTER (WHERE resultado = 'aprobado') AS apr, COUNT(*) FILTER (WHERE resultado = 'rechazado') AS rech
                  FROM tramite WHERE id_usuario_alta = :u AND fecha_alta < '2026-03-01'"""), {"u": uid})).fetchone()
            check("tramites terminados con resultado aprobado/rechazado", sin_res == 0 and res.apr > res.rech > 0,
                  f"sin resultado={sin_res} aprobados={res.apr} rechazados={res.rech}")

            # (d) encuestas.
            envios_pend = await _escalar(db, "SELECT COUNT(*) FROM encuesta_envio WHERE estado = 'pendiente'")
            check("(d) 0 encuesta_envio 'pendiente' nuevas", envios_pend == envios_pend0, f"{envios_pend0} -> {envios_pend}")

            # (e) cierre del atraso con el reloj real (los datos locales viejos de mar-oct).
            ahora_real = datetime.now(UTC)
            limite = ahora_real - timedelta(days=21)
            # IT-01: el cierre del atraso es SOLO del municipio demo; lo de otros
            # municipios (la fixture de aislamiento) queda como estaba.
            mun_demo = await demo_datos.municipio_demo(db)

            async def _quedan(op: str):
                return (await db.execute(text(f"""
                    SELECT (SELECT COUNT(*) FROM reclamos WHERE activo AND fecha_alta < :l
                              AND estado IN ('Sin asignar','En gestión','En espera') AND id_municipio {op} :m) AS reclamos,
                           (SELECT COUNT(*) FROM tramite WHERE activo AND fecha_alta < :l AND resultado = 'pendiente'
                              AND fecha_archivado IS NULL AND id_municipio {op} :m) AS tramites,
                           (SELECT COUNT(*) FROM emergencia_evento e JOIN emergencia_estado s ON s.id_emergencia_estado = e.id_estado
                             WHERE e.activo AND NOT s.es_terminal AND e.fecha_hora_recepcion < :l
                               AND e.id_municipio {op} :m) AS emergencias
                """), {"l": limite, "m": mun_demo})).fetchone()

            otros_antes = tuple(await _quedan("<>"))
            dr = {
                "t": await demo_tramites.cerrar_atraso_tramites(db, aplicar=False, incluir_no_demo=True),
                "e": await demo_atencion.cerrar_atraso_emergencias(db, aplicar=False, incluir_no_demo=True),
                "r": await demo_datos.cerrar_atraso_reclamos(db, aplicar=False, incluir_no_demo=True),
            }
            print(f"     atraso (dry-run): reclamos {dr['r']['evaluados']} (no demo {dr['r']['no_demo']}), "
                  f"OT historicas {dr['r']['ot_historicas']['ot_creadas']}, tramites {dr['t']['evaluados']} "
                  f"(no demo {dr['t']['no_demo']}), emergencias {dr['e']['evaluados']}")
            ap = {
                "t": await demo_tramites.cerrar_atraso_tramites(db, aplicar=True, incluir_no_demo=True),
                "e": await demo_atencion.cerrar_atraso_emergencias(db, aplicar=True, incluir_no_demo=True),
                "r": await demo_datos.cerrar_atraso_reclamos(db, aplicar=True, incluir_no_demo=True),
            }
            check("(e) el dry-run anticipa lo que aplica",
                  dr["r"]["a_resuelto"] == ap["r"]["a_resuelto"] and dr["t"]["evaluados"] == ap["t"]["evaluados"]
                  and dr["e"]["evaluados"] == ap["e"]["evaluados"]
                  and dr["r"]["ot_historicas"]["ot_creadas"] == ap["r"]["ot_historicas"]["ot_creadas"],
                  f"reclamos {dr['r']['a_resuelto']}/{ap['r']['a_resuelto']} tramites {dr['t']['evaluados']}/"
                  f"{ap['t']['evaluados']} emergencias {dr['e']['evaluados']}/{ap['e']['evaluados']} OT historicas "
                  f"{dr['r']['ot_historicas']['ot_creadas']}/{ap['r']['ot_historicas']['ot_creadas']}")
            quedan = await _quedan("=")
            check("(e) el cierre del atraso deja 0 pendientes de mas de 21 dias en el municipio demo",
                  quedan.reclamos == 0 and quedan.tramites == 0 and quedan.emergencias == 0,
                  f"reclamos={quedan.reclamos} tramites={quedan.tramites} emergencias={quedan.emergencias}")
            otros = tuple(await _quedan("<>"))
            check("(e) los pendientes de otros municipios no se tocan", otros == otros_antes,
                  f"(reclamos, tramites, emergencias) {otros_antes} -> {otros}")
            sin_ot = await _escalar(db, """
                SELECT COUNT(*) FROM reclamos r WHERE r.activo AND r.id_usuario_alta = :u
                   AND r.fecha_primer_asignacion IS NOT NULL AND NOT EXISTS (
                       SELECT 1 FROM ordenes_trabajo o WHERE o.id_reclamo = r.id_reclamo AND o.activo AND NOT o.es_auditoria)""",
                                   u=uid)
            check("(e) completar_ot: ningun reclamo demo que paso por En gestion queda sin OT", sin_ot == 0, str(sin_ot))
            dr2 = {
                "t": await demo_tramites.cerrar_atraso_tramites(db, aplicar=False, incluir_no_demo=True),
                "e": await demo_atencion.cerrar_atraso_emergencias(db, aplicar=False, incluir_no_demo=True),
                "r": await demo_datos.cerrar_atraso_reclamos(db, aplicar=False, incluir_no_demo=True),
            }
            check("(e) idempotente: una segunda corrida no encuentra nada",
                  dr2["r"]["evaluados"] == 0 and dr2["t"]["evaluados"] == 0 and dr2["e"]["evaluados"] == 0
                  and dr2["r"]["ot_historicas"]["ot_creadas"] == 0,
                  f"{dr2['r']['evaluados']}/{dr2['t']['evaluados']}/{dr2['e']['evaluados']}")
            envios_pend = await _escalar(db, "SELECT COUNT(*) FROM encuesta_envio WHERE estado = 'pendiente'")
            check("(d) tras el atraso: 0 encuesta_envio 'pendiente' nuevas", envios_pend == envios_pend0,
                  f"{envios_pend0} -> {envios_pend}")

            # Rebalanceo historico (opt-in): meses viejos < 60 % llevados a su objetivo.
            rb_dry = await demo_datos.rebalancear_sla_historico(db, uid, aplicar=False)
            rb = await demo_datos.rebalancear_sla_historico(db, uid, aplicar=True)
            print("     rebalanceo:", {m: (v["antes"], v["despues"], v["objetivo"]) for m, v in rb["meses"].items()})
            check("rebalanceo: dry-run = aplicar", rb_dry["reclamos_adelantados"] == rb["reclamos_adelantados"],
                  f"{rb_dry['reclamos_adelantados']} / {rb['reclamos_adelantados']}")
            fuera_rango = []
            for f in (await db.execute(text("""
                SELECT to_char(r.fecha_alta AT TIME ZONE 'UTC', 'YYYY-MM') AS mes,
                       COUNT(*) FILTER (WHERE r.estado IN ('Resuelto','En auditoría','Auditado') AND tr.sla_minutos IS NOT NULL) AS c,
                       COUNT(*) FILTER (WHERE r.estado IN ('Resuelto','En auditoría','Auditado') AND tr.sla_minutos IS NOT NULL
                            AND r.fecha_cierre - r.fecha_alta <= make_interval(mins => tr.sla_minutos)) AS d,
                       COUNT(*) FILTER (WHERE r.estado IN ('Sin asignar','En gestión','En espera')) AS p
                  FROM reclamos r JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
                 WHERE r.id_usuario_alta = :u GROUP BY 1 ORDER BY 1"""), {"u": uid})).fetchall():
                if f.c and not f.p and not (0.60 <= f.d / f.c <= 0.85):
                    fuera_rango.append(f"{f.mes}: {f.d / f.c:.1%}")
            check("rebalanceo: todo mes demo cerrado queda en [60, 85] dentro del SLA", not fuera_rango, str(fuera_rango))
            rb2 = await demo_datos.rebalancear_sla_historico(db, uid, aplicar=False)
            check("rebalanceo idempotente", rb2["reclamos_adelantados"] == 0, str(rb2["reclamos_adelantados"]))
            hist = await _escalar(db, sql_desorden, u=uid)
            ot_mal = await _escalar(db, """
                SELECT COUNT(*) FROM reclamos r JOIN ordenes_trabajo o ON o.id_reclamo = r.id_reclamo
                   AND o.activo AND NOT o.es_auditoria
                 WHERE r.id_usuario_alta = :u AND r.estado IN ('Resuelto','En auditoría','Auditado')
                   AND o.fecha_cierre IS DISTINCT FROM r.fecha_cierre""", u=uid)
            check("tras rebalanceo + atraso: ningun historial demo nuevo fuera de orden y OT con el cierre del reclamo",
                  hist == desorden0 and ot_mal == 0,
                  f"historial desordenado {desorden0} (preexistente) -> {hist}; OT con otro cierre={ot_mal}")
            ocup = await _escalar(db, """
                SELECT COUNT(*) FROM ocupaciones oc JOIN ordenes_trabajo o ON o.id_ot = oc.id_orden_trabajo
                 WHERE o.id_ot > :m""", m=max_ot0)
            check("(c) tras el atraso: ninguna OT nueva con ocupacion", ocup == 0, str(ocup))
            print(f"     parte B: {time.monotonic() - t0:.0f} s")
        finally:
            await db.close()
            await trans.rollback()
    async with engine.connect() as conn:
        resto = await _escalar(conn, """SELECT COUNT(*) FROM reclamos WHERE id_usuario_alta = :u
                                          AND fecha_alta >= '2026-01-01' AND fecha_alta < '2026-03-01'""", u=uid)
    check("rollback: la DB local quedo como estaba", resto == 0, str(resto))


async def main() -> None:
    await parte_a()
    await parte_b()
    print(f"\n{OK} OK / {FAIL} FAIL")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())
