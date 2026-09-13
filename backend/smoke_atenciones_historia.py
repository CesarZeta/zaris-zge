# -*- coding: utf-8 -*-
"""
Smoke in-process — Historia clinica minima viable (proyecto ATENCION F5, migs 107 + 107b).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_atenciones_historia.py [--rate]

SOLO LOCAL: aborta si la DB no es zaris_dev (sin credenciales de prod, §40 — solo cuentas
@municipio.gob.ar con la clave dev). Corre el app FastAPI real con httpx.ASGITransport
(memoria feedback_smoke_authz_asgi_in_process): middlewares, deps y DB async local, sin puerto.

Cubre GET /api/v1/turnos/atenciones/historia (+ /permiso): guard Salud + nivel 1 resuelto
por agentes.id_subarea (regla 1:1 §39), union turno_atencion + emergencia_atencion, log
append-only historia_clinica_acceso, greedy /{id_turno} intacto, endpoint viejo intacto,
marker OpenAPI. Caso 24 (429) solo con --rate: deja ~60 filas ok en el log.

Setup idempotente (NOT EXISTS): usuarios f5supsalud (n2) / f5atencion (n3) / f5medico (n4,
vinculado a la Guardia) / f5consultor (n5) con agente en la subarea Emergencias del area
de la clave id_area_salud, y f5sinagente (n3 sin agente). Ciudadano 1 con al menos una
emergencia_atencion atendida (se deriva+atiende via API solo si falta).
Los datos NO se limpian (regla del proyecto: se conservan como demo). El log crece en
cada corrida: esperado (append-only).
"""
import asyncio
import os
import sys
from typing import Any, Optional

import httpx

os.environ.setdefault("ENV_FILE", ".env.local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import DBAPIError  # noqa: E402

from app.core.config import settings  # noqa: E402

if "zaris_dev" not in settings.ASYNC_DATABASE_URI:
    sys.exit("ABORT: este smoke es SOLO LOCAL (la DB configurada no es zaris_dev). No corre contra prod.")

from app.core.auth import hash_password  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402

import logging  # noqa: E402
logging.getLogger("httpx").setLevel(logging.WARNING)   # sin una linea INFO por request

RATE = "--rate" in sys.argv
# Clave de las cuentas de prueba: env ZARIS_QA_PASS o la dev estandar. Este smoke aborta
# fuera de zaris_dev (arriba), asi que nunca se usa contra prod (§40).
PWD_DEV = os.environ.get("ZARIS_QA_PASS") or "123456"
HIST = "/api/v1/turnos/atenciones/historia"
PERMISO = "/api/v1/turnos/atenciones/historia/permiso"
UA = "smoke-f5/1.0"

ok_count = 0
fail_count = 0
skip_count = 0
fallidos: list[dict] = []
# requests de DATOS (200/403/404) que DEBEN dejar fila en historia_clinica_acceso
esperados_log = 0


def check(nombre: str, cond: bool, extra: str = "", esperado: str = "", obtenido: str = "") -> bool:
    global ok_count, fail_count
    if cond:
        ok_count += 1
        print(f"  OK   {nombre} {extra}")
    else:
        fail_count += 1
        print(f"  FAIL {nombre} {extra}")
        fallidos.append({"caso": nombre, "esperado": esperado or extra, "obtenido": obtenido or extra})
    return cond


def skip(nombre: str, motivo: str) -> None:
    global skip_count
    skip_count += 1
    print(f"  SKIP {nombre} ({motivo})")


def short(r: httpx.Response, n: int = 160) -> str:
    return f"{r.status_code} {r.text[:n]}"


# ---------------------------------------------------------------------------
# SQL helpers (UNA sentencia por execute: asyncpg no acepta multi-statement)
# ---------------------------------------------------------------------------
async def q(sql: str, **params) -> list[dict]:
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(text(sql), params)).mappings().all()
        return [dict(r) for r in rows]


async def q1(sql: str, **params) -> Optional[dict]:
    rows = await q(sql, **params)
    return rows[0] if rows else None


async def exec_commit(sql: str, **params) -> int:
    async with AsyncSessionLocal() as s:
        res = await s.execute(text(sql), params)
        await s.commit()
        return res.rowcount if res.rowcount is not None else -1


# ---------------------------------------------------------------------------
# Setup §6.1 (idempotente)
# ---------------------------------------------------------------------------
USUARIOS_F5 = [  # (username, nombre, nivel, con_agente)
    ("f5supsalud",  "F5 Supervisor Salud", 2, True),
    ("f5atencion",  "F5 Atencion Salud",   3, True),
    ("f5medico",    "F5 Medico Guardia",   4, True),   # + espacio_agentes a la Guardia (pasa _guardia_o_404)
    ("f5consultor", "F5 Consultor Salud",  5, True),   # Consultor DE Salud -> 403 igual
    ("f5sinagente", "F5 Sin Agente",       3, False),  # nivel 3 sin agente -> 403 sin_agente
]
SQL_USUARIO = """
INSERT INTO usuarios (nombre, username, email, nivel_acceso, password_hash, activo, id_municipio,
                      buc_acceso, es_externo, debe_cambiar_password)
SELECT CAST(:n AS text), CAST(:u AS text), CAST(:u AS text) || '@municipio.gob.ar', CAST(:niv AS int),
       CAST(:h AS text), TRUE, 1, FALSE, FALSE, FALSE
 WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE username = CAST(:u AS text))
"""
SQL_AGENTE = """
INSERT INTO agentes (nombre, apellido, email, id_subarea, id_usuario, activo, id_cargo, id_municipio)
SELECT 'F5', CAST(:n AS text), CAST(:u AS text) || '@municipio.gob.ar',
       (SELECT s.id_subarea FROM subarea s
         WHERE s.activo AND lower(s.nombre) = 'emergencias'
           AND s.id_area = (SELECT NULLIF(TRIM(valor), '')::int FROM configuracion_general
                             WHERE clave = 'id_area_salud' AND activo)
         ORDER BY s.id_subarea LIMIT 1),
       u.id_usuario, TRUE, 4, 1
  FROM usuarios u WHERE u.username = CAST(:u AS text)
   AND NOT EXISTS (SELECT 1 FROM agentes a WHERE a.id_usuario = u.id_usuario)
"""
SQL_VINCULO_GUARDIA = """
INSERT INTO espacio_agentes (id_espacio, id_agente, activo, id_municipio)
SELECT (SELECT NULLIF(TRIM(valor), '')::int FROM configuracion_general WHERE clave = 'id_espacio_guardia' AND activo),
       a.id_agente, TRUE, 1
  FROM agentes a JOIN usuarios u ON u.id_usuario = a.id_usuario
 WHERE u.username = 'f5medico'
   AND NOT EXISTS (SELECT 1 FROM espacio_agentes ea WHERE ea.id_agente = a.id_agente
                     AND ea.id_espacio = (SELECT NULLIF(TRIM(valor), '')::int FROM configuracion_general
                                           WHERE clave = 'id_espacio_guardia' AND activo))
"""
SQL_VERIF_F5 = """
SELECT u.email, u.nivel_acceso, g.id_agente, g.id_subarea, s.id_area
  FROM usuarios u
  LEFT JOIN agentes g ON g.id_usuario = u.id_usuario
  LEFT JOIN subarea s ON s.id_subarea = g.id_subarea
 WHERE u.username LIKE 'f5%'
 ORDER BY u.nivel_acceso, u.username
"""


async def precondiciones() -> dict:
    """Aborta si faltan las migs 107/107b (tabla, clave activa, area activa)."""
    print("== Precondiciones (migs 107 + 107b en local)")
    reg = await q1("SELECT to_regclass('public.historia_clinica_acceso') AS r")
    clave = await q1("SELECT valor, tipo, activo FROM configuracion_general WHERE clave = 'id_area_salud'")
    area = await q1("""
        SELECT a.id_area, a.nombre, a.activo FROM configuracion_general cg
          JOIN area a ON a.id_area = CASE WHEN TRIM(cg.valor) ~ '^[0-9]+$' THEN TRIM(cg.valor)::int END
         WHERE cg.clave = 'id_area_salud'
    """)
    guardia = await q1("SELECT valor FROM configuracion_general WHERE clave = 'id_espacio_guardia' AND activo")
    print(f"   to_regclass(historia_clinica_acceso) = {reg and reg['r']}")
    print(f"   id_area_salud = {clave} -> area {area}")
    print(f"   id_espacio_guardia = {guardia and guardia['valor']}")
    if not (reg and reg["r"]):
        sys.exit("ABORT: falta la tabla historia_clinica_acceso -> aplicar migracion 107")
    if not (clave and clave["activo"] and area and area["activo"]):
        sys.exit("ABORT: clave id_area_salud ausente/inactiva o area inactiva -> aplicar migracion 107b")
    if not guardia:
        sys.exit("ABORT: falta id_espacio_guardia (mig 106b): el setup de f5medico la necesita")
    return {"id_area_salud": area["id_area"], "id_espacio_guardia": int(guardia["valor"])}


async def setup_usuarios() -> None:
    print("== Setup usuarios f5* (idempotente, NOT EXISTS)")
    h = hash_password(PWD_DEV)
    for username, nombre, nivel, con_agente in USUARIOS_F5:
        n1 = await exec_commit(SQL_USUARIO, n=nombre, u=username, niv=nivel, h=h)
        n2 = await exec_commit(SQL_AGENTE, n=nombre, u=username) if con_agente else 0
        print(f"   {username:<12} n{nivel}  usuario {'creado' if n1 == 1 else 'ya existia'}"
              f"{'  agente ' + ('creado' if n2 == 1 else 'ya existia') if con_agente else '  (sin agente a proposito)'}")
    n3 = await exec_commit(SQL_VINCULO_GUARDIA)
    print(f"   f5medico -> espacio_agentes Guardia {'creado' if n3 == 1 else 'ya existia'}")

    print("== Verificacion independiente post-setup (SELECT usuarios/agentes/subarea)")
    rows = await q(SQL_VERIF_F5)
    for r in rows:
        print(f"   {r['email']:<32} n{r['nivel_acceso']}  agente={r['id_agente']}  subarea={r['id_subarea']}  area={r['id_area']}")
    por_user = {r["email"].split("@")[0]: r for r in rows}
    faltan = [u for u, *_ in USUARIOS_F5 if u not in por_user]
    if faltan:
        sys.exit(f"ABORT: usuarios f5 no creados: {faltan}")
    sin_sub = [u for u, _, _, con in USUARIOS_F5 if con and por_user[u]["id_subarea"] is None]
    if sin_sub:
        sys.exit(f"ABORT: la subarea 'Emergencias' del area id_area_salud resolvio NULL para {sin_sub}: "
                 "no seguir con 403 falsos (revisar subarea/area activas)")
    if por_user["f5sinagente"]["id_agente"] is not None:
        sys.exit("ABORT: f5sinagente tiene agente vinculado; el caso 16 (sin_agente) no es representativo")


_login_n = 0


async def login(c: httpx.AsyncClient, email: str) -> dict[str, str]:
    """El login limita 10/min por IP (loginint-ip) y el smoke loguea 11 cuentas
    desde el mismo proceso: cada login sale con un X-Forwarded-For distinto (fallback
    legitimo de get_real_ip fuera de Envoy). Solo en el login: los GET de historia
    van sin ese header para que el log registre la IP real del transporte."""
    global _login_n
    _login_n += 1
    r = await c.post("/api/v1/auth/login", json={"email": email, "password": PWD_DEV},
                     headers={"X-Forwarded-For": f"10.99.0.{_login_n}", "User-Agent": UA})
    if r.status_code != 200:
        sys.exit(f"ABORT: login {email} -> {short(r)}")
    return {"Authorization": f"Bearer {r.json()['access_token']}", "User-Agent": UA}


async def setup_ciudadano1(c: httpx.AsyncClient, H_admin: dict) -> Optional[int]:
    """Ciudadano 1 en ambas fuentes. Si YA tiene emergencia_atencion atendida, no
    deriva de nuevo (hoy existe: evento 56). Devuelve el id_emergencia_evento esperado."""
    print("== Setup ciudadano 1 en ambas fuentes")
    ta = await q1("SELECT count(*) AS n FROM turno_atencion WHERE id_ciudadano = 1 AND activo")
    ea = await q1("""SELECT id_emergencia_atencion, id_emergencia_evento FROM emergencia_atencion
                      WHERE id_ciudadano = 1 AND estado = 'atendida' AND activo
                      ORDER BY id_emergencia_atencion DESC LIMIT 1""")
    print(f"   turno_atencion activas del ciudadano 1: {ta['n']}")
    if ea:
        print(f"   emergencia_atencion atendida YA existe (id {ea['id_emergencia_atencion']}, evento "
              f"{ea['id_emergencia_evento']}): no se deriva de nuevo")
        return ea["id_emergencia_evento"]
    ev = await q1("""
        SELECT ev.id_emergencia_evento FROM emergencia_evento ev
          JOIN emergencia_estado es ON es.id_emergencia_estado = ev.id_estado
         WHERE es.codigo <> 'DESESTIMADO'
           AND NOT EXISTS (SELECT 1 FROM emergencia_atencion x
                            WHERE x.id_emergencia_evento = ev.id_emergencia_evento
                              AND x.activo AND x.estado = 'pendiente')
         ORDER BY ev.id_emergencia_evento DESC LIMIT 1
    """)
    if not ev:
        print("   sin evento elegible para derivar: los asserts de 'emergencia' del ciudadano 1 se saltean")
        return None
    idev = ev["id_emergencia_evento"]
    r = await c.post(f"/api/v1/emergencias/eventos/{idev}/derivar-guardia",
                     json={"motivo": "F5 smoke: control post sutura", "id_ciudadano": 1}, headers=H_admin)
    print(f"   POST derivar-guardia evento {idev} -> {r.status_code}")
    if r.status_code != 201:
        print(f"   derivacion fallo: {short(r)} — se saltean los asserts de emergencia")
        return None
    ida = r.json().get("id_emergencia_atencion")
    r = await c.patch(f"/api/v1/turnos/guardia/atenciones/{ida}/atender",
                      json={"intervencion": "F5 smoke: control clinico en guardia", "recomendaciones": "reposo 48 h"},
                      headers=H_admin)
    print(f"   PATCH atender atencion {ida} -> {r.status_code}")
    if r.status_code != 200:
        print(f"   atender fallo: {short(r)} — se saltean los asserts de emergencia")
        return None
    return idev


# ---------------------------------------------------------------------------
# Matriz §6.2
# ---------------------------------------------------------------------------
ITEM_KEYS = {
    "origen", "id", "fecha_hora", "estado", "titulo", "gestion_nombre", "ubicacion_nombre",
    "profesional_nombre", "id_turno", "id_emergencia_evento", "numero_operativo",
    "motivo_derivacion", "intervencion", "recomendaciones", "registrado_en",
}
CIUD_KEYS = {"id_ciudadano", "apellido", "nombre", "doc_tipo", "doc_nro", "fecha_nac", "edad", "activo"}
LISTA_NEGRA = {"direccion_evento", "ciudadano_dni", "paciente_nombre", "derivado_por", "prioridad_codigo",
               "estado_evento", "telefono", "email", "sexo", "cuil", "domicilio"}
TURNOS_CIUD1 = {34, 35, 45}


async def hist(c: httpx.AsyncClient, H: Optional[dict], **params) -> httpx.Response:
    """GET de datos. Si responde 200/403/404 DEBE haber dejado fila en el log."""
    global esperados_log
    r = await c.get(HIST, params=params, headers=H or {"User-Agent": UA})
    if r.status_code in (200, 403, 404):
        esperados_log += 1
    return r


async def permiso(c: httpx.AsyncClient, H: dict) -> tuple[int, Any, Any]:
    r = await c.get(PERMISO, headers=H)
    j = r.json() if r.status_code == 200 else {}
    return r.status_code, j.get("puede"), j.get("motivo")


async def main() -> int:
    global esperados_log
    cfg = await precondiciones()
    await setup_usuarios()

    log_antes = (await q1("SELECT count(*) AS n FROM historia_clinica_acceso"))["n"]

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://smoke.local", timeout=60) as c:
        H = {}
        for u in ("ciudadanovl", "sofiamedrano", "juanpesto", "operadorcom", "administrativo",
                  "f5supsalud", "f5atencion", "f5medico", "f5consultor", "f5sinagente"):
            H[u] = await login(c, f"{u}@municipio.gob.ar")
        H["smoke96n4a"] = await login(c, "smoke96n4a@smoke96.local")
        admin = H["ciudadanovl"]

        idev_esperado = await setup_ciudadano1(c, admin)
        # El setup pudo consumir requests de datos? No: derivar/atender no son /historia.

        print("\n== Matriz")
        # 1. sin JWT
        r = await hist(c, None, id_ciudadano=1)
        check("1. sin JWT -> 401", r.status_code == 401, f"({r.status_code})", "401", short(r))

        # 2. admin, contenido
        r = await hist(c, admin, id_ciudadano=1, contexto="consulta")
        check("2. admin ciudadano 1 -> 200", r.status_code == 200, f"({r.status_code})", "200", short(r))
        base = r.json() if r.status_code == 200 else {"items": [], "total": -1, "ciudadano": {}}
        items = base["items"]
        ciud = base["ciudadano"]
        check("2a. encabezado ciudadano 1 (Pérez / 12345678 / edad int / activo)",
              ciud.get("id_ciudadano") == 1 and ciud.get("apellido") == "Pérez" and ciud.get("doc_nro") == "12345678"
              and isinstance(ciud.get("edad"), int) and ciud.get("activo") is True, f"({ciud})")
        check("2b. total >= 3 y total == len(items) (cabe en una pagina)",
              base["total"] >= 3 and base["total"] == len(items), f"(total={base['total']}, items={len(items)})")
        origenes = {i["origen"] for i in items}
        if idev_esperado is not None:
            check("2c. origenes == {turno, emergencia}", origenes == {"turno", "emergencia"}, f"({origenes})")
        else:
            skip("2c. origenes == {turno, emergencia}", "sin emergencia_atencion atendida del ciudadano 1")
            check("2c'. origen turno presente", "turno" in origenes, f"({origenes})")
        fechas = [i["fecha_hora"] for i in items]
        check("2d. fecha_hora no creciente (orden DESC)", all(fechas[k] >= fechas[k + 1] for k in range(len(fechas) - 1)),
              f"({fechas})")
        check("2e. ningun estado 'pendiente'", all(i["estado"] in ("atendida", "ausente") for i in items),
              f"({[i['estado'] for i in items]})")
        turnos_it = [i for i in items if i["origen"] == "turno"]
        check("2f. items turno: id_turno en {34,35,45}, titulo/gestion/ubicacion via prestacion, sin motivo_derivacion",
              len(turnos_it) >= 2 and all(
                  i["id_turno"] in TURNOS_CIUD1 and i["titulo"] == "Atencion medica - Odontologia"
                  and i["gestion_nombre"] == "Odontología" and i["ubicacion_nombre"] == "Sala Municipal de Odontologia"
                  and i["motivo_derivacion"] is None and i["id_emergencia_evento"] is None and i["estado"] == "atendida"
                  for i in turnos_it),
              f"({[(i['id_turno'], i['titulo'], i['gestion_nombre'], i['ubicacion_nombre']) for i in turnos_it]})")
        emer_it = [i for i in items if i["origen"] == "emergencia"]
        if idev_esperado is not None:
            check("2g. item emergencia: EM-, evento esperado, intervencion, Guardia/Emergencias, id_turno null",
                  len(emer_it) >= 1 and any(
                      (i["numero_operativo"] or "").startswith("EM-") and i["id_emergencia_evento"] == idev_esperado
                      and i["intervencion"] and i["ubicacion_nombre"] == "Guardia" and i["gestion_nombre"] == "Emergencias"
                      and i["id_turno"] is None and i["estado"] == "atendida"
                      for i in emer_it),
                  f"({[(i['numero_operativo'], i['id_emergencia_evento'], i['ubicacion_nombre'], i['gestion_nombre']) for i in emer_it]})")
        else:
            skip("2g. item emergencia", "sin emergencia_atencion atendida del ciudadano 1")

        # 3. lista negra + keys exactas
        keys_items = set().union(*(set(i.keys()) for i in items)) if items else set()
        check("3a. keys de item == HistoriaClinicaItemOut", bool(items) and all(set(i.keys()) == ITEM_KEYS for i in items),
              f"(diff={keys_items ^ ITEM_KEYS})")
        check("3b. keys de ciudadano == HistoriaClinicaCiudadanoOut", set(ciud.keys()) == CIUD_KEYS,
              f"(diff={set(ciud.keys()) ^ CIUD_KEYS})")
        check("3c. lista negra ausente en items y encabezado",
              not (LISTA_NEGRA & keys_items) and not (LISTA_NEGRA & set(ciud.keys())),
              f"({LISTA_NEGRA & (keys_items | set(ciud.keys()))})")

        # 4. paginacion
        r1 = await hist(c, admin, id_ciudadano=1, limit=1)
        r2 = await hist(c, admin, id_ciudadano=1, limit=1, offset=1)
        j1 = r1.json() if r1.status_code == 200 else {}
        j2 = r2.json() if r2.status_code == 200 else {}
        check("4a. limit=1 -> 1 item, total igual al caso 2, limit/offset eco",
              r1.status_code == 200 and len(j1.get("items", [])) == 1 and j1.get("total") == base["total"]
              and j1.get("limit") == 1 and j1.get("offset") == 0,
              f"({r1.status_code}, items={len(j1.get('items', []))}, total={j1.get('total')})")
        check("4b. limit=1&offset=1 -> items[1] del caso 2",
              r2.status_code == 200 and len(j2.get("items", [])) == 1 and len(items) > 1 and j2["items"][0] == items[1]
              and j2.get("offset") == 1,
              f"({r2.status_code}, {j2.get('items', [{}])[0].get('id') if j2.get('items') else None} vs {items[1]['id'] if len(items) > 1 else None})")

        # 5. ciudadano 328 (solo emergencias atendidas)
        r = await hist(c, admin, id_ciudadano=328)
        j = r.json() if r.status_code == 200 else {}
        n328 = (await q1("""SELECT count(*) AS n FROM emergencia_atencion
                             WHERE id_ciudadano = 328 AND activo AND estado IN ('atendida','ausente')"""))["n"]
        check("5. ciudadano 328 -> 200, total == emergencias cerradas por SQL, todas emergencia/atendida",
              r.status_code == 200 and j.get("total") == n328 and n328 >= 1
              and all(i["origen"] == "emergencia" and i["estado"] == "atendida" for i in j.get("items", [])),
              f"({r.status_code}, total={j.get('total')}, sql={n328})")

        # 6. ciudadano 409 (solo pendiente)
        r = await hist(c, admin, id_ciudadano=409)
        j = r.json() if r.status_code == 200 else {}
        check("6. ciudadano 409 (solo pendiente) -> 200 total 0, doc 92676508",
              r.status_code == 200 and j.get("total") == 0 and j.get("items") == []
              and j.get("ciudadano", {}).get("doc_nro") == "92676508",
              f"({r.status_code}, total={j.get('total')}, doc={j.get('ciudadano', {}).get('doc_nro')})")

        # 7. ciudadano sin registros (2 por defecto; se verifica por SQL, si tiene se busca otro)
        sin_reg = await q1("""
            SELECT c.id_ciudadano FROM ciudadanos c
             WHERE c.id_ciudadano = 2
               AND NOT EXISTS (SELECT 1 FROM turno_atencion ta WHERE ta.id_ciudadano = c.id_ciudadano AND ta.activo)
               AND NOT EXISTS (SELECT 1 FROM emergencia_atencion ea WHERE ea.id_ciudadano = c.id_ciudadano
                                  AND ea.activo AND ea.estado IN ('atendida','ausente'))
        """)
        if not sin_reg:
            sin_reg = await q1("""
                SELECT c.id_ciudadano FROM ciudadanos c
                 WHERE NOT EXISTS (SELECT 1 FROM turno_atencion ta WHERE ta.id_ciudadano = c.id_ciudadano AND ta.activo)
                   AND NOT EXISTS (SELECT 1 FROM emergencia_atencion ea WHERE ea.id_ciudadano = c.id_ciudadano
                                      AND ea.activo AND ea.estado IN ('atendida','ausente'))
                 ORDER BY c.id_ciudadano LIMIT 1
            """)
            print(f"   (ciudadano 2 tiene registros: se usa el {sin_reg and sin_reg['id_ciudadano']} para el caso 7)")
        if sin_reg:
            idc7 = sin_reg["id_ciudadano"]
            r = await hist(c, admin, id_ciudadano=idc7)
            j = r.json() if r.status_code == 200 else {}
            check(f"7. ciudadano {idc7} sin registros -> 200 total 0 + encabezado",
                  r.status_code == 200 and j.get("total") == 0 and j.get("items") == []
                  and j.get("ciudadano", {}).get("id_ciudadano") == idc7,
                  f"({r.status_code}, total={j.get('total')})")
        else:
            skip("7. ciudadano sin registros", "no hay ciudadano sin registros en local")

        # 8. inexistente
        r = await hist(c, admin, id_ciudadano=999999)
        check("8. ciudadano 999999 -> 404 'Ciudadano no encontrado'",
              r.status_code == 404 and r.json().get("detail") == "Ciudadano no encontrado", f"({short(r)})")

        # 9. 422 x6 (antes del guard: no registran)
        casos_422 = [
            ("id_ciudadano=abc", {"id_ciudadano": "abc"}),
            ("limit=500", {"id_ciudadano": 1, "limit": 500}),
            ("contexto=xyz", {"id_ciudadano": 1, "contexto": "xyz"}),
            ("id_ciudadano=0", {"id_ciudadano": 0}),
            # > int32: antes daba 500 en el INSERT del log (asyncpg int4) y el intento no
            # quedaba registrado; con le=2147483647 es 422 antes del guard (revision F5).
            ("id_ciudadano=3000000000 (> int32)", {"id_ciudadano": 3000000000}),
            ("sin params", {}),
        ]
        for nombre, params in casos_422:
            r = await hist(c, admin, **params)
            extra = ""
            cond = r.status_code == 422
            if nombre == "sin params" and cond:
                errs = r.json().get("detail", [])
                cond = any(e.get("type") == "missing" and e.get("loc", [])[-1] == "id_ciudadano" for e in errs) \
                    and not any(e.get("loc", [])[-1] == "id_turno" for e in errs)
                extra = f"({[(e.get('type'), e.get('loc')) for e in errs]})"
            check(f"9. {nombre} -> 422", cond, extra or f"({r.status_code})", "422", short(r))

        # 10. greedy intacto
        r = await c.get("/api/v1/turnos/34", headers=admin)
        check("10a. GET /turnos/34 -> 200 (greedy /{id_turno} intacto)",
              r.status_code == 200 and r.json().get("id_turno") == 34, f"({short(r, 80)})")
        r = await c.get("/api/v1/turnos/historia", headers=admin)
        errs = r.json().get("detail", []) if r.status_code == 422 else []
        check("10b. GET /turnos/historia (1 segmento) -> 422 int_parsing en id_turno (cae en el greedy, documentado)",
              r.status_code == 422 and any(e.get("type") == "int_parsing" and e.get("loc", [])[-1] == "id_turno" for e in errs),
              f"({short(r, 120)})")

        # 11. n5 sofiamedrano: 403 y 403 (no 404) — el guard corre antes de la BUC
        r1 = await hist(c, H["sofiamedrano"], id_ciudadano=1)
        r2 = await hist(c, H["sofiamedrano"], id_ciudadano=999999)
        check("11. n5 sofiamedrano -> 403 (ciud 1) y 403 (ciud inexistente), detail 'Consultor'",
              r1.status_code == 403 and r2.status_code == 403 and "Consultor" in r1.json().get("detail", "")
              and "Consultor" in r2.json().get("detail", ""), f"({r1.status_code}/{r2.status_code} {r1.text[:90]})")

        # 12. n5 de Salud
        r = await hist(c, H["f5consultor"], id_ciudadano=1)
        check("12. n5 f5consultor (agente en Salud) -> 403 'Consultor'",
              r.status_code == 403 and "Consultor" in r.json().get("detail", ""), f"({short(r, 90)})")

        # 13. juanpesto: historia 403 + endpoint viejo 200 con sus filas (agente 1 = recurso de 34/35/45)
        r = await hist(c, H["juanpesto"], id_ciudadano=1)
        rv = await c.get("/api/v1/turnos/atenciones", params={"id_ciudadano": 1}, headers=H["juanpesto"])
        viejo = rv.json() if rv.status_code == 200 else []
        check("13a. n3 juanpesto (fuera de Salud) -> historia 403 'Salud'",
              r.status_code == 403 and "Salud" in r.json().get("detail", ""), f"({short(r, 90)})")
        check("13b. n3 juanpesto -> GET /turnos/atenciones?id_ciudadano=1 200 con >=2 filas de turnos {34,35,45} (scope viejo intacto)",
              rv.status_code == 200 and len(viejo) >= 2 and {x["id_turno"] for x in viejo} <= TURNOS_CIUD1,
              f"({rv.status_code}, ids={[x.get('id_turno') for x in viejo]})")

        # 14. otras areas
        for u in ("operadorcom", "smoke96n4a"):
            r = await hist(c, H[u], id_ciudadano=1)
            check(f"14. {u} (otra area) -> 403 'Salud'", r.status_code == 403 and "Salud" in r.json().get("detail", ""),
                  f"({short(r, 90)})")

        # 15. area 'Salud' INACTIVA (administrativo@ n2)
        r = await hist(c, H["administrativo"], id_ciudadano=1)
        check("15. n2 administrativo (area 1 'Salud' INACTIVA) -> 403 fuera_salud",
              r.status_code == 403 and "Secretaría de Salud" in r.json().get("detail", ""), f"({short(r, 90)})")

        # 16. sin agente
        r = await hist(c, H["f5sinagente"], id_ciudadano=1)
        check("16. n3 f5sinagente -> 403 'agente vinculado'",
              r.status_code == 403 and "agente vinculado" in r.json().get("detail", ""), f"({short(r, 90)})")

        # 17. Salud n2/n3/n4 -> 200, total igual al caso 2
        for u in ("f5supsalud", "f5atencion", "f5medico"):
            r = await hist(c, H[u], id_ciudadano=1, contexto="guardia")
            j = r.json() if r.status_code == 200 else {}
            check(f"17. {u} (Salud) -> 200, total == caso 2", r.status_code == 200 and j.get("total") == base["total"],
                  f"({r.status_code}, total={j.get('total')})")

        # 18. no regresion F4
        r = await c.get("/api/v1/turnos/guardia/atenciones", headers=H["f5medico"])
        check("18. f5medico GET /turnos/guardia/atenciones -> 200 (vinculado por espacio_agentes)",
              r.status_code == 200 and isinstance(r.json(), list), f"({short(r, 80)})")

        # 19. /permiso x6
        esperado_permiso = [("ciudadanovl", True, "admin"), ("f5medico", True, "salud"), ("f5consultor", False, "nivel"),
                            ("juanpesto", False, "fuera_salud"), ("f5sinagente", False, "sin_agente"),
                            ("sofiamedrano", False, "nivel")]
        for u, puede, motivo in esperado_permiso:
            st, p, m = await permiso(c, H[u])
            check(f"19. permiso {u} -> ({puede}, '{motivo}')", st == 200 and p is puede and m == motivo,
                  f"({st}, {p}, {m})")
        st, p, m = await permiso(c, H["f5supsalud"])
        check("19b. permiso f5supsalud (n2 Salud) -> (True, 'salud')", st == 200 and p is True and m == "salud",
              f"({st}, {p}, {m})")

        # 20. clave desactivada (try/finally SIEMPRE restaura)
        try:
            n = await exec_commit("UPDATE configuracion_general SET activo = FALSE WHERE clave = 'id_area_salud'")
            if n != 1:
                print(f"   (aviso: el UPDATE de desactivacion afecto {n} filas)")
            st, p, m = await permiso(c, admin)
            check("20a. clave inactiva: permiso admin -> (True, 'admin_sin_config')",
                  st == 200 and p is True and m == "admin_sin_config", f"({st}, {p}, {m})")
            r = await hist(c, admin, id_ciudadano=1)
            check("20b. clave inactiva: historia admin -> 200 (nivel 1 siempre)", r.status_code == 200, f"({r.status_code})")
            r = await hist(c, H["f5medico"], id_ciudadano=1)
            check("20c. clave inactiva: historia f5medico -> 403 sin_config (fail-closed)",
                  r.status_code == 403 and "id_area_salud" in r.json().get("detail", ""), f"({short(r, 90)})")
            st, p, m = await permiso(c, H["f5medico"])
            check("20d. clave inactiva: permiso f5medico -> (False, 'sin_config')",
                  st == 200 and p is False and m == "sin_config", f"({st}, {p}, {m})")
        finally:
            await exec_commit("UPDATE configuracion_general SET activo = TRUE WHERE clave = 'id_area_salud'")
            rest = await q1("SELECT activo, valor FROM configuracion_general WHERE clave = 'id_area_salud'")
            check("20e. finally: clave id_area_salud restaurada (activo=TRUE, mismo valor)",
                  bool(rest) and rest["activo"] is True and str(rest["valor"]).strip() == str(cfg["id_area_salud"]),
                  f"({rest})")
            st, p, m = await permiso(c, H["f5medico"])
            check("20f. tras restaurar: permiso f5medico -> (True, 'salud')", st == 200 and p is True and m == "salud",
                  f"({st}, {p}, {m})")

        # 21. log
        log_despues = (await q1("SELECT count(*) AS n FROM historia_clinica_acceso"))["n"]
        check(f"21a. el log crecio exactamente en {esperados_log} (requests de datos 200/403/404; 401/422/permiso/greedy no suman)",
              log_despues - log_antes == esperados_log, f"(antes={log_antes}, despues={log_despues}, delta={log_despues - log_antes})")
        ult_med = await q1("""
            SELECT h.resultado, h.motivo, h.n_registros, h.contexto, h.ip, h.user_agent, h.id_ciudadano
              FROM historia_clinica_acceso h JOIN usuarios u ON u.id_usuario = h.id_usuario
             WHERE u.username = 'f5medico' AND h.id_historia_clinica_acceso > :desde
             ORDER BY h.id_historia_clinica_acceso DESC LIMIT 1""", desde=0)
        # la ULTIMA de f5medico en esta corrida es la del caso 20c (denegado/sin_config); la del 17 es la ok/salud
        ult_med_ok = await q1("""
            SELECT h.resultado, h.motivo, h.n_registros, h.contexto, h.ip, h.user_agent
              FROM historia_clinica_acceso h JOIN usuarios u ON u.id_usuario = h.id_usuario
             WHERE u.username = 'f5medico' AND h.resultado = 'ok'
             ORDER BY h.id_historia_clinica_acceso DESC LIMIT 1""")
        check("21b. ultima fila ok de f5medico: ('ok','salud', n>=3, 'guardia', ip no nula, UA del smoke)",
              bool(ult_med_ok) and ult_med_ok["motivo"] == "salud" and (ult_med_ok["n_registros"] or 0) >= 3
              and ult_med_ok["contexto"] == "guardia" and ult_med_ok["ip"] and ult_med_ok["user_agent"] == UA,
              f"({ult_med_ok})")
        check("21c. ultima fila de f5medico (caso 20c): ('denegado','sin_config', NULL)",
              bool(ult_med) and ult_med["resultado"] == "denegado" and ult_med["motivo"] == "sin_config"
              and ult_med["n_registros"] is None, f"({ult_med})")
        ult_sofia = await q1("""
            SELECT h.resultado, h.motivo, h.n_registros FROM historia_clinica_acceso h
              JOIN usuarios u ON u.id_usuario = h.id_usuario
             WHERE u.username = 'sofiamedrano' ORDER BY h.id_historia_clinica_acceso DESC LIMIT 1""")
        check("21d. ultima fila de sofiamedrano: ('denegado','nivel', NULL)",
              bool(ult_sofia) and ult_sofia["resultado"] == "denegado" and ult_sofia["motivo"] == "nivel"
              and ult_sofia["n_registros"] is None, f"({ult_sofia})")
        inex = await q1("""
            SELECT count(*) AS n FROM historia_clinica_acceso h JOIN usuarios u ON u.id_usuario = h.id_usuario
             WHERE u.username = 'ciudadanovl' AND h.resultado = 'inexistente' AND h.motivo = 'admin'
               AND h.id_ciudadano = 999999 AND h.n_registros = 0""")
        check("21e. existe fila ('inexistente','admin') con id_ciudadano=999999 (caso 8)", inex["n"] >= 1, f"(n={inex['n']})")
        sinag = await q1("""
            SELECT count(*) AS n FROM historia_clinica_acceso h JOIN usuarios u ON u.id_usuario = h.id_usuario
             WHERE u.username = 'f5sinagente' AND h.resultado = 'denegado' AND h.motivo = 'sin_agente'""")
        fuera = await q1("""
            SELECT count(*) AS n FROM historia_clinica_acceso h JOIN usuarios u ON u.id_usuario = h.id_usuario
             WHERE u.username = 'administrativo' AND h.resultado = 'denegado' AND h.motivo = 'fuera_salud'""")
        check("21f. filas denegado sin_agente (f5sinagente) y fuera_salud (administrativo) registradas",
              sinag["n"] >= 1 and fuera["n"] >= 1, f"(sin_agente={sinag['n']}, fuera_salud={fuera['n']})")

        # 22. append-only (en transaccion con rollback)
        for op, sql in (("UPDATE", """UPDATE historia_clinica_acceso SET n_registros = 0
                                     WHERE id_historia_clinica_acceso = (SELECT max(id_historia_clinica_acceso) FROM historia_clinica_acceso)"""),
                        ("DELETE", """DELETE FROM historia_clinica_acceso
                                     WHERE id_historia_clinica_acceso = (SELECT max(id_historia_clinica_acceso) FROM historia_clinica_acceso)""")):
            msg = ""
            try:
                async with AsyncSessionLocal() as s:
                    try:
                        await s.execute(text(sql))
                    finally:
                        await s.rollback()
            except DBAPIError as e:
                msg = str(e.orig) if e.orig else str(e)
            except Exception as e:  # noqa: BLE001
                msg = str(e)
            check(f"22. {op} sobre historia_clinica_acceso -> excepcion 'append-only'", "append-only" in msg,
                  f"({msg[:80] if msg else 'NO lanzo excepcion'})")
        log_final = (await q1("SELECT count(*) AS n FROM historia_clinica_acceso"))["n"]
        check("22c. el log no cambio tras UPDATE/DELETE rechazados", log_final == log_despues,
              f"({log_despues} -> {log_final})")

        # 23. OpenAPI marker
        r = await c.get("/openapi.json")
        paths = r.json().get("paths", {}) if r.status_code == 200 else {}
        resp = paths.get(HIST, {}).get("get", {}).get("responses", {})
        check("23. openapi: /atenciones/historia con 403/404/429 y /permiso presente (marker §9)",
              r.status_code == 200 and {"403", "404", "429"} <= set(resp) and PERMISO in paths
              and "/api/v1/turnos/{id_turno}" in paths and "/api/v1/turnos/atenciones" in paths,
              f"(responses={sorted(resp)}, permiso={PERMISO in paths})")

        # 24. rate limit (opcional)
        if RATE:
            previos = (await q1("""SELECT count(*) AS n FROM historia_clinica_acceso h JOIN usuarios u ON u.id_usuario = h.id_usuario
                                   WHERE u.username = 'f5medico' AND h.fecha_hora > NOW() - INTERVAL '60 seconds'"""))["n"]
            # el bucket in-memory ya tiene las llamadas de f5medico de este proceso (17, 20c): las descontamos
            hechos = 0
            ultimo = None
            for _ in range(61):
                ultimo = await hist(c, H["f5medico"], id_ciudadano=1)
                hechos += 1
                if ultimo.status_code == 429:
                    break
            check("24. --rate: f5medico recibe 429 al superar 60/min (in-memory, mismo proceso)",
                  ultimo is not None and ultimo.status_code == 429 and hechos <= 61,
                  f"(429 en el intento {hechos} de esta tanda; previos en 60s={previos})")
        else:
            skip("24. rate limit 429", "solo con --rate: deja ~60 filas ok en el log")

    log_final = (await q1("SELECT count(*) AS n FROM historia_clinica_acceso"))["n"]   # incluye la tanda --rate
    print(f"\n{'TODOS OK' if fail_count == 0 else 'HAY FALLOS'}: {ok_count} OK / {fail_count} FAIL / {skip_count} SKIP")
    print("Fixtures que quedan como demo (solo local): usuarios f5supsalud/f5atencion/f5medico/f5consultor/f5sinagente"
          "@municipio.gob.ar (pwd dev), ciudadano 1 con turno_atencion + emergencia_atencion atendida; "
          f"log historia_clinica_acceso: {log_final} filas.")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
