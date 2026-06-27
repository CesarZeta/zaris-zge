---
name: feedback_admin_tablas_checklist_tabla_nueva
description: "Al agregar una tabla a admin_tablas, hay 4 lugares que deben tocarse en sincronía — olvidar uno deja la tabla operativa en backend pero invisible o muerta en frontend"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e7b5da85-1482-4943-b52c-9c40bbde7b8d
---

Cuando se agrega una tabla al módulo admin_tablas, se requieren cambios en **4 lugares**. Omitir cualquiera produce un síntoma distinto:

| Lugar | Síntoma si falta |
|---|---|
| `TABLE_CONFIG` en `backend/app/api/routes/admin_tablas.py` | 404 al llamar a la API (`Tabla no administrable`) |
| Sidebar (`<div class="sidebar-item" data-tabla="...">`) en `frontend/admin_tablas.html` | La tabla no aparece en el menú lateral |
| `SCHEMAS` (JS) en `frontend/admin_tablas.html` | La tabla aparece en el sidebar pero no abre nada al hacer clic |
| `ICONS_MAP` (JS) en `frontend/admin_tablas.html` | Error JS silencioso al intentar cargar la tabla — no renderiza el header con ícono |

**Casos reales sesión 2026-05-17:**
- `estado_ot` — tenía backend pero le faltaban los 3 items de frontend (sidebar + SCHEMAS + ICONS_MAP).
- `equipo_agentes` — igual que el anterior.

**Why:** el ICONS_MAP es el que más se olvida porque es el último en el archivo y no produce error de validación visible — simplemente no renderiza el ícono del header y puede crashear la carga.

**How to apply:** al agregar una tabla nueva, completar el checklist de 4 ítems antes de hacer commit. El orden de edición natural: backend TABLE_CONFIG → frontend sidebar → frontend SCHEMAS → frontend ICONS_MAP.

**Simétrico:** al ELIMINAR una tabla (tabla dropeada en migración), removerla de los 4 lugares. Si solo se quita del backend, el sidebar muestra el ítem pero da 404 al hacer clic. Casos reales: `equipo_usuarios`, `reclamos_area`, `reclamos_subarea` — permanecieron como ítems muertos hasta este QA.
