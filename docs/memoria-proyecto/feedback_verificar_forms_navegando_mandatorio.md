---
name: feedback_verificar_forms_navegando_mandatorio
description: "Mandatorio verificar navegando con el explorador todo cambio en formularios, interfaces y navegación/routing. La verificación la hago YO con el browser MCP — nunca pedírsela al usuario. Si no se pudo, declararlo en el PRIMER párrafo del cierre."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fd319fd9-f838-423f-ae64-a5d843565c54
---

Siempre que se hagan cambios en **formularios, interfaces o navegación/routing**, es **MANDATORIO** verificar su funcionalidad **navegando con el explorador** (browser MCP) — abrir la pantalla real, interactuar como un usuario (clickear, llenar, guardar) y confirmar el comportamiento. No alcanza con typecheck, build, ni smoke de API.

**Por qué:** para el usuario la realidad vive en la interfaz; el código es una hipótesis. Un endpoint que responde + tipos que matchean + HTML servido correcto pueden seguir dando una pantalla rota (caché de iframe, sección que no renderiza, handler que no dispara, 404 de GH Pages bajo `/zaris-zge/`, NavLink relativo que expulsa al dashboard). El usuario lo declaró regla de por vida tras varias entregas "completadas" con bugs vivos.

**La verificación la hago YO, no el usuario.** No cerrar una tarea de frontend diciendo "falta tu verificación visual" ni preguntar "¿lo verificás vos?". Tengo el browser MCP integrado; delegarle al usuario lo que puedo hacer yo es trabajo que le tiro de vuelta (sesión 2026-05-14: "NO ME PIDAS VERIFICACIONES VISUALES, VOS PODÉS HACERLAS"). El cierre dice qué verifiqué y qué vi.

**How to apply:**
- Levantar servicios (API + server local — receta detached en skill `win-quirks`), inyectar sesión, navegar al módulo, ejecutar el flujo real (alta/edición/guardar), leer el resultado en DOM/DB, limpiar datos de prueba. Si el cambio ya está en prod: navegar prod (zge.zaris.com.ar).
- **Confirmar que el iframe carga el bundle NUEVO antes de juzgar** — cache-bust `src='about:blank'` → `src=...?_cb=<único>` y verificar el hash del `<script src>` ([[feedback_browser_mcp_iframe_cache]]).
- **Recorrer TODAS las vías de navegación que el usuario tiene a mano**: cada tab/botón, ida y vuelta entre secciones. NO entrar por URL directa a cada vista — eso oculta bugs de links relativos (caso Config 2026-05-22: las tabs expulsaban al dashboard y "entré por URL y cargó" lo tapó). Procedimiento completo en CLAUDE.md §41.
- Si por alguna razón no se pudo verificar navegando, **decirlo explícito en el PRIMER párrafo del cierre** ("no testeado visualmente, falta validar X/Y/Z") — no enterrarlo en pendientes al final. Si entregás varios pedazos y solo algunos los probaste, prefijá cada uno: `[verificado en navegador]` / `[smoke API ok, sin navegador]` / `[no testeado]`.

**Corolario (confirmado 3× el 2026-06-01): documentar/usar una pantalla como usuario destapa bugs que el código "compila" oculta.** Generar un manual, capturar una pantalla o recorrer un circuito E2E real encontró: (1) un tab del builder implementado pero sin botón en la barra → inaccesible; (2) el handler GET de detalle armaba su `Out` sin el campo nuevo aunque el helper de mutaciones sí → panel siempre vacío; (3) un guard de visados que bloqueaba la salida a subsanación → trámite trabado sin salida. Ninguno lo veían typecheck ni smoke parcial.

Relacionado: [[feedback_repaso_visual_caza_bugs]] (repaso end-to-end proactivo), [[feedback_seedear_cuando_mesa_vacia]], [[feedback_dar_links_para_testear]].
