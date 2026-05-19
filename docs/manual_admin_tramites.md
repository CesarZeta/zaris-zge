# Manual de uso — Configuración de trámites

**Audiencia:** Admin (nivel 1) o Supervisor (nivel 2) del municipio.
**Acceso:** Trámites → tab **Configuración**.
**Versión:** 2026-05-18 · UI cerrada en sesión del día.

---

## 1. Conceptos clave (leer una vez)

Antes de empezar a clickear, hay 3 cosas que conviene entender:

### 1.1 Tipo vs versión
Cada **tipo de trámite** (ej. "Poda de árbol", código `poda-arbol`, prefijo `POD`) puede tener **varias versiones** de su circuito interno. Solo una versión está **publicada** a la vez — es la que se usa para crear nuevos trámites.

### 1.2 Estados posibles de una versión
- **Borrador** (`borrador`) — Editable. Sirve para diseñar/ajustar el circuito antes de publicarlo. Solo puede haber **un** borrador abierto por tipo.
- **Publicado** (`publicado`) — Versión activa. Cualquier trámite nuevo se crea contra esta versión.
- **Archivado** (`archivado`) — Versión histórica. Trámites creados con ella siguen funcionando, pero no se crean nuevos.

### 1.3 Regla de edición (importante)
- Una versión **publicada sin trámites** todavía se puede editar in-place.
- Una versión **publicada con trámites instanciados** queda **inmutable**. Para cambiar el circuito hay que **crear un nuevo borrador** (la UI hace una copia exacta de la publicada, y a partir de ahí editás libre).
- Una versión **archivada** nunca se edita.

> Esta regla protege la trazabilidad: si modificás el FSM de un trámite ya en curso, podrías romper su historial. La copia + nueva versión es la forma segura.

---

## 2. Crear un tipo nuevo (de cero)

Pantalla: `Trámites → Configuración → Nuevo tipo`

1. Completá:
   - **Código** (obligatorio) — Kebab-case (`a-z`, `0-9`, guiones). Ej: `poda-arbol`. Es único y **no se puede cambiar después**.
   - **Nombre** (obligatorio) — Lo que ve el usuario. Ej: "Poda de árbol".
   - **Prefijo numerador** (obligatorio) — 1 a 20 chars MAYÚSCULAS+números. Ej: `POD` → expedientes "POD-LPL-2026-0001".
   - **Iniciadores permitidos** — Quién puede iniciar este trámite. Al menos uno de: `ciudadano`, `empresa`, `area_interna`.
   - **Largo correlativo** — 1 a 8. Default 4 (genera "0001" hasta "9999" por año).
   - **Permitir representante** (opcional) — Si lo marcás, un ciudadano puede iniciar el trámite en nombre de otro.
   - **Descripción** (opcional).

2. Click **"Crear tipo"**. La UI te redirige automáticamente al **editor de la v1 (borrador)**.

> ⚠️ Acabás de crear el tipo, pero **no está publicado**. La v1 está vacía (sin estados, campos ni transiciones). Tenés que agregarle al menos 1 estado inicial + 1 estado final antes de poder publicar.

---

## 3. Editor de una versión (la pantalla más importante)

Llegás haciendo click en el icono ⚙ de la lista de tipos.

### 3.1 Layout

- **Arriba:** nombre del tipo + botones **Editar tipo** (modifica datos identitarios) y **Desactivar** (soft-delete).
- **Selector de versiones:** pills `v1 borrador` / `v2 publicado` / `v3 archivado`. Click en cualquiera para verla. La activa queda en negro.
- **Botones de versión:**
  - **Nuevo borrador** — Crea una versión nueva en borrador. Si la publicada actual tiene estructura, la copia. Bloqueado si ya hay un borrador abierto.
  - **Publicar** — Solo aparece si la versión activa es borrador. Valida que tenga 1 estado inicial + ≥1 final.
  - **Archivar** — Solo aparece si es borrador o publicada.
- **Mensaje de estado** debajo de los botones — Te dice si la versión es editable o no, y por qué.
- **5 Tabs:** General · Campos · Estados · Transiciones · Docs requeridos.

### 3.2 Tab General

Tabla de solo lectura con todos los datos identitarios del tipo (código, prefijo, largo correlativo, etc.). Para editarlos usá el botón **"Editar tipo"** del header.

### 3.3 Tab Campos

Son los campos del **formulario de inicio** que ve el iniciador al crear un trámite de este tipo.

**Para agregar:** botón **Nuevo** → modal:
- **Nombre interno** (snake_case, único, no editable después) — Es la key en `datos_jsonb`. Ej: `motivo`, `monto_solicitado`.
- **Etiqueta visible** — Lo que ve el iniciador. Ej: "Motivo de la solicitud".
- **Tipo de dato** — Texto, número, fecha, sí/no, selección (con opciones), buscador de ciudadano/empresa/agente/subárea/equipo, dirección con buscador OSM, adjunto inline.
- **Opciones** (solo si tipo = selección / selección múltiple) — Una por línea, formato `valor|Etiqueta visible`. Ejemplo:
  ```
  alta|Alta
  media|Media
  baja|Baja
  ```
- **Orden** — Para ordenar visualmente.
- **Obligatorio** — Si el iniciador debe completarlo sí o sí.
- **Visible en bandeja** — Si aparece como columna en la lista de trámites.
- **Ayuda** (tooltip).

### 3.4 Tab Estados

Son los **nodos del circuito** (la máquina de estados). Cada trámite siempre está en exactamente un estado.

**Para agregar:** botón **Nuevo** → modal:
- **Código** (snake_case, único, no editable después) — Ej: `ingresado`, `en_revision`, `resuelto`.
- **Etiqueta visible** — Ej: "Ingresado", "En revisión".
- **Descripción** — Texto largo para que el agente entienda qué significa el estado.
- **Color del badge** — Color picker + paleta sugerida (azul/verde/amarillo/rojo/gris/violeta). Es el color que se ve en la bandeja al lado del estado.
- **Orden** — Para ordenar la lista en la UI.
- **Estado inicial** — Cada versión debe tener **exactamente uno**. Todo trámite nuevo arranca acá.
- **Estado final** — Puede haber varios (ej: "Resuelto", "Cancelado", "Rechazado"). Cuando un trámite llega a un estado final, ya no se le pueden ejecutar más transiciones.
- **Permite adjuntar / comentar** — Si el agente puede subir docs o comentar mientras el trámite está en este estado.

> 💡 **Mínimo para publicar:** 1 estado inicial + 1 estado final. Sin esto, "Publicar" devuelve error 409.

### 3.5 Tab Transiciones

Son las **flechas del circuito** — los botones que aparecen en cada estado para pasar al siguiente.

**Para agregar:** botón **Nuevo** → modal:
- **Estado origen** — Desde dónde sale la transición.
- **Estado destino** — A dónde va. **No puede ser igual al origen.**
- **Etiqueta del botón** — Lo que ve el agente. Ej: "Aprobar", "Rechazar", "Pasar a revisión", "Derivar a Espacios Verdes".
- **Orden** — Si hay varias transiciones desde el mismo estado, controla en qué orden aparecen.
- **Requiere comentario obligatorio** — Forza al agente a escribir un comentario al ejecutar esta transición.
- **Requiere al menos un adjunto nuevo** — Forza al agente a subir un documento desde que entró al estado origen.
- **Notifica al iniciador** — Si dispara mail + notificación in-app al iniciador cuando se ejecute.

> Necesitás ≥ 2 estados antes de poder crear transiciones. El botón "Nuevo" queda deshabilitado si no hay.

### 3.6 Tab Docs requeridos

Son los **documentos que el sistema espera** en distintos momentos del circuito.

**Para agregar:** botón **Nuevo** → modal:
- **Nombre** — Ej: "DNI del solicitante", "Plano del lote".
- **Descripción**.
- **Vincular al estado** — Si lo dejás vacío, es un documento **exigible al iniciar el trámite**. Si elegís un estado, se vuelve exigible al entrar a ese estado.
- **Aporta** — `iniciador` (el ciudadano/empresa lo carga), `oficina_actual` (lo carga el agente que tiene el trámite), `cualquiera`.
- **Formatos permitidos** — Chips clickeables (pdf, jpg, jpeg, png, webp, heic, doc/x, xls/x). Naranja = activado.
- **Tamaño máx (MB)** — Default 10.
- **Obligatorio** — Si el flujo se bloquea hasta tenerlo.
- **Requiere firma digital** — Si pide firma post-upload.

---

## 4. Flujos típicos

### 4.1 Crear un tipo de cero y publicarlo

1. Configuración → **Nuevo tipo** → completar form → guardar.
2. La UI te lleva al editor con v1 en borrador.
3. Tab **Estados** → crear "Ingresado" (es_inicial=✓), "En revisión", "Resuelto" (es_final=✓).
4. Tab **Transiciones** → crear "Ingresado → En revisión" (etiqueta "Pasar a revisión"), "En revisión → Resuelto" (etiqueta "Resolver", requiere_comentario=✓).
5. Tab **Campos** → crear los campos del form inicial.
6. Tab **Docs requeridos** → crear los docs que el ciudadano debe adjuntar al iniciar.
7. Volver arriba → **Publicar**. La UI confirma y la v1 pasa a estado publicado.

Desde ese momento, los usuarios pueden crear trámites de este tipo desde **Trámites → Nuevo**.

### 4.2 Modificar el circuito de un tipo ya en uso

1. Configuración → click ⚙ del tipo.
2. La v1 publicada está bloqueada (mensaje: "Esta versión tiene N trámite(s) instanciado(s). Es inmutable…").
3. Click **Nuevo borrador** → la UI crea v2 copiando toda la estructura de v1.
4. Editás v2 libremente.
5. Click **Publicar** → v2 queda activa, v1 pasa a archivada.
   - Los trámites en curso siguen con la versión v1 (su circuito original).
   - Los nuevos trámites usan v2.

### 4.3 Desactivar un tipo (que ya no se usa)

1. Click ⚙ del tipo.
2. Botón **Desactivar** (arriba a la derecha).
3. Confirmar.
4. Si tiene trámites activos → rechazado con HTTP 409. Hay que esperar a que se cierren o transferirlos.
5. Si no tiene → soft-delete (`activo=FALSE`). El tipo desaparece de la lista pero sigue en DB para auditoría.

### 4.4 Archivar una versión publicada

Cuando ya no querés que un tipo acepte nuevos trámites pero querés conservarlo:
1. Click ⚙ del tipo → versión publicada activa.
2. Botón **Archivar** → confirmar.
3. El tipo queda sin versión publicada (los usuarios no pueden crear más trámites de ese tipo, pero los existentes siguen funcionando).

Si querés volver a abrir el tipo, creá un nuevo borrador y publicalo.

---

## 5. Errores comunes y qué hacer

| Síntoma | Causa | Solución |
|---|---|---|
| "Ya existe un tipo con código X" | Códigos son únicos por municipio | Elegí otro código |
| "Solo se puede publicar una versión en estado borrador" | Click en Publicar sobre archivada/publicada | Crear borrador primero |
| "La versión debe tener exactamente 1 estado inicial" | 0 o 2+ estados con `es_inicial=TRUE` | Editá los estados y dejá exactamente uno marcado |
| "La versión debe tener al menos 1 estado final" | Ningún estado con `es_final=TRUE` | Marcá al menos uno como final |
| "No se puede desactivar: hay N trámite(s) activo(s)" | El tipo tiene expedientes vivos | Esperar/cerrar trámites, o solo archivar la versión |
| "No se puede desactivar el estado: hay N transiciones que lo referencian" | El estado está en uso como origen o destino | Borrar primero las transiciones que lo usan |
| "Ya existe un borrador abierto" | Hay un borrador anterior sin publicar | Publicalo o archivalo |
| "Origen y destino no pueden ser el mismo estado" | Click "Guardar" con mismo estado en ambos selects | Cambiar uno |
| Botón "Nuevo" en Transiciones está deshabilitado | La versión tiene <2 estados | Agregar estados primero |

---

## 6. Detalles que no son obvios

- **Iconos del sidebar:** los tipos no tienen icono en el sidebar (sigue siendo "trámites"). El campo `icono` del tipo se reserva para futuras visualizaciones (badge color, ícono en la card de "Nuevo trámite", etc.).
- **Numerador:** el correlativo se reinicia cada año (`correlativo_reinicia_anual=TRUE` por default). Si lo desactivás, el contador sigue creciendo sin reiniciarse.
- **`incluye_municipio`:** controla si el número de expediente lleva el código del municipio. Default `TRUE` ("POD-**LPL**-2026-0001"). Útil desactivar si el municipio es uno solo.
- **Eliminar vs Desactivar:** la UI dice "Desactivar" porque siempre hace **soft-delete**. Para borrar físicamente hay que entrar a la DB. Por diseño se evita el delete físico (regla §5 del CLAUDE.md).
- **Notificación al publicar:** cuando publicás v2, los agentes que estaban trabajando en v1 **no reciben notificación**. Si querés avisarles, hacelo por afuera (mail, Slack, etc.).
- **Documentos requeridos vinculados a un estado borrado:** si borrás un estado que tenía docs requeridos vinculados, los docs siguen ahí con `id_tipo_tramite_estado=NULL` (= exigibles al inicio). Conviene editarlos.

---

## 7. ¿Y si necesito algo más complejo?

Estos casos **NO** están soportados por la UI actual (solo via API):

- **Permisos finos por transición** (`quien_puede_jsonb` con `subareas`/`equipos`/`roles`) — La UI siempre la deja vacía (`{}`), que significa "cualquier agente autorizado puede ejecutar". Si necesitás restringir, hay que editar la DB directo o llamar al endpoint `PUT /api/v1/admin/tramites/transiciones/{id}`.
- **Destino automático** (`destino_automatico_jsonb`) — Permite que al ejecutar una transición, el trámite pase automáticamente a una subárea/equipo. Pendiente UI.
- **Validaciones JSONB en campos** (`validacion_jsonb`) — Reglas tipo `{"min":0,"max":1000}` para `monto`. Pendiente UI.
- **Firmantes JSONB en docs** (`firmantes_jsonb`) — Lista de roles que deben firmar un documento. Pendiente UI.

Si necesitás cualquiera de estos antes de que se haga la UI, avisar y se agrega.

---

## 8. Atajos / glosario

| Término | Qué es |
|---|---|
| Tipo | Catálogo (poda-arbol, licencia-ordinaria…) |
| Versión | Snapshot del circuito de un tipo (v1, v2…) |
| FSM | Finite State Machine = máquina de estados = circuito |
| Estado | Nodo del FSM (ingresado, en_revision, resuelto…) |
| Transición | Arco del FSM = botón que pasa el trámite de un estado al siguiente |
| Campo | Input del form que llena el iniciador al crear el trámite |
| Doc requerido | Archivo que el sistema espera en algún momento del flujo |
| Iniciador | Quién crea el trámite (ciudadano / empresa / area_interna) |
| Bandeja | Lista de trámites del módulo (los "expedientes") |

---

## 9. Endpoints de la API (referencia para devs)

Si necesitás scriptear o automatizar el catálogo, todos los endpoints están en `/api/v1/admin/tramites/*`:

```
POST   /tipos                              crear tipo + v1 borrador
PUT    /tipos/{id}                         editar datos del tipo
DELETE /tipos/{id}                         soft-delete tipo
GET    /tipos/{id}/admin                   detalle con todas las versiones
GET    /versiones/{id}                     detalle completo de una versión (campos+estados+transiciones+docs)
POST   /tipos/{id}/versiones               crear nuevo borrador (copia la publicada)
POST   /versiones/{id}/publicar            publicar borrador
POST   /versiones/{id}/archivar            archivar versión
POST   /versiones/{id}/campos              crear campo
PUT    /campos/{id}                        editar campo
DELETE /campos/{id}                        soft-delete campo
POST   /versiones/{id}/estados             crear estado
PUT    /estados/{id}                       editar estado
DELETE /estados/{id}                       soft-delete estado
POST   /versiones/{id}/transiciones        crear transición
PUT    /transiciones/{id}                  editar transición
DELETE /transiciones/{id}                  soft-delete transición
POST   /versiones/{id}/documentos-requeridos    crear doc requerido
PUT    /documentos-requeridos/{id}              editar doc requerido
DELETE /documentos-requeridos/{id}              soft-delete doc requerido
```

Todos requieren JWT (`Authorization: Bearer <token>`) con `nivel_acceso <= 2`.

---

**Fin del manual.** Cualquier inconsistencia con la UI real avisar para actualizarlo.
