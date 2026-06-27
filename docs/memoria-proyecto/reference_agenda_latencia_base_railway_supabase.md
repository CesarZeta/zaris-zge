---
name: agenda-latencia-base-railway-supabase
description: "Latencia base Railway↔Supabase para queries no triviales con JOINs es ~2-3s. Es el piso de cualquier endpoint de agenda. Cualquier reporte de \"lento\" debajo de eso no se arregla optimizando queries."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 730ba002-bb4e-4ffc-a6c4-7067ae9362ab
---

Medido sesión 2026-05-14 tras optimizar `/calendario` y `/semana` con batch helpers. Una vez eliminados los loops O(N×M), los endpoints quedaron en:

| Endpoint | Latencia |
|---|---|
| `/agenda/calendario` 1 día, 84 recursos | 2.2 - 2.9s |
| `/agenda/semana` 7 días, 84 recursos | 2.6 - 3.3s |
| `/agenda/semana` 14 días, 86 recursos | 3.3s |
| `/agenda/mes` (sin disponibilidad) | 2.4s |
| `/agenda/recursos/conteos` (4 COUNTs simples) | 2.9s |
| `/agenda/disponibilidad/efectiva` (singular) | 1.5s |

**Why:** Cada round-trip Railway (us-west) ↔ Supabase (pooler regional) cuesta ~30-50ms con TLS. Una query con 3-4 JOINs sobre 84 filas más serialización JSON suma ~200-400ms. Los endpoints actuales hacen 5-7 queries totales (recursos + ocupaciones + ausencias + eventos + encargados + disponibilidad batch). El piso teórico es ~1.5-2s incluso si todas las queries fueran instantáneas.

**Cómo usar este número:**
- Si reporte de prod dice "tarda X segundos":
  - X < 4s → ya está cerca del piso. Optimizar query da poco. Considerar: caché client-side, prefetch en background, optimistic UI.
  - X 4-10s → hay round-trips de más en algún endpoint. Buscar loops `for ... await`.
  - X > 10s → casi seguro N×M sin batch. Patrón verificado: helper batch + singular wrapper.
- Antes de prometer una mejora de latencia, **medir el endpoint contra Railway con un GET vacío equivalente** para saber el piso real.
- **QA por navegador en PROD (2026-06-10):** este piso también aplica a los checks de UI — verificar el resultado de una mutación a los 3-4s da FALSOS NEGATIVOS (pasó 3 veces en una sesión: "no se creó el evento" / "no se promovió" cuando sí, solo que la respuesta tardó). Esperar **5-6s** tras cada mutación antes de juzgar, y ante un "falló", re-chequear una vez más antes de diagnosticar.

**Cómo bajar el piso (no hecho, deuda futura):**
- Mover backend al mismo region/AZ que Supabase (Railway permite seleccionar region).
- Usar Supabase Connection Pooler (PgBouncer) en lugar de connection directa — reduce TLS handshake amortizado.
- Cachear queries hot (`/recursos/conteos`, listado de recursos) con Redis en Railway.
- Reducir JOINs: pre-computar nombres y devolver IDs cuando alcance.

Ninguna de esas se justifica con la performance actual; sub-2s ya es usable.
