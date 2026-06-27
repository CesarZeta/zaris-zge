---
name: feedback-react-pdf-pin-pdfjs-version
description: "react-pdf 10.x exige pdfjs-dist en una versión EXACTA; pnpm puede instalar más nueva y falla con \"API version does not match Worker version\". Pinear la versión que declara react-pdf."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e77756f2-e217-4421-a18c-df927d47dfb5
---

`react-pdf@10.4.1` declara `pdfjs-dist@5.4.296` como peer/dep exacta. `pnpm add react-pdf pdfjs-dist` puede traer `pdfjs-dist@5.7.x` (más nuevo) y todo compila, pero al renderizar el primer PDF tira:

```
UnknownErrorException: The API version "5.4.296" does not match the Worker version "5.7.284".
```

**Why:** `react-pdf` importa la API de `pdfjs-dist@5.4.296` (de su árbol interno) y el worker lo asignás vos desde `pdfjs-dist/build/pdf.worker.min.mjs?url` del top-level de `node_modules` — versiones distintas, protocolo binario distinto.

**How to apply:** después de `pnpm add react-pdf`, leer `node_modules/react-pdf/package.json` campo `"dependencies"."pdfjs-dist"` y correr `pnpm add pdfjs-dist@<esa-version-exacta>`. Verificar con `cat node_modules/pdfjs-dist/package.json | grep version`. Si más adelante actualizás `react-pdf`, repetir el paso.

Pattern aplicado en sesión 2026-05-18 al implementar `VisorDocumento.tsx` para módulo Trámites. Ver §35 — sección "Visor de documentos".
