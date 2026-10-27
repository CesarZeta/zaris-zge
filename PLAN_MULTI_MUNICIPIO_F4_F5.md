# IT-01 F4+F5 — Alta de municipios y subdominios: plan de implementación

> **Para agentes:** SUB-SKILL REQUERIDA: usar superpowers:subagent-driven-development (recomendada) o superpowers:executing-plans para ejecutar este plan tarea por tarea. Los pasos usan casillas (`- [ ]`) para el seguimiento.

**Objetivo:** que el super administrador dé de alta un municipio completo desde «Municipios», y que la gente de ese municipio (administrador, agentes, vecinos) use la plataforma por su propio subdominio, con los tres frontends en Cloudflare Pages.

**Arquitectura:**
- **Dos cortes en prod.** El **corte A** (Tareas 1-3) muda los tres frontends a Cloudflare Pages sin cambiar comportamiento: CORS por patrón, hostnames de municipio reconocidos y dominios movidos de a uno. El **corte B** (Tarea 20) sube todo F4 y las direcciones por municipio, y cierra con el alta de un municipio de prueba en prod.
- **El municipio pasa a tener estado** (`puesta_en_marcha`, `produccion`, `demo`, `modelo`, `baja`), país y provincia del catálogo, módulos habilitados y tope de cuentas. Todo lo que hoy mira `activo` o `direccion_base` para decidir comportamiento pasa a mirar el estado.
- **El alta, el modelo y el vaciado reusan lo que ya existe en scripts locales:** el `Clonador` y `borrar_municipio_aislamiento` de `seed_municipio_aislamiento.py` se llevan a servicios de la app, guiados por `municipio_tabla_clase` (que gana la columna `grupo`) y las FK compuestas `fkm_*`.
- **Los links de mails y QR se arman por municipio** en `core/urls.py`, y un barrido impide volver a armarlos a mano.

**Stack:** FastAPI 0.111 + SQLAlchemy async (asyncpg), PostgreSQL 17 · shell vanilla + React 19 (Vite) · PWAs `zaris-vecinos` y `zaris-agentes` (React + VitePWA) · Cloudflare Pages + DNS de Cloudflare · Supabase Storage · Resend.

**Spec:** [`PLAN_MULTI_MUNICIPIO_F4_F5_DISENO.md`](PLAN_MULTI_MUNICIPIO_F4_F5_DISENO.md), aprobado por César el 2026-10-27. Base: [`PLAN_MULTI_MUNICIPIO.md`](PLAN_MULTI_MUNICIPIO.md) §5-§10; siguen valiendo las reglas R1-R11 de [`PLAN_MULTI_MUNICIPIO_F1_F2.md`](PLAN_MULTI_MUNICIPIO_F1_F2.md) y lo de F3/F3b (CLAUDE.md §1, §3). Relevamiento del código: commits ZGE `7272595`, zaris-vecinos `afa1182`, zaris-agentes `8d0c5f2`.

## Restricciones globales

- **Ramas:** `it01-f4-f5` en el worktree `ZGE/.claude/worktrees/it01-f4-f5`; `cloudflare-pages` en `zaris-vecinos` y en `zaris-agentes`. Las Tareas 1-2 se mergean a `main` en el corte A (Tarea 3); el resto, solo en el corte B (Tarea 20). Base de pruebas: `zaris_dev`.
- **Migraciones** (se renumeran si otra toma el número antes, CLAUDE.md §21):
  - `130_municipios_f4_restricciones.sql` — lleva `DROP` (CHECK de `super_admin_acceso.accion`): en prod la corre César en el SQL Editor.
  - `130b_municipios_f4.sql` — tablas y columnas, sin `DROP`, por MCP.
  - `130c_municipios_f4_datos.sql` — datos (países, estados, áreas de sistema, módulos de San Andrés, grupos), por MCP.
  - Toda tabla nueva: campos de §10, `ENABLE ROW LEVEL SECURITY`, fila en `municipio_tabla_clase` **con su `grupo`**.
- **Constantes del spec** (en `app/services/municipios/constantes.py`):
  - `ESTADOS = ("puesta_en_marcha", "produccion", "demo", "modelo", "baja")`.
  - `ESTADOS_OPERABLES = {"puesta_en_marcha", "produccion", "demo"}` (login, páginas públicas, procesos programados).
  - `ESTADOS_VACIABLES = {"puesta_en_marcha", "demo"}`, además de `fue_produccion = false`.
  - `GRUPOS = ("operativo", "contactos", "maestros", "usuarios", "configuracion")`.
  - `MODULOS_FIJOS = {"usuarios", "admin_tablas", "padrones", "municipios"}` (no se deshabilitan).
  - `DEPENDENCIAS_MODULOS = {"turnos": {"agenda"}, "entradas": {"agenda"}, "ot_supervisor": {"reclamos"}, "ot_agente": {"reclamos"}, "ot_auditoria": {"reclamos"}, "agentes_gestion": {"padrones"}}`.
  - La Guardia vive dentro de `turnos` y además exige `emergencias` habilitado: se controla en el servicio (Tarea 7), no en el grafo.
  - `INVITACION_HORAS = 72`, `EXPORTACION_RETENCION_DIAS = 90`, `TOPE_AVISO = 0.9`.
  - `PATRON_SUBDOMINIO = r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"` (el mismo de `_PATRON_HOST`).
  - `SUBDOMINIOS_RESERVADOS = {"www", "api", "zge", "vecinos", "agentes", "admin", "app", "mail", "soporte", "status", "demo", "modelo"}`.
  - `PATRON_CODIGO_CORTO = r"^[A-Z]{2,5}$"`.
- **Textos fijos de la interfaz:**
  - Tope (409): «El municipio llegó al tope de {M} cuentas activas. Pedí al soporte de ZARIS que lo amplíe o desactivá una cuenta.»
  - Aviso de tope: «{N} de {M} cuentas activas.»
  - Área fija (422): «Es un área fija del sistema: se puede renombrar, no dar de baja.»
  - Vaciado no permitido (409): «Este municipio está o estuvo en producción: sus datos no se pueden vaciar.»
  - Confirmación: «Escribí el nombre del municipio para confirmar.»
  - Invitación vencida o usada: «El enlace venció o ya se usó. Pedí al soporte de ZARIS que te reenvíe la invitación.»
  - Dependencia de módulo (422): «{modulo} necesita {dependencia} habilitado.»
- **Credenciales:** el token de la API de Cloudflare vive en `C:\Users\Cesar\Documents\ZARIS\credenciales-testing\cloudflare_api_token.txt`. Nunca en el repo, en memorias, en Railway ni en la conversación. El backend no tiene credenciales de Cloudflare.
- **Panel de Cloudflare:** el login no funciona en el navegador integrado de VS Code (Turnstile). Lo que se haga en el panel lo hace César desde Chrome o Edge, con instrucciones paso a paso (sitio, botón, resultado esperado).
- **Smokes:** solo contra `zaris_dev`, in-process con `httpx.ASGITransport`, mail en MOCK (`settings.RESEND_API_KEY = ""`), con `SEGUNDO_FACTOR_OBLIGATORIO` prendido in-process donde se loguee un nivel 0/1 (patrón de `smoke_segundo_factor.py`). Un smoke nuevo: `backend/smoke_alta_municipio.py`, que crece tarea a tarea. Emails de prueba con dominio `@prueba-aislamiento.com.ar` (email-validator rechaza `.test`).
- **Antes de cada commit:** `grep -riE "h[u]sky" .` vacío; `pnpm typecheck` si toca `web-app/` o una PWA; bump de `?v=` si toca assets del shell.
- **Mutaciones de larga duración** (alta, exportación, vaciado): asíncronas, 202 + `GET` de estado, sesión SQL propia (`AsyncSessionLocal`), patrón `/demo/poblar` (CLAUDE.md §9).

## Foco de revisión

1. **Un subdominio o código corto inválido, reservado o ya usado** (`Vicente-Lopez`, `córdoba`, `api`, el de San Andrés): 422 o 409 antes de escribir nada. Lo prueba la Tarea 11 (`test_alta_validaciones`).
2. **Un alta que falla a mitad** (por ejemplo, una FK rota al copiar un catálogo del modelo): no queda ni el municipio ni ninguna fila suya. Lo prueba la Tarea 11 (`test_alta_atomica`).
3. **Un vecino o funcionario del municipio B recibe un mail:** todos sus links apuntan a `b.<app>.zaris.com.ar`, y los de San Andrés siguen sin prefijo. Lo prueba la Tarea 9 (`test_links_por_municipio`) más el barrido.
4. **El vaciado pedido por API directa** sobre un municipio en `produccion`, o reactivado después de haberlo estado: 409, sin tocar nada. Lo prueba la Tarea 16 (`test_vaciado_guardas`).
5. **Doble clic en «Dar de alta» o dos vaciados del mismo municipio a la vez:** se ejecuta uno solo. El alta lo frena el único de `subdominio`/`codigo_corto`; el vaciado, un `pg_advisory_xact_lock(id_municipio)`. Lo prueban la Tarea 11 (`test_alta_concurrente`) y la Tarea 16 (`test_vaciado_concurrente`).

---

## Corte A — mudanza de los frontends a Cloudflare Pages

### Tarea 1: CORS por patrón y hostnames de municipio en los clientes

**Archivos:**
- Modificar: `backend/app/main.py:89-112` (CORS)
- Modificar: `frontend/js/menu.js:7-9`, `frontend/login.html:443-444` (API base por hostname)
- Modificar: `web-app/src/lib/shellNav.ts:24,39` (sin suponer subpath)
- Modificar: comentarios desactualizados relevados: `core/urls.py:9-10`, `schemas/publico_alta.py:6`, `.github/workflows/deploy-web-app.yml` (encabezado), `zaris-vecinos/src/lib/identidad.ts:21`
- Test: `backend/smoke_municipio_request.py` (ampliar)

**Interfaces:**
- Produce en `app/main.py`: `ORIGEN_ZARIS_REGEX = r"^https://([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)?(zge|vecinos|agentes)\.zaris\.com\.ar$|^https://([a-z0-9-]+\.)?zaris-(zge|vecinos|agentes)\.pages\.dev$"`, pasado como `allow_origin_regex`. `allow_origins` queda con localhost y los orígenes viejos hasta el corte B (`cesarzeta.github.io`, `zaris-vecinos.vercel.app`, `zaris-agentes.vercel.app`).
- Los nombres de proyecto de Cloudflare Pages quedan fijos: **`zaris-zge`**, **`zaris-vecinos`**, **`zaris-agentes`** (dominios `*.pages.dev`).
- En el shell, `esProd(hostname)`: `true` para `zge.zaris.com.ar`, `*.zge.zaris.com.ar` y `*.zaris-zge.pages.dev`/`zaris-zge.pages.dev`.

- [ ] **Paso 1: Tests** en `smoke_municipio_request.py`:
  - `test_cors_patron`: preflight `OPTIONS /api/v1/config/identidad` con `Origin` = `https://zge.zaris.com.ar`, `https://b.vecinos.zaris.com.ar`, `https://zaris-agentes.pages.dev` y `https://abc123.zaris-zge.pages.dev` devuelve `access-control-allow-origin` igual al Origin.
  - Con `https://zge.zaris.com.ar.evil.com`, `https://evilzaris.com.ar` y `http://zge.zaris.com.ar` (sin https) no lo devuelve.
- [ ] **Paso 2:** correr (`cd backend; $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_municipio_request.py`). Esperado: FALLA en `test_cors_patron`.
- [ ] **Paso 3:** implementar el regex, verificando antes que la Starlette instalada soporta `allow_origin_regex` (`python -c "import starlette; print(starlette.__version__)"`).
- [ ] **Paso 4:** `esProd` en `menu.js` y `login.html`; `shellNav.ts` toma el subpath de `document.baseURI` relativo a la raíz del sitio en lugar del primer segmento. Correr `pnpm typecheck`.
- [ ] **Paso 5:** tests en verde; abrir `http://localhost:8080/index.html` y navegar dos módulos con clics (no debe cambiar nada).
- [ ] **Paso 6: Commit** `feat(it-01-f4-f5): CORS por patron y hostnames de municipio en los clientes`.

### Tarea 2: Proyectos de Cloudflare Pages para los tres frontends

**Archivos:**
- Crear: `zaris-vecinos/public/_redirects` (`/* /index.html 200`), `zaris-vecinos/public/_headers` (los headers de `/sw.js` de `vercel.json`: `Cache-Control: max-age=0, must-revalidate` y `Service-Worker-Allowed: /`). Ídem en `zaris-agentes`.
- Crear: `tools/cloudflare_pages_build.sh` en ZGE: instala con pnpm y buildea `web-app`, después arma `_site/` copiando `index.html`, `frontend/`, `design-system/`, `docs/`, `web-app/dist/` y los demás archivos públicos que hoy sirve GitHub Pages, en las mismas rutas.
- Crear: `tools/dominios_municipio.py` (Interfaces).
- Crear: `docs/cloudflare_pages.md`: configuración de cada proyecto (comando de build, directorio de salida, variables, dominios). Sin credenciales.
- Todavía **no** se borra `web-app/dist` del repo ni `deploy-web-app.yml`: GitHub Pages sigue sirviendo hasta que se mueva `zge.` (Tarea 3).

**Interfaces:**
- `tools/dominios_municipio.py <subdominio> [--quitar] [--solo-verificar]`:
  - lee el token de `credenciales-testing/cloudflare_api_token.txt` (aborta si falta);
  - por cada app en (`zge`, `vecinos`, `agentes`): crea el CNAME `<sub>.<app>` → `<proyecto>.pages.dev` en la zona `zaris.com.ar` y agrega el dominio `<sub>.<app>.zaris.com.ar` al proyecto de Pages correspondiente;
  - es idempotente: si ya existen, no duplica;
  - `--solo-verificar` imprime, por dominio, DNS resuelto / estado del dominio en Pages / `GET https://…` con código.
  - El modo de proxy del CNAME (gris o naranja) es el que pida la documentación oficial de Cloudflare Pages para dominios propios; el builder lo verifica en la doc y lo deja anotado en `docs/cloudflare_pages.md`.
- Las variables de entorno de las PWAs pasan a Cloudflare: `VITE_API_URL=https://zaris-api-production-bf0b.up.railway.app` y `VITE_APP_VERSION`.

- [ ] **Paso 1: Pasos de César en el panel de Cloudflare** (Chrome o Edge; se los paso de a uno, con el resultado esperado de cada uno):
  - crear el token de API con permisos `Zone → DNS → Edit` sobre `zaris.com.ar` y `Account → Cloudflare Pages → Edit`, y guardarlo en el archivo de `credenciales-testing/`;
  - conectar la cuenta de GitHub a Cloudflare Pages y crear los tres proyectos con los nombres fijos, cada uno desde su repo y rama `main`, con la configuración de `docs/cloudflare_pages.md`.
- [ ] **Paso 2:** leer los **términos oficiales** de Cloudflare (Self-Serve Subscription Agreement y los términos específicos de Pages) y anotar en `docs/cloudflare_pages.md` la cita sobre uso comercial y límites. Si hay algo que contradiga lo decidido, parar y avisar a César.
- [ ] **Paso 3:** los tres proyectos publican en `*.pages.dev` desde las ramas de trabajo (vista previa) y después desde `main`. Verificar con `curl -s -o /dev/null -w '%{http_code}'` el `index.html` de cada uno y `/sw.js` con sus headers (`curl -sI`).
- [ ] **Paso 4:** con el backend de la Tarea 1 en local, recorrer en el navegador `https://zaris-vecinos.pages.dev` y `https://zaris-agentes.pages.dev` contra el backend de prod **solo** después del corte A del backend (Tarea 3, paso 2). Hasta entonces, verificar que el build y los archivos están.
- [ ] **Paso 5:** `tools/dominios_municipio.py prueba-cf --solo-verificar` corre sin error (sin crear nada) y reporta «no existe» en los 3.
- [ ] **Paso 6: Commit** en cada repo: `build: Cloudflare Pages (_redirects, _headers)` y en ZGE `build(it-01-f4-f5): build de Cloudflare Pages y script de dominios por municipio`.

### Tarea 3: Corte A en prod — mover los dominios (con César)

- [ ] **Paso 1:** backup de prod (`/backup-prod`). Avisar la ventana a los usuarios de San Andrés (minutos por dominio).
- [ ] **Paso 2:** merge de la Tarea 1 a `main` (backend + shell). Verificar el deploy de Railway con el marcador: preflight con `Origin: https://zaris-agentes.pages.dev` devuelve `access-control-allow-origin` (CLAUDE.md §9; control con `https://zge.zaris.com.ar`).
- [ ] **Paso 3:** recorrer `zaris-agentes.pages.dev` y `zaris-vecinos.pages.dev` contra prod: login, un listado, una acción. Caen al municipio base, como se espera.
- [ ] **Paso 4: mover `agentes.zaris.com.ar`:** agregar el dominio al proyecto `zaris-agentes` de Cloudflare y apuntar el CNAME; verificar HTTPS, login y push con un celular con la app instalada; recién ahí quitar el dominio del proyecto de Vercel.
- [ ] **Paso 5: mover `vecinos.zaris.com.ar`:** igual. Verificar además, con la PWA instalada antes de la mudanza: abre, mantiene la sesión, recibe un push de prueba y se actualiza al build nuevo.
- [ ] **Paso 6: mover `zge.zaris.com.ar`:** igual, con el proyecto `zaris-zge`. Verificar shell, login con segundo factor, un módulo React, `frontend/alta-vecino.html?m=SAN`, `frontend/encuesta.html` con un token de prueba, `docs/qa_reclamos_ot.html` y un link profundo `/#/reclamos/<id>`.
- [ ] **Paso 7:** apagar GitHub Pages: borrar `CNAME`, `deploy-web-app.yml` y `web-app/dist/` del repo (agregar `web-app/dist/` a `.gitignore`) y desactivar Pages en el repo. Quitar de `allow_origins` los orígenes viejos (`cesarzeta.github.io`, `*.vercel.app`) y desplegar.
- [ ] **Paso 8:** actualizar CLAUDE.md §6 (URLs y hosting), §9 y §32 (ya no se commitea `dist`; el build lo hace Cloudflare), la skill `win-quirks` y las memorias de Vercel/Pages. Commit y push. Registrar en ESTADO.

---

## F4 y direcciones por municipio (local, rama `it01-f4-f5`)

### Tarea 4: Base de datos de F4

**Archivos:**
- Crear: `backend/migrations/130_municipios_f4_restricciones.sql`, `130b_municipios_f4.sql`, `130c_municipios_f4_datos.sql`
- Modificar: `backend/app/services/accesos_super.py` (`ACCIONES`)
- Crear: `backend/app/services/municipios/__init__.py`, `constantes.py` (las de Restricciones globales)
- Crear: `backend/smoke_alta_municipio.py` (esqueleto de `smoke_super_admin.py`: guarda `zaris_dev`, `check()`, in-process)

**Interfaces (base):**
- **`130`:** el CHECK `ck_super_admin_acceso_accion` suma `municipio_alta`, `municipio_estado`, `municipio_modulos`, `exportacion`, `vaciado`, `super_alta`, `super_baja`, en `BEGIN … COMMIT`.
- **`130b`:**
  - `paises (codigo_pais CHAR(2) PK, nombre VARCHAR(80) NOT NULL, etiqueta_nivel_1 VARCHAR(40) NOT NULL, etiqueta_nivel_2 VARCHAR(40) NOT NULL, zona_horaria VARCHAR(64) NOT NULL, habilitado_para_alta BOOLEAN NOT NULL DEFAULT FALSE, + §10 sin id_municipio)`, clase `global`, grupo `NULL` (las globales no llevan grupo).
  - `municipios`: `estado VARCHAR(20) NOT NULL DEFAULT 'puesta_en_marcha'` con CHECK de los 5; `fue_produccion BOOLEAN NOT NULL DEFAULT FALSE`; `estado_antes_baja VARCHAR(20) NULL`; `max_usuarios_activos INTEGER NULL CHECK (> 0)`; `id_provincia INTEGER NULL → provincias`; `id_partido INTEGER NULL → partidos`; único parcial `uq_municipio_modelo ON municipios ((true)) WHERE estado = 'modelo'`; CHECK `id_provincia IS NOT NULL OR estado IN ('baja','modelo')`; trigger `municipios_estado_sync` que deriva `activo = (estado <> 'baja')`, pone `fue_produccion = true` al pasar a `produccion` y nunca lo devuelve a false; trigger que exige `codigo_pais = provincias.codigo_pais` si hay provincia.
  - `municipio_modulo (id_municipio_modulo SERIAL PK, id_municipio → municipios, modulo_codigo → modulos, habilitado BOOLEAN NOT NULL, min_nivel_acceso SMALLINT NOT NULL CHECK 0-5, + §10)`, único `(id_municipio, modulo_codigo)`, clase `catalogo`, grupo `configuracion`.
  - `area.es_sistema BOOLEAN NOT NULL DEFAULT FALSE` y trigger `area_sistema_no_baja` que rechaza `activo = false` en un área con `es_sistema` (mensaje del texto fijo).
  - `municipio_tabla_clase.grupo VARCHAR(20) NULL` con CHECK en `GRUPOS`, y CHECK `clase = 'global' OR grupo IS NOT NULL` agregado `NOT VALID` y validado en la `130c` después de cargar los grupos.
  - `usuario_invitacion (id_invitacion BIGSERIAL PK, id_usuario → usuarios, id_municipio NULL → municipios, token_hash TEXT NOT NULL UNIQUE, vence_en TIMESTAMPTZ NOT NULL, usada_en TIMESTAMPTZ NULL, id_usuario_alta, activo, fecha_alta)`, clase `mixta`, grupo `usuarios`.
  - `municipio_tarea (id_tarea UUID PK, id_municipio → municipios NULL, tipo VARCHAR(20) CHECK IN ('alta','exportacion','vaciado'), estado VARCHAR(20) CHECK IN ('pendiente','corriendo','ok','error'), detalle JSONB, archivo VARCHAR(300) NULL, vence_en TIMESTAMPTZ NULL, id_usuario_alta, fecha_alta, fecha_modificacion)`, clase `mixta`, grupo `configuracion`, para el estado de las tareas asíncronas y la retención de exportaciones.
- **`130c`:**
  - `paises`: `AR` (Argentina, Provincia, Partido, `America/Argentina/Buenos_Aires`, habilitado) y `VE` (Venezuela, Estado, Municipio, `America/Caracas`, **no** habilitado).
  - San Andrés: `estado = 'demo'`, `id_provincia` = la de nombre «Buenos Aires»; id 2: `estado = 'baja'`.
  - `area.es_sistema = true` para las 6 áreas activas de San Andrés, **por nombre**: Secretaría de Gobierno, Secretaría de Planeamiento y Obras Públicas, Secretaría de Salud, Secretaría de Seguridad, Secretaría de Servicios Públicos, Subsecretaría de Tránsito. La migración falla si no encuentra las 6.
  - `municipio_modulo` de San Andrés: todos los módulos activos, `habilitado = true`, `min_nivel_acceso` = el de `modulos`.
  - `grupo` de cada tabla no global. El builder lo propone con una consulta (`clase` + FKs a `ciudadanos`/`empresas`/`usuarios`) y la lista final va en la migración; la `130c` termina con `VALIDATE CONSTRAINT`.

- [ ] **Paso 1: Tests** en `smoke_alta_municipio.py`:
  - `test_base_f4`: existen las tablas y columnas; San Andrés en `demo` con provincia; id 2 en `baja` y `activo = false`; 6 áreas con `es_sistema`; `municipio_modulo` de San Andrés = cantidad de módulos activos; ninguna tabla no global sin `grupo`.
  - `test_triggers_f4`: `UPDATE area SET activo = false` sobre un área de sistema falla; un segundo municipio en `modelo` falla por el único; pasar un municipio de prueba a `produccion` pone `fue_produccion = true` y volver a `puesta_en_marcha` lo deja en true; `estado = 'baja'` pone `activo = false`; una provincia de otro país que el `codigo_pais` falla.
  - `test_acciones_super`: `registrar_acceso_super(accion="vaciado", …)` deja su fila.
- [ ] **Paso 2:** fallan. **Paso 3:** escribir y aplicar las tres migraciones en `zaris_dev`. **Paso 4:** pasan; `smoke_segmentacion_f1.py` sigue en verde (tablas nuevas clasificadas).
- [ ] **Paso 5: Commit** `feat(it-01-f4-f5): base de F4 (migs 130, 130b y 130c)`.

### Tarea 5: El estado del municipio en tiempo de ejecución

**Archivos:**
- Modificar: `backend/app/core/municipio.py` (`_municipios`, `por_cada_municipio`, `municipio_por_slug`)
- Modificar: `backend/app/core/auth.py` (`get_current_user`, `get_current_ciudadano`)
- Modificar: `backend/app/services/demo_datos.py:303`, `backend/app/api/routes/demo_datos.py:138`
- Test: `backend/smoke_alta_municipio.py`

**Interfaces:**
- `_municipios(db)` carga `id_municipio, subdominio, direccion_base, estado` de **todos** los municipios y expone `por_subdominio` solo con los de `ESTADOS_OPERABLES`; `ids_activos` = operables.
- `async def estado_municipio(db, id_municipio: int) -> str | None` (cacheada con el mismo TTL).
- `municipio_actual`: para el super con `X-Municipio`, acepta también el municipio `modelo` (para editarlo) y rechaza `baja` (404).
- `get_current_user` / `get_current_ciudadano`: si el municipio de la cuenta no está en `ESTADOS_OPERABLES`, 401 `SESION_VENCIDA` (no revela el estado). El super no tiene municipio y no lo afecta.
- `por_cada_municipio` recorre solo `ESTADOS_OPERABLES`.
- `municipio_por_slug` (y `?m=`) responde 404 para `modelo` y `baja`.
- El generador demo selecciona `WHERE estado = 'demo'` en lugar de `direccion_base`.

- [ ] **Paso 1: Tests:** con un municipio de prueba C creado por el smoke (estado `puesta_en_marcha`, subdominio `c-prueba`, cuenta nivel 2):
  - `test_estado_baja`: pasar C a `baja` → login de su cuenta 401, su token vigente da 401, `GET /api/v1/publico/identidad-municipio` con `Origin: https://c-prueba.vecinos.zaris.com.ar` da 404, `alta-vecino` con `?m=` de C da 404; volver a `puesta_en_marcha` y todo responde.
  - `test_modelo_no_operable`: un municipio en `modelo` no resuelve por Origin (404) ni por slug; el super con `X-Municipio` del modelo lista sus áreas.
  - `test_demo_por_estado`: `POST /demo/poblar` con el administrador de San Andrés sigue aceptado; con el de C, 403.
- [ ] **Paso 2:** fallan. **Paso 3:** implementar. **Paso 4:** pasan, y `smoke_municipio_request.py`, `smoke_super_admin.py` y `smoke_demo_poblar.py` siguen en verde.
- [ ] **Paso 5: Commit** `feat(it-01-f4-f5): el estado del municipio decide login, origen, slug, crons y demo`.

### Tarea 6: País, provincia y agrupamientos

**Archivos:**
- Modificar: `backend/app/api/routes/super_admin.py` (`MunicipioSuperOut`, listado, PUT)
- Crear: `backend/app/api/routes/geo_catalogo.py` o ampliar `geo.py` con `GET /api/v1/geo/paises` (con `?para_alta=true`) y `GET /api/v1/geo/provincias?codigo_pais=` y `GET /api/v1/geo/partidos?id_provincia=` (con token, cualquier nivel)
- Modificar: `web-app/src/modules/municipios/pages/MunicipiosPage.tsx`, `web-app/src/shell/SelectorMunicipio.tsx`, `frontend/js/menu.js:517-583` (selector)
- Test: `backend/smoke_alta_municipio.py`

**Interfaces:**
- `MunicipioSuperOut` suma `estado`, `fue_produccion`, `codigo_corto`, `id_provincia`, `provincia_nombre`, `id_partido`, `partido_nombre`, `codigo_pais`, `pais_nombre`, `etiqueta_nivel_1`, `etiqueta_nivel_2`, `max_usuarios_activos`, `cuentas_activas`.
- `GET /super/municipios` ordena por país, provincia y nombre; acepta `?codigo_pais=&id_provincia=&estado=`.
- `PUT /super/municipios/{id}` acepta `id_provincia` e `id_partido` (validados contra el país); ya no acepta `pais` ni `provincia` en texto (se ignoran: el texto se deriva).
- El selector «Operando en» agrupa con `<optgroup>` por país y provincia, e incluye el modelo rotulado «Modelo — <nombre>». Los municipios en `baja` no aparecen en el selector.

- [ ] **Paso 1: Tests:** `test_geo_catalogo` (paises con `para_alta` devuelve solo AR; provincias de AR son 24); `test_municipio_provincia` (PUT con una provincia de otro país → 422; con la de AR → 200 y `provincia_nombre` correcto; filtro por `id_provincia`).
- [ ] **Paso 2-4:** fallan, implementar, pasan. Typecheck.
- [ ] **Paso 5:** en el navegador local, el super ve la lista agrupada y el selector con grupos.
- [ ] **Paso 6: Commit** `feat(it-01-f4-f5): pais y provincia del catalogo, municipios agrupados`.

### Tarea 7: Módulos por municipio en el backend

**Archivos:**
- Crear: `backend/app/services/municipios/modulos.py`
- Modificar: `backend/app/core/auth.py:256-303` (`modulos_permitidos`, `require_modulo`)
- Modificar: `backend/app/api/routes/buc.py:75-86` (borrar la copia; usar el servicio en lote)
- Modificar: `backend/app/services/login_interno.py:148`, `backend/app/api/routes/admin_permisos.py`
- Modificar: `backend/app/main.py` (dependency de módulo en cada `include_router`)
- Modificar: `backend/app/api/routes/publico_identidad.py`, `config_identidad.py` (lista de módulos habilitados)
- Modificar: los servicios con efectos cruzados (lista en el Paso 3)
- Test: `backend/smoke_alta_municipio.py`

**Interfaces:**
- `async def modulos_habilitados(db, id_municipio: int) -> dict[str, int]`: `{modulo_codigo: min_nivel_acceso}` de `municipio_modulo` con `habilitado`, unido a `modulos.activo`. Cacheado por proceso 60 s, con `invalidar_modulos(id_municipio)`.
- `async def modulo_esta_habilitado(db, id_municipio: int, codigo: str) -> bool`: atajo sobre `modulos_habilitados`, para las guardas en servicios y procesos programados.
- `async def modulos_permitidos(db, id_usuario: int, nivel: int, id_municipio: int | None) -> list[str]`: si `id_municipio` es None (super sin selección), usa `modulos` como hoy; si no, defaults = habilitados con `min_nivel >= nivel`, y los overrides de `usuario_modulos` **solo** sobre módulos habilitados (un override no habilita un módulo apagado).
- El administrador del municipio llama con su municipio; `get_current_user` ya trae `id_municipio`, y `login_interno.py:148` y `auth.py:200` lo pasan.
- `async def modulos_permitidos_lote(db, usuarios: list[tuple[int, int]], id_municipio: int) -> dict[int, list[str]]` para `buc.py`.
- `def modulo_habilitado(*codigos: str)`: dependency de router. Resuelve el municipio de la request sin exigir token cuando la ruta es pública (`municipio_de_origen` / token del vecino / `municipio_actual`) y responde **404** si ninguno de los `codigos` está habilitado. Se monta con `include_router(..., dependencies=[Depends(modulo_habilitado("reclamos"))])`. Mapa router → códigos en `app/services/municipios/modulos.py::MODULOS_POR_ROUTER`, documentado (reclamos, adjuntos y públicos de reclamos → `reclamos`; OT y adjuntos de OT → `ot_supervisor|ot_agente|ot_auditoria`; agenda_* → `agenda`; turnos y turnos públicos → `turnos`; agenda pública y entradas del vecino → `entradas`; tramites* → `tramites`; emergencias y emergencias públicas → `emergencias`; encuestas* → `encuestas`; bi* → `bi`). Los routers de auth, BUC, usuarios, config, super, geo, notificaciones y dashboard no llevan la dependency.
- `async def validar_dependencias(habilitados: set[str]) -> None`: 422 con el texto fijo si un habilitado no tiene sus `DEPENDENCIAS_MODULOS`.
- `PUT /api/v1/admin/permisos/modulos/{codigo}`: pasa a escala del municipio de la request; el administrador cambia `min_nivel_acceso` (1-5) en `municipio_modulo`; el super además `habilitado` (`municipio_modulos` en el registro). Los módulos de nivel 0 no aparecen para el administrador.
- `IdentidadOut` e `IdentidadMunicipioOut` suman `modulos_habilitados: list[str]`.

- [ ] **Paso 1: Tests** (municipio C del smoke con `reclamos` y `encuestas` deshabilitados):
  - `test_modulo_404`: un admin de C → `GET /api/v1/reclamos` 404; un vecino de C → `GET /api/v1/publico/reclamos` 404; `GET /publico/identidad-municipio` de C no lista `reclamos`; en San Andrés, todo 200.
  - `test_modulos_permitidos_municipio`: `/auth/me` de un admin de C no trae `reclamos` aunque tenga un override `permitido = true`.
  - `test_nivel_por_municipio`: el admin de C sube `turnos` a nivel 2 → un nivel 4 de C ya no lo ve; en San Andrés el nivel 4 lo sigue viendo.
  - `test_dependencias`: el super intenta habilitar `turnos` con `agenda` apagado → 422 «turnos necesita agenda habilitado»; deshabilitar `agenda` con `turnos` prendido → 422.
  - `test_efectos_apagados`: en C con `encuestas` apagado, cumplir un turno no crea `encuesta_envio`; con `emergencias` apagado, la Guardia responde 404 y no escribe `emergencia_atencion`.
- [ ] **Paso 2:** fallan.
- [ ] **Paso 3:** implementar. Relevar con `grep` los efectos cruzados (creación de `encuesta_envio`, `services/autoasignacion.py`, `services/guardia.py`, el dispatcher de encuestas, el cron de trámites) y poner la guarda `await modulo_esta_habilitado(db, id_municipio, "<codigo>")` en cada uno; la lista queda en el docstring de `modulos.py`.
- [ ] **Paso 4:** pasan; `smoke_aislamiento.py` completo sin fallas (con San Andrés y B con todo habilitado) y la suite (`correr_suite.py`) en verde.
- [ ] **Paso 5: Commit** `feat(it-01-f4-f5): modulos habilitados y nivel minimo por municipio, aplicados en la API`.

### Tarea 8: Módulos por municipio en los frontends

**Archivos:**
- Modificar: `web-app/src/modules/usuarios/views/CatalogoModulosView.tsx` (municipio del selector; columna «Habilitado» solo para el super)
- Modificar: `zaris-vecinos/src/lib/identidad.ts`, `src/pages/HomePage.tsx` y la navegación (ocultar lo deshabilitado); ídem `zaris-agentes`
- Modificar: `frontend/js/menu.js` (sin cambios de lógica si `modulos_permitidos` ya viene filtrado; verificar)

**Interfaces:**
- Consume: `modulos_habilitados` de la identidad y `modulos_permitidos` ya filtrados (Tarea 7).
- En la PWA del vecino: `reclamos` oculta Mis reclamos y Nuevo reclamo; `turnos` y `entradas` sus secciones; `emergencias` la sección y el botón de pánico. Sin lista o con lista vacía (backend viejo), se muestra todo.

- [ ] **Paso 1:** implementar. **Paso 2:** typecheck en los tres repos.
- [ ] **Paso 3:** en el navegador local, con C sin `reclamos`: el sidebar del admin de C no lo muestra; la PWA del vecino de C (`localhost:5174` con el backend apuntando a C por un Origin forzado en el entorno de desarrollo, o vía el `tenant` mock de DEV) no muestra reclamos; el super en Usuarios → Catálogo ve la columna «Habilitado».
- [ ] **Paso 4: Commit** en cada repo `feat(it-01-f4-f5): modulos habilitados por municipio en la interfaz`.

### Tarea 9: Direcciones y links por municipio

**Archivos:**
- Modificar: `backend/app/core/urls.py`
- Modificar los armadores relevados el 2026-10-27: `core/auth.py:280` (`_login_url`), `services/cuenta_zaris.py:292-293`, `services/encuestas_service.py:535,848`, `services/notificaciones.py:279,760,868,972`, `api/routes/publico_alta.py:111,172,323,662,701,730`, `services/cuenta_vecino.py:167`, `api/routes/publico_auth.py:245,376,557`, `api/routes/publico_reclamos.py:363`, `services/push.py:237`, `api/routes/config_identidad.py:150-151`, `publico_identidad.py:45`, `segundo_factor.py:133`
- Crear: `tools/barrido_links_mail.py`
- Test: `backend/smoke_alta_municipio.py`, `backend/smoke_alta_portal_links.py` (ampliar)

**Interfaces:**
- `async def base_app(db, id_municipio: int, app: Literal["zge", "vecinos", "agentes", "api"]) -> str`:
  - `api` → `settings.API_PUBLIC_BASE_URL` (una sola API para todos);
  - si el municipio es el de `direccion_base` → la URL de la setting de siempre (`FRONTEND_BASE_URL`, `APP_VECINOS_FRONTEND_URL`, `APP_AGENTES_FRONTEND_URL`), así local y San Andrés no cambian;
  - si no → `https://<subdominio>.<app>.zaris.com.ar`, tomando `zaris.com.ar` de la setting nueva `DOMINIO_BASE` (default `zaris.com.ar`);
  - fail-closed: sin subdominio o setting inválida → `""` y el llamador no arma el link.
- `url_portal_vecino`, `url_login_backoffice`, `url_alta_publica` pasan a recibir `(db, id_municipio)`; `url_alta_publica` ya no necesita `?m=` cuando el municipio tiene subdominio (lo sigue llevando para el municipio base).
- `tools/barrido_links_mail.py`: falla (exit 1) si en `backend/app` aparece `settings.FRONTEND_BASE_URL`, `settings.APP_VECINOS_FRONTEND_URL`, `settings.APP_AGENTES_FRONTEND_URL` o `settings.APP_BASE_URL` fuera de `core/urls.py` y `core/config.py`. Se suma a la suite.

- [ ] **Paso 1: Tests:**
  - `test_links_por_municipio`: con MOCK de mail capturando el HTML, disparar para C y para San Andrés: alta de vecino (verificación), recuperación de clave del vecino, recuperación de clave del funcionario, cuenta ZARIS desde la ficha, aviso de reclamo, encuesta. Todo link de C empieza con `https://c-prueba.<app>.zaris.com.ar`; todo link de San Andrés, con la setting de siempre.
  - `test_links_responden`: en `smoke_alta_portal_links.py`, seguir el link del mail de San Andrés (GET) como hoy.
  - `tools/barrido_links_mail.py` da exit 0.
- [ ] **Paso 2-4:** fallan, implementar, pasan.
- [ ] **Paso 5: Commit** `feat(it-01-f4-f5): links de mails y QR por municipio, con barrido`.

### Tarea 10: Páginas públicas por origen

**Archivos:**
- Modificar: `frontend/alta-vecino.html:283,383` (sin `?m=`, resuelve por Origin)
- Modificar: `backend/app/api/routes/publico_alta.py` (endpoints que hoy exigen `m`: aceptar Origin cuando falta)
- Modificar: `web-app/src/autoservicio/` si algo asume el municipio base
- Test: `backend/smoke_alta_un_paso.py` (ampliar)

**Interfaces:**
- Regla única: `?m=<slug>` gana si viene; si no, `municipio_de_origen`. Así los links viejos con `?m=SAN` siguen andando.

- [ ] **Paso 1: Tests:** alta en un paso para C con `Origin: https://c-prueba.zge.zaris.com.ar` sin `m` → la ficha queda en C; con `?m=SAN` desde el mismo origen → gana el slug (San Andrés); sin `m` y sin Origin → municipio base.
- [ ] **Paso 2-4:** fallan, implementar, pasan. **Paso 5:** recorrido en el navegador de `alta-vecino.html` sin `?m=` en local (cae al base).
- [ ] **Paso 6: Commit** `feat(it-01-f4-f5): paginas publicas resuelven el municipio por origen`.

### Tarea 11: Alta de municipio (backend)

**Archivos:**
- Crear: `backend/app/services/municipios/clonado.py` (el `Clonador` extraído de `seed_municipio_aislamiento.py`, con un parámetro `marcar: bool` — el alta usa `False`)
- Crear: `backend/app/services/municipios/alta.py`
- Crear: `backend/app/services/municipios/invitacion.py`
- Modificar: `backend/app/api/routes/super_admin.py`
- Modificar: `backend/seed_municipio_aislamiento.py` (importa el `Clonador` del servicio con `marcar=True`)
- Crear: `backend/app/api/routes/invitacion.py` (público: `/api/v1/auth/invitacion/*`)
- Test: `backend/smoke_alta_municipio.py`

**Interfaces:**
- `class AltaMunicipioIn(BaseModel)`: `nombre`, `codigo_pais`, `id_provincia`, `id_partido: int | None`, `zona_horaria: str | None`, `codigo_corto`, `subdominio`, `identidad: {color, logo_url, geo_limite_geojson, geo_bbox_centro_lat, geo_bbox_centro_lon, geo_bbox_delta_grados}` (todas opcionales), `copiar: list[str]` (grupos de catálogo del modelo, de `CATALOGOS_COPIABLES`), `modulos: list[str]`, `max_usuarios_activos: int | None`, `administrador: {nombre, apellido, dni, email}`.
- `CATALOGOS_COPIABLES = {"areas_subareas", "cargos", "tipos_reclamo", "prestaciones", "tramites", "emergencias", "encuestas"}`, cada uno con su lista de tablas en `alta.py`. Las áreas fijas y la configuración se copian siempre.
- `async def dar_de_alta(db, datos: AltaMunicipioIn, *, id_super: int) -> dict`:
  - todo en **una transacción**;
  - valida `PATRON_SUBDOMINIO`, `SUBDOMINIOS_RESERVADOS`, `PATRON_CODIGO_CORTO`, país con `habilitado_para_alta`, provincia del país, módulos con `validar_dependencias` y que incluyan `MODULOS_FIJOS`;
  - crea el municipio en `puesta_en_marcha` → copia del modelo (clonado sin marca, re-mapeo de FK) → `municipio_modulo` → todas las claves de `configuracion_general` del modelo, con `activo` y `tipo` explícitos, pisadas por la identidad recibida y re-sembrando por nombre `id_area_salud` e `id_espacio_guardia` → ficha BUC + agente + usuario nivel 1 en la primera subárea activa del área fija «Secretaría de Gobierno» (si no copió ninguna, crea «Administración» en esa área) → invitación;
  - devuelve `{"id_municipio", "advertencias": [...]}` (p. ej. «sin contorno ni bbox: el geocoding usará la zona por defecto»);
  - registra `municipio_alta` con `registrar_acceso_super_en` en la misma transacción.
- `POST /api/v1/super/municipios` → 201 con lo anterior. Si el clonado puede superar los 300 s, pasar a 202 + `municipio_tarea` (el builder mide con el modelo real en local; si tarda menos de 30 s queda síncrono).
- `POST /api/v1/super/municipios/{id}/estado` body `{estado, confirmacion}`: transiciones de la §4.1 del spec; `produccion` exige `confirmacion == nombre`; `baja` guarda `estado_antes_baja`; reactivar vuelve a `estado_antes_baja`. Registra `municipio_estado`. Invalida la caché de municipios y de módulos.
- `PUT /api/v1/super/municipios/{id}/modulos` body `{modulos: [{codigo, habilitado}]}`.
- `GET /api/v1/super/municipios/{id}/dominios` → por cada app `{host, dns: bool, https: int | None}` (resolución con `asyncio.get_running_loop().getaddrinfo` y GET con httpx, timeout 5 s).
- `POST /api/v1/super/municipios/{id}/prueba` → lista de chequeos `{nombre, ok, detalle}` (identidad pública por cada host, que el login resuelva el municipio por Origin sin loguear — un `POST /auth/login` con credenciales inválidas desde ese Origin da 401 y no 404 —, invitación vigente y su link con 200, módulos = los elegidos).
- Invitación (`invitacion.py`):
  - `async def crear_invitacion(db, *, id_usuario: int, id_municipio: int | None, id_actor: int) -> str`: token `secrets.token_urlsafe(32)`, guarda `sha256` en `token_hash`, vence en `INVITACION_HORAS`, desactiva las anteriores de la cuenta, devuelve el link `base_app(…, "zge")/frontend/invitacion.html?t=<token>`. Manda el mail con la identidad del municipio (o ZARIS si es super).
  - `POST /api/v1/auth/invitacion/aceptar` body `{token, password}`: valida token vigente sin usar (texto fijo si no), valida la política de clave, guarda el hash, marca `usada_en`, **habilita el segundo factor** (`segundo_factor.habilitar`, actor = la cuenta del super que invitó) y responde lo mismo que el login para una cuenta en estado `vincular` (desafío + estado), así el shell sigue directo a vincular.
  - `POST /api/v1/super/usuarios/{id}/invitacion` reenvía.
- Crear: `frontend/invitacion.html` (vanilla, mismo DS que `login.html`): pide la clave dos veces, llama a `aceptar` y continúa con el flujo de vinculación de `login.html` (reusar su código, no copiarlo: extraer a `frontend/js/segundo_factor.js` si hace falta).

- [ ] **Paso 1: Tests:**
  - `test_alta_validaciones`: subdominio `Vicente-Lopez`, `córdoba`, `api`, el de San Andrés; código `sa`, `SAN`; país `VE`; provincia de otro país; módulos sin `usuarios` o con `turnos` sin `agenda` → 422/409, y la cantidad de municipios no cambia.
  - `test_alta_ok`: alta de D desde el modelo (el smoke crea un modelo mínimo si no hay) → D en `puesta_en_marcha`; sus áreas fijas = 6 con `es_sistema`; claves de configuración = las del modelo; `id_area_salud` apunta a un área de D; existe su admin nivel 1 con agente y subárea; hay una invitación vigente; el registro del super tiene `municipio_alta`.
  - `test_alta_atomica`: forzar un fallo en el clonado (monkeypatch del `Clonador.clonar` para la tercera tabla) → no existe D ni ninguna fila con su id en las tablas `catalogo`/`operativo`.
  - `test_alta_concurrente`: dos `POST` iguales con `asyncio.gather` → uno 201, el otro 409.
  - `test_invitacion`: aceptar con token correcto → 200 y respuesta de vinculación; el mismo token otra vez → 401 texto fijo; un token vencido (fecha forzada) → 401; el mail capturado tiene el link al subdominio de D.
  - `test_estados`: `produccion` sin confirmación → 422; con confirmación → `fue_produccion`; `baja` y reactivar → vuelve a `produccion`.
- [ ] **Paso 2-4:** fallan, implementar, pasan. `seed_municipio_aislamiento.py` y `smoke_aislamiento.py` siguen en verde con el `Clonador` importado.
- [ ] **Paso 5: Commit** `feat(it-01-f4-f5): alta de municipio, estados e invitacion del primer administrador`.

### Tarea 12: Municipio modelo

**Archivos:**
- Crear: `backend/crear_municipio_modelo.py`
- Crear: `docs/municipio_modelo_inventario.md` (generado por el script, sin datos personales)

**Interfaces:**
- `python crear_municipio_modelo.py --inventario`: imprime y escribe en `docs/municipio_modelo_inventario.md`, por cada tabla de grupo `maestros` y `configuracion` de San Andrés: cantidad de filas activas, cuántas copiaría y cuáles propone descartar con el motivo (inactivas, nombres que matchean `(?i)test|prueba|qa|demo|borrar`, catálogos sin uso).
- `python crear_municipio_modelo.py --aplicar --excluir <archivo>`: crea el municipio «Modelo ZARIS» (`estado = 'modelo'`, sin subdominio, código `MOD`, provincia Buenos Aires) y copia los catálogos aprobados con el `Clonador` sin marca. Nunca copia tablas de grupo `contactos`, `usuarios` ni `operativo`. Idempotente: si ya existe un modelo, aborta.
- El script corre contra local y, en el corte B, contra prod con `ENV_FILE` del pooler (CLAUDE.md, memoria de conexión directa), con confirmación por consola.

- [ ] **Paso 1:** correr `--inventario` en local y **presentarle a César la tabla completa** (catálogo, cantidad, a copiar, a descartar con motivo). Esperar su aprobación; lo que él cambie va al archivo de exclusiones.
- [ ] **Paso 2:** `--aplicar` en local; `test_modelo` en el smoke: el modelo existe, no tiene filas en tablas de grupo `contactos`/`usuarios`/`operativo`, tiene las 6 áreas fijas y todas las claves de configuración.
- [ ] **Paso 3:** recorrer en el navegador como super con el selector en «Modelo»: Maestros → Áreas, Tipos de reclamo, Prestaciones.
- [ ] **Paso 4: Commit** `feat(it-01-f4-f5): municipio modelo e inventario de catalogos`.

### Tarea 13: Áreas fijas en la interfaz y en la API

**Archivos:**
- Modificar: `backend/app/api/routes/admin_tablas.py` (baja de `area` con `es_sistema` → 422 texto fijo, antes de tocar la base)
- Modificar: `frontend/admin_tablas.html` (botón de baja deshabilitado con tooltip para `es_sistema`)

- [ ] **Paso 1: Test:** `test_area_fija_api`: `PUT` de baja sobre un área fija → 422 texto fijo; renombrarla → 200.
- [ ] **Paso 2-4:** falla, implementar, pasa. **Paso 5:** verificar en el navegador local el botón deshabilitado.
- [ ] **Paso 6: Commit** `feat(it-01-f4-f5): areas fijas no se dan de baja`.

### Tarea 14: Tope de cuentas activas

**Archivos:**
- Crear: `backend/app/services/municipios/tope.py`
- Modificar: todas las vías que crean o reactivan una cuenta interna: `services/cuenta_zaris.py::crear_usuario_interno`, `api/routes/buc.py` (alta y reactivación de usuarios), la reactivación por `PUT /buc/usuarios/{id}/estado`
- Modificar: `web-app/src/modules/usuarios/views/MaestroView.tsx` («N de M» y aviso desde el 90 %)
- Modificar: `GET /api/v1/buc/usuarios` (o un endpoint chico) para devolver `cuentas_activas` y `max_usuarios_activos`

**Interfaces:**
- `async def exigir_cupo(db, id_municipio: int) -> None`: con `SELECT … FOR UPDATE` sobre la fila del municipio (serializa altas simultáneas), cuenta `usuarios` activos del municipio con nivel 1-5; si `max_usuarios_activos` no es NULL y la cuenta es `>=`, 409 texto fijo.
- `async def cupo(db, id_municipio: int) -> dict`: `{activas, maximo, aviso: bool}`.

- [ ] **Paso 1: Tests:** `test_tope`: C con tope 2 y 2 activas → crear la tercera 409 (por las dos vías); desactivar una → crear 201; reactivar con el tope lleno → 409; bajar el tope a 1 con 2 activas no desactiva a nadie; dos altas simultáneas con 1 lugar → una 201, una 409.
- [ ] **Paso 2-4:** fallan, implementar, pasan. **Paso 5:** «N de M» en el navegador. **Paso 6: Commit** `feat(it-01-f4-f5): tope de cuentas activas por municipio`.

### Tarea 15: Pantallas de alta, ficha del municipio y super administradores

**Archivos:**
- Modificar/crear: `web-app/src/modules/municipios/` (`pages/AltaMunicipioPage.tsx` asistente de 6 pasos, `pages/MunicipioFichaPage.tsx` con estado, módulos, dominios, prueba, tope, invitación, exportaciones y vaciado; `pages/SuperAdministradoresPage.tsx`; `api.ts`)
- Crear: `backend/app/services/municipios/super_admins.py` y endpoints `GET/POST /api/v1/super/administradores`, `POST /api/v1/super/administradores/{id}/baja`

**Interfaces:**
- `POST /super/administradores` body `{nombre, apellido, email}`: cuenta nivel 0 sin municipio, email reservado (la regla de F3), invitación con mail como ZARIS; registra `super_alta`.
- `POST /super/administradores/{id}/baja`: 409 si es el último super activo o si es el propio; registra `super_baja`.
- El asistente usa los textos fijos; los catálogos copiables se muestran con su nombre visible, no con el código. La ficha muestra las advertencias del alta.

- [ ] **Paso 1: Tests backend:** `test_super_admins` (alta → nivel 0 sin municipio + invitación; baja del último → 409; baja propia → 409).
- [ ] **Paso 2-4:** fallan, implementar, pasan. Typecheck.
- [ ] **Paso 5:** recorrido en el navegador local, con clics: alta de un municipio E completo desde el asistente; ficha; deshabilitar un módulo; cambiar el tope; reenviar la invitación; abrir el link de invitación del mail (MOCK) en otra pestaña con el Origin del base (en local cae al base: verificar solo que la página carga y valida el token); alta y baja de un super.
- [ ] **Paso 6: Commit** `feat(it-01-f4-f5): asistente de alta, ficha del municipio y super administradores`.

### Tarea 16: Exportación y vaciado

**Archivos:**
- Crear: `backend/app/services/municipios/exportacion.py`, `vaciado.py`
- Modificar: `backend/app/api/routes/super_admin.py` (endpoints)
- Crear: `backend/app/api/routes/municipios_mantenimiento.py` (dispatcher con `X-Dispatcher-Token` para la purga) y un job en el workflow existente de mantenimiento o uno nuevo `.github/workflows/municipios-mantenimiento.yml` (diario)
- Supabase: bucket privado `exportaciones` (local: el mismo nombre en el proyecto de Storage de desarrollo que usen los smokes, o MOCK si no hay)

**Interfaces:**
- `async def exportar(id_municipio: int, *, id_super: int) -> uuid.UUID`: crea `municipio_tarea` tipo `exportacion`, corre en `BackgroundTasks` con sesión propia; arma un zip con un JSON por tabla (`catalogo`, `operativo` y filas propias de `mixta`), sube a `exportaciones/m{id}/<AAAAMMDD-HHMMSS>.zip`, `vence_en = now + EXPORTACION_RETENCION_DIAS`.
- `GET /super/municipios/{id}/exportaciones` → lista vigente; `POST …/exportaciones` → 202 `{id_tarea}`; `GET /super/tareas/{id_tarea}` → estado; `GET …/exportaciones/{id_tarea}/descarga` → URL firmada de 10 min y registro `exportacion` en `super_admin_acceso`.
- `async def plan_vaciado(db, id_municipio: int, grupos: set[str]) -> list[dict]`: `[{tabla, filas}]` en orden de borrado, calculado con `grupo` + `fkm_*`; incluye lo que arrastra cada grupo (contactos arrastra operativo que los referencia y las credenciales de vecinos; `usuarios.id_ciudadano` se pone en NULL si no se eligió `usuarios`).
- `POST /super/municipios/{id}/vaciado/plan` body `{grupos}` → el plan (sin escribir).
- `POST /super/municipios/{id}/vaciado` body `{grupos, confirmacion}` → 409 si `estado ∉ ESTADOS_VACIABLES` o `fue_produccion`; 422 si `confirmacion != nombre`; si no, 202: exporta, y solo si la exportación terminó `ok` vacía en una transacción con `pg_advisory_xact_lock(id_municipio)`, borra los objetos de Storage de los adjuntos leídos antes de borrar las filas, re-siembra las claves por id desde el modelo, registra `vaciado`. Nunca toca: globales, grupo `configuracion`, áreas fijas, el administrador principal (el primer nivel 1 del municipio por `fecha_alta`) con su agente, ficha y subárea.
- `POST /api/v1/municipios/mantenimiento/purgar-exportaciones` (dispatcher): borra objetos y marca las tareas con `vence_en < now`.

- [ ] **Paso 1: Tests:**
  - `test_vaciado_guardas`: C en `produccion` → 409; C pasada a `baja` y reactivada (vuelve a `produccion`) → 409; C en `puesta_en_marcha` con confirmación mal → 422.
  - `test_vaciado_operativo`: C con un reclamo, un turno y un trámite; vaciar `operativo` → 0 filas operativas, los contactos siguen, la configuración y las áreas fijas siguen.
  - `test_vaciado_todo`: vaciar los 4 grupos → solo quedan el administrador principal (y su agente, ficha y subárea), las áreas fijas, la configuración y `municipio_modulo`; las claves por id apuntan a filas existentes; recorrer `GET` de cada listado de C → sin 500.
  - `test_vaciado_concurrente`: dos vaciados a la vez → uno corre, el otro 409 «ya hay un vaciado en curso».
  - `test_exportacion_retencion`: la exportación existe y su zip tiene un JSON por tabla con filas de C y ninguna de otro municipio; con `vence_en` forzado al pasado, la purga la borra.
- [ ] **Paso 2-4:** fallan, implementar, pasan.
- [ ] **Paso 5:** en el navegador, desde la ficha: ver el plan, vaciar con confirmación, descargar la exportación.
- [ ] **Paso 6: Commit** `feat(it-01-f4-f5): exportacion con retencion de 90 dias y vaciado por grupos`.

### Tarea 17: Arreglos de pantallas con tablas vacías y menores de F1+F2

**Archivos** (detalle con archivo:línea en `docs/guia_arranque_tablas.md`, «Riesgos estructurales»):
- R3: `config_identidad.py:172-178` y `guardar_config` pasan a insertar o actualizar; `ParametrosSistemaView.tsx:184-187` muestra las claves faltantes con su valor por defecto en lugar de ocultarlas.
- R4: sin claves `geo_bbox_*`, el geocoding responde 409 «El municipio no tiene configurada su zona de búsqueda» en vez de caer a Vicente López (salvo el municipio base, que conserva el fallback).
- R6: `turnos.py:1133-1135` distingue el único de horario (409 «horario tomado») de cualquier otra `IntegrityError` (422 con el motivo).
- R7: `autoasignacion.py` y `reclamos.py` buscan los estados de OT por código y fallan con 409 claro si faltan, sin insertar con estado NULL.
- R8: `guardia.py:30` valida la clave con `^[0-9]{1,9}$` (fail-closed).
- R9/R10: nacionalidad y tipo de representación por defecto salen de `configuracion_general` del municipio (claves nuevas `id_nacionalidad_defecto`, `id_tipo_representacion_defecto`, sembradas por nombre en la `130c` y en el alta).
- Menores: el límite de intentos del login por mail se clavea por municipio (`check_rate_limit(f"login:{id_municipio}:{ip}")`); `seed_catalogos_emergencias.py` y `seed_activos_local.py` reciben `--municipio`.

- [ ] **Paso 1: Test** `test_municipio_vacio` en el smoke: después de `test_vaciado_todo`, el admin de C recorre por API cada listado y cada alta mínima de la guía de arranque (crear subárea, tipo de reclamo, reclamo, prestación, turno, tipo de trámite, trámite, emergencia) en el orden de la guía: ninguna respuesta 500; los errores esperables son 409/422 con mensaje.
- [ ] **Paso 2-4:** falla, implementar, pasa.
- [ ] **Paso 5:** recorrer en el navegador cada módulo del municipio C vacío (con clics): estados vacíos, sin pantallas rotas.
- [ ] **Paso 6: Commit** `fix(it-01-f4-f5): pantallas y altas con tablas vacias`.

### Tarea 18: Suite, aislamiento con tres municipios y documentación

- [ ] **Paso 1:** `smoke_aislamiento.py` en sus tres modos con San Andrés, el modelo y un municipio dado de alta por el servicio de la Tarea 11 (además del B de siempre): 0 fallas. El modelo no aparece en ninguna respuesta de un municipio.
- [ ] **Paso 2:** suite completa (`correr_suite.py`) en verde, más `tools/barrido_links_mail.py` y `tools/barrido_guards_nivel.py`.
- [ ] **Paso 3:** revisión final del branch por un revisor fresco (el más capaz disponible) contra el spec; arreglar lo que salga, cada arreglo con su test.
- [ ] **Paso 4: Documentación:**
  - CLAUDE.md: §10 (toda tabla nueva lleva `grupo`); §5 (links solo con `base_app`/helpers de `urls.py`); §1/§3 (estado del municipio, módulos por municipio, `modulo_habilitado` en todo router nuevo de un módulo deshabilitable); §21 (migs 130); §6 (dominios por municipio).
  - Skills: `modulo-permisos` (municipio_modulo), `modulo-usuarios` (tope, invitación), `modulo-config`, `modulo-app-vecinos` (links por municipio), `modulo-admin-tablas` (áreas fijas).
  - `docs/guia_arranque.md` para el administrador de un municipio nuevo, a partir del anexo A del plan general.
  - `docs/contrato_api_publica.md`: `modulos_habilitados` en la identidad.
- [ ] **Paso 5: Commit** `docs(it-01-f4-f5): reglas, skills, guia de arranque y contrato`.

### Tarea 19: Revisión de la lista de tareas del corte B (con César)

- [ ] **Paso 1:** presentarle a César la lista de pasos del corte B (Tarea 20) con lo que él hace en cada uno (SQL Editor, panel de Cloudflare, el email del administrador de prueba) y la ventana.
- [ ] **Paso 2:** acordar fecha y el email del administrador de prueba (lo da César en el momento; no va al repo).

### Tarea 20: Corte B en prod (con César)

- [ ] **Paso 1:** backup de prod; pausar los 4 workflows de cron.
- [ ] **Paso 2:** `130` por César en el SQL Editor; `130b` y `130c` por MCP, de a una, verificando cada una (el código viejo sigue respondiendo 200: las columnas nuevas tienen default y `activo` sigue igual).
- [ ] **Paso 3:** merge de `it01-f4-f5` a `main` y de las ramas `cloudflare-pages` de las PWAs (si quedó algo de la Tarea 8). Verificar el deploy de Railway con un marcador (`/api/v1/super/municipios/{id}/estado` en `/openapi.json`) y los builds de Cloudflare Pages.
- [ ] **Paso 4:** GET de cada tabla tocada para absorber el `InvalidCachedStatementError` (CLAUDE.md §21). Smokes de San Andrés contra prod de solo lectura; reanudar los crons.
- [ ] **Paso 5:** `crear_municipio_modelo.py --inventario` contra prod, aprobación de César, `--aplicar`.
- [ ] **Paso 6: prueba de cierre** (spec §5), con César: alta de «Municipio de Prueba» (`prueba`, `PRU`) desde la interfaz → `tools/dominios_municipio.py prueba` → «Verificar» en verde → invitación al email de César → clave + vinculación → entra por `prueba.zge.zaris.com.ar` → carga la guía de arranque y un registro por circuito → vecino en `prueba.vecinos` con el mismo DNI que uno de San Andrés → agente en `prueba.agentes` → módulo deshabilitado da 404 → tope → vaciado con exportación y re-carga → San Andrés intacto (smokes, apps instaladas, push) → municipio de prueba a `baja` y `tools/dominios_municipio.py prueba --quitar`.
- [ ] **Paso 7:** escribir la **guía privada de alta** en `C:\Users\Cesar\Documents\ZARIS\credenciales-testing\guia_alta_municipio.md` a partir de la corrida (qué pedirle al cliente, pasos, DNS, primer administrador, perfiles mínimos, carga inicial). Nunca al repo.
- [ ] **Paso 8:** registro: `HISTORIAL_MIGRACIONES.md` (130 por César, 130b y 130c por MCP, fecha), `ESTADO.md`, memoria `project_it01_multi_municipio`. Commit y push.

## Lo que queda para fases posteriores

- **F5b:** zona horaria por municipio en el código, validadores y etiquetas de documento por país, geocoding por país; habilitar otro país en `paises.habilitado_para_alta`.
- **F6:** RLS con rol no dueño, prefijo `m{id}/` en los buckets, logs de crons por municipio, restauración de una exportación en una base vacía.
- **F7:** tableros consolidados por país y provincia.
- **Bloque del vecino** (después de esta fase, orden de César): web = app, iniciar trámites, Vecino 360, base de conocimiento.
