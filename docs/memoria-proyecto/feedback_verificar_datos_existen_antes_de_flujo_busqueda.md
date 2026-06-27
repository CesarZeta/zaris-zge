---
name: feedback_verificar_datos_existen_antes_de_flujo_busqueda
description: "Antes de construir un flujo 'buscar/recuperar por campo X', verificar con execute_sql que X tenga datos reales en prod — sino el flujo es decorativo (devuelve siempre vacío)."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 37e34652-08e6-403e-981b-ad8ea8ad8cdd
---

Antes de implementar cualquier flujo del tipo "ingresá X y te busco/recupero Y" (recovery por documento, login alternativo, vinculación por campo), **verificar con `execute_sql` que la columna X tenga datos cargados en prod**, no solo que la columna exista.

**Caso real (sesión 2026-06-13, recovery interno):** el usuario pidió "recuperar usuario por número de documento". El plan natural era buscar en `agentes.cuil`. Un `COUNT(*) FILTER (WHERE cuil IS NOT NULL)` reveló **0 de 90 agentes con CUIL** — el flujo hubiera devuelto vacío para todos. Eso cambió el diseño: hubo que **agregar `agentes.dni`** (mig 90) para que el recovery tuviera sustento real, y planteárselo al usuario con `AskUserQuestion` (eligió "agregar DNI primero").

**Why:** "la columna existe" ≠ "la columna tiene datos". Un flujo de búsqueda contra una columna vacía pasa el smoke (200 OK, anti-enumeración devuelve OK igual) pero es inútil en producción — y el bug es invisible hasta que un usuario real lo prueba.

**How to apply:**
- Antes de codear el flujo: `SELECT COUNT(*), COUNT(*) FILTER (WHERE <campo> IS NOT NULL AND <campo> <> '') FROM <tabla> WHERE activo`.
- Si está vacío o casi: avisar al usuario y proponer (a) cargar los datos primero, (b) agregar la columna que sí tendrá datos, o (c) usar otro campo que sí esté poblado. Decidirlo con `AskUserQuestion`, no asumir.
- Familia de [[feedback_verificar_drift_completo_prod]] (verificar la realidad de prod antes de codear) — acá la dimensión nueva es **densidad de datos**, no solo existencia/CHECK/default.
