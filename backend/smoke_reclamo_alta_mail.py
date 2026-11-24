# -*- coding: utf-8 -*-
"""
Smoke in-process — mail al vecino con el número del reclamo que carga un agente desde el
backoffice (decisión de César, 2026-11-20).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_reclamo_alta_mail.py

SOLO LOCAL (aborta si la DB no es zaris_dev). El app FastAPI real con httpx.ASGITransport y el
envío de mails CAPTURADO: no sale ningún correo (.env.local tiene una key real de Resend).
Necesita el admin ciudadanovl (nivel 1), el vecino demo id 3 con email, una ficha demo de
funcionario (DNI 99.xxx.xxx) y un ciudadano sin email, todos del municipio 1. Los reclamos
creados quedan como demo.

Cubre:
  1. Presencial a un vecino con email: un mail, asunto y cuerpo con el número, texto de
     comprobante, botón a /reclamos del Portal del Ciudadano, remitente con el municipio.
  2. Descripción con HTML: llega escapada.
  3. De oficio: ningún mail.
  4. Ficha demo de funcionario: 422 (no tiene cuenta, registro previo F2) y ningún mail.
  5. Ciudadano sin email: ídem (sin correo no hay cuenta).
  6. El mail del reclamo cargado desde la app conserva su texto.
"""
import asyncio
import os
import sys
from typing import Optional

import httpx

os.environ.setdefault("ENV_FILE", ".env.local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402

if "zaris_dev" not in settings.ASYNC_DATABASE_URI:
    sys.exit("ABORT: este smoke es SOLO LOCAL (la DB configurada no es zaris_dev).")

settings.RESEND_API_KEY = ""  # además del capturador, MOCK

# Preparación y verificación como dueño de la base: no pasa por la barrera (IT-01 F6).
from app.core.sistema import SesionSistema as AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.services import email as svc_email  # noqa: E402

MAILS: list[dict] = []


async def _capturar(to, subject, body_html, body_text=None, from_override=None):
    MAILS.append({"to": to, "subject": subject, "html": body_html, "text": body_text or "",
                  "from": from_override})
    return True


svc_email.enviar_mail = _capturar

PWD_DEV = os.environ.get("ZARIS_QA_PASS") or "123456"
ADMIN_EMAIL = "ciudadanovl@municipio.gob.ar"
ID_VECINO = 3
OK = FAIL = 0


def check(cond: bool, nombre: str, detalle: str = "") -> None:
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  OK   {nombre}")
    else:
        FAIL += 1
        print(f"  FAIL {nombre} {detalle}")


async def q1(sql: str, **params) -> Optional[dict]:
    async with AsyncSessionLocal() as s:
        row = (await s.execute(text(sql), params)).mappings().first()
        return dict(row) if row else None


async def main() -> int:
    vecino = await q1("SELECT email FROM ciudadanos WHERE id_ciudadano = :i AND id_municipio = 1", i=ID_VECINO)
    demo = await q1("SELECT id_ciudadano FROM ciudadanos WHERE activo AND id_municipio = 1 "
                    "AND doc_tipo = 'DNI' AND doc_nro ~ '^99[0-9]{6}$' "
                    "AND COALESCE(email, '') <> '' ORDER BY id_ciudadano LIMIT 1")
    sin_email = await q1("SELECT id_ciudadano FROM ciudadanos WHERE activo AND id_municipio = 1 "
                         "AND COALESCE(TRIM(email), '') = '' ORDER BY id_ciudadano LIMIT 1")
    tipo = await q1("SELECT tr.id_tipo_reclamo FROM tipo_reclamo tr JOIN subarea s ON s.id_subarea = tr.id_subarea "
                    "WHERE tr.activo AND tr.id_municipio = 1 ORDER BY tr.id_tipo_reclamo LIMIT 1")
    if not (vecino and vecino["email"] and demo and tipo):
        print("faltan datos de prueba:", vecino, demo, sin_email, tipo)
        return 1

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://smoke.local", timeout=90) as c:
        r = await c.post("/api/v1/auth/login", json={"identificador": ADMIN_EMAIL, "password": PWD_DEV})
        if r.status_code != 200 or "access_token" not in r.json():
            print("login fallo:", r.status_code, r.text[:200])
            return 1
        HA = {"Authorization": f"Bearer {r.json()['access_token']}"}

        async def crear(id_ciudadano: int, canal: str, desc: str = "Smoke mail de alta de reclamo") -> Optional[str]:
            rr = await c.post("/api/v1/reclamos", headers=HA, json={
                "id_ciudadano": id_ciudadano, "id_tipo_reclamo": tipo["id_tipo_reclamo"],
                "descripcion": desc, "direccion": "Av. Maipú 1234", "canal_origen": canal})
            if rr.status_code != 201:
                print("   crear fallo:", rr.status_code, rr.text[:300])
                return None
            return rr.json()["nro_reclamo"]

        print("[1] Presencial a un vecino con email")
        MAILS.clear()
        nro = await crear(ID_VECINO, "presencial")
        al_vecino = [m for m in MAILS if m["to"] == vecino["email"].strip()]
        check(nro is not None and len(al_vecino) == 1, "un mail al vecino", f"{nro} {len(al_vecino)}")
        if al_vecino:
            m = al_vecino[0]
            check(nro in m["subject"], "asunto con el número", m["subject"])
            check(nro in m["html"] and nro in m["text"], "número en el cuerpo (html y texto)")
            check("comprobante" in m["html"], "texto de comprobante")
            check("/reclamos" in m["html"] and "Portal del Ciudadano" in m["html"], "botón al portal")
            check(bool(m["from"]) and "<" in m["from"], "remitente con el municipio", str(m["from"]))

        print("[2] Descripción con HTML")
        MAILS.clear()
        nro = await crear(ID_VECINO, "telefono", 'Pozo <b>grande</b> & "hondo"')
        m = next((x for x in MAILS if x["to"] == vecino["email"].strip()), None)
        check(m is not None and "&lt;b&gt;grande&lt;/b&gt;" in m["html"] and "<b>grande" not in m["html"],
              "escapada en el html")
        check(m is not None and 'Pozo <b>grande</b> & "hondo"' in m["text"], "legible en el texto plano",
              (m or {}).get("text", "")[:400])

        print("[3] De oficio")
        MAILS.clear()
        nro = await crear(ID_VECINO, "oficio")
        check(nro is not None and not MAILS, "ningún mail", f"{nro} {len(MAILS)}")

        print("[4] Ficha demo de funcionario")
        MAILS.clear()
        nro = await crear(demo["id_ciudadano"], "presencial")
        check(nro is None and not MAILS, "no se crea y ningún mail", f"{nro} {len(MAILS)}")

        print("[5] Ciudadano sin email")
        if not sin_email:
            print("  SKIP no hay un ciudadano activo sin email en el municipio 1")
        else:
            MAILS.clear()
            nro = await crear(sin_email["id_ciudadano"], "presencial")
            check(nro is None and not MAILS, "no se crea y ningún mail", f"{nro} {len(MAILS)}")

    print("[6] Mail del reclamo cargado desde la app")
    MAILS.clear()
    await svc_email.enviar_mail_confirmacion_reclamo_ciudadano(
        to="x@example.com", nombre="Ana", apellido="Paz", nro_reclamo="REC-SAN-TEST",
        descripcion="d", direccion="calle", municipio_nombre="Muni", frontend_url="https://v.example",
        id_municipio=1)
    m = MAILS[0] if MAILS else None
    check(m is not None and "notificación" in m["html"] and "comprobante" not in m["html"],
          "conserva el texto de la app")

    print(f"\n== {OK} OK · {FAIL} FAIL ==")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
