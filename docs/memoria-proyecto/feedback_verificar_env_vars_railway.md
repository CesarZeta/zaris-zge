---
name: verificar-env-vars-railway
description: "Despues de pushear una feature backend que lea env vars nuevas (o use Supabase Storage), testear el endpoint EN PROD (Railway) no solo en local. Railway no hereda automáticamente las vars de .env.local."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 76abb031-f1fc-41a4-97a8-16b043ddea10
---

Smoke local con `.env.local` ≠ smoke prod. Railway tiene su propio set de env vars seteadas a mano en el dashboard del proyecto. Cuando agregas una feature backend que lee `settings.X`, el código pasa el smoke local pero **explota 503 (o 500) en Railway** si la var no fue agregada al dashboard.

**Why:** las features se prueban en local primero y eso da una falsa sensación de "feature OK". Sub-fase B5 de Reclamos (adjuntos) se cerró 2026-05-12 como "verificada E2E local" pero **nunca funcionó en prod** desde el deploy porque Railway no tenía `SUPABASE_URL` / `SUPABASE_SERVICE_KEY`. El bug se descubrió 2026-05-13 cuando se agregó otra feature (upload de logo) que pegó contra el mismo `storage.py` y dio el mismo 503.

**How to apply:**
- Cuando agregás una feature que lee `settings.X` nueva (o cualquier var del bloque Supabase, OAuth, secrets, etc.), después del push hacer **explícitamente** un smoke contra Railway, no solo contra local. Ejemplo:
  ```powershell
  $login = Invoke-RestMethod -Method Post -Uri 'https://zaris-api-production-bf0b.up.railway.app/api/v1/auth/login' -ContentType 'application/json' -Body '{"email":"<USUARIO-DEMO>@municipio.gob.ar","password":"<PASS-DEMO>"}'
  $h = @{ Authorization = "Bearer $($login.access_token)" }
  Invoke-RestMethod -Method Post -Uri 'https://zaris-api-production-bf0b.up.railway.app/api/v1/<endpoint-nuevo>' -Headers $h ...
  ```
- Si el endpoint da 503 con mensaje "X no configurado", la var falta en Railway dashboard. Hay que pasársela al usuario (yo no la puedo setear via MCP) — copiar el bloque de `backend/.env.local` y pedirle que lo agregue en Railway → Variables.
- Reusar este patrón para CUALQUIER deploy que dependa de vars: Stripe keys, Sentry DSN, OAuth secrets, JWT secrets nuevos, etc.

**Tip de detección temprana**: si una feature pasada también usa la misma var y de repente se rompe, no es regression — es que la var nunca estuvo, y el deploy nuevo solo lo amplificó al agregar más superficie afectada.

Caso real 2026-05-13: bucket `config-assets` + endpoint `/logo-upload-url` daban 503. Diagnóstico: la misma falla aplicaba a `/reclamos/{id}/adjuntos/upload-url` desde el deploy de B5 (2026-05-12). Solución: el usuario setea las 3 vars (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ADJUNTOS_BUCKET`) en Railway → deploy automático → ambas features andan.

Relacionado: [[feedback_verificar_runtime_antes_de_agente]] (verificar runtime backend antes de gastar tiempo de QA externo — patrón similar pero distinto).
