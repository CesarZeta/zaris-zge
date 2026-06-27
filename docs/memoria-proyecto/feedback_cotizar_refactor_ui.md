---
name: cotizar-refactor-ui
description: "Antes de prometer \"X horas\" para migrar CSS/HTML legacy, abrir el archivo definitorio (styles.css, design-system, etc.) y mirar si es alias-thin o componentes-thick. Conteo de ocurrencias miente."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 018adadb-6bb9-4190-af10-c4b4dfb651d1
---

**Regla:** antes de cotizar un refactor de estilos UI ("renombrar `--z-*`", "migrar `.z-btn`", "borrar `styles.css`"), **abrir el CSS al que se apunta a migrar/borrar** y medir el alcance real, no el conteo de ocurrencias en HTMLs.

**Why:** sesión 2026-05-12 ofrecí "§31 pasos 4-6: 4-5h, low risk" basado en ~500 ocurrencias de `var(--z-*)` y `.z-*` en 5 HTMLs. Cuando finalmente abrí `frontend/styles.css` (838 líneas), eran ~30 clases con CSS propio (`.z-btn` con 5 variantes, `.z-card`, `.z-modal`, `.z-input`, `.z-toast`, `.z-spinner`, `.z-badge`, etc.) que el DS nuevo NO tiene. Migrar es **reescribir componentes**, no renombrar variables. Alcance real: 6-8h con riesgo medio de regresión visual, o sesión enorme dedicada. Pasé de "low risk, andar a hacer" a "documentar y diferir" en 5 minutos de lectura.

**How to apply:**
- "Renombrar `--var`": alias-thin, suele ser rápido. Confirmar leyendo el archivo que define las variables.
- "Borrar/migrar clase `.foo`": componente-thick, si la clase tiene CSS propio en algún lugar, migrar significa reescribir. **Abrir ese archivo antes de cotizar.**
- "Migrar HTML al DS nuevo": leer 1-2 archivos del DS nuevo (`design-system/colors_and_type.css`, componentes existentes) y 1 archivo del que se migra. Si las clases del legacy NO tienen equivalente listo, el costo se multiplica.
- Cuando descubrís que el alcance era mayor del cotizado, **decirlo explícitamente** ("subestimé") y proponer estrategias con costos honestos en lugar de seguir adelante con el plan original.

Patrón inverso útil: si vas a estimar "rápido y sin riesgo", buscar el archivo que materializa el sistema viejo (el que define las clases/variables que querés borrar). Si tiene 50 líneas → rápido. Si tiene 500+ → planificar.

Vinculado: [[verificar-drift-completo-prod]] tiene el mismo espíritu — abrir la fuente real antes de actuar, no confiar en señales indirectas.
