# -*- coding: utf-8 -*-
"""
Smoke in-process — avisos de turnos y entradas al vecino (PLAN_AVISOS_TURNOS_ENTRADAS.md, mig 144).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_avisos_turnos.py

SOLO LOCAL. Mails y notificaciones CAPTURADOS: no sale nada. Correr con DB_BARRERA=true y con false.
Usa el vecino demo 3 (cuenta activada) y otro con la cuenta sin activar; cancela lo que reserva y da de
baja los eventos que crea.
"""
import asyncio
import os
import random
import sys
from datetime import timedelta

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
settings.DISPATCHER_TOKEN = settings.DISPATCHER_TOKEN or "smoke-avisos"

from app.core.auth import create_access_token, crear_token_ciudadano  # noqa: E402
from app.core.sistema import SesionSistema  # noqa: E402
from app.main import app  # noqa: E402
from app.services import avisos_turnos as svc  # noqa: E402
from app.services import email as svc_email  # noqa: E402
from app.utils.fechas import hoy_local  # noqa: E402

MAILS: list[dict] = []
PUSH: list[dict] = []
FALLAR_MAIL = False


async def _mail(to, subject, body_html, body_text=None, from_override=None):
    MAILS.append({"to": to, "subject": subject, "html": body_html, "text": body_text})
    return not FALLAR_MAIL


async def _push(id_ciudadano, titulo, cuerpo, url="/inicio"):
    PUSH.append({"c": id_ciudadano, "titulo": titulo, "cuerpo": cuerpo, "url": url})
    return 1


svc_email.enviar_mail = _mail
svc.enviar_push_ciudadano = _push
VECINO = 3
RES: list[bool] = []


def check(nombre: str, ok, detalle="") -> None:
    RES.append(bool(ok))
    print(f"  {'OK  ' if ok else 'FAIL'} {nombre}{(' — ' + str(detalle)) if not ok else ''}")


async def sql(q: str, **p):
    async with SesionSistema() as db:
        r = await db.execute(text(q), p)
        filas = r.mappings().all() if r.returns_rows else []
        await db.commit()
        return [dict(f) for f in filas]


async def avisos(tipo: str, recurso: int) -> list[dict]:
    return await sql("SELECT titulo, mensaje, url_destino, id_ciudadano FROM ciudadano_aviso "
                     "WHERE tipo = :t AND recurso_id = :r ORDER BY id_ciudadano_aviso", t=tipo, r=recurso)


def limpiar():
    MAILS.clear()
    PUSH.clear()


async def main() -> int:
    global FALLAR_MAIL
    admin = (await sql("SELECT id_usuario FROM usuarios WHERE id_municipio = 1 AND nivel_acceso = 1 AND activo "
                       "AND NOT COALESCE(debe_cambiar_password, FALSE) ORDER BY id_usuario LIMIT 1"))[0]["id_usuario"]
    correo = (await sql("SELECT email FROM ciudadanos WHERE id_ciudadano = :i", i=VECINO))[0]["email"]
    pend = (await sql("SELECT c.id_ciudadano, c.email FROM ciudadanos c JOIN ciudadano_credencial k USING (id_ciudadano) "
                      "WHERE c.id_municipio = 1 AND c.activo AND k.activo AND NOT k.activado AND c.doc_nro NOT LIKE '99%' "
                      "AND c.email <> '' ORDER BY c.id_ciudadano DESC LIMIT 1"))[0]
    prest = {f["salud"]: f for f in await sql("""
        SELECT DISTINCT ON (salud) * FROM (
            SELECT tp.id_tipo_prestacion AS id, tp.nombre, e.nombre AS lugar, e.direccion,
                   COALESCE(s.id_area::text = (SELECT valor FROM configuracion_general
                        WHERE clave = 'id_area_salud' AND id_municipio = 1), FALSE) AS salud
              FROM tipo_prestacion tp JOIN espacios_agenda e ON e.id_espacio = tp.id_espacio_ubicacion
              LEFT JOIN subarea s ON s.id_subarea = tp.id_subarea
             WHERE tp.activo AND tp.id_municipio = 1 AND e.direccion <> '' AND tp.nombre NOT ILIKE 'smoke%') x
         ORDER BY salud, nombre""")}
    HA = {"Authorization": "Bearer " + create_access_token({"sub": str(admin), "mun": 1, "sf": True})}
    HV = {"Authorization": "Bearer " + crear_token_ciudadano(VECINO, 1)}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=60) as c:
        async def slots(id_prest: int) -> list[dict]:
            r = await c.get("/api/v1/turnos/publico/slots", params={
                "id_tipo_prestacion": id_prest, "fecha_desde": str(hoy_local() + timedelta(days=3)), "dias": 25})
            s = r.json()
            if r.status_code != 200 or not s:
                sys.exit(f"sin horarios libres para la prestación {id_prest}: {r.status_code} {r.text[:200]}")
            random.shuffle(s)
            return s

        async def crear(id_prest: int, vecino: int) -> dict:
            for s in (await slots(id_prest))[:8]:
                r = await c.post("/api/v1/turnos", headers=HA, json={
                    "id_ciudadano": vecino, "id_tipo_prestacion": id_prest, "fecha": s["fecha"],
                    "hora_inicio": s["hora_inicio"]})
                if r.status_code == 201:
                    return r.json()
            sys.exit(f"no se pudo crear el turno: {r.status_code} {r.text[:200]}")

        comun, salud = prest[False], prest[True]

        print("1. Turno cargado por un agente")
        limpiar()
        t = await crear(comun["id"], VECINO)
        idt = t["id_turno"]
        av = await avisos("turno", idt)
        check("un aviso en la bandeja", len(av) == 1 and av[0]["titulo"] == "Turno confirmado", av)
        check("el aviso nombra prestación, lugar y abre /turnos",
              av and comun["nombre"] in av[0]["mensaje"] and comun["lugar"] in av[0]["mensaje"]
              and av[0]["url_destino"] == "/turnos", av)
        check("una notificación", len(PUSH) == 1 and PUSH[0]["c"] == VECINO, PUSH)
        check("un correo a su casilla", [m["to"] for m in MAILS] == [correo], MAILS)
        check("el correo lleva a «Mis turnos» del portal", MAILS and "/turnos" in MAILS[0]["html"]
              and "Ver mis turnos" in MAILS[0]["html"])

        print("2. Cambios")
        limpiar()
        r = await c.put(f"/api/v1/turnos/{idt}", headers=HA, json={"observaciones": "smoke"})
        check("cambiar las observaciones no avisa", r.status_code == 200 and not MAILS and not PUSH, r.text[:150])
        await sql("UPDATE turnos SET recordado_en = NOW() WHERE id_turno = :i", i=idt)
        for s in await slots(comun["id"]):
            r = await c.put(f"/api/v1/turnos/{idt}", headers=HA,
                            json={"fecha": s["fecha"], "hora_inicio": s["hora_inicio"]})
            if r.status_code == 200:
                break
        check("reprogramar avisa por los tres canales", r.status_code == 200 and len(MAILS) == 1 and len(PUSH) == 1
              and (await avisos("turno", idt))[-1]["titulo"] == "Cambió tu turno", r.text[:150])
        rec = (await sql("SELECT recordado_en FROM turnos WHERE id_turno = :i", i=idt))[0]["recordado_en"]
        check("el recordatorio vuelve a quedar pendiente", rec is None, rec)

        print("3. Cancelación por el municipio")
        limpiar()
        r = await c.patch(f"/api/v1/turnos/{idt}/cancelar", headers=HA)
        check("avisa por los tres canales", r.status_code == 200 and len(MAILS) == 1 and len(PUSH) == 1
              and "canceló" in MAILS[0]["subject"], (r.status_code, MAILS))
        r = await c.patch(f"/api/v1/turnos/{idt}/cancelar", headers=HA)
        check("repetirla no vuelve a avisar", r.status_code == 200 and len(MAILS) == 1)

        print("4. Turno de Salud: sin prestación ni lugar afuera de la app")
        limpiar()
        t = await crear(salud["id"], VECINO)
        afuera = PUSH[0]["cuerpo"] + MAILS[0]["html"] + MAILS[0]["text"] + MAILS[0]["subject"]
        check("la notificación y el correo no la nombran",
              salud["nombre"] not in afuera and salud["lugar"] not in afuera, afuera[:200])
        check("sí dicen la dirección", salud["direccion"] in PUSH[0]["cuerpo"], PUSH)
        av = await avisos("turno", t["id_turno"])
        check("la bandeja, con sesión, sí la nombra", salud["nombre"] in av[0]["mensaje"], av)
        await c.patch(f"/api/v1/turnos/{t['id_turno']}/cancelar", headers=HA)

        print("5. Cuenta sin activar")
        limpiar()
        t = await crear(comun["id"], pend["id_ciudadano"])
        check("queda en su bandeja y no le sale ningún correo",
              len(await avisos("turno", t["id_turno"])) == 1 and not MAILS, MAILS)
        pendiente = t["id_turno"]

        print("6. Turno sacado y cancelado por el vecino")
        limpiar()
        r = None
        for s in (await slots(comun["id"]))[:10]:
            r = await c.post("/api/v1/publico/turnos", headers={**HV, "X-Forwarded-For": f"10.9.{random.randint(1, 250)}.{random.randint(1, 250)}"},
                             json={"id_tipo_prestacion": comun["id"], "fecha": s["fecha"], "hora_inicio": s["hora_inicio"]})
            if r.status_code == 404 or r.status_code == 405:
                r = await c.post("/api/v1/publico/turnos/reservar", headers={**HV, "X-Forwarded-For": f"10.9.{random.randint(1, 250)}.{random.randint(1, 250)}"},
                                 json={"id_tipo_prestacion": comun["id"], "fecha": s["fecha"], "hora_inicio": s["hora_inicio"]})
            if r.status_code == 201:
                break
        check("aviso y correo, sin notificación", r.status_code == 201 and len(MAILS) == 1 and not PUSH,
              (r.status_code, r.text[:150], PUSH))
        if r.status_code == 201:
            limpiar()
            r2 = await c.patch(f"/api/v1/publico/turnos/{r.json()['id_turno']}/cancelar", headers=HV)
            check("cancelarlo él mismo no avisa", r2.status_code == 200 and not MAILS and not PUSH, r2.text[:150])

        print("7. Entradas")
        esp = (await sql("SELECT id_espacio, nombre FROM espacios_agenda WHERE activo AND id_municipio = 1 "
                         "AND direccion <> '' ORDER BY id_espacio LIMIT 1"))[0]
        base = {"nombre": "Smoke avisos & <b>entradas</b>", "fecha": str(hoy_local() + timedelta(days=9)),
                "hora_inicio": "18:00", "hora_fin": "20:00", "capacidad_ciudadanos": 20, "tipo_qr": "nominal",
                "admite_autoservicio": True, "id_espacio": esp["id_espacio"]}
        ev = (await c.post("/api/v1/agenda/eventos", headers=HA, json=base)).json()["id_evento"]
        limpiar()
        r = await c.post(f"/api/v1/agenda/eventos/{ev}/reservas", headers=HA,
                         json={"id_ciudadano": VECINO, "origen": "backoffice"})
        idr = r.json().get("id_evento_reserva")
        check("reserva del backoffice: tres canales", r.status_code == 201 and len(MAILS) == 1 and len(PUSH) == 1
              and (await avisos("entrada", idr))[0]["url_destino"] == "/entradas", (r.status_code, r.text[:150]))
        check("el nombre del evento va escapado en el correo", MAILS and "<b>entradas</b>" not in MAILS[0]["html"]
              and "&lt;b&gt;" in MAILS[0]["html"])
        await c.post(f"/api/v1/agenda/eventos/{ev}/reservas", headers=HA,
                     json={"id_ciudadano": pend["id_ciudadano"], "origen": "backoffice"})
        limpiar()
        await c.put(f"/api/v1/agenda/eventos/{ev}", headers=HA, json={"descripcion": "otra"})
        check("cambiar la descripción no avisa", not MAILS and not PUSH)
        await c.put(f"/api/v1/agenda/eventos/{ev}", headers=HA, json={"hora_inicio": "17:30"})
        check("cambiar la hora avisa a los dos (correo solo al de la cuenta activada)",
              len(PUSH) == 2 and [m["to"] for m in MAILS] == [correo], (PUSH, MAILS))
        limpiar()
        r = await c.patch(f"/api/v1/agenda/reservas/{idr}/cancelar", headers=HA)
        check("cancelar la reserva avisa", r.status_code == 200 and len(MAILS) == 1 and len(PUSH) == 1)
        r = await c.patch(f"/api/v1/agenda/reservas/{idr}/cancelar", headers=HA)
        check("repetirla no vuelve a avisar", len(MAILS) == 1)
        limpiar()
        r = await c.post(f"/api/v1/publico/entradas/eventos/{ev}/reservar",
                         headers={**HV, "X-Forwarded-For": f"10.8.{random.randint(1, 250)}.{random.randint(1, 250)}"})
        check("reserva del vecino: correo sin notificación", r.status_code == 201 and len(MAILS) == 1 and not PUSH,
              (r.status_code, r.text[:150]))
        limpiar()
        await c.patch(f"/api/v1/agenda/eventos/{ev}/cancelar", headers=HA)
        check("cancelar el evento avisa a los dos", len(PUSH) == 2 and len(MAILS) == 1
              and "ya no es válida" in PUSH[0]["cuerpo"], PUSH)
        limpiar()
        await c.delete(f"/api/v1/agenda/eventos/{ev}", headers=HA)
        check("eliminar un evento ya cancelado no vuelve a avisar", not PUSH and not MAILS)

        print("8. Recordatorio del día anterior")
        # Primero se lleva lo que hubiera en la base: lo que se mide es lo que crea este smoke.
        url = "/api/v1/avisos/mantenimiento/recordatorios"
        await c.post(url, headers={"X-Dispatcher-Token": settings.DISPATCHER_TOKEN})
        ev2 = (await c.post("/api/v1/agenda/eventos", headers=HA, json={**base, "nombre": "Smoke recordatorio",
               "fecha": str(hoy_local() + timedelta(days=1))})).json()["id_evento"]
        r = await c.post(f"/api/v1/agenda/eventos/{ev2}/reservas", headers=HA,
                         json={"id_ciudadano": VECINO, "origen": "backoffice"})
        rec_ent = r.json()["id_evento_reserva"]
        viejo = (await crear(comun["id"], VECINO))["id_turno"]
        nuevo = (await crear(comun["id"], VECINO))["id_turno"]
        manana = hoy_local() + timedelta(days=1)
        for i, (idx, dias) in enumerate(((viejo, 3), (nuevo, 0), (pendiente, 3))):
            await sql("UPDATE turnos SET fecha = :f, hora_inicio = make_time(22, :m, 0), hora_fin = make_time(22, :m2, 0), "
                      "fecha_alta = NOW() - make_interval(days => CAST(:d AS int)), recordado_en = NULL WHERE id_turno = :i",
                      f=manana, m=random.randint(0, 9) + i * 15, m2=random.randint(10, 14) + i * 15, d=dias, i=idx)
        await sql("UPDATE evento_reservas SET fecha_alta = NOW() - INTERVAL '3 days' WHERE id_evento_reserva = :i", i=rec_ent)
        r = await c.post(url, headers={"X-Dispatcher-Token": "otro"})
        check("sin el token de la tarea → 401", r.status_code == 401, r.status_code)
        limpiar()
        r = await c.post(url, headers={"X-Dispatcher-Token": settings.DISPATCHER_TOKEN})
        j = r.json()
        check("la tarea responde con el resumen por municipio", r.status_code == 200 and j.get("municipios")
              and not j.get("con_error"), r.text[:300])
        check("recuerda el turno viejo", (await avisos("turno", viejo))[-1]["titulo"] == "Mañana tenés un turno")
        check("recuerda la entrada", (await avisos("entrada", rec_ent))[-1]["titulo"] == "Mañana es tu evento")
        check("no recuerda lo reservado hoy", (await avisos("turno", nuevo))[-1]["titulo"] == "Turno confirmado")
        check("no recuerda a la cuenta sin activar", (await avisos("turno", pendiente))[-1]["titulo"] == "Turno confirmado")
        mios = [m for m in MAILS if m["to"] == correo]
        check("dos correos al vecino (turno y entrada)", len(mios) == 2, [m["subject"] for m in MAILS])
        limpiar()
        r = await c.post(url, headers={"X-Dispatcher-Token": settings.DISPATCHER_TOKEN})
        check("repetir la tarea no recuerda dos veces", not MAILS and not PUSH, MAILS)
        await sql("UPDATE turnos SET recordado_en = NULL WHERE id_turno = :i", i=viejo)
        FALLAR_MAIL = True
        r = await c.post(url, headers={"X-Dispatcher-Token": settings.DISPATCHER_TOKEN})
        FALLAR_MAIL = False
        check("un correo que no sale deja el municipio con error", r.json()["fallidos"] == 1 and r.json()["con_error"],
              r.text[:300])

        for i in (viejo, nuevo, pendiente):
            await c.patch(f"/api/v1/turnos/{i}/cancelar", headers=HA)
        await c.patch(f"/api/v1/agenda/eventos/{ev2}/cancelar", headers=HA)
        await c.delete(f"/api/v1/agenda/eventos/{ev2}", headers=HA)

        print("9. Módulo deshabilitado")
        limpiar()
        t = await crear(comun["id"], VECINO)
        limpiar()
        from app.services.municipios import modulos as m
        real = m.modulo_esta_habilitado

        async def _no(*a, **k):
            return False
        m.modulo_esta_habilitado = _no
        await svc.avisar_turno(t["id_turno"], "confirmado")
        m.modulo_esta_habilitado = real
        check("no sale nada", not MAILS and not PUSH)
        await c.patch(f"/api/v1/turnos/{t['id_turno']}/cancelar", headers=HA)

    print(f"\n{sum(RES)} OK · {len(RES) - sum(RES)} FAIL")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
