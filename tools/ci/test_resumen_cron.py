# -*- coding: utf-8 -*-
"""Prueba de tools/ci/resumen_cron.py (IT-01 F6.4). Sin dependencias:

    python tools/ci/test_resumen_cron.py
"""
import json
import os
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resumen_cron.py")
FALLAS = 0


def correr(cuerpo) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(cuerpo if isinstance(cuerpo, str) else json.dumps(cuerpo))
    try:
        r = subprocess.run([sys.executable, SCRIPT, f.name], capture_output=True, text=True, encoding="utf-8")
        return r.returncode, r.stdout + r.stderr
    finally:
        os.unlink(f.name)


def check(cond: bool, nombre: str, detalle: str = "") -> None:
    global FALLAS
    print(f"  {'OK  ' if cond else 'FAIL'} {nombre}" + ("" if cond else f" {detalle}"))
    FALLAS += 0 if cond else 1


codigo, salida = correr({"municipios": [
    {"id_municipio": 1, "nombre": "San Andrés", "estado": "ok", "error": None},
    {"id_municipio": 4, "nombre": "Prueba", "estado": "omitido", "error": None}], "con_error": []})
check(codigo == 0 and "OK      San Andrés (1)" in salida and "OMITIDO Prueba (4)" in salida, "todos_ok", salida)

codigo, salida = correr({"municipios": [
    {"id_municipio": 1, "nombre": "San Andrés", "estado": "ok", "error": None},
    {"id_municipio": 4, "nombre": "Prueba", "estado": "error", "error": "KeyError: x"}],
    "con_error": ["Prueba (4): KeyError: x"]})
check(codigo == 1 and "ERROR   Prueba (4)" in salida and "::error::Municipios con error: Prueba (4): KeyError: x" in salida,
      "uno_con_error", salida)

codigo, salida = correr({"envios": {"procesados": 0}})
check(codigo == 0 and "no trae el detalle por municipio" in salida, "respuesta_sin_municipios", salida)

codigo, salida = correr("esto no es json")
check(codigo == 0 and "no es JSON" in salida, "respuesta_no_json", salida)

print("FALLAS:", FALLAS)
sys.exit(1 if FALLAS else 0)
