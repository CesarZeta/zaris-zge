# Trámites del vecino — Fase 1 (backend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** que el backend permita al vecino iniciar trámites, verlos, subir los documentos del paso y responder pedidos, y que el agente pueda pedirle algo al vecino; todo en prod y verificado.

**Architecture:** migración 139 (el vecino como actor del ledger, `ofrecer_al_vecino`, tabla `tramite_pedido_iniciador`); la lógica de alta se extrae a un servicio que usan el backoffice y el router público nuevo `publico_tramites.py`; los pedidos viven en `services/tramites/pedidos.py` con sus endpoints de backoffice en `tramites.py`; el desistimiento por pedido es una función nueva del cron de mantenimiento existente.

**Tech Stack:** FastAPI + SQLAlchemy async (`text()`), asyncpg, PostgreSQL 17 (Supabase), Supabase Storage; smokes in-process con `httpx.ASGITransport`.

**Spec:** [`docs/superpowers/specs/2026-11-21-tramites-vecino-design.md`](../specs/2026-11-21-tramites-vecino-design.md). Leer antes también las skills `modulo-tramites` y `modulo-app-vecinos`, y CLAUDE.md §5, §10, §21, §24.

## Global Constraints

- Migraciones **139** (DDL) y **139b** (datos), en `backend/migrations/`; local Y prod. La 139 lleva `DROP CONSTRAINT`/`DROP NOT NULL`: en prod la corre César en el SQL Editor de Supabase; la 139b va por MCP.
- Tabla nueva: `ENABLE ROW LEVEL SECURITY`, fila en `municipio_tabla_clase` (`operativo`, grupo `operativo`), política `barrera_municipio TO zaris_app` con la expresión de la 138, `id_municipio NOT NULL` sin DEFAULT, FK compuestas `(id_municipio, col)` a `tramite` y `ciudadanos`/`agentes`, campos §10.
- Router público: `get_current_ciudadano`, municipio con `municipio_vecino`, registrado en `main.py` con `dependencies=_modulo("publico_tramites_router")` y `"publico_tramites_router": ("tramites",)` en `MODULOS_POR_ROUTER`. `id_ciudadano` siempre del token; lo ajeno = 404 idéntico a inexistente. Rate limit con prefijo `trampub:`.
- Regla de César: todo trámite de iniciador ciudadano exige cuenta de vecino (`ciudadano_credencial` activa, activada o pendiente). Mensaje 422: «El vecino no tiene cuenta en el portal: dale de alta la cuenta desde su ficha».
- Avisos al vecino de trámites: url `"/alertas"` en esta fase (la PWA todavía no tiene `/tramites/:id`; el cambio es de la fase 3). Tipo nuevo `tramite_pedido` en `ciudadano_aviso`.
- Mails solo con los helpers de `app/core/urls.py`; los smokes con mail capturado y `settings.RESEND_API_KEY = ""`.
- Smokes: solo local (abortan si la DB no es `zaris_dev`), corren con `DB_BARRERA=true` y `false`; preparan datos con `SesionSistema`.
- Movimientos nuevos del ledger: `pedido_iniciador`, `respuesta_iniciador`, `pedido_cancelado`.

## Review Focus

1. **Archivo que falla a mitad del alta atómica** (el segundo de dos documentos excede el tamaño): no queda trámite, ni número consumido visible, ni objeto en Storage. → Task 4, `test_alta_atomica_sin_restos`.
2. **Vecino que adivina ids ajenos** en detalle, documento, subir documento y responder pedido: siempre 404 igual a inexistente. → Task 5 y Task 6, `test_ajeno_404`.
3. **Movimientos y documentos con actor vecino en las pantallas del backoffice**: el detalle, el historial y la lista de documentos no pierden filas por un `JOIN agentes` interno. → Task 2, `test_backoffice_ve_movimientos_del_vecino`.
4. **Pedido sobre un trámite que pasa a estado final o se archiva**: el reloj del pedido no lo desiste dos veces ni avisa sobre un trámite cerrado. → Task 7, `test_pedido_en_tramite_cerrado_no_avisa`.
5. **Dos respuestas simultáneas al mismo pedido** (doble toque en el celular): una sola respuesta registrada, la otra 409. → Task 6, `test_respuesta_doble_409`.

---

### Task 1: Migración 139 + 139b

**Files:**
- Create: `backend/migrations/139_tramites_vecino.sql`, `backend/migrations/139b_tramites_vecino_datos.sql`

**Interfaces:**
- Produces (schema):
  - `tramite.id_agente_iniciador`, `tramite_movimiento.id_agente`, `tramite_documento.id_agente_subio` → NULL permitido.
  - `tramite_movimiento.id_ciudadano_actor INTEGER`, `tramite_documento.id_ciudadano_subio INTEGER`, `tramite_documento.id_tramite_pedido INTEGER` (FK compuestas); CHECKs `ck_tramite_movimiento_un_actor` y `ck_tramite_documento_un_actor`: `NOT (agente IS NOT NULL AND ciudadano IS NOT NULL)`.
  - `tipo_tramite.ofrecer_al_vecino BOOLEAN NOT NULL DEFAULT FALSE` y `tipo_tramite.exige_identidad_validada BOOLEAN NOT NULL DEFAULT FALSE` (la 139b no la prende en ninguno).
  - `ciudadano_identidad_validacion` (spec §5.10: `id_ciudadano_identidad_validacion` PK, `id_ciudadano`, `id_agente` NOT NULL, `fecha` TIMESTAMPTZ NOT NULL DEFAULT NOW(), `documento_presentado` VARCHAR(40) NOT NULL, `observacion`, `motivo_revocacion`, `id_agente_revoca`, `fecha_revocacion`, §10). Único parcial `uq_ciudadano_identidad_activa (id_ciudadano) WHERE activo`. Clasificación `operativo`, grupo `contactos`; RLS + `barrera_municipio`; FK compuestas a `ciudadanos` y `agentes`.
  - `tramite_pedido_iniciador` (`id_tramite_pedido` PK, `id_tramite`, `texto` TEXT NOT NULL, `pide_archivo` BOOL NOT NULL DEFAULT FALSE, `estado` VARCHAR(12) CHECK `abierto|respondido|cancelado`, `id_agente_pide` NULL, `fecha_pedido` TIMESTAMPTZ NOT NULL DEFAULT NOW(), `respuesta_texto`, `fecha_respuesta`, `id_agente_cancela`, `motivo_cancelacion`, `respuesta_vista_en`, `aviso_nivel` SMALLINT NOT NULL DEFAULT 0, `aviso_en`, + §10). Único parcial `uq_tramite_pedido_abierto (id_tramite) WHERE estado='abierto' AND activo`.
  - CHECK de `tramite_movimiento.tipo` + `pedido_iniciador`, `respuesta_iniciador`, `pedido_cancelado`; CHECK `ck_ciudadano_aviso_tipo` + `tramite_pedido`.
  - 139b: `ofrecer_al_vecino = TRUE` donde `codigo IN ('aviso-obra','poda-arbol','inscripcion-profesional','exencion-tasas','permiso-espacio-publico','recurso-administrativo')`, en todos los municipios.

- [ ] **Step 1:** Antes de escribir: en local Y prod, `pg_constraint` de los CHECK a reemplazar (copiar la lista exacta de tipos vigente de cada entorno) y confirmar que existen los únicos `(id_municipio, id_tramite)` en `tramite` y `(id_municipio, id_ciudadano)` en `ciudadanos` que necesitan las FK compuestas (si falta alguno, crearlo en la 139).
- [ ] **Step 2:** Escribir 139 y 139b; aplicar en local con el patrón `driver_connection.execute` (§5).
- [ ] **Step 3:** Verificar en local por otra vía: `information_schema.columns` (nullability y columnas nuevas), `pg_constraint` (los 4 CHECK), `relrowsecurity` y `pg_policies` de la tabla nueva, `SELECT codigo FROM tipo_tramite WHERE ofrecer_al_vecino` (6 en San Andrés local). Correr `python smoke_barrera.py` → verde.
- [ ] **Step 4:** Commit `feat(db): migracion 139, el vecino como actor de los tramites y pedidos al vecino`.

### Task 2: El vecino como actor en servicios y pantallas existentes

**Files:**
- Modify: `backend/app/services/tramites/movimientos.py` (`registrar_movimiento`)
- Modify: `backend/app/services/tramites/ciclo_vida.py`, `retencion.py`, `autorizacion.py`
- Modify: `backend/app/api/routes/tramites.py` (los SELECT de detalle, movimientos y documentos)
- Modify: `backend/app/schemas/tramites.py` (salidas que nombran al actor)
- Create: `backend/smoke_tramites_vecino.py` (smoke de toda la fase; cada task le suma casos)

**Interfaces:**
- Produces: `registrar_movimiento(db, id_tramite, tipo, id_usuario: int | None, id_agente: int | None, id_municipio, request=None, ..., id_ciudadano_actor: int | None = None) -> dict`. Los movimientos y documentos del backoffice exponen `actor_tipo: Literal["agente","ciudadano","sistema"]` y `actor_nombre: str | None`.

- [ ] **Step 1: test** `test_backoffice_ve_movimientos_del_vecino`: el smoke inserta (como dueño) un trámite de San Andrés con `id_agente_iniciador NULL`, un movimiento y un documento con `id_ciudadano_*`; `GET /tramites/{n}`, `/movimientos` y `/documentos` con el admin → 200, la fila está, `actor_tipo == "ciudadano"` y `actor_nombre` es «Apellido, Nombre» del vecino.
- [ ] **Step 2:** correrlo → falla (filas perdidas por `JOIN agentes` interno o 500).
- [ ] **Step 3:** implementar: `registrar_movimiento` con los dos actores opcionales; `JOIN agentes` → `LEFT JOIN` + `LEFT JOIN ciudadanos` en cada SELECT de `tramites.py` que cuelga de `id_agente`, `id_agente_subio` o `id_agente_iniciador` (barrer con `grep -n "JOIN agentes" app/api/routes/tramites.py`); los crons de `ciclo_vida.py` y `retencion.py` pasan `id_agente=d["id_agente_iniciador"]` tal cual (puede ser NULL = sistema); `{"iniciador": true}` en `autorizacion.py` da False si `id_agente_iniciador` es NULL.
- [ ] **Step 4:** el test pasa; `python smoke_tramites_ciclo_vida.py` (contra uvicorn local) y `smoke_tramites_resultado_final.py` siguen verdes.
- [ ] **Step 5:** commit `feat(tramites): el ledger acepta al vecino como actor`.

### Task 3: Servicio común de alta + regla «nada sin cuenta»

**Files:**
- Create: `backend/app/services/tramites/alta.py`
- Modify: `backend/app/api/routes/tramites.py` (`crear_tramite` usa el servicio)

**Interfaces:**
- Produces:
  - `async def vecino_tiene_cuenta(db, id_ciudadano: int) -> bool`
  - `async def crear_tramite_en_db(db, *, tipo: dict, datos: dict, asunto: str | None, iniciador_fks: dict, iniciador_tipo: str, id_municipio: int, actor_agente: dict | None, id_ciudadano_actor: int | None, id_usuario: int | None, destinatario: tuple[str, int], request) -> int` (id_tramite; numerador, INSERT, movimientos `creacion`/`numeracion`, aprobaciones del estado inicial; **no** commitea).

- [ ] **Step 1: tests** `test_backoffice_alta_sin_cuenta_422`: admin crea poda-arbol para un ciudadano sin `ciudadano_credencial` → 422 con el mensaje de Global Constraints y `count(tramite)` igual antes y después. `test_backoffice_alta_con_cuenta_201`: con el vecino demo con cuenta → 201, número con el prefijo del tipo, movimientos `creacion` y `numeracion` con `id_agente` del admin.
- [ ] **Step 2:** correr → el primero falla (hoy da 201).
- [ ] **Step 3:** extraer el cuerpo de `crear_tramite` a `crear_tramite_en_db` sin cambiar el comportamiento; agregar el chequeo de cuenta cuando `iniciador.tipo == "ciudadano"`, antes de numerar.
- [ ] **Step 4:** los dos tests pasan; `smoke_tramites_aviso_inicio.py` sigue verde.
- [ ] **Step 5:** commit `feat(tramites): un tramite de vecino exige su cuenta del portal`.

### Task 3b: Identidad validada en el municipio

**Files:**
- Create: `backend/app/services/identidad.py`
- Modify: `backend/app/api/routes/buc.py` (endpoints + `identidad_validada` en el GET de la ficha y en `/cuentas`), `backend/app/schemas/buc.py`, `backend/app/api/routes/publico_perfil.py`, `backend/app/services/tramites/alta.py`, `backend/app/api/routes/tramites.py` (alta del backoffice)

**Interfaces:**
- Produces:
  - `async def identidad_validada(db, id_ciudadano: int) -> dict | None` (`{fecha, agente_nombre}` de la fila activa).
  - `POST /api/v1/buc/ciudadanos/{id}/identidad/validar` `{documento_presentado: str (2..40), observacion: str | None}` → 201; nivel ≤ 3 con agente; 409 si ya está validada.
  - `POST /api/v1/buc/ciudadanos/{id}/identidad/revocar` `{motivo: str (min 5)}` → 200; nivel ≤ 2; 404 si no hay validación activa.
  - `identidad_validada: {fecha, agente_nombre} | null` en la ficha, en `/cuentas` y en `GET /publico/perfil` (en el perfil público, solo `{fecha}`).
  - En `crear_tramite_en_db`'s caller del backoffice: si `tipo.exige_identidad_validada` y el iniciador ciudadano no la tiene → 422 «Validá la identidad del vecino en su ficha antes de iniciar este trámite».
  - Constante `MSG_IDENTIDAD_PORTAL = "Para iniciar este trámite tenés que validar tu identidad en el municipio. Acercate con tu documento."` en `services/identidad.py` (la usa la Task 4).

- [ ] **Step 1: tests** `test_identidad_validar_y_revocar`: un usuario nivel 4 → 403; nivel 3 valida → 201 y la ficha trae `identidad_validada`; validar de nuevo → 409; nivel 3 revoca → 403; nivel 2 revoca → 200 y la ficha vuelve a `null`; en DB quedan las dos filas (una revocada). `test_backoffice_alta_exige_identidad`: con `exige_identidad_validada=true` en poda-arbol (el smoke lo prende y lo restaura), alta para un vecino con cuenta sin validar → 422; tras validar → 201.
- [ ] **Step 2:** correr → fallan.
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** pasan con y sin barrera.
- [ ] **Step 5:** commit `feat(buc): validar la identidad del vecino en el municipio`.

### Task 4: Router público — tipos y alta atómica

**Files:**
- Create: `backend/app/api/routes/publico_tramites.py`, `backend/app/schemas/publico_tramites.py`
- Modify: `backend/app/main.py`, `backend/app/services/municipios/modulos.py`, `backend/app/services/tramites/documentos.py` (borrar un objeto ya subido si la transacción falla: reusar `borrar_archivo`)

**Interfaces:**
- Consumes: `crear_tramite_en_db` (Task 3), `validar_campos_contra_tipo`, `validar_archivo_mock`, `guardar_archivo_mock`.
- Produces:
  - `async def tipos_ofrecidos(db, id_municipio: int, id_tipo: int | None = None) -> list[dict]` en `services/tramites/alta.py` (criterio del spec §5.1, en SQL).
  - `async def documentos_del_alta(db, id_version: int, id_estado_inicial: int) -> list[dict]` (aporta iniciador, sin estado o del estado inicial, sin `requiere_firma`).
  - `GET /api/v1/publico/tramites/tipos` → `[{id_tipo_tramite, nombre, descripcion, exige_identidad_validada, puede_iniciar, motivo_no_puede: str | None}]` (`puede_iniciar=false` + `MSG_IDENTIDAD_PORTAL` si exige y el vecino no la tiene; el POST responde 422 con ese texto); `GET /tipos/{id}` → `{..., campos: [{nombre_interno, etiqueta, tipo_dato, obligatorio, opciones, ayuda, orden}], documentos: [{id_documento_requerido, nombre, descripcion, obligatorio, formatos_permitidos, tamano_max_mb, cantidad_max_archivos}]}`.
  - `POST /api/v1/publico/tramites` multipart: `id_tipo_tramite: int`, `datos: str` (JSON), `archivos: list[UploadFile]`, `documentos: str` (JSON lista paralela de `id_documento_requerido`, uno por archivo) → 201 `{id_tramite, numero_expediente}`.

- [ ] **Step 1: tests** (vecino demo con cuenta, login por `/publico/auth/login`):
  - `test_tipos_ofrecidos`: lista = los tipos con `ofrecer_al_vecino` de San Andrés; `permiso-demo-e2e` no está; un tipo no ofrecido en `GET /tipos/{id}` → 404.
  - `test_alta_vecino_ok`: poda-arbol con su foto → 201; en DB: `id_agente_iniciador IS NULL`, `id_ciudadano_iniciador` = el del token, `id_subarea_actual = tipo.id_subarea`, movimiento `creacion` con `id_ciudadano_actor`, un `tramite_documento` con `id_ciudadano_subio`; un mail capturado al vecino con el número.
  - `test_alta_sin_documento_obligatorio_422`: sin la foto → 422 y sin filas nuevas.
  - `test_alta_atomica_sin_restos` (Review Focus 1): dos archivos, el segundo excede `tamano_max_mb` → 422, ninguna fila nueva en `tramite`/`tramite_documento` y ningún objeto nuevo bajo la carpeta del expediente (Storage simulado en el smoke: monkeypatch de `storage.subir_objeto`/`borrar_objeto` que registra llamadas, memoria `reference_storage_local_apunta_a_prod`).
  - `test_alta_campo_invalido_422`: `seleccion` con un valor fuera de las opciones → 422.
  - `test_alta_exige_identidad_portal`: con `exige_identidad_validada=true` en poda-arbol (el smoke lo prende y lo restaura) y el vecino sin validar → el tipo aparece con `puede_iniciar=false` y `motivo_no_puede=MSG_IDENTIDAD_PORTAL`; el POST → 422 con ese texto y sin filas nuevas.
- [ ] **Step 2:** correr → 404 (router inexistente).
- [ ] **Step 3:** implementar. Orden dentro del POST: validar tipo ofrecido → validar campos → validar cada archivo contra su documento requerido y que estén todos los obligatorios → `crear_tramite_en_db` (actor ciudadano, destinatario `("subarea", tipo.id_subarea)`) → subir archivos e insertar documentos + movimientos `adjunto` → commit; ante cualquier excepción después de subir, `borrar_archivo` de lo subido y re-lanzar. Post-commit: `notificar_tramite_a_bandeja(..., "creacion")` y `notificar_inicio_a_iniciador`.
- [ ] **Step 4:** los tests pasan con `DB_BARRERA=true` y `false`.
- [ ] **Step 5:** commit `feat(publico): el vecino inicia tramites desde el portal`.

### Task 5: Router público — mis trámites, detalle, documentos del paso, resumen

**Files:**
- Modify: `backend/app/api/routes/publico_tramites.py`, `backend/app/schemas/publico_tramites.py`, `backend/app/api/routes/publico_portal.py`

**Interfaces:**
- Produces:
  - `GET /publico/tramites` → `[{id_tramite, numero_expediente, tipo_nombre, estado_etiqueta, estado_color, resultado, fecha_alta, tiene_pedido_abierto, documentos_pendientes}]`.
  - `GET /publico/tramites/{id}` → lo anterior + `datos: [{etiqueta, valor}]` (sin campos `agente`/`subarea`), `documentos: [{id_tramite_documento, nombre, fecha_alta, binario_purgado}]` (solo `id_ciudadano_subio` = él), `documentos_del_paso` (mismo shape que el alta, del estado actual, con `subidos`), `pedido_abierto: {id_tramite_pedido, texto, pide_archivo, fecha_pedido} | null`, `historial: [{fecha, texto}]`.
  - `GET /publico/tramites/{id}/documentos/{id_doc}/contenido` (binario; 410 si purgado).
  - `POST /publico/tramites/{id}/documentos` multipart (`archivos`, `documentos`) → 201 `{subidos: n}`.
  - `mi-resumen` suma `tramites: {vigentes, total, pedidos_abiertos}`.
- Historial: lista cerrada de tipos de movimiento `creacion, transicion, cambio_estado, pedido_iniciador, respuesta_iniciador, pedido_cancelado, resultado, aviso_iniciador, desistido, archivado_inactividad`, más `adjunto` solo si lo subió él. Texto por tipo armado en el backend; en `transicion` = etiqueta del estado destino + `mensaje_iniciador` si la transición lo tiene. Nunca `comentario` interno ni nombres de agentes.

- [ ] **Step 1: tests:**
  - `test_mis_tramites_incluye_ventanilla`: un trámite creado por el admin para el vecino (Task 3) y uno del vecino (Task 4) aparecen los dos.
  - `test_detalle_sin_datos_internos`: tras un `comentar` y un `pase` del admin, el historial no contiene el texto del comentario ni el nombre del agente; sí contiene la creación.
  - `test_ajeno_404` (Review Focus 2): el trámite de otro ciudadano en detalle, contenido de documento y subir documento → 404 con el mismo cuerpo que un id inexistente.
  - `test_documento_del_paso`: con un requisito `aporta_quien='iniciador'` atado al estado actual → aparece en `documentos_del_paso`; subirlo → 201 y movimiento `adjunto`; un `id_documento_requerido` de otro estado → 422.
  - `test_resumen_tramites`: `mi-resumen.tramites.total` = cantidad del vecino.
- [ ] **Step 2:** correr → fallan.
- [ ] **Step 3:** implementar; la subida del paso notifica al colectivo destinatario con `notificar_documento_vecino(db, id_tramite, background_tasks)` (nueva en `services/notificaciones.py`, mismo armado que `notificar_tramite_a_bandeja`: in-app + mail).
- [ ] **Step 4:** pasan con y sin barrera.
- [ ] **Step 5:** commit `feat(publico): mis tramites, detalle y documentos del paso`.

### Task 6: Pedidos al vecino

**Files:**
- Create: `backend/app/services/tramites/pedidos.py`
- Modify: `backend/app/api/routes/tramites.py` (endpoints de backoffice + `pedidos` en `TramiteDetalleOut` en **los dos** armados: `_tramite_detalle_out` y el handler `GET /{numero_o_id}`; `pedido_abierto: bool` y `respuesta_sin_ver: bool` en las filas de bandeja y mi-bandeja), `backend/app/schemas/tramites.py`, `backend/app/api/routes/publico_tramites.py`, `backend/app/services/avisos.py` (`TIPOS_AVISO` + `tramite_pedido`), `backend/app/services/notificaciones.py`

**Interfaces:**
- Produces:
  - `POST /api/v1/tramites/{ref}/pedidos` `{texto: str (min 5), pide_archivo: bool}` → `TramiteDetalleOut`. Guards: agente resuelto, no Consultor, `agente_puede_operar`; 422 si iniciador no ciudadano, sin cuenta, archivado, estado final o ya hay uno abierto.
  - `POST /api/v1/tramites/{ref}/pedidos/{id}/cancelar` `{motivo: str (min 5)}` → `TramiteDetalleOut`.
  - `POST /api/v1/tramites/{ref}/pedidos/{id}/visto` → 204 (marca `respuesta_vista_en`; lo llama la fase 2 al abrir el detalle).
  - `POST /api/v1/publico/tramites/{id}/pedidos/{id_pedido}/responder` multipart `texto` (min 5), `archivos` → 200. 422 si `pide_archivo` y no hay archivos; 409 si el pedido no está abierto.
  - `TramiteDetalleOut.pedidos: list[PedidoOut]` con `{id_tramite_pedido, texto, pide_archivo, estado, fecha_pedido, agente_pide, respuesta_texto, fecha_respuesta, documentos_respuesta, motivo_cancelacion}`.
  - Notificaciones: al pedir y al cancelar, `ciclo_vida._avisar_vecino(d, "tramite_pedido", titulo, cuerpo, con_email=True)`; su mail (`_mail_vecino`) suma un botón «Ir al Portal del Ciudadano» con `url_portal_vecino(db, id_municipio)` (oculto si viene vacío), y el test de abajo comprueba que el mail capturado lo trae; al responder, `notificar_respuesta_vecino(db, id_tramite, background_tasks)` (nueva: in-app + mail al tomador si hay y al colectivo destinatario).

- [ ] **Step 1: tests:**
  - `test_pedido_ciclo_completo`: admin pide con `pide_archivo=true` → aviso `tramite_pedido` en `ciudadano_aviso` y mail capturado; el detalle público muestra `pedido_abierto`; responder sin archivo → 422; con archivo → 200, pedido `respondido`, documento con `id_tramite_pedido`, movimiento `respuesta_iniciador`, notificación in-app al colectivo; el detalle del backoffice trae el pedido con la respuesta y la bandeja `respuesta_sin_ver=true`; `/visto` → la bandeja `respuesta_sin_ver=false`.
  - `test_pedido_reglas_422`: segundo pedido con uno abierto → 422; pedido sobre trámite de iniciador empresa → 422; sobre un vecino sin cuenta → 422.
  - `test_respuesta_doble_409` (Review Focus 5): dos `responder` concurrentes (`asyncio.gather`) → uno 200 y otro 409; una sola respuesta guardada (el UPDATE toma la fila con `FOR UPDATE` y exige `estado='abierto'`).
  - `test_cancelar_pedido`: cancelar → `cancelado`, aviso al vecino, responder después → 409.
  - `test_ajeno_404` (Review Focus 2): responder un pedido de un trámite ajeno → 404.
- [ ] **Step 2:** correr → fallan.
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** pasan con y sin barrera.
- [ ] **Step 5:** commit `feat(tramites): pedidos al vecino y su respuesta desde el portal`.

### Task 7: Desistimiento por pedido sin respuesta

**Files:**
- Modify: `backend/app/services/tramites/ciclo_vida.py`, `backend/app/api/routes/tramites_mantenimiento.py`

**Interfaces:**
- Produces: `async def procesar_pedidos_sin_respuesta(db, *, id_municipio: int, limite: int = 500) -> dict` (`{avisos, desistidos, ids}`), llamada desde el cron de mantenimiento después de `procesar_desistimientos`, con su resultado en la respuesta por municipio.
- Reglas: mismas claves y escalones que `procesar_desistimientos` (aviso1, aviso2, último aviso a `desistimiento_dias − aviso_final_horas`, desistido a `desistimiento_dias`), t0 = `fecha_pedido`, nivel en `tramite_pedido_iniciador.aviso_nivel`. Solo pedidos `abierto` de trámites no archivados, no finales y con `resultado='pendiente'`. Avisos con el texto del pedido. Al desistir: el mismo UPDATE y movimiento `desistido` que el timer existente + el pedido a `cancelado` con motivo «desistimiento» + `al_terminar(id, con_email=True)`. Respeta `tramite_desistimiento_activo`.

- [ ] **Step 1: tests** (viajan en el tiempo moviendo `fecha_pedido`; aíslan el resto de la base como `smoke_tramites_ciclo_vida.py`):
  - `test_pedido_escalones`: a1+1 días → nivel 1 y aviso; correr de nuevo sin mover → sin aviso nuevo; a `desistimiento_dias`+1 con nivel 3 → `resultado='desistido'`, pedido `cancelado`.
  - `test_cambio_de_estado_no_reinicia`: con nivel 1, una transición del trámite no cambia `aviso_nivel`.
  - `test_pedido_en_tramite_cerrado_no_avisa` (Review Focus 4): pedido abierto en un trámite ya archivado o en estado final → ni aviso ni desistimiento.
- [ ] **Step 2:** correr → fallan.
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** pasan; `smoke_tramites_ciclo_vida.py` sigue verde.
- [ ] **Step 5:** commit `feat(tramites): un pedido sin respuesta termina en desistimiento`.

### Task 8: `ofrecer_al_vecino` y `exige_identidad_validada` en el catálogo admin

**Files:**
- Modify: `backend/app/schemas/tramites.py` (`TipoTramiteCreateIn`, `TipoTramiteUpdateIn`, `TipoTramiteAdminOut`, `TipoTramiteAdminListItem`), `backend/app/api/routes/tramites_admin.py` (INSERT del POST, `sets` del PUT, los dos SELECT: `_detalle_tipo_admin` y `listar_tipos_admin`)

- [ ] **Step 1: test** `test_admin_ofrecer_al_vecino`: PUT `{ofrecer_al_vecino: true}` sobre un tipo con `ciudadano` → el detalle y la lista admin lo devuelven `true` y el tipo aparece en `GET /publico/tramites/tipos`; PUT `true` sobre un tipo solo de empresa → 422 «Solo se ofrece al vecino un trámite que admite iniciador ciudadano». Igual para `exige_identidad_validada` (ida y vuelta por PUT, visible en detalle y lista admin; sin la restricción de iniciador).
- [ ] **Step 2:** correr → falla.
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** pasa.
- [ ] **Step 5:** commit `feat(tramites-admin): marcar un tipo como ofrecido al vecino`.

### Task 9: Contrato, skills y deploy a prod

**Files:**
- Modify: `docs/contrato_api_publica.md` (sección nueva «Trámites»), `.claude/skills/modulo-tramites/SKILL.md`, `.claude/skills/modulo-app-vecinos/SKILL.md`, `HISTORIAL_MIGRACIONES.md`, CLAUDE.md §21 (línea de la 139), `ESTADO.md`

- [ ] **Step 1:** `python tools/barrido_links_mail.py`, `python tools/barrido_sistema.py`, `python smoke_barrera.py` y `smoke_tramites_vecino.py` con `DB_BARRERA=true` y `false` → todo verde.
- [ ] **Step 2:** prod, antes del deploy: César corre la 139 en el SQL Editor (pasarle el archivo con app, URL y camino); verificar por MCP (columnas, CHECKs, política, clasificación); aplicar la 139b por MCP y verificar `ofrecer_al_vecino` (6 en San Andrés, 5 en el modelo).
- [ ] **Step 3:** push a `main`; esperar el deploy y verificar `GET /api/health` → `commit` = el pusheado y `/openapi.json` con `/api/v1/publico/tramites` y `/api/v1/tramites/{tramite_ref}/pedidos`.
- [ ] **Step 4:** en prod, sin escribir: `GET /publico/tramites/tipos` con el vecino de prueba → los 6 tipos; `GET /publico/tramites` → 200. El alta real en prod queda para la verificación de la fase 3 (navegando la PWA).
- [ ] **Step 5:** actualizar docs y commit `docs(tramites): contrato y reglas de los tramites del vecino`.
