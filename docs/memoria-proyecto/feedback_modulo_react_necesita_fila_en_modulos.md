---
name: modulo-react-necesita-fila-en-modulos
description: "Un módulo React nuevo con data-modulo en el sidebar queda OCULTO para todos (incluso admin) si su código no existe como fila en la tabla `modulos`. Insertar la fila con migración formal."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 44d96066-6920-456e-855d-1f0b243cc615
---

Al publicar un módulo React nuevo en el shell vanilla (CLAUDE.md §12), el ítem del sidebar lleva `data-modulo="<codigo>"`. `frontend/js/menu.js` filtra cada ítem contra `user.modulos_permitidos`: si el código **no existe como fila en la tabla `modulos`** (catálogo de permisos §30), el backend nunca lo devuelve en `modulos_permitidos`, así que `menu.js` hace `a.hidden=true` y **el ítem desaparece para TODOS los usuarios, admin incluido**.

**Why:** la UI del sidebar se filtra por permisos, y el catálogo `modulos` es la fuente. Sin fila, el módulo es invisible aunque el código React esté perfecto y deployado. Es un gap fácil de olvidar porque §12 paso 4 solo decía "agregá el `<a data-modulo>`" sin mencionar la fila en DB.

**How to apply:** al crear un módulo React con `data-modulo`, insertar la fila con migración formal aplicada en local Y prod (§24):
```sql
INSERT INTO modulos (modulo_codigo, nombre, descripcion, min_nivel_acceso, activo, id_municipio)
VALUES ('<codigo>', '<Nombre>', '<desc>', <nivel>, TRUE, 1)
ON CONFLICT (modulo_codigo) DO NOTHING;
```
- `min_nivel_acceso` = el nivel mínimo que ve el módulo (2 = supervisor/admin, 4 = todos). Debe coincidir con el gating del módulo React (`WrapNivel`) y con el guard del backend.
- Verificar ANTES con `SELECT ... FROM modulos WHERE modulo_codigo='<codigo>'` — si ya existe (raro), no duplicar.
- Si el módulo es informativo (debe verlo cualquiera), NO le pongas `data-modulo` — ej. Guías queda sin él.

**Detalle del gating doble:** el gate por nivel del propio módulo React (`useAuthStore(s => s.user.nivel_acceso <= N)`) es independiente del filtro del sidebar. Un admin puede ENTRAR por deep-link aunque su sesión cacheada no tenga el código (cazado: la sesión vieja no tenía `encuestas` en `modulos_permitidos` pero el admin entró igual por nivel). Pero el ÍTEM del sidebar solo aparece cuando (a) la fila existe en `modulos` y (b) la sesión se refrescó (`/auth/me` al re-loguear). Aviso a usuarios: cerrar sesión y volver a entrar para ver el ítem nuevo.

Cazado 2026-05-26: módulo Encuestas deployado, pero el ítem "encuestas" no salía en el sidebar hasta crear la fila `encuestas` en `modulos` (mig 61, local+prod).

## Memorias relacionadas
- [[feedback_verificar_drift_completo_prod]] — verificar el schema/seeds en prod antes de asumir.
- [[guard_nivel_endpoint_no_solo_ui]] — el filtro del sidebar NO protege el endpoint; el backend debe validar nivel igual.
