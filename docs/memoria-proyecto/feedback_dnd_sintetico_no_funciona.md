---
name: dnd-sintetico-no-funciona
description: PointerEvent sintetico (dispatched desde JS) no activa el PointerSensor de @dnd-kit porque setPointerCapture requiere isTrusted=true. No intentes probar drag programaticamente.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a511bbae-7e29-4cf5-a153-a13a6c1bd56c
---

@dnd-kit usa `setPointerCapture` internamente, que solo funciona con eventos `isTrusted=true`. Los eventos creados con `new PointerEvent(...)` y `dispatchEvent(...)` tienen `isTrusted=false`. El sensor nunca dispara `onDragStart` aunque pongas la secuencia perfecta de `pointerdown → pointermove(>5px) → pointerup`.

**Why:** descubierto en sesion 2026-05-12 al intentar verificar el drag de OT a hora exacta via `browser_eval` + dispatchEvent. La secuencia no fallaba (no tiraba error), simplemente no pasaba nada — no aparecia el `ConfirmModal` esperado y no se creaba la ocupacion. Despues lo confirmo el usuario probando manualmente: con el mouse real funciono al primer intento.

**How to apply:**
- Para probar drag en @dnd-kit hay dos opciones: (1) drag fisico real del usuario, (2) tests con Playwright/Cypress que tienen drivers nativos del navegador.
- `browser_eval` con dispatchEvent NO sirve para verificar dnd-kit.
- Si necesitas verificar la logica sin hacer drag, podes:
  - Invocar directamente las mutations (`useDragMutations.crearDesdeOT.mutate(...)`) desde el componente y mockear el state — no es testing real pero valida la rama.
  - Inspeccionar el DOM y atributos (`aria-roledescription`, `cursor`, `tabIndex`, props del componente) para confirmar que el draggable esta correctamente configurado.
  - Pedirle al usuario que haga el drag y mirar el resultado en DB / network.

Caso real: cuando se quiso validar item "drag de OT a hora exacta" se intento 1 simulacion sintetica → no respondio → se documento como "pendiente prueba humana". El usuario hizo el drag manual y mando screenshot → funcionaba perfecto. Lo programatico nunca iba a andar.

Para drag de bloque existente (entre filas, dentro de la misma fila) misma regla: solo se prueba manualmente o con E2E real.
