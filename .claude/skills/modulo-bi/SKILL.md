---
name: modulo-bi
description: "Usar al trabajar en el módulo Datos / BI (Análisis de datos) de ZARIS (archivos: backend/app/api/routes/bi.py, web-app/src/modules/bi/, components/HistogramaTemporal.tsx, components/exportCsv.ts; sidebar 'datos', moduloCodigo='bi'). Tableros analíticos sobre reclamos. Cubre la estructura Landing→Operativo, las reglas OBLIGATORIAS de visualización (Recharts 2.15, etiquetas de total, pastilla oscura, drill-down, Exportar CSV), las convenciones de backend (área vía subárea, mono-municipio con id_municipio NULL, agregación 100% en SQL) y los datos demo. Invocar ANTES de tocar cualquier endpoint, visualización o vista del módulo Datos/BI."
---

# Módulo Datos (BI — Análisis de datos) — §43

Tableros analíticos sobre `reclamos`. Módulo React `web-app/src/modules/bi/` (sidebar "datos", `moduloCodigo='bi'`, mig 65, nivel ≤ 2). Router backend `backend/app/api/routes/bi.py` (`/api/v1/bi/*`, guard JWT a nivel router). Entregado 2026-05-26.

### Estructura
- **Landing DATOS** (`/bi`, `pages/DatosLanding.tsx`): 2 tarjetas estilo Contactos → **Operativo** (activo) + **Ejecutivo** (placeholder "Próximamente", contenido a definir por el usuario).
- **Operativo** (`/bi/operativo/*`, `BiLayout` con 4 tabs): Resumen, Resueltos/SLA, Pendientes (+ mapa geo), Subreclamos.

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

### Datos demo (prod, 2026-05-26)
Los 30 reclamos de prod fueron poblados con `fecha_cierre` (resueltos) y `latitud/longitud` (todos) para que el BI tenga contenido. Backups `_backup_reclamos_fecha_cierre_2026_05_26` y `_backup_reclamos_geo_demo_2026_05_26`.
