---
name: modulo-config
description: "Usar al trabajar en el módulo Config (React, admin-only) de ZARIS (archivos: web-app/src/modules/config/ — IdentidadView, UsuariosPermisosView, CatalogoModulosView, SistemaView, ParametrosSistemaView, api/configApi.ts, hooks/useConfig.ts, lib/shellNav.ts; endpoints: /api/v1/config/identidad, /api/v1/admin/permisos/*, /api/v1/admin/configuracion_general). Cubre los 4 tabs (Identidad, Permisos por usuario, Catálogo de módulos, Sistema tipado), los bugs de navegación en iframe (window.location absoluto, NavLink relativo) y el quirk de configuracion_general.tipo NOT NULL en prod. Invocar ANTES de tocar cualquier tab, endpoint o navegación del módulo Config."
---

# Módulo Config (React) + estándar de verificación en la interfaz — §41

> **Nota:** el "Estándar OBLIGATORIO: verificar navegación/UI en la interfaz" (parte de §41) es una regla **transversal** y permanece en CLAUDE.md §41 — aplica a cualquier módulo React, no solo Config. Acá vive solo lo específico del módulo Config.

Módulo React `web-app/src/modules/config/` (ítem "configuración" del sidebar, `data-modulo="admin_tablas"` desde §39). Es admin-only — el backend exige `nivel_acceso=1` en `require_admin` (los endpoints de identidad y permisos). 4 tabs en `ConfigLayout`:

| Tab | Vista | Endpoint backend | Qué hace |
|---|---|---|---|
| Identidad | `IdentidadView` | `GET/PUT /api/v1/config/identidad` (+ `/logo-upload-url`) | Nombre y logo del municipio en el topbar. `app_nombre` ('GESTION ESTADO') es interno, NO editable (§14) — el PUT lo ignora. |
| Permisos por usuario | `UsuariosPermisosView` | `GET /api/v1/admin/permisos/usuarios/{id}/modulos` + `PUT` | Matriz de overrides por módulo (§30). Lista usuarios vía `GET /api/v1/admin/usuarios` (handler genérico admin_tablas). |
| Catálogo de módulos | `CatalogoModulosView` | `GET /api/v1/admin/permisos/modulos` + `PUT /{codigo}` | Editar `min_nivel_acceso` de cada módulo. |
| Sistema | `SistemaView` + `ParametrosSistemaView` | `GET /api/v1/admin/configuracion_general` + `PUT /{id_config}` | **Desde 2026-05-25:** pantalla de ajustes agrupada y tipada (toggle/number/text/color) sobre `configuracion_general`, secciones Encuestas / Reclamos y OT / App Vecinos / Otros. Debajo, atajos a Municipios/Maestros. Ver [[reference_config_sistema_pantalla_tipada]]. Clave nueva: seed (mig) + leer backend + sumar a `SECCIONES`. **`configuracion_general.tipo` es NOT NULL en PROD (`string`/`boolean`/`integer`) pero NO existe en local** (drift cazado 2026-06-01, §24) — al insertar una clave nueva en prod, **incluir `tipo`** o el INSERT falla con `null value in column "tipo"`; el seed que corra en ambos entornos debe detectar la columna (`information_schema.columns`) y armar el INSERT con/sin `tipo` según exista (patrón en `migrations/75b_tramites_retencion_config.sql`). `municipio_nombre`/`logo` ocultos acá (se editan en Identidad). El item "usuarios" se quitó del sidebar del shell (sigue accesible acá vía atajo "Usuarios del sistema"). |

**Cliente API:** `web-app/src/modules/config/api/configApi.ts` + hooks en `hooks/useConfig.ts`. Los 3 endpoints existen, están registrados en `main.py` y las shapes coinciden. Verificado end-to-end en navegador 2026-05-22.

### Bugs de navegación cazados y resueltos (2026-05-22) — referencia para módulos React en iframe

Tres bugs distintos en este módulo, todos de **navegación**, ninguno detectable leyendo el código solo (ver estándar en CLAUDE.md §41):

1. **`window.location.href` absoluto rompe bajo `/zaris-zge/`** (commit `3ea2847`). `SistemaView` e `ConfigLayout` (botón INICIO) caían a `window.location.href = '/${href}'` en el fallback → salta a `cesarzeta.github.io/${href}` SIN el subpath → 404 de GH Pages en el iframe (§32 Quirk 13). **Fix:** helper compartido `web-app/src/lib/shellNav.ts` (`shellNavigate` + `shellGoInicio`) que delega en `window.parent.shellNavigate` y solo en standalone dev resuelve el subpath. **Reusar este helper en cualquier módulo React que navegue al shell** en vez de reinventar el patrón.
2. **`NavLink to="x"` relativo expulsa al dashboard** (commit `9105dbf`). Los tabs usaban `to="permisos"` (relativo): estando en `/config/identidad`, React Router lo resolvía a `/config/identidad/permisos` (ruta inexistente) → catch-all `path:'*'` en `routes.tsx` → redirect a `/dashboard`. Solo se notaba **al clickear una tab** (la primera carga directa por URL funcionaba). **Fix:** paths ABSOLUTOS `to="/config/<tab>"`. **Regla:** en layouts con tabs internas usar paths absolutos, no relativos — el relativo anida contra la ruta actual completa.
3. **Tipos del API mentían** (commit `a04878c`, deuda menor): `app_nombre` figuraba en `IdentidadUpdate` (lo ignora el PUT) y `listarUsuarios` mandaba `?limit=200` que el handler genérico ignora. Alineados con el backend real.

### `admin_tablas` configuracion_general — mostrar `descripcion` en la preview (2026-05-22)

La tabla `configuracion_general` tiene columna `descripcion` con texto útil por parámetro, pero la vista previa de `admin_tablas.html` mostraba solo `clave` + `valor` (vía `composeLabel`/`composeMeta` genéricos). El admin veía claves crudas sin saber qué hacen. **Fix** (commit `b32b71f`): caso especial en `renderVistaPrevia` para `tablaActual === 'configuracion_general'` que renderiza clave + descripción en gris debajo + valor a la derecha. `configuracion_general` **no tiene columna `activo`** (sin baja lógica) — borrar registros de basura es DELETE físico, no soft-delete.
