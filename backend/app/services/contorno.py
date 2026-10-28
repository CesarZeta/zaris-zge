"""
Contorno del municipio (PLAN_CONTORNO_MUNICIPIO_DISENO.md, aprobado por César el 2026-10-28).

Todo contorno que se guarde pasa por `normalizar_contorno`: el del IGN, el archivo que sube el
usuario y el del alta. El cliente nunca manda un contorno «ya depurado» que se guarde sin repasar.

- Acepta Polygon, MultiPolygon, Feature, FeatureCollection y GeometryCollection de polígonos; varias
  figuras se juntan en un MultiPolygon (sin unión geométrica).
- Rechaza con un mensaje para el usuario y un `paso` que coincide con la sección del instructivo:
  formato | metros | invertido | tipo | pais | tamano.
- Simplifica (≈ 5 m), redondea a 5 decimales (≈ 1 m) y descarta, con aviso, las partes que la
  simplificación deja sin superficie.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any

from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.polygon import orient
from shapely.validation import make_valid

from app.services.geo_limite import ENCUADRE_PAIS

TOLERANCIA_GRADOS = 0.00005     # ≈ 5 m
DECIMALES = 5                   # ≈ 1 m
MAX_ENTRADA = 5_000_000         # bytes del archivo que se sube
MAX_GUARDADO = 200_000          # bytes del contorno ya depurado
MARGEN_ZONA = 0.1               # grados que se suman al radio de la zona de búsqueda (≈ 11 km)
RADIO_MAXIMO = 5.0              # el mismo tope que valida core/geo_zona.py

COMO_ARMAR = "Mirá «¿Cómo armo el archivo?»."


class ContornoInvalido(ValueError):
    def __init__(self, mensaje: str, paso: str):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.paso = paso


@dataclass
class ContornoNormalizado:
    geometria: dict
    partes: int
    vertices_antes: int
    vertices_despues: int
    superficie_km2: float
    recuadro: dict
    avisos: list[str] = field(default_factory=list)


def _leer(entrada: str | bytes | dict) -> Any:
    if isinstance(entrada, dict):
        return entrada
    if isinstance(entrada, (bytes, bytearray)):
        if len(entrada) > MAX_ENTRADA:
            raise ContornoInvalido("El archivo pesa más de 5 MB. Simplificalo en QGIS antes de subirlo "
                                   f"(Vectorial → Geometría → Simplificar). {COMO_ARMAR}", "tamano")
        try:
            entrada = bytes(entrada).decode("utf-8-sig")
        except UnicodeDecodeError:
            entrada = None
    if entrada is not None and len(entrada) > MAX_ENTRADA:
        raise ContornoInvalido("El archivo pesa más de 5 MB. Simplificalo en QGIS antes de subirlo "
                               f"(Vectorial → Geometría → Simplificar). {COMO_ARMAR}", "tamano")
    try:
        if entrada is None or entrada.lstrip().startswith("<"):
            raise ValueError
        return json.loads(entrada)
    except ValueError:
        raise ContornoInvalido("El archivo no es GeoJSON válido. Si tenés un shapefile, un KML u otro formato, "
                               f"abrilo en QGIS y exportalo como GeoJSON. {COMO_ARMAR}", "formato") from None


def _poligonos(obj: Any) -> list[list]:
    """Las coordenadas de cada polígono del objeto GeoJSON (lista de anillos)."""
    if not isinstance(obj, dict) or "type" not in obj:
        raise ContornoInvalido(f"El archivo no es GeoJSON válido. {COMO_ARMAR}", "formato")
    tipo = obj["type"]
    if tipo == "FeatureCollection":
        geoms = [f.get("geometry") for f in obj.get("features") or [] if isinstance(f, dict)]
    elif tipo == "Feature":
        geoms = [obj.get("geometry")]
    elif tipo == "GeometryCollection":
        geoms = list(obj.get("geometries") or [])
    else:
        geoms = [obj]
    geoms = [g for g in geoms if g]
    if not geoms:
        raise ContornoInvalido("El archivo no trae ninguna figura: hace falta el polígono del municipio. "
                               f"{COMO_ARMAR}", "tipo")
    polis: list[list] = []
    for g in geoms:
        t = g.get("type") if isinstance(g, dict) else None
        if t == "Polygon":
            polis.append(g.get("coordinates") or [])
        elif t == "MultiPolygon":
            polis.extend(g.get("coordinates") or [])
        else:
            raise ContornoInvalido(f"El archivo trae una figura de tipo {t or 'desconocido'}: hace falta un "
                                   f"polígono cerrado (Polygon o MultiPolygon). {COMO_ARMAR}", "tipo")
    return polis


def _anillo(crudo: Any) -> list[tuple[float, float]]:
    if not isinstance(crudo, list):
        raise ContornoInvalido(f"El archivo no es GeoJSON válido. {COMO_ARMAR}", "formato")
    puntos: list[tuple[float, float]] = []
    for c in crudo:
        if (not isinstance(c, (list, tuple)) or len(c) < 2
                or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in c[:2])):
            raise ContornoInvalido(f"El archivo tiene coordenadas que no son números. {COMO_ARMAR}", "formato")
        p = (float(c[0]), float(c[1]))          # sin la tercera coordenada (altura)
        if not puntos or puntos[-1] != p:
            puntos.append(p)
    if puntos and puntos[0] != puntos[-1]:
        puntos.append(puntos[0])
    return puntos


def _dentro(rec: dict, x0: float, y0: float, x1: float, y1: float) -> bool:
    return rec["oeste"] <= x0 and x1 <= rec["este"] and rec["sur"] <= y0 and y1 <= rec["norte"]


def _revisar_coordenadas(anillos: list[list[tuple[float, float]]], codigo_pais: str) -> None:
    xs = [p[0] for a in anillos for p in a]
    ys = [p[1] for a in anillos for p in a]
    if max(map(abs, xs)) > 180 or max(map(abs, ys)) > 90:
        raise ContornoInvalido("El archivo está en metros, no en latitud/longitud. Exportalo de nuevo eligiendo "
                               f"el sistema EPSG:4326 — WGS 84. {COMO_ARMAR}", "metros")
    pais = ENCUADRE_PAIS.get(codigo_pais, ENCUADRE_PAIS["AR"])
    if _dentro(pais, min(xs), min(ys), max(xs), max(ys)):
        return
    if _dentro(pais, min(ys), min(xs), max(ys), max(xs)):
        raise ContornoInvalido("La latitud y la longitud del archivo están invertidas (cada punto tiene que ir "
                               f"como [longitud, latitud]). Exportalo de nuevo desde QGIS. {COMO_ARMAR}", "invertido")
    raise ContornoInvalido("El contorno cae fuera del país del municipio. Revisá que sea el archivo correcto. "
                           f"{COMO_ARMAR}", "pais")


def _redondear(anillo) -> list[list[float]]:
    puntos: list[list[float]] = []
    for x, y in anillo.coords:
        p = [round(x, DECIMALES), round(y, DECIMALES)]
        if not puntos or puntos[-1] != p:
            puntos.append(p)
    return puntos


def normalizar_contorno(entrada: str | bytes | dict, *, codigo_pais: str = "AR") -> ContornoNormalizado:
    polis = _poligonos(_leer(entrada))
    vertices_antes = sum(len(a) for p in polis for a in p if isinstance(a, list))
    anillos_por_poli = [[_anillo(a) for a in p] for p in polis]
    _revisar_coordenadas([a for p in anillos_por_poli for a in p if a], codigo_pais)

    avisos: list[str] = []
    partes: list[Polygon] = []
    for anillos in anillos_por_poli:
        if not anillos or len(anillos[0]) < 4:
            raise ContornoInvalido("Hay un polígono con menos de 3 puntos distintos: tiene que cerrar sobre el "
                                   f"primero. {COMO_ARMAR}", "tipo")
        poli = Polygon(anillos[0], [a for a in anillos[1:] if len(a) >= 4])
        if not poli.is_valid:
            arreglado = make_valid(poli)
            geoms = getattr(arreglado, "geoms", [arreglado])
            reparadas = [g for g in geoms if isinstance(g, Polygon) and not g.is_empty]
            for g in geoms:
                if isinstance(g, MultiPolygon):
                    reparadas.extend(g.geoms)
            if not reparadas:
                raise ContornoInvalido("El polígono se corta a sí mismo y no se pudo reparar. Revisalo en QGIS "
                                       f"(Vectorial → Herramientas de geometría → Corregir geometrías). {COMO_ARMAR}",
                                       "tipo")
            avisos.append("El polígono se cortaba a sí mismo: se reparó.")
        else:
            reparadas = [poli]
        for parte in reparadas:
            simple = parte.simplify(TOLERANCIA_GRADOS, preserve_topology=False)
            if simple.is_empty or simple.area == 0:
                avisos.append("Se descartó una parte muy chica (de pocos metros), que no tiene superficie a esta escala.")
                continue
            if not isinstance(simple, Polygon) or not simple.is_valid:
                simple = parte.simplify(TOLERANCIA_GRADOS, preserve_topology=True)
            partes.append(orient(simple, 1.0))
    if not partes:
        raise ContornoInvalido(f"El contorno es demasiado chico: no queda ninguna superficie. {COMO_ARMAR}", "tipo")

    coords = []
    for p in partes:
        exterior = _redondear(p.exterior)
        if len(exterior) < 4:
            continue
        coords.append([exterior] + [h for h in (_redondear(i) for i in p.interiors) if len(h) >= 4])
    geometria = ({"type": "Polygon", "coordinates": coords[0]} if len(coords) == 1
                 else {"type": "MultiPolygon", "coordinates": coords})
    if len(json.dumps(geometria, separators=(",", ":"))) > MAX_GUARDADO:
        raise ContornoInvalido("El contorno sigue siendo demasiado detallado después de simplificarlo. Simplificalo "
                               f"en QGIS (Vectorial → Geometría → Simplificar). {COMO_ARMAR}", "tamano")

    xs = [c[0] for p in coords for a in p for c in a]
    ys = [c[1] for p in coords for a in p for c in a]
    lat_media = (min(ys) + max(ys)) / 2
    km_por_grado = 111.32
    superficie = sum(p.area for p in partes) * km_por_grado ** 2 * math.cos(math.radians(lat_media))
    return ContornoNormalizado(
        geometria=geometria,
        partes=len(coords),
        vertices_antes=vertices_antes,
        vertices_despues=sum(len(a) for p in coords for a in p),
        superficie_km2=round(superficie, 1),
        recuadro={"sur": min(ys), "oeste": min(xs), "norte": max(ys), "este": max(xs)},
        avisos=avisos,
    )


def zona_desde_contorno(c: ContornoNormalizado) -> dict[str, str]:
    """Zona de búsqueda de direcciones (geo_bbox_*) derivada del contorno: centro del recuadro y radio =
    mitad del lado mayor + 0,1° de margen (direcciones de los linderos), con el tope de 5."""
    r = c.recuadro
    lat = (r["sur"] + r["norte"]) / 2
    lon = (r["oeste"] + r["este"]) / 2
    radio = min(max(r["norte"] - r["sur"], r["este"] - r["oeste"]) / 2 + MARGEN_ZONA, RADIO_MAXIMO)
    return {"geo_bbox_centro_lat": repr(round(lat, 6)), "geo_bbox_centro_lon": repr(round(lon, 6)),
            "geo_bbox_delta_grados": repr(round(radio, 6))}
