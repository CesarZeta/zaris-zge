---
name: feedback_misma_magnitud_dos_endpoints_diverge
description: "Cuando dos endpoints/funciones calculan la MISMA magnitud de negocio por su cuenta, divergen en silencio. Al auditar un circuito, comparar qué muestra cada superficie ANTES de creer que 'ya funciona'."
metadata:
  node_type: memory
  type: feedback
  originSessionId: daed0e04-a29f-4421-b911-2c1951371b90
---

Bug central de la auditoría de OT/Agenda (2026-06-15): la "disponibilidad de un equipo" se calculaba en **dos lugares con lógicas distintas** — `services/agenda.py::disponibilidad_efectiva('equipo')` (grilla de Agenda) leía el **horario propio** del equipo; `ordenes_trabajo.py::_slots_libres_recurso('equipo')` (planificador de OT) hacía la **unión de los horarios de los agentes**. Para la misma cuadrilla la grilla mostraba 08–15 y el planificador ofrecía 08–16; una cuadrilla sin horario propio pero con agentes salía **toda gris en la agenda** pero igual recibía OT. Nadie lo notó porque cada pantalla, por separado, "se veía bien".

**Why:** una magnitud de negocio (disponibilidad, SLA, saldo, cupo, estado derivado) que se recalcula independientemente en N puntos es una divergencia latente: basta que alguien toque uno y no el otro. El síntoma no es un error — son dos números que no coinciden, y solo se cae si comparás las superficies lado a lado. La doc puede incluso documentar el comportamiento correcto mientras un endpoint hace otra cosa (acá CLAUDE.md §27 ya decía "unión de agentes" y el código de la grilla hacía horario propio).

**How to apply:**
1. **Al auditar un circuito que cruza módulos, listá QUIÉN calcula cada magnitud y compará los resultados con datos reales** antes de declarar "funciona". No alcanza con que cada endpoint pase su smoke aislado: corré la misma entidad por las dos vías (`/agenda/disponibilidad/efectiva` vs `/ot/slots-recurso`) y verificá que coinciden.
2. **El fix correcto no es "copiar la lógica buena al otro lado", es UNIFICAR en una sola función** y que ambos la llamen. Acá `_slots_libres_recurso('equipo')` pasó a **delegar** en `disponibilidad_efectiva('equipo')` — la duplicación era la causa raíz, no un detalle.
3. **Si hay versión singular Y batch** (perf, [[feedback_patron_batch_helper_singular_wrapper]]), el fix va en LAS DOS o vuelven a divergir. `disponibilidad_efectiva` y `disponibilidad_efectiva_batch` tuvieron que cambiar juntas.
4. Familia de [[feedback_guard_subarea_cubre_todas_las_vias]] (un guard en una sola ruta deja las demás abiertas) y [[feedback_columna_nueva_auditar_todos_los_select]] (tocar todos los SELECT, no uno): **el mismo dato/regla replicado en N lugares exige tocar los N**.

Relacionado: [[project_agenda_espacios_disponibilidad]], [[reference_agenda_semana_disponibilidad_key]].
