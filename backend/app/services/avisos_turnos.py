"""
ZARIS API — Avisos de turnos y entradas al vecino (PLAN_AVISOS_TURNOS_ENTRADAS.md, mig 144).

Momentos: `confirmado` (se reservó), `cambiado` (el municipio cambió fecha, hora, lugar o prestación),
`cancelado` (por el municipio) y `recordatorio` (el día anterior). Lo que cancela el propio vecino no
avisa: la pantalla ya se lo confirma.

Canales: bandeja «Alertas» siempre, notificación si la tiene activada en su teléfono, y correo SOLO a
quien tiene la cuenta activada (correo confirmado). El recordatorio sale entero solo a cuentas
activadas. Es una regla general, sin excepciones por dominio: los vecinos de demostración no la cumplen
y por eso no se les escribe.

Un turno de la gestión Salud no nombra la prestación ni el lugar en la notificación y el correo (dato de
salud a la vista en la pantalla bloqueada): solo la dirección. El detalle está en la app, con sesión.

Best-effort: se llama DESPUÉS del commit, con sesión propia, y nunca levanta excepción. Toda vía nueva
que reserve, cambie o cancele un turno o una entrada tiene que llamar a este servicio.
"""
from __future__ import annotations

import html
import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.services import email as svc_email
from app.services.avisos import registrar_aviso_ciudadano
from app.services.push import enviar_push_ciudadano
from app.utils.fechas import ahora_local, hoy_local

logger = logging.getLogger("zaris.avisos_turnos")

_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
          "octubre", "noviembre", "diciembre")

_TITULOS = {
    "turno": {"confirmado": "Turno confirmado", "cambiado": "Cambió tu turno",
              "cancelado": "El municipio canceló tu turno", "recordatorio": "Mañana tenés un turno"},
    "entrada": {"confirmado": "Entrada confirmada", "cambiado": "Cambió el evento de tu entrada",
                "cancelado": "El municipio canceló tu entrada", "recordatorio": "Mañana es tu evento"},
}
# Tope de recordatorios por corrida, municipio y circuito: la tarea corre varias veces y sigue donde quedó.
TOPE_POR_CORRIDA = 150


def cuando(fecha: date, hora) -> str:
    """«el jueves 26 de noviembre a las 10:30 h»."""
    return f"el {_DIAS[fecha.weekday()]} {fecha.day} de {_MESES[fecha.month - 1]} a las {hora.strftime('%H:%M')} h"


def marca_recordatorio(fecha: date) -> Optional[datetime]:
    """Valor de `recordado_en` al cambiar la fecha: si es para hoy o mañana, el aviso del cambio alcanza
    (ya dado por recordado); si es para después, vuelve a quedar pendiente."""
    return None if fecha > hoy_local() + timedelta(days=1) else datetime.now().astimezone()


async def _enviar(*, clase: str, momento: str, fila: Any, que: str, que_reservado: Optional[str],
                  lugar: Optional[str], lugar_reservado: Optional[str], url: str, recurso_id: int,
                  con_push: bool) -> Optional[bool]:
    """Manda un aviso por sus canales. Devuelve False si un correo que correspondía no salió."""
    activada = bool(fila["activada"])
    if momento == "recordatorio" and not activada:
        return None
    titulo = _TITULOS[clase][momento]
    texto_cuando = cuando(fila["fecha"], fila["hora_inicio"])

    def frase(nombre: Optional[str], sitio: Optional[str]) -> str:
        sujeto = f"{nombre}, " if nombre else ""
        if momento == "cancelado":
            final = ("Si todavía lo necesitás, podés reservar de nuevo." if clase == "turno"
                     else "La entrada ya no es válida.")
            cuerpo = f"{sujeto}{texto_cuando}. {final}"
        else:
            cuerpo = f"{sujeto}{texto_cuando}{f', en {sitio}' if sitio else ''}."
        return cuerpo[0].upper() + cuerpo[1:]

    await registrar_aviso_ciudadano(
        int(fila["id_ciudadano"]), clase, titulo, frase(que, lugar)[:1000], url,
        recurso_tipo=clase, recurso_id=recurso_id)
    publica = frase(que_reservado, lugar_reservado)
    if con_push:
        await enviar_push_ciudadano(int(fila["id_ciudadano"]), titulo=titulo, cuerpo=publica[:180], url=url)

    correo = (fila["email"] or "").strip()
    if not (activada and "@" in correo):
        return None
    from app.core.urls import url_portal_vecino
    from app.services.cuenta_vecino import _municipio_branding
    async with AsyncSessionLocal() as db:
        portal = await url_portal_vecino(db, fila["id_municipio"])
        if not portal:
            return None
        nombre_mun, logo = await _municipio_branding(db, fila["id_municipio"])
    extra = "Podés ver el detalle y cancelarlo desde el Portal del Ciudadano."
    if momento == "cancelado":
        extra = "Podés ver tus reservas en el Portal del Ciudadano."
    elif clase == "entrada":
        extra = "Para ingresar mostrá el código QR que está en «Mis entradas»."
    return await svc_email.enviar_mail_aviso_vecino(
        to=correo, nombre=fila["nombre"] or "", titulo=titulo, parrafo=html.escape(publica),
        parrafo_extra=extra, cta_texto="Ver mis turnos" if clase == "turno" else "Ver mis entradas",
        cta_url=f"{portal}{url}", municipio_nombre=nombre_mun, municipio_logo_url=logo,
        id_municipio=fila["id_municipio"])


async def avisar_turno(id_turno: int, momento: str, *, con_push: bool = True) -> Optional[bool]:
    """Avisa al vecino de un turno. `con_push=False` cuando lo acaba de sacar desde la app."""
    try:
        from app.services.historia_clinica import gestion_es_salud
        from app.services.municipios.modulos import modulo_esta_habilitado
        async with AsyncSessionLocal() as db:
            f = (await db.execute(text("""
                SELECT t.id_turno, t.id_ciudadano, t.id_municipio, t.fecha, t.hora_inicio, t.estado,
                       t.id_espacio_ubicacion, tp.nombre AS prestacion, tp.id_subarea,
                       e.nombre AS lugar, e.direccion, c.nombre, c.email,
                       COALESCE(k.activado AND k.activo, FALSE) AS activada
                  FROM turnos t
                  JOIN ciudadanos c ON c.id_ciudadano = t.id_ciudadano AND c.activo
                  LEFT JOIN ciudadano_credencial k ON k.id_ciudadano = t.id_ciudadano
                  LEFT JOIN tipo_prestacion tp ON tp.id_tipo_prestacion = t.id_tipo_prestacion
                  LEFT JOIN espacios_agenda e ON e.id_espacio = COALESCE(t.id_espacio_ubicacion, t.id_espacio)
                 WHERE t.id_turno = :i AND t.activo
            """), {"i": id_turno})).mappings().first()
            if not f or datetime.combine(f["fecha"], f["hora_inicio"]) <= ahora_local():
                return None
            # El estado puede haber cambiado entre la acción y este aviso.
            if f["estado"] != ("cancelado" if momento == "cancelado" else "reservado"):
                return None
            if not await modulo_esta_habilitado(db, f["id_municipio"], "turnos"):
                return None
            salud = await gestion_es_salud(db, f["id_subarea"], f["id_espacio_ubicacion"],
                                           id_municipio=f["id_municipio"])
        lugar = ", ".join(x for x in (f["lugar"], f["direccion"]) if x) or None
        return await _enviar(
            clase="turno", momento=momento, fila=f, que=f["prestacion"],
            que_reservado=None if salud else f["prestacion"], lugar=lugar,
            lugar_reservado=(f["direccion"] or None) if salud else lugar,
            url="/turnos", recurso_id=id_turno, con_push=con_push)
    except Exception as e:  # noqa: BLE001 — best-effort SIEMPRE
        logger.warning("avisar_turno(%s, %s) falló: %s", id_turno, momento, e)
        return False


_SQL_ENTRADA = """
    SELECT r.id_evento_reserva, r.id_ciudadano, r.id_municipio, ev.nombre AS evento, ev.fecha,
           ev.hora_inicio, ev.activo AS evento_activo, er.codigo AS estado, ee.codigo AS estado_evento,
           e.nombre AS lugar, e.direccion, c.nombre, c.email,
           COALESCE(k.activado AND k.activo, FALSE) AS activada
      FROM evento_reservas r
      JOIN eventos ev ON ev.id_evento = r.id_evento
      JOIN ciudadanos c ON c.id_ciudadano = r.id_ciudadano AND c.activo
      LEFT JOIN ciudadano_credencial k ON k.id_ciudadano = r.id_ciudadano
      LEFT JOIN estado_reserva er ON er.id_estado_reserva = r.id_estado_reserva
      LEFT JOIN estado_evento ee ON ee.id_estado_evento = ev.id_estado_evento
      LEFT JOIN espacios_agenda e ON e.id_espacio = ev.id_espacio
     WHERE r.id_evento_reserva = :i AND r.activo
"""


async def avisar_entrada(id_evento_reserva: int, momento: str, *, con_push: bool = True) -> Optional[bool]:
    """Avisa al vecino de una entrada. En `cancelado` vale la reserva cancelada o el evento suspendido."""
    try:
        from app.services.municipios.modulos import modulo_esta_habilitado
        async with AsyncSessionLocal() as db:
            f = (await db.execute(text(_SQL_ENTRADA), {"i": id_evento_reserva})).mappings().first()
            if not f or datetime.combine(f["fecha"], f["hora_inicio"]) <= ahora_local():
                return None
            evento_vigente = f["evento_activo"] and f["estado_evento"] != "cancelado"
            vigente = f["estado"] == "reservada" and evento_vigente
            if vigente == (momento == "cancelado"):
                return None
            if not await modulo_esta_habilitado(db, f["id_municipio"], "entradas"):
                return None
        lugar = ", ".join(x for x in (f["lugar"], f["direccion"]) if x) or None
        return await _enviar(
            clase="entrada", momento=momento, fila=f, que=f["evento"], que_reservado=f["evento"],
            lugar=lugar, lugar_reservado=lugar, url="/entradas", recurso_id=id_evento_reserva,
            con_push=con_push)
    except Exception as e:  # noqa: BLE001 — best-effort SIEMPRE
        logger.warning("avisar_entrada(%s, %s) falló: %s", id_evento_reserva, momento, e)
        return False


async def avisar_evento(id_evento: int, momento: str) -> None:
    """Avisa a todos los que tienen una entrada reservada (evento cambiado, cancelado o eliminado)."""
    try:
        async with AsyncSessionLocal() as db:
            ids = (await db.execute(text("""
                SELECT r.id_evento_reserva FROM evento_reservas r
                  JOIN estado_reserva er ON er.id_estado_reserva = r.id_estado_reserva
                 WHERE r.id_evento = :e AND r.activo AND er.codigo = 'reservada'
                 ORDER BY r.id_evento_reserva
            """), {"e": id_evento})).scalars().all()
    except Exception as e:  # noqa: BLE001
        logger.warning("avisar_evento(%s, %s) falló: %s", id_evento, momento, e)
        return
    for i in ids:
        await avisar_entrada(int(i), momento)


async def enviar_recordatorios(db: AsyncSession, id_municipio: int) -> dict:
    """Recordatorio del día anterior. Marca primero y manda después: uno solo aunque la tarea se repita.
    Lo reservado hoy para mañana no se recuerda (recién recibió la confirmación)."""
    from app.services.municipios.modulos import modulos_habilitados
    modulos = set(await modulos_habilitados(db, id_municipio))
    manana = hoy_local() + timedelta(days=1)
    p = {"m": id_municipio, "f": manana, "hoy": hoy_local(), "tope": TOPE_POR_CORRIDA}
    activada = """EXISTS (SELECT 1 FROM ciudadano_credencial k
                           WHERE k.id_ciudadano = x.id_ciudadano AND k.activado AND k.activo)"""
    antes_de_hoy = "CAST(x.fecha_alta AT TIME ZONE 'America/Argentina/Buenos_Aires' AS date) < :hoy"
    turnos: list[int] = []
    entradas: list[int] = []
    if "turnos" in modulos:
        turnos = [int(i) for i in (await db.execute(text(f"""
            UPDATE turnos SET recordado_en = NOW() WHERE id_turno IN (
                SELECT x.id_turno FROM turnos x
                 WHERE x.id_municipio = :m AND x.fecha = :f AND x.activo AND x.estado = 'reservado'
                   AND x.recordado_en IS NULL AND {antes_de_hoy} AND {activada}
                 ORDER BY x.hora_inicio, x.id_turno LIMIT :tope FOR UPDATE OF x SKIP LOCKED)
            RETURNING id_turno"""), p)).scalars().all()]
    if "entradas" in modulos:
        entradas = [int(i) for i in (await db.execute(text(f"""
            UPDATE evento_reservas SET recordado_en = NOW() WHERE id_evento_reserva IN (
                SELECT x.id_evento_reserva FROM evento_reservas x
                  JOIN eventos ev ON ev.id_evento = x.id_evento AND ev.activo AND ev.fecha = :f
                  JOIN estado_reserva er ON er.id_estado_reserva = x.id_estado_reserva AND er.codigo = 'reservada'
                  LEFT JOIN estado_evento ee ON ee.id_estado_evento = ev.id_estado_evento
                 WHERE x.id_municipio = :m AND x.activo AND x.recordado_en IS NULL
                   AND COALESCE(ee.codigo, '') <> 'cancelado' AND {antes_de_hoy} AND {activada}
                 ORDER BY x.id_evento_reserva LIMIT :tope FOR UPDATE OF x SKIP LOCKED)
            RETURNING id_evento_reserva"""), p)).scalars().all()]
    await db.commit()
    fallidos = 0
    for i in turnos:
        fallidos += (await avisar_turno(i, "recordatorio")) is False
    for i in entradas:
        fallidos += (await avisar_entrada(i, "recordatorio")) is False
    salida: dict[str, Any] = {"turnos": len(turnos), "entradas": len(entradas), "fallidos": fallidos}
    if fallidos:
        salida["error"] = f"{fallidos} recordatorio(s) sin enviar"
    return salida
