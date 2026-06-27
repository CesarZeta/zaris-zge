---
name: feedback_validacion_reactiva_cambios_programaticos
description: Validación de form atada a input/change no se dispara al poblar campos por código; re-evaluar a mano tras cambios programáticos.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 90c78aff-16dc-4a6e-b058-f0b4dbcf4122
---

Un validador reactivo que habilita/deshabilita un botón escuchando eventos `input`/`change` del form **no se re-ejecuta cuando los campos se llenan programáticamente** (setear `el.value = x` por JS NO dispara `input`/`change`). El botón se queda con el estado de la última evaluación real.

**Caso 2026-05-26 (módulo Usuarios vanilla):** `ZValidaciones.bindGuardarBoton(form, btn, {extra})` deja el botón Guardar **gris en modo edición** porque al editar un usuario, `poblarFormulario()` setea los `.value` por código y nunca se vuelve a correr el `check()`. El propio comentario en `frontend/js/validaciones.js:206` ya advertía "Cambios programáticos de campos requieren llamar manualmente al check devuelto" — pero `usuarios.js` descartaba el `{check}` devuelto.

**Why:** los frameworks reactivos basados en eventos del DOM dependen de que el cambio venga de interacción del usuario. El llenado por código (cargar para editar, autofill de password manager, restaurar estado) los saltea silenciosamente. Síntoma típico: "el botón está gris y no entiendo por qué" en una pantalla que abrió ya poblada.

**How to apply:**
- Cualquier helper que devuelva un `check()`/`revalidate()` → capturarlo y llamarlo a mano DESPUÉS de poblar el form, en cada `poblar*/activarModo*`. No descartar el objeto devuelto.
- Si el botón se deshabilita por una regla no obvia (password debe coincidir + 8 chars), mostrar **feedback en vivo** del motivo. Si el botón está gris, el usuario no puede apretarlo para ver el error → círculo vicioso. Patrón usado: pista contextual en el hint del campo (`pistaPassword()` en `usuarios.js`).
- Aplica a `bindGuardarBoton` (hoy único consumidor) y a cualquier validador reactivo futuro. Relacionado con [[feedback_verificar_forms_navegando_mandatorio]] — esto solo se ve abriendo la pantalla, no leyendo el código.
