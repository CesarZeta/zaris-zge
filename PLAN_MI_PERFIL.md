# PLAN — Vista «Mi perfil» del usuario en ZARIS (backoffice)

> Pedido de César (2026-09-26): un lugar propio del usuario en ZARIS desde donde
> **descargar la app del vecino desde el celular**. Alcance acordado: **completa**
> (cabecera con datos y foto + tarjeta App del vecino con QR y link + cambio de
> contraseña voluntario). Ejecución: **próxima sesión**, de punta a punta
> (backend + vista + menú + build + prod). Estimación: una sesión.
>
> Hechos verificados el 2026-09-26 (no asumir, re-verificar si pasó tiempo):
> no existe vista de perfil en el backoffice; el cambio de contraseña
> voluntario NO tiene pantalla (solo el forzado en `frontend/login.html`); el
> bundle React ya tiene `qrcode` (`web-app/src/modules/agenda/components/QRDisplay.tsx`);
> `GET /auth/me` devuelve `id_usuario, nombre, email, nivel_acceso, foto_url,
> debe_cambiar_password, modulos_permitidos, cargo_nombre, id_subarea, subarea_nombre`;
> existen `POST /auth/cambiar-password` (`password_actual` + `password_nueva` ≥ 8),
> `POST /auth/me/foto-upload-url` + `PUT /auth/me/foto`; el backend conoce la URL
> de la PWA en `settings.APP_VECINOS_FRONTEND_URL` (la usa en los mails de activación).

## 1. Diseño

**Ruta:** `web-app/dist/index.html#/perfil` — módulo React `perfil`, `hideFromSidebar: true`,
**sin `moduloCodigo`** (visible para cualquier usuario autenticado, como Guías; no toca datos
de terceros). Sin fila en `modulos`, sin migración.

**Acceso:** ítem nuevo **«Mi perfil»** como PRIMER ítem del menú del avatar del shell vanilla
(`index.html` `#user-menu-dropdown`, handler en `frontend/js/menu.js` →
`shellNavigate('web-app/dist/index.html#/perfil')`), y también al clickear el bloque de nombre
(`#user-menu-info`). Espejar en el AppShell dev (`web-app/src/shell/TopBar/TopBar.tsx`,
dropdown → `navigate('/perfil')`), regla §4 «dev clona el shell».

**Contenido (tarjetas, DS §13, tokens en `*.module.css`):**

1. **Cabecera** — avatar grande (foto `foto_url` o iniciales, como el topbar) + nombre + email
   + rol por `nivel_acceso` (1 Administrador · 2 Supervisor · 3 Atención · 4 Gestión ·
   5 Consultor) + cargo (`cargo_nombre`) + gestión (`subarea_nombre`). Botón «Cambiar foto»
   (PNG/JPG ≤ 2 MB) reusando el flujo del shell: `POST /auth/me/foto-upload-url` → PUT del
   binario a Storage → `PUT /auth/me/foto`; al terminar, `refreshSession()` del store (la
   vista muestra la foto nueva al instante). El avatar del topbar del shell vanilla se
   actualiza recién al recargar el shell (`menu.js` lee la sesión al boot); si molesta, sumar
   en `menu.js` un refresco contra `/auth/me` al recibir foco la ventana. No inventar un canal
   iframe→shell nuevo por esto.
2. **App de agentes** (desde el 2026-09-27; hasta entonces la tarjeta fue la del vecino, que
   pasó al perfil del portal del vecino por decisión de César: cada quien instala su app desde
   su propio lugar) — título «ZARIS Agentes en tu celular», URL `app_agentes_url` de
   `/config/identidad` (env `APP_AGENTES_FRONTEND_URL`), QR + link + «Copiar link» + pasos.
   Diseño original de la tarjeta (sigue vigente): título «Portal del Ciudadano», texto «Los vecinos la instalan desde el
   navegador del celular (no está en las tiendas)», **QR grande** (≥ 200 px) con la URL,
   la URL como link (abre en pestaña nueva), botón «Copiar link», y dos líneas de instalación:
   Android → Chrome ofrece «Instalar» en la bienvenida; iPhone → Compartir → «Agregar a inicio».
   Reusar `QRDisplay` de Agenda (import cross-module, memoria `feedback_cross_module_imports_react`)
   o un canvas propio con `qrcode` si el tamaño/estilo no encaja. (La «tarjeta gemela» de
   agentes terminó REEMPLAZANDO a la del vecino el 2026-09-27, no conviviendo.)
3. **Seguridad** — cambio de contraseña voluntario: actual + nueva + repetir; validación en vivo
   (≥ 8, coinciden); `POST /auth/cambiar-password` con `{password_actual, password_nueva}`;
   toast de éxito; el 401/422 del backend se muestra tal cual (`detail`). No cierra sesión.

**Fuente de la URL de la app:** `GET /api/v1/config/identidad` (público) suma
`app_vecinos_url: str` desde `settings.APP_VECINOS_FRONTEND_URL` (`config_identidad.py`,
`IdentidadOut` + `_leer_claves`). Una sola fuente con los mails; cuando llegue IT-01
(multi-municipio) se mueve a `configuracion_general` sin tocar la vista.
⚠️ En Railway el valor lo da la env var (no verificable desde afuera): si tras el deploy la
identidad devuelve `http://localhost:5174` o `http://localhost:5175`, **César las setea en Railway → Variables** (`APP_VECINOS_FRONTEND_URL`, `APP_AGENTES_FRONTEND_URL`).

## 2. Pasos (orden)

1. **Backend** (`backend/app/api/routes/config_identidad.py`): campo `app_vecinos_url` en
   `IdentidadOut` + valor desde settings. Sin migración. Push → verificar en prod que
   `/openapi.json` tiene la propiedad en `components.schemas.IdentidadOut` (marker §9) y que
   `GET /api/v1/config/identidad` devuelve `https://vecinos.zaris.com.ar`.
2. **Módulo React** `web-app/src/modules/perfil/`: `index.tsx` (manifest `id: 'perfil'`,
   `hideFromSidebar: true`, sin `moduloCodigo`, ruta index), `pages/PerfilPage.tsx`,
   `PerfilPage.module.css`, `api/perfilApi.ts` (me, identidad, cambiar-password, foto),
   `hooks/usePerfil.ts` (react-query). Registrar en `web-app/src/modules/index.ts`
   (skill `nuevo-modulo-react`). Datos del usuario: `useAuthStore().user` + refresco con
   `GET /auth/me` al montar (la sesión guardada puede estar vieja: foto, cargo).
3. **Shell vanilla**: `index.html` ítem `#btn-perfil` (icono Lucide inline `user`,
   `stroke-width 1.5`) primero en el dropdown + click en `#user-menu-info`; `frontend/js/menu.js`
   handler; **bump `?v=` de `menu.js`/`menu.css`** (§14 cache-bust).
4. **AppShell dev**: ítem «Mi perfil» en el dropdown de `TopBar.tsx`.
5. **Docs**: CLAUDE.md §4 (tabla de módulos: fila Perfil, React, sin `data-modulo`) y §14
   (lista del menú de usuario: «Mi perfil» + IDs); `ESTADO.md`; skill `modulo-guias`? no
   (no es guía). Manual/guía de uso: agregar «Mi perfil» al manual del shell si existe.
6. **Verificación (§41, obligatoria antes de declararlo hecho):** `pnpm typecheck` + build;
   navegar en local (`localhost:5173` para la vista; `localhost:8080` + `?modulo=…%23/perfil`
   para el iframe real) **clickeando desde el menú del avatar**, no por URL; probar: QR escaneable
   (leerlo con el celular → abre `vecinos.zaris.com.ar`), copiar link, cambio de clave con actual
   incorrecta (401) y correcta (usuario de testing, NO `cesar@`), foto nueva (avatar del topbar
   actualizado tras recargar). Push sin `[skip ci]` → `deploy-web-app.yml` publica el dist;
   confirmar en prod el hash nuevo del bundle y el ítem en el menú.

## 3. Decisiones tomadas / abiertas

- **Tomadas (2026-09-26):** alcance completo · sin permiso de módulo · sin sidebar · URL desde
  la env var vía identidad (no migración) · el cambio de clave NO desloguea.
- **Abiertas (decidir al arrancar):** ¿el toggle de modo oscuro y «Guías de uso» se duplican en
  la vista o quedan solo en el menú? (propuesta: solo en el menú, la vista no repite
  preferencias) · ¿mostrar `modulos_permitidos` como «Módulos a los que accedés»? (propuesta: sí,
  solo lectura, ayuda a soporte).

## 4. Cierre y seguimiento (2026-09-27)

- **HECHO el 2026-09-26** (`4be8773`, verificado en prod con jsQR: el QR decodifica a `https://vecinos.zaris.com.ar`). Decisiones abiertas resueltas: dark/guías solo en el menú; «Módulos a los que accedés» sí (solo lectura). Regla técnica que quedó: el cambio de clave usa fetch directo porque `api.post` cierra sesión ante cualquier 401 (CLAUDE.md §14).
- **Decisión de César (2026-09-27):** los funcionarios bajan **la app de agentes** desde este perfil; los vecinos bajan la app del vecino **desde el portal del vecino**, sin entrar a ZARIS. Próximo paso: tarjeta gemela «App de agentes» (backend `app_agentes_url` en `/config/identidad` desde `APP_AGENTES_FRONTEND_URL`) y definir el canal de la app del vecino en el portal; confirmar si la tarjeta del vecino se queda acá.
