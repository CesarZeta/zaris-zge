# ZARIS — Brand Mark Usage

Guía de uso del isotipo ZARIS. Pareada con los archivos en
`assets/zaris-mark-flat.svg`, `assets/zaris-favicon.svg` y
`assets/zaris-social-share.svg`.

---

## Variantes disponibles

| Archivo | Descripción | Cuándo usar |
|---|---|---|
| `zaris-mark-flat.svg` | `stroke="currentColor"`, sin fondo | **Default en producto.** Hereda color del contexto. Usar para login, splash, sidebar, topbar, autoservicio. |
| `zaris-favicon.svg` | 32×32, fondo negro con `rx=80`, trazo 44px | Favicon del navegador |
| `zaris-social-share.svg` | 1200×630, mark + wordmark + tagline | Open Graph, Twitter card |

> **Decisión 2026-05-12:** se removieron las variantes `zaris-mark.svg`
> (fondo negro), `zaris-mark-white.svg` (solo blanco), `zaris-mark-inverse.svg`
> (sobre cream) y `zaris-logo.svg` (wordmark suelto). Estaban definidas pero
> ningún archivo del repo las referenciaba. Cualquier variante de color se
> resuelve componiendo `zaris-mark-flat.svg` (currentColor) con un wrapper que
> setee `color:` y/o `background:` según el caso. Una sola fuente, sin
> versiones que queden desincronizadas.

---

## Default en la app

Usá **`zaris-mark-flat.svg`** con CSS `color` para teñirlo.

### En HTML (vanilla)

`<img>` no respeta `currentColor` (el SVG queda sandboxed). Para que el color
herede del contenedor hay dos opciones:

```html
<!-- Opción A: inline (mejor para herencia de color, peor para cacheo) -->
<span style="color: var(--zaris-orange); display: inline-flex;">
  <!-- copiar contenido de zaris-mark-flat.svg aca, o usar <svg><use href=...> -->
</span>

<!-- Opción B: <img> sin tinte (el SVG queda con su currentColor base) -->
<img src="/design-system/assets/zaris-mark-flat.svg" alt="ZARIS" width="32" height="32">
```

### En React / TS (con Vite)

```ts
// Importar como texto crudo e inyectar inline (hereda color, single source).
import markSvg from '../../../design-system/assets/zaris-mark-flat.svg?raw'

<span style={{ color: 'var(--zaris-orange)' }} dangerouslySetInnerHTML={{ __html: markSvg }} />
```

Implementado en `web-app/src/autoservicio/shared.tsx`.

---

## Favicon

```html
<link rel="icon" type="image/svg+xml" href="/zaris-favicon.svg">
<link rel="apple-touch-icon" href="/zaris-apple-touch-icon.png">  <!-- 180×180, exportar a futuro -->
```

Si necesitás PNG fallback (16/32/180px), generalos a partir del SVG.

---

## Social share (Open Graph)

```html
<meta property="og:image" content="https://zaris.app/zaris-social-share.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
```

Twitter y Facebook prefieren PNG sobre SVG para previews — exportá
`zaris-social-share.svg` a PNG 1200×630 antes de subirlo.

---

## Reglas de uso

- **Padding mínimo:** 1× ancho del trazo principal (≈34px en viewBox 500) en
  todos los lados. No incrustes el mark contra el borde de su contenedor.
- **Tamaño mínimo:** 16px de alto. Por debajo, los terminales redondeados se
  pierden y la geometría se ve sucia.
- **Color custom:** permitido dentro de la paleta del DS (`--fg-1`,
  `--zaris-cream`, `--zaris-orange` en momentos excepcionales).
- **No deformar.** El SVG es cuadrado (500×500). Mantené aspect-ratio 1:1.
- **No agregar efectos.** Sin sombras, sin gradientes, sin outlines extra,
  sin animaciones del mark en sí (sí podés animar su entrada/salida).
- **No combinar con otros marks.** El mark va solo o en lockup con el wordmark
  "ZARIS" — nunca con logos de terceros pegados.

---

## Lockup

Cuando va junto al wordmark "ZARIS":

- Mark a la izquierda, wordmark a la derecha.
- Gap entre mark y wordmark: **0.33× ancho del mark** (ej: mark 36px → gap 12px).
- Wordmark en Space Grotesk, weight 500-600, tracking 0.04em.
- Alineación vertical: centro óptico del wordmark con centro del mark.
