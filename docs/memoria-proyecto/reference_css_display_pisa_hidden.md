---
name: reference_css_display_pisa_hidden
description: "Una clase CSS con display:flex/block pisa el atributo HTML `hidden`; el elemento se ve aunque tenga hidden. Bug recurrente en el shell vanilla."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 66522a61-0d0e-4607-85b4-d5e52d067515
---

El atributo HTML `hidden` equivale a `display:none` **por defecto del navegador**, pero **cualquier regla CSS con `display:` explícito lo pisa por especificidad**. Un elemento con `class="x"` + atributo `hidden`, donde `.x { display:flex }`, **se ve igual** — el `hidden` no tiene efecto.

Síntomas que produce:
- Un elemento que debería arrancar oculto (`<div hidden>`) **aparece visible al cargar**.
- Hacer `el.hidden = true` desde JS **no lo oculta** (el JS está bien, el CSS lo ignora).

Fix: agregar la regla que devuelve la prioridad al atributo:
```css
.x[hidden] { display: none; }
```

**Casos reales en este repo (2026-05-20, MISMO bug dos veces):**
- `.topbar__bell-badge` (badge "0" de notificaciones) — commit `5dfe00c`.
- `.notif-menu__dropdown` (panel de notificaciones que "no cerraba / arrancaba abierto") — commit `fda6c01`.

Ambos en `frontend/css/menu.css`. Si agregás un componente del shell vanilla con `display:flex/grid/block` que también usa el atributo `hidden` para toggle, agregá la regla `[hidden]{display:none}` desde el principio. Ver [[feedback_sintoma_usuario_no_es_diagnostico]].
