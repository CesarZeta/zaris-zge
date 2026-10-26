"""Barrido de cierre de fase (IT-01 F3): el super administrador (nivel 0) tiene en un municipio
todo lo del administrador (nivel 1). Una comparación del nivel por igualdad con 1 en el frontend
lo deja afuera sin ningún error (I3 de la revisión final de F3).

Falla si encuentra `nivel === 1`, `nivel_acceso == 1` y variantes en web-app/src o en el shell
vanilla. Para «es administrador» usar `esAdministrador(user)` de web-app/src/stores/auth.ts (o
`hasPermission(1)`). Una excepción a propósito se marca en la misma línea con `// solo nivel 1:`
y el motivo.

    python tools/barrido_guards_nivel.py
"""
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CARPETAS = [RAIZ / "web-app" / "src", RAIZ / "frontend"]
EXTENSIONES = {".ts", ".tsx", ".js", ".html"}
PATRON = re.compile(r"\bnivel\w*\)?\s*(?:===|==)\s*1\b|\b1\s*(?:===|==)\s*\(?[\w.?]*nivel\w*")
MARCA = "// solo nivel 1:"


def main() -> int:
    hallazgos = []
    for carpeta in CARPETAS:
        for archivo in sorted(carpeta.rglob("*")):
            if archivo.suffix not in EXTENSIONES or "node_modules" in archivo.parts or "dist" in archivo.parts:
                continue
            for n, linea in enumerate(archivo.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if PATRON.search(linea) and MARCA not in linea:
                    hallazgos.append(f"{archivo.relative_to(RAIZ)}:{n}: {linea.strip()}")
    for h in hallazgos:
        print(h)
    print(f"{len(hallazgos)} comparaciones del nivel con 1 sin marcar")
    return 1 if hallazgos else 0


if __name__ == "__main__":
    sys.exit(main())
