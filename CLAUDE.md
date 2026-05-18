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
- **Mapas (módulos React):** **Leaflet 1.9 vanilla** (`leaflet` + `@types/leaflet`, sin `react-leaflet`). React 19 + react-leaflet v5 tuvo bugs de compat al cierre 2026-05-12; el patrón usado es montar el mapa en `useEffect` con `useRef<L.Map>` y mantener `onChange` estable vía `useRef` callback. Referencia: `web-app/src/modules/reclamos/components/MapaPicker.tsx`. Workaround obligatorio para iconos del marker (Vite rompe los paths default): import explícito de los PNG (`marker-icon-2x.png`, `marker-icon.png`, `marker-shadow.png`) y `L.Marker.prototype.options.icon = L.icon({...})`.
  - **Elegir tile basemap según uso:**
    - **Pin manual / formularios** (`MapaPicker` Reclamos B4): OSM Standard `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`. Tile colorinche pero útil para reconocer calles al picar pin.
    - **Dashboards / mapas con markers** (`DashboardMap`): **CartoDB Positron** `https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png` (subdomains `'abcd'`, maxZoom 20). Gris claro minimal, gratis, sin API key. Los markers de color destacan sin competir con el tile. Atribución obligatoria: `© OpenStreetMap © CARTO`.
  - **Markers custom por estado:** `L.divIcon` con `<div>` inline (círculo de color + borde blanco + box-shadow) en lugar de PNG. Permite color dinámico y se renderiza más nítido en retina.
  - **Colores de estado deben venir del DS, no inventados.** Para "En gestión" usar `--color-success` `#1f8a65` (verde teal). NUNCA usar naranja para estado porque choca con `--zaris-orange` `#f54e00` del brand (item activo del sidebar, bordes de cards). Otros estados: `Sin asignar=#c62828` rojo, `En espera=#f57f17` amarillo, `En auditoría=#6a1b9a` violeta — todos lo bastante lejos del brand para no confundirse.
- **Backend:** FastAPI (Python 3.10+), SQLAlchemy async + asyncpg, PostgreSQL (Supabase prod / `zaris_dev` local).

### Estado real de cada módulo (verificado 2026-05-12)

No suponer paridad entre stacks. Hoy:

| Módulo | Vanilla (`frontend/`) | React (`web-app/src/modules/`) | Producción carga |
|---|---|---|---|
| Login | `login.html` | `LoginPage` (solo en `localhost:5173`) | vanilla |
| Shell del producto | `index.html` | `AppShell` (solo dev) | vanilla |
| **BUC ciudadanos** | — (borrado 2026-05-12) | **`modules/ciudadanos/`** | **React** (publicado) |
| **Empresas** | — (borrado 2026-05-12) | **`modules/empresas/`** | **React** (publicado) |
| **Reclamos** | — (borrado 2026-05-12) | **`modules/reclamos/`** (Fases A + B1+B2 + B3) | **React** (publicado) |
| Usuarios | `usuarios.html` | — | vanilla |
| Admin tablas | `admin_tablas.html` | — | vanilla |
| **Agenda** | — (legacy borrado 2026-05-12) | **`modules/agenda/`** (Fase 3.A + 3.B drag&drop + B1+B2 espacios/disponibilidad) | **React** (publicado) |
| **Turnos** | — | **`modules/turnos/`** (backoffice completo 2026-05-14 — lista/alta/reprogramar/cumplir/cancelar; autoservicio público pendiente) | **React** (publicado) |
| **Entradas** | — | **`modules/entradas/`** (backoffice completo 2026-05-14 — lista de eventos con espacio + gestión de reservas reusando `ReservaModal` de Agenda; autoservicio ya funciona vía flujo público de eventos) | **React** (publicado) |
| **Dashboard** | — | **`modules/dashboard/`** (mapa Leaflet + stats reales) | **React — HOME del iframe** desde 2026-05-13 (se carga al entrar al shell y al hacer click en INICIO desde cualquier módulo) |
| **OT (3 mesas)** | — (borrado, era `ot_supervisor.html`/`ot_agente.html`/`ot_auditoria.html`) | **`modules/ot/`** (Supervisor / Agente / Auditoría + drawer detalle compartido) | **React** (publicado) |
| **Trámites** | — | **`modules/tramites/`** (backend Fase 1+2 + frontend Fase 3 completo — bandeja, detalle, acciones, timeline, adjuntos, pase, relacionar; 2026-05-16) | **React** (publicado) |
| Config (permisos/identidad/etc.) | — | `modules/config/` | React |

**Implicaciones:**
- Si te piden "imitar el módulo X en React", verificar primero si existe ahí. Hoy **Dashboard, Agenda, Ciudadanos, Empresas, Reclamos, OT, Trámites y Config** están en React en producción. Usuarios y Admin Tablas siguen en vanilla.
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
  - **Legacy `modificado_en`:** `lugares_atencion`, `servicios` (las únicas con esta forma post mig 39). `agenda_clase` y `agenda_feriado` fueron estandarizadas en mig 39; el resto de `agenda_*` legacy y `areas` fueron dropeadas. La tabla legacy `turnos` fue dropeada en mig 39, pero **mig 45 creó una `turnos` nueva** (estándar §10 completo) para el módulo Turnos — no confundir.
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

### Gate de typecheck (pre-commit hook)

Desde 2026-05-13 hay un hook `pre-commit` que corre `tsc -b --noEmit` cuando el commit toca `web-app/**/*.{ts,tsx,json}`. Sino, exit 0 inmediato (no penaliza commits que solo tocan `backend/` o `frontend/`).

- **Script npm:** `pnpm typecheck` (en `web-app/`) → `tsc -b --noEmit`. Útil para correrlo a mano sin commitear.
- **Hook fuente:** versionado en `tools/hooks/pre-commit`. `.git/hooks/` no entra a git por diseño — tras clonar el repo, instalar con `bash tools/hooks/install.sh` (idempotente).
- **Bypass puntual:** `git commit --no-verify`. No usar como hábito; el hook existe porque el build ya corre `tsc -b` (ver `build` en `web-app/package.json`) y queremos cazar errores de tipo antes del push, no en Vercel/GH Pages.
- **Costo:** ~5s con cache TS caliente, ~10s en frío. Cero costo si el commit no toca `web-app/`.

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
- **`hideFromSidebar?: boolean`** en el `ModuleManifest` (`web-app/src/lib/types.ts`): si está en `true`, el módulo se registra (rutas activas, deep-links del shell vanilla funcionan, links inter-módulo siguen funcionando) **pero NO aparece como ítem en el sidebar del shell React standalone** (`localhost:5173`). Útil cuando un módulo es accesible solo desde una landing agrupadora — ej: `ciudadanosModule` y `empresasModule` lo setean porque se entra via la landing del módulo `contactosModule`. El filtro vive en `web-app/src/shell/Sidebar/Sidebar.tsx` y corre antes que el filtro de permisos §30.
- **Estilos:** usar tokens del DS (`var(--zaris-orange)`, `var(--fg-1)`, etc.) en lugar de colores hardcodeados — el shell vanilla los inyecta vía `design-system/colors_and_type.css` y el shell React los importa también (`web-app/src/styles/tokens.css`).

## 13. Design System Visual — Obligatorio

El estilo oficial de ZARIS vive en `design-system/`. Tokens en `colors_and_type.css`, componentes en `design-system/components/*.css` (agrupados por `design-system/components.css`). **Prohibido** inventar variables propias, copiar valores hex literales, o agregar archivos como el legacy `frontend/styles.css` (que fue eliminado el 2026-05-12 junto a sus clases `.z-*` y vars `--z-*`).

> **Estado:** `admin_tablas.html` ya usa tokens DS directos (0 `var(--z-*)` desde commit `951232a`, 2026-05-13). Conserva clases internas ad-hoc (`.btn-primary`, `.field`, `.modal`) **a propósito** — renombrarlas a `*-zaris` colisionaría con el DS sin ganancia funcional. No carga ningún CSS legacy. Cualquier módulo nuevo debe usar el DS directo.

> **Antes de crear un componente nuevo del DS o adoptar un naming nuevo:** `grep -rn "<naming-propuesto>" design-system/` para evitar dos namings paralelos. Sesión 2026-05-12 evitó duplicar `btn-zaris` con un hipotético `ds-btn` al detectar 3 huérfanos pre-existentes en `colors_and_type.css`. Aplica también a variables CSS (`--<nombre>`).

### CSS a incluir en todo HTML frontend (vanilla)

La ruta depende de dónde vive el archivo:

```html
<!-- Módulos en frontend/ (un nivel de profundidad): -->
<link rel="stylesheet" href="../design-system/fonts/fonts.css">
<link rel="stylesheet" href="../design-system/colors_and_type.css">
<link rel="stylesheet" href="../design-system/components.css">

<!-- Archivos en la raíz (index.html): -->
<link rel="stylesheet" href="design-system/fonts/fonts.css">
<link rel="stylesheet" href="design-system/colors_and_type.css">
<link rel="stylesheet" href="design-system/components.css">
```

> `welcome.html` fue borrado el 2026-05-13. La home del shell ahora es el módulo Dashboard React, cargado directamente en el iframe. Cualquier referencia legacy a `shellNavigate('frontend/welcome.html')` debe usar `shellNavigate('web-app/dist/index.html#/dashboard')`. Lo mismo aplica al `src` por defecto del iframe.

### CSS del DS que llega al shell React (módulos en `web-app/`)

**Atención:** el shell React **NO carga `design-system/components.css`**. Solo importa los tokens via `web-app/src/styles/tokens.css` (que duplica/espeja las CSS variables de `colors_and_type.css`). Esto significa:

- ✅ Las **CSS variables** `var(--zaris-orange)`, `var(--fg-1)`, `var(--surface-100)`, `var(--font-display)`, etc. funcionan dentro de cualquier módulo React sin importar nada extra.
- ❌ Las **clases `.btn-zaris`, `.card-zaris`, `.menu-card-zaris`, etc. NO estilan nada** dentro de los módulos React. Si las usás, vas a obtener un `<button>` sin estilos.

**Patrón para módulos React:** usar CSS Modules locales (`*.module.css`) con tokens del DS. Mirá `web-app/src/modules/contactos/pages/Overview.module.css` o `web-app/src/modules/dashboard/pages/Overview.module.css` como referencia. Para una landing con tarjetas estilo "menu-card", **NO se puede importar `menu-card.css` del DS** — replicar el estilo localmente (~50 líneas).

> **Si vas a copiar visualmente un componente del DS dentro de un módulo React:** abrí su archivo `design-system/components/<componente>.css`, copiá el bloque que necesitás a tu `.module.css` local, y reemplazá los selectores `.foo-zaris` por nombres locales `.foo`. Toma 2 min, evita el bug silencioso de "¿por qué no aplica?".

> **Alternativa rechazada:** importar `components.css` desde `main.tsx`. Hoy el shell React es un build estático que también vive embebido en iframe — sumar todo el DS al bundle ahorra ~50 LOC repetidas pero pesa más, y obliga a cuidar colisiones con CSS Modules. Hasta que tengamos un módulo React que necesite la mayoría del DS visual, mantener el patrón de "tokens sí, componentes locales".

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

<!-- CON sidebar interno que SÍ debe verse en iframe (ej. admin_tablas.html — selector de tablas): -->
<script>
if (window.self !== window.top) {
  // Solo ocultamos el header interno. El sidebar interno se mantiene porque
  // es el UNICO selector para cambiar de tabla. Reajustamos top/height del
  // sidebar porque su offset asumía que el header propio ocupaba 64px.
  var st = document.createElement('style');
  st.textContent = '.z-header{display:none!important}'
                 + '.layout{min-height:100vh!important}'
                 + '.sidebar{top:0!important;height:100vh!important}';
  document.head.appendChild(st);
}
</script>
```

**Excepción: doble sidebar permitido cuando el módulo tiene MUCHOS sub-items.** El shell vanilla muestra los módulos (sidebar plano `.nav-flat`); el módulo interno (admin_tablas) muestra el selector de sub-recursos (17 tablas agrupadas). Es feo si el sidebar interno tiene 1-3 items (poner tabs en lugar), pero válido cuando son 10+.

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

### Guard de sesión del shell — DEBE ir en `<head>`, ANTES del iframe

El shell `index.html` redirige a `frontend/login.html` si no hay `zaris_session` en localStorage. El script **DEBE ejecutarse en `<head>` antes de que el navegador empiece a cargar el `<iframe>`**, no al final del body. Si va abajo, el iframe arranca primero, el bundle React monta sin sesión, hace requests al backend, recibe 401, y el handler de 401 redirige el iframe — en producción bajo `/zaris-zge/` ese redirect termina en `cesarzeta.github.io/login` → **404 de GitHub Pages dentro del iframe** mientras el shell padre se ve OK.

Patrón obligatorio en `index.html`:
```html
<head>
  <!-- ... CSS, lucide, etc ... -->

  <!-- Guard de sesion — DEBE ir antes del iframe para que nunca monte sin sesion -->
  <script>
    if (!localStorage.getItem('zaris_session')) {
      window.location.replace('frontend/login.html');
    }
  </script>
</head>
```

### Guard vanilla en iframe
Si un módulo vanilla quiere doblar el check (defensa en profundidad por si alguien abre el HTML standalone), patrón estándar:
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

### Sidebar plano — `.nav-flat` (estilo shell React)

Desde 2026-05-12 jornada 4, el sidebar del shell vanilla (`index.html`) usa diseño **plano de 1 nivel** con icono + label, sin acordeones. Reemplaza la versión anterior `.nav__group/.nav__panel/.nav__sub` con 3 niveles colapsables. Clona el estilo del `Sidebar.tsx` del shell React.

**Estructura:**

```html
<aside class="sidebar" aria-label="Menú principal">
  <nav class="nav-flat" id="nav" aria-label="Navegación principal">
    <a class="nav-flat__item" href="web-app/dist/index.html#/reclamos" data-modulo="reclamos">
      <svg class="nav-flat__icon" viewBox="0 0 24 24" ...>...</svg>
      <span>reclamos</span>
    </a>
    <!-- Item que cubre múltiples permisos: ver §30 data-modulo-fallback -->
    <a class="nav-flat__item" href="..." data-modulo="ot_supervisor" data-modulo-fallback="ot_agente,ot_auditoria">
      <svg ...>...</svg><span>OT</span>
    </a>
  </nav>
  <footer class="sidebar__foot">zaris-zge · v0.1</footer>
</aside>
```

**Reglas:**
- 1 item por módulo (no acordeones). Si un módulo necesita sub-vistas (OT con 3 mesas, Agenda con 4 vistas), las tabs internas del módulo manejan eso.
- **Iconos SVG inline** copiados de Lucide (`stroke-width="1.5"`, `currentColor`). NO cargar Lucide UMD via `<script>` — suma 200KB+ al shell.
- Estado activo: borde naranja a la izquierda (`box-shadow: inset 3px 0 0 var(--zaris-orange)`) + fondo `var(--surface-400)`.
- Si un módulo grande necesita un selector de sub-recursos (ej: admin_tablas con 17 tablas), ese módulo expone su PROPIO sidebar interno cuando corre en iframe. Doble sidebar permitido — ver "Excepción" arriba.

**CSS:** `frontend/css/menu.css` bloque `.nav-flat*`. Las clases legacy `.nav__group/.nav__panel/.nav__sub` quedan en el archivo sin uso (deuda cosmética, no urgente).

**JS:** `frontend/js/menu.js` selecciona ambos (`.nav-flat__item, .nav__link`) por compat retro.

### Topbar — layout (izquierda · centro · derecha)

Desde 2026-05-13 el topbar tiene 3 bloques fijos:

| Posición | Contenido | IDs/clases |
|---|---|---|
| **Izquierda** | `ZARIS` (logo+wordmark, link a inicio) · "GESTION ESTADO" (hardcoded, NO editable) · separador vertical · logo municipio (opcional, `<img>` hidden si no hay URL) · nombre municipio | `.brand` `.brand__name` `.brand__app` `.topbar__sep` `.muni` `#topbar-muni-logo` `#topbar-muni-nombre` |
| **Centro** | Fecha+hora "mar 13 may, 14:32", refresca cada 30s | `.topbar__center` `#topbar-clock` |
| **Derecha** | Campana de notificaciones (placeholder) · dropdown usuario con nombre+rol+logout | `.topbar__bell` `.user-menu` |

**"GESTION ESTADO" es interno del producto.** Vive hardcoded en el HTML como `<span class="brand__app">GESTION ESTADO</span>`. NO se puede editar desde UI ni se persiste en DB. Backend lo expone en `GET /api/v1/config/identidad` solo por compat con el shell vanilla. Si en el futuro alguien tiene que cambiar el nombre del producto, edita `index.html` y `backend/app/api/routes/config_identidad.py` (constante `APP_NOMBRE`).

**El nombre y logo del municipio SÍ son editables** desde el módulo Config → Identidad (ver §21 para las claves y §32 Quirk 13 para el flujo de upload). `menu.js` los carga al boot llamando a `GET /api/v1/config/identidad` (público).

**Cache-bust `?v=`:** los assets del shell (`menu.css`, `menu.js`) se cargan con `?v=YYYY-MM-DDx`. Bumpear ese sufijo cuando los edites o el navegador puede servir la versión vieja por días. Aplica también a JS/CSS de cualquier módulo vanilla.

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
`agentes`, `equipos`, `equipo_usuarios`, `equipo_agentes`, `servicios`, `tipo_usuario`, `cargos`, `area`, `subarea`, `usuarios`, `tipo_reclamo`, `tipo_representacion`, `actividades`, `nacionalidades`, `estado_reclamo`, `estado_ot`, `configuracion_general`, `lugares_atencion`, `agenda_clase`, `agenda_feriado`.

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

### Configuración general

| Clave | Tipo | Descripción |
|---|---|---|
| `auditor_misma_subarea_permitido` | boolean | Si `false`, auditor no puede pertenecer a la subárea del reclamo |
| `ot_pendiente_dias_vencimiento` | integer | Días máximos que una OT Pendiente puede estar sin reasignarse |
| `municipio_nombre` | string | Nombre del municipio que se muestra en el topbar (ej. "MUNICIPALIDAD DE SAN ANDRÉS"). Editable desde Config → Identidad. |
| `municipio_logo_url` | string | URL pública del logo del municipio (servida desde bucket `config-assets` de Supabase Storage). Vacía = sin logo. Editable desde Config → Identidad. |

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
| `estado_ot` | pre-existente | Seeds **aplicados 2026-05-12 via MCP** (la tabla estaba vacía en prod, el endpoint `/reclamos/{id}/cancelar` lo cazó al fallar buscando `'Cancelada'`). 5 estados: En gestión, En espera, Pendiente, Terminada, Cancelada. Idempotente con `ON CONFLICT (nombre) DO NOTHING`. |
| `equipo_agentes` | pre-existente | Reemplaza `equipo_usuarios` en lógica de OTs |
| `configuracion_general` | pre-existente | Seeds: `auditor_misma_subarea_permitido`, `ot_pendiente_dias_vencimiento` |

**Estados de reclamos en prod** fueron migrados en 2026-05-04:
- `Ingresado` → `Sin asignar`
- `En revisión` → `En gestión`
- `Cerrado` → `Resuelto`
- `Rechazado` → `Cancelado`

CHECK constraint activo: `ck_reclamo_estado` con valores `('Sin asignar','En gestión','En espera','En auditoría','Resuelto','Cancelado')`.

### Drift no-migración: `ciudadanos.latitud/longitud` + `empresas.latitud/longitud`

**Verificado prod + local 2026-05-15.** Las 4 columnas existen como `NUMERIC(10,7) NULL` en ambos entornos, **sin migración formal numerada**. Probable cambio manual viejo (mismo origen que `agentes.es_auditor` — caso documentado en §24). Los modelos SQLAlchemy `Ciudadano`/`Empresa` ya las exponían; los schemas Pydantic `*Out` también. Lo que faltaba al 2026-05-15 era declararlas en `CiudadanoBase`/`Update` + `EmpresaBase`/`Update` para aceptarlas en POST/PUT — agregado en commit `164b817` junto a la normalización OSM (ver §22).

**Implicación:** si una sesión futura pide "agregar lat/lon a ciudadanos/empresas", la respuesta es verificar con `execute_sql` y solo tocar schemas Pydantic + frontend. NO redactar `ADD COLUMN`. Ver memoria [[reference_buc_lat_lon_columnas_existentes]].

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

### Migraciones 40-43 — Agenda sub-fase B1: Espacios + Disponibilidad multi-rango

**Aplicadas en local y prod al 2026-05-13.** Habilitan los tres tipos de recurso (`agente`, `equipo`, `espacio`) y horarios laborales multi-rango con turnos rotativos. Detalle:

- **Mig 40** (`40_agenda_espacios.sql`): crea `espacios_agenda` (estándar §10 completo, con `atendido BOOLEAN DEFAULT TRUE`, `capacidad_personas`, `direccion`, `id_subarea`) + N:M `espacio_agentes` (con UNIQUE `(id_espacio, id_agente)`). Catálogo separado de `lugares_atencion` legacy a propósito (ese legacy no tiene shape §10 y no es 1:1 con espacios de agenda — ver decisión 2026-05-13).
- **Mig 41** (`41_agenda_disponibilidad_recurso.sql`): crea `disponibilidad_recurso` (multi-rango — múltiples filas por recurso permiten turnos rotativos). Columnas clave: `tipo_recurso ∈ {agente,equipo,espacio}`, `id_recurso`, `dias_semana SMALLINT 0-127` (bitmask §27), `hora_inicio/hora_fin TIME`, `vigente_desde/vigente_hasta DATE` (opcionales, para rotaciones programadas), `etiqueta`. CHECK enforce: `hora_fin > hora_inicio` y `vigente_hasta >= vigente_desde`. Estándar §10 completo.
- **Mig 42** (`42_agenda_tipo_recurso_espacio.sql`): amplía CHECK `tipo_recurso` en `ocupaciones` (`ck_ocup_tipo_recurso`) y `evento_encargados` (`ck_evt_enc_tipo_recurso`) agregando `'espacio'`. Sin FK física (id_recurso es polimórfica; validación en backend).
- **Mig 43** (`43_agenda_eventos_id_espacio.sql`): agrega `eventos.id_espacio INTEGER REFERENCES espacios_agenda(id_espacio) ON DELETE SET NULL` (opcional — eventos itinerantes/virtuales no usan espacio).

Migraciones idempotentes (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `DROP CONSTRAINT IF EXISTS`). No rompen compat: las tablas nuevas vienen vacías y el filtro `tipo_recurso` en endpoints existentes seguía aceptando `agente|equipo|todos` y ahora también acepta `espacio`.

### Migración 45 — Módulo Turnos (`backend/migrations/45_turnos.sql`)

**Aplicada en local y prod al 2026-05-14.** Crea el catálogo `tipo_servicio_turno` (estándar §10, con `duracion_min`, 3 seeds idempotentes) y la tabla transaccional `turnos` (estándar §10, FKs a `ciudadanos`/`agentes`/`tipo_servicio_turno`, `estado` CHECK `reservado|cumplido|cancelado`, `id_ocupacion` → fila espejo en `ocupaciones`). Idempotente (`CREATE TABLE IF NOT EXISTS`). Ver §33 para el modelo del módulo. **Ojo:** la tabla legacy `turnos` que mig 39 dropeó NO es esta — son tablas distintas que comparten nombre.

### Migración 46 — Turnos autoservicio (`backend/migrations/46_turnos_autoservicio.sql`)

**Aplicada en local y prod al 2026-05-14.** Agrega `turnos.token_turno UUID` (no enumerable, único, default `gen_random_uuid()`, backfill de filas existentes — habilita que el ciudadano consulte/cancele su turno sin JWT) y `turnos.origen VARCHAR(15)` CHECK `backoffice|autoservicio` default `backoffice`. Requiere `pgcrypto` (ya creada en mig 35). Idempotente. Ver §33 sección "Turnos autoservicio".

### Migración 38 — Permisos por módulo (`backend/migrations/38_permisos_por_modulo.sql`)

**Aplicada en local y prod al 2026-05-12.** Crea `modulos` (8 seeds iniciales: reclamos, padrones, ot_*, turnos, usuarios, admin_tablas con `min_nivel_acceso` segmentado) + `usuario_modulos` (overrides). Ambas con estándar §10 completo. CHECK `min_nivel_acceso BETWEEN 1 AND 4`. UNIQUE `(id_usuario, modulo_codigo)` en overrides. Ver §30 para el detalle del modelo y los endpoints. **Mig 44 (2026-05-14)** separó `turnos` en `agenda`/`turnos`/`entradas` → catálogo actual 10 módulos.

### Migración 26 — Cleanup de áreas duplicadas con/sin tilde (`backend/migrations/26_cleanup_areas_duplicadas.sql`)

**Aplicada en local y prod al 2026-05-10.** Consolida 15 pares de áreas duplicadas (una con tildes, otra sin) eligiendo dinámicamente como canónico el de cada par con más referencias entrantes (`subarea + tipo_reclamo + reclamos + lugares_atencion`); en empate, el activo; en empate, el id menor. Re-routea las FKs entrantes y soft-deletea los duplicados. Si **ambos** estaban inactivos en el grupo, no reactiva nada (área histórica sin uso).

Resultado prod: 19 reclamos legacy de "Servicios Públicos" sin tilde (id=9, ya inactiva) reasignados al canónico "Secretaría de Servicios Públicos" (id=22), que ahora suma 19 reclamos + 49 subáreas + 184 tipos. Las 5 áreas activas finales son: Gobierno (1), Planeamiento con tilde (6 — renombrada 2026-05-15), Servicios Públicos con tilde (22), Seguridad con tilde (28), Tránsito con tilde (36). Snapshot pre-update en `_backup_area_2026_05_10` en ambos entornos.

**Operación por nombre normalizado, NO por ID hardcodeado** — los IDs canónicos difieren entre local y prod (local elige los sin-tilde porque eran los activos, prod elige una mezcla); la función `_ascii_fold(text)` se crea on-the-fly y se borra al final. Idempotente.

> Nota: `area.id_area=6` renombrada con tildes a "Secretaría de Planeamiento y Obras Públicas" en local y prod el 2026-05-15. Deuda cerrada.

### Migración 25 — `reclamos.id_empresa` (`backend/migrations/25_reclamos_id_empresa.sql`)

**Aplicada en local y prod al 2026-05-10.** Agrega `id_empresa INTEGER NULL REFERENCES empresas(id_empresa) ON DELETE SET NULL` en `reclamos` (1:1, opcional). El backend valida en POST/subreclamo que el ciudadano represente a la empresa via `ciudadano_empresa.activo=TRUE`; si no, 422. El subreclamo hereda `id_empresa` del padre por defecto (override permitido). El GET detalle hace JOIN con `empresas` y devuelve `empresa_nombre` y `empresa_cuit`. La N:M `ciudadano_empresa` (con `id_tipo_representacion`) sigue siendo la única fuente de verdad de qué empresas representa cada ciudadano — esta columna en `reclamos` solo guarda el "a nombre de quién" del reclamo puntual.

### Migración 24 — Re-seed de subarea + tipo_reclamo desde CSVs (`backend/migrations/24_reseed_subareas_tipos_desde_csv.sql` + `backend/seed_subareas_tipos_csv.py`)

**Aplicada en prod y local al 2026-05-09.** Re-seed completo desde `Tablas Iniciales/subarea.csv` (40) y `tipo_reclamo.csv` (288), más 9 subáreas inferidas como huérfanas. Resultado prod:

| Área canónica | id_area prod | Subáreas | Tipos |
|---|---|---|---|
| Secretaría de Servicios Públicos | 22 | 33 | 184 |
| Gobierno | 1 | 6 | 54 |
| Secretaría de Planeamiento y Obras Públicas | 6 | 5 | 27 |
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
- **Implementado en (vanilla):** patrón vigente para cualquier módulo vanilla nuevo. La versión React del autocompletar BUC vive en `web-app/src/modules/ciudadanos/components/CiudadanoSearch.tsx` (también usado por Reclamos y Agenda) — misma idea (debounce + dropdown + skipNextRef post-pick, ver §29) pero con JSX en lugar de innerHTML.

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

Todo HTML de módulo en `frontend/` (excepto `login.html`) **debe** mostrar un breadcrumb arriba del título que ayude al usuario a entender dónde está parado. Patrón único:

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
      window.parent.shellNavigate('web-app/dist/index.html#/dashboard');
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

Las futuras tablas de disponibilidad usarán **`dias_semana SMALLINT`** con bitmask, NO TEXT como `servicios` (`agenda_agente`/`agenda_lugar`/`agenda_servicio` originalmente la usaban, ahora dropeadas en mig 39):

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

#### Sub-fase 1.B — limpieza legacy ✅ ENTREGADA (2026-05-13, mig 39)
- [x] **Drop 9 tablas legacy vacías**: `agenda_agente`, `agenda_servicio`, `agenda_lugar`, `agenda_servicio_agente`, `agenda_lugar_servicio`, `agenda_ausencia`, `agenda_alerta`, `turnos`, `areas` (plural). Sí existían en prod aunque la doc decía lo contrario. Todas con 0 filas en ambos entornos.
- [x] **Estandarizar `agenda_clase` y `agenda_feriado`** al §10: PK `id_agenda_clase` / `id_agenda_feriado`, `creado_por` → `id_usuario_alta`, `creado_en` → `fecha_alta`, `modificado_en` → `fecha_modificacion`, agregadas `id_usuario_modificacion`, `id_municipio`, `id_subarea`, `activo SET DEFAULT TRUE`. Backfill `id_municipio=1`. `agenda_clase.id_area` y `fecha_baja` dropeadas.
- [x] **Tabla nueva `ausencias_agente`** (estándar §10 completo, FK `id_agente` → `agentes.id_agente`). Reemplaza `agenda_ausencia`. `agenda_v2` ya consulta esta tabla en `/calendario`, `/mes`, `/recurso/{tipo}/{id}` — el JOIN ahora va por `id_agente` directo (no por `usuarios.id_usuario`).
- [x] **Cleanup FKs a `areas`**: `agenda_clase`, `lugares_atencion` y `servicios` tenían `id_area` → `areas(id)`. Limpiado a NULL y FK dropeado. Las columnas `id_area` sobreviven en `lugares_atencion`/`servicios` por compatibilidad (sin FK, siempre NULL); en `agenda_clase` fue dropeada.
- [x] **Backend limpio**: `models/agenda.py` reescrito (solo modelos vivos), `schemas/agenda.py` borrado, `routes/agenda.py` borrado, `main.py` deja de registrar el router legacy. Helper `agenda_ausencia_cols` removido.
- [x] **admin_tablas actualizado**: `agenda_clase` y `agenda_feriado` con PK nueva y `has_audit: True`. Item `areas` removido del sidebar y de `SCHEMAS` del frontend. `lugares_atencion`/`servicios` quedaron sin selector `id_area`.

Snapshot pre-mig en prod y local: `_backup_agenda_clase_2026_05_13`, `_backup_agenda_feriado_2026_05_13`, `_backup_areas_2026_05_13`, `_backup_lugares_atencion_id_area_2026_05_13`, `_backup_servicios_id_area_2026_05_13`. Ver `backend/migrations/39_agenda_legacy_dropear_y_estandarizar.sql`.

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
| Marcar asistió (por id) | **PATCH** | `/reservas/{id_evento_reserva}/asistio` |
| Acreditar asistencia escaneando QR | **POST** | `/reservas/acreditar-qr` |

Smoke test reproducible: `smoke_agenda.ps1` en la raíz. Cubre 15 endpoints clave.

#### QR físico de reservas — flujo de acreditación (2026-05-14)

El QR de una reserva de evento (`evento_reservas.qr_codigo`, formato opaco `EVT{id}-RES{id}-{ts}` generado por `services/agenda.py::generar_qr_codigo`) es un **identificador**, no una URL. El operador lo escanea con un lector y se acredita la asistencia vía `POST /api/v1/agenda/reservas/acreditar-qr` con body `{qr_codigo}` — resuelve la reserva por el string y marca `asistio`. Errores: 404 si el QR no corresponde a reserva activa, 409 si la reserva está cancelada. Reusa el helper `_patch_reserva_estado`. El endpoint se registra **antes** que `/reservas/{id}/...` en el router (defensa contra match greedy, aunque distinto número de segmentos). UI: sección "Acreditar por QR" en `ReservaModal.tsx` (input + botón, Enter acredita). El `id`-numérico (`PATCH /reservas/{id}/asistio`) sigue existiendo para acreditar manual desde la lista.

#### Sub-fase 3.B — Drag & Drop sobre la grilla ✅ ENTREGADA (2026-05-11)

Lib: **`@dnd-kit/core@6.3.1`** (PointerSensor, distancia mínima 5px para no confundir click con drag). Implementación en [web-app/src/modules/agenda/dnd/](web-app/src/modules/agenda/dnd/) (types, gridConstants, useDragMutations, useOTsPendientes) + cambios en `GanttOccupationBlock` (useDraggable), `GanttResourceRow` (useDroppable), `TimelineView` (DndContext + DragOverlay + ConfirmModal) y nuevo `PendingOTsPanel` colapsable.

Backend ampliado: `OcupacionUpdate` ahora acepta `tipo_recurso` e `id_recurso` opcionales (juntos) en `PUT /agenda/ocupaciones/{id}`; el handler revalida conflictos contra el recurso nuevo. Sin migración (las columnas ya existían en `ocupaciones`).

Capacidades:
1. **Mover dentro del mismo recurso:** snap a 15 min, clamp dentro de 07-20, persiste directo sin confirmación.
2. **Reasignar a otro recurso:** abre `ConfirmModal` con nombre del recurso destino y horario. Cancelar = no llama backend.
3. **Crear ocupación desde OT pendiente:** drag de OT del `PendingOTsPanel` (lista `GET /ot?estado=Pendiente` filtrada client-side por `id_agente IS NULL && id_equipo IS NULL`) a una fila → modal "Planificar OT" → confirma → `POST /ocupaciones` tipo='ot' con `hora_inicio=09:00`, duración 60min. El usuario ajusta después si quiere.

Pruebas validadas: 9 PASS / 0 FAIL en agente Chrome (T1-T11, ver `reporte_pruebas_3B_2026-05-11.md` si existe). Smoke `smoke_agenda.ps1` 15/15 OK pre y post-cambios.

#### Sub-fase 3.B — Pendientes restantes
- [x] ~~**Drag con teclado:**~~ cerrado — `KeyboardSensor` activo en `TimelineView.tsx` (`keyboardCoordinateGetter` con flechas en pasos de `SNAP_MIN`/`ROW_HEIGHT`).
- [x] ~~**Drag de OT a hora exacta del drop:**~~ cerrado — `TimelineView.tsx::handleDragEnd` rama `pending-ot` usa `activatorEvent.clientX + delta.x` mapeado al rect de la fila (`data-row-tipo/id`) y snap a `SNAP_MIN`. Cae a 09:00 solo si el drop queda fuera del rect.
- [x] ~~**Snap visual durante drag:**~~ cerrado — `GanttResourceRow.tsx` usa `useDndMonitor` (`onDragMove`) para computar la posición de snap y renderiza una línea vertical naranja (`zIndex 25`, box-shadow) mientras la fila es el droppable activo.
- [x] ~~**Bloquear drag de ocupaciones tipo=evento:**~~ cerrado — `GanttOccupationBlock.tsx` setea `dragDisabled = ocupacion.tipo === 'evento'` y pasa `disabled` a `useDraggable`; el `title` del bloque indica "editar desde el modal del evento".
- [x] ~~Imagen QR renderizada~~ cerrado — `QRDisplay.tsx` renderiza el código sobre `<canvas>` con lib `qrcode` (errorCorrectionLevel 'M', ~26KB gzipped). Usado en `ReservaModal.tsx` (backoffice, sección expandible por reserva) y `MiReservaPage.tsx` (autoservicio eventos). Turnos no requiere QR: acreditación es manual desde backoffice.
- [x] ~~Selectores con autocompletar para OT y evento en `OcupacionModal`.~~ cerrado — `OcupacionModal` usa `EventoSearch` (consume `GET /agenda/catalogos/evento-busqueda?q=`). `OcupacionOTModal` usa `OTSearch` (consume `GET /agenda/catalogos/ot-busqueda?q=`). `RecursoPicker` reescrito de `<select>` a input + dropdown debounced (250ms) sobre `GET /agenda/catalogos/recursos?q=`. Mismo patrón que `CiudadanoSearch` con `skipNextRef` post-pick. Restringido a `tipo: 'agente'|'equipo'` (los espacios se eligen con su propio listado).
- [x] ~~Selector de agente/equipo por nombre en `EventoEncargadosModal`.~~ cerrado — usa el mismo `RecursoPicker` con autocompletar.
- [x] ~~Filtro por subárea en `AgendaFilters` (backend ya lo acepta).~~ cerrado — `AgendaFilters` ya tenía el select. `MonthlyView` no lo renderizaba ni lo pasaba al hook; ahora monta el mismo select en su header y `useCalendarioMes` acepta `idSubarea`. Backend `GET /agenda/mes` extendido con `id_subarea` filtrando eventos (`eventos.id_subarea`), ocupaciones (EXISTS subquery sobre `agentes`/`equipos`/`espacios_agenda.id_subarea` según `o.tipo_recurso`) y ausencias (`agentes.id_subarea`). Verificado visualmente: cambiar el select dispara request con `&id_subarea=N` y resultados cambian.
- [x] ~~Vista autoservicio público (cuando `evento.admite_autoservicio=TRUE`).~~ cerrado — flujo end-to-end ya implementado: backend `agenda_publico.py` (GET evento + POST reservar + GET/DELETE reserva por token, sin JWT), página pública `web-app/src/autoservicio/AutoservicioPage.tsx` (form de reserva en `/autoservicio/:tokenPublico`), `MiReservaPage.tsx` (consulta + QR + cancelar). En backoffice: `EventoModal` y módulo Entradas muestran el link copiable cuando `admite_autoservicio=TRUE && token_publico`. No hay landing índice de eventos sin token a propósito — el patrón es que el municipio comparte el link via whatsapp/cartel/redes.
- [x] ~~Migrar/dropear `frontend/agenda.html` vanilla legacy~~ — cerrado 2026-05-12.

#### Aplicar en prod
- [x] ~~Replicar migraciones 30-34 + `seed_agenda.py` en Supabase prod~~ — cerrado 2026-05-12. Las tablas habían entrado en prod durante el E2E del autoservicio sin documentar. Esta sesión completó la parte 2 de mig 30 (ALTER tipo_reclamo) + creó y aplicó mig 37 (defaults + NOT NULL) en local y prod. Ver §21 sección "Migraciones 30-37".

### Sub-fase B1 — Espacios + Disponibilidad multi-rango (BACKEND ✅ ENTREGADO 2026-05-13)

Habilita 3 tipos de recurso (`agente`, `equipo`, `espacio`) en la grilla de agenda, horarios laborales multi-rango (turnos rotativos), distinción atendido/desatendido para espacios, y eventos como bloques en la grilla. **Frontend pendiente** (sub-fase B2).

**DB (migs 40-43):** ver §21.

**Servicio `services/agenda.py::disponibilidad_efectiva(db, tipo_recurso, id_recurso, fecha)`**: resuelve los rangos horarios efectivos para una fecha aplicando bitmask `dias_semana` + ventana `vigente_desde/hasta`. Para `tipo_recurso='espacio'`:
- **Espacio desatendido**: devuelve directo el horario propio del espacio.
- **Espacio atendido**: intersecta el horario propio del espacio con la **unión** de horarios de los agentes vinculados activos (tabla `espacio_agentes`). Si el espacio no tiene horario propio, devuelve la unión sola. Si no tiene agentes vinculados, lista vacía.

Función auxiliar `_merge_rangos()` une rangos solapados o contiguos para evitar duplicados (preserva la `etiqueta` del primer rango). Etiqueta de los rangos unidos se descarta. Quirk: cast explícito `(:f)::date` en SQL — asyncpg pasa parámetros DATE como `unknown` y Postgres no puede resolver el overload de `EXTRACT(ISODOW FROM ...)` sin el cast (cazado en smoke del 2026-05-13).

**Routers nuevos:**

| Router | Prefix | Endpoints |
|---|---|---|
| `agenda_espacios.py` | `/api/v1/agenda/espacios` | GET `` (listado, filtros `atendido`/`q`), POST, GET `/{id}` (con `agentes_vinculados`), PUT `/{id}`, DELETE `/{id}` (soft + cascade soft N:M), GET `/{id}/agentes`, POST `/{id}/agentes`, DELETE `/{id}/agentes/{id_espacio_agente}` |
| `agenda_disponibilidad.py` | `/api/v1/agenda/disponibilidad` | GET `` (filtros tipo_recurso/id_recurso), POST, PUT `/{id}`, DELETE `/{id}` (soft), GET `/efectiva?tipo_recurso=&id_recurso=&fecha=` |

Permisos: `nivel_acceso <= 2` (admin/supervisor) puede mutar; cualquier autenticado lee. POST valida existencia del recurso (`agentes/equipos/espacios_agenda WHERE activo=TRUE`).

**Modificaciones a `agenda_v2.py`:**

| Endpoint | Cambio |
|---|---|
| `GET /agenda/calendario` | Acepta `tipo_recurso='espacio'` y `tipo_recurso='todos'` (default) ahora incluye espacios. Nuevo query param `atendido` (solo aplica si tipo=`espacio` o `todos`). Response agrega `recursos[].atendido`, `recursos[].disponibilidad: [{hora_inicio,hora_fin,etiqueta}]`, y top-level `eventos: [{id_evento,nombre,...,capacidad_ciudadanos,reservas_activas,cupo_libre,id_espacio,encargados:[[tipo,id]]}]`. |
| `GET /agenda/mes` | Acepta `tipo_recurso` opcional. Cuando != `todos` el conteo de ocupaciones se filtra por `ocupaciones.tipo_recurso`. |
| `GET /agenda/semana` (**nuevo**) | `desde=YYYY-MM-DD&dias=N` (1-14, default 7). Mismos filtros que `/calendario`. Response: `{desde, hasta, id_municipio, recursos:[...sin ocupaciones], dias:[{fecha, ocupaciones, ausencias, eventos, disponibilidad_por_recurso}]}`. |

**Schemas Pydantic nuevos en `schemas/agenda_v2.py`:**
- `DisponibilidadRangoEfectivo` — `{hora_inicio: time, hora_fin: time, etiqueta?: str}`. Es lo que devuelve `disponibilidad_efectiva()`.
- `EventoEnCalendarioOut` — vista liviana del evento con `cupo_libre`, `id_espacio`, `encargados: list[tuple[str,int]]` (para pintar bloque en la fila adecuada).
- `CalendarioSemanaOut` + `CalendarioSemanaDiaOut`.
- `EspacioAgendaCreate/Update/Out`, `EspacioAgenteCreate/Out`, `DisponibilidadRecursoCreate/Update/Out`.
- `CalendarioRecurso` agrega `atendido: bool | None` y `disponibilidad: list[DisponibilidadRangoEfectivo]`.
- `RecursoOut.tipo_recurso`, `EventoEncargadoCreate.tipo_recurso`, `OcupacionCreate.tipo_recurso`, `OcupacionUpdate.tipo_recurso` aceptan ahora `'espacio'`.

**Compat retro garantizado:**
- Endpoints existentes (`/calendario`, `/mes`, `/ocupaciones`, `/eventos/{id}/encargados`) siguen aceptando los valores anteriores (`agente|equipo|todos`); solo agregan `espacio`.
- Campos nuevos en responses (`atendido`, `disponibilidad`, `eventos` en /calendario) son listas con default `[]` — clientes viejos pueden ignorarlos.
- Validador del CHECK constraint enforce: insertar `tipo_recurso='espacio'` en `ocupaciones`/`evento_encargados` ya funciona.

**Verbos HTTP nuevos del módulo (sub-fase B1):**

| Acción | Verbo | Path |
|---|---|---|
| Listar espacios | GET | `/api/v1/agenda/espacios` |
| Crear espacio | POST | `/api/v1/agenda/espacios` |
| Detalle espacio (con agentes vinculados) | GET | `/api/v1/agenda/espacios/{id}` |
| Editar espacio | PUT | `/api/v1/agenda/espacios/{id}` |
| Borrar espacio (soft + N:M cascade) | DELETE | `/api/v1/agenda/espacios/{id}` |
| Listar agentes de un espacio | GET | `/api/v1/agenda/espacios/{id}/agentes` |
| Vincular agente | POST | `/api/v1/agenda/espacios/{id}/agentes` |
| Desvincular agente | DELETE | `/api/v1/agenda/espacios/{id}/agentes/{id_ea}` |
| Listar disponibilidad | GET | `/api/v1/agenda/disponibilidad` |
| Crear disponibilidad | POST | `/api/v1/agenda/disponibilidad` |
| Editar | PUT | `/api/v1/agenda/disponibilidad/{id}` |
| Borrar (soft) | DELETE | `/api/v1/agenda/disponibilidad/{id}` |
| Consultar efectiva (resolver bitmask + vigencia + intersección espacio atendido) | GET | `/api/v1/agenda/disponibilidad/efectiva?tipo_recurso=&id_recurso=&fecha=` |
| Vista semanal | GET | `/api/v1/agenda/semana?desde=&dias=&tipo_recurso=&atendido=` |
| Conteos de recursos por tipo (pills B2) | GET | `/api/v1/agenda/recursos/conteos?id_municipio=` |

#### Quirks operativos B1 (cazados en sesión 2026-05-13)

- ~~**`GET /agenda/semana` con `tipo_recurso='todos'` es O(recursos × días)**~~ **Optimizado 2026-05-14** (commits `37d5034` + `8d047f5`). `/semana 7d` con 84 agentes pasó de timeout a 2.6s; `/semana 14d` a 3.3s. Ya **es seguro llamar `/semana` con `tipo_recurso='todos'`** sin penalty. Ver sección "Performance" más abajo en B2.
- **Espacio `atendido=TRUE` SIN agentes vinculados → disponibilidad efectiva `[]`**. La mig 40 deliberadamente NO enforce "atendido => al menos 1 agente" para no bloquear el alta inicial; queda como validación de capa frontend o checklist UX. Síntoma: el espacio aparece en `/calendario` pero su grilla queda toda gris ("fuera de horario") sin razón obvia. Recomendado en B2: badge "⚠ falta vincular agentes" en el espacio del listado cuando `atendido && agentes_vinculados.length === 0`.
- **`EXTRACT(field FROM :param)` con asyncpg requiere cast inline** — usar `(:f)::date` (memoria [[feedback_asyncpg_extract_cast_date]]). Aplicar a cualquier query que extienda `disponibilidad_efectiva` o consulte fechas/horas con parámetros bindeados.
- **Smoke local ≠ prod en este módulo**: prod arrancó la sesión con 1 espacio + 2 disponibilidades + 1 evento residuales del E2E de autoservicio del 2026-05-12. Inocuos pero alteran conteos del smoke. Si vas a contar items en prod, considerar `WHERE fecha_alta > '2026-05-13'` para excluir los demos viejos.

### Sub-fase B2 — Frontend (✅ CERRADA al 2026-05-14, commit `7186fe1`)

> **Verificación visual completa en navegador hecha 2026-05-14.** Levanté `pnpm dev` + uvicorn local, seedeé 2 espacios (atendido+desatendido) + 3 disponibilidades vía API, y caminé Día/Semana/Mes + Config (Espacios + Disponibilidad). Bloque de evento se renderiza con bg violeta `rgba(106,27,154,.2)` en la fila del encargado, los filtros de pills filtran la grilla correctamente, la disponibilidad efectiva intersecta espacio atendido con agentes vinculados.

**Estructura del módulo Agenda al cierre B2:**

- **4 tabs principales** en `AgendaLayout`: **Vistas / Eventos / Conflictos / Config**.
- Dentro de **Vistas** (default), **sub-toggle Día / Semana / Mes** (botones), persistido en `agendaStore.vistaGrilla` (no en la URL).
- Compat retro: URLs viejas `/agenda/timeline`, `/agenda/mensual` redirigen a `Vistas`.
- **Pills de tipo de recurso** (4 opciones con conteo): Agentes / Equipos · OT / Esp. atendidos · Turnos / Esp. eventos · Entradas. Persistido en `agendaStore.filtroRecurso: FiltroRecursoUI`. NO existe opción "Todos" (consistente con el quirk de performance B1). **Las pills NO son intercambiables — cada vista sirve a un módulo distinto** (Pendiente Grande 2, cerrado 2026-05-14): Equipos→asignación de OT, Esp. atendidos→Turnos, Esp. eventos→Entradas. `RecursoTogglePills` muestra un subtítulo dinámico explicando el propósito de la pill activa.
- Helper `web-app/src/lib/diasSemana.ts`: `serialize/deserialize/togglearDia/format` para el bitmask `dias_semana`. `format(31)` → `'Lun a Vie'`, `format(96)` → `'Sab y Dom'`, `format(127)` → `'Todos los dias'`.
- Helper `agendaStore.filtroUIaBackend(filtro)` → `{ tipo_recurso, atendido, scopeSubareaPropia }` para pasar al backend (`espacios_atendidos` → `tipo_recurso='espacio', atendido=true`; `equipos` → `scopeSubareaPropia=true`).
- **Scope por subárea del supervisor (vista Equipos):** `/calendario` y `/semana` aceptan `scope_subarea_propia: bool`. Cuando es `true`, el backend resuelve la subárea del usuario logueado vía `usuarios.id_usuario → agentes.id_usuario → agentes.id_subarea` (helper `services/agenda.py::subarea_del_usuario`) y filtra los recursos a esa subárea. **Admin (nivel 1) NO se scopea** — ve todo. **Fail-open:** si no se puede resolver la subárea (usuario sin agente, o agente sin `id_subarea` — drift común en prod, hoy 0 agentes tienen subárea seedeada), no se aplica el filtro. La pill "Equipos · OT" manda `scope_subarea_propia=true` automáticamente; las otras pills no. El helper `_resolver_scope_subarea` en `agenda_v2.py` centraliza la lógica: `id_subarea` explícito > scope propio > None.

**Componentes nuevos:**

| Archivo | Rol |
|---|---|
| `views/VistasView.tsx` | Contenedor de Vistas — VistaToggle + RecursoTogglePills + render switcheable |
| `views/WeeklyView.tsx` | Vista Semana (Gantt 7 días, sin DnD) consume `/agenda/semana` |
| `views/MonthlyView.tsx` | Refactor: usa fecha del store + tipo_recurso del filtro |
| `views/ConfigView.tsx` | Pantalla Config con sub-tabs Espacios + Disponibilidad |
| `components/RecursoTogglePills.tsx` | 4 pills con conteo (consume `/recursos/conteos`) |
| `components/VistaToggle.tsx` | Sub-toggle Día/Semana/Mes |
| `components/config/EspaciosConfig.tsx` | Tabla CRUD de espacios |
| `components/config/EspacioFormModal.tsx` | Crear/editar espacio |
| `components/config/EspacioAgentesModal.tsx` | Listar/vincular/desvincular agentes a espacio |
| `components/config/DisponibilidadConfig.tsx` | Tabla CRUD de disponibilidad |
| `components/config/DisponibilidadFormModal.tsx` | Crear/editar disponibilidad (checkboxes días + horario + vigencia) |
| `hooks/useEspacios.ts` | Query + mutaciones espacios |
| `hooks/useDisponibilidad.ts` | Query + mutaciones disponibilidad + efectiva |

**Cambios visuales en la grilla (Vista Día):**

- Fondo base de cada fila: gris diagonal "fuera de horario".
- Encima, **rectángulos blancos** por cada rango de `disponibilidad` efectiva de la fecha = horario habilitado.
- Eventos del response `/calendario.eventos[]` se pintan como bloques violeta (`rgba(106,27,154,.20)` con borde `#6a1b9a`) en la fila del/los encargado(s) o del espacio. Badge `(reservas_activas/capacidad)`; cuando `cupo_libre <= 0` el nombre se tacha y se muestra "agotado" en rojo.
- Filtro `'espacios_atendidos'` / `'espacios_desatendidos'`: la columna izq muestra subtítulo `espacio · atendido` o `espacio · desatendido` + ícono violeta.

**Quirks ya documentados que ataca B2:**

- Conteos: una sola request al endpoint nuevo `/recursos/conteos` con `staleTime: 60_000` en lugar de 4 GETs paralelos.
- Espacio atendido sin agentes: la pill muestra el conteo, pero la grilla pinta toda la fila gris. Pendiente UX: badge "⚠ falta vincular agentes" cuando `atendido && agentes_vinculados.length === 0` (no implementado en este sprint).
- `disponibilidad_por_recurso` en `/semana` usa clave `"{tipo}:{id}"` con dos puntos (ver [[reference_agenda_semana_disponibilidad_key]]).

**Restricción explícita en `EventoEncargadosModal`:** el modal usa `type EncargadoTipoRecurso = 'agente' | 'equipo'` local (no `TipoRecurso` global), porque un espacio NO puede ser encargado de un evento — los espacios se linkean via `eventos.id_espacio`. Si en el futuro se quiere permitir "espacio como encargado", revisar este alias específicamente.

**DnD:** solo en Vista Día (igual que sub-fase 3.B). Vista Semana NO tiene DnD por simplicidad.

**Hallazgos de la verificación visual 2026-05-14 (fixeados en el commit):**
- **Drift `id_municipio NULL`** entre `/recursos/conteos` y `/calendario`/`/semana`: el conteo usaba `WHERE id_municipio = :im` mientras los listados de grilla usan `IS NULL OR =`. En prod hay agentes/equipos legacy con `id_municipio` NULL (3 agentes, 3 equipos) y el pill decía "Agentes 1" pero la grilla mostraba 4. **Fix aplicado en `7186fe1`**: ahora ambas reglas son consistentes (`IS NULL OR = :im`). Si agregás un endpoint nuevo que filtre por municipio sobre agentes/equipos, usar la misma regla NULL-friendly.

**Pendientes post-B2:** todos cerrados al 2026-05-14 jornada 5 (commit `9bce2eb` salvo el primero).
- ~~3 ítems `data-modulo="turnos"` duplicados en sidebar vanilla~~ — cerrado 2026-05-14 (mig 44). Los 3 ítems ahora tienen `data-modulo` propios (`turnos`/`entradas`/`agenda`) y apuntan a `#/turnos`, `#/entradas`, `#/agenda`.
- ~~Eventos sin `id_espacio` ni encargados invisibles en grilla Día~~ — cerrado. `GanttGrid.tsx` arma `eventosSinAsignar` (sin encargados Y sin espacio) y los pinta en una fila sintética "Eventos sin asignar" (solo bloques violeta, sin droppable ni disponibilidad).
- ~~Badge "⚠ falta vincular agentes" en EspaciosConfig~~ — cerrado. El backend (`agenda_espacios.py`) expone `cant_agentes` sin n+1; `EspaciosConfig.tsx` muestra el badge cuando `atendido && cant_agentes === 0`.
- ~~Drag en vista Semana~~ — cerrado. `WeeklyView.tsx` tiene `DndContext` + `useDraggable`/`useDroppable` + `ConfirmModal` para mover ocupaciones entre días/recursos conservando horario.
- ~~KeyboardSensor en DnD~~ — cerrado (ver sub-fase 3.B arriba).
- ~~Título "timeline" residual en vista Día~~ — cerrado en `9bce2eb`.

### Performance — optimización 2026-05-14 (commits `37d5034` + `8d047f5`)

Con 84 agentes en prod, los endpoints B1 originales eran inusables:

| Endpoint | Original | Final | Mejora |
|---|---|---|---|
| `/agenda/calendario` agente 1d | 23.1s | 2.2s | ~10× |
| `/agenda/semana` agente 7d | timeout >60s | 2.6s | >23× |
| `/agenda/semana` todos 14d | (peor) | 3.3s | flat |

**Cómo bajar de O(recursos × días) round-trips a O(1)** — patrón aplicado:

1. **`services/agenda.py::disponibilidad_efectiva_batch(session, recursos, fechas)`** — 2 queries totales (`disponibilidad_recurso` con `WHERE tipo = ANY AND id = ANY`, descartando pares espureos en Python; + `espacio_agentes` para los atendidos del input). Bitmask + vigencia + intersección espacio↔agentes se resuelven en Python sobre las filas ya cargadas. La función singular `disponibilidad_efectiva` sigue intacta para `/disponibilidad/efectiva` (compat retro).

2. **`agenda_v2.py::_eventos_del_rango(db, fd, fh, mun)`** — 1 query base (`eventos BETWEEN :fd AND :fh`) + 1 bulk de encargados (`evento_encargados WHERE id_evento = ANY(:ids)`). `_eventos_del_dia(db, f, m)` queda como wrapper compat retro que delega al rango con `fd=fh=f`.

3. **`/calendario` y `/semana`** ahora ambos llaman a los batch directos. **Compat retro 100%** verificado con smoke regression byte-a-byte entre singular y batch (agente con horario, espacio atendido con intersección, espacio desatendido, espacio fuera de días, evento con encargado).

**Latencia base Railway↔Supabase es ~2-3s** para queries con JOINs sobre 84 filas. Por debajo de eso es físicamente imposible sin tocar arquitectura (mover backend a la misma region, PgBouncer, caché Redis). Ver memoria [[reference_agenda_latencia_base_railway_supabase]] para más detalles.

**Patrón generalizable** para próximos endpoints con loops N×M: ver memoria [[feedback_patron_batch_helper_singular_wrapper]]. Aplica a cualquier nuevo endpoint que itere sobre recursos × fechas/items.

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

**Shell vanilla (`frontend/js/menu.js`):** al cargar el shell, llamar `/auth/me`, leer `modulos_permitidos`, ocultar items del sidebar cuyos `data-modulo` no estén en la lista.

```html
<!-- Sidebar plano (estilo nav-flat, post 2026-05-12 jornada 4) -->
<a class="nav-flat__item" href="web-app/dist/index.html#/reclamos" data-modulo="reclamos">
  <svg ...></svg><span>reclamos</span>
</a>

<!-- Item que cubre MULTIPLES moduloCodigos (data-modulo-fallback CSV) -->
<a class="nav-flat__item"
   href="web-app/dist/index.html#/ot/supervisor"
   data-modulo="ot_supervisor"
   data-modulo-fallback="ot_agente,ot_auditoria">
  <svg ...></svg><span>OT</span>
</a>
```

```js
// menu.js: si CUALQUIERA de los codigos (principal + fallback) esta permitido,
// el item se muestra. Util cuando un modulo cubre varios sub-permisos (OT con
// 3 mesas) o cuando supervisor/agente/auditoria viven en el mismo bundle.
const permitidos = new Set((session.user.modulos_permitidos ?? []))
document.querySelectorAll('.nav-flat__item[data-modulo], .nav__link[data-modulo]').forEach(a => {
  const principal = a.dataset.modulo
  const fallback = (a.dataset.moduloFallback || '').split(',').map(s => s.trim()).filter(Boolean)
  const algunoPermitido = [principal, ...fallback].some(m => permitidos.has(m))
  if (!algunoPermitido) a.hidden = true
})
```

**Sin `data-modulo-fallback` declarado, OT desaparece** del sidebar para usuarios con `ot_agente` pero sin `ot_supervisor` — caso real cazado en sesión 2026-05-12 jornada 4. Cuando un manifest React cubre múltiples permisos backend, exponer todos los códigos en el HTML del shell.

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

**Migración 38 (`backend/migrations/38_permisos_por_modulo.sql`) aplicada en local y prod.** Tablas `modulos` + `usuario_modulos` siguiendo §10. **Migración 44 (2026-05-14) separó el código `turnos` en tres** (`agenda` / `turnos` / `entradas`). Catálogo actual — 10 módulos:

| Código | Nombre | min_nivel_acceso | Cubre |
|---|---|---|---|
| `reclamos` | Reclamos | 4 | módulo React `reclamos` |
| `padrones` | Padrones | 4 | módulos React `ciudadanos` + `empresas` |
| `ot_agente` | OT - Agente | 3 | módulo React `ot` (vista Agente) |
| `agenda` | Agenda | 3 | módulo React `agenda` — sustrato de disponibilidad horaria de agentes/espacios |
| `turnos` | Turnos | 3 | módulo React `turnos` — backoffice de turnos de atención (tabla `turnos`, mig 45) |
| `entradas` | Entradas | 3 | módulo React `entradas` — backoffice de eventos con cupo en espacios físicos |
| `ot_supervisor` | OT - Supervisor | 2 | módulo React `ot` (vista Supervisor) |
| `ot_auditoria` | OT - Auditoría | 2 | módulo React `ot` (vista Auditoría) |
| `usuarios` | Usuarios | 1 | `frontend/usuarios.html` (pantalla propia — admin_tablas no hashea password) |
| `admin_tablas` | Maestros | 1 | resto de `frontend/admin_tablas.html?tabla=*` |

> **Migración 44** (`44_permisos_separar_agenda_turnos_entradas.sql`, aplicada local + prod 2026-05-14): la fila `turnos` ("Turnos y eventos") se reconvirtió en `agenda` ("Agenda") vía `UPDATE` de la PK — seguro porque no había overrides en `usuario_modulos`. Se insertaron `turnos` y `entradas`. Los scaffolds React `web-app/src/modules/turnos/` y `entradas/` son landings mínimas; la lógica (backoffice + autoservicio) es sub-fase futura.

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
- `ModuleManifest` extendido con `moduloCodigo?: string`. Lo usan `agendaModule` (`agenda`), `turnosModule` (`turnos`), `entradasModule` (`entradas`), `contactosModule` (`padrones`); `dashboardModule` queda sin filtro (es stub demo, no se filtra).
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
| `frontend/js/config.js` + `validaciones.js` | 0 | 0 | ✅ |
| `frontend/admin_tablas.html` | 0 (desde `951232a`) | 5 (solo `z-header*` oculto en iframe) | ✅ tokens DS directos. Clases internas (`.btn-primary`, `.field`, `.modal`) se conservan a propósito — ver §15. |
| `frontend/login.html`, `welcome.html` | 0 | 0 | ✅ |

> **Nota 2026-05-12:** los HTMLs `ciudadano.html`, `empresa.html`, `reclamos.html` (y sus JS) fueron eliminados al migrar a React (commits `a61ec9d`, `6aa3fdc`, `3e4a532`-`deae0bc`). Las equivalencias de tokens/clases listadas más abajo siguen siendo útiles si en algún momento se reintroduce un módulo vanilla nuevo.
>
> **Nota 2026-05-13:** los HTMLs `ot_supervisor.html`, `ot_agente.html`, `ot_auditoria.html` también fueron eliminados — el módulo OT vive 100% en React (`web-app/src/modules/ot/`) desde antes; la entrada en esta tabla quedó como residuo histórico. Los códigos de permiso `ot_supervisor`/`ot_agente`/`ot_auditoria` siguen activos a nivel sidebar vanilla, pero el destino del link es el bundle React, no un HTML.

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

### Deuda futura — cerrada

`admin_tablas.html` fue migrado a tokens DS directos en commit `951232a` (2026-05-13): 0 `var(--z-*)` remanentes. Las clases internas (`.btn-primary`, `.field`, `.modal`) se conservan a propósito (renombrarlas a `*-zaris` colisionaría con el DS sin ganancia funcional). No queda deuda de estilos legacy en el repo.

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

### Quirk 11: `Start-Process pnpm/npm/npx/yarn` falla — son `.cmd`, no `.exe`

Tirar `Start-Process -FilePath "pnpm" -ArgumentList "dev"` desde PowerShell devuelve `"%1 no es una aplicación Win32 válida"`. En Windows, `pnpm`/`npm`/`npx`/`yarn`/`tsc` (y cualquier CLI instalado por Node) son shims `.cmd`, no binarios PE. `Start-Process` quiere un ejecutable.

**Receta verificada (sesión 2026-05-12):**

```powershell
Start-Process -FilePath "cmd.exe" `
  -ArgumentList "/c","pnpm dev > _dev.log 2> _dev.err.log" `
  -WorkingDirectory "c:\Users\Cesar\Documents\ZARIS\Desarrollo\ZGE\web-app" `
  -WindowStyle Hidden
```

Es decir: `cmd.exe /c "<comando>"` como wrapper. La redirección dentro del string queda manejada por cmd, no por PowerShell — útil para no perder stdout/stderr.

Esta es la contraparte node-de [[Quirk 9: `python -m http.server`]]. Para Python alcanzaba con `Start-Process python ...` porque `python.exe` sí es un ejecutable. Para herramientas Node hay que pasar por cmd.

**Alternativa:** ejecutar el binario directo desde `node_modules/.bin/` (que sí es un script Node con shebang, pero PowerShell lo ejecuta vía `node`). Ej: `Start-Process node -ArgumentList "$cwd/node_modules/.bin/vite","build"`. Menos legible.

Para foreground (no detached) PowerShell ejecuta `pnpm dev` sin Start-Process y funciona perfecto — el problema es solo con `Start-Process`.

### Quirk 12: bundle React standalone en prod debe redirigir al shell vanilla

`web-app/dist/index.html` se sirve en GH Pages bajo `/zaris-zge/web-app/dist/`. Si un usuario abre esa URL directo (compartiendo link, marcador viejo, o "abrir en nueva pestaña"), ve el `AppShell` React **standalone con su propio sidebar** — viola la regla §14 (un solo shell en producción) y desconcierta porque la nav es distinta a la del shell vanilla.

**Fix**: script inline en `<head>` de `web-app/index.html` (NO en main.tsx — necesita correr ANTES de que React monte y pueda redirigir sin destellar el AppShell):

```html
<script>
  (function () {
    try {
      if (window.self !== window.top) return;                   // OK: embebido en iframe
      var p = window.location.pathname || '';
      if (p.indexOf('/zaris-zge/web-app/dist/') === -1) return; // dev local: dejar pasar
      var hash = window.location.hash || '';
      var target = '/zaris-zge/index.html';
      if (hash && hash.length > 1) {
        target += '?modulo=' + encodeURIComponent('web-app/dist/index.html' + hash);
      }
      window.location.replace(target);
    } catch (e) { /* fail-open */ }
  })();
</script>
```

**Complemento obligatorio** en `frontend/js/menu.js`: la whitelist de `?modulo=` debe aceptar paths del bundle React además de los HTMLs vanilla, sino el shell descarta el redirect silenciosamente:

```js
const isVanilla = /^frontend\/[a-z0-9_-]+\.html(\?.*)?$/i.test(mod || '')
const isReact   = /^web-app\/dist\/index\.html(#\/.*)?$/i.test(mod || '')
if (mod && (isVanilla || isReact)) {
  document.getElementById('module-frame').src = mod
}
```

**Por qué necesita ambas piezas**: si solo aplicas el guard sin actualizar la whitelist, el redirect funciona pero el shell descarta el `?modulo=` y queda mostrando welcome. Si solo aplicas la whitelist sin el guard, el bundle sigue accesible standalone.

Cazado en sesión 2026-05-12 jornada 4 — el usuario reportó "veo un shell con sidebar dashboard/agenda/ciudadanos que no es el shell normal". Verificar en prod abriendo `https://cesarzeta.github.io/zaris-zge/web-app/dist/index.html#/reclamos` en pestaña nueva: debe redirigir a `index.html?modulo=...` automáticamente.

### Quirk 13: redirects absolutos del bundle React rompen bajo subpath `/zaris-zge/`

En prod el shell vive en `cesarzeta.github.io/zaris-zge/index.html` y el bundle React vive en `cesarzeta.github.io/zaris-zge/web-app/dist/index.html`. Cualquier `window.location.href = '/foo'` desde dentro del bundle (o desde JS del shell) salta a `cesarzeta.github.io/foo` **sin** el prefijo `/zaris-zge/`. En GH Pages eso devuelve el 404 genérico ("There isn't a GitHub Pages site here.") porque no existe un proyecto `cesarzeta.github.io/foo`.

Casos en los que vas a tropezar:
- Handler 401 en `web-app/src/lib/api.ts` redirigiendo a `/login`.
- Botones "Cerrar sesión" haciendo `window.location.href = '/login.html'`.
- Cualquier `<a href="/...">` que el bundle tenga hardcoded.

**Patrón correcto** desde el bundle React (que vive en iframe en prod):
```ts
// Detectar el subpath del shell padre y redirigir el parent, no el iframe.
if (typeof window !== 'undefined' && window.self !== window.top) {
  const subpath = window.parent.location.pathname.match(/^\/[^/]+\//)?.[0] ?? '/'
  ;(window.parent as Window).location.href = subpath + 'frontend/login.html'
} else {
  // standalone (localhost:5173 dev)
  window.location.href = '/login'
}
```

**Síntoma visual del bug**: el shell vanilla carga OK (topbar + sidebar normales), pero **dentro del iframe** aparece el 404 de GitHub Pages con logo de GitHub y "There isn't a GitHub Pages site here.". Aplica a cualquier asset/ruta que el bundle pida con path absoluto desde la raíz.

Cazado 2026-05-13 cuando dashboard pasó a ser home: el handler 401 hacía `window.location.href = '/login'`. Antes con welcome.html como home no se notaba porque welcome.html no hace requests al backend, así que nunca se gatillaba el 401 → redirect mal.

### Quirk 14: `web-app/dist/` y commits — qué compila Vite y en qué orden commitear

`vite build` compila **todo lo que esté en el working tree en ese momento**, no lo que está staged. Dos consecuencias operativas al commitear:

1. **No rebuildees `dist/` para commit con trabajo ajeno sin commitear en el working tree.** Si hay cambios a medias de otra tarea (común en este repo), Vite los mete en el bundle y el commit queda con un `dist/` que incluye fuentes que todavía no se commitearon (o que van en otro commit). El HEAD final puede quedar consistente, pero el commit intermedio tiene dist cruzado — malo para `git bisect` / revisar PRs / `git checkout <ese commit>`. Orden correcto: **commitear los fuentes primero, rebuildear el dist con el working tree ya acotado, commitear el dist** (o incluirlo en el mismo commit que sus fuentes). Si no podés acotar el working tree, stasheá lo ajeno antes de rebuildear. Detalle: memoria `feedback_rebuild_dist_working_tree_limpio`.

2. **Antes de commitear `dist/`, rebuildear sin `VITE_API_BASE` en el shell y verificar que apunte a Railway.** Si rebuildeaste en modo dev para verificación local (`vite build --mode development` → apunta a `127.0.0.1:8000`), ese dist NO debe commitearse. `grep -o 'zaris-api-production' web-app/dist/assets/index-*.js` debe dar match antes del commit. Ver Quirk 1.

## 33. Módulos Turnos y Entradas

Dos módulos React que se apoyan en el sustrato de Agenda. Implementados al 2026-05-14 (backoffice completo). Ver §27 para el modelo de agenda subyacente.

### Turnos — turnos de atención sobre agentes

Un turno reserva un bloque de la disponibilidad de un agente para que un ciudadano realice un trámite (tipo de servicio). Estados: `reservado` → `cumplido` | `cancelado`.

**DB (migración 45 `45_turnos.sql`, aplicada local + prod 2026-05-14):**
- `tipo_servicio_turno`: catálogo (estándar §10) con `duracion_min`. Gestionado desde **admin_tablas** (`TABLE_CONFIG["tipo_servicio_turno"]`). 3 seeds: Atención general (30min), Licencia de conducir (45min), Habilitación comercial (60min).
- `turnos`: tabla transaccional (estándar §10). FKs a `ciudadanos`, `agentes`, `tipo_servicio_turno`. `estado` CHECK `reservado|cumplido|cancelado`. `id_ocupacion` → fila espejo en `ocupaciones`.

**Patrón clave — ocupación espejo:** cada turno mantiene una fila en `ocupaciones` (tipo='turno', tipo_recurso='agente') para aparecer en la grilla del módulo Agenda. El backend (`routes/turnos.py`) sincroniza ambas tablas:
- crear turno → INSERT turno + INSERT ocupación espejo
- reprogramar → UPDATE ambas
- cumplir → solo UPDATE turno.estado (la ocupación se mantiene como histórico en la grilla)
- cancelar → UPDATE turno.estado + soft-delete de la ocupación espejo (libera la grilla)

**Endpoints (`/api/v1/turnos`):** GET `/catalogo/tipos-servicio`, GET `` (filtros estado/agente/ciudadano/fecha), GET `/{id}`, POST `` (calcula `hora_fin` con `duracion_min` si se omite; valida solapamiento del agente), PUT `/{id}` (reprograma — solo estado `reservado`), PATCH `/{id}/cumplir`, PATCH `/{id}/cancelar`. Permisos: nivel 1-3 muta, cualquiera lee.

**Frontend:** `web-app/src/modules/turnos/` — vista única con tabla + filtros + chips de conteo + `TurnoFormModal` (alta/reprogramación). Reusa `Modal`, `ConfirmModal`, `CiudadanoSearch` del módulo Agenda (cross-module import OK, comparten el recurso agente).

### Entradas — eventos con cupo en espacios físicos

**No tiene tablas ni migración propias.** Reusa la entidad `eventos` + `evento_reservas` del backend de Agenda. Un "evento con entradas" es simplemente un `evento` con `id_espacio` no nulo.

**Cambios backend en `agenda_v2.py` (compat-retro, campos opcionales):**
- `EventoOut` y `EventoBase`/`EventoUpdate` ahora incluyen `id_espacio`.
- `_evento_to_out` y `listar_eventos` devuelven `id_espacio`; `crear_evento`/`actualizar_evento` lo persisten.
- `GET /agenda/eventos` acepta query param `con_espacio` (True=solo con espacio, False=solo sin, omitir=todos). El módulo Entradas filtra con `con_espacio=true`.

**Frontend:** `web-app/src/modules/entradas/` — grilla de cards de eventos con espacio + `EventoEntradaFormModal` (alta, con selector de espacio vía `useEspacios` de Agenda). La gestión de reservas reusa **directamente el `ReservaModal` de Agenda** (`modules/agenda/modals/ReservaModal.tsx`).

**Autoservicio:** Entradas YA tiene autoservicio funcionando — un evento con `admite_autoservicio=true` tiene `token_publico` y la página pública `/autoservicio/:tokenPublico` (que ya existía para eventos) lo gestiona sin cambios. La card de Entradas muestra el link público.

### Turnos autoservicio — ENTREGADO (2026-05-14)

Flujo público sin JWT para que el ciudadano reserve un turno sin pasar por mesa. A diferencia de eventos (fecha/hora fija), el ciudadano elige un slot libre que el backend calcula cruzando `disponibilidad_recurso` con `ocupaciones`.

**DB (migración 46 `46_turnos_autoservicio.sql`, aplicada local + prod 2026-05-14):** agrega `turnos.token_turno UUID` (no enumerable, único, default `gen_random_uuid()`, backfill de filas viejas — espeja `evento_reservas.token_reserva`) y `turnos.origen VARCHAR(15)` CHECK `backoffice|autoservicio` default `backoffice`. Requiere `pgcrypto` (ya creada en mig 35). Idempotente.

**Router `backend/app/api/routes/turnos_publico.py` (prefix `/api/v1/turnos/publico`, sin auth):**

| Acción | Verbo | Path |
|---|---|---|
| Listar tipos de servicio | GET | `/tipos-servicio` |
| Listar agentes con disponibilidad cargada | GET | `/agentes` |
| Slots libres | GET | `/slots?id_tipo_servicio_turno=&id_agente=&fecha_desde=&dias=` |
| Reservar turno | POST | `/reservar` |
| Consultar turno por token | GET | `/turno/{token_turno}` |
| Cancelar turno por token | DELETE | `/turno/{token_turno}` |

> **Orden de routers crítico (main.py):** `turnos_publico_router` se registra **ANTES** de `turnos_router`. `turnos_router` tiene `/api/v1/turnos/{id_turno}` con `{id_turno}` int; sin el orden explícito `/turnos/publico/*` sería atrapado como `{id_turno}='publico'` → 422. Mismo quirk §5.

**Cálculo de slots (`_slots_libres_agente`):** llama a `services/agenda.py::disponibilidad_efectiva('agente', id, fecha)`, parte cada rango en bloques de `duracion_min` del tipo de servicio (descarta el último si no entra completo), y filtra los que se solapan con cualquier fila activa de `ocupaciones` (tipo_recurso='agente', misma fecha). `id_agente` opcional: si se omite, busca en todos los agentes con disponibilidad cargada.

**POST /reservar:** valida tipo + agente activos, que el slot caiga dentro de la disponibilidad efectiva, que no se solape con ocupaciones, busca/crea ciudadano por DNI (`buscar_o_crear_ciudadano_por_dni`), rechaza si el ciudadano ya tiene turno no-cancelado ese día. Crea turno (`origen='autoservicio'`) + ocupación espejo. Devuelve `token_turno` en la respuesta (sin él el ciudadano no puede volver a su turno).

**Frontend público (`web-app/src/autoservicio/`):**
- `TurnosPage.tsx` — path `/turnos-autoservicio`. Flujo de 4 pasos (tipo → agente → slot → datos) con `StepIndicator`. Al reservar redirige a `/turno/:tokenTurno`.
- `MiTurnoPage.tsx` — path `/turno/:tokenTurno`. Ver/cancelar el turno. Espeja `MiReservaPage` de eventos.
- `api.ts` extendido con `getTiposServicioTurno/getAgentesTurno/getSlotsTurno/postTurnoPublico/getTurnoPublico/deleteTurnoPublico`.
- El backoffice de Turnos (`modules/turnos/pages/Overview.tsx`) muestra un banner "Autoservicio para ciudadanos" con el link fijo `#/turnos-autoservicio` + botón copiar. A diferencia de Entradas (token por evento), el link de Turnos es fijo — el ciudadano arranca eligiendo el trámite.

## 34. Módulo OT — frontend dedicado del Supervisor (crear OT + agendar en una pasada)

Implementado 2026-05-14 jornada 5. El bullet "OT" del menú es el frontend donde el supervisor, desde la bandeja de reclamos de su subárea, crea la OT **y** la planifica en la agenda de agentes/equipos en un solo flujo. Antes eran dos pasos en dos módulos (crear OT en `modules/ot`, agendarla en `modules/agenda`).

### Vista Supervisor — layout 2 columnas (tab "Asignar")

`web-app/src/modules/ot/views/SupervisorView.tsx`: el tab Asignar usa grid `minmax(0,1fr) 340px` — bandeja de reclamos a la izquierda, `PlanificadorOT` a la derecha. Click en una fila (o en el botón "Planificar") selecciona el reclamo en el panel. El flujo de **lote** (checkboxes + `AsignarModal`) se mantiene intacto: agendar 10 OTs distintas en un panel no tiene sentido, el lote sigue siendo asignación simple sin agenda. El tab "Reasignar" no cambió.

### `PlanificadorOT.tsx` — panel de planificación

`web-app/src/modules/ot/components/PlanificadorOT.tsx`: muestra contexto del reclamo → selector agente/equipo → fecha → **slots libres como chips clickeables** → dos acciones:
- **"Crear OT y agendar"** → `POST /ot/con-agenda` (crea OT + ocupación espejo en una transacción).
- **"Crear OT sin agendar"** → `POST /ot` normal. La OT queda sin ocupación; igual registra al supervisor en `id_supervisor_asigna`.

Valida FK antes de enviar (ver memoria `feedback_validar_fk_antes_submit`).

### Backend nuevo en `ordenes_trabajo.py`

| Acción | Verbo | Path | Notas |
|---|---|---|---|
| Slots libres de un recurso | GET | `/api/v1/ot/slots-recurso?tipo_recurso=&id_recurso=&fecha=&duracion_min=` | **Segmento fijo: registrado ANTES de `GET /{id_ot}`** (§5). Agente: disponibilidad efectiva menos sus ocupaciones. Equipo: unión de las disponibilidades de los agentes del equipo (`equipo_agentes`) menos la unión de ocupaciones de todos ellos. Equipo sin agentes con agenda → `[]`. |
| Crear OT + agenda | POST | `/api/v1/ot/con-agenda` | Crea OT y ocupación tipo `'ot'` en una transacción. Body `dict` → convierte fecha/hora con `date.fromisoformat`/`time.fromisoformat` (asyncpg no castea strings, ver memoria `feedback_asyncpg_dict_crudo_fecha`). Detecta conflictos de solapamiento y los devuelve, pero la OT igual se crea. `id_supervisor_asigna` = usuario logueado. |

`GET /ot/mesa/supervisor` ahora expone **`ot_activa_agendada`** (boolean): el CTE `ot_activa` agrega un `EXISTS` sobre `ocupaciones` tipo `'ot'` activas ligadas a la OT. Permite distinguir en la bandeja las OTs creadas sin agendar.

Helpers compartidos en `ordenes_trabajo.py`: `_slots_de_rango`, `_solapa`, `_merge_rangos` (une rangos solapados — usado para la unión de disponibilidades del equipo), `_slots_libres_recurso`. Reutilizan `services/agenda.py::disponibilidad_efectiva`.

### Hooks `useOT.ts`

`useSlotsRecurso(tipo, id, fecha, duracion)` — query de slots, `enabled` solo con recurso+fecha elegidos. `useCrearOTConAgenda()` — mutation que invalida mesas de OT **y** queries de agenda (`['agenda']`), porque la ocupación nueva debe aparecer en la grilla del módulo Agenda.

### Estado de los 3 módulos del menú (confirmado 2026-05-14)

- **OT** → frontend dedicado del supervisor (esta sección). Crea OT relacionada al reclamo + la agenda.
- **Turnos** → ligado a **agentes**, turnos de atención al ciudadano (§33). NO se tocó.
- **Entradas** → ligado a **espacios** + eventos con cupo (§33). NO se tocó.

`OcupacionOTModal` en el módulo Agenda (§ ver jornada anterior) se mantiene: sigue siendo válido planificar en la Agenda una OT ya creada. El flujo nuevo de OT no lo reemplaza, lo complementa.

## 35. Módulo Trámites / Expedientes

Gestión de expedientes administrativos tipo "ventanilla" (entrada de documentación → circuito interno → resolución). Diseñado para flujos multi-área, firmas digitales y numeración correlativa por tipo.

### Filosofía de diseño

- **Separación catálogo / instancia**: el catálogo (`tipo_tramite`, `tipo_tramite_version`, `_campo`, `_estado`, `_transicion`, `_documento_requerido`) define el FSM y los campos de cada tipo de trámite. Las instancias (`tramite`, `tramite_movimiento`, `tramite_documento`, `tramite_firma`) son los expedientes reales.
- **Versionado del circuito**: cada tipo tiene versiones numeradas (`tipo_tramite_version`). Un trámite instanciado queda vinculado a la versión que estaba publicada al momento de crearse — cambiar el circuito no altera trámites en curso.
- **FK circular diferida**: `tipo_tramite.id_version_publicada → tipo_tramite_version` y `tipo_tramite_version.id_tipo_tramite → tipo_tramite` se resuelven con `DEFERRABLE INITIALLY DEFERRED`.
- **Numeración atómica**: `tipo_tramite_numerador` con `INSERT ... ON CONFLICT DO UPDATE SET ultimo_numero + 1 RETURNING` evita race conditions. Formato: `{prefijo}{sep}{codigo_municipio}{sep}{anio}{sep}{correlativo_padded}` → ej. `POD-LPL-2026-0001`.
- **Ledger append-only**: `tramite_movimiento` registra cada acción (creacion, pase, cambio_estado, firma, etc.) como fila nueva. Nunca se modifica.
- **Iniciador polimórfico**: `iniciador_tipo ∈ {ciudadano, empresa, area_interna}` + CHECK que enforce exactamente una de `{id_ciudadano_iniciador, id_empresa_iniciadora, id_subarea_iniciadora}` según el tipo.
- **Destinatario polimórfico**: `destinatario_actual_tipo ∈ {subarea, equipo}` + CHECK similar.

### Tablas

**Catálogo (7 tablas):**

| Tabla | PK | Rol |
|---|---|---|
| `tipo_tramite` | `id_tipo_tramite` | Catálogo maestro con código único, prefijo de numeración, iniciadores permitidos, config de número |
| `tipo_tramite_version` | `id_tipo_tramite_version` | Versión del circuito (v1, v2…). FK circular deferida. `publicada=TRUE` = activa |
| `tipo_tramite_campo` | `id_tipo_tramite_campo` | Campos del formulario de inicio (tipo_dato, orden, opciones_jsonb) |
| `tipo_tramite_estado` | `id_tipo_tramite_estado` | Estados del FSM (codigo, etiqueta, color, es_inicial/es_final) |
| `tipo_tramite_transicion` | `id_tipo_tramite_transicion` | Arco del FSM (origen→destino, quien_puede_jsonb, requiere_comentario/adjunto) |
| `tipo_tramite_documento_requerido` | `id_tipo_tramite_documento_requerido` | Docs que el iniciador/área debe adjuntar (obligatorio, formatos, requiere_firma) |
| `tipo_tramite_numerador` | `(id_tipo_tramite, anio, id_municipio)` | Contador correlativo atómico |

**Instancias (5 tablas):**

| Tabla | PK | Rol |
|---|---|---|
| `tramite` | `id_tramite` | Expediente instanciado. `numero_expediente` único. Polimorfismo iniciador + destinatario |
| `tramite_movimiento` | `id_tramite_movimiento` | Ledger append-only. UNIQUE `(id_tramite, orden_secuencial)` |
| `tramite_documento` | `id_tramite_documento` | Adjunto real (storage_path, sha256, mime_type, size_bytes) |
| `tramite_firma` | `id_tramite_firma` | Firma digital solicitada/aplicada. Polimorfismo: agente / subarea / equipo |
| `tramite_relacion` | `id_tramite_relacion` | Vínculo entre trámites (asociacion_simple, derivacion, sustitución) |

Todas siguen estándar §10: `activo BOOLEAN NOT NULL DEFAULT TRUE`, `id_municipio INT NOT NULL`, `fecha_alta TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `fecha_modificacion TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `id_usuario_alta`, `id_usuario_modificacion`.

### Migraciones

| # | Archivo | Contenido |
|---|---|---|
| 47 | `47_tramites_catalogos.sql` | Agrega `codigo_corto` a `municipios` si falta. Crea las 7 tablas catálogo. FK circular deferida. |
| 48 | `48_tramites_instancias.sql` | Crea las 5 tablas instancia con todos los CHECK constraints. |
| 49 | `49_tramites_indices.sql` | 12 índices (destinatario, estado actual, número, movimientos, firmas pendientes). |

**Aplicadas en local (zaris_dev) y en prod (Supabase) al 2026-05-16.** Las 5 tablas catálogo + 5 instancia + columnas de auditoría (mig 50) están en ambos entornos. Verificable con `to_regclass('public.tramite')` + chequeo de `id_usuario_alta/modificacion` en `information_schema.columns`.

### Seeds

`backend/seed_tramites.py` — idempotente, crea:
- 7 subareas del circuito (Mesa de Entradas, Habilitaciones, Bromatología, Obras Particulares, Legales, RRHH, Espacios Verdes)
- 9 tipos de trámite con versión publicada v1 (campos, estados, transiciones, docs requeridos):
  - `poda-arbol` (POD) — ciudadano/empresa, 5 estados, 5 transiciones
  - `pedido-informe` (INF) — area_interna, 4 estados, 3 transiciones
  - `licencia-ordinaria` (LIC) — ciudadano, 5 estados, 4 transiciones
  - `habilitacion-comercial` (HAB) — empresa, 6 estados, 6 transiciones
  - `cambio-domicilio-comercial` (CDC) — empresa, 4 estados, 3 transiciones
  - `transferencia-habilitacion` (THC) — empresa, 5 estados, 4 transiciones
  - `inspeccion-bromatologica` (BRO) — ciudadano/empresa, 4 estados, 3 transiciones
  - `cartel-publicitario` (CAR) — ciudadano/empresa, 5 estados, 4 transiciones
  - `recurso-administrativo` (REA) — ciudadano/empresa, 5 estados, 4 transiciones
- 20 trámites instanciados en estados variados con movimientos, documentos y 2 relaciones entre trámites

Comando:
```powershell
cd backend
$env:ENV_FILE=".env.local"; python seed_tramites.py
```

### Endpoints (Fase 1 — solo consulta)

`APIRouter(prefix="/api/v1/tramites", tags=["tramites"])`. Router registrado ANTES de `admin_tablas_router` (evita colisión con `/{tabla}` greedy).

| Método | Path | Descripción |
|---|---|---|
| GET | `/tipos` | Listar tipos activos. Filtros: `iniciador`, `q` (ILIKE nombre/codigo). Devuelve `{total, items}`. |
| GET | `/tipos/{id_tipo_tramite}` | Detalle completo: campos, estados, transiciones, docs requeridos. |
| GET | `` (bandeja) | Listar trámites. Filtros: `estado_codigo`, `id_tipo_tramite`, `iniciador_tipo`, `iniciador_id`, `destinatario_tipo` (`subarea`\|`equipo`), `destinatario_id`, `numero`, `q`, `desde`, `hasta`, `solo_activos`, `limit`, `offset`. `X-Total-Count` + `Access-Control-Expose-Headers`. |
| GET | `/{numero_o_id}` | Detalle del trámite (acepta número de expediente `POD-LPL-2026-0001` o id int). Incluye últimos 5 movimientos. |
| GET | `/{numero_o_id}/movimientos` | Historial completo de movimientos con paginación. |
| GET | `/{numero_o_id}/documentos` | Documentos adjuntos del trámite. |

Todos los endpoints requieren JWT (`Depends(get_current_user)`).

### Servicios

`backend/app/services/tramites/numerador.py`:
- `proximo_numero(db, id_tipo_tramite, id_municipio, anio) -> int` — atómico via INSERT ON CONFLICT DO UPDATE RETURNING.
- `formatear_numero(prefijo, separador, incluye_municipio, incluye_anio, codigo_municipio, anio, correlativo, largo_correlativo) -> str`

### JSONB en asyncpg — quirk crítico (Fase 1)

asyncpg no acepta `dict` Python ni el shorthand `::jsonb` en prepared statements vía SQLAlchemy `text()`. Dos patrones verificados:

```python
# Mal — falla en asyncpg:
conn.execute(text("INSERT INTO t (col) VALUES (:v::jsonb)"), {"v": {"key": "val"}})

# Bien — serializar a string + CAST SQL estándar:
conn.execute(
    text("INSERT INTO t (col) VALUES (CAST(:v AS jsonb))"),
    {"v": json.dumps({"key": "val"}) if val is not None else None}
)
```

Aplica a cualquier columna JSONB en `tramites` (campos, transiciones, movimientos). Documentado porque el `::jsonb` funciona en `psql` y en scripts que van por `asyncpg_conn.execute()` directo (§5 multi-statement), pero no en prepared statements de SQLAlchemy + asyncpg.

### Fase 2 — Backend mutaciones (✅ ENTREGADA 2026-05-16)

Implementa el ciclo de vida operacional completo via API. Smoke test §9 pasado: trámite `POD-LPL-2026-0009` creado → tomado → adjunto → transicionado → 6 movimientos en ledger.

**Migración 050 (`50_tramites_auditoria.sql`, aplicada local 2026-05-16):** agrega `id_usuario_alta` e `id_usuario_modificacion` a las 5 tablas de instancias (`tramite`, `tramite_movimiento`, `tramite_documento`, `tramite_firma`, `tramite_relacion`). Idempotente (`ADD COLUMN IF NOT EXISTS`).

**Servicios en `backend/app/services/tramites/`:**

| Módulo | Función principal |
|---|---|
| `auth.py` | `resolver_agente_desde_usuario` → `{id_agente, id_subarea, ids_equipos, id_municipio, nivel_acceso}`. `es_admin(nivel)=nivel<=2`. `agente_puede_tomar/operar` con reglas de toma exclusiva. |
| `autorizacion.py` | `quien_puede_actuar(quien_puede_jsonb, agente_info)` — OR entre `subareas/equipos/iniciador/roles`. `listar_transiciones_permitidas` anota cada transición con `disponible + motivo_no_disponible`. |
| `movimientos.py` | `registrar_movimiento(db, id_tramite, tipo, ...)` — append-only al ledger con `COALESCE(MAX, 0)+1` y `CAST(:v AS jsonb)` para todos los JSONB. |
| `creacion.py` | `validar_campos_contra_tipo` — todos los `tipo_dato` incluyendo seleccion_multiple, FKs, archivo (ignorado en creación). `resolver_iniciador` — polimórfico ciudadano/empresa/area_interna. `determinar_destinatario_inicial` — v1: subarea del agente creador. |
| `documentos.py` | Guarda en `backend/uploads/tramites/{anio}/{expediente}/{slug}.{ext}`. SHA256 streaming 64KB. `crear_firmas_pendientes` desde `firmantes_jsonb`. |
| `firmas.py` | `agente_puede_firmar` — polimórfico agente/subarea/equipo asignado. `marcar_firma` captura `ip_firma`, `user_agent_firma`, `hash_documento_firmado`. `actualizar_estado_firma_documento` — solo rol `'firma'` bloquea; `visado/notificacion` son informativos. `verificar_integridad_documento` — recomputa SHA256 del disco. |

**12 endpoints nuevos (`routes/tramites.py`):**

| Verbo | Path | Descripción |
|---|---|---|
| POST | `/api/v1/tramites` | Crear trámite (201). Numerador atómico, estado inicial FSM, 2 movimientos (creacion + numeracion). |
| GET | `/{ref}/transiciones-permitidas` | Transiciones del estado actual anotadas con `disponible + motivo`. |
| POST | `/{ref}/tomar` | Pessimistic lock (`SELECT FOR UPDATE`). Valida colectivo destinatario. |
| POST | `/{ref}/liberar` | Libera toma. Solo el tomador o admin. |
| POST | `/{ref}/transicionar` | Valida `quien_puede_jsonb`, `requiere_adjunto` (count docs desde `fecha_entrada_estado_actual`), aplica `destino_automatico_jsonb`, libera toma. |
| POST | `/{ref}/pase` | Pase manual a subarea/equipo. Libera toma automáticamente. |
| POST | `/{ref}/comentar` | Comentario libre (201). Cualquier agente autenticado. |
| POST | `/{ref}/documentos` | Upload multipart. Validación extensión + tamaño. `crear_firmas_pendientes` si el doc_requerido lo indica. (201) |
| GET | `/{ref}/documentos/{id}/contenido` | `FileResponse` streaming desde `backend/uploads/`. |
| POST | `/{ref}/documentos/{id}/firmar` | Verifica integridad SHA256 + registra evidencia de firma auditable. |
| POST | `/{ref}/documentos/{id}/rechazar-firma` | Marca rechazado + recalcula `estado_firma` del documento. |
| POST | `/{ref}/relacionar` | Vincula dos trámites (sorted para UNIQUE). Registra movimiento `relacion` en ambos. (201) |

**Reglas operativas críticas:**
- Toda mutación abre transacción y hace `SELECT ... FOR UPDATE` sobre `tramite` antes de modificar.
- `pase` y transición a estado final auto-liberan la toma (`id_agente_tomado_por = NULL`).
- `requiere_adjunto` se valida contando `tramite_documento.activo=TRUE` con `fecha_alta >= fecha_entrada_estado_actual`.
- El parámetro `iniciador_fks` de `resolver_iniciador` devuelve claves largas (`id_ciudadano_iniciador`, etc.); el INSERT las mapea explícitamente a `:cid`, `:eid`, `:crep`, `:sub_ini`.
- Mock storage en `backend/uploads/` (en `.gitignore`). SHA256 en el INSERT; `FileResponse` sirve directo.

**Quirk resuelto — mapeo de parámetros iniciador:** el spread `**iniciador_fks` sobre el dict del INSERT falla porque las claves largas no coinciden con los `:alias` del SQL. Siempre mapear explícitamente: `"cid": iniciador_fks.get("id_ciudadano_iniciador")`, etc. (sesión 2026-05-16).

**Smoke test §9 — resultados (local, 2026-05-16):**
- Login: 200 — `ciudadanovl@municipio.gob.ar` (nivel 1, agente 1, subarea 1)
- Crear trámite: 201 — `POD-LPL-2026-0009` (tipo 3, `id_tipo_tramite` empieza en 3 en local por cómo los creó el seed)
- Transiciones: 200 — 1 transición disponible: "Derivar a Espacios Verdes" (id=1)
- Tomar: 200 — agente 1 tomó el trámite
- Adjuntar: 201 — doc 17, `estado_firma: no_requiere`
- Transicionar: 200 — `en_evaluacion`, destinatario `Espacios Verdes`, toma liberada
- Comentar: 201
- Timeline: 6 movimientos (creacion, numeracion, toma, adjunto, transicion, comentario)

### Fase 3 — Frontend React (✅ ENTREGADA 2026-05-16)

Módulo completo en `web-app/src/modules/tramites/`. Pusheado en commit `e2234de`.

**Páginas y componentes:**

| Archivo | Rol |
|---|---|
| `pages/BandejaTramites.tsx` | Lista de trámites con filtros (estado, tipo, texto) + chips de conteo |
| `pages/DetalleTramite.tsx` | Vista detalle: metadatos, documentos, historial (Timeline), relaciones, panel acciones |
| `pages/CrearTramite.tsx` | Alta de trámite desde la UI: selector de tipo + formulario dinámico generado desde `tipo_tramite_campo` + resolución de iniciador (ciudadano/empresa/area_interna) |
| `components/FormularioDinamico.tsx` + `CampoDinamico.tsx` | Render del formulario derivado del catálogo del tipo (todos los `tipo_dato` soportados) |
| `components/EntitySelect.tsx` | Buscador con autocompletar para FKs (ciudadano/empresa). Recibe `path`, NO URL completa (ver memoria [[feedback_entityselect_path_no_url]]) |
| `components/DatosTramite.tsx` | Panel de datos/campos del trámite en el detalle |
| `components/EstadoBadge.tsx` | Badge de color dinámico con `estado_etiqueta` + `estado_color` del FSM |
| `components/EstadoFirmaBadge.tsx` | Badge del estado de firma de un documento |
| `components/Timeline.tsx` | Historial append-only de movimientos (tipo, actor, fecha, comentario, campos_modificados) |
| `components/ListaDocumentos.tsx` | Lista de adjuntos del trámite con descarga |
| `components/PanelAcciones.tsx` | Botones de acción según transiciones permitidas: transicionar, tomar/liberar, pasar, relacionar, comentar |
| `components/FileUploader.tsx` | Modal drag&drop para adjuntar documentos (multi-archivo, progreso, observación) |
| `components/VisorDocumento.tsx` | Modal full-screen para previsualizar adjuntos: PDFs (react-pdf 10.4 + pdfjs-dist 5.4.296, navegación páginas + zoom + teclado ←/→/Esc), imágenes (PNG/JPG/WEBP/GIF/HEIC con `<img>` + zoom), fallback a descarga para otros mimes. Carga via `descargarDocumentoBlob` (fetch con Bearer header + `cache: 'no-store'`) y `URL.createObjectURL`, revoke al cerrar |
| `components/ModalTransicion.tsx` | Modal para aplicar una transición FSM con comentario y adjuntos requeridos |
| `components/ModalFirma.tsx` | Modal para firmar/rechazar firma de un documento (captura evidencia auditable) |
| `components/ModalPase.tsx` | Modal para pase manual a subárea o equipo con selector + comentario |
| `components/ModalRelacionar.tsx` | Modal para vincular trámites por número de expediente (resuelve número → id via bandeja) |
| `hooks/useTramites.ts` | react-query hooks: `useTramite`, `useBandeja`, `useTransicionesPermitidas` |
| `lib/api.ts` | Funciones tipadas para todos los endpoints de trámites |
| `lib/types.ts` | Tipos TypeScript: `TramiteBandejaItem`, `TramiteDetalle`, `TramiteMovimiento`, `TramiteRelacion`, etc. |

**Rutas:** `/tramites` (bandeja) + `/tramites/nuevo` (alta) + `/tramites/:numero` (detalle). Hash router compatible con GH Pages.

**Módulo en catálogo DB:** `modulos (modulo_codigo='tramites', min_nivel_acceso=3)` — insertado en prod 2026-05-16.

**Seed prod:** 9 tipos, 21 trámites demo. Seed idempotente en `backend/seed_tramites.py`.

### Visor de documentos (✅ ENTREGADO 2026-05-18)

`VisorDocumento.tsx` reemplaza el `<a target=_blank>` que estaba roto en `ListaDocumentos.tsx` (el endpoint `/documentos/{id}/contenido` solo acepta auth por header `Authorization`, no por `?token=` query param). Botones nuevos: **Ver** (abre visor inline) y **Descargar** (fetch + anchor con `URL.createObjectURL`).

**Dependencias:** `react-pdf@10.4.1` + `pdfjs-dist@5.4.296` (pin obligatorio — `react-pdf` 10.4 declara `pdfjs-dist@5.4.296` exacto; pnpm puede instalar `5.7.x` que falla con `UnknownErrorException: API version "5.4.296" does not match the Worker version "5.7.284"`). Worker importado con `import pdfWorkerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url'` y asignado a `pdfjs.GlobalWorkerOptions.workerSrc`.

**Quirks resueltos al implementar:**
- **Bug pre-existente en `DetalleTramite.tsx`:** la página pasaba `documentos={[]}` hardcoded a `ListaDocumentos`, NUNCA llamaba a `obtenerDocumentos`. Además `obtenerDocumentos` esperaba `TramiteDocumento[]` plano pero el endpoint devuelve `{numero_expediente, documentos:[], total}`. Fix: tipar el wrapper + agregar `documentos` al hook `useTramite` + pasar `docsData` real.
- **Shape de respuesta `/documentos`:** el endpoint NO devuelve `hash_sha256`, `nombre_archivo_original`, `agente_subio_nombre` ni `asignado_a.{tipo,id,nombre}` rico — solo `asignado_nombre` plano. `types.ts` los marcó opcionales y `ListaDocumentos`/`ModalFirma` ya soportan ambos shapes con `?? '—'`.
- **HTTP cache cazó el binario viejo durante la verificación:** `fetch()` default usa el cache del browser; con `Last-Modified` de FastAPI puede devolver 304 + body cacheado. Fix: `cache: 'no-store'` en `descargarDocumentoBlob`. Si en el futuro agregás otro helper que sirva binarios autenticados, replicar.
- **Path quirk de `services/tramites/documentos.py::ruta_absoluta_mock` (no fixeado, deuda):** la función devuelve `Path("backend") / storage_path`. Como uvicorn corre con cwd=`backend/`, eso resuelve a `backend/backend/uploads/...`. Cualquier carpeta `backend/backend/` que aparezca en `git status` es artefacto de uploads viejos — borrarla. Fix definitivo sería usar path absoluto desde `__file__`, pero requiere migrar storage_path o un fallback que pruebe ambos.

### Notificaciones a la bandeja (✅ ENTREGADO 2026-05-18)

Sistema in-app + email cuando un trámite entra a la bandeja del destinatario (creación, pase, transición que cambia destinatario).

**Migración 51 (`51_notificaciones.sql`):** crea `notificacion` (estándar §10 + columnas in-app: `id_usuario`, `tipo`, `titulo`, `mensaje`, `url_destino`, `recurso_tipo`/`recurso_id` polimórfica, `leida`/`leida_en`, `enviada_mail`/`enviada_mail_en`). Índices: `(id_usuario, leida, fecha_alta DESC)` parcial sobre `activo=TRUE` y `(recurso_tipo, recurso_id)`. **Solo aplicada en local al 2026-05-18.** Falta aplicar en prod Supabase.

**Backend nuevo:**
- `app/core/config.py` agrega `SMTP_HOST/PORT/USER/PASS/FROM/USE_TLS` + `APP_BASE_URL`. Cuando SMTP queda vacío, el sender corre en modo MOCK (log a stdout, no rompe el flow). Apuntado a Zoho Mail (`smtp.zoho.com:587` + STARTTLS).
- `app/services/email.py::enviar_mail(to, subject, body_html, body_text)` — usa `smtplib` de stdlib (síncrono, OK en threadpool de BackgroundTasks de FastAPI). Sin nueva dep.
- `app/services/notificaciones.py::notificar_tramite_a_bandeja(db, id_tramite, evento, background_tasks)` — resuelve destinatarios (todos los agentes activos con email del subarea/equipo destinatario actual del trámite), inserta una fila por usuario en `notificacion` y dispara mail async via `background_tasks.add_task`. Fail-safe: cualquier error se logea pero no levanta. **CRITICAL: hace `await db.commit()` adentro** porque el caller ya commiteó antes y la sesión queda lista para nueva transacción; sin commit las filas se descartaban silenciosamente.
- Hooks en `routes/tramites.py`: `crear_tramite` (siempre), `pase_tramite` (siempre), `transicionar_tramite` (solo cuando el destinatario cambia y no es estado final). Los tres signatures suman `background_tasks: BackgroundTasks`.
- Router nuevo `routes/notificaciones.py` (prefix `/api/v1/notificaciones`): `GET ""`, `GET /count`, `PATCH /{id}/leer`, `PATCH /leer-todas`. Solo del usuario logueado. `X-Total-Count` expuesto via `Access-Control-Expose-Headers`.

**Frontend nuevo:**
- `web-app/src/lib/notificacionesBackend.ts` — cliente tipado + hooks react-query (`useNotificaciones`, `useNotificacionesCount` con `refetchInterval: 30_000`, `useMarcarLeida`, `useMarcarTodasLeidas`). **Separado de `stores/notifications`** que sigue usándose para toasts efímeros.
- `web-app/src/shell/TopBar/NotificacionesDropdown.tsx` — componente nuevo de campana + dropdown. Reemplaza el botón Bell estático del TopBar. Maneja iframe/standalone: en iframe usa `window.parent.shellNavigate('web-app/dist/index.html#/tramites/...')`; standalone usa `useNavigate(hash)`. Cierra con click-outside + Escape. Click en notif: marca leída + navega + cierra.
- `web-app/src/shell/TopBar/TopBar.tsx` simplificado: importa el nuevo dropdown, ya no necesita el contador del store local.

**Verificación visual (2026-05-18):**
1. Login como `ciudadanovl@municipio.gob.ar` (admin, nivel 1).
2. Para que el admin pueda crear trámites necesité crearle un agente: `INSERT INTO agentes (nombre,apellido,id_usuario,id_subarea,id_municipio,activo) VALUES ('Cesar','Zeta',1,1,1,TRUE)` — quedó como agente 9. CONSERVAR esta fila para sesiones futuras.
3. POST /tramites con `id_tipo_tramite=4` (pedido-informe), iniciador `area_interna`/subarea=1, destinatario subarea=1 → `INF-LPL-2026-0009` creado.
4. Backend insertó 2 notificaciones (Cesar Zeta + Roberto Filad, ambos agentes activos de subarea 1).
5. Email logueado en MOCK con HTML + body text + link a `https://zge.zaris.com.ar/#/tramites/INF-LPL-2026-0009`.
6. Topbar polling → badge "1" rojo en la campana.
7. Click campana → dropdown con la notif. Click notif → URL cambió a `#/tramites/INF-LPL-2026-0009` + DB confirma `leida=true, leida_en=NOW()`.

**Quirks cazados durante implementación:**
- **`tramite` no tiene `id_tipo_tramite` directo, va via `tipo_tramite_version`.** Mi JOIN inicial `tt ON tt.id_tipo_tramite = t.id_tipo_tramite` rompía con `UndefinedColumnError`. Fix: `JOIN tipo_tramite_version ttv ON ttv.id_tipo_tramite_version = t.id_tipo_tramite_version JOIN tipo_tramite tt ON tt.id_tipo_tramite = ttv.id_tipo_tramite`.
- **`db.flush()` no persiste si el endpoint no commitea después.** El caller ya hizo su commit, dejando la sesión SQLAlchemy lista para nueva transacción. Sin un commit nuevo dentro del service, las filas insertadas se descartan al cerrar la sesión. Fix: `db.commit()` adentro del service (no flush).
- **`subarea.id_municipio` está NULL en muchas filas del seed local** (mig 22 lo dejó sin backfill). Cualquier endpoint que filtre `WHERE id_municipio = :mun` no las matchea. Para que el smoke pase: `UPDATE subarea SET id_municipio=1 WHERE id_subarea=1`. NO replicar en prod sin diagnóstico — puede haber filas históricas con NULL intencional.

**Email en MOCK hasta que se setee SMTP en Railway:**
Para activar envíos reales agregar al `.env` de Railway (y `backend/.env.local` para dev):
```
SMTP_HOST=smtp.zoho.com
SMTP_PORT=587
SMTP_USER=<tu-zoho-user>
SMTP_PASS=<app-password-zoho>
SMTP_FROM=ZARIS <noreply@municipio.gob.ar>
SMTP_USE_TLS=True
APP_BASE_URL=https://zge.zaris.com.ar
```
Si alguna de las primeras 4 está vacía, `smtp_configurado()` devuelve False y se cae a modo MOCK. Reiniciar uvicorn tras cambiar el env.

**Pendientes futuros (no críticos):**
- Aplicar mig 51 en prod Supabase.
- Setear credenciales Zoho SMTP en Railway.
- Notificaciones para otros eventos: firma pendiente solicitada al firmante, comentario en trámite que tomé, transición a estado final si el iniciador es interno. Diseño extensible: el `tipo` y `recurso_tipo` ya soportan más casos.
- Campana en el shell vanilla (hoy es placeholder). Por arquitectura distinta a React, requiere implementarla en `index.html` + `frontend/js/menu.js` aparte. La campana React ya cubre el flujo principal (el usuario navega dentro del bundle React cuando trabaja con trámites).
