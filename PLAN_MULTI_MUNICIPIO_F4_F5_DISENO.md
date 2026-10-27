# IT-01 F4+F5 — Alta de municipios y subdominios por municipio (diseño)

> **Borrador para aprobación de César (2026-10-27), con las respuestas al builder check incorporadas.** Base: [`PLAN_MULTI_MUNICIPIO.md`](PLAN_MULTI_MUNICIPIO.md) §5, §5b, §6, §8, §9 y §10, cuyas decisiones (todas de César, 2026-10-23) siguen valiendo y no se repiten acá salvo donde este documento las precisa. F1+F2 en prod desde el 2026-10-25; F3, F3b y el lote de limpieza desde el 2026-10-26. Relevamiento del código del 2026-10-27 (commits ZGE `7272595`, zaris-vecinos `afa1182`, zaris-agentes `8d0c5f2`).
>
> Marcas: **[César]** = decisión de César; **[Claude]** = criterio mío, revisable; **[builder]** = queda a quien implemente.

## 1. Por qué

- **Hoy no se puede dar de alta un municipio.** No hay pantalla ni endpoint para crearlo, ni para crear su primer administrador (ningún nivel 1 se crea desde la interfaz).
- **Aunque existiera, su gente no podría entrar.** El login busca la cuenta en el municipio del header `Origin` (`core/municipio.py`), y el shell vive en GitHub Pages, que sirve un solo dominio (`zge.zaris.com.ar` = el municipio demo). Lo mismo pasa con las apps del vecino y de agentes en Vercel. Por eso F4 y F5 van juntas: la prueba de cierre es en **prod**, con el administrador de un municipio nuevo entrando por su subdominio **[César, 2026-10-27]**.
- **El hosting actual no sirve para lo comercial.** Vercel Hobby es «non-commercial, personal use only» (docs oficiales, 2026-10-27). Hoy es desarrollo y no hay uso comercial; empieza con el primer municipio implementado **[César]**. Los tres frontends se mudan a **Cloudflare Pages** (costo cero, el DNS ya está ahí, 100 dominios por proyecto en el plan gratis) **[César, 2026-10-27]**.

## 2. Objetivos, no objetivos y anti-objetivos

**Objetivos**
1. El super administrador da de alta un municipio completo desde «Municipios», en un solo flujo, y el municipio queda operable sin tocar la base a mano.
2. El administrador de ese municipio recibe una invitación por mail, elige su clave, vincula su segundo factor y entra por `<sub>.zge.zaris.com.ar`.
3. Los vecinos del municipio nuevo usan `<sub>.vecinos.zaris.com.ar` y los agentes `<sub>.agentes.zaris.com.ar`, con la identidad de su municipio. Todo link que les llega por mail los lleva a SU subdominio.
4. Cada municipio tiene solo los módulos que el super le habilitó, y eso se respeta en el backend (no solo en el menú).
5. El super puede vaciar los datos de un municipio que todavía no está en producción, con resguardo previo.
6. San Andrés sigue funcionando igual, en las mismas direcciones, durante y después de la mudanza.

**No objetivos (F4+F5)**
- RLS como segunda barrera, procesos programados con logs por municipio y prefijo `m{id}/` en los buckets: siguen en **F6**. La exportación por municipio entra acá solo como resguardo previo al vaciado (§4.8).
- Localización por país (F5b) y el módulo de documentos por país (tema reservado de César).
- Tablero consolidado del super (F7).
- Manifest de las PWAs por municipio (nombre e ícono al instalar): la app instalada se sigue llamando «Portal del Ciudadano» / la de agentes con su nombre actual; la identidad del municipio se ve adentro. **[Claude]**
- El bloque del vecino (web = app, iniciar trámites, Vecino 360) y la base de conocimiento: van después **[César, 2026-10-27]**.
- Mover el backend de Railway.

**Anti-objetivos (cosas que harían fracasar la fase aunque «funcione»)**
- Que un usuario o vecino de un municipio vea, reciba por mail o pueda tocar algo de otro.
- Un link de mail que lleve al subdominio equivocado (el login falla porque el `Origin` no coincide con el municipio del token).
- Que San Andrés pierda servicio durante la mudanza más allá de minutos, o que se rompan las suscripciones push, las apps instaladas o los links ya enviados.
- Que el vaciado pueda correr sobre un municipio en producción, o borre algo global o de otro municipio.
- Que el super administrador conozca la clave del primer administrador.
- Credenciales de Cloudflare dentro del repositorio o en un artefacto publicado.
- Un módulo deshabilitado que siga respondiendo por la API.

## 3. Decisiones de César

Del 2026-10-23 (en `PLAN_MULTI_MUNICIPIO.md`): municipio modelo sin datos personales del que se copia, con casillas por catálogo · 6 áreas fijas (las activas de San Andrés), renombrables y no removibles · estados `puesta_en_marcha`, `produccion`, `demo`, `baja`; el paso a producción no tiene vuelta atrás desde la interfaz y apaga el vaciado · primer administrador por invitación de mail · tope de cuentas internas activas por municipio · vaciado solo por el super, solo en `puesta_en_marcha` o `demo`, por grupos, con exportación previa · direcciones `<municipio>.zge|vecinos|agentes.zaris.com.ar`, las sin prefijo para el municipio demo · municipio de prueba dado de alta de punta a punta y guía privada de alta en `credenciales-testing/`.

Del 2026-10-27: **F4 y F5 juntas**, prueba de cierre en prod · **los tres frontends a Cloudflare Pages** · **exportaciones previas al vaciado: 90 días con borrado automático; las descarga solo el super, y el administrador del municipio pide la suya a través de él** · **municipios de otros países: está planeado como próxima etapa; esta fase deja los datos segmentados por país, provincia (o su equivalente) y municipio, con agrupamientos por país y provincia** (§4.1b).

## 4. Diseño

### 4.1 Estado del municipio y municipio modelo

- `municipios.estado` NOT NULL con CHECK: `puesta_en_marcha`, `produccion`, `demo`, `baja` y **`modelo`** **[Claude]**: el modelo es un municipio más, con estado propio en lugar de una marca aparte. Un solo municipio en `modelo` (índice único parcial).
- Valores al migrar: San Andrés → `demo`; «MUNICIPIO OSPINO» (id 2, ya inactivo) → `baja`.
- `activo` se mantiene por compatibilidad y lo deriva el backend: `activo = (estado <> 'baja')`. Todas las lecturas nuevas miran `estado`. **[Claude]**
- **Qué hace cada estado:**

| Estado | Login de funcionarios y vecinos | Páginas públicas | Procesos programados | Generador demo | Vaciado |
|---|---|---|---|---|---|
| `puesta_en_marcha` | sí | sí | sí | no | sí |
| `produccion` | sí | sí | sí | no | **no** |
| `demo` | sí | sí | sí | **sí** | sí |
| `modelo` | **nadie** (no tiene cuentas ni subdominio) | no | no | no | no (se edita, no se vacía) |
| `baja` | **nadie** (401 genérico) | 404 | no | no | no |

- El generador demo deja de usar `direccion_base` y corre para los municipios en `demo` (`services/demo_datos.py:303`, `routes/demo_datos.py:138`). `direccion_base` queda solo para resolver las direcciones sin prefijo.
- **El super edita el modelo con las pantallas de siempre:** el selector «Operando en» lista también el modelo (rotulado «Modelo»). Así se curan sus catálogos sin pantallas nuevas. **[Claude]**
- **Armado inicial del modelo:** una migración/script lo crea copiando los catálogos de San Andrés **sin datos personales** y sin lo que sea de prueba. Antes de copiar, el builder le presenta a César la lista de catálogos con sus cantidades y lo que propone descartar (p. ej. tipos «Test QA», áreas inactivas); César aprueba esa lista. **[Claude]**
- **Transiciones** (solo el super): `puesta_en_marcha → produccion` (confirmación escribiendo el nombre; sin vuelta atrás desde la interfaz) · cualquiera → `baja` · `baja →` el estado que tenía antes de la baja (reactivar) · `demo` y `modelo` no se crean por el alta (solo por migración). **[Claude]**
- **`municipios.fue_produccion`** BOOLEAN, se pone en true al pasar a `produccion` y no vuelve a false. El vaciado exige `fue_produccion = false` además del estado: un municipio que estuvo en producción, aunque se dé de baja y se reactive, nunca habilita el vaciado. **[Claude, a partir del builder check]**

### 4.1b País, provincia y agrupamientos [César, 2026-10-27]

Hoy (prod, 2026-10-27): `provincias` es global con `codigo_pais` (24 filas, Argentina), `partidos` cuelga de ella; no hay catálogo de países; `municipios` tiene `provincia` en texto libre, `pais` en texto y `codigo_pais`.

- **Catálogo global `paises`**: código ISO (PK), nombre, **cómo se llama cada nivel** en ese país (p. ej. «Provincia» / «Partido» en Argentina, «Estado» / «Municipio» en Venezuela), zona horaria por defecto y **`habilitado_para_alta`**. Lo edita solo el super.
- **`municipios.id_provincia`** (FK a `provincias`) reemplaza al texto libre; `codigo_pais` debe coincidir con el de la provincia (CHECK o trigger). `id_partido` opcional (FK a `partidos`), porque un municipio puede no corresponder a un partido existente (San Andrés es ficticio). La migración resuelve San Andrés → Buenos Aires; «MUNICIPIO OSPINO» (en `baja`) queda con `id_provincia` NULL permitido solo en `baja`. **[Claude]**
- **Agrupamientos:** la lista de «Municipios» y el selector «Operando en» del super se agrupan y filtran por país y provincia. Los tableros consolidados por país o provincia siguen en F7.
- **Alcance de esta fase:** el alta solo ofrece países con `habilitado_para_alta = true`, que hoy es **solo Argentina**. Otro país se habilita en la próxima etapa (F5b: zona horaria por municipio en el código, documentos por país), cargando sus provincias (o equivalente) en el catálogo global. Las etiquetas de nivel ya se usan en el alta y en la ficha, para que esa etapa no tenga que tocar estas pantallas.

### 4.2 Áreas fijas

- `area.es_sistema` BOOLEAN NOT NULL DEFAULT false. Las 6 áreas activas de San Andrés quedan marcadas; el modelo las tiene y el alta las crea siempre.
- Con `es_sistema`: se renombran, no se dan de baja (422 en la API, botón deshabilitado en Maestros). El guard va en la API y en un trigger de base, para que ningún camino las desactive. **[Claude]**
- Las claves de `configuracion_general` que apuntan a ellas por id (`id_area_salud`, `id_espacio_guardia`) se siembran en el alta por nombre (regla §21 de CLAUDE.md).

### 4.3 Módulos por municipio

- Tabla nueva `municipio_modulo (id_municipio, modulo_codigo, habilitado, min_nivel_acceso, …estándar §10)`, clase `catalogo`, único `(id_municipio, modulo_codigo)`. `modulos` sigue global: es el catálogo y su `min_nivel_acceso` pasa a ser el **valor por defecto** del alta.
- **Habilitar o quitar** un módulo: solo el super. **Nivel mínimo** de cada módulo en su municipio: el administrador del municipio (nivel 1), dentro de 1-5; los módulos de nivel 0 no aparecen para él (decisiones del plan general §4).
- Módulos que no se pueden deshabilitar (el municipio no funciona sin ellos): Usuarios, Configuración, Mi perfil, Inicio. Lista exacta **[builder]**, revisada contra el catálogo.
- **Dependencias entre módulos [Claude, a partir del builder check]:**
  - **Duras** (habilitar uno exige el otro; deshabilitar el otro exige deshabilitar antes el dependiente): Turnos y Entradas → Agenda; Guardia → Emergencias y Turnos; Órdenes de Trabajo → Reclamos. Se declaran en un solo lugar (tabla o constante) y las valida la API del alta y de la edición.
  - **Efectos automáticos de un módulo apagado: dejan de ocurrir**, con la guarda en el servicio y en los procesos programados, no solo en los routers: sin Encuestas no se crean envíos (al cerrar un reclamo, cumplir un turno o cerrar un trámite) y el dispatcher saltea el municipio; sin Órdenes de Trabajo no hay asignación automática y el reclamo se resuelve con el cierre directo que ya existe. Lista completa de efectos cruzados **[builder]**, relevada contra el código.
- **Se aplica en el backend, no solo en el menú:**
  - `modulos_permitidos` recibe el municipio y une `modulos` + `municipio_modulo` + `usuario_modulos`; se borra la copia de esa lógica en `buc.py:75-86`.
  - Cada router de un módulo deshabilitable lleva una dependency a nivel de router que responde **404** si el módulo está deshabilitado en el municipio de la request (para el super, el del selector). Los endpoints públicos del vecino de ese módulo, también 404. **[Claude: 404 y no 403, para no revelar qué tiene cada municipio]**
  - Los guards de nivel fijos que ya tienen los routers (p. ej. `agenda_v2.py:85`, `ordenes_trabajo.py:53`) siguen: el nivel mínimo por municipio puede **endurecer** el acceso, no aflojar un guard de negocio. **[Claude]**
- **Frontends:** el sidebar ya oculta por `modulos_permitidos`. La app del vecino y la de agentes reciben la lista de módulos habilitados en el endpoint de identidad que ya consultan, y ocultan lo deshabilitado.
- San Andrés y el modelo arrancan con todos los módulos habilitados y los niveles actuales.
- Pantallas: el catálogo de módulos (Usuarios → Catálogo) pasa a mostrar el municipio del selector; el super ve «habilitado» y el nivel, el administrador solo el nivel. Detalle de UI **[builder]**.

### 4.4 Alta de un municipio (módulo «Municipios»)

Un asistente con los pasos del plan general §5, con estas precisiones:

1. **Datos:** nombre, país (de los habilitados para el alta), provincia (del catálogo, con la etiqueta del país), partido opcional, zona horaria (por defecto la del país), `codigo_corto` (prefijo de numeración, único, mayúsculas, 2-5 caracteres) y `subdominio` (minúsculas, sin tildes, guiones; único; validado contra una lista de reservados: `www`, `api`, `zge`, `vecinos`, `agentes`, `admin`…). Una vez dado de alta, `codigo_corto` no se edita. **[Claude]**
2. **Identidad:** logo, color, contorno del mapa y bbox del geocoding, con valores por defecto si no se cargan. **Si no se cargan el contorno o el bbox, el alta lo advierte**: el geocoding caería a Vicente López (riesgo R4 de la guía de arranque).
3. **Qué copiar del modelo:** casillas por catálogo. Las áreas fijas se copian siempre. La copia re-mapea las FK al municipio nuevo (base: el clonador de `seed_municipio_aislamiento.py`, hoy solo local, llevado a un servicio de la app).
4. **Módulos habilitados.**
5. **Tope de cuentas** (`max_usuarios_activos`, opcional).
6. **Primer administrador:** nombre, apellido, DNI, email. Se crea su ficha en la BUC del municipio, su **agente** y su usuario nivel 1 en **una subárea** (sin subárea, crear un trámite da 500: `creacion.py`, `ck_tramite_destinatario`); la subárea es la primera de un área fija, o una que el super elige. **[Claude]**
7. **Configuración:** el alta siembra **todas** las claves de `configuracion_general` del municipio desde el modelo (no solo las que el super toca), con `activo` y `tipo` explícitos (regla §21).

- **Una transacción** para todo lo de base. Si algo falla, no queda nada.
- **Invitación:** mail con un link a `https://<sub>.zge.zaris.com.ar/…` para elegir la clave, válido 72 h, de un solo uso, reenviable por el super. Elegir la clave **habilita la vinculación del segundo factor** de esa cuenta (24 h, como F3b) y lleva directo a vincular la app. El super nunca conoce la clave. **[Claude]** El mail sale con la identidad del municipio nuevo.
- **Pasos externos (DNS y dominios):** ver §4.10. La ficha del municipio muestra el estado de cada uno de los 3 dominios (DNS, certificado, responde) con un botón «Verificar» que los chequea desde el backend sin credenciales (resolución DNS + GET HTTPS).
- **Prueba automática de puesta en marcha** (botón en la ficha, y al final del alta si los dominios ya responden): identidad pública por cada subdominio, que el login del administrador resuelva su municipio (sin completar el login), mail de invitación generado y su link respondiendo 200, módulos habilitados = los elegidos.

### 4.5 Usuarios del municipio y tope

- Como en el plan general §5b. Al llegar al tope, crear o reactivar una cuenta interna da 409 con mensaje claro; Usuarios muestra «N de M cuentas» y avisa desde el 90 %. No cuentan el super ni los vecinos.
- Si el super baja el tope por debajo de las cuentas activas, no desactiva a nadie: solo impide crear o reactivar hasta bajar del tope. **[Claude]**

### 4.6 Alta de más super administradores

- Desde «Municipios» → «Super administradores»: solo otro super. Cuenta de nivel 0 sin municipio, invitación por mail (mismo mecanismo que §4.4, el mail sale como ZARIS), segundo factor obligatorio (F3b), alta y baja registradas en `super_admin_acceso`.
- No se puede dar de baja al último super activo. **[Claude]**

### 4.7 Vaciado de datos

Como en el plan general §9, con estas precisiones:

- **Grupos:** `municipio_tabla_clase` gana una columna **`grupo`** (`operativo`, `contactos`, `maestros`, `usuarios`, `configuracion`), asignada a mano una vez por tabla en la migración y **obligatoria para toda tabla nueva** (regla a sumar en §10 de CLAUDE.md). La clase sola no alcanza: contactos, usuarios y operativo son todas `operativo`. **[Claude, a partir del builder check]**
- **Arrastre:** el orden de borrado y lo que arrastra cada grupo se calculan con las FK compuestas `fkm_*` (mig 125d), no con una lista a mano. Borrar contactos arrastra lo operativo que los referencia y las cuentas de la app del vecino; las cuentas internas vinculadas a una ficha (`usuarios.id_ciudadano`) se desvinculan, no se borran, salvo que también se elija el grupo usuarios. La pantalla muestra antes cuántas filas de cada tabla se borran. Base: `borrar_municipio_aislamiento` de `seed_municipio_aislamiento.py`, llevado a un servicio de la app con guard de estado.
- **Nunca:** tablas `global`, el grupo `configuracion` (claves de `configuracion_general` del municipio, identidad, logo, contorno, bbox y las claves que apuntan por id a entidades), `municipio_modulo`, áreas fijas, `municipios`, `super_admin_acceso`, el administrador principal y su agente, ficha y subárea. Si un vaciado de maestros borra una entidad a la que apunta una clave por id (p. ej. el espacio «Guardia»), esa clave se vuelve a sembrar desde el modelo en la misma operación. El municipio queda **como recién dado de alta: configurado y sin datos.** **[Claude, a partir del builder check]**
- **Archivos:** antes de borrar las filas se leen las rutas de los adjuntos del municipio (reclamos, OT, trámites, foto de perfil, logos) y se borran esos objetos de los buckets. No depende del prefijo `m{id}/` (que es F6). **[Claude]**
- **Resguardo:** se genera la exportación (§4.8) y el vaciado no corre si la exportación falla.
- **Confirmación** escribiendo el nombre del municipio; registro en `super_admin_acceso`.
- **Asíncrono** (puede pasar los 300 s del edge de Railway): 202 + estado por polling, mismo patrón que `/demo/poblar` (CLAUDE.md §9).

### 4.8 Exportación por municipio (solo lo que necesita el vaciado)

- Vuelca las filas del municipio (tablas `catalogo`, `operativo` y las filas suyas de `mixta`) a un archivo JSON comprimido por tabla, en un bucket **privado** (`exportaciones`, ruta `m{id}/<fecha>.zip`). Asíncrona como el vaciado. Formato **[builder]**.
- **Retención [César, 2026-10-27]:** 90 días y se borran solas (un proceso programado diario, con su registro). **Las descarga solo el super**, por URL firmada de vida corta, y cada descarga queda en `super_admin_acceso`. El administrador del municipio pide la suya a través del super; no hay descarga desde su sesión.
- La restauración en una base vacía y la entrega al municipio siguen siendo de F6.

### 4.9 Subdominios: backend

- **CORS:** `allow_origin_regex` alineado con `_PATRON_HOST` (`https://([a-z0-9-]+\.)?(zge|vecinos|agentes)\.zaris\.com\.ar`), más la lista exacta de localhost y de los dominios de vista previa de Cloudflare que se usen. Verificar soporte en la Starlette que arrastra FastAPI 0.111.
- **Links de mails y QR — todos por municipio:** `core/urls.py` pasa a recibir el municipio y arma `https://<sub>.<app>.zaris.com.ar` (o el dominio sin prefijo si el municipio es el de `direccion_base`). Se migran a esos helpers **todos** los armadores relevados el 2026-10-27, incluidos los que hoy no pasan por `urls.py`: `auth.py:280`, `services/cuenta_zaris.py:292-293`, `services/encuestas_service.py:535,848`, `services/notificaciones.py:279,760,868,972`, `publico_alta.py:111`, `services/cuenta_vecino.py:167`, `publico_auth.py:245,376,557`, `publico_reclamos.py:363`. Las settings globales quedan solo como base del dominio (`zaris.com.ar`) y para local. Un barrido (`grep` en CI o smoke) falla si aparece un link armado fuera de los helpers. **[Claude]**
- **Caché de municipios:** se invalida al dar de alta, cambiar estado o subdominio. Con una sola réplica en Railway alcanza el TTL de 60 s; si un día hay más, hay que revisarlo.
- **Páginas públicas vanilla:** `alta-vecino.html` resuelve el municipio por el `Origin` cuando no trae `?m=` (hoy da error sin slug). `encuesta.html` ya va por token.

### 4.10 Subdominios: frontends y mudanza a Cloudflare Pages

- **Tres proyectos de Cloudflare Pages** conectados a sus repos (`zaris-zge`, `zaris-vecinos`, `zaris-agentes`), que buildean en Cloudflare en cada push a `main`.
  - **Shell:** se deja de commitear `web-app/dist` a main (se borra el workflow `deploy-web-app.yml` y `dist` sale del repo). Cloudflare buildea `web-app` y publica la raíz del repo más el `dist`. Detalle del build **[builder]**: lo que importa es que `index.html`, `frontend/`, `design-system/`, `docs/` y el bundle queden en las mismas rutas que hoy.
  - **Apps:** se replica lo que hoy hace `vercel.json` (rewrite a `/index.html`, headers del `sw.js`) en el formato de Cloudflare (`_redirects` / `_headers`). Las variables de entorno de Vercel (`VITE_API_URL`, `VITE_APP_VERSION`) pasan a Cloudflare.
- **Dominios:** cada proyecto lleva el dominio sin prefijo (el demo) y uno por municipio (`<sub>.zge…`, `<sub>.vecinos…`, `<sub>.agentes…`), cada uno con su CNAME en modo DNS only o proxied según lo que pida Cloudflare Pages **[builder, verificando la doc oficial]**.
- **Alta de dominios de un municipio:** un script local (`tools/dominios_municipio.py <subdominio>`) que usa un token de la API de Cloudflare (permisos DNS:Edit de la zona + Pages:Edit) guardado en `credenciales-testing/`, **nunca en el repo ni en Railway**. Crea los 3 registros y agrega los 3 dominios a los 3 proyectos. El backend no tiene credenciales de Cloudflare. **[Claude]**
- **Orden de la mudanza (sin cortar San Andrés):**
  1. Proyectos de Cloudflare publicando en sus direcciones `*.pages.dev`; CORS ya aceptándolas; prueba completa ahí (caen al municipio base, que es lo esperado).
  2. Leer los **términos oficiales** de Cloudflare antes de mover un dominio.
  3. Mover un dominio por vez (primero `agentes.`, después `vecinos.`, al final `zge.`): agregar el dominio al proyecto de Cloudflare y cambiar el CNAME; verificar; recién ahí quitarlo de Vercel / GitHub Pages.
  4. Las PWAs conservan su origen (mismo dominio), así que el service worker, las apps instaladas y las suscripciones push siguen. Verificarlo con un celular con la app instalada antes y después.
  5. GitHub Pages se apaga al final (se borra el `CNAME` del repo).
- **Shell sin subpath:** `shellNav.ts:24,39` deja de suponer un primer segmento de ruta.
- **API base:** sigue fija por hostname (local o prod) en `menu.js` y `login.html`; ahora tiene que reconocer también los subdominios de municipio como prod.

### 4.11 Arreglos de pantallas con tablas vacías

Los relevados en [`docs/guia_arranque_tablas.md`](docs/guia_arranque_tablas.md) (R3-R10): Identidad y Config → Sistema pasan a insertar-o-actualizar y a mostrar las claves faltantes · asignación automática que inserta la OT sin estado · resolver un reclamo sin el estado «Terminada» · nacionalidad y tipo de representación fijos en 1 · Turnos traduciendo cualquier error de integridad a «horario tomado» · cast sin validar de la clave de Guardia · geocoding cayendo a Vicente López sin aviso. Más los menores «antes de F4» de ESTADO: el límite de intentos del login por mail común a todos los municipios y los dos seeds (`seed_catalogos_emergencias.py`, `seed_activos_local.py`) que no mandan el municipio. La prueba incluye **recorrer cada módulo del municipio nuevo con las tablas vacías** sin errores 500.

### 4.12 Guía de arranque y guía privada de alta

- La **guía de arranque** (qué cargar primero, por circuito) se escribe para el administrador del municipio a partir del anexo A del plan general. Formato: se define con la base de conocimiento; en esta fase queda como documento en `docs/`. **[Claude]**
- La **guía privada de alta** para César (qué pedirle al cliente, pasos, DNS, primer administrador, perfiles mínimos, carga inicial) sale de la corrida de cierre y va a `credenciales-testing/`, nunca al repo **[César]**.

## 5. Prueba de cierre (en prod)

1. Alta de un municipio de prueba desde «Municipios» (subdominio `prueba`, código `PRU`), copiando todo del modelo; dominios creados con el script; «Verificar» en verde para los 3.
2. El primer administrador (un email de César) recibe la invitación, elige la clave, vincula la app y entra por `prueba.zge.zaris.com.ar` viendo la identidad del municipio de prueba.
3. Carga lo de la guía de arranque y crea al menos un registro en cada circuito: reclamo con OT, turno, evento con reserva, trámite, emergencia, encuesta respondida.
4. Un vecino se da de alta en `prueba.vecinos.zaris.com.ar` **con el mismo DNI** que una cuenta de San Andrés; cada uno ve solo lo suyo; los links de sus mails van a su subdominio.
5. Un agente del municipio de prueba usa `prueba.agentes.zaris.com.ar`.
6. Un módulo deshabilitado no aparece y su API responde 404, también para el vecino.
7. Tope de cuentas: al llegar, 409.
8. Vaciado con exportación previa; el municipio vuelve a operar cargando desde cero; recorrido de cada módulo vacío sin 500.
9. San Andrés: smokes en verde, apps instaladas y push funcionando tras la mudanza.
10. El municipio de prueba queda en `baja`. Sale la guía privada.

Además, como en las fases anteriores: smoke de aislamiento con tres municipios (demo, modelo, prueba) sin fugas, suite local en verde y recorrido en el navegador.

## 6. Restricciones

- Migraciones desde la **130**; tablas nuevas clasificadas en `municipio_tabla_clase` y con RLS habilitado (§10 y §21 de CLAUDE.md). Las que llevan `DROP` las corre César en el SQL Editor; el resto por MCP, de a una.
- Backup de prod antes del corte. Primero local, después prod (§24).
- Se publica primero el código que deja de leer lo que se borra (regla del lote de limpieza).
- El login de Cloudflare no funciona en el navegador integrado de VS Code (Turnstile): lo que haya que hacer en el panel lo hace César desde Chrome o Edge, paso a paso. Igual con la conexión de los repos de GitHub a Cloudflare Pages.
- Ningún token de Cloudflare en el repo, en memorias ni en Railway.

## 7. Lo que queda al builder

- Forma exacta de las tablas, endpoints, pantallas del asistente y del catálogo de módulos.
- Lista de módulos no deshabilitables, revisada contra el catálogo.
- Configuración de build y de dominios de Cloudflare Pages (verificando la documentación oficial).
- Orden interno de tareas y cortes, siempre con la mudanza de frontends antes de los subdominios de un municipio nuevo.
- Formato de la exportación, mientras sirva para restaurar después (F6).
