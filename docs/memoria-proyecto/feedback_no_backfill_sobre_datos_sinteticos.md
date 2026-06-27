---
name: feedback-no-backfill-sobre-datos-sinteticos
description: "Antes de proponer un backfill que llame a un servicio externo (geocoding, validación, etc.), inspeccionar la plausibilidad de los datos seed. Direcciones random no se pueden geocodificar."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: dfc52c6d-67d2-4a36-93ca-2b5655f60612
---

Si el backfill propuesto invoca un servicio externo (Nominatim, validador CUIT, scraper, etc.), antes de escribir el script o pedir confirmación: **inspeccionar un sample de 10-15 filas y juzgar si los inputs son plausibles**. Si los datos vienen de un seed con `random()` (alturas inventadas, nombres genéricos, teléfonos secuenciales), el servicio externo va a devolver basura o NULL en la mayoría de los casos — y vas a marcar lat/lon a registros con coordenadas que NO corresponden al titular real.

**Why:** Sesión 2026-05-15 (cierre). Después de pasar lat/lon a ciudadanos y empresas, planteé backfill de 502 ciudadanos sin lat/lon. Confirmé con el usuario y arranqué dry-run de 8 min. Mientras corría, miré por curiosidad el contenido — las alturas eran números random altísimos (1260, 5012, 8796, 9429 sobre calles "Mitre", "Belgrano", "Las Heras" de Vicente López). Esas alturas NO existen en esas calles. ~10% son directamente ficticias ("Calle Falsa", "Av. Siempre Viva"). El backfill iba a marcar ~150 registros con coordenadas falsas y dejar ~350 sin coords. Aborté.

**How to apply:** Antes de armar un script de backfill que cruce datos contra un servicio externo:

1. `SELECT campo_clave FROM tabla WHERE <condicion> ORDER BY random() LIMIT 15;` — leer 15 filas reales.
2. Pregunta concreta: "¿estos valores se generaron a mano por un usuario, o vinieron de un seed?". Si los CSV están en `Tablas Iniciales/`, recordá [[feedback_aprendizajes_proyecto]] § "Antes de codear un seed, inspeccionar el CSV" — la lógica es la misma pero hacia el otro lado.
3. Si el dato es sintético: el backfill agrega ruido, no señal. Mejor declarar el backfill como innecesario y dejar que los registros reales (form nuevo con validación OSM) llenen la columna por construcción.
4. Si el dato es real pero algunos van a fallar: dry-run primero, calcular tasa de éxito sobre **el dataset completo**, y solo aplicar si >70%. Tomar la decisión con números, no con la idea.

**Patrón de razonamiento operativo:** "datos malos in, datos malos out". El servicio externo no inventa la calidad que tu input no tiene. Si tu fuente es seed sintético, el backfill no resuelve nada — agranda el problema.

Aplica también a: validación CUIT/CUIL masiva contra AFIP, normalización de nombres contra una API, lookups de email contra un MX, etc.
