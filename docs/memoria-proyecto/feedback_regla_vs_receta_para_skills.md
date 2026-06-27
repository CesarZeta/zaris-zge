---
name: feedback_regla_vs_receta_para_skills
description: Criterio para decidir qué va a CLAUDE.md (regla) vs a una skill (receta)
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1965dc04-f954-4e6c-8bf6-1a05e8e8faf6
---

Al optimizar CLAUDE.md (sesión 2026-05-31/06-01, 272KB→184KB) el usuario aprobó este criterio para decidir qué sale del prompt base a una skill y qué se queda:

- **Regla de criterio** = gobierna decisiones que tomo SIN invocar nada (ej. "nunca tabla propia de personas, usá la BUC §2"; "createHashRouter, nunca createBrowserRouter §12"; "verificar drift en prod antes de codear backend §24"). **Se queda en CLAUDE.md** (prompt base, siempre cargada). Si vive solo en una skill, meto la pata ANTES de acordarme de invocarla.
- **Receta deliberada** = pasos de una tarea que arranco explícitamente (seedear, scaffoldear un módulo, generar un manual, quirks de build/PowerShell). **Puede ir a skill** — carga on-demand, no pesa cada turno.

Hechas así: `win-quirks` (§32), `seed-csv` (§24), `generar-manual` (§36), `nuevo-modulo-react` (§12). En cada una dejé en CLAUDE.md las reglas de criterio + un puntero a la skill, y moví solo las recetas.

**Datos del entorno que confirman el porqué:** un `@import` de Claude Code se expande SIEMPRE (no baja el prompt base — descartado). Una **skill** sí baja el prompt base porque el modelo solo ve nombre+description hasta invocarla. Por eso skills, no imports, para reducir contexto.

**Why:** reduce el contexto sin perder las reglas que previenen errores. **How to apply:** antes de mover algo de CLAUDE.md a skill, preguntarse "¿esto lo necesito ANTES de saber que estoy en esa tarea?". Sí → queda. No → skill. Cuidado con el quirk de render de skills al escribirlas: [[reference_skill_render_expande_dolar_y_cachea]].
