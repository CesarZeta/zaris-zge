# -*- coding: utf-8 -*-
"""Mezcla de SLA de los datos demo (decision de Cesar 2026-10-21).

Regla: cada mes calendario (por mes de ALTA) una fraccion p entre 60 % y 85 %
de lo que se cierra lo hace DENTRO del SLA del tipo y el resto FUERA. La usan
los generadores de reclamos (demo_datos.py) y de tramites (demo_tramites.py).

Como se logra sin guardar nada en la DB:

- p del mes: determinista por (modulo, anio, mes) -> el cron diario que arma un
  mes de a un dia usa siempre el mismo p para ese mes.
- Que cada item caiga dentro o fuera: secuencia de Weyl sobre el id del item
  (`frac(id * phi + offset) < p`). Para ids consecutivos (los lotes diarios del
  generador lo son) la fraccion que cae dentro es p con error O(log n / n): el
  mes cierra en p +- 1 punto, no en p +- 3 como con un sorteo independiente.
- La demora de cada item: random.Random sembrado con el id (string seed ->
  sha512, estable entre procesos e independiente de PYTHONHASHSEED).

Asi el generador (al crear) y avanzar_pendientes (dias despues) calculan el
MISMO plan para el mismo item: el cierre ocurre en la fecha del plan, no "ahora".

Definicion de "dentro del SLA" = la del BI. Reclamos (desde la mig 120, SLA en
minutos): cierre - alta <= sla, exacto, igual que el vencimiento del trigger
(`dentro_sla_reclamo`, bi.py `_DENTRO_SLA`). Tramites: FLOOR(dias entre alta y
cierre) <= sla_dias (`dentro_sla`). Las demoras se sortean con margen para que
los dos criterios coincidan: dentro <= sla - 30 min; fuera >= sla + 1,05 dias.
"""
from __future__ import annotations

import math
import random
from datetime import datetime

P_MIN = 0.60   # rango pedido por Cesar
P_MAX = 0.85
# p se sortea con un punto de margen de cada lado: subreclamos, retrabajos y
# cancelaciones agregan ruido de +-1 punto al mes medido y este no debe salir de
# [60, 85].
_P_SORTEO = (P_MIN + 0.01, P_MAX - 0.01)
_PHI = (math.sqrt(5) - 1) / 2  # 0,618... (golden ratio conjugate)

# Tope de duracion de un reclamo demo: "lo viejo se cierra" (todo lo de mas de 3
# semanas esta cerrado). Los tramites usan max(TOPE, 3 x sla).
TOPE_DIAS = 20.0


def p_mes(modulo: str, anio: int, mes: int) -> float:
    """Fraccion objetivo dentro del SLA para el mes (determinista)."""
    r = random.Random(f"zaris-demo-sla:{modulo}:{anio:04d}-{mes:02d}")
    lo, hi = _P_SORTEO
    return round(lo + (hi - lo) * r.random(), 4)


def _offset(modulo: str) -> float:
    return random.Random(f"zaris-demo-weyl:{modulo}").random()


def cae_dentro(modulo: str, id_item: int, p: float) -> bool:
    """True si el item (por su id) cierra dentro del SLA en un mes con fraccion p."""
    return ((int(id_item) * _PHI + _offset(modulo)) % 1.0) < p


def rnd_de(modulo: str, id_item: int) -> random.Random:
    """Generador propio del item: el mismo id da siempre la misma secuencia."""
    return random.Random(f"zaris-demo:{modulo}:{int(id_item)}")


def demora_dentro(rnd: random.Random, sla: float) -> float:
    """Dias entre alta y cierre DENTRO del SLA: media ~30 % del SLA, entre 1 h y
    media hora antes del vencimiento. Con un SLA de pocas horas (mig 120) los
    bordes se achican a un 10 % del SLA para no caer fuera (desde 5 h el
    resultado es el mismo que antes)."""
    sla = max(float(sla), 1 / 144)  # piso: 10 minutos
    d = sla * rnd.betavariate(1.3, 3.0)
    return min(max(d, min(1 / 24, sla * 0.1)), sla - min(1 / 48, sla * 0.1))


def demora_fuera(rnd: random.Random, sla: float, tope: float = TOPE_DIAS) -> float:
    """Dias entre alta y cierre FUERA del SLA: 94 % entre sla+1 y 3 x sla (sesgado
    al vencimiento) y 6 % de cola hasta 5 x sla, acotado por `tope`.

    Con estas demoras lo pendiente de las ultimas 3 semanas ronda el 10 % (11-13 %
    con p = 60 %, 8-10 % con p = 85 %): lo que sigue abierto es lo reciente y lo
    que se esta demorando, como en la realidad."""
    sla = max(float(sla), 0.5)
    piso = sla + 1.05
    techo = max(3 * sla, piso + 1)
    if rnd.random() < 0.94:
        d = rnd.triangular(piso, techo, piso)
    else:
        d = rnd.uniform(techo, max(techo + 1, 5 * sla))
    return min(d, max(tope, piso + 0.5))


def dentro_sla(alta: datetime, cierre: datetime, sla: float | None) -> bool | None:
    """Criterio del BI de TRAMITES: FLOOR(dias) <= sla. None si el tipo no tiene SLA."""
    if not sla:
        return None
    return math.floor((cierre - alta).total_seconds() / 86400.0) <= float(sla)


def dentro_sla_reclamo(alta: datetime, cierre: datetime, sla: float | None) -> bool | None:
    """Criterio del BI de RECLAMOS (mig 120): el cierre llega antes del vencimiento,
    exacto (sla en dias, con fraccion si el tipo lo tiene en horas o minutos).
    None si el tipo no tiene SLA."""
    if not sla:
        return None
    return (cierre - alta).total_seconds() <= float(sla) * 86400.0
