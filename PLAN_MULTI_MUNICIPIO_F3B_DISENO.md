# IT-01 F3b — Segundo factor para el super administrador y los administradores de municipio (diseño)

> Decisiones tomadas por César el 2026-10-26, en la conversación de arranque de F3b (§3). **Documento aprobado por César el 2026-10-26.** Plan de implementación: [`PLAN_MULTI_MUNICIPIO_F3B.md`](PLAN_MULTI_MUNICIPIO_F3B.md). Base: F3 en prod desde el 2026-10-26 ([`PLAN_MULTI_MUNICIPIO_F3.md`](PLAN_MULTI_MUNICIPIO_F3.md)); spec general en [`PLAN_MULTI_MUNICIPIO.md`](PLAN_MULTI_MUNICIPIO.md) §3, que dejaba «cómo se implementa el segundo factor del nivel 0» a criterio del builder.

## 1. Por qué

- **Super administrador (nivel 0):** ve los datos de todos los municipios, incluida la historia clínica con motivo. Hoy alcanza con su clave, y la clave se recupera por mail: quien tome ese correo tiene la cuenta entera. Por eso su token dura 8 h y no 24 h (decisión de César del 2026-10-26, «hasta F3b»).
- **Administrador de municipio (nivel 1):** es el superusuario de su municipio. Su cuenta comprometida expone un municipio completo.
- **Cuándo:** F3b va **antes del primer municipio real** (decisión de César del 2026-10-25). Hasta F1-F6 terminadas no entra un segundo municipio con datos reales.

## 2. Objetivos, no objetivos y anti-objetivos

**Objetivos**
- Para entrar con una cuenta de **nivel 0 o 1**: la clave **más** un código de 6 dígitos de una app de autenticación del celular. Son los códigos que cambian cada 30 segundos (TOTP, RFC 6238), como los de Google Authenticator, Microsoft Authenticator y equivalentes.
- **Obligatorio**, sin forma de saltearlo: ni por la recuperación de clave, ni con un token viejo, ni desde otra app.
- **Recuperable**:
  - con códigos de emergencia de un solo uso;
  - el de un administrador, con un restablecimiento que hace solo el super;
  - el del super, con un script que corre quien tiene acceso a la base.

**No objetivos (F3b)**
- Llaves de seguridad o passkeys (WebAuthn). Quedan atadas al dominio, y el shell cambia de dominio en F5. Se pueden sumar después.
- «Recordar este dispositivo». El token de 8 h o 24 h ya es el recuerdo.
- Segundo factor para los niveles 2-5 o para los vecinos. El código queda preparado para ampliar los niveles (ver §4.1), pero no se amplía.
- Una pantalla para ver los eventos del segundo factor. Quedan en una tabla que se consulta por SQL; lo visible es el estado de cada cuenta y el registro del super (§4.6).
- Regenerar los códigos de emergencia desde «Mi perfil» sin haberlos usado.
- Rotar la clave de cifrado del secreto.

**Anti-objetivos (cosas que harían fracasar la fase aunque «funcione»)**
- Un camino que entregue un token de nivel 0 o 1 sin haber pasado el código. Por ejemplo: un login viejo, el cambio forzado de clave, el reset de clave, la app de agentes, un token emitido antes del despliegue o una cuenta recién ascendida a nivel 1.
- El segundo paso por **mail**. La clave ya se recupera por mail, así que el mismo correo daría las dos cosas.
- Dejar a un administrador sin forma de volver a entrar (deadlock), o a todos los de nivel 0/1 afuera si falta una variable de entorno, sin un mensaje claro.
- El secreto TOTP viajando en cualquier `SELECT` de `usuarios`, por ejemplo en el listado de solo lectura de Maestros.
- Romper los smokes locales y el barrido de aislamiento, que loguean con cuentas de nivel 1.

## 3. Decisiones de César (2026-10-26)

1. **Factor:** código de una app de autenticación del celular. Ni mail ni llave física.
2. **Alcance:** obligatorio para el **nivel 0 y el nivel 1**, en todos los municipios (incluido San Andrés), **sin interruptor por municipio**.
3. **Token:** el del super sigue en **8 h**, que pasa de transitorio a definitivo. El del nivel 1 sigue en 24 h.
4. **Primera vez:** la vinculación se hace en el mismo login, después de la clave, y no se puede saltear. Termina mostrando **10 códigos de emergencia** de un solo uso.
5. **Pérdida del celular:** con un código de emergencia se entra y se obliga a vincular de nuevo. Pérdida total: al administrador lo restablece **solo el super** desde Usuarios, y queda en su registro. Un administrador no puede restablecer a otro. Al super lo restablece un script.
6. **Sesiones abiertas:** al desplegar se cortan las de nivel 0/1. Quien suba a nivel 1 tiene que volver a ingresar y vincular.
7. **Clave temporal** de un administrador nuevo: clave → vincular → código → cambio forzado de clave.
8. **App de agentes:** a un administrador le pide el código también ahí. La **vinculación se hace solo desde la computadora**, porque el QR no se puede escanear con el mismo celular en el que se muestra. Si la cuenta no tiene app vinculada, la app de agentes muestra un mensaje que manda al backoffice.
9. **Protecciones** (propuestas por Claude, aprobadas):
   - 5 códigos mal puestos bloquean la cuenta 15 minutos;
   - un código usado no sirve dos veces;
   - el secreto se guarda cifrado con una clave que vive solo en Railway;
   - cada ingreso, fallo y uso de código de emergencia queda registrado.
10. **Local:** el segundo paso se apaga con una variable que existe solo en `.env.local`. Por defecto está **prendido**: si la variable falta en Railway, se exige igual.
11. **Habilitación de la vinculación por el super:** una cuenta de nivel 0/1 sin app vinculada (la primera vez o después de un restablecimiento) **solo puede vincular dentro de las 24 h siguientes a que el super la habilite**. Sin habilitación, la clave sola no alcanza para vincular. Así se cierra el hueco del primer ingreso, en el que quien tuviera la clave podía vincular su propio celular. No depende del mail: dos de las tres cuentas de nivel 1 de San Andrés tienen el correo en un dominio que no existe. Detalle en §4.3.

## 4. Cómo funciona

### 4.1 Quién lo tiene

- Una cuenta **requiere segundo factor** si su nivel **real** en la base es 0 o 1 y el segundo factor está activo en el entorno (§5).
- El conjunto de niveles vive en **una sola constante** del backend. Ampliarlo, por ejemplo al nivel 2, es cambiar esa constante y nada más.
- El nivel se lee de la base en cada request (como hoy en `get_current_user`). Por eso un ascenso o un descenso de nivel se aplica en la request siguiente, sin esperar a que venza el token.

### 4.2 Ingreso de todos los días

1. `POST /api/v1/auth/login` con identificador y clave, igual que hoy, con la misma búsqueda (`_buscar_usuario_login`, `_buscar_super_admin`) y los mismos límites por IP y por identificador.
2. Si la clave es correcta y la cuenta **requiere segundo factor**, el login **no devuelve `access_token`**. Responde 200 con:
   - `requiere_segundo_factor: true`;
   - `vincular: true|false`, que dice si la cuenta tiene app vinculada;
   - un **desafío**: un token corto, de 5 minutos, con un `scope` propio. `get_current_user` lo rechaza por scope, como ya rechaza los tokens del vecino.
3. El cliente muestra la pantalla del código y lo manda junto con el desafío a un endpoint del segundo paso.
4. Si el código es válido:
   - recién ahí se emite el token de siempre (el del super o el de municipio) con un claim nuevo que dice que pasó el segundo factor;
   - se escriben la auditoría de login (`usuario_login_log`, o la fila `login` de `super_admin_acceso` para el super);
   - se evalúa la renovación de clave (mig 96).

   Hoy esas tres cosas pasan después de la clave; con F3b pasan después del código.
5. `get_current_user` **rechaza con 401 «Sesión vencida»** todo token de una cuenta que requiere segundo factor y no trae el claim. Es el mismo patrón que el claim `mun` en F2, y cubre los tokens viejos y los ascensos de nivel.
6. **Revocación (decisión de Claude, tras la revisión del diseño):** hoy ningún mecanismo revoca un token, ni siquiera el cambio de clave. F3b agrega por cuenta una marca «sesiones válidas desde».
   - Se actualiza al **restablecer** el segundo factor y al **confirmar una vinculación nueva**, tanto la primera como la que sigue a un código de emergencia.
   - Los tokens pasan a llevar `iat`. `get_current_user` rechaza con 401 un token de una cuenta con segundo factor cuyo `iat` sea anterior a la marca.
   - Así, el restablecimiento corta también las sesiones abiertas de una cuenta comprometida.
   - El cambio de clave queda fuera de F3b: si revocara, habría que reemitir el token en el cambio forzado.
7. **Único otro lugar que decodifica el JWT por su cuenta:** `backend/app/api/routes/demo_datos.py::_autorizar`. Hoy acepta cualquier token de nivel 1 sin pasar por `get_current_user`, así que tiene que exigir el claim y la marca igual que el guard central (verificado con `grep jwt.decode` en `backend/app` el 2026-10-26: solo están `core/auth.py` y ese).

### 4.3 Primera vinculación (en el login del shell)

0. **Habilitación (decisión 11):**
   - **Quién habilita:**
     - el super, desde Usuarios → detalle de la cuenta, con un solo botón que restablece y habilita a la vez (§4.4). Sirve para las cuentas de nivel 1 de cualquier municipio;
     - la cuenta del super (nivel 0) se habilita con el script de §4.4, también en el corte.
   - **La ventana dura 24 h desde la habilitación.** Si vence sin que la persona vincule, el super vuelve a habilitar.
   - **Si la cuenta no está habilitada o la ventana venció:** el login con la clave correcta no entrega token, ni desafío de vinculación, ni QR. Muestra «Tu cuenta necesita que el soporte de ZARIS habilite la vinculación de la app de códigos».
   - **Consecuencias aceptadas:**
     - después del corte, las cuentas de nivel 1 de San Andrés no entran hasta que el super las habilite;
     - una cuenta que el administrador de un municipio suba a nivel 1 tampoco entra hasta que el super la habilite.
1. Después de la clave, con `vincular: true` y la cuenta habilitada, el login del shell muestra:
   - un QR, generado en el backend como SVG con una librería probada (ver §5);
   - el secreto en texto, para tipearlo si el QR no se puede escanear.
2. La persona escanea el QR con su app y escribe el primer código. El secreto queda **confirmado** recién cuando ese código es válido. Antes de eso hay un secreto pendiente, que se reemplaza si la persona vuelve a empezar.
3. Al confirmar, se muestran **10 códigos de emergencia** una sola vez, con un botón para copiarlos. Para seguir hay que marcar «Los guardé».
4. Después se entra como en §4.2.4. Si la cuenta tenía clave temporal, recién ahí aparece el cambio forzado de clave (`debe_cambiar_password`), con el token ya emitido, como hoy.

### 4.4 Códigos de emergencia y pérdida del celular

- En la pantalla del código hay un enlace: «Usar un código de emergencia».
- Un código de emergencia válido se marca usado y obliga a **vincular de nuevo** en ese mismo flujo: se muestra un QR nuevo y, al confirmar, salen 10 códigos nuevos que invalidan los que quedaban.
- **El secreto viejo sigue valiendo hasta que se confirma el nuevo** (decisión de Claude, tras la revisión del diseño). Si la persona abandona la vinculación a mitad, la cuenta queda como estaba: vinculada a la app vieja y con los códigos de emergencia que le quedan. Así, un código de emergencia nunca deja la cuenta en el estado «sin vincular», que solo autoriza la clave.
- **Pérdida total, administrador:** el super, desde Usuarios → detalle de la cuenta, usa «Restablecer y habilitar vinculación», con confirmación.
  - Borra el secreto y los códigos, corta las sesiones abiertas (§4.2.6) y abre la ventana de 24 h para vincular (§4.3.0).
  - Lo mismo, sobre una cuenta que nunca vinculó, solo la habilita.
  - El botón lo ve y lo usa **solo el super**. El administrador del municipio ve el resultado en el registro del super (§4.6).
- **Pérdida total, super, y primera vinculación de la 102:** un script del backend, en la misma línea que `seed_super_admin.py`, que restablece y habilita. En local conecta a `zaris_dev`; para prod imprime el SQL para correrlo por `execute_sql`.

### 4.5 Otras superficies

| Superficie | Qué cambia |
|---|---|
| Login del shell (`frontend/login.html`, prod) | Pantallas de código, vinculación y códigos de emergencia, en el mismo patrón que la pantalla oculta del cambio forzado. Tiene que funcionar con las dos formas de respuesta: con `access_token` sigue el flujo de hoy. |
| App de agentes (repo `zaris-agentes`, Vercel) | Después de la clave, si viene `requiere_segundo_factor`: con app vinculada, pide el código; sin app vinculada, muestra «Vinculá la app de códigos entrando primero desde la computadora» con el link al backoffice. **No acepta códigos de emergencia** (decisión de Claude): usar uno obliga a vincular, y eso solo se hace desde la computadora. Muestra «Para usar un código de emergencia, entrá desde la computadora». |
| Login del shell React de desarrollo (`web-app/src/app/LoginPage.tsx`, solo `localhost:5173`) | Si viene `requiere_segundo_factor`, muestra un mensaje para entrar por el login del shell vanilla. No implementa el código. |
| Usuarios (módulo React) | En el detalle de una cuenta de nivel 0/1: «Segundo factor: vinculado el … / sin vincular / habilitada para vincular hasta … / bloqueado hasta …». El botón «Restablecer y habilitar vinculación» solo lo ve el super. |
| PWA del vecino | Sin cambios. |

### 4.6 Registro

- **Tabla nueva de eventos del segundo factor**, append-only con el mismo trigger que `super_admin_acceso`. Registra: vinculado, ingreso con código, código fallido, código de emergencia usado, bloqueo y restablecido. Cada fila lleva cuenta, municipio de la cuenta (`NULL` para el super), quién lo hizo (en el restablecimiento, el super), IP y user agent.
- La fila `login` del super en `super_admin_acceso` se escribe **después** del código, no después de la clave.
- El restablecimiento que hace el super sobre una cuenta de un municipio tiene que aparecer en «Registro del super administrador» de ese municipio con un rótulo legible, por ejemplo «Restableció el segundo factor de Juana Pérez», y registrarse **en la misma transacción** que el cambio (`registrar_acceso_super_en`, regla de F3). Ver §8 sobre la acción del CHECK.

## 5. Datos, configuración y dependencias

- **El secreto NO va en `usuarios`.** Va en una tabla propia por cuenta, para que ningún `SELECT` de usuarios lo arrastre. Guarda:
  - el secreto cifrado y el pendiente de confirmación;
  - la fecha de confirmación;
  - el último paso de 30 s usado (anti-repetición);
  - los intentos fallidos consecutivos y el «bloqueado hasta» (el bloqueo es **persistente en la base**: el `check_rate_limit` es en memoria y se pierde con cada deploy);
  - `id_municipio` espejo del de la cuenta.
- **Códigos de emergencia:** en otra tabla, guardados con bcrypt, con fecha de uso.
- **Las tres tablas nuevas** (secreto, códigos, eventos):
  - clase `mixta` en `municipio_tabla_clase` (`NULL` = el super);
  - `ENABLE ROW LEVEL SECURITY` sin políticas;
  - FK a `usuarios`;
  - campos de §10 donde apliquen. La de eventos es append-only y no los necesita todos.
- **Cifrado:** Fernet (`cryptography`, ya instalada vía `python-jose[cryptography]`) con una clave en la env var **`SEGUNDO_FACTOR_CLAVE`**.
  - La carga César en Railway **antes** del deploy.
  - En `.env.local` va una clave de desarrollo.
  - Sin la clave y con el segundo factor activo, las cuentas de nivel 0/1 no pueden entrar: el login responde con un mensaje claro de configuración (503), nunca con un token sin segundo factor.
- **Interruptor de entorno:** **`SEGUNDO_FACTOR_OBLIGATORIO`**, por defecto `True`. Solo `.env.local` lo pone en `False`.
- **Dependencias nuevas:** `pyotp` (TOTP) y `segno` (QR en SVG, Python puro), con versión fija en `requirements.txt`. Regla del proyecto: librería probada, no encoder casero.
- **Verificación del código:** ventana de ±1 paso (30 s) para tolerar relojes corridos; se rechaza un paso igual o anterior al último usado.
- **En la app de autenticación:** el emisor se muestra como «ZARIS» y la cuenta como el email. Para un administrador, el email más el nombre o código del municipio, para que distinga dos cuentas.

## 6. Orden de despliegue (corte)

1. Backup de prod (`/backup-prod`).
2. César carga `SEGUNDO_FACTOR_CLAVE` en Railway. Se verifica que el servicio la tenga sin imprimirla.
3. Migraciones de las tablas nuevas por MCP, verificadas de a una. Si hay alguna parte con `DROP` (ver §8), la corre César en el SQL Editor.
4. **Primero los clientes**, que aceptan las dos formas de respuesta: el login del shell (GitHub Pages) y la app de agentes (Vercel). Verificar que sirvan la versión nueva.
5. Después el backend (merge a `main` → Railway). Confirmar el deploy con un path nuevo en `/openapi.json`, buscando el path exacto (regla de CLAUDE.md §9).
6. Verificación con César:
   - se habilita la 102 con el script (SQL por `execute_sql`);
   - César la vincula, entra con código y guarda sus códigos de emergencia;
   - desde la 102 habilita `cesar@` y la vincula. La cuenta de Roy y la id 1 quedan sin habilitar hasta que haga falta;
   - un token anterior de nivel 1 da 401;
   - un nivel 2 entra sin cambios;
   - el registro muestra los eventos.
7. Docs: CLAUDE.md §1 (segundo factor; las 8 h dejan de ser transitorias), skill `modulo-usuarios`, `HISTORIAL_MIGRACIONES.md`, `ESTADO.md`.

## 7. Pruebas

- **Smoke nuevo, in-process (ASGI), con el segundo factor prendido**, contra `zaris_dev` y con el mail en MOCK. Casos:
  - login de nivel 1 → desafío sin token;
  - sin habilitar, o con la ventana de 24 h vencida → ni token, ni desafío de vinculación, ni QR;
  - habilitada → vinculación completa;
  - código correcto → token con el claim;
  - el mismo código otra vez → rechazado;
  - 5 fallos → bloqueo de 15 min, también contando códigos de emergencia;
  - código de emergencia → obliga a vincular y los viejos dejan de servir;
  - token sin claim de una cuenta de nivel 1 → 401, y ascenso de un nivel 2 → 401 hasta re-ingresar;
  - el desafío no sirve como token en ningún endpoint;
  - el desafío vencido → rechazado;
  - restablecer: el super sí y queda registrado; un administrador no (403);
  - nivel 2-5 → login sin cambios;
  - sin `SEGUNDO_FACTOR_CLAVE` → 503 para nivel 0/1, nivel 2 sin cambios.
- **Suite existente** (22 smokes) y **barrido de aislamiento** con el segundo factor apagado, en verde.
- **Scripts que entran a PROD con una cuenta de nivel 1** (`backend/seed_prod.py`, `backend/smoke_alta_un_paso.py` y `backend/smoke_publico_adjuntos.py`, estos dos con `cesar@`) dejan de poder entrar después del corte. Decisión de Claude:
  - si sus chequeos funcionan con una cuenta de nivel 2, se pasan a una;
  - si no, piden el código por consola cuando el login responde `requiere_segundo_factor`.
- Agregar al smoke nuevo los casos de revocación: un token emitido antes de restablecer o revincular da 401, y `/demo/poblar` con un token sin el claim también.
- **Recorrido en el navegador** del login del shell (vinculación, ingreso, emergencia) y de la app de agentes (código y mensaje sin vincular).

## 8. Lo que queda a criterio del builder

- Nombres de endpoints, del claim, del scope del desafío, de las tablas y de las columnas.
- Cómo aparece el restablecimiento en «Registro del super administrador». Hay dos opciones:
  - una acción nueva en el CHECK `ck_super_admin_acceso_accion`. Cambiar un CHECK lleva `DROP CONSTRAINT`, así que esa parte la corre César en el SQL Editor;
  - la fila `request` que ya deja `municipio_actual` más un rótulo legible en la vista.

  Lo que no se negocia es el resultado: el administrador del municipio lo ve con el nombre de la cuenta afectada, y el registro va en la misma transacción que el cambio.
- La forma exacta de las pantallas, dentro del design system y del patrón del cambio forzado.
- Si el desafío es de un solo uso. El código ya lo es por el anti-repetición, así que no es obligatorio.
- Límite por IP en memoria para el endpoint del código, con clave prefijada (CLAUDE.md §5), además del bloqueo persistente por cuenta.

## 9. Pendiente de César

Nada. La primera vinculación se resolvió el 2026-10-26: la habilita el super (decisión 11, §4.3.0).
