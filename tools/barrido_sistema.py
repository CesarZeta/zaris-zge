"""
Barrido de la conexión sin barrera (IT-01 F6, PLAN_MULTI_MUNICIPIO_F6_DISENO.md §4.1).

    python tools/barrido_sistema.py

Falla (exit 1, con archivo:línea) si en backend/app:
  - se importa `app.core.sistema` (SesionSistema, get_db_sistema, funciones de excepción) desde un
    archivo que no está en PERMITIDOS;
  - aparece `create_async_engine` fuera de app/core/database.py y app/core/sistema.py.

Cada entrada de PERMITIDOS es una de las cinco excepciones del diseño, con su motivo. Sumar un archivo
acá es ampliar la excepción: tiene que caber en una de las cinco.
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "backend" / "app"

PERMITIDOS: dict[str, str] = {
    "core/sistema.py": "define la conexión sin barrera",
}

MOTORES = {"core/database.py", "core/sistema.py"}

_IMPORTA_SISTEMA = re.compile(r"^\s*(from\s+app\.core\.sistema\s+import|from\s+app\.core\s+import\s+[^#\n]*\bsistema\b|import\s+app\.core\.sistema)")
_MOTOR = re.compile(r"\bcreate_async_engine\s*\(")


def main() -> int:
    fallas: list[str] = []
    for archivo in sorted(RAIZ.rglob("*.py")):
        rel = archivo.relative_to(RAIZ).as_posix()
        for n, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), 1):
            if _IMPORTA_SISTEMA.search(linea) and rel not in PERMITIDOS:
                fallas.append(f"{rel}:{n}: importa la conexión sin barrera y no está en PERMITIDOS")
            if _MOTOR.search(linea) and rel not in MOTORES:
                fallas.append(f"{rel}:{n}: crea un motor de base fuera de database.py/sistema.py")
    for f in fallas:
        print(f)
    print(f"barrido_sistema: {len(fallas)} problema(s); {len(PERMITIDOS)} archivo(s) permitido(s)")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
