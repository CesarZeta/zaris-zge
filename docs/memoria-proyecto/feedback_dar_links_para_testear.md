---
name: Pasar links concretos al pedir test visual
description: Cuando el usuario tiene que probar algo visualmente, dar el URL exacta a abrir (local si los cambios están en local, prod si ya están deployados). No describir "andá a tal lado".
type: feedback
---
Cuando termino una tarea y le pido al usuario que verifique visualmente el resultado, debo darle el URL concreto a abrir, no instrucciones de navegación.

**Why:** el usuario quiere abrir el link y ver. Decirle "abrí Reclamos en el menú" lo hace navegar de más cuando podría hacer clic directo.

**How to apply:**
- Si los cambios están **solo en local** (no hice push), pasarle la URL local relevante:
  - Frontend vanilla: `http://localhost:8080/index.html?modulo=frontend/reclamos.html` (ruta del shell con el módulo precargado, gracias al patrón `?modulo=` documentado en CLAUDE.md §14 / sesión 2026-05-10).
  - Si el módulo es standalone: `http://localhost:8080/frontend/<nombre>.html`.
  - API local Swagger: `http://127.0.0.1:8000/docs`.
  - Aclarar que necesita tener corriendo `python -m http.server 8080` (raíz del repo) y `uvicorn app.main:app --host 127.0.0.1 --port 8000` (desde `backend/` con `$env:ENV_FILE=".env.local"`).
- Si los cambios ya están en **prod** (push hecho + Railway / GitHub Pages deployaron):
  - Frontend prod con módulo precargado: `https://cesarzeta.github.io/zaris-zge/index.html?modulo=frontend/reclamos.html`.
  - Swagger prod: `https://zaris-api-production-bf0b.up.railway.app/docs`.
- Si hay cambios mixtos (frontend en prod + backend local, o viceversa), aclarar cuál URL apunta a qué.
- Cuando aplique, también pasar pasos concisos de qué clickear dentro de la página (ej. "abrí REC-2026-000022 → botón Editar reclamo").
