# PLAN — App de agentes: reclamos de oficio + control de entradas (QR)

> **Estado: PROPUESTA diseñada el 2026-10-12, PENDIENTE DE APROBACIÓN de César** (la sesión cerró antes de
> que la revisara). No hay código. Al retomar: releer este archivo, confirmar o corregir el diseño con César y
> recién entonces arrancar F1. El estado de avance vivirá en [`ESTADO.md`](ESTADO.md).

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

### Backend (`zaris-zge`) — sin migración
Router `backend/app/api/routes/agentes_app.py` bajo `/api/v1/agentes/*`, guard usuario interno **nivel ≤ 4**:
- `POST /agentes/reclamos` — body como el del vecino (`id_tipo_reclamo`, `descripcion ≥ 5`, `direccion`, lat/lon,
  `fuente_geolocalizacion`). Inserta con `canal_origen='oficio'`, `id_usuario_alta`=user, `id_ciudadano`=
  `usuarios.id_ciudadano` o NULL, prioridad Media, estado «Sin asignar» (FK + VARCHAR), localidad derivada de coords;
  historial «Reclamo de oficio cargado desde la app de agentes por <agente>». Devuelve `{id_reclamo, nro_reclamo}`.
- `GET /agentes/reclamos` — reclamos de oficio cargados por mí (`id_usuario_alta = me AND canal_origen='oficio'`).
- Reusar: `GET /reclamos/catalogo/tipos`, `GET /geo/buscar`, `GET /geo/reverse`, `GET /reclamos/{id}`,
  `GET /reclamos/{id}/adjuntos` (la app ya los usa para OT). **Verificar el guard de
  `reclamo_adjuntos.py` upload-url/confirm**: si exige ≤ 3, excepción «quien cargó el reclamo puede adjuntarle fotos».
- `POST /agentes/entradas/acreditar-qr` — refactor de `acreditar_reserva_qr` a un helper compartido (el endpoint de
  Agenda queda igual). Respuesta para la puerta, **siempre 200**: `{resultado: 'acreditada'|'ya_acreditada'|'cancelada'|
  'no_encontrada', acreditada_en, reserva: {evento, fecha, hora, espacio, ciudadano}}`. «ya_acreditada» = entrada
  repetida (rojo, con la hora del primer ingreso). Sigue disparando la encuesta CSAT.
- `GET /agentes/entradas/eventos-hoy` — eventos del día con reservas/acreditadas y `soy_encargado`.
- Smoke in-process `backend/smoke_agentes_app.py`: reclamo de oficio por nivel 4 (201, canal oficio, historial), nivel 5
  → 403, QR válido/repetido/cancelado/inexistente, eventos-hoy.

### App de agentes (`zaris-agentes`)
- Barra inferior: Inicio · Mis OT · **Reclamos** · **Entradas** · Cuenta (5 ítems).
- Reclamos: `/reclamos` (Mis reclamos) → `/reclamos/nuevo` (portado del vecino: tipo con buscador, descripción,
  dirección OSM + «usar mi ubicación» + pin en el mapa, fotos con la cámara) → `/reclamos/:id` (detalle + historial).
- Control de entradas: `/entradas` (eventos de hoy, los míos primero, botón **Escanear QR**) → `/entradas/escanear`
  (cámara: `BarcodeDetector` en Android/Chrome; fallback `jsqr` para iPhone; campo manual) → tarjeta de resultado
  verde/rojo/ámbar + «Escanear otra» + contador de la sesión.
- Inicio: accesos a los dos apartados.

### Manual y docs
`manual_app_agentes.html` (+2 secciones, una regeneración al final), `ESTADO.md` de los dos repos, skills
`modulo-reclamos` (canal oficio desde la app) y `modulo-agenda` (acreditación desde la app), README de la app.

### Fases
F1 backend + smoke → F2 app Reclamos → F3 app Control de entradas → F4 manual + docs → F5 prod (push, OpenAPI,
Vercel), todo verificado navegando antes de declararlo.
