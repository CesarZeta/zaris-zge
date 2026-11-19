# Versionado y «Acerca de» en todas las aplicaciones

Estado: **decisiones de César tomadas el 2026-11-03; texto del «Acerca de» aprobado el 2026-11-19** («© ZARIS. Todos los derechos reservados.» + `https://zaris.com.ar`; en el backoffice, en el menú del avatar). Implementación del 2026-11-19 en «Hecho» al final.

## Para qué

Después de un cambio en producción, alguien puede seguir con una ventana abierta sin refrescar. Hay que poder detectarlo y avisarle, y poder saber qué versión tiene una persona cuando se investiga un problema técnico o de uso.

## Decidido por César

- **Versión vieja: un aviso, no una recarga automática.** La persona actualiza desde el aviso. Vale para todas las aplicaciones (backoffice, App Vecinos y app de agentes).
- **Todas las aplicaciones tienen un «Acerca de»** con los datos de ZARIS: que el software es propiedad de ZARIS y un enlace a la página. **La versión va ahí**, como es usual en el software.

## Propuesta de Claude (presentada el 2026-11-03, sin objeción)

- **Un solo número por aplicación**, generado en cada publicación en lugar de escrito a mano, más una marca de la publicación exacta (el commit). La API también informa la suya.
- **Detección:** cada sitio publica un archivo con su versión actual, y la pantalla abierta lo compara cada pocos minutos y al volver a la pestaña. El aviso es fijo, con un botón «Actualizar», para no perder un formulario a medio completar.
- **Historial:** una etiqueta en git por versión y un registro corto de qué cambió.

## Lo que hay hoy (verificado el 2026-11-03)

| Dónde | Qué dice |
|---|---|
| Login y barra inferior del backoffice (`frontend/login.html`, `index.html`, `web-app/src/app/LoginPage.tsx`) | `v0.1`, escrito a mano |
| API (`backend/app/main.py`, `/api/health`) | `1.0.0`, escrito a mano |
| App Vecinos (`src/lib/app.ts`) | `VITE_APP_VERSION` o `0.1.0`; se ve en Bienvenida y en Acerca de |
| App de agentes (`src/lib/app.ts`, `AcercaPage`) | Versión y «Buscar actualizaciones» |
| Git | Ningún tag (936 commits en `zaris-zge`) |

- **«Acerca de»:** existe en las dos apps (`AcercaPage`), pero no dice de quién es el software ni enlaza a la página. **El backoffice no tiene ninguno.**
- **Actualización de las apps:** usan `registerType: 'autoUpdate'` del service worker, que recarga solo. Hay que compatibilizarlo con la decisión del aviso.

## Definido por César (2026-11-19)

- Texto: «© ZARIS. Todos los derechos reservados.» y `https://zaris.com.ar`.
- El «Acerca de» del backoffice va en el menú del avatar.

## Hecho (2026-11-19)

**Número de versión:** fecha y hora de Argentina de la publicación, `AAAA.MM.DD.HHMM`, más el commit corto. Lo genera el build; nadie lo escribe a mano.

**Backoffice (`zaris-zge`):**
- `tools/cloudflare_pages_build.sh` calcula la versión, reescribe `frontend/js/version.js` (en el repo dice `dev`) y publica `/version.json`; el bundle React la recibe por `VITE_APP_VERSION` / `VITE_APP_COMMIT` (`web-app/src/lib/version.ts`).
- La barra inferior y el login la muestran; el menú del avatar tiene «Acerca de ZARIS» (versión, versión del servidor, propiedad y enlace).
- `menu.js` compara la versión de la pantalla con `/version.json` a los 15 s, cada 5 min y al volver a la pestaña; si difieren, aviso fijo con «Actualizar» (no recarga sola).

**API:** `/api/health` informa `version` (fecha y hora del arranque del proceso en Railway, con el mismo formato; `dev` en local) y `commit` (`RAILWAY_GIT_COMMIT_SHA`).

**App Vecinos y app de agentes** (`zaris-vecinos` `4226a03`, `zaris-agentes` `8e35dae`): la versión la calcula `vite.config.ts` en el build de Cloudflare (`CF_PAGES`); el service worker pasa a `registerType: 'prompt'` y `src/lib/actualizacion.ts` muestra el aviso «Actualizar» (busca cada 5 min y al volver a la app). «Acerca de» con la propiedad, el enlace y la versión con su commit. Probado el ciclo completo en local: aviso, «Actualizar», versión nueva. Quien tenía abierta la versión anterior (recarga automática) recibe esta la próxima vez que cierra la app del todo y la vuelve a abrir: el service worker nuevo queda en espera y el código viejo no lo activa (verificado en el navegador el 2026-11-19). Desde esta versión, ya aparece el aviso. Los dos proyectos de Cloudflare Pages tienen una variable `VITE_APP_VERSION=0.1.0` vieja: el build ya la ignora (`4542c81`, `60592ef`); se puede borrar del panel cuando convenga. Verificado en prod el 2026-11-19: los bundles publicados traen la fecha y el commit.

**Para más adelante:** la etiqueta de git por versión y el registro corto de cambios.
