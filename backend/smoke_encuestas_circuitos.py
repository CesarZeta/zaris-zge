# -*- coding: utf-8 -*-
"""
Smoke in-process - Encuestas: todas las ramas en los cuatro circuitos (mig 136, 2026-11-06).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_encuestas_circuitos.py

SOLO LOCAL: aborta si la DB no es zaris_dev. El mail va en MOCK y el aviso al area se captura.

Cubre lo aprobado por Cesar en PLAN_MULTI_MUNICIPIO_F4_F5.md -> "Encuestas: textos aprobados":
  1. Plantillas: los textos de cada circuito y los mismos valores que reclamos, en el municipio
     de direccion_base y en el modelo.
  2. Formulario publico de cada circuito en cada rama (GET + POST como lo hace encuesta.html).
  3. Pedido de contacto: la referencia del aviso al area en cada circuito.
  4. Resumen integrado: por area y por circuito cuentan los cuatro; el filtro de circuito alcanza
     a todos los bloques, y la suma por circuito da el total.

Crea envios y respuestas de prueba en el municipio de direccion_base y los borra al terminar.
"""
import asyncio
import os
import sys
import uuid
from datetime import date, timedelta
from typing import Any, Optional

import httpx

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

os.environ.setdefault("ENV_FILE", ".env.local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402

if "zaris_dev" not in settings.ASYNC_DATABASE_URI:
    sys.exit("ABORT: este smoke es SOLO LOCAL (la DB configurada no es zaris_dev). No corre contra prod.")

settings.RESEND_API_KEY = ""  # mail en MOCK: .env.local tiene una clave real (CLAUDE.md §5)

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.services import encuestas_service as svc  # noqa: E402

import logging  # noqa: E402
logging.getLogger("httpx").setLevel(logging.WARNING)

PWD_DEV = os.environ.get("ZARIS_QA_PASS") or "123456"
ADMIN = "ciudadanovl@municipio.gob.ar"
BASE = "/api/v1/admin/encuestas"
PUBLICO = "/api/v1/publico/encuesta"
CIRCUITOS = ("reclamos", "turnos", "tramites", "entradas")
CONTACTO = "¿Querés que un responsable del municipio te contacte?"
FALTO = "¿Qué faltó para que tu experiencia fuera mejor?"
PROBLEMA = "¿Cuál fue el principal problema?"

# Textos aprobados, tal cual el plan. Es la referencia contra la que se mide la migración.
TEXTOS: dict[str, dict[str, list[str]]] = {
    "reclamos": {
        "satisfechos": ["¿Qué aspecto destacarías de la atención recibida?", "¿Recomendarías este canal de reclamos a otros vecinos?"],
        "neutrales": [FALTO, "¿La resolución fue lo que esperabas?"],
        "insatisfechos": [PROBLEMA, CONTACTO],
    },
    "turnos": {
        "satisfechos": ["¿Qué aspecto destacarías de la atención recibida?", "¿Recomendarías este punto de atención a otros vecinos?"],
        "neutrales": [FALTO, "¿La atención fue lo que esperabas?"],
        "insatisfechos": [PROBLEMA, CONTACTO],
    },
    "tramites": {
        "satisfechos": ["¿Qué aspecto destacarías de la gestión?", "¿Recomendarías hacer este trámite por este canal?"],
        "neutrales": [FALTO, "¿El resultado del trámite fue lo que esperabas?"],
        "insatisfechos": [PROBLEMA, CONTACTO],
    },
    "entradas": {
        "satisfechos": ["¿Qué aspecto destacarías del evento?", "¿Recomendarías estos eventos a otros vecinos?"],
        "neutrales": [FALTO, "¿El evento fue lo que esperabas?"],
        "insatisfechos": [PROBLEMA, CONTACTO],
    },
}

# Los únicos valores cuyo texto visible cambia por circuito.
ETIQUETAS: dict[str, dict[str, str]] = {
    "demora": {"reclamos": "Demora excesiva", "turnos": "Demora excesiva", "tramites": "Demora excesiva", "entradas": "Demora en el ingreso"},
    "no_resuelto": {"reclamos": "No resolvieron el problema", "turnos": "No resolvieron mi consulta", "tramites": "No resolvieron mi trámite", "entradas": "No fue lo que se anunció"},
    "solucion_incorrecta": {"reclamos": "Solución incorrecta", "turnos": "Respuesta incorrecta", "tramites": "Resolución incorrecta", "entradas": "Mala organización"},
    "mejor_solucion": {"reclamos": "Mejor solución", "turnos": "Mejor respuesta", "tramites": "Mejor resolución", "entradas": "Mejor organización"},
    "calidad": {"reclamos": "Calidad de la solución", "turnos": "Calidad de la atención", "tramites": "Calidad de la gestión", "entradas": "Calidad del evento"},
}

ok_count = 0
fail_count = 0
skip_count = 0
fallidos: list[str] = []


def check(nombre: str, cond: bool, extra: str = "") -> bool:
    global ok_count, fail_count
    if cond:
        ok_count += 1
        print(f"  OK   {nombre}")
    else:
        fail_count += 1
        print(f"  FAIL {nombre} {extra}")
        fallidos.append(nombre)
    return cond


def skip(nombre: str, motivo: str) -> None:
    global skip_count
    skip_count += 1
    print(f"  SKIP {nombre} ({motivo})")


async def filas(sql: str, **params) -> list[dict[str, Any]]:
    async with AsyncSessionLocal() as s:
        return [dict(r) for r in (await s.execute(text(sql), params)).mappings().all()]


async def una(sql: str, **params) -> Optional[dict[str, Any]]:
    res = await filas(sql, **params)
    return res[0] if res else None


async def preguntas_de(id_municipio: int, tipo: str) -> list[dict[str, Any]]:
    return await filas("""
        SELECT q.id_encuesta_pregunta AS id, q.rama, q.tipo, q.orden, q.obligatoria, q.texto,
               COALESCE((SELECT json_agg(json_build_object('v', o.valor, 't', o.texto) ORDER BY o.orden)
                           FROM encuesta_opcion o
                          WHERE o.id_pregunta = q.id_encuesta_pregunta AND o.activo = TRUE
                            AND o.id_municipio = :m), '[]'::json) AS opciones
          FROM encuesta_pregunta q
          JOIN encuesta_plantilla p ON p.id_encuesta_plantilla = q.id_plantilla
         WHERE p.id_municipio = :m AND p.tipo = :t AND p.activo = TRUE AND q.activo = TRUE
         ORDER BY q.rama, q.orden
    """, m=id_municipio, t=tipo)


async def test_plantillas(id_municipio: int, nombre: str) -> None:
    print(f"\n[1] Plantillas de {nombre}")
    referencia = await preguntas_de(id_municipio, "reclamos")
    valores_ref = {
        (q["rama"], q["tipo"], i): [o["v"] for o in q["opciones"]]
        for rama in TEXTOS["reclamos"]
        for i, q in enumerate(x for x in referencia if x["rama"] == rama)
    }
    for tipo in CIRCUITOS:
        pregs = await preguntas_de(id_municipio, tipo)
        for rama, esperadas in TEXTOS[tipo].items():
            reales = [q["texto"] for q in pregs if q["rama"] == rama]
            check(f"{tipo}/{rama}: textos del plan", reales == esperadas, f"{reales}")
            # Sin orden repetido dentro de la rama: el formulario ordena solo por `orden`.
            ordenes = [q["orden"] for q in pregs if q["rama"] == rama]
            check(f"{tipo}/{rama}: orden sin repetir", len(set(ordenes)) == len(ordenes), f"{ordenes}")
        for rama in TEXTOS[tipo]:
            for i, q in enumerate(x for x in pregs if x["rama"] == rama):
                esperado = valores_ref.get((rama, q["tipo"], i))
                check(f"{tipo}/{rama}/{i}: mismos valores que reclamos",
                      [o["v"] for o in q["opciones"]] == esperado, f"{q['opciones']} vs {esperado}")
                check(f"{tipo}/{rama}/{i}: obligatoria", q["obligatoria"] is True)
        etiquetas = {o["v"]: o["t"] for q in pregs for o in q["opciones"]}
        for valor, por_circuito in ETIQUETAS.items():
            check(f"{tipo}: texto visible de {valor}", etiquetas.get(valor) == por_circuito[tipo],
                  f"{etiquetas.get(valor)!r}")
    turnos = await preguntas_de(id_municipio, "turnos")
    espera = [q for q in turnos if q["texto"] == "¿El tiempo de espera te pareció razonable?"]
    check("turnos conserva «tiempo de espera» para todas las ramas",
          len(espera) == 1 and espera[0]["rama"] == "todos" and espera[0]["tipo"] == "likert5")
    orden_espera = espera[0]["orden"] if espera else 0
    check("turnos: las ramas van después de «tiempo de espera»",
          all(q["orden"] > orden_espera for q in turnos if q["rama"] != "todos"))


async def crear_envio(id_municipio: int, tipo: str, id_origen: int, id_ciudadano: int, id_subarea: int) -> dict[str, Any]:
    col = {"reclamos": "id_reclamo", "turnos": "id_turno", "tramites": "id_tramite", "entradas": "id_evento_reserva"}[tipo]
    token = str(uuid.uuid4())
    async with AsyncSessionLocal() as s:
        id_plantilla = await s.scalar(text("""
            SELECT id_encuesta_plantilla FROM encuesta_plantilla
             WHERE id_municipio = :m AND tipo = :t AND activo = TRUE
             ORDER BY id_encuesta_plantilla LIMIT 1
        """), {"m": id_municipio, "t": tipo})
        id_envio = await s.scalar(text(f"""
            INSERT INTO encuesta_envio (id_plantilla, id_ciudadano, {col}, token_unico, email_destino_snapshot,
                                        fecha_envio, fecha_expiracion, estado, id_municipio, id_subarea)
            VALUES (:p, :c, :o, CAST(:tok AS uuid), 'smoke@example.com', NOW(), NOW() + interval '15 days',
                    'enviada', :m, :s)
            RETURNING id_encuesta_envio
        """), {"p": id_plantilla, "c": id_ciudadano, "o": id_origen, "tok": token, "m": id_municipio, "s": id_subarea})
        await s.commit()
    return {"id": id_envio, "token": token, "tipo": tipo}


def armar_respuestas(preguntas: list[dict[str, Any]], rama: str, comentario: str) -> list[dict[str, Any]]:
    """Lo mismo que manda encuesta.html: las de `todos` y las de la rama."""
    salida: list[dict[str, Any]] = []
    for p in preguntas:
        if p["rama"] not in ("todos", rama):
            continue
        if p["tipo"] == "likert5":
            salida.append({"id_pregunta": p["id_pregunta"], "valor_numerico": {"insatisfechos": 1, "neutrales": 3, "satisfechos": 5}[rama]})
        elif p["tipo"] == "multiple":
            salida.append({"id_pregunta": p["id_pregunta"], "id_opcion_seleccionada": p["opciones"][0]["id_opcion"]})
        elif p["tipo"] == "si_no":
            salida.append({"id_pregunta": p["id_pregunta"], "valor_numerico": 1})
        elif p["tipo"] == "texto_libre":
            salida.append({"id_pregunta": p["id_pregunta"], "valor_texto": comentario})
    return salida


async def test_formulario_y_contacto(c: httpx.AsyncClient, id_municipio: int, origenes: dict[str, int],
                                     id_ciudadano: int, id_subarea: int, marca: str,
                                     creados: list[int]) -> list[dict[str, Any]]:
    print("\n[2] Formulario público y [3] pedido de contacto")
    avisos: list[dict[str, Any]] = []
    original = svc._notificar_solicitud_contacto

    async def capturar(db, *, id_subarea, referencia):  # noqa: ANN001
        avisos.append({"id_subarea": id_subarea, "referencia": referencia})

    svc._notificar_solicitud_contacto = capturar
    respuestas_creadas: list[dict[str, Any]] = []
    try:
        ip = 0
        for tipo in CIRCUITOS:
            for rama, clasif in (("insatisfechos", 1), ("neutrales", 3), ("satisfechos", 5)):
                env = await crear_envio(id_municipio, tipo, origenes[tipo], id_ciudadano, id_subarea)
                creados.append(env["id"])
                ip += 1
                h = {"X-Envoy-External-Address": f"10.99.0.{ip}"}
                r = await c.get(f"{PUBLICO}/{env['token']}", headers=h)
                if not check(f"{tipo}/{rama}: el formulario carga", r.status_code == 200, r.text[:200]):
                    continue
                preguntas = r.json()["preguntas"]
                visibles = sorted((p for p in preguntas if p["rama"] in ("todos", rama)), key=lambda p: p["orden"])
                textos = [p["texto"] for p in visibles if p["rama"] == rama]
                check(f"{tipo}/{rama}: se ven las preguntas de la rama", textos == TEXTOS[tipo][rama], f"{textos}")
                check(f"{tipo}/{rama}: el comentario queda al final", visibles[-1]["tipo"] == "texto_libre")
                body = {
                    "clasificacion_inicial": clasif, "tiempo_completado_seg": 5,
                    "respuestas": armar_respuestas(preguntas, rama, f"{marca} {tipo}"),
                }
                r = await c.post(f"{PUBLICO}/{env['token']}/responder", json=body, headers=h)
                check(f"{tipo}/{rama}: la respuesta se registra", r.status_code == 200 and r.json().get("ok", True) is not False,
                      f"{r.status_code} {r.text[:200]}")
                fila = await una("""
                    SELECT rama_seguida, solicita_contacto FROM encuesta_respuesta
                     WHERE id_envio = :e AND id_municipio = :m
                """, e=env["id"], m=id_municipio)
                check(f"{tipo}/{rama}: rama correcta", bool(fila) and fila["rama_seguida"] == rama, str(fila))
                # Pide contacto solo el «sí» de la rama negativa; el de recomendación no cuenta.
                check(f"{tipo}/{rama}: pedido de contacto", bool(fila) and fila["solicita_contacto"] is (rama == "insatisfechos"), str(fila))
                respuestas_creadas.append({"tipo": tipo, "rama": rama, "id_envio": env["id"]})
    finally:
        svc._notificar_solicitud_contacto = original

    por_prefijo = {"reclamos": "Reclamo #", "turnos": "Turno #", "tramites": "Trámite ", "entradas": "Evento "}
    check("hay un aviso por circuito", len(avisos) == 4, str(avisos))
    for tipo, a in zip(CIRCUITOS, avisos):
        check(f"{tipo}: referencia del aviso «{a['referencia']}»",
              a["referencia"].startswith(por_prefijo[tipo]) and "None" not in a["referencia"])
        check(f"{tipo}: el aviso va a la gestión del envío", a["id_subarea"] == id_subarea, str(a))
    return respuestas_creadas


async def test_resumen(c: httpx.AsyncClient, h: dict[str, str], id_municipio: int, marca: str, creados: list[int]) -> None:
    print("\n[4] Resumen integrado")
    periodo = {"desde": "2020-01-01", "hasta": (date.today() + timedelta(days=1)).isoformat()}

    async def resumen(**extra) -> dict[str, Any]:
        r = await c.get(f"{BASE}/dashboard/resumen", params={**periodo, **extra}, headers=h)
        return r.json() if r.status_code == 200 else {}

    async def por_area(**extra) -> list[dict[str, Any]]:
        r = await c.get(f"{BASE}/dashboard/por-area", params={**periodo, "limit": 100, **extra}, headers=h)
        return r.json() if r.status_code == 200 else []

    general = await resumen()
    check("por área suma todas las respuestas, no solo reclamos",
          sum(a["total_respuestas"] for a in await por_area()) == general.get("total_completadas"),
          f"{sum(a['total_respuestas'] for a in await por_area())} vs {general.get('total_completadas')}")
    r = await c.get(f"{BASE}/dashboard/por-circuito", params=periodo, headers=h)
    circuitos = r.json() if r.status_code == 200 else []
    check("por circuito: 200 y los cuatro circuitos, siempre",
          r.status_code == 200 and [x["tipo"] for x in circuitos] == list(CIRCUITOS), f"{r.status_code} {r.text[:200]}")
    if circuitos:
        check("por circuito: las respuestas suman el total",
              sum(x["total_respuestas"] for x in circuitos) == general.get("total_completadas"))
        check("por circuito: los envíos suman el total",
              sum(x["total_enviadas"] for x in circuitos) == general.get("total_enviadas"))

    # El filtro alcanza a todos los bloques: la suma de los cuatro da lo mismo que sin filtro.
    suma_alertas = suma_area = suma_evol = 0
    r = await c.get(f"{BASE}/dashboard/evolucion", params={"meses": 6}, headers=h)
    evol_general = sum(x["total_respuestas"] for x in r.json()) if r.status_code == 200 else -1
    for tipo in CIRCUITOS:
        res = await resumen(tipo=tipo)
        suma_alertas += res.get("alertas_contacto_pendientes", 0)
        area = sum(a["total_respuestas"] for a in await por_area(tipo=tipo))
        suma_area += area
        check(f"{tipo}: por área coincide con el resumen filtrado", area == res.get("total_completadas"),
              f"{area} vs {res.get('total_completadas')}")
        r = await c.get(f"{BASE}/dashboard/evolucion", params={"meses": 6, "tipo": tipo}, headers=h)
        suma_evol += sum(x["total_respuestas"] for x in r.json()) if r.status_code == 200 else 0
        r = await c.get(f"{BASE}/dashboard/comentarios", params={"tipo": tipo, "limit": 100}, headers=h)
        propios = [x["comentario"] for x in r.json() if x["comentario"].startswith(marca)] if r.status_code == 200 else []
        check(f"{tipo}: comentarios solo del circuito",
              bool(propios) and all(x == f"{marca} {tipo}" for x in propios), str(propios[:4]))
    check("las alertas por circuito suman el total", suma_alertas == general.get("alertas_contacto_pendientes"),
          f"{suma_alertas} vs {general.get('alertas_contacto_pendientes')}")
    check("por área por circuito suma el total", suma_area == general.get("total_completadas"))
    check("la evolución por circuito suma el total", suma_evol == evol_general, f"{suma_evol} vs {evol_general}")

    for path in ("resumen", "por-area", "por-circuito", "evolucion", "comentarios"):
        r = await c.get(f"{BASE}/dashboard/{path}", params={"tipo": "cualquiera"}, headers=h)
        # por-circuito no se filtra por circuito: un parámetro de más no le cambia nada.
        esperado = 200 if path == "por-circuito" else 422
        check(f"{path}: circuito inexistente → {esperado}", r.status_code == esperado, str(r.status_code))

    r = await c.get(f"{BASE}/respuestas/pendientes-contacto", params={"limit": 200}, headers=h)
    bandeja = {x["id_encuesta_envio"]: x for x in r.json()} if r.status_code == 200 else {}
    for id_envio in creados:
        x = bandeja.get(id_envio)
        if x:
            check(f"bandeja de contactos: {x['tipo']} con referencia", bool(x["referencia"]), str(x["referencia"]))


async def test_permisos(c: httpx.AsyncClient, id_municipio: int) -> None:
    print("\n[5] Permisos")
    fila = await una("""
        SELECT email FROM usuarios
         WHERE nivel_acceso = 5 AND activo = TRUE AND id_municipio = :m AND email IS NOT NULL
         ORDER BY id_usuario LIMIT 1
    """, m=id_municipio)
    if not fila:
        skip("consultor", "sin usuario de nivel 5 en local")
        return
    r = await c.post("/api/v1/auth/login", json={"identificador": fila["email"], "password": PWD_DEV})
    if r.status_code != 200 or "access_token" not in r.json():
        skip("consultor", f"login {r.status_code}")
        return
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = await c.get(f"{BASE}/dashboard/por-circuito", headers=h)
    check("consultor: por circuito → 403", r.status_code == 403, str(r.status_code))


async def limpiar(id_municipio: int, creados: list[int]) -> None:
    if not creados:
        return
    async with AsyncSessionLocal() as s:
        p = {"ids": creados, "m": id_municipio}
        await s.execute(text("""
            DELETE FROM encuesta_respuesta_detalle
             WHERE id_municipio = :m AND id_respuesta IN (
                   SELECT id_encuesta_respuesta FROM encuesta_respuesta
                    WHERE id_municipio = :m AND id_envio = ANY(:ids))
        """), p)
        await s.execute(text("DELETE FROM encuesta_respuesta WHERE id_municipio = :m AND id_envio = ANY(:ids)"), p)
        await s.execute(text("DELETE FROM encuesta_envio WHERE id_municipio = :m AND id_encuesta_envio = ANY(:ids)"), p)
        await s.commit()


async def main() -> None:
    print("== Smoke Encuestas: cuatro circuitos - local ==")
    base = await una("SELECT id_municipio, nombre FROM municipios WHERE direccion_base = TRUE LIMIT 1")
    modelo = await una("SELECT id_municipio, nombre FROM municipios WHERE estado = 'modelo' LIMIT 1")
    if not base or not modelo:
        sys.exit("ABORT: faltan el municipio de direccion_base o el modelo")
    m = base["id_municipio"]

    await test_plantillas(m, base["nombre"])
    await test_plantillas(modelo["id_municipio"], modelo["nombre"])

    origenes: dict[str, int] = {}
    for tipo, sql in {
        "reclamos": "SELECT id_reclamo AS id FROM reclamos WHERE id_municipio = :m AND nro_reclamo IS NOT NULL ORDER BY 1 DESC LIMIT 1",
        "turnos": "SELECT id_turno AS id FROM turnos WHERE id_municipio = :m ORDER BY 1 DESC LIMIT 1",
        "tramites": "SELECT id_tramite AS id FROM tramite WHERE id_municipio = :m AND numero_expediente IS NOT NULL ORDER BY 1 DESC LIMIT 1",
        "entradas": """SELECT r.id_evento_reserva AS id FROM evento_reservas r
                         JOIN eventos e ON e.id_evento = r.id_evento
                        WHERE r.id_municipio = :m ORDER BY 1 DESC LIMIT 1""",
    }.items():
        fila = await una(sql, m=m)
        if not fila:
            sys.exit(f"ABORT: sin datos de {tipo} en el municipio {m}")
        origenes[tipo] = fila["id"]
    id_ciudadano = (await una("SELECT id_ciudadano AS id FROM ciudadanos WHERE id_municipio = :m AND activo = TRUE ORDER BY 1 LIMIT 1", m=m))["id"]
    id_subarea = (await una("SELECT id_subarea AS id FROM subarea WHERE id_municipio = :m AND activo = TRUE ORDER BY 1 LIMIT 1", m=m))["id"]

    marca = f"smoke-circuito-{uuid.uuid4().hex[:8]}"
    creados: list[int] = []
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=60) as c:
            r = await c.post("/api/v1/auth/login", json={"identificador": ADMIN, "password": PWD_DEV})
            if r.status_code != 200 or "access_token" not in r.json():
                sys.exit(f"ABORT: login del administrador: {r.status_code} {r.text[:200]}")
            h = {"Authorization": f"Bearer {r.json()['access_token']}"}
            await test_formulario_y_contacto(c, m, origenes, id_ciudadano, id_subarea, marca, creados)
            await test_resumen(c, h, m, marca, creados)
            await test_permisos(c, m)
    finally:
        await limpiar(m, creados)
        restos = await una("SELECT count(*) AS n FROM encuesta_envio WHERE id_municipio = :m AND id_encuesta_envio = ANY(:ids)",
                           m=m, ids=creados)
        print(f"\nLimpieza: quedaron {restos['n'] if restos else '?'} envíos de prueba")

    print(f"\n== {ok_count} OK · {fail_count} FAIL · {skip_count} SKIP ==")
    for f in fallidos:
        print(f"  - {f}")
    sys.exit(1 if fail_count else 0)


if __name__ == "__main__":
    asyncio.run(main())
