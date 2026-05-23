# -*- coding: utf-8 -*-
"""
Rate limiting in-memory simple (sin dependencias externas).

Suficiente para v1: Railway corre 1 replica. Limitaciones conocidas:
  - No persiste entre restarts.
  - No funciona con múltiples workers/replicas.
Si se escala a múltiples replicas o se quiere persistencia, migrar a Redis + slowapi.
"""
from collections import defaultdict
from time import time

from fastapi import HTTPException

_buckets: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(ip: str, max_requests: int = 5, window_seconds: int = 60) -> None:
    """Lanza HTTPException 429 si la IP excede max_requests en la ventana. Auto-purga."""
    now = time()
    bucket = _buckets[ip]
    bucket[:] = [t for t in bucket if now - t < window_seconds]
    if len(bucket) >= max_requests:
        raise HTTPException(429, "Demasiadas solicitudes. Intentá en unos segundos.")
    bucket.append(now)
