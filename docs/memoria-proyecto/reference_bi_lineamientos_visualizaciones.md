---
name: reference-bi-lineamientos-visualizaciones
description: "Lineamientos de visualización del módulo BI (Análisis de datos de gestión). Aplicar a TODA visualización nueva del módulo: etiquetas de totales, pastillas, toggle/drill temporal, estilo ZARIS, recharts 2."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 452630eb-4a37-48f4-84b1-201c5b3119f1
---

Estándar de visualizaciones del módulo BI (`web-app/src/modules/bi/`, CLAUDE.md §43 cuando se documente). Acordado con el usuario en la sesión 2026-05-26 (jornada BI). **Aplicar a toda visualización nueva del módulo** (fases 2+: Resueltos/SLA, Pendientes, Subreclamos).

## Reglas firmes (el usuario las pidió explícitamente)

> **APLICAR SIN EXCEPCIÓN A CADA VISUALIZACIÓN NUEVA.** El usuario marcó (2026-05-26) que estas reglas son estándar para TODAS las visualizaciones, no solo las primeras. Falló una vez al no poner etiqueta-de-total ni toggle Mes/Día en las barras de la vista Pendientes — el usuario lo notó y pidió no repetirlo. Antes de dar por terminada una vista, chequear punto por punto esta lista contra CADA chart de barras/temporal de esa vista.

1. **Toda visualización DEBE mostrar etiquetas de totales/valores.** No dejar barras ni donas "mudas".
   - Barras apiladas: valor DENTRO de cada segmento (`SegLabel`/`SegLabelH` en `components/barLabels.tsx`) + TOTAL de la barra afuera (`TotalLabel` arriba en verticales, `TotalLabelH` a la derecha en horizontales).
   - Donas: `porcentaje% (valor)` por tajada (`pieLabel` en `ResumenView.tsx`), ocultando tajadas < 4% para no amontonar.
   - Segmentos chicos se ocultan (`height < 16` vertical, `width < 22` horizontal) para no encimar texto.

2. **Etiquetas de total y de dona llevan pastilla de fondo OSCURO translúcido** (`rect` `fill="rgba(38,37,30,0.78)"` = fg-1 al 78%) con **texto claro** (`#f7f7f4`) encima — el usuario pidió oscuro, NO claro (cazado 2026-05-26: se había puesto claro `rgba(247,247,244,...)` por error y el usuario lo reclamó dos veces). Las etiquetas DENTRO de segmentos van en blanco sólido (`#fff`) sin pastilla (contraste contra el color del segmento). Constantes `PILL`/`PILL_TEXT` en `components/barLabels.tsx`; los pieLabel/LineLabel inline de cada vista deben usar el MISMO `rgba(38,37,30,0.78)` + `#f7f7f4`.

3. **Histogramas temporales: toggle Mes/Día + drill-down combinados.**
   - Toggle de dos pills (Mes / Día) en el header del card que alterna la granularidad GLOBAL del período filtrado. Activo = `var(--zaris-orange)` fondo + texto blanco.
   - En modo Mes: clic en una barra hace drill a los días de ESE mes, con botón "← Volver". El clic NO aplica en modo Día (cursor default).
   - Patrón implementado en `components/HistogramaTemporal.tsx`. Backend: endpoint `/bi/diario` acepta `mes=YYYY-MM` (drill) O `desde/hasta` (modo Día global); `mes` tiene prioridad.

4. **Eje Y con headroom**: las barras apiladas usan `margin={{ top: 24 }}` en el `BarChart` para que la etiqueta de total no quede cortada contra el borde superior del card (la barra más alta llegaba al tope del dominio).

5. **Toda tabla de detalle DEBE tener botón "Exportar CSV".** El usuario lo pidió como estándar (2026-05-26). El botón va en el header del card (slot `action` de `ChartCard`). Exporta los datos de la tabla a CSV client-side (sin endpoint extra): construye el CSV con BOM UTF-8 (`﻿` para que Excel lea bien las tildes/ñ), separador coma, valores con comillas escapadas, y dispara descarga con `Blob` + `URL.createObjectURL` + `<a download>`. Helper compartido: `components/exportCsv.ts` (`exportarCsv(filename, columnas, filas)`). Nombre de archivo con fecha: `<entidad>_YYYY-MM-DD.csv`.

## Reglas técnicas heredadas (no negociar de nuevo)

- **Recharts 2.x, NO 3.x.** Recharts 3.8 trae `es-toolkit` que ROMPE con Vite 8 (`require_isUnsafeProperty is not a function`, root vacío sin error de consola). Pin `recharts@^2.15.0`. Ver el log de Vite (`_dev.log`), no solo la consola del browser, cuando React monta a root vacío.
- **Estilo ZARIS, no la paleta violeta/verde de los tableros Power BI de Vicente López** (que son solo referencia de QUÉ mostrar). Colores de estado en `lib/theme.ts` (`colorEstado`): Resuelto=teal `#1f8a65`, En gestión=azul, En espera=ámbar, Sin asignar=rojo, En auditoría=violeta, Cancelado=gris. Naranja del brand reservado para acentos de UI, no para estados. Tipografía `var(--font-display)`.
- **Agregación en SQL, no en el frontend.** Los endpoints `/api/v1/bi/*` hacen `GROUP BY`/`date_trunc`/`FILTER`; el frontend solo dibuja. Diseñado para escalar (prod hoy tiene ~30 reclamos pero debe aguantar miles).
- **Filtro mono-municipio**: `(id_municipio = :m OR id_municipio IS NULL)` — los reclamos reales tienen `id_municipio NULL` en local Y prod. Filtrar estricto = BI vacío. Helper `_filtros_comunes` en `bi.py`.
- **Área vía subárea** (§27): JOIN `reclamos → tipo_reclamo → subarea → area`. `reclamos.id_area` legacy puede ser NULL.

## Componentes reutilizables ya creados

- `components/ui.tsx`: `KpiCard`, `ChartCard` (con prop `action` para el header), `CenterMsg`.
- `components/barLabels.tsx`: `SegLabel`, `TotalLabel`, `SegLabelH`, `TotalLabelH` (con pastilla).
- `components/FiltrosBar.tsx`: rango fechas + área + prioridad (controlado por el padre).
- `components/HistogramaTemporal.tsx`: histograma con toggle Mes/Día + drill.
- `hooks/useBi.ts`, `lib/api.ts`, `lib/types.ts`, `lib/theme.ts`.

## Estado de fases — LAS 4 COMPLETAS (verificadas en navegador, 2026-05-26)

- **Fase 1 (Resumen)**: KPIs + histograma temporal (toggle Mes/Día + drill) + dona estado + dona canal + barras por área.
- **Fase 2 (Resueltos/SLA)**: tiempos 0-3/4-7/+7 días (vía `fecha_cierre - fecha_alta`), % dentro de SLA (vs `tipo_reclamo.sla_dias`), evolución días (línea), tabla detalle + export CSV.
- **Fase 3 (Pendientes)**: KPIs por tramo de demora, histograma por estado (toggle), donas demora+estado, ranking por tipo, tabla + export, **mapa de geoposicionamiento** (card al fondo, reusa `DashboardMap` de `modules/dashboard`).
- **Fase 4 (Subreclamos = reclamos con `id_reclamo_padre`)**: KPIs (total + padres), histograma por estado (toggle), donas subreclamos+padres por estado, ranking, tabla con reclamo padre + export.

**Backend**: todos los endpoints en `backend/app/api/routes/bi.py` (router `/api/v1/bi/*`, guard JWT). Mig 65 (`modulos.bi`, nivel 2) aplicada local+prod.

**Datos demo poblados en prod (2026-05-26)**: los 30 reclamos tienen `fecha_cierre` (resueltos) y `latitud/longitud` (todos). Backups `_backup_reclamos_fecha_cierre_2026_05_26` y `_backup_reclamos_geo_demo_2026_05_26` en Supabase.

> **NO pusheado al cierre de la jornada salvo indicación.** Antes de pushear: rebuildear `web-app/dist/` en modo prod (§32 Quirk 1/14) y registrar el módulo en CLAUDE.md (§4 tabla de módulos + §12). Falta un manual en módulo Guías (opcional, §36).

Ver [[project_estado_sesion_y_pendientes]] para el estado vivo.
