# -*- coding: utf-8 -*-
"""Carga inicial de datos demo para los tableros BI (local).

Genera mes a mes desde --desde (default 2026-04-01) hasta hoy usando
app/services/demo_datos.py (el mismo motor que POST /api/v1/demo/poblar).
Al final corre una pasada de avanzar_pendientes.

Uso (desde backend/, con el venv del proyecto):
    $env:ENV_FILE=".env.local"; python seed_demo_bi.py
    $env:ENV_FILE=".env.local"; python seed_demo_bi.py --desde 2026-04-01 --semilla 42

Contra PROD no se usa este script (no hay .env.prod): la carga inicial de prod
va por el endpoint /api/v1/demo/poblar mes a mes (admin JWT o dispatcher token).
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import date, timedelta

from app.core.database import AsyncSessionLocal
from app.services import demo_datos


def _meses(desde: date, hasta: date):
    """Rangos [inicio, fin] por mes calendario entre desde y hasta."""
    actual = desde
    while actual <= hasta:
        if actual.month == 12:
            fin_mes = date(actual.year, 12, 31)
        else:
            fin_mes = date(actual.year, actual.month + 1, 1) - timedelta(days=1)
        yield actual, min(fin_mes, hasta)
        actual = fin_mes + timedelta(days=1)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--desde", default="2026-04-01")
    parser.add_argument("--hasta", default=str(date.today()))
    parser.add_argument("--min-mensual", type=int, default=300)
    parser.add_argument("--max-mensual", type=int, default=500)
    parser.add_argument("--vecinos-nuevos", type=int, default=250)
    parser.add_argument("--semilla", type=int, default=None)
    args = parser.parse_args()

    desde = date.fromisoformat(args.desde)
    hasta = date.fromisoformat(args.hasta)

    async with AsyncSessionLocal() as db:
        for i, (ini, fin) in enumerate(_meses(desde, hasta)):
            # Semilla desplazada por mes: con la misma semilla todos los meses
            # sortearian el mismo volumen y la misma secuencia.
            semilla = (args.semilla + i * 101) if args.semilla is not None else None
            r = await demo_datos.generar_periodo(
                db, ini, fin,
                min_mensual=args.min_mensual, max_mensual=args.max_mensual,
                vecinos_nuevos=args.vecinos_nuevos, semilla=semilla,
            )
            print(f"{ini} .. {fin}: {r}")
        r = await demo_datos.avanzar_pendientes(db, semilla=args.semilla)
        print(f"avanzar_pendientes: {r}")


if __name__ == "__main__":
    asyncio.run(main())
