# -*- coding: utf-8 -*-
"""
Smoke in-process — resultado del trámite al cerrarse (mig 123) + sin doble aviso al
archivar desde un estado que ya es final (2026-10-23).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_tramites_resultado_final.py

SOLO LOCAL: aborta si la DB no es zaris_dev. Corre el app FastAPI real con httpx.ASGITransport;
el mail en MOCK (.env.local tiene una key REAL de Resend) y el push capturado: no sale nada.
Necesita la mig 123 aplicada en local, el admin ciudadanovl (nivel 1, con agente), el vecino
demo id 3 y una empresa activa. El único fixture (tipo_accion de una transición, caso 4) se
restaura al final; los trámites creados quedan como demo.

Cubre:
  0. Catálogo: las transiciones finales de los 9 tipos del seed con aprobar/rechazar; las dos
     del Recurso que van a la fase 2 siguen en avanzar.
  1. Poda aprobada -> Archivado: resultado aprobado automático, un solo aviso de terminación
     (aviso PWA + push «APROBADO»), mail al iniciador, encuesta intentada.
  2. Poda rechazada -> Archivado: resultado rechazado + aviso «RECHAZADO».
  3. Cambio de domicilio: En revisión -> Rechazada (final) avisa; Rechazada -> Archivado no
     vuelve a avisar.
  4. Fixture: Rechazada final SIN resultado -> Archivado con rechazar SÍ avisa (sella el resultado).
  5. Marcador OpenAPI del endpoint de transición.
"""
import asyncio
import logging
import os
import sys
from collections import deque
from datetime import date
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

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.services import encuestas_service, notificaciones, push  # noqa: E402
from app.services.tramites import ciclo_vida  # noqa: E402

PUSHES: list[tuple[str, int, str]] = []
TERMINACIONES: list[int] = []      # llamadas a ciclo_vida.al_terminar
MAILS_FINALES: list[int] = []      # llamadas a notificaciones.notificar_estado_final_a_iniciador
ENCUESTAS: list[tuple[int, str]] = []


async def _push_ciudadano(id_ciudadano: int, titulo: str = "", *a, **k) -> int:
    PUSHES.append(("ciudadano", id_ciudadano, titulo))
    return 0


async def _push_usuario(id_usuario: int, titulo: str = "", *a, **k) -> int:
    PUSHES.append(("usuario", id_usuario, titulo))
    return 0


push.enviar_push_ciudadano = _push_ciudadano  # no sale ningún push real
push.enviar_push_usuario = _push_usuario

_al_terminar_orig = ciclo_vida.al_terminar
_notif_final_orig = notificaciones.notificar_estado_final_a_iniciador
_crear_envio_orig = encuestas_service.crear_envio_para_tramite


async def _al_terminar(id_tramite: int, **k):
    TERMINACIONES.append(id_tramite)
    return await _al_terminar_orig(id_tramite, **k)


async def _notif_final(db, id_tramite, *a, **k):
    MAILS_FINALES.append(id_tramite)
    return await _notif_final_orig(db, id_tramite, *a, **k)


async def _crear_envio(db, id_tramite):
    envio, motivo = await _crear_envio_orig(db, id_tramite)
    ENCUESTAS.append((id_tramite, motivo))
    return envio, motivo


ciclo_vida.al_terminar = _al_terminar
notificaciones.notificar_estado_final_a_iniciador = _notif_final
encuestas_service.crear_envio_para_tramite = _crear_envio

logging.getLogger("httpx").setLevel(logging.WARNING)

PWD_DEV = os.environ.get("ZARIS_QA_PASS") or "123456"
ADMIN_EMAIL = "ciudadanovl@municipio.gob.ar"
ID_CIUDADANO = 3

# Lo que deja la mig 123 en los tipos del seed (los únicos que existen en local).
ESPERADO = [
    ("poda-arbol", "aprobada", "archivado", "aprobar"),
    ("poda-arbol", "rechazada", "archivado", "rechazar"),
    ("cambio-domicilio-comercial", "aprobada", "archivado", "aprobar"),
    ("cambio-domicilio-comercial", "en_revision", "rechazada", "rechazar"),
    ("cambio-domicilio-comercial", "rechazada", "archivado", "rechazar"),
    ("transferencia-habilitacion", "aprobada", "archivado", "aprobar"),
    ("transferencia-habilitacion", "validando_anterior", "rechazada", "rechazar"),
    ("transferencia-habilitacion", "validando_nuevo", "rechazada", "rechazar"),
    ("habilitacion-comercial", "aprobada", "emitida", "aprobar"),
    ("habilitacion-comercial", "inspeccion", "rechazada", "rechazar"),
    ("inspeccion-bromatologica", "realizada", "aprobada", "aprobar"),
    ("inspeccion-bromatologica", "realizada", "rechazada", "rechazar"),
    ("cartel-publicitario", "pago_pendiente", "instalado", "aprobar"),
    ("cartel-publicitario", "revision_tecnica", "rechazado", "rechazar"),
    ("licencia-ordinaria", "aprobada_rrhh", "notificada", "aprobar"),
    ("licencia-ordinaria", "solicitada", "rechazada", "rechazar"),
    ("licencia-ordinaria", "aprobada_jefe", "rechazada", "rechazar"),
    ("recurso-administrativo", "presentado", "inadmisible", "rechazar"),
    ("pedido-informe", "respondido", "archivado", "aprobar"),
    ("recurso-administrativo", "admitido", "resolucion_dictada", "avanzar"),
    ("recurso-administrativo", "resolucion_dictada", "archivado", "avanzar"),
]

ok_count = 0
fail_count = 0


def check(nombre: str, cond: bool, extra: str = "") -> bool:
    global ok_count, fail_count
    if cond:
        ok_count += 1
        print(f"  OK   {nombre} {extra}")
    else:
        fail_count += 1
        print(f"  FAIL {nombre} {extra}")
    return cond


async def q1(sql: str, **params) -> Optional[dict]:
    async with AsyncSessionLocal() as s:
        row = (await s.execute(text(sql), params)).mappings().first()
        return dict(row) if row else None


async def qall(sql: str, **params) -> list[dict]:
    async with AsyncSessionLocal() as s:
        return [dict(r) for r in (await s.execute(text(sql), params)).mappings().all()]


async def exec_commit(sql: str, **params) -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(text(sql), params)
        await s.commit()


SQL_TRANS = """
SELECT tr.id_tipo_tramite_transicion AS id, eo.codigo AS origen, ed.codigo AS destino,
       tr.tipo_accion, tr.requiere_adjunto, ed.es_final, eo.es_inicial
  FROM tipo_tramite tt
  JOIN tipo_tramite_transicion tr ON tr.id_tipo_tramite_version = tt.id_version_publicada AND tr.activo
  JOIN tipo_tramite_estado eo ON eo.id_tipo_tramite_estado = tr.id_estado_origen
  JOIN tipo_tramite_estado ed ON ed.id_tipo_tramite_estado = tr.id_estado_destino
 WHERE tt.codigo = :t
"""


async def camino(tipo: str, pasos_finales: list[tuple[str, str]]) -> list[int]:
    """Ids de transición: del estado inicial al origen del primer paso final (BFS sin adjuntos
    obligatorios ni estados finales en el medio) + los pasos finales pedidos."""
    trans = await qall(SQL_TRANS, t=tipo)
    por_par = {(t["origen"], t["destino"]): t for t in trans}
    inicial = next(t["origen"] for t in trans if t["es_inicial"])
    objetivo = pasos_finales[0][0]
    prev: dict[str, Any] = {inicial: None}
    q = deque([inicial])
    while q:
        n = q.popleft()
        if n == objetivo:
            break
        for t in trans:
            if t["origen"] == n and not t["requiere_adjunto"] and not t["es_final"] and t["destino"] not in prev:
                prev[t["destino"]] = (n, t["id"])
                q.append(t["destino"])
    ids: list[int] = []
    n = objetivo
    while prev.get(n):
        p, idt = prev[n]
        ids.append(idt)
        n = p
    ids.reverse()
    return ids + [por_par[par]["id"] for par in pasos_finales]


def valor_campo(c: dict):
    td = c.get("tipo_dato")
    if td == "direccion":
        return "Av. Maipú 1234, Vicente López"
    if td in ("numero", "entero", "decimal"):
        return 1
    if td == "fecha":
        return date.today().isoformat()
    if td == "booleano":
        return True
    if td == "email":
        return "smoke@example.com"
    if td in ("seleccion", "seleccion_multiple"):
        ops = c.get("opciones_jsonb") or []
        if isinstance(ops, dict):
            ops = ops.get("opciones") or []
        first = ops[0] if ops else "a"
        v = first.get("valor") if isinstance(first, dict) else first
        return [v] if td == "seleccion_multiple" else v
    return "Smoke resultado final (mig 123)"


async def main() -> int:
    id_empresa = (await q1("SELECT id_empresa FROM empresas WHERE activo ORDER BY id_empresa LIMIT 1"))["id_empresa"]
    fixture: Optional[tuple[int, str]] = None

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://smoke.local", timeout=90) as c:
        r = await c.post("/api/v1/auth/login", json={"identificador": ADMIN_EMAIL, "password": PWD_DEV})
        if r.status_code != 200:
            print("login admin fallo:", r.status_code, r.text[:200])
            return 1
        HA = {"Authorization": f"Bearer {r.json()['access_token']}"}

        async def crear(tipo: str, asunto: str) -> int:
            t = await q1("SELECT id_tipo_tramite FROM tipo_tramite WHERE codigo = :c", c=tipo)
            det = (await c.get(f"/api/v1/tramites/tipos/{t['id_tipo_tramite']}", headers=HA)).json()
            datos = {ca["nombre_interno"]: valor_campo(ca) for ca in det.get("campos") or [] if ca.get("obligatorio")}
            if "ciudadano" in (det.get("iniciadores_permitidos") or []):
                ini = {"tipo": "ciudadano", "id_ciudadano": ID_CIUDADANO}
            else:
                ini = {"tipo": "empresa", "id_empresa": id_empresa}
            rr = await c.post("/api/v1/tramites", headers=HA, json={
                "id_tipo_tramite": t["id_tipo_tramite"], "asunto": asunto,
                "iniciador": ini, "datos": datos, "id_municipio": 1,
            })
            if rr.status_code not in (200, 201):
                print("   crear tramite fallo:", rr.status_code, rr.text[:200])
                return 0
            return int(rr.json()["id_tramite"])

        async def transicionar(id_tramite: int, id_trans: int) -> httpx.Response:
            return await c.post(f"/api/v1/tramites/{id_tramite}/transicionar", headers=HA,
                                json={"id_tipo_tramite_transicion": id_trans, "comentario": "smoke resultado final"})

        async def recorrer(id_tramite: int, ids: list[int]) -> Optional[httpx.Response]:
            ultimo = None
            for idt in ids:
                ultimo = await transicionar(id_tramite, idt)
                if ultimo.status_code != 200:
                    print("   transicion fallo:", idt, ultimo.status_code, ultimo.text[:200])
                    return ultimo
            return ultimo

        async def avisos(id_tramite: int) -> list[dict]:
            return await qall("""SELECT tipo, titulo FROM ciudadano_aviso
                                  WHERE recurso_tipo = 'tramite' AND recurso_id = :i AND activo""", i=id_tramite)

        try:
            # ── 0. Catálogo ─────────────────────────────────────────────────
            print("0. Catalogo (mig 123)")
            mal = []
            for tipo, o, d, esperado in ESPERADO:
                fila = next((t for t in await qall(SQL_TRANS, t=tipo) if t["origen"] == o and t["destino"] == d), None)
                if fila is None or fila["tipo_accion"] != esperado:
                    mal.append(f"{tipo} {o}->{d}={fila['tipo_accion'] if fila else 'NO EXISTE'}")
            check("0. 19 transiciones finales etiquetadas + 2 del Recurso en avanzar", not mal, str(mal) if mal else "")

            # ── 1. Poda aprobada ────────────────────────────────────────────
            print("1. Poda aprobada -> Archivado")
            id1 = await crear("poda-arbol", "Smoke resultado final 1 (aprobado)")
            ids = await camino("poda-arbol", [("en_evaluacion", "aprobada"), ("aprobada", "archivado")])
            n_term = len(TERMINACIONES)
            await recorrer(id1, ids[:-1])
            check("1a. llegar a 'Aprobada' (no final) no avisa terminacion", len(TERMINACIONES) == n_term)
            r = await transicionar(id1, ids[-1])
            det = r.json() if r.status_code == 200 else {}
            check("1b. Archivar desde Aprobada -> 200 + resultado 'aprobado'", det.get("resultado") == "aprobado",
                  f"({r.status_code} resultado={det.get('resultado')})")
            mov = await q1("""SELECT metadata_jsonb->>'automatico' AS auto, metadata_jsonb->>'tipo_accion' AS ta
                                FROM tramite_movimiento WHERE id_tramite = :i AND tipo = 'resultado'
                               ORDER BY orden_secuencial DESC LIMIT 1""", i=id1)
            check("1c. ledger 'resultado' automatico por 'aprobar'", mov == {"auto": "true", "ta": "aprobar"}, f"({mov})")
            check("1d. un solo aviso de terminacion y un mail final", TERMINACIONES.count(id1) == 1 and MAILS_FINALES.count(id1) == 1,
                  f"(al_terminar={TERMINACIONES.count(id1)} mail={MAILS_FINALES.count(id1)})")
            est = [a for a in await avisos(id1) if a["tipo"] == "tramite_estado"]
            check("1e. aviso PWA 'termino: APROBADO'", len(est) == 1 and "APROBADO" in est[0]["titulo"], f"({[a['titulo'] for a in est]})")
            ps = [p for p in PUSHES if p[0] == "ciudadano" and p[1] == ID_CIUDADANO and "APROBADO" in p[2]]
            check("1f. push al vecino 'APROBADO' (capturado)", len(ps) == 1, f"({len(ps)})")
            enc = [m for (i, m) in ENCUESTAS if i == id1]
            check("1g. encuesta intentada con el tramite terminado (no 'no terminado')",
                  len(enc) == 1 and enc[0] != encuestas_service.MOTIVO_NO_TERMINADO, f"({enc})")

            # ── 2. Poda rechazada ───────────────────────────────────────────
            print("2. Poda rechazada -> Archivado")
            id2 = await crear("poda-arbol", "Smoke resultado final 2 (rechazado)")
            r = await recorrer(id2, await camino("poda-arbol", [("en_evaluacion", "rechazada"), ("rechazada", "archivado")]))
            det = r.json() if r is not None and r.status_code == 200 else {}
            est = [a for a in await avisos(id2) if a["tipo"] == "tramite_estado"]
            check("2a. resultado 'rechazado' + un aviso 'RECHAZADO'",
                  det.get("resultado") == "rechazado" and len(est) == 1 and "RECHAZADO" in est[0]["titulo"],
                  f"(resultado={det.get('resultado')} avisos={[a['titulo'] for a in est]})")

            # ── 3. Cambio de domicilio: final -> final sin doble aviso ──────
            print("3. Cambio de domicilio: Rechazada (final) -> Archivado")
            id3 = await crear("cambio-domicilio-comercial", "Smoke resultado final 3 (sin doble aviso)")
            ids = await camino("cambio-domicilio-comercial", [("en_revision", "rechazada"), ("rechazada", "archivado")])
            r = await recorrer(id3, ids[:-1])
            det = r.json() if r is not None and r.status_code == 200 else {}
            check("3a. En revision -> Rechazada (final): resultado 'rechazado' + avisa una vez",
                  det.get("resultado") == "rechazado" and TERMINACIONES.count(id3) == 1 and MAILS_FINALES.count(id3) == 1,
                  f"(resultado={det.get('resultado')} al_terminar={TERMINACIONES.count(id3)} mail={MAILS_FINALES.count(id3)})")
            r = await transicionar(id3, ids[-1])
            det = r.json() if r.status_code == 200 else {}
            check("3b. Rechazada -> Archivado: 200, queda archivado y NO vuelve a avisar",
                  r.status_code == 200 and det.get("resultado") == "rechazado"
                  and TERMINACIONES.count(id3) == 1 and MAILS_FINALES.count(id3) == 1,
                  f"({r.status_code} al_terminar={TERMINACIONES.count(id3)} mail={MAILS_FINALES.count(id3)})")

            # ── 4. Final sin resultado -> Archivado que sella: SÍ avisa ─────
            print("4. Fixture: Rechazada final sin resultado -> Archivado con 'rechazar'")
            tr = next(t for t in await qall(SQL_TRANS, t="cambio-domicilio-comercial")
                      if t["origen"] == "en_revision" and t["destino"] == "rechazada")
            fixture = (tr["id"], tr["tipo_accion"])
            await exec_commit("UPDATE tipo_tramite_transicion SET tipo_accion = 'avanzar' WHERE id_tipo_tramite_transicion = :i", i=tr["id"])
            id4 = await crear("cambio-domicilio-comercial", "Smoke resultado final 4 (sella al archivar)")
            r = await recorrer(id4, ids[:-1])
            det = r.json() if r is not None and r.status_code == 200 else {}
            check("4a. En revision -> Rechazada con 'avanzar': resultado pendiente, avisa 'termino'",
                  det.get("resultado") == "pendiente" and TERMINACIONES.count(id4) == 1,
                  f"(resultado={det.get('resultado')} al_terminar={TERMINACIONES.count(id4)})")
            r = await transicionar(id4, ids[-1])
            det = r.json() if r.status_code == 200 else {}
            check("4b. Rechazada -> Archivado ('rechazar') sella 'rechazado' y SI avisa (2 en total)",
                  det.get("resultado") == "rechazado" and TERMINACIONES.count(id4) == 2 and MAILS_FINALES.count(id4) == 2,
                  f"(resultado={det.get('resultado')} al_terminar={TERMINACIONES.count(id4)} mail={MAILS_FINALES.count(id4)})")

            # ── 5. Marcador OpenAPI ─────────────────────────────────────────
            op = app.openapi()["paths"]["/api/v1/tramites/{tramite_ref}/transicionar"]["post"]
            check("5. marcador OpenAPI (200 'no vuelve a avisar al iniciador')",
                  "no vuelve a avisar al iniciador" in op["responses"]["200"]["description"])
        finally:
            if fixture:
                await exec_commit("UPDATE tipo_tramite_transicion SET tipo_accion = :a WHERE id_tipo_tramite_transicion = :i",
                                  a=fixture[1], i=fixture[0])
                print(f"fixture restaurado (transicion {fixture[0]} = {fixture[1]})")

    print(f"\nRESULTADO: {ok_count} OK / {fail_count} FAIL")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
