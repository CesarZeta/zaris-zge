---
name: feedback-useeffect-data-null-loop
description: "useQuery().data ?? [] dentro de useEffect deps + setter que devuelve referencia nueva = loop infinito \"Maximum update depth exceeded\". Bail explícito en el setter funcional."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5c09709a-c98e-47c6-ad6e-b77d0e2b7153
---

`useQuery().data ?? []` devuelve un **literal array nuevo en cada render** (referencia distinta). Si lo metés como dep de un `useEffect` que llama un setter cuyo callback funcional siempre devuelve referencia nueva (`new Set()`, `[...x]`, `{...obj}`), React entra en loop infinito: render → effect corre → setter → rerender → array nuevo → effect corre → ...

**Why:** descubierto en sesión 2026-05-13 cazando bug latente en `SupervisorView.tsx:73` (OT). Era preexistente; saltó al recargar el módulo en local. `setSeleccionados((prev) => { const next = new Set(); ... return next })` siempre devolvía `next !== prev` aunque las ids fueran las mismas. React no puede bailear sin ayuda.

**How to apply:**
- Si un `useEffect` depende de `algo = useQuery().data ?? []` y llama un setter funcional, el callback del setter **debe bailar** (return `prev`) cuando la estructura no cambió. Comparar elementos, no referencias.
- Alternativa: derivar `algo` con `useMemo` estable o memo del query result. Útil si la lista la consumen varios effects.
- Anti-patrón típico: cualquier setter que arme `new Set(...)`/`new Map(...)` /`[...]` cada vez. Si la lógica no detecta diff, el render es estable visualmente pero el efecto sigue corriendo (queda invisible hasta que algo gatilla el "Maximum update depth").
- Aplicable a CUALQUIER módulo React del proyecto, no solo OT. Ver también [[feedback_grilla_droppable_clicks]] para otro bug latente similar disparado por interacción.

**Patrón fix:**
```ts
useEffect(() => {
  const vivos = new Set(reclamos.map((r) => r.id_reclamo))
  setSeleccionados((prev) => {
    let allHere = true
    prev.forEach((id) => { if (!vivos.has(id)) allHere = false })
    if (allHere) return prev   // BAIL — referencia preservada, React no rerenderiza
    const next = new Set<number>()
    prev.forEach((id) => { if (vivos.has(id)) next.add(id) })
    return next
  })
}, [reclamos])
```
