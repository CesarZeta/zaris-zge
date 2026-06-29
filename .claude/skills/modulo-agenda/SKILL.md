---
name: modulo-agenda
description: "Usar al trabajar en el módulo Agenda de ZARIS (archivos: backend/app/api/routes/agenda_v2.py, agenda_espacios.py, agenda_disponibilidad.py, agenda_novedades.py, agenda_publico.py, services/agenda.py, web-app/src/modules/agenda/; tablas: eventos, evento_reservas, evento_encargados, ocupaciones, espacios_agenda, espacio_agentes, disponibilidad_recurso, agenda_feriado, agente_novedad, agenda_audit_log). Sustrato de disponibilidad horaria (agentes/equipos/espacios) que usan OT, Turnos y Entradas. Cubre disponibilidad_efectiva (+batch), bitmask dias_semana, ocupaciones polimórficas, verbos HTTP del router, QR de reservas, scope por subárea y el patrón batch de performance. Invocar ANTES de tocar cualquier endpoint, grilla, disponibilidad, evento, ocupación o espacio de Agenda."
---

# Módulo Agenda — §27

> **Bitácora de implementación** (migraciones 30-43, seeds demo, sub-fases entregadas, pendientes cerrados) en [`HISTORIAL_MIGRACIONES.md`](../../../HISTORIAL_MIGRACIONES.md). Acá quedan las reglas vivas. Estado: backend (22 endpoints `agenda_v2.py` + espacios + disponibilidad) y frontend React (`web-app/src/modules/agenda/`) en producción. Ver memoria [[project_agenda_espacios_disponibilidad]].

### Estructura del módulo (cierre B2, 2026-05-14)

- **5 tabs** en `AgendaLayout`: **Vistas / Eventos / Disponibilidad / Conflictos / Config**. Dentro de Vistas, sub-toggle **Día / Semana / Mes** (persistido en `agendaStore.vistaGrilla`). URLs viejas `/agenda/timeline`, `/agenda/mensual` redirigen a Vistas. El tab **Disponibilidad** (`DisponibilidadView.tsx`, 2026-05-28) gestiona **Feriados** (`agenda_feriado`) y **Novedades de agentes** (`agente_novedad`: inasistencias/licencias, mig 69) — ambos restan disponibilidad efectiva. CRUD vía router `agenda_novedades.py` (`/api/v1/agenda/novedades` + `/feriados`, nivel ≤ 2). API client en `agenda/api/novedadesApi.ts`.
- **Pills de tipo de recurso** (4, con conteo desde `/recursos/conteos`): Agentes / Equipos·OT / Esp. atendidos·Turnos / Esp. eventos·Entradas. **NO hay opción "Todos"** (ver Performance). **Las pills NO son intercambiables** — cada una sirve a un módulo distinto: Equipos→asignación de OT, Esp. atendidos→Turnos, Esp. eventos→Entradas. **Pill inicial por rol (2026-06-12):** supervisor (nivel 2) aterriza en Equipos·OT; el resto en Agentes. Una vez por carga del bundle (flag `pillInicialAplicada` en `agendaStore` + effect en `VistasView`); después manda el click del usuario.
- **DnD solo en Vista Día y Semana** (`@dnd-kit/core@6.3.1`, PointerSensor + KeyboardSensor). Bloques tipo `evento` no son arrastrables (se editan desde el modal del evento).

### Convenciones del módulo

**FKs a las PKs reales:** `eventos.id_subarea`→`subarea.id_subarea`, `eventos.id_estado_evento`→`estado_evento.id_estado_evento`, `evento_reservas.id_ciudadano`→`ciudadanos.id_ciudadano`, `ocupaciones.id_orden_trabajo`→`ordenes_trabajo.id_ot`. `evento_encargados.id_recurso` y `ocupaciones.id_recurso` → `agentes`/`equipos`/`espacios_agenda` (sin FK física; polimórfica por `tipo_recurso`, validación en backend).

**Tabla única `ocupaciones`** con CHECK `ck_ocupacion_consistencia`: solo se popula la FK del `tipo` (`ot`→`id_orden_trabajo`, `evento`→`id_evento`, `turno`→`id_ciudadano`, **`bloqueo`→ninguna** — mig 89). El tipo `bloqueo` es el cierre manual de un recurso sin entidad asociada (espacio en mantenimiento, agente afectado a otra tarea): exige `motivo` (schema `OcupacionCreate`), vale para los 3 tipos de recurso y se renderiza gris en la grilla. `existe_recurso` (services/agenda.py) valida agente/equipo/**espacio** desde 2026-06-12 — antes espacio devolvía False y el POST manual de ocupación sobre espacio daba 404. No usar tablas separadas por tipo.

**`equipo_agentes` (no `equipo_usuarios`):** pivot equipo↔agente. `equipo_usuarios` solo existe vacío en local; en prod no existe.

**`asignacion_a` en `tipo_reclamo`:** define si las OTs del tipo bloquean agenda de `agente` o `equipo`. `duracion_estimada_min` es lo que bloquea el calendario (distinto de `sla_dias`, deadline del reclamo).

**Tres tipos de recurso:** `agente`, `equipo`, `espacio`. Espacio puede ser `atendido` (necesita agentes vinculados vía `espacio_agentes`) o desatendido.

### Convención bitmask `dias_semana`

`dias_semana SMALLINT` con bitmask, NO TEXT. Lunes=bit0=1, Martes=2, Miércoles=4, Jueves=8, Viernes=16, Sábado=32, Domingo=64. Ejemplos: L-V=`31`, fin de semana=`96`, todos=`127`. CHECK `BETWEEN 0 AND 127`.

**Helper UI obligatorio:** `frontend/js/dias-semana.js` (vanilla) o `web-app/src/lib/diasSemana.ts` (React) con `serialize/deserialize/togglearDia/format`. `format(31)`→`Lun a Vie`, `format(96)`→`Sab y Dom`, `format(127)`→`Todos los dias`.

### Lógica `disponibilidad_efectiva(db, tipo_recurso, id_recurso, fecha)`

Resuelve los rangos horarios efectivos para una fecha aplicando bitmask `dias_semana` + ventana `vigente_desde/hasta`. **Desde 2026-05-28 además resta feriados y novedades de agentes** (helpers `_es_feriado`, `_bloqueos_novedades_agente`, `_restar_intervalos` en `services/agenda.py`): día feriado (`agenda_feriado`) → `[]`; novedad de agente (`agente_novedad`) total → `[]`, parcial → recorta el rango. La versión `_batch` (la que usan `/calendario` y `/semana`) lo hace en 2 queries extra para no romper la perf §27. Para espacio atendido, las novedades de cada agente vinculado ya se restan al armar la unión. Para `tipo_recurso='espacio'`:
- **Desatendido:** horario propio del espacio.
- **Atendido:** intersecta el horario del espacio con la **unión** de horarios de los agentes vinculados activos. Sin horario propio → la unión sola. Sin agentes vinculados → `[]` (la mig 40 NO enforce "atendido ⇒ ≥1 agente"; síntoma: grilla toda gris).

**Para `tipo_recurso='equipo'` (decisión 2026-06-15, mig 91):** la disponibilidad de una cuadrilla es la **UNIÓN de los horarios de sus agentes** activos (`equipo_agentes`), NO su horario propio. Helper `_disponibilidad_equipo_union` (espejo del caso "espacio atendido"). Equipo sin agentes → `[]`, **salvo override**: clave `configuracion_general.equipos_sin_agentes_usan_horario_propio` (default `false`, editable en Config → Sistema) — con `true` usa el horario propio del equipo. **Antes (≤ mig 67) la Agenda leía el horario propio del equipo y divergía del planificador de OT** (que ya hacía la unión); ahora ambos usan esta misma función. Aplica en `disponibilidad_efectiva` Y en `disponibilidad_efectiva_batch` (la batch pre-resuelve los agentes de cada equipo, igual que con espacios atendidos). Los 3 campos legacy `dias_semana/hora_inicio/hora_fin` de `equipos` y las franjas propias `disponibilidad_recurso(tipo_recurso='equipo')` **NO se usan** salvo override.

`_merge_rangos()` une rangos solapados/contiguos. **Quirk:** cast inline `(:f)::date` — asyncpg pasa DATE como `unknown` y Postgres no resuelve `EXTRACT(ISODOW FROM ...)` sin el cast. Ver [[feedback_asyncpg_extract_cast_date]].

**Scope por subárea del supervisor:** `/calendario` y `/semana` aceptan `scope_subarea_propia`. Si `true`, filtra recursos a la subárea del usuario (`usuarios → agentes.id_subarea`). **Admin (nivel 1) NO se scopea.** **Fail-open** si no se puede resolver la subárea. La pill "Equipos·OT" lo manda automáticamente. Helper `_resolver_scope_subarea` en `agenda_v2.py`: `id_subarea` explícito > scope propio > None.

### Sistemas de auditoría coexistentes

Dos sistemas con vocabularios distintos — **no unificar sin decisión explícita**:
- `reclamo_historial` (Reclamos + OT): cambios de estado y notas custom, append-only.
- `agenda_audit_log` (Agenda): `entidad` ∈ {evento,ocupacion,reserva} con `accion` ∈ {crear,modificar,cancelar,asignar} y diffs JSONB.

### Verbos HTTP del router agenda_v2 (referencia obligatoria)

Mezclan PUT con PATCH. Antes de scriptear un smoke o codear un cliente, `grep "@router\." backend/app/api/routes/agenda_v2.py` para confirmar.

| Acción | Verbo | Path |
|---|---|---|
| Crear / Editar full / Cancelar / Eliminar evento | POST / PUT / **PATCH** `/cancelar` / DELETE | `/eventos`, `/eventos/{id}` |
| Asignar / Quitar encargado | POST / DELETE | `/eventos/{id}/encargados[/{id_ee}]` |
| Crear reserva | POST | `/eventos/{id}/reservas` |
| Marcar asistió / Cancelar reserva | **PATCH** | `/reservas/{id}/asistio`, `/reservas/{id}/cancelar` |
| Acreditar por QR | **POST** | `/reservas/acreditar-qr` |
| Crear / Editar / Cancelar ocupación | POST / PUT / DELETE | `/ocupaciones[/{id}]` |
| Calendario día / mes / semana | GET | `/calendario` (NO `/calendario/dia`), `/mes`, `/semana?desde=&dias=` |
| Conflictos / Resolver | GET / **PATCH** | `/conflictos?resuelto=false`, `/conflictos/{id}/resolver` |
| Recurso | GET | `/recurso/{tipo_recurso}/{id_recurso}` |
| Conteos de recursos por tipo (pills) | GET | `/recursos/conteos?id_municipio=` |

**Router `agenda_espacios.py`** (`/api/v1/agenda/espacios`): GET listado (filtros `atendido`/`q`), POST, GET `/{id}` (con `agentes_vinculados` + `cant_agentes`), PUT, DELETE (soft + cascade N:M), GET/POST/DELETE `/{id}/agentes[/{id_ea}]`.
**Router `agenda_disponibilidad.py`** (`/api/v1/agenda/disponibilidad`): GET (filtros tipo/id), POST, PUT `/{id}`, DELETE `/{id}` (soft), GET `/efectiva?tipo_recurso=&id_recurso=&fecha=`.
**Router `agenda_publico.py`** (`/api/v1/agenda/publico`, SIN auth — autoservicio de eventos §33): GET `/evento/{token_publico}` · POST `/evento/{token_publico}/reservar` (busca/crea ciudadano por DNI) · GET/DELETE `/reserva/{token_reserva}`. Tokens UUID, 404 genérico anti-enumeración.
Permisos: `nivel_acceso <= 2` muta (espacios/disponibilidad/novedades); cualquier autenticado lee. **Las mutaciones de `agenda_v2.py`** (eventos/encargados/reservas/ocupaciones/resolver-conflictos) **exigen nivel ≤ 3** vía dependency `require_operador` (desde 2026-06-12 — antes solo pedían JWT y un Consultor nivel 4 podía mutar por curl; espejo de [[guard_nivel_endpoint_no_solo_ui]]). Los GET de agenda_v2 siguen con `get_current_user` pelado.

Smoke reproducible: `smoke_agenda.ps1` (raíz), 15 endpoints clave.

### QR físico de reservas

`evento_reservas.qr_codigo` es un **identificador opaco** (`EVT{id}-RES{id}-{ts}`, generado por `services/agenda.py::generar_qr_codigo`), no una URL. El operador lo escanea y acredita vía `POST /api/v1/agenda/reservas/acreditar-qr` con body `{qr_codigo}` → marca `asistio`. 404 si no es reserva activa, 409 si cancelada. Registrado **antes** que `/reservas/{id}/...` (anti-greedy). UI: sección "Acreditar por QR" en `ReservaModal.tsx`. El PNG se renderiza solo en cliente (`QRDisplay.tsx`, lib `qrcode` ~26KB) — el backend solo genera el string.

### Performance — patrón batch (optimización 2026-05-14)

Con 84 agentes en prod, los endpoints B1 originales eran inusables (`/calendario` 23s→2.2s, `/semana` 7d timeout→2.6s). El patrón que lo arregló:

1. **`disponibilidad_efectiva_batch(session, recursos, fechas)`** — 2 queries totales (`WHERE tipo=ANY AND id=ANY`), bitmask/vigencia/intersección resueltos en Python. La singular `disponibilidad_efectiva` queda para `/disponibilidad/efectiva` (compat retro).
2. **`_eventos_del_rango(db, fd, fh, mun)`** — 1 query base + 1 bulk de encargados. `_eventos_del_dia` queda como wrapper.
3. `/calendario` y `/semana` llaman a los batch. Compat retro verificado byte-a-byte.

**Latencia base Railway↔Supabase ~2-3s** con JOINs sobre 84 filas — piso físico sin tocar arquitectura. Ver [[reference_agenda_latencia_base_railway_supabase]]. Patrón generalizable para loops N×M: [[feedback_patron_batch_helper_singular_wrapper]].

**Quirk de clave:** `disponibilidad_por_recurso` en `/semana` usa formato `"{tipo}:{id}"` con dos puntos. Ver [[reference_agenda_semana_disponibilidad_key]].
