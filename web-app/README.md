# ZARIS — Web App (módulos React)

Bundle de Vite que contiene los módulos React de ZARIS. **No es el shell del producto** — es solo el contenedor de los módulos que se embeben en iframe dentro del shell vanilla (`/index.html` en la raíz del repo). Ver [CLAUDE.md §4](../CLAUDE.md) para la arquitectura completa.

## Módulos hoy

| Módulo | Path | Estado |
|---|---|---|
| Agenda | `src/modules/agenda/` | Producción (Fase 3.A + 3.B drag&drop) |
| Ciudadanos (BUC) | `src/modules/ciudadanos/` | Producción |
| Empresas | `src/modules/empresas/` | Producción |
| Reclamos | `src/modules/reclamos/` | Producción (Fases A + B1+B2 + B3) |
| Dashboard | `src/modules/dashboard/` | Stub demo, solo dev (no enlazado en prod) |

Para agregar uno nuevo: leer [CLAUDE.md §12](../CLAUDE.md) y el slash command `/migrate-vanilla-to-react`.

## Desarrollo local

```powershell
# Backend (desde backend/)
$env:ENV_FILE=".env.local"; uvicorn app.main:app --host 127.0.0.1 --port 8000

# Web-app standalone (este directorio)
pnpm dev   # http://localhost:5173 — AppShell con sidebar + topbar propios (solo dev)

# Shell vanilla + bundle React embebido (testing integración)
# Desde la raíz del repo, en otra terminal:
python -m http.server 8080   # http://localhost:8080/index.html
# Y rebuildear el bundle si tocaste código:
node_modules/.bin/vite build --mode development
```

Credenciales dev: `ciudadanovl@municipio.gob.ar` / `123456` (admin nivel 1). Ver [CLAUDE.md §32 quirk 10](../CLAUDE.md).

## Build de producción

```powershell
# En terminal limpia (sin VITE_API_BASE seteado en el shell — ver §32 quirk 1)
node_modules/.bin/vite build

# Verificar que el bundle apunta a Railway, no a localhost
grep -o "https://zaris-api[a-z0-9.-]*" dist/assets/index-*.js | head -1
grep -c "127.0.0.1\|localhost:8000" dist/assets/index-*.js   # debe ser 0
```

`web-app/dist/` está **commiteada** al repo (excepción explícita en `.gitignore`). El workflow `.github/workflows/deploy-web-app.yml` rebuildea y commitea automáticamente en cada push a `main` que toque `web-app/**`.

## Reglas que un módulo DEBE respetar

Resumen — el listado completo está en [CLAUDE.md §12](../CLAUDE.md) y §14.

- Router: `createHashRouter`, no `createBrowserRouter` (GitHub Pages no soporta HTML5 routing).
- API base: leer de `import.meta.env.VITE_API_BASE` (env files en `.env.development` / `.env.production`).
- Sesión: `useAuthStore` (`src/stores/auth.ts`) — implementa `dualShapeStorage` para que el shell vanilla pueda leer la sesión también.
- **No** agregar UI de navegación propia (sidebar/topbar/notificaciones globales) — esa UI vive en el shell vanilla. El `AppShell` se auto-oculta cuando detecta iframe.
- Estilos: tokens del DS (`var(--zaris-orange)`, `var(--fg-1)`, etc.), no colores hardcodeados.
- Confirmaciones destructivas: `ConfirmModal` (`src/modules/agenda/components/ConfirmModal.tsx`), no `window.confirm` (los headless browsers lo auto-aceptan).

## Stack

- Vite 8 + React 19 + TypeScript 6
- React Router v6 (hash router)
- TanStack Query (react-query)
- Zustand (state + persist con shape dual)
- @dnd-kit/core (drag & drop en Agenda)
- Lucide React (iconos)
- qrcode (render cliente en Agenda autoservicio)

**No agregar dependencias** sin pedir confirmación. Date nativo, no `date-fns` ni `dayjs` (ver [CLAUDE.md §28](../CLAUDE.md)).
