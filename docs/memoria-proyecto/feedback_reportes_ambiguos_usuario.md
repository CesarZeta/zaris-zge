---
name: reportes-ambiguos-usuario
description: "Cuando el usuario reporta un problema visual con vocabulario genérico (logo, icono, shell, navegación), preguntar QUÉ y DÓNDE antes de proponer fix."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d16859d3-5cdd-4a02-80e5-3f70b79c7db3
---

El usuario suele reportar problemas visuales con palabras genéricas que en este proyecto significan cosas distintas. Ejemplos reales (sesión 2026-05-12 jornada 4):

- **"logo"** puede ser: brand del topbar (`<svg class="brand__mark">` inline en `index.html`), favicon de la pestaña (`<link rel="icon">` apuntando a `design-system/assets/zaris-favicon.svg`), icono del sidebar de un módulo (Lucide React), o el SVG del login standalone.
- **"shell"** puede ser: shell vanilla (`index.html` raíz, producto real), shell React (`AppShell` standalone en `localhost:5173`, dev), o el shell React renderizado standalone en prod por un bug del guard.
- **"navegación"** puede ser: sidebar, topbar, breadcrumb, tabs internas, o el flujo de URLs.
- **"iconos antiguos"** puede ser: icono dentro del producto que sigue siendo placeholder de Vite, marca del header con colores viejos, o iconos de Lucide vs SVG inline.

**Why:** asumir el referente equivocado lleva a investigar el archivo equivocado durante 1-2 rounds antes de detectar el malentendido. Caso real: el usuario reportó "veo iconos antiguos y desincronización de navegación" → asumí favicon de la pestaña, pero era el `AppShell` React standalone visible en prod. Resolver lleva minutos; investigar el equivocado lleva mucho más.

**How to apply:**

1. **Antes de proponer fix sobre un reporte visual genérico, pedir al menos UNA cosa concreta**:
   - URL exacta donde vio el problema (incluyendo si es `cesarzeta.github.io/...`, `localhost:5173`, `localhost:8080/index.html`, o un iframe interno).
   - Screenshot del estado visible.
   - Confirmación de incógnito o hard-refresh (Ctrl+F5) — descarta cache antes de tocar archivos.

2. **Si el usuario menciona dos cosas en el mismo mensaje** ("falta acceso a X Y siguen los iconos antiguos"), tratarlas como problemas INDEPENDIENTES. No unificar. Caso real: asumí que "iconos antiguos" era el mismo issue que "agenda no aparece" — eran cosas distintas.

3. **CLAUDE.md §4 ya tiene una sección sobre esto** ("Reportes visuales del usuario: PRIMERO preguntar/verificar en qué shell lo vio") — releer cuando llegue un reporte visual ambiguo.

4. **Cuando el usuario corrige** ("eso no es el favicon, es el logo"), no insistir con la respuesta anterior. Aceptar la corrección como nueva información, releer el código relevante con la nueva interpretación.

**Lo que NO hacer:** asumir cache del browser como primera explicación cuando el usuario sigue insistiendo. Pedir incógnito + URL exacta como **primer paso de diagnóstico**, no como último recurso después de 3 rounds.

Relacionado: [[feedback_nomenclatura_shell]] (no decir "web-app" como si fuera el producto).
