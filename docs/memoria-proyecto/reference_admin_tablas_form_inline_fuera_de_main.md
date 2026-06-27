---
name: reference_admin_tablas_form_inline_fuera_de_main
description: "En admin_tablas, un form inline debe vivir FUERA de"
metadata: 
  node_type: memory
  type: reference
  originSessionId: fd319fd9-f838-423f-ae64-a5d843565c54
---

`admin_tablas.html` tiene un CRUD genérico cuyo form normalmente es un **modal** (`#formModal`). Para tablas que crecen en campos se puede usar un **form inline** en el flujo de la página (set `INLINE_FORM_TABLES = {agentes, ...}`).

**Quirk crítico:** `cargarTabla()` hace `document.getElementById('main').innerHTML = ...` en cada carga/recarga de tabla. Si el contenedor del form inline (`#inlineForm`) está **dentro de `#main`, se borra** en el primer re-render. Debe vivir como **hermano fuera de `#main`** (junto a los modales), y mostrarse/ocultarse con `style.display`.

**Patrón verificado (sesión 2026-05-26, Agentes):**
- `#inlineForm` colocado después de `</main>`, junto a `#formModal`.
- `buildForm(schema, record, bodyId)` acepta el id del contenedor (default `modalBody`); para inline se pasa `inlineFormBody`.
- `readForm()`/`guardarRegistro()` leen por id global `f_<field>`, así que funcionan igual en modal o inline sin tocarlos. Solo hay que elegir el botón correcto (`btnInlineSave` vs `btnSave`) y cerrar el form correcto.
- `selectTabla()` llama `cerrarInline()` para no arrastrar el form de otra tabla.

**Secciones custom (no derivadas de SCHEMAS.cols):** se appendean al `#inlineFormBody` tras `buildForm` solo cuando `tablaActual` matchea (ej. "Horario de asistencia" del agente → escribe en `disponibilidad_recurso` vía `/api/v1/agenda/disponibilidad`, NO en columnas de `agentes`). El id del recurso para sub-entidades sale del `editId` (edición) o del `RETURNING *` del POST genérico (alta: `saved.id_<pk>`).
