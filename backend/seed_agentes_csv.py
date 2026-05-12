"""
seed_agentes_csv.py — Carga de agentes desde CSV.

CSV: Tablas Iniciales/agente.csv con columnas
  id_usuario;nombre;apellido;username;id_cargo;enabled;cuil

El id_cargo del CSV es legacy del sistema viejo y NO mapea 1:1 con el id_cargo
de prod. Se intenta resolver por nombre via cargo.csv; si no hay match, queda NULL.

Idempotente: dedupe por (apellido,nombre) lowercase (no hay legajo confiable).

Uso:
    cd backend
    # Local
    $env:ENV_FILE=".env.local"; python seed_agentes_csv.py
    # Prod
    $env:DATABASE_URL="postgresql+asyncpg://postgres:<pwd>@db.lshfwsscvfsklrmbvkwl.supabase.co:5432/postgres"
    python seed_agentes_csv.py --confirm-prod
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import os
import re
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

CSV_AGENTES = Path(__file__).parent.parent / "Tablas Iniciales" / "agente.csv"
CSV_CARGOS = Path(__file__).parent.parent / "Tablas Iniciales" / "cargo.csv"
ID_USUARIO_SEED = 1


def _read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig") as f:
        return [{k.strip(): (v or "").strip() for k, v in row.items()}
                for row in csv.DictReader(f, delimiter=";")]


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-prod", action="store_true")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://postgres:145236@127.0.0.1:5432/zaris_dev")
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if "supabase.co" in db_url and not args.confirm_prod:
        print("ERROR: DATABASE_URL apunta a Supabase prod. Usar --confirm-prod.")
        sys.exit(2)
    print(f"DB: {db_url.split('@')[1] if '@' in db_url else db_url}")

    rows = _read_csv(CSV_AGENTES)
    cargos_legacy = _read_csv(CSV_CARGOS)
    legacy_id_to_name = {c["id_cargo"]: c["descripcion"] for c in cargos_legacy if c.get("descripcion")}
    print(f"agente.csv: {len(rows)} filas | cargo.csv legacy: {len(legacy_id_to_name)} cargos")

    engine = create_async_engine(db_url, echo=False)
    async with engine.connect() as conn:
        # Cargos en prod: nombre -> id
        cargos_prod = (await conn.execute(text(
            "SELECT id_cargo, LOWER(TRIM(nombre)) AS k FROM cargos WHERE activo"
        ))).all()
        cargo_by_name = {k: id_ for (id_, k) in cargos_prod}
        print(f"Cargos en DB: {len(cargo_by_name)}")

        # Agentes ya existentes por (apellido,nombre) lower
        existing = (await conn.execute(text(
            "SELECT LOWER(TRIM(apellido)) || '|' || LOWER(TRIM(nombre)) AS k FROM agentes"
        ))).scalars().all()
        existing_keys = set(existing)
        print(f"Agentes existentes: {len(existing_keys)}")

        inserted = 0
        skipped_dup = 0
        skipped_invalid = 0
        no_cargo = 0

        for r in rows:
            nombre = (r.get("nombre") or "").strip()[:100]
            apellido = (r.get("apellido") or "").strip()[:100]
            if not nombre or not apellido:
                skipped_invalid += 1
                continue
            key = f"{apellido.lower()}|{nombre.lower()}"
            if key in existing_keys:
                skipped_dup += 1
                continue
            existing_keys.add(key)

            email = (r.get("username") or "").strip().lower()
            id_cargo_csv = (r.get("id_cargo") or "").strip()
            cargo_nombre = legacy_id_to_name.get(id_cargo_csv, "")
            id_cargo_prod = cargo_by_name.get(cargo_nombre.lower().strip()) if cargo_nombre else None
            if id_cargo_prod is None:
                no_cargo += 1

            cuil = re.sub(r"\D", "", r.get("cuil") or "")
            legajo = (r.get("id_usuario") or "").strip() or None  # id legacy como legajo

            try:
                await conn.execute(text("""
                    INSERT INTO agentes
                        (nombre, apellido, legajo, email, id_cargo, activo, id_municipio,
                         fecha_alta, id_usuario_alta)
                    VALUES (:n, :a, :l, :e, :c, TRUE, 1, NOW(), :uid)
                """), {
                    "n": nombre, "a": apellido, "l": legajo,
                    "e": email[:150] or None, "c": id_cargo_prod, "uid": ID_USUARIO_SEED,
                })
                inserted += 1
                if inserted % 50 == 0:
                    await conn.commit()
                    print(f"  ...{inserted} agentes insertados")
            except Exception:
                skipped_invalid += 1
                await conn.rollback()
                continue
        await conn.commit()

    await engine.dispose()
    print(f"\nResumen: {inserted} insertados, {skipped_dup} duplicados, "
          f"{skipped_invalid} invalidos, {no_cargo} sin id_cargo (NULL)")


if __name__ == "__main__":
    asyncio.run(main())
