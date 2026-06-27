---
name: encuesta-envio-polimorfico-left-join
description: "encuesta_envio es polimórfico (id_reclamo XOR id_turno desde mig 72). Toda query debe LEFT JOIN reclamos/turnos y ramificar por origen, nunca inner JOIN."
metadata: 
  node_type: memory
  type: reference
  originSessionId: db12f794-d376-425b-9339-953265cd6368
---

Desde mig 72 (2026-05-28), `encuesta_envio` es **polimórfico**: tiene FK a `ciudadanos` (siempre) + **exactamente uno** de `id_reclamo` / `id_turno` (CHECK `ck_encuesta_envio_origen`, NOT VALID). `encuesta_plantilla.tipo` ∈ `{reclamos, tramites, turnos}` decide qué preguntas se sirven.

**Regla:** cualquier query que lea `encuesta_envio` y necesite datos del origen DEBE hacer **LEFT JOIN** a `reclamos` y a `turnos` (+ `tipo_prestacion` para el nombre del turno) y **ramificar por cuál FK está poblada**. Un INNER JOIN a `reclamos` revienta (devuelve 0 filas / o 500 en el endpoint) cuando el envío es de turno (`id_reclamo` NULL) — y viceversa.

**Why:** antes de mig 72 `id_reclamo` era NOT NULL y 3 lugares hacían `JOIN reclamos r ON r.id_reclamo = ee.id_reclamo` (inner). Al agregar turnos, esos inner JOIN dejaban fuera/rompían los envíos de turno. Se corrigieron en mig 72:
- `encuestas_service.py::enviar_email_encuesta` — LEFT JOIN reclamos+turnos+tipo_prestacion; branch `if id_turno: _render_email_turno() else _render_email_encuesta()`.
- `encuestas_service.py::registrar_respuesta` — LEFT JOIN; `subarea_origen = COALESCE(ee.id_subarea, tr.id_subarea, r.id_subarea)`; la notificación de solicita_contacto usa una `referencia` legible ("Reclamo #X" o "Turno #Y").
- `routes/encuestas_publico.py::cargar_encuesta` — LEFT JOIN; `reclamo_referencia` = nombre de prestación + fecha del turno, o "Reclamo {nro}".

**How to apply:** si agregás un consumidor nuevo de `encuesta_envio` (dashboard, export, dispatcher variant), o un tercer origen (ej. `id_tramite`), revisá que NO haya inner JOIN a un solo origen. El dispatcher `procesar_envios_pendientes` ya es genérico (solo lee `id_encuesta_envio`) — no asume origen, no tocar. El form público `frontend/encuesta.html` es genérico por token (no asume reclamo). Familia del patrón: [[feedback_el_backend_puede_mentir]] (cara 3, SELECT que omite una columna/origen).
