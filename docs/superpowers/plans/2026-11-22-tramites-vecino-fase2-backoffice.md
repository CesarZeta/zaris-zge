# Trámites del vecino — Fase 2 (backoffice) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** que el personal del municipio use desde ZARIS lo que la fase 1 dejó en el backend: marcar qué tipos se ofrecen al vecino, validar su identidad en la ficha, pedirle algo y ver su respuesta, y reconocer en bandejas, historial y documentos lo que hizo el vecino.

**Architecture:** solo frontend del módulo React `web-app/src/modules/tramites/` y `ciudadanos/`, contra endpoints que ya están en prod (fase 1). No hay backend nuevo ni migración. El único cambio fuera de pantallas es sumar los campos que el backend ya devuelve a los tipos TS.

**Tech Stack:** React 19 + TypeScript, react-query, CSS en línea con tokens del DS (patrón vigente del módulo), `web-app/src/lib/api.ts`.

**Spec:** [`docs/superpowers/specs/2026-11-21-tramites-vecino-design.md`](../specs/2026-11-21-tramites-vecino-design.md) §5.1, §5.2, §5.6, §5.10 y §6 fase 2. Plan anterior: [`2026-11-21-tramites-vecino-fase1-backend.md`](2026-11-21-tramites-vecino-fase1-backend.md). Leer antes las skills `modulo-tramites` y `modulo-usuarios`, y CLAUDE.md §3 (niveles), §23 (modales: cerrar al confirmar) y §41 (verificar navegando).

## Global Constraints

- **Sin backend nuevo.** Endpoints que se consumen (en prod desde el 2026-11-22, verificar en `/openapi.json` antes de empezar):
  - `POST /api/v1/tramites/{ref}/pedidos` `{texto (5-2000), pide_archivo}` → `TramiteDetalle`
  - `POST /api/v1/tramites/{ref}/pedidos/{id}/cancelar` `{motivo (5-1000)}` → `TramiteDetalle`
  - `POST /api/v1/tramites/{ref}/pedidos/{id}/visto` → 204
  - `POST /api/v1/buc/ciudadanos/{id}/identidad/validar` `{documento_presentado (2-40), observacion? (≤500)}` → 201 `{identidad_validada}`
  - `POST /api/v1/buc/ciudadanos/{id}/identidad/revocar` `{motivo (≥5)}` → `{identidad_validada: null}`
  - `GET /api/v1/buc/ciudadanos/{id}/cuentas` ya trae `identidad_validada: {fecha, agente_nombre} | null`.
  - `PUT/POST` de tipos admin aceptan `ofrecer_al_vecino` y `exige_identidad_validada`; detalle y lista admin los devuelven.
- Niveles (CLAUDE.md §3, `hasPermission(n)` = nivel ≤ n, incluye al super): validar identidad = `hasPermission(3)`; revocar = `hasPermission(2)`; pedir/cancelar pedido = `hasPermission(4)` (oculto para el Consultor, nivel 5); el backend decide el resto (`agente_puede_operar`) y su 403/422 se muestra en un toast con el `detail`.
- Textos fijos (copiarlos tal cual):
  - Casillas del configurador: «Se ofrece al vecino en el portal» y «Exige identidad validada en el municipio».
  - Chips de bandeja: «Esperando al vecino» y «Respondió el vecino».
  - Botón del detalle: «Pedir al vecino». Panel: «Pedidos al vecino».
  - Ficha: botón «Validar identidad», «Revocar validación»; estado «Identidad validada el {fecha} por {agente}» / «Identidad sin validar en el municipio».
- Modales de mutación: se cierran al confirmar, el resultado llega por toast, y resetean sus campos al abrir (CLAUDE.md §23 y §29).
- Colores solo con tokens del DS; nada de naranja para estado (`--zaris-orange` es marca).
- Gate: `pnpm typecheck` y `pnpm lint` en `web-app/` verdes en cada commit (el hook pre-commit corre el typecheck).
- No hay tests de frontend en el repo (no hay vitest): cada tarea se prueba **navegando** el shell local (`http://localhost:8080` + uvicorn `127.0.0.1:8000` + `pnpm dev`/build) con los pasos y el resultado esperado que dice la tarea. Datos de prueba locales: San Andrés en `zaris_dev`, vecino demo con cuenta (ver `credenciales-testing/`, nunca en el repo).

## Review Focus

1. **Un movimiento o documento del vecino en el historial del backoffice** muestra «null» o se rompe porque `agente_nombre` viene vacío. Esperado: «Iniciado por el vecino {nombre} desde el portal», «Subido por el vecino». → Task 2, paso de verificación con un trámite creado por `POST /publico/tramites`.
2. **Destildar «ciudadano» de los iniciadores con «Se ofrece al vecino» marcado**: el PUT da 422 y el usuario no entiende por qué. Esperado: la casilla se apaga sola y desaparece. → Task 1.
3. **Abrir el detalle marca la respuesta como vista dos veces o en cada refetch** (polling, foco de ventana). Esperado: un solo `POST /visto` por respuesta sin ver, y el chip de la bandeja desaparece. → Task 3.
4. **Consultor (nivel 5) o agente sin operar el trámite** ve «Pedir al vecino». Esperado: el Consultor no lo ve; el otro recibe el 403 del backend en un toast, sin romper la pantalla. → Task 3.
5. **Funcionario sin perfil de agente** toca «Validar identidad»: el backend da 403 «Tu usuario no tiene un perfil de agente municipal…». Esperado: toast con ese texto y la ficha intacta. → Task 5.

---

### Task 1: Casillas del configurador de tipos

**Files:**
- Modify: `web-app/src/modules/tramites/types.ts` (`TipoTramiteAdmin`, `TipoTramiteAdminListItem`: `ofrecer_al_vecino: boolean`, `exige_identidad_validada: boolean`)
- Modify: `web-app/src/modules/tramites/admin/modals/NuevoTipoModal.tsx`, `EditarTipoModal.tsx` (body del POST/PUT)
- Modify: `web-app/src/modules/tramites/admin/pages/ConfigTramites.tsx` (marca «Portal» en la fila de los tipos ofrecidos)

**Interfaces:**
- Produces: los dos campos en los tipos TS (los usa la fase 3 solo vía backend; acá no hay consumidores nuevos).

- [ ] **Step 1:** Agregar los dos `boolean` a los tipos y a los estados de ambos modales (default `false` en el alta, valor del tipo en la edición); mandarlos en el body.
- [ ] **Step 2:** «Se ofrece al vecino en el portal» se renderiza solo si `iniciadores` incluye `'ciudadano'`; al quitar `ciudadano` de los iniciadores, el estado pasa a `false`. «Exige identidad validada en el municipio» se muestra siempre que se muestre la anterior. Debajo de cada una, hint corto: «Aparece en la app del vecino para iniciarlo desde ahí» / «El vecino tiene que haber validado su identidad en una ventanilla».
- [ ] **Step 3:** En la lista, junto al nombre del tipo con `ofrecer_al_vecino`, un `Pill`/badge «Portal».
- [ ] **Step 4:** `pnpm typecheck && pnpm lint` → sin errores.
- [ ] **Step 5: verificar navegando** (local): Trámites → Configuración → «poda-arbol» → Editar: la casilla aparece marcada; destildar «ciudadano» → la casilla desaparece; volver a tildar, desmarcar «Se ofrece…», guardar → toast de éxito, la lista ya no muestra «Portal» y `GET /api/v1/publico/tramites/tipos` con el vecino demo no lo trae. Restaurar la marca al terminar.
- [ ] **Step 6:** Commit `feat(tramites-admin): casillas de oferta al vecino e identidad validada en el configurador`.

### Task 2: El vecino en el historial, los documentos y el iniciador

**Files:**
- Modify: `web-app/src/modules/tramites/types.ts` (`TipoMovimiento` + `'pedido_iniciador' | 'respuesta_iniciador' | 'pedido_cancelado'`; `TramiteMovimiento.agente_nombre: string | null`, `actor_tipo: 'agente' | 'ciudadano' | 'sistema'`, `actor_nombre: string | null`; `TramiteDocumento.actor_tipo`, `actor_nombre`)
- Modify: `web-app/src/modules/tramites/components/Timeline.tsx`, `ListaDocumentos.tsx`
- Modify: `web-app/src/modules/tramites/pages/DetalleTramite.tsx` (meta «Iniciador»)

**Interfaces:**
- Produces: `function nombreActor(m: { actor_tipo; actor_nombre; agente_nombre }): string` en `web-app/src/modules/tramites/lib/actor.ts` → `'el vecino {nombre}'` | `'{agente}'` | `'el sistema'`. Lo usan Timeline, ListaDocumentos y el panel de pedidos (Task 3).
- Produces: `const ETIQUETA_INICIADOR: Record<IniciadorTipo, string> = { ciudadano: 'Vecino', empresa: 'Empresa', area_interna: 'Área interna' }` en el mismo archivo.

- [ ] **Step 1:** `lib/actor.ts` con las dos exportaciones.
- [ ] **Step 2:** Timeline: toda etiqueta que hoy interpola `m.agente_nombre` usa `nombreActor(m)`; `creacion` con `actor_tipo==='ciudadano'` dice «Iniciado por el vecino {nombre} desde el portal». Tres entradas nuevas en `TIPO_CONFIG`: `pedido_iniciador` «Pedido al vecino» (comentario = texto del pedido), `respuesta_iniciador` «Respondió el vecino», `pedido_cancelado` «Pedido al vecino cancelado» (+ «por desistimiento» si `metadata_jsonb.automatico`). La línea del autor bajo cada fila usa `nombreActor`.
- [ ] **Step 3:** ListaDocumentos: «Subido por {nombreActor}».
- [ ] **Step 4:** DetalleTramite: el valor de «Iniciador» usa `ETIQUETA_INICIADOR`.
- [ ] **Step 5:** `pnpm typecheck && pnpm lint`.
- [ ] **Step 6: verificar navegando** (Review Focus 1): iniciar en local un trámite de «poda-arbol» como vecino demo (`POST /api/v1/publico/tramites` multipart con un PDF, por `curl` o script con el token del vecino), abrir su detalle en el backoffice: «Iniciador: Vecino — {nombre}», historial «Iniciado por el vecino {nombre} desde el portal», documento «Subido por el vecino {nombre}». Ningún «null» ni «undefined» en la pantalla (`browser_eval` sobre `document.body.innerText`).
- [ ] **Step 7:** Commit `feat(tramites): el backoffice muestra lo que hizo el vecino en historial y documentos`.

### Task 3: Pedir al vecino y ver su respuesta

**Files:**
- Modify: `web-app/src/modules/tramites/types.ts` (`TramiteDetalle.pedidos: PedidoTramite[]`; `interface PedidoTramite` con los campos de `PedidoOut`: `id_tramite_pedido, texto, pide_archivo, estado: 'abierto'|'respondido'|'cancelado', fecha_pedido, agente_pide, respuesta_texto, fecha_respuesta, respuesta_vista_en, documentos_respuesta: {id_tramite_documento, nombre, nombre_archivo_original, fecha_alta, binario_purgado}[], motivo_cancelacion`)
- Modify: `web-app/src/modules/tramites/lib/api.ts`, `hooks/useTramites.ts`
- Create: `web-app/src/modules/tramites/components/PanelPedidos.tsx`, `ModalPedido.tsx` (pedir y cancelar, dos modos)
- Modify: `web-app/src/modules/tramites/pages/DetalleTramite.tsx`

**Interfaces:**
- Consumes: `nombreActor` (Task 2), `descargarDocumentoBlob(numero, idDoc)` existente.
- Produces: `pedirAlVecino(numero, {texto, pide_archivo})`, `cancelarPedido(numero, id, {motivo})`, `marcarPedidoVisto(numero, id)` en `lib/api.ts`; hooks `usePedirAlVecino(numero)`, `useCancelarPedido(numero)` que invalidan `['tramites','detalle'|'movimientos'|'documentos', numero]` y `['tramites','bandeja']`, `['tramites','mi-bandeja']`.

- [ ] **Step 1:** api + hooks.
- [ ] **Step 2:** `ModalPedido` modo `pedir`: textarea «¿Qué le pedís al vecino?» (5-2000, contador), casilla «Tiene que adjuntar al menos un archivo», texto fijo «Le llega un aviso en la app y un correo. Si no contesta, el trámite queda desistido en el mismo plazo que los demás avisos.». Modo `cancelar`: textarea «Motivo» (5-1000). Confirmar deshabilitado fuera de rango; cerrar al confirmar.
- [ ] **Step 3:** `PanelPedidos` en la columna izquierda, debajo de «Datos del trámite», solo si `iniciador_tipo==='ciudadano'`: el pedido abierto arriba, destacado, con «Cancelar pedido»; después los anteriores (más nuevo primero) con fecha, quién pidió, texto, y respuesta (texto + archivos descargables con «Archivo depurado» si `binario_purgado`) o motivo de cancelación. Sin pedidos: «Todavía no se le pidió nada al vecino.»
- [ ] **Step 4:** Botón «Pedir al vecino» en el header del detalle: visible si `iniciador_tipo==='ciudadano'`, `!fecha_archivado`, `resultado==='pendiente'`, sin pedido abierto y nivel ≠ 5. Error del backend → toast con `detail`.
- [ ] **Step 5:** Visto (Review Focus 3): en `DetalleTramite`, un `useEffect` sobre `data?.pedidos` llama `marcarPedidoVisto` una vez por cada pedido `respondido` con `respuesta_vista_en === null`, recordando los ids ya enviados en un `useRef<Set<number>>`; al terminar invalida las bandejas. Nunca durante el render ni en cada refetch.
- [ ] **Step 6:** `pnpm typecheck && pnpm lint`.
- [ ] **Step 7: verificar navegando** (local, trámite de la Task 2): «Pedir al vecino» con archivo obligatorio → el modal se cierra al confirmar, toast, panel con el pedido abierto, historial «Pedido al vecino»; el botón desaparece. Responder como vecino (`POST /publico/tramites/{id}/pedidos/{id}/responder` con texto + PDF). Recargar el detalle: respuesta con el archivo descargable; en la red del navegador, **un** `POST …/visto`; recargar otra vez → ninguno. Con un usuario Consultor el botón no está. Pedir y luego «Cancelar pedido» → historial «Pedido al vecino cancelado».
- [ ] **Step 8:** Commit `feat(tramites): pedir al vecino desde el detalle y ver su respuesta`.

### Task 4: Chips en las bandejas

**Files:**
- Modify: `web-app/src/modules/tramites/types.ts` (`TramiteBandejaItem.pedido_abierto: boolean`, `respuesta_sin_ver: boolean`; el ítem de mi-bandeja también, si usa otro tipo)
- Create: `web-app/src/modules/tramites/components/ChipVecino.tsx` (`{pedido_abierto, respuesta_sin_ver}` → `null` | chip)
- Modify: `web-app/src/modules/tramites/pages/BandejaTramites.tsx`, `MiBandeja.tsx`

- [ ] **Step 1:** `ChipVecino`: «Respondió el vecino» (token de éxito, gana si los dos son verdaderos) o «Esperando al vecino» (token de advertencia, no naranja). Se muestra en la celda del iniciador, debajo del nombre.
- [ ] **Step 2:** Usarlo en las dos bandejas.
- [ ] **Step 3:** `pnpm typecheck && pnpm lint`.
- [ ] **Step 4: verificar navegando:** con el trámite de la Task 3 — pedido abierto → Bandeja y Mi bandeja, Buscar: «Esperando al vecino»; tras la respuesta del vecino: «Respondió el vecino»; abrir el detalle y volver: sin chip.
- [ ] **Step 5:** Commit `feat(tramites): chips de pedido al vecino en las bandejas`.

### Task 5: Validar la identidad en la ficha del ciudadano

**Files:**
- Modify: `web-app/src/modules/ciudadanos/api/ciudadanosApi.ts` (`validarIdentidad(id, {documento_presentado, observacion?})`, `revocarIdentidad(id, {motivo})`; el tipo de `/cuentas` suma `identidad_validada: {fecha: string; agente_nombre: string | null} | null`)
- Create: `web-app/src/modules/ciudadanos/components/IdentidadPanel.tsx`
- Modify: `web-app/src/modules/ciudadanos/views/FormView.tsx` (renderizarlo junto a `CuentasChips`, solo en consulta/edición)

**Interfaces:**
- Consumes: `useCuentasCiudadano(id)` existente (misma query `['buc','ciudadanos',id,'cuentas']`, que se invalida tras validar o revocar).

- [ ] **Step 1:** api + tipo.
- [ ] **Step 2:** `IdentidadPanel`: el estado (textos de Global Constraints, fecha en `es-AR` dd/mm/aaaa); con `hasPermission(3)` y sin validar, «Validar identidad» abre un modal: «Documento que presentó» (default «DNI», 2-40), «Observación» (opcional, ≤500) y el texto «Validá solo con la persona y su documento delante.»; con `hasPermission(2)` y validada, «Revocar validación» abre un modal con «Motivo» (≥5). Cerrar al confirmar, toast con el resultado o el `detail` del error (Review Focus 5).
- [ ] **Step 3:** `pnpm typecheck && pnpm lint`.
- [ ] **Step 4: verificar navegando:** Ciudadanos → buscar al vecino demo → ficha: «Identidad sin validar en el municipio»; validar con un usuario de nivel 3 con agente → «Identidad validada el {hoy} por {agente}»; con nivel 3 no aparece «Revocar»; con un supervisor, revocar → vuelve a «sin validar». Con un usuario sin agente vinculado → toast del 403 y la ficha sigue igual. Marcar en local «Exige identidad validada» en un tipo y comprobar que `GET /publico/tramites/tipos` cambia `puede_iniciar` según el estado de la ficha.
- [ ] **Step 5:** Commit `feat(ciudadanos): validar la identidad del vecino en su ficha`.

### Task 6: Publicación y verificación en prod

**Files:**
- Modify: `ESTADO.md`, `.claude/skills/modulo-tramites/SKILL.md` (sección de pantallas del vecino en el backoffice), `.claude/skills/modulo-usuarios/SKILL.md` si menciona la ficha

- [ ] **Step 1:** `grep -riE "h[u]sky" .` vacío; `pnpm typecheck`; `python tools/barrido_guards_nivel.py` verde (ningún `nivel === 1` nuevo).
- [ ] **Step 2:** Push a `main`. Verificar el deploy de Cloudflare Pages: `https://zge.zaris.com.ar/version.json` con la versión nueva y el `<script src>` de `https://zge.zaris.com.ar/web-app/dist/` igual al de `https://zaris-zge.pages.dev/web-app/dist/`.
- [ ] **Step 3: verificar navegando en prod** (CLAUDE.md §41: iframe con el bundle nuevo, entrando por el sidebar y las pestañas, no por URL): configurador con las dos casillas en un tipo de San Andrés (abrir y cancelar, sin guardar); ficha del vecino de prueba con el panel de identidad (sin validar nada real salvo que César lo pida); un trámite existente con el panel «Pedidos al vecino» vacío y el botón visible. **No** se crean pedidos ni trámites reales en prod en esta fase: el circuito completo en prod se prueba en la fase 3 con el vecino de prueba.
- [ ] **Step 4:** Actualizar ESTADO.md (fase 2 hecha, sigue la 3) y las skills; commit `docs(tramites): pantallas del backoffice para los tramites del vecino`.
