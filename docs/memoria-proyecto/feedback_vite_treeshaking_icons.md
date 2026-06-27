---
name: feedback-vite-treeshaking-icons
description: Vite tree-shaking elimina namespace imports y dict re-exports en prod — dynamic icon lookup falla silenciosamente
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 13ddb6d2-7b2a-43c2-94ad-9d6d69b2be84
---

`import * as LucideIcons` y `{ icons as lucideIcons }` (re-export como dict) ambos fallan en builds de Vite producción cuando se hace acceso dinámico de propiedades (`Namespace[nombreDinamico]`). El tree-shaker elimina todas las propiedades no referenciadas estáticamente.

**Por qué:** Vite/Rollup analiza imports estáticos en tiempo de build. Si el acceso es `map[variable]`, el bundler no puede determinar qué keys se usan → las elimina. Con named imports explícitos, el bundler garantiza que cada import sobrevive.

**Cómo aplicar:** Para cualquier lookup dinámico icon-by-name, usar un static map con named imports explícitos:

```tsx
import { FileText, MapPin, Store } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

const ICONO_MAP: Record<string, LucideIcon> = {
  'file-text': FileText,
  'map-pin': MapPin,
  'store': Store,
}

function LucideIcono({ nombre }: { nombre: string | null | undefined }) {
  const Icon = (nombre ? ICONO_MAP[nombre.toLowerCase()] : undefined) ?? FileText
  return <Icon size={20} strokeWidth={1.5} />
}
```

Aplica a cualquier librería de iconos (Heroicons, Phosphor, etc.), no solo Lucide.

Caso real: `CrearTramite.tsx`, sesión 2026-05-16. Los iconos aparecían como texto literal ("map-pin", "store") en producción aunque funcionaban perfecto en `localhost:5173`.
