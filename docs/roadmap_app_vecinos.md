# App Vecinos — Roadmap de etapas 1 a 6

> Documento de planificación. Cada etapa va a generar un prompt independiente para Claude Code, en el momento en que se inicie.
> **Etapa 0 ya documentada en `prompt_etapa_0_backend_publico_minimo.md`.**

---

## Principios que aplican a TODAS las etapas

1. **Antes de empezar cada etapa, releer la sección correspondiente de CLAUDE.md** (que se va actualizando entre etapas) y verificar el schema real de la DB con `execute_sql` antes de codear sobre tablas existentes.
2. **No mezclar etapas.** Cerrar la etapa actual con su smoke test antes de pasar a la siguiente.
3. **Cada etapa entrega valor verificable end-to-end.** No hay etapas "de andamiaje invisible".
4. **Repo PWA: `zaris-vecinos`** (uno, no uno por municipio). Hosting: **Vercel**. Stack: **React + Vite + vite-plugin-pwa**.
5. **Backend extiende el repo existente `zaris-zge`**, no se hace repo nuevo de API.

---

## Etapa 1 — Scaffold PWA `zaris-vecinos`

### Objetivo
Tener un repo nuevo, deployado en Vercel, accesible por URL, que carga una pantalla de bienvenida con el branding del municipio leído del backend (Etapa 0). El shell de la PWA funciona, el manifest está instalable, el Service Worker está activo.

### Entregables
- Repo `zaris-vecinos` creado en GitHub bajo cuenta `CesarZeta`.
- Estructura:
  ```
  zaris-vecinos/
    public/
      icons/             # iconos 192x192, 512x512, maskable
    src/
      App.tsx
      main.tsx
      lib/
        api.ts           # cliente fetch tipado con base URL desde env
        identidad.ts     # hook para /publico/identidad-municipio
      pages/
        BienvenidaPage.tsx
      styles/
        tokens.css       # CSS variables, paleta inicial
        global.css
    index.html
    vite.config.ts       # con vite-plugin-pwa configurado
    package.json
    .env.example
    README.md
    .gitignore
  ```
- `vite-plugin-pwa` configurado:
  - Estrategia `injectManifest` o `generateSW` (definir cuál — probable `generateSW` para empezar simple).
  - Manifest con `name`, `short_name`, `theme_color`, `background_color`, icons.
  - Service Worker que precachea el bundle y muestra un fallback offline simple.
- Configurar Vercel:
  - Conectar repo.
  - Env vars: `VITE_API_URL=https://zaris-api-production-bf0b.up.railway.app`, `VITE_MUNICIPIO_SLUG=vicente-lopez`.
  - Dominio inicial: el `<project>.vercel.app` que da Vercel automático.
- Pantalla de Bienvenida que:
  - Llama a `GET /publico/identidad-municipio`.
  - Muestra logo del municipio (si está configurado), nombre, descripción.
  - Tiene un botón "Ingresar" que todavía no hace nada (placeholder, link a `/login`).
  - Aplica los colores del municipio (CSS variables seteadas en runtime con los hex que devuelve el endpoint).
- Sistema de diseño v1 (mobile-first):
  - Paleta CSS variables (`--app-cream`, `--app-ink`, `--app-primary` configurable, etc.).
  - Tipografía: Inter desde Google Fonts (sin Fraunces todavía).
  - Componentes base mínimos: `<Button>`, `<Card>`. Nada más por ahora.

### Criterios de aceptación
- [ ] PWA deployada en `<project>.vercel.app` con HTTPS.
- [ ] La pantalla muestra el branding del municipio leído del backend.
- [ ] Lighthouse PWA audit pasa: instalable, SW activo, manifest válido.
- [ ] Probar instalación en Android Chrome (botón "Agregar a inicio") y verificar que el icono queda en home screen.
- [ ] README documenta cómo correr local (`pnpm dev`), cómo deployar, qué env vars necesita.

### Notas de criterio (para advertirle a Claude Code)
- **NO usar Tailwind** en esta primera versión. CSS variables + clases utilitarias minimal. Si después decidimos Tailwind, lo agregamos. Razón: queremos que el sistema de diseño viva en `tokens.css`, no diluido en miles de clases inline.
- **NO usar el shell React del backoffice (`web-app/`)** como referencia visual. La PWA tiene su propio sistema visual. Solo coincide en algunos tokens (cream + verde de success).
- React Router v6 con `BrowserRouter`. Para Vercel + SPA va a requerir un `vercel.json` con rewrites a `index.html`. Documentarlo en README.

---

## Etapa 2 — Backend público: reclamos + adjuntos + push subscriptions

### Objetivo
Extender el backend para que la PWA pueda crear reclamos, listar los del ciudadano logueado, ver detalle, subir fotos, registrar suscripciones push.

### Entregables
- Router nuevo `app/api/routes/publico_reclamos.py`:
  - `POST /api/v1/publico/reclamos` — crea reclamo. `id_ciudadano` del JWT, no del body. `canal_origen='app_movil'`. Resto de campos del body (tipo, descripción, lat/lon, dirección, fuente_geolocalizacion).
  - `GET /api/v1/publico/reclamos` — lista paginada de reclamos del ciudadano logueado (no del municipio entero). `?limit=&offset=`. Incluye nro_reclamo, estado, fecha_alta, tipo_descripcion, último cambio de historial.
  - `GET /api/v1/publico/reclamos/{id}` — detalle con timeline humanizado. Verifica que `id_ciudadano = current_ciudadano.id_ciudadano` (si no, 404, no 403 — no revelar existencia).
- Router nuevo `app/api/routes/publico_adjuntos.py`:
  - `POST /api/v1/publico/reclamos/{id}/adjuntos/upload-url` — análogo al existente del backoffice. Valida que el reclamo sea del ciudadano logueado.
  - `POST /api/v1/publico/reclamos/{id}/adjuntos/{id_adj}/confirm` — confirma upload.
  - Reusa `app/core/storage.py` existente. Mismo bucket `reclamos-adjuntos`.
- Router nuevo `app/api/routes/publico_push.py`:
  - `POST /api/v1/publico/push/subscribe` — body `{ endpoint, p256dh, auth, user_agent }`. INSERT en `ciudadano_push_subscription`. Idempotente (UNIQUE constraint en `(id_ciudadano, endpoint)` ya está en mig 53).
  - `POST /api/v1/publico/push/unsubscribe` — soft-delete por endpoint.
- Endpoint público de catálogo:
  - `GET /api/v1/publico/catalogo/tipos-reclamo` — devuelve tipos de reclamo activos del municipio. La PWA lo usa en el wizard de alta.
- VAPID keys generadas (lib `cryptography` o `pywebpush`). Guardadas en env vars de Railway: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`. Endpoint público `GET /api/v1/publico/push/public-key` para que la PWA las consuma en el momento de suscribir.
- Hook en `PUT /reclamos/{id}/estado` (backoffice existente): cuando el reclamo cambia de estado y `id_ciudadano` tiene suscripciones push activas, agendar envío push (background task). **Función real de envío** se implementa en Etapa 5; en Etapa 2 dejar `app/services/push.py` con función `enviar_push(suscripcion, titulo, mensaje, url)` que solo loguea a stdout. Esto permite que el hook se conecte ahora y solo cambie la implementación interna después.

### Criterios de aceptación
- [ ] Smoke test que crea reclamo, lista, ve detalle, sube foto, suscribe push.
- [ ] Confirmación de que un ciudadano NO puede ver reclamos de otro ciudadano (test explícito).
- [ ] Confirmación de que un agente puede ver el reclamo creado desde la PWA en el backoffice ZGE (interoperabilidad con módulo Reclamos existente).
- [ ] Migraciones aplicadas en local + prod.
- [ ] VAPID public key accesible vía endpoint público.

---

## Etapa 3 — PWA: Auth + Home + Mis Reclamos (read-only)

### Objetivo
El ciudadano puede activar su cuenta (con el token del mail), loguearse, ver el home, ver el listado de sus reclamos, ver el detalle con timeline. **Todavía no puede crear reclamos.**

### Entregables
- Páginas:
  - `/login` — formulario DNI + password, link a "¿Olvidaste tu contraseña?".
  - `/activar?token=<uuid>` — pantalla de elegir password al activar (validación de token al cargar la página, error si expiró).
  - `/recuperar` — pide DNI, manda mail.
  - `/resetear?token=<uuid>` — análogo a activar pero para recovery.
  - `/` (home, requiere auth) — saludo personal + tarjetas grandes: "Nuevo reclamo" (deshabilitado, dice "Próximamente" por ahora — se activa en Etapa 4) y "Mis reclamos".
  - `/reclamos` — listado paginado de los reclamos del ciudadano. Tarjetas con: nro_reclamo, fecha, tipo, estado (badge de color).
  - `/reclamos/:id` — detalle: tipo, descripción, lat/lon (con mini-mapa Leaflet read-only), foto si hay, timeline de estados humanizado.
- Auth flow:
  - JWT en `localStorage` con clave `vecinos_session`.
  - Helper `fetchAuth` que agrega `Authorization: Bearer <token>` automáticamente.
  - Si la API devuelve 401, limpiar sesión y redirigir a `/login`.
  - Guard de rutas: rutas que requieren auth redirigen a `/login` si no hay token.
- Componentes nuevos:
  - `<Badge>` — para estados de reclamo con los colores del DS.
  - `<Timeline>` — vertical, último arriba.
  - `<EmptyState>` — para "todavía no tenés reclamos".
  - `<Input>`, `<PasswordInput>` con validación visual.

### Criterios de aceptación
- [ ] Flow completo: agente crea ciudadano en backoffice → mail real recibido en bandeja del email puesto → ciudadano clickea link → activa → setea password → logueado → ve home.
- [ ] Login con DNI + password funciona.
- [ ] Recovery funciona end-to-end (otro mail real recibido + reset).
- [ ] Listado de "Mis reclamos" muestra solo los del ciudadano logueado (verificable creando reclamos vía backoffice para distintos ciudadanos).
- [ ] Detalle muestra timeline correcto.
- [ ] Funciona en Android Chrome instalado como PWA.
- [ ] No funciona acceder a `/reclamos/X` cuando X no es del ciudadano (404 silencioso).

### Notas de criterio
- **Diseño:** mobile-first puro. Áreas de toque ≥44px. Tipografía base 16px. Padding generoso. No densidad de información — una acción por pantalla.
- **Token JWT en localStorage:** sí, asumimos el trade-off de seguridad (XSS puede leerlo). Alternativa más segura sería httpOnly cookies pero complica CORS cross-domain. Para esta etapa, localStorage es aceptable.

---

## Etapa 4 — PWA: Nuevo Reclamo (wizard completo)

### Objetivo
Permitir al ciudadano crear un reclamo desde la app, con foto y geolocalización.

### Entregables
- Wizard de 4 pantallas:
  1. **Tipo:** lista buscable de `tipo_reclamo` activos. Si la lista es larga, agregar buscador de input. Selección obligatoria.
  2. **Ubicación:** opciones (a) usar mi ubicación actual (Geolocation API del navegador), (b) elegir manualmente en un mapa (Leaflet con tile CartoDB Positron — consistencia con el backoffice §4 CLAUDE.md), (c) buscar dirección (usa endpoint `/api/v1/geo/buscar` existente, ya proxea Nominatim).
  3. **Foto + comentario:** opcional. File input con `accept="image/*"` y `capture="environment"` (abre cámara directo en mobile). Preview. Comentario libre (textarea, máx 1000 chars).
  4. **Confirmar:** muestra resumen de los 3 pasos, botón "Enviar".
- Submit:
  1. `POST /publico/reclamos` con los datos → recibir `id_reclamo` y `nro_reclamo`.
  2. Si hay foto: `POST .../adjuntos/upload-url` → `PUT` directo a Supabase → `POST .../confirm`. Si el upload falla, mostrar toast "Reclamo creado, pero la foto no se pudo subir" y seguir.
  3. Mostrar pantalla de éxito con el `nro_reclamo` y link a "Ver mis reclamos".
- Navegación entre pasos:
  - Botón "Siguiente" sticky abajo.
  - Botón "Atrás" arriba a la izquierda.
  - El estado del wizard se conserva en memoria (no en localStorage — si la PWA se cierra, se pierde, OK para MVP).
  - Botón "Salir" en el header del wizard pide confirmación ("Vas a perder los datos. ¿Salir?").
- Activar la tarjeta "Nuevo reclamo" del home (deshabilitada en Etapa 3).

### Criterios de aceptación
- [ ] Crear reclamo completo end-to-end (foto + geo) en Android Chrome instalado.
- [ ] El reclamo aparece en el backoffice ZGE marcado con `canal_origen='app_movil'`.
- [ ] La foto se ve en el drawer de detalle del backoffice.
- [ ] Crear reclamo sin foto también funciona.
- [ ] Crear reclamo con ubicación de GPS también funciona y la lat/lon es razonable (chequear contra dónde está parado el tester).
- [ ] Si el endpoint de reclamos tarda >5s, la UI muestra spinner y no se "rompe".
- [ ] El reclamo recién creado aparece en "Mis reclamos" sin tener que refrescar manualmente.

### Notas de criterio
- **Permisos del navegador:** geolocation y cámara requieren consent. Manejar el caso de rechazo con mensajes claros ("Necesitamos acceso a la cámara para que puedas adjuntar foto. Podés activar el permiso en los ajustes del navegador.").
- **Mapa:** Leaflet 1.9 vanilla, mismo patrón que el backoffice (§4 CLAUDE.md, ver `MapaPicker.tsx`). Workaround obligatorio de iconos marker.

---

## Etapa 5 — Push notifications end-to-end

### Objetivo
Cuando un reclamo cambia de estado, el ciudadano recibe una notificación push en el celular, aunque la app esté cerrada.

### Entregables
- Backend:
  - `app/services/push.py` con función real `enviar_push(...)` usando `pywebpush`.
  - Hook en `PUT /reclamos/{id}/estado` (ya conectado en Etapa 2) ahora hace envío real.
  - Manejar errores: si `pywebpush` devuelve 410 Gone (suscripción expirada), marcar `ciudadano_push_subscription.activo=FALSE`.
- PWA:
  - Al loguearse, pedir permiso de notificaciones. Si lo concede, registrar el SW y suscribir al endpoint push del navegador → enviar suscripción a `/publico/push/subscribe`.
  - Handler en el Service Worker (`registerSW.js` o equivalente con vite-plugin-pwa) que muestra la notificación cuando llega un push.
  - Click en la notificación → abre la PWA en `/reclamos/<id>` correspondiente.
  - Pantalla de ajustes (`/configuracion`) donde el ciudadano puede ver "notificaciones activas/inactivas" y un toggle para desuscribirse.
- Smoke test end-to-end:
  1. Ciudadano se loguea, acepta permisos push.
  2. Verificar fila en `ciudadano_push_subscription` con `activo=TRUE`.
  3. Agente en backoffice cambia estado del reclamo.
  4. Notificación llega al celular del tester (PWA cerrada).
  5. Tap en la notificación → abre la app en el detalle del reclamo.

### Criterios de aceptación
- [ ] Permiso push pedido al usuario una vez logueado (no antes).
- [ ] Cambio de estado en backoffice → notif en celular del ciudadano correcto.
- [ ] Funciona con la PWA cerrada (no solo en background).
- [ ] Test con 2 dispositivos del mismo ciudadano (notif llega a ambos).
- [ ] Test con permiso revocado por el usuario (la app no spamea pedidos).
- [ ] Test en iOS Safari 16.4+ instalada como PWA (puede saltar — documentar resultado).
- [ ] VAPID keys en env vars de Railway, no hardcoded.

### Notas de criterio
- **iOS:** push solo funciona si la PWA fue instalada explícitamente en home screen. Documentar esto en la pantalla de "configuración" como restricción del sistema, no como bug.
- **Costo de Web Push:** cero. No depende de FCM ni APNs directamente (eso lo maneja el navegador).
- **Si pywebpush no funciona bien en Railway** (algún issue con SSL o crypto), evaluar alternativa: `webpush_dataclasses` o stack JS dedicado. Pero arrancar con pywebpush.

---

## Etapa 6 — Deploy + dominio + smoke E2E + handoff a un municipio

### Objetivo
Tener la PWA andando con un municipio real (Vicente López como cliente piloto), con su dominio configurado, su branding cargado, y una prueba end-to-end real con un vecino externo.

### Entregables
- Dominio configurado en Vercel: `vecinos.<municipio>.gob.ar` con CNAME apuntando a Vercel. SSL automático.
  - **Plan B para pruebas pre-municipio:** usar subdominio bajo `zaris.com.ar` (que ya controlamos vía Cloudflare — ver memoria [[project_dominio_personalizado]]). Candidato natural: `vecinos.zaris.com.ar` o `vecinos-demo.zaris.com.ar`. Esto permite hacer el smoke E2E completo sin depender del trámite DNS del municipio.
- Backend en Railway con env vars finales (`APP_VECINOS_FRONTEND_URL=https://vecinos.<municipio>.gob.ar`).
- CORS en backend agregando el dominio real.
- Branding del municipio cargado vía SQL en `configuracion_general` (logo, nombre, descripción, colores).
- Smoke E2E con un tester externo:
  1. Tester abre `vecinos.<municipio>.gob.ar` en Android Chrome.
  2. Agente del municipio lo da de alta en el backoffice.
  3. Tester recibe mail de activación en su mail real.
  4. Activa, setea password, loguea.
  5. Crea un reclamo con foto y geo.
  6. Agente lo ve en backoffice, asigna OT, cambia estado.
  7. Tester recibe push notification.
  8. Click en push → abre detalle del reclamo.
  9. Estado cambia a "Resuelto" → otra push.
- Documentación:
  - Manual operativo del agente: "Cómo dar de alta a un vecino" + "Cómo trabajar reclamos que vienen de la app".
  - Folleto/instrucciones para el vecino: "Cómo instalar la app, cómo activar tu cuenta, cómo hacer un reclamo".
- README del repo `zaris-vecinos` actualizado con instrucciones de despliegue para un municipio nuevo (los pasos para sumar municipio #2).

### Criterios de aceptación
- [ ] Smoke E2E con tester externo pasa todos los pasos.
- [ ] Dominio funciona con HTTPS.
- [ ] Push notifications funcionan en producción.
- [ ] Documentación operativa entregada.
- [ ] Repo bien documentado para que sumar municipio #2 sea solo: crear proyecto Vercel, setear env vars, configurar dominio, cargar branding en DB.

---

## Estimación de tiempo

Esto es complejidad técnica, no calendario — depende de cuántas horas le dediques por día.

| Etapa | Complejidad relativa |
|---|---|
| 0 — Backend público mínimo | Media |
| 1 — Scaffold PWA | Baja-Media |
| 2 — Backend público extendido | Media |
| 3 — PWA auth + read-only | Media-Alta |
| 4 — PWA wizard nuevo reclamo | Alta |
| 5 — Push notifications | Alta (parte más frágil) |
| 6 — Deploy + smoke | Media |

**Las etapas más arriesgadas son la 4 (wizard con cámara y geo + integración de adjuntos) y la 5 (push, que tiene muchos puntos de falla entre navegador, SW, VAPID, pywebpush).** Tener paciencia con esas dos, no apurarlas.

---

## Decisiones a postergar (no resolver ahora)

Estas se van a abrir cuando lleguemos al momento; no las cierres ahora:

1. **Refresh tokens:** ¿agregamos refresh tokens al JWT cuando un vecino tiene la app instalada por meses? Hoy: JWT de 30 días, re-login después. Si la fricción es real, evaluamos refresh tokens en una iteración.
2. **PWA shell para Funcionarios** (`zaris-funcionarios`): mismo stack, pero con scope `agente` o uno nuevo `funcionario` con permisos extendidos. Decidir si comparte código con `zaris-vecinos` (componentes UI) o es repo separado completo.
3. **Multi-tenant en una sola API:** hoy cada municipio tendrá su deploy backend separado. Si el costo de Railway escala mal, consolidar a una API con `id_municipio` derivado del subdomain.
4. **Eliminación de cuenta del vecino:** GDPR / Ley de Protección de Datos Personales argentina (25.326) puede exigir endpoint de "borrar mi cuenta". Resolver cuando aparezca el requerimiento.
5. **Encuestas de satisfacción post-resolución:** "Tu reclamo fue resuelto, ¿cómo estuvo la atención?" — feature pedible por municipios, no en MVP.

---

## Cómo seguimos

Al cerrar **Etapa 0**, hacé una sesión nueva con Claude (este chat o uno nuevo, según convenga) y pedí: *"Armame el prompt de la Etapa 1 según el roadmap que tenemos en `App Vecinos — Roadmap`."* — el roadmap actualizado vivirá en tu `CLAUDE.md` o en un archivo aparte del repo.

**Recomendación operativa:** mantené este documento actualizado a medida que avanzan las etapas. Cuando cierres la Etapa N, agregale un breve registro de "qué cambió respecto al plan original" — eso te va a salvar de discutir en Etapa N+1 cosas que ya resolviste sin querer.
