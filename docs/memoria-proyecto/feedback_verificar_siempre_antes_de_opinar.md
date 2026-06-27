---
name: feedback_verificar_siempre_antes_de_opinar
description: "Regla mandatoria de por vida — nunca asumir, verificar siempre antes de opinar/afirmar"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a0bc3f28-6b1c-4f19-bcda-aa6306374a59
---

NUNCA asumir nada. Verificar SIEMPRE contra la realidad (DB con execute_sql, código con Read/Grep, runtime con curl, navegador con browser-mcp, git log) ANTES de opinar, afirmar o recomendar. Mandatorio a nivel proyecto y en TODAS las interacciones del usuario, de por vida.

**Por qué:** el usuario lo declaró regla permanente (2026-05-23). Su realidad vive en el sistema corriendo, no en la documentación ni en mis suposiciones. Una afirmación sin verificar es un error aunque suene plausible. Ya pasó varias veces en esta sesión: asumí que el admin prod era `ciudadanovl@` (era `cesar@`), que la app password Zoho es de 16 chars (la real que funciona es de 12 — la doc §35 generalizó mal), que `_resolver_reclamo` commiteaba (no lo hace), que la firma de `crear_envio_para_reclamo` devolvía un objeto (devuelve tupla). Cada suposición costó un round-trip.

**Cómo aplicar:**
- Antes de afirmar un hecho sobre el código/DB/infra: leerlo/consultarlo primero. No deducir de la doc (puede estar atrás) ni de memoria.
- Si no puedo verificar algo (ej. logs de Railway, env vars que no veo), decirlo explícito como "no verificado" en vez de presentarlo como hecho.
- Distinguir siempre "lo verifiqué y es X" de "probablemente sea X" — y cuando sea lo segundo, ir a verificarlo antes de cerrar.
- Refuerza y generaliza [[feedback_verificar_forms_navegando_mandatorio]], [[feedback_verificar_pendientes_antes_de_atacar]], [[feedback_verificar_drift_completo_prod]], [[feedback_sintoma_usuario_no_es_diagnostico]].
