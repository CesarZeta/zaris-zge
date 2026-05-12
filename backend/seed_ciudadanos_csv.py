"""
seed_ciudadanos_csv.py — Carga masiva de ciudadanos desde CSV.

Diferencias con seed_inicial.py:
- Idempotente por DNI (no se saltea si ya hay ciudadanos: agrega los que faltan).
- Compatible con prod: usa sexo 'HOMBRE'/'MUJER'/'OTROS' (CHECK ciudadanos_sexo_check).
- Conexion configurable via DATABASE_URL.

Uso:
    cd backend
    # Local
    $env:ENV_FILE=".env.local"; python seed_ciudadanos_csv.py

    # Prod (cuidado, idempotente pero ojo con LIMITE):
    $env:DATABASE_URL="postgresql+asyncpg://postgres:<pwd>@db.lshfwsscvfsklrmbvkwl.supabase.co:5432/postgres"
    python seed_ciudadanos_csv.py --limite 500 --confirm-prod
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

CSV_PATH = Path(__file__).parent.parent / "Tablas Iniciales" / "ciudadano.csv"
ID_USUARIO_SEED = 1


def _read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig") as f:
        return [{k.strip(): (v or "").strip() for k, v in row.items()}
                for row in csv.DictReader(f, delimiter=";")]


def _parse_fecha(s: str) -> date | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _map_sexo(raw: str) -> str:
    """CSV: '1' masc, '0' fem, otro. Prod CHECK requiere uppercase."""
    if raw == "1":
        return "HOMBRE"
    if raw == "0":
        return "MUJER"
    return "OTROS"


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limite", type=int, default=500)
    parser.add_argument("--confirm-prod", action="store_true",
                        help="Necesario si DATABASE_URL apunta a Supabase.")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://postgres:145236@127.0.0.1:5432/zaris_dev")
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if "supabase.co" in db_url and not args.confirm_prod:
        print("ERROR: DATABASE_URL apunta a Supabase prod. Re-correr con --confirm-prod.")
        sys.exit(2)

    print(f"DB: {db_url.split('@')[1] if '@' in db_url else db_url}")
    print(f"CSV: {CSV_PATH} (limite={args.limite})")

    rows = _read_csv(CSV_PATH)
    print(f"CSV total: {len(rows)} filas")

    engine = create_async_engine(db_url, echo=False)
    async with engine.connect() as conn:
        # id_nacionalidad Argentina (id puede variar entre entornos)
        id_nac_arg = await conn.scalar(text(
            "SELECT id FROM nacionalidades WHERE pais ILIKE 'Argentina' LIMIT 1"
        ))
        id_nac_arg = int(id_nac_arg) if id_nac_arg else 1

        # DNIs ya existentes -> dedupe (no contar contra el limite)
        existing = (await conn.execute(text(
            "SELECT regexp_replace(doc_nro, '[^0-9]', '', 'g') FROM ciudadanos"
        ))).scalars().all()
        existing_dnis = set(existing)
        print(f"Ciudadanos existentes en DB: {len(existing_dnis)} DNIs distintos")

        inserted = 0
        skipped_invalid = 0
        skipped_dupe = 0
        cuil_seen = set()
        email_seen = set()

        for r in rows:
            if inserted >= args.limite:
                break

            doc_nro = re.sub(r"\D", "", r.get("doc_nro") or "")
            nombre = (r.get("nombre") or "")[:100]
            apellido = (r.get("apellido") or "")[:100]

            if not nombre or not apellido or len(doc_nro) < 7:
                skipped_invalid += 1
                continue
            if doc_nro in existing_dnis:
                skipped_dupe += 1
                continue
            existing_dnis.add(doc_nro)

            cuil_raw = re.sub(r"\D", "", r.get("cuil") or "")
            sexo_raw = r.get("sexo") or ""
            sexo = _map_sexo(sexo_raw)
            fecha_nac = _parse_fecha(r.get("fecha_nacimiento") or "") or date(1990, 1, 1)
            telefono = re.sub(r"[^\d+\-\s]", "", r.get("telefono") or "")[:15] or "00000000"
            calle = (r.get("calle") or "")[:200]
            altura = (r.get("calleAltura") or "")[:20]

            if not cuil_raw or len(cuil_raw) < 11:
                cuil_raw = f"20{doc_nro}{'5' if sexo == 'MUJER' else '7'}"
            cuil_fmt = (
                f"{cuil_raw[:2]}-{cuil_raw[2:10]}-{cuil_raw[10:]}"
                if len(cuil_raw) >= 11 else cuil_raw
            )
            if cuil_fmt in cuil_seen:
                skipped_dupe += 1
                continue
            cuil_seen.add(cuil_fmt)

            email = (r.get("email") or "").strip().lower()
            if not email or "@" not in email or email in email_seen:
                email = f"{nombre.lower().replace(' ','.')}.{doc_nro}@vecino.gob.ar"
            email_seen.add(email)

            try:
                await conn.execute(text("""
                    INSERT INTO ciudadanos
                        (doc_tipo, doc_nro, cuil, nombre, apellido, sexo, fecha_nac,
                         id_nacionalidad, calle, altura, localidad, provincia,
                         telefono, email, activo, ren_chk, email_chk, emp_chk,
                         fecha_alta, id_usuario_alta, id_municipio)
                    VALUES
                        ('DNI', :doc_nro, :cuil, :nombre, :apellido, :sexo, :fecha_nac,
                         :id_nac, :calle, :altura, :localidad, :provincia,
                         :telefono, :email, TRUE, FALSE, FALSE, FALSE,
                         NOW(), :uid, 1)
                """), {
                    "doc_nro": doc_nro, "cuil": cuil_fmt,
                    "nombre": nombre, "apellido": apellido,
                    "sexo": sexo, "fecha_nac": fecha_nac, "id_nac": id_nac_arg,
                    "calle": calle, "altura": altura,
                    "localidad": "Vicente Lopez", "provincia": "Buenos Aires",
                    "telefono": telefono, "email": email[:150],
                    "uid": ID_USUARIO_SEED,
                })
                inserted += 1
                if inserted % 100 == 0:
                    await conn.commit()
                    print(f"  ...{inserted} insertados")
            except Exception as e:
                skipped_invalid += 1
                await conn.rollback()
                # Continuar con la siguiente
                continue

        await conn.commit()

    await engine.dispose()
    print(f"\nResumen: {inserted} insertados, {skipped_dupe} duplicados, {skipped_invalid} invalidos")


if __name__ == "__main__":
    asyncio.run(main())
