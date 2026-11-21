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


CASOS = [test_backoffice_ve_movimientos_del_vecino]


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
