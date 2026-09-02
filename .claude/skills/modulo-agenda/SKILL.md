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

### Modo UBICACIÓN en la grilla (F2b plan ATENCION, 2026-09-01)

`/calendario` y `/semana` aceptan **`id_espacio_ubicacion`**: la grilla muestra los recursos de UNA ubicación de atención — el espacio + los agentes que atienden ahí (helper `_recursos_de_ubicacion`: `espacio_agentes` activos ∪ `tipo_prestacion.id_espacio_ubicacion`, mismo shape que `_listar_recursos_para_calendario`, así el pipeline ocupaciones/ausencias/disponibilidad batch no cambia). En ese modo se **ignoran** `tipo_recurso`/`atendido`/`id_subarea`/`scope_subarea_propia`; espacio inexistente/inactivo → 404. Compat retro: sin el parámetro todo sigue igual.

- **Frontend**: pill "Por ubicación" (PRIMERA del toggle, `FiltroRecursoUI` sumó `'ubicacion'`) + select agrupado por gestión que consume `GET /api/v1/turnos/ubicaciones` **por URL directa desde `agendaApi.ts`** — NO importar código del módulo Turnos (Turnos ya importa componentes de Agenda; un import inverso arma dependencia circular). Estado en `agendaStore.filtroUbicacion` (no persistido); `filtroUIaBackend` tiene un case `'ubicacion'` fallback inocuo por exhaustividad del switch. Sin ubicación elegida, Día/Semana muestran prompt. Vista **Mes queda fuera** del modo (muestra eventos).
- A diferencia de la Mesa de Turnos, esta grilla **NO enmascara** las ocupaciones del agente en otra ubicación: es la agenda del recurso y siempre mostró todas sus ocupaciones (comportamiento histórico del módulo).

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

**Router `agenda_espacios.py`** (`/api/v1/agenda/espacios`): GET listado (filtros `atendido`/`q`), POST, GET `/{id}` (con `agentes_vinculados` + `cant_agentes`), PUT, DELETE (soft + cascade N:M), GET/POST/DELETE `/{id}/agentes[/{id_ea}]`. Desde mig 93 (2026-07-02) los espacios tienen `latitud`/`longitud` (en schemas Base/Update/Out + INSERT + UPDATE + los 2 SELECT): el form `EspacioFormModal` usa el bloque §23 (`DireccionGeoField`, vive en `reclamos/components/`) y el Dashboard los muestra como capa geo (turnos/entradas se ubican vía su espacio).
**Router `agenda_disponibilidad.py`** (`/api/v1/agenda/disponibilidad`): GET (filtros tipo/id), POST, PUT `/{id}`, DELETE `/{id}` (soft), GET `/efectiva?tipo_recurso=&id_recurso=&fecha=`.
**Router `agenda_publico.py`** (`/api/v1/agenda/publico`, SIN auth — autoservicio de eventos §33): GET `/evento/{token_publico}` · POST `/evento/{token_publico}/reservar` (busca/crea ciudadano por DNI) · GET/DELETE `/reserva/{token_reserva}`. Tokens UUID, 404 genérico anti-enumeración.
Permisos: `nivel_acceso <= 2` muta (espacios/disponibilidad/novedades); cualquier autenticado lee. **Las mutaciones de `agenda_v2.py`** (eventos/encargados/reservas/ocupaciones/resolver-conflictos) **exigen nivel ≤ 4** vía el helper `_require_operador` (verificado en código 2026-07-17: `if nivel_acceso > 4: 403`; espeja `modulos.agenda.min_nivel_acceso=4` post-mig 92). El **Consultor (nivel 5)** queda solo-lectura; antes de 2026-06-12 estos endpoints solo pedían JWT y cualquiera podía mutar por curl (espejo de [[feedback_guard_nivel_endpoint_no_solo_ui]]). Los GET de agenda_v2 siguen con `get_current_user` pelado.

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

### Anti-carrera en reservas de eventos (mig 95, 2026-07-18) — OBLIGATORIO en toda vía nueva

Las 3 vías que insertan `evento_reservas` (backoffice `agenda_v2.crear_reserva`, autoservicio anónimo `agenda_publico.reservar_publico`, vecino `publico_entradas_vecino.reservar_entrada_vecino`) siguen el mismo protocolo — **cualquier vía nueva debe replicarlo o la carrera se reabre por esa puerta**:

1. **`lock_evento_row(db, id_evento)`** (`services/agenda.py`, `SELECT ... FOR UPDATE` de la fila de `eventos`) ANTES de `cupo_disponible` — serializa cupo + duplicado entre las 3 vías (anti-sobrecupo). Cancelar NO necesita el lock (liberar cupo nunca sobrevende).
2. **Regla global (decisión César 2026-07-18): máximo UNA reserva no-cancelada por (evento, ciudadano)** — UNIQUE parcial `uq_evento_reservas_ciudadano_vigente` `WHERE activo AND id_estado_reserva <> <cancelada>` (id resuelto dinámicamente en la mig; es 3 en local y prod). El predicado NO puede ser `WHERE activo` a secas: cancelar deja `activo=TRUE` y el flujo cancelar→re-reservar debe seguir andando. Las 3 vías tienen además el check amigable 409 ("ya tiene una reserva activa").
3. **`IntegrityError` → `await db.rollback()` + 409** alrededor de INSERT+commit en las 3 vías (y en `_patch_reserva_estado`, porque revivir una cancelada puede violar el UNIQUE vía UPDATE).
4. **CAS de estado** en `_patch_reserva_estado` (WHERE exige el `id_estado_reserva` leído + rowcount→409) y en los cancelar públicos — cancelar∥acreditar-QR ya no se pisan. **Guard nuevo:** `PATCH /reservas/{id}/asistio` rechaza 409 sobre una reserva cancelada (antes esa vía numérica bypasseaba el guard de la vía QR y revivía la reserva re-consumiendo cupo). El cancelar del backoffice sigue permitiendo cancelar una `asistio` (corrección de mesa); los cancelar públicos exigen `reservada`.

El helper `buscar_o_crear_ciudadano_por_dni` toma `advisory_lock_tx('ciudadano_dni:{dni}')` (evita ciudadanos duplicados por DNI en autoservicios concurrentes). Los locks de turnos viven en la skill `modulo-turnos-entradas`.

### Scope-subárea en mutaciones (2026-07-18, hallazgos [17][18]) — OBLIGATORIO en toda mutación nueva

Guards en `agenda_v2.py` (imitan `_validar_scope_supervisor_ot` de OT), aplican a **niveles 2 y 4** (nivel 1 y 3 sin scope — Atención ve todo por diseño; fail-closed 403 accionable si el usuario 2/4 no tiene agente/subárea; la fuente es SIEMPRE `agentes.id_subarea` vía `subarea_del_usuario`):

- **`_subarea_scope_mutacion`** (resuelve el scope) · **`_validar_scope_recurso`** (polimórfico agente/equipo/espacio; subárea NULL del recurso → fail-open) · **`_validar_scope_evento`** (evento con `id_subarea` NULL = institucional: fail-open nivel 2, 403 nivel 4).
- Aplicados en las 10 mutaciones de `agenda_v2` (eventos CRUD+cancelar, encargados asignar/quitar — en evento institucional el nivel 2 saltea el check del recurso —, ocupaciones CRUD incl. recurso NUEVO del PUT, conflictos resolver). El POST de eventos FUERZA la subárea propia al nivel 4 y el PUT bloquea mover el evento de subárea.
- `agenda_espacios` / `agenda_disponibilidad` / `agenda_novedades` (nivel ≤ 2): el SUPERVISOR queda scopeado — espacios de su subárea (NULL = compartido → solo admin; el PUT no permite reasignar la subárea), franjas y novedades solo de recursos/agentes de su subárea. **`espacio_agentes` scopea SOLO por el espacio** (los espacios atendidos se atienden con agentes de varias subáreas POR DISEÑO — no validar la subárea del agente vinculado). **Feriados sin scope** (entidad municipal; subirlos a nivel 1 es decisión de producto pendiente).
- Verificado con smoke multi-subárea (bloqueo/cancelar/borrar cross → 403; admin OK). Reservas de eventos: su protección es el anti-carrera (sección previa), no el scope.
