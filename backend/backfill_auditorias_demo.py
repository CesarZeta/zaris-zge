# -*- coding: utf-8 -*-
"""
Backfill UNA VEZ por entorno: auditorias POSTERIORES al cierre sobre la demo ya cargada
(F3 de PLAN_AUDITORIA_RECLAMOS.md, 2026-10-20).

Antes de la mig 112 el generador no producia auditorias posteriores, asi que los
cortes "En auditoria / Auditado" del BI estaban vacios. Este script sortea una
fraccion (default 8 %) de los reclamos demo Resueltos (usuario `generador.demo`)
y les aplica, con las mismas reglas que generar_periodo, una auditoria posterior:
estado En auditoria o Auditado (aprobado/observado), OT es_auditoria, historial y,
para las observadas, el reclamo de retrabajo envejecido. fecha_cierre no se toca.

    cd backend
    $env:ENV_FILE=".env.local"; python backfill_auditorias_demo.py            # dry-run (no escribe)
    $env:ENV_FILE=".env.local"; python backfill_auditorias_demo.py --aplicar

Contra PROD (mismo rodeo que reubicar_datos_demo.py): backend/.env apunta al host
directo de Supabase, que solo resuelve por IPv6; desde IPv4 pisar host y usuario
con los del pooler (session):
    $env:ENV_FILE=".env"; $env:POSTGRES_SERVER="aws-1-us-east-1.pooler.supabase.com"
    $env:POSTGRES_USER="postgres.lshfwsscvfsklrmbvkwl"; python backfill_auditorias_demo.py --aplicar

Con --aplicar crea antes el snapshot `_backup_reclamos_auditoria_<fecha>` (RLS on)
con las filas que va a tocar, aplica todo en UNA transaccion y verifica con
consultas aparte (coherencia reclamo/OT, fechas, retrabajos sin encuesta).
Idempotente en la practica: solo elige Resueltos SIN auditoria.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.services import demo_datos  # noqa: E402

VERIFICACION = [
    ("auditados_sin_ot", """
        SELECT COUNT(*) AS n FROM reclamos r
        WHERE r.estado IN ('En auditoría','Auditado') AND r.id_usuario_alta = :uid
          AND NOT EXISTS (SELECT 1 FROM ordenes_trabajo o WHERE o.id_reclamo = r.id_reclamo AND o.es_auditoria)"""),
    ("coherencia_ot", """
        SELECT r.estado, e.nombre AS ot_estado, o.resultado_auditoria, COUNT(*) AS n
        FROM ordenes_trabajo o JOIN reclamos r ON r.id_reclamo = o.id_reclamo
        JOIN estado_ot e ON e.id_estado_ot = o.id_estado
        WHERE o.es_auditoria AND o.id_usuario_alta = :uid GROUP BY 1, 2, 3 ORDER BY 1, 2, 3"""),
    ("fechas", """
        SELECT COUNT(*) FILTER (WHERE fecha_inicio_auditoria < fecha_cierre) AS inicio_antes_cierre,
               COUNT(*) FILTER (WHERE fecha_fin_auditoria < fecha_inicio_auditoria) AS fin_antes_inicio,
               COUNT(*) FILTER (WHERE fecha_inicio_auditoria > NOW()) AS futuro
        FROM reclamos WHERE fecha_inicio_auditoria IS NOT NULL AND id_usuario_alta = :uid"""),
    ("retrabajos", """
        SELECT COUNT(*) AS n, COUNT(*) FILTER (WHERE r.canal_origen = 'oficio') AS oficio,
               COUNT(*) FILTER (WHERE o.resultado_auditoria = 'observado') AS origen_observado,
               COUNT(*) FILTER (WHERE EXISTS (SELECT 1 FROM encuesta_envio ev WHERE ev.id_reclamo = r.id_reclamo)) AS con_encuesta
        FROM reclamos r JOIN reclamos o ON o.id_reclamo = r.id_reclamo_origen_auditoria
        WHERE r.id_usuario_alta = :uid"""),
    ("por_estado_demo", """
        SELECT estado, COUNT(*) AS n FROM reclamos WHERE id_usuario_alta = :uid AND activo
        GROUP BY 1 ORDER BY 1"""),
]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fraccion", type=float, default=demo_datos.TASA_AUDITORIA)
    parser.add_argument("--semilla", type=int, default=112)
    parser.add_argument("--aplicar", action="store_true", help="sin esto es dry-run")
    args = parser.parse_args()

    print(f"DB: {settings.POSTGRES_SERVER}/{settings.POSTGRES_DB}  fraccion={args.fraccion}  "
          f"semilla={args.semilla}  {'APLICAR' if args.aplicar else 'DRY-RUN'}")

    async with AsyncSessionLocal() as db:
        uid = await demo_datos._usuario_generador(db, crear=False)
        if uid is None:
            print("Sin usuario generador.demo: nada que hacer")
            return 1

        # 1. Dry-run siempre primero (misma semilla => mismo sorteo que el aplicar).
        previo = await demo_datos.backfill_auditorias(db, args.fraccion, args.semilla, aplicar=False)
        ids = previo.pop("ids")
        print("Plan:", previo)
        if not args.aplicar or not ids:
            return 0

        # 2. Snapshot de las filas que se tocan (RLS on, convencion del proyecto).
        tabla = f"_backup_reclamos_auditoria_{date.today().strftime('%Y_%m_%d')}"
        await db.execute(text(f"DROP TABLE IF EXISTS {tabla}"))
        await db.execute(text(f"CREATE TABLE {tabla} AS SELECT * FROM reclamos WHERE id_reclamo = ANY(:ids)"),
                         {"ids": ids})
        await db.execute(text(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY"))
        n_bk = (await db.execute(text(f"SELECT COUNT(*) AS n FROM {tabla}"))).scalar()
        print(f"Snapshot {tabla}: {n_bk} filas")

        # 3. Aplicar en la misma transaccion y commitear.
        resultado = await demo_datos.backfill_auditorias(db, args.fraccion, args.semilla, aplicar=True)
        resultado.pop("ids")
        await db.commit()
        print("Aplicado:", resultado)

    # 4. Verificacion por consultas aparte (sesion nueva).
    async with AsyncSessionLocal() as db:
        for nombre, sql in VERIFICACION:
            print(f"--- {nombre}")
            for fila in (await db.execute(text(sql), {"uid": uid})).mappings().all():
                print("   ", dict(fila))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
