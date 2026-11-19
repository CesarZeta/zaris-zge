"""Encuestas demo que los generadores de cada módulo no cargaban (2026-11-19, pedido de César).

- ENTRADAS: el generador de eventos acredita reservas (`asistio`) pero no las encuestaba, así que
  Encuestas → Resumen mostraba Entradas vacío. `encuestar_entradas` crea el envío de cada reserva
  demo acreditada que no lo tiene, como hace el disparo real al acreditar (`crear_envio_para_entrada`),
  y responde una parte de los ya vencidos. Las vivas las madura `demo_datos.avanzar_pendientes`, que
  ya recorre los envíos del usuario generador sin mirar el circuito.
- MOTIVOS: las respuestas demo se guardaban sin detalle, así que el Resumen no tenía motivos que
  sumar (en prod: 16 detalles para 2210 respuestas). `completar_motivos` le carga a cada respuesta
  demo sin detalle el motivo de su rama (la pregunta de opción múltiple), con pesos fijos.

Las dos son idempotentes y determinísticas: el sorteo sale del id de la fila (no de un RNG
compartido), así que repetirlas no cambia lo ya cargado ni sortea distinto lo pendiente. Tocan SOLO
filas del usuario generador (`id_usuario_alta`); una respuesta real tiene ese campo vacío y siempre
trae detalle, así que nunca entra. Como el resto del generador: nunca un envío 'pendiente' (el
dispatcher mandaría un mail).
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import demo_atencion, demo_datos

# Porción de reservas acreditadas que reciben la encuesta (el resto: sin email válido o
# anti-fatiga, como en la realidad) y de los envíos ya vencidos que quedan respondidos.
PCT_ENCUESTADAS = 0.70
PCT_RESPONDIDAS_VENCIDAS = 0.30
LOTE = 400

# Pesos de cada motivo por rama. Valores = los de la encuesta estándar (mig 136).
PESOS_MOTIVOS = {
    "insatisfechos": {"demora": 34, "no_resuelto": 26, "mala_comunicacion": 14, "solucion_incorrecta": 12,
                      "mal_trato": 7, "otro": 7},
    "neutrales": {"mas_rapidez": 36, "mas_informacion": 24, "mejor_comunicacion": 18, "mejor_solucion": 14,
                  "otro": 8},
    "satisfechos": {"rapidez": 31, "trato": 29, "claridad": 19, "calidad": 15, "otro": 6},
}
_VALORES_EXPECTATIVA = ["si", "parcialmente", "no"]


async def encuestar_entradas(db: AsyncSession, id_municipio: int, uid: int,
                             ahora: datetime | None = None) -> dict:
    ahora = ahora or datetime.now(timezone.utc)
    n = {"envios": 0, "respondidas": 0}
    id_plantilla = await db.scalar(text(
        "SELECT id_encuesta_plantilla FROM encuesta_plantilla WHERE tipo = 'entradas' AND activo "
        "AND id_municipio = :mun ORDER BY id_encuesta_plantilla LIMIT 1"), {"mun": id_municipio})
    if not id_plantilla:
        return {**n, "omitido": "sin plantilla de entradas"}
    filas = (await db.execute(text("""
        SELECT er.id_evento_reserva, er.id_ciudadano, c.email, ev.fecha, ev.hora_fin, ev.id_subarea
          FROM evento_reservas er
          JOIN eventos ev         ON ev.id_evento = er.id_evento
          JOIN estado_reserva es  ON es.id_estado_reserva = er.id_estado_reserva AND es.codigo = 'asistio'
          JOIN ciudadanos c       ON c.id_ciudadano = er.id_ciudadano
         WHERE er.id_municipio = :mun AND er.id_usuario_alta = :uid
           AND er.activo IS DISTINCT FROM FALSE
           AND COALESCE(c.email, '') <> ''
           AND NOT EXISTS (SELECT 1 FROM encuesta_envio x WHERE x.id_evento_reserva = er.id_evento_reserva)
         ORDER BY er.id_evento_reserva
    """), {"mun": id_municipio, "uid": uid})).fetchall()

    envios: list[dict] = []
    respuestas: dict[int, dict] = {}
    for f in filas:
        rnd = random.Random(f"entrada-encuesta:{f.id_evento_reserva}")
        if rnd.random() >= PCT_ENCUESTADAS:
            continue  # sale igual en cada corrida: esa reserva queda sin encuesta
        fin = demo_atencion._a_utc(f.fecha, f.hora_fin)
        fecha_envio = fin + timedelta(days=1, hours=rnd.uniform(0, 6))
        if fecha_envio > ahora - timedelta(hours=1):
            continue  # todavía no salió (el disparo real también espera 24 h): la toma otra corrida
        expiracion = fecha_envio + timedelta(days=15)
        envio = {"id_plantilla": id_plantilla, "id_ciudadano": f.id_ciudadano, "er": f.id_evento_reserva,
                 "email": f.email, "fecha_envio": fecha_envio, "fecha_apertura": None,
                 "fecha_completada": None, "fecha_expiracion": expiracion,
                 "estado": "enviada" if expiracion > ahora else "expirada",
                 "id_subarea": f.id_subarea, "uid": uid}
        if envio["estado"] == "expirada" and rnd.random() < PCT_RESPONDIDAS_VENCIDAS:
            apertura = fecha_envio + timedelta(hours=rnd.uniform(1, 72))
            completada = apertura + timedelta(minutes=rnd.uniform(2, 25))
            clasificacion = demo_datos._elegir(rnd, demo_datos.SCORES)
            envio.update({"estado": "completada", "fecha_apertura": apertura, "fecha_completada": completada})
            respuestas[f.id_evento_reserva] = {
                "clasificacion": clasificacion, "rama": demo_datos._rama(clasificacion),
                "tiempo": rnd.randint(45, 420), "id_subarea": f.id_subarea, "fecha": completada, "uid": uid}
        envios.append(envio)

    cols = ["id_plantilla", "id_ciudadano", "er", "email", "fecha_envio", "fecha_apertura",
            "fecha_completada", "fecha_expiracion", "estado", "id_subarea", "uid"]
    for i in range(0, len(envios), LOTE):
        lote = envios[i:i + LOTE]
        vals, params = demo_atencion._values(lote, cols, "e")
        params["mun"] = id_municipio
        r = await db.execute(text(f"""
            INSERT INTO encuesta_envio (id_plantilla, id_ciudadano, id_evento_reserva, email_destino_snapshot,
                                        fecha_envio, fecha_apertura, fecha_completada, fecha_expiracion,
                                        estado, id_subarea, fecha_alta, fecha_modificacion, id_usuario_alta,
                                        id_municipio)
            SELECT v.id_plantilla, v.id_ciudadano, v.er, v.email, v.fecha_envio, v.fecha_apertura,
                   v.fecha_completada, v.fecha_expiracion, v.estado, v.id_subarea, v.fecha_envio, v.fecha_envio,
                   v.uid, CAST(:mun AS int)
              FROM (VALUES {vals}) AS v({', '.join(cols)})
            RETURNING id_encuesta_envio, id_evento_reserva
        """), params)
        por_reserva = {int(x.id_evento_reserva): int(x.id_encuesta_envio) for x in r.fetchall()}
        n["envios"] += len(por_reserva)
        resp = [{**respuestas[k], "id_envio": v} for k, v in por_reserva.items() if k in respuestas]
        if resp:
            await db.execute(demo_datos._SQL_INSERT_RESPUESTA, resp)
            n["respondidas"] += len(resp)
    await db.commit()
    return n


def _sql_pesos() -> str:
    """CASE (rama, valor) -> peso; un valor sin peso (agregado después) pesa 5."""
    casos = " ".join(f"WHEN pr.rama = '{rama}' AND op.valor = '{valor}' THEN {peso}"
                     for rama, pesos in PESOS_MOTIVOS.items() for valor, peso in pesos.items())
    return f"CASE {casos} ELSE 5 END"


async def completar_motivos(db: AsyncSession, id_municipio: int, uid: int) -> dict:
    """Un detalle por respuesta demo sin detalle: la opción elegida en la pregunta de opción múltiple
    de su rama. El sorteo es una función del id de la respuesta (multiplicativo módulo 1000)."""
    r = await db.execute(text(f"""
        WITH pend AS (
            SELECT rsp.id_encuesta_respuesta AS id_resp, rsp.rama_seguida AS rama, ee.id_plantilla,
                   rsp.id_subarea, rsp.fecha_alta, rsp.id_usuario_alta,
                   ((rsp.id_encuesta_respuesta::bigint * 761) % 1000) / 1000.0 AS sorteo
              FROM encuesta_respuesta rsp
              JOIN encuesta_envio ee ON ee.id_encuesta_envio = rsp.id_envio
             WHERE rsp.id_municipio = :mun AND rsp.activo AND rsp.id_usuario_alta = :uid
               AND NOT EXISTS (SELECT 1 FROM encuesta_respuesta_detalle d
                                WHERE d.id_respuesta = rsp.id_encuesta_respuesta)
        ), opc AS (
            SELECT pr.id_plantilla, pr.rama, pr.id_encuesta_pregunta AS id_preg,
                   op.id_encuesta_opcion AS id_op,
                   SUM({_sql_pesos()}) OVER (PARTITION BY pr.id_encuesta_pregunta
                                             ORDER BY op.orden, op.id_encuesta_opcion) AS acum,
                   SUM({_sql_pesos()}) OVER (PARTITION BY pr.id_encuesta_pregunta) AS total
              FROM encuesta_pregunta pr
              JOIN encuesta_opcion op ON op.id_pregunta = pr.id_encuesta_pregunta
             WHERE pr.id_municipio = :mun AND pr.activo AND op.activo AND pr.tipo = 'multiple'
               AND op.valor <> ALL(CAST(:expectativa AS text[]))
        )
        INSERT INTO encuesta_respuesta_detalle (id_respuesta, id_pregunta, id_opcion_seleccionada, activo,
                                                id_municipio, id_subarea, fecha_alta, fecha_modificacion,
                                                id_usuario_alta)
        SELECT DISTINCT ON (p.id_resp) p.id_resp, o.id_preg, o.id_op, TRUE,
               CAST(:mun AS int), p.id_subarea, p.fecha_alta, p.fecha_alta, p.id_usuario_alta
          FROM pend p
          JOIN opc o ON o.id_plantilla = p.id_plantilla AND o.rama = p.rama
         WHERE o.acum > p.sorteo * o.total
         ORDER BY p.id_resp, o.acum
    """), {"mun": id_municipio, "uid": uid, "expectativa": _VALORES_EXPECTATIVA})
    await db.commit()
    return {"motivos": r.rowcount}


async def completar_encuestas_demo(db: AsyncSession) -> dict:
    """Paso final de cada corrida del generador demo: entradas y después motivos (así las
    respuestas de entradas recién creadas también llevan el suyo)."""
    id_municipio = await demo_datos.municipio_demo(db)
    uid = await demo_datos._usuario_generador(db)
    entradas = await encuestar_entradas(db, id_municipio, uid)
    motivos = await completar_motivos(db, id_municipio, uid)
    return {"entradas": entradas, **motivos}
