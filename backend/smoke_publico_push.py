# -*- coding: utf-8 -*-
"""
Smoke in-process — suscripciones push del vecino (`/api/v1/publico/push/*`).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_publico_push.py

SOLO LOCAL. Usa dos vecinos con cuenta, no envía ningún push y deja todo como estaba.
Correr con DB_BARRERA=true y false.
"""
import asyncio
import os
import sys
import uuid

import httpx

os.environ.setdefault("ENV_FILE", ".env.local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402

if "zaris_dev" not in settings.ASYNC_DATABASE_URI:
    sys.exit("ABORT: este smoke es SOLO LOCAL (la DB configurada no es zaris_dev).")
settings.RESEND_API_KEY = ""

from app.core.auth import crear_token_ciudadano  # noqa: E402
from app.core.sistema import SesionSistema  # noqa: E402
from app.main import app  # noqa: E402

OK = FAIL = 0
MARCA = f"https://push.invalid/{uuid.uuid4()}"


def check(cond: bool, nombre: str, detalle: object = "") -> None:
    global OK, FAIL
    OK, FAIL = (OK + 1, FAIL) if cond else (OK, FAIL + 1)
    print(f"  {'OK  ' if cond else 'FAIL'} {nombre} {'' if cond else detalle}")


async def filas(sql: str, **p) -> list[dict]:
    async with SesionSistema() as s:
        res = await s.execute(text(sql), p)
        out = [dict(r) for r in res.mappings().all()] if res.returns_rows else []
        await s.commit()
        return out


async def activas(id_c: int) -> set[str]:
    return {f["endpoint"].removeprefix(MARCA) for f in await filas(
        "SELECT endpoint FROM ciudadano_push_subscription"
        " WHERE id_ciudadano = :c AND activo AND endpoint LIKE :m", c=id_c, m=MARCA + "%")}


async def canal(id_c: int) -> bool:
    return (await filas("SELECT canal_push FROM ciudadano_canal_preferido WHERE id_ciudadano = :c", c=id_c))[0]["canal_push"]


async def main() -> None:
    vecinos = await filas("""
        SELECT c.id_ciudadano, c.id_municipio, p.canal_push FROM ciudadanos c
          JOIN ciudadano_credencial k USING (id_ciudadano)
          LEFT JOIN ciudadano_canal_preferido p USING (id_ciudadano)
         WHERE c.activo AND k.activo AND k.activado AND c.id_municipio = 1
           AND NOT EXISTS (SELECT 1 FROM ciudadano_push_subscription s
                            WHERE s.id_ciudadano = c.id_ciudadano AND s.activo)
         ORDER BY 1 LIMIT 2""")
    assert len(vecinos) == 2, "hacen falta dos vecinos activos con cuenta en zaris_dev"
    a, b = (v["id_ciudadano"] for v in vecinos)

    def h(id_c: int) -> dict:
        return {"Authorization": f"Bearer {crear_token_ciudadano(id_c, vecinos[0]['id_municipio'])}"}

    def body(dispositivo: str) -> dict:
        return {"endpoint": MARCA + dispositivo, "p256dh": "x" * 40, "auth": "y" * 20}

    P = "/api/v1/publico/push"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        try:
            r = await c.post(f"{P}/subscribe", json=body("/tel"))
            check(r.status_code == 401, "sin token: 401", r.status_code)

            r = await c.post(f"{P}/subscribe", json=body("/tel"), headers=h(a))
            check(r.status_code == 201, "A activa en su teléfono", (r.status_code, r.text))
            r = await c.post(f"{P}/subscribe", json=body("/pc"), headers=h(a))
            check(r.status_code == 201 and await activas(a) == {"/tel", "/pc"}, "A activa en su PC")
            check(await canal(a) is True, "el canal de A queda prendido")

            r = await c.post(f"{P}/unsubscribe", json={"endpoint": MARCA + "/pc"}, headers=h(a))
            check(r.status_code == 200 and await activas(a) == {"/tel"}, "A apaga la PC: el teléfono sigue", await activas(a))
            check(await canal(a) is True, "y el canal de A sigue prendido")

            r = await c.post(f"{P}/subscribe", json=body("/tel"), headers=h(b))
            check(r.status_code == 201 and await activas(b) == {"/tel"}, "B entra en el teléfono de A")
            check(await activas(a) == set(), "los avisos de A dejan de ir a ese teléfono", await activas(a))

            r = await c.post(f"{P}/unsubscribe", json={"endpoint": MARCA + "/tel"}, headers=h(b))
            check(r.status_code == 200 and await canal(b) is False, "B apaga su único dispositivo: canal apagado")

            r = await c.post(f"{P}/subscribe", json=body("/tel"), headers=h(a))
            check(r.status_code == 201 and await activas(a) == {"/tel"}, "A vuelve a su teléfono: se reactiva")
        finally:
            await filas("DELETE FROM ciudadano_push_subscription WHERE endpoint LIKE :m", m=MARCA + "%")
            for v in vecinos:
                if v["canal_push"] is None:
                    await filas("DELETE FROM ciudadano_canal_preferido WHERE id_ciudadano = :c", c=v["id_ciudadano"])
                else:
                    await filas("UPDATE ciudadano_canal_preferido SET canal_push = :v WHERE id_ciudadano = :c",
                                v=v["canal_push"], c=v["id_ciudadano"])
    print(f"\n{OK} OK, {FAIL} FAIL")
    sys.exit(1 if FAIL else 0)


asyncio.run(main())
