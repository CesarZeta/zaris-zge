---
name: feedback_guard_subarea_cubre_todas_las_vias
description: Un guard de autorización aplicado solo a un atajo del FSM deja abierta la vía normal. Cubrir todas las rutas que llegan al mismo estado.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 36788751-bb5e-4f15-9590-bd49e399b804
---

En reclamos, el guard de subárea (`_validar_cierre_directo_sin_ot`) solo se ejecutaba en el atajo `Sin asignar → Resuelto`. Pero un reclamo ya en `En gestión` podía pasar a `Resuelto`/`En auditoría` por la vía normal del FSM **sin** chequear subárea — un supervisor de subárea 3 cerraba un reclamo de subárea 4. El bloqueo era ilusorio: protegía una ruta y dejaba otra abierta al mismo estado final.

Fix: helper `_require_misma_subarea` aplicado también al pase manual a Resuelto/En auditoría (admin nivel 1 exento). Clave: el cierre vía OT (`ordenes_trabajo.py`) actualiza `reclamos.estado` directamente, NO pasa por `cambiar_estado`, así que el flujo de auditoría legítimo no se rompe — verifiqué con grep que no hubiera otro camino afectado antes de agregar el guard.

**Why:** cuando hay varias transiciones que llegan al MISMO estado sensible (atajo + grafo normal + endpoint de OT), un guard puesto en una sola es falsa seguridad. Es pariente de [[feedback_guard_nivel_endpoint_no_solo_ui]] (UI vs backend) pero a nivel de rutas internas del backend.

**How to apply:** al restringir "quién puede llevar X a estado final", enumerá TODAS las rutas que producen ese estado (grep del estado destino en los handlers) y poné el guard donde convergen o en cada una. Antes de agregar el guard, confirmá que no rompe rutas legítimas (ej. la OT que cierra por construcción ya pertenece a la subárea). Caso real 2026-05-25.
