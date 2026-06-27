---
name: reference_no_python3_en_bash_tool
description: python3 no está disponible en el Bash tool de este entorno — falla silenciosamente
metadata: 
  node_type: memory
  type: reference
  originSessionId: 1965dc04-f954-4e6c-8bf6-1a05e8e8faf6
---

En este entorno (Windows) el Bash tool **no tiene `python3` funcional**: `python3 -c "..."` da `Python was not found` o falla sin output útil, y los heredocs `python3 << 'EOF'` se reportan como ejecutados pero NO modifican nada. Cazado el 2026-05-31 al optimizar CLAUDE.md: tres "ediciones" con scripts Python (str.replace sobre el archivo) parecían exitosas pero el archivo quedó intacto — además habrían fallado igual porque el archivo tenía CRLF y mis `\n` no matcheaban.

**Why:** perdí ~6 tool-calls creyendo que había editado cuando no. El fallo es silencioso (no siempre tira excepción visible).

**How to apply:**
- Para editar archivos: usar **Edit/Write**, NUNCA scripts `python3`/`python` vía Bash.
- Para procesar texto (contar, mapear secciones): si uso un script, **verificar el resultado leyendo el output real** (escribir a archivo + Read), no confiar en que "corrió".
- Si necesito Python de verdad (seeds del backend), eso corre vía la tool **PowerShell** con `python` (el `python.exe` del sistema sí existe, ver §7/§32) — distinto del `python3` del Bash tool.
- Ojo también con CRLF: CLAUDE.md y varios archivos del repo usan CRLF; los replace con `\n` no matchean. Edit tool maneja esto solo. Relacionado con [[reference_skill_render_expande_dolar_y_cachea]] (otro "lo que escribo ≠ lo que pasa").
