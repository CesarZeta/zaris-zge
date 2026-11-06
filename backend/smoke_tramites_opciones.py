# -*- coding: utf-8 -*-
"""
Smoke in-process - Trámites: un campo de selección acepta sus propias opciones (mig 137, 2026-11-06).

    cd backend
    $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_tramites_opciones.py

SOLO LOCAL y de solo lectura. Por cada campo de selección de una versión publicada en el municipio de
direccion_base y el modelo, cada opción que ve la pantalla tiene que pasar el validador real, y un valor
inventado no. Si un trámite no se puede iniciar por esto, solo se ve al llenar el formulario.
"""
import asyncio
import json
import os
import sys

from fastapi import HTTPException

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

os.environ.setdefault("ENV_FILE", ".env.local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402

if "zaris_dev" not in settings.ASYNC_DATABASE_URI:
    sys.exit("ABORT: este smoke es SOLO LOCAL (la DB configurada no es zaris_dev).")

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.services.tramites.creacion import validar_campos_contra_tipo  # noqa: E402

ok = 0
fallas: list[str] = []


def check(nombre: str, cond: bool, extra: str = "") -> None:
    global ok
    if cond:
        ok += 1
    else:
        fallas.append(f"{nombre} {extra}")
        print(f"  FAIL {nombre} {extra}")


def opciones_de_la_pantalla(raw) -> list[str]:
    """Lo mismo que normalizarOpciones de CampoDinamico.tsx: lo que el usuario puede elegir."""
    if isinstance(raw, str):
        raw = json.loads(raw)
    if isinstance(raw, dict) and "opciones" in raw:
        raw = raw["opciones"]
    if not isinstance(raw, list):
        return []
    return [str(o["valor"]) if isinstance(o, dict) and "valor" in o else str(o) for o in raw]


async def validar(db, id_version: int, id_municipio: int, datos: dict) -> list[str]:
    try:
        await validar_campos_contra_tipo(datos, id_version, id_municipio, db)
        return []
    except HTTPException as e:
        return e.detail["errores_validacion"] if isinstance(e.detail, dict) else [str(e.detail)]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        municipios = (await db.execute(text(
            "SELECT id_municipio, nombre FROM municipios WHERE direccion_base OR estado = 'modelo' ORDER BY 1"))).all()
        check("están el municipio base y el modelo", len(municipios) == 2, str(municipios))
        for id_mun, nombre in municipios:
            print(f"\n{nombre}")
            campos = (await db.execute(text("""
                SELECT c.id_tipo_tramite_version AS v, c.nombre_interno, c.etiqueta, c.tipo_dato, c.opciones_jsonb,
                       tt.nombre AS tipo
                  FROM tipo_tramite_campo c
                  JOIN tipo_tramite_version v ON v.id_tipo_tramite_version = c.id_tipo_tramite_version
                  JOIN tipo_tramite tt ON tt.id_tipo_tramite = v.id_tipo_tramite
                 WHERE c.id_municipio = :m AND c.activo AND v.activo AND v.estado = 'publicado'
                   AND c.tipo_dato IN ('seleccion', 'seleccion_multiple')
                 ORDER BY tt.nombre, c.orden"""), {"m": id_mun})).mappings().all()
            check("tiene campos de selección para probar", bool(campos))
            for c in campos:
                ref = f"{c['tipo']} / {c['etiqueta']}"
                vals = opciones_de_la_pantalla(c["opciones_jsonb"])
                check(f"{ref}: tiene opciones", bool(vals), str(c["opciones_jsonb"])[:80])
                multiple = c["tipo_dato"] == "seleccion_multiple"
                for valor in vals:
                    errores = await validar(db, c["v"], id_mun, {c["nombre_interno"]: [valor] if multiple else valor})
                    check(f"{ref}: acepta «{valor}»", not [e for e in errores if c["etiqueta"] in e and "valid" in e], str(errores))
                errores = await validar(db, c["v"], id_mun, {c["nombre_interno"]: ["inventado"] if multiple else "inventado"})
                check(f"{ref}: rechaza un valor inventado", any(c["etiqueta"] in e and "valid" in e for e in errores), str(errores))
                raw = c["opciones_jsonb"]
                raw = json.loads(raw) if isinstance(raw, str) else raw
                check(f"{ref}: formato del builder", isinstance(raw, list) and all(
                    isinstance(o, dict) and o.get("valor") and o.get("etiqueta") for o in raw), str(raw)[:80])

        # Lo ya cargado sigue siendo válido: la migración no cambia ningún valor.
        filas = (await db.execute(text("""
            SELECT t.id_tramite, t.datos_jsonb, c.nombre_interno, c.opciones_jsonb
              FROM tramite t
              JOIN tipo_tramite_campo c ON c.id_tipo_tramite_version = t.id_tipo_tramite_version
             WHERE t.id_municipio = :m AND c.tipo_dato = 'seleccion' AND t.datos_jsonb ? c.nombre_interno"""),
            {"m": municipios[0][0]})).mappings().all()
        ajenos = [f["id_tramite"] for f in filas
                  if f["datos_jsonb"][f["nombre_interno"]] not in (None, "", *opciones_de_la_pantalla(f["opciones_jsonb"]))]
        check(f"los {len(filas)} valores ya cargados están entre las opciones", not ajenos, str(ajenos[:10]))

    print(f"\n== {ok} OK · {len(fallas)} FAIL ==")
    sys.exit(1 if fallas else 0)


if __name__ == "__main__":
    asyncio.run(main())
