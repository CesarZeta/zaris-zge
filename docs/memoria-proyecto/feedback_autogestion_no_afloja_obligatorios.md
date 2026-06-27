---
name: feedback-autogestion-no-afloja-obligatorios
description: "Regla del municipio: todo dato obligatorio internamente también lo es para la autogestión del vecino. El form de autoservicio nunca puede pedir MENOS que el alta interna; puede pedir MÁS."
metadata:
  type: feedback
---

Regla de negocio del usuario (2026-06-02): **todos los datos del ciudadano y del reclamo que son obligatorios internamente (backoffice) también lo son para la autogestión del vecino.** El formulario de autoservicio nunca puede ser más laxo que el alta interna que usan los operadores; puede ser más estricto.

**Why:** al construir el form "Nuevo reclamo" de la PWA lo armé con casi todo opcional (solo descripción). El usuario corrigió: la autogestión no afloja obligatorios. Caso concreto: el backoffice de reclamos exige solo `id_ciudadano` + `descripcion≥5` (tipo/dirección opcionales AHÍ también), pero el usuario decidió **subir el piso** para autogestión → tipo + dirección OBLIGATORIOS en el form del vecino.

**How to apply:**
- Antes de definir qué pide un form de autoservicio, leer qué exige el alta interna REAL — y no solo el schema Pydantic del backend, también el form del frontend backoffice (`validarAlta()` en `FormView.tsx` puede exigir más que el schema). El piso es el más alto de los dos.
- Hacer cumplir la obligatoriedad en EL BACKEND, no solo en la UI (no evadible por curl — [[feedback_guard_nivel_endpoint_no_solo_ui]]). En `publico_reclamos.py` el POST valida tipo+dirección+descripción con 422.
- En el front, validación en vivo + pista de qué falta (no botón gris mudo, §23): "Falta completar: el tipo, la dirección."
- Para el CIUDADANO la regla aplica al alta/autoregistro (en autogestión el ciudadano ya existe vía token). El autoregistro `alta-vecino.html` ya cumple — auditado 2026-06-02, es MÁS estricto que el alta oficial (domicilio obligatorio ahí, opcional en `CiudadanoBase`). Ver [[project_usuario_vs_ciudadano_modelo]].
