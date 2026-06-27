---
name: reference-buc-lat-lon-columnas-existentes
description: ciudadanos y empresas YA tienen columnas latitud/longitud en local y prod (drift pre-existente sin migración formal). No proponer migración nueva.
metadata: 
  node_type: memory
  type: reference
  originSessionId: dfc52c6d-67d2-4a36-93ca-2b5655f60612
---

`ciudadanos.latitud`, `ciudadanos.longitud`, `empresas.latitud`, `empresas.longitud` existen en local (zaris_dev) y prod (Supabase) con tipo `numeric` y `is_nullable=YES`. Verificado 2026-05-15 via `execute_sql` MCP en prod y `psql` en local.

Los **modelos SQLAlchemy** `Ciudadano` y `Empresa` (en `backend/app/models/buc.py` líneas 119-120 y 161-162) ya las exponen como `Column(Numeric(10, 7))`. Los **schemas Pydantic** `*Out` también las exponen. Lo que faltaba al 2026-05-15 era declararlas en `CiudadanoBase`/`Update` y `EmpresaBase`/`Update` para permitir Create/Update — agregado en commit 164b817.

**Origen del drift:** ninguna migración numerada las crea. Posiblemente cambio manual viejo igual que `agentes.es_auditor` (caso documentado en [[feedback_verificar_drift_completo_prod]]). No documentadas en CLAUDE.md §21 hasta 2026-05-15.

**Implicaciones para próximas sesiones:**
- Si alguien pide "agregar lat/lon a ciudadanos/empresas", la respuesta correcta es: verificar via `execute_sql`, confirmar que existen, solo actualizar schemas Pydantic + frontend.
- Si vas a hacer una migración nueva que toque estas tablas, NO incluyas `ADD COLUMN latitud/longitud` aunque el CSV/spec lo sugiera — chequeá primero.
- Aplica el patrón de [[feedback_verificar_drift_completo_prod]]: chequear existencia+default+NOT NULL+CHECKs en prod **antes** de codear, no solo después.
