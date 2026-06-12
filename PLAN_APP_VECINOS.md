# Plan — App Vecinos (PWA) · Portal del Ciudadano

> **Documento de iteración.** Cada etapa se trabaja contra este archivo: al cerrarla, se marca ✅ con fecha y se anotan las decisiones tomadas (mismo formato que `PLAN_MODULO_EMERGENCIAS.md`). El estado fue **verificado contra el código real de ambos repos el 2026-06-11** — este plan reemplaza al borrador de mayo, que daba por pendientes etapas que ya están entregadas.

## 0. Decisión tecnológica (revisada 2026-06-11)

**La "app Android" ES la PWA `zaris-vecinos`. No se construye app nativa.** Razones:

| Criterio | PWA (actual) | Android nativa (Kotlin) |
|---|---|---|
| Costo | $0 — Vercel free, sin Play Store | Cuenta Play Store USD 25 + mantenimiento de un segundo stack |
| Estado | **Ya está en producción** (`vecinos.zaris.com.ar`) | Cero código — reescribir todo |
| Instalación en Android | Chrome → "Agregar a pantalla de inicio" (instalable, ícono, splash, offline shell) | Play Store |
| Cámara / GPS / Push | Soportados por el navegador (input capture, Geolocation API, Web Push en Android Chrome) | Nativos |
| iOS | La misma PWA funciona (push incluido desde iOS 16.4 si se instala a Home) | Requeriría una app aparte |

**Stack vigente (no cambiar):** React 19 + Vite + `vite-plugin-pwa` + react-router 7, deploy Vercel, repo separado `CesarZeta/zaris-vecinos`. Backend: los routers `publico_*` de `zaris-zge` (FastAPI/Railway), JWT scope `publico`, sesión propia `zaris_vecino_session`.

**Opcional futuro (no es etapa):** si un municipio exige presencia en Play Store, empaquetar la MISMA PWA como TWA con PWABuilder/Bubblewrap. No agrega funcionalidad; solo distribución.

## 1. Estado real del plan original (verificado 2026-06-11)

| Etapa original | Estado | Evidencia |
|---|---|---|
| **0 — Backend público auth** | ✅ Completa (en prod) | `publico_auth` 8 endpoints + `get_current_ciudadano` + migs 52/53/76/79. **Corrección:** el email NO va por Zoho SMTP — Railway bloquea egress SMTP; se usa **Resend** (API HTTPS, §42 CLAUDE.md). |
| **1 — Scaffold PWA** | ✅ Completa | Repo `zaris-vecinos` con vite-plugin-pwa, iconos, deploy Vercel, dominio real `vecinos.zaris.com.ar`, Bienvenida con identidad del municipio. |
| **2 — Backend reclamos públicos** | 🟡 Parcial | `publico_reclamos.py` ✅ (POST/GET/detalle/catálogo/geo, guards "solo lo mío") + `publico_portal.py` ✅ (`/mi-resumen`). **Faltan:** adjuntos públicos y routers de push. |
| **3 — PWA auth + home + mis reclamos** | ✅ Completa | Pages: Login/Activar/Recuperar/Resetear/Home/MisReclamos/ReclamoDetalle/CompletarFicha. Alta pública en 2 pasos (mig 79) — superó al plan original. |
| **4 — Wizard nuevo reclamo** | 🟡 Parcial | `NuevoReclamoPage` ✅ con búsqueda de dirección (geocoding OSM con sesgo geográfico). **Faltan:** foto/cámara (depende de adjuntos públicos) y mapa con pin (no hay Leaflet en la PWA). |
| **5 — Push end-to-end** | ❌ Pendiente | Solo existe la tabla placeholder `ciudadano_push_subscription` (mig 53). Sin endpoints, sin pywebpush, sin SW handler. |
| **6 — Deploy + piloto** | 🟡 Parcial | Dominio + CORS + env vars ✅. **Faltan:** E2E en prod con vecino real (`ciudadano_credencial` en prod está vacía), branding del piloto, README municipio #2. |

**Alcance nuevo pedido por el usuario (2026-06-11):** sumar a la PWA las demás interacciones — **emergencias** (backend público YA listo, §44 Fase 5), **turnos** y **entradas**.

## 2. Etapas restantes

Orden recomendado: **A → B → C → D → E → F**. A primero (mayor valor para reclamos, cierra la deuda del plan viejo); B es la más barata (backend ya hecho); E (push) al final de las features porque es la más frágil y para entonces hay 4 tipos de contenido que notificar; F cierra el piloto.

---

### ETAPA A — Fotos en reclamos (adjuntos públicos) + pin en mapa ✅ (local, 2026-06-11 — falta deploy)

Cierra los restos de las etapas 2 y 4 del plan viejo.

**Backend (`zaris-zge`):**
- Router `/api/v1/publico/reclamos/{id}/adjuntos/*` con guard `get_current_ciudadano`: `POST /upload-url` + `POST /{id_adj}/confirm` + `GET` (lista con URLs firmadas). Clona el flujo de §26 (bucket privado `reclamos-adjuntos`, paths `reclamos/{id_reclamo}/{uuid}.{ext}`, fila `activo=FALSE` pre-upload, reusa `app/core/storage.py`).
- **Guard duro:** el reclamo debe ser DEL ciudadano del token (404 si no, mismo criterio que el detalle). Límites: solo imágenes, 10 MB, máx. 5 fotos por reclamo (anti-abuso público).
- Registrar el router ANTES de cualquier `{param}` greedy (§5) y smoke con cleanup (§ memoria smoke-cleanup-prod).

**PWA (`zaris-vecinos`):**
- En `NuevoReclamoPage`: `<input type="file" accept="image/*" capture="environment">` (abre la cámara en Android) + preview + cola de subida post-creación (crear reclamo → por cada foto: upload-url → PUT directo a Supabase → confirm). Si una foto falla, el reclamo queda creado y se informa cuántas subieron (patrón §26).
- En `ReclamoDetallePage`: galería de fotos propias (URLs firmadas).
- **Mapa con pin:** sumar `leaflet@1.9` vanilla (sin react-leaflet, §4) con tile OSM Standard + pin arrastrable, debajo del buscador de dirección — regla de diseño §23 (las DOS vías: buscador + pin). Workaround de iconos de Vite (§4) aplica.

**Criterio de cierre:** desde Android Chrome instalado como PWA, crear reclamo con foto sacada con la cámara y pin ajustado en el mapa → el reclamo aparece en el backoffice ZGE con `canal_origen='app_movil'`, la foto visible en el drawer y las coords correctas.

---

### ETAPA B — Emergencias en la PWA ⏳

**El backend ya está entregado** (§44 Fase 5, en prod): `/api/v1/publico/emergencias/*` con guard scope `publico` — `GET /tipos`, `GET /tipos/{id}/subtipos`, `GET /eventos` (mis reportes), `POST /eventos` (canal APP_VECINO forzado server-side, rate-limit 5/min/IP). Es el pendiente explícito de la Fase 5 del módulo Emergencias.

**PWA:**
- Card "Reportar emergencia" en Home (visualmente diferenciada — es urgencia, no trámite) + aviso fijo: *"Si hay riesgo de vida llamá al 911"*.
- `NuevaEmergenciaPage`: tipo (autocompletar sobre `/tipos`, patrón §23) → subtipo opcional → dirección (buscador OSM; reusar el componente de Etapa A con pin si ya está) → descripción. SIN datos de denunciante: salen del token.
- `MisEmergenciasPage` + detalle simple (número operativo `EM-YYYY-NNNNNN`, estado, fechas). Sumar conteo al `/mi-resumen` del portal si se decide mostrarlo en Home (requiere extender `publico_portal.py`).

**Criterio de cierre:** vecino logueado reporta una emergencia desde el celular → aparece en el Tablero COM del backoffice con badge "App Vecinos" → el vecino ve el estado actualizarse en "Mis reportes".

---

### ETAPA C — Turnos del vecino logueado ⏳

Hoy el autoservicio de turnos es **anónimo por token** (§33, `turnos_publico`): pide DNI a mano y el comprobante vive en un link. Esta etapa lo integra a la cuenta del vecino.

**Backend:**
- Endpoints nuevos con guard `get_current_ciudadano` (router `publico_turnos_vecino.py` o sección en `publico_portal.py` — decidir al implementar):
  - `GET /mis-turnos` — turnos del `id_ciudadano` del token (reservados + histórico).
  - `POST /reservar` — igual que `turnos_publico/reservar` pero el ciudadano sale del token (sin DNI manual, sin buscar_o_crear). Reusa los helpers existentes (`_slots_libres_recurso`, validación de disponibilidad §33, anti-doble-turno-por-día).
  - `PATCH /mis-turnos/{id}/cancelar` — solo turnos propios en estado `reservado`.
- `GET /prestaciones` y `GET /slots` públicos ya existen y se reusan tal cual (no requieren identidad).
- Los endpoints anónimos por token NO se tocan (siguen sirviendo al vecino sin cuenta).

**PWA:**
- `MisTurnosPage` + flujo de reserva en 2 pasos (prestación → slot), réplica simplificada del wizard público existente pero sin pedir datos personales.
- Home: el conteo de turnos vigentes ya viene en `/mi-resumen` — linkear la card a `MisTurnosPage`.

**Criterio de cierre:** vecino logueado reserva un turno, lo ve en "Mis turnos", lo cancela; el backoffice de Turnos refleja todo (con la ocupación espejo liberada al cancelar).

---

### ETAPA D — Entradas del vecino logueado ⏳

Espejo de la Etapa C para eventos con cupo (§33 Entradas: reusa `eventos` + `evento_reservas` de Agenda).

**Backend:**
- `GET /eventos-publicos` — eventos próximos con `admite_autoservicio=true` y cupo disponible (hoy el vecino solo llega por link directo al token del evento; esta lista los hace descubribles desde la app).
- `POST /eventos/{id}/reservar` (guard scope `publico`, ciudadano del token) + `GET /mis-entradas` (con `qr_codigo` para acreditación §27) + cancelar reserva propia.

**PWA:**
- `EventosPage` (cartelera) + `MisEntradasPage` con el **QR renderizado en el celular** (lib `qrcode` client-side, como `QRDisplay.tsx` del backoffice) — el operador lo escanea y acredita vía `POST /reservas/acreditar-qr` que ya existe.

**Criterio de cierre:** vecino descubre un evento en la app, reserva, muestra el QR en el celular y el operador lo acredita desde el backoffice.

---

### ETAPA E — Push notifications end-to-end ⏳

La etapa más frágil (navegador + SW + VAPID + permisos del SO). Se hace al final porque para entonces hay 4 fuentes de notificación: reclamos, emergencias, turnos, entradas.

**Backend:**
- VAPID keys generadas y en env vars de Railway (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIMS_EMAIL`). Recordar memoria: env vars de Railway son un set propio — setearlas explícitamente y testear en prod.
- `pip install pywebpush` + `app/services/push.py::enviar_push(id_ciudadano, titulo, cuerpo, url)`: lee suscripciones activas de `ciudadano_push_subscription`, envía; `410 Gone` → `activo=FALSE` (soft-delete §19).
- Router `/api/v1/publico/push/*` (guard scope `publico`): `GET /public-key` · `POST /subscribe` (UPSERT por `(id_ciudadano, endpoint)`) · `POST /unsubscribe`.
- Hooks **post-commit, best-effort** (patrón encuestas §42 — `try/except`, nunca rompen la operación; sesión nueva si corre en background task): cambio de estado de reclamo del ciudadano · cambio de estado de emergencia reportada por app · recordatorio no aplica en v1 (sin cron) · confirmación de turno/entrada es opcional (ya la ve en la app).
- Respeta `ciudadano_canal_preferido.canal_push` (toggle).

**PWA:**
- Pedir permiso de notificaciones **tras una acción del usuario** (toggle en `/configuracion`, NO popup automático al loguear — mejor tasa de aceptación y es el patrón recomendado).
- `pushManager.subscribe` con la public key → POST al backend. Handler `push` en el SW (mostrar notificación) + `notificationclick` (abrir la PWA en el detalle correspondiente).
- Página `/configuracion` con el toggle (escribe `canal_push` + subscribe/unsubscribe local).
- **Quirk conocido:** el SW viejo puede servir build cacheado (memoria `feedback_pwa_service_worker_sirve_build_viejo`) — al tocar el SW, verificar la actualización con una instalación limpia.

**Criterio de cierre:** agente cambia el estado de un reclamo en el backoffice → la notificación llega al celular con la PWA **cerrada** → tap → se abre el detalle del reclamo.

---

### ETAPA F — Cierre del piloto ⏳

- **Primer login real en prod:** `ciudadano_credencial` en prod está vacía — hacer el E2E completo de autoregistro (alta en 2 pasos → verificar email → login → completar ficha → crear reclamo) con un vecino/tester real, en prod.
- Branding del municipio piloto en `configuracion_general` (logo en bucket `config-assets`, nombre, descripción, colores) — editable desde Config → Identidad del backoffice.
- Template de mail: CTA con `municipio_color_primary` y fallback neutro (pendiente heredado de Etapa 0).
- Dominio por municipio (`vecinos.<municipio>.gob.ar`) si el piloto lo pide — CNAME en Vercel + alta exacta en CORS (FastAPI no acepta wildcards, §9).
- Docs: `docs/manual_alta_vecino.html` ya existe (guía pública); sumar README de `zaris-vecinos` con pasos para municipio #2 y, si hace falta, manual del portal logueado.

**Criterio de cierre:** un vecino real, sin asistencia, completa: alta → activación → reclamo con foto → recibe push al resolverse. Documentación lista para replicar en municipio #2.

---

## 3. Reglas transversales (aplican a TODAS las etapas)

1. **El `id_ciudadano` SIEMPRE sale del JWT**, nunca del body/param. Recurso ajeno → 404 con el mismo cuerpo que "no existe" (no filtrar existencia de terceros). Patrón ya vigente en `publico_reclamos`.
2. **La autogestión no afloja datos obligatorios** (memoria `feedback_autogestion_no_afloja_obligatorios`): validar en backend (422), no solo en UI.
3. **Rate-limit en todo POST público** (5/min/IP, `app/middleware/rate_limit.py`) — ya aplicado en emergencias; replicar en adjuntos/turnos/entradas.
4. **Routers de segmento fijo ANTES de los `{param}` greedy** en `main.py` (§5) — ya mordió 3 veces.
5. **Geocoding solo vía el helper `geocodificar_direccion()`** (sesgo geográfico del municipio, §23) — nunca llamar Nominatim por fuera.
6. **Sesión de la PWA = `zaris_vecino_session`** (shape propio, NO el dual-shape del backoffice). Cachear `getSnapshot` contra el string crudo (memoria `useSyncExternalStore`).
7. **Tras cada push backend, verificar prod** con `/openapi.json` (el autodeploy de Railway no es confiable, §9). Tras cada deploy PWA, descartar el SW viejo antes de juzgar.
8. **Smokes con datos únicos por corrida y cleanup inmediato** en prod.
9. La PWA se documenta en su propio repo; en `zaris-zge` solo viven los routers `publico_*` y este plan.

## 4. Registro de decisiones por etapa

> Completar al cerrar cada etapa: fecha, commits, decisiones tomadas, desvíos del plan.

- **2026-06-11 — Plan reescrito** contra el estado real de ambos repos. Decisión ratificada: PWA en lugar de app Android nativa (gratis, ya en prod, cubre cámara/GPS/push). Stack sin cambios. Se incorporó el alcance nuevo: emergencias (backend listo), turnos y entradas logueados.
- **2026-06-11 — ETAPA A implementada y verificada E2E en local.**
  - *Backend (zaris-zge):* router `publico_reclamos_adjuntos.py` (upload-url / confirm / GET con URLs firmadas), registrado en `main.py` antes del `GET /{id_reclamo}` greedy. Guard duro de pertenencia (reclamo ajeno → 404 cuerpo genérico), máx. 5 fotos activas por reclamo, solo imágenes ≤10 MB, sin fotos sobre reclamos cerrados, `id_usuario_alta=NULL` (vecino). Rate-limit 20/min/IP con clave prefijada `adjpub:` — **decisión:** el bucket in-memory de `rate_limit.py` clavea por string pelado y los endpoints públicos existentes comparten bucket por IP; el prefijo evita interferencia (los routers viejos quedan como están). **Sin DELETE público en v1** (el vecino no edita lo enviado, paridad con no poder cancelar). Smoke `backend/smoke_publico_adjuntos.py` 12/12 OK (acepta URL de prod como argv para re-correr tras el deploy).
  - *PWA (zaris-vecinos):* `leaflet@1.9.4` + `MapaPicker` propio (OSM Standard, pin arrastrable, `scrollWheelZoom:false` en mobile, botón "Usar mi ubicación actual" → `fuente='gps_dispositivo'`). `NuevoReclamoPage`: dirección pasó de chip-de-selección a **input editable + pin** (regla §23 — editar el texto NO borra coords; hint mono + "Quitar pin"); fotos con dos botones ("Sacar foto" `capture=environment` / "Elegir de galería" multiple), máx. 5, previews con quitar, subida secuencial post-creación con progreso y pantalla de aviso si alguna falla (el reclamo queda creado, §26). `ReclamoDetallePage`: galería con URLs firmadas, best-effort. API en `lib/reclamos.ts` (`subirFotos` con flujo 3 pasos).
  - *Quirk nuevo:* el `.env.local` de la PWA apunta a PROD (Railway) — para dev contra backend local se creó `.env.development.local` (`VITE_API_URL=http://127.0.0.1:8000`, solo modo dev, gitignored). Sin esto, el dev server pega a prod y los 401 confunden.
  - *Verificado navegando (login vecino demo 28547123):* crear reclamo con tipo + descripción + foto (DataTransfer) + dirección texto + pin en mapa → `REC-2026-000041` con `canal_origen='app_movil'`, `fuente='pin_manual'`, lat/lon persistidas, foto visible en galería del detalle.
  - **Pendiente para cerrar el criterio:** push del backend a prod (+ re-correr el smoke contra Railway), deploy de la PWA en Vercel, y prueba en Android Chrome real instalada como PWA.
