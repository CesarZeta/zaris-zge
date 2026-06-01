# audit-shell

Verifica la integridad del shell ZARIS: que todos los `nav__link` apunten a rutas válidas, que cada módulo tenga el guard de sesión correcto, y que el patrón iframe esté aplicado en todos los frontends.

## Pasos

### 1. Auditar `index.html` — nav__link hrefs

Leer `index.html` y extraer todos los `href` de elementos `nav__link`. Para cada uno:
- Verificar que el archivo existe en el filesystem.
- Si apunta a `web-app/dist/index.html#/<modulo>` (módulo React), verificar que el módulo existe en `web-app/src/modules/<modulo>/`.
- Verificar que no es un `nav__link--stub` apuntando a una ruta real (debería apuntar a `#`).
- Reportar rutas rotas o inconsistencias.

### 1b. Auditar `data-modulo` (permisos §30)

Cada `<a class="nav__link">` que apunta a un módulo real debe tener `data-modulo="<codigo>"`. El código debe existir en la tabla `modulos` (consultar via Supabase o local). Reportar:
- Links sin `data-modulo` (el filtro por permisos no los va a poder ocultar).
- Links con `data-modulo` cuyo código no está en la tabla `modulos`.

### 2. Auditar guard de sesión en módulos frontend

Para cada archivo HTML en `frontend/` (excluyendo `login.html` y `welcome.html`):
- Verificar que tiene el guard de sesión con el patrón correcto:
  ```js
  if (!localStorage.getItem('zaris_session')) {
    if (window.self !== window.top) { window.parent.location.href = '../index.html'; }
    else { window.location.href = '../index.html'; }
  }
  ```
- Reportar archivos que usan el patrón incorrecto (ej: redirigen a `login.html` directamente desde el iframe).

### 3. Auditar guard iframe — ocultar header y sidebar

Para cada archivo HTML en `frontend/` que tenga `.z-header` o `.sidebar` propio:
- Verificar que tiene el script inline en `<head>` que inyecta CSS para ocultar esos elementos cuando corre en iframe.
- Patrón esperado: `if (window.self !== window.top) { var s = document.createElement('style'); s.textContent = '...'; document.head.appendChild(s); }`

### 4. Auditar admin_tablas SCHEMAS

Leer `frontend/admin_tablas.html` y verificar:
- Que cada tabla en `SCHEMAS` tiene un campo `titulo` definido con el formato "Maestro de X".
- Que cada tabla en `SCHEMAS` tiene el panel de búsqueda celeste (`search-panel`) en sus templates `cargarTabla` y `renderVistaPrevia`.
- Que el `TABLE_CONFIG` en `backend/app/api/routes/admin_tablas.py` tiene entrada para cada tabla listada en el sidebar de `index.html`.

### 5. Resumen

Reportar:
- ✅ Items que pasaron
- ⚠️ Items con advertencias (funciona pero no es el patrón ideal)
- ❌ Items con errores (rotos o faltantes)

Con lista de acciones correctivas ordenadas por prioridad.

## Notas

- Este audit es de solo lectura — no modifica nada.
- Si hay inconsistencias en TABLE_CONFIG vs. SCHEMAS, es probable que el módulo cargue pero falle al hacer fetch al backend.
- `frontend/shell.html` fue eliminado el 2026-05-12 (CLAUDE.md §31). Si reaparece, reportarlo como archivo huérfano.
