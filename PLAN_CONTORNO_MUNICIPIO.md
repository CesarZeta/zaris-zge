# Contorno del municipio y catálogo de gobiernos locales — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** que cada municipio tenga su contorno, traído del IGN con un clic o subido como GeoJSON con un instructivo, depurado en un solo lugar del backend, sobre un catálogo con los 2.082 gobiernos locales y su código oficial.

**Architecture:**
- **Catálogo:** se completa con una migración de datos generada desde una instantánea versionada de Georef.
- **Servicio único:** `services/contorno.py` normaliza, valida, simplifica y guarda. Lo usan:
  - los endpoints de Configuración (administrador del municipio, `municipio_actual`);
  - los de `/super` (alta y ficha);
  - el cliente del WFS del IGN.
- **Frontend:** un componente React compartido (`ContornoMunicipio`) que se monta en el alta, la ficha y Configuración → Sistema, con el instructivo como ayuda dentro de la pantalla.

**Tech Stack:** FastAPI + SQLAlchemy async (asyncpg), `shapely` 2.x (nuevo), httpx, PostgreSQL; React 19 + react-query + Leaflet 1.9 vanilla.

**Spec:** [`PLAN_CONTORNO_MUNICIPIO_DISENO.md`](PLAN_CONTORNO_MUNICIPIO_DISENO.md) (aprobado por César el 2026-10-28). Quien ejecuta lee los dos.

## Global Constraints

- Migraciones:
  - Número al aplicar: hoy 132 (DDL) y 132b (datos).
  - Local y prod en la misma sesión. En prod por MCP `apply_migration`, sin DROP.
  - Backup en prod antes de UPDATE masivos: `_backup_partidos_2026_10_DD`, `_backup_localidades_2026_10_DD`.
- `partidos` y `provincias` siguen siendo clase `global` en `municipio_tabla_clase`, sin `id_municipio`.
- Configuración: se lee y se guarda **solo** con `leer_config` / `guardar_config` (`app/core/config_municipio.py`).
- Todo contorno que se guarde pasa por `normalizar_contorno`. Nunca se guarda el texto del cliente tal cual.
- Redondeo a **5 decimales**. Tolerancia de simplificación ≈ **5 m** (`0.00005` grados). Tope **200 KB** guardado. Entrada hasta **5 MB**.
- Zona derivada: centro del recuadro; radio = mitad del lado mayor + **0,1°**, con tope de 5.
- Pedido al IGN:
  - URL `https://wms.ign.gob.ar/geoserver/ows`, `typeNames=ign:municipio`, `CQL_FILTER=in1='<codigo>'`, `srsName=EPSG:4326`, `outputFormat=application/json`;
  - timeout de **20 s**;
  - solo desde el backend.
- Guards en el backend:
  - Configuración = nivel efectivo 1 (el super pasa como 1);
  - `/super/*` = `require_super_admin`;
  - el cambio del super se registra en la misma transacción con `registrar_acceso_super_en`.
- Mapas: Leaflet vanilla, Esri World Light Gray (`maxNativeZoom: 16`, `maxZoom: 20`) y Dark Gray en modo oscuro (CLAUDE.md §4 y §13). Estilos con tokens del DS. Sin emoji.
- Ningún municipio, coordenada ni nombre real fijo en el código ni en el archivo de ejemplo del instructivo (CLAUDE.md §23).
- La palabra prohibida de las reglas globales no aparece en nada: `grep -riE "h[u]sky"` vacío antes de cada commit.
- Push directo a `main` en verde. Tras pushear backend, verificar prod con el path exacto en `/openapi.json` (CLAUDE.md §9).
- UI verificada navegando con clics en el navegador (CLAUDE.md §41) antes de darla por terminada.

## Review Focus

1. **El IGN responde mal sin dar error HTTP.** GeoServer devuelve una `ExceptionReport` XML o HTML con status 200, o tarda más de 20 s. Se espera el mensaje «El IGN no tiene…/no respondió» con 502/404 limpio, nunca 500. Lo cubre la prueba `ign_respuesta_no_json` (Tarea 5).
2. **Un archivo que no es GeoJSON.** Un `.zip` de shapefile, un KML o un binario subidos por error. Se espera 422 «El archivo no es GeoJSON válido…», con la sugerencia de exportar desde QGIS. Lo cubre `norm_binario_y_kml` (Tarea 3).
3. **Una isla diminuta que la simplificación deja en menos de 4 puntos.** Se espera que esa parte se descarte con un aviso, sin rechazar el archivo entero. Lo cubre `norm_isla_diminuta` (Tarea 3).
4. **Un polígono con hueco** (un enclave). El hueco sobrevive a la simplificación; `punto_en_limite` da afuera en el hueco y la máscara del inicio no lo sombrea. Lo cubren `norm_hueco_preservado` (Tarea 3) y `lectores_hueco` (Tarea 4).
5. **El contorno de San Andrés ya guardado** (Polygon de 3,4 KB, previo a este trabajo) se sigue leyendo igual: mismo encuadre y misma capa en `/dashboard/resumen`. Lo cubre `lectores_compat_san_andres` (Tarea 4).

---

## Mapa de archivos

| Archivo | Responsabilidad |
|---|---|
| `backend/data/georef_gobiernos_locales_2026-10-28.json` | Instantánea de Georef: provincias y gobiernos locales (crear) |
| `backend/data/alias_catalogo_geo.json` | Alias a mano: provincias y partidos viejos → código Georef (crear) |
| `tools/georef_catalogo.py` | `descargar` (baja la instantánea) y `generar-sql` (escribe la 132b) (crear) |
| `backend/migrations/132_catalogo_gobiernos_locales.sql` | DDL: columnas `codigo_georef`, `categoria`, `nombre_completo` (crear) |
| `backend/migrations/132b_catalogo_gobiernos_locales_datos.sql` | Datos generados: casado, alta, bajas, reubicación de localidades (crear, generado) |
| `backend/app/services/contorno.py` | `normalizar_contorno`, `zona_desde_contorno`, `contorno_oficial_ign`, `guardar_contorno`, `quitar_contorno`, `leer_contorno` (crear) |
| `backend/app/services/geo_limite.py` | Lectores con MultiPolygon: `leer_limite`, `encuadre_municipio`, `punto_en_limite` (modificar) |
| `backend/app/api/routes/contorno.py` | Endpoints de Configuración `/api/v1/contorno/*` (crear) |
| `backend/app/api/routes/super_admin.py` | Endpoints `/super/contorno*` y `/super/municipios/{id}/contorno*`, cambio de partido (modificar) |
| `backend/app/api/routes/geo.py` | `/geo/partidos` con `q`, `limit`, `codigo_georef`, `categoria`; invalidar caché del bbox (modificar) |
| `backend/app/api/routes/admin_tablas.py` | 422 si se intenta guardar `geo_limite_geojson`/`geo_limite_origen` por la vía genérica (modificar) |
| `backend/app/services/municipios/alta.py` | Contorno del alta normalizado + zona derivada + origen (modificar) |
| `backend/app/main.py` | Registrar el router `contorno` (modificar) |
| `backend/requirements.txt` | `shapely>=2.0,<3` (modificar) |
| `backend/fixtures/contorno/*.geojson` | Pergamino IGN crudo, en metros, invertido, línea, dos partes, con hueco, isla diminuta (crear) |
| `backend/smoke_contorno.py` | Smoke in-process (estilo `smoke_alta_municipio.py`) (crear) |
| `web-app/src/modules/municipios/contorno/api.ts` | Tipos y llamadas del contorno (crear) |
| `web-app/src/modules/municipios/contorno/ContornoMunicipio.tsx` | Componente compartido: guardado, traer oficial, subir, previsualizar, guardar, quitar (crear) |
| `web-app/src/modules/municipios/contorno/MapaContorno.tsx` | Mapa Leaflet del polígono (crear) |
| `web-app/src/modules/municipios/contorno/InstructivoContorno.tsx` | Instructivo en modal (crear) |
| `web-app/src/modules/municipios/contorno/instructivo/*.png` | Capturas de geojson.io (crear) |
| `web-app/public/ejemplos/contorno_ejemplo.geojson` | Ejemplo genérico descargable (crear) |
| `web-app/src/modules/municipios/components/PartidoSearch.tsx` | Autocompletar de partido / municipio (crear) |
| `web-app/src/modules/municipios/pages/AltaMunicipioPage.tsx`, `MunicipioFichaPage.tsx` | Integración (modificar) |
| `web-app/src/modules/config/views/ParametrosSistemaView.tsx` | Bloque «Contorno del municipio» arriba de la zona (modificar) |
| `web-app/src/modules/dashboard/components/DashboardMap.tsx`, `hooks/useDashboardData.ts` | Máscara y tipo con MultiPolygon (modificar) |

El componente vive en el módulo Municipios y Config lo importa cross-module (memoria
`feedback_cross_module_imports_react`: la fuente es única y lo comparten dos módulos).

---

### Tarea 1: Catálogo de gobiernos locales (instantánea, migraciones, local y prod)

**Files:**
- Create: `tools/georef_catalogo.py`, `backend/data/georef_gobiernos_locales_2026-10-28.json`, `backend/data/alias_catalogo_geo.json`, `backend/migrations/132_catalogo_gobiernos_locales.sql`, `backend/migrations/132b_catalogo_gobiernos_locales_datos.sql`
- Test: `backend/smoke_contorno.py` (pruebas `catalogo_*`)

**Interfaces:**
- Produces:
  - `partidos.codigo_georef VARCHAR(6) UNIQUE NULL`, `partidos.categoria VARCHAR(40)`, `partidos.nombre_completo VARCHAR(200)`;
  - `provincias.codigo_georef CHAR(2) UNIQUE NULL`.
  - La Tarea 2 los lee; la Tarea 5 lee `partidos.codigo_georef` vía `municipios.id_partido`.

- [ ] **Paso 1: instantánea.** `python tools/georef_catalogo.py descargar` pide a Georef
  `/provincias?campos=id,nombre&max=30` y
  `/municipios?max=5000&campos=id,nombre,nombre_completo,categoria,provincia.id,provincia.nombre`.
  - Escribe la instantánea en UTF-8, ordenada por código, con `{"fecha": "2026-10-28", "provincias": [...], "municipios": [...]}`.
  - Verificar: 24 provincias y 2.082 municipios.
- [ ] **Paso 2: generador.** `python tools/georef_catalogo.py generar-sql` escribe la 132b.
  - **Normalización:** `norm(s)` = NFD sin diacríticos, minúsculas, espacios colapsados. En SQL, la misma con `lower(translate(...))` sobre `áéíóúüñÁÉÍÓÚÜÑ`. Sin depender de la extensión `unaccent`.
  - **Contenido del SQL:**
    1. Tabla temporal `_georef` con todos los gobiernos locales.
    2. Tabla temporal `_alias` con los alias, por **nombre viejo**, nunca por id: los ids difieren entre local y prod.
    3. UPDATE de `provincias.codigo_georef` por nombre normalizado + alias (la de Tierra del Fuego necesita alias).
    4. UPDATE de las filas existentes de `partidos` por (provincia, nombre normalizado) o alias, seteando código, categoría y nombre completo.
    5. INSERT ... ON CONFLICT (codigo_georef) DO UPDATE del resto. Los 6 pares de nombre repetido dentro de una provincia (Georef 2026-10-28: San Bernardo/82, Yerba Buena/90, Villa Sarmiento/14, Los Chañaritos/14, Aldea San Antonio/30, San Justo/30) usan `nombre_completo` como `nombre`. Si aun así colisiona, el nombre lleva ` (<codigo>)`. El generador **falla** si queda alguna colisión con `UNIQUE (id_provincia, nombre)`.
    6. `activo = false` para las filas sin código.
    7. Reubicación de `localidades` de filas sin código: va al gobierno local de la misma provincia cuyo `norm(nombre)` = `norm(localidad.nombre)`, solo si hay exactamente uno.
    8. `RAISE NOTICE` con los conteos: casados, insertados, dados de baja, localidades reubicadas y localidades que quedaron en filas de baja.
- [ ] **Paso 3: alias.**
  - Correr el generador en modo `--informe` contra local: lista las filas de `partidos` que quedarían sin casar.
  - Cargar en `alias_catalogo_geo.json` las que son el mismo lugar con otro nombre. Mínimo: Mar del Plata (General Pueyrredón) → General Pueyrredón; Bariloche → San Carlos de Bariloche; Iguazú → Puerto Iguazú.
  - Repetir el informe contra prod (`execute_sql` de solo lectura sobre `partidos`/`provincias`).
- [ ] **Paso 4: pruebas en rojo.** En `smoke_contorno.py`:
  - `catalogo_completo`: `count(*) FROM partidos WHERE codigo_georef IS NOT NULL` = 2082. `provincias` con código = 24.
  - `catalogo_codigos`: Pergamino `060623` y Vicente López `060861` en provincia Buenos Aires; Comuna 3 `022021`.
  - `catalogo_sin_huerfanos_de_reclamos`: el conteo de reclamos cuya localidad resuelve a un partido es el mismo antes y después. El valor previo se guarda en el paso 5.
  - `catalogo_bajas_sin_municipio`: ningún `municipios.id_partido` apunta a una fila con `activo = false`.

  Correr → FAIL (las columnas no existen).
- [ ] **Paso 5: aplicar en local.**
  1. Anotar el conteo previo de reclamos con localidad → partido.
  2. Aplicar 132 y 132b con `driver_connection.execute` (CLAUDE.md §5).
  3. Correr `python smoke_contorno.py catalogo_completo catalogo_codigos catalogo_sin_huerfanos_de_reclamos catalogo_bajas_sin_municipio` → OK.
  4. Correr la 132b **dos veces** y verificar los mismos conteos: es idempotente.
- [ ] **Paso 6: aplicar en prod.**
  1. Backup `CREATE TABLE _backup_partidos_2026_10_DD AS SELECT * FROM partidos` (ídem `localidades`) por `execute_sql`.
  2. `apply_migration` 132 y después 132b.
  3. Verificación independiente con `execute_sql`: conteos de los cuatro checks del paso 4, y que el conteo de reclamos con localidad → partido sea el mismo que antes (anotarlo antes del paso 1).
- [ ] **Paso 7: commit.** `feat(it-01): catalogo de gobiernos locales con codigo de Georef (migs 132/132b)`.

### Tarea 2: Selector de partido / municipio con autocompletar

**Files:**
- Modify: `backend/app/api/routes/geo.py` (`listar_partidos`), `web-app/src/modules/municipios/api.ts` (`listarPartidos`), `AltaMunicipioPage.tsx`, `MunicipioFichaPage.tsx`
- Create: `web-app/src/modules/municipios/components/PartidoSearch.tsx`
- Test: `smoke_contorno.py` (`geo_partidos_q`)

**Interfaces:**
- Consumes: columnas de la Tarea 1.
- Produces:
  - `GET /api/v1/geo/partidos?id_provincia=&q=&limit=` → `[{id_partido, id_provincia, nombre, nombre_completo, categoria, codigo_georef}]`. `limit` por defecto 20 y `le=100`; sin `q`, mantiene el comportamiento de hoy.
  - `PartidoSearch({ idProvincia, value: number | null, onChange(p: PartidoOpcion | null) })`.

- [ ] **Paso 1: prueba en rojo.** `geo_partidos_q`:
  - `q=perga&id_provincia=<BA>` devuelve una fila con `codigo_georef == "060623"` y `categoria` no vacía;
  - `q=villa sarm&id_provincia=<Córdoba>` devuelve 2 filas con nombres distintos;
  - `activo=false` nunca aparece.

  FAIL.
- [ ] **Paso 2:** implementar el `q` (ILIKE con AND por palabra sobre `nombre` y `nombre_completo`, como CLAUDE.md §2) y el `limit`. PASS.
- [ ] **Paso 3: `PartidoSearch`.**
  - Patrón de `CiudadanoSearch`: debounce de 250 ms y `skipNextRef` tras elegir (CLAUDE.md §29).
  - Muestra «Nombre — Categoría».
  - Reemplaza el `<select>` de partido en el alta y en la ficha. El resto del form no cambia: disponibilidad del partido, municipio ficticio.
- [ ] **Paso 4: verificación.** `pnpm typecheck` limpio. En el navegador, local: alta → provincia Córdoba → escribir «villa ma» → aparecen Villa María y Villa de María → elegir → la disponibilidad responde.
- [ ] **Paso 5: commit.** `feat(it-01): partido o municipio con autocompletar sobre el catalogo completo`.

### Tarea 3: `normalizar_contorno` (servicio puro) y fixtures

**Files:**
- Create: `backend/app/services/contorno.py` (parte pura), `backend/fixtures/contorno/` (ver abajo)
- Modify: `backend/requirements.txt` (`shapely>=2.0,<3`)
- Test: `smoke_contorno.py` (`norm_*`)

**Interfaces:**
- Produces:
  ```python
  class ContornoInvalido(ValueError):  # .mensaje (para el usuario) y .paso ("formato"|"metros"|"invertido"|"tipo"|"pais"|"tamano")
  @dataclass
  class ContornoNormalizado:
      geometria: dict          # GeoJSON Polygon (1 parte) o MultiPolygon (varias), [lon, lat], 5 decimales
      partes: int
      vertices_antes: int
      vertices_despues: int
      superficie_km2: float
      recuadro: dict           # {sur, oeste, norte, este}
      avisos: list[str]
  def normalizar_contorno(entrada: str | bytes | dict, *, codigo_pais: str = "AR") -> ContornoNormalizado
  def zona_desde_contorno(c: ContornoNormalizado) -> dict  # {"geo_bbox_centro_lat","geo_bbox_centro_lon","geo_bbox_delta_grados"} como str
  ```
- **Fixtures:**
  - `pergamino_ign.geojson`: respuesta cruda del IGN para `060623` (FeatureCollection, MultiPolygon, 2.679 vértices);
  - `pergamino_metros.geojson`: el mismo reproyectado a EPSG:22185, generado una vez con `pyproj` en el scratchpad (`pyproj` no entra a requirements);
  - `pergamino_invertido.geojson`: [lat, lon];
  - `linea.geojson`: LineString;
  - `dos_partes.geojson`: FeatureCollection con 2 Features Polygon;
  - `con_hueco.geojson`: Polygon con anillo interior;
  - `isla_diminuta.geojson`: MultiPolygon con una parte de unos 2 m de lado.

  Los inventados usan coordenadas genéricas dentro de Argentina, sin nombre de municipio real.

- [ ] **Paso 1: pruebas en rojo** (cada una con `check`):
  - `norm_pergamino_ign`: `partes == 1`, `vertices_antes == 2679`, `vertices_despues < 2679`, `len(json.dumps(geometria)) <= 200_000`, todas las coordenadas con ≤ 5 decimales, recuadro ≈ (-34.176, -60.943, -33.540, -60.139) con ±0,001.
  - `norm_metros`: `ContornoInvalido` con `paso == "metros"` y «EPSG:4326» en el mensaje.
  - `norm_invertido`: `paso == "invertido"`.
  - `norm_linea`: `paso == "tipo"` y «LineString» en el mensaje.
  - `norm_dos_partes`: `geometria["type"] == "MultiPolygon"` y `partes == 2`.
  - `norm_hueco_preservado`: Polygon con 2 anillos tras normalizar.
  - `norm_isla_diminuta`: `partes == 1` y algún aviso que contiene «descart».
  - `norm_binario_y_kml`: bytes `PK\x03\x04…` y `<kml …>` dan `paso == "formato"`, y el mensaje menciona QGIS.
  - `norm_vacio`: `{"type":"FeatureCollection","features":[]}` y un Feature con `geometry: null` dan `paso == "tipo"`.
  - `norm_tamano_entrada`: entrada de más de 5 MB da `paso == "tamano"`.
  - `norm_z_y_sin_cerrar`: coordenadas `[lon, lat, z]` y anillo sin cerrar → válido, cerrado, sin `z`.
  - `norm_fuera_de_pais`: polígono en Europa da `paso == "pais"`.
  - `zona_pergamino`: `zona_desde_contorno` da centro ≈ (-33.858, -60.541) y delta ≈ 0.402 + 0.1 = **0.502** (±0,001), como str.

  FAIL.
- [ ] **Paso 2: implementar con `shapely`.**
  - `shape()` → `make_valid` si `not is_valid`.
  - `simplify(0.00005, preserve_topology=True)`.
  - Descartar las partes que quedan con área 0 o con menos de 4 puntos, con aviso.
  - `set_precision` no: redondeo manual a 5 decimales al serializar.
  - **Detección de metros/invertido:** si `|x| > 180` o `|y| > 90` → `metros`. Si cae fuera de `ENCUADRE_PAIS[codigo_pais]` pero invertido cae adentro → `invertido`. Si no → `pais`.
  - Superficie aproximada: área proyectando con `cos(lat media)`; alcanza para el resumen.

  PASS.
- [ ] **Paso 3:** `pip install -r requirements.txt` en local y registrar la versión instalada. Verificar con `python -c "import shapely; print(shapely.__version__)"` desde `backend/`.
- [ ] **Paso 4: commit.** `feat(it-01): normalizacion de contornos con shapely y fixtures`.

### Tarea 4: Lectores con MultiPolygon (backend y máscara del inicio)

**Files:**
- Modify: `backend/app/services/geo_limite.py`, `web-app/src/modules/dashboard/hooks/useDashboardData.ts` (tipo `LimiteMunicipio`), `web-app/src/modules/dashboard/components/DashboardMap.tsx` (`mascaraExterior` y bounds)
- Test: `smoke_contorno.py` (`lectores_*`)

**Interfaces:**
- Consumes: `normalizar_contorno` (Tarea 3), para armar fixtures en la base.
- Produces:
  - `leer_limite(db, id_municipio) -> dict | None` acepta Polygon y MultiPolygon. Lo inválido devuelve None y loguea `warning` **con el `id_municipio`**.
  - `encuadre_municipio` recorre todas las partes.
  - `punto_en_limite(geo, lat, lon) -> bool` da adentro si está en alguna parte y fuera de sus huecos.
  - El tipo TS es `LimiteMunicipio = { type: 'Polygon'; coordinates: number[][][] } | { type: 'MultiPolygon'; coordinates: number[][][][] }`.

- [ ] **Paso 1: pruebas en rojo.**
  - `lectores_multi`: guardar en un municipio de prueba el MultiPolygon de `dos_partes`. `encuadre_municipio` cubre las dos partes. `punto_en_limite` da adentro en cada parte y afuera entre ellas.
  - `lectores_hueco`: afuera en el hueco de `con_hueco`.
  - `lectores_compat_san_andres`: municipio 1 local, `leer_limite` igual que antes del cambio. `encuadre_municipio(1)` da el mismo recuadro que el valor anotado antes de tocar el código.

  FAIL las dos primeras.
- [ ] **Paso 2:** implementar. PASS las tres. Correr también `python smoke_alta_municipio.py test_encuadre_mapas` → OK.
- [ ] **Paso 3: máscara.** El mundo con un hueco por **cada anillo exterior**; los huecos del contorno se vuelven a sombrear. Bounds de todas las partes.
  - Verificación en el navegador, local: el municipio de prueba con `dos_partes` muestra dos zonas limpias, y el encuadre las incluye a las dos.
  - Verificación en el navegador, local: San Andrés se ve igual que antes (captura antes/después).
- [ ] **Paso 4: commit.** `feat(it-01): el contorno puede tener varias partes y huecos`.

### Tarea 5: Contorno oficial del IGN, guardar y quitar (backend)

**Files:**
- Modify: `backend/app/services/contorno.py` (parte con base de datos y red), `super_admin.py`, `geo.py`, `admin_tablas.py`, `municipios/alta.py`, `main.py`
- Create: `backend/app/api/routes/contorno.py`
- Test: `smoke_contorno.py` (`api_*`, `ign_*`)

**Interfaces:**
- Consumes: `normalizar_contorno`, `zona_desde_contorno` (Tarea 3); `partidos.codigo_georef` (Tarea 1).
- Produces (servicio):
  ```python
  class IgnSinContorno(Exception): ...        # mensaje para el usuario
  async def contorno_oficial_ign(codigo_georef: str, *, codigo_pais="AR") -> tuple[ContornoNormalizado, dict]  # origen
  async def leer_contorno(db, id_municipio) -> dict | None   # {"geometria", "origen", "resumen"}
  async def guardar_contorno(db, id_municipio, c: ContornoNormalizado, origen: dict) -> dict  # escribe limite+origen+zona, NO commitea
  async def quitar_contorno(db, id_municipio) -> None         # NO commitea; la zona queda
  ```
  - El `origen` es un JSON guardado en la clave `geo_limite_origen`:
    - IGN: `{"via":"ign","codigo":"060623","nombre":"Municipio Pergamino","fuente":"ARBA - …","fecha":"YYYY-MM-DD"}`;
    - archivo: `{"via":"archivo","archivo":"<nombre>","fecha":"YYYY-MM-DD"}`.
- Produces (rutas). Respuesta común: `ContornoVista = {geometria, partes, vertices_antes, vertices_despues, superficie_km2, recuadro, avisos, origen}`.
  - **Configuración** (`municipio_actual`, nivel efectivo 1, `modulo_habilitado` no aplica: es configuración):
    - `GET /api/v1/contorno` → `{contorno: ContornoVista|null}`;
    - `POST /api/v1/contorno/previsualizar` body `{geojson: str, archivo: str|null}` → `ContornoVista` + `aviso_zona: str|null`;
    - `GET /api/v1/contorno/oficial` → `ContornoVista`;
    - `PUT /api/v1/contorno` body `{geojson: str, origen: {...}}` → `{contorno, zona}`. Re-normaliza; el `origen.via == "ign"` se acepta solo si el código coincide con el partido del municipio, si no 422;
    - `DELETE /api/v1/contorno` → 204.
  - **Super administrador:**
    - `POST /super/contorno/previsualizar` body `{geojson, archivo, codigo_pais}`;
    - `GET /super/contorno-oficial?id_partido=` (para el alta);
    - `GET|PUT|DELETE /super/municipios/{id}/contorno`, y el GET de oficial `/super/municipios/{id}/contorno/oficial`.
  - Errores:
    - `ContornoInvalido` → 422 `{detail: mensaje, paso}`;
    - `IgnSinContorno` → 404;
    - IGN caído, timeout o respuesta no JSON → 502 «El IGN no respondió…»;
    - municipio sin partido con código → 409 «Este municipio no tiene partido con código oficial: subí un archivo».

- [ ] **Paso 1: pruebas en rojo** (con `httpx.MockTransport` para el IGN, inyectado por un parámetro `cliente` opcional de `contorno_oficial_ign`):
  - `ign_ok`: la respuesta es el fixture de Pergamino; origen con `via == "ign"` y `codigo == "060623"`.
  - `ign_respuesta_no_json`: status 200 con `<ows:ExceptionReport>` → 502 limpio, sin 500.
  - `ign_vacio`: `features: []` → 404 con «no tiene».
  - `ign_timeout` → 502.
  - `api_guardar_y_zona`:
    - el PUT en Configuración con el fixture deja `geo_limite_geojson` igual a `geometria`;
    - `geo_limite_origen` queda con `via == "archivo"`;
    - las tres `geo_bbox_*` quedan iguales a `zona_desde_contorno`;
    - todo verificado con `leer_configs` en una sesión nueva.
  - `api_aviso_zona`: con zona previa lejana (otra provincia), `previsualizar` devuelve `aviso_zona` no nulo.
  - `api_guards`:
    - nivel 2 → 403 en PUT/DELETE/previsualizar;
    - super en `/super/municipios/{id}/contorno` → 200 y una fila nueva en `super_admin_acceso` en la misma transacción;
    - nivel 1 de otro municipio no ve el contorno ajeno.
  - `api_admin_tablas_bloquea`: POST/PUT genérico de `configuracion_general` con clave `geo_limite_geojson` → 422 «se carga desde Configuración → Sistema → Contorno».
  - `api_alta_contorno`:
    - un alta con `geo_limite_geojson` del fixture lo guarda normalizado, con origen `archivo` y zona derivada;
    - con el fixture `linea` → 422 y **no** se crea el municipio.
  - `api_quitar`: DELETE deja la clave vacía y la zona intacta; `encuadre_municipio` pasa a `origen == "zona"`.

  FAIL.
- [ ] **Paso 2:** implementar servicio, rutas y registro en `main.py`.
  - Invalidar `_bbox_cache[id_municipio]` de `geo.py` al guardar y al quitar: exponer `invalidar_bbox(id_municipio)`.
  - Marcador de deploy: el path `/api/v1/contorno/oficial` en `/openapi.json`.

  PASS todo `smoke_contorno.py` y `smoke_alta_municipio.py` completo (sin regresiones).
- [ ] **Paso 3: cambio de partido** (`editar_municipio` en `super_admin.py`). `MunicipioSuperUpdate` suma `quitar_contorno: bool = False`.
  - Si cambia `id_partido` y el origen guardado es `via == "ign"` con un código distinto del del partido nuevo:
    - sin `quitar_contorno` → 409 `{detail: "El contorno guardado es del partido anterior. Confirmá para quitarlo.", contorno_partido_anterior: true}`;
    - con `quitar_contorno` → se quita en la misma transacción.
  - Si el origen es `archivo` → se guarda el cambio y la respuesta suma `aviso_contorno`.
  - Pruebas `api_cambio_partido_ign` (409 y después 200 con el contorno vacío) y `api_cambio_partido_archivo` (200, contorno intacto, aviso). PASS.
- [ ] **Paso 4: commit y push.** `feat(it-01): contorno oficial del IGN y guardado con zona derivada`.
  - Push a `main`.
  - Poll de `/openapi.json` hasta que aparezca `"/api/v1/contorno/oficial"` (path exacto).
- [ ] **Paso 5: ¿el IGN llega desde Railway?** Es lo primero que dijo el diseño, antes de las pantallas.
  1. Pedirle a César, paso a paso, que ingrese en `https://zge.zaris.com.ar` en el navegador integrado con su cuenta de super (clave + código).
  2. Con esa sesión, `browser_eval` hace `fetch('<API>/api/v1/super/contorno-oficial?id_partido=<id de Pergamino en prod>')` con el token.
  3. Esperado: 200 con `vertices_antes == 2679`.
  4. Si da 502 o timeout: parar, anotarlo y aplicar la decisión del diseño (botón oficial deshabilitado con el aviso, subida de archivo como vía). Preguntarle a César por copia versionada o intermediario antes de seguir con la Tarea 6.

### Tarea 6: Componente `ContornoMunicipio` y las tres pantallas

**Files:**
- Create: `web-app/src/modules/municipios/contorno/{api.ts, ContornoMunicipio.tsx, MapaContorno.tsx, ContornoMunicipio.module.css}`
- Modify: `AltaMunicipioPage.tsx`, `MunicipioFichaPage.tsx`, `web-app/src/modules/config/views/ParametrosSistemaView.tsx`

**Interfaces:**
- Consumes: las rutas de la Tarea 5.
- Produces:
  ```ts
  type ModoContorno =
    | { modo: 'config' }                                   // /api/v1/contorno/*
    | { modo: 'ficha'; idMunicipio: number }               // /super/municipios/{id}/contorno*
    | { modo: 'alta'; idPartido: number | null; codigoPais: string;
        onCambio(c: { geojson: string; origen: OrigenContorno; zona: Zona } | null): void }  // no guarda: el alta lo manda en su POST
  function ContornoMunicipio(props: ModoContorno & { onAbrirInstructivo(paso?: string): void }): JSX.Element
  ```

- [ ] **Paso 1: componente.** Estados:
  - **guardado:** mapa chico + origen + fecha + «Reemplazar» / «Quitar» con `ConfirmModal`;
  - **sin contorno:** «Traer contorno oficial (IGN)» (deshabilitado con explicación si no hay partido con código) y «Subir archivo» (`.geojson`, `.json`) + «¿Cómo armo el archivo?»;
  - **previsualizando:** mapa encuadrado + resumen «N partes · antes → después vértices · X km² · origen» + avisos + `aviso_zona` + «Guardar contorno» / «Descartar»;
  - **error:** mensaje del 422 + enlace «Ver cómo arreglarlo» que abre el instructivo en el `paso`.

  Las mutaciones cierran al confirmar y el resultado llega por toast (CLAUDE.md §23).
- [ ] **Paso 2: `MapaContorno`.** Leaflet vanilla en `useEffect` con `useRef<L.Map>` (patrón de `MapaPicker`). Dibuja el GeoJSON con el borde `--zaris-orange` y hace `fitBounds`. Elige el tile claro u oscuro según `data-theme`.
- [ ] **Paso 3: alta.**
  - Reemplazar el textarea de GeoJSON por `ContornoMunicipio` en `modo: 'alta'`.
  - Con contorno, los tres campos de zona se completan con la zona derivada y quedan editables.
  - Al cambiar el partido con un contorno de origen IGN cargado: quitarlo y mostrar un aviso (mismo criterio que la ficha).
- [ ] **Paso 4: ficha.**
  - Sección «Contorno del municipio» con `modo: 'ficha'`.
  - En la edición del partido, manejar el 409 `contorno_partido_anterior`: `ConfirmModal` «Quitar el contorno y cambiar el partido» → reenviar con `quitar_contorno: true`.
  - Mostrar `aviso_contorno` si viene.
- [ ] **Paso 5: Configuración → Sistema.**
  - Bloque «Contorno del municipio», arriba de «Búsqueda de direcciones».
  - Ese bloque suma: «Se recalcula al guardar el contorno; podés ajustarla después».
  - Tras guardar o quitar, invalidar las queries de la zona para que se vean los valores nuevos.
- [ ] **Paso 6: verificación navegando** (local, uvicorn con mail en MOCK):
  - alta con Pergamino → «Traer contorno oficial» → previsualiza → completar el alta → la ficha muestra el contorno y la zona derivada;
  - ficha del municipio 6 local (ficticio) → botón oficial deshabilitado → subir `pergamino_ign.geojson` → guardar → el inicio de ese municipio (super con «Operando en») muestra la máscara;
  - subir `linea.geojson` → error con enlace al instructivo;
  - Config como administrador de nivel 1 → mismo circuito;
  - cambio de partido en la ficha con contorno IGN → confirmación → contorno quitado.

  `pnpm typecheck` limpio.
- [ ] **Paso 7: commit.** `feat(it-01): cargar el contorno desde el alta, la ficha y Configuracion`.

### Tarea 7: Instructivo dentro de la pantalla

**Files:**
- Create: `web-app/src/modules/municipios/contorno/InstructivoContorno.tsx` (+ `.module.css`), `web-app/src/modules/municipios/contorno/instructivo/geojsonio-0N.png`, `web-app/public/ejemplos/contorno_ejemplo.geojson`
- Modify: `ContornoMunicipio.tsx` (abre el instructivo en el `paso` pedido)

**Interfaces:**
- Produces: `InstructivoContorno({ abierto, paso?: 'formato'|'metros'|'invertido'|'tipo'|'pais'|'tamano'|'geojsonio'|'qgis', onCerrar })`. Los `paso` coinciden con `ContornoInvalido.paso` (Tarea 3).

- [ ] **Paso 1: contenido**, en el orden del diseño §4.7:
  1. «Antes que nada»: el oficial primero.
  2. Qué archivo sirve: tabla de sí y no.
  3. Camino A, geojson.io: pasos numerados con captura.
  4. Camino B, QGIS: pasos numerados.
  5. «Si da error»: una entrada por `paso`, con causa y arreglo, con `id` para saltar ahí.
  6. Descarga del ejemplo.
- [ ] **Paso 2: capturas de geojson.io** con el navegador integrado, una por paso:
  1. abrir;
  2. buscar una ciudad genérica;
  3. herramienta de polígono;
  4. polígono cerrado;
  5. menú Save → GeoJSON.

  Guardarlas como PNG de ≤ 200 KB cada una. Mirar cada captura antes de usarla: que se vea el control señalado.
- [ ] **Paso 3: pasos de QGIS** verificados contra la **documentación oficial de QGIS LTR en español** (`docs.qgis.org`, capítulo «Guardar y exportar capas»). Citar en un comentario del código la URL y la versión consultada. Nombres exactos: «Exportar», «Guardar objetos como…» / «Guardar objetos seleccionados como…», «Formato», «SRC», «Geometría → Incluir dimensión z».
- [ ] **Paso 4: ejemplo descargable.** Un Polygon genérico (un cuadrado chico en una zona rural de Argentina, sin nombre real). Verificar que `normalizar_contorno` lo acepta: agregar `norm_ejemplo_instructivo` a `smoke_contorno.py` → PASS.
- [ ] **Paso 5: verificación navegando.**
  - El instructivo abre desde el alta, la ficha y Config.
  - Desde un error de `metros`, abre en esa sección.
  - Las capturas cargan.
  - La descarga baja el archivo.

  `pnpm typecheck` limpio.
- [ ] **Paso 6: commit.** `feat(it-01): instructivo para armar el archivo del contorno`.

### Tarea 8: Prod, archivo para el municipio 6 y documentación

**Files:**
- Modify: `ESTADO.md`, `CLAUDE.md` (§21: migs 132/132b; §23 o §10: regla «el contorno se guarda solo con `services/contorno.py`»), `HISTORIAL_MIGRACIONES.md`

- [ ] **Paso 1: push y deploy.**
  - Push. Verificar el deploy de Pages: el `<script src>` de `zge.zaris.com.ar/web-app/dist/` es igual al de `zaris-zge.pages.dev`.
  - Verificar Railway por el marcador de la Tarea 5. Si `shapely` hizo fallar el build, se ve como deploy viejo: revisar el estado en Railway.
- [ ] **Paso 2: prueba en prod, navegando.** Con la sesión de super de César:
  - ficha del municipio 6 → subir `backend/fixtures/contorno/pergamino_ign.geojson` → previsualiza → guardar;
  - verificación independiente por `execute_sql`: `geo_limite_geojson` no vacío, `geo_limite_origen` con `via` `archivo`, zona derivada;
  - el inicio del municipio 6 muestra el contorno.
- [ ] **Paso 3: documentación.**
  - `ESTADO.md`: trabajo (b) hecho, (c) siguiente; el pendiente del catálogo de partidos cerrado.
  - `CLAUDE.md` §21: 132/132b; la próxima libre, 133.
  - La regla del contorno.
  - Memoria `project_preguntas_arranque`: sacar el ítem del catálogo.
- [ ] **Paso 4: commit y push.** `docs(it-01): contorno del municipio y catalogo de gobiernos locales en prod`.
