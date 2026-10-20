# Flujos operativos ZARIS ZGE

Diagramas Mermaid de los flujos transaccionales reales del sistema. Cada diagrama refleja exactamente los estados definidos en la base de datos (CHECK constraints / tablas catálogo) y los endpoints implementados en el backend.

Fuente única de verdad:
- Estados de reclamo: CHECK `ck_reclamo_estado` + tabla `estado_reclamo`.
- Estados de OT: tabla `estado_ot` (seeds aplicados 2026-05-12).
- Estados de turno: CHECK del campo `turnos.estado` (mig 45).
- Estados de evento y reserva: tablas `estado_evento` y `estado_reserva` (mig 31).

---

## 1. Flujo de Reclamo

Alta en "Sin asignar". Cancelación permitida en los estados de gestión (Sin asignar / En gestión / En espera). Reasignación permitida en los estados de gestión. Edición completa solo en "Sin asignar"; edición parcial (solo `observaciones`) en En gestión / En espera; `Resuelto`, `Cancelado`, `En auditoría` y `Auditado` rechazan edición con 422.

**Auditoría POSTERIOR al cierre (mig 112):** `Resuelto` es el fin de la gestión y de sus tiempos (`fecha_cierre` no cambia nunca después). La auditoría es manual: un supervisor de la subárea del reclamo (o un admin) manda un `Resuelto` a `En auditoría` y el auditor lo cierra como `Auditado` (aprobado u observado). Al observar, el auditor elige si inicia un incidente nuevo: un reclamo NUEVO de retrabajo, visible para el vecino (mail + aviso), que al resolverse dispara la encuesta.

```mermaid
flowchart TD
    Alta([POST /reclamos]) --> SinAsignar

    SinAsignar["Sin asignar<br/>(edicion completa,<br/>reasignacion, cancelacion)"]
    EnGestion["En gestion<br/>(edicion: solo observaciones,<br/>reasignacion, cancelacion)"]
    EnEspera["En espera<br/>(bloqueado por subreclamo,<br/>edicion: solo observaciones)"]
    Resuelto[["Resuelto<br/>(fin de la gestion - sin edicion)"]]
    Cancelado[["Cancelado<br/>(final - sin edicion)"]]
    EnAuditoria["En auditoria<br/>(resuelto, pendiente del auditor;<br/>sin edicion, OT, subreclamo ni cancelacion)"]
    Auditado[["Auditado<br/>(aprobado u observado - final)"]]
    Retrabajo(["Reclamo NUEVO de retrabajo<br/>(canal oficio, nace Sin asignar,<br/>id_reclamo_origen_auditoria)"])

    SinAsignar -->|"OT creada<br/>(POST /ot)"| EnGestion
    SinAsignar -->|"Cierre directo sin OT<br/>(supervisor de la subarea)"| Resuelto
    SinAsignar -->|"PUT /reclamos/{id}/cancelar<br/>(requiere motivo)"| Cancelado

    EnGestion -->|"POST /reclamos/{id}/subreclamo<br/>(padre a En espera)"| EnEspera
    EnGestion -->|"OT operativa terminada<br/>o PUT /reclamos/{id}/estado"| Resuelto
    EnGestion -->|"PUT /reclamos/{id}/cancelar<br/>(cascade a OTs activas)"| Cancelado

    EnEspera -->|"Subreclamo resuelto/cancelado"| EnGestion
    EnEspera -->|"PUT /reclamos/{id}/cancelar"| Cancelado

    Resuelto -->|"POST /reclamos/{id}/auditoria<br/>(supervisor de la subarea o admin;<br/>crea la OT de auditoria)"| EnAuditoria
    EnAuditoria -->|"PUT /ot/{id}/aprobar"| Auditado
    EnAuditoria -->|"PUT /ot/{id}/observar<br/>(observacion obligatoria)"| Auditado
    EnAuditoria -->|"OT de auditoria Cancelada"| Resuelto
    Auditado -.->|"observado con<br/>generar_retrabajo=true"| Retrabajo

    %% Subreclamo (max 1 nivel)
    SubReclamo["Subreclamo<br/>(profundidad maxima 1)"]
    EnGestion -.->|"POST subreclamo"| SubReclamo
    SubReclamo -.->|"Sub debe cerrar<br/>antes que el padre<br/>pase a Resuelto/Cancelado"| EnEspera

    classDef finalNode stroke:#1f8a65,stroke-width:3px,fill:#e7f5ef
    class Resuelto,Cancelado,Auditado finalNode
```

**Reglas clave:**
- **Sub-reclamo** se crea con `POST /reclamos/{id}/subreclamo`. Profundidad maxima 1: si el padre ya tiene `id_reclamo_padre`, la API rechaza.
- Mientras exista un sub-reclamo activo en gestión (`Sin asignar`, `En gestion`, `En espera`), el reclamo padre **no puede** pasar a `Resuelto` ni `Cancelado`. Un hijo `En auditoria`/`Auditado` ya cerró su gestión. El backend valida antes de aplicar el cambio de estado.
- `En auditoria` y `Auditado` no se alcanzan por `PUT /reclamos/{id}/estado` (422): se entra por `POST /reclamos/{id}/auditoria` y se sale por `/ot/{id}/aprobar|observar` (o cancelando la OT de auditoría).
- **Para el vecino** la auditoría del reclamo original no existe: lo sigue viendo `Resuelto`. El retrabajo SÍ lo ve («Reabierto por control de calidad del reclamo REC-…»), sin la observación del auditor.
- Cambios de estado quedan registrados como filas append-only en `reclamo_historial`.

---

## 2. Flujo de Orden de Trabajo (OT)

Estados de la tabla `estado_ot`: `Pendiente`, `En gestion`, `En espera`, `Terminada`, `Cancelada`.

```mermaid
flowchart TD
    AltaSup([Supervisor crea OT:<br/>POST /ot o POST /ot/con-agenda])
    AltaAud([OT de auditoria es_auditoria:<br/>POST /reclamos/{id}/auditoria<br/>sobre un reclamo Resuelto])

    AltaSup --> Pendiente
    AltaAud --> EnGestion

    Pendiente["Pendiente<br/>(sin asignar a agente,<br/>o asignada sin tomar)"]
    EnGestion["En gestion<br/>(agente trabajando)"]
    EnEspera["En espera<br/>(bloqueada por dependencia)"]
    Terminada[["Terminada<br/>(operativa cerrada -><br/>reclamo a Resuelto)"]]
    Cancelada[["Cancelada<br/>(cascade del reclamo padre)"]]

    Pendiente -->|"Agente toma:<br/>PUT /ot/{id}/tomar"| EnGestion
    Pendiente -->|"PUT /ot/{id}/estado"| EnGestion
    Pendiente -->|"Cancelacion del reclamo padre"| Cancelada

    EnGestion -->|"PUT /ot/{id}/estado"| EnEspera
    EnGestion -->|"PUT /ot/{id}/estado"| Terminada
    EnGestion -->|"Cancelacion del reclamo padre"| Cancelada

    EnEspera -->|"PUT /ot/{id}/estado"| EnGestion
    EnEspera -->|"Cancelacion del reclamo padre"| Cancelada

    %% OT de auditoria: se cierra solo por aprobar/observar (Terminada por /estado da 422)
    EnGestion -->|"Auditor aprueba u observa:<br/>PUT /ot/{id}/aprobar o /observar<br/>(reclamo -> Auditado)"| Terminada
    EnGestion -->|"Cancelar la auditoria<br/>(reclamo vuelve a Resuelto)"| Cancelada

    classDef finalNode stroke:#1f8a65,stroke-width:3px,fill:#e7f5ef
    classDef finalCancel stroke:#c62828,stroke-width:3px,fill:#fbe9eb
    class Terminada finalNode
    class Cancelada finalCancel
```

**Operaciones:**
- **Alta:** Supervisor crea OT desde la bandeja de reclamos (`POST /ot` simple, o `POST /ot/con-agenda` que ademas planifica ocupacion en la grilla).
- **Tomar:** Agente toma una OT no asignada con `PUT /ot/{id}/tomar`.
- **Cambio de estado:** `PUT /ot/{id}/estado` con el `id_estado_ot` destino.
- **Terminar la OT operativa** siempre deja el reclamo en `Resuelto` (no hay auditoría automática; `tipo_reclamo.audit` ya no se consulta).
- **Enviar a auditoría:** `POST /reclamos/{id}/auditoria` sobre un reclamo `Resuelto` crea la OT `es_auditoria` (en `En gestion`, `id_ot_origen` = última OT operativa terminada) y pasa el reclamo a `En auditoria`.
- **Aprobar (auditoria):** `PUT /ot/{id}/aprobar` -> OT `Terminada`/aprobada; reclamo `Auditado`/aprobado (cierre definitivo).
- **Observar (auditoria):** `PUT /ot/{id}/observar` con `observaciones` (obligatoria) y `generar_retrabajo` (bool, default `true`) -> OT `Terminada`/observada; reclamo `Auditado`/observado. Con `generar_retrabajo=true` nace un reclamo NUEVO de retrabajo y se avisa al vecino (mail genérico + aviso + push); con `false`, solo queda registrado. `/rechazar` es un alias deprecado del mismo endpoint.
- **Cancelar:** la OT operativa se cancela en cascada cuando el reclamo padre se cancela. Una OT de auditoría cancelada (`PUT /ot/{id}/estado`) devuelve el reclamo a `Resuelto`.

---

## 3. Flujo de Turnos

Estados del CHECK en `turnos.estado`: `reservado`, `cumplido`, `cancelado`. Origen via columna `turnos.origen` (`backoffice` o `autoservicio`, mig 46).

```mermaid
flowchart TD
    AltaBO([Operador desde modulo Turnos:<br/>POST /turnos<br/>origen = 'backoffice'])
    AltaAS([Ciudadano sin JWT:<br/>POST /turnos/publico/reservar<br/>origen = 'autoservicio'])

    AltaBO --> Reservado
    AltaAS --> Reservado

    Reservado["reservado<br/>(unico estado mutable)<br/>- Reprogramar: PUT /turnos/{id}<br/>- Crea ocupacion espejo en grilla"]
    Cumplido[["cumplido<br/>(asistencia confirmada)"]]
    Cancelado[["cancelado<br/>(libera ocupacion espejo)"]]

    Reservado -->|"PATCH /turnos/{id}/cumplir"| Cumplido
    Reservado -->|"PATCH /turnos/{id}/cancelar<br/>(backoffice)"| Cancelado
    Reservado -->|"DELETE /turnos/publico/turno/{token_turno}<br/>(autoservicio)"| Cancelado

    %% Reprogramacion mantiene estado reservado
    Reservado -.->|"PUT /turnos/{id}<br/>(reprograma fecha/hora,<br/>solo si estado='reservado')"| Reservado

    classDef finalOk stroke:#1f8a65,stroke-width:3px,fill:#e7f5ef
    classDef finalCancel stroke:#c62828,stroke-width:3px,fill:#fbe9eb
    class Cumplido finalOk
    class Cancelado finalCancel
```

**Notas operativas:**
- Cada turno mantiene una **ocupacion espejo** en `ocupaciones` (`tipo='turno'`, `tipo_recurso='agente'`) para aparecer en la grilla del modulo Agenda. La sincronizacion se gestiona desde `routes/turnos.py`.
- **Reprogramar** solo es valido si el estado actual es `reservado`; el handler actualiza turno + ocupacion en una transaccion.
- **Cumplir** solo modifica `turno.estado` (la ocupacion queda como historico en la grilla).
- **Cancelar** modifica `turno.estado` y hace soft-delete de la ocupacion espejo (libera el slot).
- El **autoservicio** usa `token_turno UUID` (no enumerable) en lugar de JWT.

---

## 4. Flujo de Entradas (eventos con reserva)

Estados de evento (`estado_evento`): `activo`, `finalizado`, `cancelado`. Estados de reserva (`estado_reserva`): `reservada`, `asistio`, `cancelada`.

### 4a. Ciclo de vida del evento

```mermaid
flowchart TD
    AltaEvento([Operador desde modulo Entradas:<br/>POST evento con id_espacio])

    AltaEvento --> Activo

    Activo["activo<br/>(acepta reservas,<br/>visible en grilla agenda)<br/>admite_autoservicio: token_publico"]
    Finalizado[["finalizado<br/>(cierre temporal,<br/>no admite mas reservas)"]]
    CanceladoEvt[["cancelado<br/>(operador cancela)"]]

    Activo -->|"Operador cierra<br/>(cancelar evento)"| CanceladoEvt
    Activo -->|"Llegada de fecha fin<br/>o cierre manual"| Finalizado

    classDef finalOk stroke:#1f8a65,stroke-width:3px,fill:#e7f5ef
    classDef finalCancel stroke:#c62828,stroke-width:3px,fill:#fbe9eb
    class Finalizado finalOk
    class CanceladoEvt finalCancel
```

### 4b. Ciclo de vida de la reserva

```mermaid
flowchart TD
    AltaBO([Operador via ReservaModal<br/>reusado de Agenda<br/>(backoffice)])
    AltaAS([Ciudadano sin JWT:<br/>/autoservicio/:tokenPublico<br/>POST reserva con token])

    AltaBO --> Reservada
    AltaAS --> Reservada

    Reservada["reservada<br/>(QR generado:<br/>EVT{id}-RES{id}-{ts})"]
    Asistio[["asistio<br/>(acreditada)"]]
    CanceladaRes[["cancelada"]]

    Reservada -->|"PATCH /reservas/{id}/asistio<br/>(manual desde lista)"| Asistio
    Reservada -->|"POST /reservas/acreditar-qr<br/>(escaneo del QR fisico)"| Asistio
    Reservada -->|"PATCH /reservas/{id}/cancelar<br/>(backoffice)"| CanceladaRes
    Reservada -->|"Cancelacion via token publico<br/>(autoservicio)"| CanceladaRes

    %% Cascade desde el evento
    EvtCancelado([Evento pasa a 'cancelado'])
    EvtCancelado -->|"Reservas activas<br/>se cancelan en cascada"| CanceladaRes

    classDef finalOk stroke:#1f8a65,stroke-width:3px,fill:#e7f5ef
    classDef finalCancel stroke:#c62828,stroke-width:3px,fill:#fbe9eb
    class Asistio finalOk
    class CanceladaRes finalCancel
```

**Notas operativas:**
- **Entradas no tiene tablas propias.** Reusa `eventos` + `evento_reservas` del backend de Agenda. Un "evento con entradas" es un `evento` con `id_espacio` no nulo (filtro `con_espacio=true` en `GET /agenda/eventos`).
- El **autoservicio publico** se habilita seteando `evento.admite_autoservicio=true`; el backend genera `token_publico UUID` y la pagina `/autoservicio/:tokenPublico` permite reservar sin JWT.
- El **QR de acreditacion** es un identificador opaco (no URL). Se escanea con lector fisico y se acredita via `POST /reservas/acreditar-qr` con body `{qr_codigo}`.
- La gestion de reservas en el modulo Entradas **reutiliza el `ReservaModal` del modulo Agenda** (cross-module import valido por compartir entidad backend).
