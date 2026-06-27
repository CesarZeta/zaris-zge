---
name: smoke-cleanup-prod-inmediato
description: "CAMBIO 2026-06-11: los datos de prueba en prod YA NO se limpian — el usuario pidió conservarlos como seed de demos. Identificarlos bien; limpiar solo lo roto/duplicado."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f0897cd7-1f6d-48cb-8ad7-2a9362f457e8
---

**Directiva vigente (usuario, 2026-06-11, sesión App Vecinos):** *"Todo incidente que generes, por más que sea para pruebas, conservalos para que nos sirvan de seed para demos."* Aplica a reclamos, turnos, emergencias, entradas, etc. creados por smokes o QA navegando, en local Y prod.

**Regla actual:**
1. **NO soft-deletear ni borrar** lo creado por smokes/QA — queda como dato demo. ZARIS está en etapa pre-piloto: prod ES la demo.
2. **Sí identificar el origen** en descripción/observaciones (ej. "prueba E2E etapa B") — sirve para auditar después qué es sintético.
3. **Sí limpiar** lo que quedó **roto o inconsistente** (filas a medias por un smoke que falló, duplicados exactos, datos que violan invariantes) — eso no es demo, es basura.
4. **Datos con efectos secundarios** (encuestas que mandan email, eventos en el tablero de guardia del COM): crear igual si el flujo lo pide, pero avisar al usuario qué quedó vivo y qué efecto tendrá.

**Historia (regla anterior, vigente 2026-05-12 → 2026-06-11):** todo smoke en prod llevaba cleanup inmediato en el mismo script (caso REC-2026-000022). El patrón de *identificar* lo creado (texto "Smoke X" + RETURNING id) sigue siendo válido — solo cambió el paso final: conservar en vez de borrar. El reclamo REC-2026-000041 de prod (smoke etapa A) fue restaurado (activo=TRUE) al entrar esta directiva; su adjunto binario ya se había borrado del bucket (no recuperable).

Complementa [[feedback_smoke_listar_users_primero]] (mapear identidad antes de un smoke).
