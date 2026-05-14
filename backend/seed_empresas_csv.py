"""
Seed de empresas demo desde Tablas Iniciales/EMPRESAS.csv.

Diseño:
- Lee N filas del CSV (default 500).
- Conserva direccion + latitud + longitud reales.
- Randomiza solo el nombre comercial (prefijos categoricos + numero correlativo).
- Genera cuit valido modulo-11 sintetico (prefijo 30 — persona juridica).
- Telefono/email sinteticos (NOT NULL en schema).
- Idempotente: dedupe por cuit. Re-correr no duplica.
- Por default apunta a local. Para prod pasar --confirm-prod (NO usar sin OK del usuario).

Uso:
    cd backend
    $env:ENV_FILE=".env.local"; python seed_empresas_csv.py --limite 500
    # prod (DESHABILITADO hasta confirmacion explicita):
    # python seed_empresas_csv.py --limite 500 --confirm-prod
"""

from __future__ import annotations
import argparse
import csv
import os
import random
import sys
from pathlib import Path

# UTF-8 encoding para Windows (CLAUDE.md §24)
os.environ["PYTHONIOENCODING"] = "utf-8"

import asyncio
import asyncpg

CSV_PATH = Path(__file__).resolve().parent.parent / "Tablas Iniciales" / "EMPRESAS.csv"

PREFIJOS_NOMBRE = [
    "Comercio", "Servicios", "Distribuidora", "Almacén", "Ferretería",
    "Panadería", "Farmacia", "Kiosco", "Boutique", "Librería",
    "Carnicería", "Verdulería", "Restaurante", "Café", "Taller",
    "Estudio", "Consultora", "Importadora", "Mayorista", "Bazar",
]

# Seed determinístico — re-correr genera los mismos nombres/cuits.
RNG_SEED = 42


def _cuit_digito(prefijo: int, base: int) -> int | None:
    """Calcula digito verificador modulo-11 para prefijo+base. None si toca 10 (cuit invalido)."""
    s = f"{prefijo:02d}{base:08d}"
    pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = sum(int(s[i]) * pesos[i] for i in range(10))
    resto = suma % 11
    d = 11 - resto
    if d == 11:
        return 0
    if d == 10:
        return None
    return d


def _generar_cuits(prefijo: int, base_inicio: int, cantidad: int) -> list[str]:
    """Genera N cuits validos secuenciales, saltando bases que dan digito 10.
    Garantiza unicidad por construccion (base monotonica)."""
    cuits: list[str] = []
    base = base_inicio
    while len(cuits) < cantidad:
        d = _cuit_digito(prefijo, base)
        if d is not None:
            cuits.append(f"{prefijo:02d}{base:08d}{d}")
        base += 1
    return cuits


def _parse_direccion(direccion: str) -> tuple[str, str | None]:
    """Split en ultimo token numerico. 'ESTEBAN ECHEVERRIA 4284' -> ('ESTEBAN ECHEVERRIA', '4284')."""
    direccion = direccion.strip()
    if not direccion:
        return "", None
    partes = direccion.rsplit(" ", 1)
    if len(partes) == 2 and partes[1].isdigit():
        return partes[0].strip(), partes[1]
    return direccion, None


def _parse_decimal_ar(v: str) -> float | None:
    """Convierte '-34,5109201' (formato AR) a float."""
    v = (v or "").strip()
    if not v:
        return None
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return None


def leer_csv(path: Path, limite: int) -> list[dict]:
    """Lee N filas con lat/lon validos. utf-8-sig para BOM."""
    rows: list[dict] = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for r in reader:
            lat = _parse_decimal_ar(r.get("latitud") or "")
            lon = _parse_decimal_ar(r.get("longitud") or "")
            direccion_raw = (r.get("direccion") or "").strip()
            if lat is None or lon is None or not direccion_raw:
                continue
            calle, altura = _parse_direccion(direccion_raw)
            rows.append({
                "direccion": direccion_raw,
                "calle": calle,
                "altura": altura,
                "latitud": lat,
                "longitud": lon,
            })
            if len(rows) >= limite:
                break
    return rows


def generar_payload(rows: list[dict], actividad_ids: list[int]) -> list[dict]:
    """Compone los registros listos para INSERT con nombres/cuits deterministicos."""
    rng = random.Random(RNG_SEED)
    cuits = _generar_cuits(prefijo=30, base_inicio=10_000_000, cantidad=len(rows))
    out = []
    for i, r in enumerate(rows, start=1):
        prefijo = rng.choice(PREFIJOS_NOMBRE)
        nombre = f"{prefijo} Demo {i:04d}"
        cuit = cuits[i - 1]
        out.append({
            "nombre": nombre,
            "cuit": cuit,
            "id_actividad": rng.choice(actividad_ids),
            "calle": r["calle"][:120] if r["calle"] else None,
            "altura": r["altura"][:20] if r["altura"] else None,
            "localidad": "Vicente López",
            "provincia": "Buenos Aires",
            "latitud": r["latitud"],
            "longitud": r["longitud"],
            "telefono": f"11{rng.randint(10_000_000, 99_999_999)}",
            "email": f"empresa{i:04d}@demo.zaris.local",
            "email_chk": False,
            "observaciones": f"Seed demo {i}/{len(rows)} — direccion real del CSV, datos comerciales sinteticos.",
        })
    return out


async def aplicar(dsn: str, payload: list[dict]) -> dict:
    conn = await asyncpg.connect(dsn)
    try:
        # Ids de actividades activas
        rows = await conn.fetch("SELECT id FROM actividades WHERE activo=TRUE ORDER BY id")
        if not rows:
            raise RuntimeError("No hay actividades activas en la DB. Cargá actividades antes.")

        # Cuits existentes — para dedupe
        existing = {r["cuit"] for r in await conn.fetch("SELECT cuit FROM empresas")}

        inserted = 0
        skipped = 0
        for p in payload:
            if p["cuit"] in existing:
                skipped += 1
                continue
            await conn.execute("""
                INSERT INTO empresas (
                    nombre, cuit, id_actividad, calle, altura,
                    localidad, provincia, latitud, longitud,
                    telefono, email, email_chk,
                    observaciones, activo, fecha_alta
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7, $8, $9,
                    $10, $11, $12,
                    $13, TRUE, NOW()
                )
            """,
                p["nombre"], p["cuit"], p["id_actividad"], p["calle"], p["altura"],
                p["localidad"], p["provincia"], p["latitud"], p["longitud"],
                p["telefono"], p["email"], p["email_chk"],
                p["observaciones"],
            )
            inserted += 1
        total = await conn.fetchval("SELECT COUNT(*) FROM empresas WHERE activo=TRUE")
        return {"inserted": inserted, "skipped": skipped, "total_activas": total}
    finally:
        await conn.close()


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--limite", type=int, default=500, help="Cantidad de empresas a insertar.")
    p.add_argument("--confirm-prod", action="store_true",
                   help="Apuntar a Supabase prod (default: local zaris_dev).")
    args = p.parse_args()

    if args.confirm_prod:
        dsn = os.environ.get("DATABASE_URL_PROD")
        if not dsn:
            print("[FAIL] --confirm-prod requiere DATABASE_URL_PROD seteado.", file=sys.stderr)
            sys.exit(1)
        target = "PROD (Supabase)"
    else:
        dsn = os.environ.get("DATABASE_URL_LOCAL",
                             "postgresql://postgres:145236@127.0.0.1:5432/zaris_dev")
        target = "LOCAL (zaris_dev)"

    print(f"[INFO] Target: {target}")
    print(f"[INFO] CSV:    {CSV_PATH}")
    print(f"[INFO] Limite: {args.limite}")

    if not CSV_PATH.exists():
        print(f"[FAIL] No existe {CSV_PATH}", file=sys.stderr)
        sys.exit(1)

    rows = leer_csv(CSV_PATH, args.limite)
    print(f"[OK]  Leidas {len(rows)} filas validas del CSV.")
    if not rows:
        sys.exit(1)

    # Necesitamos actividades para el payload — un round-trip mas a la DB
    conn = await asyncpg.connect(dsn)
    try:
        actividad_ids = [r["id"] for r in await conn.fetch(
            "SELECT id FROM actividades WHERE activo=TRUE ORDER BY id")]
    finally:
        await conn.close()
    if not actividad_ids:
        print("[FAIL] No hay actividades activas en la DB. Cargá actividades antes.", file=sys.stderr)
        sys.exit(1)
    print(f"[OK]  {len(actividad_ids)} actividades activas disponibles.")

    payload = generar_payload(rows, actividad_ids)
    print(f"[OK]  Payload generado: {len(payload)} empresas.")
    print(f"      Muestra: {payload[0]['nombre']} — {payload[0]['calle']} {payload[0]['altura']} "
          f"(lat={payload[0]['latitud']}, lon={payload[0]['longitud']}) cuit={payload[0]['cuit']}")

    res = await aplicar(dsn, payload)
    print(f"[OK]  Insertadas: {res['inserted']} | Skipped (cuit duplicado): {res['skipped']} "
          f"| Total activas en DB: {res['total_activas']}")


if __name__ == "__main__":
    asyncio.run(main())
