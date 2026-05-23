# -*- coding: utf-8 -*-
"""Helpers de request HTTP (extracción de IP detrás de proxy)."""
from fastapi import Request


def get_real_ip(request: Request) -> str:
    """
    Extrae la IP real considerando el proxy de Railway.
    Prioridad: X-Forwarded-For (primer IP) > request.client.host > 'unknown'.
    """
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
