# IT-01 F3b — Segundo factor: plan de implementación

> **Para agentes:** SUB-SKILL REQUERIDA: usar superpowers:subagent-driven-development (recomendada) o superpowers:executing-plans para ejecutar este plan tarea por tarea. Los pasos usan casillas (`- [ ]`) para el seguimiento.

**Objetivo:** que las cuentas de nivel 0 y 1 entren con la clave más un código de 6 dígitos de una app de autenticación, sin ningún camino que entregue su token sin ese código.

**Arquitectura:**
- El login deja de emitir el token para las cuentas de nivel 0/1. En su lugar entrega un **desafío** de 5 minutos.
- Endpoints nuevos (`/api/v1/auth/segundo-factor/*`) verifican el código o vinculan la app, y recién ahí emiten el token, con el claim `sf` e `iat`.
- `get_current_user` rechaza el token de una cuenta de nivel 0/1 sin `sf`, o con `iat` anterior a `usuarios.sesiones_validas_desde`.
- El secreto vive cifrado (Fernet) en una tabla propia. La vinculación solo se abre si el super la habilitó en las últimas 24 h.

**Stack:**
- Backend: FastAPI + SQLAlchemy async (asyncpg), PostgreSQL 17, python-jose, `cryptography` (Fernet, ya instalada) y las nuevas `pyotp` y `segno`.
- Login del shell: vanilla (`frontend/login.html`).
- Usuarios: React 19.
- App de agentes: React (repo `zaris-agentes`).

**Spec:** [`PLAN_MULTI_MUNICIPIO_F3B_DISENO.md`](PLAN_MULTI_MUNICIPIO_F3B_DISENO.md), aprobado por César el 2026-10-26. Base: F3 en prod ([`PLAN_MULTI_MUNICIPIO_F3.md`](PLAN_MULTI_MUNICIPIO_F3.md)); siguen valiendo las reglas R1-R11 de [`PLAN_MULTI_MUNICIPIO_F1_F2.md`](PLAN_MULTI_MUNICIPIO_F1_F2.md).

## Restricciones globales

- **Todo en local primero; prod una sola vez, en la Tarea 10.**
  - Rama `it01-f3b-segundo-factor` en el worktree `ZGE/.claude/worktrees/it01-f3b-segundo-factor`. No se mergea a `main` antes de la Tarea 10.
  - La app de agentes va en la rama `segundo-factor` de `zaris-agentes`. Tampoco se mergea antes.
  - Base de pruebas: `zaris_dev`.
- **Niveles con segundo factor:** `{0, 1}`, en una sola constante (`NIVELES_CON_SEGUNDO_FACTOR`).
- **Constantes del spec** (en `app/services/segundo_factor.py`):
  - TOTP de 6 dígitos y paso de 30 s, con ventana ±1 paso;
  - desafío de 5 min;
  - 5 fallos consecutivos bloquean 15 min;
  - la habilitación dura 24 h;
  - 10 códigos de emergencia;
  - el emisor en la app es `ZARIS`.
- **Variables de entorno:**
  - `SEGUNDO_FACTOR_OBLIGATORIO`: por defecto `True`. Solo `backend/.env.local` lo pone en `false`.
  - `SEGUNDO_FACTOR_CLAVE`: clave Fernet. Si falta y el segundo factor está activo, las cuentas de nivel 0/1 reciben 503 y nunca un token.
  - Ninguna de las dos se commitea con un valor real.
- **El secreto no va en `usuarios`.** La única columna nueva de `usuarios` es `sesiones_validas_desde`.
- **Migraciones:**
  - la `128` lleva `DROP`: en prod la corre César en el SQL Editor;
  - la `128b` no lleva `DROP` y va por MCP;
  - se renumeran si otra migración toma el número antes (CLAUDE.md §21);
  - toda tabla nueva lleva RLS y su fila en `municipio_tabla_clase`.
- **Smokes:**
  - solo contra `zaris_dev`, con el mail en MOCK (`settings.RESEND_API_KEY = ""`);
  - los del segundo factor prenden el interruptor **in-process** (`settings.SEGUNDO_FACTOR_OBLIGATORIO = True` y una clave Fernet generada en el momento);
  - sin credenciales de prod en archivos versionados (CLAUDE.md §40).
- **Antes de cada commit:**
  - `grep -riE "h[u]sky" .` tiene que dar vacío;
  - `pnpm typecheck` si el commit toca `web-app/` o `zaris-agentes/`;
  - bump del `?v=` si se tocan assets del shell.
- **Textos fijos de la interfaz:**
  - Sin habilitar: «Tu cuenta necesita que el soporte de ZARIS habilite la vinculación de la app de códigos.»
  - Código inválido (401): «El código no es válido. Revisá la app y probá de nuevo.»
  - Bloqueo (429): «Demasiados códigos incorrectos. Probá de nuevo en 15 minutos.»
  - Desafío vencido o inválido (401): «Pasaron más de 5 minutos. Volvé a ingresar tu clave.»
  - Sin configuración (503): «El ingreso con segundo factor no está configurado en el servidor. Avisá al soporte de ZARIS.»
  - App de agentes, sin vincular: «Vinculá la app de códigos entrando primero desde la computadora.»
  - App de agentes, emergencia: «Para usar un código de emergencia, entrá desde la computadora.»
- **Fuera de alcance:**
  - passkeys;
  - «recordar este dispositivo»;
  - los niveles 2-5 y los vecinos;
  - una pantalla de eventos;
  - regenerar los códigos de emergencia desde «Mi perfil»;
  - rotar `SEGUNDO_FACTOR_CLAVE`;
  - que el cambio de clave revoque sesiones.

## Foco de revisión

Lo que el spec implica y es más probable que muerda, con la tarea que lo prueba:

1. **El mismo código mandado dos veces a la vez** (doble clic, dos pestañas): un solo token. El anti-repetición es un `UPDATE … WHERE ultimo_paso < :t RETURNING`, nunca leer y después escribir. Lo prueba la Tarea 2 (`test_codigo_concurrente`).
2. **Un código escrito con espacios** (`123 456`) **o un código de emergencia en minúsculas, con o sin guion:** se aceptan, porque se normalizan antes de comparar (Tarea 2).
3. **Una cuenta desactivada o bajada a nivel 2 entre la clave y el código**, con el desafío todavía vigente: 401 «Pasaron más de 5 minutos…» y ningún token (Tarea 4).
4. **Una vinculación abandonada y retomada dentro de la ventana de habilitación:** el QR nuevo reemplaza al pendiente y el viejo ya no confirma. Después de un código de emergencia, abandonar deja intacta la app vieja (Tarea 4).
5. **Un código válido en el segundo 29 del paso que llega en el segundo 1 del siguiente:** se acepta por la ventana ±1. Pero un código de un paso ya usado se rechaza, aunque esté dentro de la ventana (Tarea 2).

---

### Tarea 1: Base de datos, configuración y dependencias

**Archivos:**
- Crear: `backend/migrations/128_segundo_factor_accion_registro.sql` (con `DROP`; en prod la corre César)
- Crear: `backend/migrations/128b_segundo_factor.sql` (sin `DROP`, por MCP)
- Modificar: `backend/app/services/accesos_super.py` (`ACCIONES` suma `"segundo_factor"`)
- Modificar: `backend/app/core/config.py` (dos settings)
- Modificar: `backend/requirements.txt` (`pyotp==2.9.0`, `segno==1.6.1`)
- Modificar (local, no versionado): `backend/.env.local` (`SEGUNDO_FACTOR_OBLIGATORIO=false` y una clave Fernet de desarrollo)
- Crear: `backend/smoke_segundo_factor.py`. Lo amplían las Tareas 2 a 5. Usa el mismo esqueleto que `smoke_super_admin.py`: guarda `zaris_dev`, in-process con `httpx.ASGITransport` y `check()`.

**Interfaces:**
- Produce en la base:
  - **`128`:** el CHECK `ck_super_admin_acceso_accion` se reemplaza por uno que suma `'segundo_factor'` a las siete acciones actuales, en `BEGIN … COMMIT`.
  - **`usuarios.sesiones_validas_desde TIMESTAMPTZ NULL`.**
  - **Tabla `usuario_segundo_factor`:**
    - `id_usuario INTEGER PK → usuarios ON DELETE CASCADE`;
    - `id_municipio INTEGER NULL → municipios` (espejo de la cuenta; NULL = el super);
    - `secreto_cifrado TEXT NULL`, `secreto_pendiente_cifrado TEXT NULL`, `confirmado_en TIMESTAMPTZ NULL`, `ultimo_paso BIGINT NULL`;
    - `intentos_fallidos SMALLINT NOT NULL DEFAULT 0`, `bloqueado_hasta TIMESTAMPTZ NULL`, `habilitado_hasta TIMESTAMPTZ NULL`;
    - campos de §10 (`activo`, `fecha_alta`, `fecha_modificacion`, `id_usuario_alta`, `id_usuario_modificacion`), sin `id_subarea`.
  - **Tabla `usuario_codigo_emergencia`:**
    - `id_codigo_emergencia BIGSERIAL PK`, `id_usuario INTEGER NOT NULL → usuarios`, `id_municipio INTEGER NULL → municipios`;
    - `codigo_hash TEXT NOT NULL`, `usado_en TIMESTAMPTZ NULL`, `activo BOOLEAN NOT NULL DEFAULT TRUE`, `fecha_alta TIMESTAMPTZ NOT NULL DEFAULT NOW()`;
    - índice `(id_usuario) WHERE activo AND usado_en IS NULL`.
  - **Tabla `usuario_segundo_factor_evento`, append-only:**
    - `id_evento BIGSERIAL PK`, `id_usuario INTEGER NOT NULL → usuarios`, `id_municipio INTEGER NULL → municipios`;
    - `evento VARCHAR(20) NOT NULL` con CHECK en (`vinculado`, `ingreso`, `fallido`, `emergencia`, `bloqueo`, `habilitado`);
    - `id_usuario_actor INTEGER NULL → usuarios`, `ip VARCHAR(64)`, `user_agent VARCHAR(1000)`, `fecha_hora TIMESTAMPTZ NOT NULL DEFAULT NOW()`;
    - triggers que rechazan UPDATE, DELETE y TRUNCATE, copiados de los de `super_admin_acceso` en la `127b`.
  - Las tres tablas llevan `ENABLE ROW LEVEL SECURITY` y su fila en `municipio_tabla_clase` como `mixta`, con la nota «NULL = cuenta del super administrador».
- Produce en `Settings`: `SEGUNDO_FACTOR_OBLIGATORIO: bool = True` y `SEGUNDO_FACTOR_CLAVE: str = ""`.

- [ ] **Paso 1: Tests en `smoke_segundo_factor.py`:**
  - `test_tablas_segundo_factor`:
    - las tres tablas existen;
    - un `UPDATE` y un `DELETE` sobre `usuario_segundo_factor_evento` lanzan la excepción append-only;
    - un evento `'otro'` falla por el CHECK;
    - `registrar_acceso_super(accion="segundo_factor", …)` deja su fila;
    - `usuarios.sesiones_validas_desde` existe.
- [ ] **Paso 2:** correrlo (`cd backend; $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_segundo_factor.py`). Esperado: FALLA.
- [ ] **Paso 3:** escribir la `128` y la `128b`. Antes, verificar en local el nombre real del CHECK (`pg_constraint`); en prod es `ck_super_admin_acceso_accion`. Aplicarlas en `zaris_dev` (psql, o el patrón `driver_connection` de CLAUDE.md §5).
- [ ] **Paso 4:**
  - settings, `ACCIONES` y `requirements.txt`;
  - `pip install pyotp==2.9.0 segno==1.6.1`;
  - las dos variables en `.env.local`. La clave sale de `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
- [ ] **Paso 5:** el test en verde, y `smoke_segmentacion_f1.py` en verde (tablas clasificadas).
- [ ] **Paso 6: Commit** `feat(it-01-f3b): base del segundo factor (migs 128 y 128b), settings y dependencias`.

### Tarea 2: Servicio del segundo factor

**Archivos:**
- Crear: `backend/app/services/segundo_factor.py`
- Test: `backend/smoke_segundo_factor.py`

**Interfaces:**
- Consume: las tablas y los settings de la Tarea 1.
- Produce:
  - `class SegundoFactorNoConfigurado(Exception)`: la lanza el cifrado si `SEGUNDO_FACTOR_CLAVE` falta o no es una clave Fernet válida.
  - `def cifrar(secreto: str) -> str` / `def descifrar(token: str) -> str`: Fernet con `settings.SEGUNDO_FACTOR_CLAVE`.
  - `def normalizar_codigo(texto: str) -> str`: solo dígitos.
  - `def normalizar_codigo_emergencia(texto: str) -> str`: mayúsculas, sin nada que no sea alfanumérico.
  - `def generar_codigos_emergencia() -> list[str]`:
    - devuelve 10 códigos con formato `XXXXX-XXXXX`;
    - el alfabeto es `ABCDEFGHJKMNPQRSTUVWXYZ23456789`;
    - se generan con `secrets`.
  - `@dataclass class EstadoCuenta`: `vinculada: bool`, `confirmado_en: datetime | None`, `habilitado_hasta: datetime | None`, `bloqueado_hasta: datetime | None`, `habilitada: bool` (`habilitado_hasta > now`).
  - `async def estado_cuenta(db, id_usuario: int) -> EstadoCuenta`. Sin fila, todo vacío y `vinculada=False`.
  - `async def iniciar_vinculacion(db, *, id_usuario: int, id_municipio: int | None, etiqueta: str) -> dict`:
    - genera el secreto (`pyotp.random_base32()`) y lo guarda cifrado en `secreto_pendiente_cifrado` (upsert);
    - devuelve `{"qr": <data URI SVG>, "secreto": <base32>, "emisor": "ZARIS", "cuenta": etiqueta}`;
    - el QR es `segno.make(uri, error="m").svg_data_uri(scale=6)` con `uri = pyotp.TOTP(secreto).provisioning_uri(name=etiqueta, issuer_name="ZARIS")`.
  - `async def confirmar_vinculacion(db, *, id_usuario: int, codigo: str) -> list[str] | None`:
    - si el código vale contra el **pendiente**:
      - el pendiente pasa a `secreto_cifrado`;
      - `confirmado_en = NOW()`, `ultimo_paso` = el paso usado, `habilitado_hasta = NULL`;
      - los códigos viejos pasan a `activo = FALSE` y se insertan 10 nuevos con `bcrypt.hashpw(normalizado, bcrypt.gensalt(rounds=10))`;
      - `usuarios.sesiones_validas_desde = date_trunc('second', NOW())`;
      - devuelve los 10 en claro.
    - si no vale: `None`. No commitea: commitea el caller.
  - `async def verificar_codigo(db, *, id_usuario: int, codigo: str) -> bool`:
    - prueba los pasos `t-1`, `t` y `t+1` contra el secreto **confirmado**, con `hmac.compare_digest(totp.generate_otp(paso), codigo)`;
    - si coincide, aplica `UPDATE … SET ultimo_paso = :paso, intentos_fallidos = 0 WHERE id_usuario = :id AND (ultimo_paso IS NULL OR ultimo_paso < :paso) RETURNING 1`. Es `True` solo si devuelve la fila.
  - `async def usar_codigo_emergencia(db, *, id_usuario: int, codigo: str) -> bool`: compara con bcrypt contra los activos sin usar y marca `usado_en` en el que coincide.
  - `async def registrar_fallo(db, *, id_usuario: int) -> bool`:
    - suma un intento;
    - al quinto: `bloqueado_hasta = NOW() + 15 min`, intentos en 0 y evento `bloqueo`;
    - devuelve `True` si bloqueó.
  - `async def bloqueada(db, id_usuario: int) -> bool`.
  - `async def habilitar(db, *, id_usuario: int, id_municipio: int | None, id_actor: int | None) -> None`:
    - upsert de la fila con todo el estado en vacío (secretos, `confirmado_en`, `ultimo_paso`, intentos y bloqueo) y `habilitado_hasta = NOW() + 24 h`;
    - los códigos pasan a `activo = FALSE`;
    - `usuarios.sesiones_validas_desde = date_trunc('second', NOW())`;
    - evento `habilitado` con el actor.
  - `async def registrar_evento(db, *, id_usuario: int, id_municipio: int | None, evento: str, id_actor: int | None = None, ip: str | None = None, user_agent: str | None = None) -> None`: trunca `user_agent` a 1000.

- [ ] **Paso 1: Tests**. Todos directos contra el servicio, sobre una cuenta de nivel 1 del municipio 1 que el smoke crea (idempotente) con email `sf.admin@prueba-aislamiento.com.ar` y clave `123456`:
  - `test_cifrado`:
    - `descifrar(cifrar("ABC")) == "ABC"`;
    - con `settings.SEGUNDO_FACTOR_CLAVE = ""`, `cifrar` lanza `SegundoFactorNoConfigurado`;
    - con `"basura"`, también.
  - `test_vinculacion`:
    - `habilitar` deja `habilitada=True`;
    - `iniciar_vinculacion` devuelve un `qr` que empieza con `data:image/svg+xml` y un `secreto` de 32 caracteres base32;
    - `confirmar_vinculacion` con un código mal da `None`;
    - con `pyotp.TOTP(secreto).now()` devuelve 10 códigos con el formato `^[A-Z2-9]{5}-[A-Z2-9]{5}$`, `estado_cuenta().vinculada` pasa a `True` y `sesiones_validas_desde` no es NULL.
  - `test_reintento_vinculacion`: un segundo `iniciar_vinculacion` reemplaza el pendiente. Un código del primer secreto ya no confirma.
  - `test_codigo_y_repeticion`:
    - `verificar_codigo` con el código actual da `True` y con el mismo código da `False`;
    - con `totp.at(now + 30 s)` (paso `t+1`) da `True`;
    - con `"123 456"` normalizado, si es el código vigente de un paso nuevo, da `True`.
  - `test_codigo_concurrente`: dos `verificar_codigo` con el mismo código, en dos sesiones y con `asyncio.gather`. Exactamente uno da `True`.
  - `test_emergencia`:
    - un código devuelto por `confirmar_vinculacion`, en minúsculas y sin guion, da `True` con `usar_codigo_emergencia`;
    - el mismo otra vez da `False`;
    - un código inventado da `False`.
  - `test_bloqueo`: 4 `registrar_fallo` dan `False`; el quinto da `True` y deja `bloqueada()` en `True` y un evento `bloqueo`. Al final, restaurar `bloqueado_hasta = NULL` e `intentos_fallidos = 0`: los tests siguientes usan la misma cuenta.
- [ ] **Paso 2:** fallan; **Paso 3:** implementar; **Paso 4:** pasan.
- [ ] **Paso 5: Commit** `feat(it-01-f3b): servicio del segundo factor (TOTP, codigos de emergencia, bloqueo, habilitacion)`.

### Tarea 3: Token y guard central

**Archivos:**
- Modificar: `backend/app/core/auth.py`
- Modificar: `backend/app/api/routes/demo_datos.py` (`_autorizar`)
- Test: `backend/smoke_segundo_factor.py`

**Interfaces:**
- Consume: `settings.SEGUNDO_FACTOR_OBLIGATORIO` (Tarea 1).
- Produce:
  - `NIVELES_CON_SEGUNDO_FACTOR: frozenset[int] = frozenset({0, 1})`.
  - `def requiere_segundo_factor(nivel_real: int) -> bool`: `settings.SEGUNDO_FACTOR_OBLIGATORIO and nivel_real in NIVELES_CON_SEGUNDO_FACTOR`.
  - `create_access_token(data)` agrega `iat` (entero, UTC). Un `sf` en `data` viaja tal cual.
  - `crear_token_super_admin(id_usuario: int, *, segundo_factor: bool) -> str`: suma `sf` e `iat`. La vigencia sigue en `SUPER_ADMIN_TOKEN_MINUTES = 480`. Hay que corregir el comentario «hasta F3b»: pasa a ser definitivo.
  - `get_current_user`:
    - el `SELECT` suma `sesiones_validas_desde`;
    - si `requiere_segundo_factor(user.nivel_acceso)`, devuelve 401 `SESION_VENCIDA` cuando el token no trae `sf is True`, o cuando la marca no es NULL y `iat` falta o es menor que `int(marca.timestamp())`;
    - el dict devuelto **no** incluye `sesiones_validas_desde`.
  - `demo_datos._autorizar`:
    - el JWT se valida llamando a `get_current_user(request, HTTPAuthorizationCredentials(scheme="Bearer", credentials=…), db)`, con un `HTTPException` atrapado;
    - acepta solo si `not es_super_admin`, `nivel_real == 1` e `id_municipio ==` el municipio demo;
    - no queda ningún `jwt.decode` propio. Verificarlo con `grep -n "jwt.decode" backend/app`: solo dos, en `core/auth.py`.

- [ ] **Paso 1: Tests** (smoke, con el interruptor prendido):
  - `test_token_sin_sf`: un `create_access_token({"sub": id_sf_admin, "mun": 1})` sin `sf` → `GET /api/v1/auth/me` da 401. Con `sf: True` da 200.
  - `test_ascenso`:
    - una cuenta de nivel 2 (`sf.nivel2@prueba-aislamiento.com.ar`, creada por el smoke) con token sin `sf` da 200 en `/auth/me`;
    - después de `UPDATE usuarios SET nivel_acceso = 1`, el mismo token da 401;
    - restaurar el nivel 2.
  - `test_marca`:
    - un token con `sf` da 200;
    - esperar 1,1 s y fijar la marca en `date_trunc('second', NOW())`: el mismo token da 401;
    - un token nuevo da 200.
  - `test_super_sin_sf`: un `crear_token_super_admin(id_super, segundo_factor=False)` da 401 en `/auth/me`.
  - `test_interruptor_apagado`: con `settings.SEGUNDO_FACTOR_OBLIGATORIO = False`, el token sin `sf` de nivel 1 da 200. Restaurar `True`.
  - `test_demo_poblar_sin_sf`: `POST /api/v1/demo/poblar` con un token de nivel 1 del municipio demo sin `sf` da 401.
- [ ] **Paso 2:** fallan; **Paso 3:** implementar; **Paso 4:** pasan, y `smoke_super_admin.py` y `smoke_municipio_request.py` siguen en verde con el interruptor apagado.
- [ ] **Paso 5: Commit** `feat(it-01-f3b): token con sf e iat, guard central y demo/poblar por el guard`.

### Tarea 4: Login en dos pasos

**Archivos:**
- Crear: `backend/app/services/login_interno.py`. Recibe de `routes/auth.py` a `_perfil_agente_del_usuario`, la emisión del token y el armado de `user_data`.
- Modificar: `backend/app/api/routes/auth.py` (`login`, `me`)
- Crear: `backend/app/api/routes/segundo_factor.py` (router `/api/v1/auth/segundo-factor`), registrado en `backend/app/main.py`
- Modificar: `backend/app/core/urls.py` (`url_login_backoffice()`)
- Test: `backend/smoke_segundo_factor.py`

**Interfaces:**
- Consume: el servicio (Tarea 2) y los tokens (Tarea 3).
- Produce:
  - `services/login_interno.py`:
    - `async def perfil_agente_del_usuario(db, id_usuario: int) -> dict`: el `_perfil_agente_del_usuario` actual, movido sin cambios. `/me` lo importa de acá.
    - `async def completar_login(db, request, user, *, segundo_factor: bool) -> dict`. Hace lo que hoy hace `login` desde la auditoría en adelante:
      - para el super, la fila `login` de `super_admin_acceso`; para el resto, `usuario_login_log`;
      - `fecha_ultimo_login`;
      - la renovación de clave (mig 96);
      - el token, con `sf=segundo_factor`;
      - `user_data`.

      Devuelve `{"access_token", "token_type": "bearer", "user"}`. `user` es una fila con las columnas de `_USUARIO_LOGIN_SELECT`.
    - `async def cargar_usuario(db, id_usuario: int)`: la fila con esas mismas columnas.
  - `routes/auth.py::login`:
    - después de validar la clave, si `requiere_segundo_factor(user.nivel_acceso)` **no** llama a `completar_login`;
    - con `SegundoFactorNoConfigurado` (o si `descifrar` no puede), devuelve 503 con el texto fijo;
    - si no, devuelve `SegundoFactorRequerido`;
    - `response_model=LoginResponse | SegundoFactorRequerido`.
  - `class SegundoFactorRequerido(BaseModel)`:
    - `requiere_segundo_factor: Literal[True] = True`;
    - `estado: Literal["codigo", "vincular", "sin_habilitar"]`;
    - `desafio: str | None` (None con `sin_habilitar`);
    - `mensaje: str | None` (el texto fijo con `sin_habilitar`);
    - `url_backoffice: str`.
  - Desafío, en `segundo_factor.py`:
    - `crear_desafio(id_usuario: int, *, fin: Literal["codigo", "vincular", "revincular"], id_municipio: int | None) -> str`: JWT con `scope="segundo_factor"`, `sub`, `fin`, `mun` (o `sa=True` si es None), que vence a los 5 min;
    - `async def leer_desafio(db, token: str, fines: set[str])` devuelve `(fin, user)`. Valida firma, scope, `fin ∈ fines` y vencimiento. Recarga la cuenta y exige: activa, `requiere_segundo_factor(nivel)` y municipio igual al del desafío. Si algo falla, 401 con el texto «Pasaron más de 5 minutos…».
  - Estados que decide `login` con `estado_cuenta`:
    - `vinculada` → `codigo`;
    - no vinculada y `habilitada` → `vincular`;
    - si no → `sin_habilitar`.
  - Endpoints. Todos llevan `check_rate_limit(f"segfac-ip:{ip}", max_requests=10, window_seconds=60)`. Si la cuenta está bloqueada, 429 con el texto fijo antes de mirar el código. Cada fallo llama a `registrar_fallo` y a `registrar_evento("fallido")`, y responde 401 con el texto fijo (o 429 si ese fallo bloqueó).
    - `POST /verificar` `{desafio, codigo}`, fin `codigo`: con un código válido, evento `ingreso` y `completar_login(..., segundo_factor=True)`.
    - `POST /emergencia` `{desafio, codigo}`, fin `codigo`: con un código válido, evento `emergencia` y devuelve `{"desafio": crear_desafio(..., fin="revincular")}`. No emite token y no toca el secreto confirmado.
    - `POST /vinculacion` `{desafio}`:
      - fin `vincular` (además exige `habilitada`, si no 403 con el texto fijo de sin habilitar) o fin `revincular`;
      - `iniciar_vinculacion` con `etiqueta` = el email (super) o `"{email} · {municipios.codigo_corto}"` (administrador).
    - `POST /vinculacion/confirmar` `{desafio, codigo}`, fin `vincular` (vuelve a exigir `habilitada`, si no 403) o `revincular`:
      - con `confirmar_vinculacion` ≠ None: evento `vinculado`, y devuelve `{"codigos_emergencia": [...], **completar_login(..., segundo_factor=True)}`;
      - un código que no confirma cuenta como fallo.
  - `url_login_backoffice() -> str`: `url_publica(settings.FRONTEND_BASE_URL)` + `/frontend/login.html`, fail-closed como los otros helpers.

- [ ] **Paso 1: Tests** (smoke, interruptor prendido, cliente ASGI con `Origin` del municipio 1):
  - `test_login_pide_codigo`:
    - login de la cuenta vinculada en la Tarea 2 → 200, sin `access_token`, con `estado == "codigo"` y un `desafio`;
    - el desafío como Bearer en `/auth/me` da 401;
    - `POST /verificar` con el código vigente da `access_token`, y ese token da 200 en `/auth/me`;
    - queda una fila nueva en `usuario_login_log` y un evento `ingreso`.
  - `test_nivel_2_sin_cambios`: el login de `sf.nivel2@…` devuelve `access_token` directo.
  - `test_sin_habilitar`:
    - una cuenta nivel 1 nueva sin fila → `estado == "sin_habilitar"`, `desafio is None` y `mensaje` igual al texto fijo;
    - con `habilitado_hasta` en el pasado, lo mismo;
    - `POST /vinculacion` con un desafío `vincular` fabricado para esa cuenta da 403.
  - `test_vinculacion_por_login`:
    - `habilitar` → login da `estado == "vincular"`;
    - `/vinculacion` da `qr`;
    - `/vinculacion/confirmar` con el código del secreto devuelto da 10 códigos y `access_token`;
    - un login posterior da `estado == "codigo"`.
  - `test_emergencia_revincula`:
    - `/emergencia` con un código de emergencia da un desafío `revincular`;
    - con ese desafío, `/vinculacion` y **sin confirmar**: un login nuevo sigue en `codigo` y el código del secreto **viejo** sigue entrando;
    - después, otro código de emergencia → `/vinculacion` → `/vinculacion/confirmar` da 10 códigos nuevos y los anteriores ya no sirven.
  - `test_bloqueo_http`:
    - 5 `/verificar` con `000000` → el quinto da 429;
    - el código correcto da 429 mientras dure el bloqueo;
    - con `bloqueado_hasta` en el pasado, entra. Así la cuenta queda desbloqueada para los tests siguientes.
  - `test_desafio`:
    - un desafío con `exp` vencido da 401;
    - un desafío `codigo` contra `/vinculacion/confirmar` da 401;
    - un desafío de una cuenta que entre los dos pasos pasa a `activo = FALSE` da 401, y lo mismo si pasa a nivel 2.
  - `test_clave_temporal`: con `debe_cambiar_password = TRUE`, `/verificar` devuelve `user.debe_cambiar_password == True`.
  - `test_super`:
    - login del super local (`super.admin@prueba-aislamiento.com.ar`, habilitado y vinculado en el test) → `codigo`;
    - la fila `login` de `super_admin_acceso` aparece recién después de `/verificar`, no después de la clave;
    - el token trae `sa` y `sf`.
  - `test_sin_clave_503`:
    - con `settings.SEGUNDO_FACTOR_CLAVE = ""`, el login de nivel 1 da 503 con el texto fijo;
    - el de nivel 2 da 200 con `access_token`;
    - restaurar la clave.
- [ ] **Paso 2:** fallan; **Paso 3:** implementar; **Paso 4:** pasan.
- [ ] **Paso 5:** con el interruptor apagado, toda la suite (`correr_suite.py`, ver Tarea 9) en verde. El login de siempre no cambió para nadie.
- [ ] **Paso 6: Commit** `feat(it-01-f3b): login en dos pasos, vinculacion y codigos de emergencia`.

### Tarea 5: Habilitación por el super y estado en Usuarios (backend)

**Archivos:**
- Modificar: `backend/app/api/routes/segundo_factor.py`
- Crear: `backend/habilitar_segundo_factor.py`
- Test: `backend/smoke_segundo_factor.py`

**Interfaces:**
- Consume: `habilitar`, `estado_cuenta` (Tarea 2); `municipio_actual`, `require_super_admin` y `registrar_acceso_super_en` (F3).
- Produce:
  - `GET /api/v1/auth/segundo-factor/cuentas/{id_usuario}` → `{nivel, requiere: bool, vinculada, confirmado_en, habilitado_hasta, bloqueado_hasta}`:
    - nivel efectivo 1 (administrador o super), con `municipio_actual`;
    - una cuenta de otro municipio o de nivel 0 da 404;
    - nunca devuelve secretos ni códigos.
  - `POST /api/v1/auth/segundo-factor/cuentas/{id_usuario}/habilitar` → 200 con el estado nuevo:
    - `require_super_admin` y `municipio_actual`;
    - la cuenta tiene que ser de nivel 1 del municipio elegido (si no, 404);
    - en una sola transacción: `habilitar(..., id_actor=super)` y `registrar_acceso_super_en(db, accion="segundo_factor", id_municipio=…, detalle=f"Restableció y habilitó la vinculación de {nombre} ({email})")`;
    - si el registro falla, no queda el cambio.
  - `backend/habilitar_segundo_factor.py --email E [--imprimir-sql]`:
    - restablece y habilita una cuenta de nivel 0, con el mismo efecto que `habilitar` y el actor en NULL;
    - en local conecta a `zaris_dev` y exige `current_database() = 'zaris_dev'`;
    - con `--imprimir-sql` no conecta e imprime el SQL para correrlo por `execute_sql` en prod;
    - sale con error si el email no es de una cuenta de nivel 0.

- [ ] **Paso 1: Tests:**
  - `test_habilitar_por_super`:
    - el super (con `X-Municipio: 1`) habilita a `sf.admin@…` → 200;
    - la cuenta queda `habilitada`, sin secreto, con los códigos inactivos y la marca puesta;
    - un token suyo emitido antes da 401;
    - hay una fila `segundo_factor` en `super_admin_acceso` con `id_municipio = 1`, y un evento `habilitado` con el actor.
  - `test_habilitar_no_admin`:
    - un administrador del municipio 1 (token con `sf`) en el mismo endpoint → 403;
    - el super sobre una cuenta del municipio de aislamiento con `X-Municipio: 1` → 404;
    - el super sobre su propia cuenta → 404.
  - `test_estado_cuenta_endpoint`:
    - el administrador del municipio 1 ve el estado de `sf.admin@…` y la respuesta no tiene las claves `secreto*` ni `codigo*`;
    - un nivel 2 → 403;
    - una cuenta del municipio de aislamiento → 404.
  - `test_script_habilitar`: `habilitar_segundo_factor.py --email super.admin@prueba-aislamiento.com.ar` deja al super local `habilitada`. Con `--imprimir-sql` imprime SQL y no cambia la base.
- [ ] **Paso 2:** fallan; **Paso 3:** implementar; **Paso 4:** pasan, y `smoke_aislamiento.py --rutas /api/v1/auth/segundo-factor` en 0 fallas.
- [ ] **Paso 5: Commit** `feat(it-01-f3b): habilitacion por el super, estado por cuenta y script del nivel 0`.

### Tarea 6: Login del shell

**Archivos:**
- Modificar: `frontend/login.html`. **Este commit toca solo este archivo**: en la Tarea 10 va a `main` antes que el backend.

**Interfaces:**
- Consume: el contrato de la Tarea 4. Tiene que funcionar también contra el backend viejo: si la respuesta del login trae `access_token`, sigue el flujo de hoy.
- Produce, con el mismo patrón de formularios ocultos que `cambio-form` y una función `entrarConSesion(data)`:
  - `entrarConSesion(data)` es lo de las líneas actuales que deciden entre `mostrarCambioForzado` y `persistirSesion` + redirect;
  - `codigo-form`: un input numérico de 6 dígitos (`autocomplete="one-time-code"`, `inputmode="numeric"`) que llama a `/verificar`, y un enlace «Usar un código de emergencia» que cambia el input a texto y llama a `/emergencia`. Esa respuesta lleva a `vincular-form` con el desafío `revincular`;
  - `vincular-form`: `<img>` con `src` = `qr` (data URI, **nunca** `innerHTML`), el secreto en texto mono con un botón «Copiar», el input del código y el botón «Vincular». Llama a `/vinculacion` al mostrarse y a `/vinculacion/confirmar` al enviar;
  - `emergencia-panel`: la lista de los 10 códigos, «Copiar todos», un checkbox «Los guardé en un lugar seguro» y el botón «Entrar», deshabilitado hasta tildar. Al entrar llama a `entrarConSesion`;
  - `estado: "sin_habilitar"`: el `mensaje` en el error del login, sin cambiar de vista;
  - 401, 429 y 503 de los pasos: el `detail` en el error de la vista activa. Un 401 con desafío vencido vuelve a la vista de login.

- [ ] **Paso 1:** implementar.
- [ ] **Paso 2: Verificación en el navegador**, local con el interruptor **prendido** (uvicorn con `SEGUNDO_FACTOR_OBLIGATORIO=true` solo en esa terminal) y `python -m http.server 8080`. Recorrer con clics:
  - (a) super habilitado → QR → código de la app de prueba (`pyotp` en consola) → códigos → Entrar → shell;
  - (b) logout → login → código → shell;
  - (c) código mal → texto fijo;
  - (d) emergencia → QR nuevo → confirmar → shell;
  - (e) cuenta sin habilitar → mensaje;
  - (f) nivel 2 → entra directo;
  - (g) cuenta con clave temporal → código → cambio forzado.

  Leer el DOM además de mirar la pantalla.
- [ ] **Paso 3:** con el backend de `main` (interruptor apagado, contrato viejo), el login de un nivel 1 entra como hoy.
- [ ] **Paso 4: Commit** `feat(it-01-f3b): login del shell con segundo factor`.

### Tarea 7: Usuarios (React) y login de desarrollo

**Archivos:**
- Crear: `web-app/src/modules/usuarios/components/SegundoFactorPanel.tsx`
- Modificar: `web-app/src/modules/usuarios/api/usuariosApi.ts`, `hooks/useUsuarios.ts`, `views/MaestroView.tsx` (montar el panel en la sub-tab Datos), `views/AccesosSuperView.tsx` (`ACCIONES` suma `segundo_factor: 'Segundo factor'`)
- Modificar: `web-app/src/app/LoginPage.tsx`

**Interfaces:**
- Consume: los endpoints de la Tarea 5.
- Produce:
  - `obtenerSegundoFactor(id: number)` y `habilitarSegundoFactor(id: number)` en `usuariosApi.ts`, con sus hooks de react-query. El hook de estado se invalida al habilitar.
  - `<SegundoFactorPanel usuario={u} />`:
    - se muestra solo si la cuenta es de nivel 0 o 1;
    - muestra «Segundo factor: vinculado el {fecha} / sin vincular / habilitada para vincular hasta {fecha y hora} / bloqueado hasta {hora}»;
    - el botón «Restablecer y habilitar vinculación» aparece solo si `useAuthStore` dice `es_super_admin`, con el `ConfirmModal` que MaestroView ya usa para la baja;
    - el modal se cierra al confirmar y el resultado llega por toast (CLAUDE.md §23).
  - `LoginPage.tsx`: si la respuesta trae `requiere_segundo_factor`, muestra el error «Esta cuenta pide un código: ingresá por el login del shell (localhost:8080/frontend/login.html).» y no guarda sesión.

- [ ] **Paso 1:** implementar.
- [ ] **Paso 2:** `pnpm typecheck` en `web-app/` → 0 errores.
- [ ] **Paso 3: Verificación en el navegador** (shell local, interruptor prendido), con clics:
  - como super, en Usuarios → `sf.admin@…`, el panel muestra el estado; el botón restablece y queda «habilitada para vincular hasta …»;
  - Usuarios → «Registro del super administrador» muestra la fila «Segundo factor» con el detalle;
  - como administrador de nivel 1, el panel se ve sin el botón;
  - en un nivel 3 no hay panel.
- [ ] **Paso 4: Commit** `feat(it-01-f3b): estado y habilitacion del segundo factor en Usuarios`.

### Tarea 8: App de agentes

**Archivos** (repo `zaris-agentes`, rama `segundo-factor`):
- Modificar: `src/lib/session.ts` (tipo `SegundoFactorRequerido`)
- Modificar: `src/lib/auth.ts` (`login`, `verificarCodigo`)
- Modificar: `src/pages/LoginPage.tsx`

**Interfaces:**
- Consume: `/auth/login` y `/auth/segundo-factor/verificar` (Tarea 4).
- Produce:
  - `login(identificador, password): Promise<AuthOut | SegundoFactorRequerido>`. Guarda sesión solo si viene `access_token`.
  - `verificarCodigo(desafio: string, codigo: string): Promise<AuthOut>`, con `{ auth: false }` como el login. Guarda la sesión.
  - `LoginPage`:
    - con `estado: "codigo"`, pasa a un paso «Código de la app» (6 dígitos, `autocomplete="one-time-code"`). Al validar navega como hoy (`/cambiar-clave` o `/inicio`). Debajo, el texto fijo de emergencia;
    - con `vincular` muestra el texto fijo «Vinculá la app…», y con `sin_habilitar` el `mensaje`. En los dos casos, un link a `url_backoffice`;
    - un 401 o 429 del paso muestra el `detail`. Un desafío vencido vuelve al paso de la clave.

- [ ] **Paso 1:** implementar.
- [ ] **Paso 2:** `pnpm typecheck` en `zaris-agentes` → 0 errores.
- [ ] **Paso 3: Navegador** (`pnpm dev` en 5175, contra el backend local con el interruptor prendido):
  - `sf.admin@…` vinculado → código → inicio;
  - sin vincular → texto y link;
  - nivel 4 → entra directo;
  - contra el backend con el interruptor apagado, todos entran como hoy.
- [ ] **Paso 4: Commit** en la rama `segundo-factor` y push de la rama. Vercel crea un preview; producción no cambia.

### Tarea 9: Scripts contra prod, suite completa y documentación

**Archivos:**
- Crear: `backend/_login_interno_prod.py` con `def login_interno(base: str, email: str, password: str) -> str`. Si el login responde `requiere_segundo_factor`, pide el código por `input()` y llama a `/verificar`. Devuelve el token.
- Modificar: `backend/seed_prod.py`, `backend/smoke_alta_un_paso.py`, `backend/smoke_publico_adjuntos.py`:
  - en los dos smokes, si sus chequeos de admin funcionan con nivel 2, el modo prod usa la cuenta de nivel 2 de QA (`administrativo@`, misma variable de clave);
  - si no, y en `seed_prod.py`, usan `login_interno`.
- Modificar: `CLAUDE.md` §1:
  - párrafo nuevo «Segundo factor (IT-01 F3b)» de 5-8 líneas: niveles, habilitación por el super, claim `sf` e `iat`, `sesiones_validas_desde`, las dos variables de entorno y el script del nivel 0;
  - el «8 h» deja de decir «hasta el segundo factor».
- Modificar: `.claude/skills/modulo-usuarios/SKILL.md` (panel y habilitación), `HISTORIAL_MIGRACIONES.md` (128 y 128b), `CLAUDE.md` §21 (estado de las migraciones 128 y 128b), `ESTADO.md`.

- [ ] **Paso 1:** adaptar los tres scripts. Correr `smoke_alta_un_paso.py` y `smoke_publico_adjuntos.py` en modo local: en verde.
- [ ] **Paso 2: Suite completa con el interruptor apagado.**
  - Recrear el lanzador `uvicorn_mock.py` y `correr_suite.py` en `.superpowers/sdd/PLAN_MULTI_MUNICIPIO_F3B/` del worktree, copiándolos de `ZGE/.claude/worktrees/it01-multi-municipio/.superpowers/sdd/PLAN_MULTI_MUNICIPIO_F1_F2/` y sumando `smoke_segundo_factor.py` a `SUITE`.
  - Correr `python correr_suite.py final`. Esperado: todos en verde.
- [ ] **Paso 3:** `smoke_segundo_factor.py` en verde (prende el interruptor in-process). `smoke_aislamiento.py` completo con 0 fallas.
- [ ] **Paso 4:** documentación. Grep de credenciales de prod en lo que se commitea (CLAUDE.md §40).
- [ ] **Paso 5: Commit** `docs(it-01-f3b): scripts contra prod, CLAUDE, skill e historial`.

### Tarea 10: Corte en prod (con César)

Sigue el orden de §6 del spec.

- [ ] **Paso 1:** pre-chequeos de solo lectura en prod (`execute_sql`):
  - las tres tablas no existen;
  - `usuarios.sesiones_validas_desde` no existe;
  - el CHECK sigue con 7 acciones;
  - la última migración es la 127c.
- [ ] **Paso 2:** backup (`/backup-prod`).
- [ ] **Paso 3:** César carga `SEGUNDO_FACTOR_CLAVE` en Railway (servicio `zaris-api` → Variables). Se genera en su máquina con el comando de la Tarea 1. Confirmar que quedó cargada sin imprimirla: César lo ve en el panel.
- [ ] **Paso 4:** la `128b` por `apply_migration`, verificada. César corre la `128` en el SQL Editor; verificar el CHECK nuevo.
- [ ] **Paso 5: primero los clientes:**
  - `git cherry-pick` del commit de la Tarea 6 sobre `main` → push. Esperar a que GitHub Pages sirva el `login.html` nuevo (buscar `codigo-form` con `curl`) y comprobar que un nivel 2 sigue entrando;
  - merge de `segundo-factor` a `main` en `zaris-agentes`. Verificar que el deploy de Vercel esté `READY` y que el bundle servido tenga el paso del código.
- [ ] **Paso 6:** merge de la rama a `main` en ZGE → Railway. Confirmar con el path exacto `/api/v1/auth/segundo-factor/verificar` en `/openapi.json` de prod.
- [ ] **Paso 7: con César:**
  - `python habilitar_segundo_factor.py --email <el de la cuenta 102> --imprimir-sql` → `execute_sql`. El email lo dicta César y no queda en ningún archivo;
  - César entra con la 102, vincula, guarda sus códigos de emergencia y entra;
  - desde la 102, en Usuarios, habilita `cesar@` y la vincula;
  - un token viejo de nivel 1 da 401;
  - un nivel 2 entra sin cambios;
  - hay eventos `vinculado` e `ingreso` y la fila `segundo_factor` del registro.
- [ ] **Paso 8:** ESTADO.md, `HISTORIAL_MIGRACIONES.md` (fecha del corte) y la memoria `project_it01_multi_municipio`. Push.
