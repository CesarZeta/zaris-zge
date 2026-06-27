---
name: modulos-turnos-entradas
description: Módulos Turnos y Entradas — backoffice + autoservicio completos al 2026-05-14. Turnos = tabla propia + ocupación espejo. Entradas = reusa eventos de Agenda. Agenda backoffice reorganizada por propósito.
metadata: 
  node_type: memory
  type: project
  originSessionId: 66b9774c-3e58-4b94-91c1-f9fd113131b3
---

Backoffice de Turnos y Entradas implementado 2026-05-14 jornada 3. Ambos se apoyan en el sustrato de Agenda. Detalle completo en §33 CLAUDE.md.

**REPLANTEO 2026-05-28 (mig 71): los turnos cumplen PRESTACIONES.** El usuario invirtió el modelo. Antes: "tipo de servicio" (solo duración) + recurso elegido suelto al reservar. Ahora: una **PRESTACIÓN** define de una vez el recurso fijo (un agente O un lugar de atención), su duración y su **clase** ∈ {`atencion`, `reserva_espacio`}. La reserva elige **prestación + slot**; el recurso lo trae la prestación y se COPIA al turno al reservar (turno autocontenido).
- Mig 71 renombró `tipo_servicio_turno` → `tipo_prestacion` (PK `id_tipo_prestacion`, FK en `turnos` renombrada a `id_tipo_prestacion`) + columnas `clase`/`tipo_recurso`/`id_agente`/`id_espacio` + CHECKs `ck_tipo_prestacion_recurso` (exactamente uno, **NOT VALID**) y `ck_tipo_prestacion_reserva_espacio`. Solo DDL — seeds en `seed_turnos_demo.py`.
- **Quirk CHECK NOT VALID:** igual se evalúa al UPDATE de filas viejas → el seed (y el SQL de prod) soft-deletea las prestaciones viejas sin recurso asignándoles placeholder (`tipo_recurso='agente', id_agente=<primero>`) en el MISMO update.
- **ABM de prestaciones = pantalla React propia** (tab "Prestaciones" en el módulo Turnos, `TurnosLayout` con 2 tabs), **NO admin_tablas** (se quitó de TABLE_CONFIG + HTML). **Mutar prestaciones exige nivel ≤ 2** (`_require_supervisor` backend + tab oculto si `!hasPermission(2)`). El usuario lo pidió explícito: "debe ser usuario nivel supervisor para dar de alta prestaciones".
- Endpoints CRUD: `GET/POST/PUT/DELETE /api/v1/turnos/prestaciones[/{id}]`. `GET /catalogo/tipos-servicio` se eliminó.
- Autoservicio pasó de 4 pasos a **3** (prestación → slot → datos). Endpoints públicos `/tipos-servicio`,`/agentes`,`/recursos` eliminados; queda `/prestaciones` + `/slots?id_tipo_prestacion=`.
- En prod se aplicó vía SQL directo por MCP Supabase (NO hay `.env.prod`): mig 71 + prestaciones 4-7 + 3 turnos demo. Local vía psql + `seed_turnos_demo.py`.

**Modelo base (sin cambios):** turno = tabla `turnos` propia + fila espejo en `ocupaciones` (tipo='turno'). El backend sincroniza ambas (crear→insert ambas, cancelar→soft-delete la ocupación, cumplir→solo update turno). Estados: `reservado` → `cumplido` | `cancelado`. `turnos.id_agente`/`id_espacio` (mig 70, polimórfico, CHECK exactamente uno). `routes/turnos.py` + `turnos_publico.py` + `schemas/turnos.py` + módulo React `web-app/src/modules/turnos/`.

**Entradas** — thin module:
- SIN tablas ni migración propias. Reusa `eventos` + `evento_reservas` del backend de Agenda.
- "Evento con entradas" = `evento` con `id_espacio` no nulo. Backend: `id_espacio` agregado a schemas de evento + filtro `con_espacio` en `GET /agenda/eventos`.
- Módulo React `web-app/src/modules/entradas/` reusa el `ReservaModal` de Agenda directamente.
- Autoservicio de Entradas YA funciona (reusa el flujo público de eventos `/autoservicio/:token`).

**Agenda backoffice** — reorganizada por propósito (Pendiente Grande 2):
- Las 4 pills de tipo de recurso ya no son intercambiables: Agentes, Equipos·OT, Esp. atendidos·Turnos, Esp. eventos·Entradas. Cada una sirve a un módulo distinto, con subtítulo explicativo.
- La pill "Equipos · OT" manda `scope_subarea_propia=true` → backend scopea los equipos a la subárea del supervisor logueado (`agentes.id_usuario → agentes.id_subarea`). Admin no se scopea. Fail-open si no se puede resolver (prod tiene 0 agentes con `id_subarea` seedeada — drift de datos a corregir cuando el municipio cargue agentes).

**Turnos autoservicio — ENTREGADO 2026-05-14 jornada 4 (commit `7285dec`):** mig 46 agregó `turnos.token_turno` (UUID no enumerable) + `origen`. Router `backend/app/api/routes/turnos_publico.py` (prefix `/api/v1/turnos/publico`, sin auth, registrado ANTES de `turnos_router` por el `{id_turno}` greedy): tipos-servicio, agentes, slots libres (cruza `disponibilidad_efectiva` con `ocupaciones`), reservar, ver/cancelar por token. Frontend `web-app/src/autoservicio/TurnosPage.tsx` (flujo 4 pasos) + `MiTurnoPage.tsx`. Banner con link fijo `#/turnos-autoservicio` en el backoffice. Detalle CLAUDE.md §33.

**QR físico Agenda — ENTREGADO 2026-05-14 jornada 4:** `POST /api/v1/agenda/reservas/acreditar-qr` resuelve la reserva por `qr_codigo` y marca `asistio`. UI "Acreditar por QR" en `ReservaModal.tsx`. Detalle CLAUDE.md §27.

**REVISIÓN 2026-05-28 (scoping + cumplir con observación + encuesta diferenciada, mig 72):**
- **Scoping backend por nivel** en `GET /turnos` y `/{id}` (`_scope_turnos_para_usuario`): nivel ≤ 2 ve todo; nivel 3-4 ve solo turnos donde es el agente involucrado O de un espacio de su misma subárea. No evadible por curl. `get_current_user` NO trae id_agente/id_subarea → SELECT puntual a `agentes`. **OJO:** los espacios en prod tienen `id_subarea` NULL → el operador solo ve sus turnos como agente hasta que se cargue la subárea del lugar (Agenda→Config→Espacios).
- **Cumplir con observación:** `PATCH /turnos/{id}/cumplir` acepta body `{observaciones}` (schema `TurnoCumplir`), se ANEXA a `turnos.observaciones`. Frontend: `CumplirTurnoModal` (textarea) reemplaza el ConfirmModal.
- **Encuesta diferenciada de turnos:** al cumplir dispara `crear_envio_para_turno` (best-effort, tras commit). Plantilla CSAT `tipo='turnos'` seedeada. Email lo manda el dispatcher con delay 24h. Detalle en §42 y [[encuesta_envio_polimorfico_left_join]].
- **Tab Atendidos** (`pages/Atendidos.tsx`): turnos cumplidos + **export PDF** (`jspdf`+`jspdf-autotable`, `lib/exportPdf.ts`) + filtros agente/lugar solo para `hasPermission(2)`. CTA "Ver en agenda" (`navigate('/agenda')`). `TurnosLayout` pasó a **3 tabs** (Turnos/Atendidos/Prestaciones).
- Verificado end-to-end en navegador (local: cumplir→envío→form público→respuesta; prod: deploy backend confirmado con probe no-destructiva del endpoint público).

Memorias relacionadas: [[feedback_verificar_forms_navegando_mandatorio]], [[project_agenda_espacios_disponibilidad]], [[reference_agenda_v2_verbos_http]], [[feedback_pendiente_verificar_es_gap]], [[encuesta_envio_polimorfico_left_join]].
