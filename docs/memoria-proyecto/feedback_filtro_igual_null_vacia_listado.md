---
name: feedback-filtro-igual-null-vacia-listado
description: "Un filtro SQL 'columna = :param' con :param NULL devuelve 0 filas SIN error (NULL no es igual a nada en SQL). Sintoma del usuario: un listado/bandeja aparece vacio. La causa esta 2 capas debajo del sintoma."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 69f0aa1d-d88b-42cd-acf3-be104f89255f
---

Bug de Roy (2026-06-01): reporto "Trámites no me deja subir adjuntos / no carga los documentos / no aparece el botón Adjuntar". **Causa raíz, 2 capas debajo del síntoma:** su fila en `agentes` tenía `id_municipio = NULL`, y `GET /tramites/mi-bandeja` filtra `t.id_municipio = :mun` con `:mun = agente["id_municipio"]`. En SQL **`columna = NULL` no matchea NADA** (ni siquiera otro NULL) → la bandeja devolvía 0 trámites → Roy no veía ningún expediente → no podía abrir ninguno → sin documentos ni botón. Confirmado: 0 con el filtro, 8 sin él.

**Why:** el síntoma que reporta el usuario (UI sin botón / sin docs) estaba muy lejos de la causa (un filtro SQL con un parámetro NULL). Perdí tiempo persiguiendo el botón, el endpoint de documentos (200 OK), un 500 transitorio del detalle (era blip de Railway, hammer 90/90 OK) y el guard de firma — ninguno era. La diferencia entre el admin que funcionaba (Cesar) y el que no (Roy) era un solo dato: `id_municipio` (1 vs NULL).

**How to apply:**
1. **Síntoma "no carga / listado vacío / no veo nada" en un módulo con bandeja filtrada → sospechar primero un filtro `= :param` con `:param` NULL**, no la UI. Reproducir la query con el valor real del usuario (no el tuyo, que probablemente no es NULL).
2. **Buscar la diferencia de DATOS entre el usuario que funciona y el que no**, antes de tocar código. Acá: `SELECT id_agente, id_municipio FROM agentes WHERE ...` mostró 4 agentes con municipio NULL (drift de datos, no bug de código).
3. **Fix en 2 capas:** (a) corregir el dato (UPDATE, con backup §24) — desbloquea YA sin deploy; (b) blindar el código: mono-municipio (§38) usa `(:mun IS NULL OR t.id_municipio = :mun OR t.id_municipio IS NULL)` para tolerar NULL en ambos lados. Reclamos/BI ya lo hacían; `mi-bandeja` no.
4. **Patrón de drift:** `agentes.id_municipio` quedó NULL en altas que no lo setearon (los creados por la regla 1:1 agente↔usuario, mig 64). Si ves un `= :mun` estricto sobre una columna que puede venir NULL por drift, es bug latente.

**Instancia 2 (2026-06-15):** la Mesa del Supervisor de OT filtraba por `r.id_subarea = :id_subarea`, pero `reclamos.id_subarea` está **NULL en el 100% de los reclamos** (la subárea real vive en `tipo_reclamo.id_subarea`, §27) → pasar la subárea vaciaba la bandeja en silencio. Fix: derivar de `tr.id_subarea` (JOIN al tipo). Mismo criterio en las 2 mesas de auditoría. Acá la columna NO era drift puntual: era NULL **por diseño** (legacy post-mig 27, [[feedback_filtros_legacy_post_mig27]]) — el filtro estaba roto desde el día uno y nadie lo notó porque nadie filtró por subárea. Un filtro sobre una columna SIEMPRE NULL es peor que el de drift: falla al 100%, no a veces.

Relacionado: [[feedback_sintoma_usuario_no_es_diagnostico]] (el síntoma del usuario no es el diagnóstico), [[feedback_verificar_drift_completo_prod]] (verificar drift de datos en prod).
