# IT-01 F6 — Segunda barrera y operación (diseño)

> Diseño para aprobar antes de escribir el plan de tareas. Marcas: **[César]** decidido por César,
> **[Claude]** criterio de Claude (corregible). Plan general: [`PLAN_MULTI_MUNICIPIO.md`](PLAN_MULTI_MUNICIPIO.md) §3, §8 y fila F6.
> Relevamiento contra prod y el código: 2026-11-20.

## 1. Para qué

Hoy cada municipio ve solo lo suyo porque **el código** filtra cada consulta por municipio (F1-F2). F6 suma
una **segunda barrera dentro de la base de datos**: aunque una consulta se olvide el filtro, la base no
devuelve ni modifica filas de otro municipio. Es requisito de salida: **ningún segundo municipio carga datos
reales hasta terminar F1-F6** [César, 2026-10-23].

F6 trae además lo que quedó de operación: archivos en carpetas por municipio, procesos programados que informan
por municipio, restauración probada de una exportación, y dos ajustes de las cuentas internas.

**Objetivos**
- Una consulta sin filtro de municipio, ejecutada por la aplicación, solo ve y solo escribe filas del municipio
  de la request.
- Lo que opera un municipio sin pasar por la barrera es una lista corta, explícita y revisable.
- San Andrés funciona igual que hoy después del corte (smokes existentes en verde, mismos tiempos de respuesta).

**No objetivos**
- Importar un municipio dentro de la base compartida (traerlo desde otra base). Es otro proyecto.
- Proteger contra quien ya tiene la clave de la base o del usuario dueño: la barrera es contra errores de la
  aplicación, no contra el administrador de la base.
- Cambiar la API pública de Supabase: sigue cerrada como hoy.

**Lo que haría fallar a F6 aunque "ande"**
- Que la excepción (el acceso sin barrera) quede al alcance de cualquier parte del código.
- Que la barrera falle abierta: si no se sabe el municipio, **no se ve nada**, nunca todo.
- Que un corte sin vuelta atrás deje a San Andrés sin servicio.

## 2. Cómo está hoy (verificado en prod el 2026-11-20)

- El backend se conecta como `postgres` por el pooler de Supabase (Supavisor). `postgres` tiene `BYPASSRLS` y
  es dueño de las 143 tablas: hoy ninguna regla de la base lo frenaría.
- Las 143 tablas tienen RLS encendido y **ninguna política**: eso deja cerrada la API pública de Supabase
  (`anon`/`authenticated`). Debe seguir así.
- `municipio_tabla_clase` clasifica 103 tablas: 19 `global`, 27 `catalogo`, 50 `operativo`, 7 `mixta`. Las 40
  restantes son respaldos `_backup_*`.
- **`usuarios` está clasificada `operativo` pero admite `id_municipio` NULL** (las cuentas del super, F3). Para
  la barrera se trata como mixta.
- Las mixtas: `configuracion_general` (NULL = parámetro global), `municipio_tarea`, `super_admin_acceso`,
  `usuario_codigo_emergencia`, `usuario_invitacion`, `usuario_segundo_factor`, `usuario_segundo_factor_evento`.
- La sesión de base se abre (`get_db`) **antes** de saber el municipio; muchos guardados hacen varios commits en
  la misma request (el reclamo y después su historial), y 12 archivos abren sesiones propias fuera de la
  request (avisos, mails, autoasignación, exportación, vaciado).

## 3. Enfoques considerados

| | Cómo | A favor | En contra |
|---|---|---|---|
| **A. Dos usuarios de conexión** | Un usuario nuevo `zaris_app`, sin `BYPASSRLS` ni dueño, para todo lo que opera un municipio; `postgres` solo para una lista cerrada de procesos de sistema | La excepción queda encerrada en pocos lugares revisables; un olvido no la abre | Dos juegos de conexiones; más trabajo de corte |
| B. Un usuario con «modo sistema» | Un solo usuario sujeto a la barrera y una marca que el código prende para saltearla | Menos cambio | Cualquier parte del código puede prender la marca: protege menos contra el error que F6 quiere frenar |
| C. Pasar todo si no se sabe el municipio | La regla deja ver todo con el municipio vacío | Lo más fácil | Falla abierta: anula la barrera |

**Elegido: A** [César, 2026-11-20].

## 4. Diseño

### 4.1 Dos conexiones

- **`zaris_app`** (nuevo): `LOGIN`, sin `BYPASSRLS`, no dueño de nada. `SELECT/INSERT/UPDATE/DELETE` en las
  tablas de la aplicación, uso de secuencias y ejecución de funciones; privilegios por defecto para las tablas
  que creen las migraciones futuras. **Ningún permiso sobre los respaldos `_backup_*`.** [Claude]
- **`postgres`** (el de hoy): queda para las migraciones y para la lista de procesos de sistema (§4.4).
- El backend tiene dos motores: `engine_app` (el de siempre para requests y procesos) y `engine_sistema`. Este
  último **solo se importa desde un módulo** (`app/core/sistema.py`) que expone funciones con nombre propio por
  cada excepción; un barrido (`tools/barrido_sistema.py`, como los barridos de guards y de links) falla si
  `engine_sistema` o la conexión de sistema aparecen en cualquier otro archivo. [Claude]
- **Interruptor de corte:** `DB_BARRERA` (env). Con `false`, `engine_app` se conecta como `postgres` y todo
  funciona como hoy (el filtro del código sigue). Es la vuelta atrás del corte, sin redeploy de código. [Claude]
- **Credenciales:** el usuario y la clave de `zaris_app` los crea César en el SQL Editor de Supabase y los
  carga en Railway; nunca pasan por el repo ni por el chat (§4.8).

### 4.2 Reglas de la base (políticas)

Se generan desde `municipio_tabla_clase` en una migración (la misma clasificación que usan el vaciado y la
exportación), todas `TO zaris_app` — `anon` y `authenticated` siguen sin ninguna política. [Claude]

| Clase | Ver | Escribir |
|---|---|---|
| `catalogo`, `operativo` | `id_municipio` = municipio de la sesión | ídem (también el valor nuevo: no se puede mover una fila a otro municipio) |
| `mixta` (y `usuarios`) | municipio de la sesión **o** `id_municipio IS NULL` solo en `configuracion_general` (parámetros globales, de solo lectura para `zaris_app`) | municipio de la sesión. Las filas NULL de las demás mixtas (cuentas, segundo factor y registro del super) **no se ven ni se escriben** con `zaris_app`: van por sistema (§4.4) |
| `global` | todas | todas [Claude: la barrera separa municipios; las tablas globales no tienen municipio. Quién puede editarlas lo siguen controlando los guards del código, `require_super_admin`] |

- El municipio de la sesión es la variable `app.id_municipio`. **Sin variable, la comparación da NULL y no se ve
  nada** (falla cerrada).
- La política usa `(SELECT current_setting('app.id_municipio', true)::int)` para que Postgres la evalúe una
  vez por consulta y no por fila; se apoya en el índice por `id_municipio` que F1 dejó en cada tabla. [Claude]
- **Toda tabla nueva** se clasifica en `municipio_tabla_clase` (regla vigente, §10) y además **recibe su
  política en la misma migración**. Un control nuevo en el barrido de clasificación falla si una tabla
  clasificada no tiene política. [Claude]
- **Funciones y triggers:** corren con el usuario que ejecuta (`zaris_app`), así que también quedan bajo la
  barrera. El builder audita las funciones de la base (numeradores, SLA, `configuracion_general_clave_global`,
  disparadores de auditoría) para confirmar que solo leen filas del mismo municipio o globales, y que ninguna
  es `SECURITY DEFINER` sin necesidad.

### 4.3 Cómo se fija el municipio en cada sesión

- Un **listener `after_begin`** de SQLAlchemy aplica `set_config('app.id_municipio', <m>, true)` al empezar
  **cada transacción** de la sesión, leyendo el municipio de `session.info`. Así sobrevive a los commits
  intermedios de un mismo guardado (con `SET LOCAL` a secas se perdería en el primer commit) y es seguro con el
  pooler (la variable no queda pegada a la conexión). [Claude]
- **Quién fija el municipio en una request:**
  - Funcionario: `get_current_user` lo toma del claim `mun` del token **antes** de leer su cuenta, y valida que
    la cuenta sea de ese municipio (hoy ya lo compara). El super, con su municipio elegido, lo fija
    `municipio_actual` después de validar `X-Municipio`.
  - Vecino: `get_current_ciudadano`, del claim `mun`.
  - Público sin token: `municipio_de_origen` / `municipio_por_slug`.
  - Rutas con token en la URL: el municipio sale de la búsqueda del token (excepción de sistema, §4.4), y desde
    ahí sigue con la barrera.
- Si una ruta lee datos de un municipio antes de que se haya fijado, ve vacío: el error aparece en la prueba,
  no como fuga.
- **Procesos fuera de la request:** un helper `sesion_municipio(id_municipio)` abre la sesión con el municipio
  ya fijado. Los 12 archivos que hoy abren `AsyncSessionLocal()` pasan a usarlo, y los avisos en segundo plano
  reciben el municipio de quien los encola (el que encola siempre lo conoce). `por_cada_municipio` fija el
  municipio de cada vuelta. [Claude]

### 4.4 Lo único que corre sin barrera (procesos de sistema)

Funciones con nombre propio en `app/core/sistema.py`, cada una con la consulta mínima y sin devolver más de lo
necesario: [Claude]

1. **Cuentas del super por identificador:** en el login, buscar la cuenta del super (nivel 0, sin municipio)
   cuando el identificador no es de una cuenta del municipio de origen; y al crear o editar una cuenta de un
   municipio, el control de emails reservados (§1 de CLAUDE.md: un email de nivel 0 no lo puede usar ninguna
   cuenta de un municipio). Devuelve solo «existe / no existe» o el id. Las cuentas del municipio se buscan con
   la barrera de ese municipio.
2. **Sesión del super:** validar su token (leer su cuenta sin municipio), su segundo factor y sus códigos de
   emergencia, y escribir su registro de accesos (`super_admin_acceso`, que también tiene filas sin municipio).
3. **Tokens públicos** (encuesta, turno, reserva, pantalla del colero, invitación, activación): token →
   `id_municipio`, nada más. El resto de la request sigue con la barrera de ese municipio.
4. **Alta de un municipio:** lee del modelo y escribe en el nuevo en una sola transacción.
5. **Pantallas globales del super:** módulo «Municipios» (listado con conteos por municipio, tope de cuentas),
   parámetros globales (`configuracion_general` con municipio NULL) y su registro de accesos.

Todo lo que no está en esta lista corre con la barrera, **incluidos la exportación y el vaciado**: los dos
trabajan sobre un solo municipio, y la barrera garantiza que un zip nunca lleve filas de otro y que un vaciado
no pueda borrar fuera del suyo, aunque haya un error en la lista de tablas.

### 4.5 Archivos con carpeta por municipio

- Los archivos nuevos se guardan con prefijo `m{id_municipio}/` en cada bucket: adjuntos de reclamos (backoffice
  y app), de OT, documentos de trámites, foto de perfil y logo del municipio (hoy `municipio/{id}/…`). La
  exportación ya usa `m{id}/`. [Plan general §8]
- **Los existentes no se mueven** (son de San Andrés y sus rutas están en la base). [Plan general §8]
- Las validaciones de ruta que hoy esperan el formato viejo (`auth.py` y `vaciado.py` para la foto, y
  `storage.ruta_valida`) aceptan los dos formatos.

### 4.6 Procesos programados por municipio

Los cuatro procesos (encuestas, trámites, integridad de cuentas, datos demo) ya recorren municipio por municipio
(`por_cada_municipio`). Falta que **el resultado por municipio quede en el log del workflow** de GitHub Actions
(hoy la respuesta lo trae, pero el workflow no lo imprime) y que un municipio con error haga fallar el paso
con su nombre. [Claude]

### 4.7 Restauración de una exportación

- Herramienta aparte, **fuera de la aplicación** (`tools/restaurar_exportacion.py`): crea el esquema en una base
  Postgres vacía (desde un volcado solo de estructura) y carga el zip de un municipio en orden de dependencias,
  ajustando las secuencias. Corre con el usuario dueño de esa base nueva. [Claude]
- La exportación no lleva secretos (claves, segundo factor): después de restaurar, cada cuenta tiene que
  reiniciar su clave (decisión de F4+F5).
- **Prueba:** la exportación de San Andrés restaurada en una base local vacía, con conteos por tabla iguales a
  los del zip, y el backend levantado contra esa base mostrando el inicio de San Andrés.

### 4.8 Corte en prod

1. Todo en local primero: `zaris_app` en `zaris_dev`, políticas, smokes (§5).
2. César crea el usuario en el SQL Editor de Supabase (le paso el SQL sin la clave; la clave la elige él) y carga
   dos variables en Railway: usuario y clave de `zaris_app`. [Claude]
3. Migración de políticas por MCP. **No cambia nada todavía:** el backend sigue entrando como `postgres`, que
   las saltea.
4. Deploy con `DB_BARRERA=false`, verificación de que prod sigue igual.
5. Se pasa `DB_BARRERA=true` en Railway (reinicio del servicio, sin código nuevo). Verificación con un
   administrador y con la app del vecino: inicio, reclamos, trámites, turnos, un alta de reclamo, un link de
   encuesta.
6. Vuelta atrás: `DB_BARRERA=false` y reinicio.

### 4.9 Dos ajustes de las cuentas internas

Van en F6 porque tocan el mismo lugar (`get_current_user`) [Claude]:

1. **Clave temporal:** mientras la cuenta tenga la marca de cambio obligatorio, su sesión solo sirve para
   cambiar la clave, ver su propia cuenta y cerrar sesión; cualquier otra ruta responde 403 con un código que
   los clientes reconocen. El builder confirma antes que el login del shell y la app de agentes no pidan otra
   cosa mientras la marca está puesta (los dos ya llevan a la pantalla de cambio).
2. **Corte de sesiones:** la marca que hoy invalida las sesiones abiertas de los niveles 0 y 1 (al restablecer
   la clave o vincular la app) se exige a **todos los niveles**, y se pone también cuando un administrador
   restablece la clave de cualquier cuenta y cuando la persona cambia su clave. Al cambiar la propia clave se
   cortan las otras sesiones abiertas (por ejemplo, la app de agentes) y la respuesta trae una sesión nueva
   para la pantalla desde la que se cambió, así la persona no tiene que volver a entrar ahí.

## 5. Pruebas de cierre

- **Prueba de la barrera** (nueva, `smoke_barrera.py`, contra la base local con dos municipios): conectado como
  `zaris_app` con el municipio A, un `SELECT *` **sin filtro** de cada tabla `catalogo`/`operativo`/mixta
  devuelve solo filas de A; con el municipio sin fijar no devuelve nada; un INSERT o UPDATE con el municipio B
  es rechazado. Recorre todas las tablas desde `municipio_tabla_clase`, no una lista a mano.
- **Endpoint de prueba sin filtro** (solo local, con el filtro del código quitado a propósito): con dos
  municipios, la barrera igual frena (es la prueba que pide el plan general).
- **Todos los smokes existentes en verde con `DB_BARRERA=true`** (aislamiento, alta de municipio, vaciado,
  segundo factor, super admin, trámites, reclamos, turnos, encuestas, app del vecino).
- Tiempos: los endpoints del inicio y de los listados con la barrera, comparados contra los de hoy.
- Barrido de sistema en verde (§4.1) y barrido de políticas en verde (§4.2).
- Restauración de San Andrés (§4.7).

## 6. Fases propuestas [Claude]

| Fase | Contenido | Se cierra con |
|---|---|---|
| **F6.1** | Ajustes de cuentas (§4.9) | Smoke de cuentas; login del shell y app de agentes con clave temporal |
| **F6.2** | `zaris_app`, políticas, municipio por sesión, módulo de sistema, sesiones de segundo plano, en local | Prueba de la barrera + todos los smokes en verde con la barrera |
| **F6.3** | Corte en prod (§4.8) | Prod con `DB_BARRERA=true` y recorrido verificado |
| **F6.4** | Archivos con carpeta por municipio + logs de procesos por municipio | Un adjunto nuevo en `m1/…`; workflow con el resultado por municipio |
| **F6.5** | Restauración | San Andrés restaurado en base local vacía |

## 7. Lo que queda a criterio del builder

- Nombres exactos de las funciones de `sistema.py`, del helper de sesión y de las variables de Railway.
- Si las políticas se escriben una por operación o una `FOR ALL` con `USING` + `WITH CHECK`.
- Tamaño de cada pool (hoy 5 + 10 de desborde) y si el pool de sistema puede ser más chico; verificar el límite
  de conexiones del pooler de Supabase para un usuario nuevo.
- Formato del volcado de estructura para la restauración.

## 8. Por verificar al empezar

- Que Supavisor acepte el usuario nuevo (en el pooler el usuario va como `zaris_app.<ref>`) y en qué modo del
  pooler está conectado Railway hoy.
- Que ninguna función de la base sea `SECURITY DEFINER` o lea filas de otro municipio (§4.2).
- Que las migraciones nuevas sigan corriendo como `postgres` (MCP / SQL Editor) y no queden bajo la barrera.
