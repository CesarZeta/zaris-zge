# PLAN DE IMPLEMENTACION - ATENCION POR UBICACION (Turnos reorganizados + Colero + Guardia + Historia Clinica + BI por gestion)

**Estado:** F1 + F2 + F2b (2026-09-01), F3 colero (2026-09-06, mig 105),
F4 Guardia (2026-09-06, migs 106 + 106b) y **F5 Historia clinica (2026-09-13,
migs 107 + 107b) HECHAS, verificadas y en prod**.
Siguiente: F6 (BI de atencion).
**Ultima revision:** 2026-09-13

---

## 0. CONTEXTO Y DECISIONES CERRADAS

### 0.1 Que es

Reorganizacion del acceso y la gestion de Turnos alrededor del concepto de
**UBICACION** (el lugar fisico donde se gestiona la atencion), mas cuatro
piezas nuevas:

1. **Pantalla de gestion de turnos scopeada por ubicacion** (hoy lista todos
   los turnos sin agrupamiento).
2. **Pantalla colero** por ubicacion para salas de espera (numeros + nombres
   de convocados, actuales e historicos, en pantalla grande/TV).
3. **Gestiones fijas** (Atencion Clinica / Cultura / Servicios Publicos) que
   agrupan ubicaciones y tienen su propio analisis BI con dimensiones propias
   (quien atendio, turnos caidos, tiempos de espera, etc.).
4. **Guardia + Historia Clinica**: las Emergencias derivan SIEMPRE a la
   ubicacion Guardia (salud) generando una atencion; toda atencion de salud
   (por turno o por emergencia) alimenta la historia clinica del vecino.

### 0.2 Decisiones cerradas con el usuario (2026-09-01)

| Decision | Valor |
|---|---|
| Que es una "ubicacion" | La entidad existente `espacios_agenda` (tiene subarea, direccion, capacidad, lat/lon). La tabla legacy `lugares_atencion` NO se usa (huerfana, sin FKs entrantes, id_area todo NULL) |
| Ubicacion de prestaciones por agente | Nueva columna `tipo_prestacion.id_espacio_ubicacion` ("donde se atiende"); para prestaciones por espacio = el mismo espacio. Se COPIA al turno al reservar (`turnos.id_espacio_ubicacion`), igual que el recurso (turno autocontenido) |
| Que es una "gestion" | Gestion = AREA existente. Salud (57) y Servicios Publicos (22) ya activas; Cultura se reactiva y se le cuelgan subareas. Hereda scoping por subarea, permisos y BI. Sin taxonomia paralela |
| Turnos por agente vs solo por ubicacion (decidido 2026-09-01, 2a ronda) | **Se mantienen AMBOS recursos** (agente O espacio: el recurso define de quien es la agenda que el turno consume — dos profesionales en el mismo edificio tienen grillas separadas) **+ la ubicacion es OBLIGATORIA en toda prestacion de atencion** (backend 422 en POST/PUT de prestaciones + form). Jerarquia: Gestion (area) -> Ubicacion (espacio) -> Agentes que atienden ahi -> Turnos |
| Atenciones derivadas de Emergencias | **NO van con turno** (definicion explicita de Cesar). La derivacion a Guardia genera una ATENCION DIRECTA en registro propio (`emergencia_atencion`), vinculada al evento COM. Sin turno de por medio |
| Historia clinica (esta etapa) | Minima viable: timeline por ciudadano leyendo DOS fuentes (`turno_atencion` + `emergencia_atencion`), permiso restringido a gestion Salud + admin. Ficha clinica ampliada (diagnostico, antecedentes) queda para etapa 2 |
| Privacidad pantalla colero | Numero + nombre e inicial de apellido (ej. "A-014 - Maria G."). Criterio Ley 25.326: no exponer identidad completa en pantalla publica |

### 0.3 Criterios profesionales aplicados (delegados por el usuario)

| Criterio | Justificacion |
|---|---|
| Colero = pagina publica tokenizada (no pop-up interno) | Una TV no puede mantener sesion JWT. Token UUID no enumerable por espacio (`token_pantalla`, mismo patron que `token_turno`). Polling ~5s. El endpoint publico devuelve SOLO numero + nombre display |
| Estados nuevos `llamado` y `ausente` en turnos | Sin `ausente` no se puede medir la tasa de turnos caidos (KPI pedido). Sin `llamado` no hay colero ni tiempo de espera real |
| Log `turno_llamado` (llamados y re-llamados) | El tiempo de espera real (hora de llamado vs hora del turno) es KPI del BI; el estado solo no captura re-llamados |
| Numero diario visible por ubicacion (ej. A-014) | El vecino se referencia por numero corto, no por id interno. Se asigna secuencial por ubicacion+fecha |
| Guard de permisos SIEMPRE en backend | Historia clinica = dato sensible Ley 25.326. Hoy la ve cualquier nivel <=2; pasa a gestion Salud + admin |
| Refresh del colero por polling (no WebSocket) | MVP simple, mismo criterio que el tablero de Emergencias |

### 0.4 Realidad verificada en prod (2026-09-01, execute_sql)

- `espacios_agenda`: 7 activos (Consultorio Municipal/subarea 79, Sala Odontologia/78, Mesa de Atencion/68, Sala Tramites Express/68, Auditorio/69, Teatro/74, SUM/74).
- `turnos.estado` CHECK: solo `reservado|cumplido|cancelado`. `origen` CHECK: `backoffice|autoservicio`.
- `turnos` guarda `id_agente` XOR `id_espacio` (recurso copiado, mig 70) — un turno por agente NO sabe donde se atiende. Ese es el gap central que resuelve F1.
- `turno_atencion` (mig 86) ya existe: 1:1 turno, `intervencion` + `recomendaciones`, consulta por ciudadano. Base de la historia clinica.
- Areas activas: Gobierno(1), Planeamiento(6), Serv.Publicos(22), Seguridad(28), Transito(36), Salud(57). Cultura solo inactiva (12/37/45).
- `emergencia_evento`: sin concepto de derivacion interna a guardia (solo `id_organismo_derivacion` externo).

---

## 1. ESTANDARES APLICABLES

Referencia primaria: `CLAUDE.md` (raiz). Recordatorios criticos:

- Migraciones desde **103** (la 51 esta duplicada; ultima aplicada 102), idempotentes, aplicadas LOCAL y PROD en la misma sesion. Tabla nueva => `ENABLE ROW LEVEL SECURITY`. Seeds separados del DDL.
- **Anti-carrera mig 95 obligatorio** en toda via nueva de escritura de turnos: advisory locks en orden fijo + captura `IntegrityError` -> 409 + CAS de estado en UPDATEs.
- Columna nueva expuesta => **auditar TODOS los SELECT** del modulo (TurnoOut en listar/detalle/atenciones/publico) + mapearla en el modelo ORM (columna no mapeada = setattr silencioso).
- `CAST(:p AS tipo)` en raw SQL asyncpg; sin acentos en strings Python.
- Orden de routers: rutas especificas antes que `{param}` greedy (`/turnos/publico` y `/turnos/atenciones` ANTES de `/turnos/{id}`; aplica a lo nuevo tipo `/turnos/pantalla/*`).
- Frontend React: tokens DS via CSS Modules, `ConfirmModal` (no `window.confirm`), sin emoji, `hasPermission` + guard espejo en backend.
- Ruta publica nueva del bundle => sumarla a la whitelist del guard standalone en `web-app/index.html` (quirk Q12 de win-quirks) — aplica a `/pantalla/:token`.
- Verificacion visual navegando en la interfaz antes de declarar terminado (estandar §41).

---

## 2. MODELO DE DATOS

### 2.1 Mig 103 — Ubicacion de atencion (F1)

```
ALTER TABLE tipo_prestacion ADD COLUMN id_espacio_ubicacion INTEGER
  REFERENCES espacios_agenda(id_espacio);   -- NULL = sin ubicacion asignada
ALTER TABLE turnos ADD COLUMN id_espacio_ubicacion INTEGER
  REFERENCES espacios_agenda(id_espacio);   -- copiado de la prestacion al reservar

-- Backfill: las prestaciones/turnos cuyo RECURSO ya es un espacio
UPDATE tipo_prestacion SET id_espacio_ubicacion = id_espacio
  WHERE tipo_recurso = 'espacio' AND id_espacio IS NOT NULL
    AND id_espacio_ubicacion IS NULL;
UPDATE turnos SET id_espacio_ubicacion = id_espacio
  WHERE id_espacio IS NOT NULL AND id_espacio_ubicacion IS NULL;

CREATE INDEX ix_turnos_ubicacion_fecha ON turnos (id_espacio_ubicacion, fecha);
```

Los turnos viejos por agente quedan `NULL` ("sin ubicacion") hasta que la
prestacion tenga ubicacion cargada; el frontend los muestra en un bucket
"Sin ubicacion" para que no desaparezcan (leccion filtros legacy mig 27).

### 2.2 Mig 105 — Ciclo de llamado + colero (F3)

```
turnos.estado           += 'llamado', 'ausente'   (recrear CHECK)
turnos.numero_diario    VARCHAR(10)               -- ej. 'A-014', secuencia por ubicacion+fecha
turno_llamado           (id_turno_llamado PK, id_turno FK, puesto VARCHAR NULL,
                         llamado_en TIMESTAMPTZ, id_usuario_llama FK usuarios,
                         + campos estandar §10, RLS)
espacios_agenda.token_pantalla UUID UNIQUE DEFAULT gen_random_uuid()
```

FSM resultante: `reservado -> llamado -> cumplido | ausente`, con
`reservado -> cancelado` y `llamado -> llamado` (re-llamado, va al log).
Cumplir/cancelar siguen funcionando desde `reservado` (mesa sin colero).
CAS de estado en todos los UPDATE nuevos.

### 2.3 Mig 106 — Guardia + atencion por emergencia (F4)

```
emergencia_atencion (
  id_emergencia_atencion PK,
  id_emergencia_evento   FK emergencia_evento NOT NULL,
  id_ciudadano           FK ciudadanos NULL,     -- evento anonimo/contacto eventual => NULL
  id_espacio_ubicacion   FK espacios_agenda NOT NULL,  -- la Guardia
  id_agente_atiende      FK agentes NULL,
  intervencion           TEXT NOT NULL,
  recomendaciones        TEXT NULL,
  atendido_en            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  + campos estandar §10, RLS
)
configuracion_general: clave 'id_espacio_guardia' (tipo integer, activo true explicitos)
```

La accion "Derivar a Guardia" del evento COM crea la fila (intervencion se
completa al atender) y queda en el log del evento. Historia clinica =
`turno_atencion` UNION `emergencia_atencion` por `id_ciudadano` (patron
polimorfico LEFT JOIN, como encuesta_envio).

### 2.4 Migs 107 + 107b — Historia clinica (F5)

```
historia_clinica_acceso (
  id_historia_clinica_acceso PK BIGSERIAL,
  id_usuario     FK usuarios ON DELETE RESTRICT NOT NULL,
  id_ciudadano   INTEGER NOT NULL,           -- SIN FK a ciudadanos: registra tambien ids inexistentes
  fecha_hora     TIMESTAMPTZ DEFAULT NOW(),
  origen         'historia' | 'export',      -- 'export' reservado para etapa 2
  contexto       turno | guardia | mesa | consulta | otro,
  resultado      ok | denegado | inexistente,
  motivo         VARCHAR(20),                -- admin | admin_sin_config | salud | nivel | sin_agente | sin_subarea | fuera_salud | sin_config
  n_registros    INTEGER NULL,               -- NULL si denegado
  ip, user_agent, id_municipio
)  -- append-only (triggers no_update/no_delete), RLS, indices por ciudadano y por usuario
configuracion_general: clave 'id_area_salud' (integer, activo explicitos) —
  area ACTIVA "Secretaria de Salud" resuelta POR NOMBRE (56 local / 57 prod)
```

Guard (`app/services/historia_clinica.py::permiso_historia_clinica`): nivel 1
SIEMPRE (motivo `admin_sin_config` si falta la clave); niveles 2-4 solo si
`agentes.id_subarea` (regla 1:1 §39, NO `usuarios.id_subarea`) cuelga del area
de la clave con area + subarea + agente activos; nivel 5 nunca; 403 accionable
evaluado ANTES de leer la BUC. `/turnos/atenciones` (mig 86) conserva su scope
generico. Union = `turno_atencion` + `emergencia_atencion` atendida|ausente
(`pendiente` es estado de mesa, no historia). Todo acceso (incluso denegado o
sobre un id inexistente) se registra en `historia_clinica_acceso` dentro de la
misma transaccion, antes de responder.

---

> **Renumeracion (2026-09-06):** la **104** la tomo `tipo_tramite.id_subarea`
> (gestion responsable del tipo de tramite, ordenamiento de Cesar para el smoke
> de la demo — ver `HISTORIAL_MIGRACIONES.md`), que se aplico antes que F3.
> Por eso el colero pasa a la **105** y la guardia a la **106**.

## 3. FASES

### F1 — Modelo Ubicacion (HECHA 2026-09-01 — smoke 16/16 + verificacion visual)

- Mig 103 local + prod.
- Modelos ORM (`tipo_prestacion`, `turnos`) + schemas Pydantic.
- `routes/turnos.py`: crear/reprogramar copian `id_espacio_ubicacion` de la
  prestacion; `TurnoOut` y `TipoPrestacionOut` exponen `id_espacio_ubicacion`
  + `ubicacion_nombre` (JOIN espacios_agenda) en TODOS los SELECT.
- `turnos_publico.py` + `publico_turnos_vecino.py`: el INSERT publico tambien copia la ubicacion.
- Frontend: `PrestacionFormModal` suma selector de ubicacion (useEspacios);
  tipos TS; columna/chip de ubicacion en listados existentes (minimo).

### F2 — Pantalla de gestion por ubicacion (NUCLEO HECHO 2026-09-01 — smoke 15/15 + visual; falta F2b)

Entregado:
- **Regla obligatoria**: POST/PUT de prestaciones exige `id_espacio_ubicacion`
  (422) + validacion en el form. Prestaciones demo backfilleadas en local Y
  prod (0 activas sin ubicacion en ambos).
- **Landing** (`pages/Ubicaciones.tsx`, index del modulo): cards por GESTION
  (area) -> ubicaciones con direccion, subarea, N agentes, N prestaciones y
  contadores del dia. Backend `GET /turnos/ubicaciones` (espacios activos que
  son ubicacion de una prestacion o tienen espacio_agentes; contadores con el
  MISMO scope por nivel que GET /turnos). Boton "Todos los turnos" (escape).
- **Mesa del dia** (`pages/MesaUbicacion.tsx`, tab "Mesa del dia"): grilla
  horaria con una columna por recurso (el espacio + cada agente de la
  ubicacion via espacio_agentes ∪ prestaciones), franjas de disponibilidad
  efectiva de fondo + bloques de ocupacion; clic en turno -> detalle; alta
  rapida. Backend `GET /turnos/ubicaciones/{id}/mesa` (usa
  `disponibilidad_efectiva_batch` §27; guard: nivel 3-4 solo su subarea o
  donde es agente, 404). **Turno del agente en OTRA ubicacion viene
  ENMASCARADO desde el backend** (bloque "Ocupado en otra ubicacion", sin
  ciudadano/prestacion/estado — muestra la indisponibilidad sin exponer la
  otra mesa) y no cuenta en los contadores.
- **Contexto persistente** (`stores/ubicacionTurnos.ts`, zustand+persist
  `zaris_turnos_ubicacion`): barra "Ubicacion: X · Cambiar/Quitar" en el
  layout; Turnos (lista), Agenda y Atendidos filtran por
  `id_espacio_ubicacion` (filtro backend nuevo en GET /turnos). Tabs nuevas:
  Ubicaciones (index) / Mesa del dia / Turnos (`/turnos/lista`) / resto igual.

**F2b (HECHA 2026-09-01 — smoke 10/10 + visual dia/semana/estado vacio):**
modo UBICACION en el modulo AGENDA. Pill nueva "Por ubicacion" (primera del
toggle) + select agrupado por gestion (consume `GET /turnos/ubicaciones` por
URL directa — SIN importar codigo del modulo Turnos, para no armar dependencia
circular). Backend: `id_espacio_ubicacion` en `/agenda/calendario` y
`/agenda/semana` (helper `_recursos_de_ubicacion` = espacio + agentes via
espacio_agentes ∪ prestaciones; mismo shape que el listado normal, el pipeline
ocupaciones/ausencias/disponibilidad batch no cambia; ignora
tipo_recurso/atendido/subarea; 404 si la ubicacion no existe; compat retro
verificada). Vistas Dia y Semana muestran la grilla mixta (espacio + agentes)
con disponibilidad y bloques; sin ubicacion elegida -> prompt. NOTA: a
diferencia de la Mesa de Turnos, la grilla de Agenda NO enmascara las
ocupaciones del agente en otra ubicacion — es la agenda del recurso y siempre
mostro todas sus ocupaciones (comportamiento historico del modulo, cualquier
autenticado). Vista Mes queda fuera del modo ubicacion (muestra eventos).

Pendiente residual de F2: los turnos LEGACY por agente sin ubicacion solo se
ven en "Todos los turnos" (sin seleccion); no hay bucket dedicado.

### F3 — Ciclo de llamado + Pantalla colero (HECHA 2026-09-06 — smoke 18/19 + 12/12 + verificacion visual)

- Mig 105 local + prod.
- Endpoints: `PATCH /turnos/{id}/llamar` (asigna numero_diario si falta,
  inserta turno_llamado, estado -> llamado; re-llamar = mismo endpoint),
  `PATCH /turnos/{id}/ausente`. Guard de scope + CAS.
- Mesa de atencion: botones Llamar / Re-llamar / Cumplir / Ausente + columna
  numero. Numeracion: secuencia diaria por ubicacion (advisory lock
  `colero:{id_espacio}:{fecha}` para no duplicar numero).
- Publico: `GET /api/v1/turnos/pantalla/{token_pantalla}` (sin auth, rate
  limited con prefijo `pantalla:`) -> `{ ubicacion, llamando: [...], previos: [...] }`
  con nombre display "Nombre I." SOLO.
- Frontend publico: `/pantalla/:token` fullscreen (tipografia display gigante,
  tokens DS, dark-friendly), polling 5s, destacado del ultimo llamado +
  lista de previos. Whitelist en `web-app/index.html`. Boton "Abrir pantalla /
  copiar link" en la mesa (nivel <=2).

**Entregado (2026-09-06):** mig 105 en local Y prod (estados `llamado`/`ausente`,
`turnos.numero_diario`, tabla `turno_llamado` append-only, `espacios_agenda.token_pantalla`
+ `prefijo_colero`). Backend: `PATCH /turnos/{id}/llamar` (asigna numero con advisory
lock `colero:{id_espacio}:{fecha}`, re-llamar = mismo endpoint, CAS de estado) y
`PATCH /turnos/{id}/ausente`; cumplir/cancelar ahora aceptan tambien `llamado`;
`GET /turnos/publico/pantalla/{token}` sin auth con rate limit `pantalla:`.
Frontend: `PanelAtencion` en la Mesa del dia (numero + Llamar/Re-llamar/Atendido/
Ausente + campo Puesto recordado + "Abrir pantalla"/"Copiar link" solo nivel <=2) y
`/pantalla/:token` fullscreen con polling 5 s.

**Decisiones tomadas en F3 (cerraban pendientes del §4):**
- **Formato del numero**: correlativo diario de 3 digitos por ubicacion, con
  prefijo OPCIONAL por ubicacion (`espacios_agenda.prefijo_colero`, VARCHAR(4)).
  Sin prefijo cargado sale `014`; con prefijo `A`, sale `A-014`.
- **El numero se asigna al PRIMER llamado**, no al reservar: un turno que nunca
  se llama no consume numero (la numeracion del dia no queda con huecos).
- **`ausente` NO libera el slot** (la ocupacion espejo se mantiene, igual que
  cumplido): el turno ocurrio y su franja es historica. Solo cancelar libera.
- **Ausente tambien se acepta desde `reservado`** (no solo desde `llamado`): la
  mesa cierra turnos que nunca llego a llamar.
- El endpoint publico quedo bajo `/turnos/publico/pantalla/{token}` (router sin
  auth ya existente) en vez de `/turnos/pantalla/{token}`: abrir un hueco sin
  `get_current_user` en el router autenticado es fragil ante un guard futuro a
  nivel router, que ademas no se puede anular por handler.
- **Sonido/chime**: RESUELTO 2026-09-06 (decision de Cesar: "que se active con un
  boton"). La pantalla `/pantalla/:token` tiene el boton "Activar sonido" (el
  gesto destraba el AudioContext); a partir de ahi cada llamado nuevo (llamado_en
  mas reciente que el ultimo visto) dispara un chime sintetizado con Web Audio.
- **Prefijo del numero**: formato fijado por Cesar 2026-09-06 — EXACTAMENTE 3
  alfanumericos + "-" + correlativo de 3 digitos (`ODO-001`). Validado en el
  schema (`normalizar_prefijo_colero`: strip/upper, 422 si no son 3) y cargable
  desde Agenda -> Config -> Espacios (campo "Prefijo del colero"). Vacio = `001`.

### F4 — Guardia + derivacion desde Emergencias (HECHA 2026-09-06 — smoke 23/23 + verificacion visual)

**Entregado (2026-09-06):** mig **106** (DDL) + **106b** (seed) en local Y prod.
`emergencia_atencion` con `estado` pendiente|atendida|ausente (el plan decia
"intervencion NOT NULL": paso a NULL hasta atender, con CHECK `atendida =>
intervencion + atendido_en`), `paciente_nombre` libre (el denunciante NO es
necesariamente el paciente; evento anonimo => la Guardia lo identifica) y UNIQUE
parcial "una pendiente por evento" (re-derivar => 409; cerrada => se puede volver
a derivar). Seed por NOMBRE: subarea "Emergencias" bajo Secretaria de Salud
(local 115 / prod 82), espacio "Guardia" (local 12 / prod 9, prefijo GUA,
atendido) y clave `configuracion_general.id_espacio_guardia`.
**Emergencias:** `POST /eventos/{id}/derivar-guardia` (motivo obligatorio,
paciente BUC o nombre) — **NO es transicion del FSM**: el evento sigue su ciclo;
solo DESESTIMADO no deriva (422). Log `DERIVACION_GUARDIA`; `_SELECT_EVENTO`
expone `guardia_atencion_id/estado/derivado_en` (LATERAL: pendiente primero).
Boton "Derivar a la Guardia" en el detalle (tambien en RESUELTO) con modal
`DerivarGuardiaModal`; dato "Guardia" en la tab Datos.
**Turnos:** la Guardia entra a la landing por la clave (badge GUARDIA + "N
derivaciones pendientes") y su mesa muestra `PanelGuardia` (pendientes de
cualquier dia + cerradas del dia, polling 30 s; Atender = modal con
intervencion obligatoria, recomendaciones y vinculo opcional a BUC via
`CiudadanoSearch`; "No se presento" = ausente). Endpoints
`GET /turnos/guardia/atenciones?fecha=&estado=`, `PATCH .../{id}/atender`,
`PATCH .../{id}/ausente` (segmentos fijos antes de `/{id_turno}`), guard = el
mismo alcance que la mesa (nivel <= 2 todo; 3-4 solo subarea de la Guardia o
agente vinculado; 404 generico). El log del evento recibe `ATENCION_GUARDIA`
**sin el detalle clinico** (el COM lee ese log; la intervencion queda solo en
la atencion — Ley 25.326). Servicio compartido `app/services/guardia.py`.

- **DEFINICION DE CESAR (2026-09-06): la Guardia vive en el area Secretaria de
  Salud, bajo una subarea "Emergencias"** ("debe estar en el area de salud de
  emergencias"). Verificado en prod: Secretaria de Salud (id 57, activa) tiene
  hoy solo Odontologia (78) y Clinica medica (79) — la subarea Emergencias NO
  existe y la crea la mig 106 (resolver el area POR NOMBRE, nunca por id: en
  local Salud tiene otro id, §24). F4 queda destrabada.
- Mig 106 local + prod. Subarea "Emergencias" (bajo Secretaria de Salud) +
  espacio "Guardia" en esa subarea, seed + clave de config.
- Emergencias: accion "Derivar a Guardia" en el detalle del evento (respeta
  FSM del modulo — invocar skill modulo-emergencias antes de tocar) -> crea
  `emergencia_atencion` + entrada en `emergencia_log`.
- Pantalla de la Guardia (dentro de Turnos, la mesa de esa ubicacion): lista
  las atenciones derivadas pendientes + completar intervencion/recomendaciones.
- SIN turnos de por medio (decision cerrada 0.2).

### F5 — Historia clinica (minima viable) (HECHA 2026-09-13 — smoke 61/61 + verificacion visual)

**Entregado (2026-09-13):** migs **107** (log de accesos `historia_clinica_acceso`,
append-only) + **107b** (clave `configuracion_general.id_area_salud` por nombre del
area activa "Secretaria de Salud": 56 local / 57 prod) en local y prod.
**Backend:** `GET /turnos/atenciones/historia?id_ciudadano=&contexto=&limit=&offset=`
(+ `GET /turnos/atenciones/historia/permiso` para la UI) en `routes/turnos.py` junto
a `/atenciones` (segmentos fijos de 2-3 niveles, inmunes al greedy `/{id_turno}`);
servicio `app/services/historia_clinica.py` (unica fuente del permiso + SQL);
`UNION ALL` de `turno_atencion` y `emergencia_atencion` (atendida|ausente) con
`origen`, fecha normalizada a UTC-3, `COUNT(*) OVER ()` para el total; rate limit
`hc:{id_usuario}` 60/min; markers OpenAPI 403/404/429; `id_ciudadano` acotado a
int32 (`le=2147483647`, cazado por el smoke: un id mayor daba 500 y el intento no
quedaba en el log). **Frontend:** `components/HistoriaClinica.tsx` (Panel embebible,
Modal a nivel pagina y Boton, los tres gateados por `/permiso`); 3a solapa lazy
"Historia clinica" en `TurnoDetalleModal`; boton por fila en `PanelGuardia` (solo
pendientes con BUC) y en `PanelAtencion` (incluidas las cumplidas); `<details>`
cerrado con el Panel compacto dentro de `AtenderGuardiaModal`; 3a solapa en
`Consultas`; `ApiError` con `status` en `lib/api.ts` (retrocompatible) para el
403 amigable; seccion "Atencion (Turnos, Guardia e historia clinica)" en Config →
Sistema con `id_espacio_guardia` e `id_area_salud`. **Smoke** in-process
`backend/smoke_atenciones_historia.py` (61 casos; fixtures `f5*@municipio.gob.ar`
SOLO local; `--rate` para el 429).

**Decisiones tomadas en F5:**
- **Gestion Salud = clave de config `id_area_salud`** (no nombre en runtime ni
  derivada de la Guardia): `ILIKE '%salud%'` pesca 4 areas en local (3 inactivas) y
  hardcodea un string de negocio. Mismo patron que `id_espacio_guardia`. Sin la
  clave, fail-closed para niveles 2-4 (`sin_config`); nivel 1 ve la historia con
  motivo `admin_sin_config` y la UI le avisa que configure.
- **Nivel 5 (Consultor) excluido** aunque su agente sea de Salud.
- **Areas "Salud" inactivas excluidas**: el guard exige area + subarea + agente
  activos y compara por id con la clave (caso `administrativo@` local → `fuera_salud`).
- **`pendiente` fuera, `ausente` dentro** de la historia: la pendiente es la cola
  viva de la Guardia; la ausencia es un hecho clinico (no se presento).
- **403 accionable (no 404) evaluado ANTES de leer la BUC**: quien no es Salud
  recibe el mismo 403 sea cual sea el id (no revela existencia). Los mensajes
  dicen que falta (agente, subarea, clave, nivel).
- **Ciudadano dado de baja en la BUC SI muestra su historia**, con
  `ciudadano.activo=false` y aviso en la UI (la baja logica no borra hechos clinicos).
- **Log NO best-effort**: INSERT + commit antes de responder, incluye 403
  (`denegado`) y 404 (`inexistente`); si el registro falla, la lectura falla.
  `/permiso`, 401, 422 y 429 no registran (no llegan a datos). Sin pantalla de
  auditoria en F5 (consulta por SQL; `admin_tablas` NO la whitelistea).
- **Sin export PDF de la historia clinica** (dato sensible fuera del sistema sin
  registro: etapa 2 con `origen='export'`).
- **Sin flag en login/`/me`**: la capacidad se pregunta a `/permiso` (misma
  funcion que el guard, cero drift UI↔API, cache 5 min por usuario). Prohibido
  derivar la visibilidad de `nivel_acceso`/`id_subarea` de la sesion.
- **Nunca apilar dos `Modal` de Agenda** (comparten el listener de ESC): el modal
  HC se abre solo desde tablas a nivel pagina; dentro de `TurnoDetalleModal`,
  `AtenderGuardiaModal` y `Consultas` se embebe el Panel.
- **Query key con `limit`** (`['turnos','historia','ciudadano',id,contexto,limit]`)
  para que "Ver mas" dispare una lectura nueva (y una fila nueva en el log).
- **En la solapa "Historia clinica" de Consultas el boton "Exportar PDF" no se
  ofrece** (la HC no se exporta y exportar "otra cosa" desde ahi sorprende); en
  las otras dos solapas sigue igual. Ver pendiente en §4.
- `CumplirTurnoModal` y `DetalleEvento` (COM) NO son puntos de entrada (el COM no
  ve detalle clinico; el camino critico del cumplir no se toca).

Plan original de F5 (referencia):

- Endpoint `GET /atenciones/historia?id_ciudadano=` unificando ambas fuentes,
  orden cronologico, con origen (turno/prestacion vs emergencia/evento).
- Guard nuevo: SOLO agentes cuya subarea pertenece al area Salud + nivel 1.
  Reemplaza el scope generico actual de `/turnos/atenciones` PARA la vista
  historia clinica (el endpoint viejo conserva su semantica).
- Vista React "Historia clinica" (timeline) accesible desde el detalle del
  turno/mesa de guardia y desde la consulta por ciudadano.

### F6 — BI de Atencion por gestion

- Tablero nuevo en Datos (skill modulo-bi obligatoria): por gestion (area) y
  drill-down por ubicacion/prestacion/agente.
- Metricas: otorgados / cumplidos / ausentes / cancelados, tasa de
  ausentismo, tiempo de espera real (turno_llamado vs hora turno), atenciones
  por agente, ocupacion por ubicacion, origen (backoffice/autoservicio),
  atenciones de guardia por emergencia, CSAT de turnos (ya existe §42).
- Cultura: reservas/asistencia de eventos y clases (entradas + agenda).

### Orden y dependencias

F1 -> F2 -> F3 es la cadena critica. F4 depende solo de F1 (necesita la
ubicacion Guardia). F5 depende de F4. F6 depende de F3 (llamados) y F4
(guardia) para estar completa, pero puede arrancar con lo de F1/F2.

---

## 4. PENDIENTES / ABIERTOS

- Walk-in de guardia SIN evento de emergencia (vecino que llega solo): fuera
  de alcance por ahora; la demanda de guardia entra via Emergencias.
- ~~Sonido/chime en la pantalla colero al llamar~~ **RESUELTO 2026-09-06**: se
  activa con un boton en la pantalla (decision de Cesar); ver F3.
- ~~Formato del numero diario~~ **RESUELTO en F3**: correlativo de 3 digitos por
  ubicacion + prefijo opcional configurable (`espacios_agenda.prefijo_colero`).
- Reactivacion del area Cultura + subareas + ubicaciones reales: dato de
  negocio que carga Cesar cuando arranque F2/F6.
- Ficha clinica ampliada (motivo, diagnostico, antecedentes): etapa 2 de F5.
- Etapa 2 HC: vista admin de `historia_clinica_acceso` (hoy por SQL); export PDF
  con log `origen='export'`; motivo obligatorio break-the-glass cuando quien
  consulta no atendio nunca al paciente; aviso al vecino en la PWA; panel HC
  dentro de `CumplirTurnoModal` si Salud lo pide.
- Export PDF de Consultas → "Prestaciones realizadas" saca intervencion/
  recomendaciones sin guard Salud ni registro (hereda el scope generico de
  `/turnos/atenciones`): **DECISION DE CESAR pendiente** (quitar / gatear por
  `/permiso` / dejar). Desde F5, estando en la solapa "Historia clinica" el boton
  exporta el listado de turnos (no las prestaciones realizadas).
- Canal lateral `turnos.observaciones`: prestaciones de Salud sin
  `registra_atencion` (local: 6 Clinica general) pueden recibir texto clinico
  visible al vecino; marcar `registra_atencion=true` en TODAS las prestaciones de
  Salud (dato de negocio, prod no verificado).
- Derivaciones de Guardia sin BUC (paciente por nombre libre) quedan fuera de la
  HC hasta vincular el ciudadano (no hay listado de huerfanas).
- Rate limit `hc:{id_usuario}` es in-memory por instancia (se resetea en cada
  deploy): defensa en profundidad; la contramedida principal es el log.
