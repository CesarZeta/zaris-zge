---
name: agenda-latencia-base-railway-supabase
description: "Cifras de latencia de prod VIGENTES (2026-09-26): round-trip Railway↔Supabase 4-5 ms (misma zona), DB ejecuta en 1-3 ms, piso ~150 ms por request desde Argentina (tramo internacional edge gru1↔Virginia). Un endpoint que tarda segundos NO es la distancia a la DB: es N+1, CPU o inserts masivos. Cómo medir sin engañarse."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 730ba002-bb4e-4ffc-a6c4-7067ae9362ab
  modified: 2026-09-26T21:51:15.824Z
---

**Medido 2026-09-26** (sesión São Paulo, [[project_migrar_region_sao_paulo]]), desde la máquina de
César con conexión HTTP reutilizada, 5-8 muestras por endpoint, en régimen:

| Endpoint (prod, Railway) | Mediana |
|---|---|
| `GET /api/health` (sin DB) | 150 ms |
| `GET /config/identidad` (BEGIN + 2 queries + ROLLBACK) | 172 ms |
| `GET /auth/me` | 187 ms |
| `GET /reclamos?limit=20` | 187 ms |
| `GET /agenda/recursos/conteos` (4 COUNTs) | 189 ms |
| `GET /dashboard/resumen` (6 tarjetas + mapa) | 205 ms |
| `POST /auth/login` (bcrypt) | 570 ms |

**Descomposición del piso (~150 ms):** TCP connect local→edge Railway `gru1` (São Paulo) ~35 ms;
edge↔origen (Virginia) ida y vuelta ~115 ms; app ~1 ms. **Railway↔Supabase: 4-5 ms por viaje**
(22 ms para 4 viajes) — misma zona que Supabase `us-east-1`, conexión directa
`db.<ref>.supabase.co:5432` sin pooler. **DB:** `pg_stat_statements` de 141 días = 166 k queries,
4,7 min de ejecución total, 1,7 ms de media; queries triviales 1-3 ms; `UPDATE usuarios SET
fecha_ultimo_login` 31 ms (la más cara de las frecuentes). Compute Free: `shared_buffers` 224 MB,
`work_mem` 2 MB, `max_connections` 60.

**Cómo usar estas cifras:**
- Reporte de "tarda X" en prod: X < 0,3 s = normal; 0,3-1 s = mirar cuántas queries hace
  (cada una suma ~5 ms + ejecución) o si hay bcrypt/Storage; X > 1 s = N+1, inserts masivos o
  CPU del contenedor — **nunca "la distancia a la DB"**. (El "14,5 min del generador demo" del
  2026-09-21 fue descartado por César como caso aislado: no citarlo.)
- Comparar SIEMPRE contra un endpoint sin DB del mismo momento (`/api/health`): el piso
  internacional varía con la red y con episodios del edge.
- **Trampa cazada el 2026-09-26:** `curl` con conexión nueva por request dio 465 ms (health) y
  1.380 ms (identidad) en 6 muestras seguidas y 10 min después 240/250 ms. No se explicó;
  medir con conexión reutilizada (`httpx.Client`, o `curl` con varias URLs en UNA invocación)
  y en varias rondas antes de concluir. Receta: `latencia.py` (login `administrativo@` n2, 5
  muestras por endpoint, JSON por etiqueta) en el scratchpad de esa sesión — recrear si hace falta.
- **QA por navegador en PROD (2026-06-10, sigue vigente):** verificar el resultado de una
  mutación a los 3-4 s da FALSOS NEGATIVOS; esperar 5-6 s tras cada mutación y re-chequear una
  vez antes de diagnosticar.

**Histórico (2026-05-14, ya NO vigente):** los endpoints de Agenda medían 2,2-3,3 s
(`/agenda/recursos/conteos` 2,9 s; hoy 189 ms). Ese piso se atribuyó a un round-trip
Railway↔Supabase de 30-50 ms con Railway en us-west; hoy no se observa. Si vuelve a aparecer,
medir primero (health vs identidad) antes de tocar queries.

**Cómo bajar el piso de ~150 ms (descartado 2026-09-26):** solo con backend Y DB en São Paulo,
y Railway no tiene región en Sudamérica → salir de Railway. Ver [[project_migrar_region_sao_paulo]].
