---
name: project_tramites_pico_errores_feature_grande
description: "El proyecto casi no tiene errores en condiciones normales; el 2026-05-31 se dispararon varios a la vez en Trámites por meter una feature grande (visados/aprobaciones por etapa) de un saque. Todos fueron de la familia 'el backend puede mentir'."
metadata: 
  node_type: memory
  type: project
  originSessionId: db12f794-d376-425b-9339-953265cd6368
---

La base de calidad de ZARIS es alta: **el usuario observa que normalmente NO hay errores**. El 2026-05-31 fue una excepción notable — "justo ayer se dispararon varias veces" — y la causa no fue fragilidad del módulo sino el **tamaño del cambio**: se construyó de una sola entrega la feature más grande de Trámites (aprobaciones por etapa / visados: mig 73 + backend + builder + panel de detalle + lógica de subsanación).

Los bugs de ese día fueron casi todos de **[[feedback_el_backend_puede_mentir]]** (código compila, runtime falla):
- `b2f87b5` — `AprobacionRequeridaIn` usado como anotación sin importar → crash al construir openapi en prod (cara 2). Railway hizo rollback al deploy viejo.
- `fe9a10f` / `8204a59` — alta de trámite con body de shape plana vs anidada → 422; "no leía campos del builder" (`tipo.version.campos` vs nivel raíz) (cara 1).
- `de6d6c9` + `5c31ec6` — el GET detalle `/{numero_o_id}` armaba su `TramiteDetalleOut` sin `aprobaciones` (dos rutas construyen el mismo response) (cara 3).

**Why:** una entrega grande front↔back dispara varios bugs del MISMO patrón a la vez. No es que el módulo se volvió frágil; es que el cambio fue grande y monolítico. La línea base real es "sin errores".

**How to apply:**
- Features grandes de Trámites (o cualquier módulo con mucha superficie front↔back): **partir en entregas más chicas** y **verificar navegando el flujo real en prod antes de declarar cerrado** ([[feedback_verificar_forms_navegando_mandatorio]]). Varios de esos bugs SOLO se ven navegando, no compilando ni con typecheck.
- Si el usuario dice "hay errores de Trámites de ayer" como referencia, el primer sospechoso es esta familia en lo que se tocó (`git log` de Trámites del día). Diagnosticar contra runtime/JSON crudo, no leer solo el código.
- Estado al 2026-06-01: los bugs conocidos de ese pico están resueltos y la feature de visados quedó verificada E2E en prod ([[project_tramites_aprobaciones_por_etapa]]). Si reaparece algo, pedir el error concreto (pantalla / 422 / 500 / campo ausente) antes de tocar.
