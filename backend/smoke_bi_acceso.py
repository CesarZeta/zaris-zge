# -*- coding: utf-8 -*-
"""
Smoke in-process — acceso a Datos (Vecino 360, fase 1): los tres routers de /bi exigen el módulo `bi`.

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_bi_acceso.py

SOLO LOCAL. Correr con DB_BARRERA=true y con false. Solo lee, salvo las excepciones de módulo que pone y repone.
"""
import asyncio
import os
import sys

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

from app.core.auth import create_access_token, crear_token_ciudadano  # noqa: E402
from app.core.sistema import SesionSistema  # noqa: E402
from app.main import app  # noqa: E402

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


def rutas_bi() -> list[str]:
    """Todas las rutas GET de /bi, leídas de OpenAPI: una ruta nueva entra sola en la prueba."""
    return sorted(p for p, m in app.openapi()["paths"].items() if p.startswith("/api/v1/bi/") and "get" in m)


async def main() -> None:
    rutas = [r for r in rutas_bi() if "{" not in r]
    check("los tres tableros están en la prueba", len(rutas) > 20 and all(
        any(r.startswith(x) for r in rutas) for x in ("/api/v1/bi/ejecutivo/", "/api/v1/bi/atencion/")), len(rutas))
    minimo = (await sql("SELECT min_nivel_acceso AS n FROM municipio_modulo WHERE id_municipio = 1 "
                        "AND modulo_codigo = 'bi' AND habilitado"))[0]["n"]
    cuentas = {f["nivel_acceso"]: f["id_usuario"] for f in await sql("""
        SELECT DISTINCT ON (u.nivel_acceso) u.nivel_acceso, u.id_usuario FROM usuarios u
         WHERE u.id_municipio = 1 AND u.activo AND NOT COALESCE(u.debe_cambiar_password, FALSE)
           AND NOT EXISTS (SELECT 1 FROM usuario_modulos x WHERE x.id_usuario = u.id_usuario
                              AND x.modulo_codigo = 'bi' AND x.activo)
         ORDER BY u.nivel_acceso, u.id_usuario""")}

    def h(uid: int) -> dict:
        return {"Authorization": "Bearer " + create_access_token({"sub": str(uid), "mun": 1, "sf": True})}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=120) as c:
        print("1. Sin sesión y con sesión de vecino")
        otros = {r: (await c.get(r)).status_code for r in rutas}
        check("sin sesión: 401 en todas", set(otros.values()) == {401}, otros)
        hv = {"Authorization": "Bearer " + crear_token_ciudadano(3, 1)}
        otros = {r: (await c.get(r, headers=hv)).status_code for r in rutas}
        check("con sesión de vecino: 401 en todas", set(otros.values()) == {401}, otros)

        print(f"2. Por nivel (mínimo del municipio: {minimo})")
        for nivel in sorted(cuentas):
            res = {r: (await c.get(r, headers=h(cuentas[nivel]))).status_code for r in rutas}
            if nivel <= minimo:
                check(f"nivel {nivel}: entra en todas", not any(s in (401, 403) or s >= 500 for s in res.values()),
                      {r: s for r, s in res.items() if s in (401, 403) or s >= 500})
            else:
                check(f"nivel {nivel}: 403 en todas", set(res.values()) == {403},
                      {r: s for r, s in res.items() if s != 403})

        print("3. Excepciones por usuario")
        bajo, admin = cuentas[max(cuentas)], cuentas[1]
        muestra = [next(r for r in rutas if r.startswith(x)) for x in ("/api/v1/bi/ejecutivo/", "/api/v1/bi/atencion/")] + [
            next(r for r in rutas if "/ejecutivo/" not in r and "/atencion/" not in r)]

        async def excepcion(uid: int, permitido: bool):
            await sql("INSERT INTO usuario_modulos (id_usuario, modulo_codigo, permitido, activo, id_municipio) "
                      "VALUES (:u, 'bi', :p, TRUE, 1)", u=uid, p=permitido)

        async def quitar(uid: int):
            await sql("DELETE FROM usuario_modulos WHERE id_usuario = :u AND modulo_codigo = 'bi' AND id_municipio = 1", u=uid)
        try:
            await excepcion(bajo, True)
            res = {r: (await c.get(r, headers=h(bajo))).status_code for r in muestra}
            check("habilitado a mano: entra", not any(s in (401, 403) for s in res.values()), res)
            await excepcion(admin, False)
            res = {r: (await c.get(r, headers=h(admin))).status_code for r in muestra}
            check("administrador sin el módulo: 403", set(res.values()) == {403}, res)
        finally:
            await quitar(bajo)
            await quitar(admin)

        print("4. El inicio sigue igual para todos")
        for nivel in sorted(cuentas):
            r = await c.get("/api/v1/dashboard/resumen", headers=h(cuentas[nivel]))
            check(f"nivel {nivel}: el inicio responde", r.status_code == 200, r.status_code)


asyncio.run(main())
print(f"\n{sum(RES)}/{len(RES)} OK (barrera={settings.DB_BARRERA})")
sys.exit(0 if RES and all(RES) else 1)
