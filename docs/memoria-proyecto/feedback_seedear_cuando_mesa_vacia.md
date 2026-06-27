---
name: feedback-seedear-cuando-mesa-vacia
description: "Si verificar visualmente requiere setup de <5min de comandos seguros, seedear+verificar+cleanup vence a \"declarar no-validado\". Refinamiento de [[feedback_verificar_forms_navegando_mandatorio]]."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5c09709a-c98e-47c6-ad6e-b77d0e2b7153
---

Cuando un módulo tiene flujo dependiente (mesa vacía porque no hay datos en ese estado) y el setup es 3-5 comandos seguros, **seedear, verificar end-to-end y limpiar después** vale más que escribir "no validado, código idéntico al anterior".

**Why:** sesión 2026-05-13 (OT drawer). La mesa Auditoría estaba vacía en local. Mi primer instinto fue declarar "no validado visualmente — código idéntico a Agente, typecheck OK". El usuario pidió "POR FAVOR SEDEEAR". Tomó 4 comandos:
1. `UPDATE reclamos SET id_tipo_reclamo=6` (cambiar a un tipo con `audit=TRUE`)
2. `POST /ot` con `id_agente=1` (asignar)
3. `PUT /ot/{id}/estado` con `Terminada` (backend auto-genera la OT de auditoría)
4. Cleanup: `UPDATE` + `DELETE` para revertir.

Validó el drawer mostrando 2 OTs (origen + auditoría), badge "Esta OT" + badge "Auditoría", historial con 3 entradas reales. Mucho más fuerte que "es idéntico al de Agente".

**How to apply:**
- Antes de declarar "no validado por falta de datos", evaluar: ¿el setup es 3-5 comandos seguros (en local, idempotentes, con cleanup obvio)? Si sí, seedear.
- Cuándo NO seedear:
  - Setup requiere modificar prod.
  - Setup requiere migración de schema.
  - Setup requiere >10 min de coordinación (crear ciudadano + empresa + reclamo + activo + adjunto + asignación + ...).
  - Cleanup no es obvio (el seed deja state que dispara triggers cascade y no sé revertirlo sin riesgo).
- Cleanup en el mismo bloque que el seed (memoria [[feedback_smoke_cleanup_prod]] aplica también a local).
- Avisar antes: "voy a seedear X, hacer Y, cleanup Z" — el usuario puede vetar.

**Patrón de comandos para OT auditoría (referencia rápida):**
```bash
# 1. Cambiar tipo de un reclamo Sin asignar a uno con audit=TRUE
psql ... -c "UPDATE reclamos SET id_tipo_reclamo=<id_audit> WHERE id_reclamo=<X>"
# 2. Login + asignar OT
TOKEN=$(curl -s POST /auth/login ... | jq -r .access_token)
curl -X POST /ot -d '{"id_reclamo":X,"id_agente":1}'
# 3. Terminar la OT (dispara auditoría auto si tipo.audit=TRUE)
curl -X PUT /ot/{id}/estado -d '{"estado":"Terminada"}'
# 4. Cleanup
psql ... -c "UPDATE ordenes_trabajo SET activo=FALSE WHERE id_ot IN (...); UPDATE reclamos SET estado='Sin asignar', id_tipo_reclamo=NULL WHERE id_reclamo=X; DELETE FROM reclamo_historial WHERE id_reclamo=X AND id_historial > <baseline>"
```
