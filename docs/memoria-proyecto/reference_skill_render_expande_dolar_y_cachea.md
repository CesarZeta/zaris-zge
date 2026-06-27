---
name: reference_skill_render_expande_dolar_y_cachea
description: "Al escribir SKILL.md, el render expande $1/$VAR (los come) y cachea el cuerpo por sesión"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 1965dc04-f954-4e6c-8bf6-1a05e8e8faf6
---

Dos quirks del motor de skills de Claude Code, cazados al crear las skills de ZARIS (win-quirks, seed-csv, etc.) el 2026-06-01:

1. **El render de un `SKILL.md` expande secuencias tipo `$1`, `$2`, `$VAR` como variables de shell ANTES de mostrar el cuerpo.** Un literal `$1` (placeholder posicional de asyncpg) quedó como cadena vacía → el snippet `WHERE LOWER(nombre) LIKE $1 ORDER BY` se renderizó como `WHERE LOWER(nombre) LIKE  ORDER BY` (SQL roto). Escapar con `\$1` NO alcanza (el backslash + `$1` desaparecen igual). `$env:VAR` SÍ sobrevive (no matchea var posicional). **Cómo evitarlo:** no poner `$N` literal crudo en el cuerpo de una skill; describir el placeholder en prosa (`<ph>` "= dólar más número") o sacar el ejemplo del code fence. Vale para cualquier doc que el harness renderice expandiendo, no solo skills.

2. **El cuerpo de la skill se cachea en la primera invocación de la sesión y NO se recarga si editás el archivo después.** Edité `seed-csv/SKILL.md`, re-invoqué, y siguió mostrando la versión vieja aunque el disco ya tenía la nueva (verificado con `sed -n`). **Para validar el fix de una skill recién editada, abrir sesión nueva** — no confiar en la re-invocación dentro de la misma sesión. El disco es la fuente de verdad de lo que se servirá después.

**Why:** ambos hacen que "probé la skill y se ve mal" sea engañoso — el archivo puede estar perfecto en disco. **How to apply:** al crear/editar skills, verificá el contenido con Read/sed sobre el archivo, no solo por el render de la invocación; y evitá `$N` literal en zonas que el render toca. Relacionado con [[feedback_set_content_utf8_bom]] (otro caso de "lo que escribo ≠ lo que el consumidor lee").
