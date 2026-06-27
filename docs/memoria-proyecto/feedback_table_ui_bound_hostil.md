---
name: table-ui-bound-hostil
description: "El componente Table de web-app/src/ui exige T extends Record<string, unknown>, lo cual rechaza interfaces normales y obliga a relajar el bound. Patrón para futuros módulos React."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ba8c5bce-d171-4427-a27f-16245ac2b25e
---

El componente `Table<T>` en `web-app/src/ui/index.tsx` tenía bound `T extends Record<string, unknown>`. Cualquier interface estructurada (`EspacioAgenda`, `DisponibilidadRecurso`, `Reclamo`, etc.) **no satisface** ese bound porque TS no agrega index signature implícita a interfaces con campos conocidos.

**Síntoma:** 9 errores TS en una sola pasada de typecheck — `Type 'EspacioAgenda[]' is not assignable to type 'Record<string, unknown>[]'`, `Type 'unknown' is not assignable to type 'ReactNode'`, `(r: Record<string, unknown>) => {} is not assignable to (row: Record<string, unknown>) => ReactNode`.

**Why:** El bound se eligió originalmente para que `row[col.key]` tipara bien sin cast. Pero a costa de aceptar literalmente nada estructurado.

**How to apply:**
- Si vas a usar `Table<T>` con una interface nueva, sabé que vas a tropezar.
- Fix aplicado en sesión 2026-05-13: relajar a `T extends object` y agregar casts `(row as Record<string, unknown>)[col.key as string]` dentro del render por defecto. Las custom `render: (r) => ...` no necesitan cast porque `r: T` ahí.
- Si en otro módulo vuelve a aparecer un bound similar (`extends Record<string, unknown>` o `extends { [k: string]: any }`), no luches con el cast en cada call site — relajá el bound en la implementación una sola vez.
- Promovible: cuando aparezca el quinto consumer del Table, vale considerar tipar `column.key as keyof T` estrictamente y devolver `unknown` cast a ReactNode explícito.

Caso real: B2 Agenda (commit pendiente, sesión 2026-05-13). EspaciosConfig + DisponibilidadConfig fallaron typecheck por esto.

Relacionado: [[feedback_calibrar_alcance_migracion]] (subestimar typecheck cost), [[feedback_proponer_fases_antes_de_codear]] (verificar realidad incluye verificar bound de componentes UI).
