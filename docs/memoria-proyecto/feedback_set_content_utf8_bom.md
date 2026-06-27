---
name: feedback_set_content_utf8_bom
description: PowerShell Set-Content -Encoding utf8 mete BOM y rompe .env / archivos que otros parsean
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c90a3545-3afb-4e9e-be8d-0ee54fc10b59
---

`Set-Content archivo -Encoding utf8` en Windows PowerShell 5.1 escribe **UTF-8 CON BOM**
(bytes `239,187,191` al inicio). Si el archivo lo parsea otra herramienta — pydantic-settings
leyendo `.env.local`, un loader de config, etc. — el BOM corrompe la primera línea y la app
no arranca o lee mal el primer valor.

Cazado 2026-05-22: toggleé `DISPATCHER_TOKEN` en `.env.local` con `Set-Content -Encoding utf8`
→ BOM → uvicorn no levantó. Diagnóstico: `[System.IO.File]::ReadAllBytes(f)[0..2]` mostró
`239,187,191`.

**Fix / forma correcta de reescribir un archivo que otros parsean, sin BOM:**
```powershell
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$txt = [System.IO.File]::ReadAllText($f) -replace "^﻿",""   # quita BOM si ya lo tenía
[System.IO.File]::WriteAllText("$PWD\$f", $txt, $utf8NoBom)
```

Para verificar: los primeros bytes NO deben ser `239,187,191`.

**Variante inversa cazada 2026-06-12 (corrompí MEMORY.md):** `Get-Content` SIN `-Encoding` sobre
un archivo UTF-8 **sin BOM** lo lee como ANSI/cp1252 → cada tilde se parte en 2-3 chars; al
reescribir (WriteAllLines/Set-Content) queda doble-encodeado ("código"→"cÃ³digo", el archivo CRECE).
Filtrar/editar líneas de un archivo UTF-8 desde PowerShell exige `-Encoding UTF8` también en la
LECTURA — o directamente no usar PS. Reparación si ya pasó: en Python,
`raw.encode('cp1252', fallback latin-1 por char).decode('utf-8')`.

Aún mejor para archivos que el repo necesita: editarlos con la tool Edit/Write (no PowerShell).
PowerShell solo cuando es inevitable. Hermano del quirk de encoding en
[[feedback_aprendizajes_proyecto]] (PYTHONIOENCODING) y de la nota de encoding del tool PS.
