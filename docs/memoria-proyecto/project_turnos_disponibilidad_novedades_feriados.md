---
name: project-turnos-disponibilidad-novedades-feriados
description: "Turnos sujetos a disponibilidad efectiva (agente o lugar atendido), novedades de agentes, feriados y switch global. Migs 69/70, sesión 2026-05-28."
metadata: 
  node_type: memory
  type: project
  originSessionId: ab06eddc-2f01-4047-a0bd-b830bc546a2d
---

Sesión 2026-05-28: el módulo Turnos pasó a respetar la disponibilidad real de los recursos, y ahora un turno puede reservarse contra un agente O un lugar de atención atendido.

**Why:** el usuario pidió que la capacidad/horarios de turnos esté sujeta a la disponibilidad de agentes (horario + asistencia), poder cargar inasistencias y feriados, y crear lugares de atención atendidos/desatendidos.

**Qué se hizo (en prod + local):**
- **Mig 69**: tabla `agente_novedad` (inasistencia/licencia/vacaciones/comision/otro; rango de fechas; total o parcial por hora) + clave `configuracion_general.turnos_respeta_disponibilidad` (default 'true', tipo 'boolean'). OJO `configuracion_general` tiene `tipo` y `activo` NOT NULL sin default.
- **Mig 70**: `turnos.id_espacio` (FK espacios_agenda) + `id_agente` nullable + CHECK `ck_turnos_recurso` (exactamente uno). Turno polimórfico agente|espacio.
- `services/agenda.py::disponibilidad_efectiva` (y `_batch`, la de /calendario y /semana) ahora **restan feriados** (día completo, `agenda_feriado`) y **novedades de agentes** (helpers `_es_feriado`, `_bloqueos_novedades_agente`, `_restar_intervalos`). Para espacio atendido, las novedades de cada agente vinculado ya se restan al armar la unión.
- `turnos_respeta_disponibilidad(db)` switch: con true el alta de turno (backoffice + autoservicio) exige que caiga en la disponibilidad efectiva; con false, modo libre. El anti-solapamiento siempre aplica.
- Router `agenda_novedades.py` (`/api/v1/agenda/novedades` + `/feriados`, CRUD, nivel ≤ 2).
- Frontend Agenda: tab nuevo **disponibilidad** (`DisponibilidadView.tsx`, sub-tabs Feriados/Novedades). API en `agenda/api/novedadesApi.ts`.
- Turnos backoffice (`TurnoFormModal`) + autoservicio público (`autoservicio/TurnosPage.tsx`): toggle Agente / Lugar de atención. Endpoint público nuevo `/turnos/publico/recursos` (agentes + espacios atendidos). `/slots` acepta `tipo_recurso`+`id_recurso`.
- `seed_turnos_demo.py`: disponibilidad L-V de agentes, 1 lugar atendido + 1 desatendido, turnos demo. Idempotente.

**Ciudadano modelo (vista 360°):** se eligió **Juan Pérez (id_ciudadano=1, DNI 12345678)** como eje. Ya tiene en prod: 2 turnos, 10 reclamos, 1 trámite. La pantalla 360° visual quedó **pendiente para otra sesión** (el usuario pidió "solo dejar datos sembrados" por ahora). Idea acordada: sección "Interacciones" en el detalle del ciudadano (Contactos/Padrones) vía endpoint `/buc/ciudadanos/{id}/interacciones`.

**Commit:** `569dfa7` en main. Backend prod verificado (slots agente+espacio OK), bundle en GH Pages OK.

**Trampa cazada:** la mig 69 quedó a medias en prod (el INSERT falló y revirtió el CREATE TABLE) → 500 en /slots hasta crear `agente_novedad` a mano. Ver [[feedback_apply_migration_parcial_aborta_todo]].
