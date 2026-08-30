---
name: modulo-encuestas
description: "Usar al trabajar en el módulo Encuestas (CSAT — satisfacción) de ZARIS (archivos: backend/app/api/routes/encuestas_admin.py, app/services/encuestas_service.py, frontend/encuesta.html, web-app/src/modules/encuestas/; tablas: encuesta_plantilla, encuesta_pregunta, encuesta_opcion, encuesta_envio, encuesta_respuesta, encuesta_respuesta_detalle). Cubre el disparo automático al cerrar reclamos y cumplir turnos, encuesta_envio polimórfico (id_reclamo XOR id_turno), anti-fatiga, delay/expiración, dispatcher con X-Dispatcher-Token, form público por token, email vía Resend y los quirks SQL del módulo. Invocar ANTES de tocar cualquier endpoint, tabla, dispatcher o pantalla de Encuestas."
---

# Módulo Encuestas (CSAT) — §42 — Reglas de negocio

Encuestas de satisfacción disparadas al cierre de reclamos (Resuelto) **y al cumplir turnos** (mig 72). Encuesta estándar ZARIS (no editable por municipio en v1), ramificación condicional según satisfacción inicial. DB: mig 57 (6 tablas + toggle) + 58 (tracking atención) + 72 (turnos). Todas las fases entregadas y verificadas E2E (auditoría email, services, router admin, form público, dispatcher, encuesta de turnos). Backoffice React `web-app/src/modules/encuestas/`.

### Tablas (mig 57 + 58 + 72)
`encuesta_plantilla` → `encuesta_pregunta` → `encuesta_opcion` (catálogo); `encuesta_envio` → `encuesta_respuesta` (1:1) → `encuesta_respuesta_detalle`. PKs estilo `id_<tabla>`, estándar §10 completo, RLS habilitado sin políticas (deny-all, service_role bypassa, §26). Mig 58 sumó a `encuesta_respuesta`: `atendida`/`atendida_por`/`fecha_atendida` + índice parcial `idx_encuesta_respuesta_pendientes`.

> **`encuesta_envio` es polimórfico desde mig 72:** FK física a `ciudadanos` (siempre) + **exactamente uno** de `id_reclamo` / `id_turno` (CHECK `ck_encuesta_envio_origen` NOT VALID). `encuesta_plantilla.tipo` ∈ `{reclamos, tramites, turnos}` selecciona qué preguntas se sirven. Hay 1 plantilla activa `tipo='reclamos'` y 1 `tipo='turnos'` (ambas en local + prod). **Cualquier query que toque `encuesta_envio` debe hacer LEFT JOIN a reclamos/turnos (NO inner), y ramificar por origen** — los 3 puntos que lo hacían con inner JOIN (`enviar_email_encuesta`, `registrar_respuesta`, `cargar_encuesta` del router público) se corrigieron en la mig 72.

### Disparo automático
- **Reclamos:** se disparan **solo al cerrar con estado `'Resuelto'`** (NO `'Cancelado'`). Service `encuestas_service.crear_envio_para_reclamo(db, id_reclamo) -> tuple[mapping|None, motivo]`.
- **Turnos (mig 72):** se disparan **al cumplir un turno** (`PATCH /turnos/{id}/cumplir`, §33). Service `crear_envio_para_turno(db, id_turno) -> tuple[mapping|None, motivo]` — espejo del de reclamos pero usa la plantilla `tipo='turnos'` y la FK `id_turno`; la subárea para anti-fatiga sale de `turnos.id_subarea` o, en su defecto, de la prestación (`tipo_prestacion.id_subarea`). El hook está en `routes/turnos.py::cumplir_turno`, **tras el commit**, best-effort (`try/except`, no rompe el cumplimiento). El **email lo manda el dispatcher existente con delay 24h** (`procesar_envios_pendientes`, que es genérico — recorre envíos `pendiente` sin asumir origen); `enviar_email_encuesta` ramifica el render: `_render_email_turno` (asunto "Tu opinión sobre la atención…", referencia = nombre de la prestación + fecha) vs `_render_email_encuesta` (reclamo). El form público es genérico por token → carga la encuesta de turno sin cambios de UI.
- El segundo elemento del tuple es una constante `MOTIVO_*` (string legible) que el endpoint `POST /disparar` mapea a 422. Constantes nuevas: `MOTIVO_SIN_PLANTILLA_TURNO`, `MOTIVO_NO_CUMPLIDO`.

### Toggle de activación
- Clave `encuestas_activas` (boolean) en `configuracion_general`. Si `'false'`, el service no crea envíos (ni de reclamos ni de turnos). Default tras mig 57: `'true'`.

### Resolución de subárea
- La subárea del envío se deriva de `tipo_reclamo.id_subarea` (vía `reclamos.id_tipo_reclamo`), con fallback a `reclamos.id_subarea` (legacy puede ser NULL, §27). Aplica al anti-fatiga, a la notificación al área cuando el vecino solicita contacto, y a los dashboards por-área.

### Anti-fatiga
- Un ciudadano no recibe más de una encuesta de la misma subárea (derivada) en los últimos 30 días. El dashboard agrupa por área.
- **Desactivable (desde 2026-05-25, mig 60):** la regla se puede apagar con la clave `encuestas_antifatiga_activo` en `configuracion_general` (toggle en Config → Sistema). `encuestas_service.antifatiga_esta_activo(db)` la lee; default seguro TRUE (clave ausente/error → regla activa). Con `'false'` se encuesta en cada cierre. `DIAS_ANTIFATIGA=30` sigue hardcodeado (solo el on/off es configurable).

### Delay de envío
- El email se envía 24 h después del cierre (no inmediato): dar tiempo a verificar que la solución persistió. El dispatcher procesa envíos `'pendiente'` con `fecha_alta < NOW() - 24h`.

### Expiración
- Los links expiran 15 días después del envío. `expirar_envios_vencidos()` marca `'expirada'` los `'enviada'/'abierta'` vencidos. El form público (2D) devolverá 410 Gone para tokens expirados.

### Email
- Reutiliza el sender central `app.services.email.enviar_mail(...) -> bool` (NO existe `email_service.enviar_email`; ver auditoría 2A). Template inline en `encuestas_service._render_email_encuesta`. `from_override` con display name del municipio sobre `RESEND_FROM` (§38, §42). Si el vecino solicita contacto (rama insatisfechos, P7=Sí), se notifica por email a los usuarios de la subárea.

### Datos personales / logs
- Los endpoints de dashboard NO devuelven datos personales del ciudadano. Solo `/envios/{id}` y `/respuestas/pendientes-contacto` los incluyen (para que el agente contacte). El form público (2D) NO devolverá nombre/email/DNI.
- Logs del módulo: nunca email completo, nunca texto libre de respuestas, nunca token completo (truncar a 8 chars con `_tok()`).

### Quirks SQL del módulo (asyncpg)
- INTERVAL parametrizado: usar `make_interval(days => :p)` / `make_interval(months => :p)`, NO `(:p || ' days')::interval` (rompe con int).
- Fin de rango de fecha: pasar `hasta_excl = hasta + timedelta(days=1)` como objeto `date` y comparar `< :hasta_excl`, NO `(:hasta::date + 1)` (el `::date` rompe el parser de bind params de asyncpg). Familia de [[feedback_asyncpg_extract_cast_date]].

### Router admin (`/api/v1/admin/encuestas`, fase 2C)
Auth a nivel router (`dependencies=[Depends(get_current_user)]`, §39). Registrado en `main.py` **ANTES** de `admin_tablas_router` (evita el `/{tabla}` greedy que atraparía `'encuestas'`, §5). Mono-municipio (§38): filtra por query param `id_municipio` (default 1), NO por un `user.id_municipio` inexistente (`get_current_user` no lo expone).

| Verbo | Path | Notas |
|---|---|---|
| GET | `/plantillas` · `/plantillas/{id}` | Detalle con preguntas + opciones anidadas |
| GET | `/envios` · `/envios/{id}` | Filtros estado/reclamo/fecha; `X-Total-Count`. Detalle incluye respuesta anidada |
| GET | `/respuestas/pendientes-contacto` | `solicita_contacto=TRUE AND atendida=FALSE`, orden FIFO, con datos del ciudadano |
| GET | `/dashboard/resumen` · `/por-area` · `/evolucion` · `/comentarios` | DB vacía → ceros, no rompe |
| POST | `/disparar` | 201 o 422 con motivo concreto |
| PATCH | `/respuestas/{id}/atender` | nivel ≤ 2; 422 si ya atendida |

### Niveles de acceso al módulo
- Listados (envíos, plantillas, disparar): cualquier usuario autenticado.
- Dashboards (resumen, por-area, evolucion, comentarios, pendientes-contacto): admin/supervisor (`nivel_acceso <= 2`), vía helper `_require_supervisor(user)` en `encuestas_admin.py`.
- Atender respuestas (`PATCH /respuestas/{id}/atender`): admin/supervisor.
- Endpoints públicos `/api/v1/publico/encuesta/*`: SIN auth, validados por token UUID + rate limiting 5/min por IP (in-memory, `app/middleware/rate_limit.py`). Router separado (§39). Nunca devuelven datos personales del ciudadano ni descripción del reclamo (§40). Token inválido/inexistente → 404; completada → 410; expirada → 410 (y marca `estado='expirada'`). IP real vía `app/utils/request_helpers.py::get_real_ip` (lee `X-Forwarded-For` por el proxy de Railway). `valor_texto` se trunca a 1000 chars (no se rechaza); body máx 4 KB.

### Dispatcher (fase 2E — endpoint ENTREGADO, cron pendiente)
Endpoint `POST /api/v1/admin/encuestas/dispatcher/ejecutar` (commit `bb51749`) con override de auth (header `X-Dispatcher-Token` en vez de JWT — máquina, no humano), token en `settings.DISPATCHER_TOKEN` (Railway env var, NO commitear). Llama a `procesar_envios_pendientes()` (envíos `pendiente` con `fecha_alta < NOW()-24h`) + `expirar_envios_vencidos()`. **El token de `.env.local` es de DEV (≠ el de Railway) — usar el de Railway para disparar prod, sino 401.** Cron horario via GitHub Actions (`.github/workflows/encuestas-dispatcher.yml`) = **sub-bloque D, NO implementado**.

### Hook de cierre (fase 2E.C — ENTREGADO 2026-05-23)
Hook no-bloqueante que crea el `encuesta_envio` al pasar un reclamo a 'Resuelto'. En 2 puntos, **tras el `db.commit()`** (nunca antes): `cambiar_estado` en `reclamos.py` (cierre manual, condicionado a `nuevo_estado=='Resuelto'`) y helper `_disparar_encuesta()` en `ordenes_trabajo.py` (llamado tras los commits de `cambiar_estado_ot` y `aprobar_ot`). Defensivo: `try/except` con log warning, sin re-raise — el cierre del reclamo nunca falla por encuestas (verificado V6). `crear_envio_para_reclamo` devuelve **tupla** `(fila_mapping|None, motivo)`, NO un objeto — acceso por key `envio["id_encuesta_envio"]`. `_resolver_reclamo` NO commitea (lo hacen sus callers).

### Form público del ciudadano (fase 2D frontend — ENTREGADO 2026-05-23)
`frontend/encuesta.html` (vanilla público, sin sesión, auth por token UUID). Consume `GET/POST /api/v1/publico/encuesta/{token}` (backend 2D ya existía). Ramificación condicional client-side: P1 likert 1-5 → rama visible (`<=2 insatisfechos`, `3 neutrales`, `>=4 satisfechos`); el backend recalcula `rama_seguida` server-side. Verificado en navegador (local + prod). Link del email apunta a `{FRONTEND_BASE_URL}/frontend/encuesta.html?token=...` (default prod `zge.zaris.com.ar`).

### Fixes del email (2026-05-23)
- **Logo URL absoluta** (`b5d9162`): `municipio_logo_url` puede ser ruta relativa (`/design-system/...`) → `<img>` roto en clientes de email. Helper `_absolutizar_url()` en `encuestas_service.py` la prefija con `FRONTEND_BASE_URL` si no es http(s). URL del bucket Supabase (ya absoluta) queda intacta. **En prod el logo sale del bucket `config-assets`; el `/design-system/...` es solo el placeholder de local.**
- **`fecha_cierre`** (`938e7f5`): `cambiar_estado` y `_resolver_reclamo` no seteaban `reclamos.fecha_cierre` al pasar a estado final (§22 lo exige) → el email mostraba "cerrado el ." vacío. Fix: `fecha_cierre=NOW()` al pasar a Resuelto/Cancelado (CASE en `cambiar_estado` para no pisar en transiciones intermedias).

### Email vía Resend (API HTTP) — RESUELTO 2026-05-24
Railway bloquea egress SMTP (587/465 timeout); Resend usa HTTPS/443. `services/email.py` reescrito con `httpx.AsyncClient` contra `POST https://api.resend.com/emails`.
- **`enviar_mail(to, subject, body_html, body_text=None, from_override=None) -> bool` es ASYNC** (los 3 callers async ganaron `await`; las 2 fns de App Vecinos pasaron a `async def`). **`enviar_mail_raise(...) -> str`** devuelve `message_id`, levanta `ResendError`; `enviar_mail` la envuelve a bool. Modo MOCK si `RESEND_API_KEY` vacía. `message_id` solo en logs (no en DB).
- **Config**: `RESEND_API_KEY` (NO commitear) + `RESEND_FROM` (default `notificaciones@zaris.com.ar`). `extra="ignore"` en pydantic-settings (sino el backend no arranca con `SMTP_*` viejas residuales, [[feedback_pydantic_extra_forbidden_al_borrar_settings]]).
- **El remitente debe ser EXACTAMENTE el dominio verificado en Resend: `@zaris.com.ar` (raíz), NO `@send.zaris.com.ar`** (subdominio da 403). Ver [[reference_railway_bloquea_egress_smtp]].

### Sanitización de PII en logs (Ley 25.326)
`app.utils.log_helpers.mask_email()` → `<char>***@<dominio>` (3 asteriscos fijos), aplicado en los 4 logs `to=` de `services/email.py`. Tokens: helper `_tok()` (8 chars). Smoke `backend/scripts/test_mask_email.py`.

### UI backoffice + agenda de turnos
- `views/PlantillasView.tsx` (tab "Encuestas" en `/encuestas/plantillas`): plantillas activas (reclamos/turnos) + preguntas por rama. Filtro TIPO + `id_plantilla` en `/envios` y `/dashboard/resumen` (columnas Tipo/Referencia).
- **Trap polimórfico** ([[encuesta_envio_polimorfico_left_join]]): `pendientes-contacto`/`dashboard/resumen`/`/envios` usan LEFT JOIN reclamos+turnos+tipo_prestacion (inner a reclamos excluía turnos). `referencia`=`COALESCE(nro_reclamo, prestacion_nombre)`. `dashboard/por-area` solo-reclamos. `POST /disparar` acepta `id_turno`.
- La **agenda solo-turnos** vive en §33 (`turnos/pages/AgendaTurnos.tsx`), no reusa la Gantt de Agenda.

### Encuestas de ENTRADAS (mig 98 + 98b, 2026-07-18)

Tercera rama del polimorfismo: `encuesta_envio.id_evento_reserva` (FK `ON DELETE RESTRICT`, mismo criterio que `id_turno`) + `ck_encuesta_envio_origen` XOR de 3 + tipo `'entradas'` sumado a `ck_encuesta_plantilla_tipo`. **Disparo:** al pasar la reserva a `asistio` (acreditación) — hook post-commit best-effort en `agenda_v2._patch_reserva_estado`, cubre el PATCH por id Y el acreditar-QR con un solo punto. `crear_envio_para_entrada` (service) espeja al de turnos: mismo gate `encuestas_activas`, anti-fatiga (subárea desde `eventos.id_subarea`), plantilla activa `tipo='entradas'` (seed 98b: "Encuesta de asistencia a eventos", likert5 + texto_libre; sin plantilla → return silencioso). **Al sumar OTRA rama futura:** ampliar el CHECK, los LEFT JOIN de dispatcher/admin/público/schemas ([[encuesta_envio_polimorfico_left_join]]) Y los label-maps del frontend (`EnviosView`/`PlantillasView`). `referencia` = `COALESCE(nro_reclamo, prestacion_nombre, evento_nombre, numero_expediente)`.

### Encuestas de TRÁMITES (mig 101 + 101b, 2026-08-30)

Cuarta rama: `encuesta_envio.id_tramite` (FK `ON DELETE RESTRICT`) + `ck_encuesta_envio_origen` XOR de 4 + índice parcial. **Disparo:** cuando el trámite **termina con `resultado` aprobado/rechazado** e iniciador **ciudadano** (decisión de César: lo que se comunica es "terminó y fue aprobado/rechazado"). Hook en `services/tramites/ciclo_vida.al_terminar` (post-commit; lo llaman la transición final y `POST /resultado`). `crear_envio_para_tramite` espeja al de entradas: gate `encuestas_activas`, anti-fatiga (subárea = `id_subarea_actual` o la del agente destinatario), plantilla `tipo='tramites'` (seed 101b: "Encuesta de satisfacción de trámites", likert5 + texto_libre). `_render_email_tramite` (asunto "Tu opinión sobre la gestión de tu trámite…", menciona expediente + tipo + resultado, sin datos del expediente). LEFT JOIN `tramite trm` (+ `tipo_tramite_version`/`tipo_tramite` donde hace falta el nombre del tipo) en dispatcher, `registrar_respuesta`, público y los 4 SELECT del admin; `POST /disparar` acepta `id_tramite`; filtro `?id_tramite=` en `/envios`. Los label-maps del front ya tenían `tramites`.
