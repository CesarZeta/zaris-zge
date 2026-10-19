# -*- coding: utf-8 -*-
"""Lleva los datos geolocalizados al municipio demo "San Andres".

Contexto (2026-10-19): el municipio demo paso a ser Vicente Lopez + San Isidro
(contorno en configuracion_general.geo_limite_geojson, mig 111). Dos pasos:

A) Reclamos del generador demo (id_usuario_alta = generador.demo): se les
   vuelve a sortear la localidad con los mismos pesos y jitter del generador
   (demo_datos._ubicar), asi quedan repartidos entre los dos partidos.
B) Cualquier punto que siga FUERA del contorno, de cualquier origen (cargas a
   mano de QA, emergencias del generador viejo en el borde de la Gral. Paz):
   reclamos, emergencias, espacios y tramites con direccion georreferenciada.
   Se re-sortean dentro del municipio con una direccion sintetica coherente
   ("Calle Altura, Localidad"). Pedido de Cesar: ningun punto fuera del poligono.

Determinista (la semilla de cada fila es su capa + id): correrlo dos veces deja
el mismo resultado. No toca fecha_modificacion (reubicacion de datos demo, no
una modificacion de negocio).

Uso (desde backend/):
    $env:ENV_FILE=".env.local"; python reubicar_datos_demo.py            # dry-run
    $env:ENV_FILE=".env.local"; python reubicar_datos_demo.py --aplicar

Contra PROD: backend/.env apunta al host directo de Supabase, que solo resuelve
por IPv6; desde una red IPv4 pisar host y usuario con los del pooler (session):
    $env:ENV_FILE=".env"; $env:POSTGRES_SERVER="aws-1-us-east-1.pooler.supabase.com"
    $env:POSTGRES_USER="postgres.lshfwsscvfsklrmbvkwl"; python reubicar_datos_demo.py

Con --aplicar, antes de cada UPDATE copia las filas que cambia a
_backup_<tabla>_geo_<fecha> (regla S24). Una fila ya respaldada no se pisa:
el backup conserva siempre el valor ORIGINAL aunque el script corra dos veces.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from collections import Counter
from datetime import date

from sqlalchemy import text

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.services import demo_datos
from app.services.geo_limite import punto_en_limite

for _s in (sys.stdout, sys.stderr):
    _s.reconfigure(encoding="utf-8", errors="replace")

LOTE = 400
SUFIJO = f"{date.today():%Y_%m_%d}"


def _direccion_conservando_calle(vieja: str | None, localidad: str) -> str:
    # El generador arma "Calle Altura, Localidad": se conserva calle y altura.
    base = (vieja or "").rsplit(", ", 1)[0].strip() or "Sin calle"
    return f"{base}, {localidad}"


def _sortear(cat, semilla: str) -> tuple[int, str, float, float, random.Random]:
    rnd = random.Random(semilla)
    id_loc, loc_nombre, lat0, lon0, radio = demo_datos._elegir_localidad(rnd, cat)
    lat, lon = demo_datos._ubicar(rnd, cat, lat0, lon0, radio)
    return id_loc, loc_nombre, lat, lon, rnd


def _direccion_sintetica(rnd: random.Random, localidad: str) -> str:
    return f"{rnd.choice(demo_datos.CALLES)} {rnd.randint(100, 5900)}, {localidad}"


async def _respaldar(db, tabla: str, pk: str, columnas: str, ids: list[int]) -> None:
    if not ids:
        return
    backup = f"_backup_{tabla}_geo_{SUFIJO}"
    await db.execute(text(
        f"CREATE TABLE IF NOT EXISTS {backup} AS SELECT {pk}, {columnas} FROM {tabla} WHERE FALSE"
    ))
    # Tabla nueva sin politicas = deny-all para la API publica de Supabase (S21).
    await db.execute(text(f"ALTER TABLE {backup} ENABLE ROW LEVEL SECURITY"))
    await db.execute(text(f"""
        INSERT INTO {backup} SELECT {pk}, {columnas} FROM {tabla}
         WHERE {pk} = ANY(:ids) AND {pk} NOT IN (SELECT {pk} FROM {backup})
    """), {"ids": ids})


async def _update_lotes(db, sql_tpl: str, columnas: list[tuple[str, str]], filas: list[dict]) -> None:
    """UPDATE ... FROM (VALUES ...) con CAST por columna (asyncpg tipa los params)."""
    for i in range(0, len(filas), LOTE):
        lote = filas[i:i + LOTE]
        valores = ", ".join(
            "(" + ", ".join(f"CAST(:{c}{j} AS {t})" for c, t in columnas) + ")"
            for j in range(len(lote))
        )
        params = {f"{c}{j}": f[c] for j, f in enumerate(lote) for c, _ in columnas}
        await db.execute(text(sql_tpl.format(valores=valores)), params)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true", help="sin esto es dry-run")
    args = parser.parse_args()

    # Que quede a la vista contra QUÉ base corre (local vs prod).
    print(f"Base: {settings.POSTGRES_USER}@{settings.POSTGRES_SERVER}/{settings.POSTGRES_DB}"
          + (" (DATABASE_URL)" if settings.DATABASE_URL else ""))

    async with AsyncSessionLocal() as db:
        cat = await demo_datos._cargar_catalogos(db)
        if cat.limite is None:
            raise SystemExit("Falta geo_limite_geojson (mig 111): no hay contorno contra el cual reubicar.")
        if not cat.poblacion_localidades:
            raise SystemExit("Ninguna localidad de referencia resolvio contra la tabla localidades.")
        limite = cat.limite
        uid_gen = await demo_datos._usuario_generador(db, crear=False)

        def afuera(lat, lon) -> bool:
            return lat is None or lon is None or not punto_en_limite(limite, float(lat), float(lon))

        # ---------------- Reclamos (paso A + paso B) ----------------
        filas = (await db.execute(text("""
            SELECT id_reclamo, direccion, descripcion, latitud, longitud, id_usuario_alta
              FROM reclamos WHERE latitud IS NOT NULL ORDER BY id_reclamo
        """))).fetchall()
        reclamos, por_loc = [], Counter()
        n_gen = n_fuera = 0
        for f in filas:
            es_gen = uid_gen is not None and f.id_usuario_alta == uid_gen
            if not es_gen and not afuera(f.latitud, f.longitud):
                continue
            id_loc, loc, lat, lon, rnd = _sortear(cat, f"san-andres-{f.id_reclamo}")
            if es_gen:
                n_gen += 1
                nueva = _direccion_conservando_calle(f.direccion, loc)
            else:
                n_fuera += 1
                nueva = _direccion_sintetica(rnd, loc)
            desc = f.descripcion.replace(f.direccion, nueva) if (f.descripcion and f.direccion) else f.descripcion
            reclamos.append({"id": f.id_reclamo, "lat": lat, "lon": lon, "loc": id_loc,
                             "dir": nueva, "descr": desc})
            por_loc[loc] += 1

        # ---------------- Emergencias (paso B) ----------------
        filas = (await db.execute(text("""
            SELECT id_emergencia_evento AS id, latitud, longitud
              FROM emergencia_evento WHERE latitud IS NOT NULL ORDER BY 1
        """))).fetchall()
        emergencias = []
        for f in filas:
            if not afuera(f.latitud, f.longitud):
                continue
            _id_loc, loc, lat, lon, rnd = _sortear(cat, f"san-andres-emergencia-{f.id}")
            emergencias.append({"id": f.id, "lat": lat, "lon": lon, "dir": _direccion_sintetica(rnd, loc)})

        # ---------------- Espacios (paso B) ----------------
        filas = (await db.execute(text("""
            SELECT id_espacio AS id, latitud, longitud, direccion
              FROM espacios_agenda WHERE latitud IS NOT NULL ORDER BY 1
        """))).fetchall()
        espacios = []
        for f in filas:
            if not afuera(f.latitud, f.longitud):
                continue
            _id_loc, loc, lat, lon, rnd = _sortear(cat, f"san-andres-espacio-{f.id}")
            espacios.append({"id": f.id, "lat": lat, "lon": lon, "dir": _direccion_sintetica(rnd, loc)})

        # ---------------- Tramites (paso B): campos tipo 'direccion' {texto,lat,lon} ----
        filas = (await db.execute(text("""
            SELECT t.id_tramite AS id, tc.nombre_interno AS campo,
                   t.datos_jsonb -> tc.nombre_interno AS dir
              FROM tramite t
              JOIN tipo_tramite_campo tc ON tc.id_tipo_tramite_version = t.id_tipo_tramite_version
                                        AND tc.tipo_dato = 'direccion'
             WHERE jsonb_typeof(t.datos_jsonb -> tc.nombre_interno) = 'object'
               AND jsonb_typeof(t.datos_jsonb -> tc.nombre_interno -> 'lat') = 'number'
               AND jsonb_typeof(t.datos_jsonb -> tc.nombre_interno -> 'lon') = 'number'
             ORDER BY 1, 2
        """))).fetchall()
        tramites = []
        for f in filas:
            d = f.dir if isinstance(f.dir, dict) else json.loads(f.dir)
            if not afuera(d.get("lat"), d.get("lon")):
                continue
            _id_loc, loc, lat, lon, rnd = _sortear(cat, f"san-andres-tramite-{f.id}-{f.campo}")
            tramites.append({"id": f.id, "campo": f.campo,
                             "valor": json.dumps({**d, "texto": _direccion_sintetica(rnd, loc),
                                                  "lat": lat, "lon": lon}, ensure_ascii=False)})

        print(f"Reclamos del generador a re-sortear (paso A): {n_gen}")
        print(f"Reclamos de otro origen fuera del municipio (paso B): {n_fuera}")
        print(f"Emergencias fuera del municipio: {len(emergencias)}")
        print(f"Espacios fuera del municipio: {len(espacios)}")
        print(f"Campos de direccion de tramites fuera del municipio: {len(tramites)}")
        print("Reclamos por localidad destino:")
        for loc, n in por_loc.most_common():
            print(f"  {loc:20s} {n:5d}")
        fuera_final = sum(afuera(x["lat"], x["lon"]) for x in reclamos + emergencias + espacios) \
            + sum(afuera(json.loads(t["valor"])["lat"], json.loads(t["valor"])["lon"]) for t in tramites)
        print(f"Puntos nuevos que quedarian fuera del contorno: {fuera_final}")

        if not args.aplicar:
            print("\nDry-run: no se escribio nada. Repetir con --aplicar.")
            return

        await _respaldar(db, "reclamos", "id_reclamo",
                         "latitud, longitud, id_localidad, direccion, descripcion",
                         [r["id"] for r in reclamos])
        await _update_lotes(db, """
            UPDATE reclamos r
               SET latitud = v.lat, longitud = v.lon, id_localidad = v.loc,
                   direccion = v.dir, descripcion = v.descr
              FROM (VALUES {valores}) AS v(id, lat, lon, loc, dir, descr)
             WHERE r.id_reclamo = v.id
        """, [("id", "integer"), ("lat", "numeric"), ("lon", "numeric"), ("loc", "integer"),
              ("dir", "text"), ("descr", "text")], reclamos)

        await _respaldar(db, "emergencia_evento", "id_emergencia_evento",
                         "latitud, longitud, direccion_evento", [e["id"] for e in emergencias])
        await _update_lotes(db, """
            UPDATE emergencia_evento e
               SET latitud = v.lat, longitud = v.lon, direccion_evento = v.dir
              FROM (VALUES {valores}) AS v(id, lat, lon, dir)
             WHERE e.id_emergencia_evento = v.id
        """, [("id", "integer"), ("lat", "numeric"), ("lon", "numeric"), ("dir", "text")], emergencias)

        await _respaldar(db, "espacios_agenda", "id_espacio",
                         "latitud, longitud, direccion", [e["id"] for e in espacios])
        await _update_lotes(db, """
            UPDATE espacios_agenda e
               SET latitud = v.lat, longitud = v.lon, direccion = v.dir
              FROM (VALUES {valores}) AS v(id, lat, lon, dir)
             WHERE e.id_espacio = v.id
        """, [("id", "integer"), ("lat", "numeric"), ("lon", "numeric"), ("dir", "text")], espacios)

        await _respaldar(db, "tramite", "id_tramite", "datos_jsonb", [t["id"] for t in tramites])
        for t in tramites:
            await db.execute(text("""
                UPDATE tramite SET datos_jsonb = jsonb_set(datos_jsonb, ARRAY[:campo], CAST(:valor AS jsonb))
                 WHERE id_tramite = :id
            """), t)

        await db.commit()
        print(f"\nAplicado. Respaldos en _backup_<tabla>_geo_{SUFIJO}.")


if __name__ == "__main__":
    asyncio.run(main())
