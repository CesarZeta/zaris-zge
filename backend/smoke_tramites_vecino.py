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
    await ejecutar("INSERT INTO tipo_tramite_campo (id_tipo_tramite_version, nombre_interno, etiqueta, tipo_dato, obligatorio, orden, id_municipio) "
                   "VALUES (:v, 'archivo_falso', 'Archivo falso', 'archivo', FALSE, 99, :m)", v=ver, m=mun)
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


CASOS = [test_backoffice_ve_movimientos_del_vecino, test_backoffice_alta_sin_cuenta_422,
         test_backoffice_alta_con_cuenta_201,
         test_identidad_validar_y_revocar, test_identidad_en_perfil_publico, test_backoffice_alta_exige_identidad,
         test_tipos_ofrecidos, test_alta_vecino_ok, test_alta_sin_documento_obligatorio_422,
         test_alta_atomica_sin_restos, test_alta_campo_invalido_422, test_alta_exige_identidad_portal,
         test_alta_limites_de_carga, test_alta_filtra_datos_ajenos,
         test_mis_tramites_incluye_ventanilla, test_detalle_sin_datos_internos, test_ajeno_404,
         test_documento_del_paso, test_resumen_tramites,
         test_estado_oculto_para_iniciador]


async def main() -> int:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://smoke.local", timeout=90) as c:
        ha = await login_admin(c)
        for caso in CASOS:
            await caso(c, ha)
    print(f"\n{OK}/{OK + FAIL} OK")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
