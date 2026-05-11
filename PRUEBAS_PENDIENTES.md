# Pruebas de navegador pendientes

Checklist vivo. Marcar `[x]` cuando se pruebe, fecha + entorno (local/prod) + observación. Si falla, anotar en "Fallos detectados" al final.

URLs:
- **Local API:** http://127.0.0.1:8000 — Swagger: http://127.0.0.1:8000/docs
- **Local web-app (React):** http://localhost:5173
- **Local frontend vanilla:** http://localhost:8080
- **Prod API:** https://zaris-api-production-bf0b.up.railway.app
- **Prod frontend:** https://cesarzeta.github.io/zaris-zge/index.html

Comandos para arrancar:
```powershell
# Backend
cd backend; $env:ENV_FILE=".env.local"; uvicorn app.main:app --host 127.0.0.1 --port 8000

# Frontend vanilla
python -m http.server 8080

# Web-app React
cd web-app; pnpm dev
```

---

## Estado del documento

| Bloque | Origen | Total casos |
|---|---|---|
| [A. Módulo Agenda (web-app React)](#a-módulo-agenda-web-app-react) | Fase 3.A | 47 |
| [B. Login con usuarios nuevos (prod)](#b-login-con-usuarios-nuevos-en-prod) | seed 2026-05-10 | 8 |
| [C. Módulo Reclamos (frontend vanilla)](#c-módulo-reclamos-frontend-vanilla) | Fases 1-3 reclamos | 22 |
| [D. Módulo Órdenes de Trabajo (frontend vanilla)](#d-módulo-órdenes-de-trabajo-frontend-vanilla) | OT V1 | 11 |
| [E. Admin tablas — drill-down inline](#e-admin-tablas--drill-down-inline) | sub-fase admin | 6 |
| [F. Breadcrumb + accesos](#f-breadcrumb-en-frontends-vanilla) | migración DS | 10 |
| [G. Topbar y sesión](#g-topbar--menú-de-usuario) | shell | 4 |
| **Total** | | **108** |

---

## A. Módulo Agenda (web-app React)

**Pre-requisitos:**
- Backend corriendo en :8000 con migraciones 30-34 aplicadas.
- `seed_agenda.py` corrido (4 agentes activos + 1 equipo demo + 1 evento "Vacunacion antigripal").
- Web-app corriendo en :5173.
- Login OK (admin o cualquier usuario del seed).

> Datos esperables: en `2026-05-11` (lunes próximo de cuando se corrió el seed) hay un evento "Vacunacion antigripal" 09:00-12:00 con encargado equipo demo + 3 ocupaciones residuales del E2E backend.

### A.1 Acceso al módulo
- [ ] **A.1.1** Después de login, en el sidebar aparece la entrada **"agenda"** con icono de calendario.
- [ ] **A.1.2** Click en "agenda" navega a `/agenda` (el shell hace match con el módulo).
- [ ] **A.1.3** La pestaña **timeline** está activa por defecto (barra naranja debajo de la tab).
- [ ] **A.1.4** Header del módulo muestra "agenda" + subtítulo + 4 tabs visibles: timeline / mensual / eventos / conflictos.

### A.2 Vista Timeline — render base
- [ ] **A.2.1** Por defecto, fecha activa = hoy. El input date arriba lo confirma.
- [ ] **A.2.2** Filtros visibles: ChevronLeft, date picker, etiqueta "Martes 11 mayo 2026" (o la fecha que sea), ChevronRight, Hoy, segmentos todos/agente/equipo, indicador "municipio 1".
- [x] **A.2.3** Grilla horaria 07:00-20:00 visible. Header sticky con horas cada hora. La columna izquierda lista los 4 agentes (Juan Pérez, Laura Martínez, María González, Carlos Demo) y los equipos activos. — **backend OK 2026-05-11** (smoke `GET /agenda/calendario` devolvió 8 recursos). UI visual pendiente.
- [ ] **A.2.4** Si la fecha es **hoy**, hay una línea vertical roja con badge "ahora" en la posición de la hora actual.
- [ ] **A.2.5** Si no hay ocupaciones para esa fecha, las filas se ven vacías pero con la grilla intacta (separadores cada hora).

### A.3 Vista Timeline — fecha con datos
- [ ] **A.3.1** Cambiar fecha a `2026-05-11` (o la fecha del evento residual). Aparece un bloque azul "evento" en la fila de un equipo (capacidad 20, encargado).
- [ ] **A.3.2** Hover sobre el bloque muestra tooltip con tipo + horario + descripción corta.
- [ ] **A.3.3** Los bloques de tipo `ot` se ven con borde naranja, `evento` con borde azul, `turno` con borde verde. Verificar visualmente colores distintos.
- [ ] **A.3.4** Si hay una ocupación con conflicto pendiente (de la sesión de Fase 2), el bloque tiene **borde rojo + badge "conflicto"** en la esquina.

### A.4 Filtros de Timeline
- [ ] **A.4.1** Click "todos" → ve agentes + equipos.
- [ ] **A.4.2** Click "agente" → solo agentes (los equipos desaparecen).
- [ ] **A.4.3** Click "equipo" → solo equipos.
- [ ] **A.4.4** ChevronLeft retrocede 1 día; ChevronRight avanza 1 día. La etiqueta de fecha se actualiza.
- [ ] **A.4.5** Click "Hoy" vuelve a la fecha de hoy.

### A.5 Navegación dentro de bloque
- [ ] **A.5.1** Click en bloque tipo `evento` → abre **EventoModal** con los datos del evento, no la ocupación.
- [ ] **A.5.2** Click en bloque tipo `ot` o `turno` → abre **OcupacionModal** en modo lectura con todos los campos.
- [ ] **A.5.3** Click en una celda vacía de un recurso → abre **OcupacionModal** en modo creación con `tipo='turno'`, `tipo_recurso`, `id_recurso`, `fecha`, `hora_inicio`, `hora_fin` pre-cargados (snap a 30 min).
- [ ] **A.5.4** ESC cierra cualquier modal.
- [ ] **A.5.5** Click fuera del modal (overlay) cierra el modal.

### A.6 Modal Evento — crear
- [ ] **A.6.1** Click "Nuevo evento" en la parte superior → abre EventoModal en modo creación con defaults (hora 09:00-10:00, capacidad 10, tipo_qr=ninguno).
- [ ] **A.6.2** Cargar: nombre "Test 3.A", fecha = mañana, hora 14:00-15:00, capacidad 3, encargados 1, tipo_qr=nominal, autoservicio=ON.
- [x] **A.6.3** Submit. Toast verde "Evento creado id=N". — **backend OK 2026-05-11** (`POST /agenda/eventos` retorna 201 con id). Toast UI pendiente.
- [ ] **A.6.4** Inmediatamente después, abre **EventoEncargadosModal** del nuevo evento.

### A.7 Modal Encargados
- [ ] **A.7.1** Lista vacía al inicio.
- [x] **A.7.2** Seleccionar tipo `agente`, ID 1, click "Agregar". Toast verde "Encargado asignado". — **backend OK 2026-05-11** (`POST /eventos/{id}/encargados` retorna `EncargadoConflictoWarning`). UI pendiente.
- [x] **A.7.3** El encargado aparece en la lista con "Pérez, Juan". — **backend OK 2026-05-11** (`GET /eventos/{id}/encargados`).
- [ ] **A.7.4** Click papelera quita el encargado (con confirm). Toast verde "Encargado quitado".
- [ ] **A.7.5** Si asigno un encargado con conflicto de agenda existente, toast NARANJA "Encargado asignado con conflicto" + el encargado igualmente queda asignado.

### A.8 Modal Reservas
- [ ] **A.8.1** Click en EventoModal del evento creado, después click acción "Reservas" (desde tabla de eventos) o abrir manualmente desde botón. Aparece header con capacidad / activas / cupo disponible.
- [ ] **A.8.2** Buscador BUC: tipear "perez" → dropdown con resultados (debounce ~280ms).
- [ ] **A.8.3** Tipear "1164295018" → matchea por teléfono normalizado.
- [ ] **A.8.4** Seleccionar un ciudadano del dropdown → aparece "Seleccionado: Apellido, Nombre" con DNI.
- [x] **A.8.5** Click "Reservar". Toast verde "Reserva creada" + aparece QR como string (`EVT...-RES...-epoch`). — **backend OK 2026-05-11** (3/3 reservas con QR generado).
- [ ] **A.8.6** El cupo disponible decrementa en 1.
- [x] **A.8.7** Crear N reservas más hasta agotar cupo. La última debe dar toast rojo "Sin cupo disponible". — **backend OK 2026-05-11** (4ta reserva rechazada con 422 por cupo).
- [ ] **A.8.8** En la lista de reservas activas, cada reserva tiene 2 botones: CheckCircle (asistio) y X (cancelar).
- [x] **A.8.9** Click cancelar en una reserva → toast verde + la reserva queda atenuada (opacity 0.55) + cupo se libera. — **backend OK 2026-05-11** (`PATCH /reservas/{id}/cancelar`).
- [x] **A.8.10** Click asistio en otra reserva → toast verde + estado cambia a "asistio". — **backend OK 2026-05-11** (`PATCH /reservas/{id}/asistio`).

### A.9 Modal Ocupación — crear
- [ ] **A.9.1** Desde celda vacía en Timeline. Modal abre con datos pre-cargados (tipo=turno, recurso del slot, horario snap a la posición del click).
- [ ] **A.9.2** Cambiar tipo a `ot`. Aparece campo "ID orden de trabajo".
- [ ] **A.9.3** Cambiar tipo a `evento`. Aparece campo "ID evento".
- [ ] **A.9.4** Volver a `turno`. Aparece CiudadanoSearch + textarea motivo.
- [x] **A.9.5** Buscar y seleccionar ciudadano, completar motivo, submit. Toast verde "Ocupacion creada sin conflictos" si la franja está libre. — **backend OK 2026-05-11** (`POST /ocupaciones` retorna `OcupacionCreatedOut` con lista de conflictos).
- [ ] **A.9.6** Crear una ocupación que solape con una existente del mismo agente. Toast NARANJA "Ocupacion creada con conflicto" + el bloque aparece con borde rojo + badge.

### A.10 Modal Ocupación — lectura
- [ ] **A.10.1** Click en una ocupación existente. Modal abre en modo lectura, todos los campos visibles como texto plano.
- [ ] **A.10.2** Botón "Eliminar" abajo. Click → confirm dialog → toast verde "Ocupacion dada de baja".
- [ ] **A.10.3** Recargar timeline: el bloque desaparece (baja lógica, no físico).

### A.11 Vista Mensual
- [ ] **A.11.1** Tab "mensual" → grilla 6×7 del mes actual. Cabecera lun-dom.
- [ ] **A.11.2** El día de hoy tiene borde naranja y peso de fuente más fuerte.
- [ ] **A.11.3** Días con actividad muestran contadores ("2 evt", "5 ocup", "1 lic") + dot naranja en la esquina.
- [ ] **A.11.4** Click ChevronLeft pasa al mes anterior; ChevronRight al siguiente; "Hoy" vuelve al mes actual.
- [ ] **A.11.5** Click en una celda con actividad → navega a `/agenda/timeline` con esa fecha activa.
- [ ] **A.11.6** Click en una celda vacía → navega igualmente al timeline (no debería romper aunque no haya nada que ver).

### A.12 Vista Eventos (event list)
- [x] **A.12.1** Tab "eventos" → tabla con columnas: fecha, horario, nombre, cupo, estado, acciones. — **backend OK 2026-05-11** (`GET /agenda/eventos` con header `X-Total-Count`). UI tabla pendiente.
- [ ] **A.12.2** Header con filtros "desde / hasta" (date inputs) + "total: N" en mono a la derecha.
- [ ] **A.12.3** Estado `activo` con badge verde, `cancelado` con badge rojo.
- [ ] **A.12.4** Botón ícono Calendar abre el modal de editar evento.
- [ ] **A.12.5** Botón ícono Users abre el modal de encargados.
- [ ] **A.12.6** Botón "+R" abre el modal de reservas.
- [ ] **A.12.7** Filtrar por rango de fechas reduce la tabla; el total cambia.
- [ ] **A.12.8** Paginación: "Anterior / Siguiente" + contador "1 - N de M".
- [ ] **A.12.9** Si total > 50, click Siguiente avanza el offset.
- [ ] **A.12.10** Si total = 0 con un rango raro, EmptyState "No hay eventos en el rango".

### A.13 Vista Conflictos
- [x] **A.13.1** Tab "conflictos" → segmentos "pendientes / resueltos / todos" arriba. — **backend OK 2026-05-11** (`GET /agenda/conflictos?resuelto=false`).
- [ ] **A.13.2** Lista de cards con AlertTriangle, descripción, badge "pendiente"/"resuelto", botón "ver".
- [ ] **A.13.3** Si no hay conflictos, EmptyState "No hay conflictos / Genial, no hay solapes pendientes".
- [ ] **A.13.4** Click "ver" → ConflictoModal con 2 columnas (ocupación origen vs conflicto) + textarea observaciones + "Marcar como resuelto".
- [x] **A.13.5** Resolver: agregar texto, click botón → toast verde + modal cierra + el card pasa a estado "resuelto". — **backend OK 2026-05-11** (`PATCH /conflictos/{id}/resolver`).
- [ ] **A.13.6** Filtrar por "resueltos" muestra el que acabo de resolver. "Pendientes" lo oculta.

### A.14 Edición y cancelación de evento
- [ ] **A.14.1** Desde EventListView, abrir un evento. Modal con campos cargados.
- [x] **A.14.2** Cambiar el nombre y submit. Toast "Evento actualizado". El cambio se refleja en la tabla. — **backend OK 2026-05-11** (`PUT /agenda/eventos/{id}`).
- [x] **A.14.3** Botón "Cancelar evento" → confirm → toast → en la tabla el badge pasa a rojo "cancelado". — **backend OK 2026-05-11** (`PATCH /agenda/eventos/{id}/cancelar`).
- [ ] **A.14.4** Botón "Eliminar" → confirm → el evento desaparece de la tabla (activo=FALSE).

### A.15 Comportamiento general
- [x] **A.15.1** Token expirado: forzar `localStorage.removeItem('zaris_session')` y refresh → redirige a `/login`. — **backend OK 2026-05-11** (Bearer inválido → 401, api.ts redirige).
- [ ] **A.15.2** Si el backend está caído, al cargar `/agenda` aparece un mensaje de error en rojo (no se queda colgado).
- [ ] **A.15.3** Los skeletons aparecen mientras carga (no flicker de "vacío").
- [ ] **A.15.4** Cambiar fecha rápido no genera N+1 fetches innecesarios (react-query cachea por queryKey).

### A.16 Accesibilidad (smoke)
- [ ] **A.16.1** Tab navigation por los elementos del modal funciona.
- [ ] **A.16.2** Botones de ícono tienen `aria-label` (inspeccionar uno con DevTools).
- [ ] **A.16.3** ESC cierra modal (ya cubierto en A.5.4).

### A.17 Performance básica
- [ ] **A.17.1** Con 8 recursos × 3 ocupaciones, el render es instantáneo (<100ms).
- [ ] **A.17.2** Si se llega a tener 50 recursos × 30 ocupaciones, debería renderizar en <500ms. (No reproducible con seed actual; testear si se carga más data).

---

## B. Login con usuarios nuevos en prod

**Pre-requisitos:** prod accesible (https://zaris-api-production-bf0b.up.railway.app + https://cesarzeta.github.io/zaris-zge/).

Sembrado el 2026-05-10:
- `lmartinez@municipio.gob.ar` / `123456` → Laura Martínez (agente id=2, usuario id=7, nivel 3, no auditor).
- `mgonzalez@municipio.gob.ar` / `123456` → María González (agente id=3, usuario id=8, nivel 3, auditor).

- [ ] **B.1** Login con `lmartinez` aterriza en el shell con sidebar visible.
- [ ] **B.2** `lmartinez` ve la entrada "Mesa Agente" en sidebar y al entrar ve OTs asignadas a su agente y OTs disponibles para tomar.
- [ ] **B.3** `lmartinez` **NO** ve "Mesa Auditoría" (porque `es_auditor=FALSE`).
- [ ] **B.4** Logout, login con `mgonzalez` aterriza en el shell.
- [ ] **B.5** `mgonzalez` ve la mesa Agente y la mesa Auditoría.
- [ ] **B.6** Tomar una OT disponible desde la mesa Agente como `lmartinez` la asigna al agente correctamente.
- [ ] **B.7** Cambiar estado de OT desde mesa Agente funciona y deja entrada en historial.
- [ ] **B.8** Aprobar/Rechazar OT desde mesa Auditoría como `mgonzalez` funciona y dispara el flujo (Resuelto / nueva OT Pendiente).

---

## C. Módulo Reclamos (frontend vanilla)

> Frontend vanilla en `frontend/reclamos.html`. Solo en local con backend local, o contra Railway.

### C.1 Modal "Nuevo reclamo" — buscador ciudadano
- [ ] **C.1.1** Buscador autocompletar muestra dropdown con 2 líneas (apellido+nombre+DNI / teléfono+email+dirección+edad).
- [ ] **C.1.2** Highlight del término buscado en los resultados.
- [ ] **C.1.3** Indicador "Buscando..." con spinner CSS.
- [ ] **C.1.4** Footer "y N más — refiná la búsqueda" cuando `total > limit`.
- [ ] **C.1.5** Buscar por teléfono con formato `(11) 6429-5018` matchea correctamente.
- [ ] **C.1.6** Búsqueda multi-palabra hace AND (ej: "perez juan" no devuelve todos los "Pérez").
- [ ] **C.1.7** Navegación con teclado en dropdown (↓ ↑ Enter Esc).
- [ ] **C.1.8** Modal anidado de alta de ciudadano (botón "+ Nuevo") funciona con todos los campos requeridos.

### C.2 Modal "Nuevo reclamo" — tipo + área
- [ ] **C.2.1** Buscador "Tipo de reclamo" autocompletar funciona; deduce Área/Subárea al seleccionar.
- [ ] **C.2.2** No hay select de Área independiente (fue removido en sesión 2026-05-09).

### C.3 Modal "Nuevo reclamo" — geo
- [ ] **C.3.1** Mapa Leaflet carga (tiles OSM visibles).
- [ ] **C.3.2** Pin manual setea `fuente_geolocalizacion='pin_manual'`.
- [ ] **C.3.3** Búsqueda Nominatim devuelve sugerencias; al elegir setea `fuente='geocoding_osm'`.
- [ ] **C.3.4** Selector de activo en mapa: al elegir activo, lat/lon del activo se copian y `fuente='activo_referenciado'`.

### C.4 Modal "Nuevo reclamo" — empresa + adjuntos
- [ ] **C.4.1** Si el ciudadano tiene empresas vinculadas, aparecen en el select; si no, queda deshabilitado.
- [ ] **C.4.2** Modal anidado de alta de empresa funciona y vuelve al padre con la nueva empresa preseleccionada.
- [ ] **C.4.3** Adjuntos: drag&drop + file picker + preview base64 + delete por archivo antes de guardar.
- [ ] **C.4.4** Al guardar: POST /reclamos OK + por cada adjunto: upload-url → PUT → confirm.
- [ ] **C.4.5** Si algún upload falla, toast informa cuántos subieron.

### C.5 Drawer detalle
- [ ] **C.5.1** Drawer abre con sección Ubicación + link OSM operativo.
- [ ] **C.5.2** Empresa vinculada se muestra como "A nombre de empresa: <nombre> (CUIT)".
- [ ] **C.5.3** Galería de adjuntos en grid; click abre lightbox; ESC / click fuera cierra.
- [ ] **C.5.4** Hover sobre adjunto muestra botón × para borrar (soft-delete + remove del bucket).
- [ ] **C.5.5** Historial muestra timeline completo con notas custom de ediciones.

### C.6 Editar / cancelar / sub-reclamo
- [ ] **C.6.1** "Editar" solo visible si reclamo no cerrado y `nivel_acceso ≤ 3`.
- [ ] **C.6.2** Reclamo en "Sin asignar": modal muestra todos los campos editables.
- [ ] **C.6.3** Reclamo en "En gestión/En espera/En auditoría": modal solo Observaciones + Nota.
- [ ] **C.6.4** Intentar editar campo prohibido en estado vivo → 422 visible en DevTools.
- [ ] **C.6.5** "Cancelar reclamo" pide motivo obligatorio + advierte cascade a OTs activas.
- [ ] **C.6.6** Tras cancelar: reclamo pasa a Cancelado, fecha_cierre se setea, OTs activas pasan a Cancelada.
- [ ] **C.6.7** Crear sub-reclamo desde drawer del padre. Padre pasa a "En espera". Sub-reclamo hereda `id_empresa` (override permitido).
- [ ] **C.6.8** Intentar crear sub-reclamo de un sub-reclamo → rechazado (max 1 nivel).

---

## D. Módulo Órdenes de Trabajo (frontend vanilla)

### D.1 Mesa Supervisor (`ot_supervisor.html`)
- [ ] **D.1.1** Tab "Asignar": lista reclamos sin OT activa, columnas Subárea, SLA color-coded.
- [ ] **D.1.2** Multi-select batch + asignar a agente/equipo en una sola acción.
- [ ] **D.1.3** Tab "Reasignar": lista OTs activas, permite reasignar con nota obligatoria.
- [ ] **D.1.4** Reasignación deja entrada en `reclamo_historial`.

### D.2 Mesa Agente (`ot_agente.html`)
- [ ] **D.2.1** Como `lmartinez`: ve OTs asignadas + OTs disponibles ("Pendientes para tomar").
- [ ] **D.2.2** "Tomar OT" pasa la OT a su nombre y la mueve a su lista.
- [ ] **D.2.3** Cambiar estado de OT (En gestión / En espera / Terminada) deja entrada en historial.

### D.3 Mesa Auditoría (`ot_auditoria.html`)
- [ ] **D.3.1** Como `mgonzalez`: ve OTs en estado "En auditoría".
- [ ] **D.3.2** Si `auditor_misma_subarea_permitido=FALSE`, no ve OTs de su misma subárea.
- [ ] **D.3.3** "Aprobar": OT → Terminada, reclamo → Resuelto, `fecha_cierre` se setea.
- [ ] **D.3.4** "Rechazar": nueva OT Pendiente con `id_ot_origen` apuntando a la rechazada, reclamo vuelve a En gestión.

---

## E. Admin tablas — drill-down inline

> `frontend/admin_tablas.html?tabla=<nombre>`.

- [ ] **E.1** Listado de **Áreas**: cada fila muestra sus subáreas asociadas debajo con sangría e indicador naranja, sin botón.
- [ ] **E.2** Listado de **Subáreas**: cada fila muestra sus tipos de reclamo asociados.
- [ ] **E.3** Panel de búsqueda celeste visible como primer elemento (`renderVistaPrevia`).
- [ ] **E.4** **No** debe haber badges de conteo duplicados en la celda nombre (el conteo va en el título del panel).
- [ ] **E.5** Sí debe haber badge en preview de 5 últimos.
- [ ] **E.6** **Agentes**: columna `id_usuario` se resuelve a nombre (no número), `es_auditor` se edita como checkbox.

---

## F. Breadcrumb en frontends vanilla

Verificar `INICIO › <Módulo>` arriba del título con clase `.zaris-breadcrumb`.

- [ ] **F.1** `frontend/reclamos.html`
- [ ] **F.2** `frontend/admin_tablas.html` (3 templates: listado, formulario, vista previa)
- [ ] **F.3** `frontend/agenda.html`
- [ ] **F.4** `frontend/ciudadano.html`
- [ ] **F.5** `frontend/empresa.html`
- [ ] **F.6** `frontend/mainconfig.html`
- [ ] **F.7** `frontend/usuarios.html`
- [ ] **F.8** `frontend/ot_supervisor.html`
- [ ] **F.9** `frontend/ot_agente.html`
- [ ] **F.10** `frontend/ot_auditoria.html`

Para cada uno chequear:
- Color naranja del link INICIO.
- Separador `›` visible.
- Click en INICIO navega al welcome (via `shellNavigate` si está en iframe).
- Acceso standalone (`https://cesarzeta.github.io/zaris-zge/frontend/X.html`) redirige al shell con el módulo cargado en iframe.

---

## G. Topbar — menú de usuario

- [ ] **G.1** Click en nombre/avatar abre dropdown con nombre completo + rol.
- [ ] **G.2** Botón "Cerrar sesión" limpia `localStorage.zaris_session` y redirige a `frontend/login.html`.
- [ ] **G.3** Login con admin (`ciudadanovl`) — ver nombre "Cesar Zeta" + rol Administrador.
- [ ] **G.4** Login con `lmartinez` — ver nombre "Laura Martínez" + rol Operador.

---

## Notas operativas

- Si una prueba falla, anotar acá debajo con fecha + descripción + entorno.
- Marcar `[x]` solo cuando se verificó manualmente.
- Para probar en prod hay que pushear los cambios. Para probar en local: `cd backend; $env:ENV_FILE=".env.local"; uvicorn app.main:app --host 127.0.0.1 --port 8000` + `python -m http.server 8080` (raíz) o `cd web-app; pnpm dev`.
- Las pruebas del módulo Agenda (bloque A) solo aplican a la web-app React (port 5173). El resto sigue siendo vanilla en port 8080.

### Fallos detectados

_(vacío — se completa cuando aparezca alguno)_

| Fecha | Caso | Detalle | Entorno | Estado |
|---|---|---|---|---|
| | | | | |
