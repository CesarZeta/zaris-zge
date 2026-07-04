# -*- coding: utf-8 -*-
"""Helpers de request HTTP (extracción de IP detrás de proxy)."""
from fastapi import Request


def get_real_ip(request: Request) -> str:
    """
    Extrae la IP real del cliente detrás del proxy de Railway.

    Railway corre sobre Envoy, que computa la IP externa REAL en el header
    ``X-Envoy-External-Address`` (una sola IP, no una lista) y NO es spoofeable
    por el cliente: aunque el cliente mande su propio ``X-Forwarded-For``, Envoy
    lo recalcula. Por eso preferimos ese header para rate-limiting y auditoría.

    Fallback NO-regresivo si el header de Envoy no está presente (entornos que no
    sean Railway/Envoy): se mantiene el comportamiento anterior
    (``X-Forwarded-For`` primer IP → ``request.client.host`` → 'unknown'). Así,
    en el peor caso el resultado es idéntico al de antes; en Railway mejora
    (deja de ser spoofeable el bucket de rate-limit y la IP auditada).

    Nota: ``X-Forwarded-For`` primer-IP es controlable por el cliente. Si algún
    día Railway deja de exponer el header de Envoy, endurecer acá tomando la IP
    del lado del proxy (última del XFF según hops confiables), no la primera.
    """
    envoy = request.headers.get("X-Envoy-External-Address")
    if envoy and envoy.strip():
        return envoy.strip()
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
