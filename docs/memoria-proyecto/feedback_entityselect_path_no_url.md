---
name: feedback-entityselect-path-no-url
description: EntitySelect.endpoint recibe un PATH no una URL completa — api.get() ya antepone VITE_API_BASE internamente
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 13ddb6d2-7b2a-43c2-94ad-9d6d69b2be84
---

`EntitySelect` (y cualquier componente que llame a `api.get(endpoint)` de `web-app/src/lib/api.ts`) espera un **path** como `/api/v1/buc/empresas/buscar`, NO una URL completa.

**Por qué:** `api.ts` construye `${BASE}${path}` internamente donde `BASE = import.meta.env.VITE_API_BASE`. Pasar una URL completa produce `https://api.railway.app/https://api.railway.app/...` → 404 silencioso, sin resultados en el dropdown.

**Cómo aplicar:**

```tsx
// MAL — doble BASE, 404 silencioso:
const BASE = import.meta.env.VITE_API_BASE
<EntitySelect endpoint={`${BASE}/api/v1/buc/empresas/buscar`} ... />

// BIEN — solo el path:
<EntitySelect endpoint="/api/v1/buc/empresas/buscar" ... />
```

Lo mismo aplica a cualquier llamada directa: `api.get('/api/v1/...')`, `api.post('/api/v1/...')`.

Caso real: `CrearTramite.tsx` (4 ocurrencias) y `CampoDinamico.tsx` (ENDPOINTS map), sesión 2026-05-16. El buscador de empresa/ciudadano no mostraba resultados al tipear aunque el endpoint funcionaba correctamente probado de forma independiente.
