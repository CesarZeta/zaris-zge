# -*- coding: utf-8 -*-
"""Carga inicial de datos demo para los tableros BI (local).

Genera mes a mes desde --desde (default 2026-04-01) hasta --hasta (default AYER:
solo dias completos) usando los mismos motores que POST /api/v1/demo/poblar:
app/services/demo_datos.py (reclamos + OT), demo_atencion.py (turnos / colero /
Guardia / eventos) y demo_tramites.py (expedientes). Al final corre una pasada
de avanzar_pendientes de cada modulo.

Reclamos y tramites son idempotentes por dia (un dia ya generado se saltea):
re-correr el script sobre un rango ya cargado agrega ~0.

Uso (desde backend/, con el venv del proyecto):
    $env:ENV_FILE=".env.local"; python seed_demo_bi.py
    $env:ENV_FILE=".env.local"; python seed_demo_bi.py --desde 2026-04-01 --semilla 42
    $env:ENV_FILE=".env.local"; python seed_demo_bi.py --modulos tramites
    # Cierre del atraso (lo viejo que quedo abierto). Sin --aplicar = dry-run:
    $env:ENV_FILE=".env.local"; python seed_demo_bi.py --modo cerrar_atraso
    $env:ENV_FILE=".env.local"; python seed_demo_bi.py --modo cerrar_atraso --aplicar --incluir-no-demo

Contra PROD no se usa este script (no hay .env.prod): la carga de prod va por el
endpoint /api/v1/demo/poblar (workflow demo-datos.yml, admin JWT o dispatcher token).
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, timedelta

from app.core.database import AsyncSessionLocal
from app.services import demo_atencion, demo_datos, demo_tramites


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
    parser.add_argument("--hasta", default=str(date.today() - timedelta(days=1)))
    parser.add_argument("--min-mensual", type=int, default=300)
    parser.add_argument("--max-mensual", type=int, default=500)
    parser.add_argument("--tramites-min-mensual", type=int, default=60)
    parser.add_argument("--tramites-max-mensual", type=int, default=120)
    parser.add_argument("--vecinos-nuevos", type=int, default=250)
    parser.add_argument("--semilla", type=int, default=None)
    parser.add_argument("--modulos", default="reclamos,atencion,tramites",
                        help="reclamos,atencion,tramites (default los tres)")
    parser.add_argument("--dias-futuro", type=int, default=7)
    parser.add_argument("--modo", choices=("poblar", "cerrar_atraso"), default="poblar")
    parser.add_argument("--aplicar", action="store_true", help="cerrar_atraso: escribir (sin esto, dry-run)")
    parser.add_argument("--incluir-no-demo", action="store_true",
                        help="cerrar_atraso: incluir datos de QA/seed que no son del generador")
    parser.add_argument("--dias-atraso", type=int, default=21)
    parser.add_argument("--rebalancear-sla", action="store_true",
                        help="cerrar_atraso: llevar los meses viejos < 60 %% dentro del SLA a su objetivo")
    args = parser.parse_args()

    desde = date.fromisoformat(args.desde)
    hasta = date.fromisoformat(args.hasta)
    modulos = {m.strip() for m in args.modulos.split(',') if m.strip()}

    async with AsyncSessionLocal() as db:
        if args.modo == "cerrar_atraso":
            if "tramites" in modulos:
                r = await demo_tramites.cerrar_atraso_tramites(
                    db, dias=args.dias_atraso, aplicar=args.aplicar, incluir_no_demo=args.incluir_no_demo)
                print("atraso tramites:", json.dumps(r, ensure_ascii=False, default=str))
            if "atencion" in modulos:
                r = await demo_atencion.cerrar_atraso_emergencias(
                    db, dias=args.dias_atraso, aplicar=args.aplicar, incluir_no_demo=args.incluir_no_demo)
                print("atraso emergencias:", json.dumps(r, ensure_ascii=False, default=str))
            if "reclamos" in modulos:
                r = await demo_datos.cerrar_atraso_reclamos(
                    db, dias=args.dias_atraso, aplicar=args.aplicar, incluir_no_demo=args.incluir_no_demo,
                    rebalancear_sla=args.rebalancear_sla)
                print("atraso reclamos:", json.dumps(r, ensure_ascii=False, default=str))
            print("APLICADO" if args.aplicar else "DRY-RUN (nada escrito): repetir con --aplicar")
            return

        for i, (ini, fin) in enumerate(_meses(desde, hasta)):
            # Semilla desplazada por mes: con la misma semilla todos los meses
            # sortearian la misma secuencia.
            semilla = (args.semilla + i * 101) if args.semilla is not None else None
            if "reclamos" in modulos:
                r = await demo_datos.generar_periodo(
                    db, ini, fin,
                    min_mensual=args.min_mensual, max_mensual=args.max_mensual,
                    vecinos_nuevos=args.vecinos_nuevos, semilla=semilla,
                )
                print(f"{ini} .. {fin} reclamos: {r}")
            if "atencion" in modulos:
                r = await demo_atencion.generar_periodo_atencion(
                    db, ini, fin, semilla=semilla, dias_futuro=args.dias_futuro,
                )
                print(f"{ini} .. {fin} atencion: {r}")
            if "tramites" in modulos:
                r = await demo_tramites.generar_periodo_tramites(
                    db, ini, fin, min_mensual=args.tramites_min_mensual,
                    max_mensual=args.tramites_max_mensual, semilla=semilla,
                )
                print(f"{ini} .. {fin} tramites: {r}")
        if "reclamos" in modulos:
            r = await demo_datos.avanzar_pendientes(db, semilla=args.semilla)
            print(f"avanzar_pendientes: {r}")
        if "atencion" in modulos:
            r = await demo_atencion.avanzar_pendientes_atencion(db, semilla=args.semilla)
            print(f"avanzar_pendientes_atencion: {r}")
        if "tramites" in modulos:
            r = await demo_tramites.avanzar_pendientes_tramites(db, semilla=args.semilla)
            print(f"avanzar_pendientes_tramites: {r}")


if __name__ == "__main__":
    asyncio.run(main())
