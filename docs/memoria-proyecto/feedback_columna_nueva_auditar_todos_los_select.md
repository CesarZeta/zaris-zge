---
name: feedback_columna_nueva_auditar_todos_los_select
description: "Al agregar una columna/campo nuevo, auditar TODOS los SELECT de lista explícita y TODOS los builders del response que lo deberían exponer — un endpoint que lo omite lo devuelve undefined en silencio."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8472eb9d-cfe0-4aef-8479-c1c691aba39e
---

Al agregar una columna nueva (migración + schema Pydantic + INSERT) **no alcanza con tocar el camino de escritura**: hay que auditar **todos los SELECT de lista explícita y todos los builders del response** que deberían exponerla. Un SELECT que no la incluye no falla — el endpoint la devuelve `undefined`/ausente en silencio y el frontend muestra un panel vacío sin error.

**Por qué (3 casos reales en Trámites):**
- Columna nueva del catálogo agregada a migración/schema/INSERT pero NO al SELECT de lista explícita de `detalle_version` (`tramites_admin.py`) → el endpoint la devolvía `undefined` silencioso.
- `tramite.resultado` (mig 74): el detalle se construye en DOS lugares — el helper `_tramite_detalle_out` (mutaciones) y el handler GET `/{numero_o_id}` que arma su propio `TramiteDetalleOut`. Setearlo solo en uno deja al otro sin el campo.
- `aprobaciones` (mig 73): mismo patrón — hubo que tocar el GET handler además del helper; el panel quedaba siempre vacío y solo se vio navegando ([[feedback_verificar_forms_navegando_mandatorio]]).

**How to apply:** tras sumar la columna, `grep` del nombre de la tabla/response en el router y servicios: listar cada SELECT con columnas explícitas y cada lugar que construye el schema `*Out`. Si dos rutas arman el mismo response (helper + handler), tocar las dos. Verificar el JSON crudo del endpoint, no solo el tipo TS ([[feedback_el_backend_puede_mentir]]).
