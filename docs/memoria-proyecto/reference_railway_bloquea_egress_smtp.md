---
name: reference_railway_bloquea_egress_smtp
description: Railway bloquea el egress SMTP saliente (587 y 465). RESUELTO 2026-05-24 migrando services/email.py a Resend (API HTTP/443). Verificado en prod end-to-end.
metadata: 
  node_type: memory
  type: reference
  originSessionId: a0bc3f28-6b1c-4f19-bcda-aa6306374a59
---

**Railway bloquea el egress SMTP saliente en TODOS los puertos.** Verificado 2026-05-23 con logs de Railway: `enviar_mail` da `error=timed out` tanto en puerto **587 (STARTTLS)** como en **465 (SSL)**. Es la red del datacenter (anti-spam), no la config de la app ni la password.

**Consecuencia:** ningún email sale desde el backend en prod (Railway) vía SMTP. Afecta a los 4 clientes del sender central `services/email.py`: encuestas, notificaciones, trámites, App Vecinos. En **local funciona** (Zoho SMTP por 587), lo que engaña: un mail que "anduvo" probablemente salió desde uvicorn local, NO desde prod. Antes de afirmar "el mail de prod salió", verificar `encuesta_envio.fecha_envio` / `estado='enviada'` en la DB de prod — no la bandeja.

**Diagnóstico que llevó al fix (histórico, 2026-05-23):** bajo SMTP, prod tuvo SIEMPRE 0 envíos `enviada`. Los intentos del dispatcher sobre el envío 3 (CSAT a <EMAIL-ADMIN>) daban `timed out`. Cambiar 587↔465 NO lo resolvió → confirmó que era bloqueo de red, no config. (Ese mismo envío 3 fue el que cerró el test post-Resend el 2026-05-24.)

**Fix aplicado (RESUELTO 2026-05-24, commit `139332e`):** `services/email.py` reescrito a **Resend** (API HTTP por 443, nunca bloqueado) con `httpx.AsyncClient` directo (sin la lib oficial). NO hay fallback SMTP — se borraron las 6 vars `SMTP_*` del config. `enviar_mail` pasó a **async** (mismos params, los 3 callers ganaron `await`); nueva `enviar_mail_raise -> str` que levanta `ResendError` en 4xx/5xx. Modo MOCK si falta `RESEND_API_KEY`. Verificado en prod end-to-end: dispatcher de encuestas → envío `id=3` (que tenía 2 intentos fallidos bajo SMTP) pasó a `enviada`, mail recibido OK. Detalle en §42 CLAUDE.md.

**Dos quirks que costaron tiempo en la migración:**
- **Remitente `@zaris.com.ar` (raíz), NO `@send.zaris.com.ar`.** El subdominio da 403 `not authorized to send from send.zaris.com.ar` — lo verificado en Resend es el dominio raíz (el subdominio es solo Return-Path interno de SES). El `from` debe ser EXACTAMENTE el dominio verificado.
- **pydantic-settings en `extra_forbidden` por default** (esta versión): al borrar `SMTP_*` del modelo, el backend NO arranca mientras `.env.local`/Railway aún las tengan. Fix: `extra = "ignore"` en el `Config`. Cazado al importar el módulo.
- El `message_id` de Resend NO se persiste en DB — vive solo en logs (`email enviado (Resend): ... message_id=...`).

**Para diagnosticar fallos de mail en prod:** el `error=` real solo está en los logs de Railway (Deploy Logs, filtro `email AND fallo`, logger `zaris.email`). NO hay acceso por MCP a logs/vars/deploys de Railway — pedirle al usuario que los pegue. NO inventar. Relacionado: [[feedback_verificar_env_vars_railway]], [[project_railway_caido_2026-05-19]].
