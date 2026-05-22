# Prompt — Etapa 1: Scaffold PWA `zaris-vecinos`

> Este prompt es autocontenido. Va a una sesión nueva de Claude Code donde se va a crear un **repo nuevo desde cero**, separado de `zaris-zge`. Leer entero antes de empezar.

---

## Contexto del producto

**ZARIS Gestión Estatal (ZGE)** es un backoffice para municipios argentinos. Los agentes municipales lo usan para gestionar reclamos, OTs, turnos, trámites, etc. Repo principal: `github.com/CesarZeta/zaris-zge`, backend en Railway, shell vanilla + módulos React en GitHub Pages bajo `zge.zaris.com.ar`.

**Ahora arranca una nueva línea de producto: `zaris-vecinos`** — una **PWA mobile-first** para que los vecinos (ciudadanos del municipio) hagan reclamos desde el celular sin pasar por la municipalidad. El backend ya está preparado (CLAUDE.md §38 del repo zaris-zge documenta el módulo "Auth público de ciudadanos" + identidad del municipio).

Esta es **Etapa 1 de un roadmap de 6 etapas** definido en `docs/roadmap_app_vecinos.md` del repo zaris-zge. **Solo trabajamos en Etapa 1 acá.** No tocar las siguientes.

---

## Objetivo de Etapa 1

Crear un repo nuevo `zaris-vecinos` con scaffold de **React + Vite + vite-plugin-pwa**, deployado en **Vercel**, accesible vía HTTPS, que carga una pantalla de bienvenida con branding leído del backend de zaris-zge. El shell de la PWA debe ser **instalable** desde Android Chrome, el Service Worker activo, y el manifest válido.

**Esta etapa NO incluye auth ni login del vecino.** Solo el shell + bienvenida + branding del municipio. La auth viene en Etapa 3.

---

## Backend ya disponible (no tocar)

El backend de zaris-zge ya expone (sin auth):

- `GET https://zaris-api-production-bf0b.up.railway.app/api/v1/publico/identidad-municipio`
  - **Sin auth** (la PWA lo lee antes de tener token, en la pantalla de bienvenida).
  - Devuelve JSON con: `municipio_nombre`, `municipio_logo_url`, `municipio_descripcion`, `municipio_color_primary`, `municipio_color_accent`. Claves ausentes/vacías → `null`.
  - Ejemplo de respuesta esperada:
    ```json
    {
      "municipio_nombre": "MUNICIPALIDAD DE SAN ANDRÉS",
      "municipio_logo_url": "https://...supabase.co/storage/.../logo.png",
      "municipio_descripcion": "Atención al vecino digital",
      "municipio_color_primary": "#1f8a65",
      "municipio_color_accent": "#f54e00"
    }
    ```
  - Si todas las claves están vacías, igual devuelve `200` con `null` en cada campo. La PWA debe manejar el caso "sin branding cargado" con defaults.

**CORS:** el backend tiene allowlist explícita en `app/main.py`. **Antes de hacer requests desde el dominio nuevo de Vercel a Railway, hay que agregar ese dominio a `allow_origins`** del backend zaris-zge. Esto se hace en una sesión separada (no en esta) — pero documentarlo como prerequisito en el README de zaris-vecinos.

> **Quirk crítico:** durante el desarrollo local de zaris-vecinos en `http://localhost:5174`, hay que agregar también ese origin al CORS del backend en `app/main.py` y reiniciar uvicorn. Documentar este paso en el README.

---

## Stack

- **React 19** (último estable, igual que el shell React de zaris-zge).
- **TypeScript** estricto.
- **Vite** (última estable).
- **vite-plugin-pwa** con estrategia `generateSW` (más simple para empezar — `injectManifest` se considera en etapas futuras si hace falta).
- **React Router v6** con `BrowserRouter`.
- **Fetch nativo** (sin axios, sin react-query — todavía no hace falta).
- **CSS variables + clases utilitarias mínimas.** NO Tailwind. NO CSS-in-JS. Si más adelante decidimos Tailwind, se agrega.
- **Tipografía:** Inter desde Google Fonts vía `<link>` en `index.html`. Sin Fraunces todavía.

---

## Estructura esperada del repo

```
zaris-vecinos/
├─ .github/
│  └─ workflows/                  # vacío por ahora (Vercel hace el deploy)
├─ public/
│  ├─ icons/
│  │  ├─ icon-192.png             # 192x192 — para Android home screen
│  │  ├─ icon-512.png             # 512x512 — para splash screen
│  │  └─ icon-512-maskable.png    # 512x512 con safe-zone para iconos adaptive
│  └─ favicon.svg                 # favicon de pestaña (puede ser uno genérico)
├─ src/
│  ├─ App.tsx                     # router + layout root
│  ├─ main.tsx                    # entry + registro del SW
│  ├─ lib/
│  │  ├─ api.ts                   # cliente fetch tipado con base URL desde env
│  │  ├─ identidad.ts             # hook useIdentidadMunicipio()
│  │  └─ branding.ts              # aplica colores del municipio a CSS variables
│  ├─ pages/
│  │  └─ BienvenidaPage.tsx
│  ├─ components/
│  │  ├─ Button.tsx
│  │  └─ Card.tsx
│  └─ styles/
│     ├─ tokens.css               # CSS variables (paleta, espaciado, tipografía)
│     ├─ reset.css                # reset minimal (no normalize.css completo)
│     └─ global.css               # estilos globales (body, fonts)
├─ index.html
├─ vite.config.ts                 # con vite-plugin-pwa configurado
├─ tsconfig.json
├─ tsconfig.node.json
├─ package.json
├─ pnpm-lock.yaml                 # commiteado
├─ vercel.json                    # rewrites SPA a index.html
├─ .env.example                   # template
├─ .gitignore
└─ README.md
```

---

## Sistema de diseño v1 (mobile-first)

### Paleta CSS variables (en `src/styles/tokens.css`)

```css
:root {
  /* Colores base — fallback si el municipio no tiene branding cargado */
  --app-cream: #f2f1ed;          /* fondo de página */
  --app-surface: #ffffff;         /* tarjetas */
  --app-ink: #26251e;             /* texto primario */
  --app-ink-2: rgba(38, 37, 30, 0.7);    /* texto secundario */
  --app-ink-3: rgba(38, 37, 30, 0.5);    /* texto terciario */
  --app-border: rgba(38, 37, 30, 0.12);
  --app-success: #1f8a65;
  --app-error: #cf2d56;

  /* Colores del municipio — se sobrescriben en runtime con los hex del endpoint */
  --app-primary: #1f8a65;         /* default verde ZARIS */
  --app-accent: #f54e00;          /* default naranja ZARIS */
  --app-primary-contrast: #ffffff;
  --app-accent-contrast: #ffffff;

  /* Espaciado (escala 4px) */
  --sp-1: 4px;
  --sp-2: 8px;
  --sp-3: 12px;
  --sp-4: 16px;
  --sp-5: 24px;
  --sp-6: 32px;
  --sp-7: 48px;
  --sp-8: 64px;

  /* Radios */
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-pill: 999px;

  /* Tipografía */
  --font-base: 'Inter', system-ui, -apple-system, sans-serif;
  --fs-1: 14px;
  --fs-2: 16px;          /* tamaño base — NO bajar de aca en mobile */
  --fs-3: 18px;
  --fs-4: 22px;
  --fs-5: 28px;
  --fs-6: 36px;

  /* Sombras */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.06);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.08);
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.12);

  /* Áreas de toque — minimo 44px segun Apple HIG, 48dp segun Material */
  --tap-min: 48px;
}
```

### Helper de branding (`src/lib/branding.ts`)

Función que toma la respuesta del endpoint de identidad y aplica los colores a las CSS variables del root:

```ts
export function aplicarBrandingMunicipio(data: {
  municipio_color_primary: string | null
  municipio_color_accent: string | null
}) {
  const root = document.documentElement
  if (data.municipio_color_primary) {
    root.style.setProperty('--app-primary', data.municipio_color_primary)
  }
  if (data.municipio_color_accent) {
    root.style.setProperty('--app-accent', data.municipio_color_accent)
  }
  // theme-color del manifest (afecta la barra de status en mobile)
  const themeMeta = document.querySelector('meta[name="theme-color"]')
  if (themeMeta && data.municipio_color_primary) {
    themeMeta.setAttribute('content', data.municipio_color_primary)
  }
}
```

### Componentes base mínimos

**`<Button variant="primary" | "secondary" | "ghost" size="md" | "lg">`** — `min-height: var(--tap-min)`, padding generoso, sin sombras agresivas. `primary` usa `--app-primary` con `--app-primary-contrast`. Loading state con spinner inline.

**`<Card padding="md" | "lg">`** — fondo `--app-surface`, radio `--radius-lg`, sombra `--shadow-sm`. Sin border por default.

Nada más. No agregar Input/Select/Modal en esta etapa — esos vienen en Etapa 3 cuando arranca el form de login.

---

## Vite + PWA — config esperada

### `vite.config.ts`

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'icons/*.png'],
      manifest: {
        name: 'ZARIS Vecinos',
        short_name: 'Vecinos',
        description: 'Atención al vecino digital',
        theme_color: '#1f8a65',
        background_color: '#f2f1ed',
        display: 'standalone',
        orientation: 'portrait',
        scope: '/',
        start_url: '/',
        icons: [
          {
            src: '/icons/icon-192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any'
          },
          {
            src: '/icons/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any'
          },
          {
            src: '/icons/icon-512-maskable.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable'
          }
        ]
      },
      workbox: {
        // Cachear el shell de la app pero NO las llamadas a la API
        // (esas son siempre frescas)
        navigateFallback: '/index.html',
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/fonts\.(googleapis|gstatic)\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts-cache',
              expiration: {
                maxEntries: 10,
                maxAgeSeconds: 60 * 60 * 24 * 365
              }
            }
          }
        ]
      }
    })
  ],
  server: {
    port: 5174,
    strictPort: true
  }
})
```

> **Nota sobre el puerto 5174:** el shell React de zaris-zge usa 5173; usamos 5174 para que ambos puedan correr en paralelo en local sin conflicto.

### `index.html`

```html
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
  <meta name="theme-color" content="#1f8a65" />
  <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
  <link rel="apple-touch-icon" href="/icons/icon-192.png" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <title>ZARIS Vecinos</title>
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/main.tsx"></script>
</body>
</html>
```

---

## Pantalla de Bienvenida

Ruta: `/` (única ruta de esta etapa).

**Layout** (mobile-first):
- Header chico con el logo del municipio (si está en `municipio_logo_url`).
  - Si no hay logo, mostrar solo el nombre.
  - Si tampoco hay nombre, mostrar "ZARIS Vecinos" como fallback.
- Hero centrado verticalmente con:
  - Nombre del municipio en `--fs-5` (28px).
  - Descripción del municipio en `--fs-3` (18px), opcional, `--app-ink-2`.
  - Espacio.
  - Botón primario grande "Ingresar" — `width: 100%`, `--app-primary`. Por ahora navega a `/login` con `react-router` aunque esa ruta no exista todavía (mostrar `<div>Próximamente</div>` como placeholder). Cuando se llegue a Etapa 3, esto se reemplaza.
  - Debajo, un link secundario "¿No tenés cuenta? Solicitala en tu municipio" (sin link real, solo texto).
- Footer chico con `ZARIS · zaris.com.ar` y versión del build (leída de `import.meta.env.VITE_APP_VERSION` o hardcoded `v0.1.0`).

**Lógica:**
1. Al montar, llamar a `GET /publico/identidad-municipio`.
2. Mientras carga, mostrar un skeleton (no spinner — la app es mobile, no queremos pantalla en blanco).
3. Cuando llega la data, aplicar branding con `aplicarBrandingMunicipio` y renderizar.
4. Si la request falla (network down, CORS roto), mostrar igual el contenido con defaults + un toast/banner "Sin conexión — mostrando contenido básico". No romper la pantalla.

**Hook esperado** (`src/lib/identidad.ts`):

```ts
export interface IdentidadMunicipio {
  municipio_nombre: string | null
  municipio_logo_url: string | null
  municipio_descripcion: string | null
  municipio_color_primary: string | null
  municipio_color_accent: string | null
}

export function useIdentidadMunicipio(): {
  data: IdentidadMunicipio | null
  loading: boolean
  error: Error | null
}
```

Implementación con `useState` + `useEffect`. Sin react-query.

---

## Vercel — config esperada

### `vercel.json`

```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ],
  "headers": [
    {
      "source": "/sw.js",
      "headers": [
        { "key": "Cache-Control", "value": "public, max-age=0, must-revalidate" },
        { "key": "Service-Worker-Allowed", "value": "/" }
      ]
    }
  ]
}
```

### Env vars (en `.env.example`)

```
VITE_API_URL=https://zaris-api-production-bf0b.up.railway.app
VITE_APP_VERSION=0.1.0
```

Vercel lee variables con prefijo `VITE_` y las inyecta al build. No commitear `.env.local`.

### Pasos de deploy (documentar en README)

1. Crear proyecto Vercel desde el repo (importar de GitHub).
2. Framework Preset: Vite.
3. Build Command: `pnpm build` (Vercel detecta `pnpm-lock.yaml`).
4. Output Directory: `dist`.
5. Install Command: `pnpm install`.
6. Env Variables: `VITE_API_URL` apuntando a Railway prod.
7. Deploy.

---

## Iconos — generar desde el mark oficial de ZARIS

**Fuente:** `design-system/assets/zaris-mark-flat.svg` del repo zaris-zge (path absoluto local: `c:\Users\Cesar\Documents\ZARIS\Desarrollo\ZGE\design-system\assets\zaris-mark-flat.svg`). Es un SVG 500x500 con `stroke="currentColor"`, sin fondo — el color de las líneas se decide al renderizar.

**Copiar el SVG al repo `zaris-vecinos`:**

```
zaris-vecinos/
  public/
    icons/
      zaris-mark-flat.svg          # copia exacta del original
      icon-192.png                 # generado
      icon-512.png                 # generado
      icon-512-maskable.png        # generado
```

**Especificaciones de los 3 PNGs:**

| Archivo | Tamaño | Fondo | Mark | Padding interno |
|---|---|---|---|---|
| `icon-192.png` | 192×192 | `#f54e00` (naranja ZARIS) | blanco `#ffffff` | ~15% (mark ocupa ~70% del canvas) |
| `icon-512.png` | 512×512 | `#f54e00` (naranja ZARIS) | blanco `#ffffff` | ~15% (mark ocupa ~70% del canvas) |
| `icon-512-maskable.png` | 512×512 | `#f54e00` (naranja ZARIS) | blanco `#ffffff` | ~25% (mark ocupa ~50% del canvas) — safe-zone ampliada |

**Por qué el maskable tiene padding mayor:** Android aplica una máscara (círculo, squircle, redondeado) sobre el icono y recorta lo que queda afuera. Si el mark está pegado al borde, queda cortado. Dejar 25% de margen garantiza que el mark se vea completo bajo cualquier máscara.

### Receta concreta para generar los PNGs

Usar `sharp` (Node) que ya está disponible si el proyecto tiene Vite. Crear un script `scripts/generate-icons.mjs`:

```js
import sharp from 'sharp'
import { mkdirSync, writeFileSync } from 'fs'
import { resolve } from 'path'

const OUT = resolve(process.cwd(), 'public/icons')
mkdirSync(OUT, { recursive: true })

// Función que genera el SVG completo con fondo + mark centrado + escalado
function buildSvg(canvasSize, markScale) {
  const markSize = Math.round(canvasSize * markScale)
  const offset = Math.round((canvasSize - markSize) / 2)
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${canvasSize}" height="${canvasSize}" viewBox="0 0 ${canvasSize} ${canvasSize}">
    <rect width="${canvasSize}" height="${canvasSize}" fill="#f54e00"/>
    <g transform="translate(${offset}, ${offset}) scale(${markSize / 500})">
      <g fill="none" stroke="#ffffff" stroke-width="34" stroke-linecap="round" stroke-linejoin="round">
        <path d="M 110 78 L 388 78"/>
        <path d="M 388 78 L 110 430"/>
        <path d="M 388 220 L 222 430"/>
        <path d="M 388 362 L 334 430"/>
      </g>
    </g>
  </svg>`
}

const targets = [
  { name: 'icon-192.png',           size: 192, scale: 0.70 },
  { name: 'icon-512.png',           size: 512, scale: 0.70 },
  { name: 'icon-512-maskable.png',  size: 512, scale: 0.50 }
]

for (const t of targets) {
  const svg = buildSvg(t.size, t.scale)
  await sharp(Buffer.from(svg)).png().toFile(resolve(OUT, t.name))
  console.log(`generated ${t.name}`)
}
```

Ejecutar una vez: `pnpm add -D sharp && node scripts/generate-icons.mjs`. Después podés sacar `sharp` de devDependencies si querés (los PNGs ya están commiteados, no se regeneran en cada build). O dejarlo si pensás iterar los iconos.

**Favicon de pestaña** (`public/favicon.svg`): usar el mismo SVG del mark con color `#26251e` (ink oscuro) directamente — sin fondo, para que se vea bien en pestañas claras y oscuras del browser:

```html
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 500">
  <g fill="none" stroke="#26251e" stroke-width="34" stroke-linecap="round" stroke-linejoin="round">
    <path d="M 110 78 L 388 78"/>
    <path d="M 388 78 L 110 430"/>
    <path d="M 388 220 L 222 430"/>
    <path d="M 388 362 L 334 430"/>
  </g>
</svg>
```

> **Cuándo cambiar esto:** en una etapa futura cuando un municipio aporte su logo brandeado para usar como ícono de la app instalada (en lugar del mark de ZARIS). Hoy todos los municipios comparten el mismo ícono ZARIS — la marca del municipio aparece dentro de la app (logo + nombre en la bienvenida), no en el ícono del home screen.

---

## Criterios de aceptación

### Funcionales
- [ ] `pnpm dev` levanta la PWA en `http://localhost:5174`.
- [ ] `pnpm build` genera `dist/` sin errores de TS.
- [ ] `pnpm preview` sirve el build local y la PWA es instalable.
- [ ] La pantalla de bienvenida llama a `/publico/identidad-municipio` y muestra el branding.
- [ ] Si el backend no responde (timeout/network error), la pantalla muestra defaults sin crashear.
- [ ] Los colores `--app-primary` y `--app-accent` se sobrescriben con los del municipio cuando el endpoint los devuelve no-null.

### PWA
- [ ] Lighthouse PWA audit en Chrome DevTools: **score ≥ 90** en categoría PWA.
- [ ] `manifest.webmanifest` se genera en `dist/` y es válido (validar con https://manifest-validator.appspot.com/).
- [ ] Service Worker activo (verificable en DevTools → Application → Service Workers).
- [ ] El botón "Instalar app" aparece en Chrome desktop (al lado de la URL).
- [ ] **Probar instalación en Android Chrome real** y verificar que el icono queda en home screen + la PWA abre en standalone (sin barra de URL).

### Deploy
- [ ] PWA accesible vía HTTPS en `<project>.vercel.app`.
- [ ] Reload en cualquier ruta no devuelve 404 (rewrites OK).
- [ ] El build de Vercel pasa.

### Código
- [ ] TypeScript estricto, sin `any` ni `@ts-ignore`.
- [ ] `pnpm typecheck` (o equivalente con `tsc --noEmit`) pasa.
- [ ] Sin warnings de React en consola al cargar la app.
- [ ] Estructura del repo según el árbol especificado arriba.

### README
- [ ] Incluye: stack, cómo correr local, cómo deployar, cómo agregar un municipio nuevo (instrucciones de Vercel), qué env vars necesita.
- [ ] Documenta el prerequisito de CORS en el backend zaris-zge (agregar el dominio Vercel a `allow_origins` y reiniciar uvicorn local en `:5174`).
- [ ] Documenta cómo regenerar los iconos.

---

## Restricciones y antipatrones

**NO hacer en esta etapa:**

1. **NO implementar login/auth.** La pantalla de bienvenida tiene un botón "Ingresar" que navega a `/login` con un placeholder "Próximamente". El form real viene en Etapa 3.
2. **NO usar el shell React del backoffice (`web-app/` de zaris-zge) como referencia visual.** La PWA tiene su propio sistema de diseño. Solo comparten algunos tokens (cream + verde de success).
3. **NO usar Tailwind, CSS-in-JS, Emotion, Styled-Components.** CSS variables + clases utilitarias en `global.css`. Si se necesita modularidad de estilos por componente, usar CSS Modules (`*.module.css`).
4. **NO agregar react-query, zustand, redux, axios.** Esta etapa no tiene estado complejo ni múltiples requests. `useState` + `useEffect` + `fetch` nativo alcanza.
5. **NO agregar dependencias innecesarias.** Cada `pnpm add` se justifica.
6. **NO copiar el patrón de hash router del backoffice (`createHashRouter`).** Eso es para GitHub Pages bajo subpath. Vercel sirve la PWA en el root, podemos usar `BrowserRouter` con `<vercel.json>` rewrites.
7. **NO inventar endpoints del backend.** Solo se usa `GET /publico/identidad-municipio`. Si parece que falta algo, frenar y consultar.

---

## Quirks heredados de zaris-zge a tener presentes

Estos vienen del CLAUDE.md del repo zaris-zge. Aplican acá porque vamos a interactuar con el backend de Railway:

1. **CORS:** el backend en `app/main.py` tiene allowlist explícita. Antes de cualquier request desde un dominio nuevo (Vercel o `localhost:5174`), hay que agregarlo en una sesión separada del repo zaris-zge. Esta sesión NO lo hace, pero el README de zaris-vecinos lo documenta como prerequisito.

2. **`Access-Control-Expose-Headers`:** si más adelante consumimos endpoints que devuelven `X-Total-Count` u otros headers custom, el browser necesita que el backend los exponga. No aplica en Etapa 1 (la identidad no usa headers custom) pero tenerlo presente.

3. **Latencia base Railway↔Supabase:** ~2-3s para queries con JOINs (memoria `reference_agenda_latencia_base_railway_supabase` de zaris-zge). El endpoint de identidad es liviano, debería responder en <500ms, pero la primera request después de un período de inactividad puede tardar más (Railway puede hibernar el container).

4. **Cold start de Vercel:** el primer request a la PWA después de un período sin tráfico puede tomar 1-2s extra. Esto es esperado y no requiere mitigación en Etapa 1.

---

## Workflow esperado

1. **Crear el repo:**
   - Crear repo nuevo en GitHub bajo `CesarZeta/zaris-vecinos` (público está OK).
   - `git init` local, primer commit con el scaffold completo.
   - Push a `main`.

2. **Scaffold inicial:**
   - `pnpm create vite zaris-vecinos --template react-ts` (o equivalente).
   - Agregar dependencias: `react-router-dom`, `vite-plugin-pwa`.
   - Configurar `vite.config.ts`, `tsconfig.json` con strict.
   - Crear estructura de carpetas según el árbol arriba.
   - Implementar `tokens.css`, `global.css`, `reset.css`.
   - Implementar componentes `<Button>`, `<Card>`.
   - Implementar `lib/api.ts`, `lib/identidad.ts`, `lib/branding.ts`.
   - Implementar `BienvenidaPage.tsx`.
   - Generar los 3 iconos placeholder.
   - Configurar `vercel.json`, `.env.example`.
   - Escribir README.

3. **Verificación local:**
   - `pnpm dev` → abrir `http://localhost:5174` en Chrome → verificar render.
   - **Pedirle al usuario que agregue temporalmente `http://localhost:5174` al CORS del backend local** (NO es responsabilidad de esta sesión hacerlo). Si no es posible, dejar el endpoint mockeado en `lib/identidad.ts` con un `if (import.meta.env.DEV)` que devuelva data hardcoded y avisar al usuario.
   - `pnpm build && pnpm preview` → verificar Lighthouse PWA audit.

4. **Deploy:**
   - **NO hacer el deploy a Vercel desde esta sesión.** El usuario lo hace manualmente desde la UI de Vercel (importar repo, setear env vars, deploy).
   - Esta sesión deja el repo listo para deploy: `vercel.json` configurado, `.env.example` documentado, README con los pasos.

5. **Cerrar:**
   - Confirmar al usuario qué pasos siguen (configurar CORS en zaris-zge backend, deployar en Vercel, configurar DNS Cloudflare para `vecinos.zaris.com.ar`).
   - **NO actualizar CLAUDE.md de zaris-zge desde esta sesión** — esa documentación se actualiza en otra sesión cuando se cierre la Etapa 1 verificada.

---

## Reportar al cerrar

Al terminar, devolver al usuario:

1. URL del repo en GitHub (`https://github.com/CesarZeta/zaris-vecinos`).
2. Commit hash del scaffold inicial.
3. Output de `pnpm build` (que pase sin errores).
4. Screenshot o descripción de Lighthouse PWA audit local.
5. Lista de pasos pendientes que requieren intervención del usuario:
   - Agregar dominio Vercel + `http://localhost:5174` al CORS del backend zaris-zge.
   - Crear proyecto en Vercel + importar repo + setear env vars + primer deploy.
   - Configurar dominio custom `vecinos.zaris.com.ar` en Vercel + CNAME en Cloudflare (DNS only, sin proxy).
   - Probar instalación en Android Chrome real.

**Si algo no se puede completar** (ej. los iconos placeholder no se pueden generar desde la sesión), dejarlo declarado explícitamente en el reporte de cierre, no enmascarado.
