# Plan de implementación — IT-01 F1 + F2 (segmentación por municipio y municipio de la request)

> **Para quien lo ejecute (agente o persona):** sub-skill requerida: `superpowers:subagent-driven-development` (recomendada) o `superpowers:executing-plans`, tarea por tarea. Los pasos usan casillas (`- [ ]`) para seguir el avance.

**Objetivo:** que cada dato de ZARIS pertenezca a un municipio (`id_municipio NOT NULL` con FK) y que ninguna request de un funcionario, de un vecino o de una página pública lea o modifique datos de otro municipio. San Andrés tiene que seguir funcionando igual.

**Arquitectura:** F1 es la base de datos: una tabla de clasificación (`municipio_tabla_clase`) dice de qué clase es cada tabla, y desde ella las migraciones ponen `id_municipio NOT NULL`, una FK simple a `municipios` y **FK compuestas** `(id_municipio, x)`, para que la propia base rechace referencias entre municipios. F2 es el código: el municipio sale de un solo lugar por tipo de request (claim `mun` del JWT, origen de la request o slug para lo público), y se aplica en todos los routers con reglas fijas (R1-R11). Un barrido automático de las 370 rutas, con un municipio de aislamiento cargado en local, prueba que nada se filtra.

**Stack:** FastAPI + SQLAlchemy async (asyncpg), PostgreSQL 17 (local `zaris_dev` y Supabase), python-jose (JWT), httpx `ASGITransport` para los smokes in-process.

**Spec:** [`PLAN_MULTI_MUNICIPIO.md`](PLAN_MULTI_MUNICIPIO.md) (aprobado por César el 2026-10-24). Este plan cubre sus fases F1 y F2; F3 en adelante quedan afuera.

## Restricciones globales

- **Todo en local primero; prod se toca una sola vez** (Tarea 20), en la ventana que anuncie César. Se trabaja en la rama `it01-multi-municipio`; se puede pushear la rama (Railway y GitHub Pages solo despliegan `main`), pero **no se mergea a `main` antes de la Tarea 20**.
- **Sin `DROP` en las migraciones que van por MCP**: `apply_migration` rechaza cualquier sentencia con `DROP`. Se usa `CREATE OR REPLACE`, `ADD … IF NOT EXISTS` y `ALTER COLUMN … SET DEFAULT NULL` (en lugar de `DROP DEFAULT`). Todo lo que exige `DROP` va al **lote de limpieza** (al final), que corre César en el SQL Editor antes de F4.
- Datos separados del DDL (§21: `125` DDL, `125b` datos). Toda tabla nueva lleva `ENABLE ROW LEVEL SECURITY`. Todo INSERT a `configuracion_general` lleva `activo` y `tipo` explícitos.
- Números de migración: este plan usa 125, 125b, 125c, 125d y 126; **se renumeran al aplicarlas** si otra migración ocupó el número en el medio (§21).
- **Smokes SOLO LOCAL**: abortan si la base no es `zaris_dev`, el mail va en MOCK (`settings.RESEND_API_KEY = ""`) y las notificaciones push quedan capturadas.
- **Todo lo existente es del municipio 1** (San Andrés en prod, «Municipio Demo» `LPL` en local), incluidos los 8 usuarios con 377.
- Detalle o mutación por id de otro municipio → **404 con el mismo `detail` que un id inexistente**.
- El municipio **nunca** sale de un query param, del body ni de un header en F2 (el header `X-Municipio` del super administrador es de F3).
- Antes de cada commit: `grep -riE "h[u]sky" .` vacío y `pnpm typecheck` si el commit toca `web-app/`.

## Foco de revisión

Lo que el spec implica y es más probable que muerda a quien use el sistema, con la tarea que lo prueba:

1. **Un id de otro municipio en la URL** (`/reclamos/<id de B>`) tiene que dar 404, no 200 ni 403: barrido de la Tarea 7, todas las rutas.
2. **Un id de otro municipio en el body** (crear un reclamo con el tipo, el ciudadano o el agente de B) tiene que dar 422 y no crear nada. La FK compuesta lo frena en la base (Tarea 3), pero sin validar antes en el código sale un 500 (R4). Las pruebas de referencias cruzadas son las de la Tarea 7.
3. **Buscar un reclamo, una OT o una emergencia por número** tiene que encontrarlo con el formato viejo (`REC-2026-002982`) y con el nuevo (`REC-SAN-2026-002983`), y solo dentro del municipio propio: Tareas 2 y 9.
4. **Caches en memoria** (bbox del geocoding, identidad, subdominios): si la clave no incluye el municipio, B ve la configuración de A sin ningún error (R9). Lo prueban las Tareas 9 y 17.
5. **La sesión vieja después del corte** (token sin `mun`) tiene que dar 401 y mandar al login, sin quedar en bucle, en el shell, en los módulos React, en la PWA del vecino y en la app de agentes. Lo prueban la Tarea 6 (backend) y la Tarea 20 (navegador).

---

## Clasificación de tablas (fuente de `municipio_tabla_clase`)

Clases: `global` (sin municipio; si hoy tiene la columna, queda sin uso hasta el lote de limpieza) · `catalogo` (por municipio, se copia del modelo en F4) · `operativo` (por municipio) · `mixta` (`NULL` = valor global) · `legado` (sin uso en el código, se borra en el lote de limpieza).

| Clase | Tablas |
|---|---|
| global | `actividades`, `nacionalidades`, `tipo_representacion`, `tipos_representacion`, `tipos_activo`, `provincias`, `partidos`, `localidades`, `estado_reclamo`, `estado_ot`, `estado_evento`, `estado_reserva`, `emergencia_estado`, `tipo_usuario`, `modulos`, `municipios`, `tipo_documento`, `municipio_tabla_clase` |
| catalogo | `area`, `subarea`, `cargos`, `tipo_reclamo`, `tipo_prestacion`, `tipo_tramite`, `tipo_tramite_version`, `tipo_tramite_campo`, `tipo_tramite_estado`, `tipo_tramite_transicion`, `tipo_tramite_documento_requerido`, `tipo_tramite_aprobacion_requerida`, `emergencia_tipo`, `emergencia_subtipo`, `emergencia_organismo_derivacion`, `emergencia_canal_ingreso`, `emergencia_prioridad`, `servicios`, `lugares_atencion`, `espacios_agenda`, `agenda_clase`, `agenda_feriado`, `encuesta_plantilla`, `encuesta_pregunta`, `encuesta_opcion`, `equipos` |
| operativo | `agentes`, `usuarios`, `usuario_modulos`, `usuario_login_log`, `usuario_push_subscription`, `ciudadanos`, `ciudadano_credencial`, `ciudadano_canal_preferido`, `ciudadano_push_subscription`, `ciudadano_aviso`, `ciudadano_empresa`, `empresas`, `empresa_credencial`, `activos`, `reclamos`, `reclamo_historial`, `reclamo_adjuntos`, `ordenes_trabajo`, `ot_adjuntos`, `emergencia_evento`, `emergencia_log`, `emergencia_contacto_eventual`, `emergencia_atencion`, `turnos`, `turno_atencion`, `turno_llamado`, `historia_clinica_acceso`, `eventos`, `evento_reservas`, `evento_encargados`, `ocupaciones`, `espacio_agentes`, `disponibilidad_recurso`, `agente_novedad`, `ausencias_agente`, `conflictos_log`, `agenda_audit_log`, `equipo_agentes`, `tramite`, `tramite_movimiento`, `tramite_documento`, `tramite_firma`, `tramite_relacion`, `tramite_aprobacion`, `tipo_tramite_numerador`, `encuesta_envio`, `encuesta_respuesta`, `encuesta_respuesta_detalle`, `notificacion`, `numerador_municipio` |
| mixta | `configuracion_general` |
| legado | `reclamos_area`, `reclamos_subarea`, `reclamos_tipo` (cero referencias en `backend/app`), `emergencia_numerador` (lo reemplaza `numerador_municipio`), `equipo_usuarios` (solo existe en local) |

Las tablas `_backup_*` no se clasifican. **Regla nueva para `CLAUDE.md` §10 (Tarea 19):** toda tabla nueva lleva una fila en `municipio_tabla_clase` en la misma migración; si es de un municipio, nace con `id_municipio NOT NULL` y FK.

**`configuracion_general` en F1:** las 3 claves `vapid_*` pasan a globales (`id_municipio NULL`) y las otras 29 a municipio 1. `password_renovacion_dias` queda en el municipio 1 hasta F3, cuando exista el super administrador que la administre (si pasara ahora a global, nadie podría editarla desde Configuración → Sistema). El índice viejo `UNIQUE (clave)` queda hasta el lote de limpieza, así que en F1 y F2 **no se insertan claves nuevas** en otros municipios (un municipio sin la clave lee la global o ninguna: fail-closed).

---

## Fase F1 — Base de datos (local)

### Tarea 1: Verificador de F1, migración 125 (DDL nuevo) y 125b (clasificación y backfill)

**Archivos:**
- Crear: `backend/smoke_segmentacion_f1.py`
- Crear: `backend/migrations/125_segmentacion_municipio.sql`
- Crear: `backend/migrations/125b_segmentacion_municipio_datos.sql`

**Interfaces:**
- Produce: tabla `municipio_tabla_clase(tabla TEXT PK, clase TEXT CHECK (clase IN ('global','catalogo','operativo','mixta','legado')), nota TEXT)`; tabla `numerador_municipio(id_municipio INT FK, entidad TEXT CHECK (entidad IN ('reclamo','ot','emergencia')), anio INT, ultimo_numero INT NOT NULL, fecha_modificacion TIMESTAMPTZ DEFAULT NOW(), PK (id_municipio, entidad, anio))`; función `fn_siguiente_numero(p_mun INT, p_entidad TEXT, p_anio INT) RETURNS INT` (INSERT … ON CONFLICT DO UPDATE … RETURNING); tabla global `tipo_documento(id_tipo_documento SERIAL PK, codigo_pais CHAR(2), codigo VARCHAR(20), nombre VARCHAR(80), aplica_a VARCHAR(10) CHECK IN ('persona','empresa'), activo, fecha_alta, fecha_modificacion, UNIQUE (codigo_pais, codigo))`; columnas `municipios.subdominio VARCHAR(63)`, `municipios.codigo_pais CHAR(2)`, `municipios.zona_horaria VARCHAR(64) NOT NULL DEFAULT 'America/Argentina/Buenos_Aires'`, `municipios.direccion_base BOOLEAN NOT NULL DEFAULT FALSE`, `provincias.codigo_pais CHAR(2) NOT NULL DEFAULT 'AR'`, `ciudadanos.doc_pais` y `empresas.doc_pais CHAR(2) NOT NULL DEFAULT 'AR'`, e `id_municipio INTEGER` (nullable) en `configuracion_general`, `reclamo_historial`, `usuario_login_log`, `ciudadano_empresa`, `lugares_atencion`, `servicios`.
- `smoke_segmentacion_f1.py` acepta `--foto <ruta.json>` (guarda conteos por tabla) y `--comparar <ruta.json>` (verifica conteos iguales); sin argumentos corre los chequeos de abajo.

- [ ] **Paso 1: Escribir el verificador.** Chequeos (cada uno imprime OK/FALLA y el script sale con 1 si alguno falla):
  - `toda_tabla_clasificada`: toda tabla de `public` que no empiece con `_backup_` tiene fila en `municipio_tabla_clase`; toda fila no `legado` corresponde a una tabla existente.
  - `id_municipio_completo`: toda tabla `catalogo`/`operativo` tiene `id_municipio` NOT NULL, con FK a `municipios` y 0 filas en NULL.
  - `sin_377`: `SELECT count(*) FROM usuarios WHERE id_municipio = 377` = 0.
  - `config_dividida`: `configuracion_general` con `id_municipio IS NULL` = exactamente las 3 `vapid_*`; el resto con 1.
  - `municipio_base`: un único municipio con `direccion_base`, que es el 1, con `subdominio = 'sanandres'` y `codigo_pais = 'AR'`; el 2 con `activo = false`.
  - `unicos_compuestos`: existen los índices de la Tarea 2.
  - `numeracion_nueva`: dentro de una transacción con ROLLBACK, insertar un reclamo mínimo y una OT del municipio 1 → `nro_reclamo ~ '^REC-' || codigo_corto || '-[0-9]{4}-[0-9]{6}$'` y el sufijo es `ultimo_numero` del año + 1 (ídem OT y emergencia).
  - `fk_compuesta`: dentro de una transacción con ROLLBACK, crear un municipio temporal e insertar en él un reclamo con un `id_tipo_reclamo` del municipio 1 → `ForeignKeyViolation`.
- [ ] **Paso 2: Sacar la foto y correr el verificador antes de migrar.** `cd backend; $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_segmentacion_f1.py --foto $env:TEMP\f1_conteos_antes.json` y después sin argumentos. Esperado: la foto se guarda y los chequeos FALLAN (`municipio_tabla_clase` no existe).
- [ ] **Paso 3: Escribir `125` (solo DDL, re-aplicable):** las tablas, la función y las columnas de las Interfaces. Además, índices únicos parciales: `municipios(subdominio) WHERE subdominio IS NOT NULL`, `municipios(direccion_base) WHERE direccion_base`, `municipios(upper(codigo_corto)) WHERE codigo_corto IS NOT NULL`, y CHECK de formato del subdominio `^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$` dentro de `DO $$ IF NOT EXISTS (pg_constraint) $$`. RLS en las 3 tablas nuevas.
- [ ] **Paso 4: Escribir `125b` (datos), en este orden:**
  1. Una aserción que aborte la migración si alguna tabla catalogo/operativo tiene `id_municipio` fuera de `{NULL, 1, 377}`.
  2. Las filas de `municipio_tabla_clase` (tabla de arriba, `ON CONFLICT DO UPDATE`).
  3. `municipios`: el 1 con `subdominio='sanandres'`, `direccion_base=TRUE` y `codigo_pais='AR'`; el 2 con `activo=FALSE` y `codigo_pais` derivado de `pais` (`Venezuela`→`VE`, lo demás→`AR`).
  4. `tipo_documento`: AR `DNI` y `PASAPORTE` (persona; son los dos que acepta `schemas/buc.py`), AR `CUIL` (persona) y AR `CUIT` (empresa).
  5. Backfill: `DISABLE TRIGGER` de `trg_ciudadanos_modif`, `trg_empresas_modif`, `trg_usuarios_modif`, `trg_tipo_reclamo_sla_sync`, `emergencia_log_no_update` e `historia_clinica_acceso_no_update` (los dos últimos lanzan una excepción ante cualquier UPDATE; los otros cambiarían fechas o datos). Después, un `DO` que recorre las tablas `catalogo`/`operativo` y ejecuta `UPDATE … SET id_municipio = 1 WHERE id_municipio IS DISTINCT FROM 1`. Al final, `ENABLE TRIGGER` de los seis.
  6. `configuracion_general`: `id_municipio = 1` para todas las claves salvo `vapid_%`.
  7. `numerador_municipio` del municipio 1: reclamos y OT con el máximo del sufijo numérico por año de `nro_reclamo ~ '^REC-[0-9]{4}-[0-9]+$'` y `nro_ot ~ '^OT-[0-9]{4}-[0-9]+$'`; emergencias, copiando `emergencia_numerador`.
- [ ] **Paso 5: Aplicar en local.** Con `psql -v ON_ERROR_STOP=1 -1 -f` cada archivo (una transacción por archivo). Esperado: sin errores; re-aplicar los dos no cambia nada.
- [ ] **Paso 6: Verificador parcial.** Esperado: OK en `toda_tabla_clasificada`, `sin_377`, `config_dividida` y `municipio_base`; los demás siguen FALLANDO hasta las Tareas 2 y 3.
- [ ] **Paso 7: Commit.** `git add backend/smoke_segmentacion_f1.py backend/migrations/125_segmentacion_municipio.sql backend/migrations/125b_segmentacion_municipio_datos.sql` y `git commit -m "feat(it-01): clasificacion de tablas y backfill de id_municipio (migs 125, 125b)"`.

### Tarea 2: Migración 125c — NOT NULL, FK, únicos compuestos y numeración con código

**Archivos:**
- Crear: `backend/migrations/125c_segmentacion_municipio_restricciones.sql`

**Interfaces:**
- Consume: `municipio_tabla_clase`, `numerador_municipio`, `fn_siguiente_numero` (Tarea 1).
- Produce: los formatos de número `REC-<codigo_corto>-<AAAA>-<NNNNNN>`, `OT-<codigo_corto>-<AAAA>-<NNNNNN>` y `EM-<codigo_corto>-<AAAA>-<NNNNNN>` (6 dígitos, contador por municipio, entidad y año). Las tablas `catalogo`/`operativo` quedan con **`DEFAULT 1` temporal**, que anula la migración 126 (Tarea 19).

- [ ] **Paso 1: Escribir `125c`:**
  - Un `DO` sobre las tablas `catalogo`/`operativo`: `ALTER COLUMN id_municipio SET NOT NULL`, `SET DEFAULT 1`; FK `fkmun_<tabla>` a `municipios(id_municipio)` si la columna no tiene ya una; índice `ix_<tabla>_mun (id_municipio)` si no existe.
  - `configuracion_general` (clase `mixta`): FK a `municipios` y sin NOT NULL (`NULL` = global).
  - `municipios.codigo_pais SET NOT NULL`.
  - Únicos compuestos (coexisten con los globales viejos hasta el lote de limpieza): `ciudadanos (id_municipio, doc_pais, doc_tipo, doc_nro)`, `ciudadanos (id_municipio, cuil)`, `empresas (id_municipio, doc_pais, cuit)`, `usuarios (id_municipio, username)`, `reclamos (id_municipio, nro_reclamo)`, `ordenes_trabajo (id_municipio, nro_ot)`, `emergencia_evento (id_municipio, numero_operativo)`, `activos (id_municipio, codigo_unico)`, `agenda_feriado (id_municipio, fecha)`, `emergencia_canal_ingreso`, `emergencia_prioridad` y `emergencia_organismo_derivacion (id_municipio, codigo)`, `configuracion_general UNIQUE NULLS NOT DISTINCT (id_municipio, clave)`.
  - `CREATE OR REPLACE FUNCTION fn_generar_nro_reclamo / fn_generar_nro_ot / fn_generar_numero_emergencia`: si el número viene vacío, `fn_siguiente_numero(NEW.id_municipio, <entidad>, año de NOW())` y el `codigo_corto` del municipio. Si el municipio no tiene `codigo_corto`, `RAISE EXCEPTION 'El municipio % no tiene codigo_corto'`. El año se sigue tomando de `NOW()`, como hoy (la zona horaria por municipio es de F5b).
- [ ] **Paso 2: Aplicar en local** (`psql -1`, como en la Tarea 1).
- [ ] **Paso 3: Verificador.** Esperado: OK en todo salvo `fk_compuesta`.
- [ ] **Paso 4: Commit** de `125c` con el mensaje `feat(it-01): id_municipio NOT NULL, unicos por municipio y numeracion con codigo (mig 125c)`.

### Tarea 3: Migración 125d — FK compuestas entre tablas del mismo municipio

**Archivos:**
- Crear: `backend/migrations/125d_segmentacion_municipio_fk_compuestas.sql`

**Interfaces:**
- Produce: por cada FK simple declarada entre dos tablas `catalogo`/`operativo`, una FK compuesta `(id_municipio, col) → padre(id_municipio, col_ref)`. Consecuencia para F2 (regla R1): **un JOIN por una FK declarada no puede cruzar municipios, así que alcanza con filtrar la tabla raíz de la consulta.**

- [ ] **Paso 1: Escribir `125d`** como un `DO` que recorre `pg_constraint` (`contype = 'f'`, una sola columna, hija y padre `catalogo`/`operativo`, **padre distinto de `usuarios`**: las columnas de auditoría `id_usuario_*` apuntan a usuarios, y el super administrador de F3 no tiene municipio). Para cada FK:
  - si no existe, crea `CREATE UNIQUE INDEX uqm_<padre>_<col_ref> ON <padre>(id_municipio, <col_ref>)`;
  - crea `fkm_<nombre de la FK original>` (truncado a 63 caracteres) con `NOT VALID` y después `VALIDATE CONSTRAINT`.
  - Sin `ON DELETE`: el borrado lo sigue gobernando la FK simple original. Y no hay borrados físicos, salvo el vaciado de F4, que borra todo un municipio.
  - Al final, `RAISE NOTICE` con la cantidad de FK creadas.
- [ ] **Paso 2: Aplicar en local.** Esperado: el aviso con N > 0 y sin errores (todo es del municipio 1, así que valida).
- [ ] **Paso 3: Verificador completo.** Esperado: todo OK, incluido `fk_compuesta`.
- [ ] **Paso 4: Commit** de `125d` con el mensaje `feat(it-01): FK compuestas por municipio (mig 125d)`.

### Tarea 4: Cierre de F1 — San Andrés igual que antes

**Archivos:** ninguno nuevo (si un smoke existente se rompe, corregir el código que lo rompe).

- [ ] **Paso 1: Conteos.** `python smoke_segmentacion_f1.py --comparar $env:TEMP\f1_conteos_antes.json`. Esperado: cantidad de filas por tabla idéntica.
- [ ] **Paso 2: Smokes existentes** con uvicorn local o in-process, según cada uno: `smoke_auditoria_reclamos.py`, `smoke_sla_asignacion_general.py`, `smoke_tramites_ciclo_vida.py`, `smoke_tramites_resultado_final.py`, `smoke_publico_auth.py`, `smoke_alta_un_paso.py`, `smoke_publico_turnos.py`, `smoke_publico_entradas.py`, `smoke_atenciones_historia.py`, `smoke_bi_atencion.py`, `smoke_cuentas_funcionario.py`, `smoke_orden_listados.py`, `..\smoke_agenda.ps1`, `..\smoke_emergencias.ps1`. Esperado: todos en verde. Lo que falle por el formato de número nuevo se corrige en el smoke, no en la migración.
- [ ] **Paso 3: Commit** de las correcciones de smokes, si las hubo, con el mensaje `test(it-01): smokes al dia con la numeracion por municipio`.

---

## Fase F2 — Municipio de la request

### Reglas de filtrado (las aplican las Tareas 8 a 18)

- **R1.** Toda sentencia sobre una tabla `catalogo`/`operativo` filtra la **tabla raíz** con `<alias>.id_municipio = :id_municipio`. Los JOIN por FK declarada no necesitan filtro propio (Tarea 3); las subconsultas y los EXISTS sobre tablas no unidas por FK sí.
- **R2.** Todo INSERT en una tabla `catalogo`/`operativo` lleva `id_municipio` explícito: el de la request o el de la fila padre. Lo mismo vale para el ORM (`Model(..., id_municipio=...)`). Se borra el `default=1`/`default=377` de `app/models/*`.
- **R3.** Detalle o mutación por id: `WHERE <pk> = :id AND id_municipio = :id_municipio`. Si no hay fila, 404 con el mismo `detail` que un id inexistente.
- **R4.** Todo id que llega en el body o en la query (`id_tipo_reclamo`, `id_agente`, `id_ciudadano`, `id_espacio`, `id_subarea`, `id_prestacion`, etc.) se valida contra el municipio **antes** de usarlo. Si no pertenece, 422 con el texto `"<entidad> inexistente"`. Sin esa validación la FK compuesta lo frena igual, pero con un 500.
- **R5.** Se quita `id_municipio` de los query params, de los schemas de entrada (`Create`/`Update`/`Request`) y de las columnas editables de `admin_tablas` (`TABLE_CONFIG`, también `equipos`). Los schemas de salida pueden seguir mostrándolo.
- **R6.** Se quitan las tolerancias `OR id_municipio IS NULL` (38), los `or 1`, los `= 1` fijos, `id_municipio: int = 1` y `ID_MUNICIPIO_DEFAULT`.
- **R7.** Las funciones de `services/` que leen o escriben datos reciben `id_municipio: int` como argumento keyword-only y sin default…
- **R8.** …salvo los services disparados por una entidad (`id_reclamo`, `id_ot`, `id_turno`, `id_tramite`, `id_evento`): esos toman el municipio de la fila de esa entidad y no lo reciben. Así no cambia la firma de lo que llaman los background tasks.
- **R9.** Toda lectura de `configuracion_general` pasa por `leer_config` (Tarea 6). Todo cache en memoria lleva el municipio en la clave.
- **R10.** Las tablas `global` no se filtran.
- **R11.** Rutas públicas: con token en la URL (encuesta, turno, reserva, pantalla), el municipio sale de la fila del token; sin token, de `municipio_de_origen`, o de `municipio_por_slug` si la ruta recibe `?m=`.

### Tarea 5: Municipio de aislamiento (fixture local)

**Archivos:**
- Crear: `backend/seed_municipio_aislamiento.py`

**Interfaces:**
- Produce, en `zaris_dev`, un municipio con `nombre='AISLAB Municipio de Aislamiento'`, `codigo_corto='AIS'`, `subdominio='aislamiento'`, `codigo_pais='AR'`, al menos una fila de cada tabla de la lista `COBERTURA` del script y **la marca `AISLAB` en todo campo de texto**.
- Usuarios: `admin.b@aislamiento.test` (nivel 1) y `super.b@aislamiento.test` (nivel 2), con agente en una subárea de B. Además, **dos cuentas con el mismo email `doble@aislamiento.test`**: una en el municipio 1 (nivel 5) y otra en B (nivel 1). Clave dev `123456`.
- Vecino de B: DNI `97000001` con credencial activada y clave `123456`. Empresa de B: un CUIT válido generado con el dígito verificador de `schemas/buc.py`.
- Función `async def ids_aislamiento(db) -> dict[str, int]` (tabla → un id de B), que importa el smoke de la Tarea 7. Busca por la marca y no guarda archivos.

- [ ] **Paso 1: Escribir el script.**
  - Guarda `zaris_dev` (como los smokes).
  - Idempotente: si el municipio `aislamiento` ya existe, imprime `ids_aislamiento` y sale.
  - Helper `async def clonar(db, tabla: str, id_origen: int, cambios: dict) -> int`: lee una fila del municipio 1, arma el INSERT con todas las columnas salvo la PK, aplica `cambios`, antepone `AISLAB ` a los textos libres, pone `NULL` en tokens y números (los regeneran el default o el trigger) y devuelve el id nuevo.
  - Clona, en orden de dependencias:
    - catálogos: área, subárea, cargo, tipo de reclamo, los 5 catálogos de emergencias, prestación, espacio, lugar de atención, servicio, clase y feriado de agenda, plantilla de encuesta con pregunta y opción, equipo;
    - un tipo de trámite publicado con su versión, campos, estados, transiciones, documento requerido y numerador, mapeando los ids de la versión;
    - personas: usuarios, agentes, ciudadano con credencial y canal preferido, empresa con su vínculo;
    - operativo: reclamo con historial y OT, emergencia con log y contacto, turno con atención y llamado, evento con reserva, encargado y ocupación, trámite con movimiento, envío de encuesta con respuesta, notificación, aviso al ciudadano, disponibilidad y novedad de agente.
- [ ] **Paso 2: Correrlo.** `python seed_municipio_aislamiento.py`. Esperado: lista `tabla → id`; una segunda corrida no crea nada.
- [ ] **Paso 3: Verificación independiente.** Por SQL, cada tabla de `COBERTURA` tiene ≥ 1 fila con el `id_municipio` de B, y `reclamos` de B tiene `nro_reclamo` con `REC-AIS-`.
- [ ] **Paso 4: Commit** del script con el mensaje `test(it-01): municipio de aislamiento para los smokes`.

### Tarea 6: Núcleo — JWT con municipio, origen, slug y configuración por municipio

**Archivos:**
- Crear: `backend/app/core/municipio.py`
- Crear: `backend/app/core/config_municipio.py`
- Modificar: `backend/app/core/auth.py` (`create_access_token`, `crear_token_ciudadano`, `get_current_user`, `get_current_ciudadano`)
- Modificar: `backend/app/api/routes/auth.py` (`_buscar_usuario_login`, `login`, recuperación de clave y «olvidé mi usuario», y el registro en `usuario_login_log`)
- Modificar: `backend/app/api/routes/publico_auth.py` (login, activación, recuperación y alta por agente del vecino)
- Crear: `backend/smoke_municipio_request.py`

**Interfaces:**
- Consume: fixture B (Tarea 5).
- Produce:
  - claim **`mun: int`** en los tokens de agente y de vecino. `create_access_token({"sub": str(id_usuario), "mun": id_municipio})`; `crear_token_ciudadano(id_ciudadano: int, id_municipio: int, expira_dias: int | None = None) -> str`.
  - `get_current_user` y `get_current_ciudadano` exigen `mun` (sin el claim, 401 con `detail="Sesión vencida. Volvé a ingresar."`); verifican que `mun` coincida con el `id_municipio` de la fila en la base y, **si la request trae header `Origin`**, que `mun` sea igual a `municipio_de_origen(request)` (si no, 401). Un `Origin` sin prefijo resuelve al municipio base, así que el token de B usado desde `zge.zaris.com.ar` da 401; sin `Origin` (curl, smokes, procesos) no se compara. El dict que devuelven incluye `id_municipio`.
  - `municipio.py`:
    - `def subdominio_de_origen(origin: str | None) -> str | None`: pura; matchea `^(?P<sub>[a-z0-9-]+)\.(zge|vecinos|agentes)\.zaris\.com\.ar$` sobre el hostname en minúsculas.
    - `async def municipio_de_origen(request: Request, db: AsyncSession = Depends(get_db)) -> int`: un subdominio desconocido o inactivo da 404 `"Municipio no encontrado"`; sin subdominio (sin `Origin`, `zge.zaris.com.ar`, `cesarzeta.github.io`, `localhost`), el municipio con `direccion_base`; si no hay ninguno, 503.
    - `async def municipio_por_slug(db: AsyncSession, slug: str) -> dict`: devuelve `{id_municipio, nombre, slug}` por `codigo_corto` entre los activos; 404 si no existe. Reemplaza al `_resolver_municipio` de `publico_alta.py`.
    - `async def municipio_actual(current_user: dict = Depends(get_current_user)) -> int`: **el único punto que F3 modifica para el super administrador.**
    - `async def municipio_vecino(ciudadano: dict = Depends(get_current_ciudadano)) -> int`.
    - Cache de subdominio → id con TTL de 60 s.
  - `config_municipio.py`:
    - `async def leer_config(db: AsyncSession, clave: str, id_municipio: int | None) -> str | None`: la fila activa del municipio y, si no hay, la global (`id_municipio IS NULL`), con `ORDER BY id_municipio NULLS LAST LIMIT 1`.
    - `async def guardar_config(db: AsyncSession, clave: str, valor: str, id_municipio: int) -> bool`: UPDATE solo de la fila del municipio; devuelve `False` si no existe (en F2 no se insertan claves, ver la clasificación).
  - Login de agente: la búsqueda por email o DNI se restringe a `usuarios.id_municipio = municipio_de_origen` (y la de `ciudadanos`/`agentes` del DNI, también). Login de vecino: DNI dentro del municipio de origen.
- [ ] **Paso 1: Escribir los tests en `smoke_municipio_request.py`:**
  - `test_subdominio_de_origen`: `"https://aislamiento.zge.zaris.com.ar"` → `"aislamiento"`; `"https://AISLAMIENTO.vecinos.zaris.com.ar"` → `"aislamiento"`; `"https://zge.zaris.com.ar"`, `"https://cesarzeta.github.io"`, `"http://localhost:8080"`, `None` y `"basura"` → `None`.
  - `test_token_sin_mun_401`: un token firmado sin `mun` en `GET /api/v1/auth/me` → 401 y `detail == "Sesión vencida. Volvé a ingresar."`.
  - `test_login_mismo_email`: login de `doble@aislamiento.test` sin `Origin` → token con `mun = 1`; con `Origin: https://aislamiento.zge.zaris.com.ar` → `mun` = id de B; en los dos casos `/auth/me` devuelve el `id_municipio` correspondiente.
  - `test_token_de_b_con_origen_base`: el token de `admin.b` con `Origin: https://zge.zaris.com.ar` → 401; sin `Origin` → 200.
  - `test_subdominio_desconocido`: login con `Origin: https://noexiste.zge.zaris.com.ar` → 404 `"Municipio no encontrado"`.
  - `test_vecino`: login del DNI `97000001` sin `Origin` → 401 (no existe en el municipio base); con el `Origin` de B → 200 y `mun` = B.
  - `test_leer_config`: `leer_config(db, "vapid_public_key", <B>)` devuelve la global; `leer_config(db, "municipio_nombre", <B>)` → `None`; `leer_config(db, "municipio_nombre", 1)` → el nombre del municipio 1.
- [ ] **Paso 2: Correr los tests.** `python smoke_municipio_request.py`. Esperado: FALLAN (`app.core.municipio` no existe).
- [ ] **Paso 3: Implementar** las Interfaces de arriba, y que el registro de login escriba `usuario_login_log.id_municipio`.
- [ ] **Paso 4: Correr los tests otra vez** y además `smoke_publico_auth.py` y `smoke_cuentas_funcionario.py`. Esperado: todo en verde.
- [ ] **Paso 5: Marcador para OpenAPI.** En `GET /auth/me`, `responses={401: {"description": "Sesión sin municipio: volver a ingresar"}}`. Es el marcador de deploy de la Tarea 20.
- [ ] **Paso 6: Commit** con el mensaje `feat(it-01): municipio en el JWT, por origen y por slug; configuracion por municipio`.

### Tarea 7: Barrido de aislamiento (falla al principio y es la prueba de cierre de F2)

**Archivos:**
- Crear: `backend/smoke_aislamiento.py`

**Interfaces:**
- Consume: `ids_aislamiento` (Tarea 5) y las cuentas de la fixture.
- CLI: `python smoke_aislamiento.py [--rutas <prefijo>] [--solo-get]`. Sale con 1 si hay FALLAS, agrupadas por router.

- [ ] **Paso 1: Escribir el barrido:**
  - Recorre `app.routes` (rutas `APIRoute`). Arma los path params con `PARAM_A_TABLA` (por ejemplo `id_reclamo → reclamos`, `numero → tramite.numero_expediente`, `tabla` → cada clave de `TABLE_CONFIG` con su id de B). **Un parámetro sin mapear es una FALLA** («ruta sin cubrir»), salvo que la ruta esté en `SALTEAR` con su motivo (salud, OpenAPI, `/demo/*` con token de dispatcher, rutas con token público, que se prueban aparte).
  - **GET como `admin` del municipio 1**, con los ids de B y `?id_municipio=<B>` agregado: el status tiene que ser 403, 404 o 2xx, y **ninguna respuesta puede contener `AISLAB`**.
  - **Control positivo como `admin.b`**: el detalle de reclamo, OT, turno, evento, trámite, emergencia, ciudadano, empresa y usuario de B → 200 y contiene `AISLAB`. Prueba que la fixture y el mapeo andan.
  - **Mutaciones con body válido**, como admin del municipio 1 contra ids de B. Lista `MUTACIONES` de las 20 críticas: editar y cambiar estado de reclamo, tomar y cambiar estado de OT, estado de turno, operar trámite, acciones de emergencia, editar ciudadano, empresa y usuario, permisos de usuario, reserva de evento, ocupación, disponibilidad, novedad, configuración del sistema, identidad. Cada una tiene que dar 403, 404 o 422, y el **checksum de B** queda igual (`md5(string_agg(t::text, '|' ORDER BY <pk>))` por tabla `catalogo`/`operativo` filtrada por B, antes y después de todo el barrido).
  - **Referencias cruzadas en el body**, como admin del municipio 1: crear un reclamo con `id_tipo_reclamo` de B, con `id_ciudadano` de B, una OT con un agente de B, un turno con una prestación de B y una reserva con un ciudadano de B → 422 y la cantidad de filas del municipio 1 no cambia.
  - **Vecino**: el token del vecino de B contra `/publico/reclamos/<id del municipio 1>` → 404. El token del vecino del municipio 1 con el `Origin` de B → 401.
  - **Públicas sin token**: `GET /publico/identidad-municipio` con el `Origin` de B → el nombre de B; sin `Origin` → el del municipio 1.
- [ ] **Paso 2: Correrlo.** `python smoke_aislamiento.py`. Esperado: FALLA en casi todos los routers. Guardar el resumen en el scratchpad como línea de base.
- [ ] **Paso 3: Commit** con el mensaje `test(it-01): barrido de aislamiento entre municipios`.

### Tareas 8 a 18: aplicar las reglas por módulo

Todas siguen la misma secuencia; cada tarea lista sus archivos, sus smokes y lo propio del módulo. **Antes de tocar un módulo, cargar su skill** (`modulo-<nombre>`), como manda `CLAUDE.md`.

- [ ] **Paso 1:** `python smoke_aislamiento.py --rutas <prefijos de la tarea>`. Esperado: FALLAS (la línea de base de la Tarea 7).
- [ ] **Paso 2:** aplicar R1-R11 en los archivos de la tarea, cambiando también los services que llama según R7 y R8, y los consumidores de esos services en otros archivos.
- [ ] **Paso 3:** `python smoke_aislamiento.py --rutas <prefijos>`. Esperado: 0 FALLAS en esos prefijos.
- [ ] **Paso 4:** los smokes del módulo. Esperado: en verde.
- [ ] **Paso 5:** `grep -nE "id_municipio IS NULL|id_municipio: int = 1|or 1\b" <archivos de la tarea>` sin resultados.
- [ ] **Paso 6:** commit con el mensaje `feat(it-01): <módulo> por municipio`.

| Tarea | Prefijos de ruta | Archivos | Smokes | Propio del módulo |
|---|---|---|---|---|
| **8 — BUC y cuentas** | `/api/v1/buc` | `routes/buc.py`, `services/cuenta_zaris.py`, `services/cuenta_vecino.py`, `schemas/buc.py`, `models/buc.py` | `smoke_cuentas_funcionario.py`, `smoke_orden_listados.py` | La búsqueda por DNI, CUIL, CUIT y teléfono dentro del municipio. El alta de ciudadano o empresa toma el municipio de la request, no de la ficha (`buc.py:597/664/812`, `cuenta_zaris.py:116`). La cuenta ZARIS nace en el municipio de la ficha. |
| **9 — Reclamos** | `/api/v1/reclamos` (incluye `/{id_reclamo}/adjuntos`), `/api/v1/activos`, `/api/v1/geo` | `routes/reclamos.py`, `routes/reclamo_adjuntos.py`, `routes/activos.py`, `routes/geo.py`, `services/geo_limite.py`, `models/reclamos.py`, `models/activos.py` | `smoke_auditoria_reclamos.py`, `smoke_sla_asignacion_general.py` | `reclamos.py` no tiene hoy ninguna referencia a `id_municipio`. El insert de `reclamo_historial` lleva el municipio. La búsqueda por número acepta los dos formatos (Foco 3). `geo.py::_bbox_municipio()` pasa a `_bbox_municipio(id_municipio: int)`, con cache por municipio, y el contorno de `services/geo_limite.py` igual. Test directo (Foco 4): con el bbox del municipio 1 cambiado por UPDATE dentro del test, `_bbox_municipio(1)` devuelve el cambiado y `_bbox_municipio(<B>)` el de respaldo, aunque se llamen seguidas. |
| **10 — OT** | `/api/v1/ot` (incluye `/{id_ot}/adjuntos`) | `routes/ordenes_trabajo.py`, `routes/ot_adjuntos.py`, `services/autoasignacion.py` | `smoke_sla_asignacion_general.py`, `smoke_auditoria_reclamos.py` | La autoasignación reparte solo entre agentes del municipio del reclamo (R8). Los guards de subárea (`_subarea_forzada_supervisor`, `_validar_scope_supervisor_ot`) siguen igual. |
| **11 — Emergencias** | `/api/v1/emergencias`, `/api/v1/publico/emergencias` | `routes/emergencias.py`, `routes/publico_emergencias.py`, `services/guardia.py` | `..\smoke_emergencias.ps1` | Los catálogos se buscan por `codigo` dentro del municipio. `emergencias.py` fija la nacionalidad en 1 (global, queda). El botón de pánico del vecino crea el evento en el municipio del token. |
| **12 — Agenda y Entradas** | `/api/v1/agenda` (incluye `/agenda/espacios` y `/agenda/publico`) | `routes/agenda_v2.py`, `agenda_espacios.py`, `agenda_disponibilidad.py`, `agenda_novedades.py`, `agenda_publico.py`, `services/agenda.py`, `schemas/agenda_v2.py`, `models/agenda.py`; `web-app/src/modules/agenda/` (dejar de mandar `id_municipio` en `agendaApi.ts`, `RecursoPicker`, `EventoSearch`, `OcupacionModal`, `EventoModal`, hooks y tipos) | `..\smoke_agenda.ps1`, `smoke_publico_entradas.py` | Tiene 9 query params `id_municipio: int = 1` (R5). `disponibilidad_efectiva` y su versión batch reciben el municipio (R7). |
| **13 — Turnos** | `/api/v1/turnos` (incluye `/turnos/publico`) | `routes/turnos.py`, `routes/turnos_publico.py`, `schemas/turnos.py`, `services/historia_clinica.py` | `smoke_publico_turnos.py`, `smoke_atenciones_historia.py` | La pantalla del colero y la reserva pública por token: el municipio sale de la fila del token (R11). La historia clínica se lee por `id_area_salud` del municipio vía `leer_config`. |
| **14 — Trámites** | `/api/v1/tramites` (salvo las rutas de mantenimiento, Tarea 18), `/api/v1/admin/tramites` | `routes/tramites.py`, `tramites_admin.py`, `tramites_mantenimiento.py`, `services/tramites/*`, `schemas/tramites.py`, `models/tramites.py` | `smoke_tramites_ciclo_vida.py`, `smoke_tramites_resultado_final.py` | Ya tiene la columna completa: hay que quitar las 7 tolerancias y los `= 1`. El numerador ya es por municipio. La retención, la purga y el desistimiento leen sus plazos por municipio (R9). |
| **15 — Encuestas, notificaciones y push** | `/api/v1/admin/encuestas` (salvo el dispatcher, Tarea 18), `/api/v1/publico/encuesta`, `/api/v1/notificaciones`, `/api/v1/auth/push`, `/api/v1/publico/push` | `routes/encuestas_admin.py`, `encuestas_publico.py`, `notificaciones.py`, `usuario_push.py`, `publico_push.py`; `services/encuestas_service.py`, `notificaciones.py`, `push.py`, `avisos.py`, `email.py`; `models/encuestas.py`, `models/usuario_push.py`, `schemas/encuestas.py` | `smoke_publico_perfil_avisos.py` | Fuera `ID_MUNICIPIO_DEFAULT = 1` y las 12 tolerancias. Las claves VAPID se leen como globales. El nombre del municipio que va en los mails sale del municipio destinatario (R8). |
| **16 — Portal del vecino** | `/api/v1/publico` (salvo `emergencias`, `encuesta`, `push` e `identidad-municipio`, de las Tareas 11, 15 y 17) | `routes/publico_alta.py`, `publico_portal.py`, `publico_perfil.py`, `publico_avisos.py`, `publico_reclamos.py`, `publico_reclamos_adjuntos.py`, `publico_turnos_vecino.py`, `publico_entradas_vecino.py`; `models/ciudadano_credencial.py`, `schemas/publico_alta.py` | `smoke_alta_un_paso.py`, `smoke_alta_portal_links.py`, `smoke_publico_perfil_avisos.py`, `smoke_publico_adjuntos.py`, `smoke_publico_auth.py` | `_resolver_municipio` pasa a `municipio_por_slug` (con `?m=` vale el slug; sin él, `municipio_de_origen`). Todo lo del vecino logueado usa `municipio_vecino`. |
| **17 — Datos, inicio, configuración y maestros** | `/api/v1/bi`, `/api/v1/dashboard`, `/api/v1/config`, `/api/v1/publico/identidad-municipio`, `/api/v1/admin` (salvo `encuestas` y `tramites`) | `routes/bi.py`, `bi_ejecutivo.py`, `bi_atencion.py`, `dashboard.py`, `config_identidad.py`, `publico_identidad.py`, `admin_tablas.py`, `admin_permisos.py`; `frontend/admin_tablas.html` (quitar la columna `id_municipio` del form de equipos) | `smoke_bi_atencion.py` | La agregación del BI sigue 100 % en SQL, con el filtro en la tabla raíz. Identidad: lectura y guardado con `leer_config`/`guardar_config`, sin el «único municipio activo» (`config_identidad.py:132`, `publico_identidad.py:48`). Si el municipio no tiene `municipio_nombre`, se muestra `municipios.nombre` (así lo ve la fixture B, que no tiene claves propias). En `admin_tablas`, el listado y el CRUD de cada tabla `catalogo`/`operativo` se filtran por municipio; `municipios` solo la lista el nivel 1 del municipio base hasta F3. `configuracion_general` muestra solo las filas del municipio, así que la clave privada VAPID deja de verse. |
| **18 — Procesos sin request** | `/api/v1/demo`, `/api/v1/usuarios` y las rutas con `X-Dispatcher-Token` de `encuestas_admin.py`, `tramites_mantenimiento.py`, `emergencias.py` y `turnos.py` | `routes/demo_datos.py`, `services/demo_*.py`, el `dispatcher_router` de `encuestas_admin.py`, `tramites_mantenimiento.py`, `usuarios_mantenimiento.py`, `services/integridad_cuentas.py`, y el cierre automático de `emergencias.py`/`turnos.py` | `smoke_demo_poblar.py`, `smoke_demo_sla.py` | Cada proceso recorre `SELECT id_municipio FROM municipios WHERE activo` y procesa por municipio, con su configuración. Si un municipio falla, se registra y se sigue con el siguiente. El generador demo corre solo para el municipio con `direccion_base` (F4 lo cambia por `estado = 'demo'`); el body no cambia. Test: con la fixture B, una corrida del dispatcher y del mantenimiento no crea filas en B ni lee su configuración (checksum de B igual). |

### Tarea 19: Cierre de F2 — sin defaults, todo en verde y documentación

**Archivos:**
- Crear: `backend/migrations/126_sin_default_municipio.sql`
- Modificar: `CLAUDE.md` (§1 claim `mun` y re-login; §10 regla nueva de `id_municipio` y `municipio_tabla_clase`; §21 estado de migraciones), `HISTORIAL_MIGRACIONES.md`, `ESTADO.md`, y las skills `modulo-bi`, `modulo-tramites`, `modulo-encuestas`, `modulo-agenda`, `modulo-admin-tablas`, `modulo-app-vecinos` y `modulo-usuarios` (quitar la regla «mono-municipio» e `IS NULL` y dejar R1-R11 con un link a este plan).

- [ ] **Paso 1: Escribir `126`:** un `DO` que pone `ALTER COLUMN id_municipio SET DEFAULT NULL` en toda tabla `catalogo`/`operativo` (incluye `usuarios`, que hoy tiene 377 en prod).
- [ ] **Paso 2: Aplicarla en local** y correr `python smoke_aislamiento.py`. Esperado: **0 FALLAS**. Un INSERT que se haya olvidado del municipio ahora falla por NOT NULL: corregirlo con R2.
- [ ] **Paso 3: Todos los smokes de la Tarea 4**, más `smoke_municipio_request.py` y `smoke_segmentacion_f1.py`. Esperado: todos en verde.
- [ ] **Paso 4: Barridos estáticos sobre `backend/app`.** Esperado: los cuatro vacíos.
  - `grep -rnE "id_municipio IS NULL|ID_MUNICIPIO_DEFAULT|id_municipio: int = 1|get\(\"id_municipio\"\) or 1" backend/app`
  - `grep -rn "default=377\|default=1" backend/app/models`
  - `grep -rn "FROM configuracion_general" backend/app`: solo `core/config_municipio.py`.
  - `grep -rn "id_municipio" web-app/src`: solo en tipos de respuesta.
- [ ] **Paso 5: Navegador en local** (shell vanilla `localhost:8080` y el API local), siguiendo §41: login, y recorrer con clics Reclamos, OT, Turnos, Agenda, Trámites, Emergencias, Datos, Configuración y Maestros. Esperado: todo como antes; los números nuevos salen con `LPL`.
- [ ] **Paso 6: Documentación** (archivos listados arriba).
- [ ] **Paso 7: Commit** con el mensaje `feat(it-01): cierre de F2 - sin default de municipio, docs y skills (mig 126)`.

### Tarea 20: Corte en prod (con César, en la ventana anunciada)

- [ ] **Paso 1: Preparación.** `git fetch` y rebase de la rama sobre `main`. Confirmar en prod que los números 125-126 están libres (renumerar los archivos si no). Re-correr en prod el inventario de la Tarea 1 y comparar con el de este plan (tablas nuevas desde el 2026-10-24 → clasificarlas).
- [ ] **Paso 2: Respaldo.** `/backup-prod` (dump completo), y verificar el tamaño del archivo y la cantidad de tablas que trae.
- [ ] **Paso 3: Frenar los procesos programados durante la ventana:** `gh workflow disable` de `encuestas-dispatcher`, `integridad-cuentas`, `tramites-mantenimiento` y `demo-datos`.
- [ ] **Paso 4: Migraciones compatibles con el código viejo**, **de a una** por `apply_migration`, verificando cada una antes de la siguiente: `125`, `125b` (la aserción frena si hay municipios inesperados), `125c` y `125d`. Después, `smoke_segmentacion_f1.py` adaptado para leer prod (solo lectura), o sus mismas consultas por `execute_sql`.
- [ ] **Paso 5: Código.** Merge `--no-ff` a `main` y push. Esperar el deploy de Railway hasta que `/openapi.json` muestre el marcador de la Tarea 6 en el path exacto `/api/v1/auth/me` (no buscar por palabra). Si en ~5 min no aparece, revisar el panel de Railway (§9).
- [ ] **Paso 6: Migración 126** por `apply_migration` (ahora sí: el código nuevo ya manda el municipio en cada INSERT).
- [ ] **Paso 7: Verificación en prod.**
  - Login con la cuenta de prueba de `credenciales-testing/`: token con `mun = 1`.
  - Los listados de reclamos, turnos, trámites y emergencias dan los mismos conteos que antes del corte.
  - Un token viejo da 401.
  - Las 4 superficies en el navegador (shell, un módulo React, la PWA y la app de agentes): la sesión vieja va al login sin bucle y el login nuevo entra (Foco 5).
  - Un reclamo nuevo de prueba sale como `REC-SAN-…`, solo si César lo autoriza: queda en prod como dato de prueba.
- [ ] **Paso 8: Reactivar los procesos** (`gh workflow enable`), disparar a mano uno (el dispatcher de encuestas) y revisar su log por municipio.
- [ ] **Paso 9: Registro.** `HISTORIAL_MIGRACIONES.md` (migs 125-126 en prod, vía y fecha), `ESTADO.md` y la memoria `project_it01_multi_municipio`. Commit y push.

---

## Lote de limpieza (fuera de este plan, antes de F4; lo corre César en el SQL Editor)

Exige `DROP`, que el MCP rechaza, y no hace falta para San Andrés solo. Antes de correrlo hay que verificar `pg_depend` y que el código no use lo que se borra:

- Índices únicos globales viejos: `uq_ciudadano_doc`, `uq_ciudadano_cuil`, `uq_empresa_cuit`, `usuarios_username_key`, `reclamos_nro_reclamo_key`, `ordenes_trabajo_nro_ot_key`, `emergencia_evento_numero_operativo_key`, `activos_codigo_unico_key`, `agenda_feriado_fecha_key`, `emergencia_canal_ingreso_codigo_key`, `emergencia_prioridad_codigo_key`, `emergencia_organismo_derivacion_codigo_key` y `configuracion_general_clave_key`. Sin borrarlos no puede haber el mismo DNI en dos municipios ni claves de configuración por municipio y globales a la vez.
- Tablas `legado` y columnas `id_municipio` sin uso de las tablas `global`.

## Lo que queda para fases posteriores (no hacerlo acá)

- **F3:** nivel 0, `X-Municipio` dentro de `municipio_actual`, selector, registro de accesos, mover `password_renovacion_dias` a global, y las FK de auditoría hacia `usuarios` para el super administrador.
- **F4:** `municipios.estado`, `max_usuarios_activos`, municipio modelo, alta, vaciado y `municipio_modulo`.
- **F5:** CORS con regex, subdominios reales, links de mails por municipio.
- **F5b:** año y fechas en la zona horaria del municipio, también en los triggers de numeración.
- **F6:** RLS con `SET LOCAL app.id_municipio` en `municipio_actual`/`municipio_vecino`/`municipio_de_origen` y un rol sin `BYPASSRLS`; las políticas se generan desde `municipio_tabla_clase`. También el prefijo `m{id}/` en los buckets y los índices compuestos `(id_municipio, …)` de las consultas calientes, medidos con datos de dos municipios. En F1 va solo un índice simple por tabla: con un municipio, uno compuesto no se puede medir.

## Criterios de Claude en este plan (para que César los revise)

- **FK compuestas en la base (Tarea 3):** no están en el spec. Hacen que la propia base rechace un reclamo de A con el tipo de B, y simplifican F2: alcanza con filtrar la tabla raíz de cada consulta.
- **`municipio_tabla_clase`:** una sola fuente para la clasificación. La leen las migraciones de F1, el barrido, el vaciado y la exportación de F4 y las políticas de RLS de F6.
- **Numeración:** contador por municipio que **continúa** desde el último número de San Andrés (`REC-SAN-2026-002983` sigue a `REC-2026-002982`). Los números viejos no cambian.
- **`password_renovacion_dias` queda en el municipio 1 hasta F3** (si fuera global ahora, nadie podría editarla).
- **El token de un municipio usado desde el subdominio de otro da 401**, también para funcionarios (el spec lo pedía para vecinos).
- **Cuatro migraciones compatibles con el código viejo + una (126) después del deploy**, para que el corte no tenga un momento con la base adelantada y el código atrasado.
