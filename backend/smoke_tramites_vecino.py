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


CASOS = [test_backoffice_ve_movimientos_del_vecino, test_backoffice_alta_sin_cuenta_422,
         test_backoffice_alta_con_cuenta_201,
         test_identidad_validar_y_revocar, test_identidad_en_perfil_publico, test_backoffice_alta_exige_identidad]


async def main() -> int:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://smoke.local", timeout=90) as c:
        ha = await login_admin(c)
        for caso in CASOS:
            await caso(c, ha)
    print(f"\n{OK}/{OK + FAIL} OK")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
