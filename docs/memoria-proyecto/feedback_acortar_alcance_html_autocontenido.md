---
name: acortar-alcance-html-autocontenido
description: "HTMLs autocontenidos con capturas base64 pesan 1-3MB. Servirlos como archivos en /docs/ + abrir en pestaña nueva, no embeber en iframe ni descargar."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fc045d9c-7164-4f89-9bb2-bbede897fec8
---

Cuando un manual o doc lleva muchas capturas, el HTML autocontenido (base64 inline) puede pesar 1-3 MB. Tres opciones para servirlo, y solo una funciona bien:

| Opción | Pros | Cons |
|---|---|---|
| **Pestaña nueva** | Sidebar + topbar del shell siguen visibles, usuario tiene el doc al lado del módulo | requiere `target=_blank` + URL externa, no integración visual |
| Iframe embedded | "Integrado" visualmente | Pierde sidebar, 1-3 MB pesados de cargar en iframe, scroll anidado feo |
| Download | Funciona offline | Rompe flujo (tiene que abrirlo a mano después), no se puede compartir link |

**Recomendación verificada (sesión 2026-05-18, módulo Guías):** pestaña nueva.

**Why:** los 3 HTMLs (manual_reclamos.html 2.49 MB, manual_ot.html 1.38 MB, manual_admin_tramites.html 1.58 MB) renderizan en <1s en pestaña nueva. En iframe se notaba lag visible y el usuario perdía contexto del módulo activo.

**How to apply:**
1. Los HTMLs van a `docs/` (GH Pages los sirve directo).
2. El componente que linkea usa `<a href="..." target="_blank" rel="noopener noreferrer">`.
3. URL se arma con helper `urlDocs(htmlName)` que detecta iframe vs standalone y resuelve correcto.

**Helper `urlDocs()` pattern** (ver `web-app/src/modules/guias/pages/GuiasIndex.tsx`):
```ts
function urlDocs(htmlName: string): string {
  if (typeof window === 'undefined') return `/docs/${htmlName}`
  // Caso 1: dentro de iframe (prod o local 8080) → window.parent.location
  if (window.self !== window.top) {
    try {
      const parentLoc = window.parent.location
      const base = parentLoc.pathname.replace(/[^/]*$/, '')
      return `${parentLoc.origin}${base}docs/${htmlName}`
    } catch { /* cross-origin: fallback */ }
  }
  // Caso 2: standalone localhost:5173 → apunta al shell vanilla local
  if (window.location.hostname === 'localhost' && window.location.port === '5173') {
    return `http://localhost:8080/docs/${htmlName}`
  }
  // Caso 3: standalone otros (degenerado)
  return `${window.location.origin}/docs/${htmlName}`
}
```

**Para sumar manuales:** generar `docs/manual_X.html` con el patrón Playwright + base64 + agregar entrada al array `GUIAS` en `GuiasIndex.tsx`. No requiere tocar manifest, sidebar ni typecheck.

Relacionado: [[feedback_screenshots_no_persisten_browser_mcp]] (cómo generar las capturas).
