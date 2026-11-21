# Trámites desde el portal del vecino — diseño

Fecha: 2026-11-21. Estado: borrador para aprobación de César.

## 1. Intención

Que el vecino pueda hacer sus trámites sin ir a la ventanilla: **iniciarlos, ver en qué estado están, subir los documentos que le corresponden y responder cuando el municipio le pide algo.** Es el punto 2 del «bloque del vecino» que César ordenó el 2026-10-27 («todas las prestaciones del vecino»): reclamos, turnos y entradas ya se hacen desde la app; los trámites no.

Hoy (verificado en prod el 2026-11-21):
- El vecino no tiene ningún endpoint ni pantalla de trámites; solo recibe avisos en «Alertas» (`tramite_estado`, `tramite_pendiente`, con url `/alertas`).
- San Andrés tiene 6 tipos reales que admiten iniciador ciudadano (aviso-obra, poda-arbol, inscripcion-profesional, exencion-tasas, permiso-espacio-publico, recurso-administrativo). Cuatro piden documentos obligatorios. Todos tienen gestión responsable (`tipo_tramite.id_subarea`) con agentes.
- Ningún circuito tiene un paso donde el municipio le pida algo al vecino y el vecino conteste. El único estado con `espera_iniciador` (inscripcion-profesional «subsanar») no tiene transiciones de entrada ni de salida. Mientras tanto, el timer de desistimiento le manda mails al vecino pidiéndole documentación que no tiene dónde presentar.

## 2. Objetivos, no-objetivos, anti-objetivos

**Objetivos**
1. El vecino logueado elige un tipo, completa el formulario del tipo y adjunta los documentos que le corresponden; el trámite nace con número y entra a la bandeja de la gestión responsable.
2. Ve la lista de sus trámites y el detalle de cada uno: estado, resultado, datos cargados, sus documentos e historial.
3. Sube los documentos que el circuito le pide en el estado actual.
4. Responde (texto + archivos) los pedidos que le hace el municipio.
5. Del lado del municipio: el agente puede «Pedir al vecino» desde el detalle del trámite y ve la respuesta.

**No-objetivos (esta etapa)**
- Trámites de empresa (Habilitación comercial y los otros 6 de empresa): segunda etapa.
- Que el vecino desista, cancele o edite un trámite ya iniciado (misma decisión vigente que en reclamos).
- Pagos, firma digital del vecino, modo escritorio del portal (tiene su propio diseño pendiente).
- Ver los documentos que sube el municipio.

**Anti-objetivos (aunque funcione, sería un fracaso si…)**
- El vecino ve información interna: comentarios, pases, tomas, nombres de agentes.
- Un trámite nace sin sus documentos obligatorios, o sin gestión que lo reciba.
- El vecino responde un pedido y nadie del municipio se entera.
- Un vecino ve o toca un trámite de otro.

## 3. Restricciones

- **Regla básica de César (2026-11-21): ningún trámite ni servicio se hace sin cuenta de vecino o de empresa**, porque la cuenta tiene los datos para las devoluciones y las notificaciones. Consecuencias en este proyecto:
  - El alta del backoffice (`POST /tramites`) con iniciador ciudadano **exige que el ciudadano tenga cuenta de vecino** (credencial activa, activada o pendiente de activar); si no, 422 «El vecino no tiene cuenta en el portal: dale de alta la cuenta desde su ficha». Hoy no lo exige: en prod hay 9 trámites cargados por agentes a vecinos sin cuenta (más 226 del generador demo, que escribe por SQL y no pasa por el endpoint).
  - «Pedir al vecino» exige lo mismo (422 con el mismo criterio): cubre los trámites viejos y los demo.
  - Que reclamos, turnos y entradas cargados en el backoffice cumplan la misma regla **queda fuera de este proyecto** y se anota como pendiente para verificar.

- Todo lo de IT-01: el municipio sale del token del vecino (`municipio_vecino`); tabla nueva clasificada en `municipio_tabla_clase` (`operativo`, grupo `operativo`) con su política `barrera_municipio` y RLS; FK compuestas `(id_municipio, col)`; migraciones desde la **139**, aplicadas en local y prod.
- Archivos con `storage.ruta_de_municipio` (bucket `tramites-documentos`), SHA256 como hoy.
- Router público con `get_current_ciudadano`, `modulo_habilitado("tramites")`, rate limit con prefijo propio. El `id_ciudadano` sale siempre del token. Lo ajeno responde 404 igual que lo inexistente.
- La PWA es un repo aparte con deploy independiente: el backend va primero y se verifica en `/openapi.json` de prod antes de publicar la PWA (CLAUDE.md §9).
- Actualizar `docs/contrato_api_publica.md` (contrato que consume la PWA).
- Las rutas fijas nuevas en `routes/tramites.py` van antes de los greedy `/{numero_o_id}` (§5).

## 4. Enfoques considerados

- **A. El pedido como paso del circuito**: un estado «Esperando al vecino» con transiciones de entrada (agente) y salida (vecino) en cada tipo. Obliga a rediseñar los 6 tipos y los futuros, y solo se puede pedir en las etapas previstas.
- **B. «Pedido al vecino» paralelo al circuito** — **elegido por César el 2026-11-21.** El pedido es una marca sobre el trámite, como `resultado` o el archivado: no cambia el estado del FSM, funciona en todos los circuitos existentes sin tocarlos y en cualquier etapa.

## 5. Diseño

### 5.1 Qué tipos se le ofrecen al vecino
- Columna nueva `tipo_tramite.ofrecer_al_vecino BOOLEAN NOT NULL DEFAULT FALSE` (fail-closed: un tipo nuevo no aparece hasta que alguien lo marca). Casilla «Se ofrece al vecino en el portal» en el configurador de tipos (alta y edición), visible solo si `iniciadores_permitidos` incluye `ciudadano`.
- La migración la prende, **por código**, en los 6 tipos reales de San Andrés y en los que existan de esa lista en el modelo (el modelo no tiene inscripcion-profesional: quedan 5). `permiso-demo-e2e` queda apagado. *(Decisión de Claude: lista cerrada por código, no «todos los de ciudadano».)*
- Se ofrece si: activo, versión publicada, `ofrecer_al_vecino`, `ciudadano` en iniciadores, gestión (`id_subarea`) asignada y activa, y ningún campo activo de tipo `agente` o `subarea` (son internos). Si falla alguna, no aparece.

### 5.2 El vecino como actor (migración)
Hoy `tramite.id_agente_iniciador`, `tramite_movimiento.id_agente` y `tramite_documento.id_agente_subio` son NOT NULL. Cambios:
- Las tres pasan a admitir NULL.
- `tramite_movimiento.id_ciudadano_actor` y `tramite_documento.id_ciudadano_subio` nuevas (FK compuesta a `ciudadanos`).
- CHECK: nunca los dos actores a la vez. *(Decisión de Claude: se permite que ambos sean NULL para las acciones del sistema, como hacen hoy los crons con el agente iniciador como relleno; el builder decide si los crons siguen igual.)*
- En los trámites que inicia el vecino, `id_agente_iniciador` queda NULL. **Todo consumidor de esas tres columnas tiene que tolerar el NULL**: autorización (`{"iniciador": true}` deja de cumplirse, que es lo correcto), retención, desistimiento, ciclo de vida, el generador demo y las pantallas del backoffice (el «Iniciado por» muestra al ciudadano).
- El destinatario inicial es la gestión del tipo (`destinatario_actual_tipo='subarea'`, `id_subarea_actual = tipo_tramite.id_subarea`).
- `id_usuario_alta` queda NULL (el vecino no es `usuarios`), como en reclamos.

### 5.3 Iniciar
- `GET /publico/tramites/tipos` (los ofrecidos, con nombre y descripción) y `GET /publico/tramites/tipos/{id}` (campos activos con tipo, obligatoriedad, opciones y ayuda; documentos «del alta»: `aporta_quien='iniciador'` **sin estado o atados al estado inicial**, con formatos, tamaño y cantidad máxima). *(Decisión de Claude: los dos grupos, porque en prod poda-arbol y recurso-administrativo atan su documento obligatorio al estado inicial; con solo «sin estado» nacerían sin él.)*
- Un documento requerido con `requiere_firma` no se le pide al vecino ni se acepta de él (hoy ninguno de los seis tipos tiene uno así). *(Decisión de Claude.)*
- `POST /publico/tramites` **multipart**: `id_tipo_tramite`, `datos` (JSON) y los archivos, cada uno asociado a su documento requerido. **Atómico:** se valida todo antes de crear (campos con `validar_campos_contra_tipo`, documentos obligatorios del alta presentes, formatos, tamaños y cantidades). Si algo falla, 422 y no se crea nada. Los archivos se suben a Storage antes del commit y se borran si la transacción falla.
- Crea el trámite como el `POST /tramites` de hoy (numerador, estado inicial, movimientos `creacion` y `numeracion` con `id_ciudadano_actor`, aprobaciones del estado inicial) y luego `tramite_documento` + movimiento `adjunto` por cada archivo. Post-commit: `notificar_tramite_a_bandeja` y `notificar_inicio_a_iniciador` (ya existen).
- La lógica común con el `POST /tramites` del backoffice se extrae a un servicio; no se duplica. *(Decisión de Claude.)*
- Campos `direccion`: la PWA usa su buscador y su mapa (`MapaPicker`), y manda el objeto `{texto, lat, lon}` que el validador ya acepta.

### 5.4 Ver
- `GET /publico/tramites` → **todos** los suyos (`id_ciudadano_iniciador` = token), sin importar dónde se iniciaron (ventanilla o app) ni si el tipo se ofrece hoy al vecino (César, 2026-11-21). En el detalle de cualquiera se ocultan los campos de tipo `agente` o `subarea`. Del más nuevo al más viejo: número, tipo, estado (etiqueta y color), resultado, fecha de inicio, `tiene_pedido_abierto`, `documentos_pendientes` (cantidad).
- `GET /publico/tramites/{id}` → detalle: lo de la lista + los datos que cargó (con las etiquetas de los campos), sus documentos, los documentos que le pide el estado actual, el pedido abierto si hay y el historial.
- **Historial para el vecino** (lista cerrada de tipos de movimiento): creación, transición (etiqueta del estado destino + `mensaje_iniciador` de la transición si tiene), pedido y respuesta, adjunto subido por él, resultado, aviso al iniciador, desistido, archivado. **Nunca** comentarios, pases, tomas, liberaciones, firmas, relaciones, aprobaciones ni nombres de agentes. Cada fila: fecha, texto y nada más.
- `GET /publico/tramites/{id}/documentos/{id_doc}/contenido` → solo los documentos que subió él; 410 si el binario fue purgado (mismo criterio que el backoffice).
- `/publico/portal/mi-resumen` suma `tramites: {vigentes, total, pedidos_abiertos}`. Vigente = no archivado y estado no final.

### 5.5 Documentos del estado actual
- Los documentos requeridos con `aporta_quien='iniciador'` e `id_tipo_tramite_estado` = estado actual del trámite son «lo que te pide este paso». El catálogo ya tiene 27 de esos.
- `POST /publico/tramites/{id}/documentos` (multipart, uno o varios archivos con su documento requerido) solo acepta esos, con sus formatos, tamaños y cantidad máxima. Crea `tramite_documento` + movimiento `adjunto` y notifica al colectivo destinatario (in-app + mail, mismo mecanismo que los avisos de bandeja).
- El vecino no sube documentos sueltos fuera de esto ni de un pedido. *(Decisión de Claude: evita ruido en el expediente.)*

### 5.6 Pedido al vecino
- Tabla nueva `tramite_pedido_iniciador`: `id_tramite_pedido`, `id_tramite`, `texto` (lo que se pide), `pide_archivo` (bool), `estado` ∈ `abierto|respondido|cancelado`, `id_agente_pide`, `fecha_pedido`, `respuesta_texto`, `fecha_respuesta`, `motivo_cancelacion`, campos §10. **Un solo pedido abierto por trámite** (único parcial). La respuesta y sus archivos quedan para siempre (los archivos como `tramite_documento` con `id_ciudadano_subio`, sin documento requerido, vinculados al pedido).
- **Pedir** (backoffice): `POST /tramites/{ref}/pedidos` `{texto, pide_archivo}`. Lo puede hacer quien puede operar el trámite (`agente_puede_operar`), nunca el Consultor. Solo si el iniciador es ciudadano, el trámite no está archivado ni en estado final y no hay otro pedido abierto. Movimiento nuevo `pedido_iniciador`. Post-commit: aviso en la bandeja de la PWA, push y mail al vecino, con link `/tramites/{id}`.
- **Cancelar** (backoffice): `POST /tramites/{ref}/pedidos/{id}/cancelar` `{motivo}`; mismos permisos. Movimiento `pedido_cancelado`. Aviso al vecino.
- **Responder** (vecino): `POST /publico/tramites/{id}/pedidos/{id_pedido}/responder` multipart `{texto, archivos}`. Texto obligatorio (mín. 5 caracteres); si `pide_archivo`, al menos un archivo. Movimiento `respuesta_iniciador`. Post-commit: notificación in-app + mail al tomador si lo hay y al colectivo destinatario.
- El detalle del backoffice (`DetalleTramite`) muestra el botón «Pedir al vecino» (iniciador ciudadano) y un panel con el pedido abierto y los anteriores con sus respuestas. La bandeja y «Mi bandeja» muestran un chip «Esperando al vecino» cuando hay pedido abierto, y otro «Respondió el vecino» mientras la respuesta no fue vista. *(Decisión de Claude: «vista» = el agente abrió el detalle después de la respuesta; el builder elige cómo guardarlo.)*
- El pedido **no cambia el estado** ni frena las transiciones: el agente puede avanzar aunque el vecino no haya contestado.

### 5.7 Desistimiento con pedido abierto
**Decisión de César (2026-11-21): si el vecino no contesta, al cabo del plazo el trámite queda desistido.**
- El pedido abierto tiene su **propio reloj**, independiente del de los estados con `espera_iniciador`: mismos escalones y claves de Configuración → Sistema que el timer existente (aviso 1 → aviso 2 → último aviso → desistido), contados desde `fecha_pedido`, con su propio nivel de aviso guardado en el pedido (no en `tramite.desist_aviso_nivel`).
- Responder o cancelar el pedido frena su reloj. **Un cambio de estado del trámite no lo reinicia.**
- Si los dos relojes corren a la vez, desiste el primero que vence; los avisos de cada uno salen por separado y dicen a qué se refieren (el pedido, con su texto).
- Al desistir por pedido: `resultado='desistido'`, `archivado_motivo='desistimiento'`, el pedido pasa a `cancelado` con motivo «desistimiento», y aviso + mail al vecino como hoy.
- Los estados con `espera_iniciador` siguen funcionando como hoy.

### 5.8 Avisos al vecino
- Tipo de aviso nuevo `tramite_pedido` en el CHECK de `ciudadano_aviso` (pedido nuevo y cancelado).
- Los avisos de trámites (los nuevos y los que ya existen, `tramite_estado` y `tramite_pendiente`) pasan a llevar url `/tramites/{id}` en vez de `/alertas`, igual que el push.
- Mails con los helpers de `app/core/urls.py` (link al portal del municipio del vecino).

### 5.9 PWA (`zaris-vecinos`)
- Inicio: tarjeta «Trámites» con vigentes y un indicador si hay pedidos abiertos; oculta si el municipio no tiene el módulo `tramites` (`modulos_habilitados`).
- `/tramites`: lista. `/tramites/nuevo`: elegir tipo → formulario del tipo → documentos → revisar y confirmar → pantalla final con el número. `/tramites/:id`: detalle con estado, pedido abierto destacado arriba con «Responder», documentos del paso, sus documentos e historial.
- Formulario dinámico para los tipos de dato `texto`, `texto_largo`, `numero`, `decimal`, `moneda`, `fecha`, `booleano`, `seleccion`, `seleccion_multiple`, `direccion` (los de los tipos ofrecidos). Validación en vivo, con los mismos criterios que el backend.
- Mismo estilo y componentes que reclamos (`NuevoReclamoPage`, `ReclamoDetallePage`).

### 5.10 Identidad validada en el municipio (decisión de César, 2026-11-21: por tipo)
Hoy `ciudadanos.estado_validacion='verificado'` mezcla «lo cargó un agente» con «confirmó su correo»: no dice que alguien haya visto el documento de la persona. Se agrega un acto aparte:
- **Validar la identidad**: un agente (nivel ≤ 3, con agente vinculado), con el vecino y su documento delante, toca «Validar identidad» en la ficha del ciudadano. Tabla nueva `ciudadano_identidad_validacion` (append-only): `id_ciudadano`, `id_agente`, `fecha`, `documento_presentado` (texto corto, p. ej. «DNI»), `observacion`, `activo`, `motivo_revocacion`, `id_agente_revoca`, `fecha_revocacion`, §10. La identidad está validada si hay una fila activa. Revocar (nivel ≤ 2) la desactiva con motivo. *(Decisiones de Claude: tabla con historia, no columnas en `ciudadanos`; quién valida y quién revoca.)* `estado_validacion` no se toca.
- **Por tipo**: `tipo_tramite.exige_identidad_validada BOOLEAN NOT NULL DEFAULT FALSE`, casilla «Exige identidad validada en el municipio» en el configurador. La migración no la prende en ningún tipo: lo decide la gestión.
- **Portal**: un tipo que la exige se lista igual, con `puede_iniciar=false` y el texto «Para iniciar este trámite tenés que validar tu identidad en el municipio. Acercate con tu documento.»; el alta responde 422 con ese texto.
- **Backoffice**: el alta de un tipo que la exige, para un vecino sin identidad validada, también responde 422 («Validá la identidad del vecino en su ficha antes de iniciar este trámite»). *(Decisión de Claude: la regla es del tipo, no del canal.)*
- La ficha del ciudadano (`GET /buc/ciudadanos/{id}` y `/cuentas`) y `GET /publico/perfil` exponen `identidad_validada: {fecha, agente} | null`.
- Fuera de alcance: documentos que deban presentarse en original en el municipio (se puede resolver más adelante con una casilla en el documento requerido).

## 6. Fases propuestas
1. **Backend**: migración (columnas, tabla, CHECKs, clasificación, barrera), router público, pedidos en el backoffice, ajustes a timer/avisos/consumidores, contrato y smokes (con y sin `DB_BARRERA`). Deploy y verificación en prod.
2. **Backoffice**: casillas en el configurador («Se ofrece al vecino», «Exige identidad validada»), «Validar identidad» en la ficha del ciudadano, botón y panel de pedidos, chips en las bandejas, «Iniciado por» con ciudadano.
3. **PWA**: tarjeta, lista, alta, detalle y respuesta. Verificación navegando en prod con el vecino de prueba.

## 7. Queda para el builder
Nombres finales de columnas, endpoints y componentes; cómo extraer el servicio común de creación; cómo guardar «respuesta vista»; diseño visual de las pantallas dentro del estilo existente; orden interno de tareas en cada fase; cuántos smokes y qué casos, cubriendo como mínimo: tipo no ofrecido (404), documento obligatorio faltante (422 sin crear nada), trámite ajeno (404), respuesta sin archivo cuando se pidió (422), pedido sobre iniciador no ciudadano (422), y las dos variantes de la barrera.
