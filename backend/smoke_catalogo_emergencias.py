# -*- coding: utf-8 -*-
"""
Smoke in-process — catálogo de emergencias del vecino (PLAN_CATALOGO_EMERGENCIAS_VECINO.md, mig 145).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_catalogo_emergencias.py

SOLO LOCAL. La alerta al COM está CAPTURADA: no sale ningún aviso ni mail. Correr con DB_BARRERA=true y con
false. Usa el vecino demo 3; da de baja los eventos que crea y deja el catálogo como estaba.
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

from app.api.routes import publico_emergencias as rutas  # noqa: E402
from app.core.auth import create_access_token, crear_token_ciudadano  # noqa: E402
from app.core.sistema import SesionSistema  # noqa: E402
from app.main import app  # noqa: E402
from app.services.municipios.alta import CATALOGOS_COPIABLES, _TABLAS_COPIABLES  # noqa: E402
from app.services.municipios.clonado import Clonador, FilaOmitida, conexion_asyncpg  # noqa: E402
from app.services.municipios.cruces import contar_cruces  # noqa: E402

ALERTAS: list[int] = []
VECINO = 3
RES: list[bool] = []
CREADOS: list[int] = []
BASE = "/api/v1/publico/emergencias"
ADMIN = "/api/v1/admin"
DIR = "Av. Maipú 2500 (prueba del catálogo)"


async def _alerta(id_evento, background_tasks=None):
    ALERTAS.append(id_evento)
    return 1


rutas.notificar_alerta_panico = _alerta
rutas.check_rate_limit = lambda *a, **k: None


def check(nombre: str, ok, detalle="") -> None:
    RES.append(bool(ok))
    print(f"  {'OK  ' if ok else 'FAIL'} {nombre}{(' — ' + str(detalle)) if not ok else ''}")


async def sql(q: str, **p):
    async with SesionSistema() as db:
        r = await db.execute(text(q), p)
        filas = r.mappings().all() if r.returns_rows else []
        await db.commit()
        return [dict(f) for f in filas]


async def evento(id_evento: int) -> dict:
    return (await sql("""
        SELECT t.codigo AS tipo, st.codigo AS subtipo, p.codigo AS prioridad, e.es_panico, e.clasificacion_vecino,
               e.observaciones_recepcion, e.id_ciudadano_buc, e.id_subarea, t.id_subarea AS sub_tipo, l.payload_json
          FROM emergencia_evento e JOIN emergencia_tipo t ON t.id_emergencia_tipo = e.id_tipo
          LEFT JOIN emergencia_subtipo st ON st.id_emergencia_subtipo = e.id_subtipo
          JOIN emergencia_prioridad p ON p.id_emergencia_prioridad = e.id_prioridad
          JOIN emergencia_log l ON l.id_evento = e.id_emergencia_evento AND l.tipo_accion = 'CREACION'
         WHERE e.id_emergencia_evento = :i""", i=id_evento))[0]


async def main() -> int:
    admin = (await sql("SELECT id_usuario FROM usuarios WHERE id_municipio = 1 AND nivel_acceso = 1 AND activo "
                       "AND NOT COALESCE(debe_cambiar_password, FALSE) ORDER BY id_usuario LIMIT 1"))[0]["id_usuario"]
    HA = {"Authorization": "Bearer " + create_access_token({"sub": str(admin), "mun": 1, "sf": True})}
    HV = {"Authorization": "Bearer " + crear_token_ciudadano(VECINO, 1)}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=60) as c:
        async def reportar(**body):
            r = await c.post(f"{BASE}/eventos", headers=HV, json={"direccion_evento": DIR, **body})
            if r.status_code == 201:
                CREADOS.append(r.json()["id_emergencia_evento"])
            return r

        print("1. Catálogo del vecino")
        r = await c.get(f"{BASE}/catalogo")
        check("sin sesión no responde", r.status_code in (401, 403), r.status_code)
        r = await c.get(f"{BASE}/catalogo", headers=HA)
        check("una sesión de funcionario no entra", r.status_code in (401, 403), r.status_code)
        r = await c.get(f"{BASE}/catalogo", headers=HV)
        check("responde 200", r.status_code == 200, r.text[:200])
        cat = r.json() if r.status_code == 200 else {"grupos": [], "botones_sos": {}}
        check("los 10 grupos en el orden aprobado", [g["nombre"] for g in cat["grupos"]] == [
            "Salud y accidentes", "Fuego", "Gas y sustancias", "Árboles y cables", "Derrumbes", "Agua y tormenta",
            "Personas en problemas", "Animales", "Seguridad", "Otra emergencia"], [g["nombre"] for g in cat["grupos"]])
        opciones = {o["nombre"]: o for g in cat["grupos"] for o in g["opciones"]}
        check("34 opciones", len(opciones) == 34, len(opciones))
        check("«Alerta de pánico» no está en la lista: solo desde su botón", "Alerta de pánico" not in opciones)
        check("no viaja nada del triage", all(set(o) == {"id_opcion", "nombre", "texto_ayuda", "descripcion_obligatoria"}
                                             for o in opciones.values()), next(iter(opciones.values()), None))
        check("los cinco botones SOS con su opción",
              {k: v["nombre"] for k, v in cat["botones_sos"].items()} == {
                  "asistencia": "Emergencia médica", "accidente": "Accidente de tránsito", "incendio": "Incendio",
                  "tormenta": "Daños por tormenta", "seguridad": "Alerta de pánico"}, cat["botones_sos"])
        if not opciones:
            return 1
        textos = " ".join(opciones).lower()
        check("lo que no se ofrece no aparece", not any(
            x in textos for x in ("broma", "simulacro", "agradecimiento", "prófugo", "queja", "terrorismo")), textos)

        print("2. Reportar desde el catálogo")
        r = await reportar(id_opcion=opciones["Objeto sospechoso"]["id_opcion"], descripcion="Un bolso")
        check("201", r.status_code == 201, r.text[:200])
        e = await evento(r.json()["id_emergencia_evento"])
        check("tipo y subtipo del COM", (e["tipo"], e["subtipo"]) == ("HALLAZGO", "OBJETO_DUDOSO_PELIGROSO"), e)
        check("guarda lo que eligió el vecino", e["clasificacion_vecino"] == "Objeto sospechoso", e)
        check("gestión del tipo, vecino del token, no es pánico",
              e["id_subarea"] == e["sub_tipo"] and e["id_ciudadano_buc"] == VECINO and not e["es_panico"], e)
        check("el log de creación nombra la opción", (e["payload_json"] or {}).get("opcion") == "Objeto sospechoso", e)
        r = await reportar(id_opcion=opciones["Violencia familiar o de género"]["id_opcion"])
        e = await evento(r.json()["id_emergencia_evento"])
        check("violencia familiar o de género: tipo propio y P1",
              (e["tipo"], e["prioridad"]) == ("VIOLENCIA_FAMILIAR_GENERO", "P1"), e)

        print("3. Validaciones")
        otra = opciones["Otra emergencia"]
        check("«Otra emergencia» pide descripción", otra["descripcion_obligatoria"])
        r = await reportar(id_opcion=otra["id_opcion"], descripcion="   ")
        check("sin descripción: 422 con el motivo", r.status_code == 422 and "qué está pasando" in r.text, r.text[:200])
        r = await reportar(id_opcion=otra["id_opcion"], descripcion="Se hundió la vereda")
        check("con descripción: 201 como pedido genérico", r.status_code == 201 and (
            await evento(r.json()["id_emergencia_evento"]))["tipo"] == "PEDIDO_GENERICO_AUXILIO", r.text[:200])
        r = await reportar(id_opcion=2_000_000_000)
        check("opción inexistente: 422", r.status_code == 422 and "pción" in r.text, r.text[:200])
        r = await reportar(id_opcion=3_000_000_000)
        check("id fuera de rango: 422, no 500", r.status_code == 422, r.status_code)
        r = await reportar()
        check("sin clasificar: 422", r.status_code == 422, r.status_code)
        r = await reportar(id_opcion=otra["id_opcion"], boton_sos="incendio", descripcion="x y z")
        check("dos clasificaciones a la vez: 422", r.status_code == 422, r.status_code)
        ajena = (await sql("SELECT id_emergencia_opcion_vecino AS i FROM emergencia_opcion_vecino "
                           "WHERE id_municipio <> 1 AND codigo = 'ROBO' LIMIT 1"))[0]["i"]
        r = await reportar(id_opcion=ajena)
        check("opción de otro municipio: 422 como inexistente", r.status_code == 422 and "pción" in r.text, r.text[:200])

        print("4. Botones SOS")
        for boton, tipo, prio in (("asistencia", "EMERGENCIA_SALUD", "P1"), ("incendio", "INCENDIO", "P1"),
                                  ("accidente", "ACCIDENTE_VIA_PUBLICA", "P2"), ("tormenta", "TORMENTA_SEVERA", "P2")):
            r = await reportar(boton_sos=boton)
            e = await evento(r.json()["id_emergencia_evento"]) if r.status_code == 201 else {"error": r.text[:200]}
            check(f"{boton} → {tipo} {prio}, sin pánico",
                  (e.get("tipo"), e.get("prioridad"), e.get("es_panico")) == (tipo, prio, False), e)
        ALERTAS.clear()
        r = await reportar(boton_sos="seguridad")
        e = await evento(r.json()["id_emergencia_evento"]) if r.status_code == 201 else {"error": r.text[:200]}
        check("seguridad → Alerta de pánico P1, marcada pánico sin depender del texto",
              (e.get("tipo"), e.get("prioridad"), e.get("es_panico")) == ("ALERTA_PANICO", "P1", True), e)
        check("avisa al COM una vez", ALERTAS == CREADOS[-1:], ALERTAS)
        r = await reportar(boton_sos="robo")
        check("botón desconocido: 422", r.status_code == 422, r.status_code)

        print("5. El pánico no depende del catálogo")
        await sql("UPDATE emergencia_opcion_vecino SET activo = FALSE WHERE id_municipio = 1 AND boton_sos IS NOT NULL")
        try:
            r = await reportar(boton_sos="seguridad")
            e = await evento(r.json()["id_emergencia_evento"]) if r.status_code == 201 else {"error": r.text[:200]}
            check("sin su opción, igual entra como Alerta de pánico",
                  (e.get("tipo"), e.get("es_panico"), e.get("clasificacion_vecino")) == ("ALERTA_PANICO", True, "Alerta de pánico"), e)
            await sql("UPDATE emergencia_tipo SET activo = FALSE WHERE id_municipio = 1 AND codigo = 'ALERTA_PANICO'")
            r = await reportar(boton_sos="seguridad")
            e = await evento(r.json()["id_emergencia_evento"]) if r.status_code == 201 else {"error": r.text[:200]}
            check("sin el tipo, entra como pedido de auxilio y sigue siendo pánico",
                  (e.get("tipo"), e.get("es_panico")) == ("PEDIDO_GENERICO_AUXILIO", True), e)
            r = await reportar(boton_sos="incendio")
            check("otro SOS sin opción: 422 (la app abre el formulario)", r.status_code == 422, r.status_code)
            r = await c.get(f"{BASE}/catalogo", headers=HV)
            check("el catálogo lo informa", r.json()["botones_sos"] == {}, r.json()["botones_sos"])
        finally:
            await sql("UPDATE emergencia_tipo SET activo = TRUE WHERE id_municipio = 1 AND codigo = 'ALERTA_PANICO'")
            await sql("UPDATE emergencia_opcion_vecino SET activo = TRUE WHERE id_municipio = 1 AND boton_sos IS NOT NULL")

        print("6. Una opción cuyo tipo se dio de baja no se ofrece ni se acepta")
        await sql("UPDATE emergencia_tipo SET activo = FALSE WHERE id_municipio = 1 AND codigo = 'MALTRATO_ANIMAL'")
        try:
            cat2 = (await c.get(f"{BASE}/catalogo", headers=HV)).json()
            check("no está en el catálogo", "Maltrato animal" not in [o["nombre"] for g in cat2["grupos"] for o in g["opciones"]])
            r = await reportar(id_opcion=opciones["Maltrato animal"]["id_opcion"])
            check("422", r.status_code == 422, r.status_code)
        finally:
            await sql("UPDATE emergencia_tipo SET activo = TRUE WHERE id_municipio = 1 AND codigo = 'MALTRATO_ANIMAL'")

        print("7. La versión anterior de la app sigue andando")
        tipos = (await c.get(f"{BASE}/tipos", headers=HV)).json()
        robo = next(t for t in tipos if t["codigo"] == "ROBO")
        r = await reportar(id_tipo=robo["id_emergencia_tipo"], descripcion="ALERTA DE PÁNICO — desde la app")
        e = await evento(r.json()["id_emergencia_evento"]) if r.status_code == 201 else {"error": r.text[:200]}
        check("id_tipo + prefijo: pánico como siempre",
              (e.get("tipo"), e.get("es_panico"), e.get("clasificacion_vecino")) == ("ROBO", True, None), e)

        print("8. Lo que ve cada uno")
        mios = (await c.get(f"{BASE}/eventos", headers=HV, params={"limit": 100})).json()
        m = next(x for x in mios if x["id_emergencia_evento"] == CREADOS[0])
        check("el vecino ve su opción, no el tipo del COM",
              (m["tipo_nombre"], m["subtipo_nombre"]) == ("Objeto sospechoso", None), m)
        d = (await c.get(f"/api/v1/emergencias/eventos/{CREADOS[0]}", headers=HA)).json()
        check("el COM ve su tipo y lo que eligió el vecino",
              (d.get("tipo_codigo"), d.get("clasificacion_vecino")) == ("HALLAZGO", "Objeto sospechoso"), d.get("clasificacion_vecino"))

        print("9. Maestros")
        r = await c.get(f"{ADMIN}/emergencia_opcion_vecino", headers=HA)
        check("lista las opciones del municipio", r.status_code == 200 and len(r.json()) == 35, r.status_code)
        fila = next((x for x in r.json() if x["codigo"] == "VIOLENCIA_FAMILIAR_GENERO"), None) if r.status_code == 200 else None
        if fila:
            pk = fila["id_emergencia_opcion_vecino"]
            r = await c.put(f"{ADMIN}/emergencia_opcion_vecino/{pk}", headers=HA,
                            json={"texto_ayuda": "También podés llamar a la Línea 144."})
            check("el municipio define el texto con los teléfonos", r.status_code == 200, r.text[:200])
            cat3 = (await c.get(f"{BASE}/catalogo", headers=HV)).json()
            ayuda = next(o for g in cat3["grupos"] for o in g["opciones"] if o["id_opcion"] == pk)["texto_ayuda"]
            check("y el vecino lo ve", ayuda == "También podés llamar a la Línea 144.", ayuda)
            await c.put(f"{ADMIN}/emergencia_opcion_vecino/{pk}", headers=HA, json={"texto_ayuda": None})
            sub_robo = (await sql("SELECT s.id_emergencia_subtipo AS i FROM emergencia_subtipo s JOIN emergencia_tipo t "
                                  "ON t.id_emergencia_tipo = s.id_tipo WHERE t.id_municipio = 1 AND t.codigo = 'ROBO' "
                                  "AND t.activo LIMIT 1"))[0]["i"]
            r = await c.put(f"{ADMIN}/emergencia_opcion_vecino/{pk}", headers=HA, json={"id_subtipo": sub_robo})
            check("subtipo de otro tipo: 422 con el motivo", r.status_code == 422 and "ubtipo" in r.text, f"{r.status_code} {r.text[:120]}")
            r = await c.put(f"{ADMIN}/emergencia_opcion_vecino/{pk}", headers=HA, json={"boton_sos": "incendio"})
            check("dos opciones con el mismo botón SOS: 409", r.status_code == 409, r.status_code)
            r = await c.put(f"{ADMIN}/emergencia_opcion_vecino/{pk}", headers=HA, json={"id_grupo": None})
            check("sin grupo ni botón: 422", r.status_code == 422, r.status_code)
            gr_ajeno = (await sql("SELECT id_emergencia_grupo_vecino AS i FROM emergencia_grupo_vecino WHERE id_municipio <> 1 LIMIT 1"))[0]["i"]
            r = await c.put(f"{ADMIN}/emergencia_opcion_vecino/{pk}", headers=HA, json={"id_grupo": gr_ajeno})
            check("grupo de otro municipio: 422", r.status_code == 422, r.status_code)
        r = await c.get(f"{ADMIN}/emergencia_grupo_vecino", headers=HA)
        check("lista los grupos", r.status_code == 200 and len(r.json()) == 10, r.status_code)

    print("10. El alta de un municipio copia el catálogo (con rollback: no queda nada)")
    modelo = (await sql("SELECT id_municipio AS i FROM municipios WHERE estado = 'modelo'"))[0]["i"]
    async with SesionSistema() as db:
        nuevo = await db.scalar(text(
            "INSERT INTO municipios (nombre, estado, codigo_corto, subdominio, codigo_pais, id_provincia) "
            "SELECT 'Prueba copia 145', 'puesta_en_marcha', 'QXZW', 'prueba-copia-145', 'AR', min(id_provincia) "
            "FROM municipios RETURNING id_municipio"))
        conn = await conexion_asyncpg(db)
        c = Clonador(conn, nuevo, permitidas=_TABLAS_COPIABLES, solo_activas=True)
        await c.cargar_clases()
        omitidas = 0
        for t in CATALOGOS_COPIABLES["emergencias"]:
            for f in await conn.fetch(f'SELECT "id_{t}" AS i FROM "{t}" WHERE id_municipio = $1 AND activo ORDER BY 1', modelo):
                try:
                    await c.clonar(t, f["i"])
                except FilaOmitida:
                    omitidas += 1
        n = {t: await conn.fetchval(f'SELECT count(*) FROM "{t}" WHERE id_municipio = $1', nuevo)
             for t in ("emergencia_tipo", "emergencia_grupo_vecino", "emergencia_opcion_vecino")}
        check("52 tipos, 10 grupos y 35 opciones, ninguna omitida",
              list(n.values()) == [52, 10, 35] and omitidas == 0, (n, omitidas))
        check("los 5 botones SOS", await conn.fetchval(
            "SELECT count(boton_sos) FROM emergencia_opcion_vecino WHERE id_municipio = $1", nuevo) == 5)
        cruces = await contar_cruces(conn, nuevo)
        check("ninguna referencia a otro municipio", cruces == [], cruces)
        await db.rollback()

    return 0


async def correr() -> int:
    try:
        return await main()
    finally:
        if CREADOS:
            await sql("UPDATE emergencia_evento SET activo = FALSE WHERE id_emergencia_evento = ANY(:i)", i=CREADOS)
        print(f"\n{sum(RES)}/{len(RES)} OK (barrera={settings.DB_BARRERA})")


rc = asyncio.run(correr())
sys.exit(rc or (0 if RES and all(RES) else 1))
