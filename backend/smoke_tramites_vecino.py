# -*- coding: utf-8 -*-
"""
Smoke in-process — trámites del vecino, fase 1 backend (cada task le suma casos).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_tramites_vecino.py

SOLO LOCAL (aborta si la DB no es zaris_dev). App FastAPI real con httpx.ASGITransport; los
datos de partida los inserta el dueño de la base (SesionSistema). Cada caso limpia lo que crea.
"""
import asyncio
import os
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
    sys.exit("ABORT: este smoke es SOLO LOCAL (la DB configurada no es zaris_dev).")

settings.RESEND_API_KEY = ""  # MOCK: nunca sale un mail

from app.core.sistema import SesionSistema as AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.core import storage as _storage  # noqa: E402
from app.services import email as svc_email  # noqa: E402
from app.services.tramites import ciclo_vida as _ciclo_vida  # noqa: E402
from app.services.identidad import MSG_IDENTIDAD_PORTAL  # noqa: E402

# Storage local apunta a PROD: nada sale a la red; se registran las llamadas.
SUBIDOS: list[str] = []
BORRADOS: list[str] = []
FALLAR_EN_SUBIDA_N: list[int] = []  # si tiene un n, la subida número n (1-based) levanta
MAILS: list[dict] = []


async def _subir_falso(path, contenido, content_type, bucket=None, **kw):
    SUBIDOS.append(path)
    if FALLAR_EN_SUBIDA_N and len(SUBIDOS) == FALLAR_EN_SUBIDA_N[0]:
        raise RuntimeError("falla simulada de Storage")


async def _borrar_falso(path, bucket=None):
    BORRADOS.append(path)


async def _capturar(to, subject, body_html, body_text=None, from_override=None):
    MAILS.append({"to": to, "subject": subject, "html": body_html})
    return True


_storage.subir_objeto = _subir_falso
_storage.borrar_objeto = _borrar_falso
svc_email.enviar_mail = _capturar
_ciclo_vida.enviar_mail = _capturar  # ciclo_vida lo importó por nombre al cargar app.main

PWD_DEV = os.environ.get("ZARIS_QA_PASS") or "123456"
ADMIN_EMAIL = "ciudadanovl@municipio.gob.ar"
ID_CIUDADANO = 3
DATOS_PODA = {"direccion_arbol": "Calle Smoke 123", "motivo": "Smoke de alta"}
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


async def ejecutar(sql: str, **params) -> Optional[dict]:
    """Escribe como dueño y commitea; devuelve la fila de un RETURNING si la hay."""
    async with AsyncSessionLocal() as s:
        res = await s.execute(text(sql), params)
        row = res.mappings().first() if res.returns_rows else None
        await s.commit()
        return dict(row) if row else None


async def login_admin(c: httpx.AsyncClient) -> dict:
    r = await c.post("/api/v1/auth/login", json={"identificador": ADMIN_EMAIL, "password": PWD_DEV})
    assert r.status_code == 200, f"login admin: {r.status_code} {r.text[:200]}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_backoffice_ve_movimientos_del_vecino(c: httpx.AsyncClient, ha: dict) -> None:
    print("[1] El backoffice ve movimientos y documentos del vecino")
    mun = (await q1("SELECT id_municipio FROM municipios WHERE direccion_base = TRUE LIMIT 1"))["id_municipio"]
    tipo = await q1(
        "SELECT v.id_tipo_tramite_version AS ver, e.id_tipo_tramite_estado AS est "
        "FROM tipo_tramite tt JOIN tipo_tramite_version v ON v.id_tipo_tramite = tt.id_tipo_tramite "
        "JOIN tipo_tramite_estado e ON e.id_tipo_tramite_version = v.id_tipo_tramite_version AND e.es_inicial "
        "WHERE tt.codigo = 'poda-arbol' AND tt.id_municipio = :m ORDER BY v.id_tipo_tramite_version DESC LIMIT 1",
        m=mun)
    ciu = await q1("SELECT apellido, nombre FROM ciudadanos WHERE id_ciudadano = :i", i=ID_CIUDADANO)
    if not tipo or not ciu:
        check(False, "datos de partida (poda-arbol con estado inicial, vecino 3)")
        return
    numero = "SMK-VEC-" + uuid.uuid4().hex[:8]
    t = await ejecutar(
        "INSERT INTO tramite (numero_expediente, id_tipo_tramite_version, asunto, iniciador_tipo, "
        "id_ciudadano_iniciador, id_agente_iniciador, id_tipo_tramite_estado_actual, id_municipio) "
        "VALUES (:n, :v, 'Smoke vecino actor', 'ciudadano', :c, NULL, :e, :m) RETURNING id_tramite",
        n=numero, v=tipo["ver"], c=ID_CIUDADANO, e=tipo["est"], m=mun)
    idt = t["id_tramite"]
    try:
        await ejecutar(
            "INSERT INTO tramite_movimiento (id_tramite, orden_secuencial, tipo, comentario, "
            "id_agente, id_ciudadano_actor, id_municipio) VALUES (:t, 1, 'comentario', 'del vecino', NULL, :c, :m)",
            t=idt, c=ID_CIUDADANO, m=mun)
        await ejecutar(
            "INSERT INTO tramite_documento (id_tramite, nombre, nombre_archivo_original, storage_path, "
            "mime_type, tamano_bytes, hash_sha256, posicion_orden, id_agente_subio, id_ciudadano_subio, id_municipio) "
            "VALUES (:t, 'dni.pdf', 'dni.pdf', 'smoke/dni.pdf', 'application/pdf', 10, 'x', 1, NULL, :c, :m)",
            t=idt, c=ID_CIUDADANO, m=mun)
        esperado = f"{ciu['apellido']}, {ciu['nombre']}"

        r = await c.get(f"/api/v1/tramites/{numero}", headers=ha)
        check(r.status_code == 200, "GET detalle 200", f"{r.status_code} {r.text[:200]}")

        r = await c.get(f"/api/v1/tramites/{numero}/movimientos", headers=ha)
        movs = r.json().get("movimientos", []) if r.status_code == 200 else []
        check(r.status_code == 200 and len(movs) == 1, "movimientos: la fila del vecino está", f"{r.status_code} {r.text[:200]}")
        if movs:
            check(movs[0].get("actor_tipo") == "ciudadano", "movimiento actor_tipo ciudadano", str(movs[0].get("actor_tipo")))
            check(movs[0].get("actor_nombre") == esperado, "movimiento actor_nombre Apellido, Nombre", str(movs[0].get("actor_nombre")))

        r = await c.get(f"/api/v1/tramites/{numero}/documentos", headers=ha)
        docs = r.json().get("documentos", []) if r.status_code == 200 else []
        check(r.status_code == 200 and len(docs) == 1, "documentos: la fila del vecino está", f"{r.status_code} {r.text[:200]}")
        if docs:
            check(docs[0].get("actor_tipo") == "ciudadano", "documento actor_tipo ciudadano", str(docs[0].get("actor_tipo")))
            check(docs[0].get("actor_nombre") == esperado, "documento actor_nombre Apellido, Nombre", str(docs[0].get("actor_nombre")))
    finally:
        await ejecutar("DELETE FROM tramite_documento WHERE id_tramite = :t", t=idt)
        await ejecutar("DELETE FROM tramite_movimiento WHERE id_tramite = :t", t=idt)
        await ejecutar("DELETE FROM tramite WHERE id_tramite = :t", t=idt)


async def _municipio_base() -> int:
    return (await q1("SELECT id_municipio FROM municipios WHERE direccion_base = TRUE LIMIT 1"))["id_municipio"]


async def _vecino_con_cuenta(mun: int) -> Optional[int]:
    r = await q1(
        "SELECT c.id_ciudadano FROM ciudadanos c WHERE c.activo AND c.id_municipio = :m "
        "AND EXISTS (SELECT 1 FROM ciudadano_credencial cc WHERE cc.id_ciudadano = c.id_ciudadano AND cc.activo) "
        "ORDER BY c.id_ciudadano LIMIT 1", m=mun)
    return r["id_ciudadano"] if r else None


async def _vecino_sin_cuenta(mun: int) -> Optional[int]:
    r = await q1(
        "SELECT c.id_ciudadano FROM ciudadanos c WHERE c.activo AND c.id_municipio = :m "
        "AND NOT EXISTS (SELECT 1 FROM ciudadano_credencial cc WHERE cc.id_ciudadano = c.id_ciudadano) "
        "ORDER BY c.id_ciudadano LIMIT 1", m=mun)
    return r["id_ciudadano"] if r else None


async def _tipo_poda(mun: int) -> Optional[dict]:
    return await q1(
        "SELECT id_tipo_tramite, prefijo FROM tipo_tramite WHERE codigo = 'poda-arbol' AND id_municipio = :m "
        "AND activo AND id_version_publicada IS NOT NULL", m=mun)


async def _borrar_tramite(idt: int) -> None:
    await ejecutar("DELETE FROM tramite_aprobacion WHERE id_tramite = :t", t=idt)
    await ejecutar("DELETE FROM tramite_movimiento WHERE id_tramite = :t", t=idt)
    await ejecutar("DELETE FROM tramite WHERE id_tramite = :t", t=idt)


async def test_backoffice_alta_sin_cuenta_422(c: httpx.AsyncClient, ha: dict) -> None:
    print("[2] Alta de backoffice para un vecino sin cuenta: 422 y nada escrito")
    mun = await _municipio_base()
    tipo = await _tipo_poda(mun)
    vid = await _vecino_sin_cuenta(mun)
    if not tipo or not vid:
        check(False, "datos de partida (poda-arbol y un vecino sin credencial)", f"tipo={tipo} vecino={vid}")
        return
    antes = (await q1("SELECT count(*) AS n FROM tramite"))["n"]
    corr_antes = await q1("SELECT COALESCE(SUM(ultimo_numero),0) AS n FROM tipo_tramite_numerador WHERE id_tipo_tramite = :t",
                          t=tipo["id_tipo_tramite"])
    r = await c.post("/api/v1/tramites", headers=ha, json={
        "id_tipo_tramite": tipo["id_tipo_tramite"], "asunto": "Smoke sin cuenta", "datos": DATOS_PODA,
        "iniciador": {"tipo": "ciudadano", "id_ciudadano": vid}})
    check(r.status_code == 422, "responde 422", f"{r.status_code} {r.text[:200]}")
    check("no tiene cuenta en el portal" in r.text, "mensaje de la regla", r.text[:200])
    despues = (await q1("SELECT count(*) AS n FROM tramite"))["n"]
    check(antes == despues, "no se creó ningún trámite", f"{antes} -> {despues}")
    corr_despues = await q1("SELECT COALESCE(SUM(ultimo_numero),0) AS n FROM tipo_tramite_numerador WHERE id_tipo_tramite = :t",
                            t=tipo["id_tipo_tramite"])
    check(corr_antes == corr_despues, "el numerador no avanzó", f"{corr_antes} -> {corr_despues}")


async def test_backoffice_alta_con_cuenta_201(c: httpx.AsyncClient, ha: dict) -> None:
    print("[3] Alta de backoffice para un vecino con cuenta: 201")
    mun = await _municipio_base()
    tipo = await _tipo_poda(mun)
    vid = await _vecino_con_cuenta(mun)
    if not tipo or not vid:
        check(False, "datos de partida (poda-arbol y un vecino con credencial)", f"tipo={tipo} vecino={vid}")
        return
    r = await c.post("/api/v1/tramites", headers=ha, json={
        "id_tipo_tramite": tipo["id_tipo_tramite"], "asunto": "Smoke con cuenta", "datos": DATOS_PODA,
        "iniciador": {"tipo": "ciudadano", "id_ciudadano": vid}})
    check(r.status_code == 201, "responde 201", f"{r.status_code} {r.text[:300]}")
    if r.status_code != 201:
        return
    numero = r.json().get("numero_expediente", "")
    idt = (await q1("SELECT id_tramite, id_agente_iniciador FROM tramite WHERE numero_expediente = :n", n=numero))
    try:
        check(bool(tipo["prefijo"]) and numero.startswith(tipo["prefijo"]), "número con el prefijo del tipo", numero)
        ag = await q1("SELECT a.id_agente FROM agentes a JOIN usuarios u ON u.id_usuario = a.id_usuario "
                      "WHERE u.email = :e LIMIT 1", e=ADMIN_EMAIL)
        check(idt["id_agente_iniciador"] == (ag or {}).get("id_agente"), "id_agente_iniciador = admin", str(idt))
        async with AsyncSessionLocal() as s:
            movs = (await s.execute(text(
                "SELECT tipo, id_agente, id_ciudadano_actor FROM tramite_movimiento WHERE id_tramite = :t ORDER BY orden_secuencial"),
                {"t": idt["id_tramite"]})).mappings().all()
        tipos = [m["tipo"] for m in movs]
        check(tipos[:2] == ["creacion", "numeracion"], "movimientos creacion y numeracion", str(tipos))
        check(all(m["id_agente"] == (ag or {}).get("id_agente") and m["id_ciudadano_actor"] is None for m in movs[:2]),
              "movimientos con id_agente del admin", str([dict(m) for m in movs[:2]]))
    finally:
        await _borrar_tramite(idt["id_tramite"])



# ── Task 3b: identidad validada en el municipio ─────────────────────────────

async def _usuario_fixture(mun: int, nivel: int, con_agente: bool = True) -> dict:
    """Crea (como dueño) un usuario de prueba con clave dev y, si se pide, su agente 1:1."""
    import bcrypt
    suf = uuid.uuid4().hex[:8]
    email = f"smoke3b.n{nivel}.{suf}@smoke3b.local"
    h = bcrypt.hashpw(PWD_DEV.encode(), bcrypt.gensalt()).decode()
    u = await ejecutar(
        "INSERT INTO usuarios (nombre, username, email, password_hash, nivel_acceso, activo, buc_acceso, id_municipio, "
        "password_actualizada_en) VALUES (:n, :un, :e, :h, :niv, TRUE, TRUE, :m, NOW()) RETURNING id_usuario",
        n=f"Smoke3b N{nivel}", un=f"smoke3b_{suf}", e=email, h=h, niv=nivel, m=mun)
    idag = None
    if con_agente:
        ag = await ejecutar(
            "INSERT INTO agentes (nombre, apellido, id_municipio, id_usuario, email, activo) "
            "VALUES ('Smoke3b', :ap, :m, :u, :e, TRUE) RETURNING id_agente",
            ap=f"Nivel{nivel}", m=mun, u=u["id_usuario"], e=email)
        idag = ag["id_agente"]
    return {"id_usuario": u["id_usuario"], "id_agente": idag, "email": email}


async def _borrar_usuario_fixture(f: dict) -> None:
    await ejecutar("DELETE FROM ciudadano_identidad_validacion WHERE id_agente = :a OR id_agente_revoca = :a", a=f["id_agente"] or -1)
    if f["id_agente"]:
        await ejecutar("DELETE FROM agentes WHERE id_agente = :a", a=f["id_agente"])
    await ejecutar("DELETE FROM usuarios WHERE id_usuario = :u", u=f["id_usuario"])


async def _login_fixture(c: httpx.AsyncClient, f: dict) -> dict:
    r = await c.post("/api/v1/auth/login", json={"identificador": f["email"], "password": PWD_DEV})
    assert r.status_code == 200, f"login fixture: {r.status_code} {r.text[:200]}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_identidad_validar_y_revocar(c: httpx.AsyncClient, ha: dict) -> None:
    print("[4] Validar y revocar la identidad del vecino")
    mun = await _municipio_base()
    vid = await _vecino_con_cuenta(mun)
    if not vid:
        check(False, "datos de partida (un vecino con credencial)")
        return
    fx = {n: await _usuario_fixture(mun, n) for n in (2, 3, 4)}
    try:
        h = {n: await _login_fixture(c, f) for n, f in fx.items()}
        base = f"/api/v1/buc/ciudadanos/{vid}"
        cuerpo = {"documento_presentado": "DNI", "observacion": "Smoke 3b"}
        r = await c.post(f"{base}/identidad/validar", headers=h[4], json=cuerpo)
        check(r.status_code == 403, "nivel 4 no valida (403)", f"{r.status_code} {r.text[:150]}")
        r = await c.post(f"{base}/identidad/validar", headers=h[3], json={"documento_presentado": "x"})
        check(r.status_code == 422, "documento de 1 caracter: 422", f"{r.status_code}")
        r = await c.post(f"{base}/identidad/validar", headers=h[3], json=cuerpo)
        check(r.status_code == 201, "nivel 3 valida (201)", f"{r.status_code} {r.text[:200]}")
        r = await c.get(base, headers=h[3])
        iv = r.json().get("identidad_validada") if r.status_code == 200 else None
        check(bool(iv) and bool(iv.get("fecha")) and "Nivel3" in (iv.get("agente_nombre") or ""),
              "la ficha trae identidad_validada con fecha y agente", str(iv))
        r = await c.get(f"{base}/cuentas", headers=h[3])
        check(r.status_code == 200 and bool((r.json().get("identidad_validada") or {}).get("fecha")),
              "/cuentas trae identidad_validada", r.text[:200])
        r = await c.post(f"{base}/identidad/validar", headers=h[3], json=cuerpo)
        check(r.status_code == 409, "validar de nuevo: 409", f"{r.status_code}")
        r = await c.post(f"{base}/identidad/revocar", headers=h[3], json={"motivo": "Documento dudoso"})
        check(r.status_code == 403, "nivel 3 no revoca (403)", f"{r.status_code}")
        r = await c.post(f"{base}/identidad/revocar", headers=h[2], json={"motivo": "abc"})
        check(r.status_code == 422, "motivo corto: 422", f"{r.status_code}")
        r = await c.post(f"{base}/identidad/revocar", headers=h[2], json={"motivo": "Documento dudoso"})
        check(r.status_code == 200, "nivel 2 revoca (200)", f"{r.status_code} {r.text[:200]}")
        r = await c.get(base, headers=h[2])
        check(r.status_code == 200 and r.json().get("identidad_validada") is None, "la ficha vuelve a null", r.text[:200])
        r = await c.post(f"{base}/identidad/revocar", headers=h[2], json={"motivo": "Documento dudoso"})
        check(r.status_code == 404, "revocar sin validación activa: 404", f"{r.status_code}")
        async with AsyncSessionLocal() as s:
            filas = (await s.execute(text(
                "SELECT activo, motivo_revocacion, id_agente_revoca, id_usuario_alta FROM ciudadano_identidad_validacion "
                "WHERE id_ciudadano = :c ORDER BY id_ciudadano_identidad_validacion"), {"c": vid})).mappings().all()
        check(len(filas) == 1 and filas[0]["activo"] is False and filas[0]["id_agente_revoca"] == fx[2]["id_agente"]
              and filas[0]["id_usuario_alta"] == fx[3]["id_usuario"], "en DB la fila queda revocada con quién y por qué", str([dict(f) for f in filas]))
        # una validación nueva tras revocar crea la segunda fila
        r = await c.post(f"{base}/identidad/validar", headers=h[3], json=cuerpo)
        check(r.status_code == 201, "se puede volver a validar tras revocar", f"{r.status_code}")
        n = (await q1("SELECT count(*) AS n FROM ciudadano_identidad_validacion WHERE id_ciudadano = :c", c=vid))["n"]
        check(n == 2, "en DB quedan las dos filas (una revocada)", str(n))
        # sin agente: 403
        sa = await _usuario_fixture(mun, 3, con_agente=False)
        try:
            hs = await _login_fixture(c, sa)
            await ejecutar("DELETE FROM ciudadano_identidad_validacion WHERE id_ciudadano = :c", c=vid)
            r = await c.post(f"{base}/identidad/validar", headers=hs, json=cuerpo)
            check(r.status_code == 403, "nivel 3 sin agente: 403", f"{r.status_code} {r.text[:150]}")
        finally:
            await _borrar_usuario_fixture(sa)
    finally:
        await ejecutar("DELETE FROM ciudadano_identidad_validacion WHERE id_ciudadano = :c", c=vid)
        for f in fx.values():
            await _borrar_usuario_fixture(f)


async def test_identidad_en_perfil_publico(c: httpx.AsyncClient, ha: dict) -> None:
    print("[5] Perfil público: solo la fecha, sin nombre del agente")
    from app.api.routes import publico_perfil
    mun = await _municipio_base()
    vid = await _vecino_con_cuenta(mun)
    ag = await q1("SELECT id_agente FROM agentes WHERE activo AND id_municipio = :m LIMIT 1", m=mun)
    if not vid or not ag:
        check(False, "datos de partida", f"{vid} {ag}")
        return
    await ejecutar("INSERT INTO ciudadano_identidad_validacion (id_ciudadano, id_agente, documento_presentado, id_municipio) "
                   "VALUES (:c, :a, 'DNI', :m)", c=vid, a=ag["id_agente"], m=mun)
    try:
        async with AsyncSessionLocal() as s:
            out = await publico_perfil._perfil_out(s, vid)
        check(set((out.identidad_validada or {}).keys()) == {"fecha"}, "identidad_validada = {fecha}", str(out.identidad_validada))
    finally:
        await ejecutar("DELETE FROM ciudadano_identidad_validacion WHERE id_ciudadano = :c", c=vid)
    async with AsyncSessionLocal() as s:
        out = await publico_perfil._perfil_out(s, vid)
    check(out.identidad_validada is None, "sin validación: null")


async def test_backoffice_alta_exige_identidad(c: httpx.AsyncClient, ha: dict) -> None:
    print("[6] Alta de backoffice de un tipo que exige identidad validada")
    mun = await _municipio_base()
    tipo = await _tipo_poda(mun)
    vid = await _vecino_con_cuenta(mun)
    if not tipo or not vid:
        check(False, "datos de partida", f"tipo={tipo} vecino={vid}")
        return
    previo = (await q1("SELECT exige_identidad_validada AS v FROM tipo_tramite WHERE id_tipo_tramite = :t",
                       t=tipo["id_tipo_tramite"]))["v"]
    ag = await q1("SELECT a.id_agente FROM agentes a JOIN usuarios u ON u.id_usuario = a.id_usuario WHERE u.email = :e", e=ADMIN_EMAIL)
    await ejecutar("UPDATE tipo_tramite SET exige_identidad_validada = TRUE WHERE id_tipo_tramite = :t", t=tipo["id_tipo_tramite"])
    idt = None
    try:
        await ejecutar("DELETE FROM ciudadano_identidad_validacion WHERE id_ciudadano = :c", c=vid)
        cuerpo = {"id_tipo_tramite": tipo["id_tipo_tramite"], "asunto": "Smoke identidad", "datos": DATOS_PODA,
                  "iniciador": {"tipo": "ciudadano", "id_ciudadano": vid}}
        antes = (await q1("SELECT count(*) AS n FROM tramite"))["n"]
        corr = await q1("SELECT COALESCE(SUM(ultimo_numero),0) AS n FROM tipo_tramite_numerador WHERE id_tipo_tramite = :t", t=tipo["id_tipo_tramite"])
        r = await c.post("/api/v1/tramites", headers=ha, json=cuerpo)
        check(r.status_code == 422 and "Validá la identidad del vecino" in r.text, "sin validar: 422 con el mensaje", f"{r.status_code} {r.text[:200]}")
        check((await q1("SELECT count(*) AS n FROM tramite"))["n"] == antes, "no se creó ningún trámite")
        corr2 = await q1("SELECT COALESCE(SUM(ultimo_numero),0) AS n FROM tipo_tramite_numerador WHERE id_tipo_tramite = :t", t=tipo["id_tipo_tramite"])
        check(corr == corr2, "el numerador no avanzó", f"{corr} -> {corr2}")
        r = await c.post(f"/api/v1/buc/ciudadanos/{vid}/identidad/validar", headers=ha, json={"documento_presentado": "DNI"})
        check(r.status_code == 201, "el admin valida (201)", f"{r.status_code} {r.text[:200]}")
        r = await c.post("/api/v1/tramites", headers=ha, json=cuerpo)
        check(r.status_code == 201, "validada: el alta es 201", f"{r.status_code} {r.text[:200]}")
        if r.status_code == 201:
            idt = (await q1("SELECT id_tramite FROM tramite WHERE numero_expediente = :n", n=r.json()["numero_expediente"]))["id_tramite"]
    finally:
        if idt:
            await _borrar_tramite(idt)
        await ejecutar("DELETE FROM ciudadano_identidad_validacion WHERE id_ciudadano = :c", c=vid)
        await ejecutar("UPDATE tipo_tramite SET exige_identidad_validada = :v WHERE id_tipo_tramite = :t", v=previo, t=tipo["id_tipo_tramite"])


# ── Task 4: router público (tipos + alta atómica) ───────────────────────────

DNI_VECINO = "28547123"
PNG = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)


_HV: dict = {}


async def _login_vecino(c: httpx.AsyncClient) -> dict:
    """Un solo login por corrida (el login del vecino tiene rate limit de 6/min por DNI)."""
    if _HV:
        return _HV
    r = await c.post("/api/v1/publico/auth/login", json={"dni": DNI_VECINO, "password": PWD_DEV})
    assert r.status_code == 200, f"login vecino: {r.status_code} {r.text[:200]}"
    _HV.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return _HV


async def _doc_poda(tipo_id: int) -> dict:
    return await q1(
        "SELECT d.id_tipo_tramite_documento_requerido AS id, d.cantidad_max_archivos AS cant, d.tamano_max_mb AS mb "
        "FROM tipo_tramite_documento_requerido d JOIN tipo_tramite tt ON tt.id_version_publicada = d.id_tipo_tramite_version "
        "WHERE tt.id_tipo_tramite = :t AND d.activo AND d.obligatorio AND d.aporta_quien = 'iniciador' "
        "ORDER BY d.id_tipo_tramite_documento_requerido LIMIT 1", t=tipo_id)


async def _cuenta_filas() -> tuple:
    r = await q1("SELECT (SELECT count(*) FROM tramite) AS t, (SELECT count(*) FROM tramite_documento) AS d, "
                 "(SELECT count(*) FROM tramite_movimiento) AS m")
    return (r["t"], r["d"], r["m"])


def _form(tipo_id, datos, archivos, docs):
    import json as _j
    data = {"id_tipo_tramite": str(tipo_id), "datos": _j.dumps(datos), "documentos": _j.dumps(docs)}
    files = [("archivos", (n, b, "application/octet-stream")) for n, b in archivos]
    return data, files


async def test_tipos_ofrecidos(c: httpx.AsyncClient, ha: dict) -> None:
    print("[7] Tipos ofrecidos al vecino")
    mun = await _municipio_base()
    hv = await _login_vecino(c)
    r = await c.get("/api/v1/publico/tramites/tipos", headers=hv)
    check(r.status_code == 200, "GET /tipos 200", f"{r.status_code} {r.text[:200]}")
    if r.status_code != 200:
        return
    lista = r.json()
    ids = {t["id_tipo_tramite"] for t in lista}
    async with AsyncSessionLocal() as s:
        esperados = {x[0] for x in (await s.execute(text(
            "SELECT tt.id_tipo_tramite FROM tipo_tramite tt "
            "JOIN subarea sa ON sa.id_subarea = tt.id_subarea AND sa.activo "
            "WHERE tt.id_municipio = :m AND tt.activo AND tt.ofrecer_al_vecino AND tt.id_version_publicada IS NOT NULL "
            "AND 'ciudadano' = ANY (tt.iniciadores_permitidos) "
            "AND NOT EXISTS (SELECT 1 FROM tipo_tramite_campo f WHERE f.id_tipo_tramite_version = tt.id_version_publicada "
            "AND f.activo AND f.tipo_dato IN ('agente','subarea'))"), {"m": mun})).all()}
    check(ids == esperados and len(ids) >= 1, "la lista = los tipos que cumplen el criterio", f"{ids} vs {esperados}")
    demo = await q1("SELECT id_tipo_tramite FROM tipo_tramite WHERE codigo = 'permiso-demo-e2e' AND id_municipio = :m", m=mun)
    check(not demo or demo["id_tipo_tramite"] not in ids, "permiso-demo-e2e no está")
    check(all({"id_tipo_tramite", "nombre", "descripcion", "exige_identidad_validada", "puede_iniciar", "motivo_no_puede"} <= set(t) for t in lista),
          "forma de cada tipo")
    no_ofr = await q1("SELECT id_tipo_tramite FROM tipo_tramite WHERE id_municipio = :m AND NOT ofrecer_al_vecino AND activo LIMIT 1", m=mun)
    if no_ofr:
        r = await c.get(f"/api/v1/publico/tramites/tipos/{no_ofr['id_tipo_tramite']}", headers=hv)
        check(r.status_code == 404, "un tipo no ofrecido: 404 en el detalle", f"{r.status_code}")
    tipo = await _tipo_poda(mun)
    r = await c.get(f"/api/v1/publico/tramites/tipos/{tipo['id_tipo_tramite']}", headers=hv)
    check(r.status_code == 200, "detalle de poda-arbol 200", f"{r.status_code} {r.text[:200]}")
    if r.status_code == 200:
        d = r.json()
        check({c_["nombre_interno"] for c_ in d["campos"]} >= {"direccion_arbol", "motivo"}, "trae los campos")
        check(len(d["documentos"]) >= 1 and "id_documento_requerido" in d["documentos"][0]
              and "formatos_permitidos" in d["documentos"][0], "trae los documentos del alta")
    r = await c.get("/api/v1/publico/tramites/tipos")
    check(r.status_code == 401, "sin token: 401", f"{r.status_code}")
    r = await c.get("/api/v1/publico/tramites/tipos", headers=ha)
    check(r.status_code == 401, "token de funcionario: 401", f"{r.status_code}")


async def test_alta_vecino_ok(c: httpx.AsyncClient, ha: dict) -> None:
    print("[8] Alta del vecino: 201 con todo creado")
    mun = await _municipio_base()
    tipo = await _tipo_poda(mun)
    doc = await _doc_poda(tipo["id_tipo_tramite"])
    hv = await _login_vecino(c)
    SUBIDOS.clear(); BORRADOS.clear(); MAILS.clear()
    data, files = _form(tipo["id_tipo_tramite"], DATOS_PODA, [("arbol.png", PNG)], [doc["id"]])
    r = await c.post("/api/v1/publico/tramites", headers=hv, data=data, files=files)
    check(r.status_code == 201, "responde 201", f"{r.status_code} {r.text[:300]}")
    if r.status_code != 201:
        return
    numero = r.json()["numero_expediente"]
    t = await q1("SELECT t.id_tramite, t.id_agente_iniciador, t.id_ciudadano_iniciador, t.id_subarea_actual, t.id_usuario_alta, "
                 "tt.id_subarea FROM tramite t JOIN tipo_tramite_version v ON v.id_tipo_tramite_version = t.id_tipo_tramite_version "
                 "JOIN tipo_tramite tt ON tt.id_tipo_tramite = v.id_tipo_tramite WHERE t.numero_expediente = :n", n=numero)
    try:
        check(r.json()["id_tramite"] == t["id_tramite"], "id_tramite de la respuesta")
        check(t["id_agente_iniciador"] is None and t["id_ciudadano_iniciador"] == ID_CIUDADANO, "iniciador = el del token, sin agente", str(t))
        check(t["id_subarea_actual"] == t["id_subarea"] and t["id_usuario_alta"] is None, "destinatario = gestión del tipo, sin usuario alta", str(t))
        async with AsyncSessionLocal() as s:
            movs = (await s.execute(text("SELECT tipo, id_agente, id_ciudadano_actor FROM tramite_movimiento "
                                         "WHERE id_tramite = :t ORDER BY orden_secuencial"), {"t": t["id_tramite"]})).mappings().all()
            docs = (await s.execute(text("SELECT id_ciudadano_subio, id_agente_subio, id_tipo_tramite_documento_requerido AS r, storage_path "
                                         "FROM tramite_documento WHERE id_tramite = :t"), {"t": t["id_tramite"]})).mappings().all()
        tipos = [m["tipo"] for m in movs]
        check(tipos[:2] == ["creacion", "numeracion"] and "adjunto" in tipos, "movimientos creacion, numeracion y adjunto", str(tipos))
        check(all(m["id_ciudadano_actor"] == ID_CIUDADANO and m["id_agente"] is None for m in movs), "todos con id_ciudadano_actor", str([dict(m) for m in movs]))
        check(len(docs) == 1 and docs[0]["id_ciudadano_subio"] == ID_CIUDADANO and docs[0]["id_agente_subio"] is None
              and docs[0]["r"] == doc["id"], "un tramite_documento del vecino", str([dict(d) for d in docs]))
        check(len(SUBIDOS) == 1 and SUBIDOS[0] == docs[0]["storage_path"] and not BORRADOS, "un objeto subido y ninguno borrado", f"{SUBIDOS} {BORRADOS}")
        v = [m for m in MAILS if m["to"] == "roberto.fernandez@correo.gob.ar"]
        check(len(v) == 1 and numero in v[0]["subject"] + v[0]["html"], "un mail al vecino con el número", str(MAILS)[:200])
    finally:
        await ejecutar("DELETE FROM tramite_documento WHERE id_tramite = :t", t=t["id_tramite"])
        await _borrar_tramite(t["id_tramite"])


async def test_alta_sin_documento_obligatorio_422(c: httpx.AsyncClient, ha: dict) -> None:
    print("[9] Alta sin el documento obligatorio: 422 y nada creado")
    mun = await _municipio_base()
    tipo = await _tipo_poda(mun)
    hv = await _login_vecino(c)
    antes = await _cuenta_filas()
    corr = await q1("SELECT COALESCE(SUM(ultimo_numero),0) AS n FROM tipo_tramite_numerador WHERE id_tipo_tramite = :t", t=tipo["id_tipo_tramite"])
    SUBIDOS.clear()
    data, files = _form(tipo["id_tipo_tramite"], DATOS_PODA, [], [])
    r = await c.post("/api/v1/publico/tramites", headers=hv, data=data, files=files or None)
    check(r.status_code == 422, "responde 422", f"{r.status_code} {r.text[:200]}")
    check(await _cuenta_filas() == antes and not SUBIDOS, "sin filas nuevas ni subidas")
    corr2 = await q1("SELECT COALESCE(SUM(ultimo_numero),0) AS n FROM tipo_tramite_numerador WHERE id_tipo_tramite = :t", t=tipo["id_tipo_tramite"])
    check(corr == corr2, "el numerador no avanzó", f"{corr} -> {corr2}")


async def test_alta_atomica_sin_restos(c: httpx.AsyncClient, ha: dict) -> None:
    print("[10] Atomicidad: dos archivos, el segundo excede el tamaño")
    mun = await _municipio_base()
    tipo = await _tipo_poda(mun)
    doc = await _doc_poda(tipo["id_tipo_tramite"])
    hv = await _login_vecino(c)
    await ejecutar("UPDATE tipo_tramite_documento_requerido SET cantidad_max_archivos = 2 WHERE id_tipo_tramite_documento_requerido = :d", d=doc["id"])
    try:
        antes = await _cuenta_filas()
        SUBIDOS.clear(); BORRADOS.clear()
        grande = b"\x00" * ((doc["mb"] * 1024 * 1024) + 1024)
        data, files = _form(tipo["id_tipo_tramite"], DATOS_PODA, [("a.png", PNG), ("b.png", grande)], [doc["id"], doc["id"]])
        r = await c.post("/api/v1/publico/tramites", headers=hv, data=data, files=files)
        check(r.status_code == 422, "responde 422", f"{r.status_code} {r.text[:200]}")
        check(await _cuenta_filas() == antes, "ninguna fila nueva en tramite/tramite_documento/movimiento")
        check(not SUBIDOS, "no se subió nada (rechazado por tamaño declarado antes de leer)", f"{SUBIDOS} {BORRADOS}")

        # Falla DESPUÉS de subir: la segunda subida levanta; el primer objeto se borra y no queda nada.
        SUBIDOS.clear(); BORRADOS.clear(); FALLAR_EN_SUBIDA_N[:] = [2]
        data, files = _form(tipo["id_tipo_tramite"], DATOS_PODA, [("a.png", PNG), ("b.png", PNG)], [doc["id"], doc["id"]])
        r = await c.post("/api/v1/publico/tramites", headers=hv, data=data, files=files)
        check(r.status_code >= 400, "la falla de Storage no deja 201", f"{r.status_code}")
        check(len(SUBIDOS) == 2 and set(SUBIDOS) <= set(BORRADOS), "lo subido antes de la falla se borró", f"{SUBIDOS} {BORRADOS}")
        check(await _cuenta_filas() == antes, "sin filas nuevas tras la falla")
    finally:
        FALLAR_EN_SUBIDA_N.clear()
        await ejecutar("UPDATE tipo_tramite_documento_requerido SET cantidad_max_archivos = :c WHERE id_tipo_tramite_documento_requerido = :d",
                       c=doc["cant"], d=doc["id"])


async def test_alta_campo_invalido_422(c: httpx.AsyncClient, ha: dict) -> None:
    print("[11] Campo de selección con un valor fuera de las opciones")
    mun = await _municipio_base()
    tipo = await _tipo_poda(mun)
    doc = await _doc_poda(tipo["id_tipo_tramite"])
    hv = await _login_vecino(c)
    antes = await _cuenta_filas()
    datos = dict(DATOS_PODA, especie_aproximada="valor_inexistente")
    data, files = _form(tipo["id_tipo_tramite"], datos, [("a.png", PNG)], [doc["id"]])
    r = await c.post("/api/v1/publico/tramites", headers=hv, data=data, files=files)
    check(r.status_code in (400, 422), "rechazado", f"{r.status_code} {r.text[:200]}")
    check(r.status_code == 422, "responde 422 (no 400)", f"{r.status_code}")
    check(await _cuenta_filas() == antes, "sin filas nuevas")


async def test_alta_exige_identidad_portal(c: httpx.AsyncClient, ha: dict) -> None:
    print("[12] Tipo que exige identidad validada y vecino sin validar")
    mun = await _municipio_base()
    tipo = await _tipo_poda(mun)
    doc = await _doc_poda(tipo["id_tipo_tramite"])
    hv = await _login_vecino(c)
    previo = (await q1("SELECT exige_identidad_validada AS v FROM tipo_tramite WHERE id_tipo_tramite = :t", t=tipo["id_tipo_tramite"]))["v"]
    activas = await q1("SELECT count(*) AS n FROM ciudadano_identidad_validacion WHERE id_ciudadano = :c AND activo", c=ID_CIUDADANO)
    if activas["n"]:
        check(False, "el vecino de prueba tiene una validación activa: el caso no se puede armar")
        return
    await ejecutar("UPDATE tipo_tramite SET exige_identidad_validada = TRUE WHERE id_tipo_tramite = :t", t=tipo["id_tipo_tramite"])
    try:
        r = await c.get("/api/v1/publico/tramites/tipos", headers=hv)
        t = next((x for x in r.json() if x["id_tipo_tramite"] == tipo["id_tipo_tramite"]), None) if r.status_code == 200 else None
        check(bool(t) and t["puede_iniciar"] is False and t["motivo_no_puede"] == MSG_IDENTIDAD_PORTAL
              and t["exige_identidad_validada"] is True, "se lista con puede_iniciar=false y el motivo", str(t))
        antes = await _cuenta_filas()
        data, files = _form(tipo["id_tipo_tramite"], DATOS_PODA, [("a.png", PNG)], [doc["id"]])
        r = await c.post("/api/v1/publico/tramites", headers=hv, data=data, files=files)
        check(r.status_code == 422 and MSG_IDENTIDAD_PORTAL in r.text, "el alta: 422 con el texto", f"{r.status_code} {r.text[:200]}")
        check(await _cuenta_filas() == antes, "sin filas nuevas")
    finally:
        await ejecutar("UPDATE tipo_tramite SET exige_identidad_validada = :v WHERE id_tipo_tramite = :t", v=previo, t=tipo["id_tipo_tramite"])


async def test_alta_limites_de_carga(c: httpx.AsyncClient, ha: dict) -> None:
    print("[13] Límites: cantidad por documento, total de archivos y tope del body")
    mun = await _municipio_base()
    tipo = await _tipo_poda(mun)
    doc = await _doc_poda(tipo["id_tipo_tramite"])
    hv = await _login_vecino(c)
    antes = await _cuenta_filas()
    SUBIDOS.clear()
    data, files = _form(tipo["id_tipo_tramite"], DATOS_PODA, [("a.png", PNG), ("b.png", PNG)], [doc["id"], doc["id"]])
    r = await c.post("/api/v1/publico/tramites", headers=hv, data=data, files=files)
    check(r.status_code == 422 and "admite hasta" in r.text, "más archivos que cantidad_max_archivos: 422", f"{r.status_code} {r.text[:150]}")
    n = 25
    data, files = _form(tipo["id_tipo_tramite"], DATOS_PODA, [(f"{i}.png", PNG) for i in range(n)], [doc["id"]] * n)
    r = await c.post("/api/v1/publico/tramites", headers=hv, data=data, files=files)
    check(r.status_code == 422 and "hasta 20 archivos" in r.text, "más de 20 archivos en total: 422", f"{r.status_code} {r.text[:150]}")
    grande = bytes(26 * 1024 * 1024)
    data, files = _form(tipo["id_tipo_tramite"], DATOS_PODA, [("g.png", grande)], [doc["id"]])
    r = await c.post("/api/v1/publico/tramites", headers=hv, data=data, files=files)
    check(r.status_code == 413, "body sobre el tope: 413", f"{r.status_code} {r.text[:150]}")
    check(not SUBIDOS and await _cuenta_filas() == antes, "nada subido ni filas nuevas")


async def test_alta_filtra_datos_ajenos(c: httpx.AsyncClient, ha: dict) -> None:
    print("[14] Claves ajenas de `datos` no llegan a la base")
    mun = await _municipio_base()
    tipo = await _tipo_poda(mun)
    doc = await _doc_poda(tipo["id_tipo_tramite"])
    hv = await _login_vecino(c)
    datos = dict(DATOS_PODA, clave_ajena="X" * 50, archivo_falso="y")
    ver = (await q1("SELECT id_version_publicada AS v FROM tipo_tramite WHERE id_tipo_tramite = :t", t=tipo["id_tipo_tramite"]))["v"]
    # Campo dado de baja: su clave tampoco se guarda. (Un campo `archivo` activo ya no sirve para esto:
    # desde el 2026-11-22 un tipo con un campo que el portal no sabe pedir no se ofrece.)
    await ejecutar("INSERT INTO tipo_tramite_campo (id_tipo_tramite_version, nombre_interno, etiqueta, tipo_dato, obligatorio, orden, id_municipio, activo) "
                   "VALUES (:v, 'archivo_falso', 'Archivo falso', 'texto', FALSE, 99, :m, FALSE)", v=ver, m=mun)
    idt = None
    try:
        data, files = _form(tipo["id_tipo_tramite"], datos, [("a.png", PNG)], [doc["id"]])
        r = await c.post("/api/v1/publico/tramites", headers=hv, data=data, files=files)
        check(r.status_code == 201, "responde 201", f"{r.status_code} {r.text[:200]}")
        if r.status_code != 201:
            return
        idt = r.json()["id_tramite"]
        t = await q1("SELECT datos_jsonb FROM tramite WHERE id_tramite = :t", t=idt)
        m = await q1("SELECT metadata_jsonb FROM tramite_movimiento WHERE id_tramite = :t AND tipo = 'creacion'", t=idt)
        check(set(t["datos_jsonb"]) == set(DATOS_PODA), "datos_jsonb solo con campos activos del tipo", str(t))
        check(set(m["metadata_jsonb"]["datos_iniciales"]) == set(DATOS_PODA), "el movimiento creacion tampoco las guarda", str(m))
    finally:
        await ejecutar("DELETE FROM tipo_tramite_campo WHERE id_tipo_tramite_version = :v AND nombre_interno = 'archivo_falso'", v=ver)
        if idt:
            await ejecutar("DELETE FROM tramite_documento WHERE id_tramite = :t", t=idt)
            await _borrar_tramite(idt)


# ── Task 5: mis trámites, detalle, documentos del paso, resumen ─────────────

BASE_PUB = "/api/v1/publico/tramites"
CONTENIDO_FALSO = b"BINARIO-SMOKE"


async def _descargar_falso(path):
    return CONTENIDO_FALSO


async def _tramite_ventanilla(c: httpx.AsyncClient, ha: dict, vid: int, asunto: str) -> tuple[int, str]:
    """Un trámite de poda creado por el admin para el vecino `vid` (ventanilla)."""
    mun = await _municipio_base()
    tipo = await _tipo_poda(mun)
    r = await c.post("/api/v1/tramites", headers=ha, json={
        "id_tipo_tramite": tipo["id_tipo_tramite"], "asunto": asunto, "datos": DATOS_PODA,
        "iniciador": {"tipo": "ciudadano", "id_ciudadano": vid}})
    assert r.status_code == 201, f"alta ventanilla: {r.status_code} {r.text[:200]}"
    numero = r.json()["numero_expediente"]
    idt = (await q1("SELECT id_tramite FROM tramite WHERE numero_expediente = :n", n=numero))["id_tramite"]
    return idt, numero


async def _limpiar_tramite_completo(idt: int) -> None:
    await ejecutar("DELETE FROM notificacion WHERE recurso_tipo = 'tramite' AND recurso_id = :t", t=idt)
    await ejecutar("DELETE FROM tramite_pedido_iniciador WHERE id_tramite = :t", t=idt)
    await ejecutar("DELETE FROM tramite_documento WHERE id_tramite = :t", t=idt)
    await _borrar_tramite(idt)


async def _otro_vecino_con_cuenta(mun: int) -> Optional[int]:
    r = await q1(
        "SELECT c.id_ciudadano FROM ciudadanos c WHERE c.activo AND c.id_municipio = :m AND c.id_ciudadano <> :yo "
        "AND EXISTS (SELECT 1 FROM ciudadano_credencial cc WHERE cc.id_ciudadano = c.id_ciudadano AND cc.activo) "
        "ORDER BY c.id_ciudadano LIMIT 1", m=mun, yo=ID_CIUDADANO)
    return r["id_ciudadano"] if r else None


async def test_mis_tramites_incluye_ventanilla(c: httpx.AsyncClient, ha: dict) -> None:
    print("[15] Mis trámites: el de ventanilla y el de la app aparecen, del más nuevo al más viejo")
    mun = await _municipio_base()
    tipo = await _tipo_poda(mun)
    doc = await _doc_poda(tipo["id_tipo_tramite"])
    hv = await _login_vecino(c)
    otro = await _otro_vecino_con_cuenta(mun)
    if not otro:
        check(False, "datos de partida (otro vecino con cuenta)")
        return
    idv, num_v = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke ventanilla")
    ido, num_o = await _tramite_ventanilla(c, ha, otro, "Smoke de otro vecino")
    data, files = _form(tipo["id_tipo_tramite"], DATOS_PODA, [("a.png", PNG)], [doc["id"]])
    r = await c.post(BASE_PUB, headers=hv, data=data, files=files)
    idn = r.json()["id_tramite"] if r.status_code == 201 else None
    num_n = r.json().get("numero_expediente") if r.status_code == 201 else None
    try:
        check(idn is not None, "alta de la app 201", f"{r.status_code} {r.text[:200]}")
        r = await c.get(BASE_PUB, headers=hv)
        check(r.status_code == 200, "GET /publico/tramites 200", f"{r.status_code} {r.text[:200]}")
        lista = r.json() if r.status_code == 200 else []
        nums = [t["numero_expediente"] for t in lista]
        check(num_v in nums and num_n in nums, "aparecen el de ventanilla y el de la app", str(nums[:6]))
        check(num_o not in nums, "el de otro vecino no aparece")
        check(nums.index(num_n) < nums.index(num_v) if num_v in nums and num_n in nums else False,
              "orden: el más nuevo primero")
        t = next((x for x in lista if x["numero_expediente"] == num_n), {})
        claves = {"id_tramite", "numero_expediente", "tipo_nombre", "estado_etiqueta", "estado_color", "resultado",
                  "fecha_alta", "tiene_pedido_abierto", "documentos_pendientes"}
        check(set(t) == claves, "forma de cada fila", str(sorted(t)))
        check(t.get("estado_etiqueta") == "Iniciado" and t.get("resultado") == "pendiente"
              and t.get("tiene_pedido_abierto") is False and t.get("documentos_pendientes") == 0,
              "valores del trámite recién iniciado", str(t))
        r = await c.get(BASE_PUB)
        check(r.status_code == 401, "sin token: 401", f"{r.status_code}")
        r = await c.get(BASE_PUB, headers=ha)
        check(r.status_code == 401, "token de funcionario: 401", f"{r.status_code}")
    finally:
        for i in (idv, ido, idn):
            if i:
                await _limpiar_tramite_completo(i)


async def test_detalle_sin_datos_internos(c: httpx.AsyncClient, ha: dict) -> None:
    print("[16] Detalle: sin comentarios internos ni nombres de agentes")
    mun = await _municipio_base()
    hv = await _login_vecino(c)
    idt, numero = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke detalle")
    ag = await q1("SELECT a.nombre, a.apellido FROM agentes a JOIN usuarios u ON u.id_usuario = a.id_usuario "
                  "WHERE u.email = :e", e=ADMIN_EMAIL)
    otra = await q1("SELECT id_subarea FROM subarea WHERE activo AND id_municipio = :m AND id_subarea <> "
                    "(SELECT id_subarea_actual FROM tramite WHERE id_tramite = :t) ORDER BY id_subarea LIMIT 1", m=mun, t=idt)
    try:
        secreto = "COMENTARIO-INTERNO-QX7"
        r = await c.post(f"/api/v1/tramites/{numero}/comentar", headers=ha, json={"comentario": secreto})
        check(r.status_code == 201, "el admin comenta", f"{r.status_code} {r.text[:200]}")
        r = await c.post(f"/api/v1/tramites/{numero}/pase", headers=ha,
                         json={"destinatario_tipo": "subarea", "destinatario_id": otra["id_subarea"], "comentario": secreto})
        check(r.status_code == 200, "el admin hace un pase", f"{r.status_code} {r.text[:200]}")
        r = await c.get(f"{BASE_PUB}/{idt}", headers=hv)
        check(r.status_code == 200, "GET detalle 200", f"{r.status_code} {r.text[:200]}")
        if r.status_code != 200:
            return
        d = r.json()
        crudo = r.text
        check(secreto not in crudo, "el texto del comentario no aparece en ningún lado")
        check(ag["nombre"] not in crudo and ag["apellido"] not in crudo, "el nombre del agente no aparece", f"{ag}")
        textos = [h["texto"] for h in d["historial"]]
        check(textos[:1] == ["Iniciaste el trámite."], "el historial trae la creación", str(textos))
        check(all(set(h) == {"fecha", "texto"} for h in d["historial"]), "cada fila: fecha y texto")
        check(len(textos) == 1, "ni comentario ni pase ni numeración en el historial", str(textos))
        check({"etiqueta": "Dirección del árbol", "valor": DATOS_PODA["direccion_arbol"]} in d["datos"]
              or any(x["valor"] == DATOS_PODA["direccion_arbol"] for x in d["datos"]),
              "datos con etiqueta y valor", str(d["datos"]))
        check(all(set(x) == {"etiqueta", "valor"} for x in d["datos"]), "forma de datos")
        check(d["pedido_abierto"] is None and d["documentos"] == [], "sin pedido ni documentos propios")
        check({"documentos_del_paso", "historial", "datos", "documentos", "pedido_abierto"} <= set(d), "claves del detalle")
    finally:
        await _limpiar_tramite_completo(idt)


async def test_ajeno_404(c: httpx.AsyncClient, ha: dict) -> None:
    print("[17] Lo ajeno es 404 con el mismo cuerpo que un id inexistente")
    mun = await _municipio_base()
    hv = await _login_vecino(c)
    otro = await _otro_vecino_con_cuenta(mun)
    if not otro:
        check(False, "datos de partida (otro vecino con cuenta)")
        return
    ido, _ = await _tramite_ventanilla(c, ha, otro, "Smoke ajeno")
    mio, _ = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke propio con doc de personal")
    ver = await q1("SELECT id_tipo_tramite_version AS v FROM tramite WHERE id_tramite = :t", t=ido)
    doc_ajeno = await ejecutar(
        "INSERT INTO tramite_documento (id_tramite, nombre, nombre_archivo_original, storage_path, mime_type, tamano_bytes, "
        "hash_sha256, posicion_orden, id_agente_subio, id_ciudadano_subio, id_municipio) "
        "VALUES (:t, 'x.pdf', 'x.pdf', 'smoke/x.pdf', 'application/pdf', 3, 'h', 1, NULL, :c, :m) RETURNING id_tramite_documento",
        t=ido, c=otro, m=mun)
    doc_personal = await ejecutar(
        "INSERT INTO tramite_documento (id_tramite, nombre, nombre_archivo_original, storage_path, mime_type, tamano_bytes, "
        "hash_sha256, posicion_orden, id_agente_subio, id_ciudadano_subio, id_municipio) "
        "VALUES (:t, 'p.pdf', 'p.pdf', 'smoke/p.pdf', 'application/pdf', 3, 'h', 1, NULL, NULL, :m) RETURNING id_tramite_documento",
        t=mio, m=mun)
    try:
        inexistente = 2_000_000_000
        r0 = await c.get(f"{BASE_PUB}/{inexistente}", headers=hv)
        check(r0.status_code == 404, "id inexistente: 404", f"{r0.status_code}")
        r = await c.get(f"{BASE_PUB}/{ido}", headers=hv)
        check(r.status_code == 404 and r.text == r0.text, "detalle ajeno: 404 idéntico", f"{r.status_code} {r.text}")
        r0 = await c.get(f"{BASE_PUB}/{inexistente}/documentos/1/contenido", headers=hv)
        r = await c.get(f"{BASE_PUB}/{ido}/documentos/{doc_ajeno['id_tramite_documento']}/contenido", headers=hv)
        check(r.status_code == 404 and r.text == r0.text, "contenido de un trámite ajeno: 404 idéntico", f"{r.status_code} {r.text}")
        r = await c.get(f"{BASE_PUB}/{mio}/documentos/{doc_ajeno['id_tramite_documento']}/contenido", headers=hv)
        check(r.status_code == 404, "doc ajeno colgado de mi trámite: 404", f"{r.status_code}")
        r = await c.get(f"{BASE_PUB}/{mio}/documentos/{doc_personal['id_tramite_documento']}/contenido", headers=hv)
        check(r.status_code == 404, "doc subido por el personal: 404", f"{r.status_code}")
        r0 = await c.post(f"{BASE_PUB}/{inexistente}/documentos", headers=hv, data={"documentos": "[1]"},
                          files=[("archivos", ("a.png", PNG, "image/png"))])
        r = await c.post(f"{BASE_PUB}/{ido}/documentos", headers=hv, data={"documentos": "[1]"},
                         files=[("archivos", ("a.png", PNG, "image/png"))])
        check(r0.status_code == 404 and r.status_code == 404 and r.text == r0.text,
              "subir a un trámite ajeno: 404 idéntico", f"{r.status_code} {r.text}")
        r = await c.get(f"{BASE_PUB}/{mio}", headers=hv)
        check(r.status_code == 200 and r.json()["documentos"] == [], "mi detalle no lista el doc del personal", r.text[:200])
        check(ver is not None, "fixture")
    finally:
        for i in (ido, mio):
            await _limpiar_tramite_completo(i)


async def test_documento_del_paso(c: httpx.AsyncClient, ha: dict) -> None:
    print("[18] Documentos del paso: listar, subir, descargar y notificar")
    from app.services.tramites import documentos as svc_docs_mod
    mun = await _municipio_base()
    tipo = await _tipo_poda(mun)
    doc = await _doc_poda(tipo["id_tipo_tramite"])
    hv = await _login_vecino(c)
    ver = (await q1("SELECT id_version_publicada AS v FROM tipo_tramite WHERE id_tipo_tramite = :t", t=tipo["id_tipo_tramite"]))["v"]
    est_ini = (await q1("SELECT id_tipo_tramite_estado AS e FROM tipo_tramite_estado WHERE id_tipo_tramite_version = :v AND es_inicial", v=ver))["e"]
    est_otro = (await q1("SELECT id_tipo_tramite_estado AS e FROM tipo_tramite_estado WHERE id_tipo_tramite_version = :v AND NOT es_inicial "
                         "ORDER BY orden LIMIT 1", v=ver))["e"]
    sql_req = ("INSERT INTO tipo_tramite_documento_requerido (id_tipo_tramite_version, id_tipo_tramite_estado, nombre, obligatorio, "
               "formatos_permitidos, tamano_max_mb, requiere_firma, aporta_quien, orden, id_municipio, cantidad_max_archivos) "
               "VALUES (:v, :e, :n, TRUE, ARRAY['png'], 5, FALSE, 'iniciador', 9, :m, 2) RETURNING id_tipo_tramite_documento_requerido AS id")
    data, files = _form(tipo["id_tipo_tramite"], DATOS_PODA, [("a.png", PNG)], [doc["id"]])
    r = await c.post(BASE_PUB, headers=hv, data=data, files=files)
    if r.status_code != 201:
        check(False, "alta previa", f"{r.status_code} {r.text[:200]}")
        return
    idt = r.json()["id_tramite"]
    # Los requisitos extra se crean DESPUÉS del alta (un obligatorio nuevo exigiría el documento al iniciar).
    req_ok = await ejecutar(sql_req, v=ver, e=est_ini, n="Documento extra smoke", m=mun)
    req_otro = await ejecutar(sql_req, v=ver, e=est_otro, n="Documento de otro estado smoke", m=mun)
    original = svc_docs_mod.descargar_bytes
    svc_docs_mod.descargar_bytes = _descargar_falso
    try:
        r = await c.get(f"{BASE_PUB}/{idt}", headers=hv)
        d = r.json()
        paso = {p["id_documento_requerido"]: p for p in d["documentos_del_paso"]}
        check(req_ok["id"] in paso and req_otro["id"] not in paso, "aparece el del estado actual, no el de otro estado",
              str(sorted(paso)))
        check(paso.get(req_ok["id"], {}).get("subidos") == 0 and paso.get(req_ok["id"], {}).get("formatos_permitidos") == ["png"],
              "forma del documento del paso con subidos=0", str(paso.get(req_ok["id"])))
        check(len(d["documentos"]) == 1 and d["documentos"][0]["binario_purgado"] is False, "mis documentos: el del alta", str(d["documentos"]))
        lista = (await c.get(BASE_PUB, headers=hv)).json()
        fila = next(x for x in lista if x["id_tramite"] == idt)
        check(fila["documentos_pendientes"] == 1, "documentos_pendientes = 1 (falta el extra obligatorio)", str(fila))

        # estado equivocado, extensión y cantidad
        mal = lambda ids, arch: c.post(f"{BASE_PUB}/{idt}/documentos", headers=hv, data={"documentos": json_dumps(ids)}, files=arch)
        r = await mal([req_otro["id"]], [("archivos", ("a.png", PNG, "image/png"))])
        check(r.status_code == 422, "documento de otro estado: 422", f"{r.status_code} {r.text[:150]}")
        r = await mal([req_ok["id"]], [("archivos", ("a.exe", PNG, "application/octet-stream"))])
        check(r.status_code == 422, "formato no aceptado: 422", f"{r.status_code} {r.text[:150]}")
        r = await mal([req_ok["id"]] * 3, [("archivos", (f"{i}.png", PNG, "image/png")) for i in range(3)])
        check(r.status_code == 422 and "admite hasta" in r.text, "más que la cantidad máxima: 422", f"{r.status_code} {r.text[:150]}")
        r = await c.post(f"{BASE_PUB}/{idt}/documentos", headers=hv, data={"documentos": "[]"})
        check(r.status_code == 422, "sin archivos: 422", f"{r.status_code}")

        # subida válida
        SUBIDOS.clear(); MAILS.clear()
        movs_antes = (await q1("SELECT count(*) AS n FROM tramite_movimiento WHERE id_tramite = :t AND tipo = 'adjunto'", t=idt))["n"]
        r = await mal([req_ok["id"]], [("archivos", ("extra.png", PNG, "image/png"))])
        check(r.status_code == 201 and r.json() == {"subidos": 1}, "subir el del paso: 201 {subidos: 1}", f"{r.status_code} {r.text[:200]}")
        check(len(SUBIDOS) == 1, "un objeto subido a Storage", str(SUBIDOS))
        filas = await ejecutar("SELECT id_tramite_documento AS id FROM tramite_documento WHERE id_tramite = :t "
                               "AND id_tipo_tramite_documento_requerido = :r AND id_ciudadano_subio = :c",
                               t=idt, r=req_ok["id"], c=ID_CIUDADANO)
        check(filas is not None, "tramite_documento del vecino creado")
        movs = (await q1("SELECT count(*) AS n FROM tramite_movimiento WHERE id_tramite = :t AND tipo = 'adjunto' "
                         "AND id_ciudadano_actor = :c", t=idt, c=ID_CIUDADANO))["n"]
        check(movs == movs_antes + 1, "movimiento adjunto con id_ciudadano_actor", f"{movs_antes} -> {movs}")
        dest = await q1("SELECT id_subarea_actual AS s FROM tramite WHERE id_tramite = :t", t=idt)
        usuarios = (await q1("SELECT count(*) AS n FROM agentes a JOIN usuarios u ON u.id_usuario = a.id_usuario AND u.activo "
                             "WHERE a.id_subarea = :s AND a.activo AND u.email IS NOT NULL AND u.email <> ''", s=dest["s"]))["n"]
        notifs = (await q1("SELECT count(*) AS n FROM notificacion WHERE recurso_tipo = 'tramite' AND recurso_id = :t "
                           "AND tipo = 'tramite_documento_vecino'", t=idt))["n"]
        check(notifs == usuarios, "notificación al colectivo destinatario (una por usuario)", f"{notifs} vs {usuarios}")
        d = (await c.get(f"{BASE_PUB}/{idt}", headers=hv)).json()
        check(len(d["documentos"]) == 2, "el detalle ahora lista 2 documentos", str(len(d["documentos"])))
        propio = next(x for x in d["documentos"] if x["nombre"] == "Documento extra smoke")
        paso = {p["id_documento_requerido"]: p for p in d["documentos_del_paso"]}
        check(paso[req_ok["id"]]["subidos"] == 1, "subidos = 1 en el paso", str(paso[req_ok["id"]]))
        fila = next(x for x in (await c.get(BASE_PUB, headers=hv)).json() if x["id_tramite"] == idt)
        check(fila["documentos_pendientes"] == 0, "documentos_pendientes vuelve a 0", str(fila))
        check(any(h["texto"].startswith("Subiste el documento") for h in d["historial"]), "el historial muestra lo que subió",
              str([h["texto"] for h in d["historial"]]))

        # descarga y purga
        r = await c.get(f"{BASE_PUB}/{idt}/documentos/{propio['id_tramite_documento']}/contenido", headers=hv)
        check(r.status_code == 200 and r.content == CONTENIDO_FALSO and r.headers["content-type"].startswith("image/png"),
              "descarga del propio: 200 con el binario", f"{r.status_code} {r.headers.get('content-type')}")
        await ejecutar("UPDATE tramite_documento SET binario_purgado = TRUE WHERE id_tramite_documento = :d", d=propio["id_tramite_documento"])
        r = await c.get(f"{BASE_PUB}/{idt}/documentos/{propio['id_tramite_documento']}/contenido", headers=hv)
        check(r.status_code == 410, "binario purgado: 410", f"{r.status_code}")
    finally:
        svc_docs_mod.descargar_bytes = original
        await _limpiar_tramite_completo(idt)
        await ejecutar("DELETE FROM tipo_tramite_documento_requerido WHERE id_tipo_tramite_documento_requerido = ANY(:i)",
                       i=[req_ok["id"], req_otro["id"]])


def json_dumps(x) -> str:
    import json as _j
    return _j.dumps(x)


async def test_resumen_tramites(c: httpx.AsyncClient, ha: dict) -> None:
    print("[19] mi-resumen suma los trámites")
    hv = await _login_vecino(c)
    idt, _ = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke resumen")
    try:
        r = await c.get("/api/v1/publico/portal/mi-resumen", headers=hv)
        check(r.status_code == 200, "mi-resumen 200", f"{r.status_code} {r.text[:200]}")
        if r.status_code != 200:
            return
        j = r.json()
        total = (await q1("SELECT count(*) AS n FROM tramite WHERE id_ciudadano_iniciador = :c AND activo", c=ID_CIUDADANO))["n"]
        vig = (await q1("SELECT count(*) AS n FROM tramite t JOIN tipo_tramite_estado e ON e.id_tipo_tramite_estado = t.id_tipo_tramite_estado_actual "
                        "WHERE t.id_ciudadano_iniciador = :c AND t.activo AND t.fecha_archivado IS NULL AND NOT e.es_final", c=ID_CIUDADANO))["n"]
        check(j["tramites"]["total"] == total and j["tramites"]["vigentes"] == vig and total >= 1,
              "tramites.total y vigentes = lo de la base", f"{j['tramites']} vs {total}/{vig}")
        check(j["tramites"]["pedidos_abiertos"] == 0, "pedidos_abiertos = 0", str(j["tramites"]))
        check({"reclamos", "turnos", "entradas", "avisos", "ciudadano"} <= set(j), "las claves de siempre siguen")
    finally:
        await _limpiar_tramite_completo(idt)


async def test_estado_oculto_para_iniciador(c: httpx.AsyncClient, ha: dict) -> None:
    print("[20] Estado oculto_para_iniciador: no se expone")
    mun = await _municipio_base()
    hv = await _login_vecino(c)
    idt, numero = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke estado oculto")
    t = await q1("SELECT id_tipo_tramite_version AS v, id_tipo_tramite_estado_actual AS e FROM tramite WHERE id_tramite = :t", t=idt)
    ini = await q1("SELECT etiqueta, color FROM tipo_tramite_estado WHERE id_tipo_tramite_estado = :e", e=t["e"])
    oc = await q1("SELECT id_tipo_tramite_estado AS e, etiqueta, codigo, oculto_para_iniciador AS o FROM tipo_tramite_estado "
                  "WHERE id_tipo_tramite_version = :v AND NOT es_inicial AND NOT es_final ORDER BY orden LIMIT 1", v=t["v"])
    previo = oc["o"]
    try:
        await ejecutar("UPDATE tipo_tramite_estado SET oculto_para_iniciador = TRUE WHERE id_tipo_tramite_estado = :e", e=oc["e"])
        # movimiento de transición al estado oculto + cambio real del estado actual
        await ejecutar("INSERT INTO tramite_movimiento (id_tramite, orden_secuencial, tipo, id_estado_origen, id_estado_destino, id_municipio) "
                       "VALUES (:t, 90, 'transicion', :o, :d, :m)", t=idt, o=t["e"], d=oc["e"], m=mun)
        await ejecutar("UPDATE tramite SET id_tipo_tramite_estado_actual = :e WHERE id_tramite = :t", e=oc["e"], t=idt)
        fila = next(x for x in (await c.get(BASE_PUB, headers=hv)).json() if x["id_tramite"] == idt)
        check(fila["estado_etiqueta"] == ini["etiqueta"] and fila["estado_color"] == ini["color"],
              "lista: muestra el último estado visible", str(fila))
        r = await c.get(f"{BASE_PUB}/{idt}", headers=hv)
        d = r.json()
        check(d["estado_etiqueta"] == ini["etiqueta"], "detalle: estado visible anterior", d["estado_etiqueta"])
        check(oc["etiqueta"] not in r.text and oc["codigo"] not in r.text, "la etiqueta/código oculto no aparece en ningún lado")
        check(not any("pasó a" in h["texto"] for h in d["historial"]), "el historial omite la fila del estado oculto",
              str([h["texto"] for h in d["historial"]]))
        # sin ningún estado visible previo: se borra el ledger de visibles
        await ejecutar("UPDATE tipo_tramite_estado SET oculto_para_iniciador = TRUE WHERE id_tipo_tramite_estado = :e", e=t["e"])
        d = (await c.get(f"{BASE_PUB}/{idt}", headers=hv)).json()
        check(d["estado_etiqueta"] == "En trámite" and d["estado_color"] is None, "sin visible previo: En trámite sin color",
              f"{d['estado_etiqueta']} {d['estado_color']}")
    finally:
        await ejecutar("UPDATE tipo_tramite_estado SET oculto_para_iniciador = FALSE WHERE id_tipo_tramite_estado = :e", e=t["e"])
        await ejecutar("UPDATE tipo_tramite_estado SET oculto_para_iniciador = :o WHERE id_tipo_tramite_estado = :e", o=previo, e=oc["e"])
        await _limpiar_tramite_completo(idt)


# ── Task 6: pedidos al vecino ───────────────────────────────────────────────

BASE_BO = "/api/v1/tramites"


async def _pedir(c, ha, numero, texto="Necesitamos que adjuntes una foto del frente", pide_archivo=True):
    return await c.post(f"{BASE_BO}/{numero}/pedidos", headers=ha, json={"texto": texto, "pide_archivo": pide_archivo})


async def _fila_bandeja(c, ha, numero) -> Optional[dict]:
    r = await c.get(BASE_BO, headers=ha, params={"numero": numero})
    items = r.json().get("items", []) if r.status_code == 200 else []
    return items[0] if items else None


async def test_pedido_ciclo_completo(c: httpx.AsyncClient, ha: dict) -> None:
    print("[21] Pedido al vecino: pedir, responder, ver y marcar visto")
    hv = await _login_vecino(c)
    idt, numero = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke pedido ciclo")
    url_previa = settings.APP_VECINOS_FRONTEND_URL
    settings.APP_VECINOS_FRONTEND_URL = "https://vecinos.smoke.local"
    try:
        MAILS.clear()
        r = await _pedir(c, ha, numero)
        check(r.status_code == 200, "pedir: 200", f"{r.status_code} {r.text[:200]}")
        if r.status_code != 200:
            return
        ped = r.json()["pedidos"]
        check(len(ped) == 1 and ped[0]["estado"] == "abierto" and ped[0]["pide_archivo"] is True,
              "el detalle trae el pedido abierto", str(ped))
        idp = ped[0]["id_tramite_pedido"]
        av = await q1("SELECT count(*) AS n FROM ciudadano_aviso WHERE id_ciudadano = :c AND tipo = 'tramite_pedido' "
                      "AND recurso_tipo = 'tramite' AND recurso_id = :t", c=ID_CIUDADANO, t=idt)
        check(av["n"] == 1, "aviso tramite_pedido en la bandeja del vecino", str(av))
        mail = [m for m in MAILS if numero in m["subject"] + m["html"]]
        check(len(mail) == 1, "un mail capturado al vecino", str(MAILS)[:200])
        check(bool(mail) and "Ir al Portal del Ciudadano" in mail[0]["html"] and "https://vecinos.smoke.local" in mail[0]["html"],
              "el mail trae el botón al portal", mail[0]["html"][:300] if mail else "")
        mov = await q1("SELECT metadata_jsonb FROM tramite_movimiento WHERE id_tramite = :t AND tipo = 'pedido_iniciador'", t=idt)
        check(mov is not None and mov["metadata_jsonb"].get("id_tramite_pedido") == idp,
              "movimiento pedido_iniciador con id_tramite_pedido en metadata", str(mov))

        fila = await _fila_bandeja(c, ha, numero)
        check(fila is not None and fila["pedido_abierto"] is True and fila["respuesta_sin_ver"] is False,
              "bandeja: pedido_abierto=true", str(fila))
        d = (await c.get(f"{BASE_PUB}/{idt}", headers=hv)).json()
        check(d["pedido_abierto"] is not None and d["pedido_abierto"]["id_tramite_pedido"] == idp, "detalle público: pedido_abierto",
              str(d.get("pedido_abierto")))
        check("agente_pide" not in str(d["pedido_abierto"]), "el detalle público no expone al agente")

        url = f"{BASE_PUB}/{idt}/pedidos/{idp}/responder"
        r = await c.post(url, headers=hv, data={"texto": "Ahí va la foto del frente"})
        check(r.status_code == 422, "responder sin archivo si lo pidió: 422", f"{r.status_code} {r.text[:150]}")
        r = await c.post(url, headers=hv, data={"texto": "ok"}, files=[("archivos", ("f.png", PNG, "image/png"))])
        check(r.status_code == 422, "texto de menos de 5 caracteres: 422", f"{r.status_code}")
        SUBIDOS.clear()
        r = await c.post(url, headers=hv, data={"texto": "Ahí va la foto del frente"},
                         files=[("archivos", ("frente.png", PNG, "image/png"))])
        check(r.status_code == 200, "responder con archivo: 200", f"{r.status_code} {r.text[:200]}")
        check(len(SUBIDOS) == 1, "un objeto subido a Storage", str(SUBIDOS))
        p = await q1("SELECT estado, respuesta_texto, fecha_respuesta, respuesta_vista_en FROM tramite_pedido_iniciador "
                     "WHERE id_tramite_pedido = :p", p=idp)
        check(p["estado"] == "respondido" and p["respuesta_texto"] == "Ahí va la foto del frente" and p["fecha_respuesta"] is not None
              and p["respuesta_vista_en"] is None, "pedido respondido con su texto", str(p))
        doc = await q1("SELECT id_ciudadano_subio AS c FROM tramite_documento WHERE id_tramite = :t AND id_tramite_pedido = :p",
                       t=idt, p=idp)
        check(doc is not None and doc["c"] == ID_CIUDADANO, "documento vinculado al pedido y subido por el vecino", str(doc))
        mv = await q1("SELECT id_ciudadano_actor AS c, metadata_jsonb FROM tramite_movimiento WHERE id_tramite = :t "
                      "AND tipo = 'respuesta_iniciador'", t=idt)
        check(mv is not None and mv["c"] == ID_CIUDADANO and mv["metadata_jsonb"].get("id_tramite_pedido") == idp,
              "movimiento respuesta_iniciador del vecino", str(mv))
        dest = await q1("SELECT id_subarea_actual AS s FROM tramite WHERE id_tramite = :t", t=idt)
        usuarios = (await q1("SELECT count(*) AS n FROM agentes a JOIN usuarios u ON u.id_usuario = a.id_usuario AND u.activo "
                             "WHERE a.id_subarea = :s AND a.activo AND u.email IS NOT NULL AND u.email <> ''", s=dest["s"]))["n"]
        notifs = (await q1("SELECT count(*) AS n FROM notificacion WHERE recurso_tipo = 'tramite' AND recurso_id = :t "
                           "AND tipo = 'tramite_respuesta_vecino'", t=idt))["n"]
        check(notifs == usuarios and notifs > 0, "notificación in-app al colectivo destinatario", f"{notifs} vs {usuarios}")

        d = (await c.get(f"{BASE_PUB}/{idt}", headers=hv)).json()
        check(d["pedido_abierto"] is None, "el detalle público ya no tiene pedido abierto")
        check(any(h["texto"].startswith("Te pidieron:") for h in d["historial"])
              and any(h["texto"] == "Respondiste el pedido." for h in d["historial"]),
              "historial del vecino con el pedido y la respuesta", str([h["texto"] for h in d["historial"]]))
        rb = await c.get(f"{BASE_BO}/{numero}", headers=ha)
        pb = rb.json()["pedidos"][0]
        check(pb["estado"] == "respondido" and pb["respuesta_texto"] == "Ahí va la foto del frente"
              and len(pb["documentos_respuesta"]) == 1 and pb["agente_pide"], "detalle del backoffice con la respuesta y el agente",
              str(pb))
        fila = await _fila_bandeja(c, ha, numero)
        check(fila["pedido_abierto"] is False and fila["respuesta_sin_ver"] is True, "bandeja: respuesta_sin_ver=true", str(fila))
        r = await c.post(f"{BASE_BO}/{numero}/pedidos/{idp}/visto", headers=ha)
        check(r.status_code == 204, "visto: 204", f"{r.status_code} {r.text[:150]}")
        fila = await _fila_bandeja(c, ha, numero)
        check(fila["respuesta_sin_ver"] is False, "bandeja: respuesta_sin_ver=false tras /visto", str(fila))
    finally:
        settings.APP_VECINOS_FRONTEND_URL = url_previa
        await ejecutar("DELETE FROM ciudadano_aviso WHERE tipo = 'tramite_pedido' AND recurso_tipo = 'tramite' AND recurso_id = :t", t=idt)
        await ejecutar("DELETE FROM tramite_documento WHERE id_tramite = :t", t=idt)
        await _limpiar_tramite_completo(idt)


async def test_pedido_reglas_422(c: httpx.AsyncClient, ha: dict) -> None:
    print("[22] Pedido al vecino: reglas de negocio (422)")
    mun = await _municipio_base()
    idt, numero = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke pedido reglas")
    try:
        r = await _pedir(c, ha, numero, texto="cort")
        check(r.status_code == 422, "texto de menos de 5 caracteres: 422", f"{r.status_code}")
        r = await _pedir(c, ha, numero)
        check(r.status_code == 200, "primer pedido: 200", f"{r.status_code} {r.text[:150]}")
        r = await _pedir(c, ha, numero, texto="Otro pedido distinto del anterior")
        check(r.status_code == 422, "segundo pedido con uno abierto: 422", f"{r.status_code} {r.text[:150]}")
        n = (await q1("SELECT count(*) AS n FROM tramite_pedido_iniciador WHERE id_tramite = :t", t=idt))["n"]
        check(n == 1, "sigue habiendo un solo pedido", str(n))
        await ejecutar("DELETE FROM tramite_pedido_iniciador WHERE id_tramite = :t", t=idt)

        # archivado y estado final
        await ejecutar("UPDATE tramite SET fecha_archivado = NOW() WHERE id_tramite = :t", t=idt)
        r = await _pedir(c, ha, numero)
        check(r.status_code == 422, "trámite archivado: 422", f"{r.status_code}")
        await ejecutar("UPDATE tramite SET fecha_archivado = NULL WHERE id_tramite = :t", t=idt)
        orig = (await q1("SELECT id_tipo_tramite_estado_actual AS e, id_tipo_tramite_version AS v FROM tramite WHERE id_tramite = :t", t=idt))
        fin = await q1("SELECT id_tipo_tramite_estado AS e FROM tipo_tramite_estado WHERE id_tipo_tramite_version = :v AND es_final LIMIT 1",
                       v=orig["v"])
        await ejecutar("UPDATE tramite SET id_tipo_tramite_estado_actual = :e WHERE id_tramite = :t", e=fin["e"], t=idt)
        r = await _pedir(c, ha, numero)
        check(r.status_code == 422, "estado final: 422", f"{r.status_code}")
        await ejecutar("UPDATE tramite SET id_tipo_tramite_estado_actual = :e WHERE id_tramite = :t", e=orig["e"], t=idt)

        # vecino sin cuenta (se le desactiva la credencial un rato)
        await ejecutar("UPDATE ciudadano_credencial SET activo = FALSE WHERE id_ciudadano = :c", c=ID_CIUDADANO)
        try:
            r = await _pedir(c, ha, numero)
            check(r.status_code == 422 and "cuenta" in r.text, "vecino sin cuenta en el portal: 422", f"{r.status_code} {r.text[:150]}")
        finally:
            await ejecutar("UPDATE ciudadano_credencial SET activo = TRUE WHERE id_ciudadano = :c", c=ID_CIUDADANO)

        # iniciador empresa
        emp = await q1("SELECT id_empresa FROM empresas WHERE id_municipio = :m AND activo ORDER BY id_empresa LIMIT 1", m=mun)
        if emp:
            await ejecutar("UPDATE tramite SET iniciador_tipo = 'empresa', id_ciudadano_iniciador = NULL, id_empresa_iniciadora = :e "
                           "WHERE id_tramite = :t", e=emp["id_empresa"], t=idt)
            r = await _pedir(c, ha, numero)
            check(r.status_code == 422, "iniciador empresa: 422", f"{r.status_code} {r.text[:150]}")
            await ejecutar("UPDATE tramite SET iniciador_tipo = 'ciudadano', id_ciudadano_iniciador = :c, id_empresa_iniciadora = NULL "
                           "WHERE id_tramite = :t", c=ID_CIUDADANO, t=idt)
        else:
            check(False, "datos de partida (una empresa)")
        r = await _pedir(c, ha, numero)
        check(r.status_code == 200, "con todo en regla vuelve a andar: 200", f"{r.status_code} {r.text[:150]}")
    finally:
        await ejecutar("DELETE FROM ciudadano_aviso WHERE tipo = 'tramite_pedido' AND recurso_tipo = 'tramite' AND recurso_id = :t", t=idt)
        await _limpiar_tramite_completo(idt)


async def test_respuesta_doble_409(c: httpx.AsyncClient, ha: dict) -> None:
    print("[23] Dos respuestas a la vez: una gana, la otra 409")
    hv = await _login_vecino(c)
    idt, numero = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke pedido doble")
    try:
        r = await _pedir(c, ha, numero, pide_archivo=False)
        idp = r.json()["pedidos"][0]["id_tramite_pedido"]
        url = f"{BASE_PUB}/{idt}/pedidos/{idp}/responder"

        async def uno(i):
            return await c.post(url, headers=hv, data={"texto": f"Respuesta número {i}"},
                                files=[("archivos", (f"{i}.png", PNG, "image/png"))])
        r1, r2 = await asyncio.gather(uno(1), uno(2))
        codigos = sorted([r1.status_code, r2.status_code])
        check(codigos == [200, 409], "una 200 y otra 409", str(codigos))
        n = (await q1("SELECT count(*) AS n FROM tramite_movimiento WHERE id_tramite = :t AND tipo = 'respuesta_iniciador'", t=idt))["n"]
        d = (await q1("SELECT count(*) AS n FROM tramite_documento WHERE id_tramite = :t AND id_tramite_pedido = :p", t=idt, p=idp))["n"]
        check(n == 1 and d == 1, "una sola respuesta guardada (movimiento y documento)", f"mov={n} doc={d}")
    finally:
        await ejecutar("DELETE FROM ciudadano_aviso WHERE tipo = 'tramite_pedido' AND recurso_tipo = 'tramite' AND recurso_id = :t", t=idt)
        await ejecutar("DELETE FROM tramite_documento WHERE id_tramite = :t", t=idt)
        await _limpiar_tramite_completo(idt)


async def test_cancelar_pedido(c: httpx.AsyncClient, ha: dict) -> None:
    print("[24] Cancelar un pedido")
    hv = await _login_vecino(c)
    idt, numero = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke pedido cancelar")
    try:
        r = await _pedir(c, ha, numero, pide_archivo=False)
        idp = r.json()["pedidos"][0]["id_tramite_pedido"]
        r = await c.post(f"{BASE_BO}/{numero}/pedidos/{idp}/cancelar", headers=ha, json={"motivo": "ya"})
        check(r.status_code == 422, "motivo corto: 422", f"{r.status_code}")
        r = await c.post(f"{BASE_BO}/{numero}/pedidos/{idp}/cancelar", headers=ha, json={"motivo": "Lo pedimos por error"})
        check(r.status_code == 200 and r.json()["pedidos"][0]["estado"] == "cancelado"
              and r.json()["pedidos"][0]["motivo_cancelacion"] == "Lo pedimos por error", "cancelar: 200 y estado cancelado",
              f"{r.status_code} {r.text[:200]}")
        av = (await q1("SELECT count(*) AS n FROM ciudadano_aviso WHERE id_ciudadano = :c AND tipo = 'tramite_pedido' "
                       "AND recurso_id = :t", c=ID_CIUDADANO, t=idt))["n"]
        check(av == 2, "avisos al vecino: el pedido y la cancelación", str(av))
        mov = await q1("SELECT metadata_jsonb FROM tramite_movimiento WHERE id_tramite = :t AND tipo = 'pedido_cancelado'", t=idt)
        check(mov is not None and mov["metadata_jsonb"].get("id_tramite_pedido") == idp, "movimiento pedido_cancelado con id en metadata", str(mov))
        r = await c.post(f"{BASE_PUB}/{idt}/pedidos/{idp}/responder", headers=hv, data={"texto": "Respuesta tardía al pedido"})
        check(r.status_code == 409, "responder después de cancelado: 409", f"{r.status_code}")
        r = await c.post(f"{BASE_BO}/{numero}/pedidos/{idp}/cancelar", headers=ha, json={"motivo": "Otra vez cancelado"})
        check(r.status_code == 409, "cancelar uno ya cancelado: 409", f"{r.status_code}")
        r = await c.post(f"{BASE_BO}/{numero}/pedidos/2000000000/visto", headers=ha)
        check(r.status_code == 404, "visto de un pedido inexistente: 404", f"{r.status_code}")
    finally:
        await ejecutar("DELETE FROM ciudadano_aviso WHERE tipo = 'tramite_pedido' AND recurso_tipo = 'tramite' AND recurso_id = :t", t=idt)
        await _limpiar_tramite_completo(idt)


async def test_ajeno_404_pedido(c: httpx.AsyncClient, ha: dict) -> None:
    print("[25] Responder el pedido de un trámite ajeno: 404 idéntico")
    mun = await _municipio_base()
    hv = await _login_vecino(c)
    otro = await _otro_vecino_con_cuenta(mun)
    if not otro:
        check(False, "datos de partida (otro vecino con cuenta)")
        return
    ido, numero = await _tramite_ventanilla(c, ha, otro, "Smoke pedido ajeno")
    mio, num_mio = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke pedido propio")
    try:
        r = await _pedir(c, ha, numero, pide_archivo=False)
        idp = r.json()["pedidos"][0]["id_tramite_pedido"]
        form = {"texto": "Intento responder lo ajeno"}
        r0 = await c.post(f"{BASE_PUB}/2000000000/pedidos/{idp}/responder", headers=hv, data=form)
        r = await c.post(f"{BASE_PUB}/{ido}/pedidos/{idp}/responder", headers=hv, data=form)
        check(r0.status_code == 404 and r.status_code == 404 and r.text == r0.text, "trámite ajeno: 404 idéntico",
              f"{r.status_code} {r.text}")
        r = await c.post(f"{BASE_PUB}/{mio}/pedidos/{idp}/responder", headers=hv, data=form)
        check(r.status_code == 404, "pedido ajeno colgado de mi trámite: 404", f"{r.status_code}")
        p = await q1("SELECT estado FROM tramite_pedido_iniciador WHERE id_tramite_pedido = :p", p=idp)
        check(p["estado"] == "abierto", "el pedido ajeno sigue abierto", str(p))
    finally:
        await ejecutar("DELETE FROM ciudadano_aviso WHERE tipo = 'tramite_pedido' AND recurso_tipo = 'tramite' AND recurso_id = :t", t=ido)
        for i in (ido, mio):
            await _limpiar_tramite_completo(i)


async def _limpiar_avisos_pedido(idt: int) -> None:
    await ejecutar("DELETE FROM ciudadano_aviso WHERE recurso_tipo = 'tramite' AND recurso_id = :t", t=idt)


async def test_visto_con_guard(c: httpx.AsyncClient, ha: dict) -> None:
    print("[26] /visto: solo marca quien puede operar el trámite; el resto recibe 204 sin escribir")
    mun = await _municipio_base()
    hv = await _login_vecino(c)
    idt, numero = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke pedido visto")
    cons = await _usuario_fixture(mun, 5)
    otro = await _usuario_fixture(mun, 3)
    try:
        r = await _pedir(c, ha, numero, pide_archivo=False)
        idp = r.json()["pedidos"][0]["id_tramite_pedido"]
        r = await c.post(f"{BASE_PUB}/{idt}/pedidos/{idp}/responder", headers=hv, data={"texto": "Respuesta para ver"})
        check(r.status_code == 200, "respuesta del vecino", f"{r.status_code} {r.text[:150]}")
        for nombre, f in (("Consultor", cons), ("agente que no puede operar", otro)):
            h = await _login_fixture(c, f)
            r = await c.post(f"{BASE_BO}/{numero}/pedidos/{idp}/visto", headers=h)
            check(r.status_code == 204, f"{nombre}: 204", f"{r.status_code} {r.text[:120]}")
            fila = await _fila_bandeja(c, ha, numero)
            check(fila["respuesta_sin_ver"] is True, f"{nombre}: respuesta_sin_ver sigue true", str(fila))
        r = await c.post(f"{BASE_BO}/{numero}/pedidos/{idp}/visto", headers=ha)
        check(r.status_code == 204, "admin: 204", str(r.status_code))
        fila = await _fila_bandeja(c, ha, numero)
        check(fila["respuesta_sin_ver"] is False, "admin: respuesta_sin_ver false", str(fila))
    finally:
        await _borrar_usuario_fixture(cons)
        await _borrar_usuario_fixture(otro)
        await _limpiar_avisos_pedido(idt)
        await _limpiar_tramite_completo(idt)


async def _estados_finales(idt: int) -> list[dict]:
    async with AsyncSessionLocal() as sx:
        rows = (await sx.execute(text(
            "SELECT e.id_tipo_tramite_estado AS e FROM tipo_tramite_estado e JOIN tramite t "
            "ON t.id_tipo_tramite_version = e.id_tipo_tramite_version WHERE t.id_tramite = :t AND e.es_final"),
            {"t": idt})).mappings().all()
    return [dict(x) for x in rows]


async def _hasta_estado_final(c: httpx.AsyncClient, ha: dict, idt: int, numero: str) -> bool:
    """Recorre transiciones permitidas (prefiere las que llevan a un final) hasta llegar a un estado final."""
    for _ in range(8):
        r = await c.get(f"{BASE_BO}/{numero}/transiciones-permitidas", headers=ha)
        ts = [t for t in r.json().get("transiciones", []) if t["disponible"] and not t["requiere_adjunto"]]
        if not ts:
            return False
        finales = {r2["e"] for r2 in await _estados_finales(idt)}
        t = next((x for x in ts if x["id_estado_destino"] in finales), ts[0])
        r = await c.post(f"{BASE_BO}/{numero}/transicionar", headers=ha,
                         json={"id_tipo_tramite_transicion": t["id_tipo_tramite_transicion"], "comentario": "smoke cierre"})
        if r.status_code != 200:
            return False
        if t["id_estado_destino"] in finales:
            return True
    return False


async def _chequear_cierre(idt: int, motivo: str, nombre: str) -> None:
    p = await q1("SELECT estado, motivo_cancelacion FROM tramite_pedido_iniciador WHERE id_tramite = :t", t=idt)
    check(p is not None and p["estado"] == "cancelado" and p["motivo_cancelacion"] == motivo,
          f"{nombre}: pedido cancelado con el motivo", str(p))
    m = await q1("SELECT id_agente, id_ciudadano_actor AS c, metadata_jsonb AS md FROM tramite_movimiento "
                 "WHERE id_tramite = :t AND tipo = 'pedido_cancelado'", t=idt)
    check(m is not None and m["id_agente"] is None and m["c"] is None and m["md"].get("automatico") is True,
          f"{nombre}: movimiento pedido_cancelado automático de sistema", str(m))


async def test_pedido_se_cancela_al_cerrar(c: httpx.AsyncClient, ha: dict) -> None:
    print("[27] El pedido abierto se cancela cuando el trámite termina; responder da 409")
    from app.services.tramites import retencion as svc_ret
    hv = await _login_vecino(c)
    nuevo = lambda a: _tramite_ventanilla(c, ha, ID_CIUDADANO, a)
    # a) transición a un estado final
    idt, numero = await nuevo("Smoke cierre por transición")
    try:
        await _pedir(c, ha, numero, pide_archivo=False)
        idp = (await q1("SELECT id_tramite_pedido AS i FROM tramite_pedido_iniciador WHERE id_tramite = :t", t=idt))["i"]
        llego = await _hasta_estado_final(c, ha, idt, numero)
        check(llego, "se llegó a un estado final por transiciones")
        if llego:
            await _chequear_cierre(idt, "El trámite terminó", "transición final")
            r = await c.post(f"{BASE_PUB}/{idt}/pedidos/{idp}/responder", headers=hv, data={"texto": "Respuesta tardía"})
            check(r.status_code == 409 and "ya terminó" in r.text, "responder en un trámite final: 409", f"{r.status_code} {r.text[:150]}")
    finally:
        await _limpiar_avisos_pedido(idt)
        await _limpiar_tramite_completo(idt)
    # b) desistido manual por /resultado
    idt, numero = await nuevo("Smoke cierre por desistido")
    try:
        await _pedir(c, ha, numero, pide_archivo=False)
        idp = (await q1("SELECT id_tramite_pedido AS i FROM tramite_pedido_iniciador WHERE id_tramite = :t", t=idt))["i"]
        r = await c.post(f"{BASE_BO}/{numero}/resultado", headers=ha, json={"resultado": "desistido", "comentario": "smoke desistido"})
        check(r.status_code == 200, "resultado desistido: 200", f"{r.status_code} {r.text[:150]}")
        await _chequear_cierre(idt, "El trámite se dio por desistido", "desistido manual")
        r = await c.post(f"{BASE_PUB}/{idt}/pedidos/{idp}/responder", headers=hv, data={"texto": "Respuesta tardía"})
        check(r.status_code == 409, "responder en un trámite archivado: 409", f"{r.status_code}")
    finally:
        await _limpiar_avisos_pedido(idt)
        await _limpiar_tramite_completo(idt)
    # c) archivo por inactividad (la función del cron, sobre este trámite envejecido)
    mun = await _municipio_base()
    idt, numero = await nuevo("Smoke cierre por inactividad")
    try:
        await _pedir(c, ha, numero, pide_archivo=False)
        await ejecutar("UPDATE tramite SET fecha_modificacion = NOW() - INTERVAL '5000 days', "
                       "fecha_entrada_estado_actual = NOW() - INTERVAL '5000 days' WHERE id_tramite = :t", t=idt)
        await ejecutar("UPDATE tramite_movimiento SET fecha_alta = NOW() - INTERVAL '5000 days' WHERE id_tramite = :t", t=idt)
        async with AsyncSessionLocal() as s:
            res = await svc_ret.archivar_inactivos(s, id_municipio=mun)
        if idt in res["ids"]:
            await _chequear_cierre(idt, "El trámite se archivó por inactividad", "inactividad")
        else:
            check(False, "el trámite envejecido fue archivado por inactividad", str(res)[:200])
    finally:
        await _limpiar_avisos_pedido(idt)
        await _limpiar_tramite_completo(idt)


async def _cfg_desistimiento(mun: int) -> dict:
    from app.services.tramites.retencion import _leer_int_config
    async with AsyncSessionLocal() as s:
        cfg = {k: await _leer_int_config(s, k, v, id_municipio=mun) for k, v in _ciclo_vida.DEFAULTS.items()}
    return cfg


async def _correr_pedidos_sin_respuesta(mun: int) -> dict:
    async with AsyncSessionLocal() as s:
        return await _ciclo_vida.procesar_pedidos_sin_respuesta(s, id_municipio=mun)


async def _viajar_pedido(idt: int, dias: float) -> None:
    await ejecutar("UPDATE tramite_pedido_iniciador SET fecha_pedido = NOW() - make_interval(secs => CAST(:s AS float)) "
                   "WHERE id_tramite = :t", s=dias * 86400, t=idt)


async def _estado_pedido(idt: int) -> dict:
    return await q1("SELECT id_tramite_pedido AS id, estado, aviso_nivel AS nivel, aviso_en FROM tramite_pedido_iniciador "
                    "WHERE id_tramite = :t", t=idt)


async def _avisos_pedido(idt: int) -> list:
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(text(
            "SELECT id_agente, id_usuario_alta AS id_usuario, metadata_jsonb AS md FROM tramite_movimiento "
            "WHERE id_tramite = :t AND tipo = 'aviso_iniciador' AND metadata_jsonb ->> 'id_tramite_pedido' IS NOT NULL "
            "ORDER BY id_tramite_movimiento"), {"t": idt})).mappings().all()
    return [dict(r) for r in rows]


async def test_pedido_escalones(c: httpx.AsyncClient, ha: dict) -> None:
    print("[28] Pedido sin respuesta: avisos escalonados (1 nivel por corrida) y desistimiento")
    mun = await _municipio_base()
    cfg = await _cfg_desistimiento(mun)
    a1, a2, dd, fh = (cfg[_ciclo_vida.CFG_AVISO1], cfg[_ciclo_vida.CFG_AVISO2],
                      cfg[_ciclo_vida.CFG_DESISTIR], cfg[_ciclo_vida.CFG_FINAL_HORAS])
    idt, numero = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke pedido escalones")
    texto = "Necesitamos la foto del frente del arbol"
    try:
        r = await _pedir(c, ha, numero, texto=texto, pide_archivo=False)
        check(r.status_code in (200, 201), "pedido creado", f"{r.status_code} {r.text[:120]}")
        await ejecutar("UPDATE tramite SET desist_aviso_nivel = 0 WHERE id_tramite = :t", t=idt)
        # Recien hecho: no corresponde nada.
        res = await _correr_pedidos_sin_respuesta(mun)
        check(res.get("activo") is True and (await _estado_pedido(idt))["nivel"] == 0, "pedido nuevo: sin aviso", str(res)[:120])
        # a1 + 1 dias -> nivel 1 con aviso que cita el pedido.
        await _viajar_pedido(idt, a1 + 1)
        MAILS.clear()
        res = await _correr_pedidos_sin_respuesta(mun)
        e = await _estado_pedido(idt)
        check(e["nivel"] == 1 and e["aviso_en"] is not None and idt in [x["id_tramite"] for x in res["avisados"]],
              "a1+1 dias: nivel 1", f"{e} {res}")
        check(res["avisos"] >= 1 and "avisados" in res and "desistidos" in res and "ids" in res, "forma del resultado", str(res)[:150])
        av = await _avisos_pedido(idt)
        check(len(av) == 1 and av[0]["id_agente"] is None and av[0]["id_usuario"] is None
              and av[0]["md"].get("nivel") == 1 and av[0]["md"].get("id_tramite_pedido") == e["id"]
              and av[0]["md"].get("automatico") is True, "movimiento aviso_iniciador de sistema con metadata", str(av))
        check(any(texto in m["html"] for m in MAILS), "el mail cita el texto del pedido", str([m["subject"] for m in MAILS]))
        ca = await q1("SELECT mensaje FROM ciudadano_aviso WHERE tipo = 'tramite_pedido' AND recurso_tipo = 'tramite' "
                      "AND recurso_id = :t", t=idt)
        check(ca is not None and texto in ca["mensaje"], "aviso en la bandeja del vecino con el texto", str(ca))
        ni = await q1("SELECT count(*) AS n, bool_and(mensaje LIKE '%' || :tx || '%') AS cita FROM notificacion "
                      "WHERE tipo = 'tramite_pendiente_vecino' AND recurso_tipo = 'tramite' AND recurso_id = :t", tx=texto, t=idt)
        check(ni is not None and ni["n"] >= 1 and ni["cita"] is True,
              "el aviso interno al equipo dice qué pedido no se respondió", str(ni))
        # Correr de nuevo sin mover el tiempo: ningun aviso nuevo.
        res = await _correr_pedidos_sin_respuesta(mun)
        check((await _estado_pedido(idt))["nivel"] == 1 and len(await _avisos_pedido(idt)) == 1
              and idt not in [x["id_tramite"] for x in res["avisados"]], "segunda corrida sin mover: sin aviso nuevo", str(res)[:150])
        # Un solo nivel por corrida: aunque el pedido tenga mucho atraso, de 1 pasa a 2.
        await _viajar_pedido(idt, a2 + 1)
        await _correr_pedidos_sin_respuesta(mun)
        check((await _estado_pedido(idt))["nivel"] == 2, "a2+1 dias: nivel 2")
        await _viajar_pedido(idt, dd - fh / 24.0 + 0.1)
        await _correr_pedidos_sin_respuesta(mun)
        check((await _estado_pedido(idt))["nivel"] == 3, "umbral final: nivel 3 (ultimo aviso)")
        check(len(await _avisos_pedido(idt)) == 3, "tres avisos registrados", str(len(await _avisos_pedido(idt))))
        # dd + 1 con nivel 3 -> desistido.
        await _viajar_pedido(idt, dd + 1)
        MAILS.clear()
        res = await _correr_pedidos_sin_respuesta(mun)
        t = await q1("SELECT resultado, fecha_archivado, archivado_motivo FROM tramite WHERE id_tramite = :t", t=idt)
        check(t["resultado"] == "desistido" and t["fecha_archivado"] is not None and t["archivado_motivo"] == "desistimiento"
              and idt in res["ids"] and res["desistidos"] >= 1, "dd+1 dias: tramite desistido", f"{t} {res}")
        p = await q1("SELECT estado, motivo_cancelacion FROM tramite_pedido_iniciador WHERE id_tramite = :t", t=idt)
        check(p["estado"] == "cancelado" and p["motivo_cancelacion"] == "El trámite se dio por desistido",
              "el pedido queda cancelado con el motivo", str(p))
        m = await q1("SELECT id_agente, id_usuario_alta AS id_usuario, metadata_jsonb AS md FROM tramite_movimiento WHERE id_tramite = :t "
                     "AND tipo = 'desistido'", t=idt)
        check(m is not None and m["md"].get("id_tramite_pedido") == (await _estado_pedido(idt))["id"]
              and m["md"].get("automatico") is True and m["id_usuario"] is None, "movimiento desistido con el id del pedido", str(m))
        mc = await q1("SELECT metadata_jsonb AS md FROM tramite_movimiento WHERE id_tramite = :t AND tipo = 'pedido_cancelado'", t=idt)
        check(mc is not None and mc["md"].get("automatico") is True, "movimiento pedido_cancelado automatico", str(mc))
        check(any("desistido" in m2["subject"] for m2 in MAILS), "mail de desistimiento al vecino", str([m2["subject"] for m2 in MAILS]))
        # Desistido y archivado: no vuelve a procesarse.
        res = await _correr_pedidos_sin_respuesta(mun)
        check(idt not in res["ids"] and idt not in [x["id_tramite"] for x in res["avisados"]], "no se reprocesa", str(res)[:120])
    finally:
        await _limpiar_avisos_pedido(idt)
        await _limpiar_tramite_completo(idt)


async def test_pedido_desistimiento_apagado(c: httpx.AsyncClient, ha: dict) -> None:
    print("[29] Pedido sin respuesta: con el desistimiento apagado no hace nada")
    mun = await _municipio_base()
    cfg = await _cfg_desistimiento(mun)
    idt, numero = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke pedido apagado")
    original = _ciclo_vida._leer_bool_config

    async def _apagado(db, clave, default, *, id_municipio):
        return False
    try:
        await _pedir(c, ha, numero, pide_archivo=False)
        await _viajar_pedido(idt, cfg[_ciclo_vida.CFG_DESISTIR] + 5)
        _ciclo_vida._leer_bool_config = _apagado
        res = await _correr_pedidos_sin_respuesta(mun)
        check(res.get("activo") is False and res.get("avisos") == 0 and res.get("desistidos") == 0, "resultado inactivo", str(res))
        e = await _estado_pedido(idt)
        t = await q1("SELECT resultado FROM tramite WHERE id_tramite = :t", t=idt)
        check(e["estado"] == "abierto" and e["nivel"] == 0 and t["resultado"] == "pendiente", "nada cambio", f"{e} {t}")
    finally:
        _ciclo_vida._leer_bool_config = original
        await _limpiar_avisos_pedido(idt)
        await _limpiar_tramite_completo(idt)


async def test_cambio_de_estado_no_reinicia(c: httpx.AsyncClient, ha: dict) -> None:
    print("[30] Una transicion del tramite no reinicia el timer del pedido")
    mun = await _municipio_base()
    cfg = await _cfg_desistimiento(mun)
    idt, numero = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke pedido sin reinicio")
    try:
        await _pedir(c, ha, numero, pide_archivo=False)
        await _viajar_pedido(idt, cfg[_ciclo_vida.CFG_AVISO1] + 1)
        await _correr_pedidos_sin_respuesta(mun)
        antes = await _estado_pedido(idt)
        check(antes["nivel"] == 1, "nivel 1 antes de la transicion", str(antes))
        finales = {x["e"] for x in await _estados_finales(idt)}
        r = await c.get(f"{BASE_BO}/{numero}/transiciones-permitidas", headers=ha)
        ts = [t for t in r.json().get("transiciones", [])
              if t["disponible"] and not t["requiere_adjunto"] and t["id_estado_destino"] not in finales]
        check(bool(ts), "hay una transicion no final disponible")
        if ts:
            r = await c.post(f"{BASE_BO}/{numero}/transicionar", headers=ha,
                             json={"id_tipo_tramite_transicion": ts[0]["id_tipo_tramite_transicion"], "comentario": "smoke"})
            check(r.status_code == 200, "transicion aplicada", f"{r.status_code} {r.text[:120]}")
            despues = await _estado_pedido(idt)
            check(despues["estado"] == "abierto" and despues["nivel"] == 1 and despues["aviso_en"] == antes["aviso_en"],
                  "el nivel y la fecha del aviso no cambian", f"{antes} {despues}")
            # Y el timer sigue: con mas atraso pasa a nivel 2.
            await _viajar_pedido(idt, cfg[_ciclo_vida.CFG_AVISO2] + 1)
            await _correr_pedidos_sin_respuesta(mun)
            check((await _estado_pedido(idt))["nivel"] == 2, "el timer sigue corriendo (nivel 2)")
    finally:
        await _limpiar_avisos_pedido(idt)
        await _limpiar_tramite_completo(idt)


async def test_pedido_en_tramite_cerrado_no_avisa(c: httpx.AsyncClient, ha: dict) -> None:
    print("[31] Un pedido abierto en un tramite archivado o en estado final no avisa ni desiste")
    mun = await _municipio_base()
    cfg = await _cfg_desistimiento(mun)
    atraso = cfg[_ciclo_vida.CFG_DESISTIR] + 10
    a, na = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke pedido tramite archivado")
    f, nf = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke pedido tramite final")
    try:
        for n in (na, nf):
            await _pedir(c, ha, n, pide_archivo=False)
        for i in (a, f):
            await _viajar_pedido(i, atraso)
        await ejecutar("UPDATE tramite SET fecha_archivado = NOW() WHERE id_tramite = :t", t=a)
        fin = (await _estados_finales(f))
        check(bool(fin), "el tipo tiene un estado final")
        if fin:
            await ejecutar("UPDATE tramite SET id_tipo_tramite_estado_actual = :e WHERE id_tramite = :t", e=fin[0]["e"], t=f)
        res = await _correr_pedidos_sin_respuesta(mun)
        for i, nombre in ((a, "archivado"), (f, "en estado final")):
            e = await _estado_pedido(i)
            t = await q1("SELECT resultado FROM tramite WHERE id_tramite = :t", t=i)
            check(e["estado"] == "abierto" and e["nivel"] == 0 and t["resultado"] == "pendiente"
                  and i not in res["ids"] and i not in [x["id_tramite"] for x in res["avisados"]],
                  f"tramite {nombre}: ni aviso ni desistimiento", f"{e} {t}")
    finally:
        for i in (a, f):
            await _limpiar_avisos_pedido(i)
            await _limpiar_tramite_completo(i)


async def test_admin_ofrecer_al_vecino(c: httpx.AsyncClient, ha: dict) -> None:
    print("[32] Catalogo admin: ofrecer_al_vecino y exige_identidad_validada")
    mun = await _municipio_base()
    hv = await _login_vecino(c)
    tipo = await _tipo_poda(mun)
    tid = tipo["id_tipo_tramite"]
    orig = await q1("SELECT ofrecer_al_vecino AS o, exige_identidad_validada AS e, iniciadores_permitidos AS i FROM tipo_tramite WHERE id_tipo_tramite = :t", t=tid)
    base = f"/api/v1/admin/tramites/tipos/{tid}"

    async def _lista_admin():
        r = await c.get("/api/v1/admin/tramites/tipos", headers=ha)
        return next((x for x in r.json()["items"] if x["id_tipo_tramite"] == tid), {})

    async def _publico_ids():
        r = await c.get("/api/v1/publico/tramites/tipos", headers=hv)
        return {t["id_tipo_tramite"] for t in r.json()}

    tmp = None
    try:
        r = await c.put(base, json={"ofrecer_al_vecino": False}, headers=ha)
        check(r.status_code == 200 and r.json().get("ofrecer_al_vecino") is False, "PUT false: detalle false", f"{r.status_code} {r.text[:200]}")
        check(tid not in await _publico_ids(), "no ofrecido: no esta en /publico/tramites/tipos")
        r = await c.put(base, json={"ofrecer_al_vecino": True}, headers=ha)
        check(r.status_code == 200 and r.json().get("ofrecer_al_vecino") is True, "PUT true: detalle true", f"{r.status_code} {r.text[:200]}")
        r = await c.get(base + "/admin", headers=ha)
        check(r.json().get("ofrecer_al_vecino") is True, "GET detalle admin true")
        check((await _lista_admin()).get("ofrecer_al_vecino") is True, "lista admin true")
        check(tid in await _publico_ids(), "ofrecido: aparece en /publico/tramites/tipos")
        # exige_identidad_validada: ida y vuelta
        for val in (True, False):
            r = await c.put(base, json={"exige_identidad_validada": val}, headers=ha)
            check(r.status_code == 200 and r.json().get("exige_identidad_validada") is val, f"PUT exige_identidad {val}", f"{r.status_code} {r.text[:200]}")
            check((await _lista_admin()).get("exige_identidad_validada") is val, f"lista admin exige_identidad {val}")
        # tipo solo de empresa
        cod = "smoke-solo-empresa"
        await ejecutar("DELETE FROM tipo_tramite_version WHERE id_tipo_tramite IN (SELECT id_tipo_tramite FROM tipo_tramite WHERE codigo = :c AND id_municipio = :m)", c=cod, m=mun)
        await ejecutar("DELETE FROM tipo_tramite WHERE codigo = :c AND id_municipio = :m", c=cod, m=mun)
        cuerpo = {"codigo": cod, "nombre": "Smoke solo empresa", "prefijo": "SSE", "iniciadores_permitidos": ["empresa"]}
        r = await c.post("/api/v1/admin/tramites/tipos", json={**cuerpo, "ofrecer_al_vecino": True}, headers=ha)
        check(r.status_code == 422 and "Solo se ofrece al vecino" in r.text, "POST ofrecer sin ciudadano: 422", f"{r.status_code} {r.text[:200]}")
        r = await c.post("/api/v1/admin/tramites/tipos", json=cuerpo, headers=ha)
        check(r.status_code == 201 and r.json()["ofrecer_al_vecino"] is False and r.json()["exige_identidad_validada"] is False, "POST default false", f"{r.status_code} {r.text[:200]}")
        if r.status_code == 201:
            tmp = r.json()["id_tipo_tramite"]
            r = await c.put(f"/api/v1/admin/tramites/tipos/{tmp}", json={"ofrecer_al_vecino": True}, headers=ha)
            check(r.status_code == 422 and "Solo se ofrece al vecino un trámite que admite iniciador ciudadano" in r.text, "PUT true en tipo solo empresa: 422", f"{r.status_code} {r.text[:200]}")
            r = await c.put(f"/api/v1/admin/tramites/tipos/{tmp}", json={"exige_identidad_validada": True}, headers=ha)
            check(r.status_code == 200 and r.json()["exige_identidad_validada"] is True, "exige_identidad sin restriccion de iniciador")
        # quitar 'ciudadano' con la bandera en true: 422 (estado resultante)
        r = await c.put(base, json={"iniciadores_permitidos": ["empresa"]}, headers=ha)
        check(r.status_code == 422, "PUT quitar ciudadano con la bandera true: 422", f"{r.status_code} {r.text[:200]}")
    finally:
        await ejecutar("UPDATE tipo_tramite SET ofrecer_al_vecino = :o, exige_identidad_validada = :e, iniciadores_permitidos = :i WHERE id_tipo_tramite = :t",
                       o=orig["o"], e=orig["e"], i=orig["i"], t=tid)
        if tmp:
            await ejecutar("DELETE FROM tipo_tramite_version WHERE id_tipo_tramite = :t", t=tmp)
            await ejecutar("DELETE FROM tipo_tramite WHERE id_tipo_tramite = :t", t=tmp)


# ── Ola de corrección final ──────────────────────────────────────────────────

async def _movs_timer(idt: int) -> int:
    return (await q1("SELECT count(*) AS n FROM tramite_movimiento WHERE id_tramite = :t "
                     "AND tipo IN ('aviso_iniciador', 'desistido', 'pedido_cancelado')", t=idt))["n"]


async def _avisos_bandeja(idt: int) -> int:
    return (await q1("SELECT count(*) AS n FROM ciudadano_aviso WHERE recurso_tipo = 'tramite' AND recurso_id = :t", t=idt))["n"]


async def _fila_pedido_cron(idt: int, idp: int, cfg: dict):
    async with AsyncSessionLocal() as s:
        return await _ciclo_vida.procesar_pedido_sin_respuesta(s, idt, idp, cfg)


async def test_cron_pedido_foto_fresca(c: httpx.AsyncClient, ha: dict) -> None:
    print("[33] Cron de pedidos: la fila se decide con la foto bloqueada (respondido / aprobado / cancelado no escriben)")
    mun = await _municipio_base()
    cfg = await _cfg_desistimiento(mun)
    dd, a1 = cfg[_ciclo_vida.CFG_DESISTIR], cfg[_ciclo_vida.CFG_AVISO1]
    casos = []
    try:
        # (nombre, nivel previo, atraso, cómo cambia entre la selección y el proceso)
        for nombre, nivel, atraso, sql in (
            ("pedido respondido (rama desistimiento)", 3, dd + 1,
             "UPDATE tramite_pedido_iniciador SET estado = 'respondido', respuesta_texto = 'ya respondí', "
             "fecha_respuesta = NOW() WHERE id_tramite = :t"),
            ("pedido respondido (rama aviso)", 0, a1 + 1,
             "UPDATE tramite_pedido_iniciador SET estado = 'respondido', respuesta_texto = 'ya respondí', "
             "fecha_respuesta = NOW() WHERE id_tramite = :t"),
            ("pedido cancelado (rama aviso)", 0, a1 + 1,
             "UPDATE tramite_pedido_iniciador SET estado = 'cancelado', motivo_cancelacion = 'smoke' WHERE id_tramite = :t"),
            ("trámite aprobado (rama desistimiento)", 3, dd + 1,
             "UPDATE tramite SET resultado = 'aprobado' WHERE id_tramite = :t"),
            ("trámite aprobado (rama aviso)", 0, a1 + 1,
             "UPDATE tramite SET resultado = 'aprobado' WHERE id_tramite = :t"),
        ):
            idt, numero = await _tramite_ventanilla(c, ha, ID_CIUDADANO, f"Smoke carrera {nombre}")
            casos.append(idt)
            await _pedir(c, ha, numero, pide_archivo=False)
            await _viajar_pedido(idt, atraso)
            await ejecutar("UPDATE tramite_pedido_iniciador SET aviso_nivel = :n WHERE id_tramite = :t", n=nivel, t=idt)
            idp = (await _estado_pedido(idt))["id"]
            antes_t = await q1("SELECT resultado, fecha_archivado FROM tramite WHERE id_tramite = :t", t=idt)
            await ejecutar(sql, t=idt)  # el cambio que llega entre la selección y el proceso de la fila
            esperado_t = await q1("SELECT resultado, fecha_archivado FROM tramite WHERE id_tramite = :t", t=idt)
            esperado_p = await _estado_pedido(idt)
            movs, avisos = await _movs_timer(idt), await _avisos_bandeja(idt)
            MAILS.clear()
            res = await _fila_pedido_cron(idt, idp, cfg)
            t = await q1("SELECT resultado, fecha_archivado FROM tramite WHERE id_tramite = :t", t=idt)
            p = await _estado_pedido(idt)
            check(res is None, f"{nombre}: la fila no hace nada", str(res))
            check(t == esperado_t and t["resultado"] != "desistido" and antes_t["fecha_archivado"] is None
                  and t["fecha_archivado"] is None, f"{nombre}: el trámite no cambia", f"{esperado_t} -> {t}")
            check(p == esperado_p, f"{nombre}: el pedido no cambia", f"{esperado_p} -> {p}")
            check(await _movs_timer(idt) == movs and await _avisos_bandeja(idt) == avisos and not MAILS,
                  f"{nombre}: ni movimiento, ni aviso, ni mail", f"{movs} {avisos} {[m['subject'] for m in MAILS]}")
        # Control: con la foto vigente la misma función sí avisa (no es que nunca haga nada).
        idt, numero = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke carrera control")
        casos.append(idt)
        await _pedir(c, ha, numero, pide_archivo=False)
        await _viajar_pedido(idt, a1 + 1)
        idp = (await _estado_pedido(idt))["id"]
        res = await _fila_pedido_cron(idt, idp, cfg)
        check(res == {"accion": "aviso", "nivel": 1} and (await _estado_pedido(idt))["nivel"] == 1,
              "control: pedido abierto vigente -> aviso nivel 1", str(res))
    finally:
        for i in casos:
            await _limpiar_avisos_pedido(i)
            await _limpiar_tramite_completo(i)


async def test_cron_espera_foto_fresca(c: httpx.AsyncClient, ha: dict) -> None:
    print("[34] Cron de espera_iniciador: re-chequea el trámite bloqueado antes de avisar o desistir")
    mun = await _municipio_base()
    cfg = await _cfg_desistimiento(mun)
    idt, numero = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke espera foto fresca")
    est = await q1("SELECT t.id_tipo_tramite_estado_actual AS e, e.espera_iniciador AS esp FROM tramite t "
                   "JOIN tipo_tramite_estado e ON e.id_tipo_tramite_estado = t.id_tipo_tramite_estado_actual "
                   "WHERE t.id_tramite = :t", t=idt)
    fin = await _estados_finales(idt)

    async def _fila() -> Optional[dict]:
        async with AsyncSessionLocal() as s:
            return await _ciclo_vida.procesar_desistimiento_tramite(s, idt, cfg)

    async def _foto() -> dict:
        return await q1("SELECT resultado, fecha_archivado, desist_aviso_nivel AS nivel, id_tipo_tramite_estado_actual AS e "
                        "FROM tramite WHERE id_tramite = :t", t=idt)
    try:
        await ejecutar("UPDATE tipo_tramite_estado SET espera_iniciador = TRUE WHERE id_tipo_tramite_estado = :e", e=est["e"])
        await ejecutar("UPDATE tramite SET fecha_alta = NOW() - INTERVAL '400 days', "
                       "fecha_entrada_estado_actual = NOW() - INTERVAL '400 days', desist_aviso_nivel = 3 "
                       "WHERE id_tramite = :t", t=idt)
        negativos = [("trámite aprobado", "UPDATE tramite SET resultado = 'aprobado' WHERE id_tramite = :t",
                      "UPDATE tramite SET resultado = 'pendiente' WHERE id_tramite = :t"),
                     ("estado que ya no espera al iniciador",
                      "UPDATE tipo_tramite_estado SET espera_iniciador = FALSE WHERE id_tipo_tramite_estado = "
                      "(SELECT id_tipo_tramite_estado_actual FROM tramite WHERE id_tramite = :t)",
                      "UPDATE tipo_tramite_estado SET espera_iniciador = TRUE WHERE id_tipo_tramite_estado = "
                      "(SELECT id_tipo_tramite_estado_actual FROM tramite WHERE id_tramite = :t)"),
                     ("trámite archivado", "UPDATE tramite SET fecha_archivado = NOW() WHERE id_tramite = :t",
                      "UPDATE tramite SET fecha_archivado = NULL WHERE id_tramite = :t")]
        if fin:
            negativos.append(("trámite en estado final",
                              f"UPDATE tramite SET id_tipo_tramite_estado_actual = {int(fin[0]['e'])} WHERE id_tramite = :t",
                              f"UPDATE tramite SET id_tipo_tramite_estado_actual = {int(est['e'])} WHERE id_tramite = :t"))
        for nombre, cambio, deshacer in negativos:
            await ejecutar(cambio, t=idt)
            antes, movs, avisos = await _foto(), await _movs_timer(idt), await _avisos_bandeja(idt)
            MAILS.clear()
            res = await _fila()
            check(res is None and await _foto() == antes and await _movs_timer(idt) == movs
                  and await _avisos_bandeja(idt) == avisos and not MAILS,
                  f"{nombre}: no desiste ni avisa ni escribe", f"{res} {antes} -> {await _foto()}")
            await ejecutar(deshacer, t=idt)
        # Control: con la foto vigente (nivel 3, plazo vencido) la fila desiste.
        res = await _fila()
        f = await _foto()
        check(res == {"accion": "desistido"} and f["resultado"] == "desistido" and f["fecha_archivado"] is not None,
              "control: foto vigente -> desistido", f"{res} {f}")
    finally:
        await ejecutar("UPDATE tipo_tramite_estado SET espera_iniciador = :v WHERE id_tipo_tramite_estado = :e",
                       v=bool(est["esp"]), e=est["e"])
        await _limpiar_avisos_pedido(idt)
        await _limpiar_tramite_completo(idt)


async def test_tope_cuerpo_ids_no_canonicos(c: httpx.AsyncClient, ha: dict) -> None:
    print("[35] Tope del cuerpo: todo POST bajo /publico/tramites, también con ids no canónicos")
    hv = await _login_vecino(c)
    mucho = {"Content-Length": str(26 * 1024 * 1024), "Content-Type": "multipart/form-data; boundary=x"}
    for ruta in ("/0012/documentos", "/+12/documentos", "/1_2/documentos", "/00000000012/documentos",
                 "/0012/pedidos/0001/responder", "/12/pedidos/+1/responder", "", "/", "/cualquier/cosa",
                 "%0A", "/12%0A/documentos", "/12/pedidos/1%0A/responder"):
        r = await c.post(f"{BASE_PUB}{ruta}", headers={**hv, **mucho}, content=b"--x--")
        check(r.status_code == 413, f"POST {BASE_PUB}{ruta} con Content-Length sobre el tope: 413", f"{r.status_code} {r.text[:100]}")
    # Debajo del tope el pedido llega al handler (no lo frena el middleware).
    r = await c.post(f"{BASE_PUB}/0012/documentos", headers=hv, data={"documentos": "[1]"},
                     files=[("archivos", ("a.png", PNG, "image/png"))])
    check(r.status_code not in (411, 413), "debajo del tope: lo responde el handler", f"{r.status_code}")
    r = await c.get(f"{BASE_PUB}/tipos", headers=hv)
    check(r.status_code == 200, "un GET del prefijo no se topa", f"{r.status_code}")


async def test_documentos_tramite_cerrado_409(c: httpx.AsyncClient, ha: dict) -> None:
    print("[36] Subir documentos del paso a un trámite final o archivado: 409 y nada subido")
    hv = await _login_vecino(c)
    a, _na = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke docs archivado")
    f, _nf = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke docs final")
    try:
        await ejecutar("UPDATE tramite SET fecha_archivado = NOW() WHERE id_tramite = :t", t=a)
        fin = await _estados_finales(f)
        check(bool(fin), "el tipo tiene un estado final")
        if fin:
            await ejecutar("UPDATE tramite SET id_tipo_tramite_estado_actual = :e WHERE id_tramite = :t", e=fin[0]["e"], t=f)
        for idt, nombre in ((a, "archivado"), (f, "en estado final")):
            SUBIDOS.clear()
            n = (await q1("SELECT count(*) AS n FROM tramite_documento WHERE id_tramite = :t", t=idt))["n"]
            r = await c.post(f"{BASE_PUB}/{idt}/documentos", headers=hv, data={"documentos": "[1]"},
                             files=[("archivos", ("a.png", PNG, "image/png"))])
            check(r.status_code == 409 and "ya terminó" in r.text, f"trámite {nombre}: 409", f"{r.status_code} {r.text[:150]}")
            check(not SUBIDOS and (await q1("SELECT count(*) AS n FROM tramite_documento WHERE id_tramite = :t", t=idt))["n"] == n,
                  f"trámite {nombre}: nada subido ni filas nuevas", str(SUBIDOS))
    finally:
        for i in (a, f):
            await _limpiar_tramite_completo(i)


async def test_descarga_nombre_no_latin1(c: httpx.AsyncClient, ha: dict) -> None:
    print("[37] Descarga del portal: Content-Disposition RFC 5987 con un nombre no latin-1 y nosniff")
    from urllib.parse import unquote
    from app.services.tramites import documentos as svc_docs_mod
    mun = await _municipio_base()
    hv = await _login_vecino(c)
    idt, _ = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke descarga nombre")
    nombre = 'Fachada ñ € "uno".pdf'
    doc = await ejecutar(
        "INSERT INTO tramite_documento (id_tramite, nombre, nombre_archivo_original, storage_path, mime_type, tamano_bytes, "
        "hash_sha256, posicion_orden, id_agente_subio, id_ciudadano_subio, id_municipio) "
        "VALUES (:t, 'Fachada', :n, 'smoke/f.pdf', 'application/pdf', 3, 'h', 1, NULL, :c, :m) RETURNING id_tramite_documento AS id",
        t=idt, n=nombre, c=ID_CIUDADANO, m=mun)
    original = svc_docs_mod.descargar_bytes
    svc_docs_mod.descargar_bytes = _descargar_falso
    try:
        r = await c.get(f"{BASE_PUB}/{idt}/documentos/{doc['id']}/contenido", headers=hv)
        cd = r.headers.get("content-disposition", "")
        check(r.status_code == 200 and r.content == CONTENIDO_FALSO, "descarga: 200 con el binario", f"{r.status_code} {r.text[:120]}")
        check("filename*=UTF-8''" in cd and unquote(cd.split("filename*=UTF-8''", 1)[1]) == nombre,
              "filename* lleva el nombre exacto (ñ y €) percent-encoded", cd)
        check(cd.startswith("inline; filename=\"") and cd.split('filename="', 1)[1].split('"', 1)[0].isascii(),
              "filename= de respaldo en ASCII", cd)
        check(r.headers.get("x-content-type-options") == "nosniff", "X-Content-Type-Options: nosniff", str(dict(r.headers)))
        # La misma descarga desde el backoffice (antes armaba el header crudo y daba 500 con «€»).
        r = await c.get(f"/api/v1/tramites/{idt}/documentos/{doc['id']}/contenido", headers=ha)
        cd = r.headers.get("content-disposition", "")
        check(r.status_code == 200 and r.content == CONTENIDO_FALSO, "backoffice: descarga 200 con el binario",
              f"{r.status_code} {r.text[:120]}")
        check("filename*=UTF-8''" in cd and unquote(cd.split("filename*=UTF-8''", 1)[1]) == nombre
              and cd.split('filename="', 1)[1].split('"', 1)[0].isascii(),
              "backoffice: filename* con el nombre exacto y respaldo ASCII", cd)
        check(r.headers.get("x-content-type-options") == "nosniff", "backoffice: nosniff", str(dict(r.headers)))
    finally:
        svc_docs_mod.descargar_bytes = original
        await _limpiar_tramite_completo(idt)


async def test_visto_admin_sin_agente(c: httpx.AsyncClient, ha: dict) -> None:
    print("[38] /visto de un administrador sin agente vinculado: 204 sin escribir")
    mun = await _municipio_base()
    hv = await _login_vecino(c)
    idt, numero = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke visto admin sin agente")
    adm = await _usuario_fixture(mun, 1, con_agente=False)
    try:
        r = await _pedir(c, ha, numero, pide_archivo=False)
        idp = r.json()["pedidos"][0]["id_tramite_pedido"]
        r = await c.post(f"{BASE_PUB}/{idt}/pedidos/{idp}/responder", headers=hv, data={"texto": "Respuesta para ver"})
        check(r.status_code == 200, "respuesta del vecino", f"{r.status_code} {r.text[:150]}")
        h = await _login_fixture(c, adm)
        r = await c.post(f"{BASE_BO}/{numero}/pedidos/{idp}/visto", headers=h)
        check(r.status_code == 204, "admin sin agente: 204 (no 403)", f"{r.status_code} {r.text[:150]}")
        p = await q1("SELECT respuesta_vista_en FROM tramite_pedido_iniciador WHERE id_tramite_pedido = :p", p=idp)
        check(p["respuesta_vista_en"] is None, "admin sin agente: no marca la respuesta como vista", str(p))
        r = await c.post(f"{BASE_BO}/NO-EXISTE-999/pedidos/{idp}/visto", headers=h)
        check(r.status_code == 404, "admin sin agente, trámite inexistente: 404", f"{r.status_code}")
    finally:
        await _borrar_usuario_fixture(adm)
        await _limpiar_avisos_pedido(idt)
        await _limpiar_tramite_completo(idt)


async def test_cancelar_pedido_orden_de_locks(c: httpx.AsyncClient, ha: dict) -> None:
    print("[39] Cancelar desde el backoffice toma el trámite antes que el pedido (sin deadlock con el cron)")
    idt, numero = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke orden de locks")
    try:
        r = await _pedir(c, ha, numero, pide_archivo=False)
        idp = r.json()["pedidos"][0]["id_tramite_pedido"]
        async with AsyncSessionLocal() as cron:
            # El "cron" toma el trámite como lo hace la función por fila...
            await cron.execute(text("SET LOCAL lock_timeout = '5s'"))
            await cron.execute(text("SELECT 1 FROM tramite WHERE id_tramite = :t FOR UPDATE"), {"t": idt})
            # ...mientras el agente cancela: con el orden correcto la cancelación espera en el trámite
            # sin haber tocado el pedido.
            tarea = asyncio.create_task(c.post(f"{BASE_BO}/{numero}/pedidos/{idp}/cancelar", headers=ha,
                                               json={"motivo": "Cancelado en carrera"}))
            await asyncio.sleep(1.5)
            check(not tarea.done(), "la cancelación espera el lock del trámite")
            try:
                fila = (await cron.execute(text(
                    "SELECT estado FROM tramite_pedido_iniciador WHERE id_tramite_pedido = :p FOR UPDATE"),
                    {"p": idp})).first()
                ok_lock = fila is not None and fila[0] == "abierto"
            except Exception as e:  # noqa: BLE001 — deadlock (40P01) o lock_timeout si el orden fuera otro
                ok_lock = False
                print("    (lock del pedido falló:", type(e).__name__, str(e).splitlines()[0][:120], ")")
            check(ok_lock, "el cron toma el pedido sin esperar ni deadlock (sigue abierto)")
            if ok_lock:
                await cron.commit()
            else:
                await cron.rollback()
        r = await tarea
        check(r.status_code == 200 and r.json()["pedidos"][0]["estado"] == "cancelado",
              "la cancelación termina bien después (200)", f"{r.status_code} {r.text[:150]}")
    finally:
        await _limpiar_avisos_pedido(idt)
        await _limpiar_tramite_completo(idt)


async def test_espera_congelada_si_el_vecino_subio(c: httpx.AsyncClient, ha: dict) -> None:
    print("[40] Timer de espera_iniciador: si el vecino ya subió documentos en el estado, no avanza")
    mun = await _municipio_base()
    cfg = await _cfg_desistimiento(mun)
    idt, _numero = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke espera congelada")
    est = await q1("SELECT t.id_tipo_tramite_estado_actual AS e, e.espera_iniciador AS esp FROM tramite t "
                   "JOIN tipo_tramite_estado e ON e.id_tipo_tramite_estado = t.id_tipo_tramite_estado_actual "
                   "WHERE t.id_tramite = :t", t=idt)
    id_agente = (await q1("SELECT id_agente FROM agentes WHERE id_municipio = :m AND activo = TRUE LIMIT 1", m=mun))["id_agente"]

    async def _fila() -> Optional[dict]:
        async with AsyncSessionLocal() as s:
            return await _ciclo_vida.procesar_desistimiento_tramite(s, idt, cfg)

    async def _foto() -> dict:
        return await q1("SELECT resultado, fecha_archivado, desist_aviso_nivel AS nivel FROM tramite WHERE id_tramite = :t", t=idt)

    async def _doc(alta_sql: str, vecino: bool) -> None:
        await ejecutar(
            "INSERT INTO tramite_documento (id_tramite, nombre, nombre_archivo_original, storage_path, mime_type, "
            "tamano_bytes, hash_sha256, posicion_orden, id_agente_subio, id_ciudadano_subio, id_municipio, fecha_alta) "
            f"VALUES (:t, 'Doc', 'doc.pdf', 'smoke/doc.pdf', 'application/pdf', 3, 'h', 1, :ag, :ci, :m, {alta_sql}) "
            "RETURNING id_tramite_documento AS id",
            t=idt, ag=None if vecino else id_agente, ci=ID_CIUDADANO if vecino else None, m=mun)

    async def _reiniciar() -> None:
        await ejecutar("DELETE FROM tramite_documento WHERE id_tramite = :t", t=idt)
        await ejecutar("UPDATE tramite SET desist_aviso_nivel = 0, desist_aviso_en = NULL, resultado = 'pendiente', "
                       "fecha_archivado = NULL, fecha_entrada_estado_actual = NOW() - INTERVAL '400 days' "
                       "WHERE id_tramite = :t", t=idt)
    try:
        await ejecutar("UPDATE tipo_tramite_estado SET espera_iniciador = TRUE WHERE id_tipo_tramite_estado = :e", e=est["e"])
        await ejecutar("UPDATE tramite SET fecha_alta = NOW() - INTERVAL '400 days' WHERE id_tramite = :t", t=idt)
        casos = [("sin documento del vecino (control)", None, False, True),
                 ("documento del vecino subido después de entrar al estado", "NOW() - INTERVAL '1 day'", True, False),
                 ("documento del vecino de ANTES de entrar al estado", "NOW() - INTERVAL '500 days'", True, True),
                 ("documento subido por un agente", "NOW() - INTERVAL '1 day'", False, True)]
        for nombre, alta, vecino, avisa in casos:
            await _reiniciar()
            if alta:
                await _doc(alta, vecino)
            antes, movs, avisos = await _foto(), await _movs_timer(idt), await _avisos_bandeja(idt)
            MAILS.clear()
            res = await _fila()
            if avisa:
                check(res is not None and res.get("accion") == "aviso" and (await _foto())["nivel"] == 1,
                      f"{nombre}: el timer avisa", f"{res} {await _foto()}")
            else:
                check(res is None and await _foto() == antes and await _movs_timer(idt) == movs
                      and await _avisos_bandeja(idt) == avisos and not MAILS,
                      f"{nombre}: no escribe nada (ni movimiento, ni aviso, ni nivel)", f"{res} {antes} -> {await _foto()}")
    finally:
        await ejecutar("UPDATE tipo_tramite_estado SET espera_iniciador = :v WHERE id_tipo_tramite_estado = :e",
                       v=bool(est["esp"]), e=est["e"])
        await _limpiar_avisos_pedido(idt)
        await _limpiar_tramite_completo(idt)


async def test_cerrar_atraso_cancela_pedido(c: httpx.AsyncClient, ha: dict) -> None:
    print("[38] El cierre de atrasos del generador demo cancela el pedido abierto del trámite que cierra")
    from datetime import datetime, timezone
    from app.services import demo_tramites
    idt, numero = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke cierre de atraso con pedido")
    try:
        await _pedir(c, ha, numero, pide_archivo=False)
        # Todo en el año 2000: con `ahora` en marzo de 2000, el cierre de atrasos solo ve este trámite.
        await ejecutar("UPDATE tramite SET fecha_alta = '2000-01-01', fecha_entrada_estado_actual = '2000-01-01', "
                       "fecha_modificacion = '2000-01-01' WHERE id_tramite = :t", t=idt)
        await ejecutar("UPDATE tramite_movimiento SET fecha_alta = '2000-01-01' WHERE id_tramite = :t", t=idt)
        await ejecutar("UPDATE tramite_pedido_iniciador SET fecha_pedido = '2000-01-02' WHERE id_tramite = :t", t=idt)
        async with AsyncSessionLocal() as s:
            res = await demo_tramites.cerrar_atraso_tramites(
                s, dias=21, aplicar=True, incluir_no_demo=True, semilla=7,
                ahora=datetime(2000, 3, 1, tzinfo=timezone.utc))
        t = await q1("SELECT resultado, e.es_final FROM tramite tr JOIN tipo_tramite_estado e "
                     "ON e.id_tipo_tramite_estado = tr.id_tipo_tramite_estado_actual WHERE tr.id_tramite = :t", t=idt)
        check(t is not None and (t["es_final"] or t["resultado"] != "pendiente"), "el cierre de atrasos cerró el trámite",
              f"{t} {str(res)[:200]}")
        await _chequear_cierre(idt, "El trámite terminó", "cierre de atraso demo")
    finally:
        await _limpiar_avisos_pedido(idt)
        await _limpiar_tramite_completo(idt)


async def test_tipo_expone_validacion(c: httpx.AsyncClient, ha: dict) -> None:
    print("[39] El detalle del tipo para el portal trae la validación de cada campo")
    mun = await _municipio_base()
    tipo = await _tipo_poda(mun)
    hv = await _login_vecino(c)
    campo = await q1(
        "SELECT c.id_tipo_tramite_campo AS id, c.nombre_interno AS n, c.validacion_jsonb AS v FROM tipo_tramite_campo c "
        "JOIN tipo_tramite tt ON tt.id_version_publicada = c.id_tipo_tramite_version "
        "WHERE tt.id_tipo_tramite = :t AND c.activo AND c.tipo_dato IN ('texto', 'texto_largo') "
        "ORDER BY c.orden LIMIT 1", t=tipo["id_tipo_tramite"]) if tipo else None
    if not campo:
        check(False, "datos de partida (poda-arbol con un campo de texto)")
        return
    import json as _j
    try:
        await ejecutar("UPDATE tipo_tramite_campo SET validacion_jsonb = CAST(:v AS jsonb) WHERE id_tipo_tramite_campo = :i",
                       v=_j.dumps({"min": 10}), i=campo["id"])
        r = await c.get(f"/api/v1/publico/tramites/tipos/{tipo['id_tipo_tramite']}", headers=hv)
        campos = {x["nombre_interno"]: x for x in r.json().get("campos", [])} if r.status_code == 200 else {}
        check(campos.get(campo["n"], {}).get("validacion") == {"min": 10}, "el campo trae su validación",
              f"{r.status_code} {campos.get(campo['n'])}")
        otros = [x for k, x in campos.items() if k != campo["n"]]
        check(all("validacion" in x for x in otros), "los demás campos traen la clave (null si no tienen)", str(otros)[:200])
    finally:
        await ejecutar("UPDATE tipo_tramite_campo SET validacion_jsonb = CAST(:v AS jsonb) WHERE id_tipo_tramite_campo = :i",
                       v=_j.dumps(campo["v"]) if campo["v"] is not None else None, i=campo["id"])


async def test_aviso_tramite_url(c: httpx.AsyncClient, ha: dict) -> None:
    print("[40] Los avisos de trámites al vecino (bandeja y push) abren el trámite en la app")
    from app.services import push as _push
    pushes: list[dict] = []
    original = _push.enviar_push_ciudadano

    async def _capturar_push(id_ciudadano, titulo, cuerpo, url=None, **kw):
        pushes.append({"id": id_ciudadano, "url": url})
        return 0

    _push.enviar_push_ciudadano = _capturar_push
    idt, numero = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke url del aviso")
    try:
        r = await _pedir(c, ha, numero, pide_archivo=False)
        check(r.status_code == 200, "pedido creado", f"{r.status_code} {r.text[:120]}")
        av = await q1("SELECT url_destino AS u FROM ciudadano_aviso WHERE tipo = 'tramite_pedido' AND recurso_tipo = 'tramite' "
                      "AND recurso_id = :t ORDER BY 1 DESC LIMIT 1", t=idt)
        check(av is not None and av["u"] == f"/tramites/{idt}", "el aviso de la bandeja lleva a /tramites/{id}", str(av))
        check(any(p["url"] == f"/tramites/{idt}" for p in pushes), "el push lleva a /tramites/{id}", str(pushes))
    finally:
        _push.enviar_push_ciudadano = original
        await _limpiar_avisos_pedido(idt)
        await _limpiar_tramite_completo(idt)


async def test_cerrado_no_pide_documentos(c: httpx.AsyncClient, ha: dict) -> None:
    print("[41] Un trámite desistido no le pide documentos al vecino (detalle y lista)")
    hv = await _login_vecino(c)
    idt, numero = await _tramite_ventanilla(c, ha, ID_CIUDADANO, "Smoke cerrado sin documentos del paso")
    try:
        r = await c.get(f"{BASE_PUB}/{idt}", headers=hv)
        antes = r.json() if r.status_code == 200 else {}
        check(len(antes.get("documentos_del_paso", [])) >= 1, "abierto: el paso pide su documento", str(antes)[:200])
        r = await c.post(f"{BASE_BO}/{numero}/resultado", headers=ha, json={"resultado": "desistido", "comentario": "smoke"})
        check(r.status_code == 200, "desistido manual: 200", f"{r.status_code} {r.text[:150]}")
        d = (await c.get(f"{BASE_PUB}/{idt}", headers=hv)).json()
        check(d.get("documentos_del_paso") == [] and d.get("documentos_pendientes") == 0,
              "desistido: el detalle no pide documentos", str({k: d.get(k) for k in ("documentos_del_paso", "documentos_pendientes")}))
        fila = next((x for x in (await c.get(BASE_PUB, headers=hv)).json() if x["id_tramite"] == idt), None)
        check(fila is not None and fila["documentos_pendientes"] == 0, "desistido: la lista no marca documentos pendientes", str(fila))
    finally:
        await _limpiar_avisos_pedido(idt)
        await _limpiar_tramite_completo(idt)


async def test_tipo_con_campo_no_soportado_no_se_ofrece(c: httpx.AsyncClient, ha: dict) -> None:
    print("[42] Un tipo con un campo que el portal no sabe pedir (fecha_hora, archivo, ciudadano...) no se ofrece")
    mun = await _municipio_base()
    tipo = await _tipo_poda(mun)
    hv = await _login_vecino(c)
    campo = await q1(
        "SELECT c.id_tipo_tramite_campo AS id, c.tipo_dato AS td FROM tipo_tramite_campo c "
        "JOIN tipo_tramite tt ON tt.id_version_publicada = c.id_tipo_tramite_version "
        "WHERE tt.id_tipo_tramite = :t AND c.activo AND NOT c.obligatorio ORDER BY c.orden LIMIT 1",
        t=tipo["id_tipo_tramite"]) if tipo else None
    if not campo:
        check(False, "datos de partida (poda-arbol con un campo opcional)")
        return
    try:
        await ejecutar("UPDATE tipo_tramite_campo SET tipo_dato = 'fecha_hora' WHERE id_tipo_tramite_campo = :i", i=campo["id"])
        ids = [x["id_tipo_tramite"] for x in (await c.get("/api/v1/publico/tramites/tipos", headers=hv)).json()]
        check(tipo["id_tipo_tramite"] not in ids, "con un campo fecha_hora el tipo no aparece", str(ids))
        r = await c.get(f"/api/v1/publico/tramites/tipos/{tipo['id_tipo_tramite']}", headers=hv)
        check(r.status_code == 404, "y su detalle da 404", str(r.status_code))
        r = await c.get("/api/v1/admin/tramites/tipos", headers=ha)
        item = next((x for x in r.json().get("items", []) if x["id_tipo_tramite"] == tipo["id_tipo_tramite"]), {})
        motivo = item.get("portal_motivo_excluido") or ""
        check("la app no sabe pedir estos campos" in motivo, "el configurador dice por qué no se ofrece", motivo)
    finally:
        await ejecutar("UPDATE tipo_tramite_campo SET tipo_dato = :td WHERE id_tipo_tramite_campo = :i", td=campo["td"], i=campo["id"])
    ids = [x["id_tipo_tramite"] for x in (await c.get("/api/v1/publico/tramites/tipos", headers=hv)).json()]
    check(tipo["id_tipo_tramite"] in ids, "restaurado: el tipo vuelve a aparecer", str(ids))
    r = await c.get("/api/v1/admin/tramites/tipos", headers=ha)
    item = next((x for x in r.json().get("items", []) if x["id_tipo_tramite"] == tipo["id_tipo_tramite"]), {})
    check(item.get("portal_motivo_excluido") is None, "restaurado: el configurador ya no marca motivo",
          str(item.get("portal_motivo_excluido")))


async def test_citar_texto_pedido(c: httpx.AsyncClient, ha: dict) -> None:
    print("[43] El pedido citado en un aviso no repite el punto final y el aviso interno lo recorta")
    from app.services.notificaciones import citar_texto
    from app.services.tramites.ciclo_vida import _texto_aviso_pedido
    _, cuerpo = _texto_aviso_pedido(1, {"numero_expediente": "X-1", "tipo_nombre": "Poda"}, "Traé el DNI.  ", 10, 72)
    check("DNI.." not in cuerpo and "DNI. Respondelo" in cuerpo, "aviso al vecino con un solo punto", cuerpo)
    largo = citar_texto("palabra " * 60, 120)
    check(len(largo) <= 120 and largo.endswith("…"), "cita recortada a 120 con «…»", largo)
    check(citar_texto("  hola   mundo . ") == "hola mundo", "espacios y punto final fuera", citar_texto("  hola   mundo . "))


CASOS = [test_backoffice_ve_movimientos_del_vecino, test_backoffice_alta_sin_cuenta_422,
         test_backoffice_alta_con_cuenta_201,
         test_identidad_validar_y_revocar, test_identidad_en_perfil_publico, test_backoffice_alta_exige_identidad,
         test_tipos_ofrecidos, test_alta_vecino_ok, test_alta_sin_documento_obligatorio_422,
         test_alta_atomica_sin_restos, test_alta_campo_invalido_422, test_alta_exige_identidad_portal,
         test_alta_limites_de_carga, test_alta_filtra_datos_ajenos,
         test_mis_tramites_incluye_ventanilla, test_detalle_sin_datos_internos, test_ajeno_404,
         test_documento_del_paso, test_resumen_tramites,
         test_estado_oculto_para_iniciador,
         test_pedido_ciclo_completo, test_pedido_reglas_422, test_respuesta_doble_409, test_cancelar_pedido,
         test_ajeno_404_pedido, test_visto_con_guard, test_pedido_se_cancela_al_cerrar,
         test_pedido_escalones, test_pedido_desistimiento_apagado, test_cambio_de_estado_no_reinicia,
         test_pedido_en_tramite_cerrado_no_avisa, test_admin_ofrecer_al_vecino,
         test_cron_pedido_foto_fresca, test_cron_espera_foto_fresca, test_tope_cuerpo_ids_no_canonicos,
         test_documentos_tramite_cerrado_409, test_descarga_nombre_no_latin1, test_visto_admin_sin_agente,
         test_cancelar_pedido_orden_de_locks, test_espera_congelada_si_el_vecino_subio,
         test_cerrar_atraso_cancela_pedido, test_tipo_expone_validacion,
         test_aviso_tramite_url, test_cerrado_no_pide_documentos,
         test_tipo_con_campo_no_soportado_no_se_ofrece, test_citar_texto_pedido]


async def main() -> int:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://smoke.local", timeout=90) as c:
        ha = await login_admin(c)
        solo = [x for x in os.environ.get("SMOKE_CASOS", "").split(",") if x]  # p. ej. SMOKE_CASOS=test_x,test_y
        for caso in CASOS:
            if solo and caso.__name__ not in solo:
                continue
            await caso(c, ha)
    print(f"\n{OK}/{OK + FAIL} OK")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
