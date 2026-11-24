# -*- coding: utf-8 -*-
"""
Smoke in-process — empresas del vecino logueado (PLAN_REGISTRO_PREVIO.md, F4).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_publico_empresas.py

SOLO LOCAL (aborta si la DB no es zaris_dev). Mails capturados. Con DB_BARRERA=true y con false.
La empresa creada queda dada de baja al terminar.
"""
import asyncio
import os
import random
import re
import sys

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
settings.RESEND_API_KEY = ""
settings.API_PUBLIC_BASE_URL = "http://smoke.local"

from app.core.auth import crear_token_ciudadano  # noqa: E402
from app.core.sistema import SesionSistema as AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.services import email as svc_email  # noqa: E402

MAILS: list[dict] = []


async def _capturar(to, subject, body_html, body_text=None, from_override=None):
    MAILS.append({"to": to, "html": body_html})
    return True


svc_email.enviar_mail = _capturar
P = "/api/v1/publico/empresas"
ALTA = "/api/v1/publico/alta/empresa"
OK = FAIL = 0


def check(cond, nombre, detalle="") -> None:
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  OK   {nombre}")
    else:
        FAIL += 1
        print(f"  FAIL {nombre} {detalle}")


async def q(sql: str, **p):
    async with AsyncSessionLocal() as s:
        res = await s.execute(text(sql), p)
        filas = [dict(x) for x in res.mappings().all()] if res.returns_rows else []
        await s.commit()
        return filas


def cuit_nuevo() -> str:
    while True:
        base = "30" + str(random.randint(60_000_000, 69_999_999))
        dv = 11 - sum(int(d) * m for d, m in zip(base, (5, 4, 3, 2, 7, 6, 5, 4, 3, 2))) % 11
        if dv < 10:
            return base + str(dv)


async def main() -> int:
    vec = await q("SELECT c.id_ciudadano FROM ciudadanos c JOIN ciudadano_credencial k USING (id_ciudadano) "
                  "WHERE c.activo AND k.activo AND k.activado AND c.id_municipio = 1 ORDER BY 1 LIMIT 2")
    a, b = (x["id_ciudadano"] for x in vec)
    ha = {"Authorization": f"Bearer {crear_token_ciudadano(a, 1)}"}
    hb = {"Authorization": f"Bearer {crear_token_ciudadano(b, 1)}"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://smoke.local", timeout=60) as c:
        def ip() -> dict:  # el límite por IP es de 5 altas por minuto
            return {"X-Forwarded-For": f"10.9.{random.randint(0, 255)}.{random.randint(1, 254)}"}

        async def alta(h, **extra):
            return await c.post(ALTA, headers={**h, **ip()}, json={**base, **extra})

        check((await c.get(P)).status_code == 401, "sin sesión: 401")
        r = await c.get(f"{P}/catalogos", headers=ha)
        cat = r.json()
        check(r.status_code == 200 and cat["actividades"] and cat["tipos_representacion"], "catálogos", r.text[:150])
        cuit = cuit_nuevo()
        correo = f"empresa.{cuit}@example.com"
        base = {"cuit": f"{cuit[:2]}-{cuit[2:10]}-{cuit[10]}", "razon_social": "Smoke Empresa del vecino",
                "id_actividad": cat["actividades"][0]["id"], "id_tipo_representacion": cat["tipos_representacion"][0]["id"],
                "calle": "Av. Maipú 1200", "localidad": "Olivos", "provincia": "Buenos Aires",
                "telefono": "1145556677", "email": correo}
        for nombre, cambio, codigo in (("teléfono con 0", {"telefono": "01145556677"}, 422),
                                       ("CUIT con dígito malo", {"cuit": "30-11111111-1"}, 422),
                                       ("razón social de más de 100", {"razon_social": "x" * 101}, 422),
                                       ("actividad inexistente", {"id_actividad": 999999}, 400),
                                       ("representación inexistente", {"id_tipo_representacion": 999999}, 400)):
            r = await alta(ha, **cambio)
            check(r.status_code == codigo, f"{nombre}: {codigo}", f"{r.status_code} {r.text[:150]}")
        r = await alta(ha, id_ciudadano=b)
        check(r.status_code == 201, "alta 201", f"{r.status_code} {r.text[:200]}")
        ide = r.json().get("id_empresa")
        f = await q("SELECT id_ciudadano, id_tipo_representacion FROM ciudadano_empresa WHERE id_empresa = :e AND activo", e=ide)
        check(len(f) == 1 and f[0]["id_ciudadano"] == a, "el representante es el del token, no el del body", str(f))
        mo = re.search(r"/api/v1/publico/alta/verificar\?token=[0-9a-f-]{36}[^\"&]*(?:&(?:amp;)?m=\w+)?", MAILS[-1]["html"]) if MAILS else None
        check(bool(mo) and MAILS[-1]["to"] == correo, "correo de verificación a la casilla de la empresa", str(len(MAILS)))
        r = await c.get(P, headers=ha)
        mia = next((x for x in r.json() if x["id_empresa"] == ide), None)
        check(mia and mia["email_verificado"] is False and mia["tipo_representacion"] and mia["actividad"], "la veo en mis empresas", str(mia))
        check(not any(x["id_empresa"] == ide for x in (await c.get(P, headers=hb)).json()), "otro vecino no la ve")
        if mo:
            r = await c.get(mo.group(0).replace("&amp;", "&"))
            check(r.status_code == 200 and "Empresa verificada" in r.text, "el link la verifica", f"{r.status_code}")
            mia = next(x for x in (await c.get(P, headers=ha)).json() if x["id_empresa"] == ide)
            check(mia["email_verificado"] is True, "queda verificada")
        await q("UPDATE empresas SET cuit = :g WHERE id_empresa = :e", g=base["cuit"], e=ide)  # como las filas viejas
        r = await alta(ha)
        check(r.status_code == 409 and "Ya tenés registrada" in r.text, "repetirla: 409 propia", r.text[:150])
        r = await alta(hb)
        check(r.status_code == 409 and "acercate al municipio" in r.text, "la de otro: 409 con qué hacer", r.text[:150])
    if ide:
        await q("UPDATE empresas SET activo = FALSE, cuit = :c WHERE id_empresa = :e", c=cuit, e=ide)
        await q("UPDATE ciudadano_empresa SET activo = FALSE WHERE id_empresa = :e", e=ide)
    print(f"\n== {OK} OK · {FAIL} FAIL ==")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
