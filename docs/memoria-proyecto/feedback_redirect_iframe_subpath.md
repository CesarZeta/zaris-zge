---
name: redirect-iframe-subpath
description: "window.location.href = '/foo' desde un bundle React embebido en iframe del shell salta a la raíz del dominio y rompe en GH Pages bajo /zaris-zge/. Calcular el subpath desde window.parent.location.pathname antes de redirigir."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 76abb031-f1fc-41a4-97a8-16b043ddea10
---

Cualquier redirect absoluto (`window.location.href = '/login'` u otros) desde el bundle React **no funciona en producción** porque en GH Pages el shell vive bajo `/zaris-zge/...`. El redirect salta a `cesarzeta.github.io/login` (sin el subpath) y muestra el 404 genérico de GitHub Pages **dentro del iframe**, dejando el shell padre intacto.

**Why:** la base path `/zaris-zge/` solo existe porque Pages sirve un repo, no un dominio dedicado. El runtime del bundle no sabe que está bajo un subpath salvo que se lo digamos.

**How to apply:**
- En `web-app/src/lib/api.ts` y cualquier otro lugar del bundle React que redirija ante 401/sesión expirada, detectar si estamos en iframe y leer el subpath del parent:
  ```ts
  if (typeof window !== 'undefined' && window.self !== window.top) {
    const subpath = window.parent.location.pathname.match(/^\/[^/]+\//)?.[0] ?? '/'
    ;(window.parent as Window).location.href = subpath + 'frontend/login.html'
  } else {
    window.location.href = '/login'  // standalone dev (localhost:5173)
  }
  ```
- Cuando edites cualquier `window.location.href = '/...'` del bundle, hacelo iframe-aware aunque hoy no se gatille — el día que se gatille, vas a ver un 404 raro y vas a tardar en relacionarlo.
- **Síntoma diagnóstico clave:** el shell vanilla se ve OK (topbar + sidebar normales) pero el iframe muestra "There isn't a GitHub Pages site here." con logo de GitHub. Eso siempre es un redirect que saltó del subpath.
- Caso real cazado 2026-05-13 cuando dashboard pasó a ser home (commit `d028e3e`). Con welcome.html como home no se notaba porque no hacía requests al backend → nunca se gatillaba 401 → nunca se gatillaba el redirect malo. Bug latente desde sub-fase B5.

Relacionado: [[feedback_guard_sesion_en_head]] (la otra mitad del fix), [[project_zustand_persist_session_shape]] (shape del session), [[feedback_diagnosticar_redirect_login]] (cómo diagnosticar redirects mal en web-app).
