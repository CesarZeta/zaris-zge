---
name: reference-geocoding-vecino-endpoint-scope-publico
description: "El geocoding OSM para el vecino LOGUEADO usa GET /api/v1/publico/reclamos/geo/buscar (scope publico). El /geo/buscar normal es scope agente (rechaza al vecino); el /publico/alta/geo/buscar exige slug (es del flujo de alta)."
metadata:
  type: reference
---

Hay TRES endpoints de geocoding OSM en ZARIS, cada uno con su guard — no confundirlos:

| Endpoint | Guard | Para |
|---|---|---|
| `GET /api/v1/geo/buscar` | `get_current_user` (scope **agente**) | backoffice interno. Rechaza al vecino (token scope publico → 401). |
| `GET /api/v1/publico/alta/geo/buscar?m=<slug>` | sin JWT, valida slug municipio | autoregistro sin sesión (`alta-vecino.html`). |
| `GET /api/v1/publico/reclamos/geo/buscar` | `get_current_ciudadano` (scope **publico**) | **vecino logueado** (form de nuevo reclamo en la PWA). Creado 2026-06-02. |

Los tres reusan `geocodificar_direccion(q, limit, solo_direcciones=True)` de `routes/geo.py` (la lógica de filtrado de POIs vive ahí, §22). El público de reclamos agrega `check_rate_limit` por IP (20/60s).

**Por qué un endpoint propio y no reusar:** el del backoffice es scope agente (no sirve al vecino); el de alta exige slug y es semánticamente del flujo sin sesión. El vecino logueado geocodifica su propia dirección → guard `get_current_ciudadano` es lo correcto. Registrado ANTES de `/{id_reclamo}` en `publico_reclamos.py` (segmento fijo antes del param greedy, §5).
