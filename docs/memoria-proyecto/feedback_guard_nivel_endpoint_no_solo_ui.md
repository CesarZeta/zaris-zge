---
name: guard-nivel-endpoint-no-solo-ui
description: "Restringir una accion por ROL solo en el frontend (sidebar/vista) es evadible: el endpoint backend tambien debe chequear nivel_acceso. CLAUDE.md §30 dice que los guards de endpoint son 'opcionales/no aplicados' — eso es deuda explotable, no diseño."
metadata:
  node_type: memory
  type: feedback
---

Cuando una accion debe ser exclusiva de cierto rol (ej: Mesa Supervisor / crear-asignar OT = solo nivel<=2), gatearla SOLO en el frontend (ocultar el item del sidebar por `data-modulo`, o un guard de vista React) es **evadible**: basta un `curl`/`Invoke-RestMethod` con un JWT valido de un operador para llamar el endpoint directo. El endpoint backend tiene que chequear `nivel_acceso` tambien.

**Why:** sesion 2026-05-20 (hallazgo #2 QA Royman) — `POST /ot`, `POST /ot/con-agenda` y `GET /ot/mesa/supervisor` solo usaban `get_current_user` SIN chequear nivel. Un operador (nivel 3) creaba/asignaba OT por la Mesa Supervisor. El manifest de OT (`web-app/src/modules/ot/index.tsx`) decia textualmente "el filtrado de permisos se hace... a nivel endpoint backend cuando corresponda" — pero **nunca se implemento**. Fix: helper `_require_supervisor(current_user)` (nivel<=2 → si no, 403) en los 3 endpoints + gate `WrapNivel` en el bundle React (defensa en profundidad) + link sidebar a `#/ot` con redirect por rol.

**Trampa documental:** CLAUDE.md §30 ("Permisos por modulo") dice que el helper `require_modulo` y los guards de endpoint son de "uso opcional" y "hoy no aplicado a endpoints existentes — los routers ya tenian su propio criterio (nivel_acceso)". Eso suena a decision deliberada pero en la practica deja routers SIN ningun guard (OT era uno). **No asumir que "el router ya valida nivel" — verificarlo.** El sistema de permisos por modulo (§30) filtra la UI; NO impone nada en el backend salvo que cada endpoint lo invoque.

**How to apply:**
- Al tocar/auditar cualquier endpoint que represente una accion privilegiada, leer si chequea `nivel_acceso` o `require_modulo`. Si no, es bug aunque la UI lo oculte.
- El patron del proyecto: helper local `_require_supervisor`/`_require_gestion` que levanta 403, llamado como PRIMERA linea del handler (ver `reclamos.py::_require_gestion`, `ordenes_trabajo.py::_require_supervisor`).
- Extiende el "Caso 1: endpoint sin JWT" de [[feedback_qa_modulo_smoke_priorizar_seguridad]] con un cuarto caso: **endpoint con JWT de nivel insuficiente** (no solo sin token). Login como operador → llamar la accion de supervisor → esperar 403.
- Mismo riesgo cuando un item de sidebar usa `data-modulo-fallback` (§30): el item OT con `data-modulo="ot_supervisor" data-modulo-fallback="ot_agente"` lo muestra a operadores, que aterrizaban en la Mesa Supervisor. Ver [[feedback_verificar_destino_link_sidebar]].
