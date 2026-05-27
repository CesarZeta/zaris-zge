# Reglas Mandatorias de Desarrollo — ZARIS

> **Mantenimiento de este documento:** acá van *reglas* (qué hacer siempre), no *bitácora* (qué pasó una vez). El detalle histórico de migraciones aplicadas vive en [`HISTORIAL_MIGRACIONES.md`](HISTORIAL_MIGRACIONES.md) — al cerrar una migración, su bitácora va ahí, no acá. La numeración de secciones (`§N`) tiene huecos históricos (§8/§16/§25): **no renumerar** (hay cientos de refs cruzadas). Criterio completo en memoria `feedback_mantenimiento_doc_y_memorias`.

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

Los módulos React viven en `web-app/src/modules/<nombre>/`. Se publican como build estático de Vite a GitHub Pages y el shell vanilla los carga en su iframe. **Antes de empezar leer §4 y §14** para entender el contexto.

### Crear el módulo

1. `web-app/src/modules/<nombre>/index.ts` exporta un `ModuleManifest` (ver `web-app/src/lib/types.ts`).
2. Importar el manifest en `web-app/src/modules/index.ts` (array `modules`).
3. El AppShell del shell React contenedor (solo visible en `localhost:5173` durante desarrollo) lee el array y lo agrega al sidebar y al router. Esto **NO** afecta producción.
4. Para que el módulo sea accesible en producción, agregar un `<a class="nav-flat__item" href="web-app/dist/index.html#/<nombre>/<ruta>" data-modulo="<codigo>">` en `index.html` (raíz, dentro del `nav-flat`).
5. **Si el ítem lleva `data-modulo="<codigo>"`, ese código DEBE existir como fila en la tabla `modulos` (catálogo de permisos §30) — sino el ítem queda OCULTO para TODOS los usuarios (incluido admin), porque `modulos_permitidos` nunca lo incluye.** `menu.js` filtra cada `data-modulo` contra `user.modulos_permitidos`; un código sin fila en `modulos` no se resuelve y queda `a.hidden=true`. Insertar la fila con migración formal (`INSERT INTO modulos (modulo_codigo, nombre, min_nivel_acceso, ...) ... ON CONFLICT DO NOTHING`), aplicada en local Y prod (§24). Si el módulo es informativo y debe verlo cualquiera, NO le pongas `data-modulo` (ej. Guías). El gating por nivel del propio módulo React (ej. `WrapNivel`) es independiente de esto: un admin entra por nivel aunque su sesión cacheada no tenga el código todavía — pero el ítem del sidebar igual se oculta hasta que la fila exista y la sesión se refresque. Cazado 2026-05-26 con Encuestas (mig 61). Ver [[feedback_modulo_react_necesita_fila_en_modulos]].

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
`agentes`, `equipos`, `equipo_usuarios`, `equipo_agentes`, `servicios`, `tipo_usuario`, `cargos`, `area`, `subarea`, `tipo_reclamo`, `tipo_representacion`, `actividades`, `nacionalidades`, `estado_reclamo`, `estado_ot`, `configuracion_general`, `lugares_atencion`, `agenda_clase`, `agenda_feriado`.

> `reclamos_area` y `reclamos_subarea` fueron eliminadas de admin_tablas en migración 20. El módulo Reclamos usa las tablas generales `area` y `subarea`.

> **`usuarios` es READ-ONLY en admin_tablas (sesión 2026-05-26).** GET sigue habilitado (selects FK de otras tablas: `agentes.id_usuario`), pero POST/PUT/DELETE devuelven **403** (`READ_ONLY_TABLES` en `admin_tablas.py`). Usuarios se administra SOLO desde su pantalla propia `frontend/usuarios.html` (hashea password + audita login). El ítem "Usuarios" se quitó del sidebar de Maestros y el `SCHEMAS.usuarios` del front.

> **Form de `agentes` es INLINE, no modal (sesión 2026-05-26).** `INLINE_FORM_TABLES = {agentes}` en `admin_tablas.html`: el form se renderiza en el flujo de la página (`#inlineForm`, fuera de `#main` para sobrevivir el re-render de `cargarTabla`), no en el modal genérico. Motivo: el agente crece en campos. Incluye sección "Horario de asistencia" (franjas Lun-Dom bitmask + hora inicio/fin) que escribe en `disponibilidad_recurso` (tipo_recurso=agente) vía `/api/v1/agenda/disponibilidad` — alimenta la disponibilidad efectiva del agente en Agenda (§27). El resto de tablas siguen con el modal genérico.

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

**Estado general:** migraciones 20-66 aplicadas en local Y prod (Supabase) sin divergencia conocida al 2026-05-27. La numeración 51 está duplicada (`51_notificaciones.sql` + `51_tramites_tipo_dato_direccion.sql`, ambas aplicadas) — **cualquier mig nueva debe usar 67+**. Migs 62-64 (sesión 2026-05-26): 62 `usuarios.fecha_ultimo_login` + tabla `usuario_login_log` (auditoría de accesos); 63 `agentes.cuil`; 64 índice UNIQUE parcial `agentes.id_usuario WHERE NOT NULL` (regla 1:1 agente↔usuario, §39). Mig 65: fila `modulos.bi` (nombre "Datos", nivel 2) para el módulo BI §43. **Mig 66 (sesión 2026-05-27): `tramite.id_agente_actual` + CHECK `ck_tramite_destinatario` ampliado a 4 ramas (NULL/subarea/equipo/agente) — habilita destinatario directo a un agente (§35).**

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
Para sumar adjuntos a otra entidad (ej: OTs), replicar el patrón: nueva tabla `<entidad>_adjuntos` con mismos campos, nuevo bucket si conviene aislar, y reutilizar `app/core/storage.py` (las funciones reciben `path` arbitrario y leen el bucket de settings — extraer a parámetro si se usan múltiples buckets). **Ya hecho para OT** (`ot_adjuntos`, mig 54, ver §34) — reusa el mismo bucket `reclamos-adjuntos` con paths bajo `ot/{id_ot}/`. Es la referencia canónica para clonar a futuras entidades.

## 27. Módulo Agenda

> **Bitácora de implementación** (migraciones 30-43, seeds demo, sub-fases entregadas, pendientes cerrados) en [`HISTORIAL_MIGRACIONES.md`](HISTORIAL_MIGRACIONES.md). Acá quedan las reglas vivas. Estado: backend (22 endpoints `agenda_v2.py` + espacios + disponibilidad) y frontend React (`web-app/src/modules/agenda/`) en producción. Ver memoria [[project_agenda_espacios_disponibilidad]].

### Estructura del módulo (cierre B2, 2026-05-14)

- **4 tabs** en `AgendaLayout`: **Vistas / Eventos / Conflictos / Config**. Dentro de Vistas, sub-toggle **Día / Semana / Mes** (persistido en `agendaStore.vistaGrilla`). URLs viejas `/agenda/timeline`, `/agenda/mensual` redirigen a Vistas.
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

Resuelve los rangos horarios efectivos para una fecha aplicando bitmask `dias_semana` + ventana `vigente_desde/hasta`. Para `tipo_recurso='espacio'`:
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
Devuelve 403 si el usuario no tiene el módulo. **`require_modulo` casi no se usa** — la mayoría de routers aplican su propio criterio de nivel con helpers locales (`_require_gestion` en reclamos, `_require_supervisor` en OT). La UI filtra el sidebar por módulo, pero eso NO impone nada en el backend.

> **OJO — esto es una trampa de seguridad recurrente.** Que el sidebar oculte un módulo NO protege sus endpoints. Hasta 2026-05-20, el router OT (`POST /ot`, `/ot/con-agenda`, `GET /mesa/supervisor`) NO chequeaba nivel: un operador con JWT válido los llamaba directo y creaba/asignaba OT (hallazgo QA #2). **Antes de asumir que "el router ya valida nivel", verificalo** — leé el handler y confirmá que invoca un `_require_*` o `require_modulo` como primera línea. Si no, es bug aunque la UI lo oculte. Ver memoria [[guard_nivel_endpoint_no_solo_ui]].

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

Gestión de expedientes administrativos tipo "ventanilla" (entrada de documentación → circuito interno → resolución). Diseñado para flujos multi-área, firmas digitales y numeración correlativa por tipo.

### Filosofía de diseño

- **Separación catálogo / instancia**: el catálogo (`tipo_tramite`, `tipo_tramite_version`, `_campo`, `_estado`, `_transicion`, `_documento_requerido`) define el FSM y los campos de cada tipo de trámite. Las instancias (`tramite`, `tramite_movimiento`, `tramite_documento`, `tramite_firma`) son los expedientes reales.
- **Versionado del circuito**: cada tipo tiene versiones numeradas (`tipo_tramite_version`). Un trámite instanciado queda vinculado a la versión que estaba publicada al momento de crearse — cambiar el circuito no altera trámites en curso.
- **FK circular diferida**: `tipo_tramite.id_version_publicada → tipo_tramite_version` y `tipo_tramite_version.id_tipo_tramite → tipo_tramite` se resuelven con `DEFERRABLE INITIALLY DEFERRED`.
- **Numeración atómica**: `tipo_tramite_numerador` con `INSERT ... ON CONFLICT DO UPDATE SET ultimo_numero + 1 RETURNING` evita race conditions. Formato: `{prefijo}{sep}{codigo_municipio}{sep}{anio}{sep}{correlativo_padded}` → ej. `POD-LPL-2026-0001`.
- **Ledger append-only**: `tramite_movimiento` registra cada acción (creacion, pase, cambio_estado, firma, etc.) como fila nueva. Nunca se modifica.
- **Iniciador polimórfico**: `iniciador_tipo ∈ {ciudadano, empresa, area_interna}` + CHECK que enforce exactamente una de `{id_ciudadano_iniciador, id_empresa_iniciadora, id_subarea_iniciadora}` según el tipo.
- **Destinatario polimórfico**: `destinatario_actual_tipo ∈ {subarea, equipo, agente}` + CHECK `ck_tramite_destinatario` con 4 ramas (NULL / subarea / equipo / agente), exactamente una de `{id_subarea_actual, id_equipo_actual, id_agente_actual}` poblada según el tipo. **`agente` = destinatario directo a una persona** (mig 66, sesión 2026-05-27): pasar a un agente le asigna el trámite a esa persona (aparece en SU bandeja, nadie más lo toma). Fiel al modelo Mesa Digital de VL (origin/destination con tipo `user|area|subarea|group`). **Si agregás una ruta nueva que cambie el destinatario o lleve a estado final, el UPDATE DEBE setear las 3 FKs (`id_subarea_actual`/`id_equipo_actual`/`id_agente_actual`) coherente con el tipo, o viola el CHECK** — cazado en `transicionar_tramite`, que omitía `id_agente_actual` y habría tirado 500 al transicionar un trámite ya asignado a un agente. Ver [[project_tramites_destinatario_agente_y_mi_bandeja]].

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

**Migración 050 (`50_tramites_auditoria.sql`, aplicada local + prod 2026-05-16):** agrega `id_usuario_alta` e `id_usuario_modificacion` a las 5 tablas de instancias (`tramite`, `tramite_movimiento`, `tramite_documento`, `tramite_firma`, `tramite_relacion`). Idempotente (`ADD COLUMN IF NOT EXISTS`).

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

**Rutas:** `/tramites` (bandeja) + `/tramites/mi-bandeja` (Mi bandeja) + `/tramites/nuevo` (alta) + `/tramites/:numero` (detalle). Hash router compatible con GH Pages. La ruta `mi-bandeja` va ANTES de `:numero` (param greedy).

**Módulo en catálogo DB:** `modulos (modulo_codigo='tramites', min_nivel_acceso=3)` — insertado en prod 2026-05-16.

### Mi bandeja + pases a agente (✅ ENTREGADO 2026-05-27)

Vista "Mi bandeja" (tab nuevo en `TramitesLayout`, NO ítem de sidebar — comparte el permiso `tramites`) donde el agente ve sus trámites y hace pases/toma inline. Dos endpoints nuevos en `routes/tramites.py`, ambos registrados **ANTES** de `GET /{numero_o_id}` (param greedy, §5):

- **`GET /api/v1/tramites/mi-bandeja`**: resuelve server-side los colectivos del agente (mi subárea + mis equipos/mesas + asignado a mí como `agente` + tomado por mí). El `GET /tramites` general NO sirve para esto: solo filtra `destinatario_tipo`+`id` único, no "cualquiera de mis colectivos". **El tab viejo "Mis trámites"/"Mi subárea" de `BandejaTramites` mandaba `mis_tramites:true`/`mi_subarea:true` que el backend IGNORA silenciosamente — nunca filtró; se quitaron esos tabs.** Filtros: `estado_codigo`, `tipo_codigo`, `sin_tomar`, `q`.
- **`GET /api/v1/tramites/destinatarios?q=`**: opciones de pase agrupadas (agentes / equipos / subáreas). Quirk asyncpg: `:q IS NULL` → `AmbiguousParameterError`; usar `CAST(:q AS text) IS NULL`.

Frontend: `pages/MiBandeja.tsx` (tomar + pasar por fila) + `ModalPase` ampliado a 3 solapas (Agente / Mesa(equipo) / Subárea) con buscador sobre `/destinatarios`. `usePasarTramite`, `pasarTramite`, `PaseIn.destinatario_tipo` y el type `DestinatarioTipo` ahora aceptan `'agente'`. La mesa = `equipos` existente (no hay concepto nuevo de "grupo de mesa"). Ver [[project_tramites_destinatario_agente_y_mi_bandeja]].

> **Fix colateral mismo commit:** `admin/modals/_modalShell.tsx` (los 6 modales del editor de tipos) no scrolleaba — caja `maxHeight:90vh; overflow:hidden` pero body sin `overflow-y`, dejando inaccesibles los botones de abajo en forms largos. Fix: body `flex:1; minHeight:0; overflowY:auto` (header fijo, body scrollea). Patrón a replicar en cualquier modal con cap de altura.

**Seed prod:** 9 tipos, 21 trámites demo. Seed idempotente en `backend/seed_tramites.py`.

### Visor de documentos (✅ ENTREGADO 2026-05-18)

`VisorDocumento.tsx` reemplaza el `<a target=_blank>` que estaba roto en `ListaDocumentos.tsx` (el endpoint `/documentos/{id}/contenido` solo acepta auth por header `Authorization`, no por `?token=` query param). Botones nuevos: **Ver** (abre visor inline) y **Descargar** (fetch + anchor con `URL.createObjectURL`).

**Dependencias:** `react-pdf@10.4.1` + `pdfjs-dist@5.4.296` (pin obligatorio — `react-pdf` 10.4 declara `pdfjs-dist@5.4.296` exacto; pnpm puede instalar `5.7.x` que falla con `UnknownErrorException: API version "5.4.296" does not match the Worker version "5.7.284"`). Worker importado con `import pdfWorkerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url'` y asignado a `pdfjs.GlobalWorkerOptions.workerSrc`.

**Quirks resueltos al implementar:**
- **Bug pre-existente en `DetalleTramite.tsx`:** la página pasaba `documentos={[]}` hardcoded a `ListaDocumentos`, NUNCA llamaba a `obtenerDocumentos`. Además `obtenerDocumentos` esperaba `TramiteDocumento[]` plano pero el endpoint devuelve `{numero_expediente, documentos:[], total}`. Fix: tipar el wrapper + agregar `documentos` al hook `useTramite` + pasar `docsData` real.
- **Shape de respuesta `/documentos`:** el endpoint NO devuelve `hash_sha256`, `nombre_archivo_original`, `agente_subio_nombre` ni `asignado_a.{tipo,id,nombre}` rico — solo `asignado_nombre` plano. `types.ts` los marcó opcionales y `ListaDocumentos`/`ModalFirma` ya soportan ambos shapes con `?? '—'`.
- **HTTP cache cazó el binario viejo durante la verificación:** `fetch()` default usa el cache del browser; con `Last-Modified` de FastAPI puede devolver 304 + body cacheado. Fix: `cache: 'no-store'` en `descargarDocumentoBlob`. Si en el futuro agregás otro helper que sirva binarios autenticados, replicar.
- **Path de `services/tramites/documentos.py` (fix 2026-05-19):** `UPLOADS_BASE` se resuelve desde `Path(__file__).resolve().parents[3] / "uploads"`, independiente del cwd. `storage_path` es relativo a `UPLOADS_BASE` (sin prefijo `uploads/` ni `backend/`). Si aparece carpeta `backend/backend/` en `git status`, es artefacto de uploads previos al fix — borrar con `rm -rf backend/backend`.

### Notificaciones a la bandeja (✅ ENTREGADO 2026-05-18)

Sistema in-app + email cuando un trámite entra a la bandeja del destinatario (creación, pase, transición que cambia destinatario).

**Migración 51 (`51_notificaciones.sql`):** crea `notificacion` (estándar §10 + columnas in-app: `id_usuario`, `tipo`, `titulo`, `mensaje`, `url_destino`, `recurso_tipo`/`recurso_id` polimórfica, `leida`/`leida_en`, `enviada_mail`/`enviada_mail_en`). Índices: `(id_usuario, leida, fecha_alta DESC)` parcial sobre `activo=TRUE` y `(recurso_tipo, recurso_id)`. **Aplicada en local y prod al 2026-05-18.**

**Backend nuevo:**
- `app/core/config.py` aporta las vars de email (hoy `RESEND_API_KEY`/`RESEND_FROM` — ver §42; originalmente `SMTP_*`, ya migrado a Resend) + `APP_BASE_URL`. Sin key configurada, el sender corre en modo MOCK (log a stdout, no rompe el flow).
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

**Envío de email — migrado de SMTP Zoho a Resend (API HTTP) el 2026-05-24.** El setup SMTP Zoho original quedó OBSOLETO (Railway bloquea egress SMTP). Toda la config de email vive ahora en **§42 "Email vía Resend"**: vars `RESEND_API_KEY`/`RESEND_FROM`, remitente `notificaciones@zaris.com.ar` (dominio raíz verificado), modo MOCK cuando falta la key. NO usar `SMTP_*` ni `smtp.zoho.com` — esas vars se borraron del config.

> **Quirk vigente (no específico de email):** reinicio de uvicorn obligatorio al cambiar `.env.local`. Las settings se cargan UNA VEZ al startup. `Start-Process python` sin matar el proceso anterior puede dejarlo corriendo con vars viejas (verificar `Get-Process python ... StartTime` antes del smoke). Memoria [[feedback_uvicorn_settings_no_recarga]].

**Campana en shell vanilla (✅ ENTREGADA 2026-05-18 — bug cazado en smoke prod):**

Durante el smoke end-to-end en prod del 2026-05-18 se confirmó que la campana React (`NotificacionesDropdown.tsx`) vive en `TopBar.tsx` que **se auto-oculta en iframe** (regla §14). Como en prod los usuarios viven embebidos en el shell vanilla, **la campana React es invisible**. Solo aparece en `localhost:5173` standalone (dev). El backend insertaba notifs OK y mandaba mails reales, pero el usuario nunca veía el badge.

Fix: campana funcional implementada en el shell vanilla, consumiendo los mismos endpoints `/api/v1/notificaciones`:

- `index.html`: bell + dropdown HTML (IDs: `topbar-bell`, `topbar-bell-badge`, `notif-menu-dropdown`, `notif-menu-list`, `notif-menu-mark-all`).
- `frontend/css/menu.css`: estilos `.notif-menu__*` (badge naranja, dropdown card, item con dot para no-leídas, hover).
- `frontend/js/menu.js`: bloque "Campana de notificaciones" con `_refrescarNotifBadge` (polling 30s), `_cargarNotifLista` (al abrir), `_onClickNotif` (marca leída + navega via `shellNavigate('web-app/dist/index.html#/tramites/...')`). Cierra con click-outside + Escape. Refresh extra en `visibilitychange` (volver de background).
- Cache-bust `?v=2026-05-18a` en menu.css/menu.js.

**Las DOS campanas conviven sin colisión** porque viven en DOMs distintos (shell vanilla vs shell React standalone). El bundle React mantiene su `NotificacionesDropdown` para devs que trabajan en `localhost:5173`.

> **Quirk crítico CSS (cazado 2026-05-20, commits `5dfe00c` + `fda6c01`):** tanto `.topbar__bell-badge` como `.notif-menu__dropdown` tienen `display:flex/block` en `menu.css`, que **pisa el atributo HTML `hidden`** por especificidad. Sin una regla `.<clase>[hidden]{display:none}`, el elemento se ve aunque tenga `hidden` — el badge mostraba "0" siempre, y el dropdown arrancaba ABIERTO y no se cerraba (el JS hacía `el.hidden=true` pero el CSS lo ignoraba). **Cualquier componente nuevo del shell vanilla que use `display:` explícito + toggle por atributo `hidden` DEBE incluir la regla `[hidden]{display:none}`.** Ver memoria [[reference_css_display_pisa_hidden]]. El cierre del dropdown al clickear afuera usa un overlay full-screen en el body + elevación del `.topbar` por encima (no del `.notif-menu`, que queda confinado en el stacking context del topbar `z-index:100`).

**Notificaciones extendidas a más eventos (✅ ENTREGADO 2026-05-19):**

Tres notifs nuevas que se suman a `tramite_bandeja_{creacion,pase,transicion}` (que ya existían). Todas reusan el helper `_emitir_a_usuarios()` que centraliza INSERT con RETURNING + commit + encolado del background task. Fail-safe (try/except global, log + return 0).

| Trigger | Función | Destinatarios | Tipo notif |
|---|---|---|---|
| `POST /{ref}/comentar` | `notificar_comentario_a_tomador` | Usuario del `tramite.id_agente_tomado_por`, excluyendo al que comentó (`id_usuario_que_comento`) | `tramite_comentario` |
| `POST /{ref}/transicionar` cuando `es_final=TRUE` | `notificar_estado_final_a_iniciador` | Usuarios de la `id_subarea_iniciadora` (solo si `iniciador_tipo='area_interna'`; ciudadano/empresa no se notifican porque no tienen cuenta) | `tramite_estado_final` |
| `POST /{ref}/documentos` con `requiere_firma=TRUE` y firmantes definidos | `notificar_firma_pendiente` (loop por cada `id_tramite_firma`) | Polimórfico: usuarios del agente/subarea/equipo asignado a la firma | `tramite_firma_pendiente` |

**Helpers nuevos en `services/notificaciones.py`:**
- `_datos_tramite(db, id_tramite)` — SELECT base compartido por los 4 notificadores. Trae `numero_expediente`, `asunto`, `tipo_nombre`, destinatario actual, iniciador, `id_agente_tomado_por`.
- `_usuarios_por_subarea`, `_usuarios_por_equipo`, `_usuarios_por_agente` — resuelven destinatarios con email activo.
- `_emitir_a_usuarios(...)` — inserta filas con RETURNING, commitea, encola sends. Acepta `excluir_usuario` para casos como comentario (no notificar al autor).

**Quirk de comentario:** se exige `BackgroundTasks` en la signature del endpoint `/comentar` (antes no lo tenía). El notificador corre después del commit del movimiento, idéntico patrón a creación/pase/transición.

**Smoke E2E verificado (2026-05-19):** 3 trámites pedido-informe (`INF-LPL-2026-0017/0018/0019`):
- Comentario al tomador: 1 notif a admin, excluyendo correctamente al user "administrativo" que comentó.
- Estado final: trámite avanzado por `Solicitado → Respondiendo → Respondido → Archivado` (final). 2 notifs `tramite_estado_final` a la subarea iniciadora.
- Firma pendiente: doc requerido con `firmantes_jsonb=[{tipo:subarea,id:1}]` → 2 notifs `tramite_firma_pendiente` a los users de la subarea 1.
- Todas con `enviada_mail=TRUE` (email real via Zoho). Cleanup completo.

**Pendientes futuros (no críticos):**
- (vacío al 2026-05-19)

**Marcar `enviada_mail=TRUE` tras send exitoso (✅ ENTREGADO 2026-05-19):**

Patrón usado: el INSERT en `notificacion` ahora hace `RETURNING id_notificacion`. Por cada usuario destinatario, en lugar de encolar `enviar_mail` directo como background task, se encola un wrapper `_enviar_mail_y_marcar(id_notif, to, subj, html, text)` que:
1. Llama a `enviar_mail(...)`. Si devuelve `False`, sale (deja la fila con `enviada_mail=FALSE` para reintento manual o auditoría).
2. Si `True`, abre una sesión SQL nueva via `AsyncSessionLocal()` (la sesión del request ya está cerrada cuando esto corre en background), hace `UPDATE notificacion SET enviada_mail=TRUE, enviada_mail_en=NOW() WHERE id_notificacion=:nid AND activo=TRUE AND enviada_mail=FALSE`, commitea, cierra.

**Por qué abrir sesión nueva:** los `BackgroundTasks` de FastAPI corren *después* de cerrar la respuesta HTTP, fuera del contexto del request. Reusar `db` del request da `InterfaceError: cannot operate on a closed database`.

**Por qué el `for` de sends va después del `await db.commit()`:** si el background task levanta antes de que el commit persista la fila, el `UPDATE` no encuentra nada que actualizar. Commitear primero, encolar después.

**Smoke verificado (2026-05-19):** crear trámite → 2 destinatarios → 2 mails reales enviados via Zoho → 2 filas con `enviada_mail=TRUE` + timestamp.

### Editor admin de tipos custom (✅ ENTREGADO 2026-05-18, commit `65b6ac2`)

CRUD completo del catálogo de tipos vía UI React. Antes solo se podía vía `seed_tramites.py`. Ahora cualquier Admin/Supervisor puede crear/editar tipos desde `/tramites/config`.

**Decisiones de diseño acordadas (sesión 2026-05-18):**
- **Versionado:** v1 editable in-place si NO tiene trámites instanciados. Con trámites, fuerza crear v2 borrador (UI copia estructura automáticamente).
- **Borrado:** soft-delete siempre (`activo=FALSE`). Coherente con §5.
- **Permisos:** nivel ≤ 2 (Admin + Supervisor) para todas las mutaciones del catálogo.

**Backend nuevo:**
- `routes/tramites_admin.py` — 19 endpoints CRUD bajo `/api/v1/admin/tramites`. Registrado **ANTES** de `admin_tablas_router` para evitar colisión con `/api/v1/admin/{tabla}` greedy (§5 quirk).
- `services/tramites/versionado.py` — helpers `asegurar_editable`, `crear_borrador_desde_publicada` (copia campos+estados+transiciones+docs con re-mapeo de IDs), `publicar_version` (valida 1 inicial + ≥1 final).
- `schemas/tramites.py` — 11 schemas In/Out nuevos (TipoTramiteCreateIn, CampoIn, EstadoIn, TransicionIn2, DocumentoRequeridoIn, etc.).

**Endpoints (19 total bajo `/api/v1/admin/tramites`):**

| Recurso | Endpoints |
|---|---|
| `tipos` | POST · PUT `/{id}` · DELETE `/{id}` · GET `/{id}/admin` |
| `versiones` | GET `/{id}` (detalle completo, no solo publicada) · POST `/tipos/{id}/versiones` (crear borrador) · POST `/versiones/{id}/publicar` · POST `/versiones/{id}/archivar` |
| `campos` | POST `/versiones/{id}/campos` · PUT `/campos/{id}` · DELETE `/campos/{id}` |
| `estados` | POST `/versiones/{id}/estados` · PUT `/estados/{id}` · DELETE `/estados/{id}` |
| `transiciones` | POST `/versiones/{id}/transiciones` · PUT `/transiciones/{id}` · DELETE `/transiciones/{id}` |
| `documentos-requeridos` | POST `/versiones/{id}/documentos-requeridos` · PUT `/documentos-requeridos/{id}` · DELETE `/documentos-requeridos/{id}` |

**Frontend nuevo (`web-app/src/modules/tramites/admin/`):**
- `pages/ConfigTramites.tsx` — lista de tipos con badge de versión publicada y botón "Nuevo tipo".
- `pages/ConfigTramiteDetalle.tsx` — editor con selector de versiones + 5 tabs (General/Campos/Estados/Transiciones/Docs requeridos) + botones Publicar/Archivar/Nuevo borrador + mensaje de editable.
- `modals/` — 6 modales: NuevoTipoModal, EditarTipoModal, CampoModal, EstadoModal, TransicionModal, DocReqModal + `_modalShell.tsx` (helper compartido).
- `api.ts` + `hooks.ts` — 19 hooks react-query con invalidación automática.

**UI integrada como tab "Tipos de trámite"** en `TramitesLayout` (visible solo `nivel <= 2` vía `useAuthStore.hasPermission(2)`). La pestaña se llamó "Configuración" hasta 2026-05-22, pero ese nombre sugería config del sistema; renombrada a "Tipos de trámite" (pestaña + breadcrumb + título). Las rutas internas siguen siendo `/tramites/config` por compat (solo cambió el label visible).

**Acceso:** `/tramites/config` (lista) + `/tramites/config/:idTipo` (editor).

### Listado admin de tipos + leyenda Sistema/Custom + Publicado/Borrador (2026-05-22)

**Bug de fondo corregido:** la pantalla "Tipos de trámite" reusaba el endpoint **público** `GET /api/v1/tramites/tipos`, que SOLO devuelve tipos con versión publicada (`id_version_publicada IS NOT NULL`). Consecuencia: un tipo custom en **borrador no aparecía en ningún lado** — ni en "Nuevo trámite" (correcto) ni en la lista de administración (bug: el admin no podía volver a editarlo/publicarlo si recargaba).

Fix:
- **Endpoint nuevo `GET /api/v1/admin/tramites/tipos`** (en `tramites_admin.py`, ahora 20 endpoints): lista TODOS los tipos activos (publicados + borradores + sin estados) con `es_sistema` y `estado_version` derivado (`publicado` / `borrador` / `sin_estados` / `archivado`). Es el que consume la pantalla admin (`useTiposCatalogo`), NO el público.
- **`ConfigTramites.tsx`** muestra dos badges por fila: **Origen** (`Sistema` neutral / `Custom` success) y **Estado** (`Publicado` / `Borrador` / `Borrador (sin estados)` / `Archivado`). El borrador ahora SÍ aparece en la lista.
- **`ConfigTramiteDetalle.tsx`** tiene un **banner de publicación** cuando la versión es borrador: "Listo para publicar" (botón "Publicar y habilitar" activo) o "Todavía no se puede publicar" listando qué falta (estado inicial/final). Conecta crear el tipo con disponerlo para usar.
- `es_sistema` distingue seed (`TRUE`) de custom (`FALSE`) — ver mig 56 §21 y memoria [[reference_tipo_tramite_sin_usuario_alta]].

> **Regla del flujo:** un tipo custom recién creado nace en borrador y NO está disponible en "Nuevo trámite". El alta lista solo publicados. Hay que ir al editor → agregar estados inicial+final → "Publicar y habilitar". Recién ahí aparece en el selector de alta.

**Tipos custom seedeados en prod (2026-05-22):** `exencion-tasas` (EXT) y `permiso-espacio-publico` (PEP) publicados + `solicitud-arbolado` (ARB) dejado como borrador de ejemplo (no aparece en alta hasta publicarlo).

**Manual de uso:** `docs/manual_admin_tramites.html` (autocontenido, 12 capturas reales — regenerado 2026-05-22 con la UI nueva) o vía módulo Guías (`/guias` → card "TRÁMITES (CREACIÓN)"). El manual operativo es `docs/manual_tramites.html` (card "TRÁMITES (USO OPERATIVO)").

**Smoke E2E validado:** crear tipo → 3 estados → 2 transiciones → campo → doc requerido → publicar → instanciar trámite → editar v1 publicada con trámites = 409 → crear v2 borrador (copia estructura). Cleanup completo (test data borrada, agente del admin restaurado).


## 36. Generación de manuales operativos (HTML autocontenidos)

Receta probada (sesión 2026-05-18, 3 manuales generados). Reusable para cualquier módulo nuevo.

### Patrón fundamental

1. **Carpeta temporal `_<modulo>_caps/`** (gitignored, manual al final) con:
   - `package.json` mínimo con `"type": "module"`
   - `_token.txt` y `_user.json` (auth para inyectar en localStorage)
   - `_id<entidad>.txt` (ids de demo para deep-links)
   - `capture.mjs` (script Playwright)
   - `build_html.mjs` (ensambla HTML con base64 inline)
2. **Setup Playwright local sin contaminar** `package.json` del web-app:
   ```bash
   cd _modulo_caps
   echo '{"name":"caps","type":"module","private":true}' > package.json
   npm install playwright --no-save --no-package-lock
   npx --yes -p playwright@latest playwright install chromium
   ```
3. **Datos demo** en DB para que las capturas tengan contenido rico. Sembrar vía API (no SQL crudo) para respetar reglas de negocio.
4. **Script Playwright** con UNA página fresca por captura para evitar estado residual de modales:
   ```js
   async function shot(name, url, prepFn) {
     const page = await ctx.newPage()
     await page.goto(url, { waitUntil: 'networkidle' })
     if (prepFn) try { await prepFn(page) } catch (e) { console.warn(e.message) }
     await page.screenshot({ path: path.join(OUT, name) })
     await page.close()
   }
   ```
5. **Build HTML** con `dataUrl(filename)` → `data:image/png;base64,...` y look ZARIS (tokens del DS: `--zaris-orange`, `--zaris-cream`, etc.).
6. **Cleanup OBLIGATORIO al final:** borrar data demo, restaurar flags tocados (ej. `es_auditor`), eliminar carpeta `_<modulo>_caps/`, bajar servers.

### Convenciones del HTML

- **Tamaño esperado:** 1-3 MB con 9-12 capturas embebidas. Si pasa de 5 MB, revisar (probable capturas gigantes o demasiadas).
- **Estructura:** hero con borde naranja izquierdo + breadcrumb tag + h1, índice con anchors, secciones numeradas (1-N), tablas de errores comunes + glosario al final.
- **Componentes:** `blockquote` con variantes `.warn` (ámbar), `.danger` (rojo), `.info` (azul). `.badge` con clases por estado. `.flow` para diagramas tipo "paso 1 → paso 2".
- **Footer:** "Manual generado el YYYY-MM-DD · ZARIS · Gestión Estatal · Capturas reales del entorno local".

### Almacenamiento y serving

- Los HTMLs viven en **`docs/`** en la raíz del repo (junto al `flujos_operativos_zge.md` legacy).
- GH Pages los sirve automáticamente como `https://zge.zaris.com.ar/docs/manual_X.html`.
- En dev local accesibles vía `http://localhost:8080/docs/manual_X.html` (servidos por el `python -m http.server 8080` raíz).
- **NO embeber en iframe** (lento + pierde sidebar). Servir como pestaña nueva vía `target="_blank"`. Ver [[feedback_acortar_alcance_html_autocontenido]].

### Quirks operativos a recordar

- **`browser_screenshot` del MCP NO persiste el PNG.** Solo Playwright headless guarda en disco. Ver [[feedback_screenshots_no_persisten_browser_mcp]].
- **PowerShell `Out-File -NoNewline` encoding:** strings cortos = UTF-8 con BOM, strings largos = UTF-16 LE con BOM. Leer en Node con `replace(/^﻿/, '').trim()` cubre el caso UTF-8; UTF-16 requiere `Buffer.toString('utf16le').replace(...)`.
- **El `addInitScript` de Playwright** debe inyectar la sesión ANTES de navegar, no después, para que el guard React no redirija a `/login`.
- **Sembrar data con API, NO con SQL crudo:** SQL crudo puede saltarse triggers, validaciones de negocio y dejar la DB en estado inconsistente. La API ya respeta todo.

### Manuales actuales (al 2026-05-26)

| Manual | Audiencia | Capturas | Secciones |
|---|---|---|---|
| `manual_reclamos.html` | Operador o superior | 10 | 11 |
| `manual_ot.html` | Supervisor / Agente / Auditor | 9 | 11 |
| `manual_tramites.html` | Operador o superior | 8 | 13 |
| `manual_admin_tramites.html` | Admin o Supervisor | 12 | 11 |
| `manual_encuestas.html` | Supervisor o Admin | 0 (texto) | 6 |

> **Variante sin capturas (válida):** `manual_encuestas.html` se generó SIN capturas embebidas. La receta full de §36 usa Playwright para capturas reales, pero el `browser_screenshot` del MCP integrado no persiste el PNG ([[feedback_screenshots_no_persisten_browser_mcp]]) y montar Playwright es setup pesado. Para módulos **analíticos/simples** (dashboards de lectura, pocas pantallas), un manual de texto + tablas + diagramas de flujo con el estilo ZARIS canónico es claro y suficiente — entregable sin el setup de capturas. Reservar el manual con capturas para flujos operativos multi-paso donde "ver la pantalla" agrega valor real (Reclamos, OT, Trámites).

### Próximos manuales sugeridos (no obligatorios)

- Agenda (calendario + espacios + disponibilidad)
- Turnos + Entradas (autoservicio + backoffice)
- Padrones (Ciudadanos + Empresas vía Contactos)


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

- **Login con DNI + password.** Sin autoregistro: la alta la hace un agente municipal (nivel ≤ 3) desde un endpoint protegido, o, en una etapa futura, desde un flow público de auto-registro con dedupe contra BUC.
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

### Email — display name del municipio sobre address ZARIS

El remitente real es siempre el address de `RESEND_FROM` (`notificaciones@zaris.com.ar`, dominio raíz verificado en Resend — §42; antes `noreply@zaris.com.ar` por SMTP), pero el header `From:` lleva el **display name del municipio**: `"MUNICIPALIDAD DE SAN ANDRÉS <notificaciones@zaris.com.ar>"`. Implementado vía `enviar_mail(..., from_override="...")`. La marca ZARIS no aparece en el body al vecino.

Funciones nuevas en `services/email.py`: `enviar_mail_activacion_ciudadano` y `enviar_mail_recovery_ciudadano`. Template HTML sobrio con logo del municipio (si está en `municipio_logo_url`), botón CTA naranja `var(--zaris-orange)`, link de fallback. Sin emojis.

### Variables de entorno

| Var | Default | Notas |
|---|---|---|
| `APP_VECINOS_FRONTEND_URL` | `http://localhost:5174` | URL del frontend PWA. En Railway prod debe apuntar a `https://vecinos.zaris.com.ar`. Se usa para armar los links de los mails de activación/recovery. |
| `JWT_PUBLICO_EXPIRA_DIAS` | `30` | Vigencia del JWT scope publico. |

### Estado de deploy (2026-05-20)

- **Backend Etapa 0 deployado en prod** (commit `553b0a3`). Los 8 endpoints (`/api/v1/publico/auth/*` + `/api/v1/publico/identidad-municipio`) responden en Railway. Verificado: `/identidad-municipio` → 200 con branding de San Andrés (nombre + logo cargados; `descripcion`/colores aún `null`, pendiente carga desde panel admin).
- **PWA scaffold (Etapa 1)** creada en repo separado `CesarZeta/zaris-vecinos`, deployada en Vercel → `https://vecinos.zaris.com.ar`. Verificada local end-to-end (build, SW activado, branding consumido desde prod, routing). Detalle de la PWA en su propio README; **no documentar la PWA en este CLAUDE.md** (es otro repo).
- **CORS**: el origen `https://vecinos.zaris.com.ar` (+ `http://` y `https://zaris-vecinos.vercel.app`) agregado a `allow_origins` en `backend/app/main.py` (commit `5d70425`). `http://localhost:5174` ya estaba para dev.

### Quirks operativos

- **DNI digit-only**: el endpoint `_solo_digitos()` normaliza el DNI a string sin puntos antes de comparar con `ciudadanos.doc_nro`. La PWA puede mandar "12.345.678" o "12345678" indistintamente.
- **CUIL placeholder**: el alta desde `/registrar` genera `cuil = '20' + dni.zfill(8) + '9'` (formato digit-only, prefijo masculino default). El ciudadano puede actualizarlo desde la PWA en una etapa futura. `ciudadanos.cuil` es UNIQUE NOT NULL.
- **Defaults pragmáticos en `ciudadanos`**: `doc_tipo='DNI'`, `sexo='OTROS'`, `fecha_nac='1900-01-01'` (sentinela), `id_nacionalidad=1` (Argentina), `ren_chk=FALSE`, `email_chk=FALSE`, `emp_chk=FALSE`. El agente NO los carga al alta para minimizar fricción; quedan pendientes de completar por el ciudadano.
- **CAST en lugar de `::uuid`** en queries con `text()`: `WHERE cc.token_activacion = CAST(:token AS uuid)`. sqlalchemy parsea `:token::uuid` mal porque confunde el `::` del cast con el prefijo `::` del parameter binding.
- **`INTERVAL` con duraciones variables**: en queries con duraciones (`INTERVAL '7 days'`), construir el SQL con f-string para que el número quede literal antes de pasar a `text()`. No usar `:dias` como bind param porque asyncpg no le pone comillas correctamente alrededor del INTERVAL.
- **Mail de activación**: el `BackgroundTask` corre después del commit del endpoint, sigue el patrón estándar de notificaciones (§35). Si SMTP no está configurado, `enviar_mail()` cae a modo MOCK (log a stdout, no rompe el flow).

### Smoke test

`backend/smoke_publico_auth.py` cubre los 15 pasos del prompt de Etapa 0: cleanup → login agente → registrar → verificar DB (ciudadanos + credencial + canal_preferido) → activar → /me con scope publico → /me con scope agente debe dar 401 → login → 5 fallidos → lockout → recovery → resetear-password → login con nuevo pass → /identidad-municipio → cleanup. Ejecutar con `$env:PYTHONIOENCODING="utf-8"; python smoke_publico_auth.py` desde `backend/`. Levantar uvicorn antes (`$env:ENV_FILE=".env.local"; uvicorn app.main:app --host 127.0.0.1 --port 8000`).

**Validado el 2026-05-19**: 15/15 OK en local con mails reales enviados via Zoho SMTP (display name "MUNICIPALIDAD DE SAN ANDRÉS").

### Fuera de alcance de Etapa 0

- `POST /api/v1/publico/reclamos` — Etapa 2.
- Adjuntos públicos (fotos del reclamo) — Etapa 2.
- Push notifications (envío) — Etapa 5. La tabla `ciudadano_push_subscription` queda sin endpoint hasta entonces.
- Flow público de autoregistro (reemplaza el alta del agente) — etapa futura.
- Bandeja de revisión de ciudadanos `vinculado_pendiente` — etapa futura.
- Panel admin ZARIS para configurar el branding del municipio — producto separado.

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
| Sistema | `SistemaView` + `ParametrosSistemaView` | `GET /api/v1/admin/configuracion_general` + `PUT /{id_config}` | **Desde 2026-05-25:** pantalla de ajustes agrupada y tipada (toggle/number/text/color) sobre `configuracion_general`, secciones Encuestas / Reclamos y OT / App Vecinos / Otros. Debajo, atajos a Municipios/Maestros. Ver [[reference_config_sistema_pantalla_tipada]]. Clave nueva: seed (mig) + leer backend + sumar a `SECCIONES`. `municipio_nombre`/`logo` ocultos acá (se editan en Identidad). El item "usuarios" se quitó del sidebar del shell (sigue accesible acá vía atajo "Usuarios del sistema"). |

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

Encuestas de satisfacción disparadas al cierre de reclamos. Encuesta estándar ZARIS (no editable por municipio en v1), con ramificación condicional según la satisfacción inicial. DB: mig 57 (6 tablas + toggle) + mig 58 (tracking de atención). Aplicadas en local y prod al 2026-05-22.

**Estado al 2026-05-22:** fases 2A (auditoría email), 2B (`services/encuestas_service.py`) y 2C (router admin `encuestas_admin.py`) entregadas. Form público del ciudadano (2D) y dispatcher (2E) **pendientes** — las reglas de esas fases se documentan abajo como diseño acordado, NO como código existente.

### Tablas (mig 57 + 58)
`encuesta_plantilla` → `encuesta_pregunta` → `encuesta_opcion` (catálogo); `encuesta_envio` (FK física a `ciudadanos` + `reclamos`, §2) → `encuesta_respuesta` (1:1) → `encuesta_respuesta_detalle`. PKs estilo `id_<tabla>`, estándar §10 completo, RLS habilitado sin políticas (deny-all, service_role bypassa, §26). Mig 58 sumó a `encuesta_respuesta`: `atendida`/`atendida_por`/`fecha_atendida` + índice parcial `idx_encuesta_respuesta_pendientes`.

### Disparo automático
- Las encuestas se disparan **solo cuando un reclamo se cierra con estado `'Resuelto'`**. NO con `'Cancelado'` ni otro estado final. Razón: un reclamo cancelado no tiene gestión que evaluar.
- El service real es `encuestas_service.crear_envio_para_reclamo(db, id_reclamo) -> tuple[mapping | None, motivo]`. El segundo elemento es una constante `MOTIVO_*` (string legible) que el endpoint `POST /disparar` mapea a 422.

### Toggle de activación
- Clave `encuestas_activas` (boolean) en `configuracion_general`. Si `'false'`, el service no crea envíos aunque se cierren reclamos. Default tras mig 57: `'true'`.

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

### Email vía Resend (API HTTP) — migrado desde SMTP Zoho (RESUELTO 2026-05-24, commit `139332e`)
**Por qué se migró:** Railway bloquea el egress SMTP saliente (587 Y 465 dan `timed out` desde prod; verificado 2026-05-23 con logs de Railway). En local SMTP funcionaba — engañoso. Resend usa HTTPS (puerto 443), que Railway no bloquea.

`services/email.py` fue **reescrito completo** (sin smtplib/email.mime). Usa `httpx.AsyncClient` directo contra `POST https://api.resend.com/emails` (NO la lib oficial `resend` — el backend es async, un solo endpoint). Detalle:

- **`enviar_mail(to, subject, body_html, body_text=None, from_override=None) -> bool` es ahora ASYNC.** Misma firma pública (no rompió los 4 clientes), pero los 3 callers async ganaron `await`: `notificaciones.py`, `encuestas_service.py` (×2 llamadas), y las 2 funciones App Vecinos (`enviar_mail_activacion_ciudadano`/`enviar_mail_recovery_ciudadano` pasaron a `async def` — se siguen encolando con `add_task`, Starlette await-ea corutinas).
- **`enviar_mail_raise(...) -> str` (NUEVA):** devuelve el `message_id` de Resend, levanta `ResendError(status_code, body)` ante 4xx/5xx o fallo de transporte. `enviar_mail` la envuelve y captura, devolviendo bool (contrato histórico). El dispatcher de encuestas sigue consumiendo el bool — **NO conectada al dispatcher todavía** (queda lista para distinguir 5xx-reintentar de 4xx-fallar).
- **Modo MOCK:** si `RESEND_API_KEY` vacía (`resend_configurado()` False), loggea y devuelve True sin enviar. Reemplaza al viejo `smtp_configurado()`.
- **Logging:** cada envío exitoso loggea el `message_id` (trazabilidad en Resend → Logs). Destinatario siempre enmascarado con `mask_email`. **El `message_id` NO se persiste en DB** (`encuesta_envio` no tiene columna) — vive solo en logs.
- **Timeouts:** `httpx.Timeout(30.0, connect=10.0)`.

**Config (`core/config.py`):** se borraron las 6 vars `SMTP_*`. Nuevas: `RESEND_API_KEY` (env var, NO commitear) y `RESEND_FROM` (default `notificaciones@zaris.com.ar`). Se agregó `extra = "ignore"` al `Config` de pydantic-settings — sin esto el backend **no arranca** mientras `.env.local`/Railway aún tengan las `SMTP_*` viejas (esta versión está en `extra_forbidden` por default; cazado al importar). `_from_municipio` en encuestas lee `RESEND_FROM`.

> **El remitente es `@zaris.com.ar` (dominio raíz), NO `@send.zaris.com.ar`.** El subdominio daba 403 `not authorized to send from send.zaris.com.ar` — lo verificado en Resend es el dominio raíz (`send.zaris.com.ar` es solo Return-Path interno de SES, no dominio de envío). El `from` debe usar EXACTAMENTE el dominio verificado.

**Verificado LOCAL (2026-05-24):** 3 mails reales a `cesarzarini@hotmail.com` vía `enviar_mail_raise` (message_id `f48d01b6-...`) y `enviar_mail` (`9d5618bd-...`). El 403 inicial (subdominio mal) confirmó de paso el manejo de errores: `ResendError` con status+body, `enviar_mail` → False, sin silenciar.

**Verificado PROD end-to-end (2026-05-24):** se disparó el dispatcher de encuestas en Railway (`POST /api/v1/admin/encuestas/dispatcher/ejecutar` con header `X-Dispatcher-Token`) → `{"procesados":1,"exitosos":1,"fallidos":0}`. El envío `id=3` (que venía con **2 intentos fallidos bajo SMTP** — los timeouts) pasó a `estado='enviada'` + `fecha_envio` poblada en el 3er intento, ya con Resend. Mail recibido OK. **El bloqueo SMTP de Railway quedó resuelto.** `ultimo_error_envio` NO se limpia al tener éxito (queda el texto del último fallo como histórico — no es bug). Ver memoria [[reference_railway_bloquea_egress_smtp]].

### Sanitización de PII en logs (Ley 25.326)
- Helper centralizado: `app.utils.log_helpers.mask_email()`
- Formato: `<primer_char>***@<dominio>` (3 asteriscos fijos para no leakear longitud)
- Aplicado en `services/email.py` (sender central usado por encuestas, notificaciones, trámites y App Vecinos — los 4 logs de `to=` enmascarados)
- Tokens de encuestas: helper local `_tok()` en `encuestas_service.py` (consistente con el patrón)
- Smoke test: `backend/scripts/test_mask_email.py`

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

