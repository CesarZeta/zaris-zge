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
