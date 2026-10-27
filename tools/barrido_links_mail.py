# -*- coding: utf-8 -*-
"""
Barrido de links por municipio (IT-01 F4+F5, Tarea 9): ningún link de mail, QR o pantalla se arma
con las settings de dirección fuera de `app/core/urls.py` (y su definición en `app/core/config.py`).
Los links tienen que salir de `base_app(db, id_municipio, app)` para llevar al subdominio del
municipio de la persona.

    python tools/barrido_links_mail.py      → exit 1 y la lista si aparece alguno
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "backend" / "app"
PERMITIDOS = {RAIZ / "core" / "urls.py", RAIZ / "core" / "config.py"}
PATRON = re.compile(r"settings\.(FRONTEND_BASE_URL|APP_VECINOS_FRONTEND_URL|APP_AGENTES_FRONTEND_URL|APP_BASE_URL)\b")

hallazgos = []
for f in sorted(RAIZ.rglob("*.py")):
    if f in PERMITIDOS:
        continue
    for n, linea in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        if PATRON.search(linea):
            hallazgos.append(f"{f.relative_to(RAIZ.parent)}:{n}: {linea.strip()[:120]}")

if hallazgos:
    print(f"{len(hallazgos)} links armados fuera de app/core/urls.py:")
    print("\n".join(hallazgos))
    sys.exit(1)
print("OK: ningún link armado fuera de app/core/urls.py")
