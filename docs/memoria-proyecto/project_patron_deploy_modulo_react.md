---
name: patron-deploy-modulo-react
description: "Patron probado para publicar un modulo React en produccion embebido en el shell vanilla (iframe). Reutilizable cuando se migre Reclamos, OT u otros modulos a React."
metadata: 
  node_type: memory
  type: project
  originSessionId: 9f22ae1e-23dd-4dae-9ee4-6c68e1a34b76
---

Sesion 2026-05-11 implemento el primer modulo React en produccion (Agenda). El patron quedo formalizado en CLAUDE.md §12 + §14. Esta memoria sintetiza la receta para no releerla cada vez.

**Why:** cuando un modulo de produccion sea suficientemente complejo (forms con estado, DnD, timeline interactivo, validaciones cruzadas), conviene migrarlo de vanilla HTML/JS a React. Pero la migracion debe mantener la regla §14 (un solo shell, iframe unico). Equivocarse al inicio cuesta dias (la sesion previa habia construido un shell React paralelo con sidebar/topbar propios, hubo que desarmarlo).

**How to apply (checklist para migrar un modulo X de vanilla a React):**

1. **Crear modulo en `web-app/src/modules/<x>/`** con `index.ts` exportando `ModuleManifest` (ver `web-app/src/lib/types.ts`).
2. **Registrar en `web-app/src/modules/index.ts`** (array `modules`).
3. **NO agregar sidebar/topbar propios en el modulo.** El `AppShell` (`web-app/src/app/AppShell.tsx`) ya detecta iframe via `window.self !== window.top` y se auto-oculta. En `localhost:5173` standalone se ve el AppShell del shell React para iterar; en prod queda invisible.
4. **Auth:** usar `useAuthStore` de `web-app/src/stores/auth.ts`. Ya tiene `dualShapeStorage` que mantiene la sesion compatible con modulos vanilla.
5. **Api:** `web-app/src/lib/api.ts` ya lee `import.meta.env.VITE_API_BASE`. Si se necesita otra variable, agregarla a `.env.development` y `.env.production`.
6. **Router:** `createHashRouter` ya esta configurado en `web-app/src/app/routes.tsx`. Los modulos solo agregan sus rutas hijo.
7. **Build:**
   - Local: `cd web-app && pnpm build` genera `web-app/dist/`.
   - CI: `.github/workflows/deploy-web-app.yml` lo hace automatico en cada push a main que toque `web-app/**`. Commitea `web-app/dist/` de vuelta a main.
8. **Vite base path:** ya configurado en `vite.config.ts` como `/zaris-zge/web-app/dist/`. Ajustar solo si GitHub Pages cambia de configuracion.
9. **Link desde shell vanilla:** agregar `<a class="nav__link" href="web-app/dist/index.html#/<modulo>/<ruta>">` en `index.html` (raiz), dentro del `nav__group` que corresponda. Eso es lo que hace que el iframe cargue el modulo React cuando el usuario hace click.
10. **Si el modulo React debe coexistir con la version vanilla durante migracion:** dejar las DOS entradas en el sidebar momentaneamente, con label distinto, hasta validar feature parity. Luego dropear la vanilla.

**Trampas conocidas:**

- **Cache de Chrome despues de deploy:** GitHub Pages publica rapido pero el HTML viejo queda cacheado. Si el usuario reporta 404s con hashes viejos de assets, no es bug del codigo: es cache. Hard refresh (Ctrl+Shift+R) o modo incognito.
- **Backend reiniciado:** si el modulo nuevo depende de endpoints nuevos, **verificar `openapi.json` antes** de pasar al usuario. Ver memoria `feedback_verificar_runtime_antes_de_agente`.
- **Doble shape de sesion:** si tocas la auth, ambas shapes (`access_token` plano + `state.accessToken`) deben quedar en `zaris_session`. Caso contrario, el otro shell pierde sesion al loguear desde uno.
- **`createBrowserRouter` no funciona en GH Pages.** Usar siempre `createHashRouter`. F5 sobre una ruta tipo `/agenda/timeline` daria 404 si no fuera con hash.
- **No commitear `web-app/dist/` a mano si la GitHub Action esta activa.** La Action lo hace; commits manuales generan conflictos con el bot.

**Stack hoy:**
- React 18.x, TypeScript estricto, Vite 8.x, React Router v7 (Hash), Zustand 5.x.
- UI components: `web-app/src/ui/index.tsx` (Button, Skeleton, Input, etc).
- `@tanstack/react-query` para fetch + cache.
- `@dnd-kit/core` para drag & drop (instalado para Agenda 3.B).

**Modulos en produccion al 2026-05-11:** solo Agenda. Reclamos/OT/BUC/Empresas/Usuarios/Admin Tablas siguen en vanilla.
