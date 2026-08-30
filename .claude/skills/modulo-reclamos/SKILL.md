---
name: modulo-reclamos
description: "Usar al trabajar en el módulo Reclamos de ZARIS (archivos: backend/app/api/routes/reclamos.py, geo.py, app/core/storage.py, web-app/src/modules/reclamos/; tablas: reclamos, reclamo_historial, reclamo_adjuntos, tipo_reclamo, estado_reclamo, provincias/partidos/localidades, tipos_activo/activos). Cubre tablas y triggers, CHECK constraints (prioridad/estado), FSM de estados con cierre directo y guard de subárea, endpoints, geolocalización/Nominatim, activos georreferenciados, subreclamos, adjuntos en Supabase Storage (§18+§22+§26 unificadas). Invocar ANTES de tocar cualquier endpoint, tabla, estado, geocoding o adjunto de Reclamos."
---

# Módulo Reclamos — §18 + §22 + §26

> Esta skill unifica las tres secciones del módulo Reclamos: §18 (tablas/estados/endpoints), §22 (geolocalización/activos/adjuntos) y §26 (adjuntos en Supabase Storage). Las tres anclas se conservan en CLAUDE.md.

---

## §18. Módulo Reclamos

### Tablas

| Tabla | Rol |
|---|---|
| `reclamos` | Transaccional principal — un registro por reclamo |
| `reclamo_historial` | Timeline de cambios de estado (INSERT solo, nunca UPDATE) |
| `reclamo_adjuntos` | Adjuntos del reclamo (§22) — binarios en Supabase Storage, metadatos acá |
| `tipo_reclamo` | Maestro con `id_area`, `id_subarea`, `sla_dias`, `audit` (FK → `area`, `subarea`) |
| `estado_reclamo` | Maestro de estados válidos — PK **`id_estado_reclamo`** (no `id_estado`) |
| `ordenes_trabajo` | OT operativa o de auditoría asociada a un reclamo |
| `estado_ot` | Estados de OT: `En gestión`, `En espera`, `Pendiente`, `Terminada`, `Cancelada` |
| `equipo_agentes` | Relación equipo ↔ agente (reemplaza `equipo_usuarios` en lógica de OTs) |
| `configuracion_general` | Key/value de parámetros del sistema |
| `provincias` / `partidos` / `localidades` | Árbol geo AR (§22) — `reclamos.id_localidad` apunta al nivel más fino |
| `tipos_activo` / `activos` | Catálogo de activos físicos georreferenciados (§22) |

`nro_reclamo` se genera automáticamente vía trigger `trg_nro_reclamo` → `REC-YYYY-XXXXXX`.
`nro_ot` se genera automáticamente vía trigger `trg_nro_ot` → `OT-YYYY-XXXXXX`. **Ojo (cazado 2026-05-25):** este trigger NO existía en prod pese a estar documentado acá — las OT salían con `nro_ot` NULL. Lo creó **mig 59** (`fn_generar_nro_ot` + trigger BEFORE INSERT, espejo de `fn_generar_nro_reclamo`) + backfill. Si tocás numeración de OT, verificá el trigger con `pg_trigger` (ver [[feedback_verificar_trigger_existe_no_confiar_doc]]).

### CHECK constraints en `reclamos` (verificado prod 2026-05-12)

| Campo | CHECK | Valores aceptados |
|---|---|---|
| `prioridad` | `reclamos_prioridad_check` | **`Alta`, `Media`, `Baja`** — NO acepta `Crítica`, `Urgente`, etc. Agregar valor nuevo requiere migración del CHECK ANTES de exponerlo en UI. |
| `estado` | `ck_reclamo_estado` | `Sin asignar`, `En gestión`, `En espera`, `En auditoría`, `Resuelto`, `Cancelado` (con tildes). |

Antes de modificar selects de UI o tipos TypeScript que mapean estos campos, correr:
```sql
SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
WHERE conrelid = 'reclamos'::regclass AND contype = 'c';
```
Caso real sesión 2026-05-12: introducir `'Crítica'` en `type Prioridad` costó un commit de fix (`4efcacb`) cuando el smoke API explotó con IntegrityError. La doc puede estar atrás; el CHECK es el contrato real.

### Estados de reclamo (v1.2)

`Sin asignar` → `En gestión` → `En espera` → `En auditoría` → `Resuelto` / `Cancelado`

- **Sin asignar:** reclamo ingresado, sin OT asignada.
- **En gestión:** OT generada y en ejecución.
- **En espera:** bloqueado por subreclamo activo.
- **En auditoría:** OT operativa cerrada, pendiente de auditoría.
- **Resuelto / Cancelado:** estados finales.

### Endpoints reclamos

```
GET  /api/v1/reclamos                      → lista con filtros (estado, id_area, prioridad, texto, limit, offset)
GET  /api/v1/reclamos/stats                → conteos por estado
GET  /api/v1/reclamos/catalogo/areas       → áreas activas
GET  /api/v1/reclamos/catalogo/tipos       → tipos de reclamo activos
GET  /api/v1/reclamos/{id}                 → detalle con historial, OTs y subreclamos
POST /api/v1/reclamos                      → crear reclamo (requiere id_ciudadano BUC)
PUT  /api/v1/reclamos/{id}                 → editar reclamo (alcance variable según estado)
PUT  /api/v1/reclamos/{id}/estado          → cambiar estado + insertar entrada en historial
PUT  /api/v1/reclamos/{id}/cancelar        → cancelar reclamo + cascade a OTs activas (requiere motivo)
POST /api/v1/reclamos/{id}/subreclamo      → crear subreclamo (max 1 nivel; padre pasa a En espera)
```

### Edición de reclamos — alcance por estado

`PUT /reclamos/{id}` aplica una allowlist de campos según el estado actual del reclamo (helper `_require_gestion` exige `nivel_acceso ∈ {1,2,3}`):

| Estado | Campos editables |
|---|---|
| `Sin asignar` | tipo, prioridad, canal, dirección, lat/lon, localidad, activo, empresa, fuente_geo, ciudadano, descripción, **observaciones** |
| `En gestión` / `En espera` / `En auditoría` | **observaciones** (único). Body opcional: `nota_historial` para custom-text en `reclamo_historial.nota` (default: lista de campos modificados). |
| `Resuelto` / `Cancelado` | ninguno → 422 |

Toda edición inserta entrada `Reclamo editado` en `reclamo_historial` preservando estado anterior/nuevo (= estado actual). Si el body trae un campo prohibido para el estado actual: 422 con detalle de campos rechazados vs permitidos. Cambio de tipo re-deriva `id_area` desde `subarea.id_area` (fuente única desde mig 27). Cambio de empresa valida vínculo activo en `ciudadano_empresa`.

Mismo guard `_require_gestion` aplica también a `PUT /{id}/cancelar`.

### Endpoints adjuntos (§26)

```
POST   /api/v1/reclamos/{id}/adjuntos/upload-url        → backend valida + crea fila pre-upload + URL firmada PUT (TTL 5min)
POST   /api/v1/reclamos/{id}/adjuntos/{id_adj}/confirm  → marca activo=TRUE tras subida exitosa
GET    /api/v1/reclamos/{id}/adjuntos                   → lista activos con URLs firmadas GET (TTL 1h)
DELETE /api/v1/reclamos/{id}/adjuntos/{id_adj}          → soft-delete + remove del bucket
```

### Endpoints ordenes_trabajo

```
GET  /api/v1/ot/catalogo/estados           → estados de OT activos
GET  /api/v1/ot/mesa/supervisor            → reclamos activos para asignación
GET  /api/v1/ot/mesa/agente                → OTs del agente autenticado
GET  /api/v1/ot/mesa/auditoria             → OTs en auditoría (respeta config auditor_misma_subarea)
GET  /api/v1/ot                            → lista OTs con filtros
GET  /api/v1/ot/{id_ot}                    → detalle OT
POST /api/v1/ot                            → crear OT (supervisor asigna a agente/equipo)
PUT  /api/v1/ot/{id_ot}/tomar              → agente toma OT sin asignar
PUT  /api/v1/ot/{id_ot}/estado             → cambiar estado OT
PUT  /api/v1/ot/{id_ot}/aprobar            → auditor aprueba OT → reclamo Resuelto
PUT  /api/v1/ot/{id_ot}/rechazar           → auditor rechaza OT → nueva OT Pendiente con id_ot_origen
```

### Validación de estados

`PUT /{id}/estado` consulta `estado_reclamo WHERE activo=TRUE`. Fallback hardcoded a `{"Sin asignar", "En gestión", "En espera", "En auditoría", "Resuelto", "Cancelado"}` si la tabla está vacía.

**FSM de transiciones (desde 2026-05-20, hallazgo QA #3).** `PUT /{id}/estado` valida el grafo `TRANSICIONES_PERMITIDAS` en `reclamos.py` además de exigir `_require_gestion` (nivel ≤ 3). No se permiten saltos arbitrarios (antes el endpoint aceptaba cualquier estado→cualquier estado). Grafo:

| Desde | Puede ir a |
|---|---|
| `Sin asignar` | `En gestión`, `Cancelado` |
| `En gestión` | `En espera`, `En auditoría`, `Resuelto`, `Cancelado` |
| `En espera` | `En gestión`, `En auditoría`, `Cancelado` |
| `En auditoría` | `En gestión`, `Resuelto`, `Cancelado` |
| `Resuelto` / `Cancelado` | (final — ninguno) |

- Transición fuera del grafo → 422 listando los alcanzables.
- Mismo estado (no-op) se acepta sin chequear el grafo.
- El frontend espeja el grafo en `web-app/src/modules/reclamos/components/CambiarEstadoModal.tsx` (sin `Cancelado`, que va por el endpoint dedicado `/cancelar`): el dropdown solo muestra estados alcanzables; reclamo en estado final muestra mensaje "no admite cambios". **Si modificás el grafo, tocá los DOS lugares** (backend `reclamos.py` + modal frontend) o se desincronizan.

**Integridad padre/hijo (hallazgo QA #1).** `PUT /{id}/estado` a `Resuelto` o `En auditoría` se bloquea con 422 si el reclamo (que no es subreclamo) tiene subreclamos activos con estado distinto a `Resuelto`/`Cancelado`. El mensaje enumera los pendientes. Antes se podía cerrar el padre dejando hijos huérfanos activos.

**Cierre directo sin OT (desde 2026-05-22).** Excepción al grafo FSM: `Sin asignar → Resuelto` (que el grafo normal NO permite) se habilita SOLO cuando se cumplen las 3 condiciones (helper `_validar_cierre_directo_sin_ot` en `reclamos.py`):
1. el usuario es **supervisor o admin** (`nivel_acceso ≤ 2`);
2. el reclamo **no tiene OT activa** (`ordenes_trabajo WHERE id_reclamo=:id AND activo` vacío → sino 422);
3. la **subárea del usuario** (`usuarios.id_subarea`, mig 55 §21) **== subárea del tipo de reclamo** (`tipo_reclamo.id_subarea`, derivada vía `reclamos.id_tipo_reclamo`; NO usar `reclamos.id_subarea` que puede ser NULL). Si no coincide → 403.
Caso de uso: reclamo que se resuelve sin generar OT (consulta, duplicado, sin info). El frontend (`CambiarEstadoModal.tsx`) ofrece "Resuelto" desde "Sin asignar" solo a `hasPermission(2)` y muestra un pop-up de confirmación; **el backend es la fuente de verdad de la subárea** (el modal no la conoce, así que un supervisor de otra subárea ve la opción pero recibe 403 con mensaje claro al confirmar). Es una **3ª rama** del handler `cambiar_estado`, exenta del chequeo del grafo (`es_cierre_directo` se valida antes del `elif` del grafo).

**Bloqueo cierre cross-subárea por la vía normal (desde 2026-05-25).** El chequeo de subárea de arriba SOLO cubría el atajo `Sin asignar → Resuelto`. Pero un reclamo ya en `En gestión` podía pasar a `Resuelto`/`En auditoría` por la vía normal del FSM sin chequear subárea — un supervisor de otra subárea cerraba reclamos ajenos. Fix: helper `_require_misma_subarea` aplicado también al pase manual a `Resuelto`/`En auditoría` (admin nivel 1 exento). **El cierre vía OT (`ordenes_trabajo.py` actualiza `reclamos.estado` directo, NO pasa por `cambiar_estado`) no se afecta** — el agente que cierra pertenece a la subárea por construcción. Si agregás otra ruta que lleve un reclamo a estado final, recordá el guard (ver [[feedback_guard_subarea_cubre_todas_las_vias]]).

### Configuración general

| Clave | Tipo | Descripción |
|---|---|---|
| `auditor_misma_subarea_permitido` | boolean | Si `false`, auditor no puede pertenecer a la subárea del reclamo |
| `ot_pendiente_dias_vencimiento` | integer | Días máximos que una OT Pendiente puede estar sin reasignarse |
| `municipio_nombre` | string | Nombre del municipio que se muestra en el topbar (ej. "MUNICIPALIDAD DE SAN ANDRÉS"). Editable desde Config → Identidad. |
| `municipio_logo_url` | string | URL pública del logo del municipio (servida desde bucket `config-assets` de Supabase Storage). Vacía = sin logo. Editable desde Config → Identidad. |
| `geo_bbox_centro_lat` / `geo_bbox_centro_lon` / `geo_bbox_delta_grados` | string (decimales) | Zona del municipio para el buscador de direcciones (mig 87, §23). Editables en Config → Sistema; `geo.py` las lee con cache TTL 5 min y fallback a constantes (VL demo). |

> La clave `app_nombre` **no existe** (se intentó en 2026-05-13 y se borró). "GESTION ESTADO" es interno del producto, hardcoded en el HTML del shell. Ver §14 (topbar layout).

### Ciudadano en reclamos

Todo reclamo requiere `id_ciudadano` válido de la BUC. El frontend busca ciudadanos vía `GET /api/v1/buc/ciudadanos/buscar?q=<texto>` con debounce de 300ms antes de permitir el submit.

### Patrón XSS — resultados de búsqueda BUC en vanilla JS

Cuando se renderizan resultados donde el usuario puede hacer clic para seleccionar, **nunca** interpolar datos del servidor en handlers `onclick`. Usar `data-attrs` + event delegation:

```js
// Guardar datos en un objeto auxiliar
let _bucResultados = {};
data.forEach(c => { _bucResultados[c.id_ciudadano] = c; });

// Renderizar con data-id, escapar HTML en texto visible
res.innerHTML = data.map(c => {
    const nombre = (c.nombre || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return `<div class="buc-item" data-id="${c.id_ciudadano}">${nombre}</div>`;
}).join('');

// Attach listeners después del render
res.querySelectorAll('.buc-item[data-id]').forEach(el => {
    el.addEventListener('click', () => {
        const c = _bucResultados[parseInt(el.dataset.id)];
        if (c) seleccionarCiudadano(c.id_ciudadano, c.apellido, c.nombre, c.cuil);
    });
});
```

**Implementado en:** módulos vanilla legacy. Patrón vigente para cualquier nuevo módulo vanilla que rendere resultados clickeables desde la BUC. Los módulos Reclamos / Ciudadanos / Empresas ya migrados a React resuelven el mismo issue via JSX (sin interpolar HTML), por lo que no aplica ahí.

---

## §22. Geolocalización, Activos y Adjuntos (Reclamos)

### Árbol geográfico (provincia → partido → localidad)

- `provincias`: 24 entidades (23 provincias AR + CABA).
- `partidos`: 135 partidos PBA + 15 comunas CABA + capitales del resto. Único `(id_provincia, nombre)`.
- `localidades`: nivel más fino. Único `(id_partido, nombre)`.
- `reclamos.id_localidad` y `activos.id_localidad` apuntan al nivel más fino. Para agregar por partido o provincia, hacer JOIN.
- Seed: `backend/seed_geo_argentina.py` (idempotente vía UPSERT). Comando local: `$env:DATABASE_URL="postgresql+asyncpg://postgres:145236@127.0.0.1:5432/zaris_dev"; python backend/seed_geo_argentina.py`.

### Activos (físicos del municipio)

- `tipos_activo`: catálogo (luminaria, semáforo, contenedor, etc.). Campo `requiere_ciudadano` (boolean) marca si el activo necesita asociar a un ciudadano.
- `activos`: cada ítem físico con `codigo_unico`, `id_tipo_activo`, `direccion`, `id_localidad`, `latitud`, `longitud`.
- `reclamos.id_activo` permite vincular un reclamo a un activo específico (ej. luminaria `cod_00007`). Cuando se setea, se sugiere también poblar `lat/lon` del activo en el reclamo y marcar `fuente_geolocalizacion = 'activo_referenciado'`.
- Sample anonimizado en `Tablas Iniciales/Activos.csv` (49.360 activos con lat/lon dentro del bbox de Vicente López).

### Geolocalización en `reclamos`

| Campo | Tipo | Notas |
|---|---|---|
| `latitud` / `longitud` | NUMERIC(10,7) | WGS84. Index compuesto `idx_reclamos_lat_lon`. |
| `id_localidad` | FK | nivel más fino. |
| `direccion` | VARCHAR(300) | Texto normalizado (resultado de OSM o input manual). Reemplaza al deprecado `domicilio_reclamo`. |
| `fuente_geolocalizacion` | VARCHAR(20) | `pin_manual` / `geocoding_osm` / `gps_dispositivo` / `activo_referenciado`. |

**OT vs reclamo:** la OT usa la misma lat/lon del reclamo (no tiene columnas geo propias). Para queries con lat/lon de OTs, hacer JOIN con `reclamos`.

### Servicio externo: OpenStreetMap / Nominatim

- **Geocoding directo:** `GET https://nominatim.openstreetmap.org/search?q=<calle+altura+localidad>&format=json&limit=5&countrycodes=ar` + **`viewbox` y `bounded=1`** (zona del municipio, ver regla §23 — sin esto trae homónimos de otras provincias)
- **Geocoding inverso:** `GET https://nominatim.openstreetmap.org/reverse?lat=<>&lon=<>&format=json`
- **Política de uso:** máx 1 req/seg, enviar `User-Agent: ZARIS-API/1.0 (cesar@zaris.dev)`. Para producción real, considerar Photon o Nominatim self-hosted.
- **Mapas en frontend:** Leaflet + tiles de OSM (gratis, sin API key).
- En el formulario de alta de reclamo, al pickear desde mapa setear `fuente_geolocalizacion = 'pin_manual'`; al elegir sugerencia de Nominatim, `geocoding_osm`.

#### Endpoint `GET /api/v1/geo/buscar` — proxy a Nominatim

| Param | Default | Notas |
|---|---|---|
| `q` | requerido (≥3 chars) | Texto libre a geocodificar. |
| `limit` | 5 (1-10) | Cantidad de resultados a devolver. |
| `solo_direcciones` | `false` | Si `true`, filtra POIs (comercios, hoteles, restaurantes, oficinas, escuelas, hospitales, etc.) y devuelve solo calles/edificios residenciales. Usado por el buscador OSM de Ciudadanos y Empresas. Reclamos lo deja en `false` porque ahí sí tiene sentido pickear un POI ("hay un bache frente al McDonalds"). |

**Lógica de `solo_direcciones=true`** (implementada 2026-05-15 en `backend/app/api/routes/geo.py::buscar_direccion`):

1. Pide `limit=40` upstream a Nominatim (no `limit*3`). Algunas queries genéricas tienen 15+ POIs antes del primer resultado válido — con limit bajo se devuelven 0 falsos negativos.
2. NO usar `layer=address` de Nominatim — es demasiado restrictivo, excluye `highway/secondary` (calle sin número exacto) que sí son direcciones válidas.
3. Blacklist por `class` POI puro: `amenity`, `shop`, `office`, `tourism`, `leisure`, `craft`, `healthcare`, `club`, `emergency`, `man_made` → descartar siempre.
4. Cuando `class=building` con `type` no residencial (`commercial`, `retail`, `industrial`, `office`, `hotel`, `restaurant`, `school`, `hospital`, etc.) **pero** tiene `address.road` válido → **mantener** y **reescribir `display_name` desde `address`**. Caso real: Nominatim devuelve "Warner Chappell Music, 1351, Avenida Córdoba, Retiro, CABA" → mostrar "1351 Avenida Córdoba, Retiro, Comuna 1, CABA". El edificio aloja un comercio, pero la calle+altura es la dirección postal real.
5. Cortar la iteración al alcanzar `limit` aceptados.

Response: agrega `class` al output anterior. Compat retro con `solo_direcciones=false` (default).

Detalles del aprendizaje (incluyendo trampas que NO funcionaron) en memoria [[feedback_nominatim_filtrar_pois]].

### Sub-reclamos

- Sigue como auto-referencia en `reclamos` (campo `id_reclamo_padre`).
- **Profundidad máxima: 1 nivel.** Validado en `POST /api/v1/reclamos/{id}/subreclamo`: si el padre ya tiene `id_reclamo_padre`, rechaza.
- No hay límite de cantidad de sub-reclamos por reclamo.

### Adjuntos (Supabase Storage)

- Tabla `reclamo_adjuntos`: solo metadatos (`storage_path`, `mime_type`, `tamano_bytes`).
- Bucket: `reclamos-adjuntos` con políticas RLS que requieren JWT válido.
- Path convention: `reclamos/{id_reclamo}/{uuid}.{ext}`.
- **Flujo de upload (a implementar):** frontend pide URL firmada al backend → sube directo a Storage → backend inserta fila en `reclamo_adjuntos`. La URL firmada tiene TTL corto.
- Solo imágenes en V1. Adjuntos desde web app o app móvil futura.

### Campos extras en reclamos (CRM)

| Campo | Tipo | Notas |
|---|---|---|
| `canal_origen` | VARCHAR(20) | `web` / `whatsapp` / `telefono` / `presencial` / `oficio` / `app_movil` / `otro`. |
| `fecha_primer_asignacion` | TIMESTAMPTZ | Set al pasar a `En gestión` (medición de SLA real). **Hasta 2026-05-25 NO se seteaba** (bug); ahora se hace vía `COALESCE(fecha_primer_asignacion, NOW())` en `cambiar_estado` (reclamos.py) y en `crear_ot`/`crear_ot_con_agenda` (ordenes_trabajo.py). El COALESCE evita pisarla al volver a En gestión. |
| `fecha_cierre` | TIMESTAMPTZ | Set al pasar a estado final (`Resuelto` o `Cancelado`). Lo setean **las 3 vías** que llevan a estado final: `cambiar_estado` (pase manual), `_resolver_reclamo`/cierre vía OT, y `PUT /{id}/cancelar` (este último se quedó afuera del fix de mayo y se corrigió el 2026-06-01 con `fecha_cierre=COALESCE(fecha_cierre, NOW())`, commit `00f06a7`). Si agregás otra ruta a estado final, setearla ahí también — un fix que cubre una vía no cubre las otras (ver memoria `feedback_guard_subarea_cubre_todas_las_vias`). |
| `sla_vencimiento` | TIMESTAMPTZ | Calculado por trigger `trg_sla_reclamo` = `fecha_alta + tipo_reclamo.sla_dias`. |

### Estado (FK vs VARCHAR — transición)

- **Migración 22 introduce `id_estado_fk`** como FK a `estado_reclamo(id_estado_reclamo)`.
- La columna `estado` (VARCHAR con CHECK) se mantiene poblada en paralelo durante el período de transición. Endpoints existentes que leen/escriben `estado` siguen funcionando.
- Nuevos consumidores deben usar `id_estado_fk`. Cuando frontend y endpoints migren 100%, se removerá el VARCHAR en una migración futura.

---

## §26. Adjuntos de Reclamos (Supabase Storage)

**Implementado al 2026-05-10.** El frontend nunca habla con Storage con auth de usuario — el backend firma URLs con la `service_role` key.

### Configuración
- Buckets:
  - `reclamos-adjuntos` (**privado**, 10 MB, image/jpeg|png|webp|gif|heic|heif) — fotos de reclamos.
  - `config-assets` (**público**, 2 MB, image/png|jpeg|webp|svg+xml) — logo del municipio. Endpoint `/api/v1/config/identidad/logo-upload-url` (ver §14).
- Tabla `reclamo_adjuntos` (existía desde migración 22): metadatos + `storage_bucket` + `storage_path`. Audit completa.
- Vars de entorno backend (`backend/.env.local` y **Railway**):
  - `SUPABASE_URL` — URL del proyecto Supabase (`https://<id>.supabase.co`)
  - `SUPABASE_SERVICE_KEY` — `service_role` (legacy `eyJ...`) o `sb_secret_...` (nueva). Ambas funcionan; **nunca** la `anon`/`publishable`.
  - `SUPABASE_ADJUNTOS_BUCKET` — default `reclamos-adjuntos`. El bucket `config-assets` está hardcoded en `config_identidad.py` (no usa esta var).

> **Quirk operativo cazado 2026-05-13:** las 3 env vars Supabase tienen que estar **explícitamente seteadas en Railway**. La sub-fase B5 de Reclamos pasó el smoke local (con `.env.local` válido) y se pusheó como cerrada, pero los adjuntos en prod estaban devolviendo 503 desde el deploy hasta la sesión del 13/5 porque Railway nunca tuvo esas vars. Si pusheás una feature nueva que usa Storage (o vas a modificar `storage.py`), después del deploy testeá un POST `/upload-url` contra prod, no solo contra local.

### Flujo de upload (modal nuevo reclamo)
1. Usuario elige imágenes (drag&drop o file picker) — se acumulan en memoria con preview base64.
2. Al guardar el reclamo: primero `POST /reclamos`, después por cada archivo:
   - `POST /reclamos/{id}/adjuntos/upload-url` con `{nombre_archivo, mime_type, tamano_bytes}` → backend valida, inserta fila con `activo=FALSE`, devuelve `{id_adjunto, upload_url, storage_path, bucket}`.
   - `PUT` directo a `upload_url` con header `Content-Type: <mime>` y `x-upsert: true`, body = binario.
   - `POST /reclamos/{id}/adjuntos/{id_adj}/confirm` → marca `activo=TRUE`.
3. Si algún upload falla, el reclamo queda creado y el toast informa cuántos subieron.

### Flujo de visualización (drawer detalle)
- `cargarAdjuntosDrawer(idReclamo)` se invoca desde `abrirDetalle()` después del render.
- `GET /reclamos/{id}/adjuntos` devuelve `[{id_adjunto, storage_path, nombre_archivo, mime_type, tamano_bytes, fecha_alta, url}]` — `url` es firmada con TTL 1h.
- Galería en grid; click abre lightbox (overlay full-screen con la imagen, ESC o click cierra).
- Hover muestra botón `×` para borrar (soft-delete + `DELETE` del binario en bucket).

### Diseño
- **Bucket privado** + URL firmada al servir. Los paths siguen `reclamos/{id_reclamo}/{uuid}.{ext}`.
- **No hay policies RLS sobre `storage.objects`**: el backend usa `service_role` que las bypassa. Toda autorización vive en endpoints FastAPI (validación JWT + scope al reclamo).
- **Filas pre-upload con `activo=FALSE`**: si el cliente abandona entre `upload-url` y `confirm`, queda una fila huérfana sin binario, invisible para el GET. Limpieza opcional en sesión futura via cron o batch.
- **Best-effort delete del binario**: si Storage falla al borrar, la fila queda soft-deleted igual y se loggea — el usuario nunca ve el adjunto.

### Frontend en otros módulos
Para sumar adjuntos a otra entidad (ej: OTs), replicar el patrón: nueva tabla `<entidad>_adjuntos` con mismos campos, nuevo bucket si conviene aislar, y reutilizar `app/core/storage.py` (las funciones reciben `path` arbitrario y leen el bucket de settings — extraer a parámetro si se usan múltiples buckets). **Ya hecho para OT** (`ot_adjuntos`, mig 54, ver §34) — reusa el mismo bucket `reclamos-adjuntos` con paths bajo `ot/{id_ot}/`. Es la referencia canónica para clonar a futuras entidades.


## Localidad derivada de las coordenadas (2026-08-30, para el BI Ejecutivo)

- `reclamos.id_localidad` se **deriva automáticamente** cuando el alta trae lat/lon y no trae
  id_localidad: `geo.py::localidad_desde_coords(db, lat, lon)` = reverse Nominatim (helper §23)
  + match **por nombre** (sin tildes, lower) contra el catálogo `localidades`. Best-effort: si
  Nominatim falla o el punto cae fuera del catálogo queda NULL, jamás rompe el create. Inyectada
  en `crear_reclamo`, `crear_subreclamo` (reclamos.py) y `crear_mi_reclamo` (publico_reclamos.py).
  OJO: suma ~1 llamada Nominatim (rate-limit global 1/s) al create con geo.
- `GET /geo/reverse` (backoffice, JWT) devuelve además `id_localidad` + `localidad_catalogo`.
- **FormView**: campo "Localidad" readonly autocompletado vía `derivarLocalidad()` (se dispara
  en el pick del buscador y en el pin del mapa; guard de coords vigentes para no pisar con una
  respuesta vieja); "Quitar pin" también limpia la localidad. `id_localidad` viaja en create y
  update full. La hidratación usa `localidad_nombre` del GET detalle.
- Backfill histórico 2026-08-30 (39/45 prod, 5/6 local) + regla "match por nombre, nunca por id
  de partido/localidad entre entornos": detalle en la skill `modulo-bi` (dimensión LOCALIDAD).
