# Trámites del vecino — Fase 3 (app del vecino) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** que el vecino, desde la app (`vecinos.zaris.com.ar`), inicie un trámite con sus documentos, vea los suyos, suba lo que le pide cada paso y responda los pedidos del municipio; y que los avisos de trámites lo lleven directo al trámite.

**Architecture:** casi todo en el repo `zaris-vecinos` (React 19 + Vite, sin react-query: `fetch` con `apiGet`/`apiPostForm` de `src/lib/api.ts`), con el patrón de páginas de reclamos (`NuevoReclamoPage`, `ReclamoDetallePage`, `MisReclamosPage`, `portal.module.css`). En `zaris-zge` hay dos cambios chicos de backend: exponer la validación de cada campo (antes de la PWA) y apuntar los avisos a `/tramites/{id}` (después de publicada la PWA, para que ningún aviso lleve a una ruta que todavía no existe).

**Tech Stack:** React 19, react-router-dom 7, TypeScript, Leaflet (`MapaPicker`), FastAPI (los dos cambios de backend).

**Spec:** [`docs/superpowers/specs/2026-11-21-tramites-vecino-design.md`](../specs/2026-11-21-tramites-vecino-design.md) §5.3-§5.5, §5.8, §5.9 y §6 fase 3. Contrato: [`docs/contrato_api_publica.md`](../../contrato_api_publica.md) §12. Leer antes la skill `modulo-app-vecinos` y `zaris-vecinos/ESTADO.md`.

## Global Constraints

- Contrato §12 vigente: `GET /api/v1/publico/tramites/tipos`, `GET /tipos/{id}`, `POST ""` (multipart: `id_tipo_tramite`, `datos` JSON, `documentos` JSON lista de ids uno por archivo **en el mismo orden** que `archivos`), `GET ""`, `GET /{id}`, `GET /{id}/documentos/{id_doc}/contenido`, `POST /{id}/documentos`, `POST /{id}/pedidos/{id_pedido}/responder` (`texto` 5-4000, `archivos`). Códigos a manejar: 401 (limpiar sesión → `/login`, como `ReclamoDetallePage`), 404, 409, 410, 411, 413, 422 (mostrar el `detail` del backend tal cual).
- Límites en el cliente, iguales al backend: tope total de un envío **25 MB**; por archivo `tamano_max_mb` del documento o **10 MB** si viene `null`; extensiones = `formatos_permitidos` del documento, o `pdf, jpg, jpeg, png, doc, docx, xls, xlsx` si viene vacío (y siempre esas para los archivos de una respuesta a un pedido); hasta `cantidad_max_archivos − subidos` por documento; hasta 20 archivos por envío.
- Tipos de campo del formulario: `texto`, `texto_largo`, `numero`, `decimal`, `moneda`, `fecha`, `booleano`, `seleccion`, `seleccion_multiple`, `direccion`. Valores que se mandan: `numero`/`moneda` entero, `decimal` número, `fecha` `YYYY-MM-DD`, `booleano` `true/false`, `seleccion` el `valor` de la opción, `seleccion_multiple` lista de `valor`, `direccion` `{texto, lat, lon}` (lat/lon juntos o ninguno). Opciones: lista de `{valor, etiqueta}` (mig 137). Un campo vacío y no obligatorio no se manda.
- Módulo: todo lo de trámites (tarjeta, rutas, entrada en Alertas) solo si `useModuloHabilitado()('tramites')`.
- Textos fijos: tarjeta «Mis trámites» / «Iniciá trámites y seguí su estado» / «Ver mis trámites» / «Nuevo trámite»; indicador «Te piden algo en {n} trámite(s)»; tipo que exige identidad: el `motivo_no_puede` del backend; pantalla final «Tu trámite quedó iniciado» + número + «Te avisamos por la app y por correo cada vez que avance.».
- El vecino nunca ve nada interno: la PWA muestra solo lo que devuelve el endpoint público, sin inventar estados ni nombres.
- Backend: los dos cambios se aplican en local, smoke en verde con `DB_BARRERA=true` y `false`, y se verifica prod con `/api/health` (`commit`) y `/openapi.json` (CLAUDE.md §9). Gate PWA: `pnpm typecheck` y `pnpm build` en `zaris-vecinos`.
- Verificación: navegando, en local (`pnpm dev` en 5174 contra uvicorn local) y después en prod con el vecino de prueba (credenciales en `credenciales-testing/`). Ojo con el service worker que sirve el build viejo (memoria `feedback_pwa_service_worker_sirve_build_viejo`).

## Review Focus

1. **El vecino adjunta un archivo de 12 MB, o cuatro de 8 MB** (fotos del celular): sin chequeo previo el envío falla al final con 413 y pierde todo lo cargado. Esperado: aviso en el documento antes de enviar y el formulario intacto si igual falla. → Task 3.
2. **El backend rechaza el alta con 422** (campo inválido, documento faltante, identidad sin validar): el vecino tiene que ver el texto y seguir donde estaba, sin volver a cargar todo. → Task 3.
3. **Doble toque en «Iniciar trámite» o «Responder»** con mala señal: dos trámites o un 409 confuso. Esperado: botón deshabilitado mientras viaja; el 409 de la respuesta dice «Este pedido ya fue respondido o cancelado» y recarga el detalle. → Task 3 y Task 4.
4. **Trámite con un estado `oculto_para_iniciador`, archivado o desistido**: el detalle no ofrece subir documentos ni responder (y si el backend da 409, se recarga sin romper). → Task 4.
5. **Aviso viejo con url `/alertas` y aviso nuevo con `/tramites/{id}` de un trámite que el vecino ya no ve** (404): la app muestra «No encontramos este trámite» con vuelta a la lista, no la página 404 del sitio. → Task 4 y Task 6.

---

### Task 1: Backend — la validación de cada campo para el portal

**Files (repo `zaris-zge`):**
- Modify: `backend/app/schemas/publico_tramites.py` (`CampoPublicoOut.validacion: Optional[dict] = None`)
- Modify: `backend/app/api/routes/publico_tramites.py` (el SELECT y el armado de `campos` en `GET /tipos/{id}` incluyen `validacion_jsonb`)
- Test: `backend/smoke_tramites_vecino.py` (smoke de la fase 1)

**Interfaces:**
- Produces: `campos[].validacion`: `{min?, max?, regex?}` o `null`, con el significado de `_validar_escalar` (`services/tramites/creacion.py`): largo para texto/dirección, valor para numero/moneda.

- [ ] **Step 1:** test `test_tipo_expone_validacion`: poner `validacion_jsonb = {"min": 10}` a un campo de texto de un tipo ofrecido en local → `GET /publico/tramites/tipos/{id}` trae `validacion == {"min": 10}`; un campo sin validación trae `null`.
- [ ] **Step 2:** correr → falla.
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** el smoke completo pasa con `DB_BARRERA=true` y `false`.
- [ ] **Step 5:** contrato §12 (fila de `/tipos/{id}`: sumar `validacion`); commit `feat(tramites): el portal recibe la validacion de cada campo`; push; verificar en prod `/api/health` (`commit`) y `components.schemas.CampoPublicoOut.properties.validacion` en `/openapi.json`.

### Task 2: PWA — cliente de trámites y tarjeta del inicio

**Files (repo `zaris-vecinos`):**
- Create: `src/lib/tramites.ts`
- Modify: `src/lib/portal.ts` (`MiResumen.tramites?: { vigentes: number; total: number; pedidos_abiertos: number }`, opcional por backends viejos)
- Modify: `src/pages/HomePage.tsx` (tarjeta `key: 'tramites'`)

**Interfaces:**
- Produces (`src/lib/tramites.ts`), tipos espejo de `backend/app/schemas/publico_tramites.py`: `TipoOfrecido`, `CampoPublico` (con `validacion`), `DocumentoAlta`, `TipoOfrecidoDetalle`, `MiTramite`, `MiTramiteDetalle`, `DocumentoPaso`, `PedidoAbierto`, `HistorialItem`; funciones:
  - `listarTiposOfrecidos(signal?) : Promise<TipoOfrecido[]>`
  - `getTipoOfrecido(id, signal?) : Promise<TipoOfrecidoDetalle>`
  - `iniciarTramite(idTipo: number, datos: Record<string, unknown>, archivos: ArchivoDoc[]) : Promise<{id_tramite: number; numero_expediente: string}>` donde `ArchivoDoc = { idDocumento: number; file: File }`; arma el FormData con `documentos` = JSON de los `idDocumento` en el orden de `archivos`.
  - `getMisTramites(signal?)`, `getTramite(id, signal?)`
  - `subirDocumentosPaso(idTramite, archivos: ArchivoDoc[]) : Promise<{subidos: number}>`
  - `responderPedido(idTramite, idPedido, texto: string, archivos: File[]) : Promise<{respondido: boolean}>`
  - `descargarDocumento(idTramite, idDoc) : Promise<Blob>` (fetch con el token; 410 → `ApiError`)
  - `validarArchivo(file: File, doc: DocumentoAlta | null) : string | null` (mensaje en castellano o `null`, con las reglas de Global Constraints) y `const TOPE_ENVIO_BYTES = 25 * 1024 * 1024`.

- [ ] **Step 1:** `src/lib/tramites.ts`.
- [ ] **Step 2:** tarjeta en el inicio, después de «Mis reclamos», con los textos fijos; vigentes/total de `resumen.tramites`; si `pedidos_abiertos > 0`, línea destacada «Te piden algo en {n} trámite(s)» que lleva a `/tramites`. Sin `resumen.tramites` (backend viejo), la tarjeta sin cantidades.
- [ ] **Step 3:** `pnpm typecheck`.
- [ ] **Step 4:** Commit `feat(tramites): cliente de tramites y tarjeta en el inicio`.

### Task 3: PWA — iniciar un trámite

**Files:**
- Create: `src/pages/NuevoTramitePage.tsx`, `src/components/CampoTramite.tsx`, `src/components/SelectorArchivos.tsx`
- Modify: `src/App.tsx` (rutas protegidas `/tramites/nuevo` antes de `/tramites/:id`), `src/pages/portal.module.css` si hace falta

**Interfaces:**
- Consumes: Task 2 (`listarTiposOfrecidos`, `getTipoOfrecido`, `iniciarTramite`, `validarArchivo`, `TOPE_ENVIO_BYTES`), `MapaPicker` y `buscarGeo` de `src/lib/reclamos.ts` (mismo bloque buscador + mapa + «Quitar pin» que `NuevoReclamoPage`).
- Produces: `CampoTramite({campo, valor, onChange, error})` y `validarCampo(campo: CampoPublico, valor: unknown): string | null` (exportada desde `CampoTramite.tsx`); `SelectorArchivos({doc, archivos, onChange, maxRestantes})` que muestra los errores de `validarArchivo` por archivo. Los reusa la Task 4.

- [ ] **Step 1:** `validarCampo` con las reglas de Global Constraints + `obligatorio` + `validacion` (min/max/regex, con los mismos criterios que `_validar_escalar`).
- [ ] **Step 2:** `CampoTramite` para los diez tipos (texto `Input`, texto_largo `textarea`, numero/moneda/decimal `inputMode` numérico, fecha `type="date"`, booleano casilla, seleccion `select`, seleccion_multiple casillas, direccion buscador + `MapaPicker`); `ayuda` como hint; error en vivo después del primer blur.
- [ ] **Step 3:** `NuevoTramitePage` en cuatro pasos en la misma página, sin perder lo cargado al ir y volver: (1) elegir tipo — lista con nombre y descripción; los de `puede_iniciar=false` atenuados con su `motivo_no_puede` y sin poder elegirlos; (2) formulario; (3) documentos — uno por `DocumentoAlta` con `SelectorArchivos`, obligatorios marcados, suma total visible contra 25 MB (Review Focus 1); (4) revisar (etiqueta: valor de cada campo y archivos por documento) y «Iniciar trámite». Siguiente deshabilitado mientras haya errores del paso.
- [ ] **Step 4:** envío (Review Focus 2 y 3): botón deshabilitado y «Enviando…» mientras viaja; 201 → pantalla final con el número, «Ver mi trámite» (`/tramites/{id}`) y «Volver al inicio»; 4xx → banner con el `detail` en el paso 4, todo lo cargado intacto; 401 → limpiar sesión y `/login`.
- [ ] **Step 5:** `pnpm typecheck && pnpm build`.
- [ ] **Step 6: verificar navegando** (local, vecino demo, San Andrés): «Poda de árbol» con dirección por buscador y pin + un PDF → número nuevo, y el trámite aparece en la Bandeja del backoffice de la gestión responsable. Probar: documento obligatorio sin archivo → no avanza; un JPG de 11 MB → error en el documento antes de enviar; tipo marcado en local con «Exige identidad validada» y ficha sin validar → atenuado con el texto del backend; forzar un 422 desde el backend (p. ej. borrar el archivo del FormData con la herramienta de red) → banner y formulario intacto.
- [ ] **Step 7:** Commit `feat(tramites): iniciar un tramite desde la app`.

### Task 4: PWA — mis trámites, detalle, documentos del paso y responder pedidos

**Files:**
- Create: `src/pages/MisTramitesPage.tsx`, `src/pages/TramiteDetallePage.tsx`, `src/components/ResponderPedido.tsx`
- Modify: `src/App.tsx` (`/tramites` y `/tramites/:id`)

**Interfaces:**
- Consumes: Task 2 y Task 3 (`SelectorArchivos`, `validarArchivo`), `EstadoBadge` (con `color` del backend), `fechaCorta`/`fechaHora`.

- [ ] **Step 1:** `MisTramitesPage`: lista (número, tipo, estado con su color, resultado si no es `pendiente`, fecha); chip «Te piden algo» si `tiene_pedido_abierto` y «Falta un documento» si `documentos_pendientes > 0`; vacío: «Todavía no iniciaste trámites.» + «Nuevo trámite».
- [ ] **Step 2:** `TramiteDetallePage` (patrón `ReclamoDetallePage`: 401, 404 «No encontramos este trámite.» con vuelta a `/tramites`, error genérico): arriba, si hay `pedido_abierto`, tarjeta destacada con el texto, la fecha y `ResponderPedido`; después estado/resultado, «Lo que te pide este paso» (`documentos_del_paso` con faltantes, `SelectorArchivos` por documento y «Enviar documentos» → `subirDocumentosPaso`), «Tus datos» (`datos`), «Tus documentos» (descarga; 410 → «El archivo ya no está disponible»), «Historial» (`fecha` + `texto`).
- [ ] **Step 3:** `ResponderPedido`: texto (5-4000, contador), archivos (obligatorio al menos uno si `pide_archivo`), «Responder» deshabilitado mientras viaja (Review Focus 3). 409 → mensaje «Este pedido ya fue respondido o cancelado.» y recarga el detalle; 200 → toast/banner «Enviamos tu respuesta» y recarga.
- [ ] **Step 4:** Review Focus 4: sin `documentos_del_paso` ni `pedido_abierto`, esas secciones no aparecen; un 409 al subir documentos recarga el detalle con el mensaje del backend.
- [ ] **Step 5:** `pnpm typecheck && pnpm build`.
- [ ] **Step 6: verificar navegando** (local): desde el backoffice pedirle algo al vecino con archivo obligatorio → en la app, la tarjeta del inicio dice «Te piden algo en 1 trámite», la lista muestra el chip, el detalle la tarjeta destacada; responder sin archivo → no deja; con archivo → «Enviamos tu respuesta», la tarjeta desaparece y el historial suma la respuesta; el backoffice ve «Respondió el vecino». Responder dos veces rápido (dos pestañas) → la segunda muestra el texto del 409. Un trámite de otro vecino por URL (`/tramites/{id}` ajeno) → «No encontramos este trámite».
- [ ] **Step 7:** Commit `feat(tramites): mis tramites, detalle y respuesta a pedidos en la app`.

### Task 5: Publicar la PWA y probar el circuito real en prod

- [ ] **Step 1: subida real contra prod antes de publicar** (riesgo de 411 del borde de Railway): con el vecino de prueba en prod, desde `pnpm dev` apuntado a prod o con un script, iniciar un trámite real de un tipo de San Andrés con un PDF chico. Esperado: 201 y número. Si da 411/413, frenar y diagnosticar (el `fetch` con `FormData` manda `Content-Length`; ver qué envía el cliente) antes de seguir. Este trámite es la prueba del circuito y **se conserva** (memoria `feedback_smoke_cleanup_prod`); avisarle a César su número.
- [ ] **Step 2:** push de `zaris-vecinos` a `main`; verificar el deploy de Cloudflare Pages (proyecto `zaris-vecinos`) y que `vecinos.zaris.com.ar` sirve el bundle nuevo (forzar la actualización del service worker).
- [ ] **Step 3: verificar navegando en prod** con el vecino de prueba: tarjeta, lista con el trámite del Step 1, detalle; desde el backoffice de prod, un pedido al vecino sobre ese trámite → aparece en la app; responderlo con un archivo → el backoffice ve la respuesta. Todo con datos de prueba conocidos por César.
- [ ] **Step 4:** `zaris-vecinos/ESTADO.md` (pantallas de trámites hechas); commit `docs(estado): tramites desde la app`.

### Task 6: Backend — los avisos de trámites llevan al trámite

**Files (repo `zaris-zge`):**
- Modify: `backend/app/services/tramites/ciclo_vida.py` (`_avisar_vecino`: url `f"/tramites/{id_tramite}"` en el aviso y en el push, en lugar de `URL_PWA_AVISOS`), `backend/app/services/tramites/pedidos.py` si arma la url por su cuenta
- Modify (repo `zaris-vecinos`): `src/lib/avisos.ts` (`'tramite_pedido'` en `AvisoTipo` y en `etiquetaTipo`, misma etiqueta que los otros de trámite)
- Test: `backend/smoke_tramites_vecino.py`

**Precondición:** la Task 5 publicada y verificada (si no, el aviso llevaría a una ruta inexistente).

- [ ] **Step 1:** test `test_aviso_tramite_url`: pedir al vecino → la fila nueva de `ciudadano_aviso` tiene `url_destino == f"/tramites/{id_tramite}"` y el push capturado lleva la misma url; un aviso `tramite_estado` (transición con `notifica_iniciador`) también.
- [ ] **Step 2:** correr → falla.
- [ ] **Step 3:** implementar; `avisos.ts` en la PWA.
- [ ] **Step 4:** smoke verde con `DB_BARRERA=true` y `false`; `pnpm typecheck` en la PWA.
- [ ] **Step 5:** contrato §11/§12 (url `/tramites/{id}`; los avisos viejos quedan con `/alertas`, la PWA ya los maneja); push de los dos repos; verificar prod (`/api/health` `commit`; un pedido de prueba sobre el trámite del Task 5 → en Alertas, tocarlo abre el trámite; el push también). Review Focus 5: un aviso viejo con `/alertas` sigue sin navegar.
- [ ] **Step 6:** ESTADO.md de ambos repos, skills `modulo-tramites` y `modulo-app-vecinos`; commit `feat(tramites): los avisos al vecino abren el tramite`.
