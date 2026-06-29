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
| **Turnos** | — | **`modules/turnos/`** (5 tabs: Turnos / Agenda solo-turnos / Atendidos+PDF / Consultas por ciudadano / Prestaciones; historia de atención mig 86; autoservicio público; filtros prestación/recurso/ciudadano; scoping por nivel; cumplir dispara encuesta CSAT de turnos §42) | **React** (publicado) |
| **Entradas** | — | **`modules/entradas/`** (backoffice completo 2026-05-14 — lista de eventos con espacio + gestión de reservas reusando `ReservaModal` de Agenda; autoservicio ya funciona vía flujo público de eventos) | **React** (publicado) |
| **Dashboard** | — | **`modules/dashboard/`** (mapa Leaflet + stats reales) | **React — HOME del iframe** desde 2026-05-13 (se carga al entrar al shell y al hacer click en INICIO desde cualquier módulo) |
| **OT (3 mesas)** | — (borrado, era `ot_supervisor.html`/`ot_agente.html`/`ot_auditoria.html`) | **`modules/ot/`** (Supervisor / Agente / Auditoría + drawer detalle compartido) | **React** (publicado) |
| **Trámites** | — | **`modules/tramites/`** (backend Fase 1+2 + frontend Fase 3 completo — bandeja, detalle, acciones, timeline, adjuntos, pase, relacionar; 2026-05-16) | **React** (publicado) |
| **Datos (BI)** | — | **`modules/bi/`** (landing DATOS → Operativo + Ejecutivo. Operativo: 4 tabs Resumen/Resueltos-SLA/Pendientes+mapa/Subreclamos. Ejecutivo: placeholder. 2026-05-26) | **React** (publicado) |
| **Emergencias (COM)** | — | **`modules/emergencias/`** (Tablero dispatcher polling 30s + Recepción de llamado + Detalle FSM/historial; 2026-06-10, §44) | **React** (publicado — **PRIMER ítem del sidebar**) |
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
- **`check_rate_limit` clavea por el STRING pelado** (`middleware/rate_limit.py`): los endpoints públicos viejos pasan la IP a secas, así que **comparten bucket entre endpoints** (ej. 6 búsquedas geo pueden agotar el cupo del POST de emergencias de esa IP). Endpoint nuevo → **prefijar la clave**: `check_rate_limit(f"miflujo:{ip}", ...)` como `adjpub:`/`turnovec:` (2026-06-11). Los routers viejos quedan como están hasta decisión explícita.
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

### Modo oscuro — `[data-theme="dark"]` (desde 2026-06-12)

El DS tiene paleta dark: overrides de superficies/foregrounds/bordes/sombras bajo `:root[data-theme="dark"]` en `colors_and_type.css` (espejados en `web-app/src/styles/tokens.css`). Los tokens de marca (`--zaris-orange`, `--color-*`, `--prio-*`) NO cambian. Reglas:

- **Persistencia**: `localStorage` clave **`zaris_theme`** (`'dark'` | `'light'`/ausente). El toggle vive SOLO en el dropdown de usuario del shell (`menu.js`), que además propaga el cambio en vivo al documento del iframe.
- **Todo documento del backoffice lee el tema en un script inline de `<head>`, ANTES de los CSS** (evita flash claro): `index.html`, `web-app/index.html`, `frontend/{login,usuarios,admin_tablas}.html`. **HTML interno nuevo ⇒ copiar ese snippet.** Las páginas públicas del vecino (`alta-vecino.html`, `encuesta.html`) quedan SIEMPRE claras a propósito.
- **No hardcodear superficies claras**: usar tokens. Para overlays semitransparentes sobre mapas/imágenes existe `--surface-overlay` (claro u oscuro según tema — caso Dashboard). Los rgba claros que el shell necesita literales tienen su override en el bloque `[data-theme="dark"]` al final de `menu.css`.
- **Mapas Leaflet**: en dark usar tile CartoDB `dark_all` (mismo subdominio/attribution que Positron). `DashboardMap.tsx` lo elige leyendo `document.documentElement.dataset.theme` al montar.
- El avatar del topbar usa texto `#26251e` fijo (no `--fg-1`) porque el fondo durazno no cambia entre temas.

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

### Topbar — layout (izquierda · derecha) + Statusbar inferior

Desde 2026-05-13 el topbar tiene bloques fijos; desde 2026-06-12 hay además una **statusbar inferior** (espejo del topbar al pie, fila 3 del grid `52px 1fr 30px`). **El shell NUNCA scrollea**: `menu.css` resetea `html, body { margin:0; overflow:hidden }` (el margin default de 8px del body corría el grid 100vh y la statusbar caía bajo el borde — fix 2026-06-12; scrollean solo los módulos dentro del iframe):

| Barra · Posición | Contenido | IDs/clases |
|---|---|---|
| **Topbar · Izquierda** | `ZARIS` (logo+wordmark, link a inicio) · "GESTION ESTADO" (hardcoded, NO editable) · separador vertical · logo municipio (opcional, `<img>` hidden si no hay URL) · nombre municipio | `.brand` `.brand__name` `.brand__app` `.topbar__sep` `.muni` `#topbar-muni-logo` `#topbar-muni-nombre` |
| **Topbar · Derecha** | Campana de notificaciones · contexto de usuario en 2 líneas ("Nombre · Rol" + "Cargo: X" si el agente vinculado tiene cargo, via `cargo_nombre` de login/me) · avatar (foto `usuarios.foto_url` mig 88, o iniciales) · dropdown usuario (ver abajo) | `.topbar__bell` `.topbar__context-cargo` `.topbar__avatar` `.user-menu` |
| **Statusbar · Izquierda** | Estado del servidor: dot gris/verde/rojo + label ("Servidor operativo" / "Sin conexión…"), ping `GET /api/health` cada 60s + al volver de background | `.statusbar__api` `#statusbar-api` `#statusbar-api-label` |
| **Statusbar · Centro** | Fecha+hora "mar 13 may, 14:32", refresca cada 30s (**movida desde el centro del topbar**) | `.statusbar__clock` `#statusbar-clock` |
| **Statusbar · Derecha** | Versión `zaris-zge · v0.1` (movida del pie del sidebar — `.sidebar__foot` eliminado) | `.statusbar__version` |

La statusbar está pensada para crecer con más indicadores de estado (contenido a definir). **Los labels del sidebar van con mayúscula inicial** ("Reclamos", "Trámites" — pedido del usuario 2026-06-12); no hay `text-transform`, la capitalización vive en el HTML.

**"GESTION ESTADO" es interno del producto.** Vive hardcoded en el HTML como `<span class="brand__app">GESTION ESTADO</span>`. NO se puede editar desde UI ni se persiste en DB. Backend lo expone en `GET /api/v1/config/identidad` solo por compat con el shell vanilla. Si en el futuro alguien tiene que cambiar el nombre del producto, edita `index.html` y `backend/app/api/routes/config_identidad.py` (constante `APP_NOMBRE`).

**El nombre y logo del municipio SÍ son editables** desde el módulo Config → Identidad (ver §21 para las claves y §32 Quirk 13 para el flujo de upload). `menu.js` los carga al boot llamando a `GET /api/v1/config/identidad` (público).

**Cache-bust `?v=`:** los assets del shell (`menu.css`, `menu.js`) se cargan con `?v=YYYY-MM-DDx`. Bumpear ese sufijo cuando los edites o el navegador puede servir la versión vieja por días. Aplica también a JS/CSS de cualquier módulo vanilla.

### Topbar — menú de usuario (foto · modo oscuro · guías · logout)

El topbar del shell (`index.html`) tiene un dropdown al hacer clic en el nombre/avatar (rediseñado 2026-06-12):
- **Header**: avatar grande (foto o iniciales) + nombre completo + rol + "Cargo: X" (si el agente vinculado tiene cargo).
- **Cambiar foto…**: file picker PNG/JPG ≤2MB → `POST /auth/me/foto-upload-url` (URL firmada, bucket público `config-assets`, paths `usuarios/{id}/avatar-{uuid}.{ext}`) → PUT del binario directo a Storage → `PUT /auth/me/foto` persiste `usuarios.foto_url` (mig 88). Mismo flujo que el logo del municipio (§26). El feedback (Subiendo…/Foto actualizada/error) se muestra en el label del propio botón.
- **Modo oscuro**: toggle con switch — ver "Modo oscuro" en §13.
- **Guías de uso**: `shellNavigate('web-app/dist/index.html#/guias')` (módulo Guías §37).
- **Cerrar sesión**: `localStorage.removeItem('zaris_session')` + redirect a `frontend/login.html`.
- CSS en `frontend/css/menu.css` bajo `.user-menu*`; lógica en `frontend/js/menu.js` (`_renderUserUI()` re-renderiza topbar+dropdown tras subir foto; el refresh contra `/me` también se dispara si la sesión vieja no trae `cargo_nombre`).

IDs relevantes: `#user-menu-trigger`, `#user-menu-dropdown`, `#btn-logout`, `#btn-foto`, `#input-foto`, `#btn-theme`, `#theme-switch`, `#btn-guias`, `#topbar-avatar`, `#topbar-context`, `#user-menu-info`.

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
> - **`agentes`** (sesión 2026-05-26): sección "Horario de atención" (título real del `#horarioSec` en la UI — verificado 2026-06-12; franjas Lun-Dom bitmask + hora inicio/fin) que escribe en `disponibilidad_recurso` (tipo_recurso=agente) vía `/api/v1/agenda/disponibilidad` — alimenta la disponibilidad efectiva del agente en Agenda (§27).
> - **`equipos`** (sesión 2026-05-27): sección "Integrantes del grupo" — buscador de agentes con autocompletar (filtro en cliente sobre `GET /admin/agentes`, debounce; un `<select>` de 85 agentes es inusable §23) + lista editable con "Quitar". Sincroniza con `equipo_agentes` tras guardar el equipo (re-lee relaciones reales, soft-delete las quitadas, INSERT las nuevas), espejo de cómo agentes sincroniza sus franjas. Sin backend nuevo — usa el CRUD genérico de admin_tablas (`equipos` + `equipo_agentes`). Seed de mesas demo: `backend/seed_equipos_demo.py` (idempotente, resuelve subárea+agentes por nombre; 5 mesas en prod al 2026-05-27).
>   - **`equipos.tipo_grupo`** (mig 67): distingue **`mesa_tramites`** (recibe pases de Trámites §35: los integrantes ven en "Mi bandeja" lo pasado a esa mesa y cualquiera lo toma; **subárea opcional, SIN horario**) de **`trabajo_reclamos`** (cuadrilla que atiende reclamos/OT y se agenda; **subárea OBLIGATORIA** vía CHECK `ck_equipo_subarea_reclamos`, + sección de franjas igual que agentes que escribe en `disponibilidad_recurso(tipo_recurso='equipo')`; los 3 campos legacy `dias_semana/hora_inicio/hora_fin` de la tabla NO los lee la Agenda, por eso se sacaron del form. **OJO — desde mig 91 la Agenda NO lee la disponibilidad propia del equipo por defecto: usa la unión de sus agentes (§27); las franjas propias del equipo solo se usan con el override `equipos_sin_agentes_usan_horario_propio`.**). El form muestra/oculta la sección horario y marca la subárea requerida según el tipo (`_recursoHorario`/`_bindTipoGrupo`). Las franjas reusan `renderHorarioSeccion`/`_cargarFranjas`/`_sincronizarFranjas` parametrizados por `tipo_recurso`. Listado/preview: cuadrillas muestran "Grupo de trabajo · <subárea>", mesas "Mesa de entrada de trámites" (sin subárea) + badge "N integrantes".

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

**Estado general:** migraciones 20-91 aplicadas en local Y prod (Supabase) sin divergencia conocida al 2026-06-15 (90 = recovery interno + DNI agente; 91 = clave config `equipos_sin_agentes_usan_horario_propio` §27). La numeración 51 está duplicada (`51_notificaciones.sql` + `51_tramites_tipo_dato_direccion.sql`, ambas aplicadas) — **cualquier mig nueva debe usar 92+**.

**Reglas vivas de migración:**
- **Toda tabla nueva debe nacer con `ALTER TABLE ... ENABLE ROW LEVEL SECURITY`** (sin políticas = deny-all §26; el backend conecta como `postgres` dueño y bypassea RLS). Sino el advisor de Supabase la marca (`rls_disabled_in_public`, caso mig 80).
- **Seeds/INSERTs separados del DDL** en archivo aparte (`75b` es el patrón): `apply_migration` es atómico — un INSERT que falla revierte también los CREATE ([[feedback_apply_migration_parcial_aborta_todo]], incidente mig 69).
- **CHECK `NOT VALID` igual se evalúa al UPDATE de filas viejas** — backfillar en el mismo UPDATE ([[feedback_check_not_valid_se_evalua_al_update]], caso mig 71).
- En prod no hay `.env.prod`: aplicar por MCP (`apply_migration`/`execute_sql`).

**Dónde vive la regla de cada mig reciente:** 62-64 y 77-78 (usuarios/agentes/integridad) §39 · 65 (BI) §43 · 66/68/73/74/75 (Trámites) §35 · 67 (tipo_grupo equipos) §15 · 69-71 y 86 (Turnos) §33 · 72 (encuesta de turnos) §42 · 76/79 (alta vecinos) §38 · **81-85 (Emergencias) §44**. Bitácora por mig en `HISTORIAL_MIGRACIONES.md` ("Migraciones 61-79 — resumen consolidado" + entradas propias).

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

## 23. Patrones de UI ya validados — usar como default

Estos patrones se decidieron en sesiones anteriores y **deben reutilizarse** en lugar de inventar variantes. Si necesitás algo distinto, justificá por qué este no aplica.

### Direcciones: normalizar por OSM + geoposicionar con mapa y pin (REGLA DE DISEÑO)

**Todo formulario que cargue una dirección que deba quedar normalizada y georreferenciada debe ofrecer las DOS vías**, como la sección Ubicación del form de Reclamos (`web-app/src/modules/reclamos/views/FormView.tsx` — referencia canónica):

1. **Buscador OSM**: `GeocodingSearch` (acepta POIs — "frente al club X") o `AddressSearch` con `solo_direcciones=true` (solo calles). El pick normaliza el texto Y captura lat/lon.
2. **Mapa con pin manual**: `MapaPicker` de Reclamos (tile OSM Standard, §4) debajo del buscador. Click en el mapa o drag del pin fija/ajusta las coordenadas.

El input de dirección queda **editable sin borrar las coordenadas** (el pin del mapa es la fuente geo explícita y sigue visible), con hint mono que muestra las coords y botón "Quitar pin". Pedido explícito del usuario (test de uso humano, 2026-06-11). Implementado en Reclamos (`FormView`) y Emergencias (Recepción de llamado §44). Cualquier form nuevo con dirección georreferenciable replica este bloque.

**Sesgo geográfico OBLIGATORIO (2026-06-11):** el geocoding está **restringido a la zona del municipio** — buscar "Avenida Maipú" NO debe traer la de Mendoza. Implementado UNA sola vez en `backend/app/api/routes/geo.py::geocodificar_direccion` con `viewbox` + `bounded=1` de Nominatim (bbox = centro del municipio ± ~28 km; cubre el partido + CABA + linderos). Como TODOS los buscadores de dirección (backoffice `/geo/buscar`, alta pública, reclamos del vecino) pasan por ese helper, cualquier form nuevo lo hereda gratis — **no llamar a Nominatim por fuera del helper**. **Desde mig 87 el bbox es configurable** en `configuracion_general` (`geo_bbox_centro_lat`/`geo_bbox_centro_lon`/`geo_bbox_delta_grados`, editables en Config → Sistema §41; cache TTL 5 min en `geo.py::_bbox_municipio`, sesión propia `AsyncSessionLocal` porque corre también desde routers públicos). Las constantes `GEO_BBOX_*` quedan como fallback (claves ausentes/ inválidas/DB caída → Vicente López demo, el geocoding nunca se rompe por config). Deploy de otro municipio → ajustar las claves, no el código.

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

### Modales de mutación: cerrar AL CONFIRMAR, no en `onSuccess`
La latencia Railway↔Supabase (~2s, §27) hace que un modal que espera el `onSuccess` para cerrarse se perciba como "apreté Guardar y no hace nada" (queja real del test de uso humano de Emergencias, 2026-06-11). Patrón obligatorio: al confirmar, **cerrar el modal inmediatamente** y disparar la mutación; el resultado (éxito o error) llega por toast. Además, **resetear los campos del modal al abrir** (`useEffect(open)`) — los modales viven montados con `open=false` y un cancelar deja texto residual para el próximo uso (variante de §29). Implementado en los modales de Emergencias (`EventoAccionModals.tsx`, Dispatcher y Detalle); replicar en módulos nuevos. Excepción razonable: si el modal necesita datos de la respuesta para decidir qué mostrar (no para un toast), evaluar caso a caso.

### Pantallas-gate (redirección forzada) SIEMPRE con vía de escape + auto-curación

Si una pantalla captura al usuario por una condición de su cuenta (gate tipo "completá X para continuar", "cambiá tu contraseña"), debe cumplir TRES cosas o puede convertirse en un **deadlock sin salida**: (1) **botón de cerrar sesión** visible (vía de escape manual); (2) **re-validar la condición contra el backend al montar** (auto-curación: si el server dice que la condición ya no aplica, refrescar la sesión local y soltar al usuario — la sesión guardada puede estar desactualizada o haber nacido rota por un bug); (3) recordar que `/login` con sesión activa REBOTA (SoloInvitado), así que "que vuelva a loguearse" NO es vía de escape. Caso real 2026-06-12 (PWA Vecinos): el bug de `/activar` (SELECT sin `ficha_completa`, [[feedback_columna_nueva_auditar_todos_los_select]]) guardó sesiones con `false` y el gate de CompletarFicha atrapó al usuario sin logout, sin re-validación y con el form bloqueado — trifecta de deadlock que requirió hotfix doble (backend + auto-curación).

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
- **Pills de tipo de recurso** (4, con conteo desde `/recursos/conteos`): Agentes / Equipos·OT / Esp. atendidos·Turnos / Esp. eventos·Entradas. **NO hay opción "Todos"** (ver Performance). **Las pills NO son intercambiables** — cada una sirve a un módulo distinto: Equipos→asignación de OT, Esp. atendidos→Turnos, Esp. eventos→Entradas. **Pill inicial por rol (2026-06-12):** supervisor (nivel 2) aterriza en Equipos·OT; el resto en Agentes. Una vez por carga del bundle (flag `pillInicialAplicada` en `agendaStore` + effect en `VistasView`); después manda el click del usuario.
- **DnD solo en Vista Día y Semana** (`@dnd-kit/core@6.3.1`, PointerSensor + KeyboardSensor). Bloques tipo `evento` no son arrastrables (se editan desde el modal del evento).

### Convenciones del módulo

**FKs a las PKs reales:** `eventos.id_subarea`→`subarea.id_subarea`, `eventos.id_estado_evento`→`estado_evento.id_estado_evento`, `evento_reservas.id_ciudadano`→`ciudadanos.id_ciudadano`, `ocupaciones.id_orden_trabajo`→`ordenes_trabajo.id_ot`. `evento_encargados.id_recurso` y `ocupaciones.id_recurso` → `agentes`/`equipos`/`espacios_agenda` (sin FK física; polimórfica por `tipo_recurso`, validación en backend).

**Tabla única `ocupaciones`** con CHECK `ck_ocupacion_consistencia`: solo se popula la FK del `tipo` (`ot`→`id_orden_trabajo`, `evento`→`id_evento`, `turno`→`id_ciudadano`, **`bloqueo`→ninguna** — mig 89). El tipo `bloqueo` es el cierre manual de un recurso sin entidad asociada (espacio en mantenimiento, agente afectado a otra tarea): exige `motivo` (schema `OcupacionCreate`), vale para los 3 tipos de recurso y se renderiza gris en la grilla. `existe_recurso` (services/agenda.py) valida agente/equipo/**espacio** desde 2026-06-12 — antes espacio devolvía False y el POST manual de ocupación sobre espacio daba 404. No usar tablas separadas por tipo.

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

**Para `tipo_recurso='equipo'` (decisión 2026-06-15, mig 91):** la disponibilidad de una cuadrilla es la **UNIÓN de los horarios de sus agentes** activos (`equipo_agentes`), NO su horario propio. Helper `_disponibilidad_equipo_union` (espejo del caso "espacio atendido"). Equipo sin agentes → `[]`, **salvo override**: clave `configuracion_general.equipos_sin_agentes_usan_horario_propio` (default `false`, editable en Config → Sistema) — con `true` usa el horario propio del equipo. **Antes (≤ mig 67) la Agenda leía el horario propio del equipo y divergía del planificador de OT** (que ya hacía la unión); ahora ambos usan esta misma función. Aplica en `disponibilidad_efectiva` Y en `disponibilidad_efectiva_batch` (la batch pre-resuelve los agentes de cada equipo, igual que con espacios atendidos). Los 3 campos legacy `dias_semana/hora_inicio/hora_fin` de `equipos` y las franjas propias `disponibilidad_recurso(tipo_recurso='equipo')` **NO se usan** salvo override.

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
**Router `agenda_publico.py`** (`/api/v1/agenda/publico`, SIN auth — autoservicio de eventos §33): GET `/evento/{token_publico}` · POST `/evento/{token_publico}/reservar` (busca/crea ciudadano por DNI) · GET/DELETE `/reserva/{token_reserva}`. Tokens UUID, 404 genérico anti-enumeración.
Permisos: `nivel_acceso <= 2` muta (espacios/disponibilidad/novedades); cualquier autenticado lee. **Las mutaciones de `agenda_v2.py`** (eventos/encargados/reservas/ocupaciones/resolver-conflictos) **exigen nivel ≤ 3** vía dependency `require_operador` (desde 2026-06-12 — antes solo pedían JWT y un Consultor nivel 4 podía mutar por curl; espejo de [[guard_nivel_endpoint_no_solo_ui]]). Los GET de agenda_v2 siguen con `get_current_user` pelado.

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

**Variante: modal siempre montado con default derivado de props.** Un modal que vive montado con `open=false` y deriva su estado inicial de props (`useState(permiteX)`) congela el valor del PRIMER render (cuando todavía no había entidad elegida) y nunca lo re-deriva — y ofrece una acción que el backend rechaza. Fix: `useEffect(() => { if (open) { setEstado(permiteX); /* + reset de campos */ } }, [open, permiteX])`. Caso real: `CerrarModal` de Emergencias ofrecía "Cerrar como DESESTIMADO" sobre un evento EN_SITIO → 422 del FSM (cazado en QA navegador prod 2026-06-10).

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

> **Movido a la skill `modulo-permisos`** (`.claude/skills/modulo-permisos/SKILL.md`), que carga on-demand. Modelo híbrido (nivel mínimo por módulo + override por usuario), tablas `modulos`/`usuario_modulos`, catálogo, `modulos_permitidos`/`require_modulo`, endpoints `/admin/permisos` y filtrado del sidebar (`data-modulo`/`data-modulo-fallback`) viven ahí. Ancla §30 conservada para las refs cruzadas.
>
> **TRAMPA DE SEGURIDAD recurrente (transversal — no la olvides):** que el sidebar oculte un módulo NO protege sus endpoints. `require_modulo` casi no se usa — la mayoría de routers aplican su nivel con helpers locales. **Antes de asumir "el router ya valida nivel", leé el handler.** Ver [[guard_nivel_endpoint_no_solo_ui]].

## 31. Limpieza de estilos legacy — CERRADA (2026-05-12)

DS v1.0 (`--z-*`, `.z-*`, `frontend/styles.css`, `frontend/menu.html`, `frontend/mainconfig.html`, `frontend/agenda.*`, `shell.html`) eliminado del repo. Los módulos vanilla cargan componentes `*-zaris` de `design-system/components/*.css` (§13). `admin_tablas.html` usa tokens DS directos (0 `var(--z-*)`, solo conserva `.z-header*` oculto en iframe + clases internas `.btn-primary`/`.field`/`.modal` a propósito, §15). **Cero deuda de estilos legacy.** Bitácora completa (pasos + tabla de equivalencias `--z-*`→DS, útil solo si reaparece un módulo vanilla) en `HISTORIAL_MIGRACIONES.md`.

## 32. Build de `web-app/dist/` y testing local del shell vanilla + bundle

> **Recetas operativas en la skill `win-quirks`** (`.claude/skills/win-quirks/`). Invocarla al buildear/commitear `web-app/dist/`, levantar servers locales (http.server/uvicorn/pnpm dev), correr psql, lanzar procesos detached con `Start-Process`, o diagnosticar redirects rotos bajo `/zaris-zge/`. Cubre los 14 quirks que rompen silenciosamente en Windows.

**Reglas que NO podés olvidar (las recetas para cumplirlas están en la skill):**
- Antes de commitear `dist/`: buildear modo prod (sin `VITE_API_BASE` en el shell) y verificar que apunte a Railway, no a `127.0.0.1`.
- `vite build` compila el WORKING TREE, no lo staged — commitear fuentes primero o stashear lo ajeno antes de rebuildear.
- El bundle standalone en prod debe redirigir al shell vanilla (script en `web-app/index.html` + whitelist en `menu.js`, §14). Nunca `window.location.href='/...'` absoluto desde el bundle (rompe bajo `/zaris-zge/`, [[feedback_redirect_iframe_subpath]]).
- **Tras pushear un commit que toca `web-app/**` SIN `[skip ci]`, el workflow `deploy-web-app.yml` rebuildea el dist en CI y puede commitear `build(web-app): publicar dist [skip ci]` a `main` ~1-2 min después** (el build Linux normaliza los line endings del index.html buildeado en Windows — diff de ~38 líneas, no funcional). Consecuencia: `git fetch` + `git pull --rebase` ANTES del próximo push o rebota con non-fast-forward (cazado 2026-06-10/11, commits `fe8722a`/`73bc3d0`).

## 33. Módulos Turnos y Entradas

> **Movido a la skill `modulo-turnos-entradas`** (`.claude/skills/modulo-turnos-entradas/SKILL.md`), que carga on-demand. Modelo de prestaciones (mig 71), recurso copiado al turno, ocupación espejo, historia de atención (`turno_atencion`), scoping por nivel, endpoints, frontend (5 tabs), Entradas (eventos con `id_espacio`) y los autoservicios públicos viven ahí. Ancla §33 conservada para las refs cruzadas.

## 34. Módulo OT — frontend dedicado del Supervisor (crear OT + agendar en una pasada)

> **Movido a la skill `modulo-ot`** (`.claude/skills/modulo-ot/SKILL.md`), que carga on-demand. Flujo del supervisor (crear OT + agendar), `PlanificadorOT`, slots libres por recurso, auto-asignar, las 3 mesas (Supervisor/Agente/Auditoría), guard de nivel ≤2, bypass `es_auditor` de admin y adjuntos de evidencia de OT (`ot_adjuntos`) viven ahí. Ancla §34 conservada para las refs cruzadas.

## 35. Módulo Trámites / Expedientes

> **Movido a la skill `modulo-tramites`** (`.claude/skills/modulo-tramites/SKILL.md`), que carga on-demand. Filosofía catálogo/instancia, tablas (catálogo + instancias + aprobaciones por etapa), migraciones, seeds, endpoints (operativo + admin builder), servicios, reglas críticas (firma, retención/purga, cron), storage Supabase y todos los quirks viven ahí. Ancla §35 conservada para las refs cruzadas.

## 36. Generación de manuales operativos (HTML autocontenidos)

> **Receta completa en la skill `generar-manual`** (`.claude/skills/generar-manual/`): setup Playwright, patrón de captura, convenciones del HTML, regenerar capturas tras cambio de UI, cleanup. Invocarla al crear/regenerar un `docs/manual_<modulo>.html`.

### Manuales actuales (al 2026-06-12)
**Todos viven en `docs/` (carpeta única, pedido del usuario).** `manual_reclamos.html` (Operador+, 10 caps) · `manual_ot.html` (Sup/Agente/Auditor, 9) · `manual_tramites.html` (Operador+, 8) · `manual_admin_tramites.html` (Admin/Sup, 12) · `manual_encuestas.html` (Sup/Admin, texto sin caps) · `manual_turnos.html` (Operador+, 9 caps, 13 secc. — incluye historia de atención, detalle de turno y consultas por ciudadano, 2026-06-11) · `manual_entradas.html` (Operador+, 4 caps, 10 secc.) · **`manual_alta_ciudadanos.html`** (Operador+, 3 caps, 7 secc. — alta por agente + autogestión + URL pública/Config; actualizado 2026-06-12 al alta en un paso §38) · **`manual_emergencias.html`** (Operador+, 10 caps, 10 secc. — COM: recepción, triage, FSM, derivación, App Vecinos, 2026-06-10) · **`manual_alta_vecino.html`** (público, para el vecino, sin caps, 6 secc. — un paso + vía "ya registrado", 2026-06-12) · **`manual_ciudadano.html`** (público, para el vecino, sin caps, 10 secc. — TODAS las interacciones del ciudadano: cuenta/portal, reclamos, emergencias, turnos con y sin cuenta, entradas+QR, trámites presenciales, notificaciones push, encuesta CSAT, troubleshooting; cross-linkeado desde `manual_alta_vecino.html` §5, 2026-06-12) · **`manual_agenda.html`** (Sup+ config / Operador+ consulta, 12 caps, 13 secc. — calendario único: 4 vistas de recurso, Día/Semana/Mes, disponibilidad efectiva, eventos+reservas+QR, feriados/novedades, conflictos, espacios, circuitos OT/Turnos/Entradas; 2026-06-12). **10 registrados en el módulo Guías (§37); `manual_alta_vecino.html` y `manual_ciudadano.html` NO van en Guías** — son guías públicas del vecino (no material de backoffice); el primero se abre desde "¿Cómo me doy de alta?" en `frontend/alta-vecino.html`, el segundo es para compartir en web/redes del municipio. Próximos sugeridos (no obligatorios): Padrones.

### Reglas de criterio (no las olvides)
- **Sin fechas ni nombres personales (mandatorio, 2026-06-11).** Los manuales NO llevan fecha (ni encabezado, ni pie, ni "generado el…") ni el nombre del usuario — solo aplicación, módulo y audiencia. Ver memoria [[feedback_manuales_sin_fechas_ni_nombres]].
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

> **Movido a la skill `modulo-app-vecinos`** (`.claude/skills/modulo-app-vecinos/SKILL.md`), que carga on-demand. Modelo scope `publico` vs `agente`, tablas (credencial/canal/push), endpoints de auth, activación/recovery/lockout/anti-enumeración, alta pública en UN PASO (ficha completa), alta por agente, autoservicio logueado del vecino, push y quirks viven ahí. La PWA `zaris-vecinos` NO se documenta acá (repo separado). Ancla §38 (y sub-refs §38 mono-municipio) conservada para las refs cruzadas.

## 39. Módulo Usuarios — estado y deuda crítica (QA 2026-05-19)

> **Movido a la skill `modulo-usuarios`** (`.claude/skills/modulo-usuarios/SKILL.md`), que carga on-demand. Stack vanilla, form (subárea/externo), módulos permitidos, auditoría de login (`usuario_login_log`), regla 1:1 agente↔usuario, invariante de integridad de cuentas (cron sin-vínculo mig 77), clave temporal + cambio forzado (mig 78) y login por email exacto viven ahí. Ancla §39 conservada para las refs cruzadas.

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

> **Cuerpo del módulo movido a la skill `modulo-config`** (`.claude/skills/modulo-config/SKILL.md`), que carga on-demand. Los 4 tabs (Identidad, Permisos por usuario, Catálogo de módulos, Sistema tipado), los bugs de navegación en iframe (`window.location` absoluto, `NavLink` relativo) y el quirk de `configuracion_general.tipo` NOT NULL en prod viven ahí. Ancla §41 conservada para las refs cruzadas. **El "Estándar OBLIGATORIO: verificar navegación/UI en la interfaz" de abajo es transversal y QUEDA acá** (aplica a cualquier módulo React, no solo Config).

### Estándar OBLIGATORIO: verificar navegación/UI en la interfaz, no en el código

**Todo cambio de navegación/routing/UI se verifica abriendo el navegador y reproduciendo el flujo real ANTES de declararlo terminado.** Para el humano la realidad vive en la interfaz; el código es una hipótesis. Endpoint que existe + tipo que matchea + ruta mapeada pueden seguir dando pantalla rota. Procedimiento (memoria [[feedback_verificar_forms_navegando_mandatorio]]):

1. Entorno correcto: prod si ya está deployado, o local con proxy `/zaris-zge/` si toca subpath.
2. **Confirmar que el iframe carga el bundle NUEVO** antes de juzgar — GH Pages puede servir el nuevo pero el iframe sirve el viejo cacheado (§ memoria iframe cache). Cache-bust: `frame.src='about:blank'` → `frame.src='...?_cb='+Date.now()+'#/ruta'`, verificar el hash del `<script src>` del iframe = último commit.
3. Recorrer **TODAS las vías de navegación que el usuario tiene a mano**: cada tab/botón, ida y vuelta, saltando entre secciones. NO entrar a cada vista por URL directa — eso oculta bugs de links relativos. El gesto humano es clickear, no tipear URLs.
4. Recién entonces declarar verificado. Si no lo hice, decirlo explícito.

> Caso 2026-05-22: declaré "Config completado" dos veces con bugs vivos porque verifiqué entrando por URL directa (no clickeando tabs) y porque el iframe servía bundle cacheado. "Entré a la URL y cargó" ≠ "navegué el módulo como un usuario".

## 42. Módulo Encuestas (CSAT) — Reglas de negocio

> **Movido a la skill `modulo-encuestas`** (`.claude/skills/modulo-encuestas/SKILL.md`), que carga on-demand. Tablas, disparo automático (reclamos + turnos), `encuesta_envio` polimórfico, anti-fatiga, delay/expiración, dispatcher (`X-Dispatcher-Token`), form público por token, email vía Resend, sanitización PII y quirks SQL viven ahí. Ancla §42 conservada para las refs cruzadas.

## 43. Módulo Datos (BI — Análisis de datos)

> **Movido a la skill `modulo-bi`** (`.claude/skills/modulo-bi/SKILL.md`), que carga on-demand. Estructura Landing→Operativo, reglas obligatorias de visualización (Recharts 2.15, etiqueta de total + pastilla oscura, drill-down, Exportar CSV), convenciones de backend (área vía subárea, mono-municipio con `id_municipio` NULL, agregación 100% en SQL) y datos demo viven ahí. Ancla §43 conservada para las refs cruzadas.

## 44. Módulo Emergencias (COM)

> **Movido a la skill `modulo-emergencias`** (`.claude/skills/modulo-emergencias/SKILL.md`), que carga on-demand. DB/migs, FSM de eventos, denunciante polimórfico, numerador anual, permisos por subárea, frontend React (tablero/recepción/detalle), endpoint público App Vecinos y smoke viven ahí. Plan completo en `PLAN_MODULO_EMERGENCIAS.md`. Ancla §44 (y la sub-referencia §44-permisos) conservada para las refs cruzadas.

## 45. Hilo conductor común — `ESTADO.md` versionado (sincronización Cesar ↔ Roy)

Trabajamos **dos personas con Claude Code separados** (Cesar `CesarZeta` admin + Roy `roymanrafael` write). La memoria privada de Claude Code de cada uno **NO la ve el otro** — por eso el estado de avance y los pendientes **NO pueden vivir solo ahí**. La única superficie compartida es el **repo git**. Por eso existe un archivo **`ESTADO.md` versionado en la raíz de cada repo** (`zaris-zge` y `zaris-vecinos`): es el **hilo conductor común**, lo PRIMERO que se lee al retomar y lo que se ACTUALIZA al cerrar sesión.

- **Qué es:** documento **vivo y corto** — foto del estado actual (En curso / Pendientes / Hecho reciente / mapa de fuentes de verdad). NO es bitácora histórica (eso vive en `HISTORIAL_MIGRACIONES.md`, `PLAN_*.md` y la memoria privada de cada uno).
- **Un `ESTADO.md` por repo:** el de `zaris-zge` cubre backoffice/backend; el de `zaris-vecinos` cubre la PWA. Cada uno linkea al otro. El que trabaja en un repo lee/edita el `ESTADO.md` de ESE repo.
- **Regla de oro (la que evita la desincronización que motivó esto):** **todo pendiente o avance que el otro colaborador necesite saber va al `ESTADO.md` (o al `PLAN_*.md` correspondiente), NO solo a la memoria privada.** Si un pendiente vive únicamente en tu memoria de Claude Code, el otro NO lo ve y va a chocar. La memoria privada es complemento personal, nunca la fuente de verdad compartida.
- **Cuándo se actualiza:**
  - **Al cerrar sesión** (skill `/cierre-sesion`, paso 4): actualizar el/los `ESTADO.md` afectados **ANTES** de volcar a la memoria privada. Si la sesión tocó la PWA, actualizar también `zaris-vecinos/ESTADO.md`.
  - **Al iniciar / pedir estado** (skill `/estado-proyecto`): leer el/los `ESTADO.md` como primer insumo del estado conceptual (antes que la memoria privada, que puede estar atrasada respecto de lo que pusheó el otro).
- **Mantenerlo corto:** "Hecho reciente" se poda (máx ~10 líneas); lo viejo se borra (ya está en el historial). Verificar contra git/prod antes de declarar algo hecho (`feedback_verificar_siempre_antes_de_opinar`).
- **Roadmaps detallados** siguen en `PLAN_APP_VECINOS.md` / `PLAN_MODULO_EMERGENCIAS.md`; el `ESTADO.md` los apunta, no los duplica.

