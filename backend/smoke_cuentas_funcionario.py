# -*- coding: utf-8 -*-
"""
Smoke in-process — Cuentas del ciudadano al GUARDAR la ficha (mig 110, PLAN_CUENTAS_FUNCIONARIO.md).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_cuentas_funcionario.py

SOLO LOCAL: aborta si la DB no es zaris_dev (sin credenciales de prod, §40). Corre el app
FastAPI real con httpx.ASGITransport (memoria feedback_smoke_authz_asgi_in_process). El mail
corre en modo MOCK (settings.RESEND_API_KEY = "" — .env.local tiene una key REAL de Resend,
§5) y además se captura `enviar_mail` para leer la clave temporal y los links del cuerpo.

Desde 2026-10-13 NO hay botón «Crear cuenta aplicación ZARIS»: el tilde «funcionario del
municipio» + `cuenta_zaris` (nivel, subárea, usuario) en el POST/PUT de la ficha crean la
cuenta ZARIS en el mismo guardado (solo admin), y guardar la ficha de un vecino sin credencial
le crea la cuenta de App Vecinos. Cubre: alta con tilde (201 admin / 422 sin datos / 403 nivel 2)
→ usuario vinculado + agente real + DOS mails → PUT con tilde (403 nivel 2, 422 sin datos, 409
usuario repetido, 200 crea, no-op si ya tiene, destildar no borra) → vecino legacy sin credencial
(PUT la crea una sola vez; email ajeno → sin cuenta) → ficha demo con DNI del rango 99.000.000
(ninguna vía le crea la cuenta de vecino hasta cargar el DNI real) → endpoint cuenta-zaris (403/404/409) →
login por email Y por DNI con la temporal → cambio forzado → credencial de vecino → marcadores
OpenAPI. Los datos quedan como demo (no se limpian).
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


def es_mail_credenciales(m: dict) -> bool:
    return "acceso a ZARIS" in m["subject"]


def ficha(dni: str, *, es_funcionario: bool, sufijo: str, cuenta_zaris: dict | None = None) -> dict[str, Any]:
    f: dict[str, Any] = {
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
    if cuenta_zaris is not None:
        f["cuenta_zaris"] = cuenta_zaris
    return f


async def setup() -> dict:
    admin = await q1("SELECT id_usuario, nivel_acceso, activo FROM usuarios WHERE email = :e", e=ADMIN_EMAIL)
    if not admin or admin["nivel_acceso"] != 1 or not admin["activo"]:
        sys.exit(f"ABORT: falta el admin local {ADMIN_EMAIL} (nivel 1, activo)")
    sub = await q1("SELECT id_subarea FROM subarea WHERE activo = TRUE ORDER BY id_subarea LIMIT 1")
    if not sub:
        sys.exit("ABORT: no hay subáreas activas en local")
    id_subarea = sub["id_subarea"]

    # Supervisor de prueba (nivel 2) con agente, para los 403. Idempotente.
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


async def quitar_credencial(id_ciudadano: int) -> None:
    """Simula una ficha anterior a la unificación de junio: persona en la BUC sin cuenta de vecino."""
    await exec_commit("DELETE FROM ciudadano_credencial WHERE id_ciudadano = :id", id=id_ciudadano)
    await exec_commit("DELETE FROM ciudadano_canal_preferido WHERE id_ciudadano = :id", id=id_ciudadano)


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

        # ── 1. Alta con el tilde: la cuenta ZARIS nace en el mismo guardado ──────────
        dni_a = str(random.randint(50_000_000, 54_999_999))
        cuenta_a = {"nivel_acceso": 4, "id_subarea": id_subarea, "username": f"mariana.funcionaria{dni_a[-4:]}"}
        r = await c.post("/api/v1/buc/ciudadanos", json=ficha(dni_a, es_funcionario=True, sufijo=dni_a[-4:]), headers=HA)
        check("1a. alta con tilde SIN cuenta_zaris (admin) → 422", r.status_code == 422, short(r))
        r = await c.post("/api/v1/buc/ciudadanos", json=ficha(dni_a, es_funcionario=True, sufijo=dni_a[-4:], cuenta_zaris=cuenta_a), headers=HS)
        check("1b. alta con tilde por nivel 2 → 403", r.status_code == 403, short(r))
        nada = await q1("SELECT 1 FROM ciudadanos WHERE doc_nro = :d", d=dni_a)
        check("1c. los rechazos no dejaron la persona a medias", nada is None, str(nada))

        mails.clear()
        r = await c.post("/api/v1/buc/ciudadanos", json=ficha(dni_a, es_funcionario=True, sufijo=dni_a[-4:], cuenta_zaris=cuenta_a), headers=HA)
        if not check("1d. alta con tilde + cuenta_zaris (admin) → 201", r.status_code == 201, short(r)):
            return 1
        ciu_a = r.json()
        id_a = ciu_a["id_ciudadano"]
        check("1e. la respuesta trae es_funcionario=true", ciu_a.get("es_funcionario") is True, str(ciu_a.get("es_funcionario")))
        u = await q1("SELECT id_usuario, nombre, email, nivel_acceso, id_subarea, id_ciudadano, es_externo, debe_cambiar_password "
                     "FROM usuarios WHERE id_ciudadano = :id", id=id_a)
        check("1f. usuario creado en el MISMO guardado: vinculado, 'Apellido, Nombre', temporal marcada, nivel 4, subárea",
              bool(u) and u["nombre"].startswith("Funcionaria") and u["debe_cambiar_password"]
              and u["nivel_acceso"] == 4 and u["id_subarea"] == id_subarea and not u["es_externo"], str(u))
        if not u:
            return 1
        id_usuario = u["id_usuario"]
        a = await q1("SELECT nombre, apellido, dni, cuil, email, telefono, id_subarea, activo FROM agentes WHERE id_usuario = :id", id=id_usuario)
        check("1g. agente 1:1 con datos REALES de la ficha (nombre, apellido, DNI, CUIL, email, teléfono, subárea)",
              bool(a) and a["dni"] == dni_a and a["cuil"] == ciu_a["cuil"] and a["apellido"].startswith("Funcionaria")
              and a["nombre"] == "Mariana" and a["email"] == ciu_a["email"] and a["telefono"] == ciu_a["telefono"]
              and a["id_subarea"] == id_subarea and a["activo"], str(a))
        cred_mails = [m for m in mails if es_mail_credenciales(m)]
        act_mails = [m for m in mails if not es_mail_credenciales(m)]
        check("1h. DOS mails: activación de App Vecinos + credenciales ZARIS", len(cred_mails) == 1 and len(act_mails) == 1,
              f"({[m['subject'] for m in mails]})")
        password_temporal = None
        if cred_mails:
            txt = cred_mails[0]["text"]
            for line in txt.splitlines():
                if "Contraseña temporal" in line:
                    password_temporal = line.split(":")[-1].strip()
            login_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/frontend/login.html"
            check("1i. el mail lleva el link del backoffice, el de la app de agentes y el DNI",
                  login_url in txt and "https://agentes.zaris.com.ar" in txt and f"DNI {dni_a}" in txt
                  and login_url in cred_mails[0]["html"] and "https://agentes.zaris.com.ar" in cred_mails[0]["html"],
                  f"(temporal={'ok' if password_temporal else 'NO'})")
        if not password_temporal:
            print("       (sin clave temporal capturada: se saltean los logins)")
            return 1
        r = await c.get(f"/api/v1/buc/ciudadanos/{id_a}/cuentas", headers=HA)
        cu = r.json() if r.status_code == 200 else {}
        check("1j. GET /cuentas: vecino pendiente + zaris con username y nivel",
              r.status_code == 200 and cu.get("vecino", {}).get("estado") == "pendiente"
              and (cu.get("zaris") or {}).get("username") == cuenta_a["username"]
              and (cu.get("zaris") or {}).get("nivel_acceso") == 4, short(r))
        r = await c.get(f"/api/v1/buc/usuarios/{id_usuario}", headers=HA)
        check("1k. GET /buc/usuarios/{id} expone id_ciudadano", r.status_code == 200 and r.json().get("id_ciudadano") == id_a, short(r))
        r = await c.get(f"/api/v1/buc/ciudadanos/{id_a}", headers=HA)
        check("1l. GET /buc/ciudadanos/{id} trae es_funcionario=true", r.status_code == 200 and r.json().get("es_funcionario") is True, short(r))

        # Vecino común (sin tilde) → 201 y un solo mail (activación).
        mails.clear()
        dni_b = str(random.randint(55_000_000, 59_999_999))
        r = await c.post("/api/v1/buc/ciudadanos", json=ficha(dni_b, es_funcionario=False, sufijo=dni_b[-4:]), headers=HA)
        if not check("1m. alta SIN tilde → 201", r.status_code == 201, short(r)):
            return 1
        id_b = r.json()["id_ciudadano"]
        check("1n. el vecino común recibe solo la activación de App Vecinos", len(mails) == 1 and not es_mail_credenciales(mails[0]),
              f"({[m['subject'] for m in mails]})")

        # ── 2. Edición de la ficha (PUT) con el tilde ────────────────────────────────
        cuenta_b = {"nivel_acceso": 3, "id_subarea": id_subarea, "username": f"mariana.funcionaria{dni_b[-4:]}"}
        r = await c.put(f"/api/v1/buc/ciudadanos/{id_b}", json={"es_funcionario": True, "cuenta_zaris": cuenta_b}, headers=HS)
        check("2a. nivel 2 pone el tilde → 403", r.status_code == 403, short(r))
        r = await c.put(f"/api/v1/buc/ciudadanos/{id_b}", json={"es_funcionario": True}, headers=HA)
        check("2b. admin pone el tilde SIN cuenta_zaris → 422", r.status_code == 422, short(r))
        sigue = await q1("SELECT es_funcionario FROM ciudadanos WHERE id_ciudadano = :id", id=id_b)
        check("2c. el 422 no dejó el tilde guardado", bool(sigue) and sigue["es_funcionario"] is False, str(sigue))
        r = await c.put(f"/api/v1/buc/ciudadanos/{id_b}", json={"es_funcionario": True, "cuenta_zaris": cuenta_a}, headers=HA)
        check("2d. username ya usado → 409", r.status_code == 409, short(r))
        mails.clear()
        r = await c.put(f"/api/v1/buc/ciudadanos/{id_b}", json={"es_funcionario": True, "cuenta_zaris": cuenta_b}, headers=HA)
        check("2e. admin pone el tilde + cuenta_zaris → 200 y es_funcionario=true",
              r.status_code == 200 and r.json().get("es_funcionario") is True, short(r))
        ub = await q1("SELECT id_usuario, nivel_acceso, id_ciudadano FROM usuarios WHERE id_ciudadano = :id", id=id_b)
        check("2f. la cuenta ZARIS nació en el PUT (nivel 3)", bool(ub) and ub["nivel_acceso"] == 3, str(ub))
        check("2g. un solo mail: credenciales (la activación de vecino ya la tenía del alta)",
              len(mails) == 1 and es_mail_credenciales(mails[0]), f"({[m['subject'] for m in mails]})")
        mails.clear()
        r = await c.put(f"/api/v1/buc/ciudadanos/{id_b}", json={"telefono": "11" + dni_b[-8:][::-1], "cuenta_zaris": cuenta_b}, headers=HA)
        n_usr = await q1("SELECT count(*) AS n FROM usuarios WHERE id_ciudadano = :id", id=id_b)
        check("2h. volver a guardar (teléfono) con cuenta_zaris → 200, sin usuario nuevo ni mail (no-op)",
              r.status_code == 200 and n_usr["n"] == 1 and len(mails) == 0, f"{short(r)} usuarios={n_usr['n']} mails={len(mails)}")
        r = await c.put(f"/api/v1/buc/ciudadanos/{id_b}", json={"observaciones": "editado por nivel 2"}, headers=HS)
        check("2i. nivel 2 edita otros datos de un funcionario con cuenta → 200", r.status_code == 200, short(r))
        r = await c.put(f"/api/v1/buc/ciudadanos/{id_b}", json={"es_funcionario": False}, headers=HA)
        n_usr = await q1("SELECT count(*) AS n FROM usuarios WHERE id_ciudadano = :id", id=id_b)
        check("2j. destildar → 200 y la cuenta ZARIS NO se borra (la baja sigue en Usuarios)",
              r.status_code == 200 and r.json().get("es_funcionario") is False and n_usr["n"] == 1, short(r))
        r = await c.put(f"/api/v1/buc/ciudadanos/{id_b}", json={"es_funcionario": True}, headers=HA)
        check("2k. volver a tildar a quien YA tiene cuenta → 200 sin pedir cuenta_zaris", r.status_code == 200, short(r))

        # ── 3. Vecino anterior a la unificación: guardar la ficha le crea la cuenta ──
        dni_c = str(random.randint(60_000_000, 64_999_999))
        r = await c.post("/api/v1/buc/ciudadanos", json=ficha(dni_c, es_funcionario=False, sufijo=dni_c[-4:]), headers=HA)
        if not check("3a. alta del vecino C → 201 (después se le quita la credencial para simular una ficha vieja)", r.status_code == 201, short(r)):
            return 1
        id_c = r.json()["id_ciudadano"]
        await quitar_credencial(id_c)
        r = await c.get(f"/api/v1/buc/ciudadanos/{id_c}/cuentas", headers=HA)
        check("3b. GET /cuentas: sin_cuenta", r.status_code == 200 and r.json().get("vecino", {}).get("estado") == "sin_cuenta", short(r))
        mails.clear()
        r = await c.put(f"/api/v1/buc/ciudadanos/{id_c}", json={"observaciones": "ficha vieja guardada por nivel 2"}, headers=HS)
        cred = await q1("SELECT token_activacion::text AS t, activado FROM ciudadano_credencial WHERE id_ciudadano = :id", id=id_c)
        check("3c. PUT por nivel 2 → 200 y nace la credencial de App Vecinos + mail de activación",
              r.status_code == 200 and bool(cred) and not cred["activado"] and len(mails) == 1 and not es_mail_credenciales(mails[0]),
              f"{short(r)} cred={cred} mails={len(mails)}")
        ev = await q1("SELECT estado_validacion FROM ciudadanos WHERE id_ciudadano = :id", id=id_c)
        check("3d. la ficha la cargó un agente → estado_validacion=verificado", bool(ev) and ev["estado_validacion"] == "verificado", str(ev))
        mails.clear()
        r = await c.put(f"/api/v1/buc/ciudadanos/{id_c}", json={"observaciones": "segundo guardado"}, headers=HA)
        cred2 = await q1("SELECT token_activacion::text AS t FROM ciudadano_credencial WHERE id_ciudadano = :id", id=id_c)
        check("3e. segundo guardado: ni mail nuevo ni token regenerado (pendiente no se toca)",
              r.status_code == 200 and len(mails) == 0 and cred2 and cred2["t"] == cred["t"], f"mails={len(mails)}")
        r = await c.get(f"/api/v1/buc/ciudadanos/{id_c}/cuentas", headers=HA)
        check("3f. GET /cuentas: pendiente", r.status_code == 200 and r.json().get("vecino", {}).get("estado") == "pendiente", short(r))

        # Email que ya es de la cuenta de OTRA persona: guarda igual, sin cuenta ni mail.
        dni_e = str(random.randint(65_000_000, 69_999_999))
        r = await c.post("/api/v1/buc/ciudadanos", json=ficha(dni_e, es_funcionario=False, sufijo=dni_e[-4:]), headers=HA)
        if not check("3g. alta del vecino E → 201", r.status_code == 201, short(r)):
            return 1
        id_e = r.json()["id_ciudadano"]
        await quitar_credencial(id_e)
        await exec_commit("UPDATE ciudadanos SET email = :e WHERE id_ciudadano = :id", e=ciu_a["email"], id=id_e)
        mails.clear()
        r = await c.put(f"/api/v1/buc/ciudadanos/{id_e}", json={"observaciones": "email compartido"}, headers=HA)
        cred_e = await q1("SELECT 1 FROM ciudadano_credencial WHERE id_ciudadano = :id", id=id_e)
        check("3h. email de la cuenta de otra persona → 200, sin credencial ni mail (queda 'sin cuenta')",
              r.status_code == 200 and cred_e is None and len(mails) == 0, f"{short(r)} cred={cred_e} mails={len(mails)}")

        # Ficha demo (DNI del rango reservado 99.000.000, mig 118): ninguna vía le crea la
        # cuenta de App Vecinos ni le manda mails, hasta que se carga el DNI real.
        dni_d = None
        for _ in range(20):
            cand = str(random.randint(99_500_000, 99_999_999))
            if not await q1("SELECT 1 FROM ciudadanos WHERE doc_nro = :d", d=cand):
                dni_d = cand
                break
        mails.clear()
        r = await c.post("/api/v1/buc/ciudadanos", json=ficha(dni_d, es_funcionario=False, sufijo=dni_d[-4:]), headers=HA)
        if not check("3i. alta de una ficha con DNI de prueba → 201", r.status_code == 201, short(r)):
            return 1
        id_d = r.json()["id_ciudadano"]
        cred_d = await q1("SELECT 1 FROM ciudadano_credencial WHERE id_ciudadano = :id", id=id_d)
        check("3j. el alta NO crea la cuenta de App Vecinos ni manda mail", cred_d is None and len(mails) == 0,
              f"cred={cred_d} mails={len(mails)}")
        r = await c.put(f"/api/v1/buc/ciudadanos/{id_d}", json={"observaciones": "ficha demo guardada"}, headers=HS)
        cred_d = await q1("SELECT 1 FROM ciudadano_credencial WHERE id_ciudadano = :id", id=id_d)
        check("3k. guardar la ficha demo (nivel 2) → 200, sigue sin cuenta y sin mail",
              r.status_code == 200 and cred_d is None and len(mails) == 0, f"{short(r)} cred={cred_d} mails={len(mails)}")
        r = await c.get(f"/api/v1/buc/ciudadanos/{id_d}/cuentas", headers=HA)
        vd = r.json().get("vecino", {}) if r.status_code == 200 else {}
        check("3l. GET /cuentas: sin_cuenta + ficha_demo=true", vd.get("estado") == "sin_cuenta" and vd.get("ficha_demo") is True, short(r))
        r = await c.post(f"/api/v1/buc/ciudadanos/{id_d}/cuenta-vecino", headers=HA)
        check("3m. POST /cuenta-vecino sobre la ficha demo → 422 (no 'ya activada')",
              r.status_code == 422 and "DNI de prueba" in r.text and len(mails) == 0, short(r))
        slug = await q1("SELECT codigo_corto FROM municipios WHERE activo = TRUE ORDER BY id_municipio LIMIT 1")
        r = await c.post("/api/v1/publico/alta/activar-existente",
                         json={"municipio_slug": slug["codigo_corto"], "doc_nro": dni_d})
        cred_d = await q1("SELECT 1 FROM ciudadano_credencial WHERE id_ciudadano = :id", id=id_d)
        check("3n. 'Ya estoy registrado' con el DNI de prueba → 200 genérico, sin cuenta ni mail",
              r.status_code == 200 and cred_d is None and len(mails) == 0, f"{short(r)} cred={cred_d} mails={len(mails)}")
        r = await c.get(f"/api/v1/buc/ciudadanos/{id_c}/cuentas", headers=HA)
        check("3o. una ficha con DNI real no es ficha demo", r.status_code == 200 and r.json()["vecino"].get("ficha_demo") is False, short(r))
        dni_real = str(random.randint(45_000_000, 49_999_999))
        r = await c.put(f"/api/v1/buc/ciudadanos/{id_d}", json={"doc_nro": dni_real, "cuil": cuil_valido(dni_real)}, headers=HA)
        cred_d = await q1("SELECT activado FROM ciudadano_credencial WHERE id_ciudadano = :id", id=id_d)
        check("3p. al cargar el DNI real, ESE guardado crea la cuenta + un mail de activación",
              r.status_code == 200 and bool(cred_d) and not cred_d["activado"] and len(mails) == 1
              and not es_mail_credenciales(mails[0]), f"{short(r)} cred={cred_d} mails={len(mails)}")

        # ── 4. Endpoint POST /cuenta-zaris (sigue para la API) ───────────────────────
        r = await c.post(f"/api/v1/buc/ciudadanos/{id_a}/cuenta-zaris", json=cuenta_a, headers=HS)
        check("4a. nivel 2 → 403", r.status_code == 403, short(r))
        r = await c.post(f"/api/v1/buc/ciudadanos/999999999/cuenta-zaris", json=cuenta_a, headers=HA)
        check("4b. ciudadano inexistente → 404", r.status_code == 404, short(r))
        r = await c.post(f"/api/v1/buc/ciudadanos/{id_a}/cuenta-zaris", json=cuenta_a, headers=HA)
        check("4c. ya tiene cuenta → 409", r.status_code == 409, short(r))
        r = await c.post(f"/api/v1/buc/ciudadanos/{id_c}/cuenta-zaris", json=cuenta_a, headers=HA)
        check("4d. ciudadano sin tilde → 422", r.status_code == 422, short(r))

        # ── 5. Login del funcionario A: email o DNI + temporal → cambio forzado ─────
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
        r = await c.post("/api/v1/auth/login", json={"identificador": dni_c, "password": PWD_DEV})
        check("6e. DNI de un ciudadano sin usuario → 401", r.status_code == 401, short(r))
        r = await c.post("/api/v1/auth/login", json={"password": PWD_DEV})
        check("6f. sin identificador ni email → 401", r.status_code == 401, short(r))

        # ── 7. Marcadores OpenAPI ────────────────────────────────────────────────────
        r = await c.get("/openapi.json")
        spec = r.json()
        paths = spec.get("paths", {})
        schemas = spec.get("components", {}).get("schemas", {})
        login_props = schemas.get("LoginRequest", {}).get("properties", {})
        check("7a. rutas de cuentas en OpenAPI",
              "/api/v1/buc/ciudadanos/{id}/cuenta-zaris" in paths and "/api/v1/buc/ciudadanos/{id}/cuentas" in paths)
        check("7b. LoginRequest.identificador en OpenAPI", "identificador" in login_props)
        check("7c. cuenta_zaris en CiudadanoCreate y CiudadanoUpdate (marcador del deploy)",
              "cuenta_zaris" in schemas.get("CiudadanoCreate", {}).get("properties", {})
              and "cuenta_zaris" in schemas.get("CiudadanoUpdate", {}).get("properties", {}))
        check("7d. ficha_demo en CuentaVecinoEstado (marcador del deploy 2026-10-22)",
              "ficha_demo" in schemas.get("CuentaVecinoEstado", {}).get("properties", {}))

    print(f"\nRESULTADO: {ok_count} OK, {fail_count} FAIL")
    for f in fallidos:
        print(f"  - {f['caso']}: {f['detalle']}")
    print(f"  datos demo: ciudadanos {id_a} (funcionaria, usuario {id_usuario}), {id_b} (funcionaria nivel 3), "
          f"{id_c} (vecina pendiente), {id_e} (sin cuenta, email compartido), {id_d} (ex ficha demo, ya con DNI real)")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
