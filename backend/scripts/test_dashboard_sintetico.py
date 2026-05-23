# -*- coding: utf-8 -*-
"""
Test destructivo de los dashboards del modulo Encuestas (fase 2C.5).

SOLO en zaris_dev local. Inserta un dataset sintetico predecible, llama los 4
endpoints de dashboard con un JWT real, compara con los valores esperados
(calculados en Python sobre el MISMO dataset insertado, no a mano) y limpia todo.

Salvaguardas:
  - Aborta si DATABASE_URL no apunta a localhost/127.0.0.1.
  - NO crea reclamos sinteticos: reutiliza reclamos reales 'Resuelto' sin envio.
  - Se adapta a la cantidad de reclamos disponibles (el prompt pedia 15; el script
    funciona con los que haya, manteniendo distribucion sobre las 5 clasificaciones,
    2 solicita_contacto y >=3 comentarios). Aborta si hay < 5 (muy pocos para repartir).
  - Limpia SIEMPRE (try/finally), borrando solo los ids que creo (guardados en lista).

Uso:
  cd backend
  $env:ENV_FILE=".env.local"; $env:JWT_TEST_TOKEN="<token>"; python scripts/test_dashboard_sintetico.py

Si JWT_TEST_TOKEN no esta seteado, el script hace login con las credenciales dev
(ciudadanovl@municipio.gob.ar / 123456) contra el backend local.
"""
import asyncio
import os
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone

# imports relativos desde la raiz de backend (scripts/ esta un nivel abajo)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("ENV_FILE", ".env.local")

import httpx
from sqlalchemy import text

from app.core.config import settings
from app.core.database import AsyncSessionLocal

API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000")
TOL_CSAT = 0.01
TOL_PCT = 0.1

# Distribucion objetivo (clasificacion -> cantidad). Replica la del prompt para 12
# respuestas; si hay menos reclamos, se trunca proporcionalmente manteniendo las 5
# clases representadas. solicita_contacto: 2 de las insatisfechas (clas <=2).
DISTRIB_OBJETIVO = {5: 3, 4: 3, 3: 2, 2: 2, 1: 2}  # total 12
TASA_RESPUESTA = 0.80


def rama_de(clasif: int) -> str:
    if clasif <= 2:
        return "insatisfechos"
    if clasif == 3:
        return "neutrales"
    return "satisfechos"


def construir_distribucion(n_respuestas: int) -> list[int]:
    """Lista de clasificaciones (1..5) de largo n_respuestas, lo mas parecida posible
    a DISTRIB_OBJETIVO, garantizando al menos 1 de cada clase si entran."""
    objetivo_total = sum(DISTRIB_OBJETIVO.values())  # 12
    clasifs: list[int] = []
    if n_respuestas >= objetivo_total:
        for c, cant in DISTRIB_OBJETIVO.items():
            clasifs += [c] * cant
        # completar el resto repartiendo en 4 y 5 (satisfechos)
        i = 0
        extra = [5, 4]
        while len(clasifs) < n_respuestas:
            clasifs.append(extra[i % 2]); i += 1
    else:
        # escalar manteniendo las 5 clases si entran
        base = [5, 4, 3, 2, 1]
        for c in base:
            if len(clasifs) < n_respuestas:
                clasifs.append(c)
        i = 0
        ciclo = [5, 4, 3, 2, 1]
        while len(clasifs) < n_respuestas:
            clasifs.append(ciclo[i % 5]); i += 1
    return clasifs[:n_respuestas]


async def obtener_token() -> str:
    tok = os.environ.get("JWT_TEST_TOKEN")
    if tok:
        return tok.strip()
    async with httpx.AsyncClient(base_url=API_BASE, timeout=10) as c:
        r = await c.post("/api/v1/auth/login",
                         json={"email": "ciudadanovl@municipio.gob.ar", "password": "123456"})
        r.raise_for_status()
        return r.json()["access_token"]


def aprox(a: float, b: float, tol: float) -> bool:
    return abs(float(a) - float(b)) <= tol


async def main() -> int:
    fails = 0
    creados_envios: list[int] = []

    # [1/8] DB local
    print("[1/8] Verificando DB local...", end=" ")
    db_url = settings.ASYNC_DATABASE_URI
    if not ("localhost" in db_url or "127.0.0.1" in db_url):
        print(f"FAIL\n  DATABASE_URL no es local: {db_url[:40]}... ABORTO (test destructivo).")
        return 2
    print("OK (localhost)")

    try:
        async with AsyncSessionLocal() as db:
            # [2/8] reclamos Resuelto sin envio
            print("[2/8] Buscando reclamos Resuelto sin envio...", end=" ")
            rows = (await db.execute(text("""
                SELECT r.id_reclamo, r.id_ciudadano, r.id_municipio,
                       COALESCE(tr.id_subarea, r.id_subarea) AS id_subarea,
                       c.email
                  FROM reclamos r
                  JOIN ciudadanos c ON c.id_ciudadano = r.id_ciudadano
                  LEFT JOIN tipo_reclamo tr ON tr.id_tipo_reclamo = r.id_tipo_reclamo
                 WHERE r.estado = 'Resuelto'
                   AND COALESCE(c.email, '') <> ''
                   AND NOT EXISTS (SELECT 1 FROM encuesta_envio e WHERE e.id_reclamo = r.id_reclamo)
                 ORDER BY r.id_reclamo
            """))).fetchall()
            reclamos = [r._mapping for r in rows]
            n_env = len(reclamos)
            if n_env < 5:
                print(f"FAIL\n  Solo {n_env} reclamos Resuelto con email sin envio (minimo 5). ABORTO.")
                return 2
            print(f"OK ({n_env} encontrados)")

            # plantilla activa
            pid = (await db.execute(text("""
                SELECT id_encuesta_plantilla FROM encuesta_plantilla
                 WHERE tipo='reclamos' AND activo=TRUE ORDER BY id_encuesta_plantilla LIMIT 1
            """))).scalar()
            if pid is None:
                print("  FAIL: no hay plantilla activa tipo=reclamos. ABORTO.")
                return 2
            # pregunta texto_libre (P8) para los comentarios
            qid_texto = (await db.execute(text("""
                SELECT id_encuesta_pregunta FROM encuesta_pregunta
                 WHERE id_plantilla=:p AND tipo='texto_libre' AND activo=TRUE LIMIT 1
            """), {"p": pid})).scalar()

            n_resp = max(1, round(n_env * TASA_RESPUESTA))
            clasifs = construir_distribucion(n_resp)

            # [3/8] insertar envios
            print(f"[3/8] Insertando {n_env} envios...", end=" ")
            now = datetime.now(timezone.utc)
            for i, rec in enumerate(reclamos):
                fecha_envio = now - timedelta(days=(i % 29))  # disperso 0..28 dias
                eid = (await db.execute(text("""
                    INSERT INTO encuesta_envio (
                        id_plantilla, id_ciudadano, id_reclamo, email_destino_snapshot,
                        fecha_envio, fecha_expiracion, estado, id_municipio, id_subarea
                    ) VALUES (
                        :p, :cid, :rid, :email, :fenv, :fexp, 'enviada', :mun, :sub
                    ) RETURNING id_encuesta_envio
                """), {
                    "p": pid, "cid": rec["id_ciudadano"], "rid": rec["id_reclamo"],
                    "email": rec["email"] or "test@local.invalid",
                    "fenv": fecha_envio, "fexp": fecha_envio + timedelta(days=15),
                    "mun": rec["id_municipio"], "sub": rec["id_subarea"],
                })).scalar()
                creados_envios.append(eid)
            await db.commit()
            print(f"OK (IDs: {creados_envios[0]}..{creados_envios[-1]})")

            # [4/8] insertar respuestas (las primeras n_resp envios)
            print(f"[4/8] Insertando {n_resp} respuestas...", end=" ")
            # solicita_contacto: 2 de las insatisfechas (clas<=2)
            insat_idx = [i for i, c in enumerate(clasifs) if c <= 2]
            contacto_set = set(insat_idx[:2])
            comentarios_puestos = 0
            esperado_dist = Counter()
            esperado_suma = 0
            esperado_insat = 0
            esperado_contacto = 0
            for i in range(n_resp):
                clasif = clasifs[i]
                rama = rama_de(clasif)
                solicita = i in contacto_set
                rid = (await db.execute(text("""
                    INSERT INTO encuesta_respuesta (
                        id_envio, clasificacion_inicial, rama_seguida, solicita_contacto, id_municipio, id_subarea
                    ) VALUES (:env, :clf, :rama, :sc, :mun, :sub)
                    RETURNING id_encuesta_respuesta
                """), {
                    "env": creados_envios[i], "clf": clasif, "rama": rama, "sc": solicita,
                    "mun": reclamos[i]["id_municipio"], "sub": reclamos[i]["id_subarea"],
                })).scalar()
                # comentario en P8 para >=3 respuestas
                if qid_texto and comentarios_puestos < 3:
                    await db.execute(text("""
                        INSERT INTO encuesta_respuesta_detalle (
                            id_respuesta, id_pregunta, valor_texto, id_municipio
                        ) VALUES (:rid, :qid, :txt, :mun)
                    """), {"rid": rid, "qid": qid_texto,
                           "txt": f"Comentario de prueba {i}", "mun": reclamos[i]["id_municipio"]})
                    comentarios_puestos += 1
                esperado_dist[clasif] += 1
                esperado_suma += clasif
                if clasif <= 2:
                    esperado_insat += 1
                if solicita:
                    esperado_contacto += 1
            await db.commit()
            print("OK")

        # esperados (calculados sobre lo insertado)
        exp_enviadas = n_env
        exp_compl = n_resp
        exp_csat = round(esperado_suma / n_resp, 2)
        exp_tasa = round(exp_compl * 100.0 / exp_enviadas, 1)
        exp_pct_insat = round(esperado_insat * 100.0 / exp_compl, 1)

        # [5/8] llamar endpoints
        print("[5/8] Llamando endpoints...")
        token = await obtener_token()
        H = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(base_url=API_BASE, timeout=20, headers=H) as c:
            res = (await c.get("/api/v1/admin/encuestas/dashboard/resumen")).json()
            evo = (await c.get("/api/v1/admin/encuestas/dashboard/evolucion?meses=6")).json()
            com = await c.get("/api/v1/admin/encuestas/dashboard/comentarios")
            com_total = int(com.headers.get("X-Total-Count", "0"))
            por_area = (await c.get("/api/v1/admin/encuestas/dashboard/por-area")).json()

        def check(nombre, real, esp, tol=None):
            nonlocal fails
            ok = aprox(real, esp, tol) if tol is not None else (real == esp)
            print(f"    {nombre}: {real} {'≈' if tol else '=='} {esp} {'PASS' if ok else 'FAIL'}")
            if not ok:
                fails += 1

        print("  GET /dashboard/resumen")
        check("total_enviadas", res["total_enviadas"], exp_enviadas)
        check("total_completadas", res["total_completadas"], exp_compl)
        check("csat_promedio", res["csat_promedio"], exp_csat, TOL_CSAT)
        check("tasa_respuesta_pct", res["tasa_respuesta_pct"], exp_tasa, TOL_PCT)
        check("pct_insatisfechos", res["pct_insatisfechos"], exp_pct_insat, TOL_PCT)
        check("alertas_contacto_pendientes", res["alertas_contacto_pendientes"], esperado_contacto)
        dist_real = {d["clasificacion"]: d["count"] for d in res["distribucion"]}
        dist_esp = {i: esperado_dist.get(i, 0) for i in range(1, 6)}
        check("distribucion", dist_real, dist_esp)

        print("  GET /dashboard/evolucion?meses=6")
        mes_actual = date.today().strftime("%Y-%m")
        # las respuestas tienen fecha_alta = hoy (NOW al insertar), todas en el mes actual
        evo_mes = [e for e in evo if e["anio_mes"] == mes_actual]
        if len(evo_mes) == 1 and evo_mes[0]["total_respuestas"] == exp_compl \
                and aprox(evo_mes[0]["csat_promedio"], exp_csat, TOL_CSAT):
            print(f"    1 entrada mes {mes_actual}, csat={evo_mes[0]['csat_promedio']}, n={evo_mes[0]['total_respuestas']} PASS")
        else:
            print(f"    FAIL: esperado 1 entrada {mes_actual} csat={exp_csat} n={exp_compl}; recibido {evo_mes}")
            fails += 1

        print("  GET /dashboard/comentarios")
        check("total con valor_texto (>=3)", com_total >= 3, True)

        print("  GET /dashboard/por-area")
        suma_area = sum(a["total_respuestas"] for a in por_area)
        check("suma total_respuestas por area", suma_area, exp_compl)

        return 1 if fails else 0

    finally:
        # [6/8][7/8] cleanup SIEMPRE
        print(f"[6/8] Limpiando {len(creados_envios)} envios + respuestas...", end=" ")
        if creados_envios:
            async with AsyncSessionLocal() as db:
                # borrar detalles -> respuestas -> envios (las FK tienen CASCADE igual,
                # pero borro explicito por claridad y para no depender del cascade)
                await db.execute(text("""
                    DELETE FROM encuesta_respuesta_detalle
                     WHERE id_respuesta IN (
                        SELECT id_encuesta_respuesta FROM encuesta_respuesta
                         WHERE id_envio = ANY(:ids))
                """), {"ids": creados_envios})
                await db.execute(text(
                    "DELETE FROM encuesta_respuesta WHERE id_envio = ANY(:ids)"),
                    {"ids": creados_envios})
                await db.execute(text(
                    "DELETE FROM encuesta_envio WHERE id_encuesta_envio = ANY(:ids)"),
                    {"ids": creados_envios})
                await db.commit()
        print("OK")
        print("[7/8] Verificando cleanup:", end=" ")
        async with AsyncSessionLocal() as db:
            ne = (await db.execute(text("SELECT COUNT(*) FROM encuesta_envio"))).scalar()
            nr = (await db.execute(text("SELECT COUNT(*) FROM encuesta_respuesta"))).scalar()
        print(f"{ne} envios, {nr} respuestas", "PASS" if (ne == 0 and nr == 0) else "FAIL (habia datos previos?)")


if __name__ == "__main__":
    rc = asyncio.run(main())
    print(f"[8/8] RESUMEN: exit code {rc} ({'TODOS PASS' if rc == 0 else 'HAY FAILS' if rc == 1 else 'ABORTADO'})")
    sys.exit(rc)
