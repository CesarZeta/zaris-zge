# -*- coding: utf-8 -*-
"""
Smoke in-process — contorno del municipio y catálogo de gobiernos locales
(PLAN_CONTORNO_MUNICIPIO.md). Crece tarea a tarea.

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_contorno.py [prueba ...]

SOLO LOCAL. Sin argumentos corre todas las pruebas; con nombres, solo esas.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("ENV_FILE", ".env.local")
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402

if "zaris_dev" not in settings.ASYNC_DATABASE_URI:
    sys.exit("ABORT: este smoke es SOLO LOCAL (la DB configurada no es zaris_dev).")
settings.RESEND_API_KEY = ""

from app.core.database import AsyncSessionLocal  # noqa: E402
from smoke_alta_municipio import _cliente, _municipio_c, _super_headers, _token  # noqa: E402

RES: list[tuple[str, bool, str]] = []


def check(nombre: str, ok: bool, detalle: str = "") -> None:
    RES.append((nombre, ok, detalle))
    print(f"  {'OK  ' if ok else 'FAIL'} {nombre}{(' — ' + str(detalle)) if detalle and not ok else ''}")


async def _escalar(db, sql: str, params: dict | None = None):
    return (await db.execute(text(sql), params or {})).scalar()


# ── Tarea 1: catálogo de gobiernos locales ───────────────────────────────────

async def test_catalogo_completo() -> None:
    async with AsyncSessionLocal() as db:
        n = await _escalar(db, "SELECT count(*) FROM partidos WHERE codigo_georef IS NOT NULL")
        check("2082 gobiernos locales con código", n == 2082, n)
        n = await _escalar(db, "SELECT count(*) FROM provincias WHERE codigo_georef IS NOT NULL")
        check("24 provincias con código", n == 24, n)


async def test_catalogo_codigos() -> None:
    async with AsyncSessionLocal() as db:
        for nombre, prov, codigo in (("Pergamino", "06", "060623"), ("Vicente López", "06", "060861"),
                                     ("Comuna 3", "02", "022021")):
            got = await _escalar(db, """
                SELECT pa.codigo_georef FROM partidos pa JOIN provincias pr ON pr.id_provincia = pa.id_provincia
                 WHERE pa.nombre = :n AND pr.codigo_georef = :p AND pa.activo""", {"n": nombre, "p": prov})
            check(f"{nombre} tiene el código {codigo}", got == codigo, got)
        cat = await _escalar(db, "SELECT categoria FROM partidos WHERE codigo_georef = '060623'")
        check("Pergamino trae su categoría", bool(cat), cat)


async def test_catalogo_sin_huerfanos_de_reclamos() -> None:
    async with AsyncSessionLocal() as db:
        n = await _escalar(db, """
            SELECT count(*) FROM reclamos r JOIN localidades l ON l.id_localidad = r.id_localidad
              JOIN partidos pa ON pa.id_partido = l.id_partido WHERE NOT pa.activo""")
        check("ningún reclamo queda con su localidad en un partido de baja", n == 0, n)


async def test_catalogo_bajas_sin_municipio() -> None:
    async with AsyncSessionLocal() as db:
        n = await _escalar(db, """
            SELECT count(*) FROM municipios m JOIN partidos pa ON pa.id_partido = m.id_partido
             WHERE NOT pa.activo AND m.estado <> 'baja'""")
        check("ningún municipio vigente apunta a un partido de baja", n == 0, n)


# ── Tarea 2: /geo/partidos con búsqueda ──────────────────────────────────────

async def test_geo_partidos_q() -> None:
    C = await _municipio_c()
    h = _token(C["n2"], C["id"])
    async with AsyncSessionLocal() as db:
        ba = await _escalar(db, "SELECT id_provincia FROM provincias WHERE codigo_georef = '06'")
        cba = await _escalar(db, "SELECT id_provincia FROM provincias WHERE codigo_georef = '14'")
        baja = await _escalar(db, "SELECT nombre FROM partidos WHERE NOT activo AND id_provincia = :p LIMIT 1",
                              {"p": cba})
    async with _cliente() as c:
        r = await c.get("/api/v1/geo/partidos", params={"id_provincia": ba, "q": "perga"}, headers=h)
        filas = r.json() if r.status_code == 200 else []
        check("q=perga en Buenos Aires trae solo Pergamino con su código",
              [f.get("codigo_georef") for f in filas] == ["060623"], f"{r.status_code} {str(filas)[:200]}")
        check("la fila trae categoría y nombre completo",
              bool(filas and filas[0].get("categoria") and filas[0].get("nombre_completo")), filas[:1])
        r = await c.get("/api/v1/geo/partidos", params={"id_provincia": cba, "q": "villa sarm"}, headers=h)
        nombres = [f["nombre"] for f in r.json()] if r.status_code == 200 else []
        check("q con dos palabras en Córdoba: los dos Villa Sarmiento, con nombres distintos",
              len(nombres) == 2 and len(set(nombres)) == 2, f"{r.status_code} {nombres}")
        r = await c.get("/api/v1/geo/partidos", params={"id_provincia": cba, "q": "rio cuarto"}, headers=h)
        check("sin tildes encuentra con tildes (rio cuarto → Río Cuarto)",
              r.status_code == 200 and "Río Cuarto" in [f["nombre"] for f in r.json()], r.text[:200])
        r = await c.get("/api/v1/geo/partidos", params={"id_provincia": cba, "q": baja}, headers=h)
        check("una fila de baja no se ofrece", r.status_code == 200 and baja not in [f["nombre"] for f in r.json()],
              f"{baja} {r.text[:200]}")
        r = await c.get("/api/v1/geo/partidos", params={"id_provincia": cba, "q": "a", "limit": 5}, headers=h)
        check("limit acota la respuesta", r.status_code == 200 and len(r.json()) == 5, f"{r.status_code}")
        r = await c.get("/api/v1/geo/partidos", params={"id_provincia": ba}, headers=h)
        check("sin q sigue trayendo la provincia entera", r.status_code == 200 and len(r.json()) == 135,
              f"{r.status_code} {len(r.json())}")


# ── Tarea 3: normalizar_contorno (puro) ─────────────────────────────────────

FIX = Path(AQUI) / "fixtures" / "contorno"


def _fix(nombre: str) -> str:
    return (FIX / nombre).read_text(encoding="utf-8")


def _paso(entrada) -> str | None:
    """Paso del ContornoInvalido que tira la normalización, o None si la acepta."""
    from app.services.contorno import ContornoInvalido, normalizar_contorno
    try:
        normalizar_contorno(entrada)
    except ContornoInvalido as e:
        return e.paso
    return None


def _mensaje(entrada) -> str:
    from app.services.contorno import ContornoInvalido, normalizar_contorno
    try:
        normalizar_contorno(entrada)
    except ContornoInvalido as e:
        return e.mensaje
    return ""


def _coords(g: dict):
    pols = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    return [c for pol in pols for anillo in pol for c in anillo]


async def test_norm_pergamino_ign() -> None:
    from app.services.contorno import normalizar_contorno
    c = normalizar_contorno(_fix("pergamino_ign.geojson"))
    check("Pergamino del IGN: una parte", c.partes == 1, c.partes)
    check("vértices antes = 2681", c.vertices_antes == 2681, c.vertices_antes)
    check("simplifica (menos vértices)", c.vertices_despues < 2681, c.vertices_despues)
    check("pesa hasta 200 KB", len(json.dumps(c.geometria)) <= 200_000, len(json.dumps(c.geometria)))
    check("coordenadas con 5 decimales o menos",
          all(len(repr(v).split(".")[1]) <= 5 for p in _coords(c.geometria) for v in p if "." in repr(v)))
    r = c.recuadro
    check("recuadro de Pergamino", abs(r["sur"] + 34.176) < 0.001 and abs(r["oeste"] + 60.943) < 0.001
          and abs(r["norte"] + 33.540) < 0.001 and abs(r["este"] + 60.139) < 0.001, r)


async def test_norm_metros() -> None:
    check("en metros → paso metros", _paso(_fix("pergamino_metros.geojson")) == "metros",
          _paso(_fix("pergamino_metros.geojson")))
    check("el mensaje dice EPSG:4326", "EPSG:4326" in _mensaje(_fix("pergamino_metros.geojson")))


async def test_norm_invertido() -> None:
    check("lat/lon invertidas → paso invertido", _paso(_fix("pergamino_invertido.geojson")) == "invertido",
          _paso(_fix("pergamino_invertido.geojson")))


async def test_norm_linea() -> None:
    check("una línea → paso tipo", _paso(_fix("linea.geojson")) == "tipo", _paso(_fix("linea.geojson")))
    check("el mensaje nombra LineString", "LineString" in _mensaje(_fix("linea.geojson")))


async def test_norm_dos_partes() -> None:
    from app.services.contorno import normalizar_contorno
    c = normalizar_contorno(_fix("dos_partes.geojson"))
    check("dos Features → MultiPolygon de 2 partes", c.geometria["type"] == "MultiPolygon" and c.partes == 2,
          (c.geometria["type"], c.partes))


async def test_norm_hueco_preservado() -> None:
    from app.services.contorno import normalizar_contorno
    c = normalizar_contorno(_fix("con_hueco.geojson"))
    check("el hueco sobrevive", c.geometria["type"] == "Polygon" and len(c.geometria["coordinates"]) == 2,
          c.geometria)


async def test_norm_isla_diminuta() -> None:
    from app.services.contorno import normalizar_contorno
    c = normalizar_contorno(_fix("isla_diminuta.geojson"))
    check("la isla de 2 m se descarta", c.partes == 1, c.partes)
    check("con aviso", any("descart" in a for a in c.avisos), c.avisos)


async def test_norm_binario_y_kml() -> None:
    zip_ = bytes([0x50, 0x4B, 0x03, 0x04, 0x14, 0x00, 0x00, 0x00, 0x08, 0x00]) + b"shapefile"
    kml = '<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document/></kml>'
    check("un .zip → paso formato", _paso(zip_) == "formato", _paso(zip_))
    check("un KML → paso formato", _paso(kml) == "formato", _paso(kml))
    check("el mensaje sugiere QGIS", "QGIS" in _mensaje(kml), _mensaje(kml))


async def test_norm_vacio() -> None:
    check("FeatureCollection vacía → paso tipo",
          _paso({"type": "FeatureCollection", "features": []}) == "tipo")
    check("Feature sin geometría → paso tipo",
          _paso({"type": "Feature", "properties": {}, "geometry": None}) == "tipo")


async def test_norm_tamano_entrada() -> None:
    grande = '{"type":"Polygon","coordinates":[[' + ",".join(["[-62.5,-36.5]"] * 400_000) + "]]}"
    check("entrada de más de 5 MB → paso tamano", len(grande) > 5_000_000 and _paso(grande) == "tamano",
          (len(grande), _paso(grande)))


async def test_norm_z_y_sin_cerrar() -> None:
    from app.services.contorno import normalizar_contorno
    g = {"type": "Polygon", "coordinates": [[[-62.5, -36.5, 10], [-62.4, -36.5, 11], [-62.4, -36.4, 12],
                                               [-62.5, -36.4, 13]]]}
    c = normalizar_contorno(g)
    anillo = c.geometria["coordinates"][0]
    check("se cierra el anillo", anillo[0] == anillo[-1], anillo)
    check("sin la tercera coordenada", all(len(p) == 2 for p in anillo), anillo[:2])


async def test_norm_fuera_de_pais() -> None:
    europa = {"type": "Polygon", "coordinates": [[[2.3, 48.8], [2.4, 48.8], [2.4, 48.9], [2.3, 48.9], [2.3, 48.8]]]}
    check("un polígono en Europa → paso pais", _paso(europa) == "pais", _paso(europa))


async def test_zona_pergamino() -> None:
    from app.services.contorno import normalizar_contorno, zona_desde_contorno
    z = zona_desde_contorno(normalizar_contorno(_fix("pergamino_ign.geojson")))
    ok = (abs(float(z["geo_bbox_centro_lat"]) + 33.858) < 0.001 and abs(float(z["geo_bbox_centro_lon"]) + 60.541) < 0.001
          and abs(float(z["geo_bbox_delta_grados"]) - 0.502) < 0.001 and all(isinstance(v, str) for v in z.values()))
    check("zona derivada de Pergamino: centro del recuadro, mitad del lado mayor + 0,1", ok, z)


# ── Tarea 4: lectores con MultiPolygon ──────────────────────────────────────

SAN_ANDRES_ENCUADRE = {"sur": -34.56925, "oeste": -58.5998, "norte": -34.44334, "este": -58.45952,
                       "origen": "contorno"}   # anotado el 2026-10-28 antes de tocar geo_limite.py


async def _con_contorno(id_municipio: int, geometria: dict | None):
    """Pone (o vacía, con None) el contorno del municipio; devuelve el valor anterior para restaurarlo."""
    from app.core.config_municipio import guardar_config, leer_config
    async with AsyncSessionLocal() as db:
        antes = await leer_config(db, "geo_limite_geojson", id_municipio)
        await guardar_config(db, "geo_limite_geojson", json.dumps(geometria) if geometria else "", id_municipio)
        await db.commit()
    return antes


async def _restaurar(id_municipio: int, valor) -> None:
    from app.core.config_municipio import guardar_config
    async with AsyncSessionLocal() as db:
        await guardar_config(db, "geo_limite_geojson", valor or "", id_municipio)
        await db.commit()


async def test_lectores_multi() -> None:
    from app.services.contorno import normalizar_contorno
    from app.services.geo_limite import encuadre_municipio, leer_limite, punto_en_limite
    C = await _municipio_c()
    geo = normalizar_contorno(_fix("dos_partes.geojson")).geometria
    antes = await _con_contorno(C["id"], geo)
    try:
        async with AsyncSessionLocal() as db:
            limite = await leer_limite(db, C["id"])
            enc = await encuadre_municipio(db, C["id"])
        check("leer_limite acepta el MultiPolygon", limite is not None and limite["type"] == "MultiPolygon",
              limite and limite["type"])
        check("el encuadre cubre las dos partes", enc["origen"] == "contorno" and abs(enc["oeste"] + 62.5) < 1e-6
              and abs(enc["este"] + 62.1) < 1e-6, enc)
        if limite:
            check("adentro de la primera parte", punto_en_limite(limite, -36.45, -62.45))
            check("adentro de la segunda parte", punto_en_limite(limite, -36.45, -62.15))
            check("afuera entre las dos", not punto_en_limite(limite, -36.45, -62.30))
    finally:
        await _restaurar(C["id"], antes)


async def test_lectores_hueco() -> None:
    from app.services.contorno import normalizar_contorno
    from app.services.geo_limite import punto_en_limite
    hueco = normalizar_contorno(_fix("con_hueco.geojson")).geometria
    check("Polygon: afuera en el hueco", not punto_en_limite(hueco, -36.45, -62.45))
    check("Polygon: adentro fuera del hueco", punto_en_limite(hueco, -36.49, -62.49))
    multi = {"type": "MultiPolygon", "coordinates": [hueco["coordinates"],
             [[[-62.2, -36.5], [-62.1, -36.5], [-62.1, -36.4], [-62.2, -36.4], [-62.2, -36.5]]]]}
    check("MultiPolygon: afuera en el hueco de una parte", not punto_en_limite(multi, -36.45, -62.45))
    check("MultiPolygon: adentro de la otra parte", punto_en_limite(multi, -36.45, -62.15))


async def test_lectores_compat_san_andres() -> None:
    from app.services.geo_limite import encuadre_municipio, leer_limite
    async with AsyncSessionLocal() as db:
        limite = await leer_limite(db, 1)
        enc = await encuadre_municipio(db, 1)
    check("San Andrés sigue leyéndose como Polygon", limite is not None and limite["type"] == "Polygon")
    check("San Andrés: mismo encuadre que antes", enc == SAN_ANDRES_ENCUADRE, enc)


# ── Tarea 5: contorno oficial del IGN, guardar y quitar (API) ────────────────

PERGAMINO, VICENTE_LOPEZ = "060623", "060861"
CLAVES_C = ["geo_limite_geojson", "geo_limite_origen", "geo_bbox_centro_lat", "geo_bbox_centro_lon",
            "geo_bbox_delta_grados"]


async def _foto(mid: int) -> dict:
    from app.core.config_municipio import leer_configs
    async with AsyncSessionLocal() as db:
        return await leer_configs(db, CLAVES_C, mid)


async def _volver(mid: int, foto: dict) -> None:
    """Deja C como estaba: sus claves de contorno y zona, y sin partido (es un municipio de prueba)."""
    from app.core.config_municipio import guardar_config
    async with AsyncSessionLocal() as db:
        for k in CLAVES_C:
            await guardar_config(db, k, foto.get(k) or "", mid)
        await db.execute(text("UPDATE municipios SET id_partido = NULL WHERE id_municipio = :m"), {"m": mid})
        await db.commit()


async def _c_con_partido(codigo: str | None) -> tuple[dict, int | None]:
    C = await _municipio_c()
    async with AsyncSessionLocal() as db:
        idp = (await _escalar(db, "SELECT id_partido FROM partidos WHERE codigo_georef = :c", {"c": codigo})
               if codigo else None)
        await db.execute(text("UPDATE municipios SET id_partido = :p WHERE id_municipio = :m"), {"p": idp, "m": C["id"]})
        await db.commit()
    return C, idp


def _ign(respuesta) -> list:
    """El IGN simulado: `respuesta(request)` devuelve el httpx.Response. Devuelve los pedidos recibidos."""
    import httpx
    import app.services.contorno as ct
    pedidos: list = []

    def manejar(request):
        pedidos.append(request)
        return respuesta(request)
    ct.TRANSPORTE_IGN = httpx.MockTransport(manejar)
    return pedidos


def _ign_off() -> None:
    import app.services.contorno as ct
    ct.TRANSPORTE_IGN = None


def _ign_pergamino():
    import httpx
    return _ign(lambda _r: httpx.Response(200, text=_fix("pergamino_ign.geojson"),
                                          headers={"content-type": "application/json"}))


async def test_ign_ok() -> None:
    C, idp = await _c_con_partido(PERGAMINO)
    foto = await _foto(C["id"])
    pedidos = _ign_pergamino()
    try:
        async with AsyncSessionLocal() as db:
            h = await _super_headers(db)
        async with _cliente() as c:
            r = await c.get("/api/v1/super/contorno-oficial", params={"id_partido": idp}, headers=h)
            v = r.json() if r.status_code == 200 else {}
            check("super: oficial por partido → 200 con los 2681 vértices",
                  r.status_code == 200 and v.get("vertices_antes") == 2681, f"{r.status_code} {r.text[:200]}")
            o = v.get("origen") or {}
            check("origen IGN con código y nombre", o.get("via") == "ign" and o.get("codigo") == PERGAMINO
                  and o.get("nombre") == "Municipio Pergamino", o)
            check("al IGN se le pide la capa ign:municipio por el código",
                  bool(pedidos) and "ign%3Amunicipio" in str(pedidos[-1].url) and "060623" in str(pedidos[-1].url),
                  pedidos and str(pedidos[-1].url))
            r = await c.get("/api/v1/contorno/oficial", headers=_token(C["n1"], C["id"]))
            check("Configuración: el oficial del partido del municipio → 200",
                  r.status_code == 200 and r.json().get("vertices_antes") == 2681, f"{r.status_code} {r.text[:200]}")
    finally:
        _ign_off()
        await _volver(C["id"], foto)


async def test_ign_respuesta_no_json() -> None:
    import httpx
    C, idp = await _c_con_partido(PERGAMINO)
    _ign(lambda _r: httpx.Response(200, text='<?xml version="1.0"?><ows:ExceptionReport/>'))
    try:
        async with _cliente() as c:
            r = await c.get("/api/v1/contorno/oficial", headers=_token(C["n1"], C["id"]))
        check("el IGN devuelve XML con 200 → 502 limpio", r.status_code == 502 and "IGN" in r.text,
              f"{r.status_code} {r.text[:200]}")
    finally:
        _ign_off()
        await _volver(C["id"], await _foto(C["id"]))


async def test_ign_vacio() -> None:
    import httpx
    C, idp = await _c_con_partido(PERGAMINO)
    _ign(lambda _r: httpx.Response(200, json={"type": "FeatureCollection", "features": []}))
    try:
        async with _cliente() as c:
            r = await c.get("/api/v1/contorno/oficial", headers=_token(C["n1"], C["id"]))
        check("el IGN no tiene el contorno → 404 «no tiene»", r.status_code == 404 and "no tiene" in r.text,
              f"{r.status_code} {r.text[:200]}")
    finally:
        _ign_off()
        await _volver(C["id"], await _foto(C["id"]))


async def test_ign_timeout() -> None:
    import httpx

    def lento(_r):
        raise httpx.ReadTimeout("tardó")
    C, idp = await _c_con_partido(PERGAMINO)
    _ign(lento)
    try:
        async with _cliente() as c:
            r = await c.get("/api/v1/contorno/oficial", headers=_token(C["n1"], C["id"]))
        check("el IGN no responde a tiempo → 502", r.status_code == 502, f"{r.status_code} {r.text[:200]}")
    finally:
        _ign_off()
        await _volver(C["id"], await _foto(C["id"]))


async def test_ign_sin_partido() -> None:
    C, _ = await _c_con_partido(None)
    async with _cliente() as c:
        r = await c.get("/api/v1/contorno/oficial", headers=_token(C["n1"], C["id"]))
    check("municipio sin partido → 409 «subí un archivo»", r.status_code == 409 and "archivo" in r.text,
          f"{r.status_code} {r.text[:200]}")


async def test_api_guardar_y_zona() -> None:
    from app.services.contorno import normalizar_contorno, zona_desde_contorno
    C, _ = await _c_con_partido(None)
    foto = await _foto(C["id"])
    h1 = _token(C["n1"], C["id"])
    fix = _fix("pergamino_ign.geojson")
    try:
        async with _cliente() as c:
            r = await c.put("/api/v1/contorno", headers=h1,
                            json={"geojson": fix, "origen": {"via": "archivo", "archivo": "pergamino.geojson"}})
            check("guardar desde Configuración → 200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
            vals = await _foto(C["id"])
            c_norm = normalizar_contorno(fix)
            check("se guardó el contorno depurado",
                  json.loads(vals.get("geo_limite_geojson") or "null") == c_norm.geometria)
            origen = json.loads(vals.get("geo_limite_origen") or "{}")
            check("origen archivo, con nombre y fecha", origen.get("via") == "archivo"
                  and origen.get("archivo") == "pergamino.geojson" and bool(origen.get("fecha")), origen)
            z = zona_desde_contorno(c_norm)
            check("la zona quedó derivada del contorno", all(vals.get(k) == v for k, v in z.items()),
                  {k: vals.get(k) for k in z})
            check("la respuesta trae la zona", r.status_code == 200 and r.json().get("zona") == z,
                  r.status_code == 200 and r.json().get("zona"))
            r = await c.get("/api/v1/contorno", headers=h1)
            cv = (r.json() or {}).get("contorno") if r.status_code == 200 else None
            check("GET devuelve el guardado con su origen", bool(cv) and cv["partes"] == 1
                  and cv["origen"]["via"] == "archivo", f"{r.status_code} {str(cv)[:200]}")
            r = await c.put("/api/v1/contorno", headers=h1,
                            json={"geojson": _fix("linea.geojson"), "origen": {"via": "archivo", "archivo": "x"}})
            check("una línea → 422 con paso tipo", r.status_code == 422 and r.json().get("paso") == "tipo",
                  f"{r.status_code} {r.text[:200]}")
            r = await c.put("/api/v1/contorno", headers=h1,
                            json={"geojson": fix, "origen": {"via": "ign", "codigo": PERGAMINO}})
            check("origen IGN sin ser el partido del municipio → 422", r.status_code == 422,
                  f"{r.status_code} {r.text[:200]}")
    finally:
        await _volver(C["id"], foto)


async def test_api_aviso_zona() -> None:
    from app.core.config_municipio import guardar_config
    C, _ = await _c_con_partido(None)
    foto = await _foto(C["id"])
    h1 = _token(C["n1"], C["id"])

    async def zona(lat, lon, delta):
        async with AsyncSessionLocal() as db:
            for k, v in zip(CLAVES_C[2:], (lat, lon, delta)):
                await guardar_config(db, k, v, C["id"])
            await db.commit()
    try:
        async with _cliente() as c:
            await zona("-31.4", "-64.2", "0.2")
            r = await c.post("/api/v1/contorno/previsualizar", headers=h1, json={"geojson": _fix("pergamino_ign.geojson")})
            check("zona previa lejana → aviso", r.status_code == 200 and bool(r.json().get("aviso_zona")),
                  f"{r.status_code} {r.text[:200]}")
            await zona("-33.85", "-60.54", "0.3")
            r = await c.post("/api/v1/contorno/previsualizar", headers=h1, json={"geojson": _fix("pergamino_ign.geojson")})
            check("zona previa cercana → sin aviso", r.status_code == 200 and r.json().get("aviso_zona") is None,
                  f"{r.status_code} {r.text[:200]}")
            check("previsualizar no guarda", not (await _foto(C["id"])).get("geo_limite_geojson"))
    finally:
        await _volver(C["id"], foto)


async def test_api_guards() -> None:
    C, _ = await _c_con_partido(None)
    foto = await _foto(C["id"])
    fix = _fix("pergamino_ign.geojson")
    cuerpo = {"geojson": fix, "origen": {"via": "archivo", "archivo": "p.geojson"}}
    try:
        async with _cliente() as c:
            h2 = _token(C["n2"], C["id"])
            r1 = await c.put("/api/v1/contorno", headers=h2, json=cuerpo)
            r2 = await c.delete("/api/v1/contorno", headers=h2)
            r3 = await c.post("/api/v1/contorno/previsualizar", headers=h2, json={"geojson": fix})
            check("nivel 2 → 403 en guardar, quitar y previsualizar",
                  (r1.status_code, r2.status_code, r3.status_code) == (403, 403, 403),
                  (r1.status_code, r2.status_code, r3.status_code))
            async with AsyncSessionLocal() as db:
                hs = await _super_headers(db)
                antes = await _escalar(db, "SELECT count(*) FROM super_admin_acceso WHERE id_municipio = :m "
                                           "AND accion = 'municipio_editar' AND detalle LIKE 'contorno%'", {"m": C["id"]})
            r = await c.put(f"/api/v1/super/municipios/{C['id']}/contorno", headers=hs, json=cuerpo)
            async with AsyncSessionLocal() as db:
                despues = await _escalar(db, "SELECT count(*) FROM super_admin_acceso WHERE id_municipio = :m "
                                             "AND accion = 'municipio_editar' AND detalle LIKE 'contorno%'", {"m": C["id"]})
            check("super desde la ficha → 200 y queda registrado", r.status_code == 200 and despues == antes + 1,
                  f"{r.status_code} {antes}→{despues} {r.text[:200]}")
            r = await c.get(f"/api/v1/super/municipios/{C['id']}/contorno", headers=hs)
            check("super lee el contorno de la ficha", r.status_code == 200 and (r.json() or {}).get("contorno"),
                  f"{r.status_code}")
            async with AsyncSessionLocal() as db:
                otro = await _escalar(db, "SELECT id_usuario FROM usuarios WHERE id_municipio = 1 AND nivel_acceso = 1 "
                                          "AND activo ORDER BY id_usuario LIMIT 1")
            r = await c.get("/api/v1/contorno", headers=_token(otro, 1))
            cv = (r.json() or {}).get("contorno") if r.status_code == 200 else None
            check("el administrador de otro municipio ve el suyo, no el de C",
                  bool(cv) and abs(cv["recuadro"]["oeste"] - SAN_ANDRES_ENCUADRE["oeste"]) < 1e-6,
                  f"{r.status_code} {cv and cv['recuadro']}")
    finally:
        await _volver(C["id"], foto)


async def test_api_admin_tablas_bloquea() -> None:
    from app.core.config_municipio import guardar_config
    C, _ = await _c_con_partido(None)
    foto = await _foto(C["id"])
    h1 = _token(C["n1"], C["id"])
    try:
        async with AsyncSessionLocal() as db:
            await guardar_config(db, "geo_limite_geojson", "", C["id"])
            await db.commit()
            id_config = await _escalar(db, "SELECT id_config FROM configuracion_general WHERE id_municipio = :m "
                                           "AND clave = 'geo_limite_geojson'", {"m": C["id"]})
        async with _cliente() as c:
            r = await c.put(f"/api/v1/admin/configuracion_general/{id_config}", headers=h1,
                            json={"valor": '{"type":"Polygon","coordinates":[]}'})
            check("Maestros: editar el contorno a mano → 422", r.status_code == 422 and "Contorno" in r.text,
                  f"{r.status_code} {r.text[:200]}")
            r = await c.post("/api/v1/admin/configuracion_general", headers=h1,
                             json={"clave": "geo_limite_origen", "valor": "{}", "tipo": "string",
                                   "descripcion": "x", "activo": True})
            check("Maestros: crear el origen a mano → 422", r.status_code == 422 and "Contorno" in r.text,
                  f"{r.status_code} {r.text[:200]}")
    finally:
        await _volver(C["id"], foto)


async def test_api_alta_contorno() -> None:
    import smoke_alta_municipio as sam
    from app.services.contorno import normalizar_contorno, zona_desde_contorno
    ctx = await sam._contexto_alta()
    async with AsyncSessionLocal() as db:
        sam.CODIGOS_USADOS.update(r[0] for r in (await db.execute(text("SELECT codigo_corto FROM municipios"))).all())
    fix = _fix("pergamino_ign.geojson")
    suf, cod = sam._sufijo()
    body = sam._alta_body(suf, cod, id_provincia=ctx["ba"])
    body["identidad"] = {**body["identidad"], "geo_limite_geojson": fix,
                         "geo_limite_origen": {"via": "archivo", "archivo": "pergamino.geojson"}}
    async with _cliente() as c:
        r = await c.post("/api/v1/super/municipios", json=body, headers=ctx["h"])
        check("alta con contorno → 201", r.status_code == 201, f"{r.status_code} {r.text[:200]}")
        if r.status_code == 201:
            vals = await _foto(r.json()["id_municipio"])
            c_norm = normalizar_contorno(fix)
            check("el alta guardó el contorno depurado",
                  json.loads(vals.get("geo_limite_geojson") or "null") == c_norm.geometria)
            check("con su origen", json.loads(vals.get("geo_limite_origen") or "{}").get("via") == "archivo")
            check("y la zona derivada", all(vals.get(k) == v for k, v in zona_desde_contorno(c_norm).items()),
                  {k: vals.get(k) for k in CLAVES_C[2:]})
        suf2, cod2 = sam._sufijo()
        body2 = sam._alta_body(suf2, cod2, id_provincia=ctx["ba"])
        body2["identidad"] = {**body2["identidad"], "geo_limite_geojson": _fix("linea.geojson")}
        r = await c.post("/api/v1/super/municipios", json=body2, headers=ctx["h"])
        async with AsyncSessionLocal() as db:
            creado = await _escalar(db, "SELECT count(*) FROM municipios WHERE subdominio = :s", {"s": f"d-{suf2}"})
        check("alta con una línea → 422 con paso tipo y sin crear el municipio",
              r.status_code == 422 and r.json().get("paso") == "tipo" and creado == 0,
              f"{r.status_code} {creado} {r.text[:200]}")


async def test_api_quitar() -> None:
    from app.services.geo_limite import encuadre_municipio
    C, _ = await _c_con_partido(None)
    foto = await _foto(C["id"])
    h1 = _token(C["n1"], C["id"])
    try:
        async with _cliente() as c:
            await c.put("/api/v1/contorno", headers=h1, json={"geojson": _fix("pergamino_ign.geojson"),
                                                              "origen": {"via": "archivo", "archivo": "p"}})
            zona_antes = {k: v for k, v in (await _foto(C["id"])).items() if k in CLAVES_C[2:]}
            r = await c.delete("/api/v1/contorno", headers=h1)
            vals = await _foto(C["id"])
            check("quitar → 204 y sin contorno ni origen", r.status_code == 204
                  and not vals.get("geo_limite_geojson") and not vals.get("geo_limite_origen"),
                  f"{r.status_code} {r.text[:200]}")
            check("la zona queda", {k: vals.get(k) for k in CLAVES_C[2:]} == zona_antes)
            async with AsyncSessionLocal() as db:
                enc = await encuadre_municipio(db, C["id"])
            check("los mapas encuadran por la zona", enc["origen"] == "zona", enc)
    finally:
        await _volver(C["id"], foto)


async def _cambiar_partido(c, hs: dict, mid: int, id_partido: int, quitar: bool = False):
    async with AsyncSessionLocal() as db:
        m = (await db.execute(text("SELECT nombre, subdominio, codigo_pais, id_provincia, zona_horaria "
                                   "FROM municipios WHERE id_municipio = :m"), {"m": mid})).mappings().one()
    body = {**dict(m), "id_partido": id_partido, **({"quitar_contorno": True} if quitar else {})}
    return await c.put(f"/api/v1/super/municipios/{mid}", headers=hs, json=body)


async def test_api_cambio_partido_ign() -> None:
    C, _ = await _c_con_partido(PERGAMINO)
    foto = await _foto(C["id"])
    _ign_pergamino()
    try:
        async with AsyncSessionLocal() as db:
            hs = await _super_headers(db)
            vl = await _escalar(db, "SELECT id_partido FROM partidos WHERE codigo_georef = :c", {"c": VICENTE_LOPEZ})
        async with _cliente() as c:
            r = await c.put("/api/v1/contorno", headers=_token(C["n1"], C["id"]),
                            json={"geojson": _fix("pergamino_ign.geojson"), "origen": {"via": "ign", "codigo": PERGAMINO}})
            check("guardar el oficial del partido → 200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
            r = await _cambiar_partido(c, hs, C["id"], vl)
            check("cambiar el partido con contorno IGN sin confirmar → 409",
                  r.status_code == 409 and r.json().get("contorno_partido_anterior") is True,
                  f"{r.status_code} {r.text[:200]}")
            r = await _cambiar_partido(c, hs, C["id"], vl, quitar=True)
            vals = await _foto(C["id"])
            check("confirmando → 200 y el contorno se quita", r.status_code == 200
                  and not vals.get("geo_limite_geojson") and not vals.get("geo_limite_origen"),
                  f"{r.status_code} {r.text[:200]}")
    finally:
        _ign_off()
        await _volver(C["id"], foto)


async def test_api_cambio_partido_archivo() -> None:
    C, _ = await _c_con_partido(PERGAMINO)
    foto = await _foto(C["id"])
    try:
        async with AsyncSessionLocal() as db:
            hs = await _super_headers(db)
            vl = await _escalar(db, "SELECT id_partido FROM partidos WHERE codigo_georef = :c", {"c": VICENTE_LOPEZ})
        async with _cliente() as c:
            await c.put("/api/v1/contorno", headers=_token(C["n1"], C["id"]),
                        json={"geojson": _fix("pergamino_ign.geojson"), "origen": {"via": "archivo", "archivo": "p"}})
            r = await _cambiar_partido(c, hs, C["id"], vl)
            vals = await _foto(C["id"])
            check("contorno de archivo: el cambio de partido pasa con aviso y lo conserva",
                  r.status_code == 200 and bool(r.json().get("aviso_contorno")) and bool(vals.get("geo_limite_geojson")),
                  f"{r.status_code} {r.text[:200]}")
    finally:
        await _volver(C["id"], foto)


PRUEBAS = {f.__name__.removeprefix("test_"): f for f in (
    test_catalogo_completo, test_catalogo_codigos, test_catalogo_sin_huerfanos_de_reclamos,
    test_catalogo_bajas_sin_municipio, test_geo_partidos_q,
    test_norm_pergamino_ign, test_norm_metros, test_norm_invertido, test_norm_linea, test_norm_dos_partes,
    test_norm_hueco_preservado, test_norm_isla_diminuta, test_norm_binario_y_kml, test_norm_vacio,
    test_norm_tamano_entrada, test_norm_z_y_sin_cerrar, test_norm_fuera_de_pais, test_zona_pergamino,
    test_lectores_multi, test_lectores_hueco, test_lectores_compat_san_andres,
    test_ign_ok, test_ign_respuesta_no_json, test_ign_vacio, test_ign_timeout, test_ign_sin_partido,
    test_api_guardar_y_zona, test_api_aviso_zona, test_api_guards, test_api_admin_tablas_bloquea,
    test_api_alta_contorno, test_api_quitar, test_api_cambio_partido_ign, test_api_cambio_partido_archivo,
)}


async def main(nombres: list[str]) -> int:
    for nombre in nombres or list(PRUEBAS):
        print(f"\n[{nombre}]")
        await PRUEBAS[nombre]()
    fallas = [r for r in RES if not r[1]]
    print(f"\n{len(RES) - len(fallas)} OK / {len(fallas)} FAIL")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
