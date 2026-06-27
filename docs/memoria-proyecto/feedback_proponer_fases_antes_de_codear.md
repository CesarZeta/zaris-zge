---
name: proponer-fases-antes-de-codear
description: "Cuando el usuario pide algo full-stack ambicioso (DB + backend + 3 vistas), proponer fases con AskUserQuestion ANTES de tirar código. Funcionó en B1 Agenda."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1a59de23-b5dc-4929-a71b-47033fecf69e
---

Cuando el usuario pide una funcionalidad que cruza varias capas (DB + backend + frontend + UX nueva) y el alcance excede una sesión razonable:

**Regla**: ANTES de escribir cualquier archivo, hacer:
1. Verificar estado real (schema prod, código actual) — capturar las brechas concretas.
2. `AskUserQuestion` ofreciendo 3-4 niveles de alcance ordenados por profundidad.
3. Recién con el alcance acordado, escribir TodoWrite con tareas concretas y arrancar.

**Why**: en sesión 2026-05-13 (vista agenda agente/equipo/lugar atendido/desatendido + 3 vistas switcheables), el pedido inicial habría sido ~5-7 días de trabajo. Proponiendo "Frontend only / Full stack mínimo / Full stack completo + reservas en grilla / Fase 1A mínima" con sus trade-offs el usuario eligió "Full stack completo" pero después aceptó voluntariamente "Fase 1: backend hoy, frontend próxima sesión". Entregué backend B1 cerrado y deployado en una sesión.

**Sin esa fase de alineación inicial**: habría empezado a codear el frontend asumiendo schema/endpoints que no existían, o el backend completo sin separar fases, ambos terminan en sesión inconclusa con código a medias.

**How to apply**:
- Pedido full-stack que abarca varias capas → preguntar alcance.
- Pedido que requiere 4+ migraciones → preguntar si el usuario quiere todo de un tirón o por fases.
- Pedido con UX nueva (vistas, modales, flujos) → preguntar si quiere ver datos primero (backend) o UI primero (con stubs).
- Pedido chico/aislado → NO preguntar, ejecutar.

**Pregunta canónica para alcance grande**:
- "Frontend-only con stubs" (rapidez visual, deuda de schema)
- "Mínimo viable" (lo pedido en su versión más chica)
- "Completo + features adyacentes" (lo pedido + nice-to-haves)
- "Fase 1A: solo X" (cierre temprano con valor parcial)

**No preguntar solo el alcance — también el MODELO.** Un ítem de la bitácora `project_estado_sesion_y_pendientes` es una hipótesis de hace días, NO una especificación — aunque lo haya escrito yo mismo. Sesión 2026-05-14 jornada 3: el pendiente de Turnos decía "usa `ocupaciones` directamente, no necesita tabla nueva" y el usuario eligió tabla propia + ocupación espejo; el pendiente de Agenda backoffice decía "filtros por área/lugar" y el usuario lo reencuadró como un modelo por rol (vista Equipos→OT scopeada a la subárea del supervisor). En ambos casos el `AskUserQuestion` previo a codear cazó la divergencia. Si el pendiente describe *cómo* hacer algo (modelo de datos, qué tabla, qué relación), tratá ese "cómo" como propuesta a confirmar, no como dado — sobre todo si la bitácora tiene varios días.

Relacionado: [[feedback_calibrar_alcance_migracion]] (calibrar wc -l antes de prometer migración), [[feedback_verificar_forms_navegando_mandatorio]].
