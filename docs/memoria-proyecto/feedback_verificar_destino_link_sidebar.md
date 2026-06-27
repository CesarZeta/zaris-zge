---
name: verificar-destino-link-sidebar
description: "Antes de cambiar un link del sidebar a una entrada distinta, verificar que el destino sirva contenido completo en el contexto del iframe."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d16859d3-5cdd-4a02-80e5-3f70b79c7db3
---

Cuando reorganizo el sidebar del shell vanilla y un item antes apuntaba a un menú con N sub-links, ahora apunto a un solo link tipo `frontend/admin_tablas.html?tabla=agentes`. **Verificar que el destino, embebido en iframe, exponga forma de llegar al resto de N-1 recursos.**

**Why:** la regla §14 oculta sidebars/headers internos de los módulos cuando corren en iframe. Si el módulo tiene su propio selector lateral (como `admin_tablas` que tiene un sidebar con 17 tablas), ese selector queda oculto. El usuario llega al destino pero queda atrapado en 1 sub-recurso.

**Caso real (sesión 2026-05-12 jornada 4):**
- Decidí "1 item `maestros` en sidebar plano que entra a `admin_tablas` con sub-selector interno".
- Cambié el link de `<acordeón con 17 links>` a `<a href="admin_tablas.html?tabla=agentes">maestros`.
- Pero `admin_tablas.html` ocultaba `.sidebar` cuando estaba en iframe → usuario vio solo la tabla de agentes, sin forma de cambiar a las otras 16.
- Diagnóstico: el usuario reportó "solo se accede a una tabla, faltan todas las restantes".
- Fix: editar `admin_tablas.html` para NO ocultar el sidebar interno en iframe (mantener `.z-header` oculto, sí).

**How to apply:** antes de migrar un link de sidebar plano hacia un módulo con sub-recursos:

1. **Mirar el HTML/JSX del módulo destino**: ¿tiene un sidebar/selector interno propio?
2. **Mirar el guard de iframe** del módulo: ¿oculta ese selector? (busco `window.self !== window.top` y `display:none` sobre el sidebar interno).
3. **Si lo oculta**, decidir entre:
   - Eliminar la regla que oculta el sidebar interno (caso admin_tablas).
   - Cambiar el destino para que el iframe muestre **el selector** (no la primera tabla) — ej. `admin_tablas.html` sin `?tabla=`.
   - Promover el módulo a 1 item por sub-recurso en el sidebar plano (acepta saturar el menú).
4. **Smoke en localhost:8080** (shell vanilla local) ANTES de pushear: abrir el shell, click en el item del sidebar, verificar visualmente que el destino expone forma de navegar a los N-1 sub-recursos.

**Variante con doble sidebar:** la regla §14 admite que el módulo interno mantenga su sidebar visible cuando tiene 10+ sub-recursos. Doble sidebar (shell + módulo) es feo si son 1-3 sub-items, válido si son muchos.

Relacionado: §14 doble sidebar permitido, [[feedback_nomenclatura_shell]].
