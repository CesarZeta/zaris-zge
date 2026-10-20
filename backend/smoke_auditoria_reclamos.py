# -*- coding: utf-8 -*-
"""
Smoke in-process — Auditoría de reclamos POSTERIOR al cierre (mig 112, PLAN_AUDITORIA_RECLAMOS.md).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_auditoria_reclamos.py

SOLO LOCAL: aborta si la DB no es zaris_dev (sin credenciales de prod, §40). Corre el app
FastAPI real con httpx.ASGITransport (memoria feedback_smoke_authz_asgi_in_process); el mail
corre en modo MOCK (settings.RESEND_API_KEY = "") y además se captura `enviar_mail` para leer
el mail al vecino (patrón smoke_cuentas_funcionario.py).

Cubre: envío a auditoría (403 consultor / 403 supervisor de otra subárea / 422 no Resuelto /
201 supervisor de la subárea / 422 ya abierta) → bloqueos del reclamo En auditoría (/estado,
editar, subreclamo, cancelar, OT, aviso, mesa supervisor) → mesa del auditor → aprobar (403
consultor / 200 → Auditado-aprobado, fecha_cierre intacta, sin encuesta ni aviso) → observar
(422 sin observaciones / 200 → Auditado-observado + reclamo NUEVO de retrabajo vinculado + mail
genérico, aviso y push al vecino — F4) → observar SIN retrabajo (generar_retrabajo=false: sin
reclamo nuevo ni aviso) → el vecino ve 'Resuelto' en los auditados y VE el retrabajo, con la
descripción de su reclamo original y sin la observación del auditor → dashboard (activos
excluye, mapa muestra En auditoría) → cierre de OT operativa de un tipo audit=true va a Resuelto
(sin auditoría previa) → OT de auditoría por /estado (Terminada 422, Cancelada devuelve a
Resuelto, el vecino no ve «Auditoría cancelada») → resolver el retrabajo encuesta aunque la
anti-fatiga lo hubiera bloqueado → BI → marcadores OpenAPI. Los datos quedan como demo.
"""
import asyncio
import logging
import os
import sys
from typing import Any, Optional

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

settings.RESEND_API_KEY = ""  # mail en MOCK
PORTAL_SMOKE = "https://vecinos.smoke.local"
settings.APP_VECINOS_FRONTEND_URL = PORTAL_SMOKE  # el mail de retrabajo exige portal configurado

from app.core.auth import hash_password  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.services import email as email_mod  # noqa: E402

MAILS: list[dict] = []


async def _captura_enviar_mail(to: str, subject: str, body_html: str, body_text: str | None = None,
                               from_override: str | None = None) -> bool:
    MAILS.append({"to": to, "subject": subject, "html": body_html, "text": body_text or ""})
    return True

email_mod.enviar_mail = _captura_enviar_mail  # captura (y MOCK) de todo mail saliente

logging.getLogger("httpx").setLevel(logging.WARNING)

PWD_DEV = os.environ.get("ZARIS_QA_PASS") or "123456"
ADMIN_EMAIL = "ciudadanovl@municipio.gob.ar"
DNI_VECINO = "28547123"          # vecino local con credencial (clave dev)
SUB_A, SUB_B = 20, 21            # Calles y veredas / Espacios verdes (local)
USERS = {                        # email: (nivel, id_subarea del agente | None, es_auditor)
    "f112supa@municipio.gob.ar": (2, SUB_A, False),
    "f112supb@municipio.gob.ar": (2, SUB_B, False),
    "f112aud@municipio.gob.ar":  (4, SUB_B, True),   # auditor de OTRA subárea (regla cruzada)
    "f112ag@municipio.gob.ar":   (4, SUB_A, False),  # agente operativo de la subárea A
    "f112cons@municipio.gob.ar": (5, None, False),
}

ok_count = 0
fail_count = 0
fallidos: list[dict] = []


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
    return f"({r.status_code}) {r.text[:n]}"


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


async def reclamo(id_reclamo: int) -> dict:
    return await q1("""SELECT estado, fecha_cierre, fecha_inicio_auditoria, fecha_fin_auditoria,
                              resultado_auditoria, id_reclamo_origen_auditoria, canal_origen,
                              id_ciudadano, id_tipo_reclamo, direccion, nro_reclamo
                       FROM reclamos WHERE id_reclamo = :id""", id=id_reclamo)


async def n_envios(id_reclamo: int) -> int:
    return (await q1("SELECT COUNT(*) AS n FROM encuesta_envio WHERE id_reclamo = :id AND activo", id=id_reclamo))["n"]


async def n_avisos(id_ciudadano: int) -> int:
    return (await q1("SELECT COUNT(*) AS n FROM ciudadano_aviso WHERE id_ciudadano = :id", id=id_ciudadano))["n"]


async def ultimo_aviso(id_ciudadano: int) -> Optional[dict]:
    return await q1("""SELECT titulo, mensaje, url_destino, recurso_id FROM ciudadano_aviso
                       WHERE id_ciudadano = :id ORDER BY id_ciudadano_aviso DESC LIMIT 1""", id=id_ciudadano)


async def setup() -> dict:
    admin = await q1("SELECT id_usuario, nivel_acceso, activo FROM usuarios WHERE email = :e", e=ADMIN_EMAIL)
    if not admin or admin["nivel_acceso"] != 1 or not admin["activo"]:
        sys.exit(f"ABORT: falta el admin local {ADMIN_EMAIL} (nivel 1, activo)")
    vec = await q1("SELECT id_ciudadano, email FROM ciudadanos WHERE doc_nro = :d AND activo = TRUE", d=DNI_VECINO)
    if not vec or "@" not in (vec["email"] or ""):
        sys.exit(f"ABORT: falta el vecino local DNI {DNI_VECINO} con email (el mail de retrabajo lo necesita)")
    tipo_a = await q1("SELECT id_tipo_reclamo FROM tipo_reclamo WHERE id_subarea = :s AND activo ORDER BY id_tipo_reclamo LIMIT 1", s=SUB_A)
    if not tipo_a:
        sys.exit(f"ABORT: la subárea {SUB_A} no tiene tipos de reclamo activos en local")
    # El tipo queda con audit=TRUE para probar que el cierre de OT YA NO bifurca a auditoría.
    await exec_commit("UPDATE tipo_reclamo SET audit = TRUE WHERE id_tipo_reclamo = :t", t=tipo_a["id_tipo_reclamo"])

    ids: dict[str, dict] = {}
    for email, (nivel, sub, es_aud) in USERS.items():
        u = await q1("SELECT id_usuario FROM usuarios WHERE email = :e", e=email)
        if not u:
            uname = email.split("@")[0]
            await exec_commit("""
                INSERT INTO usuarios (nombre, nivel_acceso, username, email, password_hash, id_municipio,
                                      activo, buc_acceso, id_subarea, es_externo, debe_cambiar_password)
                VALUES (:n, :niv, :n, :e, :h, 1, TRUE, TRUE, :s, FALSE, FALSE)
            """, n=uname, niv=nivel, e=email, h=hash_password(PWD_DEV), s=sub)
            u = await q1("SELECT id_usuario FROM usuarios WHERE email = :e", e=email)
        ag = None
        if sub is not None:
            await exec_commit("""
                INSERT INTO agentes (nombre, apellido, id_subarea, id_municipio, id_usuario, activo, es_auditor)
                SELECT :n, 'Smoke112', :s, 1, :u, TRUE, :aud
                 WHERE NOT EXISTS (SELECT 1 FROM agentes WHERE id_usuario = :u)
            """, n=email.split("@")[0], s=sub, u=u["id_usuario"], aud=es_aud)
            ag = await q1("SELECT id_agente FROM agentes WHERE id_usuario = :u AND activo", u=u["id_usuario"])
        ids[email] = {"id_usuario": u["id_usuario"], "id_agente": ag["id_agente"] if ag else None}
    return {"id_ciudadano": vec["id_ciudadano"], "email_vecino": vec["email"].strip(),
            "id_tipo_a": tipo_a["id_tipo_reclamo"], "users": ids}


async def main() -> int:
    ctx = await setup()
    id_c = ctx["id_ciudadano"]
    tipo_a = ctx["id_tipo_a"]
    U = ctx["users"]
    id_aud_agente = U["f112aud@municipio.gob.ar"]["id_agente"]
    id_ag_agente = U["f112ag@municipio.gob.ar"]["id_agente"]

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://smoke.local", timeout=60) as c:
        # ── 0. Logins ────────────────────────────────────────────────────────────────
        H: dict[str, dict] = {}
        for nombre, email in [("admin", ADMIN_EMAIL)] + [(e.split("@")[0], e) for e in USERS]:
            r = await c.post("/api/v1/auth/login", json={"identificador": email, "password": PWD_DEV})
            if not check(f"0. login {nombre}", r.status_code == 200, short(r)):
                return 1
            H[nombre] = {"Authorization": f"Bearer {r.json()['access_token']}"}
        HA, HSA, HSB, HAUD, HAG, HCONS = (H["admin"], H["f112supa"], H["f112supb"],
                                          H["f112aud"], H["f112ag"], H["f112cons"])
        r = await c.post("/api/v1/publico/auth/login", json={"dni": DNI_VECINO, "password": PWD_DEV})
        if not check("0. login vecino", r.status_code == 200, short(r)):
            return 1
        HV = {"Authorization": f"Bearer {r.json()['access_token']}"}

        def nuevo_reclamo(desc: str) -> dict[str, Any]:
            return {"id_ciudadano": id_c, "id_tipo_reclamo": tipo_a, "descripcion": desc,
                    "direccion": "Av. Maipú 2502, Olivos", "canal_origen": "presencial",
                    "latitud": -34.5125, "longitud": -58.4895, "fuente_geolocalizacion": "pin_manual"}

        # ── 1. Reclamo R1: alta + cierre directo (admin) ─────────────────────────────
        r = await c.post("/api/v1/reclamos", json=nuevo_reclamo("Smoke 112 — R1 auditoría aprobada"), headers=HA)
        check("1a. alta R1 → 201", r.status_code == 201, short(r))
        R1 = r.json()["id_reclamo"]
        r = await c.put(f"/api/v1/reclamos/{R1}/estado", json={"estado": "Resuelto", "nota": "cierre directo"}, headers=HSA)
        check("1b. R1 cierre directo (supervisor de la subárea) → Resuelto", r.status_code == 200, short(r))
        d = await reclamo(R1)
        cierre_r1 = d["fecha_cierre"]
        check("1c. R1 fecha_cierre seteada", cierre_r1 is not None, str(cierre_r1))
        r = await c.post("/api/v1/reclamos", json=nuevo_reclamo("Smoke 112 — R0 sin asignar"), headers=HA)
        R0 = r.json()["id_reclamo"]
        avisos_base = await n_avisos(id_c)
        envios_r1 = await n_envios(R1)

        # ── 2. Enviar a auditoría ────────────────────────────────────────────────────
        r = await c.post(f"/api/v1/reclamos/{R1}/auditoria", json={}, headers=HCONS)
        check("2a. consultor (n5) → 403", r.status_code == 403, short(r))
        r = await c.post(f"/api/v1/reclamos/{R1}/auditoria", json={}, headers=HSB)
        check("2b. supervisor de OTRA subárea → 403", r.status_code == 403, short(r))
        r = await c.post(f"/api/v1/reclamos/{R0}/auditoria", json={}, headers=HA)
        check("2c. reclamo Sin asignar → 422", r.status_code == 422, short(r))
        r = await c.post(f"/api/v1/reclamos/{R1}/auditoria",
                         json={"observaciones": "Control de calidad trimestral"}, headers=HSA)
        check("2d. supervisor de la subárea → 201", r.status_code == 201, short(r))
        OT1 = r.json().get("id_ot")
        check("2e. respuesta trae id_ot + nro_ot + estado En auditoría",
              OT1 is not None and r.json().get("nro_ot") and r.json().get("estado") == "En auditoría", short(r))
        d = await reclamo(R1)
        check("2f. R1 En auditoría, fecha_inicio seteada, fecha_cierre INTACTA",
              d["estado"] == "En auditoría" and d["fecha_inicio_auditoria"] is not None and d["fecha_cierre"] == cierre_r1,
              f"{d['estado']} inicio={d['fecha_inicio_auditoria']} cierre={d['fecha_cierre']}")
        ot = await q1("SELECT es_auditoria, id_agente, id_supervisor_asigna, observaciones FROM ordenes_trabajo WHERE id_ot = :id", id=OT1)
        check("2g. OT es_auditoria, sin auditor asignado, supervisor = quien envió",
              ot and ot["es_auditoria"] and ot["id_agente"] is None
              and ot["id_supervisor_asigna"] == U["f112supa@municipio.gob.ar"]["id_usuario"], str(ot))
        r = await c.post(f"/api/v1/reclamos/{R1}/auditoria", json={}, headers=HA)
        check("2h. segundo envío → 422 (no está Resuelto)", r.status_code == 422, short(r))
        h = await q1("SELECT accion, estado_anterior, estado_nuevo FROM reclamo_historial WHERE id_reclamo = :id ORDER BY id_historial DESC LIMIT 1", id=R1)
        check("2i. historial 'Enviado a auditoría' Resuelto→En auditoría",
              h and h["accion"] == "Enviado a auditoría" and h["estado_anterior"] == "Resuelto" and h["estado_nuevo"] == "En auditoría", str(h))
        check("2j. sin aviso al vecino por el envío", await n_avisos(id_c) == avisos_base)

        # ── 3. Bloqueos sobre un reclamo En auditoría ────────────────────────────────
        r = await c.put(f"/api/v1/reclamos/{R1}/estado", json={"estado": "Auditado"}, headers=HA)
        check("3a. /estado → Auditado → 422", r.status_code == 422, short(r))
        r = await c.put(f"/api/v1/reclamos/{R0}/estado", json={"estado": "En auditoría"}, headers=HA)
        check("3b. /estado → En auditoría → 422", r.status_code == 422, short(r))
        r = await c.put(f"/api/v1/reclamos/{R1}/estado", json={"estado": "En gestión"}, headers=HA)
        check("3c. /estado En auditoría → En gestión → 422", r.status_code == 422, short(r))
        r = await c.put(f"/api/v1/reclamos/{R1}", json={"observaciones": "x"}, headers=HA)
        check("3d. editar → 422", r.status_code == 422, short(r))
        r = await c.post(f"/api/v1/reclamos/{R1}/subreclamo", json={"descripcion": "x", "id_tipo_reclamo": tipo_a}, headers=HA)
        check("3e. subreclamo → 422", r.status_code == 422, short(r))
        r = await c.put(f"/api/v1/reclamos/{R1}/cancelar", json={"motivo": "x"}, headers=HA)
        check("3f. cancelar → 422", r.status_code == 422, short(r))
        r = await c.post("/api/v1/ot", json={"id_reclamo": R1, "id_agente": id_ag_agente}, headers=HA)
        check("3g. POST /ot → 422", r.status_code == 422, short(r))
        r = await c.post(f"/api/v1/reclamos/{R1}/avisar-supervisor", json={"accion_sugerida": "Resolver"}, headers=HA)
        check("3h. avisar-supervisor → 422", r.status_code == 422, short(r))
        r = await c.get("/api/v1/ot/mesa/supervisor", params={"id_subarea": SUB_A}, headers=HA)
        ids_mesa = {x["id_reclamo"] for x in r.json()} if r.status_code == 200 else set()
        check("3i. mesa supervisor NO lista R1 (sí R0)", r.status_code == 200 and R1 not in ids_mesa and R0 in ids_mesa, short(r, 80))

        # ── 4. Mesa del auditor + aprobar ────────────────────────────────────────────
        r = await c.get("/api/v1/ot/auditor/me", headers=HAUD)
        ots_mesa = r.json().get("ots", []) if r.status_code == 200 else []
        fila = next((o for o in ots_mesa if o["id_ot"] == OT1), None)
        check("4a. mesa auditor lista la OT de R1 con datos del cierre",
              fila is not None and fila.get("reclamo_estado") == "En auditoría" and fila.get("reclamo_fecha_cierre"), short(r, 80))
        r = await c.put(f"/api/v1/ot/{OT1}/aprobar", json={}, headers=HCONS)
        check("4b. aprobar consultor → 403", r.status_code == 403, short(r))
        r = await c.put(f"/api/v1/ot/{OT1}/aprobar", json={"observaciones": "Trabajo conforme"}, headers=HAUD)
        check("4c. aprobar auditor → 200", r.status_code == 200 and r.json().get("estado_reclamo") == "Auditado", short(r))
        d = await reclamo(R1)
        check("4d. R1 Auditado / aprobado, fecha_fin seteada, fecha_cierre INTACTA",
              d["estado"] == "Auditado" and d["resultado_auditoria"] == "aprobado"
              and d["fecha_fin_auditoria"] is not None and d["fecha_cierre"] == cierre_r1, str(d))
        ot = await q1("SELECT e.nombre AS estado, ot.resultado_auditoria FROM ordenes_trabajo ot JOIN estado_ot e ON e.id_estado_ot = ot.id_estado WHERE ot.id_ot = :id", id=OT1)
        check("4e. OT Terminada / aprobada", ot and ot["estado"] == "Terminada" and ot["resultado_auditoria"] == "aprobada", str(ot))
        check("4f. sin encuesta nueva ni aviso al vecino por la auditoría",
              await n_envios(R1) == envios_r1 and await n_avisos(id_c) == avisos_base)
        r = await c.put(f"/api/v1/ot/{OT1}/aprobar", json={}, headers=HAUD)
        check("4g. aprobar de nuevo → 422", r.status_code == 422, short(r))
        r = await c.put(f"/api/v1/reclamos/{R1}", json={"observaciones": "x"}, headers=HA)
        check("4h. editar un Auditado → 422", r.status_code == 422, short(r))

        # ── 5. R2: auditoría observada → retrabajo ───────────────────────────────────
        r = await c.post("/api/v1/reclamos", json=nuevo_reclamo("Smoke 112 — R2 auditoría observada"), headers=HA)
        R2 = r.json()["id_reclamo"]
        await c.put(f"/api/v1/reclamos/{R2}/estado", json={"estado": "Resuelto"}, headers=HSA)
        r = await c.post(f"/api/v1/reclamos/{R2}/auditoria",
                         json={"id_agente_auditor": id_aud_agente}, headers=HSA)
        check("5a. envío con auditor puntual → 201", r.status_code == 201, short(r))
        OT2 = r.json()["id_ot"]
        r = await c.post(f"/api/v1/reclamos/{R0}/auditoria", json={}, headers=HA)
        r = await c.put(f"/api/v1/ot/{OT2}/observar", json={}, headers=HAUD)
        check("5b. observar sin observaciones → 422", r.status_code == 422, short(r))
        r = await c.put(f"/api/v1/ot/{OT2}/observar",
                        json={"observaciones": "x", "generar_retrabajo": "si"}, headers=HAUD)
        check("5b2. generar_retrabajo no booleano → 422", r.status_code == 422, short(r))
        avisos_antes = await n_avisos(id_c)
        MAILS.clear()
        OBS = "Quedó un pozo sin tapar"
        # Sin generar_retrabajo: el default (true) mantiene el comportamiento del bundle anterior.
        r = await c.put(f"/api/v1/ot/{OT2}/observar", json={"observaciones": OBS}, headers=HAUD)
        check("5c. observar (default) → 200 con retrabajo", r.status_code == 200 and r.json().get("id_reclamo_retrabajo"), short(r))
        RT = r.json().get("id_reclamo_retrabajo")
        d2 = await reclamo(R2)
        check("5d. R2 Auditado / observado", d2["estado"] == "Auditado" and d2["resultado_auditoria"] == "observado", str(d2))
        dt = await reclamo(RT) if RT else None
        check("5e. retrabajo Sin asignar, canal oficio, mismo vecino/tipo/dirección, origen = R2",
              dt and dt["estado"] == "Sin asignar" and dt["canal_origen"] == "oficio"
              and dt["id_ciudadano"] == d2["id_ciudadano"] and dt["id_tipo_reclamo"] == d2["id_tipo_reclamo"]
              and dt["direccion"] == d2["direccion"] and dt["id_reclamo_origen_auditoria"] == R2
              and dt["nro_reclamo"], str(dt))
        hs = await q("SELECT accion FROM reclamo_historial WHERE id_reclamo IN (:a, :b) ORDER BY id_historial DESC LIMIT 2", a=R2, b=RT or 0)
        check("5f. historial en R2 y en el retrabajo",
              {h["accion"] for h in hs} == {"Auditoría observada", "Reclamo ingresado por auditoría observada"}, str(hs))
        av = await ultimo_aviso(id_c)
        check("5g. UN aviso al vecino, que apunta al retrabajo",
              await n_avisos(id_c) == avisos_antes + 1 and av and av["recurso_id"] == RT
              and av["url_destino"] == f"/reclamos/{RT}" and OBS not in (av["mensaje"] or ""), str(av))
        mail = MAILS[0] if len(MAILS) == 1 else None
        dt_nro = dt["nro_reclamo"] if dt else "?"
        check("5k. UN mail al vecino: números de los dos reclamos + link al portal",
              mail is not None and mail["to"] == ctx["email_vecino"]
              and d2["nro_reclamo"] in mail["subject"] and dt_nro in mail["html"]
              and f"{PORTAL_SMOKE}/reclamos" in mail["html"] and f"{PORTAL_SMOKE}/reclamos" in mail["text"],
              f"mails={len(MAILS)} {mail['subject'] if mail else ''}")
        check("5l. el mail NO trae la observación del auditor",
              mail is not None and OBS not in mail["html"] and OBS not in mail["text"])
        ot2 = await q1("SELECT resultado_auditoria FROM ordenes_trabajo WHERE id_ot = :id", id=OT2)
        check("5h. OT2 resultado 'observada'", ot2 and ot2["resultado_auditoria"] == "observada", str(ot2))
        r = await c.get(f"/api/v1/reclamos/{R2}", headers=HA)
        check("5i. detalle R2 trae retrabajo vinculado",
              r.status_code == 200 and r.json().get("retrabajo_auditoria_id") == RT and r.json().get("resultado_auditoria") == "observado", short(r, 80))
        r = await c.get(f"/api/v1/reclamos/{RT}", headers=HA)
        check("5j. detalle retrabajo trae origen", r.status_code == 200 and r.json().get("origen_auditoria_nro") == d2["nro_reclamo"], short(r, 80))

        # ── 5bis. R5: auditoría observada SIN retrabajo (el auditor elige «No») ──────
        r = await c.post("/api/v1/reclamos", json=nuevo_reclamo("Smoke F4 — R5 observada sin retrabajo"), headers=HA)
        R5 = r.json()["id_reclamo"]
        await c.put(f"/api/v1/reclamos/{R5}/estado", json={"estado": "Resuelto"}, headers=HSA)
        r = await c.post(f"/api/v1/reclamos/{R5}/auditoria", json={"id_agente_auditor": id_aud_agente}, headers=HSA)
        OT5 = r.json()["id_ot"]
        avisos_antes = await n_avisos(id_c)
        MAILS.clear()
        r = await c.put(f"/api/v1/ot/{OT5}/observar",
                        json={"observaciones": "Faltó barrer los escombros", "generar_retrabajo": False}, headers=HAUD)
        check("5m. observar sin retrabajo → 200, id_reclamo_retrabajo null",
              r.status_code == 200 and r.json().get("id_reclamo_retrabajo") is None
              and r.json().get("estado_reclamo") == "Auditado", short(r))
        d5 = await reclamo(R5)
        n_rt5 = (await q1("SELECT COUNT(*) AS n FROM reclamos WHERE id_reclamo_origen_auditoria = :id", id=R5))["n"]
        check("5n. R5 Auditado / observado y SIN reclamo nuevo",
              d5["estado"] == "Auditado" and d5["resultado_auditoria"] == "observado" and n_rt5 == 0, f"{d5} rt={n_rt5}")
        h5 = await q1("SELECT accion, nota FROM reclamo_historial WHERE id_reclamo = :id ORDER BY id_historial DESC LIMIT 1", id=R5)
        check("5o. historial «Auditoría observada» con la nota «Sin retrabajo»",
              h5 and h5["accion"] == "Auditoría observada" and "Sin retrabajo" in (h5["nota"] or ""), str(h5))
        check("5p. sin aviso ni mail al vecino", await n_avisos(id_c) == avisos_antes and not MAILS, f"mails={len(MAILS)}")
        r = await c.get(f"/api/v1/reclamos/{R5}", headers=HA)
        check("5q. detalle R5 sin retrabajo vinculado",
              r.status_code == 200 and r.json().get("retrabajo_auditoria_id") is None
              and r.json().get("resultado_auditoria") == "observado", short(r, 80))

        # ── 6. Lo que ve el vecino ───────────────────────────────────────────────────
        r = await c.get("/api/v1/publico/reclamos", params={"limit": 200}, headers=HV)
        lst = {x["id_reclamo"]: x for x in r.json()} if r.status_code == 200 else {}
        check("6a. listado del vecino: R1, R2 y R5 'Resuelto'",
              all(lst.get(x, {}).get("estado") == "Resuelto" for x in (R1, R2, R5)), short(r, 80))
        desc_r2 = "Smoke 112 — R2 auditoría observada"
        x_rt = lst.get(RT, {})
        check("6b. listado del vecino INCLUYE el retrabajo, con el origen y la descripción del original",
              x_rt.get("estado") == "Sin asignar" and x_rt.get("origen_auditoria_nro") == d2["nro_reclamo"]
              and x_rt.get("descripcion") == desc_r2, str(x_rt)[:200])
        r = await c.get("/api/v1/publico/reclamos", params={"estado": "Resuelto", "limit": 200}, headers=HV)
        check("6c. filtro estado=Resuelto incluye R1", r.status_code == 200 and R1 in {x["id_reclamo"] for x in r.json()}, short(r, 80))
        r = await c.get(f"/api/v1/publico/reclamos/{R1}", headers=HV)
        estados_hist = {(h["estado_anterior"], h["estado_nuevo"]) for h in r.json().get("historial", [])} if r.status_code == 200 else set()
        check("6d. detalle R1 para el vecino: 'Resuelto' y sin rastro de auditoría en el historial",
              r.status_code == 200 and r.json()["estado"] == "Resuelto"
              and not any("auditor" in (a or "").lower() or "auditor" in (b or "").lower() for a, b in estados_hist), short(r, 80))
        r = await c.get(f"/api/v1/publico/reclamos/{RT}", headers=HV)
        hist_rt = r.json().get("historial", []) if r.status_code == 200 else []
        check("6e. detalle del retrabajo para el vecino → 200 con origen y descripción del original",
              r.status_code == 200 and r.json().get("origen_auditoria_nro") == d2["nro_reclamo"]
              and r.json().get("id_reclamo_origen_auditoria") == R2 and r.json().get("descripcion") == desc_r2, short(r, 120))
        check("6e2. la observación del auditor no aparece en NINGÚN campo del detalle",
              r.status_code == 200 and OBS not in r.text, "")
        check("6e3. alta del retrabajo en el historial con texto genérico",
              bool(hist_rt) and hist_rt[0]["accion"] == "Reclamo reabierto por control de calidad"
              and d2["nro_reclamo"] in (hist_rt[0]["nota"] or ""), str(hist_rt[:1]))
        r = await c.get(f"/api/v1/publico/reclamos/{RT}/adjuntos", headers=HV)
        check("6e4. adjuntos públicos del retrabajo → 200", r.status_code == 200, short(r, 80))
        r = await c.get("/api/v1/publico/portal/mi-resumen", headers=HV)
        tot = await q1("SELECT COUNT(*) AS n FROM reclamos WHERE id_ciudadano = :c AND activo", c=id_c)
        check("6f. mi-resumen: el total incluye el retrabajo",
              r.status_code == 200 and r.json().get("reclamos", {}).get("total") == tot["n"], short(r, 100))

        # ── 7. Dashboard: activos excluye auditoría, el mapa muestra En auditoría ────
        r = await c.post("/api/v1/reclamos", json=nuevo_reclamo("Smoke 112 — R3 pendiente de auditoría"), headers=HA)
        R3 = r.json()["id_reclamo"]
        await c.put(f"/api/v1/reclamos/{R3}/estado", json={"estado": "Resuelto"}, headers=HSA)
        r = await c.post(f"/api/v1/reclamos/{R3}/auditoria", json={}, headers=HA)
        OT3 = r.json()["id_ot"]
        r = await c.get("/api/v1/dashboard/resumen", headers=HA)
        activos_db = (await q1("SELECT COUNT(*) AS n FROM reclamos WHERE activo AND estado IN ('Sin asignar','En gestión','En espera')"))["n"]
        geo_ids = {x["id_reclamo"] for x in r.json()["geo"]["reclamos"]} if r.status_code == 200 else set()
        check("7a. tarjeta reclamos_activos = solo en gestión",
              r.status_code == 200 and r.json()["tarjetas"]["reclamos_activos"] == activos_db, short(r, 60))
        check("7b. mapa: R3 (En auditoría) sí, R1 (Auditado) no", R3 in geo_ids and R1 not in geo_ids)

        # ── 8. Cierre de OT operativa con tipo audit=true → Resuelto (sin auditoría previa)
        r = await c.post("/api/v1/reclamos", json=nuevo_reclamo("Smoke 112 — R4 cierre por OT"), headers=HA)
        R4 = r.json()["id_reclamo"]
        r = await c.post("/api/v1/ot", json={"id_reclamo": R4, "id_agente": id_ag_agente}, headers=HA)
        check("8a. OT operativa creada", r.status_code == 201, short(r))
        OT4 = r.json().get("id_ot")
        r = await c.put(f"/api/v1/ot/{OT4}/estado", json={"estado": "Terminada", "observaciones": "hecho"}, headers=HAG)
        check("8b. agente termina la OT → 200", r.status_code == 200, short(r))
        d4 = await reclamo(R4)
        n_ot_aud = (await q1("SELECT COUNT(*) AS n FROM ordenes_trabajo WHERE id_reclamo = :id AND es_auditoria", id=R4))["n"]
        check("8c. R4 Resuelto con fecha_cierre, SIN OT de auditoría aunque el tipo tenga audit=true",
              d4["estado"] == "Resuelto" and d4["fecha_cierre"] is not None and n_ot_aud == 0, f"{d4['estado']} ot_aud={n_ot_aud}")

        # ── 9. OT de auditoría por /estado ───────────────────────────────────────────
        r = await c.put(f"/api/v1/ot/{OT3}/estado", json={"estado": "Terminada"}, headers=HA)
        check("9a. Terminar una auditoría por /estado → 422", r.status_code == 422, short(r))
        r = await c.put(f"/api/v1/ot/{OT3}/estado", json={"estado": "Cancelada"}, headers=HAG)
        check("9b. cancelar auditoría ajena como nivel 4 → 403", r.status_code == 403, short(r))
        r = await c.put(f"/api/v1/ot/{OT3}/estado", json={"estado": "Cancelada", "observaciones": "no corresponde"}, headers=HA)
        check("9c. admin cancela la auditoría → 200", r.status_code == 200, short(r))
        d3 = await reclamo(R3)
        check("9d. R3 vuelve a Resuelto, sin fecha_inicio, fecha_cierre intacta",
              d3["estado"] == "Resuelto" and d3["fecha_inicio_auditoria"] is None and d3["fecha_cierre"] is not None, str(d3))
        r = await c.get(f"/api/v1/publico/reclamos/{R3}", headers=HV)
        acciones_r3 = [h["accion"] for h in r.json().get("historial", [])] if r.status_code == 200 else []
        check("9f. el vecino NO ve «Auditoría cancelada» en el historial de R3",
              r.status_code == 200 and "Auditoría cancelada" not in acciones_r3, str(acciones_r3))
        r = await c.post(f"/api/v1/reclamos/{R3}/auditoria", json={}, headers=HA)
        check("9e. R3 se puede volver a enviar a auditoría", r.status_code == 201, short(r))

        # ── 10. Retrabajo: resolverlo avisa al vecino y encuesta SIN anti-fatiga ─────
        # Precondición: el vecino ya tiene una encuesta de esta subárea en los últimos 30
        # días (la de R1 o la de una corrida anterior), así que la anti-fatiga la bloquearía.
        previa = await q1("""SELECT COUNT(*) AS n FROM encuesta_envio ee
                              JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = :t
                             WHERE ee.id_ciudadano = :c AND ee.id_subarea = tr.id_subarea AND ee.activo
                               AND ee.fecha_alta > NOW() - INTERVAL '30 days'""", c=id_c, t=tipo_a)
        check("10pre. hay encuesta reciente de la subárea (la anti-fatiga aplicaría)", previa["n"] > 0, str(previa))
        avisos_antes = await n_avisos(id_c)
        r = await c.put(f"/api/v1/reclamos/{RT}/estado", json={"estado": "Resuelto"}, headers=HSA)
        check("10a. cierre directo del retrabajo → 200", r.status_code == 200, short(r))
        check("10b. retrabajo resuelto: 1 encuesta (exenta de anti-fatiga) y 1 aviso al vecino",
              await n_envios(RT) == 1 and await n_avisos(id_c) == avisos_antes + 1,
              f"envios={await n_envios(RT)} avisos+={await n_avisos(id_c) - avisos_antes}")
        r = await c.post("/api/v1/reclamos", json=nuevo_reclamo("Smoke F4 — R6 control anti-fatiga"), headers=HA)
        R6 = r.json()["id_reclamo"]
        await c.put(f"/api/v1/reclamos/{R6}/estado", json={"estado": "Resuelto"}, headers=HSA)
        check("10c. control: un reclamo común de la misma subárea SÍ queda bloqueado por la anti-fatiga",
              await n_envios(R6) == 0, f"envios={await n_envios(R6)}")

        # ── 11. BI ───────────────────────────────────────────────────────────────────
        r = await c.get("/api/v1/bi/resumen", headers=HA)
        check("11a. /bi/resumen 200", r.status_code == 200, short(r, 60))
        r = await c.get("/api/v1/bi/pendientes-mensual", headers=HA)
        check("11b. /bi/pendientes-mensual sin en_auditoria",
              r.status_code == 200 and all("en_auditoria" not in x for x in r.json()), short(r, 60))
        r = await c.get("/api/v1/bi/ejecutivo/cierres-por-estado", headers=HA)
        estados_ci = [x["estado"] for x in r.json()] if r.status_code == 200 else []
        check("11c. cierres-por-estado: Cumplido / En auditoría / Auditado",
              estados_ci == ["Cumplido", "En auditoría", "Auditado"], short(r, 120))
        r = await c.get("/api/v1/bi/subreclamos-mensual", headers=HA)
        check("11d. /bi/subreclamos-mensual 200", r.status_code == 200, short(r, 60))

        # ── 12. OpenAPI ──────────────────────────────────────────────────────────────
        r = await c.get("/openapi.json")
        paths = r.json().get("paths", {})
        check("12a. POST /reclamos/{id}/auditoria en OpenAPI", "post" in paths.get("/api/v1/reclamos/{id_reclamo}/auditoria", {}))
        check("12b. PUT /ot/{id}/observar en OpenAPI + /rechazar deprecado",
              "put" in paths.get("/api/v1/ot/{id_ot}/observar", {})
              and paths.get("/api/v1/ot/{id_ot}/rechazar", {}).get("put", {}).get("deprecated") is True)
        desc_422 = (paths.get("/api/v1/ot/{id_ot}/observar", {}).get("put", {})
                    .get("responses", {}).get("422", {}).get("description", ""))
        check("12c. marcador F4 en OpenAPI: generar_retrabajo", "generar_retrabajo" in desc_422, desc_422[:80])

    print(f"\n{'=' * 60}\nOK: {ok_count}  FAIL: {fail_count}")
    for f in fallidos:
        print(f"  - {f['caso']}: {f['detalle']}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
