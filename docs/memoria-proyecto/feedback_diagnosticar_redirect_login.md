---
name: Web-app redirect-a-login — sospechar primero de api.ts
description: Cuando la web-app React redirige inesperadamente a /login al navegar, el sospechoso #1 es getToken()/handler 401 en src/lib/api.ts, no el router ni AppShell ni CSS.
type: feedback
---
Cuando la web-app React (`web-app/`) redirige inesperadamente a `/login` al hacer click o cargar una ruta protegida, **el sospechoso #1 es `src/lib/api.ts`**, no el router, no `AppShell`, no el CSS, no los componentes del shell.

**Why:** En esta sesión perdí ~5 turnos diagnosticando "no se ve el shell + click en agenda redirige a login". Probé inspeccionar Sidebar.tsx, TopBar.tsx, AppShell.module.css, globals.css, routes.tsx, types.ts, tsc --noEmit, vite build. Todo limpio. El bug real era 1 línea en `getToken()` de `api.ts`: leía la estructura legacy `{access_token,...}` pero zustand/persist guarda `{state:{accessToken,...},version:0}`. Cada fetch salía sin Authorization → backend devolvía 401 → `api.ts` ejecutaba `window.location.href = '/login'` → loop visible como "no me deja entrar".

**How to apply:**
- Síntoma: usuario logueado, click en ruta protegida, browser termina en `/login` aunque AppShell estaba montado.
- Primero abrir `web-app/src/lib/api.ts` y revisar:
  1. `getToken()` — ¿lee la shape correcta del storage? (ver memoria *Shape zustand-persist en zaris_session*).
  2. Bloque `if (res.status === 401)` — ¿hace `window.location.href = '/login'`? Si sí, cualquier 401 en cualquier hook dispara el redirect global.
- Si `getToken()` devuelve `null`, el primer fetch de la ruta nueva sale sin token, da 401, redirige. Por eso el síntoma aparece *al navegar*, no al refrescar.
- Recién si `api.ts` está OK, investigar AppShell/guards/router.
