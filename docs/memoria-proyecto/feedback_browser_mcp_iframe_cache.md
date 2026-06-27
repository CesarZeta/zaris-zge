---
name: browser-mcp-iframe-cache
description: "browser-MCP cachea iframes agresivamente. Aunque Pages sirva el bundle nuevo, el iframe puede mostrar el viejo. Forzar reload con cache-bust."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d16859d3-5cdd-4a02-80e5-3f70b79c7db3
---

Cuando hago smoke con browser-MCP de un módulo embebido en iframe (shell vanilla → `/web-app/dist/index.html#/...`), el iframe puede seguir mostrando el bundle **anterior** aunque GH Pages ya sirva el nuevo. La página padre tiene el HTML actualizado, pero el iframe carga el JS cacheado.

**Why:** browser-MCP corre sobre Chromium con cache HTTP estándar. GH Pages además tiene CDN cache que tarda 30-60s. Si comparás `<script src>` en el HTML servido vs el bundle que ejecuta el iframe, ves dos hashes distintos.

**How to apply:** después de pushear un cambio al bundle React + esperar ~60s para GH Pages, **fuerzo reload del iframe con cache-bust** antes de verificar:

```js
// browser-MCP eval
(async () => {
  const frame = document.getElementById('module-frame');
  const url = new URL(frame.src);
  url.searchParams.set('_t', Date.now().toString());
  frame.src = url.toString();
  await new Promise(r => setTimeout(r, 5500));
  // ahora verificar contenido
})()
```

**Síntoma típico:** verifico HTML servido por Pages con `curl` y dice `index-XYZ.js`. browser-MCP eval me reporta `iframeBundleScripts: ['index-ABC.js']` (viejo). Si lo veo, **no es bug del deploy** — es cache del iframe. Sesión 2026-05-12 jornada 4 perdió 5 min debuggeando esto antes de cachear-bustear el iframe.

**Alternativa:** `browser_navigate` a una URL con query distinta (ej `&cb=20260512b`) fuerza re-fetch del HTML padre, pero el iframe interno sigue cacheado si el browser lo considera idéntico. La técnica del `_t` directo sobre `frame.src` es la única confiable.

## Variante: el bundle cacheado apunta a OTRO entorno

Cazado 2026-05-14. Síntoma distinto al de arriba pero misma causa raíz (cache del bundle): testeando el shell vanilla + bundle en **local** (proxy 8090), el login rebotaba inexplicablemente — POST `/auth/login` daba 200, `setItem` corría, pero la sesión desaparecía y volvía a `login.html`.

**Causa:** el `dist/` commiteado estaba compilado contra **Railway prod**. Rebuildeé contra local (`vite build --mode development`) pero el browser seguía sirviendo el `index.html` del dist **cacheado**, que referenciaba el JS viejo apuntado a prod. El iframe montaba el módulo React → hacía requests a **prod** con un token de la **DB local** → 401 → el handler de 401 borraba `zaris_session` y redirigía. Se ve idéntico a "el login no funciona" pero es "el bundle pega al backend equivocado".

**Cómo detectarlo:** ante un rebote de login inexplicable con `browser_network`, mirá **a qué host pegan las requests del iframe** (`zaris-api-production` vs `127.0.0.1:8000`), no solo si el login dio 200. Si el bundle pega a un entorno distinto del que estás testeando, es cache — no bug.

**Fix:** rebuildear el dist apuntando al entorno correcto + cache-bust en la URL de navegación (`?_t=...`) + `localStorage.clear()` antes de reloguear. El proxy local (`_serve_local_pages.py`) no manda headers no-cache, así que el browser reusa bundles viejos agresivamente — ver [[project_proxy_local_zaris_zge]].

Relacionado: [[feedback_verificar_runtime_antes_de_agente]] (verificar runtime, no solo código), [[feedback_rebuild_dist_working_tree_limpio]] (qué compila Vite), [[project_proxy_local_zaris_zge]].
