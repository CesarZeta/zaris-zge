---
name: modulo-permisos
description: "Usar al trabajar en el sistema de permisos por módulo de ZARIS (archivos: backend/app/core/auth.py, routes/admin_permisos.py, frontend/js/menu.js, web-app/src/app/Sidebar.tsx, ModuleManifest; tablas: modulos, usuario_modulos). Modelo híbrido nivel mínimo por módulo + override por usuario. Cubre el catálogo de módulos, modulos_permitidos/require_modulo, los endpoints /admin/permisos, el filtrado del sidebar (data-modulo + data-modulo-fallback) y la trampa de seguridad (ocultar en UI NO protege endpoints). Invocar ANTES de tocar el catálogo de módulos, overrides por usuario, o el filtrado de items del sidebar por permiso."
---

# Permisos por módulo — §30

§3 define `nivel_acceso ∈ {1=Admin, 2=Supervisor, 3=Operador, 4=Consultor}` — un rol único, jerárquico. Para control fino del tipo "Juan es supervisor pero solo de Reclamos, no debe ver Agenda ni Admin Tablas" se aplica el modelo híbrido descripto acá. **Implementado** en mig 38 (2026-05-12) + mig 44 (2026-05-14 separa `agenda`/`turnos`/`entradas`). Las subsecciones que mencionan "schema futuro" o "cuando se implemente" son textos heredados del diseño; el "Estado actual" al final de la sección es la referencia operativa.

### Modelo: nivel mínimo por módulo + override por usuario

Cada módulo declara su **nivel mínimo de acceso** (default). Si el `nivel_acceso` del usuario lo alcanza, ve el módulo. Adicionalmente, una tabla nueva `usuario_modulos` permite **override** explícito por usuario:

- Fila con `permitido = TRUE` → el usuario ve el módulo aunque su nivel sea más alto que el mínimo (otorga acceso).
- Fila con `permitido = FALSE` → el usuario NO ve el módulo aunque su nivel sí lo permitiría (bloquea acceso).
- Sin fila → cae al default por nivel.

### Implementación (mig 38 + 44, local + prod)

Tablas `modulos` (catálogo: `modulo_codigo` PK, `nombre`, `descripcion`, `min_nivel_acceso` SMALLINT default 4) + `usuario_modulos` (override por usuario: `(id_usuario, modulo_codigo)` UNIQUE, `permitido` BOOL, §10). Catálogo (filas principales — la fuente real es la tabla `modulos`, que además tiene `tramites`, `encuestas`, `bi`):

| Código | Nombre | min_nivel_acceso | Cubre |
|---|---|---|---|
| `emergencias` | Emergencias | 3 | módulo React `emergencias` — COM (mig 84, §44) |
| `reclamos` | Reclamos | 4 | módulo React `reclamos` |
| `padrones` | Padrones | 4 | módulos React `ciudadanos` + `empresas` |
| `ot_agente` | OT - Agente | 3 | módulo React `ot` (vista Agente) |
| `agenda` | Agenda | 3 | módulo React `agenda` — sustrato de disponibilidad horaria de agentes/espacios |
| `turnos` | Turnos | 3 | módulo React `turnos` — backoffice de turnos de atención (tabla `turnos`, mig 45) |
| `entradas` | Entradas | 3 | módulo React `entradas` — backoffice de eventos con cupo en espacios físicos |
| `ot_supervisor` | OT - Supervisor | 2 | módulo React `ot` (vista Supervisor) |
| `ot_auditoria` | OT - Auditoría | 2 | módulo React `ot` (vista Auditoría) |
| `usuarios` | Usuarios | 1 | `frontend/usuarios.html` (pantalla propia — admin_tablas no hashea password) |
| `admin_tablas` | Maestros | 1 | resto de `frontend/admin_tablas.html?tabla=*` |

**Backend (`core/auth.py`):** `modulos_permitidos(db, id_usuario, nivel) -> list[str]` (defaults por nivel + overrides) · `require_modulo(modulo)` dependency factory (devuelve `current_user`, 403 si falta). `POST /auth/login` y `GET /auth/me` incluyen `modulos_permitidos`.

**Endpoints (`admin_permisos.py`, `/api/v1/admin/permisos`):** GET `/modulos` · PUT `/modulos/{codigo}` (editar `min_nivel_acceso`) · GET `/usuarios/{id}/modulos` · PUT `/usuarios/{id}/modulos` (set bulk overrides). **Orden crítico**: `admin_permisos_router` ANTES de `admin_tablas_router` en `main.py` (sino `/{tabla}` greedy atrapa `/permisos/*` → 422 `int_parsing`, §5).

**Frontend vanilla (`menu.js`):** filtra items por `data-modulo` ∉ `modulos_permitidos`. **`data-modulo-fallback="cod1,cod2"`** (CSV): el item se muestra si CUALQUIER código (principal + fallback) está permitido — necesario cuando un bundle cubre varios sub-permisos (OT supervisor/agente/auditoría). Sin fallback, OT desaparecía para el operador (cazado 2026-05-12). Sesión vieja sin `modulos_permitidos` cacheado → refresca contra `/me`, fail-open en UI (el guard real está en backend).

**Frontend React (`localhost:5173`):** `ModuleManifest.moduloCodigo?: string` (lo usan agenda/turnos/entradas/padrones); `Sidebar.tsx` filtra, fail-open; `useAuthStore.refreshSession()` rehidrata desde `/me`.

> **TRAMPA DE SEGURIDAD recurrente:** que el sidebar oculte un módulo NO protege sus endpoints. `require_modulo` casi no se usa — la mayoría de routers aplican su nivel con helpers locales (`_require_gestion`, `_require_supervisor`). Hasta 2026-05-20 el router OT no chequeaba nivel y un operador con JWT creaba OT por curl (QA #2). **Antes de asumir "el router ya valida nivel", leé el handler.** Ver [[guard_nivel_endpoint_no_solo_ui]].
