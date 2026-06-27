---
name: feedback-tsc-b-vs-noemit
description: tsc -b --noEmit (modo build con referencias) detecta errores que tsc --noEmit suelto no ve. Verificar con el mismo comando que usa el pre-commit hook.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f84d7548-b002-463d-8332-dbf8d5375172
---

El pre-commit hook corre `tsc -b --noEmit`. Verificar con `tsc --noEmit` suelto antes del commit puede dar 0 errores y aun así fallar el hook.

**Por qué:** el modo `-b` (build) resuelve referencias de proyecto y analiza los archivos nuevos en el contexto del grafo completo. El modo suelto puede pasar por alto errores en archivos nuevos que aún no tienen sus dependencias completamente resueltas. En esta sesión (2026-05-16): `tsc --noEmit` reportó 0 errores, el hook encontró 10.

**Cómo aplicar:** antes de commitear cambios en `web-app/`, siempre correr desde `web-app/`:

```bash
./node_modules/.bin/tsc -b --noEmit
```

— **no** `./node_modules/.bin/tsc --noEmit` (sin `-b`). Son comandos distintos con resultados distintos.

**Relacionado con:** [[feedback_powershell_execution_policy_pnpm]] (cómo correr tsc sin pnpm en PS).
