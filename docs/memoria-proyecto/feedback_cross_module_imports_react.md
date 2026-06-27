---
name: feedback-cross-module-imports-react
description: "Módulos React pueden importarse entre sí (Modal, hook, tipo) cuando reutilizan datos del mismo dominio. Mejor que duplicar. Promover a ui/ es opcional, no obligatorio."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5c09709a-c98e-47c6-ad6e-b77d0e2b7153
---

Cuando un módulo React necesita un componente/hook/tipo que ya existe en otro módulo, **importar cross-module está OK**. Duplicar es peor.

**Why:** Sesión 2026-05-13 (OT drawer): `OTDetalleDrawer` necesitaba Modal + galería de adjuntos + tipos `HistorialItem/OTAsociada/Adjunto`. Las opciones eran:
1. Duplicar (rechazado — drift garantizado, el shape del backend está en un solo módulo).
2. Promover todo a `ui/` (rechazado — overkill, cada item lo usan 2 módulos como máximo).
3. Importar directo de `../../reclamos/{hooks,types}` y `../../agenda/components/Modal` (elegido).

Funciona, typecheck OK, sin drift posible porque la fuente es única.

**How to apply:**
- Importar cross-module (`../../otro-modulo/x`) cuando 2 módulos comparten el mismo concepto del backend. Ej: tipos del response shape, hooks de react-query sobre el mismo recurso.
- **Promover a `web-app/src/ui/`** sólo cuando el item lo usen ≥3 módulos O sea visualmente puro (sin dependencias del backend). Modal hoy lo usan OT (4 lugares) + Agenda — sigue viviendo en agenda/. Está bien.
- **No promover por estética.** "Modal debería estar en ui/" no justifica el cambio si no hay un consumidor nuevo concreto. CLAUDE.md §4 ya dice "promover cuando son maduros"; este memo es la regla operativa.
- **No mezclar import cross-module con tipos backend-side.** Si necesitás el shape de un response, asegurate que el módulo fuente sea el "dueño" del recurso (Reclamos para reclamos, OT para ordenes_trabajo, Agenda para eventos). El que llega después importa, no redefine.

**Casos vigentes en el repo (2026-05-13):**
- `ot/components/*.tsx` → `agenda/components/Modal`.
- `ot/components/OTDetalleDrawer.tsx` → `reclamos/hooks/useReclamos`, `reclamos/types/reclamo`, `agenda/components/Modal`.
- Sano. Si Modal pasa a un 3er consumidor, ahí sí promover.
