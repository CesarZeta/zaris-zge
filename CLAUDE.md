# Reglas Mandatorias de Desarrollo — ZARIS

## 1. Autenticación JWT (SSO)

- **Login:** `POST /api/v1/auth/login` — body `{ email, password }` → `{ access_token, token_type, user }`. Vigencia: 24 h.
- **Me:** `GET /api/v1/auth/me` — usuario autenticado actual.
- **Storage:** `localStorage` clave `zaris_session` (objeto `{ access_token, user }`). Todos los módulos leen de ahí.
- **Requests:** header `Authorization: Bearer <token>` en todo endpoint protegido. El helper `src/lib/api.ts` lo hace automáticamente.
- **Guard React:** `AppShell` redirige a `/login` sin sesión. No crear login por módulo.
- **Guard vanilla:** verificar `localStorage.getItem('zaris_session')` al inicio; si no existe, redirigir al login.
- **Hashing:** `bcrypt` 5.x directo — `bcrypt.hashpw(password.encode(), bcrypt.gensalt())`. No usar `passlib` (incompatible con bcrypt 4.x+ en Python 3.14+).
- **Seed local:** `cd backend && $env:ENV_FILE=".env.local"; python seed_auth.py`. Password dev: `123456`.
- **Prohibido:** endpoints de auth por módulo, passwords en texto plano.

## 2. Base Única de Ciudadanos (BUC)

Todo módulo con individuos (pacientes, clientes, solicitantes) **debe** referenciar `ciudadanos` via `id_ciudadano`.

- **Prohibido:** tablas propias para datos maestros de personas (DNI, nombre, teléfonos).
- **Obligatorio:** el individuo existe primero y únicamente en la BUC; datos específicos de negocio se referencian externamente.
- **Búsqueda:** `GET /api/v1/buc/ciudadanos/buscar?q=&limit=&offset=` acepta DNI, CUIL, teléfono (todos normalizados a digits-only — matchea "(11) 6429-5018" con "1164295018"), email o texto libre. En texto libre hace **AND multi-palabra**: cada token debe matchear en alguno de `apellido | nombre | email`. Devuelve header `X-Total-Count` para que el frontend pueda mostrar "y N más". El `Access-Control-Expose-Headers: X-Total-Count` está incluido — necesario para que el frontend pueda leer el header desde otro origen (GitHub Pages → Railway).

## 3. Roles y Permisos

`nivel_acceso` en `usuarios`: 1 = Administrador, 2 = Supervisor, 3 = Operador, 4 = Consultor.

Usar `get_current_user` de `app/core/auth.py` en todo endpoint que requiera identidad o permisos.

## 4. Stack Tecnológico

| Superficie | Stack | Directorio |
|---|---|---|
| Web app (shell React) | React 18 + TS + Vite + React Router v7 + Zustand | `web-app/` |
| Módulos legacy | HTML / JS / CSS | `frontend/` |

- **Tipografía web-app:** Space Grotesk + Fraunces + JetBrains Mono. Fuentes en `web-app/src/assets/fonts/`, tokens en `src/styles/tokens.css`.
- **Tipografía vanilla:** Google Fonts — Inter + JetBrains Mono.
- **Iconos:** Lucide React, `stroke-width="1.5"`, `currentColor`.
- **Backend:** FastAPI (Python 3.10+), SQLAlchemy async + asyncpg, PostgreSQL (Supabase prod / `zaris_dev` local).

## 5. Convenciones de Código

- SQL: snake_case.
- API: prefijo `/api/v1/<nombre_modulo>`.
- Archivos frontend: minúsculas con guiones o guiones_bajos.
- Timestamps: UTC.
- Bajas lógicas: `activo = false`, nunca DELETE físico.
- **CORS:** agregar nueva URL a `allow_origins` en `backend/app/main.py`. No duplicar el parámetro — Python lanza `SyntaxError`.
- **Quirks de columnas legacy de auditoría** (verificado en prod 2026-05-10, no renombrar):
  - **Estándar §10 (`fecha_modificacion`):** la mayoría de tablas (21).
  - **Legacy `fecha_modif`:** `usuarios`, `empresas`. `ciudadanos` tiene **ambas** (legacy + nueva) — usar `fecha_modificacion` como fuente.
  - **Legacy `modificado_en`:** `lugares_atencion`, `servicios`, `turnos`, `areas`, y todas las `agenda_*` (`agenda_agente`, `agenda_ausencia`, `agenda_clase`, `agenda_lugar`, `agenda_servicio`).
  - Antes de escribir un UPDATE con `fecha_modificacion = NOW()`, verificar que la tabla tenga esa columna (`information_schema.columns`). Migración 26 falló por esto en `lugares_atencion`.
- **CORS y headers custom:** cuando un endpoint devuelve un header custom (ej. `X-Total-Count`), agregar también `response.headers["Access-Control-Expose-Headers"] = "NombreHeader"`. Sin esto, navegadores cross-origin lo bloquean. Ejemplo en `GET /buc/ciudadanos/buscar`.

## 6. URLs del Proyecto

Monorepo: `github.com/CesarZeta/zaris-zge`.

| Entorno | Servicio | URL / Comando |
|---|---|---|
| Prod | API | `https://zaris-api-production-bf0b.up.railway.app` |
| Prod | Health | `https://zaris-api-production-bf0b.up.railway.app/api/health` |
| Prod | Swagger | `https://zaris-api-production-bf0b.up.railway.app/docs` |
| Prod | Frontend | `https://cesarzeta.github.io/zaris-zge/index.html` |
| Prod | Login | `https://cesarzeta.github.io/zaris-zge/frontend/login.html` |
| Local | API | `http://127.0.0.1:8000` — `$env:ENV_FILE=".env.local"; uvicorn app.main:app --host 127.0.0.1 --port 8000` (desde `backend/`) |
| Local | Web app | `http://localhost:5173` — `cd web-app && pnpm dev` |
| Local | Frontend | `http://localhost:8080` — `python -m http.server 8080` (raíz del repo) |
| Local | DB | `postgresql://postgres:145236@127.0.0.1:5432/zaris_dev` |

## 7. Workflow de Desarrollo

1. Aplicar cambios en local.
2. Verificar visualmente en local antes de cualquier push:
   - Frontend: `python -m http.server 8080` (desde la raíz del repo) → `http://localhost:8080`
   - Backend: `$env:ENV_FILE=".env.local"; uvicorn app.main:app --host 127.0.0.1 --port 8000` (desde `backend/`)
3. Hacer `git push` **solo cuando el usuario lo pida explícitamente**, o cuando sea operativamente necesario (ej: Railway necesita el código para funcionar).
4. No preguntar si hacer push después de cada tarea — indicar cómo testear local y esperar instrucción.

## 9. Deploy Railway

- **Proyecto:** `inspiring-empathy` → servicio `zaris-api`, branch `main`, root `/backend`.
- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- El Custom Start Command tiene prioridad sobre el `Procfile`. Si se mueve `main.py`, actualizar en Railway → Settings → Deploy.

## 10. Campos Estándar por Tabla

Toda tabla nueva debe incluir al final:

| Campo | Tipo | Descripción |
|---|---|---|
| `activo` | `BOOLEAN DEFAULT TRUE` | Baja lógica |
| `id_municipio` | `INTEGER` | FK futura → `municipios` |
| `id_subarea` | `INTEGER` | FK futura → `subareas` |
| `fecha_alta` | `TIMESTAMPTZ DEFAULT NOW()` | Creación |
| `fecha_modificacion` | `TIMESTAMPTZ DEFAULT NOW()` | Última modificación — no llamar `fecha_actual` |
| `id_usuario_alta` | `INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL` | Usuario creador |
| `id_usuario_modificacion` | `INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL` | Usuario modificador |

`id_usuario_alta` e `id_usuario_modificacion` los inyecta el backend desde el JWT — no vienen del frontend.

## 11. Horario en Tablas de Servicio

Tablas con horario de atención (`equipos`, `servicios`, etc.) deben incluir:

| Campo | Tipo | Ejemplo |
|---|---|---|
| `dias_semana` | `TEXT` | `"lunes,martes,miércoles,jueves,viernes"` |
| `hora_inicio` | `TIME` | `09:00` |
| `hora_fin` | `TIME` | `16:00` |

## 12. Agregar Módulo al Shell React

1. Crear `web-app/src/modules/<nombre>/`.
2. Crear `index.ts` exportando un `ModuleManifest` (ver `src/lib/types.ts`).
3. Importar el manifest en `web-app/src/modules/index.ts`.
4. El sidebar y el router lo leen automáticamente — cero cambios al shell.

## 13. Design System Visual — Obligatorio

El estilo oficial de ZARIS vive en `design-system/`. **Para código nuevo, prohibido** usar `styles.css` o variables `--z-*` (son legacy). Usar siempre los tokens del DS nuevo (`--zaris-*`, `--surface-*`, `--fg-*`, `--font-display`, `--font-mono`).

> **Estado real (verificado 2026-05-10):** los tokens `--z-*` y la clase `.z-breadcrumb` siguen vivos en 5 archivos legacy: `agenda.html`, `ciudadano.html`, `empresa.html`, `mainconfig.html`, `usuarios.html`. **Funcionan**, pero contradicen esta regla y deben migrarse al DS nuevo en una pasada futura. Mientras tanto: no agregar más usos. Si tocás esos archivos, aprovechá para migrar el bloque que tocaste.

### CSS a incluir en todo HTML frontend (vanilla)

La ruta depende de dónde vive el archivo:

```html
<!-- Módulos en frontend/ (un nivel de profundidad): -->
<link rel="stylesheet" href="../design-system/fonts/fonts.css">
<link rel="stylesheet" href="../design-system/colors_and_type.css">

<!-- Archivos en la raíz (index.html, welcome.html cargado desde raíz): -->
<link rel="stylesheet" href="design-system/fonts/fonts.css">
<link rel="stylesheet" href="design-system/colors_and_type.css">
```

**Quirk:** `welcome.html` vive en `frontend/` pero el servidor lo sirve como iframe desde la raíz, por lo que usa la ruta sin `../`.

### Tokens CSS — no inventar variables propias

| Uso | Token | Valor |
|---|---|---|
| Fondo de página | `var(--zaris-cream)` | `#f2f1ed` |
| Sidebar / nav | `var(--surface-300)` | `#ebeae5` |
| Cards, modales | `var(--surface-100)` | `#f7f7f4` |
| Superficie sutil | `var(--surface-400)` | `#e6e5e0` |
| Texto primario | `var(--fg-1)` | `#26251e` |
| Texto secundario | `var(--fg-2)` | `rgba(38,37,30,.7)` |
| Texto terciario | `var(--fg-3)` | `rgba(38,37,30,.55)` |
| Borde sutil | `var(--border-primary)` | `rgba(38,37,30,.1)` |
| Borde medio | `var(--border-medium)` | `rgba(38,37,30,.2)` |
| Acento naranja | `var(--zaris-orange)` | `#f54e00` |
| Error / hover | `var(--color-error)` | `#cf2d56` |
| Tipografía display | `var(--font-display)` | Space Grotesk |
| Tipografía mono | `var(--font-mono)` | JetBrains Mono |

### Layout shell (sidebar + topbar)

- **Grid:** `display: grid; grid-template-columns: 232px 1fr; grid-template-rows: 52px 1fr; height: 100vh`
- **Topbar:** `height: 52px`, `background: rgba(242,241,237,.88)`, `backdrop-filter: blur(12px)`
- **Sidebar:** `width: 232px`, `background: var(--surface-300)`, `border-right: 1px solid var(--border-primary)`

### Logo y marca

- Usar `../design-system/assets/zaris-mark-flat.svg` en sidebar/topbar (currentColor, sin fondo).
- Formal (splash, login): `../design-system/assets/zaris-mark.svg`.
- **Prohibido:** emoji en la UI del producto.

## 14. Shell Vanilla — Navegación y Módulos en Iframe

El shell (`index.html`) carga los módulos dentro de un `<iframe id="module-frame">`. El sidebar y topbar siempre permanecen visibles.

### Navegar desde dentro del iframe
```js
// Desde cualquier módulo cargado en el iframe:
(window.parent.shellNavigate || function(){ window.location='../index.html'; })('frontend/mi-modulo.html');
```
Usar este patrón en breadcrumbs, botones "← Inicio" y cualquier enlace de navegación inter-módulo.

### Ocultar header Y sidebar propios cuando se carga en el iframe

Todo módulo que tenga su propio header (`.z-header`) o sidebar interno (`.sidebar`) **debe** ocultarlos al correr dentro del iframe del shell, para evitar duplicación de navegación.

Agregar en `<head>` de todo HTML de módulo, **antes** de los CSS:

```html
<!-- Módulos sin sidebar propio (mayoría): -->
<script>if (window.self !== window.top) { var s = document.createElement('style'); s.textContent = '.z-header{display:none!important}'; document.head.appendChild(s); }</script>

<!-- Módulos CON sidebar propio (ej: admin_tablas.html): -->
<script>if (window.self !== window.top) { var s = document.createElement('style'); s.textContent = '.z-header{display:none!important}.sidebar{display:none!important}.layout{min-height:100vh!important}'; document.head.appendChild(s); }</script>
```

**Regla:** nunca mostrar navegación propia del módulo cuando `window.self !== window.top`. El shell es el único responsable de la navegación lateral.

### Guard vanilla en iframe
Si no hay sesión y el módulo está dentro del iframe, redirigir el shell completo al inicio (no solo el iframe):
```js
if (!localStorage.getItem('zaris_session')) {
    if (window.self !== window.top) {
        window.parent.location.href = '../index.html';
    } else {
        window.location.href = '../index.html';
    }
}
```
El shell `index.html` detecta que no hay sesión y redirige a `frontend/login.html`.

### Manejo de 401 en módulos vanilla

Cuando un fetch devuelve 401 (token expirado o inválido), el módulo debe limpiar la sesión y redirigir. Patrón estándar con `_handleUnauth()`:

```js
function _handleUnauth() {
  localStorage.removeItem('zaris_session');
  if (window.self !== window.top) {
    window.parent.location.href = '../index.html';
  } else {
    window.location.href = '../index.html';
  }
}

// En cada fetch protegido:
const res = await fetch(url, { headers: _authHeaders() });
if (res.status === 401) { _handleUnauth(); return; }
if (!res.ok) throw new Error(`HTTP ${res.status}`);
```

**Implementado en:** `admin_tablas.html` (todas las llamadas a la API).

### Topbar — menú de usuario con cerrar sesión

El topbar del shell (`index.html`) tiene un dropdown al hacer clic en el nombre/avatar:
- Muestra nombre completo y rol del usuario logueado
- Botón **Cerrar sesión** que llama a `localStorage.removeItem('zaris_session')` y redirige a `frontend/login.html`
- CSS en `frontend/css/menu.css` bajo `.user-menu*`
- Lógica en `frontend/js/menu.js`

IDs relevantes: `#user-menu-trigger`, `#user-menu-dropdown`, `#btn-logout`, `#topbar-avatar`, `#topbar-context`, `#user-menu-info`.

### Login vanilla
El shell redirige a `frontend/login.html` si no hay `zaris_session` en localStorage.  
Credenciales dev: email `<username>@municipio.gob.ar`, password `123456` (generadas con `seed_auth.py`).

## 15. Admin Tablas — CRUD Genérico de Maestros

`frontend/admin_tablas.html` es el módulo genérico para todas las tablas de configuración. Se activa via `?tabla=<nombre>` en la URL.

### Agregar una tabla nueva a admin_tablas

1. **Backend** — agregar entrada en `TABLE_CONFIG` en `backend/app/api/routes/admin_tablas.py`:
```python
"nombre_tabla": {
    "pk": "id_campo",           # columna PK
    "cols": ["col1", "col2"],   # columnas editables (nunca pk, activo, audit)
    "fecha_mod": "fecha_modificacion",  # columna de timestamp de edición, o None
    "has_audit": True,          # False si la tabla no tiene id_usuario_alta/modificacion
    "has_activo": True,         # False si la tabla no tiene columna activo
    "col_types": {              # solo si hay columnas TIME o DATE
        "hora_inicio": "time",
        "fecha": "date",
    },
}
```
   - El backend agrega `activo=True` automáticamente en INSERT cuando `has_activo=True`.
   - Columnas `TIME`/`DATE` deben declararse en `col_types` — asyncpg requiere objetos Python (`datetime.time`/`datetime.date`), no strings.

2. **Frontend** — agregar `<div class="sidebar-item">` en `admin_tablas.html` y entrada en `SCHEMAS` (JS).

3. **Shell** — agregar `<a class="nav__link" href="frontend/admin_tablas.html?tabla=nombre_tabla">` en la sección Maestros de `index.html`.

### Estándar visual obligatorio — panel de búsqueda

Todo frontend de tabla maestro (admin_tablas y módulos independientes como usuarios) **debe** incluir el panel celeste de búsqueda como primer elemento visible después del título:

```html
<div class="search-panel">
  <div class="search-panel__title">Buscar {Entidad} existente</div>
  <div class="search-panel__row">
    <input class="search-panel__input" placeholder="Ingresá nombre o descripción..." ...>
    <button class="btn-primary">Buscar</button>
    <button class="btn-primary">+ Nuevo</button>
    <button class="btn-outline">Listado</button>
  </div>
</div>
```

Debajo del panel van los últimos registros ingresados (vista previa). El patrón está implementado en `admin_tablas.html` (`renderVistaPrevia`) y en `usuarios.html`. **No** usar solo botones sueltos — siempre agrupar en el panel celeste.

### Tablas actualmente configuradas
`agentes`, `equipos`, `equipo_usuarios`, `equipo_agentes`, `servicios`, `tipo_usuario`, `cargos`, `area`, `subarea`, `usuarios`, `tipo_reclamo`, `tipo_representacion`, `actividades`, `nacionalidades`, `estado_reclamo`, `estado_ot`, `configuracion_general`, `areas`, `lugares_atencion`, `agenda_clase`, `agenda_feriado`.

> `reclamos_area` y `reclamos_subarea` fueron eliminadas de admin_tablas en migración 20. El módulo Reclamos usa las tablas generales `area` y `subarea`.

## 17. Slash Commands del Proyecto

Comandos disponibles en `.claude/commands/` — invocar con `/nombre`:

| Comando | Descripción |
|---|---|
| `/deploy-railway` | Commit + push + polling health check Railway |
| `/check-api-health` | Verifica todos los endpoints críticos en prod |
| `/run-migration` | Aplica SQL pendiente en local o Supabase prod |
| `/seed-table` | Inserta datos demo en tablas vacías (idempotente) |
| `/audit-shell` | Verifica nav__links, guards, patrones iframe y SCHEMAS |
| `/push-and-verify` | Ciclo completo: commit → push → deploy → verificación |

### Scripts de mantenimiento

| Script | Uso |
|---|---|
| `backend/seed_auth.py` | Aplica migración 11 (email en usuarios) + setea passwords `123456` |
| `backend/seed_demo.py` | Seed local — tablas vacías contra `http://127.0.0.1:8000` |
| `backend/seed_prod.py` | Seed prod — tablas vacías contra Railway (confirmar antes de usar) |
| `backend/seed_incremental.py` | Seed incremental (no borra): cargos, áreas, subareas, tipo_reclamo, ciudadanos (500 desde CSVs en `Tablas Iniciales/`) |
| `backend/seed_reclamos_prod.py` | Inserta 20 reclamos demo en prod; detecta automáticamente si el constraint de estado usa tildes |
| `backend/seed_geo_argentina.py` | Carga provincias / partidos / localidades AR (idempotente vía UPSERT) — usar tras migración 22 |

## 18. Módulo Reclamos

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
`nro_ot` se genera automáticamente vía trigger `trg_nro_ot` → `OT-YYYY-XXXXXX`.

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

Toda edición inserta entrada `Reclamo editado` en `reclamo_historial` preservando estado anterior/nuevo (= estado actual). Si el body trae un campo prohibido para el estado actual: 422 con detalle de campos rechazados vs permitidos. Cambio de tipo re-deriva `id_area` desde `subarea.id_area` (fuente de verdad — ver memoria `tipo_reclamo_area_inconsistencia`). Cambio de empresa valida vínculo activo en `ciudadano_empresa`.

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

### Configuración general

| Clave | Tipo | Descripción |
|---|---|---|
| `auditor_misma_subarea_permitido` | boolean | Si `false`, auditor no puede pertenecer a la subárea del reclamo |
| `ot_pendiente_dias_vencimiento` | integer | Días máximos que una OT Pendiente puede estar sin reasignarse |

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

**Implementado en:** `frontend/reclamos.html` (búsqueda de ciudadano en modal nuevo reclamo).

## 19. Patrón de Baja Lógica — API y Frontend

### Backend
Endpoint estándar de soft-delete (implementado para `usuarios`, `ciudadanos`, `empresas`):
```
PUT /api/v1/buc/{entidad}/{id}/estado?activo=false   → dar de baja
PUT /api/v1/buc/{entidad}/{id}/estado?activo=true    → reactivar
```
Nunca DELETE físico. El endpoint devuelve el objeto con `activo` actualizado.

### Frontend vanilla
En el bloque de resultado de búsqueda (`#result-actions`), agregar botón de baja:
```html
<button class="z-btn z-btn--sm z-btn--danger" id="btn-baja-encontrado" style="display:none;">
    Dar de baja
</button>
```
Mostrarlo en `mostrarResultadoUnico()` y conectarlo a una función `darBaja{Entidad}()` que llame al endpoint con `method: 'PUT'`.

## 20. Modelos SQLAlchemy — Stubs para Tablas sin Modelo Propio

SQLAlchemy valida en startup que toda tabla referenciada en un `ForeignKey()` exista en su metadata. Si una tabla vive en la DB pero no tiene modelo Python, la app crashea con `NoReferencedTableError`.

**Regla:** toda tabla referenciada por FK en un modelo debe tener al menos un stub en Python.

Los stubs actuales están al inicio de `backend/app/models/reclamos.py`:

```python
class Agente(Base):
    __tablename__ = "agentes"
    __table_args__ = {"extend_existing": True}
    id_agente = Column(Integer, primary_key=True, autoincrement=True)

class Area(Base):
    __tablename__ = "area"
    __table_args__ = {"extend_existing": True}
    id_area = Column(Integer, primary_key=True, autoincrement=True)

class Subarea(Base):
    __tablename__ = "subarea"
    __table_args__ = {"extend_existing": True}
    id_subarea = Column(Integer, primary_key=True, autoincrement=True)

class Equipo(Base):
    __tablename__ = "equipos"
    __table_args__ = {"extend_existing": True}
    id_equipo = Column(Integer, primary_key=True, autoincrement=True)
```

**Cuándo agregar un stub:** al crear un modelo con `ForeignKey("tabla_sin_modelo.id_campo")`, agregar el stub correspondiente en el mismo archivo antes de usarlo. `extend_existing=True` evita conflictos si la tabla ya fue declarada en otro modelo.

## 21. Estado de Migraciones en Prod (Supabase)

Las siguientes tablas ya existen en Supabase prod y **no deben re-crearse**:

| Tabla | Migración | Notas |
|---|---|---|
| `reclamos` | 20 | Trigger `trg_nro_reclamo` → `REC-YYYY-XXXXXX` |
| `reclamo_historial` | 20 | FK a `reclamos` |
| `tipo_reclamo` | 20 | Columna `audit` agregada en migración 21 |
| `estado_reclamo` | manual | Estados válidos del flujo de reclamos |
| `ordenes_trabajo` | pre-existente | Trigger `trg_nro_ot` → `OT-YYYY-XXXXXX` |
| `estado_ot` | pre-existente | Seeds: En gestión, En espera, Pendiente, Terminada, Cancelada |
| `equipo_agentes` | pre-existente | Reemplaza `equipo_usuarios` en lógica de OTs |
| `configuracion_general` | pre-existente | Seeds: `auditor_misma_subarea_permitido`, `ot_pendiente_dias_vencimiento` |

**Estados de reclamos en prod** fueron migrados en 2026-05-04:
- `Ingresado` → `Sin asignar`
- `En revisión` → `En gestión`
- `Cerrado` → `Resuelto`
- `Rechazado` → `Cancelado`

CHECK constraint activo: `ck_reclamo_estado` con valores `('Sin asignar','En gestión','En espera','En auditoría','Resuelto','Cancelado')`.

### Migración 22 — Geolocalización + Activos + Adjuntos (`backend/migrations/22_geo_activos_adjuntos.sql`)

**Aplicada en prod Supabase y en local (zaris_dev) al 2026-05-09.** Datos seedeados en prod: 24 provincias, 102 partidos, 352 localidades, 5 tipos_activo, 1000 activos. Incluye:

- Crea `provincias`, `partidos`, `localidades`.
- Crea `tipos_activo`, `activos`.
- Crea `reclamo_adjuntos`.
- Agrega a `reclamos`: `id_estado_fk` (FK → `estado_reclamo.id_estado_reclamo`), `direccion`, `latitud`, `longitud`, `id_localidad`, `id_activo`, `canal_origen`, `fuente_geolocalizacion`, `fecha_cierre`, `fecha_primer_asignacion`, `sla_vencimiento`.
- Trigger `trg_sla_reclamo`: calcula `sla_vencimiento = fecha_alta + tipo_reclamo.sla_dias` al INSERT.
- La columna `estado` (VARCHAR) se mantiene transicional para compatibilidad — deprecada cuando frontend y endpoints migren 100% a `id_estado_fk`.

### Migración 23 — Reasignación de subáreas a sus áreas correctas (`backend/migrations/23_reasignar_subareas_a_areas.sql`)

**Aplicada en prod y local al 2026-05-09.** Resuelve inconsistencia entre `tipo_reclamo.id_area` y `subarea.id_area` reasignando subáreas mal ubicadas (10 subáreas operativas que estaban bajo "Gobierno" pasan a "Servicios Públicos"; 2 a Planeamiento; 1 a Tránsito). 35/35 subáreas activas alineadas con la moda de tipos. Snapshot pre-update en `_backup_subarea_2026_05_09`.

### Migración 26 — Cleanup de áreas duplicadas con/sin tilde (`backend/migrations/26_cleanup_areas_duplicadas.sql`)

**Aplicada en local y prod al 2026-05-10.** Consolida 15 pares de áreas duplicadas (una con tildes, otra sin) eligiendo dinámicamente como canónico el de cada par con más referencias entrantes (`subarea + tipo_reclamo + reclamos + lugares_atencion`); en empate, el activo; en empate, el id menor. Re-routea las FKs entrantes y soft-deletea los duplicados. Si **ambos** estaban inactivos en el grupo, no reactiva nada (área histórica sin uso).

Resultado prod: 19 reclamos legacy de "Servicios Públicos" sin tilde (id=9, ya inactiva) reasignados al canónico "Secretaría de Servicios Públicos" (id=22), que ahora suma 19 reclamos + 49 subáreas + 184 tipos. Las 5 áreas activas finales son: Gobierno (1), Planeamiento sin tilde (6), Servicios Públicos con tilde (22), Seguridad con tilde (28), Tránsito con tilde (36). Snapshot pre-update en `_backup_area_2026_05_10` en ambos entornos.

**Operación por nombre normalizado, NO por ID hardcodeado** — los IDs canónicos difieren entre local y prod (local elige los sin-tilde porque eran los activos, prod elige una mezcla); la función `_ascii_fold(text)` se crea on-the-fly y se borra al final. Idempotente.

> Nota: en prod queda como deuda renombrar `area.id_area=6` ("Secretaria de Planeamiento y Obras Publicas") con tildes para consistencia visual. No es bloqueante. Si se hace, solo es un `UPDATE area SET nombre = 'Secretaría de Planeamiento y Obras Públicas' WHERE id_area = 6;`.

### Migración 25 — `reclamos.id_empresa` (`backend/migrations/25_reclamos_id_empresa.sql`)

**Aplicada en local y prod al 2026-05-10.** Agrega `id_empresa INTEGER NULL REFERENCES empresas(id_empresa) ON DELETE SET NULL` en `reclamos` (1:1, opcional). El backend valida en POST/subreclamo que el ciudadano represente a la empresa via `ciudadano_empresa.activo=TRUE`; si no, 422. El subreclamo hereda `id_empresa` del padre por defecto (override permitido). El GET detalle hace JOIN con `empresas` y devuelve `empresa_nombre` y `empresa_cuit`. La N:M `ciudadano_empresa` (con `id_tipo_representacion`) sigue siendo la única fuente de verdad de qué empresas representa cada ciudadano — esta columna en `reclamos` solo guarda el "a nombre de quién" del reclamo puntual.

### Migración 24 — Re-seed de subarea + tipo_reclamo desde CSVs (`backend/migrations/24_reseed_subareas_tipos_desde_csv.sql` + `backend/seed_subareas_tipos_csv.py`)

**Aplicada en prod y local al 2026-05-09.** Re-seed completo desde `Tablas Iniciales/subarea.csv` (40) y `tipo_reclamo.csv` (288), más 9 subáreas inferidas como huérfanas. Resultado prod:

| Área canónica | id_area prod | Subáreas | Tipos |
|---|---|---|---|
| Secretaría de Servicios Públicos | 22 | 33 | 184 |
| Gobierno | 1 | 6 | 54 |
| Secretaria de Planeamiento y Obras Publicas | 6 | 5 | 27 |
| Subsecretaría de Tránsito | 36 | 4 | 16 |
| Secretaría de Seguridad | 28 | 1 | 1 |
| **Total** | — | **49** | **282** |

Áreas resueltas por heurística por keyword (ver `seed_subareas_tipos_csv.py`). Áreas huérfanas (sin subáreas activas) soft-deleted automáticamente. Snapshot pre-update en `_backup_pre_reseed_2026_05_09`.

> **Importante**: cualquier nueva sesión que toque estas tablas debe verificar el estado actual con `execute_sql` antes de aplicar cambios — esta sección puede quedar desactualizada (CLAUDE.md §24 lo formaliza).

## 22. Geolocalización, Activos y Adjuntos (Reclamos)

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

- **Geocoding directo:** `GET https://nominatim.openstreetmap.org/search?q=<calle+altura+localidad>&format=json&limit=5&countrycodes=ar`
- **Geocoding inverso:** `GET https://nominatim.openstreetmap.org/reverse?lat=<>&lon=<>&format=json`
- **Política de uso:** máx 1 req/seg, enviar `User-Agent: ZARIS-API/1.0 (cesar@zaris.dev)`. Para producción real, considerar Photon o Nominatim self-hosted.
- **Mapas en frontend:** Leaflet + tiles de OSM (gratis, sin API key).
- En el formulario de alta de reclamo, al pickear desde mapa setear `fuente_geolocalizacion = 'pin_manual'`; al elegir sugerencia de Nominatim, `geocoding_osm`.

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
| `fecha_primer_asignacion` | TIMESTAMPTZ | Set al pasar de `Sin asignar` → `En gestión` (medición de SLA real). |
| `fecha_cierre` | TIMESTAMPTZ | Set al pasar a estado final (`Resuelto` o `Cancelado`). |
| `sla_vencimiento` | TIMESTAMPTZ | Calculado por trigger `trg_sla_reclamo` = `fecha_alta + tipo_reclamo.sla_dias`. |

### Estado (FK vs VARCHAR — transición)

- **Migración 22 introduce `id_estado_fk`** como FK a `estado_reclamo(id_estado_reclamo)`.
- La columna `estado` (VARCHAR con CHECK) se mantiene poblada en paralelo durante el período de transición. Endpoints existentes que leen/escriben `estado` siguen funcionando.
- Nuevos consumidores deben usar `id_estado_fk`. Cuando frontend y endpoints migren 100%, se removerá el VARCHAR en una migración futura.

## 23. Patrones de UI ya validados — usar como default

Estos patrones se decidieron en sesiones anteriores y **deben reutilizarse** en lugar de inventar variantes. Si necesitás algo distinto, justificá por qué este no aplica.

### Buscador con autocompletar (≥ ~30 opciones)
Para selectores con muchas opciones (`tipo_reclamo` tiene 282, `ciudadanos` tiene miles), un `<select>` es inusable. Usar siempre **input + dropdown de resultados** consultando un endpoint con `?q=<texto>` y filtro `ILIKE`.

- **Patrón:** input → debounce 250-300ms → fetch `/endpoint?q=&limit=20` → dropdown con resultados → click selecciona y guarda en hidden input.
- **HTML:** clase `.buc-search` con input + `<div class="buc-results">` posicionado absolute debajo.
- **Backend:** endpoint debe aceptar `q` (ILIKE) y `limit`. Ej: `GET /api/v1/reclamos/catalogo/tipos?q=bache&limit=20`.
- **Click-outside:** cerrar todos los dropdowns al click fuera del `.buc-search`.
- **XSS:** escapar HTML del nombre con `.replace(/</g,'&lt;')` siempre. Usar `data-id` + event delegation, **nunca** interpolar IDs en `onclick` inline.
- **Implementado en:** `frontend/reclamos.html` (ciudadanos, tipo de reclamo).

### Drill-down jerárquico inline (sin botón)
Para listados de tablas padre cuyo dataset cabe en pantalla (ej: ≤ 50 áreas, ≤ 50 subáreas), **mostrar siempre los hijos asociados debajo de cada fila** con sangría e indicador naranja. Sin botón "Ver hijos".

- **Pre-fetch en paralelo:** `await Promise.all(rows.map(r => fetch(/padre/{id}/hijos)))` antes de renderizar la tabla.
- **CSS:** `.asociados-row` con borde-izq naranja, `.asociados-list` en grid `repeat(auto-fill, minmax(360px, 1fr))` para nombres largos.
- **No agregar badges de conteo en la celda nombre del listado** — el panel ya muestra "(N)" en su título. Sería redundante.
- **Sí agregar badge en preview** (5 últimos), porque ahí no se muestra el panel inline.
- **Implementado en:** `frontend/admin_tablas.html` (área→subáreas, subárea→tipos).

### Modal anidado para alta inline
Cuando un form requiere referenciar una entidad que podría no existir aún (ej: ciudadano en reclamo), **modal anidado completo** con todos los campos requeridos por el `Create` schema. Z-index mayor al modal padre. ESC y click-fuera priorizan cerrar el modal anidado primero. No "form rápido relajado" — respetar siempre el schema completo.

### Listados de maestros — contador visible
- En vista preview (5 últimos): badge naranja al lado del nombre con `N hijos` (cuando aplique).
- En listado completo: usar el panel inline para mostrar el conteo en su título (`SUBÁREAS ASOCIADAS (4)`), **no duplicar** badges en la celda nombre.
- Mostrar nombres FK como texto (no IDs numéricos). Mapeo en `FK_DISPLAY_MAP` del frontend que resuelve `id_area`/`id_subarea`/`id_cargo`/`id_tipo_usuario` → nombre con tooltip del ID.

### Breadcrumb de navegación — obligatorio en todo módulo

Todo HTML de módulo en `frontend/` (excepto `login.html`, `welcome.html`, `shell.html`, `menu.html`, `mainconfig.html`) **debe** mostrar un breadcrumb arriba del título que ayude al usuario a entender dónde está parado. Patrón único:

```html
<!-- Justo antes del bloque de título del módulo -->
<nav class="zaris-breadcrumb" aria-label="Ruta de navegación">
  <a href="#" data-bc-home>INICIO</a>
  <span class="zaris-breadcrumb__sep">›</span>
  <span class="zaris-breadcrumb__current">Reclamos</span>
</nav>
```

CSS (incluir una vez por archivo, en el `<style>` del módulo):

```css
.zaris-breadcrumb {
  display: flex; align-items: center; gap: 6px;
  font-family: var(--font-display); font-size: 0.78rem;
  margin: 8px 0 16px;
}
.zaris-breadcrumb a {
  color: var(--zaris-orange); text-decoration: none;
  text-transform: uppercase; letter-spacing: 0.04em; font-weight: 600;
}
.zaris-breadcrumb a:hover { text-decoration: underline; }
.zaris-breadcrumb__sep { color: var(--fg-3); }
.zaris-breadcrumb__current {
  color: var(--fg-2); font-weight: 600;
}
```

JS (una vez por archivo, dispara navegación correcta esté o no en iframe):

```js
document.querySelectorAll('[data-bc-home]').forEach(el => {
  el.addEventListener('click', e => {
    e.preventDefault();
    if (window.parent && window.parent.shellNavigate) {
      window.parent.shellNavigate('frontend/welcome.html');
    } else {
      window.location.href = '../index.html';
    }
  });
});
```

Reglas:
- Solo dos niveles: `INICIO > <Módulo>`. Si el módulo tiene sub-vistas (ej: detalle de reclamo), agregar tercer nivel: `INICIO > Reclamos > REC-2026-000017`.
- **Prohibido** usar `.z-breadcrumb` o `var(--z-*)` (legacy, eliminadas — ver §13).
- **Implementado en:** todos los HTML de módulo. `ciudadano.html` y `empresa.html` están migrados a este patrón en una pasada futura (hoy todavía usan `.z-breadcrumb` legacy).

## 24. Workflow de seed desde CSVs en `Tablas Iniciales/`

Los CSVs en `Tablas Iniciales/` son la **fuente autoritativa** de catálogos (subáreas, tipos de reclamo, agentes, cargos, ciudadanos, actividades, nacionalidades). Reglas para escribir scripts de seed:

### Idempotencia obligatoria
Todo seed debe poder correrse múltiples veces sin duplicar ni romper. Patrón:
1. Soft-delete (`activo=FALSE`) lo activo previo.
2. Para cada row del CSV: buscar por nombre (case-insensitive, trim) — si existe, `UPDATE activo=TRUE` + actualizar campos. Si no, `INSERT`.
3. Soft-delete entidades padre que quedaron huérfanas tras el seed.

### Encoding
- Lectura del CSV: `open(path, encoding="utf-8-sig")` (incluye BOM removal).
- Output del script en Windows: setear `$env:PYTHONIOENCODING="utf-8"` antes de correr Python, sino `cp1252` rompe en `print` con caracteres unicode (✓, →, ñ, tildes).
- Evitar caracteres unicode decorativos (━, →, ❌) en `print()` de scripts; usar ASCII (`-`, `->`, `[FAIL]`).

### NO hardcodear IDs entre entornos
Local y prod tienen IDs distintos para las mismas entidades (ej: en local `id_area=1` puede ser "Salud" mientras en prod es "Gobierno"). Resolver siempre **por nombre** dentro del script:
```python
# Buscar por keyword case-insensitive, reactivar si está inactiva, crear si no existe
row = await conn.fetchrow(
    "SELECT id_area, activo FROM area WHERE LOWER(nombre) LIKE $1 ORDER BY activo DESC, id_area LIMIT 1",
    "%gobierno%"
)
```
Esto vale para áreas, tipos de usuario, cargos, nacionalidades, actividades — cualquier catálogo cuyos IDs no estén garantizados estables entre entornos.

### Aplicar en local Y prod en la misma sesión
Una migración aplicada solo en uno desincroniza los entornos. Si aplicaste en prod via MCP, corré también el script en local (o viceversa) antes de cerrar la tarea. Documentar el paso en el commit.

### Antes de aplicar, verificar el estado real con `execute_sql`
**No confiar en CLAUDE.md §21** sobre qué migraciones están aplicadas — la doc puede estar desactualizada. Siempre `to_regclass('public.tabla')` y `COUNT(*)` antes de re-aplicar para evitar duplicar datos o crashear por tabla ya existente.

### Backup antes de operaciones destructivas en prod
Para `UPDATE`/`DELETE` masivos en prod: snapshot previo en tabla `_backup_<tabla>_YYYY_MM_DD`. Permite revert manual sin necesidad de point-in-time recovery.

### CSVs y mapping de IDs legacy
- Los CSVs traen IDs del sistema legacy (ej: `id_area_servicio=6361`) que **no se usan** en la DB nueva. El mapeo es por nombre.
- Los CSVs pueden tener referencias a IDs huérfanos (ej: `tipo_reclamo.id_area_servicio=7984` que no está en `subarea.csv`). Inferir nombres del contenido de los tipos que las usan, agregar como subáreas extra.
- `subarea.csv` viene con `id_area=1` genérico. La asignación real de área se hace por **heurística por keyword** sobre el nombre de la subárea (ver `seed_subareas_tipos_csv.py`).

### Comandos de seed disponibles
| Script | Tablas | Origen |
|---|---|---|
| `seed_geo_argentina.py` | provincias, partidos, localidades | hardcoded AR |
| `seed_subareas_tipos_csv.py` | subarea, tipo_reclamo | `Tablas Iniciales/*.csv` |
| `seed_activos_local.py` | tipos_activo, activos | `Tablas Iniciales/Activos.csv` |
| `seed_auth.py` | usuarios | hardcoded dev |
| `seed_demo.py` / `seed_prod.py` | varios | hardcoded mínimo |
| `seed_incremental.py` | cargos, áreas, subareas, tipo_reclamo, ciudadanos | varios CSVs |

## 26. Adjuntos de Reclamos (Supabase Storage)

**Implementado al 2026-05-10.** El frontend nunca habla con Storage con auth de usuario — el backend firma URLs con la `service_role` key.

### Configuración
- Bucket: `reclamos-adjuntos` (privado, file_size_limit 10 MB, mime allowlist sólo imágenes: `image/jpeg|png|webp|gif|heic|heif`).
- Tabla `reclamo_adjuntos` (existía desde migración 22): metadatos + `storage_bucket` + `storage_path`. Audit completa.
- Vars de entorno backend (`backend/.env.local` y Railway):
  - `SUPABASE_URL` — URL del proyecto Supabase (`https://<id>.supabase.co`)
  - `SUPABASE_SERVICE_KEY` — `service_role` (legacy `eyJ...`) o `sb_secret_...` (nueva). Ambas funcionan; **nunca** la `anon`/`publishable`.
  - `SUPABASE_ADJUNTOS_BUCKET` — default `reclamos-adjuntos`.

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
Para sumar adjuntos a otra entidad (ej: OTs), replicar el patrón: nueva tabla `<entidad>_adjuntos` con mismos campos, nuevo bucket si conviene aislar, y reutilizar `app/core/storage.py` (las funciones reciben `path` arbitrario y leen el bucket de settings — extraer a parámetro si se usan múltiples buckets).
