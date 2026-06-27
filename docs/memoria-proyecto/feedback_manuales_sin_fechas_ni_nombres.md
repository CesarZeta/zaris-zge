---
name: feedback-manuales-sin-fechas-ni-nombres
description: Los manuales HTML de docs/ NO llevan fechas (ni encabezado ni pie) ni el nombre del usuario — solo app/módulo.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a62d2b4f-b3f3-4590-aa5f-79d8638e22fd
---

Regla mandatoria de diseño para los manuales operativos (`docs/manual_*.html`), pedida por el usuario el 2026-06-11:

- **NO poner fechas** en el manual: ni en el encabezado, ni en el pie, ni "generado el…", ni "versión de fecha".
- **NO poner el nombre del usuario** (Cesar Zarini / Cesar Zeta) en ningún lado.
- Limitarse al nombre de la aplicación (ZARIS), el módulo, la audiencia y el contenido.

**Why:** los manuales se comparten con municipios; una fecha los hace ver "vencidos" y el nombre personal no corresponde en material institucional.

**How to apply:** al generar o regenerar un manual con la skill [[generar-manual]], revisar hero, header, footer y metadatos visibles del HTML antes de cerrarlo; si la plantilla previa traía fecha o autor, quitarlos. Aplica también a manuales existentes cuando se los toque.
