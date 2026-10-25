# -*- coding: utf-8 -*-
"""
Barrido de aislamiento entre municipios (IT-01 F2, Tarea 7). SOLO LOCAL, in-process.
Plan: PLAN_MULTI_MUNICIPIO_F1_F2.md. Requiere seed_municipio_aislamiento.py.

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_aislamiento.py [--rutas /api/v1/reclamos] [--solo-get]

Como administrador del municipio 1 recorre TODAS las rutas de la app con los ids del municipio de
aislamiento (B) en la ruta, en los filtros opcionales que son ids y en `?id_municipio=<B>`:
  - ninguna respuesta puede contener la marca AISLAB (todo texto libre de B la lleva);
  - una ruta con un id de B en el path tiene que dar 403/404 (R3), nunca 2xx;
  - ningún 500.
Después: control positivo como admin de B (ve sus datos), mutaciones como admin del municipio 1
sobre ids de B (B no cambia: checksum por tabla), altas con ids de B en el body (no crean nada),
vecino de B contra datos del municipio 1, y rutas públicas por origen.
Un parámetro de ruta sin mapear es una FALLA («ruta sin cubrir»), salvo que esté en SALTEAR.
"""
import argparse
import asyncio
import datetime as dt
import enum
import os
import re
import sys
import typing
from collections import defaultdict
from typing import Any, Optional

import httpx

os.environ.setdefault("ENV_FILE", ".env.local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import logging  # noqa: E402

logging.disable(logging.WARNING)

from fastapi.routing import APIRoute  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402

if "zaris_dev" not in settings.ASYNC_DATABASE_URI:
    sys.exit("ABORT: este smoke es SOLO LOCAL (la DB configurada no es zaris_dev).")
settings.RESEND_API_KEY = ""

from app.api.routes.admin_tablas import TABLE_CONFIG  # noqa: E402
from app.core.auth import crear_token_ciudadano  # noqa: E402
from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services import push  # noqa: E402
from seed_municipio_aislamiento import DNI_VECINO_B, cuil_valido, ids_aislamiento  # noqa: E402

push._webpush_sync = lambda *a, **k: None  # nunca sale un push real

MARCA = "AISLAB"
ORIGEN_B = "https://aislamiento.zge.zaris.com.ar"
ORIGEN_B_VECINOS = "https://aislamiento.vecinos.zaris.com.ar"
CLAVE = "123456"
TEXTO_DE_BUSQUEDA = {"q", "texto", "busqueda", "buscar", "term", "termino", "nombre", "search"}
NUMERO_DE_A = re.compile(r"\b(REC|OT|EM)-(?!AIS-)([A-Z]{2,3}-)?\d{4}-\d{6}\b")

# Parámetro de ruta → tabla de B. Primero las reglas por prefijo (el mismo nombre en dos módulos).
REGLAS: list[tuple[str, str, str]] = [
    (r"^/api/v1/emergencias/", "id_evento", "emergencia_evento"),
    (r"^/api/v1/admin/tramites/", "id_doc", "tipo_tramite_documento_requerido"),
    (r"^/api/v1/tramites/", "id_doc", "tramite_documento"),
    (r"^/api/v1/ot/", "id_adjunto", "ot_adjuntos"),
    (r"^/api/v1/(reclamos|publico)/", "id_adjunto", "reclamo_adjuntos"),
    (r"^/api/v1/buc/ciudadanos/", "id", "ciudadanos"),
    (r"^/api/v1/buc/empresas/", "id", "empresas"),
    (r"^/api/v1/buc/usuarios/", "id", "usuarios"),
]
POR_NOMBRE = {
    "id_reclamo": "reclamos", "id_ot": "ordenes_trabajo", "id_turno": "turnos", "id_activo": "activos",
    "id_agenda_feriado": "agenda_feriado", "id_agente_novedad": "agente_novedad", "id_conflicto": "conflictos_log",
    "id_disponibilidad": "disponibilidad_recurso", "id_espacio": "espacios_agenda", "id_espacio_agente": "espacio_agentes",
    "id_evento": "eventos", "id_evento_encargado": "evento_encargados", "id_evento_reserva": "evento_reservas",
    "id_notificacion": "notificacion", "id_ocupacion": "ocupaciones", "id_prestacion": "tipo_prestacion",
    "id_subarea": "subarea", "id_area": "area", "id_tipo": "emergencia_tipo", "id_tipo_tramite": "tipo_tramite",
    "id_usuario": "usuarios", "id_version": "tipo_tramite_version", "id_campo": "tipo_tramite_campo",
    "id_estado": "tipo_tramite_estado", "id_trans": "tipo_tramite_transicion",
    "id_aprob_req": "tipo_tramite_aprobacion_requerida", "id_aprob": "tramite_aprobacion",
    "id_plantilla": "encuesta_plantilla", "id_respuesta": "encuesta_respuesta", "id_encuesta_envio": "encuesta_envio",
    "id_contacto": "emergencia_contacto_eventual", "id_atencion": "emergencia_atencion", "id_aviso": "ciudadano_aviso",
    "id_recurso": "agentes", "id_agente": "agentes", "id_ciudadano": "ciudadanos", "id_empresa": "empresas",
    "id_tipo_reclamo": "tipo_reclamo", "id_equipo": "equipos", "id_cargo": "cargos", "id_tipo_prestacion": "tipo_prestacion",
    "id_emergencia_evento": "emergencia_evento", "id_tramite": "tramite", "id_subtipo": "emergencia_subtipo",
    "id_canal_ingreso": "emergencia_canal_ingreso", "id_prioridad": "emergencia_prioridad",
    "id_tipo_tramite_version": "tipo_tramite_version", "id_lugar": "lugares_atencion", "id_servicio": "servicios",
    "id_ciudadano_buc": "ciudadanos", "id_contacto_eventual": "emergencia_contacto_eventual",
}
SALTEAR: list[tuple[str, str]] = [
    (r"\{token", "token público en la URL: el municipio sale de la fila del token (R11), se prueba aparte"),
    (r"^/api/v1/demo/", "generador demo con token de dispatcher (Tarea 18)"),
    (r"^/api/v1/admin/permisos/modulos/\{codigo\}", "catálogo global de módulos (habilitación por municipio en F4)"),
    (r"/geo/(buscar|reverse)", "llama a Nominatim; el bbox por municipio se prueba en la Tarea 9"),
    (r"^/api/v1/super/", "exclusivas del super administrador, sobre lo global (IT-01 F3): las prueba "
                         "smoke_super_admin.py, con 403 para todo administrador de municipio"),
]
NO_MUTAR_SIN_ID = re.compile(r"^/api/v1/(auth|demo|publico/auth|publico/alta|usuarios|tramites/mantenimiento)|"
                             r"dispatch|/push/|cambiar-password|/config/identidad")
CONTROL_POSITIVO = [
    "/api/v1/reclamos/{id_reclamo}", "/api/v1/ot/{id_ot}", "/api/v1/turnos/{id_turno}",
    "/api/v1/agenda/eventos/{id_evento}", "/api/v1/tramites/{numero_o_id}", "/api/v1/emergencias/eventos/{id_evento}",
    "/api/v1/buc/ciudadanos/{id}", "/api/v1/buc/empresas/{id}", "/api/v1/buc/usuarios/{id}",
]

FALLAS: dict[str, list[str]] = defaultdict(list)
CUENTA = defaultdict(int)


def falla(path: str, msg: str) -> None:
    grupo = "/".join(path.split("/")[:4])
    FALLAS[grupo].append(msg)


def tabla_de(path: str, param: str) -> Optional[str]:
    for patron, nombre, tabla in REGLAS:
        if nombre == param and re.search(patron, path):
            return tabla
    return POR_NOMBRE.get(param)


def saltear(path: str) -> Optional[str]:
    for patron, motivo in SALTEAR:
        if re.search(patron, path):
            return motivo
    return None


def _desnudar(anot):
    origen = typing.get_origin(anot)
    if origen in (typing.Union, getattr(__import__("types"), "UnionType", None)):
        args = [a for a in typing.get_args(anot) if a is not type(None)]
        return _desnudar(args[0]) if args else str
    if origen is typing.Annotated:
        return _desnudar(typing.get_args(anot)[0])
    return anot


def valor_para(nombre: str, anot, ids: dict, *, prof: int = 0) -> Any:
    """Valor plausible para un campo: id de B si el nombre es una referencia mapeada."""
    t = _desnudar(anot)
    tabla = POR_NOMBRE.get(nombre)
    if tabla and tabla in ids and t in (int, Any):
        return ids[tabla]
    origen = typing.get_origin(t)
    if origen is typing.Literal:
        return typing.get_args(t)[0]
    if origen in (list, tuple, set):
        return []
    if origen is dict or t is dict:
        return {}
    if isinstance(t, type):
        if issubclass(t, enum.Enum):
            return list(t)[0].value
        if issubclass(t, BaseModel):
            return cuerpo_de(t, ids, prof=prof + 1) if prof < 3 else {}
        if t is bool:
            return False
        if t is int:
            return 1
        if t is float:
            return 1.0
        # Valores que pasan la validación del body: si el request se frena en un 422 de
        # validación, el handler no corre y el guard del municipio queda sin probar.
        fin = any(x in nombre for x in ("fin", "hasta"))
        if t is dt.date:
            return dt.date.today().isoformat()
        if t is dt.datetime:
            return (dt.datetime.now() + dt.timedelta(hours=1 if fin else 0)).isoformat()
        if t is dt.time:
            return "11:00" if fin else "10:00"
        if t is str:
            if "email" in nombre:
                return "zz.prueba@prueba-aislamiento.com.ar"
            if nombre in ("cuit", "cuil"):
                return cuil_valido("30", "97000002")
            if nombre in ("codigo", "nombre_interno"):
                return "zz_prueba"
            if "telefono" in nombre:
                return "1164295018"
            if nombre == "resultado":
                return "pendiente"
            if nombre == "tipo_dato":
                return "booleano"
    return "ZZ-prueba"  # sin la marca: un error que repite el input no cuenta como filtración


def cuerpo_de(modelo, ids: dict, *, prof: int = 0) -> dict:
    out = {}
    for nombre, campo in modelo.model_fields.items():
        clave = campo.alias or nombre
        if campo.is_required() or POR_NOMBRE.get(nombre) in ids:
            out[clave] = valor_para(nombre, campo.annotation, ids, prof=prof)
    return out


def body_de(ruta: APIRoute, ids: dict) -> tuple[Optional[Any], bool]:
    """(body, lleva_ids_de_B)."""
    bf = ruta.body_field
    if bf is None:
        return None, False
    anot = getattr(bf.field_info, "annotation", None) or getattr(bf, "type_", None)
    t = _desnudar(anot)
    if isinstance(t, type) and issubclass(t, BaseModel):
        body = cuerpo_de(t, ids)
        con_b = any(POR_NOMBRE.get(k) in ids and v == ids[POR_NOMBRE[k]] for k, v in body.items())
        return body, con_b
    return {}, False


# Mutaciones críticas que reciben un dict suelto (sin schema): el generador no sabe qué
# campos esperan y el handler responde 422 ANTES del guard del municipio, así que el guard
# queda sin probar (Tarea 7: «mutaciones con body válido»). (regex del path, body).
_ADJUNTO = {"nombre_archivo": "zz.png", "mime_type": "image/png", "tamano_bytes": 10}
_OBSERVAR = {"observaciones": "zz prueba de aislamiento", "generar_retrabajo": False}
BODY_ESPECIAL: list[tuple[str, Any]] = [
    (r"^/api/v1/reclamos/\d+/estado$", {"estado": "En espera"}),
    (r"^/api/v1/reclamos/\d+/resolver$", {"resolucion": "zz prueba de aislamiento"}),
    (r"^/api/v1/reclamos/\d+/cancelar$", {"motivo": "zz prueba de aislamiento"}),
    (r"^/api/v1/reclamos/\d+/avisar-supervisor$", {"accion_sugerida": "Revisar", "comentario": "zz"}),
    (r"^/api/v1/(reclamos|ot)/\d+/adjuntos/upload-url$", _ADJUNTO),
    (r"^/api/v1/ot/\d+/reasignar$", lambda ids: {"id_agente": ids["agentes"], "nota": "zz"}),
    (r"^/api/v1/ot/\d+/tomar$", lambda ids: {"id_agente": ids["agentes"]}),
    (r"^/api/v1/ot/\d+/estado$", {"estado": "En espera"}),
    (r"^/api/v1/ot/\d+/(rechazar|observar)$", _OBSERVAR),
    (r"^/api/v1/admin/encuestas/disparar$", lambda ids: {"id_reclamo": ids["reclamos"]}),
    (r"^/api/v1/tramites/[^/]+/aprobaciones/\d+/resolver$", {"decision": "aprobada", "observaciones": "zz"}),
    # Schemas con validadores cruzados que el generador no satisface.
    (r"^/api/v1/agenda/ocupaciones/\d+$", lambda ids: {"tipo_recurso": "agente", "id_recurso": ids["agentes"]}),
    (r"^/api/v1/agenda/ocupaciones$", lambda ids: {
        "tipo": "ot", "tipo_recurso": "agente", "id_recurso": ids["agentes"], "fecha": dt.date.today().isoformat(),
        "hora_inicio": "10:00", "hora_fin": "11:00", "id_orden_trabajo": ids["ordenes_trabajo"]}),
    (r"^/api/v1/turnos/prestaciones(/\d+)?$", lambda ids: {
        "nombre": "zz", "tipo_recurso": "agente", "id_agente": ids["agentes"], "duracion_min": 30}),
    (r"^/api/v1/admin/tramites/tipos$", lambda ids: {
        "codigo": "zz_prueba_b", "nombre": "zz", "prefijo": "ZZB", "iniciadores_permitidos": ["ciudadano"],
        "id_subarea": ids["subarea"]}),
]


def body_especial(path: str, ids: dict, metodo: str) -> Optional[dict]:
    for patron, body in BODY_ESPECIAL:
        if re.search(patron, path):
            return body(ids) if callable(body) else body
    # Maestros: PUT /admin/<tabla>/<id> solo toma las columnas de TABLE_CONFIG.
    m = re.match(r"^/api/v1/admin/([a-z_]+)/\d+$", path)
    if m and metodo == "PUT" and m.group(1) in TABLE_CONFIG:
        cfg = TABLE_CONFIG[m.group(1)]
        col = cfg["cols"][0]
        tabla = POR_NOMBRE.get(col)
        tipo = cfg.get("col_types", {}).get(col)
        valor = (ids[tabla] if tabla in ids else
                 dt.date.today().isoformat() if tipo == "date" else "10:00" if tipo == "time" else "ZZ-prueba")
        return {col: valor}
    return None


QUERY_ESPECIAL = {
    "/api/v1/buc/ciudadanos/verificar-duplicado": {"campo": "doc_nro", "valor": DNI_VECINO_B},
    "/api/v1/buc/empresas/verificar-duplicado": {"campo": "cuit", "valor": cuil_valido("30", "97000001")},
}


def query_de(ruta: APIRoute, ids: dict) -> dict:
    q = {"id_municipio": ids["municipio"], **QUERY_ESPECIAL.get(ruta.path, {})}
    for f in ruta.dependant.query_params:
        nombre = getattr(f, "alias", None) or f.name
        anot = getattr(f.field_info, "annotation", None)
        if nombre in q:
            continue
        if POR_NOMBRE.get(nombre) in ids:
            q[nombre] = ids[POR_NOMBRE[nombre]]
        elif nombre in TEXTO_DE_BUSQUEDA:
            q[nombre] = MARCA  # una búsqueda que no filtra por municipio devuelve filas de B
        elif f.field_info.is_required():
            q[nombre] = valor_para(nombre, anot, ids)
    return q


def armar_paths(ruta: APIRoute, ids: dict, numero_b: str) -> list[tuple[str, bool]]:
    """Paths concretos para la ruta con ids de B: [(path, lleva_id_de_B)]. [] si hay que saltearla."""
    params = re.findall(r"{([^}:]+)", ruta.path)
    if not params:
        return [(ruta.path, False)]
    if "tabla" in params:
        out = []
        for t, cfg in TABLE_CONFIG.items():
            if t == "municipios":
                continue  # desde F3 solo la lee el super administrador: se prueba aparte (2b)
            tabla_real = cfg.get("table", t)
            p = ruta.path.replace("{tabla}", t)
            if "{id}" in p:
                if tabla_real not in ids:
                    continue  # tabla global o sin filas en B
                out.append((p.replace("{id}", str(ids[tabla_real])), True))
            else:
                out.append((p, False))
        return out
    p = ruta.path
    for param in params:
        if param in ("numero_o_id", "tramite_ref"):
            valor = numero_b
        elif param == "tipo_recurso":
            valor = "agente"
        else:
            tabla = tabla_de(ruta.path, param)
            if tabla is None or tabla not in ids:
                raise KeyError(param)
            valor = ids[tabla]
        p = p.replace("{" + param + "}", str(valor))
    return [(p, True)]


async def checksum_b(id_b: int) -> dict[str, str]:
    out = {}
    async with engine.connect() as conn:
        tablas = [r[0] for r in await conn.execute(text(
            "SELECT tabla FROM municipio_tabla_clase WHERE clase IN ('catalogo','operativo') ORDER BY 1"))]
        for t in tablas:
            if not await conn.scalar(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"public.{t}"}):
                continue
            out[t] = await conn.scalar(text(
                f'SELECT md5(coalesce(string_agg(x::text, \'|\' ORDER BY x::text), \'\')) FROM "{t}" x '
                f'WHERE x.id_municipio = :b'), {"b": id_b})
    return out


async def login(c: httpx.AsyncClient, ident: str, origen: Optional[str] = None) -> dict:
    h = {"Origin": origen} if origen else {}
    r = await c.post("/api/v1/auth/login", json={"identificador": ident, "password": CLAVE}, headers=h)
    if r.status_code != 200:
        sys.exit(f"No pude loguear {ident}: {r.status_code} {r.text[:200]}")
    hs = {"Authorization": f"Bearer {r.json()['access_token']}"}
    if origen:
        hs["Origin"] = origen
    return hs


def revisar(path: str, metodo: str, r: httpx.Response, con_id_b: bool, etiqueta: str) -> None:
    CUENTA[etiqueta] += 1
    cuerpo = r.text or ""
    if r.status_code == 429:
        CUENTA["429 (sin probar)"] += 1
        return
    # Un 4xx que repite lo que mandamos (la búsqueda con la marca) no es una filtración.
    pidio_marca = MARCA in str(r.request.url) or MARCA in (r.request.content or b"").decode("utf-8", "replace")
    # Un valor que es exactamente la marca es el eco de la búsqueda («origen NUEVO, valor AISLAB»):
    # los textos de B la llevan junto al texto original, nunca sola.
    if pidio_marca:
        cuerpo = cuerpo.replace(f'"{MARCA}"', '""')
    if r.status_code >= 500:
        falla(path, f"{metodo} {path} → {r.status_code} ({etiqueta})")
    elif MARCA in cuerpo and not (r.status_code >= 400 and pidio_marca):
        falla(path, f"{metodo} {path} → {r.status_code} con datos de B ({etiqueta})")
    elif con_id_b and 200 <= r.status_code < 300:
        falla(path, f"{metodo} {path} → {r.status_code} sobre un recurso de B; debería ser 404 ({etiqueta})")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rutas", default="", help="solo las rutas que empiezan con este prefijo")
    ap.add_argument("--solo-get", action="store_true")
    ap.add_argument("--sin-recrear", action="store_true",
                    help="no re-crear el municipio de aislamiento (por defecto se re-crea: las mutaciones lo modifican)")
    args = ap.parse_args()
    if not args.sin_recrear:
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                         "seed_municipio_aislamiento.py"), "--recrear"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            sys.exit(f"ABORT: no se pudo re-crear el municipio de aislamiento:\n{r.stdout[-800:]}\n{r.stderr[-800:]}")
    # Git Bash convierte "/api/v1/x" en "C:/Program Files/Git/api/v1/x": se recorta desde /api/.
    if "/api/" in args.rutas:
        args.rutas = args.rutas[args.rutas.index("/api/"):]
    if not any(isinstance(r, APIRoute) and r.path.startswith(args.rutas) for r in app.routes):
        sys.exit(f"ABORT: el filtro --rutas {args.rutas!r} no deja ninguna ruta (sería un falso verde).")

    async with AsyncSessionLocal() as db:
        ids = await ids_aislamiento(db)
        id_b = ids["municipio"]
        numero_b = (await db.execute(text(
            "SELECT numero_expediente FROM tramite WHERE id_tramite = :i"), {"i": ids["tramite"]})).scalar()
        admin_1 = (await db.execute(text(
            "SELECT email FROM usuarios WHERE id_municipio = 1 AND nivel_acceso = 1 AND activo AND email IS NOT NULL "
            "AND debe_cambiar_password = FALSE ORDER BY id_usuario LIMIT 1"))).scalar()
        vecino_a = (await db.execute(text("""
            SELECT c.id_ciudadano FROM ciudadanos c JOIN ciudadano_credencial cc ON cc.id_ciudadano = c.id_ciudadano
             WHERE c.id_municipio = 1 AND cc.activado AND c.activo ORDER BY c.id_ciudadano LIMIT 1"""))).scalar()
        reclamo_vecino_a = (await db.execute(text(
            "SELECT min(id_reclamo) FROM reclamos WHERE id_municipio = 1 AND id_ciudadano = :c"),
            {"c": vecino_a})).scalar()
    print(f"Municipio de aislamiento: {id_b}; admin del municipio 1: {admin_1}")

    rutas = [r for r in app.routes if isinstance(r, APIRoute) and r.path.startswith(args.rutas)]
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=60) as c:
        # Los logins de B tocan sus filas (último login, registro de logins): van antes del checksum.
        h_a = await login(c, admin_1)
        h_b = await login(c, "admin.b@aislamiento.test", ORIGEN_B)
        r = await c.post("/api/v1/publico/auth/login", json={"dni": "97000001", "password": CLAVE},
                         headers={"Origin": ORIGEN_B_VECINOS})
        hv_b = {"Authorization": f"Bearer {r.json()['access_token']}", "Origin": ORIGEN_B_VECINOS} \
            if r.status_code == 200 else None
        antes = await checksum_b(id_b)

        # 1. GET de todas las rutas como admin del municipio 1.
        print(f"\n1. GET como admin del municipio 1 ({len(rutas)} rutas en el filtro)")
        sin_cubrir = 0
        for ruta in rutas:
            if "GET" not in ruta.methods:
                continue
            motivo = saltear(ruta.path)
            if motivo:
                CUENTA["salteadas"] += 1
                continue
            try:
                paths = armar_paths(ruta, ids, numero_b)
            except KeyError as e:
                sin_cubrir += 1
                falla(ruta.path, f"GET {ruta.path} → ruta sin cubrir (parámetro {e.args[0]} sin mapear)")
                continue
            for p, con_b in paths:
                r = await c.get(p, params=query_de(ruta, ids), headers=h_a)
                revisar(p, "GET", r, con_b, "GET como municipio 1")

        # 2. Control positivo: el admin de B ve lo suyo (prueba que la fixture y el mapeo andan).
        print("2. control positivo como admin de B")
        for plantilla in CONTROL_POSITIVO:
            if not plantilla.startswith(args.rutas):
                continue
            ruta = next((r for r in app.routes if isinstance(r, APIRoute) and r.path == plantilla and "GET" in r.methods), None)
            if ruta is None:
                falla(plantilla, f"control positivo: no existe GET {plantilla}")
                continue
            p, _ = armar_paths(ruta, ids, numero_b)[0]
            r = await c.get(p, headers=h_b)
            CUENTA["control positivo"] += 1
            if r.status_code != 200 or MARCA not in r.text:
                falla(p, f"control positivo: GET {p} como admin de B → {r.status_code} {'sin' if MARCA not in r.text else 'con'} marca")

        # 2b. Maestros → municipios: desde F3 solo la lee el super administrador (lo prueba
        # smoke_super_admin.py); ningún administrador de municipio, tampoco el del base.
        if "/api/v1/admin/municipios".startswith(args.rutas):
            r = await c.get("/api/v1/admin/municipios", headers=h_b)
            CUENTA["municipios"] += 1
            if r.status_code != 403:
                falla("/api/v1/admin", f"GET /api/v1/admin/municipios como admin de B → {r.status_code}; debería ser 403")
            r = await c.get(f"/api/v1/admin/municipios/{id_b}", headers=h_b)
            CUENTA["municipios"] += 1
            if r.status_code != 403:
                falla("/api/v1/admin", f"GET /api/v1/admin/municipios/{id_b} como admin de B → {r.status_code}; debería ser 403")
            r = await c.get("/api/v1/admin/municipios", headers=h_a)
            CUENTA["municipios"] += 1
            if r.status_code != 403:
                falla("/api/v1/admin", f"GET /api/v1/admin/municipios como admin del municipio base → {r.status_code}; debería ser 403")

        if not args.solo_get:
            # 3. Mutaciones como admin del municipio 1 sobre ids de B (y altas con ids de B en el body).
            print("3. mutaciones como admin del municipio 1")
            for ruta in rutas:
                for metodo in sorted(ruta.methods - {"GET", "HEAD", "OPTIONS"}):
                    if saltear(ruta.path):
                        continue
                    try:
                        paths = armar_paths(ruta, ids, numero_b)
                    except KeyError as e:
                        falla(ruta.path, f"{metodo} {ruta.path} → ruta sin cubrir (parámetro {e.args[0]} sin mapear)")
                        continue
                    body, body_con_b = body_de(ruta, ids)
                    for p, con_b in paths:
                        if not con_b and (not body_con_b or metodo != "POST" or NO_MUTAR_SIN_ID.search(p)):
                            continue  # sin ids de B no hay nada que probar (y no se tocan datos del municipio 1)
                        # Con los query params requeridos (p. ej. ?activo= de /estado): sin ellos
                        # el 422 de validación llega antes que el guard del municipio.
                        cuerpo = body_especial(p, ids, metodo)
                        r = await c.request(metodo, p, json=body if cuerpo is None else cuerpo,
                                            params=query_de(ruta, ids), headers=h_a)
                        etiqueta = "mutación sobre id de B" if con_b else "alta con ids de B en el body"
                        revisar(p, metodo, r, True, etiqueta)

        # 4. Vecino: el de B no ve datos del municipio 1; el del municipio 1 no entra desde la dirección de B.
        if "/api/v1/publico".startswith(args.rutas) or args.rutas.startswith("/api/v1/publico"):
            print("4. vecino")
            if hv_b is None:
                falla("/api/v1/publico", "login del vecino de B falló")
            else:
                if reclamo_vecino_a:
                    r = await c.get(f"/api/v1/publico/reclamos/{reclamo_vecino_a}", headers=hv_b)
                    CUENTA["vecino"] += 1
                    if r.status_code != 404:
                        falla("/api/v1/publico", f"vecino de B → reclamo {reclamo_vecino_a} del municipio 1 → {r.status_code}")
                for ruta in rutas:
                    if not ruta.path.startswith("/api/v1/publico") or "GET" not in ruta.methods or saltear(ruta.path) \
                            or re.search(r"{", ruta.path):
                        continue
                    r = await c.get(ruta.path, params=query_de(ruta, ids), headers=hv_b)
                    CUENTA["vecino"] += 1
                    if r.status_code >= 500:
                        falla(ruta.path, f"vecino de B: GET {ruta.path} → {r.status_code}")
                    elif r.status_code < 300 and NUMERO_DE_A.search(r.text or ""):
                        falla(ruta.path, f"vecino de B: GET {ruta.path} devuelve números del municipio 1")
            tv_a = crear_token_ciudadano(vecino_a, 1)
            # El vecino del municipio 1 no ve catálogos ni filas de B (los textos de B llevan la marca).
            for ruta in rutas:
                if not ruta.path.startswith("/api/v1/publico") or "GET" not in ruta.methods or saltear(ruta.path) \
                        or re.search(r"{", ruta.path):
                    continue
                r = await c.get(ruta.path, params=query_de(ruta, ids), headers={"Authorization": f"Bearer {tv_a}"})
                revisar(ruta.path, "GET", r, False, "vecino del municipio 1")
            r = await c.get("/api/v1/publico/auth/me", headers={"Authorization": f"Bearer {tv_a}", "Origin": ORIGEN_B_VECINOS})
            CUENTA["vecino"] += 1
            if r.status_code != 401:
                falla("/api/v1/publico", f"vecino del municipio 1 con el origen de B → {r.status_code} (esperado 401)")

            # 5. Público sin token: la identidad sale del origen.
            print("5. público por origen")
            r_b = await c.get("/api/v1/publico/identidad-municipio", headers={"Origin": ORIGEN_B_VECINOS})
            r_1 = await c.get("/api/v1/publico/identidad-municipio")
            CUENTA["público"] += 2
            if r_b.status_code != 200 or MARCA not in r_b.text:
                falla("/api/v1/publico", f"identidad con el origen de B → {r_b.status_code} sin el nombre de B")
            if r_1.status_code != 200 or MARCA in r_1.text:
                falla("/api/v1/publico", f"identidad sin origen → {r_1.status_code} {'con' if MARCA in r_1.text else 'sin'} datos de B")

    despues = await checksum_b(id_b)
    cambiadas = [t for t in antes if antes[t] != despues.get(t)]
    if cambiadas:
        falla("(base)", f"datos de B modificados en: {cambiadas}")

    print("\nRequests por tipo: " + ", ".join(f"{k}={v}" for k, v in sorted(CUENTA.items())))
    total = sum(len(v) for v in FALLAS.values())
    for grupo in sorted(FALLAS):
        print(f"\n[{grupo}] {len(FALLAS[grupo])} fallas")
        for m in FALLAS[grupo]:
            print(f"  FALLA {m}")
    print(f"\nRESULTADO: {total} fallas en {len(FALLAS)} grupos")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
