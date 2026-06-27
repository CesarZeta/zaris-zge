---
name: no-sugerir-mcp-navegador
description: No proponer Chrome DevTools MCP ni Playwright MCP. Ya se intentaron y fallaron; el usuario instaló otra herramienta (integrated-browser-mcp en VSCode). Para testing navegacional usar esa.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 76abb031-f1fc-41a4-97a8-16b043ddea10
---

No sugerir instalar **Chrome DevTools MCP** ni **Playwright MCP** como pendiente, ni como alternativa, ni como "setup para próxima sesión". Ya se intentaron, fallaron, y el usuario lo aclaró más de una vez.

**Why:** el usuario ya tiene operativo `mcp__integrated-browser-mcp__*` (browser integrado en VSCode, ver tools disponibles en el system prompt). Volver a proponer las opciones descartadas es ruido y ya se pidió eliminarlo varias veces.

**How to apply:**
- Si hace falta testing navegacional (smoke E2E, validar UX, capturar regresiones), usar `mcp__integrated-browser-mcp__*` directamente (`browser_navigate`, `browser_click`, `browser_type`, `browser_screenshot`, etc.).
- Si aparece una entrada vieja en `project_estado_sesion_y_pendientes.md` mencionando Chrome DevTools MCP / Playwright MCP / "setup MCP de navegador" como pendiente, borrarla en el momento, no respetarla.
- Limitaciones del browser MCP integrado ya documentadas en [[feedback_browser_mcp_react_setup]] y [[feedback_browser_mcp_que_si_funciona]] — consultar esas memorias antes de scriptear smoke.
