---
name: pendiente-verificar-es-gap
description: "Un pendiente fraseado como \"probar/verificar X\" puede esconder código faltante — mapear el flujo completo antes de tratarlo como testing"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 60476c25-6910-4b32-b3ff-d508b6a4040f
---

Un pendiente del backlog fraseado como "verificar/probar X" o "falta probar con Y real" NO siempre es solo testing. Puede esconder un eslabón de implementación que nunca se construyó.

**Why:** sesión 2026-05-14 jornada 4 — el pendiente "Vista autoservicio Agenda con QR físico real — falta probar con app móvil/lector QR real" parecía una tarea de verificación manual. Al mapear el flujo completo descubrí que el QR generaba un código opaco (`EVT{id}-RES{id}-{ts}`) pero **no existía ningún endpoint que lo consumiera** — el operador podía escanear el QR pero el sistema no tenía cómo acreditar la asistencia con ese string. El "verificar" escondía un endpoint faltante (`POST /agenda/reservas/acreditar-qr`).

**How to apply:** antes de tratar un pendiente "verificar/probar" como testing puro:
1. Mapear el flujo completo end-to-end: quién genera el dato, quién lo consume, con qué endpoint, qué hace la UI.
2. Chequear que cada eslabón exista realmente (grep el endpoint, abrir el componente).
3. Si falta un eslabón → es trabajo de implementación, no de QA. Avisar al usuario y, si hay decisión de alcance, preguntar con AskUserQuestion antes de codear.

Esto refina [[feedback_verificar_forms_navegando_mandatorio]] (que dice "verificá vos") y [[feedback_seedear_cuando_mesa_vacia]]: a veces el motivo por el que "no se puede verificar" es que la feature está incompleta, no que falta seed.
