---
name: shell-react-no-carga-components-css
description: "El shell React (web-app/) importa solo tokens del DS, NO los componentes. Las clases .btn-zaris/.card-zaris/.menu-card-zaris no estilan nada dentro de un módulo React."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 80c889f1-fa69-434e-a345-e0a79357a71f
---

`web-app/src/main.tsx` importa `styles/tokens.css` y `styles/globals.css`, pero **NO importa `design-system/components.css`**. Consecuencia: dentro de un módulo React, las clases del DS no estilan nada — el `<button class="btn-zaris--primary">` queda como un `<button>` pelado.

**Por qué pasa:** historia, no diseño. El shell React arrancó cuando no existían los componentes `*-zaris` del DS, y nunca se enganchó porque por ahora ningún módulo lo necesitó: cada uno usa CSS Modules locales con tokens.

**Cómo aplicar la regla:**

- ✅ Dentro de un módulo React: usar `var(--zaris-orange)`, `var(--fg-1)`, `var(--surface-100)`, `var(--font-display)` directos. **Siempre funcionan**, porque `tokens.css` espeja `colors_and_type.css`.
- ❌ Dentro de un módulo React: NO esperar que `<button className="btn-zaris">` haga algo. Si lo escribís, vas a perder 10 min buscando por qué no aplica.
- ✅ Para una landing con tarjetas estilo `menu-card-zaris`: replicar el CSS localmente en un `*.module.css` (~50 LOC). Ejemplo: `web-app/src/modules/contactos/pages/Overview.module.css`.
- ✅ Antes de copiar visualmente un componente del DS dentro de un módulo React: abrir `design-system/components/<nombre>.css`, copiar el bloque relevante al `.module.css` local, renombrar selectores `.foo-zaris` → `.foo`. 2 min, evita el bug silencioso.

**Cazado:** sesión 2026-05-13 al crear módulo `contactos`. Verifiqué con grep antes de codear (siguiendo [[feedback_grep_DS_antes_de_crear]]), descubrí que `components.css` no llega al shell React, y resolví con CSS Module local en lugar de `menu-card-zaris`. Sin verificación previa habría perdido tiempo debuggeando "por qué la tarjeta no toma estilo".

**Si en el futuro un módulo React necesita la mayoría del DS visual**, evaluar importar `components.css` desde `main.tsx`. Hoy no se hace porque (a) ningún módulo lo necesitó, (b) suma peso al bundle, (c) obliga a cuidar colisiones con CSS Modules locales (`.btn` global vs `.btn` local).

Doc complementaria en CLAUDE.md §13 sección "CSS del DS que llega al shell React".
