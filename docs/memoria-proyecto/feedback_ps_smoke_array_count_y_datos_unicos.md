---
name: ps-smoke-array-count-y-datos-unicos
description: "Smokes en PS 5.1: (1) (pipe | Where-Object).Count sobre 1 resultado da NULL — envolver en @(); (2) comillas dobles dentro de args a exe nativo (git -m con here-string) rompen el parseo; (3) datos de prueba ÚNICOS por corrida (DNI/tel/nombre random) — los runs previos mutan estado (ej. promoción a BUC) y el assert falla por statefulness, no por bug."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b4c6b4f6-e7c6-435d-87f8-9c654af5ef69
---

Tres trampas cazadas escribiendo `smoke_emergencias.ps1` (2026-06-10), aplican a todo smoke `.ps1` futuro:

**1. `@()` obligatorio antes de `.Count`.** En PS 5.1, `($coleccion | Where-Object {...}).Count` devuelve NULL cuando el filtro matchea exactamente 1 elemento (objeto suelto sin propiedad Count) → el assert falla en falso. Siempre `@($coleccion | Where-Object {...}).Count`. Costó 2 FAIL fantasma.

**2. Comillas dobles dentro de argumentos a exe nativos rompen el parseo.** `git commit -m @'...texto con "comillas"...'@` explotó con `pathspec 'de' did not match` — PS 5.1 re-quotea los args al pasarlos al exe y las `"` internas parten el argumento. En mensajes de commit / args nativos: sin comillas dobles internas.

**Why:** ambos fallan silencioso o con error engañoso, y el diagnóstico apunta al backend cuando el bug es del script.

**How to apply (3 = datos únicos por corrida):** todo smoke que crea entidades identificables (DNI, teléfono, nombre, email) debe generarlas RANDOM por corrida y verificar que no existan antes de usarlas (loop hasta `origen=NUEVO` o equivalente). Los runs previos mutan estado global — en Emergencias, la promoción a BUC convierte el contacto en ciudadano, y la corrida siguiente encuentra "BUC" donde esperaba "EVENTUAL": el sistema está bien, el smoke es stateful. Complementa [[feedback_smoke_cleanup_prod]] (en prod además se limpia).
