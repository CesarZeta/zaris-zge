---
name: guard-sesion-en-head
description: "El script que verifica sesión y redirige al login en el shell vanilla DEBE ejecutarse en <head>, antes de que el iframe arranque. Si va al final del body, el bundle React monta sin sesión, hace requests, recibe 401 y rompe."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 76abb031-f1fc-41a4-97a8-16b043ddea10
---

El guard de sesión del shell vanilla (`if (!localStorage.getItem('zaris_session')) window.location.replace('frontend/login.html')`) **DEBE estar en `<head>`** de `index.html`, antes de que el browser parsee el `<iframe>`. Si va al final del body como antes, hay una ventana de carrera donde el iframe ya empezó a cargar el bundle React, este monta, hace su primer request al backend, recibe 401 (porque no hay token), y dispara su propio handler de redirect — que en prod tiene el bug del subpath y muestra 404 de GH Pages dentro del iframe.

**Why:** el `<iframe>` empieza a cargar tan pronto como el parser HTML lo encuentra. Cualquier `<script>` posterior corre después de eso. Mover el guard al `<head>` lo hace bloqueante respecto al iframe.

**How to apply:**
- En `index.html`, después de los `<link>` y los scripts globales como Lucide, poner:
  ```html
  <script>
    if (!localStorage.getItem('zaris_session')) {
      window.location.replace('frontend/login.html');
    }
  </script>
  </head>
  ```
- NO poner código async/await en ese script — debe ser sincrónico para que `replace()` termine antes de que el parser siga.
- Si agregás un nuevo guard (por nivel de acceso, fecha de expiración del token, etc.), aplicá la misma regla: va en `<head>`, sincrónico.
- Aplica solo al shell raíz (`index.html`). Los HTMLs vanilla individuales (`admin_tablas.html`, `usuarios.html`) tienen su propio guard interno por defensa en profundidad — ese puede ir en cualquier lado porque cuando el módulo ya está cargado el shell padre ya hizo su check.

Cazado 2026-05-13 (commit `d028e3e`). Síntoma: shell vanilla OK con topbar+sidebar, iframe con 404 de GitHub Pages. Sin esto el bug del [[feedback_redirect_iframe_subpath]] se gatilla todas las veces que entrás sin sesión válida.

Relacionado: [[feedback_redirect_iframe_subpath]] (la otra mitad del fix).
