---
name: validar-fk-antes-submit
description: "Modales que arman un payload con FK condicional segun 'tipo' deben validar que la FK requerida no sea null ANTES de enviar — el backend la rechaza con un error generico difícil de debuggear desde la UI."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a3fb5267-bc13-4e6e-b506-ca9eab39aa3d
---

Un modal que cambia de campos según un `tipo` (ej: ocupación `ot` → necesita `id_orden_trabajo`, `evento` → `id_evento`, `turno` → `id_ciudadano`) debe validar en su `submit()` que la FK requerida por ese tipo esté seleccionada, **antes** de llamar a la mutation.

**Why:** si el form deja pasar la FK en `null`, el backend la rechaza — pero con un `value_error`/`IntegrityError` genérico que el usuario ve como "No se pudo crear" sin pista de qué falta. Caso real: el `OcupacionModal` de Agenda mandaba `id_orden_trabajo: null` y el usuario veía un toast con un JSON de error de Pydantic crudo. Costó una vuelta entera entender que el bug era frontend, no backend.

**How to apply:** en el `submit()` de modales con payload condicional, agregar guards explícitos con toast claro por cada FK requerida:
```ts
if (payload.tipo === 'evento' && !payload.id_evento) {
  push({ kind: 'error', title: 'Falta el evento', body: 'Busca y selecciona un evento.' })
  return
}
```
Aplica también al recurso (`id_recurso`/`id_agente`) y a cualquier campo que el backend valide pero el form no marque como obligatorio en la UI. El backend igual valida — esto es para que el error sea accionable, no para reemplazar la validación server-side.
