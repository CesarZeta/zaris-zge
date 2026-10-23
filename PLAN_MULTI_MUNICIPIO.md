# Plan — Multi-municipio y super administrador (IT-01)

> Estado: **diseño con decisiones de César del 2026-10-23, pendiente de su aprobación; sin código.** Revisado por un lector independiente (builder check) el mismo día. La implementación va en una sesión dedicada. Origen: ítem IT-01 de la reunión de Configuración/UX del 2026-07-06 (multi-tenant + super administrador + selector de municipio) y definición de César del 2026-10-20 (el super administrador crea los municipios, los parámetros globales y los administradores de cada municipio; el administrador queda como superusuario de SU municipio).

## Por qué

ZARIS hoy atiende a un solo municipio por instalación. Para sumar municipios sin duplicar infraestructura, César eligió que **todos compartan una base**, con cada dato marcado con su municipio, de modo que:

1. ningún municipio vea datos de otro;
2. el día de mañana un municipio pueda llevarse **sus** datos a una instancia propia (copiar sus filas), si así se requiere;
3. haya un **super administrador** que da de alta municipios, define los parámetros globales y crea al administrador de cada uno;
4. dar de alta un municipio sea una operación guiada, no una tarea artesanal.

## Decisiones de César (2026-10-23)

| Tema | Decisión |
|---|---|
| Separación de datos | **Una base para todos**, con `id_municipio` en cada dato (modelo de ZGC). Se acepta que una copia de la base contiene a todos los municipios; la segmentación es la que permite extraer uno a futuro. |
| Alcance del super administrador | **Ve siempre** los datos de cualquier municipio. |
| Vecinos | **Una cuenta por municipio.** El mismo DNI puede existir en dos municipios; ninguno ve lo que la persona dejó en el otro. |
| Funcionarios | **Una cuenta por municipio.** El único que cruza municipios es el super administrador. |
| Dirección de cada municipio | **Su nombre antepuesto a las direcciones actuales** (`<municipio>.zge.zaris.com.ar`, `<municipio>.vecinos.zaris.com.ar`); las direcciones sin prefijo quedan para el municipio demo (§6). |
| Municipio demo | **San Andrés es ficticio**: sus datos son generados, para pruebas y demostraciones. |
| Áreas fijas | **Las 6 áreas activas de San Andrés** (§5). |
| Vaciado de datos | **Solo el super administrador**, y **solo antes de producción** (municipio en puesta en marcha o demo). En producción quedan solo las bajas lógicas (§9). |
| Tope de usuarios | **Cuentas internas activas por municipio**, fijado por el super administrador; los vecinos no tienen tope (§5b). |
| Guía de alta | Sale del alta de un municipio de prueba y se guarda **fuera del repositorio** (`credenciales-testing/`), porque todo lo que se sube al repo queda publicado. |
| Dónde trabaja el super administrador | **En el mismo shell**: un nivel nuevo por encima del administrador, selector de municipio en la barra superior y módulo «Municipios». |
| Catálogos de un municipio nuevo | **Copia de un municipio modelo**; en el alta se elige qué copiar. |
| Hosting del shell | **Se muda de GitHub Pages** (admite un solo dominio propio por sitio) a un hosting que acepte varios dominios. |
| Corte en San Andrés | **Ventana corta de mantenimiento anunciada y un re-login de todos** (funcionarios y vecinos). Un solo corte con backup; no hace falta convivir con sesiones viejas. |
| Países | **También municipios fuera de Argentina.** El modelo de datos de localización (huso horario, país del documento, catálogos geográficos por país) entra en la misma migración de F1. El **módulo de documentos de identidad por país** es un tema reservado que requiere investigación aparte (§7). |
| Historia clínica | El super administrador la abre **solo declarando el motivo, y queda registrado**. El administrador de cada municipio puede ver el registro de todo lo que hizo el super administrador en su municipio. |
| Salida a un segundo municipio real | **Todo terminado, incluida la segunda barrera en la base (RLS)**, antes de cargar datos reales de otro municipio. |

Antes (2026-08-30 y 2026-10-20): **áreas fijas** por regla de negocio (Seguridad, Salud, Servicios Públicos…) precargadas en cada municipio, **renombrables pero no removibles**, porque los módulos dependen de ellas.

## Cómo está hoy (medido en prod el 2026-10-23)

- **Infraestructura de un solo municipio:** una API (Railway), una base (Supabase, plan gratis, 40 MB), el shell en GitHub Pages (`zge.zaris.com.ar`), la app del vecino y la de agentes en Vercel. La identidad (nombre, logo, color, contorno del mapa, bbox del geocoding) vive en `configuracion_general`, que **no tiene** `id_municipio`.
- **`id_municipio` existe en 81 de 96 tablas, pero no es confiable:**
  - vacío en `reclamos` (2.962), `ordenes_trabajo` (3.089), `emergencia_evento`, `emergencia_log`, `area`, `tipo_reclamo`, `cargos`, `activos`, `turno_llamado`, `ciudadano_aviso`, entre otras;
  - parcial en `ciudadanos` (350 vacíos de 956), `empresas` (501 de 561), `subarea` (73 de 82), `encuesta_envio` (4.644 de 4.648);
  - **8 usuarios con `id_municipio = 377`**, un municipio que no existe (los primeros usuarios del sistema);
  - completo y con clave foránea solo en Trámites y Agenda (~20 tablas);
  - **sin la columna:** `ciudadano_empresa`, `configuracion_general`, `emergencia_numerador`, `localidades`, `lugares_atencion`, `partidos`, `provincias`, `reclamo_historial`, `reclamos_area`, `reclamos_subarea`, `reclamos_tipo`, `servicios`, `tipos_activo`, `tipos_representacion`, `usuario_login_log`.
- **Backend:** 655 referencias a `id_municipio` en 59 archivos; **38 filtros toleran el municipio vacío** (`... OR id_municipio IS NULL`, regla «mono-municipio» de la skill `modulo-bi` y de Trámites); `encuestas_admin.py` fija `ID_MUNICIPIO_DEFAULT = 1`; el slug público (`?m=<codigo_corto>`) se valida contra el único municipio activo (`publico_alta.py`, `config_identidad.py`).
- **Únicos globales que pasan a ser por municipio:** `ciudadanos (doc_tipo, doc_nro)` y `cuil`, `empresas.cuit`, `reclamos.nro_reclamo`, `ordenes_trabajo.nro_ot`, `emergencia_evento.numero_operativo`, `usuarios.username`.
- **Nivel de acceso:** CHECK `nivel_acceso BETWEEN 1 AND 5`; el backend tiene 19 comparaciones `== 1` / `!= 1` y 5 `<= 1` / `< 2` que hay que revisar al sumar el nivel del super administrador.
- **Huso horario fijo:** `app/utils/fechas.py` usa `TZ_MUNICIPIO = UTC-3` a propósito (Argentina sin horario de verano).
- **Archivos:** buckets `reclamos-adjuntos`, `publico-reclamos-adjuntos`, `tramites-documentos`, `config-assets`, sin carpeta por municipio.
- **Procesos programados (GitHub Actions):** `encuestas-dispatcher`, `integridad-cuentas`, `tramites-mantenimiento`, `demo-datos` (más `deploy-web-app`), todos contra la única API.
- **Tabla `municipios`:** San Andrés (id 1, `codigo_corto` SAN) y una segunda fila (id 2, otro país, cargada el 2026-07-06, sin `codigo_corto` y sin datos colgando).

## Objetivos

1. **Aislamiento:** todo dato propio de un municipio lleva `id_municipio` NOT NULL con FK a `municipios`, y ninguna lectura ni escritura cruza municipios salvo la del super administrador.
2. **Extraíble:** copiar las filas de un municipio (más los catálogos globales) alcanza para levantarlo en una base propia. Por eso también las tablas hijas (historial, adjuntos, movimientos) llevan `id_municipio`, aunque su padre ya lo tenga.
3. **Super administrador** dentro del shell: alta y edición de municipios, parámetros globales, administradores de cada municipio, y acceso a cualquier municipio mediante el selector.
4. **Alta de municipio guiada** que deja un municipio usable: datos, subdominio, identidad, catálogos copiados del modelo, áreas fijas, primer administrador invitado y una prueba automática.
5. **Un subdominio por municipio** para el shell y para la app del vecino; el login sabe de qué municipio es la persona por la dirección.
6. San Andrés sigue funcionando sin interrupción durante toda la migración.

## No objetivos (por ahora)

- Una base o instancia por municipio (descartado por César; queda **posible** gracias al objetivo 2).
- Una identidad única de vecino o de funcionario para varios municipios.
- Tablero consolidado del super administrador (fase opcional al final).
- Facturación o planes comerciales por municipio (sí queda la habilitación de módulos por municipio).
- El módulo de documentos de identidad por país (tema reservado, §7): acá solo se deja el modelo de datos listo.

## Anti-objetivos (sería un fracaso aunque funcione)

- **Que un error de filtro muestre datos de otro municipio.** El aislamiento no puede depender de que cada endpoint «se acuerde»: tiene que haber un punto único que fije el municipio de la request, y un smoke de aislamiento que lo pruebe en todos los routers.
- Que San Andrés quede caído o con datos mezclados durante la transición.
- Que el super administrador pueda operar un municipio sin que quede registrado.
- Que dar de alta un municipio exija tocar código o correr SQL a mano.

## Diseño

### 1. Clasificación de tablas

Toda tabla cae en una de tres clases (el builder completa la lista con el inventario de las 96 tablas y la deja en la migración como comentario):

- **Global (sin `id_municipio`):** catálogos geográficos y normativos comunes — `provincias`, `partidos`, `localidades`, `nacionalidades`, `actividades` (CLAE), `tipo_representacion`/`tipos_representacion`, `tipos_activo` — y los catálogos de estados del sistema que gobiernan las máquinas de estados (`estado_reclamo`, `estado_ot`, `estado_evento`, `estado_reserva`, `emergencia_estado`), `tipo_usuario` y el catálogo `modulos`. También `municipios`.
- **Por municipio, configurable (catálogo del municipio):** `area`, `subarea`, `cargos`, `tipo_reclamo`, `tipo_prestacion`, `tipo_tramite*`, `emergencia_tipo`/`_subtipo`/`_organismo_derivacion`/`_canal_ingreso`/`_prioridad`, `servicios`, `lugares_atencion`, `espacios_agenda`, `agenda_clase`, `agenda_feriado`, `encuesta_plantilla`/`_pregunta`/`_opcion`, `configuracion_general`. Son lo que se copia del municipio modelo.
- **Por municipio, operativo:** todo lo demás (personas, cuentas, reclamos, OT, turnos, trámites, emergencias, encuestas enviadas, notificaciones, logs).

Casos mixtos (criterio a aplicar):
- **`configuracion_general`:** clave única por `(id_municipio, clave)`; las filas con `id_municipio NULL` son los **parámetros globales** del super administrador y actúan de valor por defecto; un municipio sobrescribe con su propia fila. El lector existente pasa a buscar «la del municipio, si no la global».
- **Feriados:** los nacionales pueden ser globales (`id_municipio NULL`) y los locales del municipio — el builder decide si `agenda_feriado` admite NULL o si los nacionales se copian en cada alta.
- **`modulos`:** el catálogo es global; la **habilitación por municipio** va en una tabla nueva (`municipio_modulo`), que acota qué módulos existen para ese municipio por encima de los permisos por usuario (§30). Precedente: `tenants.plan` de ZGC.

### 2. Segmentación de la base (migración)

- `id_municipio INTEGER NOT NULL REFERENCES municipios(id_municipio)` en toda tabla por municipio. **Backfill: todo lo existente es de San Andrés (1)**, incluidos los 8 usuarios con 377. Backup previo (`_backup_*`, §24).
- Agregar la columna a las tablas por municipio que no la tienen (`reclamo_historial`, `usuario_login_log`, `ciudadano_empresa`, `lugares_atencion`, `servicios`, `emergencia_numerador`, `reclamos_area`/`_subarea`/`_tipo` si siguen en uso — verificar antes si son legacy para dropear).
- **Únicos compuestos:** `(id_municipio, doc_tipo, doc_nro)`, `(id_municipio, cuil)`, `(id_municipio, cuit)`, `(id_municipio, username)`, y los números de reclamo, OT y emergencia.
- **Numeración por municipio** con el código corto del municipio en el número, como ya hacen los trámites (`POD-SAN-2026-0001`): `REC-SAN-2026-000001`, `OT-SAN-…`, emergencias igual. Los números existentes **no se renumeran** (están en mails, QR y avisos ya enviados); los nuevos salen con el código. *Criterio de Claude.*
- Índices `(id_municipio, …)` en las consultas calientes (listados, bandejas, BI). Ojo con la trampa de ZGC: un índice compuesto `(tenant_id, fk)` no le sirve a una FK sola.
- Toda tabla nueva del proyecto nace con `id_municipio NOT NULL` (sumar a la regla §10 de `CLAUDE.md`).

### 3. Municipio de cada request (punto único)

- **Funcionarios:** el JWT lleva `id_municipio` (claim nuevo), tomado de su cuenta al loguear. Un dependency único (`municipio_actual`) lo entrega a todos los routers; ningún router lo lee de query params ni del body.
- **Super administrador:** su cuenta no tiene municipio; el **selector de municipio** de la barra superior fija el municipio activo, que viaja en un header (`X-Municipio`) validado por el mismo dependency **solo** para el nivel de super administrador. Cada cambio de municipio y cada request suyo sobre datos de un municipio queda en un registro de accesos (tabla nueva, append-only).
- **Vecinos y páginas públicas:** el municipio sale del subdominio (`Host`/`Origin`) o del slug, resuelto contra `municipios` (nueva columna `subdominio`). El JWT del vecino lleva su `id_municipio` y el guard rechaza un token de un municipio usado desde el subdominio de otro.
- **Login:** el `identificador` (email o DNI) se busca **dentro del municipio del subdominio**. Hoy el DNI y el email son únicos globales; con una cuenta por municipio dejan de serlo. **El super administrador entra desde cualquier subdominio:** el login busca primero entre las cuentas del municipio y, si no hay, entre las cuentas globales de nivel 0; los identificadores de las cuentas de nivel 0 quedan reservados (ninguna cuenta de un municipio puede usarlos). *Criterio de Claude.* Esto se resuelve en F2, no en F5.
- **Filtrado:** todas las consultas filtran por el municipio actual. Se eliminan las 38 tolerancias `IS NULL` y el `ID_MUNICIPIO_DEFAULT = 1`.
- **Segunda barrera (F6, requisito de salida):** RLS de Postgres con `SET LOCAL app.id_municipio` por transacción. Hoy no actuaría: el backend se conecta como `postgres`, dueño de las tablas, y el dueño saltea RLS. Exige un rol de conexión sin `BYPASSRLS` y sin ser dueño. Va después de que el filtrado de la aplicación esté completo y probado, pero **antes** de cargar datos reales de un segundo municipio (decisión de César).
- **Corte:** las sesiones emitidas antes de la migración no traen el municipio y se rechazan (401): todos vuelven a iniciar sesión una vez. Se anuncia la ventana a los usuarios de San Andrés.

### 4. Super administrador

- **Nivel 0** en `usuarios.nivel_acceso` (ampliar el CHECK a 0-5), con `id_municipio` NULL. Revisar las 24 comparaciones de nivel del backend (19 `== 1`/`!= 1`, 5 `<= 1`/`< 2`) y los guards del frontend: el nivel 0 tiene todo lo del 1, más lo propio.
- **Shell:** selector de municipio en la barra superior (solo nivel 0), siempre visible con el municipio activo para que no haya duda de dónde está operando; módulo **«Municipios»** (alta, edición, baja lógica, subdominio, identidad, módulos habilitados, administradores). Los **parámetros globales** se editan desde Configuración → Sistema con el selector en «Global».
- **Qué conserva el administrador de cada municipio (nivel 1)** — *criterio de Claude:* edita la identidad y Configuración → Sistema **de su municipio**, y el nivel mínimo de cada módulo **para su municipio** (pasa de `modulos`, global, a `municipio_modulo`). Son solo del super administrador: habilitar o quitar módulos a un municipio, crear o dar de baja administradores, y los parámetros de seguridad de las cuentas (vigencia y renovación de claves, bloqueo por intentos), que son globales y ningún municipio sobrescribe.
- **Historia clínica:** el nivel 0 no hereda el acceso del nivel 1 a la historia clínica. Para abrir una, declara el motivo (texto obligatorio) y queda en `historia_clinica_acceso` además del registro general de accesos. El administrador del municipio ve, en una pantalla de solo lectura, el registro de todo lo que hizo el super administrador en su municipio.
- El alta de super administradores la hace otro super administrador (el primero, por migración/seed). Segundo factor recomendado para el nivel 0 (el builder evalúa el esfuerzo; si es grande, fase aparte).

### 5. Alta de un municipio

Desde el módulo «Municipios», en un solo flujo:

1. **Datos:** nombre, país, provincia, zona horaria, código corto (prefijo de numeración), subdominio.
2. **Identidad:** logo, color, contorno del mapa (GeoJSON) y bbox del geocoding (§23) — con valores por defecto si no se cargan.
3. **Qué copiar del municipio modelo:** casillas por catálogo (áreas y subáreas, cargos, tipos de reclamo, prestaciones, circuitos de trámites, tipos de emergencia, plantillas de encuesta, configuración). Las áreas fijas se crean siempre.
4. **Módulos habilitados.**
5. **Primer administrador:** nombre, DNI, email → se crea su ficha en la BUC del municipio, su usuario nivel 1 y se le manda **invitación por mail** para elegir la clave (el super administrador nunca la conoce). Mismo patrón de link que el alta del vecino (§23, flujos públicos por mail).
6. **Prueba automática de puesta en marcha:** identidad pública del subdominio, login del administrador por API, mail de invitación generado (link verificado con GET, §5).

Todo en una transacción para la parte de base; lo externo (DNS, dominio en el hosting) como pasos posteriores con estado visible en la ficha del municipio («DNS pendiente», «dominio verificado»). Primera versión aceptable: los pasos externos manuales y documentados; automatizables después con un token de Cloudflare (`Zone:DNS:Edit`) y uno del hosting, guardados fuera del repo.

- **Áreas fijas (decisión de César: las que tiene San Andrés):** las 6 áreas **activas** de San Andrés al 2026-10-23 — Secretaría de Gobierno, Secretaría de Planeamiento y Obras Públicas, Secretaría de Salud, Secretaría de Seguridad, Secretaría de Servicios Públicos y Subsecretaría de Tránsito. Las 51 áreas inactivas (duplicados y legado) no pasan al modelo. Se crean con una marca de sistema (como `tipo_tramite.es_sistema`): se pueden renombrar, no dar de baja. Las claves de `configuracion_general` que hoy apuntan a ellas por id (`id_area_salud`, `id_espacio_guardia`) se siembran en el alta, siguiendo la regla §21 (sembradas por nombre, leídas por id).
- **Municipio modelo:** un municipio marcado como modelo, con catálogos curados y **sin datos personales**, del que se copia. No es San Andrés (que tiene datos demo y usuarios); el builder lo arma a partir de los catálogos de San Andrés.
- **Estado del municipio** (`municipios.estado`): `puesta_en_marcha` (recién dado de alta, cargando datos), `produccion`, `demo` (San Andrés) y `baja`. Lo cambia el super administrador. El paso a `produccion` es explícito y no tiene vuelta atrás desde la interfaz: es el que apaga el vaciado de datos (§9).
- **Municipio de prueba y guía privada:** la prueba de cierre de F4 es dar de alta un municipio de prueba de punta a punta. De esa corrida sale la **guía de alta de municipio** para César (qué datos pedirle al cliente, pasos, DNS, primer administrador, perfiles mínimos, carga inicial). Va a `C:\Users\Cesar\Documents\ZARIS\credenciales-testing\`, nunca al repositorio. El municipio de prueba queda en estado `demo` o `baja` al terminar.
- **Fila id 2 de `municipios`** («MUNICIPIO OSPINO»): una prueba cargada desde Maestros → Municipios el 2026-07-06, sin datos colgando y desconocida para César. La migración de F1 la da de baja lógica (`activo = false`). *Criterio de Claude.*

### 5b. Usuarios de cada municipio

- **Quién crea qué:** el super administrador crea el primer administrador (invitación por mail, §5). El administrador del municipio crea el resto de las cuentas con las pantallas de hoy (Usuarios, ficha del ciudadano con «cuenta ZARIS», §23).
- **Perfiles mínimos para operar** (propuesta; se ajusta con la guía de arranque de §10): un administrador (nivel 1); por cada gestión que recibe reclamos, un supervisor (nivel 2) y al menos un agente de Gestión (nivel 4), porque la asignación automática reparte entre los agentes de nivel Gestión; Atención (nivel 3) para ventanilla o call center; Consultor (nivel 5) opcional. Salud, Guardia y Emergencias necesitan agentes en sus gestiones.
- **Tope:** `municipios.max_usuarios_activos` (NULL = sin tope), lo fija el super administrador. Cuenta las cuentas internas activas del municipio (no las del super administrador ni los vecinos). Al llegar al tope no se puede crear ni reactivar una cuenta (409 con mensaje claro); el módulo Usuarios muestra «N de M cuentas» y avisa desde el 90 %. *El comportamiento al llegar al tope es criterio de Claude.*

### 6. Frontends por subdominio

**Esquema de direcciones (decisión de César):** cada municipio antepone su nombre a las direcciones actuales, y las direcciones sin prefijo quedan para el municipio demo.

| | Municipio demo (San Andrés, ficticio) | Cada municipio nuevo |
|---|---|---|
| Backoffice (shell) | `zge.zaris.com.ar` | `<municipio>.zge.zaris.com.ar` |
| App del vecino | `vecinos.zaris.com.ar` | `<municipio>.vecinos.zaris.com.ar` |
| App de agentes | `agentes.zaris.com.ar` | `<municipio>.agentes.zaris.com.ar` |

- `<municipio>` es el subdominio del municipio (`municipios.subdominio`): minúsculas, sin tildes ni espacios, con guiones (p. ej. `vicente-lopez`). Se valida en el alta.
- **San Andrés es el municipio demo:** ficticio, con datos generados, para pruebas y demostraciones. Las instalaciones, suscripciones push y links ya enviados siguen funcionando porque sus direcciones no cambian. El generador demo corre solo para municipios marcados como demo.
- **Certificados:** con el DNS en Cloudflare, Vercel **no** puede servir un comodín (`*.zge.zaris.com.ar` exige sus nameservers), así que cada alta crea 3 registros CNAME (DNS only) y agrega los 3 dominios al hosting; el certificado de cada uno lo emite el hosting solo. Dos niveles de subdominio no son problema para el certificado.
- **Shell:** se muda a un hosting con varios dominios por proyecto (Vercel, donde ya están las apps del vecino y de agentes, o Cloudflare Pages). Un solo build; el municipio sale del hostname (`GET /publico/municipio` resuelve subdominio → identidad). El workflow `deploy-web-app.yml` cambia de destino.
- **Apps del vecino y de agentes:** mismo build para todos los municipios; el municipio sale del hostname igual que en el shell.
- **CORS:** `allow_origins` es una lista exacta; con un subdominio por municipio pasar a `allow_origin_regex` acotado a `https://([a-z0-9-]+\.)*zaris\.com\.ar` (verificar soporte en la versión de Starlette en uso).
- **Mails:** los links usan el subdominio del municipio destinatario, no una URL fija de settings (`app/core/urls.py` pasa a recibir el municipio).
- **Páginas públicas vanilla** (`alta-vecino.html`, `encuesta.html`): toman el municipio del subdominio.

### 7. Localización por país (municipios fuera de Argentina)

Hoy el sistema supone Argentina en tres lugares (medido el 2026-10-23):

- **Huso horario:** `app/utils/fechas.py` fija `TZ_MUNICIPIO = UTC-3` (26 usos de `TZ_MUNICIPIO`/`hoy_local`/`ahora_local`) y hay 13 conversiones `AT TIME ZONE 'UTC'` en 7 archivos. «Hoy», «este mes», los vencimientos de SLA, los turnos del día, los agrupamientos del BI y los plazos de los procesos programados dependen de él.
- **Documentos:** validadores de CUIL/CUIT con dígito verificador en 7 archivos (`schemas/buc.py`, `schemas/publico_alta.py`, `publico_alta.py`, `publico_auth.py`, `publico_perfil.py`, generadores demo); el login interpreta «solo dígitos, 7 u 8» como DNI (§1).
- **Geografía:** `provincias`/`partidos`/`localidades` son el árbol argentino (`seed_geo_argentina.py`); el geocoding ya es configurable por bbox (§23).

Diseño:

- **En la migración de F1 (modelo de datos):** `municipios.zona_horaria` (nombre IANA, p. ej. `America/Argentina/Buenos_Aires`, `America/Caracas`) y `municipios.pais` normalizado a código ISO; los catálogos geográficos ganan el país (`provincias.pais` o equivalente) y siguen siendo globales; personas y empresas guardan su documento como **(país, tipo de documento, número)**, con el tipo referido a un catálogo por país, de modo que el módulo de documentos (abajo) se enchufe después sin migrar datos de nuevo. Argentina queda cargada con DNI, CUIL y CUIT y sus validaciones de hoy.
- **Código (fase F5b, requisito antes del primer municipio de otro país, no de uno argentino):** `hoy_local`/`ahora_local` reciben el municipio y usan `ZoneInfo` (otros países pueden tener horario de verano); los procesos programados calculan fechas con la zona de cada municipio; los textos de la interfaz que dicen «DNI» pasan a «documento» o a la etiqueta del tipo; el geocoding suma el código de país (`countrycodes` de Nominatim) además del bbox.
- San Andrés y cualquier municipio argentino funcionan igual que hoy aunque F5b no esté hecha.

**Documentos de identidad por país — tema reservado (decisión de César, 2026-10-23).** Los conceptos de DNI, CUIL y CUIT y sus estructuras valen para Argentina; cada país tiene los suyos para personas y para empresas, con sus formatos, sus reglas de validación y **sus propias leyes de identificación y de datos personales**. Hace falta un **módulo que parametrice por país** los tipos de documento (de persona y de empresa), su formato, su validación, su máscara de carga y su etiqueta. Requiere una investigación aparte y **no se diseña en este plan**: este plan solo deja el modelo de datos preparado (país + tipo + número). Lo trae César cuando decida tratarlo; un municipio de otro país no sale a producción sin ese módulo.

### 8. Operación

- **Archivos:** los paths nuevos llevan prefijo `m{id_municipio}/…` en cada bucket; los existentes quedan como están (son de San Andrés).
- **Procesos programados:** como la API es una, cada proceso recorre los municipios activos; los logs reportan por municipio. El generador demo corre solo para municipios marcados como demo.
- **Exportación por municipio:** script que vuelca las filas de un municipio (más los catálogos globales) — es la prueba concreta del objetivo 2 y el respaldo que se le puede entregar a un municipio.
- **BI:** todo filtrado por el municipio actual; el super administrador ve el municipio elegido.

### 9. Vaciado de datos de un municipio (decisión de César, 2026-10-23)

Para dejar un municipio limpio antes de salir a producción (borrar lo que se cargó de prueba) o para regenerar el demo.

- **Quién:** solo el super administrador, a pedido del municipio.
- **Cuándo:** solo con el municipio en `puesta_en_marcha` o `demo`. En `produccion` la opción no existe y rige la baja lógica de siempre. Es la única excepción a «nunca DELETE físico» (§5 de `CLAUDE.md`), justificada porque no hay datos de producción.
- **Qué:** todo, o por grupos. Grupos propuestos: *operativo* (reclamos, OT, turnos, trámites, emergencias, encuestas enviadas, notificaciones, registros), *contactos* (ciudadanos, empresas y sus cuentas de la app del vecino), *maestros del municipio* (catálogos copiados del modelo, salvo las áreas fijas) y *usuarios* (salvo el administrador principal). Borrar un grupo arrastra lo operativo que depende de él (no se pueden borrar los ciudadanos y dejar sus reclamos); la pantalla muestra antes cuántas filas de qué tablas se van a borrar.
- **Nunca:** catálogos globales, áreas fijas, `municipios`, el registro de accesos del super administrador.
- **Resguardo:** antes de vaciar se genera la exportación del municipio (§8) y se guarda; confirmación escribiendo el nombre del municipio; queda en el registro del super administrador. También se borran los archivos del municipio en los buckets (prefijo `m{id}/`). *Exportación previa automática: criterio de Claude.*
- **Arrancar vacío:** después de vaciar, el municipio tiene que poder operar cargando datos desde cero. La guía de arranque (§10) dice qué cargar primero, y la prueba de F4 incluye recorrer cada módulo con las tablas vacías para que ninguno se rompa (pantallas con estado vacío, sin errores 500).

### 10. Guía de arranque: qué cargar primero

Documento para el administrador de un municipio nuevo (y para la guía privada de César): por cada circuito (cuentas, contactos, reclamos y OT, turnos, agenda y entradas, trámites, emergencias, encuestas, app del vecino, inicio y BI), qué tablas hay que cargar antes del primer registro, en qué orden y desde qué pantalla; y el orden global de carga. El relevamiento contra la base y el código se hizo el 2026-10-23 (ver «Anexos»). Los riesgos de pantallas que se rompen con tablas vacías que salgan de ese relevamiento se corrigen en F4.

Lo que el relevamiento cambia en este plan:

- **F2 tiene su inventario:** todo el código supone el municipio 1 — defaults `id_municipio = 1` en los schemas (`schemas/buc.py`, `turnos.py`, `tramites.py`, `agenda_v2.py`), `current_user.get("id_municipio") or 1` (`get_current_user` hoy no devuelve el municipio) y filtros estrictos `= 1` (`turnos.py`, `turnos_publico.py`, `tramites.py`, `agenda_espacios.py`, `agenda_disponibilidad.py`). Más los `DEFAULT 1` de la base. Todo eso se reemplaza por el municipio de la request.
- **F4 incorpora el primer administrador:** hoy no se puede crear desde ninguna pantalla (el alta exige ser admin y ningún script crea un nivel 1). El alta del municipio lo crea **con su agente y una subárea**: sin subárea, crear un trámite da 500 (`creacion.py`, CHECK `ck_tramite_destinatario`).
- **El alta siembra todas las claves de configuración** desde los parámetros globales: hoy Config → Identidad solo hace UPDATE (si la clave no existe responde 200 sin guardar) y Config → Sistema esconde las claves inexistentes. Con la configuración por municipio, el guardado pasa a ser «insertar o actualizar».
- **Correcciones de F4 (pantallas con tablas vacías):** asignación automática que inserta la OT con estado NULL si falta «Asignada» y pierde el error (`autoasignacion.py`); resolver un reclamo sin el estado «Terminada» da 500 (`reclamos.py`); nacionalidad e id de tipo de representación fijos en 1 (`emergencias.py`, `services/agenda.py`, `schemas/buc.py`, `publico_alta.py`); Turnos traduce cualquier error de integridad a «el horario acaba de ser tomado» (`turnos.py`); la clave de Guardia se convierte a número sin validar (`guardia.py`); el geocoding y los mapas caen a las coordenadas de Vicente López sin avisar si faltan las claves `geo_bbox_*`. Detalle con archivo:línea en el anexo.
- **Hallazgos sueltos:** la clave `ot_pendiente_dias_vencimiento` aparece en Config → Sistema pero ningún código del backend la usa (verificado con grep); la base local no tiene `municipios.pais` (prod sí).

## Fases propuestas

| Fase | Contenido | Prueba de cierre |
|---|---|---|
| **F1 — Segmentación** | Clasificación de tablas; migración `id_municipio` NOT NULL + FK + backfill + únicos compuestos + numeración con código; `configuracion_general` por municipio con globales; modelo de localización (zona horaria, país, tipos de documento por país). Un solo corte en ventana anunciada, junto con F2. | San Andrés idéntico en prod (smokes existentes en verde); conteos por tabla antes/después. |
| **F2 — Municipio de la request** | Claim en el JWT, dependency único, filtrado en todos los routers, fin de las tolerancias `IS NULL`, login dentro del municipio. Segundo municipio de prueba en local. | **Smoke de aislamiento**: con dos municipios cargados, ningún endpoint (agente, vecino, público) devuelve ni modifica datos del otro. |
| **F3 — Super administrador** | Nivel 0, selector de municipio, registro de accesos, parámetros globales, módulo «Municipios» (edición). | Recorrido en navegador: cambiar de municipio y ver los datos correctos; registro de accesos poblado. |
| **F4 — Alta de municipio** | Municipio modelo, áreas fijas con marca de sistema, estado del municipio, flujo de alta completo, invitación al primer administrador, prueba automática, tope de usuarios, vaciado de datos (§9), correcciones de pantallas con tablas vacías. | Alta de un municipio de prueba de punta a punta; su administrador entra, carga lo de la guía de arranque y genera un registro en cada circuito; vaciado y re-carga. **Entregable: guía privada de alta** en `credenciales-testing/`. |
| **F5 — Subdominios** | Mudanza del shell, resolución por hostname en shell y app del vecino, CORS, links de mails, páginas públicas. | Dos subdominios en prod mostrando cada uno su municipio; alta de vecino en cada uno con el mismo DNI. |
| **F5b — Localización** | Zona horaria por municipio en el código, validadores por país, etiquetas de documento, geocoding por país (§7). Requisito solo para un municipio de otro país. | Un municipio de prueba en otra zona horaria: «hoy», turnos del día, SLA y BI cortan en su medianoche local. |
| **F6 — Segunda barrera y operación** | RLS con rol de conexión no dueño; procesos programados por municipio; exportación por municipio; paths con prefijo. | Smoke de aislamiento repetido con el filtrado de la aplicación desactivado en un endpoint de prueba: RLS igual lo frena. Exportación de San Andrés restaurada en una base vacía. |
| F7 (opcional) | Tablero consolidado del super administrador. | — |

**Salida (decisión de César):** ningún segundo municipio carga datos reales hasta que F1-F6 estén terminadas (F5b solo si es de otro país). F1 y F2 son las de más riesgo (tocan todo el backend) y van juntas en la sesión dedicada, en un solo corte; F3 y F4 en la siguiente.

## Preguntas abiertas para César

Ninguna pendiente. Resueltas el 2026-10-23: áreas fijas = las 6 activas de San Andrés (§5); direcciones = prefijo por municipio y las actuales para el demo (§6); documentos por país = tema reservado con investigación en curso (§7); fila id 2 = prueba, se da de baja (§5); vaciado, tope de usuarios y guía privada (§5, §5b, §9).

## Lo que queda a criterio del builder

- Nombre y forma exacta del dependency, del claim y del header del super administrador.
- La clasificación fina de cada tabla (con el criterio de §1) y si las tablas `reclamos_area`/`_subarea`/`_tipo` son legacy para dropear.
- Hosting del shell (Vercel o Cloudflare Pages) con una comparación corta de costo y condiciones de uso comercial.
- Patrón exacto del subdominio de la app del vecino.
- Cómo se implementa el segundo factor del nivel 0, o si va en fase aparte.
- Orden interno de las migraciones dentro de F1 (siempre con backup previo y en local antes que en prod, §24).

## Anexos

- **A. Guía de arranque con tablas vacías** — [`docs/guia_arranque_tablas.md`](docs/guia_arranque_tablas.md): por circuito, qué cargar primero, por qué (FK, validación en código, clave de configuración) y desde qué pantalla; orden global de carga; catálogos que no se vacían nunca; riesgos con tablas vacías con archivo:línea; claves de `configuracion_general` y qué pasa si faltan; dependencias por FK. Relevada el 2026-10-23 sobre la base local y el código (solo lectura); la nacionalidad id 1 se verificó además en prod.
- **B. Documentos de identidad de Hispanoamérica** — investigación en curso (2026-10-23), base del módulo de documentos por país (§7).
