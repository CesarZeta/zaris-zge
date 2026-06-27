---
name: feedback-diff-claude-md-acumulado
description: "Al hacer `git status` después de tocar CLAUDE.md, verificar si el diff incluye solo TU cambio o también doc atrasada de sesiones previas. Si hay mezcla, dos commits separados — `feat(X)` para tu cambio + `docs(claude-md)` para la deuda doc."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8a7ed55b-b83e-4f0a-a792-52d4f2df39fc
---

**Why:** CLAUDE.md acumula doc entre sesiones sin commit. Cuando una sesión agrega 5 líneas al §X, el `git diff CLAUDE.md` muestra esas 5 líneas + las 100+ líneas de §Y/§Z que las sesiones de la semana pasada escribieron pero nunca commitearon. Si commiteás todo junto bajo `feat(X)`, mezclás scope y el historial pierde precisión: alguien buscando "cuándo se documentó §Y" cae en un commit que dice "fix path quirk".

**Cazado sesión 2026-05-19:** mi cambio de §34 eran 4 líneas (admin bypass es_auditor); el diff total de CLAUDE.md eran ~165 líneas con §35-37 atrasadas (editor admin tipos, manuales operativos, módulo Guías) de los commits `65b6ac2`/`de79331`/`5fd72b9` pusheados días antes.

**How to apply — protocolo al commitear CLAUDE.md:**

1. `git diff CLAUDE.md | wc -l` antes de stagear.
2. Si > 30 líneas y tu cambio es chico: leer el diff completo. Probable mezcla.
3. Si hay mezcla:
   - `git stash push -m "doc-atrasada" -- CLAUDE.md`
   - Re-aplicar SOLO tu cambio chico (Edit puntual sobre CLAUDE.md).
   - `git add CLAUDE.md` + tus otros archivos → commit 1 `feat(X)`.
   - `git stash pop` → ahora diff trae solo lo atrasado → commit 2 `docs(claude-md): documentar X / Y / Z atrasadas`.
4. Push ambos juntos.

**Costo:** 30-60s extra. Ganancia: historial limpio + commits diferenciables.

**Alternativa si los cambios son entrelazados** (mi cambio en §35 mezclado con doc atrasada del mismo §35): commit único pero con mensaje que reconozca el alcance — `feat(X) + docs: atrasos §35-37`.

**Patrón inverso a evitar:** "para qué separo, total es solo doc". No — la doc es contrato. Mezclarla con código hace harder revertir uno sin el otro.
