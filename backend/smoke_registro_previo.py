# -*- coding: utf-8 -*-
"""
Smoke in-process — registro previo, F2: ninguna transacción del backoffice a nombre de un vecino
sin cuenta en el portal (PLAN_REGISTRO_PREVIO.md §3-F2 y §4).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_registro_previo.py

SOLO LOCAL (aborta si la DB no es zaris_dev). App FastAPI real con httpx.ASGITransport y mails
CAPTURADOS. Correr con DB_BARRERA=true y con false. Crea tres vecinos de prueba en el municipio 1
(sin cuenta, ficha demo y de baja) y los deja dados de baja al terminar; cancela el turno y da de
baja el evento y la ocupación que crea.

Cubre:
  1. Las cinco vías de alta (reclamo, subreclamo, turno, reserva, ocupación tipo turno): 422 con el
     MOTIVO, sin escribir nada, para el vecino sin cuenta, la ficha demo y el dado de baja.
  2. Editar un reclamo: no se le pone un vecino sin cuenta, no se lo deja sin vecino, y editar otra
     cosa sigue andando.
  3. El buscador informa `tiene_cuenta`.
  4. Guardar la ficha crea la cuenta y las mismas altas pasan a 201.
  5. Subreclamo sin vecino en el body: hereda el del padre y no pide nada.
  6. El generador de datos demo deja a sus vecinos con cuenta.
"""
import asyncio
import os
import random
import sys
from datetime import date, timedelta
from types import SimpleNamespace
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

settings.RESEND_API_KEY = ""

# Preparación y verificación como dueño de la base: no pasa por la barrera (IT-01 F6).
from app.core.sistema import SesionSistema as AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.services import demo_datos  # noqa: E402
from app.services import email as svc_email  # noqa: E402

MAILS: list[dict] = []


async def _capturar(to, subject, body_html, body_text=None, from_override=None):
    MAILS.append({"to": to, "subject": subject})
    return True


svc_email.enviar_mail = _capturar

PWD_DEV = os.environ.get("ZARIS_QA_PASS") or "123456"
ADMIN_EMAIL = "ciudadanovl@municipio.gob.ar"
MUN = 1
T_SIN = "no tiene cuenta en el portal: abrí su ficha"
T_DEMO = "DNI de prueba"
T_BAJA = "dado de baja"
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
        res = await s.execute(text(sql), params)
        row = res.mappings().first() if res.returns_rows else None
        await s.commit()
        return dict(row) if row else None


def _cuil(dni: str, pref: str = "20") -> str:
    base = pref + dni.zfill(8)
    dv = 11 - sum(int(d) * p for d, p in zip(base, (5, 4, 3, 2, 7, 6, 5, 4, 3, 2))) % 11
    if dv == 10:
        return _cuil(dni, "23")
    return base + str(0 if dv == 11 else dv)


async def _vecino(dni: str, apellido: str, activo: bool = True, con_cuenta: bool = False) -> int:
    # Números al azar y fichas dadas de baja al terminar: no choca entre corridas.
    v = await q1("""
        INSERT INTO ciudadanos (doc_tipo, doc_nro, cuil, nombre, apellido, sexo, fecha_nac, id_nacionalidad,
                                calle, localidad, provincia, telefono, email, ren_chk, email_chk, emp_chk,
                                activo, id_municipio)
        SELECT 'DNI', CAST(:d AS varchar), :cuil, 'Registro', :ape, 'OTROS', DATE '1990-01-01', n.id,
               'Av. Smoke 1', 'Olivos', 'Buenos Aires', :tel, CAST(:d AS varchar) || '@registro-previo.test',
               FALSE, FALSE, FALSE, :act, :mun
          FROM nacionalidades n ORDER BY n.id LIMIT 1
        RETURNING id_ciudadano""", d=dni, cuil=_cuil(dni), ape=apellido, act=activo, mun=MUN,
                 tel="11" + str(random.randint(20_000_000, 79_999_999)))
    if con_cuenta:
        await q1("INSERT INTO ciudadano_credencial (id_ciudadano, activado, activo, id_municipio) "
                 "VALUES (:c, FALSE, TRUE, :m)", c=v["id_ciudadano"], m=MUN)
    return v["id_ciudadano"]


async def _conteos() -> dict:
    return await q1("SELECT (SELECT count(*) FROM reclamos) AS reclamos, (SELECT count(*) FROM turnos) AS turnos, "
                    "(SELECT count(*) FROM ocupaciones) AS ocupaciones, "
                    "(SELECT count(*) FROM evento_reservas) AS reservas")


async def main() -> int:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://smoke.local", timeout=90) as c:
        r = await c.post("/api/v1/auth/login", json={"identificador": ADMIN_EMAIL, "password": PWD_DEV})
        assert r.status_code == 200 and "access_token" in r.json(), r.text[:200]
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}

        tipo = (await q1("SELECT tr.id_tipo_reclamo FROM tipo_reclamo tr JOIN subarea s ON s.id_subarea = tr.id_subarea "
                         "WHERE tr.activo AND s.activo AND tr.id_municipio = 1 ORDER BY 1 LIMIT 1"))["id_tipo_reclamo"]
        bueno = (await q1("SELECT c.id_ciudadano FROM ciudadanos c JOIN ciudadano_credencial k USING (id_ciudadano) "
                          "WHERE c.activo AND k.activo AND c.id_municipio = 1 ORDER BY 1 LIMIT 1"))["id_ciudadano"]
        base_dni = random.randint(60_000_000, 89_999_000)
        sin = await _vecino(str(base_dni), "SmokeSinCuenta")
        demo = await _vecino("99" + str(random.randint(800_000, 999_999)), "SmokeFichaDemo")
        baja = await _vecino(str(base_dni + 1), "SmokeDeBaja", activo=False, con_cuenta=True)

        prest, slot = None, None
        desde = date.today() + timedelta(days=1)
        for p in (await c.get("/api/v1/turnos/publico/prestaciones")).json():
            rs = await c.get("/api/v1/turnos/publico/slots", params={
                "id_tipo_prestacion": p["id_tipo_prestacion"], "fecha_desde": str(desde), "dias": 14})
            cuerpo = rs.json() if rs.status_code == 200 else []
            lista = cuerpo.get("slots", []) if isinstance(cuerpo, dict) else cuerpo
            if lista:
                prest, slot = p["id_tipo_prestacion"], lista[0]
                break
        check(prest is not None, "dato de partida: una prestación con horario libre")
        agente = (await q1("SELECT id_agente FROM agentes WHERE activo AND id_municipio = 1 ORDER BY 1 LIMIT 1"))["id_agente"]
        r = await c.post("/api/v1/agenda/eventos", headers=h, json={
            "nombre": "Smoke registro previo", "fecha": str(desde), "hora_inicio": "10:00", "hora_fin": "11:00",
            "capacidad_ciudadanos": 5, "cantidad_encargados": 1, "tipo_qr": "nominal"})
        check(r.status_code == 201, "dato de partida: un evento con cupo", f"{r.status_code} {r.text[:200]}")
        evento = r.json()["id_evento"]
        r = await c.post("/api/v1/reclamos", headers=h, json={
            "id_ciudadano": bueno, "id_tipo_reclamo": tipo, "descripcion": "Smoke: reclamo padre", "canal_origen": "oficio"})
        check(r.status_code == 201, "un vecino con cuenta carga su reclamo", f"{r.status_code} {r.text[:200]}")
        padre = r.json()["id_reclamo"]

        def vias(v: int) -> list:
            return [
                ("reclamo", "/api/v1/reclamos", {"id_ciudadano": v, "id_tipo_reclamo": tipo,
                                                 "descripcion": "Smoke registro previo", "canal_origen": "oficio"}),
                ("subreclamo a nombre de otro", f"/api/v1/reclamos/{padre}/subreclamo",
                 {"id_ciudadano": v, "id_tipo_reclamo": tipo, "descripcion": "Smoke registro previo"}),
                ("turno", "/api/v1/turnos", {"id_ciudadano": v, "id_tipo_prestacion": prest,
                                             "fecha": slot["fecha"], "hora_inicio": slot["hora_inicio"]}),
                ("reserva", f"/api/v1/agenda/eventos/{evento}/reservas", {"id_ciudadano": v, "origen": "backoffice"}),
                ("ocupación tipo turno", "/api/v1/agenda/ocupaciones",
                 {"tipo": "turno", "tipo_recurso": "agente", "id_recurso": agente, "fecha": str(desde + timedelta(days=40)),
                  "hora_inicio": "06:00", "hora_fin": "06:30", "id_ciudadano": v, "motivo": "Smoke registro previo"}),
            ]

        print("[1] Sin cuenta no hay transacción, por ninguna vía")
        antes = await _conteos()
        for quien, v, motivo in (("sin cuenta", sin, T_SIN), ("ficha demo", demo, T_DEMO)):
            for nombre, url, body in vias(v):
                r = await c.post(url, headers=h, json=body)
                check(r.status_code == 422 and motivo in r.text, f"{nombre}, vecino {quien}: 422 con el motivo",
                      f"{r.status_code} {r.text[:200]}")
        for nombre, url, body in vias(baja):
            r = await c.post(url, headers=h, json=body)
            # Turnos y reservas ya respondían 404 a un vecino inactivo.
            check((r.status_code == 422 and T_BAJA in r.text) or r.status_code == 404,
                  f"{nombre}, vecino de baja: rechazado", f"{r.status_code} {r.text[:200]}")
        despues = await _conteos()
        check(antes == despues, "no se escribió nada", f"{antes} -> {despues}")

        print("[2] Editar un reclamo")
        r = await c.put(f"/api/v1/reclamos/{padre}", headers=h, json={"id_ciudadano": sin})
        check(r.status_code == 422 and T_SIN in r.text, "no se le pone un vecino sin cuenta", f"{r.status_code} {r.text[:200]}")
        r = await c.put(f"/api/v1/reclamos/{padre}", headers=h, json={"id_ciudadano": None})
        check(r.status_code == 422 and "sin vecino" in r.text, "no queda sin vecino", f"{r.status_code} {r.text[:200]}")
        r = await c.put(f"/api/v1/reclamos/{padre}", headers=h, json={"descripcion": "Smoke: editado", "id_ciudadano": bueno})
        check(r.status_code == 200, "editar otra cosa con el mismo vecino", f"{r.status_code} {r.text[:200]}")
        f = await q1("SELECT id_ciudadano FROM reclamos WHERE id_reclamo = :i", i=padre)
        check(f["id_ciudadano"] == bueno, "el vecino del reclamo no cambió", str(f))

        print("[3] El buscador informa la cuenta")
        r = await c.get("/api/v1/buc/ciudadanos/buscar", headers=h, params={"q": str(base_dni)})
        check(r.status_code == 200 and [x["tiene_cuenta"] for x in r.json()] == [False], "tiene_cuenta = false", r.text[:200])

        print("[4] Guardar la ficha crea la cuenta y las altas pasan")
        MAILS.clear()
        r = await c.put(f"/api/v1/buc/ciudadanos/{sin}", headers=h, json={"calle": "Av. Smoke 2"})
        check(r.status_code == 200, "guardar la ficha", f"{r.status_code} {r.text[:200]}")
        check(any(m["to"] == f"{base_dni}@registro-previo.test" for m in MAILS), "sale el correo de activación", str(MAILS))
        r = await c.get("/api/v1/buc/ciudadanos/buscar", headers=h, params={"q": str(base_dni)})
        check([x["tiene_cuenta"] for x in r.json()] == [True], "tiene_cuenta = true", r.text[:200])
        r = await c.put(f"/api/v1/reclamos/{padre}", headers=h, json={"id_ciudadano": sin})
        check(r.status_code == 200, "el reclamo admite al vecino ya registrado", f"{r.status_code} {r.text[:200]}")
        await c.put(f"/api/v1/reclamos/{padre}", headers=h, json={"id_ciudadano": bueno})
        creados: dict = {}
        # El subreclamo va último: deja al padre en espera.
        for nombre, url, body in sorted(vias(sin), key=lambda x: x[0].startswith("sub")):
            r = await c.post(url, headers=h, json=body)
            check(r.status_code == 201, f"{nombre}: 201", f"{r.status_code} {r.text[:200]}")
            creados[nombre] = r.json() if r.status_code == 201 else {}

        print("[5] Subreclamo sin vecino en el body: hereda el del padre")
        await q1("UPDATE ciudadano_credencial SET activo = FALSE WHERE id_ciudadano = :c", c=bueno)
        try:
            r = await c.post(f"/api/v1/reclamos/{padre}/subreclamo", headers=h,
                             json={"id_tipo_reclamo": tipo, "descripcion": "Smoke: hereda"})
            check(r.status_code == 201, "201 aunque el vecino heredado ya no tenga cuenta", f"{r.status_code} {r.text[:200]}")
        finally:
            await q1("UPDATE ciudadano_credencial SET activo = TRUE WHERE id_ciudadano = :c", c=bueno)

        print("[6] Generador de datos demo")
        async with AsyncSessionLocal() as s:  # sin commit: se revierte
            d = f"%@{demo_datos.DOMINIO_VECINO_DEMO}"
            await s.execute(text("DELETE FROM ciudadano_credencial k USING ciudadanos c WHERE c.id_ciudadano = k.id_ciudadano "
                                 "AND c.email LIKE :d AND c.id_municipio = 1 AND k.activado = FALSE"), {"d": d})
            uid = await s.scalar(text("SELECT id_usuario FROM usuarios WHERE email = :e"), {"e": ADMIN_EMAIL})
            sql = text("SELECT count(*) FROM ciudadanos c WHERE c.activo AND c.email LIKE :d AND c.id_municipio = 1 "
                       "AND NOT EXISTS (SELECT 1 FROM ciudadano_credencial k WHERE k.id_ciudadano = c.id_ciudadano)")
            n0 = await s.scalar(sql, {"d": d})
            await demo_datos._asegurar_vecinos(s, SimpleNamespace(id_municipio=1), uid, 0, random.Random(1))
            n1 = await s.scalar(sql, {"d": d})
            check(n0 > 0 and n1 == 0, "los vecinos demo quedan con cuenta", f"{n0} -> {n1}")
            await s.rollback()

        # Limpieza
        if creados.get("turno"):
            await c.patch(f"/api/v1/turnos/{creados['turno']['id_turno']}/cancelar", headers=h)
        oc = creados.get("ocupación tipo turno")
        if oc:
            await c.delete(f"/api/v1/agenda/ocupaciones/{oc['ocupacion']['id_ocupacion']}", headers=h)
        await c.delete(f"/api/v1/agenda/eventos/{evento}", headers=h)
    await q1("UPDATE ciudadanos SET activo = FALSE WHERE id_ciudadano = ANY(:ids)", ids=[sin, demo, baja])
    print(f"\n== {OK} OK · {FAIL} FAIL ==")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
