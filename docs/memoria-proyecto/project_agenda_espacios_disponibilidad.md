---
name: agenda-espacios-disponibilidad
description: "Sub-fases B1 + B2 de Agenda entregadas. Verificación visual hecha 2026-05-14, performance optimizada (/calendario 23s→2.2s, /semana timeout→2.6s). Próximo: módulo OT."
metadata: 
  node_type: memory
  type: project
  originSessionId: 730ba002-bb4e-4ffc-a6c4-7067ae9362ab
---

**B1 (backend) + B2 (frontend) cerradas al 2026-05-14.** Commits clave:
- `d3a7915` (2026-05-13) — B1 backend
- `7186fe1` (2026-05-14) — B2 frontend + endpoint `/recursos/conteos` + fix drift conteos
- `37d5034` (2026-05-14) — perf: `disponibilidad_efectiva_batch`
- `8d047f5` (2026-05-14) — perf: `_eventos_del_rango` bulk

**Performance medida en prod (84 agentes):**

| Endpoint | Original | Final | Mejora |
|---|---|---|---|
| `/calendario` agente 1d | 23.1s | 2.2s | ~10× |
| `/semana` agente 7d | timeout >60s | 2.6s | >23× |
| `/semana` todos 14d | n/a | 3.3s | flat |

**Why:** Original tenía loops `O(recursos × días)` de queries secuenciales contra Supabase. Cada `disponibilidad_efectiva(db, t, id, f)` y cada `_eventos_del_dia(db, f, m)` hacían round-trip independiente, dominado por latencia Railway↔Supabase (~30ms cada uno). Con 84 recursos × 7 días = 588+ round-trips.

**How to apply:**
- Para próximos endpoints con loops N×M sobre queries, aplicar el mismo patrón: **batch helper + singular wrapper**. Helpers nuevos verificados: `disponibilidad_efectiva_batch(session, recursos, fechas)` y `_eventos_del_rango(db, fd, fh, mun)`. La función singular se mantiene como wrapper que delega al rango (compat retro).
- **Latencia base Railway↔Supabase es ~2-3s** para queries no triviales con JOINs. Es el piso teórico de cualquier endpoint de agenda hasta que se cambie arquitectura (PgBouncer, mover backend a la misma región, etc.). No prometer sub-segundo sin tocar infra.
- Si una sesión necesita medir perf en prod, usar polling con login dentro del loop ([[feedback_polling_login_dentro_del_loop]]).

**Bug del drift de conteos (fix 7186fe1):** `/recursos/conteos` usaba `WHERE id_municipio = :im` mientras `/calendario` usa `WHERE id_municipio IS NULL OR id_municipio = :im`. En prod hay 3 agentes y 3 equipos legacy con id_municipio NULL. Pill decía "Agentes 1" pero grilla mostraba 4. Ahora ambas usan la regla NULL-friendly.

**Pendientes B2 chicos (no bloqueantes):**
- Badge "⚠ falta vincular agentes" en `EspaciosConfig` cuando un espacio atendido tiene 0 agentes (sino la grilla queda toda gris sin razón obvia).
- Limpiar título "timeline" legacy entre las pills y la fecha (residuo de sub-fase 3.A).
- Decidir UX para **eventos sin encargado ni id_espacio**: hoy son invisibles en la grilla porque no tienen fila destino. Opciones: fila "Eventos sin asignar", o validación en `POST /eventos` que exija al menos uno.
- 3 ítems `data-modulo="turnos"` duplicados en sidebar vanilla (`turnos`, `entradas`, `agenda`) — consolidar a 1.

**Pendientes B2 más grandes:**
- Drag en vista Semana (hoy solo Día tiene DnD, heredado de 3.B).
- KeyboardSensor en DnD.

**Pendientes perf restantes (todos micro vs el ahorro ya logrado):**
- En `/semana` el listado base de **ocupaciones** del rango ya es 1 query (BETWEEN), OK. **Ausencias** idem. **Recursos** idem. **Eventos+encargados** idem post-`8d047f5`. **Disponibilidad** idem post-`37d5034`. Lo que queda es latencia base Railway↔Supabase, no se gana más sin tocar infra.

Memorias relacionadas: [[reference_agenda_v2_verbos_http]], [[reference_agenda_semana_disponibilidad_key]], [[feedback_asyncpg_extract_cast_date]], [[feedback_polling_login_dentro_del_loop]], [[reference_agenda_latencia_base_railway_supabase]].
