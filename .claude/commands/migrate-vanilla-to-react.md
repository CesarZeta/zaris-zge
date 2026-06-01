# migrate-vanilla-to-react

Receta probada para migrar un módulo `frontend/<modulo>.html` + `frontend/js/<modulo>.js` vanilla a un módulo React embebido en iframe del shell vanilla. Patrón validado con Agenda (2026-05-10) y Ciudadanos (2026-05-12).

## Cuándo usar

Cuando se decida promover un módulo vanilla a React. Hoy son candidatos: Reclamos, OT (3 mesas), Empresas, Usuarios, Admin Tablas.

**Antes de invocar:** verificar con `wc -l frontend/<modulo>.html frontend/js/<modulo>.js` que el alcance es realista para la sesión. >1500 LOC = ofrecer dividir vía `AskUserQuestion` (ver `feedback_calibrar_alcance_migracion`).

## Cómo invocar

`/migrate-vanilla-to-react modulo:ciudadanos endpoint_prefix:/api/v1/buc modulo_codigo:padrones`

Argumentos:
- `modulo:<nombre>` — nombre del módulo (slug). Será el id del módulo React.
- `endpoint_prefix:<prefix>` — prefix de los endpoints backend (ej `/api/v1/buc`, `/api/v1/reclamos`).
- `modulo_codigo:<codigo>` — `moduloCodigo` para permisos §30 (ej `padrones`, `reclamos`, `ot_supervisor`).

## Pasos que ejecuta

### 1. Inventario y drift check
- `wc -l frontend/<modulo>.html frontend/js/<modulo>.js` — calibrar alcance.
- `grep "@router\." backend/app/api/routes/<modulo>.py` — listar endpoints.
- Verificar drift en prod via `mcp__claude_ai_Supabase__execute_sql` (regla §24):
  - Existencia de tablas referenciadas.
  - CHECKs, defaults, NOT NULLs en columnas que se van a usar en INSERT/PUT.
  - Conteos de catálogos.
- Leer schemas Pydantic en `backend/app/schemas/<modulo>.py` para tipos exactos.
- Leer `frontend/js/<modulo>.js` para flujos no obvios (validaciones, lookups, modos del form).

### 2. Estructura del módulo

Crear en `web-app/src/modules/<modulo>/`:

```
<modulo>/
  index.tsx                      → ModuleManifest (id, label, icon, moduloCodigo, routes)
  <Modulo>Layout.tsx              → breadcrumb + título (sin tabs si flujo lineal, con tabs si vistas paralelas)
  types/<entidad>.ts              → mirror del schema Pydantic
  api/<modulo>Api.ts              → wrappers de api.ts para cada endpoint
  hooks/use<Modulo>.ts            → useQuery/useMutation con queryKeys consistentes
  lib/<helpers>.ts                → validaciones específicas (CUIL, normalizar, formatear)
  views/
    BuscarView.tsx                → home: buscar + preview últimos + acciones
    FormView.tsx                  → alta/edición/consulta, modo derivado de URL
    ListView.tsx                  → listado con filtros + imprimir
  components/
    <Modulo>Form.tsx              → form principal
    <SubForm>.tsx                 → sub-paneles expandibles si aplica
```

### 3. Registrar el módulo
- `web-app/src/modules/index.ts` — agregar import y push al array `modules`.

### 4. Reglas obligatorias del módulo (CLAUDE.md §12)
- Router `createHashRouter` (heredado del AppShell).
- `api.ts` lee `import.meta.env.VITE_API_BASE`.
- Auth via `useAuthStore` (lee `zaris_session` con shape dual).
- **NO** UI propia de navegación (sidebar/topbar) — vive en el shell vanilla.
- Tokens DS (`var(--zaris-orange)`, etc.), no colores hardcoded.
- `useNotificationsStore.push({kind, title, body?})` para toasts.
- `ConfirmModal` (de `agenda/components`) en lugar de `window.confirm`.

### 5. Validación local

```bash
# TypeScript
cd web-app && node_modules/.bin/tsc --noEmit

# Build dev rápido
cd web-app && node_modules/.bin/vite build --mode development
```

Levantar dev server detached:
```powershell
Start-Process -FilePath "node_modules/.bin/vite.cmd" `
  -ArgumentList "--host","127.0.0.1","--port","5173" `
  -WorkingDirectory "<path>/web-app" -WindowStyle Hidden
```

### 6. Testing en browser MCP (sin setters sintéticos)

Setters via `dispatchEvent` NO disparan re-render de React (ver `feedback_browser_mcp_react_setup`). Patrón validado:

```js
// 1. Login imperativo via fetch directo
const r = await fetch('http://localhost:8000/api/v1/auth/login', {
  method: 'POST', headers: {'Content-Type':'application/json'},
  body: JSON.stringify({email:'ciudadanovl@municipio.gob.ar', password:'123456'})
});
const data = await r.json();
// Doble shape para que tanto api.ts como helpers vanilla lo lean
localStorage.setItem('zaris_session', JSON.stringify({
  state: {accessToken: data.access_token, user: data.user},
  version: 0, access_token: data.access_token, user: data.user
}));

// 2. Crear entidad via API (no via form UI)
const cre = await fetch('http://localhost:8000/api/v1/<endpoint>', {
  method: 'POST', headers: {'Content-Type':'application/json', Authorization: 'Bearer ' + data.access_token},
  body: JSON.stringify({...})
});

// 3. Navegar a la URL del módulo (browser_navigate)
// 4. Verificar hidratación con browser_eval (querySelectorAll de inputs)
```

Credenciales dev locales: `ciudadanovl@municipio.gob.ar / 123456` (admin nivel 1). Ver `feedback_smoke_credenciales_dev`.

### 7. Build prod limpio

**Cerrar terminales con env vars de Vite seteadas.** `VITE_API_BASE` exportado en el shell pisa los `.env` files (§32 quirk 1).

```bash
cd web-app && node_modules/.bin/vite build
grep -o "https://zaris-api[a-z0-9.-]*" dist/assets/index-*.js | head -1
grep -c "127.0.0.1\|localhost:8000" dist/assets/index-*.js  # debe ser 0
```

Si el bundle apunta a localhost, abortar y rebuildar en terminal limpia.

### 8. Update shell vanilla
- `index.html` — cambiar `<a class="nav__link" href="frontend/<modulo>.html" data-modulo="<modulo_codigo>">` a `<a class="nav__link" href="web-app/dist/index.html#/<modulo>" data-modulo="<modulo_codigo>">`.

### 9. Borrar vanilla (decisión §4)
- `rm frontend/<modulo>.html frontend/js/<modulo>.js`.
- Si comparte JS con otros módulos (`config.js`, `validaciones.js`), NO borrarlos.

### 10. Commit + push + smoke prod
- `git add -A && git commit -m "feat(<modulo>): migrar <modulo> vanilla a React"`.
- `git push origin main` — el workflow `.github/workflows/deploy-web-app.yml` rebuildea `web-app/dist/` automáticamente.
- Smoke: `https://cesarzeta.github.io/zaris-zge/index.html` → sidebar correspondiente → debe cargar bundle.
- Actualizar tabla en CLAUDE.md §4 "Estado real de cada módulo" marcando el módulo como React.
- Actualizar `project_estado_sesion_y_pendientes.md`.

## Reglas

- **No** migrar a React módulos chicos o simples (admin_tablas genérico, login). Vanilla está bien para eso.
- **No** prometer "migrar 3 módulos en una sesión" — cada uno es >1500 LOC vanilla típicamente.
- **No** asumir paridad pixel-perfect con el vanilla. Toasts, modales y flujos se pueden simplificar. Documentar lo no migrado.
- **No** instalar libs nuevas sin pedir — el stack hoy es Vite + React + react-router + react-query + zustand + Lucide. Date nativo, no date-fns (ver CLAUDE.md §28).

## Lecciones del proyecto que motivan esta skill

- 2026-05-10: Agenda migrada a React. Primer caso del patrón.
- 2026-05-12: Ciudadanos migrado. Refinó el patrón con: doble shape de session, testing via API + navegación, listado client-side, sub-form anidado (empresa vinculada).

Memorias relacionadas: [[project_patron_deploy_modulo_react]], [[feedback_browser_mcp_react_setup]], [[feedback_calibrar_alcance_migracion]], [[project_proxy_local_zaris_zge]].
