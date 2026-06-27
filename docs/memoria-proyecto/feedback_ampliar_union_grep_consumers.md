---
name: ampliar-union-grep-consumers
description: "Antes de ampliar un type union central (ej. TipoRecurso 2→3 variantes), grep todos los consumers y decidir cuál acepta el nuevo variant vs cuál se restringe al subset viejo. TypeScript caza el call site pero no la decisión semántica."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ba8c5bce-d171-4427-a27f-16245ac2b25e
---

Cuando ampliás un type union central de un módulo (ej. `TipoRecurso = 'agente'|'equipo'` → `'agente'|'equipo'|'espacio'`), TS te va a tirar errores en cada consumer que no acepta la nueva variante. Esos errores marcan **dónde rompe**, pero no contestan **la pregunta semántica**: ¿este consumer debe aceptar la nueva variante o restringirse al subset viejo?

**Why:** Ampliar una unión es un breaking change semántico, no solo de tipos. Cada consumer hace una asunción implícita que vale revisar.

**How to apply:**
1. Antes de ampliar, `grep` el nombre del type en todo el módulo: `Grep "TipoRecurso" --type=tsx,ts`.
2. Para cada hit, decidir: (a) acepta el nuevo variant tal cual, (b) requiere lógica nueva, (c) se restringe al subset viejo via un type alias local.
3. Casos del paso (c) merecen tipo nombrado, no cast inline. Ej:
   ```ts
   // EventoEncargadosModal: espacio NO puede ser encargado de evento.
   type EncargadoTipoRecurso = 'agente' | 'equipo'
   const [tipo, setTipo] = useState<EncargadoTipoRecurso>('agente')
   ```
4. Si descubrís un consumer (c) **después** del typecheck, no lo "arregles con cast" — replicá el patrón del alias.

Caso real sesión 2026-05-13 (Agenda B2): amplié `TipoRecurso` agregando `'espacio'`. Cazó:
- `useAgenda.ts`, `agendaApi.ts`, `RecursoAgenda`, `Ocupacion.*` aceptan el nuevo variant naturalmente (passthrough).
- `EventoEncargadosModal.tsx` NO debe — un espacio no es encargado de un evento, se linkea via `eventos.id_espacio`. Resuelto con `type EncargadoTipoRecurso = 'agente'|'equipo'` local.
- `RecursoPicker.tsx` se quedó con su tipo `'agente'|'equipo'` viejo por la misma razón (es selector de personas/equipos, no incluye espacios).

Si lo hubiera detectado **antes** de codear, el orden hubiera sido más limpio (decidir → codear) en vez de (codear → typecheck → arreglar inconsistencias).

Relacionado: [[feedback_proponer_fases_antes_de_codear]] (verificar realidad antes de codear), [[feedback_vincular_por_id]] (en B1 los espacios se linkean vía id_espacio en la entidad, no via la N:M de encargados).
