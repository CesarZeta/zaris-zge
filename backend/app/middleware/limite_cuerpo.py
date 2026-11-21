"""
Tope del cuerpo de una request ANTES de que se parsee (FastAPI parsea el multipart antes de
correr dependencias y handler, así que un chequeo dentro del handler llega tarde).

Se aplica a rutas puntuales por (método, ruta exacta). Sin Content-Length -> 411; mayor al tope
-> 413. Responde sin leer el cuerpo.
"""
from __future__ import annotations

import json


class LimiteCuerpoMiddleware:
    def __init__(self, app, limites: dict[tuple[str, str], int]):
        self.app = app
        self.limites = limites

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            tope = self.limites.get((scope["method"], scope["path"]))
            if tope is not None:
                cl = dict(scope["headers"]).get(b"content-length")
                estado = detalle = None
                if cl is None:
                    estado, detalle = 411, "Falta Content-Length"
                else:
                    try:
                        if int(cl) > tope:
                            estado, detalle = 413, "El cuerpo de la solicitud es demasiado grande"
                    except ValueError:
                        estado, detalle = 400, "Content-Length inválido"
                if estado:
                    cuerpo = json.dumps({"detail": detalle}).encode()
                    await send({"type": "http.response.start", "status": estado,
                                "headers": [(b"content-type", b"application/json"),
                                            (b"content-length", str(len(cuerpo)).encode())]})
                    await send({"type": "http.response.body", "body": cuerpo})
                    return
        await self.app(scope, receive, send)
