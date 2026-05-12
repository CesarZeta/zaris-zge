# Reglas Mandatorias de Desarrollo — ZARIS

## 1. Autenticación JWT (SSO)

- **Login:** `POST /api/v1/auth/login` — body `{ email, password }` → `{ access_token, token_type, user }`. Vigencia: 24 h.
- **Me:** `GET /api/v1/auth/me` — usuario autenticado actual.
- **Storage:** `localStorage` clave `zaris_session` — un solo objeto que mantiene **dos shapes en la misma key**: el plano `{ access_token, user }` que leen los módulos vanilla, y `{ state: { accessToken, user }, version: 0 }` que escribe `zustand/persist` en los módulos React. Tanto `frontend/login.html` como el storage custom de `web-app/src/stores/auth.ts` mantienen ambas formas sincronizadas. Detalle en §29.
- **Requests:** header `Authorization: Bearer <token>` en todo endpoint protegido. En módulos React, `web-app/src/lib/api.ts` lo hace automáticamente leyendo `state.accessToken ?? access_token`. En módulos vanilla, cada módulo lo agrega manualmente.
- **Guard módulos vanilla:** verificar `localStorage.getItem('zaris_session')` al inicio; si no existe, redirigir al login del shell vanilla.
- **Guard módulos React:** `AppShell` redirige a `/login` (interno del shell React) si no hay sesión — útil solo en `localhost:5173` standalone. En producción, el módulo React vive en iframe del shell vanilla, que ya garantizó sesión antes de cargarlo.
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

**ZARIS tiene UN SOLO shell de aplicación: el shell vanilla** (`index.html` + `frontend/`). Es el contenedor principal del producto: sidebar de navegación, topbar con usuario, iframe central donde se cargan módulos. Todo lo que ve el usuario en producción vive dentro de este shell.

Los módulos que ese shell carga pueden estar implementados en dos stacks:

| Stack del módulo | Directorio | Cuándo usarlo |
|---|---|---|
| **Vanilla** (HTML/JS/CSS) | `frontend/<modulo>.html` | Módulos legacy y módulos simples nuevos |
| **React** (build de Vite) | `web-app/src/modules/<modulo>/` | Módulos nuevos complejos (forms con estado, DnD, timeline interactivo) |

El directorio `web-app/` contiene un **shell React contenedor** (`AppShell` + sidebar + topbar propios) que **solo se usa en desarrollo local** (`localhost:5173`) para iterar módulos React sin tener que levantar el shell vanilla. **En producción, ese AppShell se auto-oculta** (regla §14) y el módulo React vive embebido en el iframe del shell vanilla. **No hay dos shells en producción** — hay uno solo (vanilla) que carga módulos de distintos stacks.

> Si en algún momento te encontrás pensando "el shell React debería tener su propio sidebar/topbar/notificaciones en prod", **estás equivocado**. Esa función es del shell vanilla. El AppShell del shell React es andamiaje de desarrollo, no UI de producción.

> **Reportes visuales del usuario: PRIMERO preguntar/verificar en qué shell lo vio.** Si el usuario dice "veo X pantalla rara / estilo viejo / sidebar distinto", la primera pregunta es **dónde** lo vio — `localhost:5173` (shell React standalone, solo dev), `localhost:8080/index.html` (shell vanilla local, producto real), `cesarzeta.github.io/zaris-zge/` (prod), o un iframe interno. Las tres superficies se ven distinto y NO es el mismo bug en cada una. Confundirlas hace que audites el archivo equivocado. Caso real sesión 2026-05-12: el usuario reportó "pantalla de logueo anterior" y se asumió que era un legacy puro; era la divergencia entre `frontend/login.html` (vanilla, oficial) y `web-app/src/app/LoginPage.tsx` (shell React, dev), ambos en DS nuevo pero con look distinto.

- **Tipografía módulo React:** Space Grotesk + Fraunces + JetBrains Mono. Fuentes en `web-app/src/assets/fonts/`, tokens en `src/styles/tokens.css`.
- **Tipografía módulo vanilla:** Google Fonts — Inter + JetBrains Mono.
- **Iconos:** Lucide React (módulos React) o SVG inline (módulos vanilla). `stroke-width="1.5"`, `currentColor`.
- **Backend:** FastAPI (Python 3.10+), SQLAlchemy async + asyncpg, PostgreSQL (Supabase prod / `zaris_dev` local).

### Estado real de cada módulo (verificado 2026-05-11)

No suponer paridad entre stacks. Hoy:

| Módulo | Vanilla (`frontend/`) | React (`web-app/src/modules/`) | Producción carga |
|---|---|---|---|
| Login | `login.html` | `LoginPage` (solo en `localhost:5173`) | vanilla |
| Shell del producto | `index.html` | `AppShell` (solo dev) | vanilla |
| BUC ciudadanos | `ciudadano.html` | — | vanilla |
| Reclamos | `reclamos.html` | — | vanilla |
| OT (3 mesas) | `ot_*.html` | — | vanilla |
| Empresas | `empresa.html` | — | vanilla |
| Usuarios | `usuarios.html` | — | vanilla |
| Admin tablas | `admin_tablas.html` | — | vanilla |
| **Agenda** | — (legacy borrado 2026-05-12) | **`modules/agenda/`** (Fase 3.A + 3.B drag&drop) | **React** (publicado) |
| Dashboard | — | `modules/dashboard/` (stub demo, solo dev) | ninguno (no enlazado) |

**Implicaciones:**
- Si te piden "imitar el módulo X en React", verificar primero si existe ahí. Hoy **solo Agenda** está en React en producción. El resto es vanilla.
- Componentes UI compartidos React: `web-app/src/ui/index.tsx` (Button, IconButton, Pill, Badge, Input, Card, EmptyState, Skeleton, Table). **No hay** modal base, datepicker, dropdown, drawer — se construyen en cada módulo o se promueven a `ui/` cuando son maduros.
- Helper `web-app/src/lib/api.ts` soporta GET/POST/PUT/PATCH/DELETE + opciones `{ params, withHeaders }`. `getWithHeaders` devuelve `{ data, headers }` para leer `X-Total-Count`.

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
- **Orden de routers FastAPI con `{param}` greedy en main.py:** si registrás un router nuevo bajo un prefix cuyo tronco lo comparte otro router que usa `/{param}` greedy (como `admin_tablas` con `/{tabla}` y `/{tabla}/{id}`), el router específico **debe registrarse ANTES** del genérico. Sino FastAPI matchea por orden de registro y atrapa la ruta nueva como si fuera `{tabla}='lo-que-sea'`. Síntoma: 422 con `int_parsing` en `{id}` (porque `{id}` no es int). Caso real sesión 2026-05-12: `admin_permisos` bajo `/api/v1/admin/permisos/*` atrapado por `admin_tablas` con `{tabla}='permisos'`, `{id}='modulos'`. Fix: invertir el orden en `main.py`.
- **asyncpg + multi-statement SQL (quirk crítico para scripts de seed/migración):** asyncpg **no acepta** múltiples statements en una sentencia preparada. Si pasás un archivo `.sql` con varios `CREATE`/`INSERT`/`ALTER` a `AsyncSession.execute(text(sql))`, falla con `"no se pueden insertar múltiples órdenes en una sentencia preparada"`. Solución verificada en `seed_agenda.py`:

  ```python
  async with engine.connect() as conn:
      raw = await conn.get_raw_connection()
      asyncpg_conn = raw.driver_connection   # conexion asyncpg real
      await asyncpg_conn.execute(sql)        # acepta scripts multi-statement
  ```

  Alternativas si no querés tocar la conexión cruda: partir el SQL por `;` en Python (cuidado con BEGIN/COMMIT, comentarios, `$$` de funciones) o usar el cliente `psql` por subprocess. La opción `driver_connection` es la más limpia para correr archivos `.sql` enteros desde Python.

## 6. URLs del Proyecto

Monorepo: `github.com/CesarZeta/zaris-zge`.

| Entorno | Servicio | URL / Comando |
|---|---|---|
| Prod | API | `https://zaris-api-production-bf0b.up.railway.app` |
| Prod | Health | `/api/health`, `/health`, `/healthz` (los 3 alias del mismo endpoint, devuelven `{status:"ok",...}`) |
| Prod | Swagger | `https://zaris-api-production-bf0b.up.railway.app/docs` |
| Prod | Shell del producto (entrada) | `https://cesarzeta.github.io/zaris-zge/index.html` |
| Prod | Login del shell | `https://cesarzeta.github.io/zaris-zge/frontend/login.html` |
| Prod | Bundle React (embebido en iframe) | `https://cesarzeta.github.io/zaris-zge/web-app/dist/index.html#/<modulo>/<ruta>` — accedés vía links del shell, no directamente |
| Local | API | `http://127.0.0.1:8000` — `$env:ENV_FILE=".env.local"; uvicorn app.main:app --host 127.0.0.1 --port 8000` (desde `backend/`) |
| Local | Shell React standalone (solo dev) | `http://localhost:5173` — `cd web-app && pnpm dev`. Muestra AppShell con sidebar+topbar propios para iterar módulos React sin levantar el shell vanilla. |
| Local | Shell del producto + módulos vanilla | `http://localhost:8080` — `python -m http.server 8080` (raíz del repo) |
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

## 12. Agregar un módulo React al producto

Los módulos React viven en `web-app/src/modules/<nombre>/`. Se publican como build estático de Vite a GitHub Pages y el shell vanilla los carga en su iframe. **Antes de empezar leer §4 y §14** para entender el contexto.

### Crear el módulo

1. `web-app/src/modules/<nombre>/index.ts` exporta un `ModuleManifest` (ver `web-app/src/lib/types.ts`).
2. Importar el manifest en `web-app/src/modules/index.ts` (array `modules`).
3. El AppShell del shell React contenedor (solo visible en `localhost:5173` durante desarrollo) lee el array y lo agrega al sidebar y al router. Esto **NO** afecta producción.
4. Para que el módulo sea accesible en producción, agregar un `<a class="nav__link" href="web-app/dist/index.html#/<nombre>/<ruta>">` en `index.html` (raíz, dentro del `nav__group` correspondiente).

### Cómo se publica a producción

- **Build:** `pnpm build` en `web-app/` genera `web-app/dist/` con assets que apuntan a `/zaris-zge/web-app/dist/` (configurado en `web-app/vite.config.ts` con `base`).
- **GitHub Pages:** sirve el repo entero desde la raíz; `web-app/dist/index.html` queda accesible en `https://cesarzeta.github.io/zaris-zge/web-app/dist/index.html`.
- **Workflow automático:** `.github/workflows/deploy-web-app.yml` rebuildea `web-app/dist/` y commitea el resultado en cada push a main que toque `web-app/**`.
- **Primer deploy:** ya está commiteado (`web-app/dist/` versionado, ver `.gitignore` con excepción explícita).

### Reglas que un módulo React DEBE respetar

- **Router:** `createHashRouter` (no `createBrowserRouter`). GitHub Pages no soporta HTML5 routing sin server-side rewrites; el F5 sobre `/agenda/timeline` daría 404. Las URLs quedan `…/web-app/dist/index.html#/agenda/timeline`.
- **API base:** leer de `import.meta.env.VITE_API_BASE`. Variables:
  - `web-app/.env.development` → `http://127.0.0.1:8000`
  - `web-app/.env.production` → URL Railway prod
- **Sesión:** usar `useAuthStore` (`web-app/src/stores/auth.ts`) que ya implementa `dualShapeStorage` (mantiene `zaris_session` con `access_token` plano + `state.accessToken`, ver §29).
- **Iframe:** el `AppShell` ya detecta `window.self !== window.top` y se auto-oculta. **No agregar UI propia de navegación** (sidebar, topbar, notificaciones globales) al shell React — esa UI vive en el shell vanilla (`index.html` + `frontend/css/menu.css`).
- **Comunicación con el shell vanilla:** `window.parent?.shellNavigate?.('frontend/<otro-modulo>.html')` para mover el iframe a otro módulo desde el código React.
- **Estilos:** usar tokens del DS (`var(--zaris-orange)`, `var(--fg-1)`, etc.) en lugar de colores hardcodeados — el shell vanilla los inyecta vía `design-system/colors_and_type.css` y el shell React los importa también (`web-app/src/styles/tokens.css`).

## 13. Design System Visual — Obligatorio

El estilo oficial de ZARIS vive en `design-system/`. Tokens en `colors_and_type.css`, componentes en `design-system/components/*.css` (agrupados por `design-system/components.css`). **Prohibido** inventar variables propias, copiar valores hex literales, o agregar archivos como el legacy `frontend/styles.css` (que fue eliminado el 2026-05-12 junto a sus clases `.z-*` y vars `--z-*`).

> **Deuda residual:** `admin_tablas.html` todavía declara internamente un alias-mapping `--z-*` → tokens DS y sus clases internas ad-hoc (`.btn-primary`, `.field`, `.modal`). Funciona, no carga ningún CSS legacy. Migrarlo al naming `*-zaris` es cosmético (~30 min) y opcional. Cualquier módulo nuevo debe usar el DS directo.

> **Antes de crear un componente nuevo del DS o adoptar un naming nuevo:** `grep -rn "<naming-propuesto>" design-system/` para evitar dos namings paralelos. Sesión 2026-05-12 evitó duplicar `btn-zaris` con un hipotético `ds-btn` al detectar 3 huérfanos pre-existentes en `colors_and_type.css`. Aplica también a variables CSS (`--<nombre>`).

### CSS a incluir en todo HTML frontend (vanilla)

La ruta depende de dónde vive el archivo:

```html
<!-- Módulos en frontend/ (un nivel de profundidad): -->
<link rel="stylesheet" href="../design-system/fonts/fonts.css">
<link rel="stylesheet" href="../design-system/colors_and_type.css">
<link rel="stylesheet" href="../design-system/components.css">

<!-- Archivos en la raíz (index.html, welcome.html cargado desde raíz): -->
<link rel="stylesheet" href="design-system/fonts/fonts.css">
<link rel="stylesheet" href="design-system/colors_and_type.css">
<link rel="stylesheet" href="design-system/components.css">
```

**Quirk:** `welcome.html` vive en `frontend/` pero el servidor lo sirve como iframe desde la raíz, por lo que usa la ruta sin `../`.

### Componentes del DS — naming `*-zaris`

| Componente | Clase base | Modificadores |
|---|---|---|
| Botón | `.btn-zaris` | `--primary`, `--accent`, `--ghost`, `--outline`, `--danger`, `--success`, `--pill`, `--pill-active`, `--xs`, `--sm`, `--lg`, `--full`, `--icon` |
| Card | `.card-zaris` | `--elevated`, `--ambient`, `--featured`, `--interactive` + `__header` / `__title` / `__body` / `__footer` |
| Input/Select/Textarea | `.input-zaris`, `.select-zaris`, `.textarea-zaris` | `--error`, `--success` |
| Form layout | `.form-zaris-group`, `.form-zaris-row` | `--2`, `--3`, `--4`, `--1-2`, `--2-1` |
| Label | `.label-zaris` | `--required` |
| Hint/error | `.input-hint-zaris`, `.input-error-zaris` | + `.visible` para mostrar error |
| Checkbox | `.checkbox-zaris` | + `__label` |
| Modal | `.modal-zaris-overlay`, `.modal-zaris` | `--lg`, `--xl` + `__header` / `__title` / `__close` / `__body` / `__footer` |
| Alert | `.alert-zaris` | `--success`, `--error`, `--warning`, `--info` |
| Toast | `.toast-zaris-container`, `.toast-zaris` | `--success`, `--error`, `--warning`, `--info` + `__icon` / `__message` |
| Badge | `.badge-zaris` | `--success`, `--error`, `--warning`, `--info`, `--neutral`, `--sm` |
| Spinner | `.spinner-zaris` | `--sm`, `--lg` |
| Menu card | `.menu-grid-zaris`, `.menu-card-zaris` | + `__icon` / `__title` / `__desc` |
| Section title | `.section-title-zaris` | — |
| Panel expandible | `.panel-expand-zaris` | + `.open` para abrir |
| Search panel celeste (§15) | `.search-panel-zaris` | + `__title` / `__row` / `__input` |
| Search box | `.search-box-zaris` | — |
| Preview row maestros | `.preview-row-zaris` | + `__nombre` / `__meta` / `__estado--activo|inactivo` / `__cta` |
| Listado wrap | `.listado-wrap-zaris`, `.listado-header-zaris`, `.listado-count-zaris` | — |

Las clases con prefijo `.zaris-*` (breadcrumb, body-serif, micro, h1-h4, etc.) siguen viviendo en `colors_and_type.css`. Las nuevas en `components/*.css`.

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

- Marca: **única variante** es `design-system/assets/zaris-mark-flat.svg` (`stroke="currentColor"`, sin fondo). En React inyectar inline con `?raw` para heredar color; en HTML vanilla usar SVG inline (`frontend/login.html` es el patrón canónico). Las variantes `zaris-mark.svg`/`-white`/`-inverse`/`zaris-logo.svg` fueron eliminadas el 2026-05-12 porque no se usaban — cualquier color se logra con CSS sobre el `flat`. Ver `design-system/assets/BRAND-USAGE.md`.
- **Prohibido:** emoji en la UI del producto.

## 14. Shell del producto — iframe único, sidebar y topbar exclusivos del shell

El shell del producto (`index.html` raíz) carga TODOS los módulos dentro de un `<iframe id="module-frame">`. El sidebar y el topbar siempre permanecen visibles y son responsabilidad EXCLUSIVA del shell. **Esta regla aplica por igual a módulos vanilla y a módulos React** — no hay excepciones.

### Regla universal: ocultar navegación propia cuando `window.self !== window.top`

Si el módulo (de cualquier stack) tiene su propio header, sidebar o topbar interno, **debe** ocultarlos al detectar que corre en iframe. Garantiza que el usuario nunca ve doble navegación.

**Módulos vanilla** — agregar en `<head>` del HTML, **antes** de los CSS:

```html
<!-- Sin sidebar propio (mayoría): -->
<script>if (window.self !== window.top) { var s = document.createElement('style'); s.textContent = '.z-header{display:none!important}'; document.head.appendChild(s); }</script>

<!-- CON sidebar propio (ej. admin_tablas.html): -->
<script>if (window.self !== window.top) { var s = document.createElement('style'); s.textContent = '.z-header{display:none!important}.sidebar{display:none!important}.layout{min-height:100vh!important}'; document.head.appendChild(s); }</script>
```

**Módulos React (shell React contenedor)** — el `AppShell` (`web-app/src/app/AppShell.tsx`) detecta el iframe al montar y renderiza solo `<Outlet>` + `<Notifications>`, sin sidebar/topbar/CommandMenu:

```ts
const isEmbedded = typeof window !== 'undefined' && window.self !== window.top
// ...
if (isEmbedded) {
  return (
    <main className={s.embeddedContent}>
      <Outlet />
      <Notifications />
    </main>
  )
}
// modo standalone (solo dev local en localhost:5173): renderiza sidebar+topbar+contenido
```

**Regla operativa al pensar un nuevo componente:** si pensaste "esto va al topbar/sidebar del shell React", PARÁ. Si va a vivir embebido, el topbar/sidebar son del shell vanilla. El componente va a `index.html` y `frontend/css/menu.css`. El shell React solo lo replica para que el módulo se vea coherente en `localhost:5173` durante desarrollo.

### Navegar entre módulos desde dentro del iframe

```js
// Desde un módulo vanilla:
(window.parent.shellNavigate || function(){ window.location='../index.html'; })('frontend/mi-modulo.html');

// Desde un módulo React (TypeScript):
declare global { interface Window { shellNavigate?: (url: string) => void } }
window.parent?.shellNavigate?.('frontend/mi-otro-modulo.html')
```

Usar este patrón en breadcrumbs, botones "← Inicio" y cualquier enlace inter-módulo. Nunca usar `window.location.href` directo — rompe el shell.

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
| `/verify-prod-schema` | Preflight: chequea que tablas/columnas existan en prod antes de codear |
| `/qa-report-template` | Convención y plantilla para reportes QA (`reporte_pruebas_<bloque>_YYYY-MM-DD.md` en raíz) |
| `/migrate-vanilla-to-react` | Receta de 10 pasos para migrar un módulo vanilla a React embebido. Validada con Agenda + Ciudadanos. |

### Scripts de mantenimiento

| Script | Uso |
|---|---|
| `backend/seed_auth.py` | Aplica migración 11 (email en usuarios) + setea passwords `123456` |
| `backend/seed_demo.py` | Seed local — tablas vacías contra `http://127.0.0.1:8000` |
| `backend/seed_prod.py` | Seed prod — tablas vacías contra Railway (confirmar antes de usar) |
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

### Migración 27 — Drop `tipo_reclamo.id_area` (`backend/migrations/27_drop_tipo_reclamo_id_area.sql`)

**Aplicada en local y prod al 2026-05-10.** Elimina la columna redundante `tipo_reclamo.id_area` (y su índice `idx_tipo_reclamo_area`). Desde mig 24 la fuente única del área de un tipo es `subarea.id_area` vía `tr.id_subarea → s.id_area`; mantener la columna espejo obligaba a doble escritura y abría la puerta a inconsistencias (123/282 filas divergentes antes de mig 23-24). Backend (`reclamos.py`, `ordenes_trabajo.py`) ya consultaba exclusivamente vía JOIN con `subarea`; `admin_tablas.py` quitó `id_area` de los `cols` editables de `tipo_reclamo`. Sin vistas ni triggers dependientes.

### Migraciones 30-37 — Módulo Agenda (sub-fase 1.A + autoservicio)

**Aplicadas en local y prod al 2026-05-12.** Estado final del módulo Agenda en prod:

- **Mig 30** (`30_agenda_municipios_y_tipo_reclamo.sql`): crea `municipios` (seed: 1 fila) + ALTER `tipo_reclamo` agregando `duracion_estimada_min INTEGER DEFAULT 60` y `asignacion_a VARCHAR(10) DEFAULT 'agente'` con CHECK `('agente','equipo')`. La parte 1 (CREATE TABLE) se aplicó en el E2E del 2026-05-12; la parte 2 (ALTER tipo_reclamo) quedó pendiente hasta esta sesión, fixed via `30_part2_alter_tipo_reclamo`.
- **Mig 31** (`31_agenda_catalogos.sql`): `estado_evento` (3 seeds: activo/finalizado/cancelado) + `estado_reserva` (3 seeds: reservada/asistio/cancelada).
- **Mig 32** (`32_agenda_eventos_y_reservas.sql`): `eventos` + `evento_encargados` + `evento_reservas`.
- **Mig 33** (`33_agenda_ocupaciones.sql`): `ocupaciones` con CHECK de consistencia tipo↔FK.
- **Mig 34** (`34_agenda_auditoria_y_conflictos.sql`): `conflictos_log` + `agenda_audit_log`.
- **Mig 35** (`35_agenda_autoservicio_tokens.sql`): `eventos.token_publico` + `evento_reservas.token_reserva` (UUID con índices únicos parciales WHERE NOT NULL) + backfill via `gen_random_uuid()`. Requiere `pgcrypto` (creada en la misma mig).
- **Mig 36** (`36_agenda_activo_defaults.sql`): `ALTER COLUMN activo SET DEFAULT TRUE` en las 7 tablas Agenda con esa columna (el E2E descubrió el drift).
- **Mig 37** (`37_agenda_defaults_y_notnull_completos.sql`): cierra el resto del drift de defaults + NOT NULL. Sincroniza ~13 defaults (`id_municipio=1` en 8 tablas, `resuelto=FALSE`, `capacidad_ciudadanos=1`, `cantidad_encargados=0`, `tipo_qr='ninguno'`, `admite_autoservicio=FALSE`) y ~18 `SET NOT NULL` en timestamps con `DEFAULT NOW()`. Verificado pre-aplicación: 0 NULLs en columnas afectadas, no requiere backfill.

**Snapshot pre-mig 30 (parte 2)** en `_backup_tipo_reclamo_2026_05_12_premig30` (282 filas).

**Smoke post-aplicación** (`/api/v1/agenda/calendario`, `/mes`, `/conflictos`, `/eventos/{id}`): 4/4 → HTTP 200 contra Railway. Endpoints públicos `/agenda/publico/*`: 4/4 OK (404/422 según corresponde sin auth).

**Catálogos seedeados en prod:** municipios=1, estado_evento=3, estado_reserva=3. Sin eventos productivos (1 residual del E2E con `activo=false`).

### Migración 38 — Permisos por módulo (`backend/migrations/38_permisos_por_modulo.sql`)

**Aplicada en local y prod al 2026-05-12.** Crea `modulos` (8 seeds: reclamos, padrones, ot_*, turnos, usuarios, admin_tablas con `min_nivel_acceso` segmentado) + `usuario_modulos` (overrides). Ambas con estándar §10 completo. CHECK `min_nivel_acceso BETWEEN 1 AND 4`. UNIQUE `(id_usuario, modulo_codigo)` en overrides. Ver §30 para el detalle del modelo y los endpoints.

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

Todo HTML de módulo en `frontend/` (excepto `login.html` y `welcome.html`) **debe** mostrar un breadcrumb arriba del título que ayude al usuario a entender dónde está parado. Patrón único:

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
- **Implementado en:** todos los HTML de módulo (login no lleva, welcome no lleva).

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

### Antes de aplicar (o de codear backend), verificar el estado real con `execute_sql`
**No confiar en CLAUDE.md §21 ni en la simetría con local.** Antes de:
- **Aplicar/re-aplicar una migración:** chequear si la tabla/columna/seeds ya existen.
- **Codear un endpoint backend que referencie una columna o filas:** chequear que existan en prod, no solo en local.
- **Codear un INSERT que omita columnas:** chequear NOT NULL + DEFAULT + CHECK constraints en prod. Lo que local acepta puede explotar en prod.

**Por qué:** la doc queda atrás Y local puede tener cambios manuales sin migración formal. Casos reales:
- Mig 22 figuraba como pendiente en CLAUDE.md cuando ya estaba aplicada con 1000 activos seedeados (2026-05-09).
- `agentes.es_auditor` existía en local (cambio manual viejo) pero no en prod. Backend `/ot/auditor/me` referenciaba la columna; en prod habría crasheado (2026-05-10).
- `agentes` tenía 3 filas en local pero 0 en prod. Las mesas Agente/Auditoría habrían estado inútiles silenciosamente (2026-05-10).
- **Sesión 2026-05-12 cazó 3 drifts en una sola pasada de E2E:** (a) tablas Agenda con `activo NOT NULL` SIN default en prod (local sí tenía), backend `INSERT` confiaba en default → 500. (b) catálogos `municipios`/`estado_evento`/`estado_reserva` vacíos en prod aunque las migs 30+31 los creaban. (c) `ciudadanos_sexo_check` solo en prod requiere uppercase (`HOMBRE|MUJER|OTROS`), backend insertaba `'otro'` → 500. **Cada uno costó un round-trip de debugging que un `execute_sql` de 5 segundos hubiera evitado.**

**Comandos de verificación:**
```sql
-- Existencia de tabla y conteo
SELECT to_regclass('public.tabla') AS existe,
       (SELECT COUNT(*) FROM tabla WHERE activo) AS filas_activas;

-- Columnas que voy a referenciar en backend
SELECT column_name FROM information_schema.columns
WHERE table_name='tabla' AND column_name IN ('col1','col2');

-- Defaults y NOT NULL (drift entre local y prod ataca acá)
SELECT column_name, is_nullable, column_default
  FROM information_schema.columns
 WHERE table_name='tabla'
   AND column_name IN ('activo','col2','col3');

-- CHECKs (valores aceptados)
SELECT conname, pg_get_constraintdef(oid)
  FROM pg_constraint
 WHERE conrelid='tabla'::regclass AND contype='c';

-- Seeds del catálogo
SELECT COUNT(*) FROM catalogo WHERE activo;
```

**Regla operativa:** si codeo backend que dependa de `tabla.columna_nueva`, o que haga un INSERT que omita columnas (confiando en defaults), verifico que TODO el contrato (existencia + defaults + CHECKs + seeds dependientes) coincida en prod via `execute_sql` ANTES de pushear. Si no, crear migración formal aunque "ya esté en local".

### Backup antes de operaciones destructivas en prod
Para `UPDATE`/`DELETE` masivos en prod: snapshot previo en tabla `_backup_<tabla>_YYYY_MM_DD`. Permite revert manual sin necesidad de point-in-time recovery.

### Antes de codear un seed, inspeccionar el CSV
Los CSVs en `Tablas Iniciales/` no son confiables ciegamente:
- Pueden estar **mal/duplicados**: `agente.csv` era idéntico a `cargo.csv` hasta 2026-05-12 (cargos por área, NO personas). Si el script lo usaba para insertar agentes, hubiera creado basura.
- Pueden estar **vacíos** o tener columnas distintas a las esperadas.
- Pueden referenciar IDs legacy que no existen en otros CSVs.

**Antes de escribir el seed, mirar:**
```bash
head -3 "Tablas Iniciales/<nombre>.csv"     # columnas reales + sample
wc -l    "Tablas Iniciales/<nombre>.csv"     # ¿está vacío?
```

Si los datos no son lo que esperabas, **avisar al usuario inmediatamente** en lugar de improvisar mapeos. Los CSVs reales los conoce el municipio; un placeholder mal hecho es deuda nueva.

### CSVs y mapping de IDs legacy
- Los CSVs traen IDs del sistema legacy (ej: `id_area_servicio=6361`) que **no se usan** en la DB nueva. El mapeo es por nombre.
- Los CSVs pueden tener referencias a IDs huérfanos (ej: `tipo_reclamo.id_area_servicio=7984` que no está en `subarea.csv`). Inferir nombres del contenido de los tipos que las usan, agregar como subáreas extra.
- `subarea.csv` viene con `id_area=1` genérico. La asignación real de área se hace por **heurística por keyword** sobre el nombre de la subárea (ver `seed_subareas_tipos_csv.py`).
- **Agentes con cargo huérfano:** si el `id_cargo` legacy no matchea con `cargo.csv` y no hay info real, NO inventar nombre de cargo. Distribuir entre cargos genéricos (id 1-5: Director/Coordinador/Técnico/Administrativo/Operario) via hash determinístico de `apellido||nombre` para que sea reproducible. Patrón usado en sesión 2026-05-12 con 71/84 agentes.

### Idempotencia de seeds — patrón obligatorio
Todo script de seed debe poder correrse N veces sin duplicar. Patrón mínimo:
1. **Dedupe sobre lo existente, no por contador**: leer `SELECT key FROM tabla` al inicio y descartar filas del CSV cuya key ya esté en DB. Anti-patrón: `if existing > 0: return` (lo que hace `seed_inicial.py` — se saltea TODO si hay 1 fila, incluso si faltan 499).
2. **`--confirm-prod` flag** cuando la conexión apunta a Supabase. Default a local.
3. **`--limite N`** parametrizable. No hardcodear 500/1000 en el código.
4. **Defaults compatibles con prod**: ver bloque anterior sobre CHECKs y NOT NULL. Pasar **siempre** todos los campos NOT NULL aunque tengan default — el default puede no existir en prod aunque sí en local.

Ejemplos canónicos: `backend/seed_ciudadanos_csv.py` y `backend/seed_agentes_csv.py` (sesión 2026-05-12).

### Comandos de seed disponibles
| Script | Tablas | Origen |
|---|---|---|
| `seed_geo_argentina.py` | provincias, partidos, localidades | hardcoded AR |
| `seed_subareas_tipos_csv.py` | subarea, tipo_reclamo | `Tablas Iniciales/*.csv` |
| `seed_activos_local.py` | tipos_activo, activos | `Tablas Iniciales/Activos.csv` |
| `seed_ciudadanos_csv.py` | ciudadanos | `Tablas Iniciales/ciudadano.csv` |
| `seed_agentes_csv.py` | agentes | `Tablas Iniciales/agente.csv` + `cargo.csv` |
| `seed_auth.py` | usuarios | hardcoded dev |
| `seed_demo.py` / `seed_prod.py` | varios | hardcoded mínimo |

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

## 27. Módulo Agenda — Estado actual (sub-fase 1.A)

### Datos en zaris_dev local al 2026-05-10 + sincronización prod 2026-05-12

**Aplicado en local Y prod (Supabase) al 2026-05-12.** Migraciones 30-34 + 36-37 + `seed_agenda.py`. Ver §21 sección "Migraciones 30-37" para detalle por mig. Smoke 4/4 endpoints OK contra Railway.

#### Migraciones nuevas

| # | Archivo | Qué hace |
|---|---|---|
| 30 | `30_agenda_municipios_y_tipo_reclamo.sql` | Crea `municipios` + ALTER `tipo_reclamo` (`duracion_estimada_min INT DEFAULT 60`, `asignacion_a VARCHAR(10) DEFAULT 'agente'` con CHECK in `agente|equipo`) |
| 31 | `31_agenda_catalogos.sql` | `estado_evento` (codes: `activo`,`finalizado`,`cancelado`) + `estado_reserva` (codes: `reservada`,`asistio`,`cancelada`) |
| 32 | `32_agenda_eventos_y_reservas.sql` | `eventos` + `evento_encargados` + `evento_reservas` |
| 33 | `33_agenda_ocupaciones.sql` | `ocupaciones` (tabla única con CHECK que garantiza consistencia por tipo: `ot|evento|turno`) |
| 34 | `34_agenda_auditoria_y_conflictos.sql` | `conflictos_log` + `agenda_audit_log` |

Todas siguen estándar §10 completo (`activo`, `id_municipio`, `fecha_alta`, `fecha_modificacion`, audit user). PKs explícitas `id_<tabla>`. Timestamps `TIMESTAMPTZ`. Idempotentes (`CREATE TABLE IF NOT EXISTS`, `ON CONFLICT DO NOTHING`).

#### Seeds demo
- 4 agentes activos en municipio 1 (3 originales + 1 demo "Carlos Demo" agregado por idempotencia).
- 1 equipo "Equipo Demo Mantenimiento" con 2 agentes vinculados vía `equipo_agentes`.
- 1 evento "Vacunacion antigripal" — lunes próximo 9:00-12:00, capacidad 20, tipo_qr=`nominal`, autoservicio=TRUE.
- 2 reservas (los 2 primeros ciudadanos activos).
- 3 ocupaciones (1 `ot` + 1 `evento` + 1 `turno`).

Comando:
```powershell
cd backend
$env:ENV_FILE=".env.local"; python seed_agenda.py
```

### Convenciones del módulo

**FKs apuntan a las PKs reales del proyecto:**
- `eventos.id_subarea` → `subarea.id_subarea`
- `eventos.id_estado_evento` → `estado_evento.id_estado_evento`
- `evento_reservas.id_ciudadano` → `ciudadanos.id_ciudadano`
- `ocupaciones.id_orden_trabajo` → `ordenes_trabajo.id_ot`
- `evento_encargados.id_recurso` y `ocupaciones.id_recurso` → `agentes.id_agente` o `equipos.id_equipo` (sin FK física porque depende de `tipo_recurso`; validación en backend).

**Tabla única `ocupaciones`** con CHECK `ck_ocupacion_consistencia`: garantiza que solo se popule la FK correspondiente al `tipo` (`ot`→`id_orden_trabajo`, `evento`→`id_evento`, `turno`→`id_ciudadano`). No usar tablas separadas por tipo.

**`equipo_agentes` (no `equipo_usuarios`):** el módulo Agenda usa `equipo_agentes` como pivot equipo↔agente (igual que el módulo OT). `equipo_usuarios` solo existe en local como tabla vacía legacy; en prod no existe.

**`asignacion_a` en `tipo_reclamo`:** define si las OTs del tipo bloquean agenda de `agente` o de `equipo`. `duracion_estimada_min` es lo que bloquea el calendario (distinto de `sla_dias`, que es deadline del reclamo).

### Convención bitmask `dias_semana`

`agenda_agente`, `agenda_lugar`, `agenda_servicio` (y futuras tablas de disponibilidad) usan **`dias_semana SMALLINT`** con bitmask, NO TEXT como `servicios`:

| Día | Bit | Valor |
|---|---|---|
| Lunes | 0 | 1 |
| Martes | 1 | 2 |
| Miércoles | 2 | 4 |
| Jueves | 3 | 8 |
| Viernes | 4 | 16 |
| Sábado | 5 | 32 |
| Domingo | 6 | 64 |

Ejemplos: lunes a viernes = `31`, fin de semana = `96`, todos = `127`. CHECK `BETWEEN 0 AND 127` cierra el universo.

**Helper UI obligatorio** cuando se renderice la UI: `frontend/js/dias-semana.js` (vanilla) o `web-app/src/lib/diasSemana.ts` (React) con `serialize(array)→int`, `deserialize(int)→array`, `format(int)→"Lun, Mié, Vie"` (con atajos "Lun a Vie" para 31 y "Todos" para 127).

### Sistemas de auditoría coexistentes

El proyecto tiene **dos sistemas de auditoría con vocabularios distintos** — no unificar sin decisión explícita:
- `reclamo_historial` (Reclamos + OT): registra cambios de estado y notas custom como filas append-only.
- `agenda_audit_log` (Agenda 3.A): registra `entidad` ∈ {evento, ocupacion, reserva} con `accion` ∈ {crear, modificar, cancelar, asignar} y diffs JSONB.

Si vas a auditar algo nuevo, elegí el sistema según la entidad. No mezclar.

### Pendientes Agenda

#### Sub-fase 1.B — estandarizar legacy (no iniciada)
- [ ] Decidir `areas` (legacy, 6 filas, usado por modelo agenda viejo) vs `area` (canónico, usado por Reclamos/OT). Probable: migrar agenda a `area`.
- [ ] Estandarizar 6 tablas legacy (`agenda_clase`, `agenda_feriado`, `agenda_agente`, `agenda_lugar`, `agenda_servicio`, `agenda_ausencia`): PK `id` → `id_agenda_<x>`, `creado_en`/`modificado_en` → `fecha_alta`/`fecha_modificacion`, `creado_por` → `id_usuario_alta`, agregar `id_usuario_modificacion`, agregar `id_municipio`/`id_subarea`.
- [ ] Migrar `agenda_agente.id_usuario` → `id_agente` (FK a `agentes`). Idem `agenda_ausencia`.
- [ ] Reescribir modelo SQLAlchemy de las legacy.
- [ ] Decidir qué hacer con `turnos`, `agenda_alerta`, `agenda_servicio_agente`, `agenda_lugar_servicio` (vacías en local, no existen en prod). El modelo nuevo (`ocupaciones`+`eventos`+`reservas`) las reemplaza conceptualmente. Probable drop si nada en backend las usa.

#### Sub-fase 2 — Backend API ✅ ENTREGADA (2026-05-10)
22 endpoints en `backend/app/api/routes/agenda_v2.py`. Servicios en `backend/app/services/agenda.py`. Schemas en `backend/app/schemas/agenda_v2.py`. Convive con router legacy `agenda.py` bajo el mismo prefix `/api/v1/agenda` sin colisión de paths. 13/13 pruebas E2E OK.

#### Sub-fase 3.A — Frontend web-app React ✅ ENTREGADA (2026-05-10)
Módulo en `web-app/src/modules/agenda/`. Vistas: Timeline (Gantt con grilla horaria 07-20, línea hora actual, conflictos resaltados), Mensual (grilla 6×7), Eventos (tabla con paginación), Conflictos. Modales: Evento, Encargados, Reserva (con buscador BUC propio), Ocupación, Conflicto. Hooks con react-query. Store Zustand para filtros. TypeScript estricto, sin libs nuevas. **Pruebas manuales en navegador en `PRUEBAS_PENDIENTES.md` bloque A (47 casos)**.

#### Verbos HTTP del router agenda_v2 (referencia obligatoria)

No son obvios y mezclan PUT con PATCH. Antes de scriptear un smoke test o codear un cliente nuevo, hacer `grep "@router\." backend/app/api/routes/agenda_v2.py` para confirmar. Mapeo al 2026-05-11:

| Acción | Verbo | Path |
|---|---|---|
| Crear evento | POST | `/eventos` |
| Editar evento (full) | PUT | `/eventos/{id}` |
| Cancelar evento | **PATCH** | `/eventos/{id}/cancelar` |
| Eliminar evento (soft) | DELETE | `/eventos/{id}` |
| Asignar encargado | POST | `/eventos/{id}/encargados` |
| Quitar encargado | DELETE | `/eventos/{id}/encargados/{id_evento_encargado}` |
| Crear reserva | POST | `/eventos/{id}/reservas` |
| Marcar asistió | **PATCH** | `/reservas/{id}/asistio` |
| Cancelar reserva | **PATCH** | `/reservas/{id}/cancelar` |
| Crear ocupación | POST | `/ocupaciones` |
| Editar ocupación | PUT | `/ocupaciones/{id}` |
| Cancelar ocupación | DELETE | `/ocupaciones/{id}` |
| Calendario día | GET | `/calendario` (**NO** `/calendario/dia`) |
| Calendario mes | GET | `/mes` |
| Conflictos | GET | `/conflictos?resuelto=false` |
| Resolver conflicto | **PATCH** | `/conflictos/{id}/resolver` |
| Recurso (agente o equipo) | GET | `/recurso/{tipo_recurso}/{id_recurso}` |

Smoke test reproducible: `smoke_agenda.ps1` en la raíz. Cubre 15 endpoints clave.

#### Sub-fase 3.B — Drag & Drop sobre la grilla ✅ ENTREGADA (2026-05-11)

Lib: **`@dnd-kit/core@6.3.1`** (PointerSensor, distancia mínima 5px para no confundir click con drag). Implementación en [web-app/src/modules/agenda/dnd/](web-app/src/modules/agenda/dnd/) (types, gridConstants, useDragMutations, useOTsPendientes) + cambios en `GanttOccupationBlock` (useDraggable), `GanttResourceRow` (useDroppable), `TimelineView` (DndContext + DragOverlay + ConfirmModal) y nuevo `PendingOTsPanel` colapsable.

Backend ampliado: `OcupacionUpdate` ahora acepta `tipo_recurso` e `id_recurso` opcionales (juntos) en `PUT /agenda/ocupaciones/{id}`; el handler revalida conflictos contra el recurso nuevo. Sin migración (las columnas ya existían en `ocupaciones`).

Capacidades:
1. **Mover dentro del mismo recurso:** snap a 15 min, clamp dentro de 07-20, persiste directo sin confirmación.
2. **Reasignar a otro recurso:** abre `ConfirmModal` con nombre del recurso destino y horario. Cancelar = no llama backend.
3. **Crear ocupación desde OT pendiente:** drag de OT del `PendingOTsPanel` (lista `GET /ot?estado=Pendiente` filtrada client-side por `id_agente IS NULL && id_equipo IS NULL`) a una fila → modal "Planificar OT" → confirma → `POST /ocupaciones` tipo='ot' con `hora_inicio=09:00`, duración 60min. El usuario ajusta después si quiere.

Pruebas validadas: 9 PASS / 0 FAIL en agente Chrome (T1-T11, ver `reporte_pruebas_3B_2026-05-11.md` si existe). Smoke `smoke_agenda.ps1` 15/15 OK pre y post-cambios.

#### Sub-fase 3.B — Pendientes restantes
- [ ] **Drag con teclado:** @dnd-kit soporta `KeyboardSensor` nativo (flechas + Enter); activarlo es 3 líneas en `TimelineView`. Pendiente porque el agente Chrome no lo pudo automatizar.
- [ ] **Drag de OT a hora exacta del drop:** hoy cae a 09:00 fijo. Para soltar en la hora del cursor hace falta computar `event.activatorEvent.clientX` y restar el rect de la fila (requiere `useDndMonitor` o pasar refs).
- [ ] **Snap visual durante drag:** línea vertical en la posición de snap mientras se arrastra (hoy solo overlay translúcido).
- [ ] **Bloquear drag de ocupaciones tipo=evento:** las ocupaciones con `rol_en_evento='encargado'` están atadas a `evento_encargados`. Hoy reasignarlas con drag mueve solo la fila de `ocupaciones`, dejando `evento_encargados.id_recurso` desincronizado. Workaround actual: pasa pero la app no lo refleja en el modal de evento. Fix: en `GanttOccupationBlock` deshabilitar `useDraggable` si `ocupacion.tipo === 'evento'`, o coordinar backend.
- [ ] Imagen QR renderizada (hoy solo el código de texto).
- [ ] Selectores con autocompletar para OT y evento en `OcupacionModal`.
- [ ] Selector de agente/equipo por nombre en `EventoEncargadosModal`.
- [ ] Filtro por subárea en `AgendaFilters` (backend ya lo acepta).
- [ ] Vista autoservicio público (cuando `evento.admite_autoservicio=TRUE`).
- [x] ~~Migrar/dropear `frontend/agenda.html` vanilla legacy~~ — cerrado 2026-05-12.

#### Aplicar en prod
- [x] ~~Replicar migraciones 30-34 + `seed_agenda.py` en Supabase prod~~ — cerrado 2026-05-12. Las tablas habían entrado en prod durante el E2E del autoservicio sin documentar. Esta sesión completó la parte 2 de mig 30 (ALTER tipo_reclamo) + creó y aplicó mig 37 (defaults + NOT NULL) en local y prod. Ver §21 sección "Migraciones 30-37".

## 28. Recibir prompts armados afuera del proyecto

Cuando el usuario pega un prompt generado fuera de la sesión (ChatGPT, otro Claude, doc compartido), tratarlo como **propuesta**, no como orden de ejecución. Antes de escribir código, validar contra la realidad del proyecto:

### Checklist obligatorio antes de empezar

1. **PKs y nombres de columnas:** los proyectos genéricos asumen `id`, `tabla(id)`. ZARIS usa `id_<tabla>`. Si el prompt dice `REFERENCES ciudadanos(id)`, hay que reescribirlo a `REFERENCES ciudadanos(id_ciudadano)`. Verificar con `information_schema.columns` o consulta a la PK real (ver §24).
2. **Tablas asumidas vs existentes:** correr `to_regclass('public.<tabla>')` para cada tabla que el prompt referencia. Si dice "si no existe creala mínima", chequear si **realmente** no existe — `ordenes_trabajo` ya existía con 18 columnas, no había que crearla mínima.
3. **Tablas deprecadas:** prompts viejos usan `equipo_usuarios` que ya no existe en prod (reemplazada por `equipo_agentes`). Revisar §18 + §21 antes de codear.
4. **Convenciones del proyecto vs prompt:** §10 (campos estándar), §5 (quirks de auditoría), §13 (DS) suelen contradecir lo que un prompt externo asume. Por defecto gana el proyecto, no el prompt.
5. **Librerías del stack:** verificar `package.json`, `requirements.txt` antes de aceptar imports. Si el prompt dice "usar date-fns" y no está, decidir entre instalarlo o reemplazar por Date nativo. Ej: web-app no tiene date-fns ni dayjs.
6. **Módulos asumidos:** "imitar el módulo X" requiere que X exista. La web-app React solo tiene `dashboard` y `agenda` — Reclamos/OT/BUC viven en `frontend/` vanilla (§4).
7. **Decisiones previas pendientes:** si en sesiones anteriores se acordó algo (ej: `dias_semana` bitmask en §27), un prompt externo puede pedir lo contrario (TEXT). Detectarlo y preguntar.
8. **Si el prompt va a involucrar agente externo de QA (Claude Chrome u otro):** antes de pasarle el prompt al usuario, **simular las preconditions** que el agente va a verificar. Especialmente: si el cambio toca schemas backend, hacer `curl /openapi.json` y confirmar que el server runtime ya tiene el código nuevo. Si toca prod, verificar que el deploy llegó (hash de bundle, fecha del último commit servido). El agente externo es caro: una verificación previa de 5 segundos evita un ida y vuelta de varios minutos. Caso real: sesión 2026-05-11, el agente Chrome frenó porque uvicorn corría código viejo — el chequeo previo lo hubiera detectado.

### Cómo responder al prompt

**No empezar a codear directo.** Primero devolver:
- Lista de conflictos detectados ("el prompt asume X pero la realidad es Y").
- Decisiones que requieren input del usuario (preguntar con `AskUserQuestion`).
- Alcance reducido si hay piezas que dependen de algo no resuelto (ej: "esto va a sub-fase B").
- Recién con eso resuelto, empezar a generar archivos.

Si el prompt es muy largo y el conflicto está al final, vale la pena leer todo antes de empezar, no descubrir el problema en archivo 15 de 25.

### Casos reales de esta sesión (2026-05-10)

Documentados como ejemplo de qué pasa cuando se omite la validación:
- Fase 1: prompt pedía `disponibilidad_base` + `disponibilidad_excepciones` que duplican `agenda_agente/lugar/servicio` existentes. Hubo que dividir en sub-fase 1.A (lo nuevo) y 1.B (estandarizar legacy).
- Fase 1: prompt usaba `REFERENCES ciudadanos(id)`, `REFERENCES subarea(id)`, `REFERENCES ordenes_trabajo(id)`. Reales: `id_ciudadano`, `id_subarea`, `id_ot`.
- Fase 1: prompt pedía `equipo_usuarios`. No existe en prod. Se usó `equipo_agentes`.
- Fase 1: prompt pedía `dias_semana TEXT`. Decisión previa de la sesión: SMALLINT bitmask. Se mantuvo bitmask.
- Fase 3.A: prompt decía "imitar Reclamos/BUC en web-app". No existen ahí. Se construyó buscador BUC propio en el módulo agenda.
- Fase 3.A: prompt suponía `date-fns` instalado. No está. Se usó Date nativo + helpers locales en `lib/dates.ts`.
- Fase 1: `seed_agenda.py` primera versión usaba `AsyncSession.execute(text(sql_completo_archivo))`. Falló por multi-statement en asyncpg. Se cambió a `raw_connection().driver_connection.execute(sql)` (ver §5).

**Regla operativa:** validar antes de codear ahorra tiempo. Codear primero y corregir después implica reescribir archivos o, peor, dejar inconsistencias.

## 29. Patrones de la web-app React (auth + storage + diagnóstico)

### `localStorage['zaris_session']` tiene **dos shapes** según superficie

La web-app y los módulos vanilla **no comparten** la forma del session storage. Cualquier helper que lea el storage directamente debe soportar ambas o el bug es silencioso (sin token → 401 → redirect a login).

```jsonc
// web-app/ — zustand/persist con name:'zaris_session'
{ "state": { "accessToken": "eyJ...", "user": {...} }, "version": 0 }

// frontend/ vanilla — guardado plano
{ "access_token": "eyJ...", "user": {...} }
```

Pattern para leer token con fallback (ver `web-app/src/lib/api.ts`):

```ts
function getToken(): string | null {
  const raw = localStorage.getItem('zaris_session')
  if (!raw) return null
  const parsed = JSON.parse(raw)
  return parsed?.state?.accessToken ?? parsed?.access_token ?? null
}
```

### Diagnóstico de "redirect inesperado a /login" en la web-app

Cuando un usuario logueado hace click en una ruta protegida y termina en `/login`:

1. **PRIMER sospechoso siempre: `web-app/src/lib/api.ts`**
   - ¿`getToken()` lee la shape correcta? (ver punto anterior)
   - ¿El handler `if (res.status === 401) { ... window.location.href = '/login' }` está disparando porque la request salió sin Authorization?

2. **Recién después:** AppShell guards, router, CSS. El loop "click → 401 → redirect" se ve idéntico a "el router no respeta auth", pero no es lo mismo.

Caso real: commit `46df578` (2026-05-10). Diagnostiqué CSS/router/AppShell durante 5 turnos cuando el bug eran 2 líneas en `getToken()`.

### Mapeo de rutas hijo en React Router v6

En `web-app/src/app/routes.tsx`, las rutas hijo de un módulo deben ser **XOR** entre `index: true` y `path: string`. Pasar `index: undefined` + `path: undefined` a la vez (cuando se mapea genérico desde un `ModuleRoute`) puede hacer que React Router descarte la ruta silenciosamente y deje solo la primera. Patrón correcto:

```ts
children: mod.routes.map((r) =>
  r.index
    ? { index: true as const, handle: r.handle, element: createElement(r.element) }
    : { path: r.path,         handle: r.handle, element: createElement(r.element) }
)
```

### Smoke tests scriptables del backend

Para verificar la capa API de un módulo nuevo sin esperar a tener UI, escribir un `.ps1` con login + secuencia de requests + asserts. Ejemplo: `smoke_agenda.ps1` cubre 15 casos del Bloque A en <2 segundos. Antes de scriptear, **leer los decoradores `@router.get/post/put/patch/delete` del archivo de rutas reales** — la doc y los hooks del frontend pueden estar desactualizados, el router no.

### Forms compartidos creación/edición — `useEffect` que reinicia el state

Modal con dos modos (creación + edición) que sincroniza el form con un detalle remoto y un `defaultDate`/`defaultX` opcional: si todos los inputs externos van al mismo `useEffect`, cualquier cambio del prop "default" mientras el modal está abierto pisa lo que el usuario tipeó.

**Mal (pisa el form):**
```ts
useEffect(() => {
  if (idEvento && detalle.data) setForm(fromDetalle(detalle.data))
  else if (!idEvento) setForm(emptyPayload(defaultDate))
}, [open, idEvento, detalle.data, defaultDate])
```

**Bien (separar reset de hidratación):**
```ts
// Reset solo al abrir o cambiar de evento. Sin defaultDate en deps.
useEffect(() => {
  if (!open) return
  if (!idEvento) setForm(emptyPayload(defaultDate))
}, [open, idEvento])

// Hidratar desde el detalle, una vez disponible.
useEffect(() => {
  if (!open || !idEvento || !detalle.data) return
  setForm(fromDetalle(detalle.data))
}, [open, idEvento, detalle.data])
```

Caso real: BUG-A-001 (commit `365b5ea`, 2026-05-11). El usuario marcó autoservicio=ON, fecha del Timeline cambió por una invalidate de query, el effect re-corrió y pisó el checkbox. Backend persistía OK; el bug era que el form mandaba `false` en submit.

### Confirmaciones de acciones destructivas

`window.confirm()` nativo se ve perfecto en navegadores reales pero **agentes QA y headless browsers tienden a auto-aceptarlo sin renderizar nada**, así que no se ve en screenshots ni se puede inspeccionar por DOM. Para apps que se testean con agentes IA (o para mejor UX consistente con el resto del producto), usar un componente `ConfirmModal` explícito — vive en `web-app/src/modules/agenda/components/ConfirmModal.tsx`. Promoverlo a `src/ui/` cuando lo use otro módulo.

### Buscadores con autocompletar — quirk del setQ post-pick

Componentes tipo `CiudadanoSearch` (input + dropdown debounced) tienen un edge case sutil: al hacer pick, lo natural es `setQ(<nombre completo>)` para mostrarlo en el input. Pero eso re-dispara el `useEffect` del debounce (porque `q.length >= 2`), que vuelve a abrir el dropdown con "Buscando…" o "Sin resultados", tapando la línea de confirmación.

Patrón obligatorio para evitarlo:

```ts
const skipNextRef = useRef(false)

useEffect(() => {
  if (skipNextRef.current) { skipNextRef.current = false; return }
  // ... resto del effect debounced
}, [q])

// En el handler del pick:
onClick={() => {
  skipNextRef.current = true
  onSelect(c)
  setOpen(false)
  setResults([])
  setQ(`${c.apellido}, ${c.nombre}`)
}}
```

Implementado en `CiudadanoSearch.tsx`. Replicar en cualquier autocompletar nuevo (OT, evento, agente — pendientes en sub-fase 3.B Agenda).

### Grillas con `useDroppable` + clicks de fondo

Si una fila de grilla es `useDroppable` (de `@dnd-kit/core`) **y** además quiere capturar clicks "en celda vacía" para crear algo, hay dos trampas que cuestan tiempo:

1. **No poner `onClick` directamente en el wrapper droppable.** El handler de pointerdown de dnd-kit y el bubbling del click pueden cruzarse y dejar la fila "muda" en algunos puntos. Patrón seguro: dentro del wrapper droppable, primer hijo absoluto `<div style="position:absolute; inset:0; zIndex:0; cursor:pointer" onClick={...}>` que actúa como background clickeable. Los bloques (draggables) se posicionan encima con `position:absolute; left/width` propios y captan pointer solo en su área.

2. **No envolver el bloque draggable en un `<div pointerEvents:auto>` que llene el wrapper.** Aunque el padre tenga `pointerEvents:none`, si el hijo `auto` no tiene un `position:absolute` con `left/width` propios, se extiende a toda la fila y se come los clicks del fondo. El draggable tiene que ser el `<button>`/`<div>` final con su `left/width`, sin wrappers intermedios full-bleed. Caso real: BUG-3B-01 en TimelineView Agenda (2026-05-11).

## 30. Permisos por módulo (diseño, no implementado)

§3 hoy solo define `nivel_acceso ∈ {1=Admin, 2=Supervisor, 3=Operador, 4=Consultor}` — un rol único, jerárquico. No alcanza para "Juan es supervisor pero solo de Reclamos, no debe ver Agenda ni Admin Tablas". Cuando se necesite ese control fino, aplicar el modelo híbrido descripto acá.

### Modelo: nivel mínimo por módulo + override por usuario

Cada módulo declara su **nivel mínimo de acceso** (default). Si el `nivel_acceso` del usuario lo alcanza, ve el módulo. Adicionalmente, una tabla nueva `usuario_modulos` permite **override** explícito por usuario:

- Fila con `permitido = TRUE` → el usuario ve el módulo aunque su nivel sea más alto que el mínimo (otorga acceso).
- Fila con `permitido = FALSE` → el usuario NO ve el módulo aunque su nivel sí lo permitiría (bloquea acceso).
- Sin fila → cae al default por nivel.

### Schema futuro (cuando se implemente)

```sql
-- Migración futura (a definir cuando se decida implementar)
CREATE TABLE usuario_modulos (
  id_usuario_modulo   SERIAL PRIMARY KEY,
  id_usuario          INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
  modulo_codigo       VARCHAR(50) NOT NULL,   -- 'reclamos', 'agenda', 'admin_tablas', etc.
  permitido           BOOLEAN NOT NULL,        -- TRUE = override que otorga, FALSE = override que bloquea
  motivo              TEXT,                    -- opcional, registro de por qué
  -- estándar §10
  activo                  BOOLEAN DEFAULT TRUE,
  id_municipio            INTEGER,
  id_subarea              INTEGER,
  fecha_alta              TIMESTAMPTZ DEFAULT NOW(),
  fecha_modificacion      TIMESTAMPTZ DEFAULT NOW(),
  id_usuario_alta         INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
  id_usuario_modificacion INTEGER REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
  UNIQUE (id_usuario, modulo_codigo)
);

-- Catálogo de módulos. Permite que el admin gestione defaults via UI.
CREATE TABLE modulos (
  modulo_codigo       VARCHAR(50) PRIMARY KEY,
  nombre              VARCHAR(100) NOT NULL,
  descripcion         TEXT,
  min_nivel_acceso    SMALLINT NOT NULL DEFAULT 4,  -- default: nivel 4 = todos pueden
  -- estándar §10
  activo              BOOLEAN DEFAULT TRUE
);

INSERT INTO modulos (modulo_codigo, nombre, min_nivel_acceso) VALUES
  ('reclamos', 'Reclamos', 4),
  ('ot', 'Órdenes de trabajo', 3),
  ('agenda', 'Agenda', 3),
  ('buc', 'Ciudadanos', 4),
  ('empresas', 'Empresas', 4),
  ('usuarios', 'Usuarios', 1),       -- solo admin
  ('admin_tablas', 'Admin tablas', 1) -- solo admin
;
```

### Endpoints futuros

- `GET /api/v1/auth/me` → devolver además `modulos_permitidos: ['reclamos', 'agenda', ...]` ya resuelto por el backend aplicando la regla híbrida.
- `GET /api/v1/admin/usuarios/{id}/modulos` → para la UI de gestión.
- `PUT /api/v1/admin/usuarios/{id}/modulos` → set bulk de overrides.
- `GET /api/v1/admin/modulos` / `PUT /api/v1/admin/modulos/{codigo}` → gestión de `min_nivel_acceso`.

### Resolución en el backend (pseudocódigo)

```python
async def modulos_permitidos(db, id_usuario: int, nivel: int) -> list[str]:
    # 1. Defaults: todos los modulos con min_nivel_acceso >= nivel
    defaults = await db.execute(text("""
        SELECT modulo_codigo FROM modulos
        WHERE activo = TRUE AND min_nivel_acceso >= :nivel
    """), {"nivel": nivel})
    permitidos = {r.modulo_codigo for r in defaults.fetchall()}

    # 2. Overrides del usuario
    overrides = await db.execute(text("""
        SELECT modulo_codigo, permitido FROM usuario_modulos
        WHERE id_usuario = :uid AND activo = TRUE
    """), {"uid": id_usuario})
    for r in overrides.fetchall():
        if r.permitido:
            permitidos.add(r.modulo_codigo)
        else:
            permitidos.discard(r.modulo_codigo)

    return sorted(permitidos)
```

### Resolución en el frontend

**Shell vanilla (`frontend/js/menu.js`):** al cargar el shell, llamar `/auth/me`, leer `modulos_permitidos`, ocultar `<a class="nav__link">` cuyos `data-modulo` no estén en la lista.

```html
<a class="nav__link" href="frontend/reclamos.html" data-modulo="reclamos">Reclamos</a>
```

```js
const permitidos = new Set((session.user.modulos_permitidos ?? []))
document.querySelectorAll('.nav__link[data-modulo]').forEach(a => {
  if (!permitidos.has(a.dataset.modulo)) a.style.display = 'none'
})
```

**Shell React (`web-app/src/app/AppShell.tsx`):** el array `modules` ya tiene `permissions?: string[]` declarado en `ModuleManifest`. Convertirlo en `modulo_codigo: string` y filtrar el sidebar leyendo `user.modulos_permitidos`. El campo `permissions` actual queda deprecado.

**Guard a nivel endpoint backend:** además del filtro UI, cada endpoint sensible debe validar que el usuario tenga el módulo. Helper futuro:

```python
async def require_modulo(modulo: str, current_user, db):
    permitidos = await modulos_permitidos(db, current_user["id_usuario"], current_user["nivel_acceso"])
    if modulo not in permitidos:
        raise HTTPException(403, f"Sin acceso al modulo '{modulo}'")
```

Sin esta validación backend, la restricción UI sería evadible (basta llamar al endpoint directo).

### Estado actual (2026-05-12) — IMPLEMENTADO

**Migración 38 (`backend/migrations/38_permisos_por_modulo.sql`) aplicada en local y prod.** Tablas `modulos` + `usuario_modulos` siguiendo §10. Catálogo seedeado con 8 módulos:

| Código | Nombre | min_nivel_acceso | Cubre |
|---|---|---|---|
| `reclamos` | Reclamos | 4 | `frontend/reclamos.html` |
| `padrones` | Padrones | 4 | `frontend/ciudadano.html` + `frontend/empresa.html` |
| `ot_agente` | OT - Agente | 3 | `frontend/ot_agente.html` |
| `turnos` | Turnos y eventos | 3 | módulo React `agenda` |
| `ot_supervisor` | OT - Supervisor | 2 | `frontend/ot_supervisor.html` |
| `ot_auditoria` | OT - Auditoría | 2 | `frontend/ot_auditoria.html` |
| `usuarios` | Usuarios | 1 | `frontend/usuarios.html` |
| `admin_tablas` | Maestros | 1 | resto de `frontend/admin_tablas.html?tabla=*` |

**Backend (`backend/app/core/auth.py`):**
- `modulos_permitidos(db, id_usuario, nivel) -> list[str]` — resuelve defaults por nivel + overrides activos.
- `require_modulo(modulo: str)` — dependency factory para guard de endpoints (devuelve `current_user` igual que `get_current_user`).

**Endpoints (`backend/app/api/routes/admin_permisos.py`, prefix `/api/v1/admin/permisos`):**
- `GET /modulos` — catálogo
- `PUT /modulos/{codigo}` — editar `min_nivel_acceso`
- `GET /usuarios/{id}/modulos` — resolución + overrides
- `PUT /usuarios/{id}/modulos` — set bulk de overrides (reemplaza activos)

**Orden de routers crítico:** `admin_permisos_router` se registra en `main.py` **antes** de `admin_tablas_router`. `admin_tablas` usa `/api/v1/admin/{tabla}` y `/api/v1/admin/{tabla}/{id}` que sin orden explícito atraparían `/api/v1/admin/permisos/*` como si `{tabla}='permisos'`. Devuelve 422 (`int_parsing` sobre `id='modulos'`).

**Auth endpoints ampliados:**
- `POST /api/v1/auth/login` — el `user` ahora incluye `modulos_permitidos: list[str]`.
- `GET /api/v1/auth/me` — idem.

**Frontend vanilla (`frontend/js/menu.js`):**
- Cada `<a class="nav__link">` en `index.html` tiene `data-modulo="<codigo>"`.
- `menu.js` filtra al cargar: oculta links cuyo `data-modulo` no esté en `user.modulos_permitidos`. Si un grupo (`.nav__panel` o `.nav__subpanel`) queda sin links visibles, se oculta el grupo entero.
- Para sesiones cargadas antes del feature (sin `modulos_permitidos` en cache), `menu.js` refresca contra `/auth/me` y persiste la nueva shape sin re-loguear. Si `/me` falla → fail-open en UI (el guard real está en backend).

**Frontend React (shell standalone `localhost:5173`):**
- `ModuleManifest` extendido con `moduloCodigo?: string`. Solo `agendaModule` lo usa (`turnos`); `dashboardModule` queda sin filtro (es stub demo, no se filtra).
- `Sidebar.tsx` filtra por `user.modulos_permitidos`. Fail-open si falta.
- `useAuthStore` agregó `refreshSession()` que llama a `/me` y actualiza el user; `AppShell` lo invoca cuando detecta que `user.modulos_permitidos` no está.

**Guard a nivel endpoint backend (uso opcional):**
```python
from app.core.auth import require_modulo

@router.get("/algo-sensible")
async def algo(current: dict = Depends(require_modulo("reclamos"))):
    ...
```
Devuelve 403 si el usuario no tiene el módulo. **Hoy no aplicado a endpoints existentes** — los routers ya tenían su propio criterio (`nivel_acceso`). Si querés bloquear acceso real al endpoint, agregalo. La UI ya está filtrada.

**Smoke verificado (2026-05-12):**
- Login admin nivel 1 → 8 módulos. Login supervisor nivel 2 → 6. Operador nivel 3 → 4.
- PUT override `reclamos:permitido=FALSE` al usuario id=2 → siguiente login pierde `reclamos`. PUT con `overrides=[]` lo restaura. PUT con `modulo_codigo` inexistente → 422.
- `/admin/permisos/modulos`: admin=200, supervisor=403, sin auth=401.
- Verificado que `/admin/agentes` (admin_tablas) sigue funcionando tras reordenar routers.

## 31. Limpieza de estilos legacy — CERRADA (2026-05-12)

**Bloque completado.** El DS v1.0 (`--z-*`, `.z-*`, `frontend/styles.css`) fue eliminado del repo. Los módulos vanilla cargan ahora componentes oficiales `*-zaris` definidos en `design-system/components/*.css`.

### Avance del bloque

| Paso | Estado | Notas |
|---|---|---|
| 1. Unificar `LoginPage.tsx` con look del vanilla | ✅ | Card sobre `surface-100`, SVG ZARIS inline (currentColor), labels uppercase, botón `fg-1`. |
| 2. Borrar `frontend/agenda.html` + `agenda.css` + `agenda.js` | ✅ | Reemplazados por módulo React. |
| 3. Borrar `frontend/shell.html` | ✅ | Huérfano. |
| 4. Promover componentes a `design-system/components/*.css` + migrar `usuarios`, `ciudadano`, `empresa` (HTML+JS) | ✅ | 10 archivos CSS nuevos (button, card, form, modal, alert, toast, badge, spinner, menu-card, misc) + agregador `components.css`. Naming `*-zaris` siguiendo lo que el DS ya tenía (`btn-zaris`, `card-zaris`, `input-zaris`). |
| 5. Borrar `frontend/styles.css` | ✅ | Cero referencias antes de borrar. |
| 6. Borrar `frontend/menu.html` + `frontend/mainconfig.html` | ✅ | Dead code legacy del shell viejo. Hrefs y `window.location.href` reemplazados por `_zarisGoInicio()` en `config.js` (helper que usa `shellNavigate('frontend/welcome.html')` en iframe o `../index.html` standalone). |

### Estado actual del codebase

| Archivo | `var(--z-*)` | `.z-*` | DS nuevo |
|---|---|---|---|
| `frontend/usuarios.html` + `usuarios.js` | 0 | 0 | ✅ |
| `frontend/ciudadano.html` + `ciudadano.js` | 0 | 0 | ✅ |
| `frontend/empresa.html` + `empresa.js` | 0 | 0 | ✅ |
| `frontend/js/config.js` + `validaciones.js` | 0 | 0 | ✅ |
| `frontend/admin_tablas.html` | ~123 | 5 (solo `z-header*` oculto en iframe) | parcial — alias-mapping local `--z-*` → DS. Sin dependencias externas. Deuda cosmética opcional. |
| `frontend/reclamos.html` | 0 | 5 (solo `z-header*` oculto) | ✅ (clases solo decorativas residuales) |
| `frontend/login.html`, `welcome.html` | 0 | 0 | ✅ |

### Equivalencias usadas en la migración (referencia)

| Legacy | DS nuevo |
|---|---|
| `--z-bg-card` | `--surface-100` |
| `--z-bg-card-alt` | `--surface-200` |
| `--z-text` | `--fg-1` |
| `--z-text2` | `--fg-2` |
| `--z-text3` | `--fg-3` |
| `--z-border` | `--border-primary` |
| `--z-border-focus` | `--border-medium` |
| `--z-accent` | `--zaris-orange` |
| `--z-text-error` | `--color-error` |
| `--z-text-success` | `--color-success` |
| `--z-radius` | `--radius-lg` |
| `--z-radius-sm` | `--radius-md` |
| `--z-radius-lg` | `--radius-xl` |
| `--z-font` | `--font-display` |
| `--z-font-mono` | `--font-mono` |
| `.z-btn .z-btn--primary` | `.btn-zaris .btn-zaris--primary` |
| `.z-card .z-card__body` | `.card-zaris .card-zaris__body` |
| `.z-input` / `.z-select` / `.z-textarea` | `.input-zaris` / `.select-zaris` / `.textarea-zaris` |
| `.z-form-group` / `.z-form-row` | `.form-zaris-group` / `.form-zaris-row` |
| `.z-label` / `.z-label--required` | `.label-zaris` / `.label-zaris--required` |
| `.z-checkbox` / `.z-checkbox__label` | `.checkbox-zaris` / `.checkbox-zaris__label` |
| `.z-input-error` / `.z-input-hint` | `.input-error-zaris` / `.input-hint-zaris` |
| `.z-modal-overlay` / `.z-modal` | `.modal-zaris-overlay` / `.modal-zaris` |
| `.z-toast-container` / `.z-toast` | `.toast-zaris-container` / `.toast-zaris` |
| `.z-badge` | `.badge-zaris` |
| `.z-spinner` | `.spinner-zaris` |
| `.z-section-title` | `.section-title-zaris` |
| `.z-search-box` | `.search-box-zaris` |
| `.z-search-panel` | `.search-panel-zaris` |
| `.z-form-state` (local) | `.form-state` (local del HTML, sin prefijo) |
| `.z-preview-row*` (local) | `.preview-row*` (local del HTML) |
| `.z-listado-wrap` / `.z-tbl-btn` (local) | `.listado-wrap` / `.tbl-btn` (local) |
| `.z-badge-activo` / `.z-badge-inactivo` (local) | `.badge-activo` / `.badge-inactivo` (local) |

> **Patrón importado:** las clases compartidas viven en `design-system/components/`. Las clases específicas del HTML (search-result, form-state, preview-row, filter-bar, listado-wrap, tbl-btn, badge-activo/inactivo, print-header, validate-group, check-validate, cuil-group, empresa-panel) viven inline en el `<style>` de cada HTML, sin prefijo `z-`. Es la convención: si una clase se usa en >1 archivo, va al DS; si es de una vista puntual, queda local.

### Posible deuda futura (opcional)

`admin_tablas.html` todavía tiene 123 `var(--z-*)` locales que mapean a tokens DS. No carga ningún CSS legacy y funciona. Migrar es find/replace de variables + renombrar clases internas — ~30 min, sin ganancia funcional. Solo si querés "0 `--z-*` en el repo".

## 32. Build de `web-app/dist/` y testing local del shell vanilla + bundle

Reglas operativas verificadas en sesión 2026-05-12 cuando se intentó probar la integración shell vanilla + módulo Agenda React **en local**.

### Quirk 1: `pnpm build` toma las env vars del shell

`web-app/vite.config.ts` lee `VITE_API_BASE` de `.env.development` o `.env.production` según el modo. **Pero si la variable está exportada en el shell al ejecutar `pnpm build`, esa gana sobre los `.env` files** — comportamiento estándar de Vite, fácil de pasar por alto.

Consecuencia real (sesión 2026-05-12): se hizo `VITE_API_BASE=http://127.0.0.1:8000 pnpm build --mode development` para probar local. El bundle resultante apuntaba a `127.0.0.1:8000` (correcto para esa prueba). **Si ese dist se commitea, prod queda roto** (apunta a un origen local desde Pages).

**Regla:** antes de commitear `web-app/dist/`, ejecutar `pnpm build` **sin variables seteadas en el shell**, en una terminal limpia, modo prod (default). Verificar con `grep "zaris-api" dist/assets/index-*.js` que el bundle apunte a Railway, no a localhost. Si dudás, abrir el archivo y mirar el primer hit del string `zaris-api`.

### Quirk 2: `web-app/dist/index.html` tiene `base: '/zaris-zge/...'`

Configurado en `vite.config.ts` para GitHub Pages (Pages sirve el repo bajo `/zaris-zge/`). Local:
- `http://localhost:8080/web-app/dist/index.html` → carga el HTML pero **los assets quedan 404** porque buscan `/zaris-zge/web-app/dist/assets/...` y el server raíz no tiene ese prefijo.
- En prod (Pages) no hay problema: la URL real es `https://cesarzeta.github.io/zaris-zge/web-app/dist/...`.

**Cómo probar local la integración shell vanilla + bundle:** levantar un server alternativo que sirva el repo bajo `/zaris-zge/`. Receta en memoria `project_proxy_local_zaris_zge.md`.

### Quirk 3: CORS de FastAPI hay que actualizar si agregás un nuevo origen local

`backend/app/main.py` tiene allowlist explícita. Si levantás un nuevo server local (ej. `localhost:8090` para el proxy), agregalo a `allow_origins` y **reiniciá uvicorn** (los cambios en main.py no entran con autoreload de uvicorn si no usás `--reload`).

### Quirk 4: levantar uvicorn local — chequear si ya hay uno corriendo

`Get-NetTCPConnection -LocalPort 8000` o `curl 127.0.0.1:8000/health` antes de `python -m uvicorn ...`. Si ya hay uno, se va a chocar con error `[Errno 10048] solo se permite un uso de cada dirección de socket`. Bajarlo con `Stop-Process` (puede pedir UAC si lo lanzó otro user) o pedir al usuario que lo baje desde su terminal.

### Quirk 5: PNG/QR en bundle React — solo render cliente

Lib `qrcode` (~26KB gzipped) sobre `<canvas>`. No agregar deps de QR al backend a menos que se necesite imprimir/firmar. El backend solo genera el string identificador (`EVT<id>-RES<id>-<ts>`) en `services/agenda.py`; el frontend lo renderiza visualmente. Patrón implementado en `web-app/src/modules/agenda/components/QRDisplay.tsx`.

### Quirk 6: usar `node_modules/.bin/vite`, no `npx vite`

`npx vite build` puede descargar una versión distinta a la que tiene fijada el proyecto y eso introduce bugs que el repo no ve. Caso 2026-05-12: `npx vite` bajó vite 8 latest que fallaba con error PostCSS resolviendo `@import url("../fonts/fonts.css")` de `design-system/colors_and_type.css`; `node_modules/.bin/vite` (también 8.0.10) compila sin problema. Diagnóstico costó 10 min hasta detectar que `npx` no usaba el binario local.

**Regla:** siempre `cd web-app && node_modules/.bin/vite build` (o `pnpm build` que también respeta el local). Nunca `npx vite`.

### Quirk 7: favicon + title del scaffold de Vite quedan invisibles hasta que un módulo entra a prod

Cuando se crea un módulo React con `pnpm create vite`, el scaffold deja `<title>web-app</title>` + `<link rel="icon" href="/vite.svg">` (rayo violeta). En desarrollo nadie mira la pestaña — y queda olvidado.

**Antes de pushear un módulo React por primera vez a producción**, verificar `web-app/index.html`:
- `<title>` debe decir "ZARIS · ..." (no "web-app", "Vite App", "React App").
- `<link rel="icon">` debe apuntar a `/zaris-favicon.svg` (no `/favicon.svg`, `/vite.svg`).
- `web-app/public/` solo debe tener `zaris-favicon.svg` (y `icons.svg` si aplica). NO debe haber `favicon.svg` (default Vite) ni `zaris-mark.svg` (variante eliminada del DS en sesión 2026-05-12).

Vite reescribe el `href="/zaris-favicon.svg"` durante el build aplicando `base: '/zaris-zge/web-app/dist/'`, así que funciona en local (`localhost:5173`) y en GH Pages (`/zaris-zge/...`) sin tocar nada.

### Quirk 8: `localhost` ≠ `127.0.0.1` para CORS del browser (no para Node/PS)

Para servidores locales que el browser MCP o el navegador del usuario vayan a usar, **abrir el HTML desde `http://localhost:<port>`, no `http://127.0.0.1:<port>`** — aunque resuelven a la misma IP, son orígenes CORS distintos. El allowlist en `backend/app/main.py` tiene `http://localhost:8080` y `http://localhost:8090` explícitos; `127.0.0.1` NO está. Si lo necesitás, lo agregás y reiniciás uvicorn.

Curl, psql, `Invoke-WebRequest` etc. no tienen este problema (sin origin/preflight). Es exclusivo del browser.

### Quirk 9: `python -m http.server` debe lanzarse detached con `Start-Process` desde PowerShell

`Bash run_in_background=true` con `python -m http.server` queda zombie en Windows: el proceso existe pero no escucha. Receta verificada:

```powershell
Start-Process -FilePath python `
  -ArgumentList "-m","http.server","8080" `
  -WorkingDirectory "c:\Users\Cesar\Documents\ZARIS\Desarrollo\ZGE" `
  -WindowStyle Hidden
```

Después `Invoke-WebRequest -UseBasicParsing -Method Head http://localhost:8080/...` valida que sirve. Para matar zombies: `Get-Process python | Where-Object { $_.StartTime -gt (Get-Date).AddMinutes(-30) } | Stop-Process -Force`.

### Quirk 10: credenciales dev en local — admin es `ciudadanovl@`, no `admin@`

Los emails dev son `<username>@municipio.gob.ar` donde `<username>` viene del campo `usuarios.username`, no del rol. En local el admin (nivel 1) tiene username `ciudadanovl` (Cesar Zeta). Probar con `admin@municipio.gob.ar` → 401. Antes de smoke con login:

```powershell
$env:PGPASSWORD="145236"
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -h 127.0.0.1 -U postgres -d zaris_dev `
  -c "SELECT email, nombre, nivel_acceso FROM usuarios WHERE activo ORDER BY nivel_acceso;"
```

En prod: lo mismo via `execute_sql` Supabase MCP. Password de todos los devs: `123456` (set por `seed_auth.py`).
