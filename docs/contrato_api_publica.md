# Contrato de API pública — App Vecinos (y autoservicio anónimo)

Referencia de los endpoints que consume la PWA `zaris-vecinos` (repo separado).
Todos viven en el backend de **`zaris-zge`** bajo `/api/v1/publico/*` (+ algunos
autoservicios anónimos por token bajo `/api/v1/turnos/publico/*` y
`/api/v1/agenda/publico/*`).

> **Esta tabla es el contrato.** Si la PWA necesita un campo o endpoint nuevo,
> el cambio es backend (este repo), se acuerda el shape acá y se mergea primero.
> Generado leyendo los routers reales — ante la duda, la fuente de verdad es el
> código en `backend/app/api/routes/publico_*.py` y `/docs` (Swagger).

## Prod

- API: `https://zaris-api-production-bf0b.up.railway.app`
- Swagger (todos los schemas): `…/docs`
- PWA: `https://vecinos.zaris.com.ar`

## Dos clases de autenticación

| Guard | Cómo se obtiene | Qué protege |
|---|---|---|
| **`scope: publico`** (vecino logueado) | JWT del `POST /publico/auth/login` o de activar/resetear. Header `Authorization: Bearer <token>`. Vigencia 30 días. | Todo lo que opera sobre los datos del vecino. El `id_ciudadano` SIEMPRE sale del token, nunca del body/URL. |
| **Sin auth** (anónimo) | — | Identidad del municipio, alta pública, autoservicios por token UUID (eventos/turnos compartidos por link). |

---

## 1. Auth del vecino — `/api/v1/publico/auth`

| Verbo | Ruta | Auth | Para qué |
|---|---|---|---|
| POST | `/login` | — | DNI + password → JWT scope publico. Lockout: 5 fallidos → 15 min. |
| GET | `/me` | publico | Datos del vecino logueado (incluye `ficha_completa`). |
| POST | `/activar` | — | Activa con `token_activacion` (7d), setea password → JWT. |
| POST | `/reenviar-activacion` | — | Reenvía mail. Anti-enumeración: siempre 200. |
| POST | `/recuperar-password` | — | Pide mail de recovery. Anti-enumeración: siempre 200. |
| POST | `/resetear-password` | — | Aplica nuevo pass con `token_recovery` (24h) → JWT. |
| GET | `/nacionalidades` | publico | Catálogo para la ficha. |
| POST | `/registrar` | **agente** (nivel ≤3) | Alta por mostrador. NO lo usa la PWA. |
| POST | `/completar-ficha` | publico | Compat (el alta nuevo es en un paso, ver §38). |

## 2. Alta pública (autoregistro) — `/api/v1/publico/alta`

Todas validan el slug `?m=<codigo_corto>` contra el único municipio del deploy.

| Verbo | Ruta | Auth | Para qué |
|---|---|---|---|
| GET | `/identidad` | — | Nombre/logo/colores del municipio. |
| GET | `/actividades` · `/nacionalidades` | — | Catálogos para el form. |
| GET | `/geo/buscar?m=&q=` | — | Geocoding OSM sesgado a la zona del municipio. |
| POST | `/cuenta` | — | Alta en UN PASO con ficha completa (CUIL real, domicilio, etc.). |
| POST | `/activar-existente` | — | Vecino ya en la BUC pide cuenta. Anti-enumeración: 200. |
| POST | `/empresa` | publico | El vecino logueado da de alta su empresa. |
| GET | `/verificar?token=&m=` | — | Link del mail; devuelve página HTML. |

## 3. Identidad del municipio — `/api/v1/publico/identidad-municipio`

| Verbo | Ruta | Auth | Para qué |
|---|---|---|---|
| GET | `` | — | Nombre/logo/descripción/colores. Lo lee la PWA antes de tener token. |

## 4. Reclamos del vecino — `/api/v1/publico/reclamos`

| Verbo | Ruta | Auth | Para qué |
|---|---|---|---|
| GET | `/catalogo/tipos` | publico | Tipos de reclamo activos. |
| GET | `/geo/buscar` | publico | Geocoding para el vecino logueado. |
| GET | `/geo/reverse?lat=&lon=` | publico | **Nuevo 2026-08-30.** Geocoding INVERSO (GPS → dirección) para autocompletar el domicilio de los tickets rápidos de emergencia y del form de reclamos. Reemplaza la llamada directa a Nominatim desde el cliente. Siempre 200: `{encontrado, direccion, display_name, calle, altura, localidad, provincia, lat, lon, address}` — con `encontrado=false` (mar / sin datos) la PWA cae a las coordenadas crudas. Rate-limit 20/min/IP. |
| GET | `` | publico | Lista SOLO los reclamos del vecino. |
| GET | `/{id_reclamo}` | publico | Detalle. **404 si no es suyo** (no filtra terceros). |
| POST | `` | publico | Crea reclamo a nombre propio. Exige `id_tipo_reclamo` + `direccion` + `descripcion≥5`. |

### Adjuntos — `/api/v1/publico/reclamos/{id_reclamo}/adjuntos`

| Verbo | Ruta | Auth | Para qué |
|---|---|---|---|
| POST | `/upload-url` | publico | URL firmada para subir foto directo a Storage. |
| POST | `/{id_adjunto}/confirm` | publico | Confirma la subida. |
| GET | `` | publico | Lista adjuntos con URLs firmadas (TTL 1h). |

## 5. Portal (home) — `/api/v1/publico/portal`

| Verbo | Ruta | Auth | Para qué |
|---|---|---|---|
| GET | `/mi-resumen` | publico | Conteos `{vigentes,total}` de reclamos/turnos/entradas en 1 request. **Desde 2026-08-30** suma `avisos: {no_leidos}` (badge de la campana, ver §11). |

## 6. Turnos del vecino — `/api/v1/publico/turnos`

| Verbo | Ruta | Auth | Para qué |
|---|---|---|---|
| GET | `` | publico | Mis turnos. |
| POST | `/reservar` | publico | Reserva un slot. Valida disponibilidad + sin solape + no pasado (hora local AR). |
| PATCH | `/{id_turno}/cancelar` | publico | Cancela un turno propio. |

## 7. Entradas del vecino — `/api/v1/publico/entradas`

| Verbo | Ruta | Auth | Para qué |
|---|---|---|---|
| GET | `` | publico | Mis reservas. |
| GET | `/eventos` | publico | Cartelera con cupo disponible. |
| POST | `/eventos/{id_evento}/reservar` | publico | Reserva entrada → genera QR. |
| PATCH | `/{id_evento_reserva}/cancelar` | publico | Cancela una reserva. |

## 8. Emergencias del vecino — `/api/v1/publico/emergencias`

| Verbo | Ruta | Auth | Para qué |
|---|---|---|---|
| GET | `/tipos` | publico | Tipos de emergencia (sin datos de triage). |
| GET | `/tipos/{id_tipo}/subtipos` | publico | Subtipos. |
| GET | `/eventos` | publico | Mis reportes. |
| POST | `/eventos` | publico | Reporta emergencia. Canal `APP_VECINO` forzado server-side. Rate-limit 5/min/IP. |

> **Alerta de pánico (botón «Seguridad» de la PWA — mig 97).** El body de `POST /eventos` **no tiene** campo `es_panico`: el backend lo deriva **únicamente** del prefijo de `descripcion`. Si `descripcion` empieza con **`ALERTA DE PANICO`** (se compara con `strip` + mayúsculas + sin tildes, así que `"Alerta de pánico: …"` también cuenta), el evento se guarda con `es_panico=true`, se notifica in-app + mail a los operadores COM de la subárea del tipo (fallback: admins) y el tablero de Emergencias lo muestra primero, con card destacada, banner rojo y sonido. **Ese prefijo es el mecanismo formal** — cualquier otro texto crea un evento común. `GET /eventos` no expone `es_panico` (el vecino ve su reporte como uno más). Fuente: `publico_emergencias.py` (`_PREFIJO_PANICO`, `_es_alerta_panico`).

## 9. Web Push — `/api/v1/publico/push`

| Verbo | Ruta | Auth | Para qué |
|---|---|---|---|
| GET | `/public-key` | publico | Clave VAPID pública para suscribir. |
| POST | `/subscribe` | publico | Registra la suscripción (UPSERT, activa `canal_push`). |
| POST | `/unsubscribe` | publico | Da de baja la suscripción. |

## 10. Perfil del vecino — `/api/v1/publico/perfil` (nuevo 2026-08-30)

| Verbo | Ruta | Auth | Para qué |
|---|---|---|---|
| GET | `` | publico | Ficha completa de la BUC del vecino logueado: `id_ciudadano, dni, doc_tipo, cuil, cuil_es_placeholder, nombre, apellido, sexo, fecha_nac (YYYY-MM-DD), id_nacionalidad, nacionalidad, calle, altura, localidad, provincia, latitud, longitud, telefono, email, email_verificado, estado_validacion, ficha_completa, canal_email, canal_push, fecha_alta, fecha_modificacion`. |
| PUT | `` | publico | Update **parcial** (solo los campos presentes en el body). Editables: `telefono` (10 dígitos sin el 0 de área; se guarda digit-only), `calle`, `altura`, `localidad`, `provincia`, `latitud`, `longitud` (mandar `null` explícito limpia lat/lon). Devuelve el perfil completo. Body vacío o inválido → 422. Rate-limit 10/min/IP. |
| POST | `/foto` | publico | **Nuevo 2026-08-30 (mig 102).** Sube/reemplaza la foto de perfil: multipart, campo `archivo`, **solo JPEG**, 1 KB a 512 KB, mínimo 100×100 px (la PWA ya reduce a 256 px). Path fijo por vecino con upsert (1 foto, sin huérfanos). Devuelve el perfil con `foto_url` (URL firmada, **TTL 1 h** — no cachearla más que eso) y `foto_actualizada_en`. 422 si no cumple; rate-limit 5/min/IP. |
| DELETE | `/foto` | publico | Quita la foto (bucket + columnas). Idempotente. Devuelve el perfil con `foto_url: null`. |

> `GET /perfil` también trae `foto_url` (firmada, TTL 1 h) y `foto_actualizada_en`, o `null` sin foto. La foto deja de vivir en `localStorage` del dispositivo: sigue al vecino entre dispositivos.

> **CUIL placeholder:** el alta por agente inventa `20 + DNI + 9` porque la columna es NOT NULL. En ese caso `cuil` viene `null` y `cuil_es_placeholder=true` — no mostrar el dato inventado.
>
> **NO editables desde la app** (se ignoran si vienen en el body): DNI, CUIL, nombre, apellido, sexo, fecha_nac, nacionalidad (datos de identidad → mostrador) y **email** (es la credencial de recovery; cambiarlo exige re-verificación, flujo aparte pendiente de definir).

## 11. Avisos del vecino (bandeja "Alertas") — `/api/v1/publico/avisos` (nuevo 2026-08-30, mig 99)

Los avisos los escribe el **backend** en los mismos hooks post-commit que disparan el push (cambio de estado de un reclamo — todas las vías, incluidas las OT — y de un reporte de emergencia). Quedan persistidos haya o no suscripción push, así la bandeja nunca depende del dispositivo. La PWA solo lee y marca leído.

| Verbo | Ruta | Auth | Para qué |
|---|---|---|---|
| GET | `?solo_no_leidos=&limit=&offset=` | publico | `{avisos: [...], no_leidos, total}`, del más nuevo al más viejo. Cada aviso: `{id_aviso, tipo ('reclamo_estado' \| 'emergencia_estado' \| 'tramite_estado' \| 'tramite_pendiente' \| 'municipio'), titulo, mensaje, url (ruta RELATIVA en la PWA, misma que el push: "/reclamos/123", "/emergencias"; los de trámites traen "/alertas"), recurso_tipo ('reclamo' \| 'emergencia' \| 'tramite'), recurso_id, leido, leido_en, fecha}`. **Trámites (desde 2026-08-30):** `tramite_estado` = "tu trámite terminó: APROBADO/RECHAZADO" (o desistido); `tramite_pendiente` = avisos escalonados cuando el expediente espera documentación del vecino (30/60 días y 72 h antes de darlo por desistido). La PWA solo los muestra; no hay endpoint público de trámites. |
| PATCH | `/{id_aviso}/leer` | publico | Marca UN aviso leído. Idempotente. **404 si no existe o no es del vecino** (mismo cuerpo). Devuelve `{ok, id_aviso, leido, leido_en, no_leidos}`. |
| POST | `/leer-todos` | publico | Marca todos los pendientes. `{ok, marcados, no_leidos: 0}`. |

---

## Autoservicios ANÓNIMOS por token UUID (no requieren login)

Para compartir por link sin que el ciudadano tenga cuenta.

### Turnos — `/api/v1/turnos/publico`
- GET `/prestaciones` · GET `/slots?id_tipo_prestacion=&fecha_desde=&dias=`
- POST `/reservar` (busca/crea ciudadano por DNI) → `token_turno`
- GET `/turno/{token_turno}` · DELETE `/turno/{token_turno}`

### Eventos/Entradas — `/api/v1/agenda/publico`
- GET `/evento/{token_publico}` · POST `/evento/{token_publico}/reservar`
- GET `/reserva/{token_reserva}` · DELETE `/reserva/{token_reserva}`

### Encuestas CSAT — `/api/v1/publico/encuesta` (rate-limited 5/min/IP)
- GET `/{token}` · POST `/{token}/responder`
- Token inválido → 404; completada/expirada → 410.

---

## Reglas que la PWA debe respetar

- **El `id_ciudadano` nunca viaja en el body ni en la URL** en endpoints scope
  publico — sale del token. La PWA no puede operar sobre terceros.
- **CORS:** los orígenes de la PWA (`vecinos.zaris.com.ar`,
  `zaris-vecinos.vercel.app`, `localhost:5174`) deben estar en `allow_origins`
  de `backend/app/main.py`. Origen nuevo → agregarlo ahí (CORS de FastAPI no
  acepta wildcards).
- **Sesión propia de la PWA:** `localStorage` key `zaris_vecino_session` (NO
  `zaris_session` del backoffice — son apps distintas).
- Anti-enumeración: los endpoints de reenvío/recovery siempre devuelven 200, no
  reveles al usuario si el DNI existe.
