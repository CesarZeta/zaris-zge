---
name: feedback-usesyncexternalstore-getsnapshot-cache
description: "useSyncExternalStore con getSnapshot que hace JSON.parse devuelve objeto nuevo por llamada → 'getSnapshot should be cached to avoid an infinite loop' + crash. Cachear el snapshot por referencia mientras el string crudo no cambie."
metadata:
  type: feedback
---

Un store sobre `localStorage` con `useSyncExternalStore(subscribe, getSnapshot)` **rompe con loop infinito** si `getSnapshot` parsea el JSON en cada llamada: `JSON.parse(raw)` devuelve un **objeto nuevo cada vez**, React ve referencia distinta en cada render → consola: `"The result of getSnapshot should be cached to avoid an infinite loop"` → el componente que lo consume crashea (root vacío).

**Why:** introducido y cazado en la misma sesión 2026-06-02 en `zaris-vecinos/src/lib/session.ts` (hook `useSesion`). El happy-path de login navegó igual a `/inicio` (el redirect ocurrió antes del re-render que reventaba), pero `SoloInvitado`/`useSesion` crasheaban al re-renderizar → pantalla en blanco. La pista vivía en `browser_console`, no en el DOM.

**How to apply:**
- `getSnapshot` DEBE devolver la **misma referencia** mientras la fuente no cambió. Cachear contra el string crudo:
  ```ts
  let cacheRaw: string | null = null
  let cacheValue: T | null = null
  function read(): T | null {
    const raw = localStorage.getItem(KEY)
    if (raw === cacheRaw) return cacheValue   // misma referencia
    cacheRaw = raw
    cacheValue = raw ? parse(raw) : null
    return cacheValue
  }
  ```
- Misma familia que [[feedback_useeffect_data_null_loop]] (referencia nueva por render = loop), pero el mecanismo es `useSyncExternalStore`, no `useEffect`+setter. El síntoma de consola es distinto ("getSnapshot should be cached" vs "Maximum update depth").
- Regla general: cualquier `getSnapshot` que derive el valor (parse, map, filter, spread) necesita cache; devolver un primitivo o una referencia estable es lo único seguro.
