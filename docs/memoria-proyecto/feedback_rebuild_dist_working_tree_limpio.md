---
name: rebuild-dist-working-tree-limpio
description: "Antes de rebuildear web-app/dist/ para un commit, el working tree solo debe tener los cambios que van en ESE commit. Vite compila todo lo que está en disco."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 9a3fb782-13dc-4b66-8cf5-fffd6cb8445a
---

Antes de correr `pnpm build` / `vite build` sobre `web-app/dist/` con intención de commitear ese dist, verificá que el working tree **solo tenga los cambios que van en ese commit**. Vite compila **todo lo que esté en disco**, no lo que está staged.

**Why:** Sesión 2026-05-14 — rebuildeé `dist/` durante la fase de cleanup de una verificación visual mientras el working tree tenía cambios de OT sin commitear (trabajo en curso del usuario, ajeno a la tarea de esa sesión). Vite los compiló dentro del bundle. Resultado: el commit `089595c` (feat permisos) quedó con un `dist/` que incluía fuentes que recién se commitearon en `555abda` (feat OT). El estado final de HEAD es consistente, pero el commit intermedio tenía dist cruzado — feo para `git bisect`, para revisar un PR, o si alguien hace `git checkout 089595c`.

**How to apply:**
- Si vas a commitear `dist/`: commiteá los **fuentes primero**, después rebuildeá el dist con el working tree ya acotado, y commiteá el dist (o inclúilo en el mismo commit que los fuentes que lo generan).
- Si hay trabajo en curso ajeno sin commitear (común en este repo — siempre hay algo a medias), o lo stasheás antes de rebuildear, o asumís conscientemente que el dist va a incluirlo y lo declarás.
- Caso especial OK: si rebuildeás dist solo para *verificación local* y NO lo vas a commitear (lo vas a regenerar en modo prod antes del commit final), no importa qué más esté en el working tree.

Relacionado: [[project_proxy_local_zaris_zge]] (rebuild dev vs prod), [[feedback_browser_mcp_iframe_cache]].
