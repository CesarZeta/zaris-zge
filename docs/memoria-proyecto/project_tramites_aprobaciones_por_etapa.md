---
name: project_tramites_aprobaciones_por_etapa
description: "Aprobaciones por etapa (visados) en Trámites: COMPLETA y en prod (mig 73 + backend + builder + detalle), 2026-06-01."
metadata: 
  node_type: memory
  type: project
  originSessionId: 52bd7592-33b9-438e-a41e-b8b057b54f45
---

**ESTADO: COMPLETA y pusheada a prod (2026-06-01, commit `5c31ec6`).** Las 4 fases entregadas y verificadas E2E. Nada pendiente. Lo de abajo queda como referencia del diseño/modelo.

**Bug cazado al cerrar la Fase 4 (ya en código):** el commit `de6d6c9` (backend+builder) agregó `aprobaciones` a `_tramite_detalle_out` (helper de las MUTACIONES) pero **omitió el handler GET `/{numero_o_id}`** de `tramites.py`, que arma su propio `TramiteDetalleOut` y caía al default `[]`. La pantalla del detalle cargaba siempre sin visados aunque el frontend estuviera bien. Fix en `5c31ec6`: agregar `aprobaciones_de_tramite` al GET. Patrón [[feedback_el_backend_puede_mentir]] (cara 3) — dos rutas construyen el mismo response, auditar ambas. Solo se ve verificando navegando, no leyendo código ([[feedback_verificar_forms_navegando_mandatorio]]).

---

Feature de Trámites diseñada con el usuario el 2026-05-31, implementada 2026-06-01.

**Problema:** durante el circuito (el trámite se deriva entre áreas) hace falta una **marca paralela a los estados** que indique que un área aprobó/rechazó una etapa o un documento, consultable en cualquier momento, que opcionalmente bloquee el avance.

**Decisiones cerradas:**
- Objeto: documento adjunto **o** etapa completa (documento opcional en la marca).
- Efecto: configurable por marca (`bloqueante` sí/no).
- Multiplicidad: **varias áreas por etapa**; bloquea avanzar hasta que TODAS las bloqueantes estén aprobadas.
- Configuración: en el **builder de tipos**, versionado con el circuito (se copia al crear borrador).
- Rechazo bloqueante: el trámite **queda trabado** con motivo visible; el área subsana y re-solicita (NO dispara transición automática).
- Relación con `tramite_firma`: **modelo nuevo unificado**. `tramite_firma` queda SOLO para firma digital con evidencia (hash/IP); las aprobaciones de etapa son el visado de gestión. Conviven.

**Modelo (2 tablas nuevas, patrón catálogo+instancia §35):**
- `tipo_tramite_aprobacion_requerida` (catálogo, versionado): `id_tipo_tramite_version`, `id_tipo_tramite_estado` (etapa), aprobador polimórfico (`subarea`/`equipo`/`agente` + CHECK exactamente uno), `etiqueta`, `bloqueante BOOL`, `id_tipo_tramite_documento_requerido` NULL (opcional), `orden`, + estándar §10.
- `tramite_aprobacion` (instancia): `id_tramite`, `id_tipo_tramite_aprobacion_requerida`, `id_tipo_tramite_estado` (desnorm), `estado` (pendiente/aprobada/rechazada), `resuelto_por_agente`, `resuelto_en`, `comentario`, `id_tramite_documento` NULL, + estándar §10.

**Lógica:**
- Al entrar a una etapa (creación/transición): instanciar como `pendiente` las aprobaciones de ese estado (idempotente).
- Guard de avance en `transicionar_tramite` (justo donde hoy está `requiere_adjunto`, ~línea 1393 de routes/tramites.py): si hay bloqueantes de la etapa actual no `aprobada` → 422 listando las pendientes. Espeja el patrón `requiere_adjunto`.
- Endpoint nuevo `POST /tramites/{ref}/aprobaciones/{id}/resolver` con `{decision, comentario}`; valida pertenencia al área (polimórfico, svc_auth); registra movimiento `aprobacion` en el timeline.

**Fases:** 1=DB (mig 73, aplicar local+prod §24) · 2=Backend (instanciación + guard + endpoint resolver + exponer en detalle) · 3=Builder (sub-sección "Aprobaciones por etapa" en `ConfigTramiteDetalle.tsx`, copia al borrador) · 4=Detalle (panel de marcas verde/rojo/gris + acción resolver + aviso de bloqueo).

**OJO mig:** la numeración 51 está duplicada; usar **73+** (§21). Aplicar en local Y prod misma sesión. Ver [[feedback_apply_migration_parcial_aborta_todo]] y [[feedback_check_not_valid_se_evalua_al_update]] al redactar los CHECK.
