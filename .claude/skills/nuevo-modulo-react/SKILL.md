---
name: nuevo-modulo-react
description: Pasos mecánicos para agregar un módulo React nuevo al producto ZARIS (web-app/src/modules/<nombre>/) y publicarlo embebido en el shell vanilla. Usar al crear un módulo React desde cero: crear el ModuleManifest, registrarlo, exponerlo en el sidebar del shell vanilla, y entender cómo se buildea/publica a GH Pages. Las REGLAS que un módulo DEBE respetar (router, API base, sesión, iframe, tokens DS, fila en modulos) viven en CLAUDE.md §12 porque gobiernan decisiones — esta skill es solo el procedimiento de alta.
---

# Agregar un módulo React al producto

Los módulos React viven en `web-app/src/modules/<nombre>/`. Build estático de Vite → GitHub Pages → el shell vanilla los carga en su iframe. **Antes de empezar leer §4 y §14 de CLAUDE.md** + las "Reglas que un módulo React DEBE respetar" de §12.

## Crear el módulo
1. `web-app/src/modules/<nombre>/index.ts` exporta un `ModuleManifest` (ver `web-app/src/lib/types.ts`).
2. Importar el manifest en `web-app/src/modules/index.ts` (array `modules`).
3. El AppShell del shell React contenedor (solo visible en `localhost:5173` en dev) lee el array y lo agrega al sidebar y al router. Esto **NO** afecta producción.
4. Para que sea accesible en producción, agregar un `<a class="nav-flat__item" href="web-app/dist/index.html#/<nombre>/<ruta>" data-modulo="<codigo>">` en `index.html` (raíz, dentro del `nav-flat`).
5. **Si el ítem lleva `data-modulo="<codigo>"`, ese código DEBE existir como fila en la tabla `modulos` (catálogo de permisos §30)** — sino el ítem queda OCULTO para TODOS (incluido admin). Insertar la fila con migración formal (`INSERT INTO modulos (...) ON CONFLICT DO NOTHING`), aplicada en local Y prod. Si el módulo es informativo y lo ve cualquiera, NO le pongas `data-modulo` (ej. Guías). Cazado 2026-05-26 con Encuestas (mig 61). Ver [[feedback_modulo_react_necesita_fila_en_modulos]].

## Cómo se publica a producción
- **Build:** `pnpm build` en `web-app/` genera `web-app/dist/` con assets que apuntan a `/zaris-zge/web-app/dist/` (configurado en `vite.config.ts` con `base`).
- **GitHub Pages:** sirve el repo entero desde la raíz; `web-app/dist/index.html` queda en `https://cesarzeta.github.io/zaris-zge/web-app/dist/index.html`.
- **Workflow automático:** `.github/workflows/deploy-web-app.yml` rebuildea `web-app/dist/` y commitea el resultado en cada push a main que toque `web-app/**`.
- `web-app/dist/` está versionado (`.gitignore` con excepción explícita).
- Antes de commitear dist: ver skill `win-quirks` (buildear modo prod, verificar apunta a Railway).

## `hideFromSidebar?: boolean` (ModuleManifest)
Si `true`, el módulo se registra (rutas activas, deep-links y links inter-módulo funcionan) pero NO aparece en el sidebar del shell React standalone. Útil cuando se entra solo desde una landing agrupadora (ej. `ciudadanosModule`/`empresasModule` se entran via `contactosModule`). El filtro vive en `web-app/src/shell/Sidebar/Sidebar.tsx`, corre antes que el filtro de permisos §30.
