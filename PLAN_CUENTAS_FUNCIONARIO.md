# PLAN — Circuito de alta de cuentas ZARIS (funcionario desde la ficha del ciudadano)

> Diseño aprobado por César el 2026-10-12. Este archivo es la especificación + plan por fases;
> el estado de avance vive en [`ESTADO.md`](ESTADO.md).
>
> **Estado: F1-F5 ENTREGADAS y en prod el 2026-10-12** (mig 110 local + prod; backend `360ce83`, backoffice
> `23fd5ea` + `23c2f26`, manuales/docs `3cae2d5`; `zaris-agentes` `ed52ea9` + `50a04cd`). Queda la prueba real
> de César en el celular (sección «Después») y la decisión pendiente de la sección 2. Reglas transversales en [`CLAUDE.md`](CLAUDE.md)
> (§3 roles, §5 links en mails, §21 migraciones, §23 patrones UI, §24 drift en prod, §39/§38 vía skills).

> **Cambio del 2026-10-13 (pedido de César, reemplaza la decisión 3):** **sin botón ni modal.** La cuenta ZARIS se
> crea **al guardar la ficha** con el tilde «funcionario»: nivel, subárea y usuario aparecen debajo del tilde
> (`CuentaZarisCampos`) y viajan en `cuenta_zaris` del `POST`/`PUT /buc/ciudadanos`. Consecuencias: el tilde pasa a
> ser **solo de Administrador** (la marca es la cuenta); el endpoint `POST /cuenta-zaris` queda para la API; guardar la
> ficha de un vecino sin credencial le crea la cuenta de App Vecinos (vía de mostrador sin botón) y los chips ofrecen
> «Reenviar correo de activación» cuando quedó pendiente. Detalle en las skills `modulo-usuarios` y `modulo-app-vecinos`.

## 1. Objetivo

Que un funcionario municipal se dé de alta **como persona en la BUC primero** y, desde esa misma
ficha, un administrador le cree **la cuenta ZARIS** (backoffice + app de agentes) con un clic. El
funcionario conserva además su cuenta de vecino (es vecino también); un vecino común **no** puede
entrar a la app de agentes. Todo listo para la prueba real en el celular (dos emails de César).

## 2. Decisiones tomadas (2026-10-12)

| # | Decisión | Elegido |
|---|---|---|
| 1 | «La cuenta del funcionario sirve también en la app del vecino» | **Dos credenciales, un solo clic.** Vecino = `ciudadano_credencial` (DNI + clave que elige por link, se crea sola en el alta). ZARIS = `usuarios` (clave temporal + cambio forzado). Vínculo explícito `usuarios.id_ciudadano`. No se mezclan los scopes JWT. |
| 2 | Quién crea la cuenta de funcionario desde la ficha | **Solo Administrador (nivel 1)**, igual que el alta en Usuarios. Nivel 2-3 ve el botón deshabilitado con la leyenda. |
| 3 | Dónde se cargan nivel / subárea / usuario | ~~**Mini-modal** al apretar «Crear cuenta aplicación ZARIS» con el tilde puesto.~~ **Reemplazada el 2026-10-13:** los tres campos van **dentro de la ficha, debajo del tilde**, y la cuenta se crea al guardar (ver nota al inicio). |
| 4 | Manuales | **Actualizar «Alta de ciudadanos» + nuevo «App de agentes».** |
| 5 | Identificador de login (pedido de César al aprobar) | El login de ZARIS (shell + app de agentes) acepta **email o número de documento** + contraseña. |

**Pendiente de decisión (no bloquea):** si la app del vecino también acepta email además del DNI
(hoy el contrato público es DNI + clave; sumar email es un cambio chico de backend + etiqueta de la PWA).

## 3. Realidad verificada que condiciona el diseño (prod, 2026-10-12)

- `usuarios` NO tiene `id_ciudadano`; el único vínculo usuario↔ciudadano es «mismo email» (así lo usa
  el cron de integridad). 92 usuarios activos, todos con agente, **1** coincide con un ciudadano por email.
- `agentes` tiene `nombre/apellido/dni/cuil/email/telefono` propios; el alta interna de hoy los deja
  mínimos (`nombre = username`, `apellido = ''`). Crear el agente desde la ficha del ciudadano los llena
  con datos reales.
- `ciudadanos` no tiene columna de funcionario. `estado_validacion`/`ficha_completa` no están mapeadas
  en el ORM (se escriben con UPDATE directo); `es_funcionario` SÍ se mapea (es campo del form).
- El login (`POST /auth/login`) busca `usuarios.email` exacto. «Olvidé mi usuario» ya resuelve DNI por
  `agentes.dni` (`POST /auth/recordar-usuario`).
- Las dos apps ya son PWA instalables con bloque «Instalar la app» (vecinos: bienvenida + Configuración;
  agentes: solo bienvenida). El manifest existe en ambos `vite.config.ts`.
- Manuales existentes: `docs/manual_alta_ciudadanos.html` (con capturas), `docs/manual_alta_vecino.html`.

## 4. Fases

### F1 — Migración 110 + backend + smoke (local)

**Mig `110_cuentas_funcionario.sql`** (idempotente; aplicar local con asyncpg y prod por MCP en la misma sesión):
- `ALTER TABLE ciudadanos ADD COLUMN IF NOT EXISTS es_funcionario BOOLEAN NOT NULL DEFAULT FALSE;`
- `ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS id_ciudadano INTEGER NULL REFERENCES ciudadanos(id_ciudadano) ON DELETE SET NULL;`
- `CREATE UNIQUE INDEX IF NOT EXISTS uq_usuarios_id_ciudadano ON usuarios(id_ciudadano) WHERE id_ciudadano IS NOT NULL;`
- Backfill: usuarios activos sin vínculo cuyo email (lower) coincide con exactamente UN ciudadano activo →
  `id_ciudadano` + `es_funcionario = TRUE` en ese ciudadano. (Verificar antes con `execute_sql` cuántas filas toca.)
- `CLAUDE.md` §21: próxima mig **111+**.

**Backend:**
- `models/buc.py` `Ciudadano.es_funcionario` + `Usuario.id_ciudadano`; `schemas/buc.py`
  `CiudadanoCreate/Update.es_funcionario: bool = False`, `CiudadanoOut.es_funcionario: bool = False`,
  `UsuarioOut.id_ciudadano: Optional[int]`. Auditar los SELECT crudos que arman `CiudadanoOut`
  ([[feedback_columna_nueva_auditar_todos_los_select]]).
- `services/cuenta_zaris.py::crear_usuario_interno(db, *, data, ciudadano=None, background_tasks)` — se
  extrae de `POST /buc/usuarios` y la usan los dos endpoints (una sola función, no dos copias). Con
  `ciudadano`: `usuarios.nombre = "Apellido, Nombre"`, `cuil`, `id_ciudadano`; el agente 1:1 con
  nombre/apellido/dni/cuil/email/telefono reales.
- **`POST /buc/ciudadanos/{id}/cuenta-zaris`** (`require_admin`), body `{nivel_acceso, id_subarea, username}`:
  422 si el ciudadano no es funcionario o no tiene email · 409 si ya tiene usuario vinculado, o username/email
  ya existen en `usuarios` · crea usuario + agente en una tx · si no tenía credencial de vecino, llama
  `asegurar_cuenta_vecino` (un clic, dos credenciales) · encola el mail de credenciales. Responde
  `{id_usuario, username, email, nivel_acceso, mail_enviado, cuenta_vecino_creada}`.
- **`GET /buc/ciudadanos/{id}/cuentas`** → `{vecino: 'sin_cuenta'|'pendiente'|'activa', zaris: {id_usuario, username, nivel_acceso, activo} | null}`.
- **Login por email o documento** (`POST /auth/login`): el campo `email` pasa a `identificador` (alias
  `email` por compat con clientes viejos). Si contiene `@` → por email (como hoy). Si son solo dígitos
  (7-8) → `usuarios.id_ciudadano → ciudadanos.doc_nro`, fallback `agentes.dni` (`id_usuario` vinculado);
  más de una coincidencia = no encontrado. Mismo 401 genérico. Rate-limit por identificador normalizado.
- Mail `enviar_mail_credenciales_usuario_interno`: dice «Usuario: tu email o tu DNI» y suma el link a la
  app de agentes (`APP_AGENTES_FRONTEND_URL`, solo si está configurada) junto al del backoffice.
- `services/integridad_cuentas.py`: vínculo a ciudadano por `id_ciudadano` **o** email (amplía).
- Marcador de deploy: las rutas nuevas aparecen en `/openapi.json`.

**Smoke `backend/smoke_cuentas_funcionario.py`** (httpx ASGI in-process, `settings.RESEND_API_KEY = ""` → MOCK):
alta de ciudadano con tilde → `cuenta-zaris` como admin (201; `usuarios.id_ciudadano`; agente con datos reales;
mail MOCK con los dos links) → `GET /cuentas` → login con la temporal por **email** y por **DNI** →
`debe_cambiar_password` → cambiar → credencial de vecino activada por token → login `/publico/auth/login` OK →
`/auth/login` con la clave de vecino = 401. Bordes: nivel 2 → 403 · sin tilde → 422 · repetido → 409 ·
username duplicado → 409 · DNI de un vecino sin usuario → 401.

### F2 — Backoffice (módulo Ciudadanos + login del shell)

- `CiudadanoForm.tsx`: sección **«Funcionario municipal»** debajo de «Representación empresarial», tilde
  «Este ciudadano es funcionario del municipio» (se guarda con la ficha; destildar no borra cuentas). En alta,
  el aviso celeste agrega que la cuenta ZARIS se crea después, desde la ficha, por un administrador.
- `FormView.tsx`: botón renombrado **«Crear cuenta aplicación ZARIS»**. Sin tilde → `cuenta-vecino` (igual).
  Con tilde y nivel 1 → `CuentaZarisModal` (nivel, subárea predictiva reusando `buscarSubareas` de Usuarios,
  usuario autocompletado `nombre.apellido` normalizado — editable, validación en vivo, patrón auto-slug §23).
  Confirmar cierra el modal y dispara; resultado por toast (§23). Con tilde y nivel 2-3 → deshabilitado con
  leyenda. Chips de estado de cuentas desde `GET /cuentas` (consulta/edición).
- `frontend/login.html`: etiqueta «Correo electrónico o DNI», `type="text"`, `autocomplete="username"`;
  manda `identificador`. El bloque «Olvidé mi usuario» sigue igual.
- `pnpm typecheck` + build + navegador local (shell 8080 + dist + API 8000) clickeando el recorrido completo
  como admin y como nivel 3 (§41).

### F3 — App de agentes (`zaris-agentes`)

- `LoginPage.tsx`: «Correo electrónico o DNI», `type="text"`, `inputMode` libre; manda `identificador`.
- `BloqueInstalar` extraído a `src/components/` y mostrado también en **Cuenta** (siempre visible, pasos
  Android/iPhone, «ya la tenés instalada» si corre standalone). Verificar manifest (`display: standalone`,
  íconos 192/512 maskable). Sin backend.
- Typecheck + build; verificar en local contra la API local.

### F4 — Manuales (skill `generar-manual`, sin fechas ni nombres)

- Regenerar `docs/manual_alta_ciudadanos.html`: tilde, botón nuevo, modal, chips, qué recibe cada uno por mail.
- Nuevo `docs/manual_app_agentes.html`: instalar en Android/iPhone (ícono en el escritorio y en el cajón de
  apps), primer ingreso con clave temporal (email o DNI), cambio de clave, qué hace la app (OT en la calle),
  notificaciones, cómo recuperar la clave. Registrarlo en `GUIAS` (`GuiasIndex.tsx`, skill `modulo-guias`).

### F5 — Prod + docs

- Mig 110 en prod por MCP (verificar antes drift: columnas, NOT NULL, defaults — §24). Push backend; esperar
  las rutas nuevas en `/openapi.json`. Push web-app; esperar el dist del CI y verificar el hash del bundle en el
  iframe. Push `zaris-agentes` (Vercel). `curl` de los DOS links del mail de credenciales en prod (§5).
- Docs: `CLAUDE.md` §21 (mig 110, próxima 111+) y §1 (login por email o DNI); skills `modulo-usuarios` y
  `modulo-app-vecinos`; `ESTADO.md` de los tres repos; `docs/contrato_api_publica.md` solo si se toca la API pública.

### Después: la prueba real (César)

Dos emails nuevos: (a) funcionario → alta en Ciudadanos con tilde → «Crear cuenta aplicación ZARIS» → mail →
instalar la app de agentes → login con DNI y clave temporal → cambio forzado → push real al asignarle una OT;
(b) vecino → autoregistro público → link de verificación → instalar la app del vecino → botón de pánico con el
backoffice a la vista. Confirma de paso la entrega de mails de Resend en prod.
