# Historial de Migraciones en Prod (Supabase) — ZARIS

> **Archivo de referencia histórica.** Extraído de CLAUDE.md §21 el 2026-05-26 para aligerar el documento de reglas. Contiene la bitácora detallada de cada migración aplicada (qué hace, cuándo se aplicó, snapshots de backup). **No es fuente de verdad** — antes de codear algo schema-dependent, verificar el estado real con `execute_sql` (regla §24 de CLAUDE.md). La doc puede quedar atrás.
>
> CLAUDE.md §21 mantiene solo el resumen vigente + el puntero a este archivo.

---

Las siguientes tablas ya existen en Supabase prod y **no deben re-crearse**:

| Tabla | Migración | Notas |
|---|---|---|
| `reclamos` | 20 | Trigger `trg_nro_reclamo` → `REC-YYYY-XXXXXX` |
| `reclamo_historial` | 20 | FK a `reclamos` |
| `tipo_reclamo` | 20 | Columna `audit` agregada en migración 21 |
| `estado_reclamo` | manual | Estados válidos del flujo de reclamos |
| `ordenes_trabajo` | pre-existente | Trigger `trg_nro_ot` → `OT-YYYY-XXXXXX` |
| `estado_ot` | pre-existente | Seeds **aplicados 2026-05-12 via MCP** (la tabla estaba vacía en prod, el endpoint `/reclamos/{id}/cancelar` lo cazó al fallar buscando `'Cancelada'`). 5 estados: En gestión, En espera, Pendiente, Terminada, Cancelada. Idempotente con `ON CONFLICT (nombre) DO NOTHING`. |
| `equipo_agentes` | pre-existente | Reemplaza `equipo_usuarios` en lógica de OTs |
| `configuracion_general` | pre-existente | Seeds: `auditor_misma_subarea_permitido`, `ot_pendiente_dias_vencimiento` |

**Estados de reclamos en prod** fueron migrados en 2026-05-04:
- `Ingresado` → `Sin asignar`
- `En revisión` → `En gestión`
- `Cerrado` → `Resuelto`
- `Rechazado` → `Cancelado`

CHECK constraint activo: `ck_reclamo_estado` con valores `('Sin asignar','En gestión','En espera','En auditoría','Resuelto','Cancelado')`.

### Drift no-migración: `ciudadanos.latitud/longitud` + `empresas.latitud/longitud`

**Verificado prod + local 2026-05-15.** Las 4 columnas existen como `NUMERIC(10,7) NULL` en ambos entornos, **sin migración formal numerada**. Probable cambio manual viejo (mismo origen que `agentes.es_auditor` — caso documentado en §24). Los modelos SQLAlchemy `Ciudadano`/`Empresa` ya las exponían; los schemas Pydantic `*Out` también. Lo que faltaba al 2026-05-15 era declararlas en `CiudadanoBase`/`Update` + `EmpresaBase`/`Update` para aceptarlas en POST/PUT — agregado en commit `164b817` junto a la normalización OSM (ver §22).

**Implicación:** si una sesión futura pide "agregar lat/lon a ciudadanos/empresas", la respuesta es verificar con `execute_sql` y solo tocar schemas Pydantic + frontend. NO redactar `ADD COLUMN`. Ver memoria [[reference_buc_lat_lon_columnas_existentes]].

### Migración 22 — Geolocalización + Activos + Adjuntos (`backend/migrations/22_geo_activos_adjuntos.sql`)

**Aplicada en prod Supabase y en local (zaris_dev) al 2026-05-09.** Datos seedeados en prod: 24 provincias, 102 partidos, 352 localidades, 5 tipos_activo, 1000 activos. Incluye:

- Crea `provincias`, `partidos`, `localidades`.
- Crea `tipos_activo`, `activos`.
- Crea `reclamo_adjuntos`.
- Agrega a `reclamos`: `id_estado_fk` (FK → `estado_reclamo.id_estado_reclamo`), `direccion`, `latitud`, `longitud`, `id_localidad`, `id_activo`, `canal_origen`, `fuente_geolocalizacion`, `fecha_cierre`, `fecha_primer_asignacion`, `sla_vencimiento`.
- Trigger `trg_sla_reclamo`: calcula `sla_vencimiento = fecha_alta + tipo_reclamo.sla_dias` al INSERT.
- La columna `estado` (VARCHAR) se mantiene transicional para compatibilidad — deprecada cuando frontend y endpoints migren 100% a `id_estado_fk`.

### Migración 23 — Reasignación de subáreas a sus áreas correctas (`backend/migrations/23_reasignar_subareas_a_areas.sql`)

**Aplicada en prod y local al 2026-05-09.** Resuelve inconsistencia entre `tipo_reclamo.id_area` y `subarea.id_area` reasignando subáreas mal ubicadas (10 subáreas operativas que estaban bajo "Gobierno" pasan a "Servicios Públicos"; 2 a Planeamiento; 1 a Tránsito). 35/35 subáreas activas alineadas con la moda de tipos. Snapshot pre-update en `_backup_subarea_2026_05_09`.

### Migración 27 — Drop `tipo_reclamo.id_area` (`backend/migrations/27_drop_tipo_reclamo_id_area.sql`)

**Aplicada en local y prod al 2026-05-10.** Elimina la columna redundante `tipo_reclamo.id_area` (y su índice `idx_tipo_reclamo_area`). Desde mig 24 la fuente única del área de un tipo es `subarea.id_area` vía `tr.id_subarea → s.id_area`; mantener la columna espejo obligaba a doble escritura y abría la puerta a inconsistencias (123/282 filas divergentes antes de mig 23-24). Backend (`reclamos.py`, `ordenes_trabajo.py`) ya consultaba exclusivamente vía JOIN con `subarea`; `admin_tablas.py` quitó `id_area` de los `cols` editables de `tipo_reclamo`. Sin vistas ni triggers dependientes.

> **Quirk derivado** (cazado 2026-05-19): `reclamos.id_area` y `reclamos.id_subarea` **siguen existiendo** en la tabla con NULL para filas viejas. Cualquier filtro `WHERE r.id_area = :x` o `WHERE r.id_subarea = :x` deja invisibles los reclamos legacy. Usar siempre `s.id_area` / `tr.id_subarea` (derivados via JOIN). Aplica también a SELECTs/JOINs (ya cubierto en sesiones previas) y a filtros WHERE (este caso). Ver memoria [[feedback_filtros_legacy_post_mig27]].

### Migraciones 30-37 — Módulo Agenda (sub-fase 1.A + autoservicio)

**Aplicadas en local y prod al 2026-05-12.** Estado final del módulo Agenda en prod:

- **Mig 30** (`30_agenda_municipios_y_tipo_reclamo.sql`): crea `municipios` (seed: 1 fila) + ALTER `tipo_reclamo` agregando `duracion_estimada_min INTEGER DEFAULT 60` y `asignacion_a VARCHAR(10) DEFAULT 'agente'` con CHECK `('agente','equipo')`. La parte 1 (CREATE TABLE) se aplicó en el E2E del 2026-05-12; la parte 2 (ALTER tipo_reclamo) quedó pendiente hasta esta sesión, fixed via `30_part2_alter_tipo_reclamo`.
- **Mig 31** (`31_agenda_catalogos.sql`): `estado_evento` (3 seeds: activo/finalizado/cancelado) + `estado_reserva` (3 seeds: reservada/asistio/cancelada).
- **Mig 32** (`32_agenda_eventos_y_reservas.sql`): `eventos` + `evento_encargados` + `evento_reservas`.
- **Mig 33** (`33_agenda_ocupaciones.sql`): `ocupaciones` con CHECK de consistencia tipo↔FK.
- **Mig 34** (`34_agenda_auditoria_y_conflictos.sql`): `conflictos_log` + `agenda_audit_log`.
- **Mig 35** (`35_agenda_autoservicio_tokens.sql`): `eventos.token_publico` + `evento_reservas.token_reserva` (UUID con índices únicos parciales WHERE NOT NULL) + backfill via `gen_random_uuid()`. Requiere `pgcrypto` (creada en la misma mig).
- **Mig 36** (`36_agenda_activo_defaults.sql`): `ALTER COLUMN activo SET DEFAULT TRUE` en las 7 tablas Agenda con esa columna (el E2E descubrió el drift).
- **Mig 37** (`37_agenda_defaults_y_notnull_completos.sql`): cierra el resto del drift de defaults + NOT NULL. Sincroniza ~13 defaults (`id_municipio=1` en 8 tablas, `resuelto=FALSE`, `capacidad_ciudadanos=1`, `cantidad_encargados=0`, `tipo_qr='ninguno'`, `admite_autoservicio=FALSE`) y ~18 `SET NOT NULL` en timestamps con `DEFAULT NOW()`. Verificado pre-aplicación: 0 NULLs en columnas afectadas, no requiere backfill.

**Snapshot pre-mig 30 (parte 2)** en `_backup_tipo_reclamo_2026_05_12_premig30` (282 filas).

**Smoke post-aplicación** (`/api/v1/agenda/calendario`, `/mes`, `/conflictos`, `/eventos/{id}`): 4/4 → HTTP 200 contra Railway. Endpoints públicos `/agenda/publico/*`: 4/4 OK (404/422 según corresponde sin auth).

**Catálogos seedeados en prod:** municipios=1, estado_evento=3, estado_reserva=3. Sin eventos productivos (1 residual del E2E con `activo=false`).

### Migraciones 40-43 — Agenda sub-fase B1: Espacios + Disponibilidad multi-rango

**Aplicadas en local y prod al 2026-05-13.** Habilitan los tres tipos de recurso (`agente`, `equipo`, `espacio`) y horarios laborales multi-rango con turnos rotativos. Detalle:

- **Mig 40** (`40_agenda_espacios.sql`): crea `espacios_agenda` (estándar §10 completo, con `atendido BOOLEAN DEFAULT TRUE`, `capacidad_personas`, `direccion`, `id_subarea`) + N:M `espacio_agentes` (con UNIQUE `(id_espacio, id_agente)`). Catálogo separado de `lugares_atencion` legacy a propósito (ese legacy no tiene shape §10 y no es 1:1 con espacios de agenda — ver decisión 2026-05-13).
- **Mig 41** (`41_agenda_disponibilidad_recurso.sql`): crea `disponibilidad_recurso` (multi-rango — múltiples filas por recurso permiten turnos rotativos). Columnas clave: `tipo_recurso ∈ {agente,equipo,espacio}`, `id_recurso`, `dias_semana SMALLINT 0-127` (bitmask §27), `hora_inicio/hora_fin TIME`, `vigente_desde/vigente_hasta DATE` (opcionales, para rotaciones programadas), `etiqueta`. CHECK enforce: `hora_fin > hora_inicio` y `vigente_hasta >= vigente_desde`. Estándar §10 completo.
- **Mig 42** (`42_agenda_tipo_recurso_espacio.sql`): amplía CHECK `tipo_recurso` en `ocupaciones` (`ck_ocup_tipo_recurso`) y `evento_encargados` (`ck_evt_enc_tipo_recurso`) agregando `'espacio'`. Sin FK física (id_recurso es polimórfica; validación en backend).
- **Mig 43** (`43_agenda_eventos_id_espacio.sql`): agrega `eventos.id_espacio INTEGER REFERENCES espacios_agenda(id_espacio) ON DELETE SET NULL` (opcional — eventos itinerantes/virtuales no usan espacio).

Migraciones idempotentes (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `DROP CONSTRAINT IF EXISTS`). No rompen compat: las tablas nuevas vienen vacías y el filtro `tipo_recurso` en endpoints existentes seguía aceptando `agente|equipo|todos` y ahora también acepta `espacio`.

### Migración 45 — Módulo Turnos (`backend/migrations/45_turnos.sql`)

**Aplicada en local y prod al 2026-05-14.** Crea el catálogo `tipo_servicio_turno` (estándar §10, con `duracion_min`, 3 seeds idempotentes) y la tabla transaccional `turnos` (estándar §10, FKs a `ciudadanos`/`agentes`/`tipo_servicio_turno`, `estado` CHECK `reservado|cumplido|cancelado`, `id_ocupacion` → fila espejo en `ocupaciones`). Idempotente (`CREATE TABLE IF NOT EXISTS`). Ver §33 para el modelo del módulo. **Ojo:** la tabla legacy `turnos` que mig 39 dropeó NO es esta — son tablas distintas que comparten nombre.

### Migración 46 — Turnos autoservicio (`backend/migrations/46_turnos_autoservicio.sql`)

**Aplicada en local y prod al 2026-05-14.** Agrega `turnos.token_turno UUID` (no enumerable, único, default `gen_random_uuid()`, backfill de filas existentes — habilita que el ciudadano consulte/cancele su turno sin JWT) y `turnos.origen VARCHAR(15)` CHECK `backoffice|autoservicio` default `backoffice`. Requiere `pgcrypto` (ya creada en mig 35). Idempotente. Ver §33 sección "Turnos autoservicio".

### Migración 38 — Permisos por módulo (`backend/migrations/38_permisos_por_modulo.sql`)

**Aplicada en local y prod al 2026-05-12.** Crea `modulos` (8 seeds iniciales: reclamos, padrones, ot_*, turnos, usuarios, admin_tablas con `min_nivel_acceso` segmentado) + `usuario_modulos` (overrides). Ambas con estándar §10 completo. CHECK `min_nivel_acceso BETWEEN 1 AND 4`. UNIQUE `(id_usuario, modulo_codigo)` en overrides. Ver §30 para el detalle del modelo y los endpoints. **Mig 44 (2026-05-14)** separó `turnos` en `agenda`/`turnos`/`entradas` → catálogo actual 10 módulos.

### Migración 26 — Cleanup de áreas duplicadas con/sin tilde (`backend/migrations/26_cleanup_areas_duplicadas.sql`)

**Aplicada en local y prod al 2026-05-10.** Consolida 15 pares de áreas duplicadas (una con tildes, otra sin) eligiendo dinámicamente como canónico el de cada par con más referencias entrantes (`subarea + tipo_reclamo + reclamos + lugares_atencion`); en empate, el activo; en empate, el id menor. Re-routea las FKs entrantes y soft-deletea los duplicados. Si **ambos** estaban inactivos en el grupo, no reactiva nada (área histórica sin uso).

Resultado prod: 19 reclamos legacy de "Servicios Públicos" sin tilde (id=9, ya inactiva) reasignados al canónico "Secretaría de Servicios Públicos" (id=22), que ahora suma 19 reclamos + 49 subáreas + 184 tipos. Las 5 áreas activas finales son: Gobierno (1), Planeamiento con tilde (6 — renombrada 2026-05-15), Servicios Públicos con tilde (22), Seguridad con tilde (28), Tránsito con tilde (36). Snapshot pre-update en `_backup_area_2026_05_10` en ambos entornos.

**Operación por nombre normalizado, NO por ID hardcodeado** — los IDs canónicos difieren entre local y prod (local elige los sin-tilde porque eran los activos, prod elige una mezcla); la función `_ascii_fold(text)` se crea on-the-fly y se borra al final. Idempotente.

> Nota: `area.id_area=6` renombrada con tildes a "Secretaría de Planeamiento y Obras Públicas" en local y prod el 2026-05-15. Deuda cerrada.

### Migración 25 — `reclamos.id_empresa` (`backend/migrations/25_reclamos_id_empresa.sql`)

**Aplicada en local y prod al 2026-05-10.** Agrega `id_empresa INTEGER NULL REFERENCES empresas(id_empresa) ON DELETE SET NULL` en `reclamos` (1:1, opcional). El backend valida en POST/subreclamo que el ciudadano represente a la empresa via `ciudadano_empresa.activo=TRUE`; si no, 422. El subreclamo hereda `id_empresa` del padre por defecto (override permitido). El GET detalle hace JOIN con `empresas` y devuelve `empresa_nombre` y `empresa_cuit`. La N:M `ciudadano_empresa` (con `id_tipo_representacion`) sigue siendo la única fuente de verdad de qué empresas representa cada ciudadano — esta columna en `reclamos` solo guarda el "a nombre de quién" del reclamo puntual.

### Migración 24 — Re-seed de subarea + tipo_reclamo desde CSVs (`backend/migrations/24_reseed_subareas_tipos_desde_csv.sql` + `backend/seed_subareas_tipos_csv.py`)

**Aplicada en prod y local al 2026-05-09.** Re-seed completo desde `Tablas Iniciales/subarea.csv` (40) y `tipo_reclamo.csv` (288), más 9 subáreas inferidas como huérfanas. Resultado prod:

| Área canónica | id_area prod | Subáreas | Tipos |
|---|---|---|---|
| Secretaría de Servicios Públicos | 22 | 33 | 184 |
| Gobierno | 1 | 6 | 54 |
| Secretaría de Planeamiento y Obras Públicas | 6 | 5 | 27 |
| Subsecretaría de Tránsito | 36 | 4 | 16 |
| Secretaría de Seguridad | 28 | 1 | 1 |
| **Total** | — | **49** | **282** |

Áreas resueltas por heurística por keyword (ver `seed_subareas_tipos_csv.py`). Áreas huérfanas (sin subáreas activas) soft-deleted automáticamente. Snapshot pre-update en `_backup_pre_reseed_2026_05_09`.

> **Importante**: cualquier nueva sesión que toque estas tablas debe verificar el estado actual con `execute_sql` antes de aplicar cambios — esta sección puede quedar desactualizada (CLAUDE.md §24 lo formaliza).

### Migraciones 52-53 — Auth público de ciudadanos (App Vecinos Etapa 0)

**Aplicadas en local y prod al 2026-05-19.** Detalle en §38.

- **Mig 52** (`52_configuracion_municipio_branding.sql`): agrega 3 claves a `configuracion_general` (`municipio_descripcion`, `municipio_color_primary`, `municipio_color_accent`). Idempotente (`INSERT ON CONFLICT DO NOTHING`). Las 3 quedan vacías esperando carga desde el panel admin.
- **Mig 53** (`53_ciudadano_credencial_y_canales.sql`): agrega `ciudadanos.estado_validacion` (CHECK `auto_registrado|vinculado_pendiente|verificado`, default `auto_registrado`) + 3 tablas nuevas: `ciudadano_credencial` (1:1 con ciudadanos, password + tokens activación/recovery + lockout), `ciudadano_canal_preferido` (1:1, flags multi-canal), `ciudadano_push_subscription` (placeholder Web Push). Las 3 con estándar §10. Idempotente.

> **Nota sobre numeración mig 51**: hay dos archivos `51_*.sql` en `backend/migrations/` (`51_notificaciones.sql` y `51_tramites_tipo_dato_direccion.sql`). Ambos están aplicados en local y prod al 2026-05-19. La numeración duplicada es deuda cosmética; cualquier mig nueva debe usar 55+.

### Migración 54 — Adjuntos de OT (`backend/migrations/54_ot_adjuntos.sql`)

**Aplicada en local y prod al 2026-05-20.** Crea `ot_adjuntos` (estándar §10, FK `id_ot` → `ordenes_trabajo(id_ot) ON DELETE CASCADE`, índice `idx_ot_adjuntos_ot`). Espejo de `reclamo_adjuntos`. Cierra el hallazgo QA Royman #4 (adjuntos en OT diferido en commit `2110263`). Idempotente (`CREATE TABLE IF NOT EXISTS`). Ver §34 sección "Adjuntos de OT".

### Migración 55 — usuarios.id_subarea + es_externo (`backend/migrations/55_usuarios_subarea_externo.sql`)

**Aplicada en local y prod al 2026-05-22.** Agrega `usuarios.id_subarea INTEGER` (FK lógica → `subarea.id_subarea`, sin FK física, índice `idx_usuarios_subarea`) y `usuarios.es_externo BOOLEAN NOT NULL DEFAULT FALSE`. Idempotente (`ADD COLUMN IF NOT EXISTS`).

- **Subárea obligatoria salvo `es_externo`**: lo enforce el backend (`schemas/buc.py` model_validator en Create/Update) y el form, NO un NOT NULL en DB (los externos van con `id_subarea=NULL`). Habilita la regla de cierre directo de reclamo (ver §18).
- **Backfill random** (en la misma sesión, local + prod): se asignó subárea random a los 84 agentes sin subárea y a los usuarios no-externos sin subárea, vía `(abs(hashtext(pk::text)) % total_subareas) + 1` sobre `subarea WHERE activo`. Determinístico/reproducible. 0 filas quedaron sin subárea.
- **`usuarios` NO tiene `id_tipo_usuario`** — el `TABLE_CONFIG` y `SCHEMAS` de admin_tablas lo referenciaban (drift histórico que rompía el UPDATE de usuario); removido en esta sesión. La columna de pertenencia es `id_subarea` + `es_externo`.

### Migración 56 — tipo_tramite.es_sistema (`backend/migrations/56_tipo_tramite_es_sistema.sql`)

**Aplicada en local y prod al 2026-05-22.** Agrega `tipo_tramite.es_sistema BOOLEAN NOT NULL DEFAULT FALSE` para distinguir tipos precargados por seed (`TRUE`) de tipos custom creados por usuario desde el editor admin (`FALSE`). Backfill por **código** (no por id — regla §24) de los 9 tipos del seed original. `seed_tramites.py` ahora inserta `es_sistema=TRUE`. Idempotente. Ver §35 sección "Listado admin de tipos". **Ojo:** `tipo_tramite` (catálogo) NO tiene `id_usuario_alta` — la mig 50 sumó auditoría de usuario solo a las tablas de instancias; por eso se usa `es_sistema` y no `id_usuario_alta IS NULL` para distinguir origen. Ver memoria [[reference_tipo_tramite_sin_usuario_alta]].

### Migración 59 — Trigger de numeración de OT (`backend/migrations/59_ot_nro_trigger.sql`)

**Aplicada en local y prod al 2026-05-25.** Crea `fn_generar_nro_ot()` + trigger `trg_nro_ot` BEFORE INSERT en `ordenes_trabajo` (espejo de `fn_generar_nro_reclamo`) y backfillea las filas con `nro_ot` NULL. **El trigger NO existía en prod** pese a estar documentado en §18 — toda OT creada vía API salía sin número (el backend solo devolvía un fallback `OT-{id}` que no persistía). Idempotente. Ver [[feedback_verificar_trigger_existe_no_confiar_doc]].

### Migración 60 — Toggle anti-fatiga de encuestas (`backend/migrations/60_encuestas_antifatiga_toggle.sql`)

**Aplicada en local y prod al 2026-05-25.** Seed de la clave `encuestas_antifatiga_activo` (boolean, default `'true'`) en `configuracion_general`. Hasta entonces la regla anti-fatiga (no reenviar encuesta al mismo ciudadano/subárea dentro de 30 días) estaba hardcodeada. Ahora `encuestas_service.antifatiga_esta_activo(db)` la lee; `'false'` la desactiva (default seguro TRUE ante clave ausente/error). Editable desde Config → Sistema (§41). Idempotente.

### Migraciones 61-79 — resumen consolidado (bitácora movida desde CLAUDE.md §21 el 2026-06-10)

Las reglas vivas de cada una están en la sección del módulo correspondiente de CLAUDE.md; acá queda el registro histórico.

- **Mig 61** (2026-05-25): fila `modulos.encuestas` — sin ella el ítem del sidebar quedaba oculto para todos ([[feedback_modulo_react_necesita_fila_en_modulos]]).
- **Migs 62-64** (sesión 2026-05-26): 62 = `usuarios.fecha_ultimo_login` + tabla `usuario_login_log` (auditoría de accesos, append-only). 63 = `agentes.cuil`. 64 = índice UNIQUE parcial `agentes.id_usuario WHERE NOT NULL` (regla 1:1 agente↔usuario, §39).
- **Mig 65** (2026-05-26): fila `modulos.bi` (nombre "Datos", nivel 2) para el módulo BI §43.
- **Mig 66** (sesión 2026-05-27): `tramite.id_agente_actual` + CHECK `ck_tramite_destinatario` ampliado a 4 ramas (NULL/subarea/equipo/agente) — destinatario directo a un agente (§35).
- **Mig 67** (sesión 2026-05-27): `equipos.tipo_grupo` (`mesa_tramites`/`trabajo_reclamos`, default `mesa_tramites`) + CHECK `ck_equipo_subarea_reclamos` (subárea obligatoria solo si `trabajo_reclamos`) — mesa de entrada de trámites vs cuadrilla de reclamos (§15).
- **Mig 68** (sesión 2026-05-28): `tipo_tramite_transicion.tipo_accion` (aprobar/rechazar/derivar/avanzar/otro, default `avanzar`) + `.mensaje_iniciador` (TEXT) + `tipo_tramite_documento_requerido.cantidad_max_archivos` (SMALLINT 1-20, default 1) — editor de tipos, issues de Roy (§35).
- **Migs 69-70** (sesión 2026-05-28, Turnos/Disponibilidad §33): 69 = tabla `agente_novedad` (inasistencias/licencias/vacaciones; total o parcial por hora; resta disponibilidad efectiva) + clave `turnos_respeta_disponibilidad` (default `true`). 70 = `turnos.id_espacio` (FK espacios_agenda) + `id_agente` nullable + CHECK `ck_turnos_recurso` → turno polimórfico agente|espacio. **Incidente:** la 69 vía `apply_migration` falló a mitad en prod la 1ª vez (el INSERT a configuracion_general abortó la tx y revirtió el CREATE TABLE) → 500 en `/slots` hasta recrear `agente_novedad` ([[feedback_apply_migration_parcial_aborta_todo]]).
- **Mig 71** (sesión 2026-05-28, replanteo Turnos §33): renombró `tipo_servicio_turno` → `tipo_prestacion` (PK `id_tipo_prestacion`, FK en `turnos` renombrada) + `clase` (atencion/reserva_espacio) + `tipo_recurso` (agente/espacio) + `id_agente`/`id_espacio` (exactamente uno por CHECK `ck_tipo_prestacion_recurso` NOT VALID) + CHECK `ck_tipo_prestacion_reserva_espacio`. Solo DDL; seeds en `seed_turnos_demo.py`. Los CHECK NOT VALID igual se evalúan al UPDATE de filas viejas — el seed les asignó placeholder en el mismo UPDATE ([[feedback_check_not_valid_se_evalua_al_update]]). En prod se aplicó vía SQL directo por MCP (no hay `.env.prod`); prestaciones 4-7, 3 turnos demo recreados.
- **Mig 72** (sesión 2026-05-28, encuesta de turnos §42): `encuesta_envio.id_reclamo` deja de ser NOT NULL + FK `id_turno` + CHECK `ck_encuesta_envio_origen` (exactamente uno, NOT VALID) + índice parcial. El seed de la plantilla CSAT `tipo='turnos'` fue en `DO` block aparte del DDL (atomicidad); en prod DDL por `apply_migration` y seed por `execute_sql` separado.
- **Mig 73** (2026-05-31/06-01, visados de Trámites §35): `tipo_tramite_aprobacion_requerida` (catálogo versionado) + `tramite_aprobacion` (instancia) + valor `'aprobacion'` en el CHECK del ledger `tramite_movimiento`.
- **Mig 74** (sesión 2026-06-01, Fase 1 retención Trámites §35): `tramite.resultado` (`pendiente|aprobado|rechazado`, CHECK `ck_tramite_resultado`, default `'pendiente'`) + valor `'resultado'` en el CHECK del ledger.
- **Mig 75 + 75b** (sesión 2026-06-01, retención Trámites Fases 2-5 §35): `tipo_tramite.retencion_nunca_depurar` + `tramite.fecha_archivado`/`archivado_motivo` (CHECK `inactividad|manual`) + `tramite_documento.binario_purgado`/`fecha_purga_binario` + valores `'archivado_inactividad'`/`'purga_binario'` en el ledger + índices parciales. El seed de las 4 claves de config fue en `75b` SEPARADO del DDL (atomicidad). **DRIFT cazado:** prod tiene `configuracion_general.tipo` NOT NULL (`string|boolean|integer`) que local NO tiene — el `75b` arma el INSERT con o sin esa columna según exista ([[feedback_verificar_drift_completo_prod]]); en prod el seed fue por `execute_sql` con `tipo` explícito.
- **Mig 76** (sesión 2026-06-01, alta pública de vecinos §38): tabla `empresa_credencial` (1:1 con `empresas`, solo verificación de email — `token_verificacion`/`verificado`/`verificado_en`, SIN password) + índice parcial sobre el token. Local por psql, prod por `apply_migration`. El ciudadano reusa `ciudadano_credencial` (mig 53).
- **Migs 77-79** (2026-06-09, integridad de cuentas + alta vecino en 2 pasos): 77 = `usuarios.suspendido_motivo`/`fecha_suspension` (cron de integridad §39). 78 = `usuarios.debe_cambiar_password` (clave temporal + cambio forzado §39 Fase 3). 79 = `ciudadanos.ficha_completa` + `ciudadano_credencial.debe_cambiar_password` (alta del vecino en dos pasos §38/§39 Fase 4).

### Migración 81 — Subáreas de Seguridad para módulo Emergencias (`backend/migrations/81_emergencias_subareas_seguridad.sql`)

**Aplicada en local y prod al 2026-06-10** (Fase 1 del plan `PLAN_MODULO_EMERGENCIAS.md`). Data-only: crea las subáreas **"Policía Municipal"** y **"Defensa Civil"** bajo el área "Secretaría de Seguridad" **activa** de cada entorno, resuelta por nombre normalizado (sin tildes) + `activo=TRUE` — nunca por ID, porque los canónicos del cleanup de mig 26 difieren (local: id 8 sin tilde; prod: id 28 con tilde). Idempotente (NOT EXISTS por nombre normalizado). Resultado: local subáreas 90/91 bajo área 8; prod subáreas 76/77 bajo área 28. Las áreas duplicadas inactivas NO se tocaron. La verificación previa confirmó 0 tablas `emergencia_*`/COM preexistentes en ambos entornos (greenfield para Fase 2).

### Migración 80 — RLS en catálogos legacy (`backend/migrations/80_rls_catalogos_legacy.sql`)

**Aplicada en local y prod al 2026-06-09.** Disparada por el mail del advisor de Supabase `rls_disabled_in_public` (08-jun): `actividades`, `nacionalidades` y `tipos_representacion` eran las únicas tablas de `public` sin Row-Level Security — legibles/escribibles por cualquiera con la URL del proyecto + anon key vía PostgREST. Fix: RLS habilitado SIN políticas (patrón deny-all de mig 57 / §26). El backend no se afecta (conecta como `postgres`, dueño de las tablas, que bypassea RLS — verificado post-fix con `GET /publico/alta/nacionalidades` 200 en prod). El DO block tolera el drift local/prod del nombre (`tipo_representacion` singular en local, `tipos_representacion` plural en prod). Verificado: 0 tablas sin RLS en ambos entornos. En la misma sesión se habilitó RLS en `used_photos` del proyecto Supabase `zaris-news-bot` (otro proyecto, sin repo acá).


---

# Módulo Agenda — bitácora de implementación (extraído de CLAUDE.md §27, 2026-05-26)

> Histórico de cómo se construyó Agenda (migraciones, seeds demo, sub-fases entregadas, pendientes ya cerrados). Las **reglas vivas** (convenciones, bitmask, verbos HTTP, performance) quedaron en CLAUDE.md §27.

## Migraciones de Agenda (aplicadas local + prod 2026-05-12/13)

| # | Archivo | Qué hace |
|---|---|---|
| 30 | `30_agenda_municipios_y_tipo_reclamo.sql` | Crea `municipios` + ALTER `tipo_reclamo` (`duracion_estimada_min INT DEFAULT 60`, `asignacion_a VARCHAR(10) DEFAULT 'agente'` CHECK `agente|equipo`) |
| 31 | `31_agenda_catalogos.sql` | `estado_evento` (activo,finalizado,cancelado) + `estado_reserva` (reservada,asistio,cancelada) |
| 32 | `32_agenda_eventos_y_reservas.sql` | `eventos` + `evento_encargados` + `evento_reservas` |
| 33 | `33_agenda_ocupaciones.sql` | `ocupaciones` (tabla única con CHECK de consistencia por tipo `ot|evento|turno`) |
| 34 | `34_agenda_auditoria_y_conflictos.sql` | `conflictos_log` + `agenda_audit_log` |
| 35-37 | (autoservicio + defaults) | tokens públicos, defaults y NOT NULL. Ver tabla de migs arriba. |
| 39 | `39_agenda_legacy_dropear_y_estandarizar.sql` | Drop 9 tablas legacy vacías (`agenda_agente/servicio/lugar/...`, `turnos` legacy, `areas`). Estandariza `agenda_clase`/`agenda_feriado` al §10. Crea `ausencias_agente`. Cleanup FKs a `areas`. Snapshots `_backup_*_2026_05_13`. |
| 40-43 | (espacios + disponibilidad) | `espacios_agenda` + `espacio_agentes` + `disponibilidad_recurso`; CHECK `tipo_recurso` agrega `espacio`; `eventos.id_espacio`. |

Todas estándar §10 completo, PKs `id_<tabla>`, TIMESTAMPTZ, idempotentes.

Seed demo (`seed_agenda.py`): 4 agentes, 1 equipo, 1 evento "Vacunacion antigripal", 2 reservas, 3 ocupaciones.

## Sub-fases entregadas

- **1.B limpieza legacy** ✅ 2026-05-13 (mig 39). Detalle arriba.
- **2 Backend API** ✅ 2026-05-10: 22 endpoints en `agenda_v2.py`, servicios en `services/agenda.py`, schemas en `schemas/agenda_v2.py`. 13/13 E2E OK.
- **3.A Frontend React** ✅ 2026-05-10: módulo `web-app/src/modules/agenda/` (Timeline, Mensual, Eventos, Conflictos + modales).
- **3.B Drag & Drop** ✅ 2026-05-11: `@dnd-kit/core@6.3.1`, PointerSensor + KeyboardSensor, mover/reasignar/crear-desde-OT. `OcupacionUpdate` acepta `tipo_recurso`/`id_recurso`.
- **B1 Espacios + Disponibilidad (backend)** ✅ 2026-05-13: routers `agenda_espacios.py` + `agenda_disponibilidad.py`; `disponibilidad_efectiva()` + `_merge_rangos()`; schemas nuevos (`DisponibilidadRangoEfectivo`, `EventoEnCalendarioOut`, `CalendarioSemanaOut`, etc.); `/agenda/semana` nuevo. Compat retro 100%.
- **B2 Frontend** ✅ 2026-05-14 (commit `7186fe1`): 4 tabs (Vistas/Eventos/Conflictos/Config), sub-toggle Día/Semana/Mes, pills de tipo de recurso, CRUD de espacios y disponibilidad. Componentes: `VistasView`, `WeeklyView`, `ConfigView`, `RecursoTogglePills`, `EspaciosConfig`, `DisponibilidadConfig`, etc. Hallazgo fixeado: drift `id_municipio NULL` entre `/recursos/conteos` y grilla.
- **Pendientes post-B2** todos cerrados 2026-05-14 (commit `9bce2eb`): items `data-modulo` duplicados, eventos sin asignar en grilla, badge falta-vincular-agentes, drag en vista Semana, KeyboardSensor, título residual.

---

# §35 Trámites — bitácora completa (archivada desde CLAUDE.md 2026-05-31)

Extraída al optimizar CLAUDE.md. La versión condensada vive en §35 del CLAUDE.md vigente. Esto es el detalle histórico de fases 1/2/3, smokes, verificaciones E2E y repasos de Roy.

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
| `documentos.py` | Sube a Supabase Storage (bucket `tramites-documentos`, path `tramites/{anio}/{expediente}/{uuid}.{ext}`). SHA256 sobre los bytes. `crear_firmas_pendientes` desde `firmantes_jsonb`. |
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
| GET | `/{ref}/documentos/{id}/contenido` | `Response` con el binario descargado del bucket Supabase (inline). |
| POST | `/{ref}/documentos/{id}/firmar` | Verifica integridad SHA256 + registra evidencia de firma auditable. |
| POST | `/{ref}/documentos/{id}/rechazar-firma` | Marca rechazado + recalcula `estado_firma` del documento. |
| POST | `/{ref}/relacionar` | Vincula dos trámites (sorted para UNIQUE). Registra movimiento `relacion` en ambos. (201) |

**Reglas operativas críticas:**
- Toda mutación abre transacción y hace `SELECT ... FOR UPDATE` sobre `tramite` antes de modificar.
- `pase` y transición a estado final auto-liberan la toma (`id_agente_tomado_por = NULL`).
- `requiere_adjunto` se valida contando `tramite_documento.activo=TRUE` con `fecha_alta >= fecha_entrada_estado_actual`.
- El parámetro `iniciador_fks` de `resolver_iniciador` devuelve claves largas (`id_ciudadano_iniciador`, etc.); el INSERT las mapea explícitamente a `:cid`, `:eid`, `:crep`, `:sub_ini`.
- **Storage: Supabase Storage** (bucket privado `tramites-documentos`, migrado 2026-05-27 desde el mock local efímero). El backend recibe el archivo en multipart, calcula el SHA256 sobre los bytes (clave para firmas) y hace PUT al bucket con service_role (`storage.subir_objeto`). La descarga streamea desde el bucket (`storage.descargar_objeto`). `verificar_integridad_documento` recomputa el SHA256 descargando del bucket. `storage_path` es relativo al bucket: `tramites/{anio}/{expediente}/{uuid}.{ext}`. Reusa `app/core/storage.py` como Reclamos (§26) y OT (§34).

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

> **Quirk vigente (no específico de email):** reinicio de uvicorn obligatorio al cambiar `.env.local`. Las settings se cargan UNA VEZ al startup. `Start-Process python` sin matar el proceso anterior puede dejarlo corriendo con vars viejas (verificar `Get-Process python ... StartTime` antes del smoke). Memoria [[feedback_uvicorn_restart_tras_registrar_routers]].

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

**Mejoras de UX del editor de campos (hallazgos QA 2026-05-27, commits `32e0ed6`+`4b967a5`):** el `CampoModal` autocompleta el nombre interno desde la etiqueta visible (auto-slug, ver §23), valida en vivo con indicador ✓/✕, edita las opciones de `seleccion`/`seleccion_multiple` con filas {Etiqueta, Valor} en vez del textarea `valor|Etiqueta`, y `_modalShell` ya no cierra al arrastrar texto fuera del modal (click-outside exige mousedown+mouseup sobre el overlay). La lista de campos tiene botones ↑↓ (`useReordenarCampo` — ver issues 2026-05-28 abajo: reasigna `orden` 1..N por posición, NO swap). BUG-01 "Failed to fetch" del reporte era blip transitorio de Railway (§9), no código.

**Vista previa del formulario en vivo (BUG-06, 2026-05-27, commit `f049296`):** la tab Campos tiene un toggle **Editar / Vista previa**. En "Vista previa", `admin/components/PreviewFormulario.tsx` renderiza el formulario de inicio reusando el **mismo** `FormularioDinamico` de la pantalla de alta real (`CrearTramite`) — interactivo (botón "Probar validación") pero no guarda. Se actualiza solo al editar campos (react-query invalida la versión). **Quirk cazado:** `CampoDinamico` ahora normaliza `opciones_jsonb` tolerando el shape legacy `{opciones:[...]}` de los tipos seedeados viejos (antes `.map` reventaba); esto **también protege el alta real**. Ver [[feedback_normalizar_jsonb_de_seeds_viejos]]. El manual `docs/manual_admin_tramites.html` quedó actualizado a esta UI (commit `aec2d11`).

**Issues del editor de tipos — repaso de Roy (2026-05-28, mig 68, commit `a132e8f`):** 6 hallazgos del editor de "Tipos de trámite", todos resueltos y verificados en navegador (local + prod):
- **BUG-01 (publicar versión publicada):** el botón "Publicar" suelto solo aparece en `borrador`; en `publicado` se muestra un banner verde "Esta versión ya está publicada" que guía a "Nuevo borrador". `handlePublicar` además aborta si el estado cacheado ya no es borrador (evita el 409 del backend por stale). En `ConfigTramiteDetalle.tsx`.
- **BUG-02 (orden en Docs requeridos):** la tabla de docs ahora tiene columna **Orden** con ↑↓ (`useReordenarDocReq`) + columna **Máx. archivos**.
- **BUG-03 (reorden de Campos fallaba):** raíz = órdenes **duplicados** en los seeds (varios campos con `orden=1`), el swap viejo no movía nada. `useReordenarCampo` ahora recibe el array de IDs en el orden deseado y **reasigna `orden` 1..N por posición** (no swap). El sort de la tabla desempata por id. Backfill de órdenes (campos + docs) corrido en local y prod.
- **BUG-04 (acción de transición ambigua):** columna nueva `tipo_tramite_transicion.tipo_accion` (`aprobar`/`rechazar`/`derivar`/`avanzar`/`otro`). El `TransicionModal` la edita con **pills de color** y el listado pinta el badge de la transición según ella (verde aprobar, rojo rechazar, violeta derivar). La etiqueta sigue siendo texto libre, pero ahora hay una intención semántica explícita.
- **BUG-05 (mensaje al vecino según resultado):** columna nueva `tipo_tramite_transicion.mensaje_iniciador` (TEXT). El modal lo edita (textarea, visible si "Notifica al iniciador"). `notificar_estado_final_a_iniciador` (notificaciones.py) acepta `mensaje_custom` y se extendió para **enviar email al iniciador ciudadano/empresa** (antes solo notificaba in-app al área interna). El handler de transición solo notifica si `trans.notifica_iniciador`. Alcance acotado (mensaje por transición, NO sistema de plantillas).
- **BUG-06 (límite de archivos por doc):** columna nueva `tipo_tramite_documento_requerido.cantidad_max_archivos` (SMALLINT 1-20, default 1) + campo en `DocReqModal`.
- **Quirk cazado (importante):** `detalle_version` en `tramites_admin.py` arma la respuesta con SELECTs de **lista explícita de columnas** (uno por campos/estados/transiciones/docs). Agregar las columnas a la migración + schemas + INSERT/UPDATE + `_copiar_estructura` NO basta: hay que sumarlas también a esos SELECT o el endpoint las devuelve sin ellas (silencioso, el frontend las ve `undefined`). Se cazó leyendo el JSON crudo del endpoint, no el código. Ver [[feedback_columna_nueva_auditar_todos_los_select]].

**Issues del ALTA de trámite — repaso de Roy (2026-05-29, commits `8204a59`+`fe9a10f`, solo frontend):** el alta (`CrearTramite.tsx`) estaba rota por **dos mismatches de contrato frontend↔backend**, ambos verificados en vivo contra prod (Aviso de Obra):
- **Campos del builder no aparecían en el paso 4 (BUG-02/03) + botón "Crear trámite" mudo (BUG-01, capa 1):** `GET /tramites/tipos/{id}` (`TipoTramiteDetalleOut`) devuelve `campos`/`estados`/`transiciones`/`documentos_requeridos` **a NIVEL RAÍZ**, y `version` es SOLO metadata (`{id_tipo_tramite_version, version_num, estado, publicada_en}`). El frontend los leía en `tipo.version.campos` → `undefined` → paso 4 mostraba "no requiere datos adicionales" + `validarDatos(undefined,…)` tiraba TypeError **antes** del try/catch (el botón parecía muerto, sin toast). Fix: `TipoTramiteDetalle` (types.ts) refleja la shape real; `CrearTramite` lee `tipo.campos`. **El `PreviewFormulario` del editor SÍ mostraba los campos** porque consume el endpoint admin con shape plana — por eso confundía (en el builder se veían, en el alta no).
- **POST siempre daba 422 (BUG-01, capa 2, descubierto al verificar):** el frontend mandaba el body con shape **plana** (`iniciador_tipo`, `id_ciudadano_iniciador`, `datos_jsonb`, `id_tipo_tramite_version`) pero `TramiteCreateIn` espera `iniciador` **anidado** (`{tipo, id_ciudadano, id_empresa, id_subarea, id_ciudadano_representante}`) + `datos` (NO `datos_jsonb`) + `id_municipio`, y deriva la versión publicada del tipo (NO se manda `id_tipo_tramite_version`). Sin este fix, aunque los campos se renderizaran, el alta nunca completaba. Fix: `CrearTramiteBody` + `handleCrear` arman la shape anidada. Verificado E2E en prod desde la UI: alta de `AVO-LPL-2026-0001` OK → redirige al detalle (luego limpiado, numerador reseteado).
- **BUG-04 (flechas de orden no funcionan):** era **comportamiento correcto** — versión publicada con trámites instanciados es inmutable (`editable=false`), las flechas quedaban `disabled`. El bug real: se veían idénticas a las activas (el estilo inline `btnOrden` no tenía estado disabled). Fix: helper `btnOrdenStyle(disabled)` (opacidad 0.35 + `cursor:not-allowed`) + tooltip "Versión no editable" en los 4 botones (campos + docs). Lección: estilo inline no soporta `:disabled` — derivar el estilo condicionalmente.

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

### Aprobaciones por etapa (visados) — backend ✅ + builder frontend ✅; detalle frontend PENDIENTE (2026-05-31, mig 73, SIN commitear/pushear al cierre)

Marca paralela a los estados FSM: un área **aprueba/rechaza** una etapa; las marcas **bloqueantes impiden avanzar** hasta estar aprobadas. Modelo nuevo, separado de `tramite_firma` (firma digital con evidencia hash/IP) — conviven. Patrón catálogo+instancia.

**DB (mig 73 `73_tramites_aprobaciones_por_etapa.sql`, aplicada local + prod, verificado por MCP):**
- `tipo_tramite_aprobacion_requerida` (catálogo **versionado**): `id_tipo_tramite_version`, `id_tipo_tramite_estado` (la etapa), aprobador **polimórfico** (`aprobador_tipo` ∈ subarea|equipo|agente + CHECK `ck_ttar_aprobador_exactamente_uno`), `etiqueta`, `bloqueante BOOL` default TRUE, `id_tipo_tramite_documento_requerido` NULL (opcional), `orden`, + estándar §10.
- `tramite_aprobacion` (instancia): `id_tramite`, FK al requisito, `id_tipo_tramite_estado` (desnorm para guard rápido), `estado` pendiente|aprobada|rechazada, `resuelto_por_agente`/`resuelto_en`/`comentario`, `id_tramite_documento` NULL, + estándar §10. UNIQUE `(id_tramite, id_tipo_tramite_aprobacion_requerida)` = idempotencia.
- `'aprobacion'` agregado al CHECK `tramite_movimiento_tipo_check` (timeline).

**Backend — COMPLETO y verificado E2E API** (en disco; `versionado.py` + `admin/api.ts` ya en commit `e10723f`, el resto sin commitear): `services/tramites/aprobaciones.py` (instanciar al entrar a etapa idempotente, `aprobaciones_bloqueantes_pendientes`, `agente_puede_resolver` polimórfico, `aprobaciones_de_tramite`). En `routes/tramites.py`: instanciación en crear/transicionar; **guard 422** tras el bloque `requiere_adjunto` (espeja su patrón); endpoint `POST /tramites/{ref}/aprobaciones/{id_aprob}/resolver`; el **rechazo NO dispara transición** (deja el trámite trabado con motivo visible). 3 CRUD `/aprobaciones-requeridas` + `_aprob_fks` + bloque en `detalle_version` en `tramites_admin.py`. Copia en `versionado._copiar_estructura`. Schemas `AprobacionOut`/`ResolverAprobacionIn`/`AprobacionRequeridaIn` + campo `aprobaciones` en `TramiteDetalleOut`. Verificado: block 422 → resolve 200 → unblock 200→final, timeline `aprobacion`.

**Builder frontend — HECHO** (compila): tab "Aprobaciones" en `ConfigTramiteDetalle.tsx` (`SeccionLista` + `AprobReqModal.tsx`, reusa `listarDestinatariosPase`) + `admin/api.ts` (`TipoTramiteAprobReq`, `AprobReqBody`, 3 fns, campo en `DetalleVersion`) + `admin/hooks.ts` (3 hooks).

**Detalle frontend — PENDIENTE** (Fase 4, no escrito; el árbol compila igual porque nada lo referencia aún): falta `tramites/types.ts` (`TramiteAprobacion` + campo en `TramiteDetalle` — OJO el archivo real es `tramites/types.ts`, NO `lib/types.ts`), `lib/api.ts resolverAprobacion`, `hooks/useTramites.ts useResolverAprobacion`, `components/PanelAprobaciones.tsx` (panel verde/rojo/gris + Resolver + aviso de bloqueo) montado en `pages/DetalleTramite.tsx`. Paso-a-paso en [[project_tramites_aprobaciones_por_etapa]] / [[project_estado_sesion_y_pendientes]].


---

# §31 Limpieza de estilos legacy — CERRADA (archivada desde CLAUDE.md 2026-05-31)

Bloque cerrado 2026-05-12. La versión condensada vive en §31 del CLAUDE.md vigente. Esto es el detalle histórico (pasos, equivalencias --z-* → DS, útil solo si reaparece un módulo vanilla).

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

