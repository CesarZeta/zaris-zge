---
name: feedback-browser-mcp-que-si-funciona
description: "Patrones de interaccion browser-MCP que SI funcionan en apps React, complementando feedback_browser_mcp_react_setup. La regla no es \"todo lo sintetico falla\" sino \"los setters sinteticos fallan en inputs controlados, los eventos DOM nativos sobre widgets con event handling propio funcionan\"."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 13d5bfd9-1a3a-4142-9bd5-f30a7038a899
---

Complemento de [[feedback_browser_mcp_react_setup]]. Esa memoria dice "setters sinteticos no disparan re-render de React" — verdadero para `input.value = ...; dispatchEvent('input')` en inputs controlados. Pero hay tres categorias de interaccion que SI funcionan via browser-MCP y se confirmaron en sesion 2026-05-12 (B4 + B5 Reclamos).

**Why:** evita gastar tiempo asumiendo que toda interaccion sintetica va a fallar. Permite smoke testing real (incluido upload de archivos end-to-end) sin necesidad de Playwright ni mouse fisico.

**How to apply:** antes de descartar un test browser-MCP porque "es React y sintetico no funciona", chequear si el componente cae en alguno de estos casos. Si si, adelante.

## Patrones que SI funcionan

### 1. Widgets con event handling propio (Leaflet, canvas, video, custom div listeners)

Si el componente engancha el handler con `element.addEventListener` o una API propia (ej. `leafletMap.on('click', cb)`), NO con `onClick={...}` controlado de React, el evento sintetico se procesa normalmente y dispara el callback. Si ese callback llama `setState`, React responde.

Caso confirmado: `MapaPicker` con Leaflet 1.9. `dispatchEvent(new MouseEvent('click', ...))` sobre `.leaflet-container` ejecuta el handler de Leaflet (`map.on('click', ...)`), que llama `onChange()` (prop) que en el padre hace `setForm({...})`. State React se actualiza, el hint "Coordenadas: ..." aparece.

### 2. `<input type="file">` via `DataTransfer` + `dispatchEvent('change')`

```js
const file = new File([blob], 'test.png', { type: 'image/png' });
const dt = new DataTransfer();
dt.items.add(file);
input.files = dt.files;
input.dispatchEvent(new Event('change', { bubbles: true }));
```

El handler `onChange={(e) => pickFiles(e.target.files)}` lee `e.target.files` del evento DOM, NO del state React. Funciona porque `input.files` es una propiedad nativa que el listener React lee directo. Setear el state derivado (`setItems`) ocurre dentro del callback como en cualquier flujo.

Caso confirmado: upload E2E Reclamos B5. Cree un PNG 1x1 programatico, lo dispare al input, aparecio en la lista de "pendientes", clickee "Subir N adjuntos" (button.click), todo el flujo POST upload-url => PUT Supabase => POST confirm => GET adjuntos => render galeria funciono.

### 2b. Forms VANILLA: `form.requestSubmit()` sobre el form CORRECTO por id

En `frontend/login.html` (y cualquier form vanilla con `addEventListener('submit')`), clickear el botón via eval puede disparar el **submit nativo** (GET que recarga la página y pierde los valores) si el eval corre entre la carga del DOM y el bind del handler, o si agarrás el form equivocado. Receta confiable (verif. 2026-06-12): setear `input.value` directo (vanilla no es controlado) y llamar `document.getElementById('login-form').requestSubmit()` — ojo que la página tiene DOS forms (`#login-form` + `#cambio-form` oculto), un `querySelector('form')` ciego puede fallar. Si tras el submit la URL no cambió y no hay error visible, el handler no corrió: re-ejecutar sobre el form por id. La navegación post-login corta el eval con "Inspected target navigated or closed" — eso ES el éxito.

### 3. `button.click()` cuando el handler no depende de state controlado

```js
const btn = document.querySelector('button.foo');
btn.click();
```

Esto siempre funciona si el handler hace algo derivable del DOM o del closure (no del state de un input controlado). Util para disparar mutations, cerrar modales, navegar.

Caso confirmado: "Quitar pin" (`onClick={() => setForm({...lat: null})}`), boton "Subir N adjuntos", boton × de borrado de adjunto.

## Lo que sigue sin funcionar (re-confirmacion)

- **`element.requestFullscreen()` tras un click sintetico** (verificado 2026-06-11, Maximizar tablero Emergencias): el navegador exige *user activation* real y `button.click()` via eval NO la tiene → la promesa rechaza en silencio. Verificable por browser-MCP: la plomeria (`document.fullscreenEnabled === true` adentro del iframe, atributo `allowfullscreen` en el iframe del shell, fallback overlay y boton salir). El enganche visual final SOLO lo prueba un click humano — decirlo explicito al cerrar la verificacion, no declararlo verificado.
- `input.value = 'foo'; input.dispatchEvent(new Event('input'))` sobre un `<input value={state} onChange={...}>` controlado. React no se entera del cambio porque el setter de value() de HTMLInputElement.prototype esta interceptado.
- Selects controlados, textareas controlados — mismo problema.
- Workaround para inputs: usar el descriptor nativo (`Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, 'foo')`) y dispatch. Pero es fragil y caso por caso; sigue siendo mas confiable hacer el smoke por API (PowerShell + curl) y dejar el browser-MCP para verificar render.

## PELIGRO: botones repetidos — scopear SIEMPRE al contenedor

Cazado 2026-06-11 (casi cancelo un turno de demo): en una tabla donde CADA fila tiene un botón "Cancelar" (y el modal abierto tiene otro "Cancelar"), un `[...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Cancelar')` agarra el PRIMERO del documento — que puede ser la acción destructiva de una fila, no el dismiss del modal. El click equivocado abrió el confirm "Cancelar turno" de una fila.

**Regla:** todo querySelector de botón por texto se scopea al contenedor correcto PRIMERO (la fila `tr` ya localizada, o el modal: `doc.querySelector('.modal-overlay')`/el div que contiene el título), y recién ahí se busca el botón. Si el texto del botón es ambiguo ("Cancelar" dismiss vs "Cancelar turno" destructivo), matchear EXACTO y verificar el resultado con un screenshot/eval antes de seguir. Tras un click dudoso, chequear contadores/DB antes de asumir que no pasó nada.

## Criterio operativo

Antes de testear una interaccion via browser-MCP:

1. Si el componente es `<input>`/`<select>`/`<textarea>` controlado => smoke por API. Browser-MCP solo para verificar render.
2. Si es boton no controlado => `button.click()` funciona.
3. Si es un widget custom (mapa, canvas, drag&drop area, dropzone) => probar el evento DOM nativo, suele funcionar.
4. Si es file input => `DataTransfer` + change event, funciona.

Para casos 2-4, podes hacer smoke E2E real en una sola sesion. Para caso 1, no insistas — perdes tiempo.
