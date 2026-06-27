---
name: feedback_git_checkout_destruye_ediciones_sesion
description: "git checkout <archivo> revierte TODO el working tree de ese archivo, incluidas ediciones no commiteadas de la sesión actual — no las \"pausa\". Si el archivo mezcla trabajo a commitear + doc en progreso, se pierden ambas."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4f23e568-0771-4048-bd3c-71fdccc3d3dd
---

`git checkout <archivo>` (o `git restore <archivo>`) **descarta el working tree completo de ese archivo a HEAD**, no solo "lo saca del próximo commit". Si el archivo tiene ediciones de la sesión actual que todavía no commiteaste, **se pierden**.

**Why:** caso real (migración Resend, 2026-05-24). El usuario descartó `CLAUDE.md` con `git checkout` para no commitearlo junto al código backend. Pero CLAUDE.md tenía mis ediciones de §42/§35/§38 documentando la migración — `checkout` las borró todas, volviendo el archivo a estado pre-sesión. Al final tuve que re-aplicarlas desde cero. El usuario pensó que "lo descartaba del commit"; en realidad lo revertía.

**How to apply:**
- Si querés que un archivo NO entre a un commit pero **conservar sus cambios**: NO uses `git checkout`/`git restore`. Simplemente no lo agregues al staging (`git add` solo los otros), o usá `git stash push -- <archivo>` (reversible con `stash pop`).
- `git checkout <archivo>` solo cuando querés genuinamente **tirar** los cambios de ese archivo.
- Cuando el usuario diga "descartá X para no commitearlo", confirmar si quiere **perder** los cambios o solo **excluirlos del commit** — son cosas distintas. Si tenía trabajo mío ahí, avisar antes de que se pierda.
- Tras un `checkout` así, asumir que las ediciones de la sesión a ese archivo se fueron — re-verificar con `grep`/`Read` antes de dar por hecho que siguen.
