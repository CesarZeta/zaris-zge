---
name: feedback_sintoma_usuario_no_es_diagnostico
description: "El síntoma que reporta el usuario (\"no se cierra\") no es el diagnóstico. Verificar el estado base (display computado, hidden, valor real) ANTES de codear el mecanismo que el síntoma sugiere."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 66522a61-0d0e-4607-85b4-d5e52d067515
---

Cuando el usuario reporta un comportamiento ("el panel no se cierra"), ese es el **síntoma**, no la causa. Verificar el estado real del elemento ANTES de asumir qué mecanismo está roto.

**Why:** Sesión 2026-05-20 — el usuario dijo "la ventana de notificaciones no se cierra". Asumí literalmente que el problema era el *cierre* y gasté 3 commits (`081929f`, `08bb47d`) en overlays, listeners de iframe y stacking-context, todos verificados como "funcionan" en mi navegador integrado. El bug real: el dropdown **nunca estuvo oculto** — `display:flex` pisaba el atributo `hidden` ([[reference_css_display_pisa_hidden]]). Lo destrabó el usuario con "cuando entro a la página ya está abierto". Un `getComputedStyle(dd).display` + `dd.hasAttribute('hidden')` al primer reporte lo hubiera cazado en 30 segundos.

**How to apply:** ante "X no se cierra/abre/aparece/oculta", el primer paso es leer el estado computado real:
- `getComputedStyle(el).display` vs `el.hasAttribute('hidden')` vs `el.hidden` — ¿coinciden? Si el atributo dice oculto pero el display dice visible, el CSS pisa al atributo.
- `el.getClientRects().length` — ¿está realmente en el layout?
- `document.elementFromPoint(x,y)` — ¿qué elemento recibe el click en ese punto?

Recién con el estado base confirmado, decidir qué mecanismo arreglar. Pista extra: si el MISMO síntoma ya lo arreglaste en otro componente esta sesión (el badge), sospechá que es el mismo bug antes de inventar una causa nueva. Ver [[feedback_leer_dom_antes_de_declarar_bug]].
