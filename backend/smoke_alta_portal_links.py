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

Cubre (PLAN_REGISTRO_PREVIO.md §6, F3): registro sin contraseña → mail con link al portal →
confirmar el correo (alta, sin gastar el token) → generar el usuario (número de 6 dígitos, mail que lo
informa) → ingresar con DNI o con el número → recuperar con el número → dos activaciones a la vez →
fail-closed (URL del portal con basura) → marcador OpenAPI. Los datos quedan como demo.
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

# Preparación y verificación como dueño de la base: no pasa por la barrera (IT-01 F6).
from app.core.sistema import SesionSistema as AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402
import app.services.email as email_mod  # noqa: E402

logging.getLogger("httpx").setLevel(logging.WARNING)

PASSWORD = "ClaveVecino2026!"
SQL_CUENTA = """
    SELECT c.email_chk, c.estado_validacion, cc.activado, cc.password_hash, cc.numero_usuario
      FROM ciudadanos c JOIN ciudadano_credencial cc ON cc.id_ciudadano = c.id_ciudadano
     WHERE c.doc_nro = :d
"""

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
    url_alta = f"{PORTAL}/registro"

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
            "telefono": "11" + dni[-8:], "email": email,
        }
        mails.clear()
        r = await c.post("/api/v1/publico/alta/cuenta", json=body)
        if not check("2a. POST /alta/cuenta 201 sin contraseña", r.status_code == 201, short(r)):
            return 1
        check("2b. salió UN mail al email del alta", len(mails) == 1 and mails[0]["to"] == email,
              f"{len(mails)} mails: {[m['to'] for m in mails]}")
        if not mails:
            return 1
        m = mails[0]
        check("2c. asunto = Confirmá tu registro", "Confirmá tu registro" in m["subject"], m["subject"])
        mo = re.search(re.escape(PORTAL) + r"/activar\?token=([0-9a-f-]{36})", m["html"])
        check("2d. el mail lleva al portal, a generar el usuario (HTML y texto)",
              bool(mo) and mo.group(0) in m["text"], mo.group(0) if mo else m["html"][-400:])
        if not mo:
            return 1
        token = mo.group(1)
        fila = await q1(SQL_CUENTA, d=dni)
        check("2e. cuenta pendiente: sin contraseña, sin número de usuario, sin verificar",
              fila["password_hash"] is None and fila["numero_usuario"] is None and fila["activado"] is False
              and fila["estado_validacion"] == "auto_registrado", str(fila))
        r = await c.post("/api/v1/publico/alta/cuenta", json={**body, "password": "PaginaVieja2026"})
        check("2f. repetir el alta → 409", r.status_code == 409, short(r))

        # ── 3. El link abre el portal: confirma el correo (alta) sin gastar el token ───
        r = await c.get(f"/api/v1/publico/alta/verificar?token={token}&m={slug}")
        check("3a. el verificar viejo, sin contraseña, manda al portal", r.status_code == 303
              and r.headers.get("location") == f"{PORTAL}/activar?token={token}", short(r))
        fila = await q1(SQL_CUENTA, d=dni)
        check("3b. abrir un link con GET no confirma nada", fila["email_chk"] is False, str(fila))
        for n in ("primera", "segunda"):
            r = await c.post("/api/v1/publico/auth/confirmar-correo", json={"token": token})
            check(f"3c. confirmar-correo 200 ({n} vez)", r.status_code == 200 and r.json()["nombre"] == "Vecina", short(r))
        fila = await q1(SQL_CUENTA, d=dni)
        check("3d. dado de alta: correo confirmado, y la cuenta sigue sin usuario",
              fila["email_chk"] is True and fila["estado_validacion"] == "verificado" and fila["activado"] is False
              and fila["numero_usuario"] is None, str(fila))
        for mal in ("no-es-un-uuid", str(uuid.uuid4())):
            r = await c.post("/api/v1/publico/auth/confirmar-correo", json={"token": mal})
            check(f"3e. token malo → 400 ({mal[:12]})", r.status_code == 400, short(r))
            r = await c.post("/api/v1/publico/auth/activar", json={"token": mal, "password": PASSWORD})
            check(f"3f. activar con token malo → 400 ({mal[:12]})", r.status_code == 400, short(r))

        # ── 4. Generar el usuario ──────────────────────────────────────────────────────
        r = await c.post("/api/v1/publico/auth/login", json={"identificador": dni, "password": PASSWORD})
        check("4a. antes de generarlo no se ingresa", r.status_code == 401, short(r))
        mails.clear()
        r = await c.post("/api/v1/publico/auth/activar", json={"token": token, "password": PASSWORD})
        check("4b. activar 200", r.status_code == 200, short(r))
        numero = (r.json().get("ciudadano") or {}).get("numero_usuario") if r.status_code == 200 else None
        check("4c. número de usuario de 6 dígitos", isinstance(numero, int) and 100001 <= numero <= 999999, str(numero))
        check("4d. el correo lo informa, con link al ingreso", len(mails) == 1 and str(numero) in mails[0]["subject"]
              and f"{PORTAL}/login" in mails[0]["html"], str([x["subject"] for x in mails]))
        r = await c.post("/api/v1/publico/auth/activar", json={"token": token, "password": PASSWORD})
        check("4e. el token ya no sirve", r.status_code == 400, short(r))
        r = await c.get(f"/api/v1/publico/alta/verificar?token={token}&m={slug}")
        check("4f. verificar con el token gastado → 400 con botón al alta", r.status_code == 400
              and f'href="{url_alta}"' in r.text, short(r))

        # ── 5. Ingreso con DNI o con número de usuario ─────────────────────────────────
        tok = ""
        for nombre, cuerpo in (("DNI", {"identificador": dni}), ("DNI con puntos", {"identificador": f"{dni[:2]}.{dni[2:5]}.{dni[5:]}"}),
                               ("número de usuario", {"identificador": str(numero)}), ("campo viejo `dni`", {"dni": dni})):
            r = await c.post("/api/v1/publico/auth/login", json={**cuerpo, "password": PASSWORD})
            ok = r.status_code == 200 and r.json()["ciudadano"]["numero_usuario"] == numero
            check(f"5a. login con {nombre}", ok, short(r))
            tok = r.json().get("access_token", tok) if r.status_code == 200 else tok
        r = await c.post("/api/v1/publico/auth/login", json={"identificador": str(numero), "password": "otra-clave"})
        check("5b. número correcto, clave mala → 401", r.status_code == 401, short(r))
        r = await c.post("/api/v1/publico/auth/login", json={"identificador": "123456789", "password": PASSWORD})
        check("5c. ni DNI ni usuario → 400 con el motivo", r.status_code == 400 and "número de usuario" in r.text, short(r))
        for ruta in ("/api/v1/publico/auth/me", "/api/v1/publico/perfil"):
            r = await c.get(ruta, headers={"Authorization": f"Bearer {tok}"})
            check(f"5e. {ruta} informa el número", r.status_code == 200 and r.json().get("numero_usuario") == numero, short(r))
        mails.clear()
        r = await c.post("/api/v1/publico/auth/recuperar-password", json={"identificador": str(numero)})
        check("5f. recuperar con el número de usuario manda el correo", r.status_code == 200 and len(mails) == 1
              and mails[0]["to"] == email, f"{short(r)} {len(mails)}")

        # ── 5g. Dos activaciones a la vez no repiten número ───────────────────────────
        tokens = []
        for _ in range(2):
            d2 = await dni_libre()
            mails.clear()
            await asyncio.sleep(0)
            r = await c.post("/api/v1/publico/alta/cuenta", json={**body, "doc_nro": d2, "cuil": cuil_valido(d2),
                             "telefono": "11" + d2[-8:], "email": f"alta.portal.{d2}@example.com"})
            mo = re.search(r"token=([0-9a-f-]{36})", mails[0]["html"]) if mails else None
            if mo:
                tokens.append(mo.group(1))
        rs = await asyncio.gather(*[c.post("/api/v1/publico/auth/activar", json={"token": t, "password": PASSWORD}) for t in tokens])
        nums = [x.json()["ciudadano"]["numero_usuario"] for x in rs if x.status_code == 200]
        check("5g. dos activaciones simultáneas: números distintos", len(nums) == 2 and len(set(nums)) == 2,
              f"{[short(x) for x in rs]}")

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
