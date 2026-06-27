---
name: feedback-pwa-service-worker-sirve-build-viejo
description: "PWA zaris-vecinos: SW viejo sirve build cacheado (desregistrar+borrar caches) + quirks de SW/push cazados 2026-06-12: dev-vs-preview se distingue por el MIME de /sw.js, serviceWorker.ready nunca rechaza (race con timeout), el browser embebido de VS Code NO tiene push service, y el primer deep-link tras un deploy puede caer al catch-all por la carrera del autoUpdate."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 24bcb12b-67b1-4877-bced-dfe51f3d7df3
---

La PWA `zaris-vecinos` usa `vite-plugin-pwa` con `registerType:'autoUpdate'`, que registra un **service worker con precache de Workbox**. En desarrollo, ese SW de una sesión anterior **intercepta todas las requests y devuelve el `index.html`/bundle cacheado**, ignorando lo que sirve el dev server de Vite. Síntoma exacto cazado 2026-06-02: el browser mostraba "Proximamente" (un componente ya borrado) aunque `fetch('/src/App.tsx')` confirmaba que el server servía el código nuevo.

**Why:** perdí ~6 tool-calls persiguiendo cache de Vite y cache del navegador integrado (maté el proceso, `--force`, pestaña nueva, cache-bust en la URL) cuando el culpable era el SW. La pista decisiva: `navigator.serviceWorker.getRegistrations()` devolvió 1 registro activo (`sw.js`) + `caches.keys()` mostró `workbox-precache-v2-...`.

**How to apply:**
- Si la PWA muestra código viejo y `fetch('/src/Foo.tsx', {cache:'no-store'})` confirma que el server sirve el nuevo → **es el service worker**, no Vite ni el browser. No sigas con `--force` ni cache-bust de URL.
- Fix (vía browser_eval): desregistrar + limpiar caches, luego recargar:
  ```js
  (async()=>{ const rs=await navigator.serviceWorker.getRegistrations(); for(const r of rs) await r.unregister(); const ks=await caches.keys(); for(const k of ks) await caches.delete(k); })()
  ```
- En prod el `autoUpdate` se encarga (el SW nuevo toma en la siguiente visita), pero en dev el SW persiste entre reinicios del server y entre pestañas. Familia del [[feedback_browser_mcp_iframe_cache]] (otra capa de cache que sirve lo viejo).
- Deuda pendiente: convendría desactivar el SW/precache en modo `dev` en `vite.config.ts` (`devOptions.enabled:false` o no registrar en dev) para que esto no vuelva a pasar al iterar.

**Quirks adicionales de SW/push (cazados implementando la etapa E, 2026-06-12):**

1. **¿Quién responde en el puerto 5174: dev o preview?** Probar `GET /sw.js`: el dev server devuelve `text/html` (fallback SPA — el SW solo existe en el build), el preview devuelve `text/javascript`. Cazado: maté el puerto y levanté `pnpm preview`, pero el dev server seguía vivo y el SW "no se registraba" (MIME error). No confiar en que el kill+start funcionó: probar el asset que solo existe en el build.
2. **`navigator.serviceWorker.ready` NUNCA rechaza** — si el SW no llega a registrarse, una página que lo await-ea cuelga para siempre ("Verificando…" eterno). Siempre `Promise.race` con timeout (patrón en `lib/push.ts::swReady`).
3. **El navegador embebido de VS Code (Electron) NO tiene push service**: `Notification.permission` puede estar `granted`, pero `pushManager.subscribe` falla con "push service not available" (sin FCM). La ENTREGA de un push solo se verifica en Chrome real / Android. Verificar todo lo demás (SW activated, toggle, endpoints, estados) y declarar el límite explícito.
4. **Primer deep-link justo después de un deploy puede caer al catch-all** (ruta nueva → `/inicio`) por la carrera del `autoUpdate` del SW: el shell viejo atiende esa navegación y a la vez se actualiza. Re-probar (click o segunda navegación) antes de declarar bug de routing. Familia de "probes durante recarga devuelven fantasmas".
5. **Handlers de push con `generateSW` SIN migrar a injectManifest**: `workbox.importScripts: ['sw-push.js']` (archivo en `public/`) — el SW generado lo importa y el precaching queda intacto.
6. **TS 5.9 + `applicationServerKey`**: `new Uint8Array(n)` tipa `Uint8Array<ArrayBufferLike>` y no es asignable a `BufferSource`; usar `new Uint8Array(new ArrayBuffer(n))`.
