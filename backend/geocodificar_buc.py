"""
geocodificar_buc.py — Llena latitud/longitud en ciudadanos y empresas activos
que tengan calle pero NO lat/lon, llamando a Nominatim (OSM) directamente.

Respeta el rate-limit de Nominatim (1 req/s + margen). Idempotente: solo
toca filas con `latitud IS NULL`. Soft-errors no abortan el lote.

Uso:
    cd backend

    # Dry-run local
    $env:ENV_FILE=".env.local"; python -u geocodificar_buc.py --dry-run

    # Prod (CUIDADO):
    $env:DATABASE_URL="postgresql+asyncpg://postgres:<pwd>@db.lshfwsscvfsklrmbvkwl.supabase.co:5432/postgres"
    python -u geocodificar_buc.py --dry-run --confirm-prod          # preview
    python -u geocodificar_buc.py --confirm-prod                    # aplicar
    python -u geocodificar_buc.py --confirm-prod --tabla empresas   # solo empresas
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from typing import Optional

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
NOMINATIM_UA = "ZARIS-API/1.0 (cesar@zaris.dev)"
NOMINATIM_TIMEOUT = 10.0
NOMINATIM_MIN_INTERVAL = 1.05

_LAST_CALL = 0.0


async def _nominatim_buscar(client: httpx.AsyncClient, q: str) -> Optional[dict]:
    global _LAST_CALL
    delta = time.monotonic() - _LAST_CALL
    if delta < NOMINATIM_MIN_INTERVAL:
        await asyncio.sleep(NOMINATIM_MIN_INTERVAL - delta)
    try:
        r = await client.get(
            f"{NOMINATIM_BASE}/search",
            params={"q": q, "format": "json", "limit": "1",
                    "countrycodes": "ar", "addressdetails": "1"},
            headers={"User-Agent": NOMINATIM_UA, "Accept-Language": "es"},
            timeout=NOMINATIM_TIMEOUT,
        )
    finally:
        _LAST_CALL = time.monotonic()
    if r.status_code != 200:
        return None
    data = r.json()
    return data[0] if isinstance(data, list) and data else None


def _armar_query(calle: str, localidad: Optional[str], provincia: Optional[str]) -> str:
    return ", ".join(p for p in [calle, localidad, provincia] if p)


async def _procesar_tabla(conn, client, tabla: str, pk: str, limite: int, dry_run: bool) -> dict:
    rows = (await conn.execute(text(f"""
        SELECT {pk}, calle, localidad, provincia
          FROM {tabla}
         WHERE activo = TRUE
           AND latitud IS NULL
           AND calle IS NOT NULL AND TRIM(calle) <> ''
         ORDER BY {pk}
         LIMIT :lim
    """), {"lim": limite})).fetchall()

    print(f"\n[{tabla}] {len(rows)} candidatos a geocodificar")
    if not rows:
        return {"tabla": tabla, "intentados": 0, "ok": 0, "sin_resultado": 0, "errores": 0}

    ok = sin_resultado = errores = 0
    for i, row in enumerate(rows, 1):
        pk_val = getattr(row, pk)
        q = _armar_query(row.calle, row.localidad, row.provincia)
        prefix = f"  [{i:>4}/{len(rows)}] {tabla}.{pk}={pk_val}"
        try:
            res = await _nominatim_buscar(client, q)
        except Exception as e:
            errores += 1
            print(f"{prefix} ERROR Nominatim: {e}")
            continue
        if not res or not res.get("lat") or not res.get("lon"):
            sin_resultado += 1
            if i <= 20 or i % 50 == 0:
                print(f"{prefix} MISS para '{q[:70]}'")
            continue
        lat, lon = float(res["lat"]), float(res["lon"])
        if dry_run:
            ok += 1
            if i <= 20 or i % 50 == 0:
                print(f"{prefix} OK dry -> {lat:.6f}, {lon:.6f}")
            continue
        try:
            await conn.execute(text(f"""
                UPDATE {tabla} SET latitud=:la, longitud=:lo, fecha_modificacion=NOW()
                 WHERE {pk}=:pk
            """), {"la": lat, "lo": lon, "pk": pk_val})
            ok += 1
            if i % 25 == 0:
                await conn.commit()
                print(f"{prefix} OK -> {lat:.6f}, {lon:.6f}  (commit batch)")
        except Exception as e:
            errores += 1
            print(f"{prefix} ERROR UPDATE: {e}")

    if not dry_run:
        await conn.commit()
    return {"tabla": tabla, "intentados": len(rows), "ok": ok,
            "sin_resultado": sin_resultado, "errores": errores}


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limite", type=int, default=1000)
    p.add_argument("--tabla", choices=["ciudadanos", "empresas", "ambas"], default="ambas")
    p.add_argument("--confirm-prod", action="store_true")
    args = p.parse_args()

    db_url = os.environ.get("DATABASE_URL",
                            "postgresql+asyncpg://postgres:145236@127.0.0.1:5432/zaris_dev")
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if "supabase.co" in db_url and not args.confirm_prod:
        print("ERROR: prod sin --confirm-prod")
        sys.exit(2)

    print(f"DB: {db_url.split('@')[1] if '@' in db_url else db_url}")
    print(f"Modo: {'DRY-RUN' if args.dry_run else 'LIVE'} | tabla(s): {args.tabla} | limite: {args.limite}")

    engine = create_async_engine(db_url, echo=False)
    resultados = []
    async with httpx.AsyncClient() as client:
        async with engine.connect() as conn:
            tablas = []
            if args.tabla in ("ciudadanos", "ambas"):
                tablas.append(("ciudadanos", "id_ciudadano"))
            if args.tabla in ("empresas", "ambas"):
                tablas.append(("empresas", "id_empresa"))
            for tabla, pk in tablas:
                r = await _procesar_tabla(conn, client, tabla, pk, args.limite, args.dry_run)
                resultados.append(r)
    await engine.dispose()

    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    for r in resultados:
        total = r["intentados"]
        if total == 0:
            print(f"  {r['tabla']}: nada para procesar")
            continue
        pct = r["ok"] / total * 100
        print(f"  {r['tabla']}: {r['ok']}/{total} OK ({pct:.1f}%) | MISS: {r['sin_resultado']} | ERR: {r['errores']}")
    if args.dry_run:
        print("\n  (dry-run: nada fue escrito. Re-correr sin --dry-run.)")


if __name__ == "__main__":
    asyncio.run(main())
