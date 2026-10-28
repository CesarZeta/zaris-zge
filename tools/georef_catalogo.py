"""Catálogo de gobiernos locales desde Georef (datos.gob.ar) — PLAN_CONTORNO_MUNICIPIO.md, tarea 1.

    python tools/georef_catalogo.py descargar      # baja la instantánea a backend/data/
    python tools/georef_catalogo.py generar-sql    # escribe backend/migrations/132b_...sql
    python tools/georef_catalogo.py informe --filas filas.json
        # filas.json = [{"provincia": "...", "nombre": "..."}] de la tabla partidos de una base:
        # lista las que quedarían sin casar (para completar el archivo de alias)

La instantánea y el archivo de alias se versionan: la migración sale siempre de ellos, nunca de
Georef en vivo, así local y prod quedan iguales.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FECHA = "2026-10-28"
INSTANTANEA = RAIZ / "backend" / "data" / f"georef_gobiernos_locales_{FECHA}.json"
ALIAS = RAIZ / "backend" / "data" / "alias_catalogo_geo.json"
MIGRACION = RAIZ / "backend" / "migrations" / "132b_catalogo_gobiernos_locales_datos.sql"
API = "https://apis.datos.gob.ar/georef/api"

# Normalización de nombres: la MISMA en Python y en SQL (sin la extensión unaccent).
_DE = "ÁÉÍÓÚÜÑáéíóúüñÀÈÌÒÙàèìòùÂÊÎÔÛâêîôûÇç"
_A = "AEIOUUNaeiouunAEIOUaeiouAEIOUaeiouCc"
_TABLA = str.maketrans(_DE, _A)


def norm(s: str) -> str:
    return " ".join(s.strip().translate(_TABLA).lower().split())


def norm_sql(col: str) -> str:
    return f"regexp_replace(lower(translate(btrim({col}), '{_DE}', '{_A}')), '\\s+', ' ', 'g')"


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.load(r)


def descargar() -> None:
    prov = _get(f"{API}/provincias?campos=id,nombre&max=30")["provincias"]
    mun = _get(f"{API}/municipios?max=5000&campos=id,nombre,nombre_completo,categoria,provincia.id")["municipios"]
    datos = {
        "fecha": FECHA,
        "fuente": f"{API}/municipios y /provincias (descargado {date.today().isoformat()})",
        "provincias": sorted(({"codigo": p["id"], "nombre": p["nombre"]} for p in prov), key=lambda x: x["codigo"]),
        "municipios": sorted(({"codigo": m["id"], "nombre": m["nombre"], "nombre_completo": m["nombre_completo"],
                               "categoria": m["categoria"], "provincia": m["provincia"]["id"]} for m in mun),
                             key=lambda x: x["codigo"]),
    }
    INSTANTANEA.parent.mkdir(parents=True, exist_ok=True)
    INSTANTANEA.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(datos['provincias'])} provincias, {len(datos['municipios'])} gobiernos locales → {INSTANTANEA}")


def _cargar() -> tuple[dict, dict]:
    datos = json.loads(INSTANTANEA.read_text(encoding="utf-8"))
    alias = json.loads(ALIAS.read_text(encoding="utf-8")) if ALIAS.exists() else {"provincias": [], "partidos": []}
    return datos, alias


def _nombres_finales(municipios: list[dict]) -> list[dict]:
    """Nombre que lleva cada gobierno local en `partidos`: el suyo; si se repite en la provincia, el
    nombre completo; si aun así se repite, con el código. Falla si queda alguna repetición."""
    rep = Counter((m["provincia"], norm(m["nombre"])) for m in municipios)
    salida = []
    for m in municipios:
        nombre = m["nombre"] if rep[(m["provincia"], norm(m["nombre"]))] == 1 else m["nombre_completo"]
        salida.append({**m, "nombre_final": nombre})
    rep2 = Counter((m["provincia"], norm(m["nombre_final"])) for m in salida)
    for m in salida:
        if rep2[(m["provincia"], norm(m["nombre_final"]))] > 1:
            m["nombre_final"] = f"{m['nombre_final']} ({m['codigo']})"
    rep3 = Counter((m["provincia"], norm(m["nombre_final"])) for m in salida)
    malos = [k for k, v in rep3.items() if v > 1]
    if malos:
        sys.exit(f"Nombres repetidos sin resolver: {malos}")
    largos = [m["codigo"] for m in salida if len(m["nombre_final"]) > 150 or len(m["nombre_completo"]) > 200]
    if largos:
        sys.exit(f"Nombres más largos que las columnas: {largos}")
    return salida


def _jsonb(nombre: str, valor) -> str:
    texto = json.dumps(valor, ensure_ascii=False, separators=(",", ":"))
    if "$j$" in texto:
        sys.exit("el JSON contiene el delimitador $j$")
    return f"  {nombre} jsonb := $j${texto}$j$;"


def generar_sql() -> None:
    datos, alias = _cargar()
    gl = [{k: m[k] for k in ("codigo", "provincia", "nombre", "nombre_completo", "categoria", "nombre_final")}
          for m in _nombres_finales(datos["municipios"])]
    n_pa, n_g = norm_sql("pa.nombre"), norm_sql("g.nombre")
    sql = f"""-- Migración 132b — catálogo de gobiernos locales (solo datos). GENERADA por
-- tools/georef_catalogo.py desde backend/data/{INSTANTANEA.name} y {ALIAS.name}: no editar a mano.
-- Diseño: PLAN_CONTORNO_MUNICIPIO_DISENO.md §4.2. Requiere la 132 (columnas codigo_georef, categoria,
-- nombre_completo). Un solo bloque: si algo falla, no queda nada a medias. Re-aplicable.
DO $mig$
DECLARE
{_jsonb("v_prov", datos["provincias"])}
{_jsonb("v_gl", gl)}
{_jsonb("v_alias_prov", alias.get("provincias", []))}
{_jsonb("v_alias_part", alias.get("partidos", []))}
  v_n integer;
  v_lista text;
BEGIN
  -- 1. Provincias: por nombre normalizado y, si no, por alias.
  UPDATE provincias p SET codigo_georef = x.codigo
    FROM jsonb_to_recordset(v_prov) AS x(codigo text, nombre text)
   WHERE p.codigo_pais = 'AR' AND p.codigo_georef IS NULL
     AND {norm_sql("p.nombre")} = {norm_sql("x.nombre")}
     AND NOT EXISTS (SELECT 1 FROM provincias o WHERE o.codigo_georef = x.codigo);
  UPDATE provincias p SET codigo_georef = a.codigo
    FROM jsonb_to_recordset(v_alias_prov) AS a(nombre text, codigo text)
   WHERE p.codigo_pais = 'AR' AND p.codigo_georef IS NULL
     AND {norm_sql("p.nombre")} = {norm_sql("a.nombre")}
     AND NOT EXISTS (SELECT 1 FROM provincias o WHERE o.codigo_georef = a.codigo);
  SELECT string_agg(x.nombre, ', ') INTO v_lista
    FROM jsonb_to_recordset(v_prov) AS x(codigo text, nombre text)
   WHERE NOT EXISTS (SELECT 1 FROM provincias p WHERE p.codigo_georef = x.codigo);
  IF v_lista IS NOT NULL THEN
    RAISE EXCEPTION 'Provincias de Georef sin fila en provincias: %', v_lista;
  END IF;

  -- 2. Partidos existentes por (provincia, nombre normalizado), solo si el nombre es único de los
  --    dos lados.
  WITH g AS (
    SELECT x.*, pr.id_provincia, {norm_sql("x.nombre")} AS n,
           count(*) OVER (PARTITION BY x.provincia, {norm_sql("x.nombre")}) AS rep
      FROM jsonb_to_recordset(v_gl) AS x(codigo text, provincia text, nombre text, nombre_completo text,
                                         categoria text, nombre_final text)
      JOIN provincias pr ON pr.codigo_georef = x.provincia
  ), viejos AS (
    SELECT pa.id_partido, pa.id_provincia, {n_pa} AS n,
           count(*) OVER (PARTITION BY pa.id_provincia, {n_pa}) AS rep
      FROM partidos pa WHERE pa.codigo_georef IS NULL
  )
  UPDATE partidos pa SET codigo_georef = g.codigo, categoria = g.categoria, nombre_completo = g.nombre_completo
    FROM viejos v JOIN g ON g.id_provincia = v.id_provincia AND g.n = v.n
   WHERE pa.id_partido = v.id_partido AND v.rep = 1 AND g.rep = 1
     AND NOT EXISTS (SELECT 1 FROM partidos o WHERE o.codigo_georef = g.codigo);
  GET DIAGNOSTICS v_n = ROW_COUNT;
  RAISE NOTICE 'casados por nombre: %', v_n;

  -- 3. Alias: el mismo lugar con otro nombre (nombre viejo → código), dentro de la provincia del código.
  WITH g AS (
    SELECT x.codigo, x.categoria, x.nombre_completo, pr.id_provincia
      FROM jsonb_to_recordset(v_gl) AS x(codigo text, provincia text, nombre text, nombre_completo text,
                                         categoria text, nombre_final text)
      JOIN provincias pr ON pr.codigo_georef = x.provincia
  )
  UPDATE partidos pa SET codigo_georef = g.codigo, categoria = g.categoria, nombre_completo = g.nombre_completo
    FROM jsonb_to_recordset(v_alias_part) AS a(nombre text, codigo text) JOIN g ON g.codigo = a.codigo
   WHERE pa.codigo_georef IS NULL AND pa.id_provincia = g.id_provincia
     AND {n_pa} = {norm_sql("a.nombre")}
     AND NOT EXISTS (SELECT 1 FROM partidos o WHERE o.codigo_georef = g.codigo);
  GET DIAGNOSTICS v_n = ROW_COUNT;
  RAISE NOTICE 'casados por alias: %', v_n;

  -- 4. Datos oficiales al día en las filas que ya tienen código (re-aplicar actualiza).
  UPDATE partidos pa SET categoria = x.categoria, nombre_completo = x.nombre_completo
    FROM jsonb_to_recordset(v_gl) AS x(codigo text, provincia text, nombre text, nombre_completo text,
                                       categoria text, nombre_final text)
   WHERE pa.codigo_georef = x.codigo
     AND (pa.categoria IS DISTINCT FROM x.categoria OR pa.nombre_completo IS DISTINCT FROM x.nombre_completo);

  -- 5. Alta del resto. Antes, ningún nombre nuevo puede chocar con uno que ya está en la provincia.
  SELECT string_agg(x.nombre_final || ' (' || x.codigo || ')', ', ') INTO v_lista
    FROM jsonb_to_recordset(v_gl) AS x(codigo text, provincia text, nombre text, nombre_completo text,
                                       categoria text, nombre_final text)
    JOIN provincias pr ON pr.codigo_georef = x.provincia
   WHERE NOT EXISTS (SELECT 1 FROM partidos o WHERE o.codigo_georef = x.codigo)
     AND EXISTS (SELECT 1 FROM partidos o WHERE o.id_provincia = pr.id_provincia AND o.nombre = x.nombre_final);
  IF v_lista IS NOT NULL THEN
    RAISE EXCEPTION 'Nombres nuevos que chocan con una fila existente (agregar alias): %', v_lista;
  END IF;
  INSERT INTO partidos (id_provincia, nombre, codigo_georef, categoria, nombre_completo, activo)
  SELECT pr.id_provincia, x.nombre_final, x.codigo, x.categoria, x.nombre_completo, TRUE
    FROM jsonb_to_recordset(v_gl) AS x(codigo text, provincia text, nombre text, nombre_completo text,
                                       categoria text, nombre_final text)
    JOIN provincias pr ON pr.codigo_georef = x.provincia
   WHERE NOT EXISTS (SELECT 1 FROM partidos o WHERE o.codigo_georef = x.codigo);
  GET DIAGNOSTICS v_n = ROW_COUNT;
  RAISE NOTICE 'gobiernos locales nuevos: %', v_n;

  -- 6. Localidades de filas sin código: a la fila del alias (si el alias apunta a un código que ya
  --    tenía otra fila) o al único gobierno local de la provincia con el mismo nombre que la localidad.
  WITH destino AS (
    SELECT l.id_localidad, d.id_partido AS id_nuevo
      FROM localidades l
      JOIN partidos v ON v.id_partido = l.id_partido AND v.codigo_georef IS NULL
      JOIN jsonb_to_recordset(v_alias_part) AS a(nombre text, codigo text)
        ON {norm_sql("v.nombre")} = {norm_sql("a.nombre")}
      JOIN partidos d ON d.codigo_georef = a.codigo AND d.id_provincia = v.id_provincia
  )
  UPDATE localidades l SET id_partido = d.id_nuevo FROM destino d WHERE l.id_localidad = d.id_localidad;
  GET DIAGNOSTICS v_n = ROW_COUNT;
  RAISE NOTICE 'localidades reubicadas por alias: %', v_n;
  WITH candidatos AS (
    SELECT l.id_localidad, d.id_partido AS id_nuevo,
           count(*) OVER (PARTITION BY l.id_localidad) AS rep
      FROM localidades l
      JOIN partidos v ON v.id_partido = l.id_partido AND v.codigo_georef IS NULL
      JOIN partidos d ON d.id_provincia = v.id_provincia AND d.codigo_georef IS NOT NULL
                     AND {norm_sql("d.nombre")} = {norm_sql("l.nombre")}
  )
  UPDATE localidades l SET id_partido = c.id_nuevo FROM candidatos c
   WHERE l.id_localidad = c.id_localidad AND c.rep = 1;
  GET DIAGNOSTICS v_n = ROW_COUNT;
  RAISE NOTICE 'localidades reubicadas por nombre: %', v_n;

  -- 7. Baja lógica de las filas sin código, salvo las que use un municipio vigente y las de una
  --    provincia de la que Georef no lista ningún gobierno local (Santa Cruz y Santiago del Estero en
  --    2026-10): ahí la fila vieja es lo único que hay para elegir.
  UPDATE partidos pa SET activo = FALSE
   WHERE pa.codigo_georef IS NULL AND pa.activo
     AND NOT EXISTS (SELECT 1 FROM municipios m WHERE m.id_partido = pa.id_partido AND m.estado <> 'baja')
     AND EXISTS (SELECT 1 FROM partidos o WHERE o.id_provincia = pa.id_provincia AND o.codigo_georef IS NOT NULL);
  GET DIAGNOSTICS v_n = ROW_COUNT;
  RAISE NOTICE 'filas viejas dadas de baja: %', v_n;
  SELECT string_agg(pa.nombre, ', ') INTO v_lista FROM partidos pa
   WHERE pa.codigo_georef IS NULL AND pa.activo;
  IF v_lista IS NOT NULL THEN
    RAISE NOTICE 'sin código y activas (municipio vigente o provincia sin datos en Georef): %', v_lista;
  END IF;
  SELECT count(*) INTO v_n FROM localidades l JOIN partidos pa ON pa.id_partido = l.id_partido
   WHERE NOT pa.activo;
  RAISE NOTICE 'localidades que quedaron en filas de baja: %', v_n;
END
$mig$;
"""
    MIGRACION.write_text(sql, encoding="utf-8", newline="\n")
    print(f"{len(gl)} gobiernos locales → {MIGRACION} ({MIGRACION.stat().st_size // 1024} KB)")


def informe(filas_path: str) -> None:
    datos, alias = _cargar()
    prov_por_nombre = {norm(p["nombre"]): p["codigo"] for p in datos["provincias"]}
    for a in alias.get("provincias", []):
        prov_por_nombre.setdefault(norm(a["nombre"]), a["codigo"])
    por_prov = Counter((m["provincia"], norm(m["nombre"])) for m in datos["municipios"])
    alias_nombres = {norm(a["nombre"]) for a in alias.get("partidos", [])}
    filas = json.loads(Path(filas_path).read_text(encoding="utf-8"))
    sin_prov = sorted({f["provincia"] for f in filas if norm(f["provincia"]) not in prov_por_nombre})
    if sin_prov:
        print("Provincias sin código (agregar alias):", sin_prov)
    sin = []
    for f in filas:
        cod = prov_por_nombre.get(norm(f["provincia"]))
        if por_prov.get((cod, norm(f["nombre"]))) == 1 or norm(f["nombre"]) in alias_nombres:
            continue
        sin.append((f["provincia"], f["nombre"], f.get("localidades", "")))
    print(f"{len(filas)} filas, {len(sin)} sin casar:")
    for p, n, loc in sorted(sin):
        print(f"  {p} | {n} | localidades: {loc}")


def main() -> None:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("descargar")
    sub.add_parser("generar-sql")
    inf = sub.add_parser("informe")
    inf.add_argument("--filas", required=True)
    a = ap.parse_args()
    {"descargar": descargar, "generar-sql": generar_sql}.get(a.cmd, lambda: informe(a.filas))()


if __name__ == "__main__":
    main()
