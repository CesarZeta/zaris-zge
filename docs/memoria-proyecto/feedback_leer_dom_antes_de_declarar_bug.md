---
name: leer-dom-antes-de-declarar-bug-visual
description: "Si un selector visual (regex en innerText, queryAll filtrado) muestra \"falta X de los 4 esperados\", leer el DOM bruto ANTES de decir \"bug\". Falsa alarma frecuente por matching incompleto."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 730ba002-bb4e-4ffc-a6c4-7067ae9362ab
---

Cuando hago verificación visual con `browser_eval` y un filtro tipo:
```js
const pills = Array.from(document.querySelectorAll('button'))
  .filter(b => /agentes|equipos|espacios/i.test(b.textContent || ''))
```

y devuelve menos elementos de los esperados, **NO concluir bug inmediatamente**.

**Why:** Es muy común que el match falle por:
- Label abreviado: "Esp. atendidos" no matchea `/espacios/`.
- Label en otro idioma o con acentos: "Día" vs "dia".
- Texto en hijo anidado: el span del badge tiene el número pero no la palabra clave.
- Whitespace que rompe el regex `^pattern$`.

**How to apply:**
Antes de declarar "bug, faltan pills":
```js
// Listar TODOS los botones, sin filtro, para inspeccionar etiquetas reales
Array.from(document.querySelectorAll('button')).map(b => (b.textContent||'').trim()).filter(t => t.length > 0)
```

Eso revela el set real y permite ajustar el regex. Recién después, si los elementos esperados no están, sí declarar bug.

Caso real sesión 2026-05-14 (verificación visual B2 Agenda): regex `/agentes|equipos|espacios/i` matcheó solo "Agentes" y "Equipos" porque los labels reales eran "Esp. atendidos" y "Esp. desatendidos" (abreviado). Casi escribí en CLAUDE.md que faltaban 2 pills. Dump del DOM completo reveló que las 4 estaban OK. ~3 min perdidos persiguiendo bug inexistente.

**Para tests de smoke en general:** si un selector "no encuentra X esperado", **dudar del selector antes que del código bajo test**.
