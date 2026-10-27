# -*- coding: utf-8 -*-
"""
Smoke in-process — SLA de los tipos de reclamo en minutos (mig 120) + asignación automática
general del municipio con excepciones por gestión (mig 121).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_sla_asignacion_general.py

SOLO LOCAL: aborta si la DB no es zaris_dev. Corre el app FastAPI real con httpx.ASGITransport;
el mail en MOCK y los avisos de la asignación (push + mail al vecino) capturados: no sale nada.
Reusa los usuarios f112* de smoke_auditoria_reclamos.py (si faltan, correr ese primero). Deja el
SLA del tipo, el flag de la gestión y la clave general como los encontró; los reclamos creados
quedan como demo.

Cubre:
  SLA — PUT del tipo en minutos (deriva sla_dias), 0 → 400 (CHECK), solo sla_dias → 422 (ya no
  se edita), vencimiento del reclamo = alta + minutos, drill-down de Subáreas y catálogo con
  sla_minutos, criterio exacto del BI (_DENTRO_SLA) a cada lado del plazo, endpoints del BI 200.
  Asignación — general prendida + gestión sin excepción → asigna; gestión «asigna a mano» → no;
  general apagada → no; clave inválida o ausente → no (fail-closed); Config → Sistema y el flag
  de Subáreas: admin 200 / supervisor 403; marcador OpenAPI.
"""
import asyncio
import logging
import os
import sys
from typing import Any, Optional

import httpx

os.environ.setdefault("ENV_FILE", ".env.local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402

if "zaris_dev" not in settings.ASYNC_DATABASE_URI:
    sys.exit("ABORT: este smoke es SOLO LOCAL (la DB configurada no es zaris_dev). No corre contra prod.")

settings.RESEND_API_KEY = ""  # mail en MOCK

from app.api.routes.bi import _DENTRO_SLA  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.services import autoasignacion, push  # noqa: E402

AVISOS: list[tuple[str, int]] = []


async def _captura_ot(id_ot: int) -> None:
    AVISOS.append(("ot_asignada", id_ot))


async def _captura_estado(id_reclamo: int, *a, **k) -> None:
    AVISOS.append(("estado_reclamo", id_reclamo))

push.notificar_ot_asignada = _captura_ot          # la asignación no manda push real
push.notificar_estado_reclamo = _captura_estado   # ni mail/push al vecino

logging.getLogger("httpx").setLevel(logging.WARNING)

PWD_DEV = os.environ.get("ZARIS_QA_PASS") or "123456"
ADMIN_EMAIL = "ciudadanovl@municipio.gob.ar"
SUP_EMAIL = "f112supa@municipio.gob.ar"   # supervisor (nivel 2) de la subárea 20
DNI_VECINO = "28547123"
SUB = 20                                   # Calles y veredas (local): tiene un agente f112ag de nivel 4
CLAVE = autoasignacion.CLAVE_ASIGNACION_GENERAL
DESC_GENERAL = ("Asignación automática de reclamos para todo el municipio. Las gestiones marcadas "
                "«Asigna a mano» en Maestros → Subáreas quedan afuera.")  # la de la mig 121b

ok_count = 0
fail_count = 0
fallidos: list[dict] = []


def check(nombre: str, cond: bool, extra: str = "") -> bool:
    global ok_count, fail_count
    if cond:
        ok_count += 1
        print(f"  OK   {nombre} {extra}")
    else:
        fail_count += 1
        print(f"  FAIL {nombre} {extra}")
        fallidos.append({"caso": nombre, "detalle": extra})
    return cond


def short(r: httpx.Response, n: int = 160) -> str:
    return f"({r.status_code}) {r.text[:n]}"


async def q1(sql: str, **params) -> Optional[dict]:
    async with AsyncSessionLocal() as s:
        row = (await s.execute(text(sql), params)).mappings().first()
        return dict(row) if row else None


async def exec_commit(sql: str, **params) -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(text(sql), params)
        await s.commit()


async def set_general(valor: Optional[str]) -> None:
    """valor None = borra la clave (para probar la clave ausente)."""
    if valor is None:
        await exec_commit("DELETE FROM configuracion_general WHERE clave = :c AND id_municipio = 1", c=CLAVE)
        return
    await exec_commit("""
        INSERT INTO configuracion_general (clave, valor, tipo, descripcion, activo, id_municipio)
        SELECT CAST(:c AS varchar), CAST(:v AS text), 'boolean', CAST(:d AS text), TRUE, 1
         WHERE NOT EXISTS (SELECT 1 FROM configuracion_general WHERE clave = CAST(:c AS varchar) AND id_municipio = 1)
    """, c=CLAVE, v=valor, d=DESC_GENERAL)
    await exec_commit("UPDATE configuracion_general SET valor = :v, activo = TRUE WHERE clave = :c AND id_municipio = 1",
                      c=CLAVE, v=valor)


async def main() -> int:
    admin = await q1("SELECT id_usuario FROM usuarios WHERE email = :e AND nivel_acceso = 1 AND activo", e=ADMIN_EMAIL)
    sup = await q1("SELECT id_usuario FROM usuarios WHERE email = :e AND activo", e=SUP_EMAIL)
    vec = await q1("SELECT id_ciudadano FROM ciudadanos WHERE doc_nro = :d AND activo AND id_municipio = 1", d=DNI_VECINO)
    tipo = await q1("SELECT id_tipo_reclamo, sla_minutos, sla_dias FROM tipo_reclamo "
                    "WHERE id_subarea = :s AND activo ORDER BY id_tipo_reclamo LIMIT 1", s=SUB)
    cand = await q1("""SELECT COUNT(*) AS n FROM agentes a JOIN usuarios u ON u.id_usuario = a.id_usuario AND u.activo
                       WHERE a.activo AND a.id_subarea = :s AND u.nivel_acceso = 4 AND NOT a.es_auditor""", s=SUB)
    if not (admin and sup and vec and tipo) or not cand["n"]:
        sys.exit("ABORT: faltan datos locales (admin, f112supa, vecino 28547123, tipo y agente nivel 4 de la "
                 "subárea 20). Correr antes smoke_auditoria_reclamos.py.")
    estado_inicial = {
        "tipo_sla": tipo["sla_minutos"],
        "manual": (await q1("SELECT asignacion_manual FROM subarea WHERE id_subarea = :s", s=SUB))["asignacion_manual"],
        "general": await q1("SELECT valor, descripcion FROM configuracion_general WHERE clave = :c AND id_municipio = 1",
                            c=CLAVE),
    }
    id_tipo = tipo["id_tipo_reclamo"]

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://smoke.local", timeout=60) as c:
            H: dict[str, dict] = {}
            for nombre, email in (("admin", ADMIN_EMAIL), ("sup", SUP_EMAIL)):
                r = await c.post("/api/v1/auth/login", json={"identificador": email, "password": PWD_DEV})
                if not check(f"0. login {nombre}", r.status_code == 200, short(r)):
                    return 1
                H[nombre] = {"Authorization": f"Bearer {r.json()['access_token']}"}
            HA, HS = H["admin"], H["sup"]

            # Que la autoasignación del POST /reclamos no interfiera: la gestión a mano.
            await exec_commit("UPDATE subarea SET asignacion_manual = TRUE WHERE id_subarea = :s", s=SUB)

            async def nuevo_reclamo(desc: str) -> int:
                r = await c.post("/api/v1/reclamos", headers=HA, json={
                    "id_ciudadano": vec["id_ciudadano"], "id_tipo_reclamo": id_tipo, "descripcion": desc,
                    "direccion": "Av. Maipú 2502, Olivos", "canal_origen": "presencial",
                    "latitud": -34.5125, "longitud": -58.4895, "fuente_geolocalizacion": "pin_manual"})
                assert r.status_code in (200, 201), short(r)
                return r.json()["id_reclamo"]

            # ── 1. SLA en minutos (mig 120) ──────────────────────────────────────────
            r = await c.put(f"/api/v1/admin/tipo_reclamo/{id_tipo}", headers=HA, json={"sla_minutos": 240})
            fila = await q1("SELECT sla_minutos, sla_dias FROM tipo_reclamo WHERE id_tipo_reclamo = :t", t=id_tipo)
            check("1a. PUT SLA 4 h → sla_minutos 240 y sla_dias derivado 1",
                  r.status_code == 200 and fila == {"sla_minutos": 240, "sla_dias": 1}, f"{short(r, 80)} {fila}")
            r = await c.put(f"/api/v1/admin/tipo_reclamo/{id_tipo}", headers=HA, json={"sla_minutos": 0})
            check("1b. SLA 0 → 400 (CHECK)", r.status_code == 400, short(r, 120))
            r = await c.put(f"/api/v1/admin/tipo_reclamo/{id_tipo}", headers=HA, json={"sla_dias": 9})
            check("1c. solo sla_dias → 422 (ya no se edita por Maestros)", r.status_code == 422, short(r, 120))

            id_r = await nuevo_reclamo("Smoke 120 — vencimiento en minutos")
            v = await q1("""SELECT EXTRACT(EPOCH FROM (sla_vencimiento - fecha_alta)) / 60 AS min
                            FROM reclamos WHERE id_reclamo = :id""", id=id_r)
            check("1d. vencimiento = alta + 240 min", v and round(float(v["min"])) == 240, str(v))

            r = await c.get(f"/api/v1/admin/subarea/{SUB}/tipos-reclamo", headers=HA)
            t = next((x for x in r.json() if x["id_tipo_reclamo"] == id_tipo), {}) if r.status_code == 200 else {}
            check("1e. drill-down de Subáreas trae sla_minutos", t.get("sla_minutos") == 240, short(r, 80))
            r = await c.get("/api/v1/reclamos/catalogo/tipos", headers=HA, params={"limit": 500})
            t = next((x for x in r.json() if x["id_tipo_reclamo"] == id_tipo), {}) if r.status_code == 200 else {}
            check("1f. catálogo de tipos trae sla_minutos", t.get("sla_minutos") == 240, short(r, 80))

            # Criterio exacto del BI: cerrado a 3 h 59 min → dentro; a 4 h 01 min → fuera.
            id_d, id_f = await nuevo_reclamo("Smoke 120 — cierre dentro"), await nuevo_reclamo("Smoke 120 — cierre fuera")
            await exec_commit("""UPDATE reclamos SET estado = 'Resuelto',
                                   fecha_cierre = fecha_alta + make_interval(mins => :m)
                                 WHERE id_reclamo = :id""", id=id_d, m=239)
            await exec_commit("""UPDATE reclamos SET estado = 'Resuelto',
                                   fecha_cierre = fecha_alta + make_interval(mins => :m)
                                 WHERE id_reclamo = :id""", id=id_f, m=241)
            for id_x, esperado, nombre in ((id_d, True, "239 min dentro"), (id_f, False, "241 min fuera")):
                res = await q1(f"""SELECT {_DENTRO_SLA} AS dentro FROM reclamos r
                                   JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
                                   WHERE r.id_reclamo = :id""", id=id_x)
                check(f"1g. BI exacto: {nombre}", res and res["dentro"] is esperado, str(res))
            for ruta in ("/api/v1/bi/sla-resumen", "/api/v1/bi/ejecutivo/score", "/api/v1/bi/ejecutivo/matriz",
                         "/api/v1/bi/ejecutivo/evolucion-indicadores"):
                r = await c.get(ruta, headers=HA)
                check(f"1h. {ruta} 200", r.status_code == 200, short(r, 120))

            # ── 2. Asignación automática general (mig 121) ───────────────────────────
            async def intento(desc: str) -> dict[str, Any]:
                """Alta (su BackgroundTask ya intentó) + un intento directo para leer el motivo."""
                return await autoasignacion.autoasignar_reclamo(await nuevo_reclamo(desc))

            await set_general("true")
            await exec_commit("UPDATE subarea SET asignacion_manual = FALSE WHERE id_subarea = :s", s=SUB)
            AVISOS.clear()
            # El alta (POST /reclamos) dispara la autoasignación como BackgroundTask.
            id_a = await nuevo_reclamo("Smoke 121 — general prendida")
            est = await q1("SELECT estado FROM reclamos WHERE id_reclamo = :id", id=id_a)
            ot = await q1("""SELECT asignacion_automatica, id_supervisor_asigna, id_agente IS NOT NULL AS con_agente
                             FROM ordenes_trabajo WHERE id_reclamo = :id AND NOT es_auditoria AND activo""", id=id_a)
            check("2a. general prendida + gestión sin excepción → el alta asigna sola",
                  est["estado"] == "En gestión" and ot is not None, f"{est} {ot}")
            check("2b. OT marcada automática, a un agente y sin supervisor",
                  ot == {"asignacion_automatica": True, "id_supervisor_asigna": None, "con_agente": True}, str(ot))
            check("2c. avisos de la asignación (capturados)",
                  [a[0] for a in AVISOS] == ["ot_asignada", "estado_reclamo"], str(AVISOS))

            await exec_commit("UPDATE subarea SET asignacion_manual = TRUE WHERE id_subarea = :s", s=SUB)
            res = await intento("Smoke 121 — gestión a mano")
            check("2d. gestión «asigna a mano» → no asigna",
                  res.get("asignada") is False and "a mano" in res.get("motivo", ""), str(res))

            await exec_commit("UPDATE subarea SET asignacion_manual = FALSE WHERE id_subarea = :s", s=SUB)
            await set_general("false")
            res = await intento("Smoke 121 — general apagada")
            check("2e. general apagada → no asigna",
                  res.get("asignada") is False and "apagada" in res.get("motivo", ""), str(res))
            await set_general("si")
            res = await intento("Smoke 121 — clave inválida")
            check("2f. valor inválido → apagada (fail-closed)", res.get("asignada") is False, str(res))
            await set_general(None)
            res = await intento("Smoke 121 — clave ausente")
            check("2g. clave ausente → apagada (fail-closed)", res.get("asignada") is False, str(res))
            await set_general("true")

            # Config → Sistema y el flag de Subáreas: solo admin.
            cfg = await q1("SELECT id_config FROM configuracion_general WHERE clave = :c AND id_municipio = 1", c=CLAVE)
            r = await c.put(f"/api/v1/admin/configuracion_general/{cfg['id_config']}", headers=HS, json={"valor": "false"})
            check("2h. supervisor no cambia la clave general (403)", r.status_code == 403, short(r, 100))
            r = await c.put(f"/api/v1/admin/configuracion_general/{cfg['id_config']}", headers=HA, json={"valor": "true"})
            check("2i. admin cambia la clave general (200)", r.status_code == 200, short(r, 100))
            r = await c.put(f"/api/v1/admin/subarea/{SUB}", headers=HS, json={"asignacion_manual": True})
            check("2j. supervisor no marca la excepción (403)", r.status_code == 403, short(r, 100))
            r = await c.put(f"/api/v1/admin/subarea/{SUB}", headers=HA, json={"asignacion_manual": True})
            fila = await q1("SELECT asignacion_manual FROM subarea WHERE id_subarea = :s", s=SUB)
            check("2k. admin marca la excepción (200)",
                  r.status_code == 200 and fila["asignacion_manual"] is True, short(r, 100))
            r = await c.put(f"/api/v1/admin/subarea/{SUB}", headers=HA, json={"asignacion_automatica": True})
            check("2l. el tilde viejo ya no se edita (422)", r.status_code == 422, short(r, 100))

            r = await c.get("/openapi.json")
            check("3. marcador OpenAPI (sla_minutos en el drill-down)",
                  "sla_minutos" in r.text, f"({r.status_code})")
    finally:
        # Estado como estaba.
        await exec_commit("UPDATE tipo_reclamo SET sla_minutos = :m WHERE id_tipo_reclamo = :t",
                          m=estado_inicial["tipo_sla"], t=id_tipo)
        await exec_commit("UPDATE subarea SET asignacion_manual = :m WHERE id_subarea = :s",
                          m=estado_inicial["manual"], s=SUB)
        if estado_inicial["general"] is None:
            await set_general(None)
        else:
            await set_general(estado_inicial["general"]["valor"])
            await exec_commit("UPDATE configuracion_general SET descripcion = :d WHERE clave = :c AND id_municipio = 1",
                              d=estado_inicial["general"]["descripcion"], c=CLAVE)

    print(f"\n{ok_count} OK / {fail_count} FAIL")
    for f in fallidos:
        print(f"  - {f['caso']}: {f['detalle']}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
