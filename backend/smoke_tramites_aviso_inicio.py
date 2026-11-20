# -*- coding: utf-8 -*-
"""
Smoke in-process — mail al iniciador cuando se inicia un trámite (decisión de César, 2026-11-19).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_tramites_aviso_inicio.py

SOLO LOCAL (aborta si la DB no es zaris_dev). El app FastAPI real con httpx.ASGITransport y el
envío de mails CAPTURADO: no sale ningún correo (.env.local tiene una key real de Resend).
Necesita el admin ciudadanovl (nivel 1, con agente), el vecino demo id 3 con email y una empresa
activa con email. Los trámites creados quedan como demo.

Cubre:
  1. Ciudadano (poda-arbol): un mail al email del ciudadano, asunto con el número de expediente,
     remitente con el nombre del municipio, botón al Portal del Ciudadano.
  2. Empresa (habilitacion-comercial): un mail al email de la empresa.
  3. Área interna (pedido-informe): ningún mail al iniciador.
"""
import asyncio
import os
import sys
from datetime import date
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
    MAILS.append({"to": to, "subject": subject, "html": body_html, "from": from_override})
    return True


svc_email.enviar_mail = _capturar  # enviar_mail_inicio_tramite lo llama por el módulo

PWD_DEV = os.environ.get("ZARIS_QA_PASS") or "123456"
ADMIN_EMAIL = "ciudadanovl@municipio.gob.ar"
ID_CIUDADANO = 3
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


def valor_campo(c: dict, id_subarea: int):
    td = c.get("tipo_dato")
    if td == "subarea":
        return id_subarea
    if td == "direccion":
        return "Av. Maipú 1234"
    if td in ("numero", "entero", "decimal"):
        return 1
    if td == "fecha":
        return date.today().isoformat()
    if td == "booleano":
        return True
    if td == "email":
        return "smoke@example.com"
    if td in ("seleccion", "seleccion_multiple"):
        ops = c.get("opciones_jsonb") or []
        v = ops[0].get("valor") if ops and isinstance(ops[0], dict) else "a"
        return [v] if td == "seleccion_multiple" else v
    return "Smoke aviso de inicio"


async def main() -> int:
    cid = await q1("SELECT email FROM ciudadanos WHERE id_ciudadano = :i", i=ID_CIUDADANO)
    emp = await q1("SELECT id_empresa, email FROM empresas WHERE activo AND id_municipio = 1 "
                   "AND COALESCE(email, '') <> '' ORDER BY id_empresa LIMIT 1")
    sub = await q1("SELECT a.id_subarea FROM agentes a JOIN usuarios u ON u.id_usuario = a.id_usuario "
                   "WHERE u.email = :e", e=ADMIN_EMAIL)
    if not (cid and cid["email"] and emp and sub):
        print("faltan datos de prueba (vecino 3 con email, empresa con email, agente del admin)")
        return 1

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://smoke.local", timeout=90) as c:
        r = await c.post("/api/v1/auth/login", json={"identificador": ADMIN_EMAIL, "password": PWD_DEV})
        if r.status_code != 200:
            print("login fallo:", r.status_code, r.text[:200])
            return 1
        HA = {"Authorization": f"Bearer {r.json()['access_token']}"}

        async def crear(tipo: str, ini: dict) -> Optional[str]:
            t = await q1("SELECT id_tipo_tramite FROM tipo_tramite WHERE codigo = :c AND id_municipio = 1", c=tipo)
            det = (await c.get(f"/api/v1/tramites/tipos/{t['id_tipo_tramite']}", headers=HA)).json()
            datos = {ca["nombre_interno"]: valor_campo(ca, sub["id_subarea"]) for ca in det.get("campos") or [] if ca.get("obligatorio")}
            rr = await c.post("/api/v1/tramites", headers=HA, json={
                "id_tipo_tramite": t["id_tipo_tramite"], "asunto": "Smoke aviso de inicio",
                "iniciador": ini, "datos": datos})
            if rr.status_code not in (200, 201):
                print("   crear fallo:", tipo, rr.status_code, rr.text[:300])
                return None
            return rr.json()["numero_expediente"]

        print("[1] Ciudadano")
        MAILS.clear()
        num = await crear("poda-arbol", {"tipo": "ciudadano", "id_ciudadano": ID_CIUDADANO})
        al_vecino = [m for m in MAILS if m["to"] == cid["email"]]
        check(num is not None and len(al_vecino) == 1, "un mail al ciudadano", f"{num} {len(al_vecino)}")
        if al_vecino:
            m = al_vecino[0]
            check(num in m["subject"], "asunto con el número de expediente", m["subject"])
            check(num in m["html"], "número en el cuerpo")
            check(bool(m["from"]) and "<" in m["from"], "remitente con el nombre del municipio", str(m["from"]))
            check("Portal del Ciudadano" in m["html"], "botón al Portal del Ciudadano")

        print("[2] Empresa")
        MAILS.clear()
        num = await crear("habilitacion-comercial", {"tipo": "empresa", "id_empresa": emp["id_empresa"]})
        a_empresa = [m for m in MAILS if m["to"] == emp["email"].strip()]
        check(num is not None and len(a_empresa) == 1, "un mail a la empresa", f"{num} {len(a_empresa)}")

        print("[3] Área interna")
        MAILS.clear()
        num = await crear("pedido-informe", {"tipo": "area_interna", "id_subarea": sub["id_subarea"]})
        aviso_inicio = [m for m in MAILS if "Iniciaste el trámite" in m["subject"]]
        check(num is not None and not aviso_inicio, "ningún aviso de inicio a un área interna",
              f"{num} {len(aviso_inicio)}")

    print(f"\n== {OK} OK · {FAIL} FAIL ==")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
