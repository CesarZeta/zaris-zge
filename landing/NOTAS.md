# Landing comercial ZARIS — notas de continuidad

> Documento para retomar el trabajo de la landing en otra sesión. Última actualización: 2026-05-18.

## Qué hay hoy

```
landing/
├── zaris.html          # landing comercial completa (~480 LOC, autocontenida)
├── img/
│   ├── zaris-dashboard.png   # 1280x800, mapa + 4 stats
│   ├── zaris-reclamos.png    # 1280x800, bandeja con filtros y totales
│   ├── zaris-agenda.png      # 1280x800, grilla día con 84 agentes
│   ├── zaris-ot.png          # 1280x800, mesa supervisor
│   ├── zaris-tramites.png    # 1280x800, bandeja 20 expedientes
│   └── zaris-contactos.png   # 1280x800, padrón ciudadanos
└── NOTAS.md            # este archivo
```

Las screenshots son **capturas reales** del producto en producción (`https://zge.zaris.com.ar`) con datos del municipio demo (San Andrés, 84 agentes seedeados, 20 trámites, 13 reclamos activos).

## Cómo verla local

```powershell
# desde la raíz del repo
python -m http.server 8080
# abrir http://localhost:8080/landing/zaris.html
```

No requiere backend levantado — la landing es 100% estática.

## Estructura del HTML (orden de secciones)

1. `<header class="topbar">` — marca + nav
2. `<section class="hero">` — eyebrow pill, título con cursiva en italic, lead, CTAs, 4 stats
3. `<section id="pilares">` — 4 cards (Tiempo real, Trazabilidad, Padrón único, Permisos)
4. `<section id="modulos" class="modulos-sec">` — 6 bloques alternados con screenshots:
   - Dashboard (tablero ejecutivo)
   - Reclamos
   - Agenda
   - OT (órdenes de trabajo)
   - Trámites
   - Contactos / BUC
5. `<section class="cita">` — frase institucional en serif italic
6. `<section id="porque">` — 6 razones numeradas
7. `<section id="contacto" class="cta">` — CTA final
8. `<footer>` — copyright

## Design system

La landing **respeta el DS oficial** y NO inventa variables propias:

- Links a `../design-system/fonts/fonts.css`, `colors_and_type.css`, `components.css` (rutas relativas desde `landing/`)
- Usa tokens: `var(--zaris-orange)`, `var(--fg-1/2/3)`, `var(--surface-100/200/300)`, `var(--font-display)`, `var(--font-serif)`, `var(--font-mono)`, `var(--radius-*)`, `var(--space-*)`, `var(--track-*)`, `var(--shadow-card)`
- Componente: solo `.btn-zaris` con modificadores `--accent`, `--primary`, `--outline` (con fallback inline por si `components.css` no carga)
- Las clases de layout (`.hero`, `.pilar`, `.modulo`, etc.) son **locales del HTML**, no del DS. Sin prefijo `z-` (legacy eliminado, ver CLAUDE.md §31).

## Decisiones tomadas

| Decisión | Por qué |
|---|---|
| Tono institucional (intendentes/secretarios) | Pedido del usuario. Lenguaje de eficiencia, transparencia, trazabilidad — evita jerga técnica de stack. |
| Capturas reales del producto en producción | Más auténticas que mockups. Tomadas via `html2canvas` dentro del iframe same-origin (`zge.zaris.com.ar`) y descargadas como PNG. |
| HTML autocontenido en `landing/` (nuevo) | Pedido del usuario. No mezcla con `frontend/` para que no se confunda con un módulo del producto con guard de sesión. |
| Sin emojis | Regla general del proyecto. Iconos SVG inline (Lucide-style, stroke-width 1.5). |
| Mockup de browser alrededor de cada screenshot | Bordeado con gradiente y "● ● ●" decorativo. Ver `.modulo__shot::before` y `::after`. |
| 8 módulos en el contador del hero | Reclamos, OT, Agenda, Turnos, Entradas, Trámites, Contactos (BUC), Maestros/Config. Coincide con sidebar prod. |

## Si querés mejorar

### Capturas más profundas
Hoy hay 1 captura por módulo (vista principal). Faltan vistas internas que mostrarían más valor:

- **Reclamos**: drawer de detalle con timeline + adjuntos + mapa
- **Agenda**: vista semanal con ocupaciones de colores; modal de planificar OT
- **OT**: detalle con drawer de auditoría aprobada/rechazada
- **Trámites**: detalle de expediente con FSM + firma digital + documentos
- **Turnos / Entradas**: ahora no tienen captura propia
- **Dashboard**: vista con más data (hoy se ve algo vacío en zonas)

Receta para capturar más (verificado 2026-05-18):

```js
// En el browser MCP, después de login + navegar al iframe del shell prod:
document.querySelector('iframe').src = 'web-app/dist/index.html#/<modulo>/<vista>'
// esperar carga
const iwin = document.querySelector('iframe').contentWindow
const idoc = document.querySelector('iframe').contentDocument
// si html2canvas no está cargado, cargarlo dentro del iframe
const canvas = await iwin.html2canvas(idoc.body, {
  useCORS: true, scale: 1, width: 1280, height: 800,
  windowWidth: 1280, windowHeight: 800
})
const a = document.createElement('a')
a.href = canvas.toDataURL('image/png')
a.download = 'zaris-<nombre>.png'
document.body.appendChild(a); a.click(); a.remove()
```

Antes de capturar: `browser_download_set` apuntando a `landing/img`. El bridge MCP del browser integrado lo expone.

### Loop interactivo del producto en lugar de PNGs
Podría reemplazar las imágenes por un `<iframe sandbox>` apuntando al bundle prod en modo demo (sin auth, datos de muestra). Requiere:
- Crear ruta pública en backend que devuelva un token "modo demo" de solo lectura
- Configurar el bundle para detectar `?demo=1` y skipear login
- Decisión de UX: iframe vs imágenes (iframe pesa más, requiere conexión, demuestra realidad)

### Versión inglesa
Hoy es 100% español. Si va a clientes fuera de Argentina, duplicar a `landing/zaris.en.html` y agregar selector de idioma en topbar.

### Logo del municipio real
La captura del dashboard muestra "MUNICIPALIDAD DE SAN ANDRÉS" (demo). Si la landing va a una propuesta concreta, capturar contra un seed con el nombre y logo del municipio target.

### SEO + meta sociales
Falta:
- `<meta property="og:image">` con preview (podría ser la captura del dashboard recortada a 1200x630)
- `<meta property="og:title">`, `og:description`, `og:url`
- `<meta name="twitter:card" content="summary_large_image">`
- `<link rel="canonical">`

### Performance
Las 6 PNGs pesan ~1.7MB total. Hoy es aceptable, pero si se publica:
- Convertir a WebP (~70% menos peso, soporte universal)
- `loading="lazy"` en `<img>` de módulos no-hero
- Considerar 2 tamaños con `srcset` (1280w para desktop, 640w para mobile)

### Publicación
Si se publica bajo GH Pages del mismo repo:
- Queda en `https://cesarzeta.github.io/zaris-zge/landing/zaris.html` (o `https://zge.zaris.com.ar/landing/zaris.html`)
- No hay conflicto con el shell del producto porque `index.html` raíz tiene su guard de sesión que redirige a login.
- Para hacerla home pública, sería otro repo o un subdominio `www.zaris.com.ar` con su propio deploy.

### Form de contacto real
Hoy el CTA "Pedir una demo" abre `mailto:contacto@zaris.com.ar`. Si querés un form embebido:
- Formspree, Basin, Tally o un endpoint propio en el backend
- Honeypot anti-spam mínimo
- Mantener accesibilidad (labels visibles, error states con `.input-zaris--error` del DS)

### Tipografía hero
El italic "todo el municipio" en Fraunces se ve elegante en escritorio pero en mobile (~360px) queda apretado. Verificar — está marcado como pendiente potencial.

## Quirks que vale recordar

- **html2canvas no captura tiles de Leaflet** bien. El dashboard salió en `landing/img/zaris-dashboard.png` con el mapa visible pero podría verse con más fidelidad si se reemplaza por una captura nativa via `Page.captureScreenshot` (no expuesto en integrated-browser-mcp hoy).
- **`Read` muestra thumbnails reducidos** — verificar tamaño real con `file landing/img/xxx.png`. Todos los archivos son 1280×800 reales.
- **El bundle React local NO funciona con login local** porque `web-app/dist/` apunta a Railway prod (CLAUDE.md §32 Quirk 1). Para iterar capturas hay 2 caminos:
  - Capturar en prod (lo que hicimos)
  - Rebuildear `web-app/dist/` apuntando a `127.0.0.1:8000`, pero **no commitear ese build** (rompería prod)

## Próximos pasos sugeridos

1. **Decidir publicación** — ¿va a un subdominio comercial separado o queda como `/landing/` del repo?
2. **Capturar vistas internas** de 2-3 módulos clave (detalle de Reclamo con drawer, FSM de Trámite, vista semanal de Agenda).
3. **Convertir a WebP + lazy loading** si la velocidad importa.
4. **Agregar meta tags sociales** + OG image (recorte 1200×630 del dashboard).
5. **Form de contacto real** si la landing va a producción comercial.
6. **Versión inglesa** si aplica.
7. **Validar texto con el área comercial** — la copy actual la escribió Claude basándose en CLAUDE.md, no fue revisada por marketing/ventas.
