# PLAN — App de agentes: relevamientos + control de entradas (QR)

> **Estado: APROBADA por César el 2026-11-22** (§2b y §2c: siguió las cuatro recomendaciones). **F1 (backend) en
> prod el 2026-11-22** (mig 141 corrida por César en el SQL Editor + `agentes_app.py`), F1b en prod el 2026-11-22,
> **F2 y F3 (pantallas de la app) hechas el 2026-11-23**.
> Avance en [`ESTADO.md`](ESTADO.md).

## 1. Pedido de César (2026-10-12, textual resumido)

1. La app de agentes tiene que poder **generar reclamos de la misma manera que la app del vecino**.
2. Tiene que tener un apartado de **entradas** («boletero / picador de boletos»): **leer el QR de una entrada y
   darla por vista/validada**.

## 2. Decisiones tomadas por César (AskUserQuestion, 2026-10-12)

| # | Decisión | Elegido |
|---|---|---|
| 1 | A nombre de quién queda el reclamo | **De oficio, cargado por el funcionario**: `canal_origen = 'oficio'`, `id_usuario_alta` = el funcionario, `id_ciudadano` = su ficha vinculada (mig 110) si la tiene o NULL. No viola la regla de roles del backoffice (§3: crear reclamos = niveles 1-3). |
| 2 | Quién carga reclamos desde la app | **Todo funcionario con la app, niveles 1-4** (Consultor 5 no). |
| 3 | Quién acredita entradas por QR desde la app | **Todo funcionario con la app, niveles 1-4** (hoy `POST /agenda/reservas/acreditar-qr` exige ≤ 3). La app muestra primero los eventos de hoy donde es encargado, pero acredita cualquier QR válido. |
| 4 | Nombre del apartado | **«Control de entradas»** → «Escanear QR». |

## 2b. Correcciones de César (2026-11-22)

1. **No son «reclamos de oficio»: se llaman relevamientos.** Un relevamiento es un tipo de incidente como el
   reclamo, pero lo lleva a cabo un agente municipal (no hay un vecino que lo pida).
2. **Un relevamiento no avisa a ningún solicitante** (ni mail, ni push, ni bandeja de la app del vecino) **y no tiene
   encuesta de satisfacción**: quien lo inicia es un agente, no un vecino.
3. **Entradas:** el agente funciona de «picaboletos»: lee el QR, **valida el acceso y marca la entrada como
   consumida** (una segunda lectura de la misma entrada tiene que decir que ya se usó). El nombre del apartado queda
   «Control de entradas» salvo que César elija otro.

**Consecuencia sobre la decisión 1 de §2:** el relevamiento **no lleva `id_ciudadano`** (antes: la ficha del
funcionario). Con la ficha, el funcionario habría recibido los avisos y la encuesta de su propio relevamiento.

**Por qué hace falta una marca propia y no alcanza con `canal_origen='oficio'`** (verificado en el código el
2026-11-22): hoy `oficio` lo usan también el reclamo de retrabajo que nace de una auditoría observada y los que
carga el backoffice; el de retrabajo **copia al vecino y sí le avisa** (F4, 2026-10-20). Los avisos de cambio de
estado (`push.notificar_estado_reclamo`) y la encuesta salen solo si hay `id_ciudadano`, y el mail de alta se
saltea para `oficio`. Un relevamiento sin ciudadano ya no dispara nada; la marca sirve para **nombrarlo, listarlo
y contarlo aparte**, y como segunda barrera explícita en cada disparo («si es relevamiento, no se avisa ni se
encuesta»).

## 2c. Definiciones de César (2026-11-22: «sigue a las cuatro recomendaciones»)

| # | Pregunta | Decisión |
|---|---|---|
| 1 | ¿Tipos propios o el mismo catálogo de tipos de reclamo? | **El mismo catálogo** (gestión, SLA y asignación ya están ahí). |
| 2 | ¿Numeración propia (`REL-SAN-2026-000001`) o la de los reclamos? | **Propia**, para que el número diga qué es. |
| 3 | ¿Sigue el mismo circuito (OT, asignación automática, auditoría)? | **Sí, el mismo**: lo que cambia es quién lo inicia. |
| 4 | ¿Dónde se ve en el backoffice y en Datos? | **En Reclamos, con etiqueta y filtro «Relevamientos»; en Datos, contado aparte** de los reclamos del vecino. |

## 3. Realidad verificada (2026-10-12)

- El vecino crea reclamos en `/publico/reclamos` (scope `publico`, `canal_origen='app_movil'`, `id_usuario_alta NULL`);
  adjuntos en `/publico/reclamos/{id}/adjuntos/*`. Código de la PWA portable (~1.100 líneas: `NuevoReclamoPage`,
  `lib/reclamos.ts`, `lib/geo.ts`, `MapaPicker`).
- `POST /reclamos` del backoffice exige `NIVELES_GESTION {1,2,3}`; `reclamos.id_ciudadano` es NULLABLE y los
  listados hacen `LEFT JOIN ciudadanos`; el CHECK `ck_reclamos_canal` ya incluye `'oficio'` y el backoffice lo etiqueta
  «Oficio».
- Acreditar por QR existe: `POST /agenda/reservas/acreditar-qr` (`AcreditarQRIn.qr_codigo`, formato
  `EVT<id>-RES<id>-<ts>`, 404 inexistente, 409 cancelada, CAS de estado mig 95, dispara CSAT de entradas) con guard
  `require_operador` (nivel ≤ 3). **Ninguna UI lo usa** (pensado para lector físico); el backoffice acredita por lista.
  Ningún repo tiene librería de lectura de QR (`qrcode` solo genera).
- `evento_encargados` existe (agentes asignados a un evento) → «tus eventos de hoy».

## 4. Diseño propuesto (a confirmar)

### Backend (`zaris-zge`) — migración chica para la marca de relevamiento (forma según §2c)
Router `backend/app/api/routes/agentes_app.py` bajo `/api/v1/agentes/*`, guard usuario interno **nivel ≤ 4**:
- `POST /agentes/relevamientos` — body como el del reclamo del vecino (`id_tipo_reclamo`, `descripcion ≥ 5`,
  `direccion`, lat/lon, `fuente_geolocalizacion`). Inserta el relevamiento **sin `id_ciudadano`**, con
  `id_usuario_alta`=user, la marca de relevamiento, prioridad Media, estado «Sin asignar» (FK + VARCHAR), localidad
  derivada de coords; historial «Relevamiento cargado desde la app de agentes por <agente>». Devuelve
  `{id_reclamo, nro_reclamo}`.
- **Ningún aviso al solicitante ni encuesta:** guard explícito por la marca en el mail de alta, en
  `push.notificar_estado_reclamo` y en `encuestas_service.crear_envio_para_reclamo` (además de no tener ciudadano).
- `GET /agentes/relevamientos` — los relevamientos cargados por mí.
- Reusar: `GET /reclamos/catalogo/tipos`, `GET /geo/buscar`, `GET /geo/reverse`, `GET /reclamos/{id}`,
  `GET /reclamos/{id}/adjuntos` (la app ya los usa para OT). **Verificar el guard de
  `reclamo_adjuntos.py` upload-url/confirm**: si exige ≤ 3, excepción «quien cargó el reclamo puede adjuntarle fotos».
- `POST /agentes/entradas/acreditar-qr` — refactor de `acreditar_reserva_qr` a un helper compartido (el endpoint de
  Agenda queda igual). Respuesta para la puerta, **siempre 200**: `{resultado: 'acreditada'|'ya_acreditada'|'cancelada'|
  'no_encontrada', acreditada_en, reserva: {evento, fecha, hora, espacio, ciudadano}}`. «ya_acreditada» = entrada
  repetida (rojo, con la hora del primer ingreso). Sigue disparando la encuesta CSAT.
- `GET /agentes/entradas/eventos-hoy` — eventos del día con reservas/acreditadas y `soy_encargado`.
- Smoke in-process `backend/smoke_agentes_app.py`: relevamiento por nivel 4 (201, marca, sin ciudadano, historial),
  nivel 5 → 403, cerrarlo **no** crea encuesta ni aviso, QR válido / ya consumido / cancelado / inexistente,
  eventos-hoy.

### App de agentes (`zaris-agentes`)
- Barra inferior: Inicio · Mis OT · **Relevamientos** · **Entradas** · Cuenta (5 ítems).
- Relevamientos: `/relevamientos` (Mis relevamientos) → `/relevamientos/nuevo` (portado del reclamo del vecino: tipo
  con buscador, descripción, dirección OSM + «usar mi ubicación» + pin en el mapa, fotos con la cámara) →
  `/relevamientos/:id` (detalle + historial).
- Control de entradas: `/entradas` (eventos de hoy, los míos primero, botón **Escanear QR**) → `/entradas/escanear`
  (cámara: `BarcodeDetector` en Android/Chrome; fallback `jsqr` para iPhone; campo manual) → tarjeta de resultado
  verde/rojo/ámbar + «Escanear otra» + contador de la sesión. Verde = acceso válido, la entrada queda consumida;
  rojo = ya consumida (con la hora del primer ingreso), cancelada o inexistente.
- Inicio: accesos a los dos apartados.

### Docs
`ESTADO.md` de los dos repos, skills `modulo-reclamos` (relevamientos) y `modulo-agenda` (acreditación desde la
app), README de la app. **Sin manual:** los manuales están en pausa hasta la base de conocimiento (CLAUDE.md §36).

### Fases
F1 backend + smoke → **F1b backoffice y Datos** (Reclamos: etiqueta y filtro «Relevamientos»; Datos: contarlos
aparte de los reclamos del vecino; antes de que la app cargue relevamientos reales) → F2 app Relevamientos → F3 app
Control de entradas → F4 docs → F5 prod (push, OpenAPI, Cloudflare Pages), todo verificado navegando antes de
declararlo.

### F1 — hecho en local (2026-11-22)
- Mig 141 (`reclamos.es_relevamiento`, CHECK sin ciudadano, numeración `REL-`), local aplicada.
- `backend/app/api/routes/agentes_app.py`: `POST/GET /agentes/relevamientos`, `GET /agentes/relevamientos/{id}`,
  `POST /agentes/entradas/acreditar-qr`, `GET /agentes/entradas/eventos-hoy` (niveles 1-4; módulos `reclamos` y
  `entradas`). Helper `acreditar_qr_en_puerta` en `agenda_v2.py` (el endpoint de Agenda no cambió).
- Cortes por la marca en los avisos y la encuesta; herencia en subreclamo y retrabajo; fotos del autor (nivel 4).
- **Confirmado por César (2026-11-22):** un QR de un evento de **otro día** responde `otra_fecha` y **no consume**
  la entrada (la puerta lo muestra en rojo con la fecha).
- Smoke `backend/smoke_agentes_app.py` 43/43 (también con `DB_BARRERA=true`); auditoría 86, encuestas 294, alta
  con mail 11 y cancelar 8 siguen en verde.

### F1b — hecho (2026-11-22)
- **Reclamos:** filtro «Clase» (todos / reclamos del vecino / relevamientos) en el listado y en los contadores,
  etiqueta «Relevamiento», bloque «Cargado por» en el detalle y tarjeta propia al editar; asignarle un vecino o una
  empresa da 422.
- **Datos:** filtro «Origen» en Operativo y Ejecutivo (por defecto reclamos del vecino; relevamientos aparte).
- Verificado navegando en local (listado, contadores, detalle, editar, Operativo y Ejecutivo) y smoke 57/57 con y
  sin barrera; Atención 85, SLA demo 45. Queda para César: las tarjetas de Datos siguen diciendo «reclamos» aunque
  el origen sea relevamientos.

### Corrección de vocabulario (César, 2026-11-23)
«No dije que el origen es distinto: dije que es un tipo de transacción distinta.» El **canal** es la interfaz de
registro (call center, app del vecino, web del portal del vecino, app de agentes). En consecuencia:
- Datos: el filtro «Origen» pasa a **«Transacción»** (API: `origen` → `clase`, igual que en Reclamos) y los textos y
  los nombres de los CSV siguen lo elegido. Reclamos: «Clase» pasa a **«Transacción»**.
- Los relevamientos se registran con canal **`app_agentes`** («App de agentes»; migración 142) en lugar de `oficio`.
  «App móvil» se muestra como «App del vecino».

### F2 y F3 — hechas (2026-11-23, `zaris-agentes`)
- **Relevamientos:** `/relevamientos`, `/relevamientos/nuevo` (tipo con buscador, descripción, hasta 5 fotos, dirección
  OSM, pin y GPS; el punto completa la dirección si está vacía) y `/relevamientos/:id` (historial, mapa, agregar fotos).
- **Control de entradas:** `/entradas` (eventos de hoy, los propios primero) y `/entradas/escanear` (`BarcodeDetector`
  o `jsqr`; campo manual; verde/rojo; contador). La cámara se apaga mientras se muestra un resultado.
- Los apartados se muestran según el módulo del municipio y el nivel (el Consultor no los ve): `lib/permisos.ts`.
- Verificado navegando en local a 360 px: alta con foto y pin, detalle, QR leído por la cámara (video simulado, vía
  `jsqr`), repetida, cancelada, inexistente, sin permiso de cámara. **Probado por César en su Android el 2026-11-23** (relevamiento con fotos y lectura del QR).
- **Últimas 20 entradas** (pedido de César, 2026-11-23): `GET /agentes/entradas/ultimas`, solo las que validó la propia
  cuenta (número, horario, persona, documento y evento); se ve en `/entradas` y debajo del lector.
