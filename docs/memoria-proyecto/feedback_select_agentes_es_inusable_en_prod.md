---
name: select-agentes-es-inusable-en-prod
description: Cualquier <select> con catalogo completo de agentes/equipos es inusable en prod (84 agentes). Usar RecursoPicker de Agenda con autocompletar.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 27c74ea3-2e69-4115-a25a-69ddf39a7d17
---

Si vas a montar un selector de agente o equipo activo del municipio, NO uses `<select>` con catalogo completo. En prod hay ~84 agentes activos y un select largo es inusable (scroll infinito, sin filtro).

**Regla:** reusar `web-app/src/modules/agenda/components/RecursoPicker.tsx` (cross-module import OK, ver [[feedback_cross_module_imports_react]]). Consume `GET /agenda/catalogos/recursos?q=&tipo=&limit=` con debounce 250ms y dropdown filtrado.

**Why:** sesion 2026-05-15 cazo este patron repetido en 4 lugares: `RecursoPicker` original (Agenda), `PlanificadorOT` (OT supervisor), `TurnoFormModal` (Turnos). En local con 4 agentes el select se ve bien y el bug pasa desapercibido en review; en prod recien se nota cuando alguien hace scroll.

**How to apply:**
- Crear/editar formularios que pidan agente o equipo: **siempre RecursoPicker** salvo que sea catalogo chico estable (<20 items) y nunca crezca.
- Para readonly (edicion bloqueada): `<div>` con texto del nombre + hint, no `<select disabled>`.
- Si `tipo` cambia entre 'agente' y 'equipo', el RecursoPicker resetea su `q` interno automaticamente (fix aplicado en commit `e2cf868`).

Aplica al patron analogo de **espacios**: hoy hay 2-3 espacios y un select va bien, pero si el municipio carga 50+ espacios hay que migrar `EventoEntradaFormModal` y el selector en `OcupacionModal`.
