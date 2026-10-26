---
name: modulo-admin-tablas
description: "Usar al trabajar en el módulo Admin Tablas / CRUD genérico de maestros de ZARIS (archivos: frontend/admin_tablas.html, backend/app/api/routes/admin_tablas.py — TABLE_CONFIG; tablas: agentes, equipos, equipo_agentes, servicios, tipo_usuario, cargos, area, subarea, tipo_reclamo, estado_reclamo, estado_ot, configuracion_general, lugares_atencion, agenda_clase, agenda_feriado, etc.). Cubre el procedimiento para agregar una tabla nueva (TABLE_CONFIG + sidebar + SCHEMAS + shell), las tablas configuradas, el READ-ONLY de usuarios y los forms INLINE de agentes/equipos (tipo_grupo, horario, integrantes). Invocar ANTES de agregar/modificar una tabla maestra, su config backend o sus forms inline. El estándar visual del panel de búsqueda es transversal y vive en CLAUDE.md §15."
---

# Admin Tablas — CRUD Genérico de Maestros — §15

`frontend/admin_tablas.html` es el módulo genérico para todas las tablas de configuración. Se activa via `?tabla=<nombre>` en la URL.

> **Nota:** el "Estándar visual obligatorio — panel de búsqueda" (parte de §15) es transversal (aplica a TODO frontend de tabla maestra) y permanece en CLAUDE.md §15. Acá vive solo lo específico del módulo admin_tablas.

### Municipio (IT-01, F2)

- Las tablas de catálogo y operativas se listan, leen, crean, editan y dan de baja dentro del municipio del usuario (`municipio_actual`): un id de otro municipio = 404 como inexistente; el alta inserta el municipio de la request (`id_municipio` no es columna editable de ninguna tabla); los ids del body (`_REFERENCIAS`: área, subárea, cargo, usuario, equipo, agente, prioridad, organismo, tipo de emergencia) se validan dentro del municipio (422 «<entidad> inexistente»). Los drill-downs área → subáreas y subárea → tipos dan 404 si el padre no es del municipio.
- **Tablas globales** (`_TABLAS_GLOBALES`: tipo_usuario, estados de reclamo/OT/emergencia, actividades, tipo_representacion, nacionalidades, municipios): las lee cualquiera (alimentan selects) y las modifica solo el administrador del municipio base hasta F3; `municipios`, además, solo la lee él (403 al resto).
- `configuracion_general` muestra y edita solo las filas del municipio: las claves globales (VAPID) no salen por acá.
- Tabla nueva en `TABLE_CONFIG`: clasificarla en `municipio_tabla_clase` y, si es global, sumarla a `_TABLAS_GLOBALES`; sus columnas que apuntan a otra tabla del municipio, a `_REFERENCIAS`. Reglas R1-R11 en [`PLAN_MULTI_MUNICIPIO_F1_F2.md`](../../../PLAN_MULTI_MUNICIPIO_F1_F2.md).

### Supervisor en Maestros → Agentes + datos de la ficha (2026-10-20, mig 113)

- **Escritura por nivel** (`admin_tablas.py::_autorizar_escritura`, en POST/PUT/DELETE — ya no `require_admin` por dependencia): admin todo; **supervisor (nivel 2)** solo `PUT agentes` de SU gestión con cargo y legajo (el resto del body se descarta; 422 si no queda nada) y alta/baja en `equipo_agentes` con equipo **y** agente de su gestión; cualquier otra tabla o acción → 403. El horario va por `/agenda/disponibilidad` (ya acotado al supervisor).
- **Lectura de agentes**: `TABLE_CONFIG["agentes"]["select"]` suma `id_ciudadano_ficha` (vía `usuarios.id_ciudadano`); un supervisor recibe la PII (DNI/CUIL/email/teléfono) solo de los agentes de su gestión.
- **Datos personales con ficha vinculada**: el PUT los ignora (`_quitar_personales_si_ficha`) y el form los muestra deshabilitados con «Se edita en la ficha del ciudadano»: la ficha es la única fuente y `PUT /buc/ciudadanos/{id}` los copia al agente (`services/cuenta_zaris.py::sincronizar_agente_desde_ficha`).
- **Frontend** (`MODO_SUPERVISOR` por `nivel_acceso` de la sesión): selector con solo «Agentes», sin «+ Nuevo» ni «Baja», campos bloqueados salvo legajo/cargo. Sección **«Equipos»** en el form del agente (sincroniza `equipo_agentes` al guardar, como los integrantes del equipo). `?tabla=agentes&editar=ID` abre el agente (link del aviso `agente_nuevo`). Shell: el ítem Maestros lleva `data-modulo-fallback="agentes_gestion"`.

### Agregar una tabla nueva a admin_tablas

1. **Backend** — agregar entrada en `TABLE_CONFIG` en `backend/app/api/routes/admin_tablas.py`:
```python
"nombre_tabla": {
    "pk": "id_campo",           # columna PK
    "cols": ["col1", "col2"],   # columnas editables (nunca pk, activo, audit)
    "fecha_mod": "fecha_modificacion",  # columna de timestamp de edición, o None
    "has_audit": True,          # False si la tabla no tiene id_usuario_alta/modificacion
    "has_activo": True,         # False si la tabla no tiene columna activo
    "col_types": {              # solo si hay columnas TIME o DATE
        "hora_inicio": "time",
        "fecha": "date",
    },
}
```
   - El backend agrega `activo=True` automáticamente en INSERT cuando `has_activo=True`.
   - Columnas `TIME`/`DATE` deben declararse en `col_types` — asyncpg requiere objetos Python (`datetime.time`/`datetime.date`), no strings.

2. **Frontend** — agregar `<div class="sidebar-item">` en `admin_tablas.html` y entrada en `SCHEMAS` (JS).

3. **Shell** — agregar `<a class="nav__link" href="frontend/admin_tablas.html?tabla=nombre_tabla">` en la sección Maestros de `index.html`.

### Encabezados, tipo `duracion` y campos de reclamos (2026-10-23)

- **Encabezado de columna = etiqueta del formulario** (`encabezadoColumna`): `col.th` si existe (versión corta para la columna: «Estado final», «Orden», «Días», «SLA», «Asigna a mano»…), si no `col.label`; la PK dice «ID». `formatHeader` (nombre de columna sin tildes) queda solo de respaldo para columnas sin campo. Campo nuevo con etiqueta larga ⇒ sumarle `th`.
- **Tipo de campo `duracion`**: número + unidad (días / horas / minutos), se guarda en MINUTOS (`readForm` multiplica; al cargar elige la unidad más grande que divide exacto, `_duracionPartes`; listado con `_fmtDuracion`: «3 días», «4 h», «30 min»). Hoy lo usa `tipo_reclamo.sla_minutos` (mig 120); valida ≥ 1 minuto.
- **Tipos de Reclamo**: SLA editable (`sla_minutos`, obligatorio, columna «SLA»); `sla_dias` NO está en `TABLE_CONFIG.cols` (lo deriva un trigger) y «Duración estimada» salió del form y de `cols` (sin uso).
- **Subáreas**: el tilde es `asignacion_manual` («Asigna a mano», excepción a la asignación automática general de Configuración → Sistema, mig 121); `asignacion_automatica` salió de `cols` (un PUT con solo ese campo da 422).
- Los `checkbox` muestran su `hint`; `.field input/textarea` con `box-sizing: border-box` (desbordaban el modal 3 px y aparecía scroll horizontal). El spinner de carga del listado se quita al pintar la tabla.

### Listado: orden por columnas (§23, F3 2026-10-22)

`GET /{tabla}` trae la tabla entera, así que el listado ordena **en pantalla** (`ordenarFilasListado` + `thOrden` en `admin_tablas.html`, estado en `_ordenListado`). Se ordena por **lo que muestra la celda**: para una FK (`FK_DISPLAY_MAP`) o un enum (`ENUM_LABELS`) por la etiqueta, no por el id guardado (`_valorOrden`; el primer intento ordenaba por id y la subárea quedaba desordenada). El desplegable «Ordenar» se eliminó: lo reemplazan los encabezados + la columna **«Alta»** (`fecha_alta`/`fecha_creacion`/`creado_en`, solo si la tabla la tiene); sin columna elegida, el más reciente primero (`reverse` del orden por PK). Las filas de hijos en línea (área → subáreas) acompañan a su padre y su `colspan` cuenta todas las columnas (`totalCols`). Columna nueva en el listado ⇒ sumarla a `totalCols`.

### Tablas actualmente configuradas
> Fuente de verdad: `TABLE_CONFIG` en `admin_tablas.py` (grepear las claves antes de confiar en esta lista). Verificado 2026-07-17:
`area`, `subarea`, `tipo_usuario`, `cargos`, `usuarios` (READ-ONLY), `agentes`, `equipos`, `equipo_agentes`, `servicios`, `lugares_atencion`, `agenda_clase`, `agenda_feriado`, `estado_reclamo`, `estado_ot`, `tipo_reclamo`, `configuracion_general`, `municipios`, `actividades`, `tipo_representacion`, `nacionalidades`, y los 6 catálogos de Emergencias (`emergencia_prioridad`, `emergencia_estado`, `emergencia_canal_ingreso`, `emergencia_organismo_derivacion`, `emergencia_tipo`, `emergencia_subtipo`). **`equipo_usuarios` NO existe** (fue reemplazada por `equipo_agentes`).

> `reclamos_area` y `reclamos_subarea` fueron eliminadas de admin_tablas en migración 20. El módulo Reclamos usa las tablas generales `area` y `subarea`.

> **`usuarios` es READ-ONLY en admin_tablas (sesión 2026-05-26).** GET sigue habilitado (selects FK de otras tablas: `agentes.id_usuario`), pero POST/PUT/DELETE devuelven **403** (`READ_ONLY_TABLES` en `admin_tablas.py`). Usuarios se administra SOLO desde el **módulo React Usuarios** (`web-app/src/modules/usuarios/`, ítem propio del sidebar `#/usuarios` — el vanilla `frontend/usuarios.html` fue borrado el 2026-07-16), que hashea password + audita login. El ítem "Usuarios" se quitó del sidebar de Maestros y el `SCHEMAS.usuarios` del front.

> **Forms `agentes` y `equipos` son INLINE, no modal.** `INLINE_FORM_TABLES = {agentes, equipos}` en `admin_tablas.html`: el form se renderiza en el flujo de la página (`#inlineForm`, fuera de `#main` para sobrevivir el re-render de `cargarTabla`), no en el modal genérico. El resto de tablas siguen con el modal genérico.
> - **`agentes`** (sesión 2026-05-26): sección "Horario de atención" (título real del `#horarioSec` en la UI — verificado 2026-06-12; franjas Lun-Dom bitmask + hora inicio/fin) que escribe en `disponibilidad_recurso` (tipo_recurso=agente) vía `/api/v1/agenda/disponibilidad` — alimenta la disponibilidad efectiva del agente en Agenda (§27).
> - **`equipos`** (sesión 2026-05-27): sección "Integrantes del grupo" — buscador de agentes con autocompletar (filtro en cliente sobre `GET /admin/agentes`, debounce; un `<select>` de 85 agentes es inusable §23) + lista editable con "Quitar". Sincroniza con `equipo_agentes` tras guardar el equipo (re-lee relaciones reales, soft-delete las quitadas, INSERT las nuevas), espejo de cómo agentes sincroniza sus franjas. Sin backend nuevo — usa el CRUD genérico de admin_tablas (`equipos` + `equipo_agentes`). Seed de mesas demo: `backend/seed_equipos_demo.py` (idempotente, resuelve subárea+agentes por nombre; 5 mesas en prod al 2026-05-27).
>   - **`equipos.tipo_grupo`** (mig 67): distingue **`mesa_tramites`** (recibe pases de Trámites §35: los integrantes ven en "Mi bandeja" lo pasado a esa mesa y cualquiera lo toma; **subárea opcional, SIN horario**) de **`trabajo_reclamos`** (cuadrilla que atiende reclamos/OT y se agenda; **subárea OBLIGATORIA** vía CHECK `ck_equipo_subarea_reclamos`, + sección de franjas igual que agentes que escribe en `disponibilidad_recurso(tipo_recurso='equipo')`; los 3 campos legacy `dias_semana/hora_inicio/hora_fin` de la tabla NO los lee la Agenda, por eso se sacaron del form. **OJO — desde mig 91 la Agenda NO lee la disponibilidad propia del equipo por defecto: usa la unión de sus agentes (§27); las franjas propias del equipo solo se usan con el override `equipos_sin_agentes_usan_horario_propio`.**). El form muestra/oculta la sección horario y marca la subárea requerida según el tipo (`_recursoHorario`/`_bindTipoGrupo`). Las franjas reusan `renderHorarioSeccion`/`_cargarFranjas`/`_sincronizarFranjas` parametrizados por `tipo_recurso`. Listado/preview: cuadrillas muestran "Grupo de trabajo · <subárea>", mesas "Mesa de entrada de trámites" (sin subárea) + badge "N integrantes".

### Super administrador (IT-01 F3, PLAN_MULTI_MUNICIPIO_F3.md)

- **Tablas globales** (`_TABLAS_GLOBALES`): las mutaciones son solo del super administrador (`_exigir_super_admin`, 403 «Acción exclusiva del super administrador») y cada una queda en el registro (`catalogo_global`). Hasta F2 las editaba el administrador del municipio base.
- **`municipios`** (`_SOLO_SUPER_LECTURA`): la lee solo el super administrador y sus mutaciones dan 403 «Los municipios se editan desde el módulo Municipios», para que haya una sola vía de edición.
- **`admin_tablas.html` manda `X-Municipio`** (el municipio del selector) en `_authHeaders` cuando la sesión es de super administrador.
