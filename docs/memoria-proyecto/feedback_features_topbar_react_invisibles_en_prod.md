---
name: feedback-features-topbar-react-invisibles-en-prod
description: Cualquier UI que pongas en TopBar.tsx del shell React es INVISIBLE en producción (regla §14 oculta TopBar en iframe). Implementar también en shell vanilla (index.html + menu.js).
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e77756f2-e217-4421-a18c-df927d47dfb5
---

`web-app/src/shell/TopBar/TopBar.tsx` solo se renderiza cuando el AppShell React corre **standalone** (`localhost:5173`). En producción los usuarios viven embebidos en iframe del shell vanilla; el AppShell React detecta el embed y devuelve solo `<Outlet/>` + `<Notifications/>` (toasts), sin TopBar (regla §14 CLAUDE.md).

**Implicación:** cualquier componente nuevo que agregues al TopBar React (campana, búsqueda global, switch de tema, indicador online, etc.) será **invisible para los usuarios reales en prod**. Solo lo verás durante `pnpm dev` standalone.

**Caso real (sesión 2026-05-18):** implementé `NotificacionesDropdown.tsx` en TopBar React, verificación visual en `localhost:5173` perfecta, pasó typecheck, deployé a prod. El bug apareció en el smoke end-to-end de prod: las notifs estaban en DB, el endpoint respondía 200, los mails salían por Zoho, pero los usuarios no veían nada. Tuve que reimplementar la campana en el shell vanilla en una segunda iteración.

**How to apply:**
- Antes de poner una feature de UI en `web-app/src/shell/TopBar/`, preguntate: **¿esto necesita ser visible en producción?** Si sí, la implementación canónica es:
  1. HTML + CSS + JS en `index.html` + `frontend/css/menu.css` + `frontend/js/menu.js`.
  2. (Opcional, solo si querés que dev local standalone se vea igual) Replicar como componente React en `TopBar.tsx`. Las dos versiones conviven sin colisión.
- **Si solo es para devs/QA en standalone**, OK ponerla en React shell, pero documentalo explícitamente en CLAUDE.md.
- **Verificación visual durante development**: no alcanza con `localhost:5173`. Hay que abrir prod (o un proxy local que replique `/zaris-zge/`, ver memoria [[project_proxy_local_zaris_zge]]) y validar que la feature se ve en el shell embebido.

Regla aplica a TopBar y por extensión también a `Sidebar.tsx` del shell React — está oculto en iframe igual.
