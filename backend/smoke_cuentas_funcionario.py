# -*- coding: utf-8 -*-
"""
Smoke in-process — Circuito de alta de cuentas ZARIS desde la ficha del ciudadano
(mig 110, PLAN_CUENTAS_FUNCIONARIO.md).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_cuentas_funcionario.py

SOLO LOCAL: aborta si la DB no es zaris_dev (sin credenciales de prod, §40). Corre el app
FastAPI real con httpx.ASGITransport (memoria feedback_smoke_authz_asgi_in_process). El mail
corre en modo MOCK (settings.RESEND_API_KEY = "" — .env.local tiene una key REAL de Resend,
§5) y además se captura `enviar_mail` para leer la clave temporal y los links del cuerpo.

Cubre: alta de ciudadano con es_funcionario → POST /buc/ciudadanos/{id}/cuenta-zaris (403 nivel 2,
422 sin tilde, 201 admin, 409 repetido / username duplicado) → usuario vinculado + agente con datos
reales + mail con los dos links y el DNI → GET /cuentas → login por email Y por DNI con la temporal →
cambio forzado → credencial de vecino activada por link → login público OK → la clave de vecino NO
entra a ZARIS (401) → DNI de un vecino sin usuario (401) → campo `email` viejo sigue andando →
marcadores OpenAPI. Los datos quedan como demo (no se limpian).
"""
import asyncio
import logging
import os
import random
import sys
from typing import Any, Optional

import httpx

os.environ.setdefault("ENV_FILE", ".env.local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# La consola de Windows arranca en cp1252 y no imprime flechas/acentos del reporte.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402

if "zaris_dev" not in settings.ASYNC_DATABASE_URI:
    sys.exit("ABORT: este smoke es SOLO LOCAL (la DB configurada no es zaris_dev). No corre contra prod.")

# Mail en MOCK (nunca Resend real desde un smoke) + app de agentes "configurada" para
# poder afirmar que el mail lleva su link.
settings.RESEND_API_KEY = ""
settings.APP_AGENTES_FRONTEND_URL = "https://agentes.zaris.com.ar"

from app.core.auth import hash_password  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402
import app.services.email as email_mod  # noqa: E402

logging.getLogger("httpx").setLevel(logging.WARNING)

PWD_DEV = os.environ.get("ZARIS_QA_PASS") or "123456"
ADMIN_EMAIL = "ciudadanovl@municipio.gob.ar"
SUP_EMAIL = "f110sup@municipio.gob.ar"

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


async def q(sql: str, **params) -> list[dict]:
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(text(sql), params)).mappings().all()
        return [dict(r) for r in rows]


async def q1(sql: str, **params) -> Optional[dict]:
    rows = await q(sql, **params)
    return rows[0] if rows else None


async def exec_commit(sql: str, **params) -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(text(sql), params)
        await s.commit()


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


def ficha(dni: str, *, es_funcionario: bool, sufijo: str) -> dict[str, Any]:
    return {
        "doc_tipo": "DNI",
        "doc_nro": dni,
        "cuil": cuil_valido(dni),
        "nombre": "Mariana",
        "apellido": f"Funcionaria{sufijo}",
        "sexo": "MUJER",
        "fecha_nac": "1990-05-20",
        "id_nacionalidad": 1,
        "calle": "Av. Maipú 2502",
        "localidad": "Olivos",
        "provincia": "Buenos Aires",
        "telefono": "11" + dni[-8:],
        "email": f"f110.{dni}@example.com",
        "emp_chk": False,
        "es_funcionario": es_funcionario,
    }


async def setup() -> dict:
    admin = await q1("SELECT id_usuario, nivel_acceso, activo FROM usuarios WHERE email = :e", e=ADMIN_EMAIL)
    if not admin or admin["nivel_acceso"] != 1 or not admin["activo"]:
        sys.exit(f"ABORT: falta el admin local {ADMIN_EMAIL} (nivel 1, activo)")
    sub = await q1("SELECT id_subarea FROM subarea WHERE activo = TRUE ORDER BY id_subarea LIMIT 1")
    if not sub:
        sys.exit("ABORT: no hay subáreas activas en local")
    id_subarea = sub["id_subarea"]

    # Supervisor de prueba (nivel 2) con agente, para el 403. Idempotente.
    sup = await q1("SELECT id_usuario FROM usuarios WHERE email = :e", e=SUP_EMAIL)
    if not sup:
        await exec_commit("""
            INSERT INTO usuarios (nombre, nivel_acceso, username, email, password_hash, id_municipio,
                                  activo, buc_acceso, id_subarea, es_externo, debe_cambiar_password)
            VALUES ('f110sup', 2, 'f110sup', :e, :h, 1, TRUE, TRUE, :s, FALSE, FALSE)
        """, e=SUP_EMAIL, h=hash_password(PWD_DEV), s=id_subarea)
        sup = await q1("SELECT id_usuario FROM usuarios WHERE email = :e", e=SUP_EMAIL)
        await exec_commit("""
            INSERT INTO agentes (nombre, apellido, id_subarea, id_municipio, id_usuario, activo)
            SELECT 'f110sup', 'Smoke', :s, 1, :u, TRUE
             WHERE NOT EXISTS (SELECT 1 FROM agentes WHERE id_usuario = :u)
        """, s=id_subarea, u=sup["id_usuario"])
    return {"id_subarea": id_subarea}


async def main() -> int:
    ctx = await setup()
    id_subarea = ctx["id_subarea"]
    email_mod.enviar_mail = _captura_enviar_mail  # captura (y MOCK) de todo mail saliente

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://smoke.local", timeout=60) as c:
        # ── 0. Logins ────────────────────────────────────────────────────────────────
        r = await c.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": PWD_DEV})
        if not check("0a. login admin (campo email viejo sigue andando)", r.status_code == 200, short(r)):
            return 1
        HA = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = await c.post("/api/v1/auth/login", json={"identificador": SUP_EMAIL, "password": PWD_DEV})
        if not check("0b. login supervisor nivel 2 (identificador=email)", r.status_code == 200, short(r)):
            return 1
        HS = {"Authorization": f"Bearer {r.json()['access_token']}"}

        # ── 1. Alta de ciudadano funcionario (tilde) y de un vecino común ────────────
        dni_a = str(random.randint(50_000_000, 54_999_999))
        r = await c.post("/api/v1/buc/ciudadanos", json=ficha(dni_a, es_funcionario=True, sufijo=dni_a[-4:]), headers=HA)
        if not check("1a. alta ciudadano con es_funcionario=True → 201", r.status_code == 201, short(r)):
            return 1
        ciu_a = r.json()
        id_a = ciu_a["id_ciudadano"]
        check("1b. la respuesta trae es_funcionario=true", ciu_a.get("es_funcionario") is True, str(ciu_a.get("es_funcionario")))
        n_mails_alta = len(mails)
        check("1c. el alta encoló el mail de activación de App Vecinos", n_mails_alta >= 1, f"({n_mails_alta} mails)")

        dni_b = str(random.randint(55_000_000, 59_999_999))
        r = await c.post("/api/v1/buc/ciudadanos", json=ficha(dni_b, es_funcionario=False, sufijo=dni_b[-4:]), headers=HA)
        if not check("1d. alta ciudadano SIN tilde → 201", r.status_code == 201, short(r)):
            return 1
        id_b = r.json()["id_ciudadano"]

        r = await c.get(f"/api/v1/buc/ciudadanos/{id_a}/cuentas", headers=HA)
        cu = r.json() if r.status_code == 200 else {}
        check("1e. GET /cuentas antes: vecino pendiente, zaris null",
              r.status_code == 200 and cu.get("vecino", {}).get("estado") == "pendiente" and cu.get("zaris") is None, short(r))

        # ── 2. Guards ────────────────────────────────────────────────────────────────
        body = {"nivel_acceso": 4, "id_subarea": id_subarea, "username": f"mariana.funcionaria{dni_a[-4:]}"}
        r = await c.post(f"/api/v1/buc/ciudadanos/{id_a}/cuenta-zaris", json=body, headers=HS)
        check("2a. nivel 2 → 403", r.status_code == 403, short(r))
        r = await c.post(f"/api/v1/buc/ciudadanos/{id_b}/cuenta-zaris", json=body, headers=HA)
        check("2b. ciudadano sin tilde → 422", r.status_code == 422, short(r))
        r = await c.post(f"/api/v1/buc/ciudadanos/999999999/cuenta-zaris", json=body, headers=HA)
        check("2c. ciudadano inexistente → 404", r.status_code == 404, short(r))

        # ── 3. Alta de la cuenta ZARIS ───────────────────────────────────────────────
        mails.clear()
        r = await c.post(f"/api/v1/buc/ciudadanos/{id_a}/cuenta-zaris", json=body, headers=HA)
        if not check("3a. admin → 201", r.status_code == 201, short(r)):
            return 1
        cz = r.json()
        id_usuario = cz["id_usuario"]
        check("3b. respuesta: mail_enviado=true, cuenta_vecino_creada=false (ya la tenía del alta)",
              cz.get("mail_enviado") is True and cz.get("cuenta_vecino_creada") is False, str(cz))

        u = await q1("SELECT nombre, email, nivel_acceso, cuil, id_subarea, id_ciudadano, es_externo, debe_cambiar_password "
                     "FROM usuarios WHERE id_usuario = :id", id=id_usuario)
        check("3c. usuarios.id_ciudadano = ciudadano, nombre 'Apellido, Nombre', temporal marcada",
              bool(u) and u["id_ciudadano"] == id_a and u["nombre"].startswith("Funcionaria") and u["debe_cambiar_password"]
              and u["nivel_acceso"] == 4 and u["id_subarea"] == id_subarea and not u["es_externo"], str(u))
        a = await q1("SELECT nombre, apellido, dni, cuil, email, telefono, id_subarea, activo FROM agentes WHERE id_usuario = :id", id=id_usuario)
        check("3d. agente 1:1 con datos REALES de la ficha (nombre, apellido, DNI, CUIL, email, teléfono, subárea)",
              bool(a) and a["dni"] == dni_a and a["cuil"] == ciu_a["cuil"] and a["apellido"].startswith("Funcionaria")
              and a["nombre"] == "Mariana" and a["email"] == ciu_a["email"] and a["telefono"] == ciu_a["telefono"]
              and a["id_subarea"] == id_subarea and a["activo"], str(a))

        cred_mail = next((m for m in mails if "acceso a ZARIS" in m["subject"]), None)
        check("3e. se encoló el mail de credenciales (MOCK capturado)", cred_mail is not None, f"({len(mails)} mails: {[m['subject'] for m in mails]})")
        password_temporal = None
        if cred_mail:
            txt = cred_mail["text"]
            for line in txt.splitlines():
                if "Contraseña temporal" in line:
                    password_temporal = line.split(":")[-1].strip()
            login_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/frontend/login.html"
            check("3f. el mail lleva el link del backoffice, el de la app de agentes y el DNI",
                  login_url in txt and "https://agentes.zaris.com.ar" in txt and f"DNI {dni_a}" in txt
                  and login_url in cred_mail["html"] and "https://agentes.zaris.com.ar" in cred_mail["html"],
                  f"(temporal={'ok' if password_temporal else 'NO'})")
        if not password_temporal:
            print("       (sin clave temporal capturada: se saltean los logins)")
            return 1

        r = await c.get(f"/api/v1/buc/ciudadanos/{id_a}/cuentas", headers=HA)
        cu = r.json() if r.status_code == 200 else {}
        check("3g. GET /cuentas después: zaris con username y nivel",
              r.status_code == 200 and (cu.get("zaris") or {}).get("username") == body["username"]
              and (cu.get("zaris") or {}).get("nivel_acceso") == 4, short(r))
        r = await c.get(f"/api/v1/buc/usuarios/{id_usuario}", headers=HA)
        check("3h. GET /buc/usuarios/{id} expone id_ciudadano", r.status_code == 200 and r.json().get("id_ciudadano") == id_a, short(r))
        r = await c.get(f"/api/v1/buc/ciudadanos/{id_a}", headers=HA)
        check("3i. GET /buc/ciudadanos/{id} trae es_funcionario=true", r.status_code == 200 and r.json().get("es_funcionario") is True, short(r))

        # ── 4. Repetidos ─────────────────────────────────────────────────────────────
        r = await c.post(f"/api/v1/buc/ciudadanos/{id_a}/cuenta-zaris", json=body, headers=HA)
        check("4a. segunda vez sobre el mismo ciudadano → 409", r.status_code == 409, short(r))
        r = await c.put(f"/api/v1/buc/ciudadanos/{id_b}", json={"es_funcionario": True}, headers=HA)
        check("4b. PUT es_funcionario=true sobre el vecino B → 200", r.status_code == 200 and r.json().get("es_funcionario") is True, short(r))
        r = await c.post(f"/api/v1/buc/ciudadanos/{id_b}/cuenta-zaris", json=body, headers=HA)
        check("4c. username ya usado → 409", r.status_code == 409, short(r))

        # ── 5. Login del funcionario: email o DNI + temporal → cambio forzado ───────
        r = await c.post("/api/v1/auth/login", json={"identificador": ciu_a["email"], "password": password_temporal})
        check("5a. login por EMAIL con la temporal → 200 + debe_cambiar_password",
              r.status_code == 200 and r.json()["user"].get("debe_cambiar_password") is True, short(r))
        r = await c.post("/api/v1/auth/login", json={"identificador": dni_a, "password": password_temporal})
        if not check("5b. login por DNI con la temporal → 200 (mismo usuario)",
                     r.status_code == 200 and r.json()["user"]["id_usuario"] == id_usuario, short(r)):
            return 1
        HF = {"Authorization": f"Bearer {r.json()['access_token']}"}
        nueva = "ClaveNueva2026!"
        r = await c.post("/api/v1/auth/cambiar-password", json={"password_actual": None, "password_nueva": nueva}, headers=HF)
        check("5c. cambio forzado → 200", r.status_code == 200, short(r))
        r = await c.post("/api/v1/auth/login", json={"identificador": f" {dni_a} ", "password": nueva})
        check("5d. login por DNI (con espacios) con la clave nueva → 200 y sin cambio pendiente",
              r.status_code == 200 and r.json()["user"].get("debe_cambiar_password") is False, short(r))
        if r.status_code == 200:
            HF = {"Authorization": f"Bearer {r.json()['access_token']}"}
            r = await c.get("/api/v1/auth/me", headers=HF)
            check("5e. /auth/me con el token del login por DNI", r.status_code == 200 and r.json().get("id_usuario") == id_usuario, short(r))
        r = await c.post("/api/v1/auth/login", json={"identificador": dni_a, "password": password_temporal})
        check("5f. la temporal ya no sirve → 401", r.status_code == 401, short(r))

        # ── 6. Credencial de vecino del funcionario (segunda credencial) ─────────────
        tok = await q1("SELECT token_activacion::text AS t, activado FROM ciudadano_credencial WHERE id_ciudadano = :id", id=id_a)
        check("6a. credencial de vecino existe sin activar", bool(tok) and not tok["activado"] and tok["t"], str(tok))
        pass_vecino = "VecinoClave2026"
        r = await c.post("/api/v1/publico/auth/activar", json={"token": tok["t"], "password": pass_vecino})
        check("6b. activar por link → 200 (JWT publico)", r.status_code == 200 and "access_token" in r.json(), short(r))
        r = await c.post("/api/v1/publico/auth/login", json={"dni": dni_a, "password": pass_vecino})
        check("6c. login en la app del VECINO con DNI + clave de vecino → 200", r.status_code == 200, short(r))
        r = await c.post("/api/v1/auth/login", json={"identificador": dni_a, "password": pass_vecino})
        check("6d. la clave de vecino NO entra a ZARIS → 401", r.status_code == 401, short(r))
        r = await c.post("/api/v1/auth/login", json={"identificador": dni_b, "password": PWD_DEV})
        check("6e. DNI de un ciudadano sin usuario → 401", r.status_code == 401, short(r))
        r = await c.post("/api/v1/auth/login", json={"password": PWD_DEV})
        check("6f. sin identificador ni email → 401", r.status_code == 401, short(r))

        # ── 7. Marcadores OpenAPI ────────────────────────────────────────────────────
        r = await c.get("/openapi.json")
        spec = r.json()
        paths = spec.get("paths", {})
        login_props = spec.get("components", {}).get("schemas", {}).get("LoginRequest", {}).get("properties", {})
        check("7a. rutas nuevas en OpenAPI",
              "/api/v1/buc/ciudadanos/{id}/cuenta-zaris" in paths and "/api/v1/buc/ciudadanos/{id}/cuentas" in paths)
        check("7b. LoginRequest.identificador en OpenAPI", "identificador" in login_props)

    print(f"\nRESULTADO: {ok_count} OK, {fail_count} FAIL")
    for f in fallidos:
        print(f"  - {f['caso']}: {f['detalle']}")
    print(f"  datos demo: ciudadanos {id_a} (funcionaria, usuario {id_usuario}) y {id_b}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
