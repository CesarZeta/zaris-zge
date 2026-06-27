---
name: feedback_triagear_informe_qa_externo
description: "Un informe de QA externo (PDF de Roy) NO es lista de bugs a codear — triagear cada hallazgo contra la realidad: bug de sistema vs config del tipo vs falso positivo vs mezcla de artefactos."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 08bb606e-1c29-403e-8e82-47ed824e60b3
---

Cuando el usuario trae un informe de QA de un tester (Roy ya trajo varios: 27/05, 31/05, 01/06), tratarlo como **propuesta a verificar**, no como lista de bugs a arreglar. Antes de codear nada, cruzar CADA hallazgo contra la realidad (DB de prod con execute_sql, código con Read, navegador) y clasificarlo. Los hallazgos suelen caer en 4 categorías y solo una se arregla con código:

- **Bug real del sistema** → se codea. (Ej. 01/06 #7: campos `direccion` sin mapa interactivo.)
- **Config del tipo/instancia, no del sistema** → se arregla configurando bien (builder/DB), no tocando código. En Trámites, los campos del paso 4 son **dinámicos** (los pone quien diseña el tipo en el builder): "Solicitante", "Fecha de solicitud", "ayuda confusa" eran campos que Roy mismo agregó al tipo "Aviso de Obra", no comportamiento del producto.
- **Falso positivo** → la propia evidencia del informe lo desmiente. (Ej. 01/06 #4/#5: "los campos no aparecen" cuando su propia captura los mostraba; las pestañas del editor existen y funcionan.)
- **Mezcla de artefactos** → el tester combina capturas de contextos distintos en un mismo hallazgo. (Ej. 01/06: las figuras eran de DOS tipos de trámite distintos — "cambio-domicilio-comercial" Y "aviso-obra" — lo confirmé consultando `tipo_tramite_campo` en prod por cada figura.)

**Why:** codear lo que parece un bug sin verificar lleva a "arreglar" cosas que no están rotas (#4/#5) o a meter código donde la solución es config (#2/#6/#8). El crítico del informe 01/06 ("el usuario no tiene un agente asociado") era del propio Roy (admin sin fila en `agentes`), no del producto — el usuario explícitamente pidió obviarlo.

**How to apply:**
- Por cada figura/hallazgo: ¿de qué entidad/tipo concreto es esta captura? Consultarlo en prod (`tipo_tramite_campo`, etc.) antes de asumir.
- Distinguir explícitamente "esto es del sistema" de "esto lo configuró quien creó el tipo". En Trámites: campos del paso 4 = dinámicos del builder.
- Devolver al usuario el triage (bug/config/falso-positivo) ANTES de codear, y pedir decisión en los que son criterio de producto (AskUserQuestion). No empezar por el archivo de código.
- Generaliza [[feedback_verificar_siempre_antes_de_opinar]] y §28 (prompts armados afuera) al caso específico de informes de QA.
