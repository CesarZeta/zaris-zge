# -*- coding: utf-8 -*-
"""
Smoke in-process - BI de Atencion por gestion (proyecto ATENCION F6, 2026-09-19).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_bi_atencion.py

SOLO LOCAL: aborta si la DB no es zaris_dev (sin credenciales de prod, §40). Corre el app
FastAPI real con httpx.ASGITransport (memoria feedback_smoke_authz_asgi_in_process).

Cubre /api/v1/bi/atencion/*: shapes de los 19 endpoints, consistencia interna (score vs
matriz vs series vs composicion), filtros (gestion / ubicacion / prestacion / periodo),
periodo anterior (anio+meses -> bloque contiguo), drill de mes (422 con basura), export con
X-Total-Count, catalogos, 401 sin token, y el guard JWT a nivel router (nivel 5 tambien
entra al backend: la UI gatea nivel <= 2, como el resto de DATOS).
No crea ni modifica datos: es un tablero de solo lectura.
"""
import asyncio
import os
import sys
from typing import Any, Optional

import httpx

# Consola Windows cp1252: sin esto un caracter fuera de Latin-1 aborta el smoke.
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

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402

import logging  # noqa: E402
logging.getLogger("httpx").setLevel(logging.WARNING)

PWD_DEV = os.environ.get("ZARIS_QA_PASS") or "123456"
BASE = "/api/v1/bi/atencion"
ADMIN = "ciudadanovl@municipio.gob.ar"   # admin dev local (win-quirks Q10)

ok_count = 0
fail_count = 0
skip_count = 0
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


def skip(nombre: str, motivo: str) -> None:
    global skip_count
    skip_count += 1
    print(f"  SKIP {nombre} ({motivo})")


def short(r: httpx.Response, n: int = 160) -> str:
    return f"{r.status_code} {r.text[:n]}"


async def q1(sql: str, **params) -> Optional[dict]:
    async with AsyncSessionLocal() as s:
        row = (await s.execute(text(sql), params)).mappings().first()
        return dict(row) if row else None


async def login(c: httpx.AsyncClient, email: str) -> dict[str, str]:
    r = await c.post("/api/v1/auth/login", json={"email": email, "password": PWD_DEV})
    if r.status_code != 200:
        sys.exit(f"ABORT: login de {email} fallo: {short(r)}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


IND_KEYS = {
    "total", "cumplidos", "ausentes", "cancelados", "pendientes", "autoservicio", "llamados",
    "re_llamados", "a_tiempo", "espera_prom_min", "espera_max_min", "atenciones_registradas",
    "horas_atendidas", "enviadas", "respuestas", "satisfechos", "pct_cumplimiento",
    "pct_ausentismo", "pct_cancelacion", "pct_a_tiempo", "pct_autoservicio", "pct_sat", "tasa_respuesta",
}


def ind_ok(d: dict) -> bool:
    return IND_KEYS <= set(d.keys())


async def main() -> None:
    print("== Smoke BI Atencion (F6) - local ==")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=60) as c:
        h = await login(c, ADMIN)

        # ── 1. Score: shape + consistencia interna ──────────────────────────
        print("\n[1] Score")
        r = await c.get(f"{BASE}/score", headers=h)
        check("score 200", r.status_code == 200, short(r))
        s = r.json()
        check("score shape indicadores", ind_ok(s), str(sorted(IND_KEYS - set(s.keys()))))
        check("score shape composicion", {"var_pct", "anterior", "por_estado", "por_origen", "niveles"} <= set(s.keys()))
        check("score: total = cumplidos + ausentes + cancelados + pendientes",
              s["total"] == s["cumplidos"] + s["ausentes"] + s["cancelados"] + s["pendientes"],
              f"{s['total']} vs {s['cumplidos']}+{s['ausentes']}+{s['cancelados']}+{s['pendientes']}")
        check("score: suma por_estado = total", sum(x["total"] for x in s["por_estado"]) == s["total"])
        check("score: suma por_origen = total", sum(x["total"] for x in s["por_origen"]) == s["total"])
        check("score: autoservicio coincide con por_origen",
              s["autoservicio"] == sum(x["total"] for x in s["por_origen"] if x["origen"] == "autoservicio"))
        check("score: suma niveles = respuestas", sum(x["total"] for x in s["niveles"]) == s["respuestas"])
        if s["cumplidos"] + s["ausentes"]:
            check("score: pct_ausentismo = ausentes/(cumplidos+ausentes)",
                  s["pct_ausentismo"] == round(s["ausentes"] / (s["cumplidos"] + s["ausentes"]) * 100, 1))
        else:
            skip("pct_ausentismo", "sin turnos con desenlace")
        check("score: a_tiempo <= llamados", s["a_tiempo"] <= s["llamados"])
        check("score: sin filtro temporal no hay anterior", s["anterior"] is None and s["var_pct"] is None)

        # Contraste directo contra la DB (universo activo=TRUE, id_municipio 1/NULL).
        db = await q1("""
            SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE estado = 'cumplido') AS cumplidos
              FROM turnos WHERE activo = TRUE AND (id_municipio = 1 OR id_municipio IS NULL)
        """)
        check("score.total = COUNT(turnos activos) en DB", s["total"] == db["total"], f"{s['total']} vs {db['total']}")
        check("score.cumplidos = DB", s["cumplidos"] == db["cumplidos"])

        # ── 2. Matriz ───────────────────────────────────────────────────────
        print("\n[2] Matriz ubicacion -> prestacion")
        r = await c.get(f"{BASE}/matriz", headers=h)
        check("matriz 200", r.status_code == 200, short(r))
        m = r.json()
        check("matriz shape", {"filas", "total"} <= set(m.keys()) and ind_ok(m["total"]))
        check("matriz: total = score.total", m["total"]["total"] == s["total"], f"{m['total']['total']} vs {s['total']}")
        check("matriz: suma de ubicaciones = total", sum(f["total"] for f in m["filas"]) == m["total"]["total"])
        check("matriz: cada ubicacion suma sus prestaciones",
              all(sum(p["total"] for p in f["prestaciones"]) == f["total"] for f in m["filas"]))
        check("matriz: filas con ubicacion/gestion/prestaciones",
              all({"id_espacio", "ubicacion", "gestion", "prestaciones", "var_pct", "ant"} <= set(f.keys()) for f in m["filas"]))

        # ── 3. Series temporales ────────────────────────────────────────────
        print("\n[3] Series")
        r = await c.get(f"{BASE}/mensual", headers=h)
        check("mensual 200", r.status_code == 200, short(r))
        mensual = r.json()
        check("mensual: suma = score.total", sum(x["total"] for x in mensual) == s["total"])
        check("mensual: keys por estado", all({"mes", "total", "cumplido", "ausente", "cancelado", "pendiente"} <= set(x.keys()) for x in mensual))
        check("mensual: total = suma de estados", all(x["total"] == x["cumplido"] + x["ausente"] + x["cancelado"] + x["pendiente"] for x in mensual))
        r = await c.get(f"{BASE}/diario", headers=h)
        check("diario 200 y suma = total", r.status_code == 200 and sum(x["total"] for x in r.json()) == s["total"], short(r))
        if mensual:
            mes = mensual[-1]["mes"]
            r = await c.get(f"{BASE}/diario", params={"mes": mes}, headers=h)
            d = r.json()
            check(f"diario?mes={mes} suma = mensual de ese mes", r.status_code == 200 and sum(x["total"] for x in d) == mensual[-1]["total"], short(r))
            check("diario?mes: todos los dias dentro del mes", all(x["dia"].startswith(mes) for x in d))
        else:
            skip("drill de mes", "sin turnos")
        r = await c.get(f"{BASE}/diario", params={"mes": "basura"}, headers=h)
        check("diario?mes=basura -> 422", r.status_code == 422, short(r))
        r = await c.get(f"{BASE}/evolucion", headers=h)
        check("evolucion 200 + keys", r.status_code == 200 and all(
            {"mes", "total", "cumplidos", "ausentes", "pct_cumplimiento", "pct_ausentismo", "espera_prom_min", "pct_sat"} <= set(x.keys())
            for x in r.json()), short(r))
        check("evolucion: suma = score.total", sum(x["total"] for x in r.json()) == s["total"])

        # ── 4. Ubicaciones / agentes / espera ───────────────────────────────
        print("\n[4] Ubicaciones, agentes, espera")
        r = await c.get(f"{BASE}/por-ubicacion", headers=h)
        pu = r.json()
        check("por-ubicacion 200 + shape", r.status_code == 200 and all(ind_ok(x) and {"id_espacio", "ubicacion", "gestion"} <= set(x.keys()) for x in pu), short(r))
        check("por-ubicacion: suma = score.total", sum(x["total"] for x in pu) == s["total"])
        r = await c.get(f"{BASE}/por-agente", params={"limit": 5}, headers=h)
        pa = r.json()
        check("por-agente 200 + shape", r.status_code == 200 and all(ind_ok(x) and {"id_agente", "agente", "ubicaciones"} <= set(x.keys()) for x in pa), short(r))
        check("por-agente: limit respetado", len(pa) <= 5)
        db = await q1("SELECT COUNT(*) AS n FROM turnos WHERE activo = TRUE AND id_agente IS NOT NULL AND (id_municipio = 1 OR id_municipio IS NULL)")
        r_all = await c.get(f"{BASE}/por-agente", params={"limit": 100}, headers=h)
        check("por-agente: suma = turnos por agente en DB", sum(x["total"] for x in r_all.json()) == db["n"])
        r = await c.get(f"{BASE}/espera", headers=h)
        e = r.json()
        check("espera 200 + shape", r.status_code == 200 and {"llamados", "re_llamados", "a_tiempo", "pct_a_tiempo", "espera_prom_min",
              "espera_max_min", "tolerancia_min", "tramos", "por_ubicacion"} <= set(e.keys()), short(r))
        check("espera: 5 tramos y suma = llamados", len(e["tramos"]) == 5 and sum(t["total"] for t in e["tramos"]) == e["llamados"])
        check("espera: llamados = score.llamados", e["llamados"] == s["llamados"])
        check("espera: suma por_ubicacion = llamados", sum(u["llamados"] for u in e["por_ubicacion"]) == e["llamados"])

        # ── 5. Guardia ──────────────────────────────────────────────────────
        print("\n[5] Guardia")
        r = await c.get(f"{BASE}/guardia", headers=h)
        g = r.json()
        check("guardia 200 + shape", r.status_code == 200 and {"derivaciones", "atendidas", "ausentes", "pendientes", "pct_atendidas",
              "demora_prom_min", "var_pct", "anterior", "por_estado", "por_agente", "por_tipo", "por_prioridad"} <= set(g.keys()), short(r))
        check("guardia: derivaciones = atendidas + ausentes + pendientes",
              g["derivaciones"] == g["atendidas"] + g["ausentes"] + g["pendientes"])
        check("guardia: suma por_tipo = derivaciones (top 10)", sum(x["derivaciones"] for x in g["por_tipo"]) == g["derivaciones"] or len(g["por_tipo"]) == 10)
        check("guardia: suma por_prioridad = derivaciones", sum(x["derivaciones"] for x in g["por_prioridad"]) == g["derivaciones"])
        db = await q1("SELECT COUNT(*) AS n FROM emergencia_atencion WHERE activo IS DISTINCT FROM FALSE AND (id_municipio = 1 OR id_municipio IS NULL)")
        check("guardia.derivaciones = DB", g["derivaciones"] == db["n"], f"{g['derivaciones']} vs {db['n']}")
        r = await c.get(f"{BASE}/guardia/mensual", headers=h)
        gm = r.json()
        check("guardia/mensual 200 + suma = derivaciones", r.status_code == 200 and sum(x["total"] for x in gm) == g["derivaciones"], short(r))
        if gm:
            r = await c.get(f"{BASE}/guardia/diario", params={"mes": gm[-1]["mes"]}, headers=h)
            check("guardia/diario?mes suma = mensual", r.status_code == 200 and sum(x["total"] for x in r.json()) == gm[-1]["total"], short(r))
        else:
            skip("guardia drill", "sin derivaciones")
        # Prestacion no aplica a la guardia: mismo resultado con o sin filtro.
        r = await c.get(f"{BASE}/guardia", params={"id_tipo_prestacion": 999999}, headers=h)
        check("guardia ignora id_tipo_prestacion", r.status_code == 200 and r.json()["derivaciones"] == g["derivaciones"], short(r))

        # ── 6. Eventos ──────────────────────────────────────────────────────
        print("\n[6] Eventos y reservas")
        r = await c.get(f"{BASE}/eventos", headers=h)
        ev = r.json()
        check("eventos 200 + shape", r.status_code == 200 and {"eventos", "eventos_realizados", "cupo_total", "reservas", "vigentes", "asistieron",
              "canceladas", "pct_asistencia", "pct_cupo", "var_pct", "anterior", "por_estado", "por_evento"} <= set(ev.keys()), short(r))
        check("eventos: reservas = vigentes + canceladas", ev["reservas"] == ev["vigentes"] + ev["canceladas"])
        check("eventos: asistieron <= vigentes", ev["asistieron"] <= ev["vigentes"])
        check("eventos: suma por_estado = reservas", sum(x["total"] for x in ev["por_estado"]) == ev["reservas"])
        check("eventos: por_evento con % (realizado => pct_asistencia no None si hay vigentes)",
              all((x["pct_asistencia"] is not None) == (x["realizado"] and x["vigentes"] > 0) for x in ev["por_evento"]))
        db = await q1("SELECT COUNT(*) AS n FROM eventos WHERE activo = TRUE AND (id_municipio = 1 OR id_municipio IS NULL)")
        check("eventos.eventos = DB", ev["eventos"] == db["n"], f"{ev['eventos']} vs {db['n']}")
        r = await c.get(f"{BASE}/eventos/mensual", headers=h)
        em = r.json()
        check("eventos/mensual 200 + suma = reservas", r.status_code == 200 and sum(x["total"] for x in em) == ev["reservas"], short(r))
        check("eventos/mensual: sin meses en cero", all(x["total"] > 0 for x in em))
        if em:
            r = await c.get(f"{BASE}/eventos/diario", params={"mes": em[-1]["mes"]}, headers=h)
            check("eventos/diario?mes suma = mensual", r.status_code == 200 and sum(x["total"] for x in r.json()) == em[-1]["total"], short(r))

        # ── 7. Filtros ──────────────────────────────────────────────────────
        print("\n[7] Filtros")
        r = await c.get(f"{BASE}/catalogo/gestiones", headers=h)
        gest = r.json()
        check("catalogo/gestiones 200 + shape", r.status_code == 200 and all({"id_area", "nombre"} <= set(x.keys()) for x in gest), short(r))
        r = await c.get(f"{BASE}/catalogo/ubicaciones", headers=h)
        ubs = r.json()
        check("catalogo/ubicaciones 200 + shape", r.status_code == 200 and all({"id_espacio", "nombre", "id_area", "gestion"} <= set(x.keys()) for x in ubs), short(r))
        r = await c.get(f"{BASE}/catalogo/prestaciones", headers=h)
        prs = r.json()
        check("catalogo/prestaciones 200 + shape", r.status_code == 200 and all({"id_tipo_prestacion", "nombre", "activo", "id_espacio_ubicacion"} <= set(x.keys()) for x in prs), short(r))

        if pu:
            # Ubicacion con mas turnos: el filtro debe reproducir su fila de por-ubicacion.
            top = max(pu, key=lambda x: x["total"])
            if top["id_espacio"] is not None:
                r = await c.get(f"{BASE}/score", params={"id_espacio_ubicacion": top["id_espacio"]}, headers=h)
                check("filtro ubicacion: score.total = fila de por-ubicacion", r.status_code == 200 and r.json()["total"] == top["total"], short(r))
                r = await c.get(f"{BASE}/catalogo/ubicaciones", params={"id_area": ubs[0]["id_area"]}, headers=h) if ubs and ubs[0]["id_area"] else None
                if r is not None:
                    check("catalogo/ubicaciones?id_area solo esa gestion", all(x["id_area"] == ubs[0]["id_area"] for x in r.json()))
            else:
                skip("filtro ubicacion", "la ubicacion top es 'Sin ubicacion'")
        # Gestion: la suma de los scores por gestion del catalogo + sin gestion = total.
        suma = 0
        for gg in gest:
            rr = await c.get(f"{BASE}/score", params={"id_area": gg["id_area"]}, headers=h)
            suma += rr.json()["total"]
        db = await q1("""
            SELECT COUNT(*) AS n FROM turnos t
              LEFT JOIN tipo_prestacion tp ON tp.id_tipo_prestacion = t.id_tipo_prestacion
              LEFT JOIN espacios_agenda ub ON ub.id_espacio = COALESCE(t.id_espacio_ubicacion, tp.id_espacio_ubicacion, t.id_espacio)
              LEFT JOIN subarea s ON s.id_subarea = COALESCE(ub.id_subarea, tp.id_subarea)
              LEFT JOIN area a ON a.id_area = s.id_area
             WHERE t.activo = TRUE AND (t.id_municipio = 1 OR t.id_municipio IS NULL) AND a.id_area IS NULL
        """)
        check("filtro gestion: suma por gestion + sin gestion = total", suma + db["n"] == s["total"], f"{suma}+{db['n']} vs {s['total']}")
        if prs:
            p0 = prs[0]["id_tipo_prestacion"]
            r = await c.get(f"{BASE}/score", params={"id_tipo_prestacion": p0}, headers=h)
            db = await q1("SELECT COUNT(*) AS n FROM turnos WHERE activo = TRUE AND id_tipo_prestacion = :p AND (id_municipio = 1 OR id_municipio IS NULL)", p=p0)
            check("filtro prestacion: score.total = DB", r.status_code == 200 and r.json()["total"] == db["n"], short(r))
        # Periodo: anio + meses -> periodo anterior contiguo (regla del Ejecutivo).
        if mensual:
            anio, mes_n = (int(x) for x in mensual[-1]["mes"].split("-"))
            r = await c.get(f"{BASE}/score", params={"anio": anio, "meses": str(mes_n)}, headers=h)
            sc = r.json()
            check("score anio+meses: total = mensual del mes", r.status_code == 200 and sc["total"] == mensual[-1]["total"], short(r))
            check("score anio+meses: trae anterior", isinstance(sc["anterior"], dict) and ind_ok(sc["anterior"]))
            a2, m2 = (anio, mes_n - 1) if mes_n > 1 else (anio - 1, 12)
            prev = next((x["total"] for x in mensual if x["mes"] == f"{a2}-{m2:02d}"), 0)
            check("score anio+meses: anterior.total = mes contiguo previo", sc["anterior"]["total"] == prev, f"{sc['anterior']['total']} vs {prev}")
            r = await c.get(f"{BASE}/matriz", params={"anio": anio, "meses": str(mes_n)}, headers=h)
            mm = r.json()
            check("matriz anio+meses: total.ant.total = anterior", r.status_code == 200 and (mm["total"]["ant"] or {}).get("total") == prev, short(r))
            r = await c.get(f"{BASE}/score", params={"desde": f"{anio}-{mes_n:02d}-01", "hasta": f"{anio}-{mes_n:02d}-28"}, headers=h)
            check("score desde/hasta: trae anterior de igual largo", r.status_code == 200 and isinstance(r.json()["anterior"], dict), short(r))
        r = await c.get(f"{BASE}/score", params={"anio": 2000}, headers=h)
        check("score anio sin datos: todo en cero, sin 500", r.status_code == 200 and r.json()["total"] == 0 and r.json()["pct_ausentismo"] is None, short(r))
        r = await c.get(f"{BASE}/matriz", params={"anio": 2000}, headers=h)
        check("matriz anio sin datos: filas vacias", r.status_code == 200 and r.json()["filas"] == [], short(r))

        # ── 8. Exportaciones ────────────────────────────────────────────────
        print("\n[8] Exportaciones")
        r = await c.get(f"{BASE}/turnos-detalle", params={"limit": 3}, headers=h)
        td = r.json()
        check("turnos-detalle 200 + X-Total-Count = score.total", r.status_code == 200 and r.headers.get("x-total-count") == str(s["total"]), f"{short(r, 60)} X-Total-Count={r.headers.get('x-total-count')}")
        check("turnos-detalle: limit respetado", len(td) <= 3)
        check("turnos-detalle: shape sin datos personales", all({"id_turno", "fecha", "estado", "origen", "gestion", "ubicacion", "prestacion", "espera_min",
              "atencion_registrada", "csat"} <= set(x.keys()) and not ({"nombre", "apellido", "dni", "id_ciudadano"} & set(x.keys())) for x in td))
        r = await c.get(f"{BASE}/turnos-detalle", params={"limit": 20000}, headers=h)
        check("turnos-detalle limit > 10000 -> 422", r.status_code == 422, short(r))
        r = await c.get(f"{BASE}/guardia-detalle", params={"limit": 3}, headers=h)
        gd = r.json()
        check("guardia-detalle 200 + X-Total-Count = derivaciones", r.status_code == 200 and r.headers.get("x-total-count") == str(g["derivaciones"]), short(r, 60))
        check("guardia-detalle: shape sin paciente", all({"id_emergencia_atencion", "estado", "derivado_en", "tipo", "prioridad", "ubicacion", "con_ciudadano"} <= set(x.keys())
              and not ({"paciente_nombre", "id_ciudadano"} & set(x.keys())) for x in gd))

        # ── 9. Auth ─────────────────────────────────────────────────────────
        print("\n[9] Auth")
        for p in ("/score", "/matriz", "/guardia", "/eventos", "/turnos-detalle", "/catalogo/gestiones"):
            r = await c.get(f"{BASE}{p}")
            check(f"sin token {p} -> 401", r.status_code == 401, short(r, 60))
        r = await c.get(f"{BASE}/score", headers={"Authorization": "Bearer basura"})
        check("token invalido -> 401", r.status_code == 401, short(r, 60))
        # Guard JWT a nivel router: cualquier nivel autenticado entra (la UI gatea <= 2).
        n2 = await q1("SELECT email FROM usuarios WHERE activo = TRUE AND nivel_acceso = 2 AND email LIKE '%@municipio.gob.ar' AND debe_cambiar_password = FALSE ORDER BY id_usuario LIMIT 1")
        if n2:
            h2 = await login(c, n2["email"])
            r = await c.get(f"{BASE}/score", headers=h2)
            check(f"supervisor n2 ({n2['email']}) -> 200", r.status_code == 200, short(r, 60))
        else:
            skip("supervisor n2", "no hay cuenta n2 dev")
        # Marker OpenAPI del router nuevo (para verificar el deploy en prod, §9).
        r = await c.get("/openapi.json")
        paths = r.json().get("paths", {})
        check("openapi: /bi/atencion/score con marker 422", "422" in paths.get(f"{BASE}/score", {}).get("get", {}).get("responses", {}))
        check("openapi: 19 rutas /bi/atencion/*", sum(1 for p in paths if p.startswith(BASE)) == 19, str(sum(1 for p in paths if p.startswith(BASE))))

    print(f"\n== Resultado: {ok_count} OK - {fail_count} FAIL - {skip_count} SKIP ==")
    for f in fallidos:
        print(f"   FAIL {f['caso']}: {f['detalle']}")
    sys.exit(1 if fail_count else 0)


if __name__ == "__main__":
    asyncio.run(main())
