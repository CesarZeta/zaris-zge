---
name: feedback-loop-envio-probar-ambas-fallas
description: "Loop de envío best-effort (push/email a N destinos): catch POR ITEM además del catch externo, y probar DOS modos de falla distintos — datos con formato inválido (explota ANTES del HTTP) y datos válidos contra destino muerto (explota EN el servicio). Cada uno ejercita un código distinto."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 24bcb12b-67b1-4877-bced-dfe51f3d7df3
---

En un loop que envía a N destinos (push a suscripciones, mails a una lista), una excepción de UN item que no esté capturada **dentro** del loop corta el envío a los restantes, aunque el caller tenga un try/except global (best-effort "de afuera" ≠ best-effort por item).

**Caso real (services/push.py, etapa E, 2026-06-12):** `_webpush_sync` solo capturaba `WebPushException`. Una suscripción con claves corruptas hacía explotar el CIFRADO (ValueError) **antes** del request HTTP → la excepción salía del loop → las demás suscripciones del ciudadano no se enviaban. El catch externo lo tapaba (la operación devolvía 200), así que el bug era silencioso. Lo cacé porque probé con un `p256dh` falso de formato inválido.

**Why:** los dos modos de falla ejercitan ramas distintas: (a) **formato inválido** → falla pre-envío (cifrado/serialización) → debe capturarse por item y seguir; (b) **formato válido + destino muerto** (endpoint FCM inexistente real) → el servicio responde 404/410 → debe disparar la limpieza (auto-baja §19). Probar solo (b) deja la rama (a) sin cobertura y viceversa.

**How to apply:** en todo loop de envío: catch genérico POR ITEM (log + continuar) + manejo del status del servicio (404/410 → soft-delete). Y en el smoke, sembrar AMBOS tipos de dato roto: uno mal formado y uno bien formado apuntando a un destino inexistente, verificando que la operación de negocio devuelva 200 igual y que la limpieza automática ocurra solo para (b).
