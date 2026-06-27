---
name: calibrar-alcance-migracion
description: "Antes de prometer \"migro el módulo X a React\", abrir el HTML + el JS y contar LOC. ~1700 LOC vanilla no equivale a 1 sesión React. Casos reales en BUC."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4ed10f75-1110-405b-a93b-8ba08aa79fe3
---

Antes de comprometer alcance ("migro el módulo X a React en esta sesión"), **abrir los archivos vanilla y medir**:

```bash
wc -l frontend/<modulo>.html frontend/js/<modulo>.js
grep -c "^async function\|^function" frontend/js/<modulo>.js
grep "@router\." backend/app/api/routes/<modulo>.py | wc -l
```

**Regla de pulgar:** >1500 LOC entre HTML+JS + más de 5 endpoints = al menos 2 sesiones largas, no 1.

**Why:** Esta sesión (2026-05-12) "BUC ciudadanos+empresas" se pensó como una unidad. Al abrir los archivos descubrí que eran:
- `ciudadano.html` (572 LOC) + `ciudadano.js` (997 LOC) = 1569 LOC solo Ciudadanos
- `empresa.html` (352 LOC) + `empresa.js` (703 LOC) = 1055 LOC Empresas
- ~2624 LOC total con features complejas: form anidado empresa, lookups de duplicados, modos new/edit/view, autogeneración CUIL, listado con filtros+imprimir.

Tuve que parar mid-sesión y preguntar al usuario cómo acotar (`AskUserQuestion` con 4 opciones). Si lo hubiera medido al principio, hubiera presentado la opción acotada **antes** de leer los 1569 LOC.

**How to apply:**
1. Cuando el usuario pida "migrar X a React" (o tarea de scope similar), **antes** de leer todo, hacer `wc -l` + `grep` rápidos para tener un número.
2. Si pasa de ~1500 LOC vanilla, **ofrecer dividir** vía `AskUserQuestion` antes de empezar a codear, no en el medio.
3. Mencionarle al usuario el número concreto: "ciudadano.html son 1569 LOC + 11 endpoints, eso es ~3-4h de trabajo React".

Relacionado: [[project_patron_deploy_modulo_react]] tiene el patrón probado de despliegue pero no menciona estimación.
