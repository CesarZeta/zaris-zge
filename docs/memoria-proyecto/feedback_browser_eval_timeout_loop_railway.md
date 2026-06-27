---
name: browser-eval-timeout-loop-railway
description: browser_eval revienta a los 30s (CDP timeout) si hace un loop de varias requests a Railway dentro del mismo eval; hacerlas de a una
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 55fe2b64-e49e-45a3-a6d5-d673e42f005d
---

`mcp__integrated-browser-mcp__browser_eval` tiene un límite duro de **30s por llamada** (`CDP request timed out after 30000ms: Runtime.evaluate`). La latencia base Railway↔Supabase es ~2-3s por request ([[reference_agenda_latencia_base_railway_supabase]]), así que un loop `for (const x of items) await fetch(railway...)` con 5-6 iteraciones dentro de UN solo `browser_eval` lo supera y aborta — **pero las requests que alcanzaron a salir SÍ se ejecutaron** (no es atómico). Síntoma engañoso: el eval "falla" pero parte del trabajo quedó hecho.

**Why:** el sembrado/seed vía API desde el browser es tentador hacerlo en un loop compacto, pero cada POST a Railway puede tardar 2-3s (más si hay cold start).

**How to apply:**
- Sembrar/mutar de a UNA request por `browser_eval` (o de a 2-3 máximo). Verificar el resultado con `execute_sql` entre tandas, no asumir.
- Si un eval con loop devuelve timeout, NO re-ejecutar el loop entero: chequear primero en DB qué se creó (cazado al sembrar 6 turnos demo — entraron 5 antes del timeout).
- Guardar el token en `window.__tok` en el primer eval para no re-loguear en cada uno ([[feedback_ps_global_no_persiste]] es el análogo en PowerShell).
- Para sembrado masivo real, preferir un script Node/PS fuera del browser, no `browser_eval`.

Relacionado: [[feedback_browser_snapshot_revienta_tokens]] (otro límite del mismo MCP, por tamaño de respuesta en vez de tiempo).
