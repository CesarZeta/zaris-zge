---
name: feedback_token-local-contra-dist-prod-nuke-sesion
description: Testear shell local + dist prod — el bundle pega a Railway con token local → 401 nukea la sesión y rebota al login. No es un bug del producto.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 04178f32-afff-4440-9a12-b965fa04d482
---

Al verificar en `localhost:8080` el shell vanilla con el **dist buildeado en modo prod**, el bundle React llama a **Railway** (`VITE_API_BASE` prod) con un token firmado por el **backend local** (SECRET_KEY distinta) → 401 → el handler de `web-app/src/lib/api.ts` hace `localStorage.removeItem('zaris_session')` y redirige el parent a `frontend/login.html`. Parece "la sesión se borra sola / rebota al login" pero es un artefacto del entorno mixto (cazado 2026-06-12, costó ~10 min de diagnóstico).

**Why:** el dist comiteado SIEMPRE apunta a Railway (regla §32); el login local emite tokens que prod rechaza.

**How to apply:** para probar la integración shell+iframe en local, loguear contra la **API prod** y sembrar `zaris_session` con ese token (ambas shapes §29 — solo el plano no hidrata zustand y el AppShell muestra su LoginPage). El shell (menu.js → API local) fallará fail-open en /me, sin romper. Las features solo-shell (statusbar, dropdown, tema) se pueden verificar con cualquier sesión. Relacionado: [[feedback_diagnosticar_redirect_login]], [[project_zustand_persist_session_shape]].

**Patrón sesión HÍBRIDA (cuando necesitás los DOS entornos vivos a la vez):** si la pantalla a probar/capturar es VANILLA y pega a la API local (`frontend/admin_tablas.html`, `usuarios.html`) PERO el iframe default carga el dashboard React (que pega a Railway), un solo token mata al otro entorno. Armar **una sola key `zaris_session` con cada forma apuntando a un entorno distinto**: `access_token`/`user` (shape plana, la que leen los módulos vanilla) con el token LOCAL, y `state.accessToken`/`state.user` (la que lee zustand/React) con el token PROD. Así el vanilla autentica local y el React autentica prod sin 401 cruzados. Cazado 2026-06-12 capturando la sección de franjas de Agentes para el manual de Agenda.
