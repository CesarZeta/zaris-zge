# Reglas Mandatorias de Desarrollo — ZARIS

> **Mantenimiento de este documento:** acá van *reglas* (qué hacer siempre), no *bitácora* (qué pasó una vez). El detalle histórico de migraciones aplicadas vive en [`HISTORIAL_MIGRACIONES.md`](HISTORIAL_MIGRACIONES.md) — al cerrar una migración, su bitácora va ahí, no acá. La numeración de secciones (`§N`) tiene huecos históricos (§8/§16/§25): **no renumerar** (hay cientos de refs cruzadas). Criterio completo en memoria `feedback_mantenimiento_doc_y_memorias`.

> **Gestión autónoma de memorias (autorizado por el usuario 2026-06-02):** puedo **crear, editar, reescribir `MEMORY.md` y borrar archivos de memoria sin pedir autorización previa**. Incluye descartar memorias que ya no tienen reuso futuro (incidentes puntuales resueltos sin patrón reutilizable, duplicados, o cosas absorbidas en CLAUDE.md) para mantener `MEMORY.md` bajo 24KB. Permisos de herramienta ya en `settings.local.json` (Write/Edit/Read/rm sobre `…/memory/`). Sigo **informando** qué borré, pero no consulto antes. No aplica a `git rm`/borrado fuera de `memory/`.

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
| **Turnos** | — | **`modules/turnos/`** (4 tabs: Turnos / Agenda solo-turnos / Atendidos+PDF / Prestaciones; autoservicio público; filtros prestación/recurso/ciudadano; scoping por nivel; cumplir dispara encuesta CSAT de turnos §42) | **React** (publicado) |
| **Entradas** | — | **`modules/entradas/`** (backoffice completo 2026-05-14 — lista de eventos con espacio + gestión de reservas reusando `ReservaModal` de Agenda; autoservicio ya funciona vía flujo público de eventos) | **React** (publicado) |
| **Dashboard** | — | **`modules/dashboard/`** (mapa Leaflet + stats reales) | **React — HOME del iframe** desde 2026-05-13 (se carga al entrar al shell y al hacer click en INICIO desde cualquier módulo) |
| **OT (3 mesas)** | — (borrado, era `ot_supervisor.html`/`ot_agente.html`/`ot_auditoria.html`) | **`modules/ot/`** (Supervisor / Agente / Auditoría + drawer detalle compartido) | **React** (publicado) |
| **Trámites** | — | **`modules/tramites/`** (backend Fase 1+2 + frontend Fase 3 completo — bandeja, detalle, acciones, timeline, adjuntos, pase, relacionar; 2026-05-16) | **React** (publicado) |
| **Datos (BI)** | — | **`modules/bi/`** (landing DATOS → Operativo + Ejecutivo. Operativo: 4 tabs Resumen/Resueltos-SLA/Pendientes+mapa/Subreclamos. Ejecutivo: placeholder. 2026-05-26) | **React** (publicado) |
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
- **PK legacy `id` (no `id_<tabla>`) en tablas viejas:** la convención §5 dice `id_<tabla>`, PERO varias tablas legacy usan PK simple **`id`**: `actividades`, `nacionalidades`, `tipo_representacion`, `ciudadano_empresa`. Cazado 2026-06-01: un `SELECT id_actividad FROM actividades` dio 500 (la columna es `id`; `empresas.id_actividad` es la FK, no la PK del destino). **Antes de escribir un SELECT/JOIN contra una tabla de catálogo legacy, verificar el nombre real de su PK** (`information_schema.columns`), no asumir `id_<tabla>`. Familia de §28 (PKs y nombres de columnas).
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
| Prod | PWA App Vecinos | `https://vecinos.zaris.com.ar` (Vercel, repo `CesarZeta/zaris-vecinos`, branch `main`) |
| Local | PWA App Vecinos | `http://localhost:5174` — `cd zaris-vecinos && pnpm dev` (repo separado, scaffold Etapa 1 creado 2026-05-19) |
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

### El autodeploy de Railway NO es confiable — verificar prod después de cada push backend

Cazado 2026-05-20: se pushearon dos commits backend a `main` y prod siguió sirviendo código viejo (endpoint nuevo daba 404, allowlist CORS vieja). **No era el código.** Dos causas que se dieron en la misma sesión:

1. **El servicio estaba caído** — el usuario tuvo que levantarlo manualmente desde el dashboard para que tomara el commit.
2. **Incidente de plataforma "builds slow to progress"** — Railway encoló el build por horas (banner amarillo en el dashboard).

**Regla operativa:** tras pushear backend, NO asumir que prod ya tiene el código. Verificar con `curl /openapi.json` (¿aparece el path nuevo?) o un preflight del header esperado. Si no aplica en ~5 min, **pedirle al usuario que mire el dashboard Railway** (servicio `zaris-api` → Deployments): banner de incidente, deploy en Failed/Building, o servicio caído. El health (`/api/health`) puede seguir 200 con el deploy VIEJO activo — no sirve para confirmar que el commit nuevo aplicó. Para eso, chequear algo que **solo exista en el commit nuevo**.

**Cómo distinguir "deploy viejo en prod" de "mi test CORS está mal hecho"**: usar un origen que YA estaba permitido hace tiempo (`https://zge.zaris.com.ar`) como control. Si el preflight `OPTIONS` con ese origen devuelve `Access-Control-Allow-Origin` pero el origen nuevo no, es deploy viejo (no test roto). Comando: `curl -s -i -X OPTIONS -H "Origin: https://zge.zaris.com.ar" -H "Access-Control-Request-Method: GET" <url> | grep -i access-control-allow-origin`.

> **CORS de FastAPI no acepta wildcards** — `allow_origins` es lista de strings exactos. `*.vercel.app` NO funciona; hay que poner la URL exacta del deploy. Ver §6 (App Vecinos).

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

Módulos React en `web-app/src/modules/<nombre>/`, build Vite → GH Pages → cargados en el iframe del shell vanilla. **Antes de empezar leer §4 y §14.**

> **Procedimiento de alta (pasos mecánicos: crear manifest, registrarlo, exponerlo en el sidebar, build/publish) en la skill `nuevo-modulo-react`** (`.claude/skills/nuevo-modulo-react/`).

### Reglas que un módulo React DEBE respetar (criterio — no se delegan a la skill)

- **Router:** `createHashRouter`, NUNCA `createBrowserRouter`. GH Pages no soporta HTML5 routing; el F5 daría 404. URLs quedan `…/web-app/dist/index.html#/<ruta>`.
- **API base:** `import.meta.env.VITE_API_BASE` (`.env.development` → `127.0.0.1:8000`, `.env.production` → Railway).
- **Sesión:** usar `useAuthStore` (`web-app/src/stores/auth.ts`, `dualShapeStorage`, §29). No leer `localStorage` a mano.
- **Iframe:** el `AppShell` se auto-oculta cuando `window.self !== window.top`. **NO agregar UI de navegación propia** (sidebar/topbar/notificaciones) al shell React — eso vive en el shell vanilla (§14).
- **Navegar a otro módulo:** `window.parent?.shellNavigate?.('frontend/<otro>.html')`. Nunca `window.location.href` absoluto (rompe bajo `/zaris-zge/`, §32).
- **Estilos:** tokens del DS (`var(--zaris-orange)`, `var(--fg-1)`…), nunca hex hardcodeado. El shell React solo importa tokens, NO los componentes `*-zaris` (§13).
- **`data-modulo="<codigo>"` exige fila en la tabla `modulos`** (§30) o el ítem queda oculto para TODOS. Migración formal en local Y prod. Módulo informativo para cualquiera → sin `data-modulo` (ej. Guías). Cazado con Encuestas (mig 61), [[feedback_modulo_react_necesita_fila_en_modulos]].

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
`agentes`, `equipos`, `equipo_usuarios`, `equipo_agentes`, `servicios`, `tipo_usuario`, `cargos`, `area`, `subarea`, `tipo_reclamo`, `tipo_representacion`, `actividades`, `nacionalidades`, `estado_reclamo`, `estado_ot`, `configuracion_general`, `lugares_atencion`, `agenda_clase`, `agenda_feriado`.

> `reclamos_area` y `reclamos_subarea` fueron eliminadas de admin_tablas en migración 20. El módulo Reclamos usa las tablas generales `area` y `subarea`.

> **`usuarios` es READ-ONLY en admin_tablas (sesión 2026-05-26).** GET sigue habilitado (selects FK de otras tablas: `agentes.id_usuario`), pero POST/PUT/DELETE devuelven **403** (`READ_ONLY_TABLES` en `admin_tablas.py`). Usuarios se administra SOLO desde su pantalla propia `frontend/usuarios.html` (hashea password + audita login). El ítem "Usuarios" se quitó del sidebar de Maestros y el `SCHEMAS.usuarios` del front.

> **Forms `agentes` y `equipos` son INLINE, no modal.** `INLINE_FORM_TABLES = {agentes, equipos}` en `admin_tablas.html`: el form se renderiza en el flujo de la página (`#inlineForm`, fuera de `#main` para sobrevivir el re-render de `cargarTabla`), no en el modal genérico. El resto de tablas siguen con el modal genérico.
> - **`agentes`** (sesión 2026-05-26): sección "Horario de asistencia" (franjas Lun-Dom bitmask + hora inicio/fin) que escribe en `disponibilidad_recurso` (tipo_recurso=agente) vía `/api/v1/agenda/disponibilidad` — alimenta la disponibilidad efectiva del agente en Agenda (§27).
> - **`equipos`** (sesión 2026-05-27): sección "Integrantes del grupo" — buscador de agentes con autocompletar (filtro en cliente sobre `GET /admin/agentes`, debounce; un `<select>` de 85 agentes es inusable §23) + lista editable con "Quitar". Sincroniza con `equipo_agentes` tras guardar el equipo (re-lee relaciones reales, soft-delete las quitadas, INSERT las nuevas), espejo de cómo agentes sincroniza sus franjas. Sin backend nuevo — usa el CRUD genérico de admin_tablas (`equipos` + `equipo_agentes`). Seed de mesas demo: `backend/seed_equipos_demo.py` (idempotente, resuelve subárea+agentes por nombre; 5 mesas en prod al 2026-05-27).
>   - **`equipos.tipo_grupo`** (mig 67): distingue **`mesa_tramites`** (recibe pases de Trámites §35: los integrantes ven en "Mi bandeja" lo pasado a esa mesa y cualquiera lo toma; **subárea opcional, SIN horario**) de **`trabajo_reclamos`** (cuadrilla que atiende reclamos/OT y se agenda; **subárea OBLIGATORIA** vía CHECK `ck_equipo_subarea_reclamos`, + sección de franjas igual que agentes que escribe en `disponibilidad_recurso(tipo_recurso='equipo')` — lo que la Agenda realmente lee §27; los 3 campos legacy `dias_semana/hora_inicio/hora_fin` de la tabla NO los lee la Agenda, por eso se sacaron del form). El form muestra/oculta la sección horario y marca la subárea requerida según el tipo (`_recursoHorario`/`_bindTipoGrupo`). Las franjas reusan `renderHorarioSeccion`/`_cargarFranjas`/`_sincronizarFranjas` parametrizados por `tipo_recurso`. Listado/preview: cuadrillas muestran "Grupo de trabajo · <subárea>", mesas "Mesa de entrada de trámites" (sin subárea) + badge "N integrantes".

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

> **El detalle histórico de cada migración (qué hace, cuándo se aplicó, snapshots de backup) vive en [`HISTORIAL_MIGRACIONES.md`](HISTORIAL_MIGRACIONES.md)** (raíz del repo). Acá queda solo el resumen vigente. **No confiar en esta doc como fuente de verdad** — antes de codear algo schema-dependent, verificar el estado real con `execute_sql` (regla §24).

**Estado general:** migraciones 20-76 aplicadas en local Y prod (Supabase) sin divergencia conocida al 2026-06-01. La numeración 51 está duplicada (`51_notificaciones.sql` + `51_tramites_tipo_dato_direccion.sql`, ambas aplicadas) — **cualquier mig nueva debe usar 77+**. **Mig 76 (sesión 2026-06-01, alta pública de vecinos §38):** tabla `empresa_credencial` (1:1 con `empresas`, solo verificación de email del autoregistro — `token_verificacion`/`verificado`/`verificado_en`, SIN password) + índice parcial sobre el token. Aplicada local (psql) + prod (`apply_migration`). El ciudadano reusa `ciudadano_credencial` (mig 53). **Mig 75 (sesión 2026-06-01, política de retención de Trámites §35, Fases 2-5):** `tipo_tramite.retencion_nunca_depurar` (BOOL, excepción por tipo) + `tramite.fecha_archivado`/`archivado_motivo` (CHECK `ck_tramite_archivado_motivo` `inactividad|manual`, auto-archivado por inactividad) + `tramite_documento.binario_purgado`/`fecha_purga_binario` (purga del binario, el registro+hash se conservan) + valores `'archivado_inactividad'`/`'purga_binario'` en el CHECK del ledger + índices parciales. **El seed de las 4 claves de `configuracion_general` (retencion_dias_aprobado/rechazado, tramite_inactividad_dias, tramite_purga_binarios_real) va en `75b` SEPARADO del DDL** (atomicidad). **DRIFT cazado: prod tiene `configuracion_general.tipo` NOT NULL (`string|boolean|integer`) que local NO tiene — el `75b` arma el INSERT con o sin esa columna según exista** (§24, [[feedback_verificar_drift_completo_prod]]); en prod el seed fue por `execute_sql` con `tipo` explícito. DDL por `apply_migration`. **Mig 74 (sesión 2026-06-01, marca de resultado de Trámites §35, Fase 1 de retención):** `tramite.resultado` (`pendiente|aprobado|rechazado`, CHECK `ck_tramite_resultado`, default `'pendiente'`) + valor `'resultado'` agregado al CHECK del ledger `tramite_movimiento_tipo_check`. Marca paralela al estado FSM que decide la política de retención de binarios. Aplicada local + prod. **Mig 73 (aprobaciones por etapa/visados de Trámites, §35):** `tipo_tramite_aprobacion_requerida` (catálogo versionado) + `tramite_aprobacion` (instancia) + valor `'aprobacion'` en el CHECK del ledger `tramite_movimiento`. Aplicada local + prod. **Mig 72 (sesión 2026-05-28, encuesta diferenciada de turnos §42):** `encuesta_envio.id_reclamo` deja de ser NOT NULL + nueva FK `id_turno` (→ `turnos`) + CHECK `ck_encuesta_envio_origen` (exactamente uno de `id_reclamo`/`id_turno`, **NOT VALID** — las filas viejas son todas reclamos) + índice parcial. El CHECK de `encuesta_plantilla.tipo` ya admitía `'turnos'` (mig 57); el seed de la plantilla CSAT `tipo='turnos'` va en un `DO` block aparte del DDL (atomicidad §21, [[feedback_apply_migration_parcial_aborta_todo]]). Aplicada local + prod; en prod el DDL fue por `apply_migration` y el seed por `execute_sql` separado. Habilita la encuesta de satisfacción al **cumplir un turno** (§42). **Mig 71 (sesión 2026-05-28, replanteo Turnos §33):** renombró `tipo_servicio_turno` → `tipo_prestacion` (PK `id_tipo_prestacion`, FK en `turnos` renombrada) + columnas `clase` (atencion/reserva_espacio) + `tipo_recurso` (agente/espacio) + `id_agente`/`id_espacio` (FK, exactamente uno por CHECK `ck_tipo_prestacion_recurso` **NOT VALID**) + CHECK `ck_tipo_prestacion_reserva_espacio`. Solo DDL — los seeds de prestaciones van en `seed_turnos_demo.py`. **CUIDADO con los CHECK NOT VALID: igual se evalúan al UPDATE de una fila existente; el seed soft-deletea las viejas sin recurso asignándoles un placeholder (`tipo_recurso='agente', id_agente=<primero>`) en el mismo UPDATE.** En prod se aplicó vía SQL directo por MCP (no hay `.env.prod`): prestaciones 4-7, 3 turnos demo recreados. **Migs 69-70 (sesión 2026-05-28, módulo Turnos/Disponibilidad §33):** 69 = tabla `agente_novedad` (inasistencias/licencias/vacaciones de agentes; rango de fechas, total o parcial por hora; resta disponibilidad efectiva) + clave `configuracion_general.turnos_respeta_disponibilidad` (switch global, default `true`). 70 = `turnos.id_espacio` (FK espacios_agenda) + `id_agente` nullable + CHECK `ck_turnos_recurso` (exactamente uno) → turno polimórfico agente|espacio. **CUIDADO: la mig 69 vía `apply_migration` falló a mitad en prod la 1ª vez (el INSERT a configuracion_general abortó la tx y revirtió el CREATE TABLE) → 500 en `/slots` hasta recrear `agente_novedad`. `apply_migration` es atómico, ver [[feedback_apply_migration_parcial_aborta_todo]].** **Mig 68 (sesión 2026-05-28): `tipo_tramite_transicion.tipo_accion` (aprobar/rechazar/derivar/avanzar/otro, default `avanzar`) + `.mensaje_iniciador` (TEXT) + `tipo_tramite_documento_requerido.cantidad_max_archivos` (SMALLINT 1-20, default 1) — editor de tipos, issues de Roy (§35).** Migs 62-64 (sesión 2026-05-26): 62 `usuarios.fecha_ultimo_login` + tabla `usuario_login_log` (auditoría de accesos); 63 `agentes.cuil`; 64 índice UNIQUE parcial `agentes.id_usuario WHERE NOT NULL` (regla 1:1 agente↔usuario, §39). Mig 65: fila `modulos.bi` (nombre "Datos", nivel 2) para el módulo BI §43. **Mig 66 (sesión 2026-05-27): `tramite.id_agente_actual` + CHECK `ck_tramite_destinatario` ampliado a 4 ramas (NULL/subarea/equipo/agente) — habilita destinatario directo a un agente (§35).** **Mig 67 (sesión 2026-05-27): `equipos.tipo_grupo` (`mesa_tramites`/`trabajo_reclamos`, default `mesa_tramites`) + CHECK `ck_equipo_subarea_reclamos` (subárea obligatoria solo si `trabajo_reclamos`) — distingue mesa de entrada de trámites vs cuadrilla de reclamos (§15).**

**Tablas que YA existen en prod y NO deben re-crearse:** `reclamos`, `reclamo_historial`, `tipo_reclamo`, `estado_reclamo`, `ordenes_trabajo`, `estado_ot` (5 seeds), `equipo_agentes`, `configuracion_general`, todas las de Agenda (migs 30-43), Turnos (45-46), permisos (38/44), trámites (47-50, 56), notificaciones (51), encuestas (57-58, 60-61), auth público de ciudadanos (52-53), adjuntos de OT (54), `usuarios.id_subarea`/`es_externo` (55), `usuario_login_log` (62). Detalle por mig en `HISTORIAL_MIGRACIONES.md`. Ver memoria [[project_supabase_estado_schema]].

**Estados de reclamos en prod** (migrados 2026-05-04): `Ingresado→Sin asignar`, `En revisión→En gestión`, `Cerrado→Resuelto`, `Rechazado→Cancelado`. CHECK `ck_reclamo_estado`: `('Sin asignar','En gestión','En espera','En auditoría','Resuelto','Cancelado')`.

**Implicaciones vivas (no son bitácora — son reglas):**
- **`ciudadanos`/`empresas` YA tienen `latitud`/`longitud`** (`NUMERIC(10,7) NULL`, sin migración formal — drift manual viejo). Si piden "agregar lat/lon", NO redactar `ADD COLUMN`: verificar con `execute_sql` y solo tocar schemas Pydantic + frontend. Ver [[reference_buc_lat_lon_columnas_existentes]].
- **Mig 27 dropeó `tipo_reclamo.id_area`** pero `reclamos.id_area`/`reclamos.id_subarea` **siguen existiendo con NULL** para filas viejas. Cualquier filtro `WHERE r.id_area=:x` o JOIN deja invisibles reclamos legacy. Usar siempre `s.id_area` / `tr.id_subarea` (derivados vía JOIN). Ver [[feedback_filtros_legacy_post_mig27]] y §27.
- **Trigger `trg_nro_ot`** lo creó mig 59 (NO existía pese a estar documentado antes). Si tocás numeración de OT, verificá el trigger con `pg_trigger`. Ver [[feedback_verificar_trigger_existe_no_confiar_doc]].

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
| `fecha_primer_asignacion` | TIMESTAMPTZ | Set al pasar a `En gestión` (medición de SLA real). **Hasta 2026-05-25 NO se seteaba** (bug); ahora se hace vía `COALESCE(fecha_primer_asignacion, NOW())` en `cambiar_estado` (reclamos.py) y en `crear_ot`/`crear_ot_con_agenda` (ordenes_trabajo.py). El COALESCE evita pisarla al volver a En gestión. |
| `fecha_cierre` | TIMESTAMPTZ | Set al pasar a estado final (`Resuelto` o `Cancelado`). Lo setean **las 3 vías** que llevan a estado final: `cambiar_estado` (pase manual), `_resolver_reclamo`/cierre vía OT, y `PUT /{id}/cancelar` (este último se quedó afuera del fix de mayo y se corrigió el 2026-06-01 con `fecha_cierre=COALESCE(fecha_cierre, NOW())`, commit `00f06a7`). Si agregás otra ruta a estado final, setearla ahí también — un fix que cubre una vía no cubre las otras (ver memoria `feedback_guard_subarea_cubre_todas_las_vias`). |
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

### Identificador técnico se autocompleta desde la etiqueta visible (auto-slug)
Cuando un form pide al usuario cargar **un identificador técnico** (snake_case, código, slug — cosas que el usuario municipal no conoce) **junto a** una etiqueta visible/legible, el identificador **debe autocompletarse desde la etiqueta** y no exigir que el usuario lo tipee a mano.

- **Patrón:** la etiqueta visible va **primero** en el form. Su `onChange` deriva el identificador con un helper `aSnakeCase` (NFD + `replace(/\p{Diacritic}/gu,'')` para tildes, lowercase, `[^a-z0-9]+`→`_`, trim de `_`, prefijo `_` si arranca con dígito). Un `useRef` marca si el usuario editó el identificador a mano: mientras no lo haya tocado, se re-deriva en cada cambio de etiqueta; una vez editado, se respeta lo suyo (pero siempre normalizado).
- **Validación en vivo, no al submit:** indicador ✓/✕ + borde verde/rojo al costado del input, hint **siempre visible** que aclara la restricción en lenguaje llano ("solo minúsculas, números y guión bajo, **sin espacios**"), y botón Guardar deshabilitado mientras el identificador sea inválido. NO dejar que el usuario complete todo el form y recién al guardar le tire un error en rojo al pie (mala UX, cazada en QA 2026-05-27).
- **Listas de opciones (`seleccion`/`seleccion_multiple`):** editar con **filas {Etiqueta visible, Valor interno}** + botón "+ Agregar opción" y quitar, NO un textarea con formato `valor|Etiqueta` (conocimiento técnico que el usuario no tiene). El valor interno se autocompleta desde la etiqueta de cada opción con el mismo `aSnakeCase`. Internamente sigue produciendo el mismo `opciones_jsonb` `[{valor,etiqueta}]`.
- **Implementado en:** `web-app/src/modules/tramites/admin/modals/CampoModal.tsx` (nombre interno del campo + valores de opción). Referencia canónica para cualquier form futuro con identificadores técnicos.
- **Modales de edición con muchos campos: cierre seguro.** El click-outside debe exigir `mousedown` Y `mouseup` sobre el overlay (no un solo `onClick`), sino arrastrar para seleccionar texto en un input y soltar sobre el fondo cierra el modal y se pierde lo cargado. Patrón en `web-app/src/modules/tramites/admin/modals/_modalShell.tsx` (cazado en QA 2026-05-27, BUG-02). El modal anidado de alta (arriba) sí prioriza cerrar con click-fuera porque es un overlay rápido; este matiz aplica a modales de carga larga.

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

> **Recetas para escribir scripts de seed en la skill `seed-csv`** (`.claude/skills/seed-csv/`). Invocarla al crear/modificar un `backend/seed_*.py` o poblar catálogos desde CSV. Cubre idempotencia, encoding Windows, resolución de IDs por nombre, inspección previa del CSV, mapping de IDs legacy y la lista de scripts disponibles.

### REGLA CRÍTICA (aplica a TODO backend, no solo seeds): verificar el estado real de prod con `execute_sql` ANTES de codear

**No confiar en §21 ni en la simetría con local.** La doc queda atrás Y local puede tener cambios manuales sin migración formal. Antes de aplicar/re-aplicar una migración, codear un endpoint que referencie una columna/filas, o un INSERT que omita columnas: chequear en prod **existencia + NOT NULL + DEFAULT + CHECK + seeds dependientes**. Lo que local acepta puede explotar en prod (casos reales: `agentes.es_auditor` solo en local → crash; `activo NOT NULL` sin default en prod → 500; `ciudadanos_sexo_check` exige uppercase solo en prod → 500). Comandos: `to_regclass`, `information_schema.columns` (is_nullable, column_default), `pg_constraint` (CHECKs). Detalle en [[feedback_verificar_drift_completo_prod]].

**Aplicar en local Y prod en la misma sesión** (sino se desincronizan). **Backup antes de UPDATE/DELETE masivos en prod**: snapshot en `_backup_<tabla>_YYYY_MM_DD`.

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
Para sumar adjuntos a otra entidad (ej: OTs), replicar el patrón: nueva tabla `<entidad>_adjuntos` con mismos campos, nuevo bucket si conviene aislar, y reutilizar `app/core/storage.py` (las funciones reciben `path` arbitrario y leen el bucket de settings — extraer a parámetro si se usan múltiples buckets). **Ya hecho para OT** (`ot_adjuntos`, mig 54, ver §34) — reusa el mismo bucket `reclamos-adjuntos` con paths bajo `ot/{id_ot}/`. Es la referencia canónica para clonar a futuras entidades.

## 27. Módulo Agenda

> **Bitácora de implementación** (migraciones 30-43, seeds demo, sub-fases entregadas, pendientes cerrados) en [`HISTORIAL_MIGRACIONES.md`](HISTORIAL_MIGRACIONES.md). Acá quedan las reglas vivas. Estado: backend (22 endpoints `agenda_v2.py` + espacios + disponibilidad) y frontend React (`web-app/src/modules/agenda/`) en producción. Ver memoria [[project_agenda_espacios_disponibilidad]].

### Estructura del módulo (cierre B2, 2026-05-14)

- **5 tabs** en `AgendaLayout`: **Vistas / Eventos / Disponibilidad / Conflictos / Config**. Dentro de Vistas, sub-toggle **Día / Semana / Mes** (persistido en `agendaStore.vistaGrilla`). URLs viejas `/agenda/timeline`, `/agenda/mensual` redirigen a Vistas. El tab **Disponibilidad** (`DisponibilidadView.tsx`, 2026-05-28) gestiona **Feriados** (`agenda_feriado`) y **Novedades de agentes** (`agente_novedad`: inasistencias/licencias, mig 69) — ambos restan disponibilidad efectiva. CRUD vía router `agenda_novedades.py` (`/api/v1/agenda/novedades` + `/feriados`, nivel ≤ 2). API client en `agenda/api/novedadesApi.ts`.
- **Pills de tipo de recurso** (4, con conteo desde `/recursos/conteos`): Agentes / Equipos·OT / Esp. atendidos·Turnos / Esp. eventos·Entradas. **NO hay opción "Todos"** (ver Performance). **Las pills NO son intercambiables** — cada una sirve a un módulo distinto: Equipos→asignación de OT, Esp. atendidos→Turnos, Esp. eventos→Entradas.
- **DnD solo en Vista Día y Semana** (`@dnd-kit/core@6.3.1`, PointerSensor + KeyboardSensor). Bloques tipo `evento` no son arrastrables (se editan desde el modal del evento).

### Convenciones del módulo

**FKs a las PKs reales:** `eventos.id_subarea`→`subarea.id_subarea`, `eventos.id_estado_evento`→`estado_evento.id_estado_evento`, `evento_reservas.id_ciudadano`→`ciudadanos.id_ciudadano`, `ocupaciones.id_orden_trabajo`→`ordenes_trabajo.id_ot`. `evento_encargados.id_recurso` y `ocupaciones.id_recurso` → `agentes`/`equipos`/`espacios_agenda` (sin FK física; polimórfica por `tipo_recurso`, validación en backend).

**Tabla única `ocupaciones`** con CHECK `ck_ocupacion_consistencia`: solo se popula la FK del `tipo` (`ot`→`id_orden_trabajo`, `evento`→`id_evento`, `turno`→`id_ciudadano`). No usar tablas separadas por tipo.

**`equipo_agentes` (no `equipo_usuarios`):** pivot equipo↔agente. `equipo_usuarios` solo existe vacío en local; en prod no existe.

**`asignacion_a` en `tipo_reclamo`:** define si las OTs del tipo bloquean agenda de `agente` o `equipo`. `duracion_estimada_min` es lo que bloquea el calendario (distinto de `sla_dias`, deadline del reclamo).

**Tres tipos de recurso:** `agente`, `equipo`, `espacio`. Espacio puede ser `atendido` (necesita agentes vinculados vía `espacio_agentes`) o desatendido.

### Convención bitmask `dias_semana`

`dias_semana SMALLINT` con bitmask, NO TEXT. Lunes=bit0=1, Martes=2, Miércoles=4, Jueves=8, Viernes=16, Sábado=32, Domingo=64. Ejemplos: L-V=`31`, fin de semana=`96`, todos=`127`. CHECK `BETWEEN 0 AND 127`.

**Helper UI obligatorio:** `frontend/js/dias-semana.js` (vanilla) o `web-app/src/lib/diasSemana.ts` (React) con `serialize/deserialize/togglearDia/format`. `format(31)`→`Lun a Vie`, `format(96)`→`Sab y Dom`, `format(127)`→`Todos los dias`.

### Lógica `disponibilidad_efectiva(db, tipo_recurso, id_recurso, fecha)`

Resuelve los rangos horarios efectivos para una fecha aplicando bitmask `dias_semana` + ventana `vigente_desde/hasta`. **Desde 2026-05-28 además resta feriados y novedades de agentes** (helpers `_es_feriado`, `_bloqueos_novedades_agente`, `_restar_intervalos` en `services/agenda.py`): día feriado (`agenda_feriado`) → `[]`; novedad de agente (`agente_novedad`) total → `[]`, parcial → recorta el rango. La versión `_batch` (la que usan `/calendario` y `/semana`) lo hace en 2 queries extra para no romper la perf §27. Para espacio atendido, las novedades de cada agente vinculado ya se restan al armar la unión. Para `tipo_recurso='espacio'`:
- **Desatendido:** horario propio del espacio.
- **Atendido:** intersecta el horario del espacio con la **unión** de horarios de los agentes vinculados activos. Sin horario propio → la unión sola. Sin agentes vinculados → `[]` (la mig 40 NO enforce "atendido ⇒ ≥1 agente"; síntoma: grilla toda gris).

`_merge_rangos()` une rangos solapados/contiguos. **Quirk:** cast inline `(:f)::date` — asyncpg pasa DATE como `unknown` y Postgres no resuelve `EXTRACT(ISODOW FROM ...)` sin el cast. Ver [[feedback_asyncpg_extract_cast_date]].

**Scope por subárea del supervisor:** `/calendario` y `/semana` aceptan `scope_subarea_propia`. Si `true`, filtra recursos a la subárea del usuario (`usuarios → agentes.id_subarea`). **Admin (nivel 1) NO se scopea.** **Fail-open** si no se puede resolver la subárea. La pill "Equipos·OT" lo manda automáticamente. Helper `_resolver_scope_subarea` en `agenda_v2.py`: `id_subarea` explícito > scope propio > None.

### Sistemas de auditoría coexistentes

Dos sistemas con vocabularios distintos — **no unificar sin decisión explícita**:
- `reclamo_historial` (Reclamos + OT): cambios de estado y notas custom, append-only.
- `agenda_audit_log` (Agenda): `entidad` ∈ {evento,ocupacion,reserva} con `accion` ∈ {crear,modificar,cancelar,asignar} y diffs JSONB.

### Verbos HTTP del router agenda_v2 (referencia obligatoria)

Mezclan PUT con PATCH. Antes de scriptear un smoke o codear un cliente, `grep "@router\." backend/app/api/routes/agenda_v2.py` para confirmar.

| Acción | Verbo | Path |
|---|---|---|
| Crear / Editar full / Cancelar / Eliminar evento | POST / PUT / **PATCH** `/cancelar` / DELETE | `/eventos`, `/eventos/{id}` |
| Asignar / Quitar encargado | POST / DELETE | `/eventos/{id}/encargados[/{id_ee}]` |
| Crear reserva | POST | `/eventos/{id}/reservas` |
| Marcar asistió / Cancelar reserva | **PATCH** | `/reservas/{id}/asistio`, `/reservas/{id}/cancelar` |
| Acreditar por QR | **POST** | `/reservas/acreditar-qr` |
| Crear / Editar / Cancelar ocupación | POST / PUT / DELETE | `/ocupaciones[/{id}]` |
| Calendario día / mes / semana | GET | `/calendario` (NO `/calendario/dia`), `/mes`, `/semana?desde=&dias=` |
| Conflictos / Resolver | GET / **PATCH** | `/conflictos?resuelto=false`, `/conflictos/{id}/resolver` |
| Recurso | GET | `/recurso/{tipo_recurso}/{id_recurso}` |
| Conteos de recursos por tipo (pills) | GET | `/recursos/conteos?id_municipio=` |

**Router `agenda_espacios.py`** (`/api/v1/agenda/espacios`): GET listado (filtros `atendido`/`q`), POST, GET `/{id}` (con `agentes_vinculados` + `cant_agentes`), PUT, DELETE (soft + cascade N:M), GET/POST/DELETE `/{id}/agentes[/{id_ea}]`.
**Router `agenda_disponibilidad.py`** (`/api/v1/agenda/disponibilidad`): GET (filtros tipo/id), POST, PUT `/{id}`, DELETE `/{id}` (soft), GET `/efectiva?tipo_recurso=&id_recurso=&fecha=`.
Permisos: `nivel_acceso <= 2` muta; cualquier autenticado lee.

Smoke reproducible: `smoke_agenda.ps1` (raíz), 15 endpoints clave.

### QR físico de reservas

`evento_reservas.qr_codigo` es un **identificador opaco** (`EVT{id}-RES{id}-{ts}`, generado por `services/agenda.py::generar_qr_codigo`), no una URL. El operador lo escanea y acredita vía `POST /api/v1/agenda/reservas/acreditar-qr` con body `{qr_codigo}` → marca `asistio`. 404 si no es reserva activa, 409 si cancelada. Registrado **antes** que `/reservas/{id}/...` (anti-greedy). UI: sección "Acreditar por QR" en `ReservaModal.tsx`. El PNG se renderiza solo en cliente (`QRDisplay.tsx`, lib `qrcode` ~26KB) — el backend solo genera el string.

### Performance — patrón batch (optimización 2026-05-14)

Con 84 agentes en prod, los endpoints B1 originales eran inusables (`/calendario` 23s→2.2s, `/semana` 7d timeout→2.6s). El patrón que lo arregló:

1. **`disponibilidad_efectiva_batch(session, recursos, fechas)`** — 2 queries totales (`WHERE tipo=ANY AND id=ANY`), bitmask/vigencia/intersección resueltos en Python. La singular `disponibilidad_efectiva` queda para `/disponibilidad/efectiva` (compat retro).
2. **`_eventos_del_rango(db, fd, fh, mun)`** — 1 query base + 1 bulk de encargados. `_eventos_del_dia` queda como wrapper.
3. `/calendario` y `/semana` llaman a los batch. Compat retro verificado byte-a-byte.

**Latencia base Railway↔Supabase ~2-3s** con JOINs sobre 84 filas — piso físico sin tocar arquitectura. Ver [[reference_agenda_latencia_base_railway_supabase]]. Patrón generalizable para loops N×M: [[feedback_patron_batch_helper_singular_wrapper]].

**Quirk de clave:** `disponibilidad_por_recurso` en `/semana` usa formato `"{tipo}:{id}"` con dos puntos. Ver [[reference_agenda_semana_disponibilidad_key]].

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

## 30. Permisos por módulo

§3 define `nivel_acceso ∈ {1=Admin, 2=Supervisor, 3=Operador, 4=Consultor}` — un rol único, jerárquico. Para control fino del tipo "Juan es supervisor pero solo de Reclamos, no debe ver Agenda ni Admin Tablas" se aplica el modelo híbrido descripto acá. **Implementado** en mig 38 (2026-05-12) + mig 44 (2026-05-14 separa `agenda`/`turnos`/`entradas`). Las subsecciones que mencionan "schema futuro" o "cuando se implemente" son textos heredados del diseño; el "Estado actual" al final de la sección es la referencia operativa.

### Modelo: nivel mínimo por módulo + override por usuario

Cada módulo declara su **nivel mínimo de acceso** (default). Si el `nivel_acceso` del usuario lo alcanza, ve el módulo. Adicionalmente, una tabla nueva `usuario_modulos` permite **override** explícito por usuario:

- Fila con `permitido = TRUE` → el usuario ve el módulo aunque su nivel sea más alto que el mínimo (otorga acceso).
- Fila con `permitido = FALSE` → el usuario NO ve el módulo aunque su nivel sí lo permitiría (bloquea acceso).
- Sin fila → cae al default por nivel.

### Implementación (mig 38 + 44, local + prod)

Tablas `modulos` (catálogo: `modulo_codigo` PK, `nombre`, `descripcion`, `min_nivel_acceso` SMALLINT default 4) + `usuario_modulos` (override por usuario: `(id_usuario, modulo_codigo)` UNIQUE, `permitido` BOOL, §10). Catálogo actual — 10 módulos:

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

**Backend (`core/auth.py`):** `modulos_permitidos(db, id_usuario, nivel) -> list[str]` (defaults por nivel + overrides) · `require_modulo(modulo)` dependency factory (devuelve `current_user`, 403 si falta). `POST /auth/login` y `GET /auth/me` incluyen `modulos_permitidos`.

**Endpoints (`admin_permisos.py`, `/api/v1/admin/permisos`):** GET `/modulos` · PUT `/modulos/{codigo}` (editar `min_nivel_acceso`) · GET `/usuarios/{id}/modulos` · PUT `/usuarios/{id}/modulos` (set bulk overrides). **Orden crítico**: `admin_permisos_router` ANTES de `admin_tablas_router` en `main.py` (sino `/{tabla}` greedy atrapa `/permisos/*` → 422 `int_parsing`, §5).

**Frontend vanilla (`menu.js`):** filtra items por `data-modulo` ∉ `modulos_permitidos`. **`data-modulo-fallback="cod1,cod2"`** (CSV): el item se muestra si CUALQUIER código (principal + fallback) está permitido — necesario cuando un bundle cubre varios sub-permisos (OT supervisor/agente/auditoría). Sin fallback, OT desaparecía para el operador (cazado 2026-05-12). Sesión vieja sin `modulos_permitidos` cacheado → refresca contra `/me`, fail-open en UI (el guard real está en backend).

**Frontend React (`localhost:5173`):** `ModuleManifest.moduloCodigo?: string` (lo usan agenda/turnos/entradas/padrones); `Sidebar.tsx` filtra, fail-open; `useAuthStore.refreshSession()` rehidrata desde `/me`.

> **TRAMPA DE SEGURIDAD recurrente:** que el sidebar oculte un módulo NO protege sus endpoints. `require_modulo` casi no se usa — la mayoría de routers aplican su nivel con helpers locales (`_require_gestion`, `_require_supervisor`). Hasta 2026-05-20 el router OT no chequeaba nivel y un operador con JWT creaba OT por curl (QA #2). **Antes de asumir "el router ya valida nivel", leé el handler.** Ver [[guard_nivel_endpoint_no_solo_ui]].

## 31. Limpieza de estilos legacy — CERRADA (2026-05-12)

DS v1.0 (`--z-*`, `.z-*`, `frontend/styles.css`, `frontend/menu.html`, `frontend/mainconfig.html`, `frontend/agenda.*`, `shell.html`) eliminado del repo. Los módulos vanilla cargan componentes `*-zaris` de `design-system/components/*.css` (§13). `admin_tablas.html` usa tokens DS directos (0 `var(--z-*)`, solo conserva `.z-header*` oculto en iframe + clases internas `.btn-primary`/`.field`/`.modal` a propósito, §15). **Cero deuda de estilos legacy.** Bitácora completa (pasos + tabla de equivalencias `--z-*`→DS, útil solo si reaparece un módulo vanilla) en `HISTORIAL_MIGRACIONES.md`.

## 32. Build de `web-app/dist/` y testing local del shell vanilla + bundle

> **Recetas operativas en la skill `win-quirks`** (`.claude/skills/win-quirks/`). Invocarla al buildear/commitear `web-app/dist/`, levantar servers locales (http.server/uvicorn/pnpm dev), correr psql, lanzar procesos detached con `Start-Process`, o diagnosticar redirects rotos bajo `/zaris-zge/`. Cubre los 14 quirks que rompen silenciosamente en Windows.

**Reglas que NO podés olvidar (las recetas para cumplirlas están en la skill):**
- Antes de commitear `dist/`: buildear modo prod (sin `VITE_API_BASE` en el shell) y verificar que apunte a Railway, no a `127.0.0.1`.
- `vite build` compila el WORKING TREE, no lo staged — commitear fuentes primero o stashear lo ajeno antes de rebuildear.
- El bundle standalone en prod debe redirigir al shell vanilla (script en `web-app/index.html` + whitelist en `menu.js`, §14). Nunca `window.location.href='/...'` absoluto desde el bundle (rompe bajo `/zaris-zge/`, [[feedback_redirect_iframe_subpath]]).

## 33. Módulos Turnos y Entradas

Dos módulos React que se apoyan en el sustrato de Agenda. Implementados al 2026-05-14 (backoffice completo). Ver §27 para el modelo de agenda subyacente.

### Turnos — los turnos cumplen PRESTACIONES (modelo mig 71)

Una **PRESTACIÓN** define recurso fijo + duración + clase. La reserva elige **prestación + slot**; el recurso ya viene determinado (ej. "Odontología por Dr. Pérez" vs "Odontología en Sala Municipal" = dos prestaciones). Un turno reserva un bloque de la disponibilidad efectiva del recurso de la prestación para un ciudadano. Estados: `reservado` → `cumplido` | `cancelado`.

**`tipo_prestacion`** (mig 71 renombró `tipo_servicio_turno`): `id_tipo_prestacion` PK + `nombre` + `duracion_min` + **`clase`** ∈ `{atencion, reserva_espacio}` + **`tipo_recurso`** ∈ `{agente, espacio}` + `id_agente`/`id_espacio` (FK, exactamente uno por CHECK `ck_tipo_prestacion_recurso` **NOT VALID**). CHECK `ck_tipo_prestacion_reserva_espacio`: `reserva_espacio` ⇒ `tipo_recurso='espacio'`. Los NOT VALID aplican a filas nuevas; el seed soft-deletea las viejas sin recurso ([[feedback_check_not_valid_se_evalua_al_update]]).

**El recurso se COPIA al turno al reservar** (`turnos.id_agente`/`id_espacio`, mig 70, CHECK `ck_turnos_recurso` exactamente uno) → turno autocontenido aunque la prestación cambie después. Ocupación espejo `tipo_recurso='agente'|'espacio'`. `TurnoOut` expone `recurso_tipo`/`recurso_nombre`/`prestacion_nombre`/`prestacion_clase`.

**Switch global `turnos_respeta_disponibilidad`** (`configuracion_general`, mig 69, default `true`): con `true` el alta (backoffice + autoservicio) exige caer en la disponibilidad efectiva (horario − feriados − novedades §27); `false` = modo libre. Helper `services/agenda.py::turnos_respeta_disponibilidad(db)`. El anti-solapamiento contra `ocupaciones` siempre aplica. Ver [[project_turnos_disponibilidad_novedades_feriados]].

**DB** (migs 45 + 46 autoservicio + 69 switch/novedades + 70 recurso polimórfico + 71 prestaciones, local + prod): `tipo_prestacion` (catálogo §10, gestionado desde tab "Prestaciones" React **NO admin_tablas** — polimorfismo + form condicional) · `turnos` (transaccional §10, FKs ciudadanos/agentes-null/espacios-null/tipo_prestacion, `estado` CHECK, `id_ocupacion` → espejo). Seed `backend/seed_turnos_demo.py` (idempotente).

**Ocupación espejo:** cada turno mantiene fila en `ocupaciones` (tipo='turno') para aparecer en la grilla de Agenda. `routes/turnos.py` sincroniza:
- crear turno → resuelve recurso+duración de la prestación → INSERT turno (recurso copiado) + INSERT ocupación espejo
- reprogramar → UPDATE ambas; si cambia la prestación re-resuelve recurso+duración
- cumplir → UPDATE turno.estado (la ocupación se mantiene como histórico en la grilla) + observación opcional **anexada** a `observaciones` + dispara la encuesta de turnos (§42, best-effort tras el commit)
- cancelar → UPDATE turno.estado + soft-delete de la ocupación espejo (libera la grilla)

**Scoping por nivel (sesión 2026-05-28, backend, no evadible por curl):** `GET /turnos` y `GET /turnos/{id}` aplican `_scope_turnos_para_usuario`. **Nivel ≤ 2 (admin/supervisor) ve TODO**; **nivel 3-4 (operador/consultor) ve solo** los turnos donde es el agente involucrado (`t.id_agente` = su `agentes.id_agente`) **O** los de un lugar de atención (espacio) de su misma subárea (`t.id_espacio IN (espacios_agenda WHERE id_subarea = su_subarea)`). El usuario sin fila en `agentes` no ve nada propio. Los filtros por query (`id_agente`/`id_espacio`) se combinan con el scope (el operador no puede ver fuera de su alcance pidiendo otro id). **OJO:** los lugares de atención necesitan `id_subarea` cargada (Agenda → Config → Espacios) para que el operador vea turnos de espacio; sin eso solo ve sus turnos como agente. `get_current_user` NO trae `id_agente`/`id_subarea` — se resuelven con un SELECT puntual a `agentes` (patrón espejo de `resolver_agente_desde_usuario` §35).

**Endpoints (`/api/v1/turnos`):**
- **Prestaciones (CRUD):** GET `/prestaciones` (filtros `clase`/`q`; lectura: cualquier autenticado), GET `/prestaciones/{id}`, POST `/prestaciones`, PUT `/prestaciones/{id}`, DELETE `/prestaciones/{id}` (soft). **Mutar prestaciones exige nivel ≤ 2 (supervisor/admin)** — helper `_require_supervisor`. Reemplaza al viejo `GET /catalogo/tipos-servicio`.
- **Turnos:** GET `` (filtros estado/agente/espacio/ciudadano/prestación/fecha; **scopeado por nivel**, ver arriba), GET `/{id}` (mismo scope), POST `` (recurso+duración salen de la prestación; calcula `hora_fin`), PUT `/{id}` (reprograma — solo `reservado`), PATCH `/{id}/cumplir` (body opcional `{observaciones}` → schema `TurnoCumplir`; anexa la observación y dispara la encuesta), PATCH `/{id}/cancelar`. Mutar turnos: nivel ≤ 3.

**Frontend:** `web-app/src/modules/turnos/` — `TurnosLayout` con **4 tabs** (**Turnos** = lista/alta/reprogramar/cumplir/cancelar; **Agenda** = grilla día/semana solo-turnos, ver abajo; **Atendidos** = turnos cumplidos + export PDF; **Prestaciones** = ABM del catálogo, **visible solo nivel ≤ 2** vía `hasPermission(2)`). `TurnoFormModal` elige prestación (sin selector de recurso, read-only de la prestación). `PrestacionFormModal` tiene form condicional: clase `atencion` → toggle agente/espacio; `reserva_espacio` → solo espacio. **`CumplirTurnoModal`** (reemplaza el ConfirmModal de cumplir): textarea de observación opcional + aviso de que dispara la encuesta; llama a `useCumplirTurno({id_turno, observaciones?})`. **`pages/Atendidos.tsx`**: lista `useTurnos({estado:'cumplido'})` (ya scopeada por backend), filtros por **agente + lugar solo para `hasPermission(2)`** (el operador no los ve), **export PDF** vía `lib/exportPdf.ts` (`jspdf` + `jspdf-autotable`, encabezado ZARIS naranja `#f54e00`). Reusa `Modal`, `ConfirmModal`, `RecursoPicker`, `useEspacios` de Agenda.
- **Tab "Agenda" (`pages/AgendaTurnos.tsx`):** grilla PROPIA día/semana sobre `GET /turnos` (NO reusa la grilla Gantt del módulo Agenda; ver §42). Hereda el scoping por nivel/subárea del backend. Excluye cancelados. El CTA **"Ver en agenda"** del Overview navega acá (`navigate('/turnos/agenda')`), NO al módulo Agenda completo.
- **Filtros Prestación / Atiende(agente|lugar) / Ciudadano** en Turnos (`Overview`) y Agenda, vía helper compartido `lib/turnoFiltros.tsx` — opciones derivadas de los turnos cargados (no catálogos completos, §23), client-side, combinables, con botón Limpiar.

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
| Listar prestaciones publicables | GET | `/prestaciones` (activas con recurso que tenga disponibilidad) |
| Slots libres | GET | `/slots?id_tipo_prestacion=&fecha_desde=&dias=` |
| Reservar turno | POST | `/reservar` (body sin recurso — lo trae la prestación) |
| Consultar turno por token | GET | `/turno/{token_turno}` |
| Cancelar turno por token | DELETE | `/turno/{token_turno}` |

> **Orden de routers crítico (main.py):** `turnos_publico_router` ANTES de `turnos_router` (sino `/turnos/publico/*` cae en `{id_turno}='publico'` → 422, §5). Mig 71 eliminó `/tipos-servicio`, `/agentes`, `/recursos` públicos (el recurso lo trae la prestación).

**Slots (`_slots_libres_recurso`):** recurso de la prestación → `disponibilidad_efectiva(tipo, id, fecha)` partido en bloques de `duracion_min` (descarta el último incompleto), filtrando solapamientos con `ocupaciones`. **POST /reservar**: valida slot dentro de disponibilidad + sin solape, busca/crea ciudadano por DNI (`buscar_o_crear_ciudadano_por_dni`), rechaza si ya tiene turno no-cancelado ese día, crea turno `origen='autoservicio'` + ocupación espejo, devuelve `token_turno`.

**Frontend público (`web-app/src/autoservicio/`):** `TurnosPage.tsx` (`/turnos-autoservicio`, 3 pasos prestación→slot→datos) · `MiTurnoPage.tsx` (`/turno/:tokenTurno`, ver/cancelar). El backoffice muestra banner con el link público + copiar.

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

### Mesa Auditoría — admin (nivel 1) bypassea `es_auditor`

Desde 2026-05-19: el check `agentes.es_auditor=TRUE` en `GET /api/v1/ot/auditor/me` se saltea cuando `current_user.nivel_acceso <= 1`. Admin por definición tiene acceso total al módulo y no necesita el flag explícito en DB. La regla "no auditar lo propio" se preserva via el filtro existente `(ot.id_agente IS NULL OR ot.id_agente = :id_agente)` del listado, que excluye las OTs operativas asignadas al mismo agente. Niveles 2-4 siguen requiriendo `es_auditor=TRUE` en su fila de `agentes`. El endpoint legacy `GET /mesa/auditoria?id_agente=` nunca chequeó `es_auditor` (recibía el id por query), así que no necesitó cambio.

### Guard de nivel — Mesa Supervisor y asignación de OT exigen nivel ≤ 2 (hallazgo QA #2, 2026-05-20)

Antes, los endpoints de asignación de OT solo usaban `get_current_user` sin chequear nivel — un Operador (nivel 3) podía crear/asignar OT desde la Mesa Supervisor. Fix:

- **Backend:** helper `_require_supervisor(current_user)` en `ordenes_trabajo.py` (403 si `nivel_acceso > 2`), aplicado como primera línea de `GET /ot/mesa/supervisor`, `POST /ot`, `POST /ot/con-agenda`. `PUT /ot/{id}/reasignar` ya lo tenía inline. Espeja `modulos.ot_supervisor.min_nivel_acceso = 2`.
- **Frontend (bundle React):** gate `WrapNivel` en `web-app/src/modules/ot/index.tsx` — `/ot/supervisor` y `/ot/auditoria` exigen nivel ≤ 2; el operador ve "Acceso restringido". El redirect de `/ot` (sin sub-ruta) es por rol: nivel ≤ 2 → `/ot/supervisor`, resto → `/ot/agente`.
- **Sidebar vanilla:** el link OT en `index.html` apunta a `#/ot` (no `#/ot/supervisor`) para que el redirect por rol decida la mesa. Conserva `data-modulo-fallback="ot_agente,ot_auditoria"` para que el item siga visible al operador (que aterriza en su Mesa de Agente).

Defensa en profundidad: aunque un operador deep-linkee a `/ot/supervisor`, el frontend muestra el mensaje y el backend rechaza con 403. Ver memoria [[guard_nivel_endpoint_no_solo_ui]].

### Adjuntos de OT — evidencia del trabajo (hallazgo QA Royman #4, 2026-05-20)

El #4 que quedó diferido en el commit `2110263`. Las OT ahora tienen adjuntos propios (fotos de la evidencia del trabajo: bache reparado, luminaria cambiada). **Independientes de los adjuntos del reclamo** (§26): el drawer muestra ambas secciones — "ADJUNTOS" (del reclamo) y "EVIDENCIA DE LA OT" (de la OT resaltada).

- **Tabla `ot_adjuntos`** (mig 54, ver §21): espejo de `reclamo_adjuntos` pero FK a `ordenes_trabajo(id_ot) ON DELETE CASCADE`. Reusa el bucket privado `reclamos-adjuntos` (paths bajo `ot/{id_ot}/{uuid}.{ext}`). Modelo `OrdenTrabajoAdjunto` en `backend/app/models/reclamos.py`.
- **Router `ot_adjuntos.py`** (prefix `/api/v1/ot/{id_ot}/adjuntos`): mismo flujo que reclamo_adjuntos — `POST /upload-url` → PUT directo al storage → `POST /{id_adj}/confirm`; `GET ""` (URLs firmadas TTL 1h); `DELETE /{id_adj}` (soft-delete + remove del bucket). Reusa `app/core/storage.py` (que ya aceptaba `bucket`/`path` arbitrarios).
- **Registrado en `main.py` ANTES de `ot_router`** (§5): `/ot/{id_ot}/adjuntos` no debe ser atrapado por el `/{id_ot}` greedy del router de OT.
- **Permiso SUBIR/BORRAR**: agente asignado a la OT (`ordenes_trabajo.id_agente` = `agentes.id_agente` del usuario, resuelto vía `agentes.id_usuario`) **o** nivel ≤ 2 (admin/supervisor). Helper `_require_puede_gestionar`. **VER (listar) lo puede cualquier autenticado** — todas las mesas ven la evidencia.
- **Frontend**: `web-app/src/modules/ot/` → `api/otAdjuntosApi.ts`, `hooks/useOTAdjuntos.ts`, `components/UploadAdjuntosOTPanel.tsx` (clon del de reclamos apuntando a la API de OT + queryKey `['ot','adjuntos',idOt]`). La sección vive en `OTDetalleDrawer.tsx` (`OTAdjuntosSection`), se muestra cuando `idOTResaltada != null`. El drawer recibe prop `puedeGestionarAdjuntos`: AgenteView lo pasa `true` si `scope ∈ {'mia','disponible_equipo'}`; Supervisor/Auditoría lo pasan `user.nivel_acceso <= 2`. El gate solo gobierna la UI — el backend igual hace cumplir el guard (un operador no-asignado recibe 403).
- **Verificado end-to-end (2026-05-20)**: smoke backend 5/5 (agente asignado sube OK, no-asignado 403, admin OK, listar, OT inexistente 404) + verificación visual en navegador (subir PNG real al storage Supabase → galería → borrar → vuelve a "Sin evidencia adjunta").

## 35. Módulo Trámites / Expedientes

Expedientes administrativos tipo "ventanilla" (entrada → circuito interno → resolución). Multi-área, firmas digitales, numeración correlativa por tipo. Frontend React `web-app/src/modules/tramites/`, backend `routes/tramites.py` + `routes/tramites_admin.py` + `services/tramites/`. **Bitácora de fases (1/2/3), smokes, verificaciones E2E y repasos de Roy en `HISTORIAL_MIGRACIONES.md`.**

### Filosofía de diseño

- **Catálogo / instancia separados**: catálogo (`tipo_tramite`, `tipo_tramite_version`, `_campo`, `_estado`, `_transicion`, `_documento_requerido`) define el FSM y los campos. Instancias (`tramite`, `tramite_movimiento`, `tramite_documento`, `tramite_firma`, `tramite_relacion`) son los expedientes reales.
- **Versionado del circuito**: un trámite queda atado a la versión publicada al crearse — cambiar el circuito NO altera trámites en curso. `tipo_tramite_version.publicada=TRUE` = activa.
- **FK circular diferida**: `tipo_tramite.id_version_publicada ↔ tipo_tramite_version.id_tipo_tramite` con `DEFERRABLE INITIALLY DEFERRED`.
- **Numeración atómica**: `tipo_tramite_numerador` PK `(id_tipo_tramite, anio, id_municipio)` con `INSERT ... ON CONFLICT DO UPDATE SET ultimo_numero+1 RETURNING`. Formato `{prefijo}-{cod_muni}-{anio}-{correlativo}` → `POD-LPL-2026-0001`.
- **Ledger append-only**: `tramite_movimiento` (UNIQUE `(id_tramite, orden_secuencial)`); cada acción es fila nueva, nunca UPDATE.
- **Iniciador polimórfico**: `iniciador_tipo ∈ {ciudadano, empresa, area_interna}` + CHECK que exige exactamente una de `{id_ciudadano_iniciador, id_empresa_iniciadora, id_subarea_iniciadora}`.
- **Destinatario polimórfico**: `destinatario_actual_tipo ∈ {subarea, equipo, agente}` + CHECK `ck_tramite_destinatario` con 4 ramas (NULL/subarea/equipo/agente), exactamente una de `{id_subarea_actual, id_equipo_actual, id_agente_actual}`. **`agente` = destinatario directo a una persona** (mig 66): aparece en SU bandeja, nadie más lo toma. **CRÍTICO: toda ruta que cambie destinatario o lleve a estado final DEBE setear las 3 FKs coherente con el tipo, o viola el CHECK** (cazado en `transicionar_tramite` que omitía `id_agente_actual`). Ver [[project_tramites_destinatario_agente_y_mi_bandeja]].

### Tablas

Catálogo (7): `tipo_tramite` (código único, prefijo, iniciadores permitidos), `tipo_tramite_version`, `tipo_tramite_campo` (tipo_dato, orden, opciones_jsonb), `tipo_tramite_estado` (codigo, etiqueta, color, es_inicial/es_final), `tipo_tramite_transicion` (origen→destino, quien_puede_jsonb, requiere_comentario/adjunto, **tipo_accion** aprobar/rechazar/derivar/avanzar/otro mig 68, **mensaje_iniciador** mig 68, **notifica_iniciador**), `tipo_tramite_documento_requerido` (obligatorio, formatos, requiere_firma, **cantidad_max_archivos** 1-20 mig 68), `tipo_tramite_numerador`.

Instancias (5): `tramite` (`numero_expediente` único, polimorfismo iniciador+destinatario, `id_agente_tomado_por`), `tramite_movimiento`, `tramite_documento` (storage_path, sha256, mime_type, size_bytes), `tramite_firma` (polimórfico agente/subarea/equipo), `tramite_relacion`.

Aprobaciones por etapa (visados, mig 73, separadas de `tramite_firma`): `tipo_tramite_aprobacion_requerida` (catálogo versionado: estado/etapa + aprobador polimórfico subarea|equipo|agente + `bloqueante` default TRUE) y `tramite_aprobacion` (instancia: estado pendiente|aprobada|rechazada, UNIQUE `(id_tramite, id_requisito)`). Las bloqueantes impiden avanzar; el rechazo NO transiciona (deja el trámite trabado con motivo visible). **Circuito de subsanación (2026-06-01):** una bloqueante pendiente/rechazada bloquea TODAS las transiciones salientes **salvo las de `tipo_accion='derivar'`** (devolución a subsanación) — sin esa excepción un visado rechazado dejaba el trámite trabado sin salida. Y al **re-entrar** a la etapa del visado (reenvío post-subsanación) los visados `rechazada` **se re-pendientizan solos** (`svc_aprob.rependientizar_rechazadas_de_estado`, limpia comentario/doc/quién/cuándo + movimiento `aprobacion` "Visados reabiertos"). Ambos en `transicionar_tramite`. Ver [[project_tramites_aprobaciones_por_etapa]].

Todas siguen §10. **El catálogo `tipo_tramite` NO tiene `id_usuario_alta`** ([[reference_tipo_tramite_sin_usuario_alta]]); la auditoría de usuario vive solo en las instancias. `es_sistema` (mig 56) distingue seed (TRUE) de custom (FALSE).

### Migraciones (todas local + prod)
47 catálogos · 48 instancias · 49 índices · 50 auditoría en instancias · 56 `es_sistema` · 66 destinatario=agente · 68 tipo_accion/mensaje_iniciador/cantidad_max_archivos · 73 aprobaciones por etapa · 74 `resultado` (Fase 1 retención) · 75 retención Fases 2-5 (`retencion_nunca_depurar`, `fecha_archivado`/`archivado_motivo`, `binario_purgado`/`fecha_purga_binario`, ledger `archivado_inactividad`/`purga_binario` + claves config en `75b`). Detalle en HISTORIAL/§21.

### Seeds
`backend/seed_tramites.py` (idempotente): 7 subáreas del circuito, 9 tipos con versión publicada v1 (poda-arbol POD, pedido-informe INF, licencia-ordinaria LIC, habilitacion-comercial HAB, cambio-domicilio-comercial CDC, transferencia-habilitacion THC, inspeccion-bromatologica BRO, cartel-publicitario CAR, recurso-administrativo REA) + ~21 trámites demo. `$env:ENV_FILE=".env.local"; python seed_tramites.py`.

### Endpoints (`/api/v1/tramites`, JWT a nivel router)

Registrado **ANTES de `admin_tablas_router`** (evita `/{tabla}` greedy, §5). Las rutas de segmento fijo (`/mi-bandeja`, `/destinatarios`, `/tipos`) van **ANTES de `/{numero_o_id}`** (param greedy).

| Verbo | Path | Notas |
|---|---|---|
| GET | `/tipos` · `/tipos/{id}` | Tipos activos publicados; detalle con campos/estados/transiciones/docs **a nivel raíz** (`version` es solo metadata) |
| GET | `` (bandeja) | Filtros estado/tipo/iniciador/destinatario/numero/q/fechas; `X-Total-Count` |
| GET | `/{numero_o_id}` (+ `/movimientos`, `/documentos`) | Acepta `POD-LPL-2026-0001` o id int |
| GET | `/mi-bandeja` | Colectivos del agente resueltos server-side (subárea + equipos/mesas + asignado a mí + tomado por mí). El `GET ""` general NO sirve (filtra un destinatario único). Filtros estado/tipo/sin_tomar/q |
| GET | `/destinatarios?q=` | Opciones de pase agrupadas (agentes/equipos/subáreas). Quirk: `CAST(:q AS text) IS NULL` (sino `AmbiguousParameterError`) |
| POST | `` | Crear (201). Numerador atómico, estado inicial, 2 movimientos. **Body: `iniciador` ANIDADO** `{tipo, id_ciudadano, id_empresa, id_subarea, id_ciudadano_representante}` + `datos` (NO `datos_jsonb`) + `id_municipio`; la versión se deriva del tipo |
| POST | `/{ref}/tomar` · `/liberar` · `/transicionar` · `/pase` · `/comentar` · `/relacionar` + GET `/transiciones-permitidas` | `tomar`=`SELECT FOR UPDATE`. `pase`/transición-final auto-liberan toma. `transicionar` valida `quien_puede_jsonb` + `requiere_adjunto` + guard de aprobaciones bloqueantes (422). `relacionar` ordena ids para UNIQUE |
| POST/GET | `/{ref}/documentos` (+ `/{id}/contenido`, `/firmar`, `/rechazar-firma`) | Upload multipart; SHA256 sobre bytes; firma captura ip/user_agent/hash. `contenido` solo auth por header (no `?token=`), fetch con `cache:'no-store'` |
| POST | `/{ref}/aprobaciones/{id_aprob}/resolver` | Aprobar/rechazar visado de etapa (mig 73) |

Admin (`/api/v1/admin/tramites`, nivel ≤ 2, registrado antes de admin_tablas): CRUD de tipos/versiones/campos/estados/transiciones/docs-requeridos/aprobaciones-requeridas (~20 endpoints) + `GET /tipos` admin (lista TODOS: publicados+borradores+sin-estados, con `es_sistema` y `estado_version`). Versionado: v1 editable in-place sin trámites; con trámites fuerza v2 borrador (copia estructura via `versionado.crear_borrador_desde_publicada`). Publicar valida 1 inicial + ≥1 final.

### Servicios (`backend/app/services/tramites/`)
`numerador.py` (`proximo_numero` atómico, `formatear_numero`) · `auth.py` (`resolver_agente_desde_usuario` → `{id_agente, id_subarea, ids_equipos, id_municipio, nivel_acceso}`, `es_admin(nivel)=nivel<=2`) · `autorizacion.py` (`quien_puede_actuar` OR entre subareas/equipos/iniciador/roles) · `movimientos.py` (append-only, `COALESCE(MAX,0)+1`) · `creacion.py` (`validar_campos_contra_tipo`, `resolver_iniciador`, `determinar_destinatario_inicial`) · `documentos.py` (Supabase Storage + SHA256) · `firmas.py` (polimórfico, captura evidencia) · `versionado.py` · `aprobaciones.py` · `retencion.py` (mig 75: `archivar_inactivos` + `purgar_binarios` dry-run, helpers de config; lo dispara `routes/tramites_mantenimiento.py` vía cron).

### Reglas operativas críticas
- Toda mutación: transacción + `SELECT FOR UPDATE` sobre `tramite`.
- `requiere_adjunto` cuenta `tramite_documento.activo` con `fecha_alta >= fecha_entrada_estado_actual`.
- **Firma de documentos (`firmas.py::agente_puede_firmar`, política del municipio):** admin (n1) firma siempre; **operador/consultor (n≥3) NUNCA**; supervisor (n2) solo si pertenece al colectivo asignado a la firma (agente/subárea/equipo); firma SIN asignación → **fail-CLOSED** (solo admin). Era fail-open antes (cualquiera firmaba). Frontend `ListaDocumentos.tsx` gatea los botones firmar/rechazar a `hasPermission(2)` — el backend sigue siendo la fuente de verdad (403 al resto).
- **`GET /tramites/mi-bandeja` filtra municipio tolerando NULL:** `(:mun IS NULL OR t.id_municipio = :mun OR t.id_municipio IS NULL)`. Filtrar con `= :mun` estricto vaciaba la bandeja en silencio cuando `agente.id_municipio` era NULL (drift de datos; `= NULL` no matchea nada en SQL). Si agregás un filtro por municipio sobre datos que pueden venir NULL, tolerá NULL (§38 mono-municipio). Ver [[feedback_filtro_igual_null_vacia_listado]].

### Marca `resultado` del trámite + política de retención de documentos (migs 74 + 75, COMPLETA 2026-06-01)
`tramite.resultado` (`pendiente|aprobado|rechazado`, CHECK `ck_tramite_resultado`) es una marca **paralela al estado FSM**, NO un estado: el estado es del flujo del circuito, el resultado dice cómo concluyó el trámite (se consulta junto al estado, "archivado, aprobado/rechazado"). Endpoint `POST /tramites/{ref}/resultado` (nivel ≤ 2, `ResultadoIn`) + movimiento `'resultado'` en el ledger. Expuesto en `TramiteDetalleOut.resultado` — **setearlo en los DOS builders del detalle** (`_tramite_detalle_out` + el GET handler `detalle_tramite`, [[feedback_columna_nueva_auditar_todos_los_select]]). Frontend: `ResultadoChip` (chip + dropdown, solo nivel ≤2).
- **Política de retención (Fases 2-5, mig 75 — toda implementada).** El **registro** de cada documento (metadatos + `hash_sha256`) NUNCA se borra; solo se depura el **binario físico** del bucket por antigüedad, marcando `tramite_documento.binario_purgado=TRUE` + `fecha_purga_binario`. Plazos **configurables** en `configuracion_general` (Config → Sistema §41): `retencion_dias_aprobado` (3650 = 10 años), `retencion_dias_rechazado` (365 = 1 año), `tramite_inactividad_dias` (180), `tramite_purga_binarios_real` (`false` = dry-run, red de seguridad — arranca apagado).
  - **Fase 2 (excepción por tipo):** `tipo_tramite.retencion_nunca_depurar` (BOOL). Si `TRUE`, los binarios de ese tipo nunca se purgan (ej. Habilitaciones). Editable en el builder de tipos (`NuevoTipoModal`/`EditarTipoModal`, checkbox) + visible en el detalle del tipo.
  - **Fase 3 (auto-archivado):** trámite sin movimiento ≥ `tramite_inactividad_dias` y NO en estado final → `fecha_archivado=NOW()`, `archivado_motivo='inactividad'`, `resultado='rechazado'`, movimiento `'archivado_inactividad'`. El archivado es una marca de mantenimiento **paralela al estado del FSM** (no fuerza un estado "archivado" que el circuito puede no tener), igual que `resultado`.
  - **Fase 4 (purga):** documentos de trámites ya concluidos (archivados o `resultado≠pendiente`), vencido el plazo según resultado, EXCEPTO tipos con `retencion_nunca_depurar`. Plazo contado desde `COALESCE(fecha_archivado, último movimiento, fecha_alta)`. **Dry-run por default** (solo reporta; el switch `tramite_purga_binarios_real='true'` la activa). Borra del bucket + marca `binario_purgado` + movimiento `'purga_binario'`. `GET /documentos/{id}/contenido` devuelve **410 Gone** si el binario fue purgado (no 404); el front muestra "Archivo depurado" en vez del botón descargar.
  - **Fase 5 (cron):** endpoint `POST /api/v1/tramites/mantenimiento/ejecutar` (router `tramites_mantenimiento.py`, SIN guard JWT — auth por header `X-Dispatcher-Token`, mismo `DISPATCHER_TOKEN` de Railway que encuestas §42; **registrado ANTES de `tramites_router`** por el `/{numero_o_id}` greedy §5). Corre `archivar_inactivos` + `purgar_binarios`. Query param `forzar_purga_real=true` ignora el dry-run para una corrida controlada. Disparado diario por `.github/workflows/tramites-mantenimiento.yml` (04:10 UTC). Motores en `services/tramites/retencion.py`. Movimientos del cron usan `id_agente_iniciador` del trámite (la columna es NOT NULL; no hay "agente sistema") + `id_usuario=None`.
  - **Quirk asyncpg:** `make_interval(days => CAST(:p AS integer))`; dentro de un `CASE` castear **cada bind param** (`CASE WHEN ... THEN CAST(:da AS integer) ELSE CAST(:dr AS integer) END`), no el CASE entero (sino asyncpg infiere `text` y falla). Familia de [[feedback_asyncpg_extract_cast_date]].
- **Storage = Supabase Storage** (bucket privado `tramites-documentos`, paths `tramites/{anio}/{expediente}/{uuid}.{ext}`). Backend recibe multipart, calcula SHA256, PUT con service_role (`app/core/storage.py`, reusado por Reclamos §26 y OT §34). `verificar_integridad_documento` recomputa SHA256 descargando del bucket. Ver [[project_tramites_storage_efimero_deuda]].
- **Notificaciones**: in-app + email cuando un trámite entra a una bandeja (creación/pase/transición que cambia destinatario), comentario al tomador, estado final al iniciador (incluye email a ciudadano/empresa con `mensaje_iniciador` custom mig 68 si `notifica_iniciador`), firma pendiente. Ver §51-notificaciones (mig 51) y [[project_notificaciones_in_app_email]]. La campana vive en el shell vanilla (`menu.js`) porque el TopBar React se auto-oculta en iframe ([[feedback_features_topbar_react_invisibles_en_prod]]).
- **Flujo de tipos custom**: nace en borrador, NO disponible en "Nuevo trámite" hasta tener estado inicial+final y "Publicar y habilitar". El alta lista solo publicados.

### Quirks (vigentes)
- **JSONB en asyncpg**: NO `:v::jsonb` ni `dict` en prepared statements de SQLAlchemy `text()`. Usar `VALUES (CAST(:v AS jsonb))` con `json.dumps(val) if val is not None else None`. (El `::jsonb` sí funciona en psql y en `asyncpg_conn.execute()` directo, §5.)
- **Mapeo de params iniciador**: `**iniciador_fks` sobre el dict del INSERT falla (claves largas ≠ `:alias`). Mapear explícito ([[feedback_mapeo_alias_sql_vs_claves_dict]]).
- **`tramite` no tiene `id_tipo_tramite` directo** — va via `id_tipo_tramite_version → tipo_tramite_version → tipo_tramite` ([[reference_tramite_no_tiene_id_tipo_tramite_directo]]).
- **`opciones_jsonb` de seeds viejos** puede venir como `{opciones:[...]}` en vez de `[...]` — normalizar antes de `.map` ([[feedback_normalizar_jsonb_de_seeds_viejos]]).
- **Columna nueva del catálogo**: sumarla también a los SELECT de lista explícita de `detalle_version` (tramites_admin.py), no solo a migración/schema/INSERT — sino el endpoint la devuelve `undefined` silencioso ([[feedback_columna_nueva_auditar_todos_los_select]]).
- **VisorDocumento**: `react-pdf@10.4.1` + `pdfjs-dist@5.4.296` (pin exacto, [[feedback_react_pdf_pin_pdfjs_version]]).
- **Modal de carga larga** (`admin/modals/_modalShell.tsx`): body `flex:1; minHeight:0; overflowY:auto` (header fijo, body scrollea) + click-outside exige mousedown+mouseup sobre el overlay. Estilo inline no soporta `:disabled` → derivar el estilo condicionalmente (botones de orden).
- **Reorden de campos/docs** (`useReordenarCampo`/`useReordenarDocReq`): reasigna `orden` 1..N por posición (NO swap — los seeds tenían órdenes duplicados).

### Aprobaciones por etapa — COMPLETA en prod (2026-06-01, mig 73)
Backend + builder + detalle operativo, todo verificado E2E navegando en prod. **Frontend:** `components/PanelAprobaciones.tsx` (verde/rojo/gris + Aprobar/Rechazar con comentario + aviso de bloqueo) montado en `pages/DetalleTramite.tsx`; `resolverAprobacion` (lib/api.ts), `useResolverAprobacion` (hooks/useTramites.ts), `TramiteAprobacion` (en `tramites/types.ts`, NO `lib/types.ts`). El tab **"Aprobaciones" del builder** (`ConfigTramiteDetalle.tsx`) se configura desde la barra de tabs (estaba implementado pero faltaba el botón en la barra hasta el 2026-06-01). **Trap recurrente cazado:** el handler GET `/{numero_o_id}` arma su propio `TramiteDetalleOut` — al sumar `aprobaciones` hubo que tocarlo además de `_tramite_detalle_out` (helper de mutaciones); dos rutas construyen el mismo response ([[feedback_columna_nueva_auditar_todos_los_select]]). Modelo/flujo en [[project_tramites_aprobaciones_por_etapa]].

### Manuales
`docs/manual_tramites.html` (uso operativo) · `docs/manual_admin_tramites.html` (creación de tipos, admin). Vía módulo Guías §37.


## 36. Generación de manuales operativos (HTML autocontenidos)

> **Receta completa en la skill `generar-manual`** (`.claude/skills/generar-manual/`): setup Playwright, patrón de captura, convenciones del HTML, regenerar capturas tras cambio de UI, cleanup. Invocarla al crear/regenerar un `docs/manual_<modulo>.html`.

### Manuales actuales (al 2026-06-01)
`manual_reclamos.html` (Operador+, 10 caps) · `manual_ot.html` (Sup/Agente/Auditor, 9) · `manual_tramites.html` (Operador+, 8) · `manual_admin_tramites.html` (Admin/Sup, 12) · `manual_encuestas.html` (Sup/Admin, texto sin caps) · `manual_turnos.html` (Operador+, 6 caps, 11 secc.) · `manual_entradas.html` (Operador+, 4 caps, 10 secc.) · **`manual_alta_ciudadanos.html`** (Operador+, 3 caps, 7 secc. — alta por agente + autogestión + URL pública/Config, 2026-06-09) · **`manual_alta_vecino.html`** (público, para el vecino, sin caps, 5 secc.). **8 registrados en el módulo Guías (§37); el `manual_alta_vecino.html` NO va en Guías** — es la guía pública del vecino, se abre desde el enlace "¿Cómo me doy de alta?" en `frontend/alta-vecino.html` (no es material de backoffice). Próximos sugeridos (no obligatorios): Agenda, Padrones.

### Reglas de criterio (no las olvides)
- **El manual es parte del entregable cuando cambia la UI que documenta.** Antes de cerrar un cambio de UI/flujo, chequear si ese módulo tiene `docs/manual_<modulo>.html`. Si lo tiene, actualizar texto + capturas afectadas es parte del mismo entregable — un manual que describe la UI vieja miente al usuario. (Cómo detectar el desfasaje y regenerar solo lo afectado: en la skill.)
- **Una sola fuente por manual.** El HTML es el canónico (es lo que se publica en `docs/` y abre el módulo Guías §37). NO mantener un `.md` paralelo — se desincroniza en silencio (`manual_admin_tramites.md` quedó 5 días atrás, eliminado 2026-05-27).

## 37. Módulo Guías (catálogo de manuales)

Módulo React `/guias` registrado en sidebar después de Configuración. Es el front-end de los manuales generados según §36. **Sin `moduloCodigo` → visible para todos los usuarios autenticados** (es material informativo, no datos protegidos).

**Archivos (`web-app/src/modules/guias/`):**
- `index.tsx` — ModuleManifest (icon: BookOpen).
- `GuiasLayout.tsx` — Layout con breadcrumb INICIO › Guías.
- `pages/GuiasIndex.tsx` — Grid de cards (auto-fill minmax 320px). Cada card abre el HTML correspondiente en pestaña nueva vía `target="_blank"` + `rel="noopener noreferrer"`.

**Sidebar vanilla (`index.html`):** item "guías" sin `data-modulo` para que sea visible para todos. Ícono SVG inline (libro abierto, `stroke-width="1.5"`).

### Cómo agregar una guía nueva

1. Generar `docs/manual_X.html` siguiendo la receta de §36.
2. Agregar una entrada al array `GUIAS` en `GuiasIndex.tsx`:
   ```ts
   {
     titulo: 'NOMBRE EN UPPERCASE',
     descripcion: 'Una frase larga (~150 chars) explicando qué cubre el manual.',
     icon: SomeLucideIcon,
     htmlName: 'manual_X.html',
     audiencia: 'Operador o superior',
     tags: ['Operativo', 'N capturas', 'N secciones'],
   }
   ```
3. **No requiere tocar:** module manifest, sidebar vanilla, typecheck, ni rebuild manual del shell.

### Helper `urlDocs(htmlName)` — quirk de resolución de URL

El componente vive en el bundle React (`/web-app/dist/index.html#/guias`) pero los HTMLs están 2 niveles arriba en `/docs/`. El helper detecta entorno:

```ts
function urlDocs(htmlName: string): string {
  // 1. Iframe del shell vanilla (prod o local 8080): usa parent location
  if (window.self !== window.top) {
    try {
      const parentLoc = window.parent.location
      const base = parentLoc.pathname.replace(/[^/]*$/, '')
      return `${parentLoc.origin}${base}docs/${htmlName}`
    } catch { /* cross-origin fallback */ }
  }
  // 2. Standalone localhost:5173 (dev React aislado): apunta al shell vanilla local
  if (window.location.hostname === 'localhost' && window.location.port === '5173') {
    return `http://localhost:8080/docs/${htmlName}`
  }
  // 3. Standalone otros (degenerado)
  return `${window.location.origin}/docs/${htmlName}`
}
```

**Verificado en navegador** (sesión 2026-05-18) que los 3 casos resuelven correcto y los HTMLs cargan en pestaña nueva sin errores.

## 38. Auth público de ciudadanos (App Vecinos)

Backend mínimo para la PWA `zaris-vecinos` que permite a los ciudadanos enviar reclamos desde el celular. Etapa 0 entrega **solo auth + identidad del municipio**. Reclamos/adjuntos/push son etapas posteriores.

### Modelo

- **Login con DNI + password.** El alta la puede hacer un agente municipal (nivel ≤ 3, `/registrar` protegido) **o el propio vecino vía autoregistro público** (`/publico/alta/*`, ya entregado — ver "Alta pública de vecinos" más abajo).
- **Activación en dos pasos:** el agente carga al ciudadano + email → backend genera `token_activacion` UUID (vigencia 7 días) y manda mail → el ciudadano clickea el link `{APP_VECINOS_FRONTEND_URL}/activar?token=<uuid>`, elige password y queda logueado.
- **Recovery análogo:** el ciudadano pide reseteo desde la PWA → mail con `token_recovery` UUID (24h) → setea nuevo pass → JWT directo.
- **Scope JWT:** todos los tokens llevan claim `scope`. `"agente"` para los usuarios internos (`usuarios`), `"publico"` para ciudadanos (`ciudadanos` + `ciudadano_credencial`). Cada guard del backend rechaza el scope opuesto con 401.
- **Multi-canal preparado pero NO conectado:** tabla `ciudadano_canal_preferido` con flags `canal_email/push/whatsapp/sms`. Solo `email` se usa en el MVP. WhatsApp/SMS son columnas reservadas.
- **Multi-municipio:** cada deploy Railway es de un municipio. El endpoint público de identidad no necesita slug porque lee la única config del proyecto. Cuando consolidemos a multi-tenant compartido (etapa futura), agregar header `X-Municipio-Slug`.

### Tablas (migraciones 52 y 53)

| Tabla | Rol |
|---|---|
| `configuracion_general` (3 claves nuevas) | `municipio_descripcion`, `municipio_color_primary`, `municipio_color_accent`. La carga real se hace desde el panel admin ZARIS (etapa futura). |
| `ciudadanos.estado_validacion` (columna nueva) | `'auto_registrado' \| 'vinculado_pendiente' \| 'verificado'`. Default `auto_registrado` para no romper inserts existentes. Los altas del agente quedan `verificado`. |
| `ciudadano_credencial` | 1:1 con `ciudadanos`. `password_hash` (NULL hasta activar), `token_activacion`/`token_recovery` UUID + expiración, lockout (`intentos_fallidos`, `bloqueada_hasta`), `activado_en`, `fecha_ultimo_login`, `fecha_ultimo_cambio_password`. Estándar §10 completo. Índices parciales sobre los dos tokens cuando NOT NULL. |
| `ciudadano_canal_preferido` | 1:1 con `ciudadanos`. `canal_email=TRUE`, `canal_push=TRUE` por default. `canal_whatsapp` y `canal_sms` por default `FALSE`. |
| `ciudadano_push_subscription` | Placeholder Web Push (`endpoint`, `p256dh`, `auth_secret`, `user_agent`). Tabla creada, sin endpoint que la consuma todavía. UNIQUE `(id_ciudadano, endpoint)`. Etapa 5. |

**Aplicadas en local Y prod al 2026-05-19.** Idempotentes (`ADD COLUMN IF NOT EXISTS` + `CREATE TABLE IF NOT EXISTS` + `INSERT ON CONFLICT DO NOTHING`).

### Endpoints (`/api/v1/publico/auth/*`)

| Verbo | Path | Auth | Descripción |
|---|---|---|---|
| POST | `/registrar` | JWT scope `agente` (nivel ≤ 3) | Alta ciudadano + credencial + canal_preferido. Manda mail de activación via `BackgroundTasks`. 409 si DNI ya existe en `ciudadanos` activos o email duplicado en credencial activa. |
| POST | `/activar` | sin auth | Activa con `token_activacion` (vigencia 7d). Setea password (min 8 chars). Devuelve JWT scope `publico`. |
| POST | `/reenviar-activacion` | sin auth | Regenera token + reenvía mail. **Anti-enumeración**: siempre 200 OK aunque el DNI no exista o la cuenta ya esté activada. Cooldown silencioso de 5 minutos. |
| POST | `/login` | sin auth | Login con DNI + password. Lockout: 5 intentos fallidos → bloqueo 15 min. |
| GET | `/me` | JWT scope `publico` | Devuelve datos básicos del ciudadano logueado. |
| POST | `/recuperar-password` | sin auth | Pide email de recovery. Misma política anti-enumeración + cooldown 5 min. |
| POST | `/resetear-password` | sin auth | Aplica nuevo pass con `token_recovery` (vigencia 24h). Resetea lockout. Devuelve JWT scope `publico` para que el ciudadano quede logueado. |

### Endpoint público de identidad (`/api/v1/publico/identidad-municipio`)

- **Sin auth** (la PWA lo lee antes de tener token, en la pantalla de login).
- Lee de `configuracion_general` las 5 claves: `municipio_nombre`, `municipio_logo_url`, `municipio_descripcion`, `municipio_color_primary`, `municipio_color_accent`. Claves ausentes/vacías → `null`.

### Vigencia de tokens

- `token_activacion`: 7 días. Renovable con `/reenviar-activacion`.
- `token_recovery`: 24 horas (más corto que activación porque la cuenta ya está activa).
- JWT scope `publico`: 30 días por default. Configurable via `JWT_PUBLICO_EXPIRA_DIAS`. **Más largo que el JWT scope `agente` (24h)** porque la PWA debe minimizar fricción de re-login.

### Lockout

5 intentos fallidos consecutivos → `bloqueada_hasta = NOW() + 15 minutes`, `intentos_fallidos` reseteado a 0. Durante el bloqueo, `/login` devuelve 401 "Cuenta bloqueada temporalmente". Al hacer reset password o login exitoso, `bloqueada_hasta` se limpia.

### Anti-enumeración

`/reenviar-activacion` y `/recuperar-password` siempre devuelven 200 OK con `{"enviado": true}` independientemente de si el DNI existe, si la cuenta ya está activada, o si el cooldown está activo. No se revela al cliente nada sobre la existencia/estado de la cuenta. El mail se manda (o no) silenciosamente en `BackgroundTasks`.

### Scope check en `core/auth.py`

- `create_access_token(data)` ahora setea `scope='agente'` por default (retrocompat con tokens existentes).
- `crear_token_ciudadano(id_ciudadano, expira_dias=None)` emite scope `publico` con vigencia `JWT_PUBLICO_EXPIRA_DIAS`.
- `get_current_user` rechaza tokens con `scope != 'agente'` (default a `'agente'` para tokens viejos sin el claim).
- `get_current_ciudadano` rechaza tokens con `scope != 'publico'`, valida que el ciudadano + credencial estén `activo=TRUE` y `activado=TRUE`. Devuelve dict con `id_ciudadano, doc_nro (dni), nombre, apellido, email, estado_validacion`.

### Email + env vars
- Remitente real `RESEND_FROM` (`notificaciones@zaris.com.ar`, §42) con header `From:` = **display name del municipio** (`"MUNICIPALIDAD … <notificaciones@zaris.com.ar>"`) vía `enviar_mail(..., from_override=...)`. La marca ZARIS no aparece al vecino. Funciones `enviar_mail_activacion_ciudadano`/`enviar_mail_recovery_ciudadano` (`services/email.py`), template sobrio con logo del municipio, sin emojis.
- **Env vars**: `APP_VECINOS_FRONTEND_URL` (default `http://localhost:5174`, prod `https://vecinos.zaris.com.ar` — arma los links de los mails) · `JWT_PUBLICO_EXPIRA_DIAS` (default 30).
- **CORS**: `vecinos.zaris.com.ar` + `zaris-vecinos.vercel.app` + `localhost:5174` en `allow_origins`.

### Estado / alcance
Backend Etapa 0 (8 endpoints) en prod, verificado. PWA en repo separado `CesarZeta/zaris-vecinos` (Vercel, `vecinos.zaris.com.ar`) — **no documentar la PWA acá** (otro repo). **Fuera de alcance**: `POST /publico/reclamos` + adjuntos públicos (Etapa 2), push (Etapa 5, `ciudadano_push_subscription` sin endpoint aún), bandeja `vinculado_pendiente` (futuro), panel admin de branding (producto separado).

### Alta pública de vecinos (autoregistro) — flujo en DOS PASOS (Fase 4, 2026-06-09, mig 79)
Página pública `frontend/alta-vecino.html?m=<slug>` (vanilla, DS ZARIS) donde el **vecino crea su cuenta** (sin agente, sin JWT). Router `routes/publico_alta.py` (`/api/v1/publico/alta/*`, sin JWT, rate-limited por IP). **Tenancy mono-tenant validado**: el slug `?m=<codigo_corto>` se valida contra el ÚNICO municipio del deploy (`municipios.codigo_corto`, ej. `lpl`) → 404 si no coincide. URL preparada para multi-deploy sin reescribir a multi-tenant.

> **Cambio de modelo 2026-06-09 (Fase 4, mig 79):** el alta se separó en DOS MOMENTOS (antes creaba cuenta + ficha JUNTAS de una). Marca nueva `ciudadanos.ficha_completa` (FALSE tras paso 1, TRUE tras paso 2) + `ciudadano_credencial.debe_cambiar_password` (reservada para alta-por-agente con clave temporal; hoy el Camino B usa activación-por-token, no la setea). El alta-de-una vieja (`POST /alta/ciudadano` + el alta-vecino.html que pedía toda la ficha) fue REEMPLAZADA. El schema `AltaCiudadanoIn/Out` quedó deprecado en `schemas/publico_alta.py` (sin endpoint que lo use).

- **PASO 1 — crear cuenta (Camino A, autogestión):** `POST /alta/cuenta` (`AltaCuentaIn`: slug + `doc_nro` DNI + `nombre` + `apellido` + `email` + `password`). Crea `ciudadanos` con el mínimo real + **placeholders** en los NOT NULL que faltan (`cuil='20'+dni+'9'`, `sexo='OTROS'`, `fecha_nac='1900-01-01'`, `id_nacionalidad=1`, `telefono='0'`), `estado_validacion='auto_registrado'`, `email_chk=FALSE`, `ficha_completa=FALSE` + `ciudadano_credencial` (password elegido + `token_activacion`, `activado=FALSE`, `debe_cambiar_password=FALSE`). Manda mail. El vecino NO es `usuarios` (scope `publico`, [[project_usuario_vs_ciudadano_modelo]]).
- **VERIFICAR email:** `GET /alta/verificar?token=&m=` → `email_chk=TRUE`, `estado_validacion='verificado'`, credencial `activado=TRUE`. La página de confirmación invita a iniciar sesión y completar datos.
- **PASO 2 — completar ficha:** `POST /publico/auth/completar-ficha` (**JWT scope publico**, `get_current_ciudadano`). El vecino ya verificado/logueado carga su ficha real (CUIL módulo-11 válido, sexo, fecha nac, nacionalidad, domicilio OSM, teléfono). Reemplaza los placeholders y marca `ficha_completa=TRUE`. El `id_ciudadano` SIEMPRE sale del token (no del body). Rechaza CUIL de otro ciudadano (409). El select de nacionalidad lo sirve `GET /publico/auth/nacionalidades` (scope publico, j3 — la PWA mono-deploy no maneja slug). **Frontend del paso 2 ENTREGADO en la PWA `zaris-vecinos`** (otro repo, commit `901b0a0`, 2026-06-09 j3): `CompletarFichaPage` + gate en `RutaProtegida` (`ficha_completa===false` → `/completar-ficha`; SOLO `===false`, undefined no). Verificado smoke E2E local. **Solo lo alcanza el autoregistro (Camino A); el alta por agente deja `ficha_completa=TRUE` y NO pasa por acá.**
- **Camino B (alta por agente) — UNIFICADO en el alta de ciudadano del backoffice (2026-06-09 j4):** el alta del frontend de Ciudadanos (`POST /api/v1/buc/ciudadanos`, módulo React `ciudadanos`/`FormView`) **crea automáticamente la cuenta de App Vecinos** + mail de activación. Ya **NO hay alta de padrón separada de la cuenta de portal**; el agente carga la ficha y al guardar se hace todo. Detalle:
  - **`email` obligatorio** (ya lo era en `CiudadanoCreate`, schema `buc.py`). Rechaza email duplicado en credencial activa (409, mismo criterio que `/publico/auth/registrar`).
  - **Servicio `services/cuenta_vecino.py::asegurar_cuenta_vecino`** (reutilizable, idempotente): crea `ciudadano_credencial` (sin password + `token_activacion`) + `ciudadano_canal_preferido` + encola el mail de activación (BackgroundTasks). Si ya hay credencial activada, no toca nada; si existe sin activar, regenera token. `crear_ciudadano` en `buc.py` lo llama tras `db.flush()`.
  - **El agente cargó la ficha completa → `ficha_completa=TRUE` + `estado_validacion='verificado'`** (ambas columnas NO mapeadas en el modelo ORM `Ciudadano` → se setean con UPDATE SQL directo, NO con setattr). El vecino **entra directo, SIN el paso 2** (a diferencia del autoregistro Camino A, que sí pasa por completar-ficha). El vecino recibe mail, clickea ACTIVAR y **elige su propia clave** (activación-por-token; NO clave-temporal+cambio-forzado).
  - **Botón "+ Nuevo" en el buscador de ciudadano** (`CiudadanoSearch` de `agenda/components`, **compartido** por reclamos/turnos/entradas/agenda): si la búsqueda no encuentra al vecino, `navigate('/ciudadanos/nuevo')` lleva al alta. El `CiudadanoForm` muestra un aviso (prop `esAlta`) de que se crea la cuenta + se manda el mail.
  - El endpoint `/publico/auth/registrar` (alta por agente con scope agente, sin pantalla propia) **sigue existiendo** pero la vía operativa real es el alta del módulo Ciudadanos. Verificado E2E (alta→credencial+canal+verificado+ficha_completa→vecino activa eligiendo clave→login). [[project_usuario_vs_ciudadano_modelo]].
- **`ficha_completa` en login/me:** `CiudadanoBasicoOut.ficha_completa` lo exponen `/publico/auth/login`, `/me` y `/resetear-password` → el portal decide si mandar al vecino a completar la ficha. `get_current_ciudadano` (core/auth) trae la columna.
- **Empresa NO se da de alta desde la página pública** (decisión 2026-06-09): se quitó el toggle de empresa de `alta-vecino.html`. La empresa la carga el vecino YA logueado y con ficha completa, desde el portal (PWA), reusando el endpoint `POST /alta/empresa` que queda en backend. **Empresa exige ciudadano previo** (BUC §2): `empresas` + `ciudadano_empresa` + `empresa_credencial` (mig 76, solo verificación de email, SIN password). Verificar → `empresas.email_chk=TRUE` + `empresa_credencial.verificado=TRUE`.
- **Geocoding OSM público**: `GET /publico/alta/geo/buscar?m=&q=` reusa `geocodificar_direccion()` extraída de `geo.py`. Lo usa el paso 2 (domicilio del vecino). El `/geo/buscar` del backoffice SIGUE exigiendo JWT — solo el público es abierto.
- Endpoints: GET `/identidad` · `/actividades` · `/nacionalidades` · `/geo/buscar` (todos validan slug) + POST `/alta/cuenta` (paso 1) · `/alta/empresa` + GET `/alta/verificar` (devuelve **página HTML**, la abre el navegador) + POST `/publico/auth/completar-ficha` (paso 2, JWT). Link del mail = `FRONTEND_BASE_URL/api/v1/publico/alta/verificar`. Templates `enviar_mail_verificacion_alta_ciudadano/_empresa` en `services/email.py`. Verificado E2E navegando (local) + smoke API (paso1→verificar→login→paso2 + bordes 401/409/404).
- **Permisos del vecino**: acciones de autoservicio acotadas a SUS datos (paridad con operador "en su nombre", NO backoffice). El `id_ciudadano` SIEMPRE sale del JWT, nunca del body/param → no puede operar sobre terceros. Ver [[project_usuario_vs_ciudadano_modelo]].
- **Autoservicio del vecino logueado (Etapa 2, 2026-06-02, commit `53edc28`, en prod):** dos routers nuevos con guard `get_current_ciudadano` (scope `publico`), SIN migración (reusan columnas existentes):
  - **`publico_reclamos.py` (`/api/v1/publico/reclamos`):** POST crea reclamo a nombre propio (`id_ciudadano` del token; `id_usuario_alta=NULL` — no es `usuarios`, columna nullable; `canal_origen='app_movil'`; estado inicial 'Sin asignar'; deriva `id_area` de `subarea.id_area` vía el tipo §27; valida tipo activo). **Desde 2026-06-02 el POST exige `id_tipo_reclamo` + `direccion` + `descripcion≥5`** — el backoffice los acepta opcionales pero la autogestión NO afloja datos obligatorios (regla del municipio, [[feedback_autogestion_no_afloja_obligatorios]]); no evadible por curl (422). + GET lista SOLO los suyos (`WHERE id_ciudadano=<token>`) + GET `/{id}` detalle con **guard duro 404 si no es suyo** (mismo cuerpo que "no existe", no filtra terceros; historial sin identidad del agente) + GET `/catalogo/tipos` + **GET `/geo/buscar` (scope publico, geocoding del vecino logueado — [[reference_geocoding_vecino_endpoint_scope_publico]])**, todos declarados ANTES de `/{id_reclamo}` por el param greedy §5.
  - **`publico_portal.py` (`/api/v1/publico/portal`):** GET `/mi-resumen` — conteos `{vigentes,total}` de reclamos/turnos/entradas del vecino en 1 round-trip (home del portal). Vigente = reclamos activos no-final, turnos `estado='reservado'`, reservas con `estado_reserva.codigo='reservada'`.
  - Ambos registrados junto a los `publico_*` en `main.py` (prefijos no colisionan con `reclamos_router` ni `publico_alta`). Smoke local 9/9 + deploy prod verificado (`/openapi.json` + 401 sin token). **v1 NO incluye:** cambiar estado, cancelar reclamo propio, "mis-turnos"/"mis-entradas" logueados (turnos/entradas siguen por token anónimo §33), adjuntos públicos.
- **URLs públicas en Config → Identidad (ENTREGADO 2026-06-09 j3/j4):** `GET /config/identidad` expone `municipio_slug` (= `municipios.codigo_corto` del único municipio activo). `IdentidadView.tsx` muestra la sección "Enlaces públicos del municipio" (solo lectura, helper `basePublica()` resuelve el origin del shell padre en iframe) con la URL del alta `…/frontend/alta-vecino.html?m=<slug>` + Copiar/Abrir. La URL **cambia por municipio en DOS partes** (dominio + `?m=código`) — mono-tenant por deploy, NO hay URL genérica. El array `ENLACES` es extensible para futuras URLs públicas.
  - **Frontend del autoservicio — PWA "Portal del Ciudadano" (`zaris-vecinos`, repo separado, Vercel):** las pantallas del flujo logueado (auth scope publico, home con `mi-resumen`, mis reclamos lista/detalle, alta de reclamo con geocoding) se construyeron 2026-06-02 (commit `0b85205`, deploy Vercel Ready). Verificado E2E contra backend LOCAL (sembré credencial + cleanup). **Verificación E2E del happy-path logueado en PROD PENDIENTE: `ciudadano_credencial` en prod está VACÍA** — el primer login real será cuando alguien se autoregistre. Detalle de la PWA (estado, contrato de endpoints, shape de sesión propio `zaris_vecino_session`) en [[project_portal_ciudadano_pwa]]. NO documentar la PWA acá (otro repo).

### Quirks
- **DNI digit-only** (`_solo_digitos()` normaliza antes de comparar con `ciudadanos.doc_nro`). **CUIL placeholder** en `/registrar`: `'20'+dni.zfill(8)+'9'` (`cuil` es UNIQUE NOT NULL). **Defaults pragmáticos** del alta: `doc_tipo='DNI'`, `sexo='OTROS'`, `fecha_nac='1900-01-01'`, `id_nacionalidad=1`, `*_chk=FALSE`.
- **SQL con `text()`**: `CAST(:token AS uuid)` no `:token::uuid` ([[feedback_sqlalchemy_cast_uuid]]); `INTERVAL` con duración variable → f-string literal, no bind param ([[feedback_asyncpg_extract_cast_date]]).
- Mail de activación corre en `BackgroundTask` post-commit (patrón §35); sin Resend key → modo MOCK.
- Smoke: `backend/smoke_publico_auth.py` (15 pasos, 15/15 OK 2026-05-19).

## 39. Módulo Usuarios — estado y deuda crítica (QA 2026-05-19)

**Stack**: vanilla puro. HTML en [frontend/usuarios.html](frontend/usuarios.html), JS en [frontend/js/usuarios.js](frontend/js/usuarios.js). Endpoints en [backend/app/api/routes/buc.py](backend/app/api/routes/buc.py) prefix `/api/v1/buc/usuarios/*`.

> **Ampliado 2026-05-22 (mig 55, §21):** el form ahora tiene **campo subárea predictivo + checkbox "usuario externo"** (subárea obligatoria salvo externo, validado en `schemas/buc.py`). Listado/preview muestran subárea + hay filtro por subárea. Buscador principal y filtro de listado pasan a predictivo en-vivo (debounce). `UsuarioOut` suma `id_subarea`/`subarea_nombre`/`es_externo`. Endpoint nuevo `GET /buc/subareas/buscar` (predictivo).

> **Bugs CRITICAL #1, #2, #3 RESUELTOS y pusheados a prod el 2026-05-22.** Ver "Estado de la deuda" abajo.

> **Rediseño 2026-05-26 (en prod, verificado navegando):**
> - **Form sin nombre/cargo/CUIL**: el username ES la identidad. `UsuarioCreate.nombre` es opcional; el backend lo iguala al username si no viene (la columna es NOT NULL). El form quedó: usuario, nivel, email, subárea, contraseña. Cargo y CUIL ya NO existen en Usuarios (sí en Agentes).
> - **Módulos a los que accede**: `UsuarioOut.modulos_permitidos` (resuelto en batch, `_modulos_permitidos_batch` en `buc.py`), mostrados como chips **al lado del Nivel** en el form (no en la previa). En alta nueva derivan del nivel + catálogo (`GET /admin/permisos/modulos`); en consulta/edición son los reales del usuario.
> - **Auditoría de login** (mig 62): `usuarios.fecha_ultimo_login` + tabla append-only `usuario_login_log` (timestamp + IP + user agent). `POST /auth/login` los escribe (best-effort, no bloquea login; usa `get_real_ip`). Último login se muestra en la previa y en la sección "Actividad" del form. Endpoint `GET /buc/usuarios/{id}/login-log` + modal "Ver historial de accesos". La auditoría se lleva por usuario y, vía la regla 1:1, se audita por agente.
> - **Regla 1:1 agente↔usuario** (mig 64): el alta de usuario **interno** crea automáticamente su agente vinculado (datos mínimos, en la misma tx de `POST /buc/usuarios`); el **externo** NO. Índice UNIQUE parcial `agentes.id_usuario WHERE NOT NULL` lo refuerza en DB.
> - **Auto-logout 10 min** (shell `menu.js`): timer global que se reinicia con actividad del shell y del iframe; a los 10 min sin actividad limpia `zaris_session` y va a login.
> - **Fix flash de login**: el guard de sesión se movió a ser lo PRIMERO del `<head>` de `index.html` (antes de CSS y del script de lucide), para no pintar el shell antes del redirect.

### Deuda conocida — estado al 2026-05-22

Detalle en [reporte_pruebas_usuarios_2026-05-19.md](reporte_pruebas_usuarios_2026-05-19.md) (untracked, sin PoCs desde que se resolvieron los críticos, ver §40).

| # | Severidad | Bug | Estado | Archivo |
|---|---|---|---|---|
| 1 | CRITICAL | Router `buc.py` sin auth — los 28 endpoints aceptaban requests sin JWT. | **✅ RESUELTO 2026-05-22** — guard a nivel router (`APIRouter(..., dependencies=[Depends(get_current_user)])`): **TODO el router exige JWT** (28 endpoints, GET incluidos). Cualquier endpoint nuevo queda protegido por defecto. Smoke: GET y POST sin token=401, con token=200/201. App Vecinos (`/publico/*`, router separado) no afectada. | [backend/app/api/routes/buc.py](backend/app/api/routes/buc.py) |
| 2 | CRITICAL | XSS persistente en `mostrarResultados()` (`u.nombre`/`u.username` sin `esc()`). | **✅ RESUELTO 2026-05-22** — `esc()` aplicado. | [frontend/js/usuarios.js](frontend/js/usuarios.js) |
| 3 | CRITICAL | XSS persistente en topbar del shell (`user.nombre` sin escape). | **✅ RESUELTO 2026-05-22** — helper `esc()` en menu.js + cache-bust `?v=2026-05-22a`. | [frontend/js/menu.js](frontend/js/menu.js) |
| 4 | HIGH | Form no captura email → users creados desde UI no podían loguearse (`/auth/login` busca por email). | **✅ RESUELTO 2026-05-22** — POST autogenera `<username>@municipio.gob.ar` si no viene (valida unicidad 409); `email` opcional en Create/Update/Out + form. Smoke: alta sin email → login OK. | [frontend/usuarios.html](frontend/usuarios.html) + [backend/app/api/routes/buc.py](backend/app/api/routes/buc.py) |
| 5 | HIGH | Módulo no accesible desde el sidebar — el item con `data-modulo="usuarios"` era en realidad "configuración" (Config React). | **✅ RESUELTO 2026-05-22** — item nuevo "usuarios" → `frontend/usuarios.html`; "configuración" pasó a `data-modulo="admin_tablas"`. | [index.html](index.html) sidebar |
| 6 | MEDIUM | Modal confirm de baja con texto equivocado ("No, continuar / Sí, salir"). | **✅ RESUELTO 2026-05-22** — `ZUtils.confirm(title, msg, opts)` acepta `cancelLabel`/`confirmLabel`/`danger` + escapa title/msg. `cambiarEstado()` pasa "Cancelar"/"Sí, dar de baja". Ver [[feedback_modal_zutils_confirm_textos_fijos]]. | [frontend/js/config.js](frontend/js/config.js) `confirm()` |
| 7 | HIGH | Botón Guardar **gris en modo edición/consulta→edición** — no se podía guardar ninguna edición. `bindGuardarBoton` solo re-evalúa con eventos `input`/`change` reales; al poblar el form por código (editar usuario) el botón quedaba con el estado inicial vacío (deshabilitado). | **✅ RESUELTO 2026-05-26** (commit `e4c13df`) — `usuarios.js` captura el `{check}` devuelto y lo llama en `revalidarGuardar()` tras `poblarFormulario`/`activarModoEdicion`/`activarModoNuevo`. Ver [[feedback_validacion_reactiva_cambios_programaticos]]. | [frontend/js/usuarios.js](frontend/js/usuarios.js) |
| 8 | MEDIUM (UX) | Cambio de contraseña: el botón Guardar se ponía gris al empezar a escribir la nueva clave y no decía por qué (falta confirmar / no coincide / corta) — el usuario no podía apretarlo para ver el error. | **✅ RESUELTO 2026-05-26** (commit `39c0d96`) — pista en vivo bajo "Confirmar contraseña" (`pistaPassword()`): mínimo 8 chars / repetí para confirmar / no coinciden / coincide. | [frontend/js/usuarios.js](frontend/js/usuarios.js) |

**Estado al 2026-05-26**: los 8 hallazgos están **resueltos y verificados** (smoke backend + navegador + DB). El router BUC completo exige JWT (guard a nivel router). `UsuarioOut` **NO** expone `password_hash` (verificado). **El módulo Usuarios/BUC queda sin deuda conocida.**

> **Cambio de contraseña funciona** (verificado E2E 2026-05-26: PUT → hash bcrypt nuevo → login OK con la clave nueva). **Login busca por email exacto, NO por username** — el email real del usuario puede no seguir el patrón `<username>@municipio.gob.ar` (en prod `ciudadanovl` es `cesarzarini@hotmail.com`). Ver [[reference_login_email_prod_no_es_patron_doc]]. Reseteo de password admin en prod: hash bcrypt directo + `UPDATE usuarios` + verificar contra el API de Railway con el email real.

> **Patrón**: para proteger un router entero (todos los verbos, incluido GET, + endpoints futuros), usar `APIRouter(prefix=..., dependencies=[Depends(get_current_user)])` en vez de `Depends` por-handler. Más robusto contra regresiones. Solo dejar endpoints sin guard si son genuinamente públicos (entonces van en un router separado, como `/publico/*`).

### Integridad de cuentas — todo `usuario` tiene un agente O un ciudadano (mig 77, roadmap en curso 2026-06-09)

**Invariante:** todo `usuario` activo debe estar vinculado a un **agente** (interno) o un **ciudadano** (vecino). Un usuario "pelado" (sin ninguno de los dos) no es un estado válido permanente — típicamente es un alta a medias. El módulo Trámites lo exige de hecho: `tramite.id_agente_iniciador` es **NOT NULL** y todos los endpoints de operación llaman `resolver_agente_desde_usuario` → 403 si no hay agente. **Origen:** informe QA Roy 2026-06-09 ("El usuario no tiene un agente asociado") — admins/operadores viejos sin fila en `agentes`.

- **Alta interna ya garantiza el agente** (§39 mig 64): `POST /buc/usuarios` con `es_externo=FALSE` crea el agente vinculado en la misma tx. El `es_externo=TRUE` NO crea agente (categoría legítima sin subárea) — ese caso lo cubre el cron.
- **Mensaje del guard (Fase 1, 2026-06-09):** el 403 de los 13 endpoints de `tramites.py` pasó de `"El usuario no tiene un agente asociado"` (técnico) a uno accionable: *"Tu usuario no tiene un perfil de agente municipal… Pedile a un administrador que lo configure desde Maestros → Usuarios."* El `detail` viaja por `lib/api.ts` (`err.detail`→`Error.message`) hasta el toast de `CrearTramite.tsx` — lo que escribas en el `HTTPException` es lo que ve el usuario.
- **Cron de integridad (Fase 2, mig 77):** `POST /api/v1/usuarios/mantenimiento/integridad-cuentas` (router `usuarios_mantenimiento.py`, SIN JWT, auth `X-Dispatcher-Token` — mismo patrón que §35/§42; soporta `?dry_run=true`). Motor `services/integridad_cuentas.py::suspender_usuarios_sin_vinculo`: usuarios **activos, nivel_acceso > 1 (admin EXENTO** para evitar lockout total**), sin agente activo y sin ciudadano vinculado por email, creados hace > 24h (gracia)** → `activo=FALSE` + `suspendido_motivo='sin_vinculo'` + `fecha_suspension=NOW()`. Reversible: un admin crea el agente/ciudadano faltante y reactiva. Vínculo a ciudadano = por email (igual que el backfill y que `/auth/login`, que loguea por email). Cron diario `.github/workflows/integridad-cuentas.yml` (04:25 UTC, desfasado del de Trámites).
- **`usuarios.fecha_alta` es `timestamp without time zone`** (legacy §5): comparar contra `(NOW() AT TIME ZONE 'UTC')` para la gracia, no contra `NOW()` directo.
- **Fase 3 — ENTREGADA (2026-06-09, mig 78).** Clave temporal + cambio forzado en 1er ingreso para usuarios INTERNOS. `usuarios.debe_cambiar_password` (BOOL). El alta (`POST /buc/usuarios`) **ya no recibe password del form**: el sistema genera una clave temporal, la marca `debe_cambiar_password=TRUE` y la **manda por email** (`enviar_mail_credenciales_usuario_interno` en `services/email.py`, marca del municipio + CTA al login del shell). **Email ahora OBLIGATORIO en el alta** (`UsuarioCreate.email` requerido — es el canal de entrega). `POST /auth/login` devuelve `debe_cambiar_password`; el **login vanilla** (`frontend/login.html`) lo detecta y muestra una pantalla de "Cambiá tu contraseña" ANTES de entrar al shell (no persiste sesión hasta cambiar). Endpoint self-service `POST /auth/cambiar-password` (forzado: no pide la actual porque ya validó la temporal al loguear; voluntario: exige y verifica la actual; rechaza nueva==actual; limpia la marca). El form de alta de `usuarios.html` oculta los campos de password y muestra un aviso ("se genera y se manda por mail"); en EDICIÓN conserva el reset manual por admin. Si el cliente igual manda `password` (seeds/compat) se respeta sin forzar cambio. Verificado smoke backend (8 bordes) + navegación E2E.
- **Fase 4 — ENTREGADA (2026-06-09, mig 79).** Alta pública del vecino en DOS PASOS (cuenta → verificar email → completar ficha). Modelo separado (vecino sigue en `ciudadanos`+`ciudadano_credencial`, NO se unifica en `usuarios`). Detalle completo en §38 ("Alta pública de vecinos — flujo en DOS PASOS"). **Pendiente: frontend del paso 2 (completar ficha) en la PWA `zaris-vecinos`** (otro repo) — pantalla post-login que aparece cuando `me.ficha_completa===false`.

## 40. Reportes vs guías de QA — qué se versiona y qué no

**Distinguir dos artefactos distintos:**

1. **Reportes de QA** (`reporte_pruebas_<bloque>_YYYY-MM-DD.md`, generados por `/qa-report-template`): el **resultado** de una corrida de pruebas. Pueden contener PoCs reproducibles de vulnerabilidades (payloads XSS, endpoint sin auth + cómo explotarlo). **NO se commitean mientras tengan PoCs de hallazgos sin resolver** — el repo es público vía GH Pages (§6 + memoria [[reference_gh_pages_publica_todo_lo_commiteado]]), commitear eso = publicar guía de explotación.
   - **SÍ se pueden versionar** cuando: (a) los hallazgos están **resueltos**, **y** (b) el reporte **no tiene payloads explotables** (verificar con `grep -cE "<script>|javascript:|onerror=|alert\("` → debe dar 0). Caso real 2026-05-22: `reporte_pruebas_admin_tablas_2026-05-17.md` se versionó tras confirmar 0 payloads + bugs resueltos.
   - Si tiene PoCs activos: mantener untracked, o archivar reescrito sin PoCs en `docs/qa-archive/`.

2. **Guías de QA** (`docs/qa_<modulo>.html`): el **plan de pruebas** para el tester humano — pasos + resultado esperado + columna PASS/FAIL. NO contienen PoCs (describen qué probar, no cómo explotar). **Se versionan normalmente** en `docs/`, servidas como `https://zge.zaris.com.ar/docs/qa_<modulo>.html`. Formato canónico: `docs/qa_reclamos_ot.html` y `docs/qa_tramites.html` (hero naranja + índice + tablas de casos + preguntas guía + glosario, sin emoji §13). **NO se registran en el módulo Guías** (ese es para manuales operativos del producto §37); las guías QA se comparten por link directo al tester. Generarlas con datos reales de prod (usuarios por rol con subárea, IDs/códigos reales).

**Regla operativa:**
- `.gitignore` no excluye los reportes — quedan visibles en `git status` como recordatorio de deuda.
- Antes de versionar cualquier `.md`/`.html` de QA: `grep` de payloads + confirmar hallazgos resueltos.
- Nunca incluir reportes con PoCs activos en commits ni en mensajes de PR.

## 41. Módulo Config (React) + estándar de verificación en la interfaz

Módulo React `web-app/src/modules/config/` (ítem "configuración" del sidebar, `data-modulo="admin_tablas"` desde §39). Es admin-only — el backend exige `nivel_acceso=1` en `require_admin` (los endpoints de identidad y permisos). 4 tabs en `ConfigLayout`:

| Tab | Vista | Endpoint backend | Qué hace |
|---|---|---|---|
| Identidad | `IdentidadView` | `GET/PUT /api/v1/config/identidad` (+ `/logo-upload-url`) | Nombre y logo del municipio en el topbar. `app_nombre` ('GESTION ESTADO') es interno, NO editable (§14) — el PUT lo ignora. |
| Permisos por usuario | `UsuariosPermisosView` | `GET /api/v1/admin/permisos/usuarios/{id}/modulos` + `PUT` | Matriz de overrides por módulo (§30). Lista usuarios vía `GET /api/v1/admin/usuarios` (handler genérico admin_tablas). |
| Catálogo de módulos | `CatalogoModulosView` | `GET /api/v1/admin/permisos/modulos` + `PUT /{codigo}` | Editar `min_nivel_acceso` de cada módulo. |
| Sistema | `SistemaView` + `ParametrosSistemaView` | `GET /api/v1/admin/configuracion_general` + `PUT /{id_config}` | **Desde 2026-05-25:** pantalla de ajustes agrupada y tipada (toggle/number/text/color) sobre `configuracion_general`, secciones Encuestas / Reclamos y OT / App Vecinos / Otros. Debajo, atajos a Municipios/Maestros. Ver [[reference_config_sistema_pantalla_tipada]]. Clave nueva: seed (mig) + leer backend + sumar a `SECCIONES`. **`configuracion_general.tipo` es NOT NULL en PROD (`string`/`boolean`/`integer`) pero NO existe en local** (drift cazado 2026-06-01, §24) — al insertar una clave nueva en prod, **incluir `tipo`** o el INSERT falla con `null value in column "tipo"`; el seed que corra en ambos entornos debe detectar la columna (`information_schema.columns`) y armar el INSERT con/sin `tipo` según exista (patrón en `migrations/75b_tramites_retencion_config.sql`). `municipio_nombre`/`logo` ocultos acá (se editan en Identidad). El item "usuarios" se quitó del sidebar del shell (sigue accesible acá vía atajo "Usuarios del sistema"). |

**Cliente API:** `web-app/src/modules/config/api/configApi.ts` + hooks en `hooks/useConfig.ts`. Los 3 endpoints existen, están registrados en `main.py` y las shapes coinciden. Verificado end-to-end en navegador 2026-05-22.

### Bugs de navegación cazados y resueltos (2026-05-22) — referencia para módulos React en iframe

Tres bugs distintos en este módulo, todos de **navegación**, ninguno detectable leyendo el código solo (ver estándar abajo):

1. **`window.location.href` absoluto rompe bajo `/zaris-zge/`** (commit `3ea2847`). `SistemaView` e `ConfigLayout` (botón INICIO) caían a `window.location.href = '/${href}'` en el fallback → salta a `cesarzeta.github.io/${href}` SIN el subpath → 404 de GH Pages en el iframe (§32 Quirk 13). **Fix:** helper compartido `web-app/src/lib/shellNav.ts` (`shellNavigate` + `shellGoInicio`) que delega en `window.parent.shellNavigate` y solo en standalone dev resuelve el subpath. **Reusar este helper en cualquier módulo React que navegue al shell** en vez de reinventar el patrón.
2. **`NavLink to="x"` relativo expulsa al dashboard** (commit `9105dbf`). Los tabs usaban `to="permisos"` (relativo): estando en `/config/identidad`, React Router lo resolvía a `/config/identidad/permisos` (ruta inexistente) → catch-all `path:'*'` en `routes.tsx` → redirect a `/dashboard`. Solo se notaba **al clickear una tab** (la primera carga directa por URL funcionaba). **Fix:** paths ABSOLUTOS `to="/config/<tab>"`. **Regla:** en layouts con tabs internas usar paths absolutos, no relativos — el relativo anida contra la ruta actual completa.
3. **Tipos del API mentían** (commit `a04878c`, deuda menor): `app_nombre` figuraba en `IdentidadUpdate` (lo ignora el PUT) y `listarUsuarios` mandaba `?limit=200` que el handler genérico ignora. Alineados con el backend real.

### `admin_tablas` configuracion_general — mostrar `descripcion` en la preview (2026-05-22)

La tabla `configuracion_general` tiene columna `descripcion` con texto útil por parámetro, pero la vista previa de `admin_tablas.html` mostraba solo `clave` + `valor` (vía `composeLabel`/`composeMeta` genéricos). El admin veía claves crudas sin saber qué hacen. **Fix** (commit `b32b71f`): caso especial en `renderVistaPrevia` para `tablaActual === 'configuracion_general'` que renderiza clave + descripción en gris debajo + valor a la derecha. `configuracion_general` **no tiene columna `activo`** (sin baja lógica) — borrar registros de basura es DELETE físico, no soft-delete.

### Estándar OBLIGATORIO: verificar navegación/UI en la interfaz, no en el código

**Todo cambio de navegación/routing/UI se verifica abriendo el navegador y reproduciendo el flujo real ANTES de declararlo terminado.** Para el humano la realidad vive en la interfaz; el código es una hipótesis. Endpoint que existe + tipo que matchea + ruta mapeada pueden seguir dando pantalla rota. Procedimiento (memoria [[feedback_testear_navegacion_en_interfaz]]):

1. Entorno correcto: prod si ya está deployado, o local con proxy `/zaris-zge/` si toca subpath.
2. **Confirmar que el iframe carga el bundle NUEVO** antes de juzgar — GH Pages puede servir el nuevo pero el iframe sirve el viejo cacheado (§ memoria iframe cache). Cache-bust: `frame.src='about:blank'` → `frame.src='...?_cb='+Date.now()+'#/ruta'`, verificar el hash del `<script src>` del iframe = último commit.
3. Recorrer **TODAS las vías de navegación que el usuario tiene a mano**: cada tab/botón, ida y vuelta, saltando entre secciones. NO entrar a cada vista por URL directa — eso oculta bugs de links relativos. El gesto humano es clickear, no tipear URLs.
4. Recién entonces declarar verificado. Si no lo hice, decirlo explícito.

> Caso 2026-05-22: declaré "Config completado" dos veces con bugs vivos porque verifiqué entrando por URL directa (no clickeando tabs) y porque el iframe servía bundle cacheado. "Entré a la URL y cargó" ≠ "navegué el módulo como un usuario".

## 42. Módulo Encuestas (CSAT) — Reglas de negocio

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

## 43. Módulo Datos (BI — Análisis de datos)

Tableros analíticos sobre `reclamos`. Módulo React `web-app/src/modules/bi/` (sidebar "datos", `moduloCodigo='bi'`, mig 65, nivel ≤ 2). Router backend `backend/app/api/routes/bi.py` (`/api/v1/bi/*`, guard JWT a nivel router). Entregado 2026-05-26.

### Estructura
- **Landing DATOS** (`/bi`, `pages/DatosLanding.tsx`): 2 tarjetas estilo Contactos → **Operativo** (activo) + **Ejecutivo** (placeholder "Próximamente", contenido a definir por el usuario).
- **Operativo** (`/bi/operativo/*`, `BiLayout` con 4 tabs): Resumen, Resueltos/SLA, Pendientes (+ mapa geo), Subreclamos.

### Reglas de visualización (OBLIGATORIAS para toda viz nueva del módulo)
Ver memoria `reference_bi_lineamientos_visualizaciones`. Resumen:
- **Recharts 2.15, NO 3.x** — la 3.8 trae `es-toolkit` que rompe con Vite 8 (`require_isUnsafeProperty`; root vacío sin error en consola del browser, el error vive en el log de Vite).
- **Toda viz lleva etiqueta de total** (barras: valor en segmento + total afuera; donas: `%` + valor). Pastilla de fondo **OSCURA** `rgba(38,37,30,0.78)` + texto claro `#f7f7f4` (el usuario pidió oscuro explícitamente).
- **Histogramas temporales: toggle Mes/Día + drill-down** (clic en barra de mes → días de ese mes). Componente genérico `components/HistogramaTemporal.tsx` (series + fetchers inyectados).
- **Toda tabla de detalle lleva botón "Exportar CSV"** (helper `components/exportCsv.ts`, BOM UTF-8 para Excel).
- **Estilo ZARIS** (tokens DS), NO la paleta de los tableros Power BI de referencia.
- **Agregación 100% en SQL** (`GROUP BY`/`date_trunc`/`FILTER`); el frontend solo dibuja. Diseñado para escalar.

### Backend
Endpoints por vista en `bi.py`. Convenciones críticas:
- **Área vía subárea** (§27): JOIN `reclamos → tipo_reclamo → subarea → area`. `reclamos.id_area` legacy es NULL.
- **Mono-municipio**: filtro `(id_municipio = :m OR id_municipio IS NULL)` — los reclamos reales tienen `id_municipio` NULL (local Y prod). Filtrar estricto = BI vacío.
- Tiempo de cierre = `fecha_cierre - fecha_alta`; demora pendiente = `NOW() - fecha_alta`. Tramos 0-3 / 4-7 / +7 días.
- Subreclamos = `id_reclamo_padre IS NOT NULL` ("intervenciones" en la jerga de los tableros de referencia).
- El mapa de Pendientes reusa `modules/dashboard/components/DashboardMap.tsx` (Leaflet vanilla) — endpoint `/bi/pendientes-geo`.

### Datos demo (prod, 2026-05-26)
Los 30 reclamos de prod fueron poblados con `fecha_cierre` (resueltos) y `latitud/longitud` (todos) para que el BI tenga contenido. Backups `_backup_reclamos_fecha_cierre_2026_05_26` y `_backup_reclamos_geo_demo_2026_05_26`.

