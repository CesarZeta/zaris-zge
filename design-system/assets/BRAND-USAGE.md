# ZARIS — Brand Mark Usage

Guía de uso del isotipo ZARIS y sus variantes. Pareada con los archivos en
`assets/zaris-mark*.svg` y `assets/zaris-favicon.svg`.

---

## Variantes disponibles

| Archivo | Descripción | Cuándo usar |
|---|---|---|
| `zaris-mark.svg` | Blanco sobre fondo negro (`#000`) | App icon, splash, login screen, momentos de marca formal |
| `zaris-mark-inverse.svg` | Ink (`#26251e`) sobre fondo cream (`#f2f1ed`) | Sobre superficies cream del DS, papelería, documentos |
| `zaris-mark-white.svg` | Solo trazos blancos, sin fondo | Overlays sobre imágenes oscuras o fondos negros propios |
| `zaris-mark-flat.svg` | `stroke="currentColor"`, sin fondo | **Default en producto.** Hereda color del contexto |
| `zaris-favicon.svg` | 32×32, fondo negro con `rx=80`, trazo 44px | Favicon del navegador |
| `zaris-social-share.svg` | 1200×630, mark + wordmark + tagline | Open Graph, Twitter card |

---

## Recomendaciones

### Default en la app
Usá **`zaris-mark-flat.svg`** con CSS `color: #26251e` o `color: #f2f1ed` según
el fondo. Una sola fuente, máxima flexibilidad — el mark hereda el color de
texto del contenedor.

```html
<span style="color: var(--fg-1);">
  <img src="/assets/zaris-mark-flat.svg" alt="ZARIS" width="32" height="32">
</span>
```

### Marca formal
Reservá **`zaris-mark.svg`** (fondo negro) para momentos de marca de alto
impacto: app icon nativo, splash screen, pantalla de login, hero de marketing.
No lo uses en sidebar o nav — ahí va el `flat`.

### Favicon
Servilo como SVG en navegadores modernos:

```html
<link rel="icon" type="image/svg+xml" href="/zaris-favicon.svg">
<link rel="apple-touch-icon" href="/zaris-apple-touch-icon.png">  <!-- 180×180 -->
```

Si necesitás PNG fallback (16/32/180px), generalos a partir del SVG.

### Social share (Open Graph)
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
- **Color custom:** permitido solo con la variante `flat`, y solo dentro de
  la paleta del DS (`--fg-1`, `--zaris-cream`, `--zaris-orange` en momentos
  excepcionales).
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
- Wordmark en Space Grotesk, weight 500, tracking -1px (proporcional al tamaño).
- Alineación vertical: centro óptico del wordmark con centro del mark.
