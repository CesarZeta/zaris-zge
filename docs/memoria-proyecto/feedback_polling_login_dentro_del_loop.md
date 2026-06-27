---
name: polling-login-dentro-del-loop
description: "Loops de polling contra prod (Railway autodeploy, /calendario, /health) deben hacer login DENTRO de cada iteración. Login fuera del loop falla con 502 transitorio y deja todas las iteraciones sin token."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 730ba002-bb4e-4ffc-a6c4-7067ae9362ab
---

Anti-patrón:
```powershell
$login = Invoke-RestMethod -Uri "$base/auth/login" ...   # FUERA
$HDR = @{Authorization = "Bearer $($login.access_token)"}
do {
  Start-Sleep -Seconds 30
  Invoke-RestMethod -Uri "$base/agenda/calendario" -Headers $HDR ...
} while (...)
```

Si Railway está en mitad de un autodeploy, la primera llamada (`/auth/login`) recibe `502 Application failed to respond` aunque transitorio. Después de eso, `$HDR` queda indefinido y **todas las iteraciones del loop fallan**, no porque haya un problema con el endpoint medido, sino porque el login inicial murió.

**Patrón correcto:**
```powershell
do {
  Start-Sleep -Seconds 30
  try {
    $login = Invoke-RestMethod -Uri "$base/auth/login" ...   # DENTRO
    $HDR = @{Authorization = "Bearer $($login.access_token)"}
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $r = Invoke-RestMethod -Uri "$base/.../endpoint" -Headers $HDR ...
    $sw.Stop()
    "intento $i | $($sw.Elapsed.TotalMilliseconds)ms"
  } catch {
    "intento $i FAIL: $($_.Exception.Message)"
  }
} while ($i -lt $max)
```

**Why:** Durante un autodeploy Railway, el origen responde 502 por 30-60s. Un solo 502 en el login fuera del loop arruina la sesión entera de polling.

**How to apply:**
- Cualquier polling contra prod (Railway, GH Pages, Supabase): login + medición + try/catch dentro de cada iteración.
- El costo del re-login por iteración es ~500-1000ms, insignificante vs el polling de 30s.
- Si la duración del JWT importa (24h en ZARIS), no es problema: cada iteración recibe uno fresco.

Caso real sesión 2026-05-14 (perf agenda): polling para medir `/calendario` post-deploy. Login estaba fuera. Primer intento devolvió 502 (Railway deployando), `$HDR` quedó vacío, los 7 intentos siguientes mostraron `[FAIL] ... -> $($_.Exception.Message)` referencias a $HDR null. Perdí la primera medición útil. Tuve que correr el script de nuevo a mano.

**Corolario (2026-06-11): un 502/503 NUNCA es veredicto del deploy — es el proxy reciclando.** Al pollear "¿el fix llegó a prod?", la condición de corte debe ser una respuesta REAL del handler (200, o el 4xx esperado del caso de borde). Un check tipo `if ($code -ne 500) { "OK" }` declaró éxito prematuro con un 502 `Application failed to respond` — el backend ni había arrancado. En el loop: `if ($code -eq 502 -or $code -eq 503) { continue }`. Mismo fenómeno en el navegador: un "Failed to fetch" del iframe justo post-push suele ser el reciclado, reintentar antes de diagnosticar.
