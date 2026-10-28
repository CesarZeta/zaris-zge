# Contorno del municipio y catálogo de gobiernos locales — diseño

> IT-01, trabajo (b) aprobado por César el 2026-10-28. Este documento es el diseño; el plan de
> ejecución se escribe después, a partir de él. Las decisiones marcadas **[César]** son suyas; las
> marcadas **[Claude]** son propuestas mías que César puede revisar; lo demás queda al constructor.

## 1. Para qué

Cada municipio necesita su **contorno** (el límite del territorio). Se usa para:

- el mapa del inicio, con lo de afuera sombreado;
- el encuadre de todos los mapas;
- el generador de datos demo, que descarta los puntos que caen afuera;
- la app del vecino (trabajo (c), aparte).

Hoy el contorno se carga como texto JSON pegado a mano. Solo lo tiene San Andrés, redondeado a mano
(3,4 KB). Un municipio nuevo arranca sin contorno, y nadie de un municipio sabe producir ese texto.

La idea es que el contorno se consiga casi siempre **de una fuente oficial con un clic**:

- la fuente es el IGN;
- la búsqueda usa el código oficial del gobierno local;
- el usuario lo confirma viendo el polígono sobre el mapa.

Cuando la fuente oficial no lo tenga, o no coincida con el municipio, el usuario **sube un archivo**
siguiendo un instructivo muy explícito.

Para buscar por código oficial, el catálogo de partidos tiene que tener ese código y estar completo.
Por eso este trabajo también completa el catálogo con los 2.082 gobiernos locales del país. Eso
cierra el pendiente «catálogo de partidos incompleto» de la lista de arranque.

## 2. Objetivos, no objetivos y anti-objetivos

**Objetivos**

1. Catálogo con todos los gobiernos locales del país (Georef «municipios»: partidos de Buenos Aires,
   comunas de la Ciudad, municipios y comunas del resto), cada uno con su código oficial.
2. Traer el contorno oficial del IGN para el gobierno local del municipio, previsualizarlo y guardarlo.
3. Subir un archivo GeoJSON propio, con un instructivo paso a paso, cuando el oficial no sirva.
4. Una sola depuración en el backend para las dos vías:
   - validar el archivo;
   - normalizarlo;
   - redondear las coordenadas;
   - simplificar el contorno;
   - avisar y rechazar con mensajes que digan qué hacer.
5. Al guardar, recalcular la zona de búsqueda de direcciones (`geo_bbox_*`) desde el contorno.
6. Que todos los que leen el contorno acepten **multipolígonos** (varias partes, por ejemplo islas):
   lectura, encuadre, «punto adentro», máscara del mapa del inicio.
7. Disponible en el alta y la ficha (super administrador) y en Configuración (administrador del
   municipio).
8. Un GeoJSON de prueba para el municipio 6 de prod (zona Pergamino).

**No objetivos**

- Dibujar o editar el polígono dentro de ZARIS (César: no hace falta; se dibuja afuera).
- Completar las **localidades** del país. Solo se reubican las existentes (§4.3).
- Contornos de países que no sean Argentina (hoy solo Argentina da de alta municipios).
- El trabajo (c), mapa de la PWA y `/geo/encuadre` público, que va aparte. Este trabajo sí deja
  `encuadre_municipio` correcto con multipolígonos, que es lo que (c) va a consumir.
- Manual operativo `docs/manual_*`: está suspendido (CLAUDE.md §36). El instructivo es ayuda
  contextual dentro de la pantalla (§4.7).

**Anti-objetivos** (cosas que harían fracasar el trabajo aunque «funcione»)

- Que un contorno inválido se guarde y el mapa quede sin contorno **sin que nadie se entere**. Pasa
  hoy con un multipolígono: `leer_limite` lo descarta en silencio.
- Que ZARIS dependa del IGN para mostrar un mapa. El IGN se consulta solo al cargar; se guarda la copia.
- Que el catálogo nuevo rompa reclamos, localidades o municipios existentes (FK, historia).
- Que un municipio quede con el contorno de otro sin aviso, por ejemplo por elegir mal el partido.
- Hardcodear un municipio, coordenadas o ejemplos de un municipio real en el código (CLAUDE.md §23).

## 3. Hechos verificados (2026-10-28)

**Georef (`apis.datos.gob.ar/georef/api`)**
- `/municipios` lista **2.082** gobiernos locales (Buenos Aires 135, Ciudad 15 comunas, Córdoba 427,
  Santa Fe 363, Entre Ríos 269).
- Cada uno tiene `id` de 6 dígitos (Pergamino `060623`, Vicente López `060861`, Comuna 3 `022021`),
  `nombre`, `categoria` (Municipio, Comuna, …) y `provincia.id`.
- `/departamentos` lista 529.

**IGN (servicio WFS `https://wms.ign.gob.ar/geoserver/ows`)**
- Capa `ign:municipio`: **2.114** polígonos. Su campo `in1` es el código de Georef.
- Pedido probado:
  `service=WFS&version=2.0.0&request=GetFeature&typeNames=ign:municipio&outputFormat=application/json&srsName=EPSG:4326&CQL_FILTER=in1='060623'`.
  - Pergamino: MultiPolygon, 1 parte, 2.679 vértices, 70 KB, fuente ARBA.
  - Vicente López: 20 KB.
  - Comuna 3 de la Ciudad: devuelve su polígono.
  - Cruz del Eje (Córdoba, `140182`): devuelve su polígono.
- El archivo masivo de Georef (`infra.datos.gob.ar/georef/departamentos.geojson`) **no sirve**: está
  muy simplificado (Vicente López tiene 8 vértices).

**ZARIS**
- `partidos(id_partido, id_provincia, nombre, activo)`, con UNIQUE `(id_provincia, nombre)` y clase
  `global`. Sin código oficial.
  - Prod: 102 filas, 50 de Buenos Aires.
  - Fuera de Buenos Aires son departamentos («Punilla», «Confluencia») o un «Capital» genérico.
- `provincias(id_provincia, nombre, iso_code, activo, codigo_pais)`: `iso_code` vacío, sin código oficial.
- `localidades(id_localidad, id_partido, nombre, codigo_postal, activo)`: 352 filas, FK a `partidos`
  con RESTRICT.
- Reclamos con localidad en prod: 3.006 (lectura: `reclamos.py` hace JOIN localidad → partido).
- Municipios en prod: **ninguno tiene `id_partido`** (1 San Andrés demo, 2 de baja, 5 modelo, 6 «de
  prueba» ficticio). El cambio de catálogo no toca ningún municipio vigente.
- `uq_municipios_partido_vigente` permite un municipio vigente por partido (mig 131).
- `services/geo_limite.py`:
  - `_validar` acepta **solo `Polygon`**;
  - `encuadre_municipio` usa el primer anillo;
  - `punto_en_limite` recorre los anillos de un solo polígono.
- El alta guarda `geo_limite_geojson` **sin validar** (`alta.py::_poner_config`).
- `DashboardMap.tsx::mascaraExterior` usa `limite.coordinates[0]`: un solo polígono, sin huecos propios.
- Configuración → Sistema oculta `geo_limite_geojson` a propósito (`ParametrosSistemaView.tsx`); la
  zona (`geo_bbox_*`) se edita ahí con «Guardar zona».
- El alta elige el partido con un `<select>` por provincia (`listarPartidos(id_provincia)`). Con 427
  opciones en Córdoba eso es inusable (CLAUDE.md §23: con unas 30 o más opciones, autocompletar).
- El backend no tiene `shapely`. QGIS no está instalado en esta máquina.

## 4. Diseño

### 4.1 Decisiones de César

- **[César]** Camino principal: el contorno oficial (IGN). Camino alternativo: un archivo que sube el
  usuario, con instructivo lo más explícito posible.
- **[César]** Quien carga el contorno es el **administrador del municipio** (Configuración). El super
  administrador también, desde el alta y la ficha (puesta en marcha).
- **[César]** El formato del archivo es GeoJSON.
- **[César]** El catálogo se completa con el código oficial, y con los **gobiernos locales** (2.082),
  no con los departamentos.

### 4.2 Catálogo de gobiernos locales

**Esquema** (migración DDL sin DROP; en prod por MCP):
- `provincias.codigo_georef CHAR(2)` UNIQUE.
- `partidos.codigo_georef VARCHAR(6)` UNIQUE, nullable porque las filas viejas que no casan quedan sin
  código.
- `partidos.categoria VARCHAR(40)` y `partidos.nombre_completo VARCHAR(200)`.
- Las dos tablas siguen siendo `global` en `municipio_tabla_clase`. **[Claude]** La tabla conserva el
  nombre `partidos`: renombrarla toca decenas de lugares sin ganancia. En pantalla se rotula
  «Partido / municipio».

**Datos**: migración aparte, solo datos, siguiendo el patrón `75b` de CLAUDE.md §21.
- **[Claude]** Generada desde una **instantánea** de Georef versionada en el repo, por ejemplo
  `backend/data/georef_gobiernos_locales_2026-10-28.json`. No se consulta Georef en vivo al migrar:
  el resultado tiene que ser reproducible y el mismo en local y prod.
- Orden de carga:
  1. **Provincias**: asignar `codigo_georef` casando por nombre normalizado (sin tildes ni mayúsculas).
     Son 24; se puede verificar a ojo.
  2. **Filas existentes de `partidos`**: casar por (provincia, nombre normalizado) y asignarles código,
     categoría y nombre completo. Las de Buenos Aires y la Ciudad casan todas o casi todas.
     - **[Claude]** Las que son el mismo lugar con otro nombre se casan con una **lista de alias a
       mano**, versionada junto a la instantánea (`id_partido` viejo → código de Georef). Así esa fila
       conserva su id y sus localidades.
     - Casos vistos en prod: «Mar del Plata (General Pueyrredón)» → General Pueyrredón, «Bariloche» →
       San Carlos de Bariloche, «Iguazú» → Puerto Iguazú.
     - El constructor arma la lista revisando la salida «sin casar» antes de aplicar.
     - Hoy no hay reclamos afectados: todas las localidades con reclamos están en Vicente López y San
       Isidro, que casan exacto.
  3. **Insertar el resto** de los gobiernos locales con UPSERT por `codigo_georef` (idempotente).
  4. **Colisión con UNIQUE `(id_provincia, nombre)`** (dos gobiernos locales con el mismo nombre en una
     provincia, o un departamento viejo con el mismo nombre que un municipio): el constructor la detecta
     antes de escribir y la resuelve.
     - **[Claude]** Para la fila nueva, usar `nombre_completo` como `nombre`.
  5. **Filas viejas sin casar** (departamentos y «Capital» genéricos): baja lógica, `activo = false`.
     Nunca DELETE, por las FK.
  6. **Sus localidades** se reubican en el gobierno local de la misma provincia cuyo nombre normalizado
     sea igual al de la localidad, solo si hay **exactamente una** coincidencia. Si no, quedan donde
     están. Lo que no se reubica se informa en la salida de la migración.
- **Backup en prod antes de los UPDATE** masivos (CLAUDE.md §24): `_backup_partidos_<fecha>` y
  `_backup_localidades_<fecha>`.
- **Seed local**: `seed_geo_argentina.py` queda como está para lo que ya carga. El catálogo completo
  llega por la migración, en local igual que en prod.

**Selector en el alta y la ficha**: el `<select>` de partido pasa a **autocompletar** (CLAUDE.md §23).
- `GET /api/v1/geo/partidos` suma `q` (ILIKE sobre nombre y nombre completo) y `limit`, y devuelve
  `codigo_georef` y `categoria`.
- Muestra «Nombre — Categoría».
- Las filas con `activo = false` no se ofrecen.

### 4.3 Depuración del contorno: un solo servicio en el backend

Una función, por ejemplo `services/geo_limite.py::normalizar_contorno(texto | dict)`. Devuelve el
contorno normalizado con un **resumen** (partes, vértices antes y después, superficie en km²,
recuadro, avisos), o un error con un mensaje para el usuario. **Todo** lo que guarda un contorno pasa
por ella: alta, ficha, Configuración y la vía IGN. El cliente nunca manda un contorno «ya depurado»
que se guarde sin repasar.

**Acepta:**
- `Polygon`, `MultiPolygon`, `Feature` y `FeatureCollection`, cuyas geometrías sean todas Polygon o
  MultiPolygon.
- Varias figuras se juntan en **un** MultiPolygon. **[Claude]** Se concatenan sus partes, sin unión
  geométrica.
- Coordenadas con tercera dimensión (`[lon, lat, z]`, que QGIS a veces exporta): se descarta la `z`.
- Anillos sin cerrar: se cierran.
- Puntos repetidos consecutivos: se quitan.
- Tamaño de entrada: **[Claude]** hasta 5 MB.

**Rechaza, con un mensaje que dice qué hacer:**
- JSON inválido: «El archivo no es GeoJSON válido».
- Otro tipo de figura (punto, línea): nombra el tipo encontrado y dice que hace falta un polígono
  cerrado.
- Coordenadas fuera de los rangos de latitud y longitud, típicamente en **metros** (Gauss-Krüger o
  POSGAR, con números del orden de 5.000.000): «El archivo está en metros, no en latitud/longitud.
  Exportalo de nuevo eligiendo EPSG:4326 — WGS 84», con enlace al paso del instructivo.
- Latitud y longitud invertidas: detectado porque cae fuera del país pero, invertido, cae adentro.
- Fuera del país del municipio: recuadro de `ENCUADRE_PAIS`.
- Anillo con menos de 4 puntos después de limpiar.
- Polígono que se corta a sí mismo, si la biblioteca lo detecta: se intenta reparar y, si no se
  puede, se rechaza.
- Más de **[Claude]** 200 KB después de simplificar: «demasiado detallado».

**Achica:**
- Simplificación de cada anillo con tolerancia de **[Claude]** unos 5 m, preservando la topología.
- Redondeo a **5 decimales** (alrededor de 1 m).
- **[Claude]** Biblioteca probada, no un algoritmo casero (memoria `feedback_no_encoder_casero`):
  `shapely`.
  - Da simplificación con topología, validez y reparación (`make_valid`).
  - El constructor verifica que instale en Railway (hay ruedas para Linux) antes de depender de ella.
  - Si no instala, implementación propia con tests contra los archivos de prueba.

**Avisa sin bloquear** (el usuario confirma):
- El contorno nuevo **no se cruza** con la zona de búsqueda que el municipio ya tenía: «¿Elegiste el
  municipio correcto?».
- Cuánto se simplificó: «2.679 → N vértices».

### 4.4 Contorno oficial (IGN)

- Endpoint `GET /api/v1/geo/contorno-oficial`, autenticado, para nivel 1 del municipio de la
  request o super administrador.
  - Toma el `id_partido` del **municipio** (no de un parámetro libre). En el alta, donde el municipio
    todavía no existe, el endpoint equivalente bajo `/super` recibe el `id_partido` elegido.
  - Lee su `codigo_georef`.
  - Pide al WFS del IGN `ign:municipio` con `in1 = código`, en EPSG:4326, con un timeout de
    **[Claude]** 20 s.
  - Pasa el resultado por `normalizar_contorno`.
  - Devuelve el contorno normalizado, el resumen y el **origen**: nombre del IGN (`fna`), fuente
    catastral (`fdc`) y código.
  - No guarda nada.
- Sin código, municipio ficticio, IGN caído o sin polígono: mensaje claro («El IGN no tiene el
  contorno de X. Podés subir un archivo: ver instructivo») y la pantalla ofrece la subida.
- Sin caché del lado de ZARIS: se pide pocas veces y lo que se guarda es la copia.
- **Alcance desde Railway (EE. UU.)**:
  - Verificado el 2026-10-28 que el IGN responde a pedidos desde fuera de Argentina: un pedido desde
    infraestructura en el exterior devolvió el contorno de Vicente López, 060861, completo.
  - Desde Railway mismo **no está verificado**. Es lo primero que hace la fase 3, con un pedido de
    prueba desde prod, antes de construir las pantallas.
  - **[Claude]** Si Railway no llega, el botón oficial queda deshabilitado con el aviso y la subida de
    archivo sigue siendo la vía. Se vuelve a evaluar con César: copia versionada de los polígonos o
    intermediario.

**Cambio de partido después de traer el contorno** **[Claude]**:
- Si el super cambia el partido en la ficha, o en el alta después de «Traer contorno oficial», y el
  contorno guardado vino del IGN con el código del partido **anterior**: el cambio pide
  confirmación y quita el contorno y su origen. No queda el contorno de otro municipio.
- Si el contorno vino de un **archivo**: se conserva, con un aviso para revisarlo (puede ser una
  corrección del nombre del partido, no otro territorio).
- La zona de búsqueda no se toca en ninguno de los dos casos.

### 4.5 Guardar y derivados

- Endpoints para previsualizar y guardar:
  - **Previsualizar** (sin efectos): recibe el archivo o el resultado del IGN y devuelve normalizado
    y resumen.
  - **Guardar**: vuelve a normalizar en el servidor y guarda.
  - Hay uno de cada en Configuración (`municipio_actual`, nivel 1) y en la ficha bajo `/super/...`.
    Este último registra el acceso del super en la misma transacción (`registrar_acceso_super_en`,
    CLAUDE.md §1).
- **Alta**: el campo `geo_limite_geojson` del alta pasa por `normalizar_contorno`. Inválido = 422 con
  el mensaje del validador.
- Se guarda con `guardar_config`, nunca con SQL a mano a `configuracion_general`:
  - `geo_limite_geojson`: el contorno normalizado (Polygon si es una sola parte, MultiPolygon si son
    varias);
  - **[Claude]** clave nueva `geo_limite_origen`: texto con la vía («IGN ign:municipio 060623 — ARBA»
    o «Archivo subido») y la fecha. Se muestra junto al contorno guardado.
- **Zona de búsqueda recalculada al guardar**:
  - centro = centro del recuadro del contorno;
  - radio = la mitad del lado mayor del recuadro, en grados, + **[Claude]** 0,1° de margen (unos
    11 km, para cubrir direcciones de los linderos), con tope de 5.
  - Reemplaza la zona anterior. El administrador puede ajustarla después en Configuración, que sigue
    editable.
  - Se invalida la caché de 5 minutos del bbox (`geo.py::_bbox_municipio`) si es simple de hacer. Si
    no, se avisa «toma efecto en unos 5 minutos», como hoy.
- **Quitar contorno**: permitido (los mapas vuelven a encuadrar por la zona o el país). No borra la zona.
- Toda escritura en local **y** prod, verificada con una consulta independiente (regla global de
  César).

### 4.6 Pantallas

Un componente compartido, por ejemplo `ContornoMunicipio`. Lo usan los módulos Municipios y Config:
se ubica en `web-app/src/ui/` o en `lib/`, a criterio del constructor.

Contenido del componente:
- **Contorno guardado**: mapa chico con el polígono (Leaflet vanilla y Esri gris claro, CLAUDE.md §4),
  origen y fecha. Botones «Reemplazar» y «Quitar».
- **Traer contorno oficial (IGN)**: deshabilitado, con explicación, si el municipio no tiene partido
  con código (los ficticios).
- **Subir archivo** (`.geojson`, `.json`) y el enlace **«¿Cómo armo el archivo?»**, que abre el
  instructivo (§4.7).
- **Previsualización** antes de guardar:
  - el polígono sobre el mapa, encuadrado;
  - la línea de resumen (partes, vértices antes → después, superficie, origen);
  - los avisos;
  - «Guardar contorno» y «Descartar».
- **Errores** del validador en lenguaje llano, con enlace al paso del instructivo que corresponde.

Dónde aparece:
- **Alta (asistente)**: reemplaza el textarea de GeoJSON del paso de ubicación.
  - Si ya se eligió el partido, ofrece primero «Traer contorno oficial».
  - Con contorno cargado, los tres campos de zona se muestran **derivados**, y el super puede tocarlos.
- **Ficha del municipio** (super): sección «Contorno del municipio».
- **Configuración → Sistema** (administrador): bloque «Contorno del municipio», arriba de «Búsqueda de
  direcciones». Ese bloque suma la nota «se recalcula al guardar el contorno».

### 4.7 Instructivo para el usuario

**[César]** Lo más explícito posible.

**Dónde vive.** **[Claude]** Es **ayuda dentro de la pantalla**: un panel o modal que abre «¿Cómo armo
el archivo?» desde los tres lugares. No es un `docs/manual_*` (§36 suspendido) ni un archivo aparte
que haya que encontrar.

**Contenido, en este orden:**
1. **Antes que nada**: si el botón «Traer contorno oficial» funcionó, no hace falta archivo. El
   archivo es para cuando el IGN no lo tiene, o el límite oficial no es el que corresponde (por ejemplo,
   un municipio con un ejido distinto al del catastro).
2. **Qué archivo sirve**, en una tabla de sí y no:
   - GeoJSON, un polígono cerrado, en latitud/longitud (EPSG:4326);
   - qué hace ZARIS solo (redondear, simplificar, juntar varias partes);
   - qué no acepta (metros, puntos, líneas, otro país).
3. **Camino A — sin instalar nada: geojson.io** (página web gratuita).
   - Paso a paso: abrir, buscar la ciudad, elegir la herramienta de polígono, marcar el contorno
     punto por punto, cerrar sobre el primer punto, revisar, guardar como GeoJSON y subirlo en ZARIS.
   - Con **capturas reales** de cada paso, tomadas en el navegador al construir. Se guardan como
     imágenes del módulo.
   - Consejos: hacer zoom para seguir calles y ríos; para islas, dibujar cada parte como otro polígono
     del mismo archivo.
4. **Camino B — con QGIS**, para quien tiene la capa del catastro.
   - Paso a paso: abrir la capa (shapefile, KML, GeoPackage, lo que tenga), seleccionar el polígono
     del municipio, clic derecho en la capa → «Exportar» → «Guardar objetos seleccionados como…»,
     formato «GeoJSON», SRC «EPSG:4326 — WGS 84», sin dimensión Z, guardar y subirlo.
   - **[Claude]** Sin capturas, porque QGIS no está en esta máquina. Los nombres de menús se
     **verifican contra la documentación oficial de QGIS** (versión LTR, interfaz en español) antes de
     publicarlos, no de memoria.
   - Si César manda capturas, se suman.
5. **Si da error**: cada mensaje del validador con su causa y su arreglo. Es la misma lista de §4.3,
   escrita para el usuario.
6. **[Claude]** Un **archivo de ejemplo** descargable: un polígono genérico, no de un municipio real,
   para comparar el formato.

### 4.8 Quienes leen el contorno: multipolígono en todos

- `leer_limite`: acepta Polygon y MultiPolygon. Lo que se lee pasa por la misma validación de
  estructura. Lo inválido sigue siendo fail-closed, pero ahora **queda registrado como warning con el
  municipio**.
- `encuadre_municipio`: recuadro de todas las partes.
- `punto_en_limite`: «adentro» si cae dentro de alguna parte (y fuera de sus huecos).
- `DashboardMap.tsx::mascaraExterior`: el mundo con **un hueco por parte**. Verificar en el navegador
  con un municipio de varias partes.
- `dashboard.py` y el generador demo: sin cambios de contrato, pero probados con un MultiPolygon.

### 4.9 GeoJSON de prueba para el municipio 6

- El municipio 6 de prod es **ficticio** (sin partido) y está en la zona de Pergamino. Por eso no
  puede usar «Traer contorno oficial»: sirve para probar **la vía archivo**.
- Archivo de prueba: el contorno de Pergamino bajado del IGN tal cual (MultiPolygon, 2.679 vértices,
  70 KB). Ejercita la depuración completa: tipo envoltorio, simplificación y tamaño.
- Se versiona como fixture del smoke (`backend/tests/fixtures/` o el lugar que use el constructor) y
  se le pasa a César para subirlo a mano en la prueba de cierre. Es dato público del IGN, sin nada
  sensible.
- Fixtures que siguen (archivos chicos, armados a mano):
  - **[Claude]** el mismo contorno exportado en metros (para el rechazo);
  - uno con lat/lon invertidas;
  - una línea en lugar de un polígono;
  - un FeatureCollection con dos partes.

## 5. Restricciones que aplican

- Migraciones: número asignado al **aplicar** (hoy la próxima libre es la 132).
  - Primero el DDL, después los datos en un archivo aparte.
  - Local y prod en la misma sesión. En prod por MCP (no hay DROP).
  - Verificar el drift de prod antes de escribir (CLAUDE.md §21 y §24).
- Toda tabla nueva lleva RLS y su clase en `municipio_tabla_clase`. Este diseño no crea tablas; si el
  constructor necesita una, aplica igual.
- Endpoints nuevos con su guard de nivel en el backend, no solo en la interfaz (memoria
  `feedback_guard_nivel_endpoint_no_solo_ui`).
- El super administrador se ve como nivel 1 ante los guards. Lo exclusivo del super usa
  `es_super_admin` (CLAUDE.md §3).
- Llamadas a un servicio externo (IGN) **desde el backend**, nunca desde el navegador del usuario: un
  único punto de timeout y mensajes.
- Verificación en la interfaz navegando con clics (CLAUDE.md §41) y verificación del deploy de Railway
  con un marcador en `/openapi.json` (CLAUDE.md §9).
- La palabra prohibida de las reglas globales no aparece en nada; se hace el grep antes de commitear.

## 6. Queda al constructor

- La forma exacta de las rutas, los nombres de funciones y la ubicación del componente compartido.
- La tolerancia exacta de simplificación (alrededor de 5 m) y el tope (alrededor de 200 KB), si al
  probar con contornos reales conviene ajustarlos. Lo que importa es que un partido grande de Buenos
  Aires quede bastante por debajo del tope y se vea igual al ojo.
- El orden de las fases. Sugerencia:
  1. catálogo y selector;
  2. depuración y lectores multipolígono;
  3. IGN, endpoints y pantallas;
  4. instructivo con capturas;
  5. prod y prueba con el municipio 6.

## 7. Cómo se sabe que está terminado

- En local y en prod, `partidos` tiene los 2.082 gobiernos locales con código. Las filas viejas sin
  casar quedan en baja lógica. Ningún reclamo pierde su localidad: el conteo de reclamos con localidad
  y partido resueltos es igual antes y después.
- En el alta, elegir «Pergamino» → «Traer contorno oficial» muestra el polígono y el resumen. Al
  guardar, el inicio del municipio lo muestra con la máscara, y la zona de búsqueda quedó recalculada.
- Subir el fixture de Pergamino en la ficha del municipio 6 de prod funciona. Subir los fixtures malos
  da cada mensaje esperado y no guarda nada.
- Un municipio de varias partes se ve bien en el mapa del inicio: dos huecos en la máscara y el
  encuadre de las dos.
- El instructivo abre desde los tres lugares, con las capturas de geojson.io. Los pasos de QGIS están
  verificados contra la documentación oficial.
