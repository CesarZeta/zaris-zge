---
name: nomenclatura-shell
description: "Vocabulario obligatorio para hablar de las superficies del proyecto ZARIS. No decir \"web-app\" como si fuera el producto entero."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 9f22ae1e-23dd-4dae-9ee4-6c68e1a34b76
---

"web-app" es el nombre de un DIRECTORIO (`web-app/`), no del producto. El producto entero es ZARIS y todo es "la app web". Confundirlos genera ambiguedad cuando hay multiples modulos viviendo en distintas superficies.

Convencion fijada por el usuario (2026-05-11):

- **"shell vanilla"** = `index.html` en la raiz + `frontend/*.html`. Lo que hoy vive en GitHub Pages prod.
- **"shell React"** = el AppShell con sidebar+topbar+router que corre en `web-app/` (localhost:5173 en dev).
- **"modulo X (React)"** = implementacion del modulo X en `web-app/src/modules/<x>/`. Ej: "modulo Agenda (React)".
- **"modulo X (vanilla)"** = implementacion del modulo X en `frontend/`. Ej: "modulo Reclamos (vanilla)".
- **"el producto"** o **"ZARIS"** cuando me refiero a la app entera.

**Why:** el usuario va a desarrollar mas modulos en shell React a futuro (no solo Agenda). Llamar "web-app" a todo lo que vive en `web-app/` mezcla el contenedor con el contenido. Tambien dificulta hablar de migraciones tipo "modulo Reclamos pasa de vanilla a React" si no hay nombres distintos para cada cosa.

**How to apply:** cada vez que vayas a decir "web-app" en una respuesta, parar y preguntarse: ¿me refiero al directorio? ¿al shell React? ¿a un modulo específico? ¿al producto? Y usar el termino correcto. Vale para conversaciones, commits, documentacion en CLAUDE.md.
