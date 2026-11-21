# -*- coding: utf-8 -*-
"""
Smoke in-process — cancelar un reclamo exige la gestión del reclamo (2026-11-21).

PUT /reclamos/{id}/cancelar pedía solo nivel ≤ 2: un supervisor de otra gestión cancelaba reclamos
ajenos. Ahora usa el mismo guard que el pase a 'Resuelto' (_require_misma_subarea; admin exento).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_reclamo_cancelar_gestion.py

SOLO LOCAL. Crea reclamos de prueba (descripción «smoke cancelar gestión») y los deja cancelados.
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
settings.RESEND_API_KEY = ""

# Preparación y verificación como dueño de la base: no pasa por la barrera (IT-01 F6).
from app.core.sistema import SesionSistema  # noqa: E402
from app.main import app  # noqa: E402

CLAVE = "123456"
RES: list[tuple[str, bool, str]] = []


def check(nombre: str, ok: bool, detalle: str = "") -> None:
    RES.append((nombre, ok, detalle))
    print(f"  {'OK  ' if ok else 'FAIL'} {nombre}{(' — ' + detalle) if detalle and not ok else ''}")


SUPERVISORES = """
    SELECT u.id_usuario, u.email, a.id_subarea
      FROM usuarios u JOIN agentes a ON a.id_usuario = u.id_usuario AND a.activo
     WHERE u.id_municipio = 1 AND u.nivel_acceso = 2 AND u.activo AND u.email IS NOT NULL
       AND NOT COALESCE(u.debe_cambiar_password, FALSE) AND a.id_subarea IS NOT NULL
       AND EXISTS (SELECT 1 FROM tipo_reclamo t WHERE t.id_subarea = a.id_subarea AND t.activo AND t.id_municipio = 1)
     ORDER BY u.id_usuario"""


async def crear_reclamo(db, id_subarea: int) -> int:
    tipo, ciudadano = (await db.execute(text("""
        SELECT (SELECT id_tipo_reclamo FROM tipo_reclamo WHERE id_subarea = :s AND activo AND id_municipio = 1
                 ORDER BY id_tipo_reclamo LIMIT 1),
               (SELECT id_ciudadano FROM ciudadanos WHERE id_municipio = 1 AND activo ORDER BY id_ciudadano LIMIT 1)"""),
        {"s": id_subarea})).one()
    return (await db.execute(text("""
        INSERT INTO reclamos (id_tipo_reclamo, id_ciudadano, descripcion, estado, prioridad, canal_origen, id_municipio)
        VALUES (:t, :c, 'smoke cancelar gestión', 'Sin asignar', 'Media', 'oficio', 1) RETURNING id_reclamo"""),
        {"t": tipo, "c": ciudadano})).scalar()


async def main() -> int:
    async with SesionSistema() as db:
        sups = (await db.execute(text(SUPERVISORES))).all()
        a = sups[0] if sups else None
        b = next((s for s in sups if a and s.id_subarea != a.id_subarea), None)
        admin = (await db.execute(text(
            "SELECT email FROM usuarios WHERE id_municipio = 1 AND nivel_acceso = 1 AND activo AND email IS NOT NULL "
            "ORDER BY id_usuario LIMIT 1"))).scalar()
        if not (a and b and admin):
            sys.exit("Faltan dos supervisores de gestiones distintas o un administrador en zaris_dev.")
        r1 = await crear_reclamo(db, a.id_subarea)
        r2 = await crear_reclamo(db, a.id_subarea)
        await db.commit()
    print(f"Supervisor de la gestión {a.id_subarea}: {a.email} · de otra ({b.id_subarea}): {b.email}")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=60) as c:
        async def token(email: str) -> str:
            r = await c.post("/api/v1/auth/login", json={"identificador": email, "password": CLAVE})
            if r.status_code != 200 or "access_token" not in r.json():
                sys.exit(f"login {email}: {r.status_code} {r.text[:200]}")
            return r.json()["access_token"]

        async def cancelar(tok: str, idr: int) -> httpx.Response:
            return await c.put(f"/api/v1/reclamos/{idr}/cancelar", json={"motivo": "smoke cancelar gestión"},
                               headers={"Authorization": f"Bearer {tok}"})

        async def estado(idr: int) -> str:
            async with SesionSistema() as db:
                return (await db.execute(text("SELECT estado FROM reclamos WHERE id_reclamo = :i"), {"i": idr})).scalar()

        tb, ta, tadm = await token(b.email), await token(a.email), await token(admin)

        r = await cancelar(tb, r1)
        check("otra_gestion_403", r.status_code == 403, f"{r.status_code} {r.text[:200]}")
        check("otra_gestion_mensaje", "misma subárea" in r.text, r.text[:200])
        check("otra_gestion_no_cambia_estado", await estado(r1) == "Sin asignar", await estado(r1))

        r = await cancelar(ta, r1)
        check("misma_gestion_200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
        check("misma_gestion_cancelado", await estado(r1) == "Cancelado", await estado(r1))

        r = await cancelar(tadm, r2)
        check("admin_cualquier_gestion_200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
        check("admin_cancelado", await estado(r2) == "Cancelado", await estado(r2))

        r = await cancelar(tb, 999_999_999)
        check("inexistente_404", r.status_code == 404, f"{r.status_code}")

    fallas = [n for n, ok, _ in RES if not ok]
    print(f"\n{len(RES) - len(fallas)}/{len(RES)} OK" + (f" — FALLARON: {', '.join(fallas)}" if fallas else ""))
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
