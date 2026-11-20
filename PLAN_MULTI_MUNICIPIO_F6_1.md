# IT-01 F6.1 — Ajustes de las cuentas internas: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** que una sesión con clave temporal solo sirva para cambiar la clave, y que el corte de sesiones abiertas valga para todos los niveles.

**Architecture:** las dos reglas viven en `get_current_user` (`backend/app/core/auth.py`), por donde pasa toda request de un funcionario. La marca `usuarios.sesiones_validas_desde` (F3b) se pone en cada cambio de clave y se exige a todos los niveles; `POST /auth/cambiar-password` devuelve un token nuevo, y los tres clientes lo adoptan **antes** de que el backend empiece a cortar.

**Tech Stack:** FastAPI + SQLAlchemy async (backend), HTML vanilla (`frontend/login.html`), React + Vite (`web-app`, `zaris-agentes`).

**Spec:** [`PLAN_MULTI_MUNICIPIO_F6_DISENO.md`](PLAN_MULTI_MUNICIPIO_F6_DISENO.md) §4.9.

## Global Constraints

- Rutas que una sesión con clave temporal puede usar: exactamente `/api/v1/auth/me` y `/api/v1/auth/cambiar-password`. Cualquier otra: **403** con `detail` = `"Tenés que cambiar tu contraseña antes de seguir."`.
- La marca se escribe siempre como `date_trunc('second', NOW())` (los `iat` son segundos enteros; un token emitido en el mismo segundo que la marca sigue valiendo).
- Sin migración: la columna `sesiones_validas_desde` existe en local y prod desde la 128b.
- Los clientes se publican antes que el backend (CLAUDE.md §9, contrato que cambia entre deploys independientes).
- Smokes solo locales, con mail en MOCK (`settings.RESEND_API_KEY = ""`), datos de prueba se conservan.
- Diferencia con el diseño §4.9 [Claude]: el 403 lleva un texto fijo y no un código que los clientes interpreten. Ninguno lo necesita: el login del shell no guarda la sesión hasta que se cambia la clave, y la app de agentes manda a `/cambiar-clave` antes de cualquier otra pantalla (verificado en `login.html` y `RutaProtegida.tsx`).

## Review Focus

1. **Una cuenta con la sesión abierta pasa a tener clave temporal:** la persona tendría que terminar en la pantalla de cambio, no en un shell que responde 403 en todos lados. Verificado el 2026-11-20: hoy no hay ninguna vía que lo haga. `UsuarioUpdate` no tiene `debe_cambiar_password`; la marca solo se pone en el alta de la cuenta (`cuenta_zaris`) y en el login por vencimiento (`login_interno`, antes de emitir el token). Sin test. **Regla para el futuro:** quien agregue una vía que marque el cambio obligatorio sobre una cuenta existente llama también a `cortar_sesiones`.
2. **El super cambia su propia clave:** el token nuevo tiene que seguir siendo de super (`sa`, 8 h) y conservar el segundo factor. → Task 3, test `caso_super_cambia_clave` (SKIP si no hay super local).
3. **Un cliente viejo cacheado** que ignora el token nuevo: después de cambiar la clave, su próxima request da 401 y vuelve al login. Es la degradación aceptada; no hay test, la mitiga el orden de deploy (Task 4).
4. **Dos sesiones de la misma persona** (shell y app de agentes): al cambiar la clave desde una, la otra da 401. → Task 3, test `caso_cambio_voluntario_corta_otra_sesion`.
5. **Restablecer por el link del mail («olvidé mi contraseña»)** con una sesión abierta en otro dispositivo: esa sesión se corta. → Task 3, test `caso_recovery_corta_sesion`.

---

### Task 1: Los tres clientes adoptan el token que devuelve el cambio de clave

Compatible hacia atrás: si la respuesta no trae `access_token` (backend actual), todo sigue como hoy.

**Files:**
- Modify: `frontend/login.html:611-629` (handler del cambio forzado)
- Modify: `web-app/src/modules/perfil/api/perfilApi.ts:57-71` (`cambiarPassword`)
- Modify: `zaris-agentes/src/lib/auth.ts:54-61` (`cambiarPassword`) y `zaris-agentes/src/lib/session.ts` (nueva `reemplazarToken`)

**Interfaces:**
- Consumes: respuesta de `POST /api/v1/auth/cambiar-password` = `{ ok: true, debe_cambiar_password: false, access_token?: string }` (el campo lo agrega la Task 3).
- Produces: `reemplazarToken(token: string): void` en `zaris-agentes/src/lib/session.ts` — pisa `access_token` conservando `user` y notifica (mismo patrón que `actualizarUsuario`).

- [ ] **Step 1:** `login.html`: en el `res.ok`, persistir `data.access_token || _tokenTemporal` en lugar de `_tokenTemporal`.
- [ ] **Step 2:** `perfilApi.ts`: en `res.ok`, leer el JSON; si trae `access_token`, `useAuthStore.getState().login(access_token, useAuthStore.getState().user!)` (el storage dual escribe las dos formas y el shell lo toma por el evento `storage`, §29).
- [ ] **Step 3:** `zaris-agentes`: `cambiarPassword` toma la respuesta de `apiPost` y, si trae `access_token`, llama a `reemplazarToken` antes de `actualizarUsuario({ debe_cambiar_password: false })`.
- [ ] **Step 4:** Verificar tipos.
  Run: `cd web-app; pnpm typecheck` y `cd ..\..\zaris-agentes; pnpm typecheck` (o `pnpm build` si no hay script)
  Expected: sin errores.
- [ ] **Step 5:** Verificar en local contra el backend actual (sin token nuevo): login del shell con una cuenta de clave temporal → cambio → entra al shell; «Mi perfil» → cambio voluntario → sigue logueado. Navegando, no por código (§41).
- [ ] **Step 6:** Commit en cada repo (`zaris-zge`: login.html + perfilApi.ts; `zaris-agentes`: auth.ts + session.ts) y push a `main` de los dos. Confirmar en Cloudflare Pages que publicaron (`/version.json` de `zge.zaris.com.ar` y de `agentes.zaris.com.ar` con el commit nuevo).

---

### Task 2: La clave temporal solo habilita el cambio de clave

**Files:**
- Modify: `backend/app/core/auth.py` (constantes + chequeo al final de `get_current_user`)
- Create: `backend/smoke_cuentas_f6_1.py`

**Interfaces:**
- Produces: `RUTAS_CON_CLAVE_TEMPORAL: frozenset[str]` y `CLAVE_TEMPORAL: str` en `app/core/auth.py`.

- [ ] **Step 1: Escribir el smoke** (`smoke_cuentas_f6_1.py`, patrón de `smoke_reclamo_alta_mail.py`: ASGITransport, aborta si no es `zaris_dev`, mail capturado). Crea por SQL una cuenta de prueba nivel 3 del municipio 1 con email único `f61-<aleatorio>@municipio.gob.ar`, `password_hash = hash_password("Temporal-123")` y `debe_cambiar_password = TRUE`. Caso `caso_clave_temporal`:
  - login → 200 con `user.debe_cambiar_password == True`;
  - `GET /api/v1/reclamos` con ese token → 403 y `detail == CLAVE_TEMPORAL`;
  - `GET /api/v1/auth/me` → 200;
  - `POST /api/v1/auth/cambiar-password {password_nueva: "Nueva-12345"}` → 200;
  - con el token que corresponda (el nuevo si vino, si no el mismo) `GET /api/v1/reclamos` → 200.
- [ ] **Step 2:** Correrlo. Run: `cd backend; $env:ENV_FILE=".env.local"; $env:PYTHONPATH="."; python smoke_cuentas_f6_1.py` — Expected: FAIL en «403 con clave temporal» (hoy da 200).
- [ ] **Step 3:** En `get_current_user`, después de validar la cuenta y antes de devolver (las dos ramas, super y municipio): si `user.debe_cambiar_password` y `request.url.path not in RUTAS_CON_CLAVE_TEMPORAL` → `HTTPException(403, CLAVE_TEMPORAL)`.
- [ ] **Step 4:** Correr el smoke — Expected: `caso_clave_temporal` en verde. Correr también `smoke_cuentas_funcionario.py` (login con temporal + cambio forzado) — Expected: sin FAIL nuevos.
- [ ] **Step 5:** Commit (`feat(auth): la clave temporal solo habilita el cambio de clave`).

---

### Task 3: Corte de sesiones para todos los niveles y token nuevo al cambiar la clave

**Files:**
- Modify: `backend/app/core/auth.py` (`get_current_user`; helper nuevo)
- Modify: `backend/app/api/routes/auth.py` (`cambiar_password`, `resetear_password_interno`)
- Modify: `backend/app/api/routes/buc.py:231-289` (`modificar_usuario`)
- Modify: `backend/smoke_cuentas_f6_1.py`
- Modify: `CLAUDE.md` §1 (párrafo «Guard» del segundo factor) y `.claude/skills/modulo-usuarios/SKILL.md`

**Interfaces:**
- Consumes: `RUTAS_CON_CLAVE_TEMPORAL`, `CLAVE_TEMPORAL` (Task 2).
- Produces:
  - `async def cortar_sesiones(db: AsyncSession, id_usuario: int) -> None` en `app/core/auth.py`: `UPDATE usuarios SET sesiones_validas_desde = date_trunc('second', NOW())`; no commitea (lo hace el llamador, en la misma transacción que el cambio).
  - `def token_nuevo_para(current_user: dict, segundo_factor: bool) -> str` en `app/core/auth.py`: super → `crear_token_super_admin(id, segundo_factor=…)`; resto → `create_access_token({"sub", "mun": id_municipio, "sf": …})`.
  - `get_current_user` deja `request.state.sesion_sf = payload.get("sf") is True`.
  - `POST /auth/cambiar-password` responde `{ ok, debe_cambiar_password: false, access_token }`.

- [ ] **Step 1: Sumar al smoke** los casos (cada uno con su propia cuenta de prueba nivel 3, creada como en la Task 2 pero sin clave temporal):
  - `caso_cambio_voluntario_corta_otra_sesion`: dos logins (tokens A y B); cambio voluntario con A → respuesta trae `access_token` (C); `GET /auth/me` con B → 401; con A → 401; con C → 200.
  - `caso_admin_cambia_clave`: login de la cuenta (token A); el admin `ciudadanovl@` hace `PUT /api/v1/buc/usuarios/{id} {password: "OtraClave-123"}` → 200; `GET /auth/me` con A → 401.
  - `caso_recovery_corta_sesion`: login (A); fijar por SQL `token_recovery = gen_random_uuid()`, `token_recovery_expira = NOW() + interval '1 hour'` y leerlo; `POST /auth/resetear-password {token, password_nueva}` → 200; A → 401.
  - `caso_super_cambia_clave`: si existe en local una cuenta nivel 0 activa con email conocido por el smoke de super (`smoke_super_admin.py`), login, cambio voluntario y luego decodificar el token nuevo: `sa == True`; si no existe, SKIP.
  - `caso_sin_marca_sigue_igual`: una cuenta nivel 4 sin marca (`sesiones_validas_desde NULL`) entra y opera como siempre.
- [ ] **Step 2:** Correr el smoke — Expected: FAIL en los cuatro primeros casos (hoy la marca solo rige para 0/1 y no se pone al cambiar la clave).
- [ ] **Step 3:** `get_current_user`: el chequeo de la marca sale del `if requiere_segundo_factor(...)` y rige para todos los niveles; el chequeo de `sf` queda donde está. Guardar `request.state.sesion_sf`.
- [ ] **Step 4:** `cambiar_password`: en la misma transacción del UPDATE, `cortar_sesiones`; después del commit, `token_nuevo_para(current_user, request.state.sesion_sf)` en la respuesta. Agregar `responses={200: {"description": "Devuelve access_token: la sesión nueva (las demás quedan cortadas)."}}` al decorador (marcador OpenAPI para verificar el deploy, §9). `resetear_password_interno`: `cortar_sesiones` en la misma transacción.
- [ ] **Step 5:** `modificar_usuario`: `cortar_sesiones(db, id)` si `update_data` trae `password_hash`.
- [ ] **Step 6:** Correr el smoke — Expected: todo en verde. Correr también `smoke_segundo_factor.py`, `smoke_super_admin.py` y `smoke_cuentas_funcionario.py` — Expected: sin FAIL nuevos.
- [ ] **Step 7:** Verificar navegando en local (shell + bundle local + uvicorn local): cambio forzado desde el login, cambio voluntario desde «Mi perfil» (sigue logueado; otra pestaña con otra sesión vuelve al login al recargar).
- [ ] **Step 8:** Docs: CLAUDE.md §1, párrafo «Guard» del segundo factor: la marca rige para todos los niveles, se pone en todo cambio de clave y al marcar el cambio obligatorio, y la clave temporal solo habilita `/auth/me` y `/auth/cambiar-password`. Misma regla en la skill `modulo-usuarios`.
- [ ] **Step 9:** Commit (`feat(auth): corte de sesiones para todos los niveles y sesion nueva al cambiar la clave`).

---

### Task 4: Publicación y verificación en prod

- [ ] **Step 1:** Confirmar que la Task 1 ya está publicada en los dos sitios (`/version.json` con su commit). Si no, esperar: el backend no sale antes.
- [ ] **Step 2:** `git grep -niE "h[u]sky"` vacío; push del backend a `main`.
- [ ] **Step 3:** Esperar a que `/api/health` informe el commit nuevo; confirmar el marcador en `/openapi.json` (`cambiar-password` con «Devuelve access_token»).
- [ ] **Step 4:** Verificación en prod sin tocar claves reales: login de una cuenta de prueba de nivel 3 (credenciales en `credenciales-testing/`, por script, §40) → `GET /auth/me` 200 y `GET /reclamos` 200 (la cuenta sin marca sigue operando). El recorrido del cambio de clave en prod lo hace César con su cuenta si quiere verlo; la regla queda probada por el smoke.
- [ ] **Step 5:** ESTADO.md: F6.1 en «Hecho reciente»; F6.2 como siguiente.
