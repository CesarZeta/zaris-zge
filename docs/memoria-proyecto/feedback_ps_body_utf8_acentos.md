---
name: ps-body-utf8-acentos
description: "Invoke-RestMethod con body que tiene acentos (En gestión, En auditoría) da 400 'error parsing the body' — mandar bytes UTF-8 explícitos, no el string de ConvertTo-Json"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a796228c-32ea-478f-9af7-92f08ae400c6
---

En smokes PowerShell contra la API, un body JSON con caracteres acentuados (`"En gestión"`, `"En auditoría"`, `ñ`, etc.) pasado como string a `Invoke-RestMethod -Body (... | ConvertTo-Json)` llega **mal codificado** al backend FastAPI → responde **400 "There was an error parsing the body"**. NO es un bug del endpoint: es que PowerShell 5.1 serializa el body en una codificación que no es UTF-8 limpio y FastAPI no puede parsear el JSON.

**Síntoma engañoso:** los asserts con valores SIN acento pasan (ej. `"Resuelto"` → 422 correcto), pero los que tienen acento dan 400. Parece que "solo algunos casos fallan" y se pierde tiempo dudando del código del endpoint. El tell es el `{"detail":"There was an error parsing the body"}` — eso es parseo, no validación de negocio.

**Why:** sesión 2026-05-20 (fixes QA Royman) — una corrida entera de smoke del FSM de estados de reclamo dio 400 en cada PUT con `"En gestión"`/`"En auditoría"` mientras `"Resuelto"` pasaba; casi audito mi propio código del FSM antes de notar que era encoding.

**How to apply:** cuando un body de smoke tenga CUALQUIER carácter no-ASCII, mandar bytes UTF-8 explícitos con `Content-Type: application/json; charset=utf-8`:

```powershell
function PutJson($h, $url, $obj) {
  $b = [System.Text.Encoding]::UTF8.GetBytes(($obj | ConvertTo-Json))
  Invoke-RestMethod -Uri "$base$url" -Method Put -Headers $h `
    -ContentType "application/json; charset=utf-8" -Body $b
}
PutJson $adminH "/api/v1/reclamos/30/estado" @{estado="En gestión"}
```

El `[System.Text.Encoding]::UTF8.GetBytes(...)` es la pieza clave — pasar el string crudo NO alcanza aunque agregues `charset=utf-8` al header. Aplica a cualquier dominio del proyecto donde los valores tengan tildes (estados de reclamo/OT, nombres de área con tilde, descripciones). Complementa [[feedback_ps_quirks_startprocess_psql]] y [[feedback_ps_global_no_persiste]].

**Ampliación 2026-06-02 — para smokes HTTP, preferir `curl.exe` con body en archivo, NO `Invoke-WebRequest`/`Invoke-RestMethod`.** En la sesión de endpoints del vecino, `Invoke-WebRequest -Body ([Encoding]::UTF8.GetBytes(...))` devolvió **HTTP 0 (fallo de transporte)** en un POST de login que con `curl.exe` daba 200 limpio; además `--data '{...}'` con comillas simples inline en PS pierde/rompe el JSON (token vacío). Lo que funciona robusto y reproducible: escribir el body a un archivo temporal con `[System.IO.File]::WriteAllText($tmp, $json, (New-Object System.Text.UTF8Encoding($false)))` (UTF-8 SIN BOM — el BOM rompe el parser, ver [[feedback_set_content_utf8_bom]]) y mandarlo con `curl.exe -s -X POST <url> -H "Content-Type: application/json" --data "@$tmp"`. Para capturar el status sin el body: `-o NUL -w "%{http_code}"`; con body: `-w "\n@@%{http_code}"` y split. Persistir el token entre llamadas en un archivo (no `$global:`, [[feedback_ps_global_no_persiste]]). Costó 3-4 iteraciones descubrir que el transporte de IWR era el problema y no el endpoint — el endpoint estaba perfecto (curl lo confirmó).
