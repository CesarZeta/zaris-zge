---
name: feedback-verificar-fix-seguridad-en-prod-durante-deploy
description: "Al verificar un fix de SEGURIDAD contra prod mientras Railway despliega, el primer intento pega al código VIEJO y ejecuta el bug que estás arreglando. Usar un probe NO destructivo o limpiar lo que cree."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c0686d84-5411-438f-9006-4373e9d0fe24
---

Cuando pusheo un fix de seguridad (auth, validación, guard) y hago polling contra prod para confirmar que aplicó, el deploy de Railway tarda 1-3 min (§9: autodeploy no confiable, suele haber un 502 transitorio). **Durante esa ventana prod sigue corriendo el código VIEJO** — y si mi probe de verificación ejerce justamente el endpoint vulnerable, lo explota de verdad contra prod.

**Why:** sesión 2026-05-22, verificando el fix de auth del router BUC. El probe era `POST /api/v1/buc/usuarios` sin token (esperando 401). El intento 1 pegó al deploy viejo → **201: creó un admin nivel 1 real** (`__probe_noauth__`, id 92) en prod. Tuve que loguearme y darlo de baja. La verificación funcionó (intento 3 dio 401), pero de paso ejecuté el bug.

**How to apply** — al verificar un fix de seguridad en prod durante el deploy:

1. **Preferí un probe READ-ONLY de control.** En vez de ejercer la mutación vulnerable, chequeá un GET que cambie de comportamiento con el fix. Ej: para el guard del router BUC, `GET /buc/nacionalidades` sin token (200 viejo → 401 nuevo) confirma el deploy SIN crear nada. Esto fue lo que usé en la 3ª tanda (guard de router) y no ensució nada.

2. **Si el probe DEBE ser la mutación** (porque el fix solo afecta escritura), asumí que el intento contra el deploy viejo va a tener efecto real:
   - Usá datos marcables (`__probe_*`, descripción "smoke fix YYYY-MM-DD") para poder limpiarlos por LIKE.
   - Incluí el cleanup en el mismo bloque, condicional: si el POST devolvió 201 (viejo), dar de baja inmediatamente lo creado.
   - Verificá que lo creado NO sea explotable mientras tanto (ej: el admin probe sin email no podía loguear → 401).

3. **El 502 transitorio NO es el fix aplicando** — es el redeploy reiniciando. No lo cuentes como confirmación. El control es el cambio de comportamiento del endpoint (200→401), no que deje de responder.

Complementa [[smoke-cleanup-prod-inmediato]] (limpiar lo que se crea) y [[feedback_polling_login_dentro_del_loop]] (login dentro del loop porque el 502 mata un login hecho afuera). Diferencia clave de esta: acá el probe mismo es el vector, no solo basura semántica.
