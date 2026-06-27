---
name: feedback-fetch-cache-binarios-autenticados
description: "fetch() por default usa el cache del browser; con Last-Modified de FastAPI puede servir body cacheado viejo aunque el archivo en disco cambió. Pasar cache \"no-store\" cuando descargues binarios desde API."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e77756f2-e217-4421-a18c-df927d47dfb5
---

`fetch(url, { headers: { Authorization } })` SIN opción `cache` usa el caché HTTP del browser. Si tu endpoint backend devuelve `Last-Modified` (`FileResponse` de FastAPI lo hace por default), el browser puede revalidar con `If-Modified-Since` y servir el body cacheado aunque vos hayas reemplazado el archivo en disco. Síntoma típico durante debugging: respondés desde curl con bytes nuevos pero el browser sigue viendo bytes viejos del archivo.

**Why:** caché transparente HTTP estándar. Aplica especialmente cuando reemplazás archivos directamente en `uploads/` durante verificación local (no es el caso productivo común — al volver a uploadear genera URL nueva).

**How to apply:** en cualquier helper que descargue binarios autenticados desde la API, agregar `cache: 'no-store'`:

```ts
const res = await fetch(url, {
  headers: token ? { Authorization: `Bearer ${token}` } : {},
  cache: 'no-store',
})
```

Patrón aplicado en `web-app/src/modules/tramites/lib/api.ts::descargarDocumentoBlob` (visor de documentos, sesión 2026-05-18). Pendiente replicarlo en otros helpers que sirvan binarios protegidos (adjuntos de reclamos, fotos de ciudadanos, etc.) cuando existan.
