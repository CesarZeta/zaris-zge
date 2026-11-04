# Versionado y «Acerca de» en todas las aplicaciones

Estado: **decisiones de César tomadas el 2026-11-03, falta el plan de implementación.** No hay código.

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

## Falta definir

- El texto exacto de propiedad y los datos de ZARIS que se muestran, y el enlace. No inventarlos: los da César. Recomendación: «© ZARIS. Todos los derechos reservados.» y `https://zaris.com.ar`, a confirmar.
- Dónde se abre el «Acerca de» del backoffice. Recomendación: el menú del avatar, junto a «Mi perfil» y «Guías de uso».
