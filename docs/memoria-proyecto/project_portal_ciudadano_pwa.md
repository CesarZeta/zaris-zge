---
name: project-portal-ciudadano-pwa
description: "PWA zaris-vecinos = 'Portal del Ciudadano' (repo separado, Vercel). Etapas A-E cerradas al 2026-06-12: reclamos con fotos+pin, emergencias, turnos, entradas con QR, push. Shape de sesión propio, NO el de zaris_session."
metadata: 
  node_type: memory
  type: project
  originSessionId: 24bcb12b-67b1-4877-bced-dfe51f3d7df3
---

La PWA `zaris-vecinos` (repo `CesarZeta/zaris-vecinos`, Vercel `vecinos.zaris.com.ar`, branch `main`) se llama **"Portal del Ciudadano"** (decisión del usuario 2026-06-02; constante `src/lib/app.ts`, manifest, `<title>`). Apunta a la API de Railway (`VITE_API_URL`). React 19 + Vite 6 + react-router-dom 7 (`BrowserRouter`, no hash — Vercel sí soporta HTML5 routing). `vite-plugin-pwa` con SW (ver [[feedback_pwa_service_worker_sirve_build_viejo]]).

**Estado al 2026-06-12 (etapas A-E del plan CERRADAS; último commit `2f5ab4c`):**
- **Auth completo** (scope `publico`, §38): Login (DNI+pass), Activar (`/activar?token`), Recuperar (anti-enumeración), Resetear. `RutaProtegida` + `SoloInvitado`; `/me` valida al entrar. SIN completar-ficha (alta en un paso fuera de la app, 2026-06-12).
- **Flujo logueado completo**: Home (`/inicio`, mi-resumen con conteos reales de los 4 dominios + acceso a `/configuracion`) · Reclamos (lista/detalle/alta con fotos cámara-galería máx 5 + MapaPicker Leaflet pin + geocoding) · Emergencias (`/emergencias`, reporte + mis reportes) · Turnos (`/turnos`, reserva 2 pasos + cancelar) · **Entradas (`/entradas` + `/entradas/eventos`: cartelera con cupo, reserva, QR en pantalla con lib `qrcode`, cancelar — etapa D)** · **Push (`/configuracion`: toggle Web Push; `public/sw-push.js` importado por el SW vía workbox.importScripts; `lib/push.ts` con timeout sobre serviceWorker.ready — etapa E)**.
- **README del repo** tiene el checklist completo para replicar en municipio #2 (branding, geo_bbox, claves VAPID propias, env vars, CORS, verificación E2E).

**Shape de sesión PROPIO** (NO el `zaris_session` del shell ZGE): `localStorage['zaris_vecino_session']` = `{ access_token, ciudadano }` plano. `src/lib/api.ts` lo lee para el Bearer; `src/lib/session.ts` es el store reactivo (`useSyncExternalStore`).

**Endpoints backend que consume** (todos `/api/v1/publico/*`, scope publico): `auth/*`, `reclamos` (+`/adjuntos` y `/geo/buscar`), `emergencias`, `turnos` (+ catálogo anónimo `turnos/publico/prestaciones|slots`), `entradas` (cartelera/reservar/cancelar), `push` (public-key/subscribe/unsubscribe), `portal/mi-resumen`, `identidad-municipio`. Ver [[reference_geocoding_vecino_endpoint_scope_publico]].

**NO incluye (decisión vigente)**: cambiar estado / cancelar reclamo propio. El autoregistro vive en el shell ZGE (`frontend/alta-vecino.html`), NO en esta PWA (§38).

**Pendiente del usuario (no de código)**: prueba en Android real — fotos+pin (etapa A) y entrega del push con la app cerrada (etapa E; el navegador embebido de VS Code no tiene push service, no se puede verificar desde acá). Vecino demo: local DNI <DNI-DEMO> / prod <DNI-DEMO> (pass <PASS-DEMO>). Ver [[project_usuario_vs_ciudadano_modelo]].
