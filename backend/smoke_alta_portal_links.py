# -*- coding: utf-8 -*-
"""
Smoke in-process — Autogestión del alta del vecino: el circuito completo le dice al vecino
a dónde ir después (links al Portal del Ciudadano y a la página de alta), 2026-10-12.

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_alta_portal_links.py

SOLO LOCAL: aborta si la DB no es zaris_dev. Corre el app FastAPI real con httpx.ASGITransport
(memoria feedback_smoke_authz_asgi_in_process). El mail corre en MOCK (settings.RESEND_API_KEY =
"" — .env.local tiene una key REAL de Resend, §5) y se captura `enviar_mail` para leer el link
de verificación y el del portal. API_PUBLIC_BASE_URL se apunta al propio cliente in-process para
poder SEGUIR el link del mail (regla CLAUDE.md §5: el link del mail se verifica, no se supone).

Cubre: GET /alta/identidad expone app_vecinos_url → POST /alta/cuenta 201 → el mail lleva el link
de verificación Y el del portal (HTML y texto) → seguir el link = 200 "Correo verificado" con el
botón al portal → el mismo link otra vez = 400 "vencido" con el botón a la página de alta → login
público con DNI + clave OK → fail-closed (URL del portal con basura ⇒ sin botón, sin 500) →
marcador OpenAPI (IdentidadAltaOut.app_vecinos_url). Los datos quedan como demo (no se limpian).
"""
import asyncio
import logging
import os
import random
import re
import sys
import uuid
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
    sys.exit("ABORT: este smoke es SOLO LOCAL (la DB configurada no es zaris_dev). No corre contra prod.")

PORTAL = "https://vecinos.zaris.com.ar"
SHELL = "https://zge.zaris.com.ar"
BASE_IN_PROCESS = "http://smoke.local"

settings.RESEND_API_KEY = ""                      # MOCK: nunca Resend real desde un smoke
settings.APP_VECINOS_FRONTEND_URL = PORTAL        # como en prod (verificado en /config/identidad)
settings.FRONTEND_BASE_URL = SHELL
settings.API_PUBLIC_BASE_URL = BASE_IN_PROCESS    # el link del mail se sigue in-process

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402
import app.services.email as email_mod  # noqa: E402

logging.getLogger("httpx").setLevel(logging.WARNING)

PASSWORD = "ClaveVecino2026!"

ok_count = 0
fail_count = 0
fallidos: list[dict] = []
mails: list[dict] = []


def check(nombre: str, cond: bool, extra: str = "") -> bool:
    global ok_count, fail_count
    if cond:
        ok_count += 1
        print(f"  OK   {nombre} {extra}")
    else:
        fail_count += 1
        print(f"  FAIL {nombre} {extra}")
        fallidos.append({"caso": nombre, "detalle": extra})
    return cond


def short(r: httpx.Response, n: int = 160) -> str:
    return f"{r.status_code} {r.text[:n]}"


async def q1(sql: str, **params) -> Optional[dict]:
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(text(sql), params)).mappings().all()
        return dict(rows[0]) if rows else None


def cuil_valido(dni: str, prefijo: str = "20") -> str:
    base = prefijo + dni.zfill(8)
    pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    s = sum(int(d) * p for d, p in zip(base, pesos))
    resto = 11 - (s % 11)
    if resto == 11:
        return base + "0"
    if resto == 10:
        return cuil_valido(dni, "23")
    return base + str(resto)


async def _captura_enviar_mail(to: str, subject: str, body_html: str, body_text: str | None = None,
                               from_override: str | None = None) -> bool:
    mails.append({"to": to, "subject": subject, "html": body_html, "text": body_text or ""})
    return True


async def dni_libre() -> str:
    for _ in range(20):
        dni = "4" + "".join(random.choice("0123456789") for _ in range(7))
        if not await q1("SELECT 1 AS x FROM ciudadanos WHERE doc_nro = :d", d=dni):
            return dni
    sys.exit("ABORT: no encontré un DNI libre")


async def main() -> int:
    muni = await q1("SELECT codigo_corto FROM municipios WHERE activo = TRUE ORDER BY id_municipio LIMIT 1")
    if not muni or not muni["codigo_corto"]:
        sys.exit("ABORT: no hay municipio activo con codigo_corto en local")
    slug = str(muni["codigo_corto"]).strip().lower()
    nac = await q1("SELECT id FROM nacionalidades ORDER BY id LIMIT 1")
    if not nac:
        sys.exit("ABORT: tabla nacionalidades vacía en local")
    url_alta = f"{SHELL}/frontend/alta-vecino.html?m={slug}"

    email_mod.enviar_mail = _captura_enviar_mail

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_IN_PROCESS, timeout=60) as c:
        # ── 1. La página de alta recibe la URL del portal ────────────────────────────
        r = await c.get(f"/api/v1/publico/alta/identidad?m={slug}")
        check("1a. GET /alta/identidad 200", r.status_code == 200, short(r))
        check("1b. identidad.app_vecinos_url = portal", r.status_code == 200 and r.json().get("app_vecinos_url") == PORTAL,
              str(r.json().get("app_vecinos_url")) if r.status_code == 200 else short(r))

        # ── 2. Alta pública de UN PASO ───────────────────────────────────────────────
        dni = await dni_libre()
        email = f"alta.portal.{dni}@example.com"
        body = {
            "municipio_slug": slug, "doc_nro": dni, "cuil": cuil_valido(dni),
            "nombre": "Vecina", "apellido": f"Portal{dni[-4:]}", "sexo": "MUJER",
            "fecha_nac": "1991-03-14", "id_nacionalidad": nac["id"],
            "calle": "Av. Maipú 2502", "localidad": "Olivos", "provincia": "Buenos Aires",
            "telefono": "11" + dni[-8:], "email": email, "password": PASSWORD,
        }
        mails.clear()
        r = await c.post("/api/v1/publico/alta/cuenta", json=body)
        if not check("2a. POST /alta/cuenta 201", r.status_code == 201, short(r)):
            return 1
        # El mail sale en BackgroundTasks: con ASGITransport corre antes de devolver la respuesta,
        # pero por las dudas damos un respiro al loop.
        for _ in range(20):
            if mails:
                break
            await asyncio.sleep(0.05)
        check("2b. salió UN mail al email del alta", len(mails) == 1 and mails[0]["to"] == email,
              f"{len(mails)} mails: {[m['to'] for m in mails]}")
        if not mails:
            return 1
        m = mails[0]
        check("2c. asunto = Verificá tu alta", "Verificá tu alta" in m["subject"], m["subject"])
        # El slug del link va tal cual está en municipios.codigo_corto (en local 'LPL', en prod 'san').
        mo = re.search(r"/api/v1/publico/alta/verificar\?token=([0-9a-f-]{36})&m=([A-Za-z0-9_-]+)", m["html"])
        check("2d. el mail trae el link de verificación (API_PUBLIC_BASE_URL)",
              bool(mo) and f"{BASE_IN_PROCESS}/api/v1/publico/alta/verificar?token=" in m["html"],
              (mo.group(0) if mo else "sin link"))
        check("2e. el mail HTML trae el link al portal", f'href="{PORTAL}"' in m["html"], "")
        check("2f. el mail TEXTO trae el link al portal, sin etiquetas",
              PORTAL in m["text"] and "<a" not in m["text"] and "<p" not in m["text"], m["text"][-400:])
        if not mo:
            return 1
        token, m_slug = mo.group(1), mo.group(2)
        check("2g. el slug del link es el del municipio", m_slug.lower() == slug, f"{m_slug} vs {slug}")

        # ── 3. Seguir el link del mail (como el vecino desde el celular) ───────────────
        link = f"/api/v1/publico/alta/verificar?token={token}&m={m_slug}"
        r = await c.get(link)
        check("3a. GET link del mail → 200", r.status_code == 200, short(r))
        check("3b. página 'Correo verificado'", "Correo verificado" in r.text, "")
        check("3c. botón 'Ir al Portal del Ciudadano' → portal", f'href="{PORTAL}"' in r.text and "Ir al Portal del Ciudadano" in r.text, "")
        fila = await q1("""
            SELECT c.email_chk, c.estado_validacion, cc.activado, cc.token_activacion
              FROM ciudadanos c JOIN ciudadano_credencial cc ON cc.id_ciudadano = c.id_ciudadano
             WHERE c.doc_nro = :d
        """, d=dni)
        check("3d. DB: email_chk + verificado + credencial activada + token consumido",
              bool(fila) and fila["email_chk"] is True and fila["estado_validacion"] == "verificado"
              and fila["activado"] is True and fila["token_activacion"] is None, str(fila))

        # ── 4. El mismo link otra vez (token consumido = vencido) ─────────────────────
        r = await c.get(link)
        check("4a. link consumido → 400", r.status_code == 400, short(r))
        check("4b. página 'inválido o vencido'", "inválido o vencido" in r.text, "")
        check("4c. botón 'Volver a la página de alta' → alta pública con el slug",
              f'href="{url_alta}"' in r.text and "Volver a la página de alta" in r.text, r.text[-500:])
        check("4d. la página de error NO ofrece el portal", "Ir al Portal del Ciudadano" not in r.text, "")

        # ── 5. Login público con DNI + la clave elegida ───────────────────────────────
        r = await c.post("/api/v1/publico/auth/login", json={"dni": dni, "password": PASSWORD})
        check("5a. login público 200 (cuenta activa)", r.status_code == 200 and "access_token" in r.json(), short(r))

        # ── 6. Token inexistente (uuid al azar): 400 con botón a la alta, sin 500 ─────
        r = await c.get(f"/api/v1/publico/alta/verificar?token={uuid.uuid4()}&m={slug}")
        check("6a. token inexistente → 400", r.status_code == 400, short(r))
        check("6b. con botón a la página de alta", f'href="{url_alta}"' in r.text, "")

        # ── 7. Fail-closed: URL del portal con basura (línea entera pegada en Railway) ─
        settings.APP_VECINOS_FRONTEND_URL = "APP_VECINOS_FRONTEND_URL=https://vecinos.zaris.com.ar"
        try:
            r = await c.get(f"/api/v1/publico/alta/identidad?m={slug}")
            check("7a. identidad.app_vecinos_url = null con basura", r.status_code == 200 and r.json().get("app_vecinos_url") is None, short(r))
            r = await c.get(f"/api/v1/publico/alta/verificar?token={uuid.uuid4()}&m={slug}")
            check("7b. verificar sigue respondiendo (400, sin 500)", r.status_code == 400, short(r))
            check("7c. sin botón al portal (no se publica una URL inválida)", "Ir al Portal" not in r.text, "")
        finally:
            settings.APP_VECINOS_FRONTEND_URL = PORTAL

        # ── 8. Marcador OpenAPI para confirmar el deploy en prod (§9) ─────────────────
        r = await c.get("/openapi.json")
        props = (r.json().get("components", {}).get("schemas", {}).get("IdentidadAltaOut", {}).get("properties", {})
                 if r.status_code == 200 else {})
        check("8a. OpenAPI IdentidadAltaOut.app_vecinos_url", "app_vecinos_url" in props, str(list(props)))

    print()
    print(f"RESULTADO: {ok_count} OK / {fail_count} FAIL  (DNI demo {dni}, email {email})")
    for f in fallidos:
        print(f"   - {f['caso']}: {f['detalle']}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
