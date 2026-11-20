# -*- coding: utf-8 -*-
"""Resumen por municipio de la respuesta de un cron (IT-01 F6.4). Lo usan los workflows de
encuestas, trámites e integridad de cuentas después de imprimir el cuerpo:

    python3 tools/ci/resumen_cron.py respuesta.json

Imprime una línea por municipio. Si alguno dio error, emite `::error::` con sus nombres y sale con 1
(el paso queda en rojo). Una respuesta sin el detalle (backend anterior a F6.4, mientras Railway
publica) no hace fallar el cron.
"""
import json
import sys


def main(ruta: str) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # nombres con acentos en cualquier consola
    try:
        with open(ruta, encoding="utf-8") as f:
            cuerpo = json.load(f)
    except (OSError, ValueError):
        print("Resumen por municipio: la respuesta no es JSON; ver el cuerpo de arriba.")
        return 0
    municipios = cuerpo.get("municipios") if isinstance(cuerpo, dict) else None
    if not isinstance(municipios, list):
        print("Resumen por municipio: la respuesta no trae el detalle por municipio (backend anterior a F6.4).")
        return 0
    print("Resumen por municipio:")
    for m in municipios:
        etiqueta = {"ok": "OK", "omitido": "OMITIDO", "error": "ERROR"}.get(m.get("estado"), str(m.get("estado")).upper())
        linea = f"  {etiqueta:<7} {m.get('nombre')} ({m.get('id_municipio')})"
        print(linea + (f" — {m['error']}" if m.get("error") else ""))
    con_error = cuerpo.get("con_error") or []
    if con_error:
        print("::error::Municipios con error: " + " | ".join(con_error))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
