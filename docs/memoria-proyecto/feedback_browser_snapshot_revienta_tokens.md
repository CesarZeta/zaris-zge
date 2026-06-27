---
name: browser-snapshot-revienta-tokens
description: browser_snapshot en páginas grandes excede el límite de tokens — default a browser_eval con queries puntuales
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 60476c25-6910-4b32-b3ff-d508b6a4040f
---

`mcp__integrated-browser-mcp__browser_snapshot` en páginas con mucho contenido (grillas, listas largas, módulos del shell) **excede el límite de tokens** y devuelve el resultado volcado a un archivo en vez de inline — inutilizable para decidir el próximo paso.

**Why:** sesión 2026-05-14 jornada 4 — `browser_snapshot` sobre la página de slots de Turnos autoservicio devolvió ~233k caracteres y reventó el límite. Tuve que pivotear a `browser_eval`.

**How to apply:** para verificación visual con browser MCP, el orden de preferencia es:
1. **`browser_eval`** con una expresión chica que devuelva datos estructurados — clickear un botón por texto, leer el valor de un input, contar elementos, extraer el estado mostrado. Es lo más rápido y barato.
2. **`browser_screenshot`** cuando importa la verificación visual real (layout, estilos, que algo se renderiza).
3. **`browser_snapshot`** SOLO en páginas chicas (un modal, un form aislado). En páginas del shell completo o con listas largas, evitarlo.

Patrón útil para clickear sin selectores frágiles:
```js
(() => {
  const btn = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Acreditar');
  if (!btn || btn.disabled) return 'no clickable';
  btn.click();
  return 'clicked';
})()
```

Complementa [[feedback_browser_mcp_que_si_funciona]] y [[feedback_browser_mcp_react_setup]].
