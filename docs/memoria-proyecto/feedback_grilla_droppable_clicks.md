---
name: grilla-droppable-clicks
description: "En grillas con useDroppable de @dnd-kit, los clicks \"en celda vacia\" no deben colgarse del wrapper droppable y los draggables no deben envolverse en divs full-bleed con pointerEvents:auto."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 9f22ae1e-23dd-4dae-9ee4-6c68e1a34b76
---

Si una fila de grilla es `useDroppable` (@dnd-kit/core) **y** ademas quiere disparar acciones al click en celdas vacias (ej: "crear ocupacion en este slot"), seguir dos reglas:

1. **Layer de fondo dedicado para clicks**, no `onClick` en el wrapper droppable. El handler de pointerdown de dnd-kit puede interferir. Patron: primer hijo del wrapper `<div style="position:absolute; inset:0; zIndex:0; cursor:pointer" onClick={...}>`. Los bloques draggables se renderean encima con `position:absolute; left/width` propios.

2. **El draggable es el elemento final** con su `left/width`. Nada de envolverlo en wrappers `<div style="position:absolute; inset:0; pointerEvents:none">` con un hijo `pointerEvents:auto` sin `position`. Ese hijo se extiende a toda la fila y come los clicks del fondo, dando la sensacion de "fila muerta".

**Why:** BUG-3B-01 en TimelineView Agenda (2026-05-11): al introducir DnD, la regresion fue "clicks en celdas vacias no abren modal de nueva ocupacion". Pase como 30 min sospechando de dnd-kit cuando el bug real era el wrapper invisible full-bleed alrededor de cada bloque.

**How to apply:** cuando agregues DnD a una grilla (Agenda, futuras Mesas, Gantts de OT), validar en navegador: click sobre cualquier punto blanco de la fila → ¿pasa algo? Si no, sospechar de wrappers invisibles antes que de dnd-kit. Inspeccionar elemento (DevTools) y ver qué nodo intercepta el click.

Documentado en CLAUDE.md §29 ("Grillas con useDroppable + clicks de fondo").
