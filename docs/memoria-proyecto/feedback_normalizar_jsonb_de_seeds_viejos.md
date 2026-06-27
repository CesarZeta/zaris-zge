---
name: feedback_normalizar_jsonb_de_seeds_viejos
description: Datos JSONB de seeds/migraciones viejos pueden tener un shape distinto al que produce el editor actual; el componente que los consume debe normalizar defensivamente.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b4719515-20a5-4b6a-9899-616010dafa3f
---

Una columna JSONB que el editor actual produce con un shape (`opciones_jsonb` = `[{valor,etiqueta}]`) puede tener **filas viejas con otro shape** seedeadas antes de que el editor existiera. Cazado 2026-05-27 al hacer el preview del formulario de Trámites (BUG-06): el campo "Especie aproximada" del seed guardó `opciones_jsonb` como **`{ opciones: ["nativa","exotica","no_se"] }`** (objeto con array de strings), no `[{valor,etiqueta}]`. `(opciones_jsonb ?? []).map(...)` reventaba con "map is not a function" — root vacío + error boundary pegado.

**Why:** el seed (`seed_tramites.py`) y el editor React nuevo no comparten el formato. La doc/los tipos TypeScript declaran el shape "correcto" (`Array<{valor,etiqueta}>`), pero los datos reales en DB son lo que algún seed viejo escribió. Confiar en el tipo declarado y hacer `.map` directo rompe en runtime solo con esas filas — invisible hasta que tocás un tipo seedeado.

**No era bug del feature nuevo:** el mismo dato habría reventado la **pantalla de alta real** (`CrearTramite` usa el mismo `CampoDinamico`) al instanciar un trámite de ese tipo. El preview solo lo destapó antes. Arreglar en el componente que consume el JSONB (no en el preview) corrige ambos caminos de una.

**How to apply:**
- Antes de hacer `.map`/`.length`/spread sobre una columna JSONB en el frontend, **normalizá defensivamente** tolerando los shapes que pudieron existir. Patrón usado en `CampoDinamico.tsx::normalizarOpciones`: si es objeto con `.opciones`, usar eso; si es array de strings, mapear a `{valor:s, etiqueta:s}`; si ya es `[{valor,...}]`, respetarlo; filtrar vacíos.
- El normalizador va en el **componente que consume** el dato (así protege todos los callers), no en cada vista por separado.
- Vale para cualquier JSONB con historia: `validacion_jsonb`, `quien_puede_jsonb`, `opciones_jsonb`, `firmantes_jsonb`, etc. Si un seed lo escribió antes de que existiera la UI de edición, sospechá del shape.
- **Diagnóstico:** si una vista React queda con root vacío SIN error en la consola del browser, mirá si hay un error boundary tragándolo; un `.map is not a function` casi siempre es shape de datos, no lógica. Familia de [[reference_bi_lineamientos_visualizaciones]] (root vacío sin error en consola del browser).
- Relacionado con asyncpg + JSONB en el backend (§35: `CAST(:v AS jsonb)` + `json.dumps`), pero esto es del lado del consumo en el frontend.
