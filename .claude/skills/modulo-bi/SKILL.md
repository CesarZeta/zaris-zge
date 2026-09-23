---
name: modulo-bi
description: "Usar al trabajar en el módulo Datos / BI (Análisis de datos) de ZARIS (archivos: backend/app/api/routes/bi.py, bi_ejecutivo.py, bi_atencion.py, web-app/src/modules/bi/, components/HistogramaTemporal.tsx, components/exportCsv.ts; sidebar 'datos', moduloCodigo='bi'). Tableros analíticos sobre reclamos (Operativo, Ejecutivo) y sobre la atención al vecino (Atención: turnos, colero, Guardia, eventos; F6 2026-09-19). Cubre la estructura Landing→Operativo, las reglas OBLIGATORIAS de visualización (Recharts 2.15, etiquetas de total, pastilla oscura, drill-down, Exportar CSV), las convenciones de backend (área vía subárea, mono-municipio con id_municipio NULL, agregación 100% en SQL) y los datos demo. Invocar ANTES de tocar cualquier endpoint, visualización o vista del módulo Datos/BI."
---

# Módulo Datos (BI — Análisis de datos) — §43

Tableros analíticos sobre `reclamos`. Módulo React `web-app/src/modules/bi/` (sidebar "datos", `moduloCodigo='bi'`, mig 65, nivel ≤ 2). Router backend `backend/app/api/routes/bi.py` (`/api/v1/bi/*`, guard JWT a nivel router). Entregado 2026-05-26.

### Estructura
- **Landing DATOS** (`/bi`, `pages/DatosLanding.tsx`): 2 tarjetas estilo Contactos → **Operativo** (activo) + **Ejecutivo** (placeholder "Próximamente", contenido a definir por el usuario).
- **Operativo = UNA PÁGINA** (`/bi/operativo`, `pages/OperativoPage.tsx`, desde 2026-08-30 — reemplazó los 4 tabs, decisión de César al revisar los tableros Power BI de referencia): barra **fija** arriba con índice de secciones (anclas `#resumen` / `#respuesta` / `#pendientes` / `#subreclamos`, `scrollIntoView`) + **filtros globales**, y las 4 secciones (`sections/*Section.tsx`) apiladas verticalmente con `Seccion` (`components/SeccionHeader.tsx`). Las rutas viejas `/bi/operativo/{resueltos|pendientes|subreclamos}` siguen existiendo y desplazan a la sección (compat). `BiLayout` quedó solo breadcrumb + título.
- **Filtros globales** (`components/FiltrosGlobales.tsx`): UNA barra gobierna todas las visualizaciones y las exportaciones. **El área de servicio es el selector principal y arranca con una por defecto** ("estas vistas son para cada área", César): Supervisor → la de su agente (`GET /bi/mi-area`, `agentes.id_subarea → subarea.id_area`, regla §3, solo áreas activas); **Admin → "Todas las áreas" SIEMPRE al abrir** (César 2026-09-01, mismo default que el Ejecutivo — el `localStorage['zaris_bi_area']` ya NO se restaura al boot). Cualquier candidata que no esté en el catálogo de áreas activas se descarta (cazado en local: agente vinculado a un área inactiva). **El período también arranca preseleccionado**: año en curso + mes anterior tildado (`periodoEjecutivoDefault()`), y "Limpiar" restaura el default COMPLETO (área + período; `hayFiltros` compara contra él). Además: atajos de **año/mes** (chips que setean `desde/hasta`; el activo se deriva del rango), rango manual, **estado**, **prioridad**, **canal** (`sin_dato` = NULL) y **tipo de reclamo** (`components/TipoSearch.tsx`, buscador contra `/reclamos/catalogo/tipos?q=&id_area=`, patrón skipNextRef §29). En el backend los 3 filtros nuevos viajan como `estado` / `id_tipo_reclamo` / `canal` y los aplica `_aplicar_extras` en TODOS los endpoints (vía los 4 helpers `_filtros_*`); una sección cuyo universo choca con el filtro queda vacía (Pendientes con estado=Resuelto), como en Power BI. **Filtro nuevo ⇒ sumarlo a `BiFiltros`, `qp()` de `lib/api.ts`, `filtrosKey()` de `hooks/useBi.ts` y `_aplicar_extras`** — si falta en uno, esa vista muestra datos viejos en silencio.
- **Sin tablas de detalle**: cada sección tiene "Exportar tickets filtrados" (Resumen → `/bi/reclamos-detalle`, universo completo; Respuesta → `/resueltos-detalle`; Pendientes → `/pendientes-detalle`; Subreclamos → `/subreclamos-detalle`), todos con `limit=10000` y los filtros globales.
- **Histórico del Resumen con toggle Estado | Tipo** (`HistogramaTemporal` prop `alterno`): por tipo usa `/bi/mensual-por-tipo` y `/diario-por-tipo`, que devuelven `{series, items}` (top 6 tipos + "Otros", pivot en Python sobre un GROUP BY período×tipo). El **mapa de pendientes colorea por semáforo de demora** (`colorTramo`, prop `colorReclamo` de `DashboardMap`, `dias_demora` en `/pendientes-geo`), como el "Pendientes geoposicionados" de Power BI.
- **Ajustes de César tras verlo en prod (2026-08-30, misma tarde):** (1) la barra fija muestra **siempre la sección activa** (strip "Sección · Respuesta — …" debajo del panel de filtros, scroll-spy **por posición**: la activa es la ÚLTIMA sección cuyo `getBoundingClientRect().top` ≤ borde inferior REAL de la barra (`stickyRef.getBoundingClientRect().bottom` + 24 — NO `offsetHeight`: en dev la barra arranca debajo del topbar del AppShell) — listener `scroll` en captura (el que scrollea es el documento del iframe en prod / `<main>` en dev) con rAF + **debounce de cola 120 ms** (el último evento de un scroll suave puede caer con un rAF pendiente y perderse) + lock de 900 ms al saltar desde el índice y **re-evaluación forzada a los 1000 ms** (no depende de que llegue otro evento). El `IntersectionObserver` original marcaba SIEMPRE la sección anterior (las secciones son más altas que el viewport). El alto real de la barra se mide con `ResizeObserver` → CSS var `--bi-sticky`, que las secciones usan como `scroll-margin-top` para que el título quede debajo de la barra al saltar. Verificado en local 7/7 clicks + 4/4 scrolls manuales); (2) **la fila de KPIs de cada sección es UNA sola línea** (`KpiRow n=6|4`, sin wrap; `KpiCard` compacta) y **siempre trae el totalizador de lo filtrado + "Prom. mensual últ. año" + "Período anterior" con variación** (`KpisComparativos`, endpoint `GET /bi/comparativo?seccion=` — universo por sección: resumen=todos por `fecha_alta`, respuesta=resueltos por `fecha_cierre`, pendientes=abiertos, subreclamos; promedio = 12 meses calendario hasta hoy con los filtros NO temporales; **desde 2026-09-01 "anterior" = período INMEDIATAMENTE anterior, misma regla que `_rango_anterior` del Ejecutivo**: meses <12 → bloque contiguo de N meses que termina antes del primero (como rango de fechas, puede cruzar de año), año completo → año-1, desde/hasta → mismo largo hacia atrás, sin filtro temporal → 12 previos; el JSON conserva la key legacy `anio_anterior` — el card dice contra qué período compara y muestra "sin datos en X" si el anterior está vacío; color por valoración con `positivoEsBueno` — en Respuesta subir es verde, en demanda/pendientes bajar es verde); Respuesta suma tiempo de cierre promedio y % SLA; (3) el panel de filtros se llama **"Filtrado de análisis"** y va en naranja (tinte `rgba(245,78,0,.10)` + borde `--zaris-orange`); (4) **los meses son tildes independientes** (multi-selección, `role=checkbox`, **solo por color, sin carácter de check** — 2ª vuelta) + casilla **"Seleccionar año completo"** que marca/desmarca los 12; viajan como `anio` + `meses=1,3,12` (`_parse_meses` ignora basura) y los aplica `_aplicar_extras` con `EXTRACT(YEAR|MONTH)` sobre `fecha_alta` (`fecha_cierre` en Respuesta); marcar un mes sin año fija el año actual; usar chips limpia desde/hasta y viceversa. Verificado en DOM en local (títulos, 6/6/6/4 cards por fila, panel naranja, tildes 5+6, año completo 12→0, requests con `meses=`).
- **2ª tanda de ajustes (`83b220b`, 2026-08-30):** (5) el panel de filtros es **contraíble** (`colapsado`/`onColapsar` desde `OperativoPage`, preferencia `localStorage['zaris_bi_filtros_colapsados']`; contraído muestra "área · período · filtros" y el strip de sección sigue visible); (6) **la barra fija va con `zIndex: 1100`** (por encima de los panes 400 y controles 1000 de Leaflet) **y el wrapper del mapa de Pendientes lleva `isolation: 'isolate'; zIndex: 0`** — sin eso el mapa se dibujaba SOBRE la barra al scrollear (cazado por César en prod); cualquier mapa Leaflet nuevo bajo una barra sticky repite el par; (7) **etiqueta de período legible**: `labelPeriodo()` en `FiltrosGlobales.tsx` y el mismo criterio en `bi_comparativo` (`periodo_actual`/`periodo_anterior`): `"2026 · año completo"` con los 12 meses, `"2026 · mes 5"`, `"2026 · meses 5, 6"` — nunca la lista de 12; (8) **toda dona lleva el total en CANTIDAD al centro**: `<Label content={DonaCentro} position="center" value={totalDe(data)} />` dentro del `<Pie>` (`DonaCentro`/`totalDe` en `SeccionHeader.tsx`; `viewBox` tipado laxo porque recharts pasa `CartesianViewBox | PolarViewBox`); (9) **separación doble entre visualizaciones**: `Seccion` con `gap: 32` y 48 entre secciones — la fila de KPIs mantiene su gap interno (10).
- Verificación navegando 2026-08-30 en `localhost:5173` (área por defecto, chips año/mes, buscador de tipos, cambio de área + localStorage, Limpiar, toggle Tipo, export → requests 200). **El navegador integrado en modo degradado puede tener viewport de alto 0** (1ª vuelta: no sirvió para scroll/sticky); en la 2ª vuelta sí tuvo 812 px y permitió verificar el scroll-spy por DOM (`scroller = <main>` en dev). Screenshots siguen sin servir — lo visual queda para prod.

### Reglas de visualización (OBLIGATORIAS para toda viz nueva del módulo)
Ver memoria `reference_bi_lineamientos_visualizaciones`. Resumen:
- **Recharts 2.15, NO 3.x** — la 3.8 trae `es-toolkit` que rompe con Vite 8 (`require_isUnsafeProperty`; root vacío sin error en consola del browser, el error vive en el log de Vite).
- **Toda viz lleva etiqueta de total** (barras: valor en segmento + total afuera; donas: `%` + valor). Pastilla de fondo **OSCURA** `rgba(38,37,30,0.78)` + texto claro `#f7f7f4` (el usuario pidió oscuro explícitamente).
- **Histogramas temporales: toggle Mes/Día + drill-down** (clic en barra de mes → días de ese mes). Componente genérico `components/HistogramaTemporal.tsx` (series + fetchers inyectados).
- **Toda tabla de detalle lleva botón "Exportar CSV"** (helper `components/exportCsv.ts`, BOM UTF-8 para Excel).
- **Estilo ZARIS** (tokens DS), NO la paleta de los tableros Power BI de referencia.
- **Agregación 100% en SQL** (`GROUP BY`/`date_trunc`/`FILTER`); el frontend solo dibuja. Diseñado para escalar.

### Backend
Endpoints por vista en `bi.py`. Convenciones críticas:
- **Área vía subárea** (§27): JOIN `reclamos → tipo_reclamo → subarea → area`. `reclamos.id_area` legacy es NULL.
- **Mono-municipio**: filtro `(id_municipio = :m OR id_municipio IS NULL)` — los reclamos reales tienen `id_municipio` NULL (local Y prod). Filtrar estricto = BI vacío.
- Tiempo de cierre = `fecha_cierre - fecha_alta`; demora pendiente = `NOW() - fecha_alta`. Tramos 0-3 / 4-7 / +7 días.
- Subreclamos = `id_reclamo_padre IS NOT NULL` ("intervenciones" en la jerga de los tableros de referencia).
- El mapa de Pendientes reusa `modules/dashboard/components/DashboardMap.tsx` (Leaflet vanilla) — endpoint `/bi/pendientes-geo`.

### Datos demo (generador, 2026-08-30 — reemplaza al poblado manual de 2026-05-26)

El grueso de los datos que alimentan los tableros es SINTETICO, producido por el
**generador demo** `backend/app/services/demo_datos.py` (+ `demo_datos_ref.py`,
distribuciones derivadas de datasets reales de VL que viven en `SMOKE/`,
carpeta **gitignoreada** — datos personales, jamas versionar):

- ~300-500 reclamos/mes desde abril 2026, con historial coherente, subreclamos
  (~4%), localidad+coords por centroide, y encuestas CSAT (~85% de los
  resueltos, ~30% respondidas, %sat ~68%). Catalogos resueltos POR NOMBRE en
  runtime (nunca por id — divergen local/prod).
- **Todo atribuido al usuario INACTIVO `generador.demo`** (`id_usuario_alta`) y
  vecinos demo con email `@vecinos-demo.zaris.com.ar` → borrar/migrar a un
  tenant (IT-01) = filtrar por eso. NO borrar a mano sin decision de Cesar.
- **Regla critica:** los `encuesta_envio` demo JAMAS nacen `pendiente` (el
  dispatcher horario los mandaria por mail). Solo enviada/completada/expirada.
- Refresco: cron semanal `.github/workflows/demo-datos.yml` (lunes 08:20 UTC) →
  `POST /api/v1/demo/poblar` (auth X-Dispatcher-Token o JWT admin nivel 1;
  genera la semana + `avanzar_pendientes` que envejece SOLO lo demo). Carga
  manual por rango: dispatch del workflow con inputs `desde`/`hasta` (max 45
  dias por llamada) o `backend/seed_demo_bi.py` en local. Ventana default del
  endpoint: `[hoy-6, hoy]` — los crones de lunes consecutivos NO se solapan.
- **Desde 2026-09-22 la corrida es ASINCRONA:** el POST valida, encola en un
  `BackgroundTask` (sesion SQL propia, `AsyncSessionLocal`) y responde **202**
  `{id_corrida, estado:'en_curso', consulta}`; el workflow hace polling de
  `GET /api/v1/demo/poblar/{id_corrida}` cada 20 s (hasta 40 min) y vuelca el JSON
  de conteos cuando `estado='ok'` (`error` = fallo con detalle y el resultado
  PARCIAL de los pasos ya commiteados; 404 = la instancia se reinicio a mitad →
  verificar la DB antes de re-disparar). **409 si ya hay una corrida en curso**
  (anti doble capa). Motivo: el edge de Railway corta toda respuesta a los ~300 s;
  con `reclamos,atencion` la semana tardo 14,5 min y el run del 2026-09-21 quedo
  en `failure` (502 "upstream error") con el backend terminando igual. Las
  corridas viven en memoria de la UNICA instancia (con replicas habria que
  persistirlas). Smoke in-process: `backend/smoke_demo_poblar.py`. Un `failure`
  del cron NO prueba que no se generaron datos: mirar los conteos por dia antes
  de tocar nada (memoria `project_cron_demo_502_railway_timeout_5min`).
- **REGLA (incidente 2026-08-31): el generador NO es idempotente y el cron de
  GitHub puede demorar HORAS.** Cada llamada a `/demo/poblar` inserta un lote
  nuevo aunque el rango ya tenga datos. Si el cron del lunes "no aparece",
  ANTES de re-dispatchar: (1) buscar un run `event=schedule` tardio en el dia
  (`gh api .../workflows/demo-datos.yml/runs`, el 2026-08-31 corrio 8 hs tarde)
  y (2) verificar los conteos por dia del periodo en la DB. Caso real: cron
  demorado + dispatch manual = semana con capas duplicadas → limpieza
  transaccional por DB directa (los lotes son bloques CONTIGUOS de id_reclamo
  del uid `generador.demo`; los conteos exactos salen del JSON en los logs del
  run). Filas borradas en `_backup_*_dup_2026_08_31`.
- Backups pre-seed en prod: `_backup_reclamos_pre_demo_2026_08_30` y
  `_backup_encuesta_envio_pre_demo_2026_08_30` (+ los viejos
  `_backup_reclamos_fecha_cierre_2026_05_26` / `_backup_reclamos_geo_demo_2026_05_26`;
  limpieza del 2026-08-31: `_backup_{reclamos,reclamo_historial,encuesta_envio,encuesta_respuesta,encuesta_resp_det}_dup_2026_08_31`).


## Tablero EJECUTIVO — "Análisis de demanda ciudadana" (2026-08-30)

Réplica ZARIS de los 5 tableros Power BI de VL sobre reclamos. Ruta `/bi/ejecutivo`
(`pages/EjecutivoPage.tsx` + `sections/*EjSection.tsx` + `components/FiltrosEjecutivo.tsx`);
backend `backend/app/api/routes/bi_ejecutivo.py` (router propio `/api/v1/bi/ejecutivo/*`,
guard JWT a nivel router, registrado en main.py después de `bi_router`). Decisiones de César:

- **Filtros = PERÍODO + ÁREA + SUBÁREA (+ localidad)** — sin estado/tipo/canal (eso es
  composición, se VE en las visualizaciones). `FiltrosEjecutivo` es un componente aparte;
  NO tocar `FiltrosGlobales` del Operativo para esto. La subárea (2ª tanda 2026-08-30) se
  puebla con `GET /bi/ejecutivo/catalogo/subareas?id_area=` (solo subáreas presentes en
  reclamos) y se resetea al cambiar de área; viaja como `id_subarea` y la aplican TODOS
  los endpoints del router vía `_where_ej`.
- **El desglose de TODAS las vistas es por SUBÁREA**: las "áreas de servicio" de los
  tableros VL (Alumbrado, Arbolado, Calles…) son nuestras subáreas de Servicios Públicos.
  Replicar "por área" a nivel secretaría daría una sola barra.
- **5 secciones** (página única, mismo patrón sticky/scroll-spy del Operativo, keys
  localStorage propias `zaris_bi_ej_*`): Resumen (score %cierre/%SLA/%sat + niveles +
  **matriz subárea → tipo expandible**, export CSV client-side de la matriz) · Evolución
  (altas vs cierres, indicadores mensuales, dona Cumplido/Auditado) · Histórico (apilados
  mensuales por subárea/canal/localidad + donas) · Mayores (top 10 por cantidad y por
  demora + donas por subárea) · Satisfacción (barras %sat vs %cierre por subárea y
  localidad + 2 mapas `DashboardMap` con `colorReclamo` por lookup id→clasificación/cerrado).

### Convenciones del backend Ejecutivo

- **GROUP BY POSICIONAL obligatorio en `_agregado`/`_encuestas`**: los strings de agrupación
  llevan alias `AS` (para el SELECT) y un alias en GROUP BY es **error de sintaxis** de
  Postgres. Se agrupa por posición (`GROUP BY 1, 2…`, param `n_grp`). Cazado en el smoke
  local (500 en /matriz y /top-tipos).
- **Satisfacción**: `encuesta_envio.id_reclamo` (JOIN `_JOIN_ENC`) + `encuesta_respuesta.
  clasificacion_inicial` 1-5; satisfecho = **>= 4** (regla del módulo Encuestas, `_rama_desde_
  clasificacion`). `%Sat` = satisfechos/respuestas · `%Rep` = respuestas/enviadas. Niveles
  sin emoji (§13): etiquetas Muy insatisfecho…Muy satisfecho + semáforo.
- **`% Var` = período INMEDIATAMENTE anterior** (`_rango_anterior`, redefinido en la 2ª
  tanda 2026-08-30 a pedido de César: "agosto se compara con julio, no con agosto del año
  pasado"): meses elegidos (1-11) → el bloque contiguo de N meses que termina antes del
  primero seleccionado, cruzando de año (`pares` = año*100+mes en `_where_ej`); año
  completo → año-1; rango manual → mismo largo hacia atrás; sin filtro temporal → None.
  En demanda **bajar es verde, subir es rojo**. **El front ESPEJA esta regla en
  `web-app/src/modules/bi/lib/periodo.ts` (`periodoEnLetras`)** — nombra el período y su
  anterior en letras; si se cambia una punta hay que cambiar la otra.
- **Período EN LETRAS en el título de cada sección del Ejecutivo** (2ª tanda): las 5
  secciones pasan `periodo={periodoEnLetras(filtros).actual}` a `Seccion` (prop nueva,
  reemplaza a los subtítulos descriptivos ahí); "agosto de 2026", "año 2026 completo",
  "01/05/2026 al 15/06/2026", "todo el histórico".
- **Matriz (2ª tanda):** SIN columna % Resp en la UI/CSV (pedido de César; el backend
  sigue devolviendo `pct_rep`). Cada indicador (prom días / % cierre / % SLA / % sat)
  lleva **triangulito de variación** contra `fila.ant` (indicadores del período anterior
  que `/matriz` calcula con los mismos agregados): dirección real ▲/▼, color por
  valoración (verde mejora, rojo empeora; días de demora invertido), ■ gris sin variación
  o sin dato previo. Componente `Tri` en `ResumenEjSection.tsx`.
- **Dona "Niveles de satisfacción"**: lleva la aclaración de que el total del centro son
  las ENCUESTAS RESPONDIDAS del período, no los incidentes (via prop `action` del
  `ChartCard`).
- **Cumplido vs Auditado**: resueltos con EXISTS en `reclamo_historial.estado_nuevo='En auditoría'`.
- **`/historico?dim=subarea|canal|localidad`** devuelve `{series, items}` (pivot Python top N +
  Otros, keys `g_<slug>`/`g_otros`) — compatible con el modo dinámico de las visualizaciones;
  para `dim=canal` las series llegan con el valor CRUDO (`app_movil`) → el front mapea con
  `labelCanal` al renderizar.
- **Smoke**: `scratchpad/smoke_bi_ejecutivo.py` (18 checks; login admin local + shapes + 401).

### 3ª y 4ª tanda del Ejecutivo (César, 2026-08-31) — reglas vigentes

- **Defaults del tablero (SIEMPRE al abrir, no se restaura de localStorage):** año en
  curso + MES ANTERIOR tildado (`periodo.ts::periodoEjecutivoDefault`, enero → dic año-1)
  y "Todas las áreas" para admin ("Todas" sigue admin-only; el supervisor n2 arranca con
  su área). "Limpiar filtros" vuelve a ESE default (período incluido) y `hayFiltros`
  compara contra él.
- **Series mensuales (2 líneas de Evolución + 3 apilados de Histórico): ventana FIJA de
  últimos 12 meses** que ignora el filtro de período (respeta área/subárea/localidad) —
  `filtros12m` + `ultimos12MesesRango()`. **Se muestran solo los meses CON datos**
  (corrección de César: tope 12, del primer al último mes con datos, huecos intermedios
  en cero — `mesesEjeSerie()`). Nota `nota="últimos 12 meses"` en minúscula al lado del
  título (`ChartCard` prop `nota`). XAxis con `interval={0}`.
- **Las 2 donas viven JUNTAS en el Resumen** (Niveles de satisfacción + Cierres por
  estado, lado a lado en grid `minmax(320px,1fr)`); Evolución quedó solo con las líneas.
- **Barras % Sat vs % Cierre**: filas con AMBOS indicadores en cero se filtran; etiquetas
  de valor 0 no se muestran (`fmtPct`).
- **Mapas de Satisfacción**: `DashboardMap` con `marcadorPunto` (punto de 5px, sin badge)
  y `LeyendaMapa` en RECUADRO debajo de cada mapa (no línea de corrido compartida).
  **Fit**: en modo punto el mapa se RE-ENCUADRA cuando cambia el dataset (cambio de
  filtros); `fittedRef` se resetea al crear el mapa (StrictMode dev lo dejaba en el
  encuadre default) + `invalidateSize` con ResizeObserver + re-fit diferido 300ms.
  Hook de QA: el container guarda `_mapDebug` (instancia Leaflet) para leer
  bounds/zoom desde `browser_eval`.
- **Shell dev**: el dropdown de notificaciones lleva z2000 (la barra sticky del BI usa
  1100 y lo tapaba); el topbar del AppShell standalone va z1500.

### 5ª tanda (César, 2026-09-01) — tablas sin scroll + Operativo con el tratamiento del Ejecutivo

- **NINGUNA tabla del módulo lleva scroll horizontal** (pedido explícito): las columnas
  numéricas van a su ancho mínimo (`width: '1%'` en el th + `nowrap` en el td) y las
  columnas de NOMBRES (la primera; en los tops también Subárea) absorben el resto con
  `whiteSpace: 'normal'` + `overflowWrap: 'break-word'`. Nada de wrappers `overflowX:
  'auto'` alrededor de tablas. OJO: un contenedor con `overflowY: 'auto'` computa
  `overflow-x: auto` — agregarle `overflowX: 'hidden'` (caso tops de Mayores). En cards
  angostas los th van SIN nowrap ("Cierre prom. días" se parte en 2 líneas en vez de
  imponer un mínimo que desborda) y el padding de celda baja a `6px 6px`. Patrón en
  `ResumenEjSection` (matriz) y `MayoresEjSection` (TablaTop); toda tabla nueva lo repite.
- **El Operativo usa los MISMOS defaults del Ejecutivo** (detalle en el bullet de
  Filtros globales de arriba) **y el mismo tratamiento de encabezados**: las 4 secciones
  pasan `periodo={periodoEnLetras(filtros).actual}` a `Seccion` (reemplazó a los
  subtítulos descriptivos, que siguen visibles en el strip de sección de la barra fija).
- **La regla del período anterior ahora vive en TRES puntas espejadas**: `_rango_anterior`
  (bi_ejecutivo.py) ↔ `bi_comparativo` (bi.py) ↔ `periodoEnLetras` (lib/periodo.ts).
  Tocar una ⇒ tocar las tres.
- **`/bi/ejecutivo/top-tipos` calcula `% Var` por tipo** contra el período contiguo
  anterior (antes pasaba `ant=None` fijo y la columna de los tops mostraba siempre "—").
- **2ª vuelta (mismo día, QA de César sobre prod):** (a) en columnas de texto de tablas
  usar `overflowWrap: 'anywhere'`, NO `'break-word'` — es el único valor que reduce el
  min-content de la columna; con break-word la tabla puede medir más que la card y quedar
  RECORTADA a la derecha sin aviso (con `overflowX: hidden`). Los wrappers `overflowY`
  de los tops llevan `paddingRight: 10` para que el scrollbar no pegue contra la última
  columna. (b) **Las pastillas de `pieLabel` se CLAMPEAN al área del chart** (aprox
  `2·cx / 2·cy`, válido porque el pie va centrado) — antes los labels laterales se
  cortaban contra el borde de la visualización; valores no enteros a 1 decimal (sin eso
  imprimía "28.400000000000002"). (c) **La barra sticky lleva un COVER absoluto**
  (`top:-24, height:24`, fondo crema) como primer hijo: el scroller embebido
  (`main.embeddedContent`, `overflow-y:auto` + `padding:16px`) pega la sticky al borde
  del CONTENIDO y en la franja del padding-top se veía pasar la página; el overflow del
  main recorta el cover en el borde del scrollport, así que nunca pisa nada. Aplica a
  las DOS páginas (Operativo + Ejecutivo); toda barra sticky nueva bajo ese scroller
  repite el patrón.

- `reclamos.id_localidad` estaba 0/65 en prod → **backfill por reverse geocoding** (Nominatim
  vía helper §23, match por NOMBRE contra `localidades` — NUNCA por id: los ids de partido
  divergen entre entornos; local id_partido 46 = Luján, prod 46 = Vicente López). Prod: 39/45
  asignados (Olivos 14 · Florida 13 · Vicente López 9 · La Lucila 2 · Munro 1); los 6 restantes
  caen fuera del partido y quedan NULL a propósito. Backups `_backup_reclamos_localidad_2026_08_30`
  en local y prod.
- **Derivación automática al crear**: `geo.py::localidad_desde_coords(db, lat, lon)` (best-effort,
  nunca levanta; prioridad de campos BARRIO-primero — distinta de la `localidad` city-primero
  del reverse legible) inyectada en los 3 creates (backoffice, subreclamo, vecino PWA) cuando
  hay lat/lon sin id_localidad. `GET /geo/reverse` (backoffice) ahora devuelve `id_localidad`/
  `localidad_catalogo`; el FormView de Reclamos muestra la localidad derivada (campo readonly,
  se limpia con "Quitar pin"). Detalle del form en la skill `modulo-reclamos`.
- `GET /bi/ejecutivo/catalogo/localidades` puebla el filtro SOLO con localidades presentes en
  reclamos (no el catálogo nacional).

## Tablero de ATENCIÓN — "BI de atención por gestión" (proyecto ATENCIÓN F6, 2026-09-19)

Tercer tablero de DATOS: **turnos + colero + Guardia + eventos**, sobre las tablas de F1-F5 del
plan de Atención (`PLAN_MODULO_ATENCION.md`). Ruta `/bi/atencion` (`pages/AtencionPage.tsx` +
`sections/{Resumen,Evolucion,Ubicaciones,Espera,Guardia,Eventos}AtSection.tsx` +
`components/FiltrosAtencion.tsx` + `components/atUtils.tsx`); backend
`backend/app/api/routes/bi_atencion.py` (router propio `/api/v1/bi/atencion/*`, 19 rutas, guard
JWT a nivel router, registrado en `main.py` después de `bi_ejecutivo_router`). **Sin migración**
(solo lectura). Smoke `backend/smoke_bi_atencion.py` (85 checks in-process, SOLO local; compara
score/matriz/series/composición entre sí y contra la DB).

- **Filtros = PERÍODO + GESTIÓN (área) + UBICACIÓN (espacio) + PRESTACIÓN** (`FiltrosAtencion`,
  cascadeo gestión → ubicación → prestación). Campos nuevos de `BiFiltros`:
  `id_espacio_ubicacion` / `id_tipo_prestacion`, sumados a `qp()`, `qpSinFechas()` y
  `filtrosKey()` (regla del filtro nuevo). **La gestión de un turno se deriva de su UBICACIÓN**
  (`COALESCE(t.id_espacio_ubicacion, tp.id_espacio_ubicacion, t.id_espacio) → espacios_agenda →
  subarea → area`, `_JOIN_TURNOS`); los legacy sin ubicación caen a `tp.id_subarea` y, si no,
  al bucket visible "Sin ubicación · Sin gestión" (lección de la mig 27: nada desaparece).
  Catálogos propios: `/catalogo/gestiones` (áreas activas con espacio activo, prestación o
  evento — NO las que solo tienen reclamos), `/catalogo/ubicaciones?id_area`,
  `/catalogo/prestaciones?id_area&id_espacio_ubicacion` (activas o con turnos). Defaults = los
  del Ejecutivo (año en curso + mes anterior; admin "Todas las gestiones"; supervisor la de su
  agente vía `/bi/mi-area` si es gestión de atención, si no la primera del catálogo).
  **Prestación NO aplica a Guardia ni a Eventos**: se ignora en el backend y la sección lo dice
  con una nota (no se vacía como en Power BI, porque no es un choque de universo sino una
  dimensión inexistente).
- **Universo de turnos = `t.activo = TRUE`.** Cancelar (turnos.py) deja `activo=TRUE` +
  `estado='cancelado'`; las filas `cancelado + activo=false` que hay en local (14) y prod (7)
  son la limpieza de un smoke del 2026-05-28 (sin `id_usuario_modificacion`), NO cancelaciones,
  y quedan fuera a propósito. Mono-municipio como el resto (`id_municipio = :m OR NULL`).
- **Indicadores** (`_indicadores`, mismos en score / matriz / por ubicación / por agente):
  `pct_cumplimiento` = cumplidos / otorgados con desenlace (sin pendientes) ·
  `pct_ausentismo` = ausentes / (cumplidos + ausentes) (turnos caídos entre los que llegaron a su
  hora — el KPI del plan) · `pct_cancelacion` = cancelados / otorgados · `pct_a_tiempo` =
  llamados dentro de `TOLERANCIA_MIN` (5) / llamados · CSAT = `encuesta_envio.id_turno` +
  `clasificacion_inicial >= 4` (LATERAL LIMIT 1 por turno) · `horas_atendidas` = duración de
  los cumplidos · `atenciones_registradas` = `turno_atencion` (LATERAL LIMIT 1).
- **Espera real** = primer `turno_llamado` − hora del turno. La hora del turno es `fecha +
  hora_inicio` LOCAL naive (UTC-3 fijo) → `+ INTERVAL '3 hours' AT TIME ZONE 'UTC'` (mismo
  criterio que `services/historia_clinica.py`); el promedio usa `GREATEST(0, delta)`. **Solo
  cuentan los llamados del MISMO día local del turno** (LATERAL `ll`): un llamado de otro día
  es una regularización tardía o un artefacto de prueba (en local había un turno del 02/09
  llamado el 06/09 = 6.300 min de "espera"). Tramos: A tiempo / 5-15 / 15-30 / 30-60 / +60.
- **Guardia** (`emergencia_atencion`, mig 106): fecha = `derivado_en` en local
  (`(x AT TIME ZONE 'UTC') - 3h ::date`); demora = `atendido_en − derivado_en`; `%atendidas` =
  atendidas / (atendidas + ausentes); desglose por médico (`id_agente_atiende`), tipo
  (`emergencia_evento.id_tipo → emergencia_tipo`) y prioridad (`emergencia_prioridad`,
  ordenada por `orden_visual`). **Eventos** (Cultura): universo `eventos.activo` por `ev.fecha`,
  gestión vía `COALESCE(ev.id_subarea, espacio.id_subarea)`; reservas por LATERAL `rs` (no
  multiplica el cupo); `% asistencia` = asistieron / vigentes SOLO de eventos ya realizados
  (`fecha < hoy_local()`); `% cupo` = vigentes / `capacidad_ciudadanos`; series mensual/diaria
  con `HAVING reservas > 0`; `por_estado` = asistió / reservada (vigentes − asistieron) /
  cancelada.
- **Período anterior**: reusa `_rango_anterior` del Ejecutivo (score, `ant` de la matriz,
  guardia, eventos) y `periodoEnLetras` en el front — **4ª punta de la regla espejada** (tocar
  una ⇒ tocar las cuatro). Las variaciones de VOLUMEN (otorgados, derivaciones, reservas) van
  en color neutro (`VAR_NEUTRO`: más demanda no es ni buena ni mala); los indicadores con
  valoración llevan el triangulito `Tri` (`invertir` para ausentismo / espera / demora).
- **Secciones** (`AtencionPage`: mismo sticky + scroll-spy + cover del Ejecutivo, keys
  `zaris_bi_at_area` / `zaris_bi_at_filtros_colapsados`): **Resumen** (6 KPIs + matriz
  UBICACIÓN → PRESTACIÓN expandible + donas estado / origen / niveles CSAT; export
  `/turnos-detalle` limit 10000) · **Evolución** (`HistogramaTemporal` por estado con drill +
  2 líneas de 12 meses vía `/evolucion`) · **Ubicaciones** (barras horizontales apiladas
  `SegLabelH`/`TotalLabelH`, alto = 70 + 38·filas, + tablas "Ocupación por ubicación" y
  "Atención por agente" top 15) · **Espera** (4 KPIs + tramos + tabla por ubicación) ·
  **Guardia** (6 KPIs + histograma + dona + tablas médico / tipo / prioridad; export
  `/guardia-detalle`) · **Eventos** (6 KPIs + histograma de reservas + dona + tabla de los
  últimos 30 eventos; CSV client-side). Tablas con `TablaAt` (`atUtils.tsx`: numéricas a
  `width 1%`, columna `texto: true` con `overflowWrap: 'anywhere'`, scroll solo vertical).
  Colores en `theme.ts` (`COLOR_TURNO` / `COLOR_GUARDIA` / `COLOR_RESERVA` + labels; sin
  naranja para estados). **Las exportaciones NO llevan datos personales del vecino**
  (Ley 25.326: el tablero es de gestión).
- **Datos demo**: NO hay generador de turnos / guardia / eventos (`demo_datos.py` es solo de
  reclamos): local ~26 turnos activos, prod ~32. El tablero se ve ralo hasta que César decida
  un generador (pendiente en `ESTADO.md`). `/score?anio=2000` devuelve ceros/`null`, no 500.
- Verificado 2026-09-19 navegando en `localhost:5173` (login admin → landing → tarjeta →
  6 secciones con septiembre/julio, chips de mes, cascadeo gestión → ubicación → prestación,
  "Limpiar filtros") + smoke 85/85 + `pnpm typecheck`. **Queda el QA visual de César en prod.**

### Datos demo de ATENCIÓN (generador, 2026-09-19 — hermano del de reclamos)

`backend/app/services/demo_atencion.py` genera **turnos + ocupaciones espejo + colero + atenciones +
CSAT de turnos + Guardia (eventos de Emergencias derivados y atendidos) + eventos con reservas**, y
se dispara por las MISMAS vías que el de reclamos: `POST /api/v1/demo/poblar` (body
`modulos: ["reclamos","atencion"]`, default ambos; `dias_futuro` 0-30, default 7), el cron semanal
`.github/workflows/demo-datos.yml` (input `modulos`, default `reclamos,atencion`) y
`backend/seed_demo_bi.py --modulos atencion`. Mismo usuario `generador.demo` en `id_usuario_alta`,
mismos vecinos demo (solo ellos: ningún turno demo cuelga de un vecino real).

- **Catálogos por nombre/código en runtime**: prestaciones activas con recurso, Guardia por la clave
  `id_espacio_guardia` + sus médicos de `espacio_agentes` (sin médicos → se omite y lo dice el
  resultado), tipos de emergencia preferidos por `codigo` (EMERGENCIA_SALUD, ACCIDENTE_VIA_PUBLICA…),
  `estado_evento`/`estado_reserva`/`emergencia_estado` por `codigo` (los ids difieren local/prod:
  estado_evento 1/2/3 vs 5/6/7), plantilla CSAT `tipo='turnos'`.
- **Turnos dentro de la disponibilidad EFECTIVA** (`disponibilidad_efectiva_batch`, la misma que
  valida la reserva real: feriados y novedades incluidos), sin pisar ocupaciones ni turnos
  existentes (índices únicos de slot mig 95), ocupando 35-65 % de los slots libres. Desenlace de
  los ya vencidos: cumplido 77 / ausente 11 / cancelado 12 %; número de colero = prefijo del espacio
  + correlativo diario continuando el MAX existente (mismo formato que `PATCH /turnos/{id}/llamar`);
  `turno_llamado` con espera realista (55 % a tiempo, colas hasta 120 min; re-llamado en 60 % de los
  ausentes) SIEMPRE el mismo día del turno; `turno_atencion` solo si la prestación
  `registra_atencion`; encuesta CSAT 85 % de los cumplidos (nunca `pendiente`). Cancelados = ocupación
  `activo=FALSE` como la cancelación real. Si el rango llega a hoy, reserva `dias_futuro` hacia
  adelante (Mesa del día / colero con turnos).
- **Guardia**: por día 0-3 derivaciones (media ~1). Cada una = `emergencia_evento` (numerado por el
  trigger `trg_numero_emergencia`, cerrado RESUELTO con `veracidad`, log CREACION → EN_CAMINO →
  EN_SITIO → DERIVACION_GUARDIA → ATENCION_GUARDIA → CIERRE) + `emergencia_atencion` atendida 85 % /
  ausente 15 % por un médico vinculado; las de hoy pueden quedar `pendiente`.
- **Eventos**: 6-10/mes en los espacios con `capacidad_personas >= 20` (sin solapar el mismo espacio),
  estado `finalizado` si ya pasaron; reservas 30-95 % del cupo, asistió 60 / reservada 25 / cancelada
  15 % en los pasados, origen autoservicio 65 % (con `token_reserva`), QR nominal en la mitad.
- **`avanzar_pendientes_atencion`** (cron): turnos demo vencidos que siguen reservados → desenlace
  completo; derivaciones demo pendientes de más de un día → atendida/ausente (+ cierre del evento);
  eventos demo pasados → finalizado (+65 % de reservas a asistió). Las encuestas de turnos las madura
  `demo_datos.avanzar_pendientes` (filtra por el usuario generador, no por origen).
- **Inserts masivos con `VALUES` + `CAST(:p AS tipo)` por columna** (`_values`/`_TIPOS`): sin el
  CAST, Postgres tipa como `text` un VALUES hecho solo de parámetros y el INSERT falla. Un
  statement por lote de 300 con RETURNING (ocupaciones → turnos → llamados/atenciones/encuestas).
- **Verificado en local 2026-09-19**: abril-septiembre = 2.706 turnos (0 fuera de la disponibilidad
  efectiva, 0 solapes propios, 0 números repetidos, 0 llamados de otro día, 0 encuestas pendientes),
  176 derivaciones, 43 eventos; smoke del tablero 85/85 con ese volumen. **Prod CARGADA el
  2026-09-19** (4 runs del workflow con `modulos=atencion`, abril → 19/09): 2.943 turnos demo,
  179 derivaciones, 45 eventos / 3.234 reservas, reclamos demo intactos, integridad 0/0/0/0/0.
  **Idempotencia** (`ea2f539`): recurso/día con turnos demo se saltea (`recurso_dia_ya_demo`),
  día con derivaciones demo se saltea (`dias_omitidos_con_demo`), eventos demo del rango
  descuentan del objetivo (`ya_existian`) — re-generar un rango poblado agrega ~0. **Prod se carga por
  chunks ≤ 45 días con el workflow (`modulos=atencion`) — NUNCA con el default `reclamos,atencion`
  sobre meses ya poblados (duplicaría reclamos, incidente 2026-08-31).** Un deploy viejo del backend
  IGNORA `modulos` (Pydantic descarta campos desconocidos) y generaría reclamos: confirmar en
  `/openapi.json` que `PoblarIn` tiene `modulos` antes de dispatchar.
