# Plan de implementación — IT-01 F3 (super administrador)

> **Para quien lo ejecute (agente o persona):** sub-skill requerida: `superpowers:subagent-driven-development` (recomendada) o `superpowers:executing-plans`, tarea por tarea. Los pasos usan casillas (`- [ ]`) para seguir el avance.

**Objetivo:** que exista un super administrador (nivel 0, sin municipio) que opere cualquier municipio desde el mismo shell eligiéndolo en un selector, con cada acceso registrado y visible para el administrador de ese municipio, y que sea el único que edita lo global: municipios, parámetros globales, catálogo de módulos y Maestros globales.

**Arquitectura:** el super administrador entra por el login de siempre, que si no encuentra al usuario en el municipio busca entre las cuentas de nivel 0. Recibe un token propio (claim `sa`, sin `mun`). `get_current_user` lo presenta ante todo el código existente **como administrador (nivel efectivo 1)** con la marca `es_super_admin`, así que las 85 comparaciones de nivel del backend no se tocan. Solo dos lugares lo distinguen a propósito: la historia clínica, que le pide motivo, y lo exclusivo del super administrador. El municipio sale del header `X-Municipio`, leído **solo** dentro de `municipio_actual` y **solo** para `es_super_admin`. Ese mismo punto deja una fila en `super_admin_acceso` por cada request, antes de que corra el handler: sin registro no hay acceso.

**Stack:** FastAPI + SQLAlchemy async (asyncpg), PostgreSQL 17, python-jose; React 19 + Vite (módulos), shell vanilla (`index.html` + `frontend/js/menu.js`).

**Spec:** [`PLAN_MULTI_MUNICIPIO.md`](PLAN_MULTI_MUNICIPIO.md) §3 (super administrador y login) y §4. Base: F1+F2 en prod desde el 2026-10-25 ([`PLAN_MULTI_MUNICIPIO_F1_F2.md`](PLAN_MULTI_MUNICIPIO_F1_F2.md), reglas R1-R11, que siguen valiendo).

**Decisiones de César (2026-10-25):**
- **2FA en una fase aparte (F3b)**, antes del primer municipio real.
- **El primer super administrador es una cuenta nueva:** `cesar@municipio.gob.ar` sigue como administrador de San Andrés. César da el email en el corte (Tarea 10); no se escribe en ningún archivo del repo.
- **Los parámetros globales se editan en una pestaña de Configuración → Sistema**, no con una opción «Global» del selector: el selector siempre tiene un municipio elegido.

## Restricciones globales

- **Todo en local primero; prod una sola vez (Tarea 10).** Rama `it01-f3-super-admin` en un worktree; no se mergea a `main` antes de la Tarea 10. Base de pruebas `zaris_dev`, con la fixture B (`seed_municipio_aislamiento.py`) para el aislamiento.
- **La 127 lleva `DROP` y no va por MCP:** en prod la corre César en el SQL Editor de Supabase; en local se corre por psql o con el patrón `driver_connection` de `CLAUDE.md` §5. Lo demás va en la 127b, sin `DROP`, por `apply_migration`. Se renumeran si otra migración ocupa el número antes (§21).
- Toda tabla nueva lleva `ENABLE ROW LEVEL SECURITY` y su fila en `municipio_tabla_clase` (`CLAUDE.md` §10).
- **El header `X-Municipio` se lee en un solo lugar** (`municipio_actual`) y **solo** para `es_super_admin`; para cualquier otra cuenta se ignora. Ningún router lo lee.
- **La 125c no se vuelve a aplicar después de la 127** (le pondría NOT NULL a `usuarios.id_municipio` y fallaría con el super administrador cargado).
- Smokes solo contra `zaris_dev`, con el mail en MOCK (`settings.RESEND_API_KEY = ""`). Ninguna credencial ni el email real del super administrador en archivos versionados (`CLAUDE.md` §40).
- Antes de cada commit: `grep -riE "h[u]sky" .` vacío; `pnpm typecheck` si toca `web-app/`; bump del `?v=` de `menu.js`/`menu.css` si se tocan.
- Etiqueta visible del nivel 0: **«Super administrador»**.
- **Fuera de alcance:**
  - F3b: segundo factor.
  - F4: alta y baja de municipios, `municipios.estado`, `municipio_modulo`, invitación de administradores, municipio modelo y vaciado.
  - Crear más super administradores desde la interfaz (se crean con el script de la Tarea 1).
  - Usar la app de agentes o la del vecino con el super administrador (sin el header, sus requests a datos dan 400).

## Foco de revisión

Lo que el spec implica y es más probable que muerda, con la tarea que lo prueba:

1. **Un funcionario común que manda `X-Municipio` de otro municipio** tiene que seguir viendo solo el suyo: el header se ignora. Lo prueban la Tarea 3 (test directo) y la Tarea 9 (barrido con el header puesto en cada request).
2. **Un super administrador que deja de serlo** (pasa a nivel 1, se desactiva o se le asigna un municipio) pierde el acceso en la request siguiente: 401, aunque su token siga vigente (Tarea 3).
3. **Un administrador de municipio que intenta escalar** tiene que ser frenado en cada vía (Tarea 4):
   - crear o editar una cuenta con nivel 0 → 422;
   - darse por permiso individual el módulo `municipios` → 422;
   - editar al super administrador por su id → 404;
   - usar su email en una cuenta → 409;
   - cambiar el catálogo global de módulos o un Maestro global → 403.
4. **`X-Municipio` con basura** (vacío, `abc`, `-1`, `1,2`, diez dígitos, el municipio inactivo id 2) da 400 o 404, nunca 500, y no deja una fila de acceso con un municipio inexistente (Tarea 3).
5. **Cambiar de municipio con un formulario abierto** (o en otra pestaña) hace que el envío salga con el municipio nuevo y los ids del viejo. Tiene que dar 422 por R4 y no crear nada en ninguno de los dos (Tarea 9).

---

### Tarea 1: Base de datos y primera cuenta

**Archivos:**
- Crear: `backend/migrations/127_super_admin_restricciones.sql` (con `DROP`; en prod la corre César)
- Crear: `backend/migrations/127b_super_admin.sql` (sin `DROP`, por MCP)
- Crear: `backend/seed_super_admin.py`
- Modificar: `backend/smoke_segmentacion_f1.py` (`chk_id_municipio_completo`)
- Crear: `backend/smoke_super_admin.py` (lo amplían las Tareas 3 a 7)

**Interfaces:**
- Produce en la base:
  - `usuarios`: CHECK `nivel_acceso BETWEEN 0 AND 5`; `id_municipio` nullable; CHECK `ck_usuarios_municipio_nivel`: `(nivel_acceso = 0) = (id_municipio IS NULL)`; índices únicos parciales `uq_usuarios_super_email ON usuarios (lower(email)) WHERE id_municipio IS NULL` y `uq_usuarios_super_username ON usuarios (lower(username)) WHERE id_municipio IS NULL`.
  - `modulos`: CHECK `min_nivel_acceso BETWEEN 0 AND 5`; fila `('municipios', 'Municipios', …, min_nivel_acceso = 0, activo = TRUE)`.
  - Tabla `super_admin_acceso`, append-only:
    - columnas: `id_super_admin_acceso BIGSERIAL PK`, `id_usuario INTEGER NOT NULL → usuarios`, `id_municipio INTEGER NULL → municipios` (NULL = acción global), `accion VARCHAR(30) NOT NULL`, `metodo VARCHAR(10)`, `ruta VARCHAR(300)`, `detalle TEXT`, `ip VARCHAR(64)`, `user_agent VARCHAR(1000)`, `fecha_hora TIMESTAMPTZ NOT NULL DEFAULT NOW()`;
    - CHECK de `accion` en (`login`, `seleccion`, `request`, `historia_clinica`, `config_global`, `municipio_editar`, `catalogo_global`);
    - índice `(id_municipio, fecha_hora DESC)`;
    - triggers que rechazan UPDATE y DELETE, como los de `historia_clinica_acceso`;
    - RLS habilitado;
    - clasificada `mixta` con nota «NULL = acción global; append-only; no se vacía (F4)»;
    - sin los campos estándar de §10: es un registro, como `historia_clinica_acceso` y `usuario_login_log`.
  - `configuracion_general`: `password_renovacion_dias` pasa a global (`id_municipio = NULL`), solo si no existe ya una fila global de esa clave.
- `seed_super_admin.py --email E --nombre N [--username U] [--password-dev P] [--imprimir-sql]`:
  - Crea una fila de `usuarios` con `nivel_acceso = 0`, `id_municipio = NULL`, `activo = TRUE`, `buc_acceso` y las demás columnas NOT NULL sin default (verificarlas con `information_schema` en la base destino, §24), y `debe_cambiar_password = TRUE`.
  - Sin `--password-dev`, `password_hash` es el bcrypt de 32 bytes aleatorios que se descartan: la clave se elige con «Olvidé mi contraseña».
  - `--password-dev` solo se acepta si `current_database() = 'zaris_dev'`.
  - Aborta con 409 si el email ya lo usa cualquier cuenta de `usuarios`.
  - `--imprimir-sql` no conecta: imprime el `INSERT … WHERE NOT EXISTS` para correrlo por `execute_sql` en prod.
  - Idempotente.

- [ ] **Paso 1: Tests en `smoke_super_admin.py`** (guarda `zaris_dev`; in-process con `httpx.ASGITransport`, como `smoke_municipio_request.py`):
  - `test_constraints_nivel_0`: un `INSERT` de nivel 0 con `id_municipio = 1` falla por `ck_usuarios_municipio_nivel`; uno de nivel 1 con `id_municipio NULL` falla igual; un `UPDATE super_admin_acceso` y un `DELETE` lanzan la excepción append-only.
  - `test_seed_super_admin`: `seed_super_admin.py --email super.admin@prueba-aislamiento.com.ar --nombre "Super Prueba" --password-dev 123456` deja una fila nivel 0 sin municipio; correrlo de nuevo no crea otra; con el email de una cuenta del municipio 1 sale con error.
  - `test_password_renovacion_global`: `leer_config(db, "password_renovacion_dias", 1)` devuelve el valor global y no hay fila de esa clave con `id_municipio = 1`.
- [ ] **Paso 2:** correrlos. Esperado: FALLAN.
- [ ] **Paso 3: Escribir la 127 y la 127b.** En la 127, verificar antes los nombres reales de los CHECK en local (`pg_constraint`); en prod son `usuarios_nivel_acceso_check` y `modulos_min_nivel_acceso_check`. La 127 relaja restricciones y es compatible con el código viejo. Va en `BEGIN … COMMIT` para el SQL Editor.
- [ ] **Paso 4: Aplicarlas en local** (127 por psql, 127b igual) y escribir `seed_super_admin.py`.
- [ ] **Paso 5: `smoke_segmentacion_f1.py`:** `chk_id_municipio_completo` acepta `usuarios` nullable si existe `ck_usuarios_municipio_nivel` y las filas con `id_municipio NULL` son exactamente las de nivel 0. Correr el smoke: en verde.
- [ ] **Paso 6:** tests de la tarea en verde, y `smoke_aislamiento.py` en 0 fallas (con el super administrador cargado no cambia nada).
- [ ] **Paso 7: Commit** `feat(it-01-f3): base del super administrador (migs 127 y 127b) y script de alta`.

### Tarea 2: Registro de accesos

**Archivos:**
- Crear: `backend/app/services/accesos_super.py`
- Test: `backend/smoke_super_admin.py`

**Interfaces:**
- `ACCIONES: tuple[str, ...]`: las siete del CHECK de la Tarea 1.
- `async def registrar_acceso_super(*, id_usuario: int, accion: str, id_municipio: int | None, metodo: str | None = None, ruta: str | None = None, detalle: str | None = None, ip: str | None = None, user_agent: str | None = None) -> None`:
  - Abre su propia sesión (`AsyncSessionLocal`) y hace commit. Así la fila queda aunque el handler falle o sea un GET que no commitea.
  - Si el INSERT falla, `HTTPException(503, "No se pudo registrar el acceso")`: sin registro no hay acceso.
  - `ruta` y `user_agent` se truncan al largo de su columna.

- [ ] **Paso 1: Tests:**
  - `test_registrar_acceso_super`: una llamada con `accion='seleccion'` deja una fila con esos datos y se ve desde otra sesión.
  - `test_registro_falla_cierra`: con `accion='inexistente'` (viola el CHECK) lanza 503 y no deja fila.
- [ ] **Paso 2:** fallan; **Paso 3:** implementar; **Paso 4:** pasan.
- [ ] **Paso 5: Commit** `feat(it-01-f3): registro de accesos del super administrador`.

### Tarea 3: Núcleo — login, token, nivel efectivo y municipio por header

**Archivos:**
- Modificar: `backend/app/core/auth.py` (`crear_token_super_admin`, `get_current_user`, `require_super_admin`, `require_modulo`)
- Modificar: `backend/app/core/municipio.py` (`municipio_actual`, cache `_municipios` con `ids_activos`)
- Modificar: `backend/app/api/routes/auth.py` (`_buscar_super_admin`, `login`, `me`, `recuperar_password`)
- Test: `backend/smoke_super_admin.py`

**Interfaces:**
- Consume: `registrar_acceso_super` (Tarea 2); la cuenta local de la Tarea 1.
- Produce:
  - `def crear_token_super_admin(id_usuario: int) -> str`: claims `sub`, `scope="agente"`, `sa=True`, sin `mun`, con la misma vigencia que el agente (24 h).
  - `get_current_user`:
    - Con `sa=True`: exige en la base `nivel_acceso = 0` e `id_municipio IS NULL` (si no, 401 `SESION_VENCIDA`) y no compara el `Origin`.
    - Una fila de nivel 0 con un token sin `sa`: 401.
    - El dict devuelto agrega `es_super_admin: bool` y `nivel_real: int`. Para el super administrador, `nivel_acceso` vale **1** (nivel efectivo) e `id_municipio` vale `None`.
  - `async def require_super_admin(current_user: dict = Depends(get_current_user)) -> dict`: 403 `"Requiere super administrador"`.
  - `require_modulo` y `/auth/me` llaman a `modulos_permitidos` con `nivel_real` (el super administrador recibe además `municipios`).
  - `HEADER_MUNICIPIO = "X-Municipio"`.
  - `async def municipio_actual(request: Request, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> int`:
    - Sin `es_super_admin`: devuelve `current_user["id_municipio"]`, como hoy, y **no lee el header**.
    - Con `es_super_admin`:
      - Sin header: 400 `"Elegí un municipio en el selector"`.
      - Un valor que no matchea `^[0-9]{1,9}$`: 400 `"Municipio inválido"`.
      - Un id que no está en `ids_activos`: 404 `"Municipio no encontrado"`.
      - Si es válido: `registrar_acceso_super(accion="request", id_municipio=…, metodo, ruta=request.url.path, ip=get_real_ip(request), user_agent=…)` y devuelve el id.
  - Login:
    - Si `_buscar_usuario_login` no encuentra la cuenta y el identificador tiene `@`, `_buscar_super_admin(db, email)` busca por email exacto con `id_municipio IS NULL AND nivel_acceso = 0` (en cualquier `Origin`).
    - Para el super administrador no se escribe `usuario_login_log`: se registra `accion="login"` con `id_municipio=None` y `detalle` = el municipio de origen.
    - La renovación de clave se lee como global.
    - El token sale de `crear_token_super_admin`.
    - `user` lleva `nivel_acceso: 0`, `id_municipio: None` y `es_super_admin: True`; las demás cuentas, `es_super_admin: False`.
  - `/auth/me` devuelve `nivel_acceso = nivel_real` y `es_super_admin`.
  - `recuperar_password`: la misma búsqueda de respaldo por email; el mail usa la identidad del municipio de origen. `resetear-password` ya va por token y no cambia.
  - **Lecturas del nivel desde la base**, fuera de `current_user` (relevadas el 2026-10-25):
    - Las consultas de destinatarios de `notificaciones.py` y `autoasignacion.py` (`u.nivel_acceso = 1 AND u.id_municipio = :mun`) dejan afuera al super administrador, y está bien: no es administrador de ningún municipio.
    - `services/tramites/auth.py::resolver_agente_desde_usuario` exige un agente, y el super administrador no tiene. Operar un trámite sigue exigiendo agente, como para un administrador sin ficha. La bandeja y el detalle se tienen que ver: lo verifica el recorrido de la Tarea 9.

- [ ] **Paso 1: Tests** (con la fixture B y la cuenta de la Tarea 1):
  - `test_login_super`:
    - login con el email del super administrador sin `Origin` y con `Origin: https://aislamiento.zge.zaris.com.ar` → 200 las dos veces;
    - el token tiene `sa = True` y no tiene `mun`; `user.nivel_acceso == 0` y `user.es_super_admin is True`;
    - queda una fila `accion='login'` y ninguna fila nueva en `usuario_login_log`.
  - `test_header_super`:
    - con `X-Municipio: <B>`, `GET /api/v1/reclamos/<id de B>` → 200 y contiene `AISLAB`;
    - con `X-Municipio: 1`, el mismo GET → 404;
    - cada request deja una fila `accion='request'` con su municipio.
  - `test_header_invalido`: con `X-Municipio` ausente o `""` → 400 `"Elegí un municipio en el selector"`; con `"abc"`, `"-1"`, `"1,2"`, `"1234567890"` → 400; con `"2"` (inactivo) o `"999999"` → 404. Ninguno es 500 y ninguno deja una fila `request`.
  - `test_header_ignorado_para_comunes`: `admin.b` con `X-Municipio: 1` lee sus propios datos (200, `AISLAB`) y el reclamo del municipio 1 da 404; `admin` del municipio 1 con `X-Municipio: <B>` → el reclamo de B da 404.
  - `test_super_degradado`: con el token del super vigente, `UPDATE usuarios SET nivel_acceso = 1, id_municipio = 1` → la siguiente request da 401 `"Sesión vencida. Volvé a ingresar."`; con `activo = FALSE` → 401. Al final, restaurar la cuenta.
  - `test_nivel_efectivo`:
    - el super administrador pasa los guards de nivel 1: `PUT /api/v1/config/identidad` con `X-Municipio: <B>` → 409 (B no tiene claves propias, decisión de F2), no 403;
    - `/auth/me` → `nivel_acceso == 0`, `es_super_admin is True` y `municipios` en `modulos_permitidos`;
    - un admin de nivel 1 no tiene `municipios`.
  - `test_recuperar_super`: `POST /auth/recuperar-password` con el email del super administrador → 200 y, en MOCK, un mail con link de reseteo; `POST /auth/resetear-password` con ese token → 200; el login con la clave nueva entra.
- [ ] **Paso 2:** correrlos. Esperado: FALLAN.
- [ ] **Paso 3: Implementar** las Interfaces.
- [ ] **Paso 4:** los tests en verde, más `smoke_municipio_request.py`, `smoke_cuentas_funcionario.py` y `smoke_aislamiento.py` en verde o en 0 fallas.
- [ ] **Paso 5: Commit** `feat(it-01-f3): login, token y municipio por header del super administrador`.

### Tarea 4: Lo que solo hace el super administrador, y cierre de escaladas

**Archivos:**
- Modificar: `backend/app/api/routes/admin_tablas.py` (`_exigir_admin_base` → `_exigir_super_admin`; `municipios` solo lectura)
- Modificar: `backend/app/api/routes/admin_permisos.py` (`PUT /modulos/{codigo}`, `PUT /usuarios/{id_usuario}/modulos`)
- Crear: `backend/app/services/super_admin.py` (`email_reservado_super_admin`)
- Modificar: `backend/app/api/routes/buc.py` (alta y edición de usuarios) y `backend/app/services/cuenta_zaris.py`
- Test: `backend/smoke_super_admin.py`

**Interfaces:**
- `async def email_reservado_super_admin(db: AsyncSession, email: str | None) -> bool`: True si `lower(email)` es el de una cuenta con `id_municipio IS NULL`.
- Maestros globales (`_TABLAS_GLOBALES`):
  - las mutaciones exigen `es_super_admin`, si no 403 `"Acción exclusiva del super administrador"`;
  - la lectura de `municipios` pasa a ser solo del super administrador;
  - las mutaciones de `municipios` dan 403 `"Los municipios se editan desde el módulo Municipios"`, para que haya una sola vía de edición;
  - cada mutación global del super administrador registra `accion="catalogo_global"`.
- `PUT /admin/permisos/modulos/{codigo}`: `require_super_admin` + `accion="catalogo_global"`.
- `PUT /admin/permisos/usuarios/{id}/modulos`: un override `permitido = TRUE` de un módulo con `min_nivel_acceso = 0` → 422 `"Ese módulo es exclusivo del super administrador"`.
- Alta o edición de usuario (`buc.py`) y cuenta ZARIS desde la ficha (`cuenta_zaris.py`): un email reservado → 409 `"Ese email está reservado"`. El nivel 0 ya lo rechazan los schemas (`ge=1`): se agrega un test, no código.

- [ ] **Paso 1: Tests:**
  - `test_escaladas_admin` (como `admin` del municipio 1):
    - crear un usuario con `nivel_acceso: 0` → 422;
    - editar uno a `nivel_acceso: 0` → 422;
    - override de `municipios` → 422;
    - `GET`/`PUT` de `/buc/usuarios/<id del super>` → 404;
    - alta de usuario con el email del super administrador → 409;
    - `PUT /admin/permisos/modulos/reclamos` → 403;
    - `PUT` de una fila de `estado_reclamo` en Maestros → 403;
    - `GET /admin/municipios` → 403.
  - `test_global_super`: el super administrador, con `X-Municipio: 1`, edita `modulos/reclamos` (y lo restaura) y una fila de `nacionalidades` → 200, con filas `catalogo_global`; un `PUT` a `municipios` por Maestros → 403 con el texto de arriba.
- [ ] **Paso 2:** fallan; **Paso 3:** implementar; **Paso 4:** pasan, junto con `smoke_cuentas_funcionario.py` y `smoke_aislamiento.py --rutas /api/v1/admin`.
- [ ] **Paso 5: Commit** `feat(it-01-f3): edicion global solo del super administrador y cierre de escaladas`.

### Tarea 5: Endpoints del super administrador y registro para el administrador del municipio

**Archivos:**
- Crear: `backend/app/api/routes/super_admin.py` (prefijo `/api/v1/super`, todas con `require_super_admin`)
- Crear: `backend/app/api/routes/auditoria_super.py` (prefijo `/api/v1/auditoria`)
- Modificar: `backend/app/main.py` (registrar los dos routers; ninguno colisiona con el `/{tabla}` de `admin_tablas`)
- Test: `backend/smoke_super_admin.py`

**Interfaces:**
- `GET /api/v1/super/municipios` → `list[MunicipioSuperOut]`, con `id_municipio`, `nombre`, `codigo_corto`, `subdominio`, `codigo_pais`, `pais`, `zona_horaria`, `direccion_base` y `activo`. Trae todos, también los inactivos.
- `PUT /api/v1/super/municipios/{id_municipio}`, con body `MunicipioSuperUpdate`:
  - campos editables: `nombre` (3-150), `subdominio` (`^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$` o null), `codigo_pais` (`^[A-Z]{2}$`), `pais` y `zona_horaria` (válida si `zoneinfo.ZoneInfo(valor)` no falla; si no, 422);
  - un subdominio repetido → 409;
  - después de guardar: `invalidar_cache_municipios()` y `accion="municipio_editar"` con el antes y el después en `detalle`;
  - **no se editan** `codigo_corto` (es el prefijo de los números), `direccion_base` ni `activo` (los da F4).
- `POST /api/v1/super/seleccion` con body `{id_municipio: int}`:
  - un id inactivo o inexistente → 404;
  - si es válido, registra `accion="seleccion"` y devuelve `{id_municipio, nombre, logo_url}`: `nombre` es `leer_config("municipio_nombre")` o, si no hay, `municipios.nombre`; `logo_url` es `leer_config("municipio_logo_url")`.
- `GET /api/v1/super/config-global` → las filas `id_municipio IS NULL AND clave NOT LIKE 'vapid\_%'`, con `id_config`, `clave`, `valor`, `tipo` y `descripcion`.
- `PUT /api/v1/super/config-global/{id_config}` con body `{valor: str}`:
  - solo sobre esas filas (otra fila → 404);
  - valida por `tipo` con la misma regla que Maestros → `configuracion_general`;
  - registra `accion="config_global"` con `"clave: viejo → nuevo"`.
- `GET /api/v1/auditoria/accesos-super`:
  - guard `require_admin` (nivel efectivo 1) + `municipio_actual`;
  - params `desde`, `hasta` (date), `accion`, `orden` ∈ {`fecha`, `accion`, `usuario`}, `dir`, `limit` ≤ 200 y `offset`, con el orden por `clausula_orden` y desempate por la PK;
  - filas del municipio con el nombre del usuario;
  - headers `X-Total-Count` y `Access-Control-Expose-Headers`.

- [ ] **Paso 1: Tests:**
  - `test_super_municipios`:
    - el listado trae 1, 2 y B;
    - editar el `nombre` de B → 200, con `municipio_editar`;
    - zona `"Marte/Olympus"` → 422;
    - el subdominio de B puesto en el municipio 1 → 409;
    - `admin` del municipio 1 → 403 en todas las rutas de `/super`.
  - `test_seleccion`: B → 200 con su nombre y la fila `seleccion`; el id 2 → 404.
  - `test_config_global`:
    - el listado tiene `password_renovacion_dias` y ninguna `vapid_*`;
    - editarla → 200 y `leer_config(…, 1)` ve el valor nuevo;
    - el `id_config` de una fila del municipio 1 → 404.
  - `test_auditoria_accesos_super`: tras las requests del super administrador con `X-Municipio: <B>`, `admin.b` ve esas filas y ninguna del municipio 1; `admin` del municipio 1 no ve las de B; `orden=fecha&dir=asc` funciona y `orden=basura` → 422.
- [ ] **Paso 2:** fallan; **Paso 3:** implementar; **Paso 4:** pasan. Además, `GET /api/v1/admin/<tabla>/<id existente>` sigue andando (el greedy de `admin_tablas` intacto, §5).
- [ ] **Paso 5: Commit** `feat(it-01-f3): endpoints del super administrador y registro visible para el municipio`.

### Tarea 6: Historia clínica con motivo declarado

**Archivos:**
- Modificar: `backend/app/services/historia_clinica.py` (`permiso_historia_clinica`)
- Modificar: `backend/app/api/routes/turnos.py` (`historial_atenciones`, `permiso_historia`, `historia_clinica`)
- Modificar: `web-app/src/modules/turnos/components/HistoriaClinica.tsx`, `HistorialAtenciones.tsx`, `api/turnosApi.ts`, `hooks/useTurnos.ts`
- Test: `backend/smoke_super_admin.py`; `backend/smoke_atenciones_historia.py` sin cambios, en verde

**Interfaces:**
- `permiso_historia_clinica(db, user, *, id_municipio: int, motivo_declarado: str | None = None)`, con `es_super_admin`:
  - con `motivo_declarado.strip()` de 10 caracteres o más → `{"puede": True, "motivo": "super_admin"}`;
  - si no → `{"puede": False, "motivo": "requiere_motivo"}`.
  - No hereda el `"admin"` del nivel 1. Para las demás cuentas no cambia nada.
- `historial_atenciones` e `historia_clinica` suman `motivo: Optional[str] = Query(None, max_length=500)` y se lo pasan al permiso. Con el super administrador:
  - `historia_clinica_acceso.motivo` lleva `'super_admin'` (la columna es `VARCHAR(20)`);
  - además, `registrar_acceso_super(accion="historia_clinica", detalle=f"ciudadano {id}: {motivo}")`, dentro del mismo request;
  - los intentos denegados quedan como `denegado`, igual que hoy.
- Frontend: si el permiso responde `requiere_motivo`, el componente muestra un campo «Motivo de la consulta», con el aviso «Queda registrado y lo ve el administrador del municipio», y un botón «Ver historia». La consulta sale con `motivo`.

- [ ] **Paso 1: Tests:**
  - `test_hc_super`, con `X-Municipio: 1`:
    - sin motivo, el permiso es `requiere_motivo` y la historia da 403 con una fila `denegado`;
    - con `motivo="  corto  "` → 403;
    - con un motivo de 10 caracteres o más → 200, una fila `ok` con `motivo='super_admin'` y una fila `historia_clinica` con el texto.
  - `admin` de nivel 1 sin motivo sigue entrando como hoy.
- [ ] **Paso 2:** fallan; **Paso 3:** implementar backend y frontend; **Paso 4:** pasan, junto con `smoke_atenciones_historia.py` y `pnpm typecheck`.
- [ ] **Paso 5: Commit** `feat(it-01-f3): historia clinica del super administrador con motivo`.

### Tarea 7: Shell — selector de municipio y header en todas las requests

**Archivos:**
- Modificar: `index.html` (topbar: `<select id="topbar-municipio">`, con la etiqueta «Operando en», oculto salvo para el super administrador)
- Modificar: `frontend/js/menu.js` (`NIVELES[0]`, `_authHeaders`, carga del selector, cambio de municipio)
- Modificar: `frontend/css/menu.css` (estilo del selector con tokens del DS, también en oscuro)
- Modificar: `frontend/admin_tablas.html` (`_authHeaders`)
- Crear: `web-app/src/lib/municipioActivo.ts`
- Modificar: `web-app/src/lib/api.ts`, `web-app/src/lib/types.ts`, `web-app/src/shell/TopBar/TopBar.tsx` (réplica del selector para el shell de desarrollo, §4) y los mapas de etiquetas de nivel (`TopBar.tsx`, `perfil/pages/PerfilPage.tsx`, `ciudadanos/components/CuentasChips.tsx`, `usuarios/views/MaestroView.tsx`)

**Interfaces:**
- Clave de `localStorage`: **`zaris_municipio_activo`** (id numérico como texto). La comparten el shell y el iframe porque son del mismo origen.
- `municipioActivo.ts`: `getMunicipioActivo(): number | null` y `headerMunicipio(): Record<string, string>`. Este último devuelve `{ 'X-Municipio': id }` solo si la sesión es de un super administrador y hay municipio elegido.
- `api.ts` suma `headerMunicipio()` a cada request. Los `fetch` directos de `web-app` (subidas a URLs firmadas, `auth/me`, `cambiar-password`, `health`, autoservicio) no lo necesitan.
- `types.ts`: `nivel_acceso: 0 | 1 | 2 | 3 | 4 | 5` y `es_super_admin?: boolean`.
- Comportamiento del shell:
  1. **Al arrancar (super administrador):** `GET /super/municipios` → opciones (solo activos). Si no hay municipio guardado o ya no está activo, elige el de `direccion_base`. Después hace `POST /super/seleccion`, guarda el id y muestra en el topbar el nombre y el logo que devuelve.
  2. **Al cambiar el selector:** `POST /super/seleccion`, guarda el id, actualiza el topbar y recarga el iframe en el inicio.
  3. **El selector siempre muestra el municipio activo.** Para cualquier otra cuenta el selector no existe, y el header nunca sale aunque haya algo en la clave.
  4. **El selector de desarrollo de `TopBar.tsx` hace lo mismo con React.**

- [ ] **Paso 1: Navegador en local** (shell `localhost:8080` + API local, `CLAUDE.md` §41). Entrar con el super administrador y comprobar:
  - el selector aparece con el municipio 1;
  - Reclamos lista los del municipio 1;
  - al cambiar a B se recarga el inicio, el topbar dice el nombre de B y Reclamos lista los de B (`AISLAB`);
  - Maestros (`admin_tablas.html`) muestra los de B;
  - con `administrativo@` (o el `admin` local) no hay selector, y poner `zaris_municipio_activo` a mano no cambia nada.
- [ ] **Paso 2: Implementar.**
- [ ] **Paso 3:** repetir el recorrido del Paso 1 con clics, ida y vuelta (no por URL directa, §41), y confirmar con la red del navegador que cada request del super administrador lleva `X-Municipio` y que las de la otra cuenta no.
- [ ] **Paso 4:** `pnpm typecheck` y bump de `?v=`.
- [ ] **Paso 5: Commit** `feat(it-01-f3): selector de municipio del super administrador en el shell`.

### Tarea 8: Pantallas nuevas — Municipios, parámetros globales y registro del super administrador

**Archivos:**
- Crear: `web-app/src/modules/municipios/` (manifest con `moduloCodigo: 'municipios'`; listado y edición). Seguir la skill `nuevo-modulo-react`.
- Modificar: `index.html` (ítem del sidebar `data-modulo="municipios"`, ícono Lucide `landmark` inline)
- Modificar: `web-app/src/modules/config/views/SistemaView.tsx` (pestaña «Parámetros globales», solo con `es_super_admin`) y `web-app/src/modules/config/api/configApi.ts`
- Crear: `web-app/src/modules/usuarios/views/AccesosSuperView.tsx`; modificar `web-app/src/modules/usuarios/index.tsx` (ruta `accesos-super`, «Registro del super administrador», visible para el nivel 1)

**Interfaces:**
- Consume los endpoints de la Tarea 5.
- **Municipios:** tabla con `ThOrden` y `ordenarFilas` (el endpoint trae todo, §23), con nombre, código, subdominio, país, zona horaria y estado. Al hacer clic se abre la edición de los campos editables de la Tarea 5. `codigo_corto` aparece como solo lectura, con la ayuda «Es el prefijo de los números; se fija en el alta». La pantalla no tiene búsqueda diferida: es un catálogo sin filtros (§23).
- **Parámetros globales:** misma tabla y edición que Sistema, sobre `/super/config-global`.
- **Registro del super administrador:**
  - filtros fecha desde y hasta, y acción, con búsqueda diferida (`useBusquedaDiferida`, §23);
  - orden por columnas en el backend;
  - aviso de tope si hay más filas que las mostradas;
  - columnas: fecha y hora, usuario, acción, método, ruta y detalle.

- [ ] **Paso 1: Navegador en local:**
  - el super administrador ve «Municipios» en el sidebar, edita el nombre de B y lo ve en el selector;
  - edita `password_renovacion_dias` en «Parámetros globales»;
  - `admin.b` entra a Usuarios → «Registro del super administrador», aprieta Buscar y ve las filas de la Tarea 7 en B, ordena por acción y no ve «Municipios»;
  - un administrador común no ve la pestaña «Parámetros globales».
- [ ] **Paso 2: Implementar.**
- [ ] **Paso 3:** repetir el Paso 1 con clics y `pnpm typecheck`.
- [ ] **Paso 4: Commit** `feat(it-01-f3): modulo Municipios, parametros globales y registro del super administrador`.

### Tarea 9: Cierre de F3 — barridos, recorrido y documentación

**Archivos:**
- Modificar: `backend/smoke_aislamiento.py` (opciones `--header-ajeno` y `--como-super`)
- Modificar:
  - `CLAUDE.md`: §1 (token del super administrador y login), §3 (nivel 0), §14 (selector del topbar) y §21 (migs 127 y 127b);
  - `HISTORIAL_MIGRACIONES.md`;
  - las skills `modulo-usuarios`, `modulo-permisos`, `modulo-config`, `modulo-admin-tablas` y `modulo-turnos-entradas`.

**Interfaces:**
- `smoke_aislamiento.py --header-ajeno`: el barrido de siempre, con `X-Municipio: <B>` en **cada** request del admin del municipio 1. Esperado: el mismo resultado, 0 fallas.
- `smoke_aislamiento.py --como-super`: el barrido de GET con el token del super administrador y `X-Municipio: 1`. Ninguna respuesta contiene `AISLAB`. El control positivo con `X-Municipio: <B>` sí lo contiene.

- [ ] **Paso 1: Test del Foco 5:** en `smoke_super_admin.py`, `test_cambio_de_municipio_con_form_abierto`: el super administrador, con `X-Municipio: <B>`, crea un reclamo con el `id_tipo_reclamo` y el `id_ciudadano` del municipio 1 → 422, y la cantidad de reclamos de 1 y de B no cambia.
- [ ] **Paso 2:** `smoke_aislamiento.py`, `--header-ajeno` y `--como-super` → 0 fallas; `smoke_super_admin.py` completo y la suite de la Tarea 19 de F1+F2 en verde.
- [ ] **Paso 3: Barridos estáticos:**
  - `grep -rn "X-Municipio\|x-municipio" backend/app` solo en `core/municipio.py`;
  - `grep -rn "nivel_real\|es_super_admin" backend/app` solo en `core/auth.py`, `core/municipio.py`, `routes/auth.py`, `routes/super_admin.py`, `routes/admin_tablas.py`, `routes/admin_permisos.py`, `routes/turnos.py` y `services/historia_clinica.py`. Cualquier otro uso es una exclusividad nueva que no está en el plan: se justifica o se saca.
- [ ] **Paso 4: Prueba de cierre del spec, en el navegador local:** cambiar de municipio y ver los datos correctos en Reclamos, Turnos, Trámites (bandeja y detalle), Emergencias, Datos y Maestros, y ver el registro poblado desde la pantalla del administrador de cada municipio.
- [ ] **Paso 5: Documentación** (archivos de arriba). En `CLAUDE.md` §3, la regla: el nivel 0 se ve como nivel 1 ante los guards, y solo `es_super_admin` lo distingue.
- [ ] **Paso 6: Revisión final** de toda la rama por un revisor fresco (agente aparte), con foco en el Foco de revisión.
- [ ] **Paso 7: Commit** `feat(it-01-f3): cierre de F3 - barridos, recorrido y documentacion`.

### Tarea 10: Corte en prod (con César)

No invalida sesiones: los tokens de los funcionarios y de los vecinos no cambian, así que no hace falta ventana con re-login ni pausar los procesos programados.

- [ ] **Paso 1: Preparación.**
  - `git fetch` y rebase de la rama sobre `main`.
  - Confirmar en prod que 127 y 127b están libres.
  - Verificar los nombres de los CHECK de `usuarios` y `modulos` (`pg_constraint`) y las columnas NOT NULL de `usuarios` (§24).
  - `/backup-prod`, verificando el archivo.
- [ ] **Paso 2: César corre la 127** en el SQL Editor. Verificación por `execute_sql`: las dos CHECK nuevas, `usuarios.id_municipio` nullable y `ck_usuarios_municipio_nivel`.
- [ ] **Paso 3: 127b** por `apply_migration`. Verificación: la tabla con sus triggers y RLS, la fila en `municipio_tabla_clase`, la fila `municipios` en `modulos` y `password_renovacion_dias` global. El código viejo sigue andando: un login de `administrativo@` da 200.
- [ ] **Paso 4: Código.** Merge `--no-ff` a `main` y push. Esperar en `/openapi.json` el path exacto `/api/v1/super/municipios`, no la palabra. Después, `git pull` del commit de dist de CI.
- [ ] **Paso 5: Primera cuenta.** César da el email. `seed_super_admin.py --imprimir-sql --email <email> --nombre <nombre>` y el `INSERT` por `execute_sql`; verificar la fila.
- [ ] **Paso 6: César elige la clave** desde `zge.zaris.com.ar` con «Olvidé mi contraseña». Verificar que el link del mail abre la página de reseteo (§5, links de mail).
- [ ] **Paso 7: Verificación en prod.**
  - César entra como super administrador; el selector muestra San Andrés y Reclamos lista lo mismo que con `cesar@`.
  - En la base, filas `login`, `seleccion` y `request` del municipio 1.
  - Con `cesar@`, Usuarios → «Registro del super administrador» muestra esas filas.
  - Un token común sigue andando y `administrativo@` no tiene selector.
- [ ] **Paso 8: Registro.** `HISTORIAL_MIGRACIONES.md` (127 por César en el SQL Editor, 127b por MCP, fecha), `ESTADO.md` y la memoria `project_it01_multi_municipio`. Commit y push.

---

## Lo que queda para fases posteriores

- **F3b:** segundo factor del nivel 0, antes del primer municipio real.
- **F4:** alta y baja de municipios (`estado`, `codigo_corto` en el alta), `municipio_modulo` (el nivel mínimo por municipio vuelve a ser del administrador), invitación del primer administrador, alta de más super administradores desde la interfaz, municipio modelo y vaciado. Las claves globales que siembran un municipio nuevo se cargan en «Parámetros globales».
- **F5:** subdominios reales. El selector del super administrador ya funciona desde cualquier dirección.
- **F6:** RLS. Las políticas de `usuarios` y de `super_admin_acceso` tienen que contemplar las filas con `id_municipio NULL`.

## Criterios de Claude en este plan (para que César los revise)

- **Nivel efectivo 1 en un solo punto** en lugar de revisar las 85 comparaciones de nivel. Las que quedan atadas al nivel real son las tres exclusividades del super administrador: la historia clínica, la edición global y los módulos exclusivos.
- **Registro por request** desde `municipio_actual`, con su propia transacción, y acceso negado si el registro falla. Las acciones globales (login, parámetros globales, catálogo de módulos, edición de municipios) quedan con `id_municipio NULL` y no las ve ningún municipio.
- **Al entrar, el selector arranca en el municipio de la dirección** (`direccion_base`), en lugar de obligar a elegir. Siempre queda visible.
- **`codigo_corto`, `direccion_base` y `activo` no se editan en F3**: cambiarlos cambia los números nuevos, la dirección sin prefijo o los procesos, y eso es del alta y la baja de F4.
- **Maestros → Municipios queda en solo lectura**, para que haya una sola vía de edición.
- **El registro del super administrador para el administrador del municipio va en Usuarios**, junto al historial de accesos de las cuentas.
