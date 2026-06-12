"""
Helpers de fecha/hora en horario LOCAL del municipio.

El server (Railway) corre en UTC; el municipio opera en Argentina (UTC-3,
sin horario de verano desde 2009). Cualquier validacion de "ya paso" sobre
turnos/slots (que guardan TIME naive local) debe comparar contra la hora
LOCAL, no contra datetime.now() del server: usar date.today() en UTC corre
el dia entre las 21:00 y las 00:00 de Argentina.

Offset fijo a proposito (no ZoneInfo): America/Argentina no tiene DST y el
paquete tzdata puede faltar en el dev local Windows. Si algun deploy futuro
sale de Argentina, mover el offset a configuracion_general.
"""
from __future__ import annotations

from datetime import datetime, date, time, timedelta, timezone

TZ_MUNICIPIO = timezone(timedelta(hours=-3))


def ahora_local() -> datetime:
    """Datetime naive en hora local del municipio (comparable con TIME de DB)."""
    return datetime.now(TZ_MUNICIPIO).replace(tzinfo=None)


def hoy_local() -> date:
    return ahora_local().date()


def hora_local() -> time:
    return ahora_local().time()
