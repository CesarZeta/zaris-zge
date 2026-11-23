# -*- coding: utf-8 -*-
"""
Smoke in-process — app de agentes, F1 backend: relevamientos (mig 141) y control de entradas.

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_agentes_app.py

SOLO LOCAL (aborta si la DB no es zaris_dev). App FastAPI real con httpx.ASGITransport. Los datos
de partida los inserta el dueño de la base (SesionSistema) y cada caso borra lo que crea. Mails en
MOCK y Storage simulado: nada sale a la red. Plan: PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md.
"""
import asyncio
import os
import sys
import uuid
from datetime import timedelta
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

settings.RESEND_API_KEY = ""  # MOCK: nunca sale un mail

from app.core.sistema import SesionSistema as AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.core import storage as _storage  # noqa: E402
from app.services import email as svc_email  # noqa: E402
from app.services import encuestas_service  # noqa: E402
from app.services import push as svc_push  # noqa: E402
from app.utils.fechas import hoy_local  # noqa: E402

MAILS: list[dict] = []


async def _capturar(to, subject, body_html, body_text=None, from_override=None):
    MAILS.append({"to": to, "subject": subject})
    return True


async def _url_subida_falsa(path, *a, **kw):
    return {"upload_url": f"https://storage.invalid/{path}", "url": f"https://storage.invalid/{path}", "bucket": "reclamos-adjuntos", "path": path, "token": "x"}


svc_email.enviar_mail = _capturar
_storage.crear_signed_upload_url = _url_subida_falsa

PWD_DEV = os.environ.get("ZARIS_QA_PASS") or "123456"
ADMIN = "ciudadanovl@municipio.gob.ar"      # nivel 1
GESTION = "f5medico@municipio.gob.ar"       # nivel 4, con agente
GESTION_2 = "f110.51957994@example.com"     # nivel 4, otro agente
CONSULTOR = "f5consultor@municipio.gob.ar"  # nivel 5
OK = FAIL = 0
CREADOS: list[int] = []  # reclamos a borrar al final


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


async def ejecutar(sql: str, **params) -> Optional[dict]:
    async with AsyncSessionLocal() as s:
        res = await s.execute(text(sql), params)
        row = res.mappings().first() if res.returns_rows else None
        await s.commit()
        return dict(row) if row else None


async def login(c: httpx.AsyncClient, email: str) -> dict:
    r = await c.post("/api/v1/auth/login", json={"identificador": email, "password": PWD_DEV})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text[:200]}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _tipo_de_prueba() -> dict:
    return await q1(
        "SELECT tr.id_tipo_reclamo, tr.id_subarea FROM tipo_reclamo tr JOIN subarea s ON s.id_subarea = tr.id_subarea "
        "WHERE tr.activo AND s.activo AND tr.id_municipio = 1 ORDER BY tr.id_tipo_reclamo LIMIT 1")


def _cuerpo(tipo: dict, **extra) -> dict:
    return {"id_tipo_reclamo": tipo["id_tipo_reclamo"], "descripcion": "Smoke: bache relevado en la recorrida",
            "direccion": "Av. Smoke 1234", **extra}


# ─── Relevamientos ───────────────────────────────────────────────────────────

async def test_alta_relevamiento(c, h) -> Optional[dict]:
    print("[1] Un agente de nivel Gestión carga un relevamiento")
    tipo = await _tipo_de_prueba()
    r = await c.post("/api/v1/agentes/relevamientos", headers=h["gestion"],
                     json=_cuerpo(tipo, latitud=-34.52, longitud=-58.49, fuente_geolocalizacion="gps_dispositivo"))
    check(r.status_code == 201, "201", f"{r.status_code} {r.text[:200]}")
    if r.status_code != 201:
        return None
    d = r.json()
    CREADOS.append(d["id_reclamo"])
    check(d["nro_reclamo"].startswith("REL-"), "numeración propia REL-", d["nro_reclamo"])
    fila = await q1("SELECT es_relevamiento, id_ciudadano, canal_origen, estado, id_usuario_alta, "
                    "(SELECT id_usuario FROM usuarios WHERE email = :e) AS yo FROM reclamos WHERE id_reclamo = :i",
                    i=d["id_reclamo"], e=GESTION)
    check(fila["es_relevamiento"] and fila["id_ciudadano"] is None, "marcado y sin ciudadano", str(fila))
    check(fila["id_usuario_alta"] == fila["yo"], "queda a nombre del agente")
    check(fila["canal_origen"] == "app_agentes", "el canal es la app de agentes", str(fila["canal_origen"]))
    h1 = await q1("SELECT accion, nota FROM reclamo_historial WHERE id_reclamo = :i ORDER BY id_historial LIMIT 1",
                  i=d["id_reclamo"])
    check(h1 and h1["accion"] == "Relevamiento ingresado" and "app de agentes" in h1["nota"], "historial", str(h1))
    return d


async def test_reclamo_sigue_con_rec(c, h) -> None:
    print("[2] Un reclamo común sigue numerándose REC- con su propio contador")
    tipo = await _tipo_de_prueba()
    r = await c.post("/api/v1/reclamos", headers=h["admin"],
                     json={"id_ciudadano": 3, "id_tipo_reclamo": tipo["id_tipo_reclamo"],
                           "descripcion": "Smoke reclamo común", "canal_origen": "oficio"})
    check(r.status_code == 201 and r.json()["nro_reclamo"].startswith("REC-"), "REC-", r.text[:200])
    if r.status_code == 201:
        CREADOS.append(r.json()["id_reclamo"])


async def test_exige_persona(c, h) -> None:
    print("[13] Sin ficha de persona vinculada no se carga un relevamiento; con ficha, es el remitente")
    tipo = await _tipo_de_prueba()
    f = await q1("SELECT id_ciudadano FROM usuarios WHERE email = :e", e=GESTION_2)
    await ejecutar("UPDATE usuarios SET id_ciudadano = NULL WHERE email = :e", e=GESTION_2)
    try:
        r = await c.post("/api/v1/agentes/relevamientos", headers=h["gestion2"], json=_cuerpo(tipo))
        check(r.status_code == 403 and "ficha de persona" in r.text, "sin ficha: 403 con el motivo", r.text[:160])
    finally:
        await ejecutar("UPDATE usuarios SET id_ciudadano = :c WHERE email = :e", c=f["id_ciudadano"], e=GESTION_2)
    r = await c.post("/api/v1/agentes/relevamientos", headers=h["gestion2"], json=_cuerpo(tipo))
    check(r.status_code == 201, "con ficha: 201", r.text[:160])
    if r.status_code == 201:
        CREADOS.append(r.json()["id_reclamo"])
        d = (await c.get(f"/api/v1/agentes/relevamientos/{r.json()['id_reclamo']}", headers=h["gestion2"])).json()
        check(bool(d.get("remitente")), "el detalle trae el remitente", str(d.get("remitente")))


async def test_publico_sin_cuenta(c) -> None:
    print("[14] Sin cuenta no se saca turno ni entrada; ver y cancelar por el link siguen andando")
    r = await c.post("/api/v1/turnos/publico/reservar", json={})
    check(r.status_code == 410 and "portal" in r.text, "turno sin cuenta: 410", f"{r.status_code} {r.text[:120]}")
    r = await c.post(f"/api/v1/agenda/publico/evento/{uuid.uuid4()}/reservar", json={})
    check(r.status_code == 410 and "portal" in r.text, "entrada sin cuenta: 410", f"{r.status_code} {r.text[:120]}")
    antes = (await q1("SELECT COUNT(*) AS n FROM ciudadanos"))["n"]
    t = await ejecutar("""
        INSERT INTO turnos (id_ciudadano, id_agente, id_tipo_prestacion, fecha, hora_inicio, hora_fin, estado, origen, id_municipio)
        SELECT 3, a.id_agente, tp.id_tipo_prestacion, CURRENT_DATE + 400, '03:00', '03:10', 'reservado', 'autoservicio', 1
          FROM (SELECT id_agente FROM agentes WHERE id_municipio = 1 AND activo ORDER BY 1 LIMIT 1) a,
               (SELECT id_tipo_prestacion FROM tipo_prestacion WHERE id_municipio = 1 AND activo ORDER BY 1 LIMIT 1) tp
        RETURNING id_turno, CAST(token_turno AS text) AS tok""")
    ev = await _evento(hoy_local(), "Smoke link de entrada")
    try:
        r = await c.get(f"/api/v1/turnos/publico/turno/{t['tok']}")
        check(r.status_code == 200, "ver el turno por su link", f"{r.status_code} {r.text[:120]}")
        r = await c.delete(f"/api/v1/turnos/publico/turno/{t['tok']}")
        check(r.status_code == 200 and r.json()["estado"] == "cancelado", "cancelar el turno por su link", f"{r.status_code} {r.text[:120]}")
        rs = await ejecutar("""
            INSERT INTO evento_reservas (id_evento, id_ciudadano, id_estado_reserva, origen, token_reserva, activo, id_municipio)
            VALUES (:e, 3, (SELECT id_estado_reserva FROM estado_reserva WHERE codigo = 'reservada'), 'autoservicio',
                    gen_random_uuid(), TRUE, 1) RETURNING CAST(token_reserva AS text) AS tok""", e=ev)
        r = await c.get(f"/api/v1/agenda/publico/reserva/{rs['tok']}")
        check(r.status_code == 200, "ver la reserva por su link", f"{r.status_code} {r.text[:120]}")
        r = await c.delete(f"/api/v1/agenda/publico/reserva/{rs['tok']}")
        check(r.status_code == 200 and r.json()["estado_codigo"] == "cancelada", "cancelar la reserva por su link", f"{r.status_code} {r.text[:120]}")
        evt = await q1("UPDATE eventos SET admite_autoservicio = TRUE, token_publico = gen_random_uuid() WHERE id_evento = :e "
                       "RETURNING CAST(token_publico AS text) AS tok", e=ev)
        await ejecutar("UPDATE eventos SET admite_autoservicio = TRUE, token_publico = CAST(:t AS uuid) WHERE id_evento = :e", t=evt["tok"], e=ev)
        r = await c.get(f"/api/v1/agenda/publico/evento/{evt['tok']}")
        check(r.status_code == 200, "la página del evento se ve", f"{r.status_code} {r.text[:120]}")
        check((await q1("SELECT COUNT(*) AS n FROM ciudadanos"))["n"] == antes, "no se creó ninguna persona")
    finally:
        await ejecutar("DELETE FROM turnos WHERE id_turno = :i", i=t["id_turno"])
        await ejecutar("DELETE FROM evento_reservas WHERE id_evento = :e", e=ev)
        await ejecutar("DELETE FROM eventos WHERE id_evento = :e", e=ev)


async def test_validaciones(c, h) -> None:
    print("[3] Validaciones y permisos del alta")
    tipo = await _tipo_de_prueba()
    r = await c.post("/api/v1/agentes/relevamientos", headers=h["consultor"], json=_cuerpo(tipo))
    check(r.status_code == 403, "Consultor (5): 403", str(r.status_code))
    r = await c.post("/api/v1/agentes/relevamientos", headers=h["gestion"], json=_cuerpo(tipo, latitud=-34.5))
    check(r.status_code == 422, "latitud sin longitud: 422", str(r.status_code))
    r = await c.post("/api/v1/agentes/relevamientos", headers=h["gestion"],
                     json={**_cuerpo(tipo), "descripcion": "   abc  "})
    check(r.status_code == 422, "descripción corta: 422", str(r.status_code))
    otro = await q1("SELECT id_tipo_reclamo FROM tipo_reclamo WHERE id_municipio <> 1 LIMIT 1")
    if otro:
        r = await c.post("/api/v1/agentes/relevamientos", headers=h["gestion"],
                         json={**_cuerpo(tipo), "id_tipo_reclamo": otro["id_tipo_reclamo"]})
        check(r.status_code == 422, "tipo de otro municipio: 422", str(r.status_code))
    r = await c.post("/api/v1/agentes/relevamientos", headers=h["gestion"],
                     json={**_cuerpo(tipo), "id_tipo_reclamo": 2_000_000_000})
    check(r.status_code == 422, "tipo inexistente: 422", str(r.status_code))


async def test_listado_y_detalle(c, h, rel: dict) -> None:
    print("[4] Mis relevamientos y el detalle: cada agente ve solo lo suyo")
    r = await c.get("/api/v1/agentes/relevamientos", headers=h["gestion"])
    ids = [x["id_reclamo"] for x in r.json()] if r.status_code == 200 else []
    check(rel["id_reclamo"] in ids, "aparece en mis relevamientos", str(r.status_code))
    check(int(r.headers.get("X-Total-Count", "0")) >= 1, "X-Total-Count")
    r = await c.get(f"/api/v1/agentes/relevamientos/{rel['id_reclamo']}", headers=h["gestion"])
    check(r.status_code == 200 and r.json()["historial"], "detalle con historial", r.text[:200])
    r = await c.get("/api/v1/agentes/relevamientos", headers=h["gestion2"])
    check(rel["id_reclamo"] not in [x["id_reclamo"] for x in r.json()], "otro agente no lo lista")
    r = await c.get(f"/api/v1/agentes/relevamientos/{rel['id_reclamo']}", headers=h["gestion2"])
    check(r.status_code == 404, "otro agente: 404", str(r.status_code))
    r = await c.get("/api/v1/agentes/relevamientos/3000000000", headers=h["gestion"])
    check(r.status_code == 404, "id fuera de rango: 404", str(r.status_code))


async def test_adjuntos_del_autor(c, h, rel: dict) -> None:
    print("[5] Quien cargó el relevamiento le sube fotos; otro agente de nivel Gestión no")
    body = {"nombre_archivo": "foto.jpg", "mime_type": "image/jpeg", "tamano_bytes": 1000}
    r = await c.post(f"/api/v1/reclamos/{rel['id_reclamo']}/adjuntos/upload-url", headers=h["gestion"], json=body)
    check(r.status_code == 201, "autor: 201", f"{r.status_code} {r.text[:200]}")
    r = await c.post(f"/api/v1/reclamos/{rel['id_reclamo']}/adjuntos/upload-url", headers=h["gestion2"], json=body)
    check(r.status_code == 403, "otro agente de nivel 4: 403", str(r.status_code))
    reclamo_comun = await q1("SELECT id_reclamo FROM reclamos WHERE id_municipio = 1 AND NOT es_relevamiento "
                             "AND activo ORDER BY id_reclamo DESC LIMIT 1")
    r = await c.post(f"/api/v1/reclamos/{reclamo_comun['id_reclamo']}/adjuntos/upload-url",
                     headers=h["gestion"], json=body)
    check(r.status_code == 403, "nivel 4 en un reclamo común: sigue 403", str(r.status_code))
    await ejecutar("DELETE FROM reclamo_adjuntos WHERE id_reclamo = :i", i=rel["id_reclamo"])


async def test_sin_avisos_ni_encuesta(c, h, rel: dict) -> None:
    print("[6] Resolver un relevamiento no avisa a nadie ni crea encuesta")
    MAILS.clear()
    avisos_antes = (await q1("SELECT COUNT(*) AS n FROM ciudadano_aviso"))["n"]
    r = await c.post(f"/api/v1/reclamos/{rel['id_reclamo']}/resolver", headers=h["admin"],
                     json={"resolucion": "Bache tapado en la recorrida"})
    check(r.status_code in (200, 201), "resuelto por el admin", f"{r.status_code} {r.text[:200]}")
    enc = await q1("SELECT COUNT(*) AS n FROM encuesta_envio WHERE id_reclamo = :i", i=rel["id_reclamo"])
    check(enc["n"] == 0, "sin encuesta", str(enc))
    async with AsyncSessionLocal() as s:
        envio, motivo = await encuestas_service.crear_envio_para_reclamo(s, rel["id_reclamo"])
    check(envio is None and motivo == encuestas_service.MOTIVO_RELEVAMIENTO,
          "crear_envio_para_reclamo lo rechaza por ser relevamiento", str(motivo))
    await svc_push.notificar_estado_reclamo(rel["id_reclamo"])
    avisos_despues = (await q1("SELECT COUNT(*) AS n FROM ciudadano_aviso"))["n"]
    check(avisos_despues == avisos_antes, "sin avisos en la bandeja de ningún vecino")
    check(not MAILS, "sin mails", str(MAILS))


async def test_backoffice_y_datos(c, h, rel: dict) -> None:
    print("[11] F1b: Reclamos separa por clase y Datos cuenta los relevamientos aparte")
    ids = lambda r: [x["id_reclamo"] for x in r.json()]  # noqa: E731
    r = await c.get("/api/v1/reclamos", headers=h["admin"], params={"clase": "relevamientos", "limit": 500})
    check(r.status_code == 200 and rel["id_reclamo"] in ids(r), "clase=relevamientos lo trae", str(r.status_code))
    check(all(x["es_relevamiento"] for x in r.json()), "y solo trae relevamientos")
    r = await c.get("/api/v1/reclamos", headers=h["admin"],
                    params={"clase": "reclamos", "texto": rel["nro_reclamo"], "limit": 500})
    check(rel["id_reclamo"] not in ids(r), "clase=reclamos no lo trae")
    r = await c.get("/api/v1/reclamos", headers=h["admin"], params={"texto": rel["nro_reclamo"]})
    check(rel["id_reclamo"] in ids(r), "sin clase: lo trae junto con los reclamos")
    r = await c.get("/api/v1/reclamos", headers=h["admin"], params={"clase": "basura"})
    check(r.status_code == 422, "clase inválida: 422", str(r.status_code))
    st_rel = (await c.get("/api/v1/reclamos/stats", headers=h["admin"], params={"clase": "relevamientos"})).json()
    st_rec = (await c.get("/api/v1/reclamos/stats", headers=h["admin"], params={"clase": "reclamos"})).json()
    st_all = (await c.get("/api/v1/reclamos/stats", headers=h["admin"])).json()
    check(sum(st_rel.values()) + sum(st_rec.values()) == sum(st_all.values()) and sum(st_rel.values()) >= 1,
          "contadores: relevamientos + reclamos = todos", f"{st_rel} {st_rec}")

    d = (await c.get(f"/api/v1/reclamos/{rel['id_reclamo']}", headers=h["admin"])).json()
    check(d.get("es_relevamiento") is True and d.get("cargado_por_nombre"), "detalle: marca y quién lo cargó",
          str({k: d.get(k) for k in ("es_relevamiento", "cargado_por_nombre")}))

    nuevo = await c.post("/api/v1/agentes/relevamientos", headers=h["gestion"],
                         json=_cuerpo(await _tipo_de_prueba()))
    if nuevo.status_code == 201:
        idn = nuevo.json()["id_reclamo"]
        CREADOS.append(idn)
        est = (await q1("SELECT estado FROM reclamos WHERE id_reclamo = :i", i=idn))["estado"]
        if est == "Sin asignar":
            r = await c.put(f"/api/v1/reclamos/{idn}", headers=h["admin"], json={"id_ciudadano": 3})
            check(r.status_code == 422, "editar: asignarle un vecino da 422", str(r.status_code))
            r = await c.put(f"/api/v1/reclamos/{idn}", headers=h["admin"],
                            json={"descripcion": "Smoke: relevamiento editado", "id_ciudadano": None})
            check(r.status_code == 200, "editar la descripción anda", f"{r.status_code} {r.text[:150]}")
        else:
            print(f"  (la asignación automática ya lo pasó a {est}: se saltea la edición completa)")

    print("[12] Datos: la transacción separa reclamos y relevamientos en el Operativo y el Ejecutivo")
    n_rel = (await q1("SELECT COUNT(*) AS n FROM reclamos WHERE id_municipio = 1 AND activo AND es_relevamiento"))["n"]
    n_rec = (await q1("SELECT COUNT(*) AS n FROM reclamos WHERE id_municipio = 1 AND activo AND NOT es_relevamiento"))["n"]
    for url in ("/api/v1/bi/resumen", "/api/v1/bi/ejecutivo/score"):
        t_def = (await c.get(url, headers=h["admin"])).json()["total"]
        t_rec = (await c.get(url, headers=h["admin"], params={"clase": "reclamos"})).json()["total"]
        t_rel = (await c.get(url, headers=h["admin"], params={"clase": "relevamientos"})).json()["total"]
        check(t_def == t_rec == n_rec, f"{url}: por defecto solo reclamos del vecino", f"{t_def} {t_rec} {n_rec}")
        check(t_rel == n_rel, f"{url}: clase=relevamientos los cuenta aparte", f"{t_rel} {n_rel}")
    r = await c.get("/api/v1/bi/resumen", headers=h["admin"], params={"clase": "basura"})
    check(r.status_code == 422, "clase inválida: 422", str(r.status_code))


async def test_subreclamo_hereda(c, h) -> None:
    print("[7] El subreclamo de un relevamiento también es relevamiento y sin ciudadano")
    tipo = await _tipo_de_prueba()
    r = await c.post("/api/v1/agentes/relevamientos", headers=h["gestion"], json=_cuerpo(tipo))
    if r.status_code != 201:
        check(False, "alta del padre", r.text[:200])
        return
    padre = r.json()
    CREADOS.append(padre["id_reclamo"])
    r = await c.post(f"/api/v1/reclamos/{padre['id_reclamo']}/subreclamo", headers=h["admin"],
                     json={"descripcion": "Smoke subreclamo", "id_tipo_reclamo": tipo["id_tipo_reclamo"],
                           "id_ciudadano": 3})
    check(r.status_code == 201, "201", f"{r.status_code} {r.text[:200]}")
    if r.status_code == 201:
        hijo = r.json()
        id_hijo = hijo.get("id_reclamo") or hijo.get("id_subreclamo")
        CREADOS.append(id_hijo)
        f = await q1("SELECT es_relevamiento, id_ciudadano, nro_reclamo FROM reclamos WHERE id_reclamo = :i", i=id_hijo)
        check(f["es_relevamiento"] and f["id_ciudadano"] is None and f["nro_reclamo"].startswith("REL-"),
              "hereda la marca, sin ciudadano, REL-", str(f))


async def test_check_de_la_base() -> None:
    print("[8] La base no acepta un relevamiento con ciudadano")
    try:
        await ejecutar("UPDATE reclamos SET id_ciudadano = 3 WHERE id_reclamo = :i", i=CREADOS[0])
        check(False, "el CHECK lo rechaza")
    except Exception as e:  # noqa: BLE001
        check("ck_reclamos_relevamiento_sin_ciudadano" in str(e), "el CHECK lo rechaza", str(e)[:120])


# ─── Control de entradas ─────────────────────────────────────────────────────

async def _evento(fecha, nombre: str) -> int:
    f = await ejecutar(
        "INSERT INTO eventos (nombre, fecha, hora_inicio, hora_fin, id_estado_evento, capacidad_ciudadanos, "
        "activo, id_municipio) VALUES (:n, :f, '10:00', '12:00', "
        "(SELECT id_estado_evento FROM estado_evento WHERE codigo = 'activo'), 50, TRUE, 1) RETURNING id_evento",
        n=nombre, f=fecha)
    return f["id_evento"]


async def _reserva(id_evento: int, id_ciudadano: int, estado: str) -> str:
    qr = f"SMK-AGT-{uuid.uuid4().hex[:10]}"
    await ejecutar(
        "INSERT INTO evento_reservas (id_evento, id_ciudadano, id_estado_reserva, origen, qr_codigo, activo, id_municipio) "
        "VALUES (:e, :c, (SELECT id_estado_reserva FROM estado_reserva WHERE codigo = :es), 'backoffice', :q, TRUE, 1)",
        e=id_evento, c=id_ciudadano, es=estado, q=qr)
    return qr


async def test_control_de_entradas(c, h) -> None:
    print("[9] Control de entradas: válida, repetida, otro día, cancelada, inexistente")
    ciudadanos = [x for (x,) in (await _todas("SELECT id_ciudadano FROM ciudadanos WHERE id_municipio = 1 "
                                             "AND activo ORDER BY id_ciudadano LIMIT 2"))]
    hoy, manana = hoy_local(), hoy_local() + timedelta(days=1)
    e_hoy = await _evento(hoy, "Smoke control de entradas")
    e_manana = await _evento(manana, "Smoke evento de mañana")
    try:
        qr_ok = await _reserva(e_hoy, ciudadanos[0], "reservada")
        qr_cancelada = await _reserva(e_hoy, ciudadanos[1], "cancelada")
        qr_manana = await _reserva(e_manana, ciudadanos[0], "reservada")
        ag = await q1("SELECT a.id_agente FROM agentes a JOIN usuarios u ON u.id_usuario = a.id_usuario "
                      "WHERE u.email = :e", e=GESTION)
        await ejecutar("INSERT INTO evento_encargados (id_evento, tipo_recurso, id_recurso, activo, id_municipio) "
                       "VALUES (:e, 'agente', :a, TRUE, 1)", e=e_hoy, a=ag["id_agente"])

        url = "/api/v1/agentes/entradas/acreditar-qr"
        r = await c.post(url, headers=h["gestion"], json={"qr_codigo": f"  {qr_ok} "})
        d = r.json()
        check(r.status_code == 200 and d["resultado"] == "acreditada", "válida: acreditada", r.text[:200])
        check(d.get("reserva", {}) and d["reserva"]["evento"] == "Smoke control de entradas" and d["reserva"]["ciudadano"],
              "trae evento y ciudadano", str(d.get("reserva")))
        est = await q1("SELECT er.codigo FROM evento_reservas r JOIN estado_reserva er USING (id_estado_reserva) "
                       "WHERE r.qr_codigo = :q", q=qr_ok)
        check(est["codigo"] == "asistio", "la entrada queda consumida")
        r = await c.post(url, headers=h["gestion2"], json={"qr_codigo": qr_ok})
        d2 = r.json()
        check(d2["resultado"] == "ya_acreditada" and d2["acreditada_en"], "repetida: ya_acreditada con la hora",
              r.text[:200])
        r = await c.post(url, headers=h["gestion"], json={"qr_codigo": qr_manana})
        check(r.json()["resultado"] == "otra_fecha", "de otro día: otra_fecha", r.text[:200])
        est = await q1("SELECT er.codigo FROM evento_reservas r JOIN estado_reserva er USING (id_estado_reserva) "
                       "WHERE r.qr_codigo = :q", q=qr_manana)
        check(est["codigo"] == "reservada", "la de otro día no se consume")
        r = await c.post(url, headers=h["gestion"], json={"qr_codigo": qr_cancelada})
        check(r.json()["resultado"] == "cancelada", "cancelada", r.text[:200])
        r = await c.post(url, headers=h["gestion"], json={"qr_codigo": "basura-que-no-existe"})
        check(r.status_code == 200 and r.json()["resultado"] == "no_encontrada", "inexistente: no_encontrada")
        r = await c.post(url, headers=h["consultor"], json={"qr_codigo": qr_ok})
        check(r.status_code == 403, "Consultor (5): 403", str(r.status_code))
        r = await c.post("/api/v1/agenda/reservas/acreditar-qr", headers=h["admin"], json={"qr_codigo": qr_cancelada})
        check(r.status_code == 409, "el endpoint de Agenda sigue igual (409 cancelada)", str(r.status_code))

        print("[10] Eventos de hoy: los míos primero, con los contadores")
        r = await c.get("/api/v1/agentes/entradas/eventos-hoy", headers=h["gestion"])
        lista = r.json() if r.status_code == 200 else []
        mio = next((x for x in lista if x["id_evento"] == e_hoy), None)
        check(mio is not None and mio["soy_encargado"], "aparece como mío", str(mio))
        check(mio and mio["reservas"] == 1 and mio["acreditadas"] == 1, "1 reserva vigente, 1 acreditada", str(mio))
        check(lista and lista[0]["soy_encargado"], "los míos van primero")
        check(all(x["id_evento"] != e_manana for x in lista), "el de mañana no aparece")
        r = await c.get("/api/v1/agentes/entradas/eventos-hoy", headers=h["gestion2"])
        otro = next((x for x in r.json() if x["id_evento"] == e_hoy), None)
        check(otro is not None and not otro["soy_encargado"], "para otro agente no es suyo")
    finally:
        for e in (e_hoy, e_manana):
            await ejecutar("DELETE FROM encuesta_envio WHERE id_evento_reserva IN "
                           "(SELECT id_evento_reserva FROM evento_reservas WHERE id_evento = :e)", e=e)
            await ejecutar("DELETE FROM agenda_audit_log WHERE entidad = 'reserva' AND id_entidad IN "
                           "(SELECT id_evento_reserva FROM evento_reservas WHERE id_evento = :e)", e=e)
            await ejecutar("DELETE FROM evento_reservas WHERE id_evento = :e", e=e)
            await ejecutar("DELETE FROM evento_encargados WHERE id_evento = :e", e=e)
            await ejecutar("DELETE FROM eventos WHERE id_evento = :e", e=e)


async def _todas(sql: str, **params) -> list:
    async with AsyncSessionLocal() as s:
        return (await s.execute(text(sql), params)).all()


async def limpiar() -> None:
    for i in reversed(CREADOS):
        await ejecutar("DELETE FROM encuesta_envio WHERE id_reclamo = :i", i=i)
        await ejecutar("DELETE FROM ordenes_trabajo WHERE id_reclamo = :i", i=i)
        await ejecutar("DELETE FROM reclamo_historial WHERE id_reclamo = :i", i=i)
        await ejecutar("DELETE FROM reclamo_adjuntos WHERE id_reclamo = :i", i=i)
        await ejecutar("UPDATE reclamos SET id_reclamo_padre = NULL WHERE id_reclamo_padre = :i", i=i)
        await ejecutar("DELETE FROM reclamos WHERE id_reclamo = :i", i=i)


async def main() -> int:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://smoke.local") as c:
        h = {"admin": await login(c, ADMIN), "gestion": await login(c, GESTION),
             "gestion2": await login(c, GESTION_2), "consultor": await login(c, CONSULTOR)}
        try:
            rel = await test_alta_relevamiento(c, h)
            await test_reclamo_sigue_con_rec(c, h)
            await test_validaciones(c, h)
            await test_exige_persona(c, h)
            await test_publico_sin_cuenta(c)
            if rel:
                await test_listado_y_detalle(c, h, rel)
                await test_adjuntos_del_autor(c, h, rel)
                await test_sin_avisos_ni_encuesta(c, h, rel)
                await test_backoffice_y_datos(c, h, rel)
            await test_subreclamo_hereda(c, h)
            if CREADOS:
                await test_check_de_la_base()
            await test_control_de_entradas(c, h)
        finally:
            await limpiar()
    print(f"\n{OK}/{OK + FAIL} OK")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
