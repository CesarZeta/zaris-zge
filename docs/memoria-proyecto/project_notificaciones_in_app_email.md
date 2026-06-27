---
name: project-notificaciones-in-app-email
description: "Sistema de notificaciones in-app + email entregado 2026-05-18 y extendido 2026-05-19. Mig 51 aplicada local + prod. SMTP Zoho enviando real. 6 tipos de eventos cubiertos."
metadata:
  node_type: memory
  type: project
  originSessionId: e77756f2-e217-4421-a18c-df927d47dfb5
---

Sistema transversal de notificaciones entregado 2026-05-18 (primera versión, 3 eventos: creación/pase/transición a bandeja) y extendido 2026-05-19 (3 eventos más: comentario al tomador, estado final al iniciador, firma pendiente al firmante). Diseño extensible: `tipo` y `recurso_tipo` soportan más casos sin migración.

**Estado al 2026-05-19:**
- **Mig 51 (tabla `notificacion`)** aplicada en local Y prod Supabase al 2026-05-18.
- **SMTP Zoho** configurado y enviando real desde local + Railway. App password de 16 chars seteada en Railway. Smoke verificado.
- **`enviada_mail=TRUE` se persiste tras send exitoso** (2026-05-19) via wrapper `_enviar_mail_y_marcar` que abre sesión SQL nueva post-background — ver [[feedback_background_tasks_sesion_nueva]].
- **Eventos cubiertos:**
  - `tramite_bandeja_creacion` / `_pase` / `_transicion` → destinatario actual del trámite.
  - `tramite_comentario` → al usuario del agente tomador, excluyendo al autor del comentario.
  - `tramite_estado_final` → a la subarea iniciadora (solo si `iniciador_tipo='area_interna'`).
  - `tramite_firma_pendiente` → polimórfico (agente / subarea / equipo) según firmantes definidos.
- **Frontend campana en shell vanilla** (`index.html` + `frontend/js/menu.js` + `frontend/css/menu.css`, commit `c7833cc`). La versión React del TopBar es invisible en iframe (regla §14) — ambas conviven, la React queda solo para devs en `localhost:5173` standalone.

**How to apply:**
- Para sumar notif de otro evento: nueva función en `services/notificaciones.py` que reuse `_emitir_a_usuarios` (helper centralizado: INSERT con RETURNING + commit + encolado del background task con `_enviar_mail_y_marcar`). Hook en el endpoint backend, opcionalmente nuevo valor `tipo` para discriminar en frontend.
- Para sumar destinatario `iniciador` ciudadano/empresa: requiere modelo "portal ciudadano" futuro (hoy no tienen `id_usuario`).
- Patrón obligatorio: services post-commit del endpoint hacen su propio `db.commit()` ([[feedback_service_commit_propio]]).
- Background tasks abren sesión SQL nueva via `AsyncSessionLocal()` ([[feedback_background_tasks_sesion_nueva]]).

Ver CLAUDE.md §35 "Notificaciones a la bandeja" + "Notificaciones extendidas" para detalle completo + smoke E2E.
