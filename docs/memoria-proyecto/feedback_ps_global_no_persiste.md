---
name: ps-global-no-persiste-entre-tools
description: $Global:VAR seteada en un PS tool-call no existe en el siguiente. Cada PowerShell tool-call arranca proceso nuevo. Login + uso del token deben ir en el MISMO bloque o el segundo recibe 401.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 730ba002-bb4e-4ffc-a6c4-7067ae9362ab
---

Cada invocación de la tool `PowerShell` (o `Bash`) arranca un proceso shell nuevo. **Las variables que setees, incluso con `$Global:` o `$env:`, NO sobreviven al cierre del proceso** — el "shell estado no persiste" del prompt de Bash aplica idéntico a PS.

**Síntoma**: hacés login en un PS call, guardás `$Global:HDR = @{Authorization=...}` con el Bearer token, y la siguiente llamada PS recibe 401 porque `$HDR` está vacío.

**Why:** En este entorno cada tool-call es un proceso independiente. La env var `ENV_FILE` que setés con `$env:ENV_FILE = ".env.local"` tampoco se hereda al `Start-Process python ...` posterior si está en una llamada distinta (receta confiable: wrapper `cmd /c "set ENV_FILE=..."`, skill `win-quirks` Q17).

**How to apply:**
- Cuando una operación necesite token de auth, hacé **login + uso** en el mismo PS call. No dividir.
- Si necesitás 6 mediciones con auth: 1 sola PS call que hace login + loop de mediciones adentro.
- Si necesitás encadenar comandos que dependen de variables: chain con `;` dentro del **mismo** PS call, no en calls separadas.
- Cuando el child process necesita una env var (uvicorn quiere `ENV_FILE`), seteala en el PS call que llama a `Start-Process`. Si la seteás en una call anterior, el child no la va a tener.

Caso real sesión 2026-05-14 (perf agenda): seteé `$Global:HDR` en un PS call y los 4 PS calls siguientes recibieron `{"detail":"No autenticado"}`. Tuve que re-pegar login + todo el seed en una sola llamada. Perdí ~2 min por esto.
