---
name: grep-ds-antes-de-crear-componentes
description: "Antes de crear un componente nuevo del DS (o adoptar un naming nuevo), grep el DS por el patrón propuesto. Sesión 2026-05-12 evitó dos namings paralelos así."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a623b6ca-1631-40c7-b4a6-b9fefd38ee74
---

**Regla:** antes de elegir un naming para componentes nuevos del DS (o de inventar variables), `grep` el DS existente por el patrón propuesto Y por los alternativos plausibles.

**Why:** sesión 2026-05-12, antes de crear los nuevos componentes en `design-system/components/`, había acordado con el usuario naming `ds-btn`, `ds-card`, etc. Al hacer `grep btn-zaris` antes de empezar encontré que `colors_and_type.css` ya definía `btn-zaris`, `card-zaris`, `input-zaris` huérfanos (3 componentes sueltos sin agrupar). Si hubiera arrancado con `ds-*` quedaban DOS namings paralelos oficiales — `btn-zaris` viejo y `ds-btn` nuevo. Pregunté al usuario, eligió extender lo existente. Resultado: un solo naming `*-zaris` para todo el DS.

**How to apply:**
- Antes de empezar a escribir CSS de componentes: `grep -rn "btn-zaris\|card-zaris\|input-zaris\|<naming-propuesto>" design-system/`.
- Si encontrás definiciones huérfanas, **NO las dupliques**: o las extendés o las movés al naming nuevo (con migración de referencias).
- Aplica también a vars CSS: `grep "--<nombre-propuesto>" design-system/` antes de declarar tokens nuevos.
- Aplica a clases globales de Tailwind/utility en proyectos que las usen.

**Generalización:** la regla §28 ("validar prompts externos contra realidad") aplica también a planes propios. Cuando armás un plan en base a `grep` de ocurrencias (cuántos `.z-btn` hay, cuántos `--z-foo`), ABRIR los archivos clave antes de prometer alcance. En esta sesión `admin_tablas.html` no importaba `styles.css` — eso cambió el alcance del refactor entero.
