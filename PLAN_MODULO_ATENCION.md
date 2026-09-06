# PLAN DE IMPLEMENTACION - ATENCION POR UBICACION (Turnos reorganizados + Colero + Guardia + Historia Clinica + BI por gestion)

**Estado:** F1 y F2 COMPLETAS y verificadas (2026-09-01): modelo ubicacion +
regla obligatoria + modulo Turnos ubicacion-primero (landing/mesa/contexto) +
modo "Por ubicacion" en la grilla del modulo Agenda (F2b). Nada
commiteado/pusheado aun. Siguiente: F3 (llamado + colero).
**Ultima revision:** 2026-09-01

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

### F3 — Ciclo de llamado + Pantalla colero

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

### F4 — Guardia + derivacion desde Emergencias

- Mig 106 local + prod. Espacio "Guardia" (subarea de Salud) seed + clave de config.
- Emergencias: accion "Derivar a Guardia" en el detalle del evento (respeta
  FSM del modulo — invocar skill modulo-emergencias antes de tocar) -> crea
  `emergencia_atencion` + entrada en `emergencia_log`.
- Pantalla de la Guardia (dentro de Turnos, la mesa de esa ubicacion): lista
  las atenciones derivadas pendientes + completar intervencion/recomendaciones.
- SIN turnos de por medio (decision cerrada 0.2).

### F5 — Historia clinica (minima viable)

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
- Sonido/chime en la pantalla colero al llamar: evaluar en F3 (autoplay de
  audio en TVs suele requerir interaccion previa).
- Formato del numero diario (prefijo por ubicacion configurable?): definir en F3.
- Reactivacion del area Cultura + subareas + ubicaciones reales: dato de
  negocio que carga Cesar cuando arranque F2/F6.
- Ficha clinica ampliada (motivo, diagnostico, antecedentes): etapa 2 de F5.
