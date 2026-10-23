# Arranque con tablas vacías: qué cargar primero y qué se rompe

Análisis de solo lectura del repo ZARIS (`backend/app`, `web-app/src`, `frontend/`) y de la base **local** `zaris_dev` (2026-10-23). No se modificó ningún archivo ni ninguna base. No se consultó prod.

**Cómo leer las marcas**
- **[base local]**: lo verifiqué con una consulta SELECT a `zaris_dev` (111 tablas, 349 claves foráneas, 85 CHECK, 19 triggers).
- **[código]**: lo verifiqué leyendo el código en la línea citada. No ejecuté la API: el efecto en tiempo de ejecución sale de la lectura.
- **[a probar]**: es una sospecha que además depende de un dato faltante concreto que no reproduje.
- Prod no se verificó, salvo la nacionalidad id 1 (Argentina en prod, verificado el 2026-10-23).

---

## 0. Resumen ejecutivo

1. **Todo el código supone que el municipio es el `id_municipio = 1`.** Los schemas traen `id_municipio = 1` por defecto, la base tiene `DEFAULT 1` en muchas tablas y varios listados filtran con `= 1` estricto. Además, `get_current_user` no devuelve `id_municipio`, así que cada `current_user.get("id_municipio") or 1` termina siempre en 1. Si la base se vacía con `DELETE` (no `TRUNCATE … RESTART IDENTITY`), el municipio nuevo nace con otro id: fallan las FK NOT NULL hacia `municipios` y los listados estrictos quedan vacíos sin ningún error. **Regla: `municipios` no se vacía. Si se recrea, tiene que ser con `id_municipio = 1`.**
2. **El primer administrador no se puede crear desde ninguna pantalla.** El alta de usuarios exige ser admin, y ningún script crea un usuario de nivel 1. Va por SQL directo, y conviene crearlo **con su agente 1:1 y una subárea**. Sin subárea, crear un trámite da 500.
3. **La tabla `modulos` no tiene endpoint de alta.** Si está vacía, el login funciona pero el sidebar solo muestra Inicio y Guías.
4. **`configuracion_general` vacía rompe cosas en silencio:**
   - Config → Identidad "guarda" sin guardar.
   - Config → Sistema esconde las claves que no existen.
   - El buscador de direcciones queda atado a Vicente López.
   - No salen encuestas.
   - No hay asignación automática.
5. **Los catálogos de estados se buscan por nombre o código literal en el código** (estado_ot, estado_evento, estado_reserva, emergencia_estado, canal `APP_VECINO`). Son catálogos globales y no se tienen que vaciar.

---

## (c) Orden global recomendado de carga

Va de los catálogos sin dependencias hacia lo operativo. Entre paréntesis: dónde se carga hoy.

| # | Qué | Por qué va acá | Dónde se carga hoy |
|---|---|---|---|
| 0 | Esquema y migraciones completas (incluidas las semillas de catálogo: 21, 30, 31, 38, 44, 52, 57, 61, 65, 72, 84, 98b, 101b, 113…) | Varias tablas de catálogo solo se pueblan desde migraciones | Migraciones / `/run-migration` |
| 1 | **`municipios`: una fila `id_municipio = 1`**, activa, con `codigo_corto` | FK NOT NULL desde `modulos`, `usuario_modulos`, `estado_evento`, `estado_reserva`, `eventos`, `evento_reservas`, `evento_encargados`, `ocupaciones`, `agenda_audit_log`, `conflictos_log`, `tipo_tramite*` y `tramite*`. Además, defaults y filtros con 1 en todo el código | SQL. Maestros `?tabla=municipios` exige estar logueado (huevo y gallina) |
| 2 | Catálogos globales sin dependencias: `modulos`, `estado_reclamo`, `estado_ot`, `estado_evento`, `estado_reserva`, `emergencia_estado`, `emergencia_prioridad`, `emergencia_canal_ingreso`, `emergencia_organismo_derivacion`, `nacionalidades`, `actividades`, `tipo_representacion`, `provincias`→`partidos`→`localidades`, `tipos_activo`, `cargos`, `agenda_feriado` | Ver (d). Los estados se buscan por nombre o código | Migraciones, `seed_geo_argentina.py`, `seed_catalogos_buc.py`, `seed_catalogos_emergencias.py` (estados, prioridades y canales), Maestros |
| 3 | `configuracion_general`: claves técnicas (anexo A) | Varias tienen fallback silencioso equivocado | SQL o Maestros `?tabla=configuracion_general`. **No desde Config → Sistema** (no crea claves) |
| 4 | Estructura: `area` → `subarea` (gestiones). Incluye, si se van a usar: «Secretaría de Seguridad» → «Policía Municipal» / «Defensa Civil» (Emergencias) y «Secretaría de Salud» → gestiones de Salud (historia clínica / Guardia) | El usuario interno exige subárea. Tipos de reclamo, tipos de emergencia, prestaciones y trámites cuelgan de la gestión | Maestros `?tabla=area`, `?tabla=subarea` |
| 5 | **Primer admin**: `usuarios` (nivel 1) + `agentes` 1:1 con `id_subarea` | Sin admin nadie entra. Sin agente con subárea no opera Trámites | **SQL directo** (no hay pantalla ni script) |
| 6 | Resto de cuentas: usuarios y agentes (nivel 2 supervisor, 3 atención, 4 gestión), `cargos`, `es_auditor`, `equipos` (`tipo_grupo`), `equipo_agentes`; opcional `usuario_modulos` | Scope por subárea, destinatarios de OT, autoasignación, auditoría | Módulo Usuarios (React `#/usuarios`) o el tilde «funcionario» en la ficha del ciudadano. Maestros → Agentes/Equipos/Equipo-Agentes |
| 7 | Catálogos de negocio por gestión: `tipo_reclamo` (con subárea, `sla_minutos`, `asignacion_a`), `emergencia_tipo` / `emergencia_subtipo`, opcional `activos` | Sin tipo no hay reclamo ni emergencia | Maestros (`tipo_reclamo`, `emergencia_tipo`, `emergencia_subtipo`) o `seed_subareas_tipos_csv.py` / `seed_catalogos_emergencias.py` |
| 8 | Agenda base: `espacios_agenda` (ubicaciones, Guardia), `espacio_agentes`, `disponibilidad_recurso`, `agente_novedad` (opcional). Después, las claves `id_espacio_guardia` e `id_area_salud` | Sin ubicación no hay prestación. Sin disponibilidad no hay turno (409) | Agenda → Espacios / Disponibilidad. Las claves por Config → Sistema **solo si la fila ya existe** |
| 9 | `tipo_prestacion` | Recurso fijo + ubicación obligatoria | Turnos → Prestaciones (nivel ≤ 2) |
| 10 | Trámites: `tipo_tramite` → versión → estados, transiciones, campos, documentos y aprobaciones → **publicar** | Sin versión publicada: 400 | Trámites → Configuración de tipos (nivel ≤ 2). `seed_tramites.py` además crea unos 20 trámites demo: no usarlo tal cual en un municipio limpio |
| 11 | Encuestas: plantillas, preguntas y opciones por tipo (reclamos, turnos, entradas, trámites) + `encuestas_activas = true` | No hay pantalla de alta de plantillas | `seed_encuestas.py` + migraciones 72 / 98b / 101b |
| 12 | Contactos: `ciudadanos` (BUC) y `empresas` | Necesitan `nacionalidades`, `actividades` y `tipo_representacion` | Contactos (React) o alta pública del vecino |
| 13 | Operativo: reclamos→OT, turnos, eventos y reservas, trámites, emergencias, encuestas | — | Cada módulo |

> Los pasos 2 a 12 no tienen por qué esperar el orden exacto entre catálogos independientes (por ejemplo, nacionalidades y estados). Lo que sí es estricto: **1 antes que todo**, **4 antes que 5–9**, **5 antes de usar la UI**, **8 antes que 9**.

---

## (d) Catálogos globales que NO deberían vaciarse nunca

| Tabla | Filas hoy [base local] | Por qué es global / cómo la usa el código |
|---|---|---|
| `municipios` | 2 (id 1 activo, codigo_corto `LPL`; id 2 inactivo) | Ancla de FK NOT NULL y del supuesto «municipio 1» (ver §R1) |
| `modulos` | 15 | `modulos_permitidos` arma el menú (`core/auth.py:164-190`). Sin endpoint de alta: `admin_permisos.py` solo tiene GET `:45` y PUT `:62`. Los códigos coinciden con los `data-modulo` de `index.html:199-364` |
| `estado_ot` | 5 | Por **nombre**: `'En gestión'`, `'En espera'`, `'Pendiente'`, `'Terminada'`, `'Cancelada'`, más la columna `es_final` (`ordenes_trabajo.py:30-36, 284-291`; `reclamos.py:333-341, 1133-1137, 1335, 1582-1591`; `autoasignacion.py:48, 173-174`) |
| `estado_reclamo` | 7 | `'Sin asignar'` por nombre (`reclamos.py:738-742`; `publico_reclamos.py:313`). El estado real es texto con CHECK `ck_reclamo_estado` |
| `estado_evento` / `estado_reserva` | 3 / 3 | Por **código** (`activo`, `cancelado` / `reservada`, `asistio`, `cancelada`). Sin seed: 500 explícito (`agenda_v2.py:427-429, 650-652, 934-936, 1012-1014`; `agenda_publico.py:165-167, 301-303`; `publico_entradas_vecino.py:169-171, 243-245`). Tienen `id_municipio` NOT NULL FK |
| `emergencia_estado` | 7 | Códigos de la máquina de estados (`emergencias.py:292-300`, `:843`; `publico_emergencias.py:170-175`) |
| `emergencia_prioridad` | 3 | FK NOT NULL de `emergencia_evento` y `emergencia_tipo` |
| `emergencia_canal_ingreso` | 2 | `APP_VECINO` por código (`publico_emergencias.py:38, 163-168`); `LLAMADA_TEL` para el COM |
| `emergencia_organismo_derivacion` | 12 | Derivaciones (FK opcional) |
| `nacionalidades` | 67 | FK NOT NULL de `ciudadanos`. Hay ids fijos en el código (§R9) |
| `actividades` (CLAE) | 26 | FK NOT NULL de `empresas` |
| `tipo_representacion` | 7 | FK NOT NULL de `ciudadano_empresa`. **El id 1 se usa como default** (§R10) |
| `provincias` / `partidos` / `localidades` | 24 / 102 / 352 | Geografía AR (`seed_geo_argentina.py`). Derivación de localidad de reclamos y BI Ejecutivo |
| `tipos_activo` | 5 | FK NOT NULL de `activos` |
| `configuracion_general` (claves técnicas) | 32 | No es catálogo, pero se pierde configuración que cuesta reconstruir (anexo A). Incluye material criptográfico VAPID |
| `encuesta_plantilla` / `encuesta_pregunta` / `encuesta_opcion` | 4 / 17 / 19 | Solo se crean por seed y migración (no hay pantalla) |
| `agenda_feriado` | 12 | Semiglobal (feriados nacionales). Vacía no rompe: solo deja de restar días |

**Legacy, sin uso en los routers** (grep en `backend/app/api`): `tipo_usuario`, `agenda_clase`, `lugares_atencion`, `servicios`, `equipo_usuarios`, `reclamos_area`, `reclamos_subarea` y `reclamos_tipo`. Aparecen en Maestros pero ningún circuito las necesita. `usuarios.id_tipo_usuario` es FK opcional.

---

## Circuitos

### 1. Login y cuentas internas

**(a) Qué cargar, en orden**

| # | Tabla / dato | Por qué | Desde dónde |
|---|---|---|---|
| 1 | `municipios` id 1 | `modulos.id_municipio` y `usuario_modulos.id_municipio` son NOT NULL FK → municipios con `DEFAULT 1` [base local]. `UsuarioCreate.id_municipio = Field(1)` (`schemas/buc.py:75`) | SQL |
| 2 | `modulos` (15 códigos) | Sin filas, `modulos_permitidos` devuelve `[]` (`core/auth.py:169-176`) y `menu.js:350-356` oculta todo ítem con `data-modulo`: solo quedan Inicio y Guías. No hay alta por API (`admin_permisos.py:45, 62`) | Migraciones 38/44/61/65/84/113 |
| 3 | `area` → `subarea` | El usuario interno exige subárea: `_subarea_obligatoria_salvo_externo` (`schemas/buc.py:86-92`) | Maestros `?tabla=area` / `?tabla=subarea` |
| 4 | **Primer admin** (`usuarios` nivel 1) + su `agentes` 1:1 con `id_subarea` | El alta exige ser admin: `POST /buc/usuarios` → `require_admin` (`buc.py:214-219`). Ningún script crea un nivel 1: los únicos `INSERT INTO usuarios` están en smokes, `demo_datos.py:374` y `seed_prod_agentes_usuarios.py`, que reparte niveles 2/3/4. `seed_inicial.py` *supone* que ya existe `id_usuario = 1` (`seed_inicial.py:12, 52`). Columnas NOT NULL sin default [base local]: `nombre`, `nivel_acceso`, `username`, `password_hash` (bcrypt), `id_municipio`, `activo`, `buc_acceso`. Para loguear: `email` (login por email exacto, `auth.py:153-155`) o DNI vía agente/ciudadano (`auth.py:157-179`) | **SQL directo** |
| 5 | `cargos` (opcional) | `agentes.id_cargo` es opcional; solo se muestra en topbar y perfil | Maestros `?tabla=cargos` |
| 6 | Resto de usuarios | Alta con clave temporal por mail (`services/cuenta_zaris.py:181-293`). El agente 1:1 se crea solo (`cuenta_zaris.py:240-267`) | Módulo Usuarios (React), o ficha del ciudadano con «funcionario» (`buc.py:537-608`, exige admin y ciudadano previo) |
| 7 | `usuario_modulos` (opcional) | Excepciones al nivel | Usuarios → Permisos |
| 8 | Claves `municipio_nombre` / `municipio_logo_url` y `password_renovacion_dias` | Mails (fallback «Tu municipio», `auth.py:362-369`) y vencimiento de clave (sin clave = desactivado, `auth.py:231-239`) | SQL / Maestros (ver anexo A) |

**(b) Riesgos con tablas vacías**
- [código] Con `modulos` vacía el login responde 200 pero el shell queda sin módulos (`core/auth.py:169-190`; `frontend/js/menu.js:341-356`). Ningún backend usa `require_modulo` (grep): la protección real está en los guards por nivel de cada router.
- [código] Los usuarios **externos** (`es_externo`, nivel > 1, sin agente) se suspenden a las 24 h si no hay una ficha BUC con su mismo email o vinculada (`services/integridad_cuentas.py:48-62`, gracia de 24 h). El admin está exento.
- [código] Un admin creado sin agente entra, pero recibe 403 en Trámites (`tramites.py:1139-1141`) y no puede «tomar» reclamos (`reclamos.py:311`). Con agente pero sin subárea, crear un trámite da **500** (§R5).
- No verificado: el mail con la clave temporal depende de Resend y variables de entorno (fuera de la base).

### 2. Contactos: ciudadanos (BUC) y empresas

**(a)**

| # | Tabla | Por qué | Desde dónde |
|---|---|---|---|
| 1 | `nacionalidades` | `ciudadanos.id_nacionalidad` es NOT NULL FK [base local] y obligatorio en el schema (`schemas/buc.py:213`) | Maestros `?tabla=nacionalidades` / `seed_catalogos_buc.py` |
| 2 | `actividades` | `empresas.id_actividad` es NOT NULL FK [base local] | Maestros `?tabla=actividades` |
| 3 | `tipo_representacion` (con **id 1**) | `ciudadano_empresa.id_tipo_representacion` es NOT NULL FK. Default 1 en `schemas/buc.py:412`, `web-app/src/modules/empresas/views/FormView.tsx:167` (`|| 1`) y `publico_alta.py:535` (`or 1`) | Maestros `?tabla=tipo_representacion` |
| 4 | Ciudadano representante | Toda empresa nace con un vecino activo (`buc.py:1053-1063`) | Contactos (React) |
| 5 | (opcional) `municipio_nombre` / `municipio_logo_url` | El alta del ciudadano crea la cuenta de App Vecinos y manda el mail de activación (`buc.py:590-600`; branding en `services/cuenta_vecino.py:47-60`) | — |

**(b)**
- [código][a probar] `crear_empresa` commitea empresa + vínculo sin `try` (`buc.py:1076-1087`). Si el `id_tipo_representacion` enviado (o el 1 por defecto) no existe, la FK falla y da 500, no 422.
- [código] El email del ciudadano es obligatorio y tiene que ser único entre cuentas de vecino activas (`buc.py:560-576`). Con la tabla vacía no hay problema, pero es lo primero que choca al cargar un padrón con emails repetidos.

### 3. Reclamos + Órdenes de trabajo (incluida la asignación automática) + auditoría

**(a)**

| # | Tabla / dato | Por qué | Desde dónde |
|---|---|---|---|
| 1 | `estado_ot` (5 nombres exactos + `es_final`) | Ver (d). Crear una OT sin el estado da 500 explícito (`ordenes_trabajo.py:284-291`) | Migración 21 / Maestros `?tabla=estado_ot` |
| 2 | `estado_reclamo` | `id_estado_fk` se resuelve por nombre (nullable, `reclamos.py:738-742`) | Migración / Maestros |
| 3 | `area` → `subarea` (gestiones; `asignacion_manual`) | Gestión del tipo | Maestros |
| 4 | `tipo_reclamo` **con `id_subarea`** | `id_tipo_reclamo` es obligatorio (`reclamos.py:679-681`). Sin subárea no se autoasigna (`autoasignacion.py:133-142`, JOIN subarea), no se cierra directo (`reclamos.py:126-130`) y queda fuera del alcance del supervisor | Maestros `?tabla=tipo_reclamo` |
| 5 | Ciudadano | `id_ciudadano` es obligatorio (`reclamos.py:679`) | Contactos |
| 6 | Usuario nivel 1-3 para crear | `NIVELES_GESTION` (`reclamos.py:59, 675`) | Usuarios |
| 7 | Supervisor nivel 2 **con agente y subárea** | Sin eso, 403 en la mesa del supervisor (`ordenes_trabajo.py:59-76`) y en el listado de reclamos (`reclamos.py:195-210`) | Usuarios / Maestros → Agentes |
| 8 | Destinatario de la OT: agente con usuario activo de nivel ≤ 4, o equipo con al menos un integrante así | `_validar_destinatario_ot` (`ordenes_trabajo.py:135-180`) | Usuarios + Maestros → Equipos / Equipo-Agentes |
| 9 | **Asignación automática**: clave `reclamos_asignacion_automatica = 'true'`. Candidatos de la gestión: agentes con usuario **nivel 4**, no auditores, o cuadrillas `tipo_grupo = 'trabajo_reclamos'` con `id_subarea` e integrantes, según `tipo_reclamo.asignacion_a` | `autoasignacion.py:54-60` (fail-closed), `:69-98`. CHECK `ck_equipo_subarea_reclamos` [base local] | SQL o Maestros (clave); Usuarios; Maestros → Equipos |
| 10 | Auditoría: supervisor (≤ 2) de la gestión; auditor = agente con `es_auditor = TRUE` y usuario nivel ≤ 2 (o admin) | `reclamos.py:1084-1131`; mesa gateada a ≤ 2 en el bundle (`web-app/src/modules/ot/index.tsx:21-28, 69`) y `es_auditor` en `ordenes_trabajo.py:624-629`. Sin la clave `auditor_misma_subarea_permitido` vale false (`ordenes_trabajo.py:264-267, 533-537`) | Maestros → Agentes |
| 11 | Opcional: `localidades` (derivación best-effort, `reclamos.py:729-734`), `tipos_activo` / `activos`, encuesta tipo `reclamos` | — | — |

**(b)**
- [código][a probar] **Asignación automática que falla callada**: busca `'En gestión'` por nombre (`autoasignacion.py:173-174`). Si falta, inserta la OT con `id_estado` NULL y viola el NOT NULL. El `except` general lo traga (`autoasignacion.py:206-208`): el reclamo queda «Sin asignar», solo con una línea de log y sin aviso a nadie.
- [código][a probar] **Resolver con OT abierta y sin `'Terminada'`**: `_terminar_ots_operativas` escribe `id_estado = (SELECT … 'Terminada')` = NULL (`reclamos.py:333-341`, llamado en `:1051`) → NOT NULL → 500.
- [código] Tipo de reclamo sin subárea: el reclamo se crea, pero nadie con alcance de gestión lo ve, no se autoasigna y no admite cierre directo (422).
- [código] La autoasignación sin candidatos avisa a los supervisores nivel 2 de la gestión y, si no hay, a los admins (`autoasignacion.py:103-123`). Con usuarios vacíos no avisa a nadie.
- Dato: `ot_pendiente_dias_vencimiento` aparece en Config → Sistema (`ParametrosSistemaView.tsx:78`), pero ningún código del backend la lee (grep en `backend/app`).

### 4. Turnos (prestaciones, ubicaciones, disponibilidad, colero, Guardia, historia clínica)

**(a)**

| # | Tabla / dato | Por qué | Desde dónde |
|---|---|---|---|
| 1 | `municipios` id 1 | `ocupaciones.id_municipio` es NOT NULL FK [base local]. `TurnoCreate.id_municipio = 1` (`schemas/turnos.py:113`). Listados estrictos: `turnos.py:171-175` (prestaciones), `:394` (turnos), `turnos_publico.py:129, 141` | SQL |
| 2 | `area` / `subarea` | Gestión de la prestación; alcance de nivel 3-4 (`turnos.py:93-109`) | Maestros |
| 3 | `agentes` (+ usuario) | Recurso o atención | Usuarios / Maestros |
| 4 | `espacios_agenda` (ubicación) | **Toda prestación declara ubicación** (`turnos.py:218-223`). Listado estricto `id_municipio = 1` (`agenda_espacios.py:122, 129`) | Agenda → Espacios (nivel ≤ 2) |
| 5 | `espacio_agentes` | Un espacio atendido sin agentes tiene disponibilidad `[]` (`services/agenda.py:79-86`) | Agenda → Espacios → agentes |
| 6 | `disponibilidad_recurso` | Sin la clave `turnos_respeta_disponibilidad` vale TRUE (`services/agenda.py:695-705`). Fuera de la disponibilidad, el turno da 409 (`turnos.py:1062-1070`). El autoservicio no ofrece prestaciones sin disponibilidad (`turnos_publico.py:127-166`) | Agenda → Disponibilidad |
| 7 | `tipo_prestacion` | Recurso (agente XOR espacio, CHECK `ck_tipo_prestacion_recurso`) + duración + ubicación | Turnos → Prestaciones (nivel ≤ 2, `turnos.py:209-245`) |
| 8 | Ciudadano | `turnos.id_ciudadano` NOT NULL. El autoservicio lo crea por DNI y necesita `nacionalidades` (`services/agenda.py:728-801`) | Contactos / autoservicio |
| 9 | Colero | El turno necesita ubicación para numerarse (`turnos.py:1422-1427`). `prefijo_colero` es opcional; `token_pantalla` tiene default | Agenda → Espacios |
| 10 | Guardia: espacio + clave `id_espacio_guardia` | `services/guardia.py:23-34`. Derivar sin clave da 422 (`emergencias.py:1236-1240`) | Espacio en Agenda. Clave por SQL o Maestros (Config → Sistema solo edita si existe) |
| 11 | Historia clínica: clave `id_area_salud` → área activa | `services/historia_clinica.py:33-45, 64-104`. Sin clave, solo el admin. Las prestaciones de Salud fuerzan `registra_atencion` (`turnos.py:199-206`) | Igual que la anterior |
| 12 | `agenda_feriado` (opcional), encuesta tipo `turnos` | — | — |

**(b)**
- [código][a probar] `crear_turno` atrapa **cualquier** `IntegrityError` y lo informa como 409 «El horario acaba de ser tomado por otra reserva» (`turnos.py:1133-1135`). Sin municipio 1, la FK de `ocupaciones` da ese mensaje engañoso.
- [código][a probar] Autoservicio público con `nacionalidades` vacía: `id_nac = … else 1` (`services/agenda.py:772-775`) → FK → 500. `turnos_publico.py:318-328` solo atrapa `ValueError`.
- [código][a probar] `guardia.py:30` castea `NULLIF(TRIM(cg.valor),'')::int` **sin validar**. Si la clave tiene texto no numérico, `GET /turnos/ubicaciones` (`turnos.py:646`) da 500 y cae toda la landing de Turnos. El lector de historia clínica sí valida con regex (`historia_clinica.py:41`). Con la clave ausente no pasa nada.
- [código] La disponibilidad vacía no es un bug, pero es la causa más probable de «no puedo dar turnos» en un municipio nuevo (409 en todo turno).

### 5. Agenda y Entradas (espacios, eventos con cupo, reservas)

**(a)**

| # | Tabla | Por qué | Desde dónde |
|---|---|---|---|
| 1 | `municipios` id 1 | NOT NULL FK desde `eventos`, `evento_reservas`, `evento_encargados`, `estado_evento`, `estado_reserva`, `ocupaciones`, `agenda_audit_log` y `conflictos_log` [base local] | SQL |
| 2 | `estado_evento`, `estado_reserva` | Ver (d) | Migración 31 |
| 3 | `area` / `subarea` | Nivel 2/4 solo crea eventos de su subárea (`agenda_v2.py:430-440`) | Maestros |
| 4 | `espacios_agenda` | Entradas solo lista eventos con espacio (`web-app/src/modules/entradas/api/entradasApi.ts:9, 25`) | Agenda → Espacios |
| 5 | Agentes, equipos, espacios + `disponibilidad_recurso` | Grilla y conflictos | Agenda |
| 6 | Ciudadanos | Reservas (`evento_reservas.id_ciudadano` NOT NULL). El autoservicio los crea por DNI (`agenda_publico.py:141`) | Contactos / autoservicio |
| 7 | Encuesta tipo `entradas` | Opcional | Migración 98b |

**(b)**
- [código][a probar] `crear_evento` hace INSERT + `registrar_audit` con `id_municipio = 1` sin `try` (`agenda_v2.py:441-467`). Sin municipio 1 → IntegrityError → 500.
- [código] Hay listados estrictos por `id_municipio = :m` con default 1: `agenda_v2.py:1479, 1629, 1670, 1747, 1773, 1861`; `agenda_espacios.py:129`; `agenda_disponibilidad.py:110`. Con datos de otro id_municipio, vacíos sin error.

### 6. Trámites (tipos, versiones publicadas, circuitos, numerador)

**(a)**

| # | Tabla / dato | Por qué | Desde dónde |
|---|---|---|---|
| 1 | `municipios` id 1 con `codigo_corto` | `tipo_tramite*` y `tramite*` tienen `id_municipio` NOT NULL FK [base local]. `crear_tramite` hace JOIN con municipios y filtra por `id_municipio` (`tramites.py:1146-1155`). El código va en el número de expediente; si está vacío se omite (`services/tramites/numerador.py:58-59`) | SQL / Maestros |
| 2 | `area` / `subarea` (+ `equipos` tipo `mesa_tramites`, opcional) | Destinatarios de pases (`tramites.py:471-513`) | Maestros |
| 3 | Agente del operador **con subárea** | Sin agente: 403 (`tramites.py:1139-1141`). El destinatario inicial es la subárea del agente (`services/tramites/creacion.py:310-314`) | Usuarios |
| 4 | `tipo_tramite` (crea la v1 en borrador) | `tramites_admin.py:151-204` (nivel ≤ 2, `:64-72`) | Trámites → Configuración de tipos |
| 5 | Estados (exactamente 1 inicial y al menos 1 final), transiciones sin estados muertos, campos, documentos y aprobaciones | Lo valida `publicar_version` (`services/tramites/versionado.py:338-378`) | Mismo builder |
| 6 | **Publicar** | Sin versión publicada: 400 (`tramites.py:1156-1157`) | `POST /admin/tramites/versiones/{id}/publicar` (`tramites_admin.py:492`) |
| 7 | `tipo_tramite_numerador` | Se crea solo con `INSERT … ON CONFLICT` (`numerador.py:30-43`) | — |
| 8 | Iniciador (ciudadano / empresa / área interna) | CHECK `ck_tramite_iniciador` [base local]; `iniciadores_permitidos` | Contactos |
| 9 | Claves de ciclo de vida y retención | Tienen defaults en código (`services/tramites/ciclo_vida.py:61-66`; `retencion.py`) | Opcional |

**(b)**
- [código] **500 al crear un trámite si el agente no tiene subárea**: `determinar_destinatario_inicial` devuelve `("subarea", None)` (`creacion.py:310-314`). El INSERT (`tramites.py:1184, 1203-1247`) viola `ck_tramite_destinatario` [base local] sin manejo. Es exactamente el caso del primer admin creado por SQL con un agente sin subárea.
- [código] Si el `tipo_tramite` quedó con un `id_municipio` distinto de 1 (o el municipio no existe), devuelve 404 «Tipo de tramite no encontrado» (`tramites.py:1146-1155`).
- [código] `seed_tramites.py` crea además unos 20 trámites demo y 5 subáreas (cabecera del script): no sirve como seed limpio.

### 7. Emergencias (COM)

**(a)**

| # | Tabla / dato | Por qué | Desde dónde |
|---|---|---|---|
| 1 | Área «Secretaría de Seguridad» → subáreas «Policía Municipal» y «Defensa Civil» | `emergencia_evento.id_subarea` y `emergencia_tipo.id_subarea` son NOT NULL FK. `seed_catalogos_emergencias.py` aborta si no existen (guard en `:89-93`); se resuelven por nombre (migración 81) | Maestros (área/subárea) |
| 2 | `emergencia_prioridad`, `emergencia_estado` (códigos de la FSM), `emergencia_canal_ingreso` (`APP_VECINO`, `LLAMADA_TEL`), `emergencia_organismo_derivacion` | Ver (d) | `seed_catalogos_emergencias.py` / Maestros |
| 3 | `emergencia_tipo` (prioridad default NOT NULL) y `emergencia_subtipo` | `emergencias.py:790-812` | Maestros (`admin_tablas.py:182-192`) o seed |
| 4 | Operador nivel ≤ 3 (`emergencias.py:255-257`) con agente en la subárea | Alcance de nivel 3 (`:260-287`) | Usuarios |
| 5 | Denunciante: ciudadano BUC, contacto eventual o anónimo | CHECK `ck_emergencia_evento_denunciante` [base local] | — |
| 6 | Guardia (`id_espacio_guardia`) | Derivar sin ella da 422 (`emergencias.py:1236-1240`) | Ver circuito 4 |
| 7 | `emergencia_numerador` | Lo crea el trigger `fn_generar_numero_emergencia` [base local] | — |

**(b)**
- [código][base local] **Bug ya presente**: al promover un contacto eventual a la BUC se fija `id_nacionalidad = 1` (`emergencias.py:620-628`). En `zaris_dev`, `nacionalidades.id = 1` es «Afganistan» y Argentina es el id 4. Con el catálogo vacío o sin id 1 → FK → 500. **En prod el id 1 es Argentina (verificado el 2026-10-23 con SELECT), así que hoy no falla en prod; sí en local, y depende de que el id coincida.**
- [código] Un operador nivel 3 sin agente o sin subárea **ve todo** (fail-open documentado, `emergencias.py:273-280`).
- [código] La alerta de pánico avisa a los usuarios de nivel ≤ 3 de la subárea y, si no hay, a los admins (`services/notificaciones.py` ~801-848). Con usuarios vacíos no llega a nadie.

### 8. Encuestas (plantillas, disparo)

**(a)**
1. `encuesta_plantilla` + `encuesta_pregunta` + `encuesta_opcion`, una por tipo (`reclamos`, `turnos`, `entradas`, `tramites`). **No hay alta por pantalla**: `encuestas_admin.py` solo tiene GET más `/disparar` (`:598`) y `/atender` (`:648`). Se cargan con `seed_encuestas.py` (reclamos) y las migraciones 72 (turnos), 98b (entradas) y 101b (trámites).
2. Clave `encuestas_activas = 'true'`. Sin ella no se envía nada (`services/encuestas_service.py:78-89`). `encuestas_antifatiga_activo`: si falta, la regla queda **activa** (`:92-110`).
3. Ciudadano con email y un reclamo, turno, reserva o trámite cerrado.
4. Fuera de la base (no verificado): cron con `X-Dispatcher-Token` y Resend.

**(b)**
- [código] Todo falla en silencio: sin plantilla devuelve un motivo `SIN_PLANTILLA` (`encuestas_service.py:196-202, 294-300, 395-401, 488-494`) y sin clave no envía. Ninguna pantalla lo avisa.

### 9. App del vecino: alta pública y portal

**(a)**

| # | Dato | Por qué | Desde dónde |
|---|---|---|---|
| 1 | `municipios`: fila activa **con `codigo_corto`** | Es el slug del alta: sin él, 404 «Municipio no encontrado» (`publico_alta.py:85-107`). La identidad pública devuelve `url_alta_publica = None` (`publico_identidad.py:47-50`) | Maestros `?tabla=municipios` |
| 2 | Claves `municipio_nombre`, `municipio_logo_url`, `municipio_descripcion`, `municipio_color_primary`, `municipio_color_accent` | Branding de PWA, alta y mails (`publico_identidad.py:36-60`; `publico_alta.py:110-119`) | **Crear la fila** por SQL o Maestros. Después se editan en Config → Identidad |
| 3 | `nacionalidades`, `actividades`, `tipo_representacion` (id 1) | Selects y validación del alta (`publico_alta.py:194-218, 274-279, 481-487, 535`) | Maestros |
| 4 | `geo_bbox_*` | Buscador de direcciones del alta y de los reclamos del vecino (§R4) | SQL / Maestros |
| 5 | Para que el portal tenga contenido: `tipo_reclamo`; `emergencia_tipo` + canal `APP_VECINO`; prestaciones con disponibilidad; eventos con `admite_autoservicio` | Circuitos 3, 7, 4 y 5 | — |
| 6 | VAPID (variables de entorno o claves `vapid_*`) | Push opcional: sin claves no se envía (`services/push.py:37-66`) | Entorno / SQL |
| 7 | Fuera de la base (no verificado): `APP_VECINOS_FRONTEND_URL`, `API_PUBLIC_BASE_URL`, Resend | Links y mails de activación | Railway |

**(b)**
- [código] **Config → Identidad guarda sin guardar**: `update_identidad` solo hace `UPDATE … WHERE clave = :k` (`config_identidad.py:172-178`). Si las claves no existen, responde 200 con los defaults («MUNICIPALIDAD», `config_identidad.py:139-149`) y no persiste nada.
- [código][a probar] El alta pública de una empresa usa `id_tipo_representacion or 1` (`publico_alta.py:535`) → FK si el id 1 no existe.

### 10. Inicio (dashboard) y Datos (BI) con todo vacío

- **Inicio** [código]: `GET /dashboard/resumen` es una sola consulta de agregados que siempre devuelve una fila (`dashboard.py:54-74`). Las 6 tarjetas quedan en 0 y las capas vacías. Sin `geo_limite_geojson` no hay máscara del municipio y el mapa arranca en el **centro fijo de Vicente López** (`web-app/src/modules/dashboard/components/DashboardMap.tsx:28, 306`). Pasa lo mismo en Emergencias (`EmergenciasMap.tsx:30`) y en el pin de reclamos (`reclamos/components/MapaPicker.tsx:31`).
- **Datos (BI)** [código]: las divisiones están protegidas (`bi.py:199, 553-554, 1697`; `bi_ejecutivo.py:136-143`). Con todo vacío devuelve ceros o `null`. Filtra `id_municipio = 1 OR NULL` (`bi.py:75-84`). Sin áreas, el selector de área por defecto toma `catalogo[0]?.id_area` (`OperativoPage.tsx:75`); el admin arranca en «Todas». **[a probar]** cómo se ven los gráficos con listas vacías: no lo verifiqué en el navegador. El módulo `bi` es `min_nivel_acceso = 1` [base local].

---

## Riesgos estructurales (detalle)

- **R1 — El supuesto «municipio 1»** [código][base local]
  - Defaults en schemas: `schemas/buc.py:75`, `schemas/turnos.py:82, 113`, `schemas/tramites.py:302, 478`, `schemas/agenda_v2.py:53, 179, 524, 609`; modelos `models/agenda.py:153-324` (`default=1`).
  - `DEFAULT 1` en la base: `espacios_agenda`, `tipo_prestacion`, `turnos`, `eventos`, `modulos`, `usuario_modulos`, `disponibilidad_recurso`, …
  - `get_current_user` no devuelve `id_municipio` (`core/auth.py:85-94`), así que `current_user.get("id_municipio") or 1` (`buc.py:597, 664, 812`; `cuenta_zaris.py:116`) es siempre 1.
  - Filtros estrictos: ver circuitos 4, 5 y 6.
  - Consecuencia: si se vacía `municipios` con `DELETE`, la secuencia sigue (hoy ya hay un id 2) y el municipio nuevo no será el 1.
- **R2 — El primer admin y los módulos** (circuito 1).
- **R3 — Claves de configuración**:
  - Identidad no inserta (`config_identidad.py:172-178`).
  - Config → Sistema **oculta** las claves ausentes: `.filter(… !!f.param)` (`web-app/src/modules/config/views/ParametrosSistemaView.tsx:184-187`). Si una sección no tiene ninguna clave, desaparece entera. Las claves solo se crean por Maestros → Configuración general (`admin_tablas.py:133-138`, POST genérico) o SQL.
  - En prod, `configuracion_general.tipo` es NOT NULL sin default según CLAUDE.md §21; en local tiene default `'string'` [base local]. No verificado en prod.
- **R4 — Geocoding atado a Vicente López** [código]: sin `geo_bbox_centro_lat`, `geo_bbox_centro_lon` y `geo_bbox_delta_grados`, cae a las constantes de Vicente López (`geo.py:47-49, 78-80`, solo un warning en el log) con `bounded=1`. En otro municipio, el buscador no encontraría sus calles.
- **R5 — Trámite sin subárea** (circuito 6).
- **R6 — Turnos: IntegrityError presentado como «horario tomado»** (`turnos.py:1133-1135`).
- **R7 — Estados de OT por nombre** (`autoasignacion.py:173-183, 206-208`; `reclamos.py:333-341, 1051`).
- **R8 — Cast sin validar en la clave Guardia** (`guardia.py:30`).
- **R9 — Nacionalidad fija en 1** (`emergencias.py:626` — bug ya presente en local; en prod el id 1 es Argentina; `services/agenda.py:775`).
- **R10 — Tipo de representación fijo en 1** (`schemas/buc.py:412`; `publico_alta.py:535`; `FormView.tsx:167`; commit sin `try` en `buc.py:1080-1087`).

### Hallazgos laterales (no son de tablas vacías)
- [base local] **Drift local**: `municipios` no tiene la columna `pais` (la migración 94 no está aplicada en `zaris_dev`), pero `admin_tablas.py:141` la incluye y el form de Maestros la ofrece (`frontend/admin_tablas.html:1097`). Crear o editar un municipio en local con «País» cargado debería dar 400 (columna inexistente). **[a probar]**. Prod no verificado.
- [código] `ot_pendiente_dias_vencimiento` se muestra en Config → Sistema y nadie la lee en el backend.

---

## Anexo A — Claves de `configuracion_general` y qué pasa si faltan

| Clave | Si falta | Evidencia |
|---|---|---|
| `municipio_nombre`, `municipio_logo_url`, `municipio_descripcion`, `municipio_color_primary`, `municipio_color_accent` | Defaults («MUNICIPALIDAD», «Tu municipio», vacío). **Identidad no puede crearlas** | `config_identidad.py:139-149, 172-178`; `auth.py:362-369` |
| `geo_bbox_centro_lat` / `_lon` / `geo_bbox_delta_grados` | Fallback silencioso a Vicente López | `geo.py:47-49, 56-82` |
| `geo_limite_geojson` | Sin máscara del municipio; mapa en el centro fijo | `services/geo_limite.py:43-52`; `DashboardMap.tsx:28` |
| `reclamos_asignacion_automatica` | Apagada (fail-closed) | `autoasignacion.py:54-60` |
| `auditor_misma_subarea_permitido` | false | `ordenes_trabajo.py:264-267` |
| `encuestas_activas` | No se envían encuestas | `encuestas_service.py:78-89` |
| `encuestas_antifatiga_activo` | Regla activa | `encuestas_service.py:92-110` |
| `turnos_respeta_disponibilidad` | TRUE (exige disponibilidad) | `services/agenda.py:695-705` |
| `equipos_sin_agentes_usan_horario_propio` | Lectura en `services/agenda.py:196-208` (default no revisado en detalle) | — |
| `id_espacio_guardia` | Derivar a Guardia da 422; Turnos sin Guardia | `guardia.py:23-34`; `emergencias.py:1236-1240` |
| `id_area_salud` | Historia clínica solo para el admin | `historia_clinica.py:33-45, 82-89` |
| `password_renovacion_dias` | 0 = sin vencimiento | `auth.py:231-239` |
| `tramite_sla_dias_default`, `tramite_desistimiento_*` | Defaults 30 / 30 / 60 / 90 / 72 | `services/tramites/ciclo_vida.py:61-66` |
| `retencion_dias_*`, `tramite_inactividad_dias`, `tramite_purga_binarios_real` | Defaults en código; la purga queda en simulacro | `services/tramites/retencion.py:56-90` |
| `vapid_public_key`, `vapid_private_key`, `vapid_claims_email` | Sin push (salvo que estén en el entorno) | `services/push.py:37-66` |
| `ot_pendiente_dias_vencimiento` | Sin efecto (nadie la lee) | grep |

Las claves de Guardia, Salud y asignación general las **sembraron migraciones resolviendo por nombre** (106b, 107b, 121b). Una base vaciada no las vuelve a correr: hay que crearlas a mano después del paso 8.

## Anexo B — Dependencias por FK [base local]

«NN» = FK con columnas NOT NULL (bloquea el INSERT); «opc» = FK opcional. Se omiten las FK de auditoría `id_usuario_alta` / `id_usuario_modificacion` (todas opcionales) y las tablas `_backup_*`.

| Tabla | Depende (NN) | Depende (opc) |
|---|---|---|
| activos | tipos_activo | localidades |
| agenda_audit_log | municipios | — |
| agente_novedad / ausencias_agente | agentes | — |
| agentes | — | cargos, subarea |
| ciudadano_aviso / _canal_preferido / _credencial / _push_subscription | ciudadanos | — |
| ciudadano_empresa | ciudadanos, empresas, tipo_representacion | — |
| ciudadanos | nacionalidades | — |
| conflictos_log | municipios | ocupaciones |
| disponibilidad_recurso | — | subarea (el recurso es polimórfico, sin FK) |
| emergencia_atencion | emergencia_evento, espacios_agenda | agentes, ciudadanos |
| emergencia_evento | emergencia_canal_ingreso, emergencia_estado, emergencia_prioridad, emergencia_tipo, subarea | ciudadanos, emergencia_contacto_eventual, emergencia_organismo_derivacion, emergencia_subtipo |
| emergencia_log | emergencia_evento | — |
| emergencia_tipo | emergencia_prioridad, subarea | emergencia_organismo_derivacion |
| emergencia_subtipo | emergencia_tipo | emergencia_prioridad |
| empresas | actividades | — |
| empresa_credencial | empresas | — |
| encuesta_envio | ciudadanos, encuesta_plantilla | reclamos, turnos, evento_reservas, tramite (exactamente uno, CHECK) |
| encuesta_pregunta → encuesta_opcion | encuesta_plantilla → encuesta_pregunta | — |
| encuesta_respuesta / _detalle | encuesta_envio / encuesta_respuesta, encuesta_pregunta | encuesta_opcion |
| equipos | — | subarea (NOT NULL si `tipo_grupo = 'trabajo_reclamos'`, CHECK) |
| equipo_agentes | agentes, equipos | — |
| espacios_agenda | — | subarea |
| espacio_agentes | agentes, espacios_agenda | subarea |
| estado_evento / estado_reserva / modulos | municipios | — |
| eventos | estado_evento, municipios | espacios_agenda, subarea |
| evento_reservas | ciudadanos, estado_reserva, eventos, municipios | — |
| evento_encargados | eventos, municipios | — |
| historia_clinica_acceso / notificacion / usuario_login_log / usuario_push_subscription | usuarios | — |
| localidades → partidos → provincias | partidos / provincias | — |
| ocupaciones | municipios | ciudadanos, eventos, ordenes_trabajo |
| ordenes_trabajo | estado_ot, reclamos | agentes, equipos |
| ot_adjuntos / reclamo_adjuntos / reclamo_historial | ordenes_trabajo / reclamos | — |
| reclamos | — | activos, area, ciudadanos, empresas, estado_reclamo, localidades, tipo_reclamo (el código exige ciudadano y tipo) |
| subarea | — | area |
| tipo_prestacion | — | agentes, espacios_agenda, subarea (recurso agente XOR espacio, CHECK) |
| tipo_reclamo | — | subarea |
| tipo_tramite | municipios | subarea, tipo_tramite_version |
| tipo_tramite_version | municipios, tipo_tramite | agentes |
| tipo_tramite_estado / _campo | municipios, tipo_tramite_version | — |
| tipo_tramite_transicion | municipios, tipo_tramite_version, tipo_tramite_estado | — |
| tipo_tramite_documento_requerido | municipios, tipo_tramite_version | tipo_tramite_estado |
| tipo_tramite_aprobacion_requerida | tipo_tramite_version, tipo_tramite_estado | agentes, equipos, subarea, documento requerido |
| tipo_tramite_numerador | municipios, tipo_tramite | — |
| tramite | agentes (iniciador), municipios, tipo_tramite_estado, tipo_tramite_version | ciudadanos, empresas, equipos, subarea |
| tramite_movimiento / _relacion / _documento | agentes, municipios, tramite | — |
| tramite_firma | municipios, tramite_documento | agentes, equipos, subarea |
| tramite_aprobacion | tramite, tipo_tramite_aprobacion_requerida, tipo_tramite_estado | agentes, tramite_documento |
| turnos | ciudadanos, tipo_prestacion | agentes, espacios_agenda, ocupaciones, subarea |
| turno_atencion / turno_llamado | turnos (+ ciudadanos) | — |
| usuario_modulos | modulos, municipios, usuarios | — |
| usuarios | — | ciudadanos, subarea, tipo_usuario (`id_municipio` NOT NULL **sin FK**) |

Triggers que generan datos solos [base local]: `trg_nro_reclamo`, `trg_sla_reclamo`, `trg_nro_ot`, `trg_numero_emergencia` (crea `emergencia_numerador`), `trg_tipo_reclamo_sla_sync`. Los logs `emergencia_log` e `historia_clinica_acceso` son de solo agregado (no admiten UPDATE ni DELETE).
