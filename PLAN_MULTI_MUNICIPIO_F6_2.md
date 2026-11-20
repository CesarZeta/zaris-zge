# IT-01 F6.2 — La segunda barrera, en local: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** que en local, con `DB_BARRERA=true`, la base de datos misma impida que una request vea o modifique filas de otro municipio, y que todo el producto siga funcionando.

**Architecture:** un usuario de conexión nuevo, `zaris_app`, sin permiso para saltear RLS, con políticas generadas desde `municipio_tabla_clase` que comparan `id_municipio` con la variable `app.id_municipio`. Un listener de SQLAlchemy aplica la variable al empezar cada transacción, leyéndola de `session.info`. Lo que no puede saber el municipio de antemano (cinco excepciones del diseño §4.4) usa una segunda conexión como `postgres`, que solo se obtiene desde `app/core/sistema.py`.

**Tech Stack:** PostgreSQL 17 (RLS), SQLAlchemy async + asyncpg, FastAPI.

**Spec:** [`PLAN_MULTI_MUNICIPIO_F6_DISENO.md`](PLAN_MULTI_MUNICIPIO_F6_DISENO.md) §4.1-4.4 y §5.

## Global Constraints

- **Solo local.** Nada de esta fase toca prod: la migración se aplica en `zaris_dev`; el corte en prod es F6.3.
- La barrera **falla cerrada**: sin `app.id_municipio`, una tabla de municipio no devuelve filas.
- Las políticas son `TO zaris_app`; `anon` y `authenticated` siguen sin ninguna (la API pública de Supabase queda cerrada).
- `zaris_app` no tiene ningún permiso sobre `_backup_*`.
- La clave de `zaris_app` en local es un valor de desarrollo en `backend/.env.local` (no se commitea); la migración no lleva claves.
- `DB_BARRERA=false` (default) deja todo como hoy: `engine` conecta como `postgres`.
- Con `DB_BARRERA=true` y sin `APP_DB_USER`/`APP_DB_PASSWORD`, el backend no arranca.
- Número de migración: el próximo libre al aplicarla (hoy 138; CLAUDE.md §21).

## Review Focus

1. **Una consulta corre antes de fijar el municipio** (dependencias que leen la base antes de `municipio_actual`): con la barrera ve vacío y responde 404/401 sin error explícito. → Task 4: la corrida completa de smokes con la barrera es la prueba; además, el chequeo «sin variable → 0 filas» de la Task 1.
2. **Un `commit()` a mitad de un guardado** (reclamo y después su historial): la segunda transacción tiene que conservar el municipio. → Task 2, test `transaccion_despues_de_commit`.
3. **Una sesión de segundo plano sin municipio** (avisos, mails, autoasignación): el aviso no sale y nadie se entera. → Task 4: smokes que esperan el mail o el aviso (`smoke_reclamo_alta_mail.py`, `smoke_tramites_aviso_inicio.py`) con la barrera.
4. **El super cambia de municipio en el selector** dentro de la misma pestaña: cada request fija el suyo; no puede quedar el anterior. → Task 3, el municipio va en `session.info` de la sesión de esa request (no hay estado global).
5. **Una tabla nueva sin política**: con la barrera nadie la ve. → Task 1, barrido de políticas en `smoke_barrera.py`.

---

### Task 1: Usuario `zaris_app`, permisos y políticas (local)

**Files:**
- Create: `backend/migrations/138_barrera_municipio.sql`
- Create: `tools/crear_usuario_zaris_app_local.sql` (crea el usuario en local con una clave que se pasa por `psql -v`; no se usa en prod)
- Create: `backend/smoke_barrera.py`

**Interfaces:**
- Produces: usuario `zaris_app`; políticas `barrera_municipio` en cada tabla clasificada; variable de sesión `app.id_municipio` (texto con el id).

- [ ] **Step 1: Escribir `smoke_barrera.py`** (solo local; conecta con asyncpg como `zaris_app` usando `APP_DB_USER`/`APP_DB_PASSWORD` de `.env.local`; recorre las tablas desde `municipio_tabla_clase`). Casos:
  - `sin_municipio_no_ve_nada`: sin variable, `SELECT count(*)` de cada tabla `catalogo`/`operativo` y de `usuarios` = 0.
  - `solo_ve_su_municipio`: con `set_config('app.id_municipio', '1', false)`, `SELECT count(*) … WHERE id_municipio <> 1` = 0 en cada tabla `catalogo`/`operativo`/`mixta` y en `usuarios`; y la tabla `reclamos` tiene filas.
  - `no_escribe_en_otro`: con el municipio 1, `UPDATE reclamos SET id_municipio = <otro> WHERE id_reclamo = <uno del 1>` falla (`new row violates row-level security policy`) y `INSERT` en `area` con otro municipio falla. Dentro de una transacción con ROLLBACK.
  - `globales_visibles`: `municipios`, `provincias`, `modulos` devuelven filas con o sin variable.
  - `config_global_solo_lectura`: con el municipio 1 se ven filas de `configuracion_general` con `id_municipio IS NULL`; `UPDATE` de una de ellas afecta 0 filas.
  - `super_invisible`: con el municipio 1, `usuarios WHERE id_municipio IS NULL` = 0.
  - `todas_con_politica`: toda tabla de `municipio_tabla_clase` con clase ≠ `global` tiene una política para `zaris_app` (`pg_policies`), y ninguna política en `public` nombra a `anon`/`authenticated`.
  - `sin_backups`: `SELECT` de una `_backup_*` da `permission denied`.
- [ ] **Step 2: Correr** `python smoke_barrera.py` — Expected: aborta porque el usuario no existe (RED).
- [ ] **Step 3: `tools/crear_usuario_zaris_app_local.sql`**: `CREATE ROLE zaris_app LOGIN PASSWORD :'clave' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE` (si no existe). Sumar `APP_DB_USER=zaris_app` y `APP_DB_PASSWORD=<dev>` a `backend/.env.local` y las dos claves (vacías) a `backend/.env.example`.
- [ ] **Step 4: Migración 138** (un archivo, un bloque `DO`; aborta con un mensaje claro si `zaris_app` no existe):
  - `GRANT USAGE ON SCHEMA public`, `GRANT SELECT, INSERT, UPDATE, DELETE` en cada tabla de `municipio_tabla_clase` (no en `_backup_*`), `GRANT USAGE, SELECT ON ALL SEQUENCES`, `GRANT EXECUTE ON ALL FUNCTIONS`; `ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO zaris_app` (y secuencias).
  - Por cada tabla `catalogo`/`operativo`: `CREATE POLICY barrera_municipio ON <t> FOR ALL TO zaris_app USING (id_municipio = (SELECT current_setting('app.id_municipio', true))::int) WITH CHECK (igual)`.
  - `usuarios` y las mixtas: la misma política; `configuracion_general` suma una segunda política `FOR SELECT TO zaris_app USING (id_municipio IS NULL)` (globales de solo lectura).
  - `global`: `CREATE POLICY barrera_global ON <t> FOR ALL TO zaris_app USING (true) WITH CHECK (true)`.
  - `DROP POLICY IF EXISTS` antes de cada `CREATE` (idempotente). Anotarla en `HISTORIAL_MIGRACIONES.md` como «solo local hasta F6.3».
- [ ] **Step 5: Aplicar en local** (crear el usuario, después la migración) y correr `smoke_barrera.py` — Expected: todo en verde. Si `current_setting('…')::int` falla con `''` (variable definida vacía), cambiar a `NULLIF(current_setting('app.id_municipio', true), '')::int` y anotar el Ruling.
- [ ] **Step 6:** Commit (`feat(db): usuario zaris_app y politicas de la barrera por municipio (local)`).

---

### Task 2: Dos conexiones y el municipio en cada transacción

**Files:**
- Modify: `backend/app/core/config.py` (`DB_BARRERA: bool = False`, `APP_DB_USER: str = ""`, `APP_DB_PASSWORD: str = ""`, propiedad `ASYNC_DATABASE_URI_APP`)
- Modify: `backend/app/core/database.py`
- Create: `backend/app/core/sistema.py`
- Create: `tools/barrido_sistema.py`
- Modify: `backend/smoke_barrera.py`

**Interfaces:**
- Produces:
  - `settings.ASYNC_DATABASE_URI_APP -> str`: con `DB_BARRERA`, la URI de `ASYNC_DATABASE_URI` con usuario y clave de `zaris_app` (`sqlalchemy.engine.make_url(...).set(username=..., password=...)`); si no, la misma URI. Con `DB_BARRERA` y alguno vacío: `RuntimeError` al importar `database.py`.
  - `database.engine` conecta con `ASYNC_DATABASE_URI_APP`; `AsyncSessionLocal` y `get_db` sin cambios de firma.
  - `async def fijar_municipio(db: AsyncSession, id_municipio: int) -> None` en `database.py`: guarda `db.info["id_municipio"]` y aplica `set_config('app.id_municipio', '<id>', true)` en la transacción en curso.
  - `def sesion_municipio(id_municipio: int) -> AsyncContextManager[AsyncSession]` en `database.py`: sesión de `AsyncSessionLocal` con el municipio ya fijado.
  - Listener `after_begin` sobre `sqlalchemy.orm.Session`: si `session.info` tiene `id_municipio`, aplica la variable en la transacción nueva.
  - `app/core/sistema.py`: `SesionSistema` (sessionmaker) y `async def get_db_sistema()` (dependency). Con `DB_BARRERA=false` reusa `database.engine` (mismas credenciales: ninguna conexión extra contra el pooler); con `true`, motor propio con `ASYNC_DATABASE_URI` (`postgres`) y pool chico (`pool_size=2, max_overflow=3`). **Ningún otro archivo** importa estos nombres ni crea motores (lo controla `tools/barrido_sistema.py`).
- [ ] **Step 1: Sumar a `smoke_barrera.py`** (corriendo el código del backend con `DB_BARRERA=true` in-process): `transaccion_despues_de_commit` — una sesión de `AsyncSessionLocal` con `fijar_municipio(db, 1)` ve reclamos; tras `commit()`, la consulta siguiente sigue viendo reclamos; una sesión sin `fijar_municipio` ve 0. `sesion_municipio_ve_lo_suyo`: `async with sesion_municipio(1)` ve reclamos solo del 1. `sistema_ve_todo`: `SesionSistema` ve filas de más de un municipio.
- [ ] **Step 2: Correr** — Expected: FAIL (no existen `fijar_municipio`, `sesion_municipio`, `sistema`).
- [ ] **Step 3: Implementar** las interfaces de arriba.
- [ ] **Step 4: `tools/barrido_sistema.py`**: falla (exit 1, lista archivo:línea) si `sistema` (`SesionSistema`, `get_db_sistema`, `_engine_sistema`) se importa desde un archivo que no está en su lista permitida, o si aparece `create_async_engine` fuera de `database.py`/`sistema.py`. La lista permitida arranca vacía y crece en la Task 3 con cada excepción, una línea por archivo con el motivo.
- [ ] **Step 5: Correr** `smoke_barrera.py` y el barrido — Expected: verde. Correr `smoke_cuentas_f6_1.py` con `DB_BARRERA=false` — Expected: 20/20 (nada cambió sin la barrera).
- [ ] **Step 6:** Commit (`feat(db): conexion con barrera, municipio por transaccion y modulo de sistema`).

---

### Task 3: Fijar el municipio en cada entrada y las cinco excepciones

**Files (los seguros; la corrida de la Task 4 puede sumar otros):**
- Modify: `backend/app/core/auth.py` (`get_current_user`, `get_current_ciudadano`)
- Modify: `backend/app/core/municipio.py` (`municipio_actual`, `municipio_de_origen`, `municipio_por_slug`, `municipio_de_slug_u_origen`, `por_cada_municipio`)
- Modify: `backend/app/core/sistema.py` (funciones de excepción)
- Modify: `backend/app/services/login_interno.py`, `backend/app/api/routes/auth.py` (recuperar/restablecer), `backend/app/api/routes/segundo_factor.py`, `backend/app/services/accesos_super.py`
- Modify: rutas con token público: `encuestas_publico.py`, `turnos_publico.py`, `agenda_publico.py`, `invitacion.py`, `publico_auth.py`, `publico_alta.py`
- Modify: `backend/app/api/routes/super_admin.py`, `auditoria_super.py` y el guardado de parámetros globales (dependency `get_db_sistema`); exportación y vaciado siguen con la barrera del municipio de la ruta (`fijar_municipio`)

**Interfaces:**
- Consumes: `fijar_municipio`, `get_db_sistema`, `SesionSistema` (Task 2).
- Produces en `app/core/sistema.py`:
  - `async def cuenta_super_por_identificador(identificador: str) -> Optional[int]` (id de la cuenta de nivel 0 sin municipio, o None).
  - `async def es_email_de_super(email: str) -> bool`.
  - `async def cuenta_super(id_usuario: int) -> Optional[Row]` (las columnas que hoy lee `get_current_user`).
  - `async def municipio_de_token(tipo: str, token: str) -> Optional[int]`, con un diccionario cerrado `tipo → (tabla, columna)` (encuesta, turno, reserva, evento, pantalla, invitación, activación y recuperación del vecino, verificación del alta, recuperación interna). Un `tipo` fuera del diccionario: `ValueError`.
- Reglas:
  - `get_current_user`: con `sa`, la cuenta sale de `cuenta_super`; si no, `fijar_municipio(db, payload["mun"])` **antes** de leer `usuarios` (un claim que no es entero: 401 como hoy).
  - `get_current_ciudadano`: `fijar_municipio(db, payload["mun"])` antes de leer.
  - `municipio_actual` (super con `X-Municipio`), `municipio_de_origen`, `municipio_por_slug`, `municipio_de_slug_u_origen`: `fijar_municipio` con el municipio resuelto.
  - `por_cada_municipio`: `fijar_municipio(db, id_m)` al empezar cada vuelta.
  - Rutas con token: `municipio_de_token` → 404 si None → `fijar_municipio` → sigue igual que hoy.
  - Login y recuperación: el municipio de origen se fija antes de buscar la cuenta del municipio; la del super va por `cuenta_super_por_identificador`; restablecer por token usa `municipio_de_token("recuperacion_interna", …)` y, si la cuenta es del super, `SesionSistema`.
  - Segundo factor: la cuenta del desafío se ubica con `sistema`; si es de un municipio, `fijar_municipio`; si es del super, el handler usa `SesionSistema`.
  - `registrar_acceso_super` (sesión propia) usa `SesionSistema`; `registrar_acceso_super_en(db, …)` con `id_municipio=None` solo se llama desde handlers que ya usan `get_db_sistema` (lo comprueba la corrida).
- [ ] **Step 1:** Correr con `DB_BARRERA=true` `smoke_aislamiento.py`, `smoke_super_admin.py`, `smoke_segundo_factor.py`, `smoke_cuentas_f6_1.py` — Expected: FAIL (anotar el conteo de cada uno en el registro: es la línea base RED).
- [ ] **Step 2:** Implementar las reglas de arriba, sumando cada archivo que importe `sistema` a la lista permitida del barrido con su motivo.
- [ ] **Step 3:** Correr los cuatro smokes con la barrera — Expected: verde. Correrlos con `DB_BARRERA=false` — Expected: verde (sin la barrera nada cambia).
- [ ] **Step 4:** `python tools/barrido_sistema.py` — Expected: verde, con la lista permitida limitada a las cinco excepciones del diseño (más los archivos que las implementan).
- [ ] **Step 5:** Commit (`feat(db): cada entrada fija su municipio; excepciones de sistema acotadas`).

---

### Task 4: Procesos de segundo plano y corrida completa con la barrera

**Files:**
- Modify: los 12 archivos que abren `AsyncSessionLocal()` fuera de una request (`push.py`, `notificaciones.py`, `email.py`, `avisos.py`, `autoasignacion.py`, `tramites/ciclo_vida.py`, `municipios/exportacion.py`, `municipios/vaciado.py`, `accesos_super.py`, `geo.py`, `demo_datos.py`): pasan a `sesion_municipio(id_municipio)`; las funciones encoladas reciben el municipio de quien las encola cuando hoy no lo reciben.
- Modify: `CLAUDE.md` (§10: toda tabla nueva recibe su política en la misma migración; §1 o §5: `fijar_municipio`/`sesion_municipio`, prohibido `AsyncSessionLocal()` directo y `sistema` fuera de la lista), `HISTORIAL_MIGRACIONES.md`, `ESTADO.md`
- Create: endpoint de prueba **solo local** (registrado únicamente si `_es_entorno_local()`), `GET /api/v1/_prueba/reclamos-sin-filtro`: `SELECT id_municipio, count(*) FROM reclamos GROUP BY 1` sin filtro de municipio, con `get_current_user` + `municipio_actual`.

- [ ] **Step 1: Test** `sin_filtro_igual_frena` en `smoke_barrera.py`: con la barrera, el admin del municipio 1 llama al endpoint de prueba y recibe un solo grupo, el del 1. Correr — Expected: FAIL (el endpoint no existe).
- [ ] **Step 2:** Crear el endpoint y correr — Expected: con `DB_BARRERA=true`, un solo grupo; con `false`, más de uno (el filtro que falta se nota).
- [ ] **Step 3:** Convertir los 12 archivos. Correr `smoke_reclamo_alta_mail.py`, `smoke_tramites_aviso_inicio.py`, `smoke_encuestas_circuitos.py`, `smoke_demo_poblar.py`, `smoke_alta_municipio.py` con la barrera — Expected: verde.
- [ ] **Step 4: Corrida completa** con `DB_BARRERA=true` de **todos** los `backend/smoke_*.py` in-process (lista con `ls`), salida a archivos del registro. Expected: los mismos resultados que con `DB_BARRERA=false` (correr las dos y comparar; un smoke que ya estaba rojo sin la barrera, como `smoke_publico_turnos.py` por el límite de reservas, se anota y no cuenta).
- [ ] **Step 5: Tiempos**: con uvicorn local, 20 requests de `GET /dashboard/resumen`, `GET /reclamos?limit=50` y `GET /tramites?limit=50` con y sin la barrera; anotar medianas. Expected: diferencia menor al 20 %.
- [ ] **Step 6: Navegando** con la barrera (shell local + bundle local + uvicorn con `DB_BARRERA=true`): inicio, Reclamos (buscar, abrir uno), Trámites (bandeja), Turnos (Buscar), Mi perfil; y el super cambiando de municipio en el selector.
- [ ] **Step 7:** Docs (CLAUDE.md, historial, ESTADO). Commit y push (`feat(db): segundo plano con municipio y corrida completa con la barrera`). Con `DB_BARRERA` en `false` por defecto y la migración solo en local, el push no cambia prod.

---

## Resultado (2026-11-20)

Hecho en local; prod sin cambios (`DB_BARRERA=false` por defecto, migración 138 solo en `zaris_dev`).

- **La prueba central:** el endpoint de prueba consulta reclamos sin filtro de municipio. Sin la barrera devuelve 30 municipios; con la barrera, solo el de la request.
- **Corrida completa:** los 23 smokes in-process y los 7 por HTTP dan el mismo resultado con y sin la barrera (las diferencias que aparecieron son de datos o de la ventana de 15 minutos del ciclo de vida, detalladas en el registro de la ejecución).
- **Navegando con la barrera:** inicio, Reclamos (búsqueda y detalle), Trámites, Turnos, Mi perfil y el super cambiando de municipio en el selector.

**Desvíos del diseño, decididos en la ejecución:**
- **El vaciado no va con la barrera** (diseño §4.4): deshabilita triggers y eso solo lo puede el dueño de las tablas. Sigue borrando solo filas del municipio y después de la exportación.
- **Las sesiones de segundo plano heredan el municipio de la request** por una variable de contexto, en vez de recibirlo como parámetro: menos cambios y el mismo efecto. Fuera de una request, sin `sesion_municipio`, no ven nada.
- El control de módulos habilitados fija el municipio de la request (corre antes que el handler).

**Pendiente para F6.3:** la barrera suma unos 9 ms a la bandeja de trámites en local (una consulta de 11 tablas pasa de 7 a 16 ms; el inicio y los reclamos casi no cambian). Medirlo en prod antes de prender `DB_BARRERA`.

**F6.3, corte en prod (2026-11-20):**
- **Usuario y variables:** César creó `zaris_app` en el SQL Editor y cargó la clave en Railway. Claude cargó `APP_DB_USER=zaris_app.<ref>`, que es el formato del pooler en modo sesión, el mismo que usa `DATABASE_URL`. La 138 la corrió César en el SQL Editor (el MCP la rechazó por los `DROP`).
- **Medición:** 7 endpoints con dos cuentas (supervisor y atención), primero con `DB_BARRERA=false` y después con `true`. Los conteos dan igual (715 trámites, 953 ciudadanos, 150 turnos de 7 días) y los tiempos también (bandeja de trámites: 228/222 ms sin la barrera, 218/176 ms con ella). En prod los 9 ms de local no se notan: el piso es la latencia de ~170 ms.
- **Recorrido con la barrera:**
  - Alta de dos reclamos por ventanilla: REC-SAN-2026-003478 (gestión que asigna a mano) y REC-SAN-2026-003479, que se asignó solo en segundo plano con la OT-SAN-2026-003659, aviso al agente y aviso al vecino.
  - App del vecino: login, sus reclamos y su resumen.
  - Sin token: identidad por origen y link de encuesta (el token inválido da 404).
  - Cron de encuestas disparado a mano: HTTP 200, con el resultado por municipio.
  - En `pg_stat_activity` el backend aparece como `zaris_app`, y los logs de Postgres no muestran ningún permiso denegado.
- **Vuelta atrás:** `DB_BARRERA=false` en Railway (redeploy de unos 30 s, sin código).
