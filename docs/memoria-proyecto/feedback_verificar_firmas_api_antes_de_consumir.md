---
name: feedback_verificar_firmas_api_antes_de_consumir
description: "Antes de escribir un componente que llame a api.ts, leer la firma exacta de cada función y el tipo real del response. Evita 10 errores TS de una sola vez."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f84d7548-b002-463d-8332-dbf8d5375172
---

Antes de escribir cualquier componente o página que consume funciones de `lib/api.ts` de un módulo, abrir ese archivo y leer:

1. **Nombre exacto de la función** — ¿`relacionarTramite` o `relacionarTramites`? ¿`pasarTramite`?
2. **Firma de parámetros** — ¿`(numero, file, opts?)` o `(id, file, nombre, onProgress)`? ¿`destinatario_id` o `id_destinatario`?
3. **Tipo real del response** — ¿`{items, total}` o `{movimientos, total}` o un array plano?

**Por qué:** en la sesión 2026-05-16, escribir `FileUploader`, `ModalPase`, `ModalRelacionar`, `PanelAcciones` y `DetalleTramite` sin releer `api.ts` generó 10 errores de TypeScript en el pre-commit hook, todos evitables con 2 minutos de lectura previa:

| Error | Causa evitable |
|---|---|
| `relacionarTramites` no existe | Nombre real: `relacionarTramite` (singular) |
| `id_destinatario` vs `destinatario_id` | ModalPase y PanelAcciones usaron nombres distintos |
| `adjuntarDocumento(id, file, str, fn)` | Firma real: `(numero, file, opts?)` con objeto |
| `{items, total}` en movimientos | Response real: `{movimientos, total, numero_expediente}` |
| `numero_tramite_a/b` en relaciones | Campo real: `numero_expediente_relacionado` |

**Cómo aplicar:** el checklist es `Read(api.ts)` → `Read(types.ts)` → recién entonces escribir el componente. 5 minutos de lectura = 0 errores TS al commitear.

**Relacionado con:** [[feedback_leer_patron_existente_antes_de_implementar]], [[feedback_tsc_b_vs_noEmit]].
