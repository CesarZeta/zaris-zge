# Plan — Auditoría de reclamos POSTERIOR al cierre

> Estado: **F1 (backend + mig 112), F2 (frontend) y F3 (generador demo + backfill en prod) implementadas el 2026-10-20 y en prod** (`a42fb3e`, `f378f04`). **F4 (circuito del resultado + retrabajo visible + mail) implementada el 2026-10-20**, junto con la doc de usuario (manuales de Reclamos y OT, guía QA). Los puntos *supuesto* de abajo se aplicaron tal cual están escritos, más dos decisiones que el plan no cubría (ver «Cómo quedó»).
>
> **F3 (2026-10-20):** `services/demo_datos.py` ya no simula la auditoría previa; sortea auditorías posteriores (~8 % de los resueltos, 1-10 días tras el cierre, revisión de 1-7 días, 80 % aprobada / 20 % observada con retrabajo de oficio) con su OT e historial, y `avanzar_pendientes` las envejece (cierra ~60 % de las pendientes por corrida, manda ~3 % de los resueltos recientes). Sobre la demo cargada antes de la mig 112 se corrió una vez `backend/backfill_auditorias_demo.py` en local y en prod (prod: 2.517 candidatos → 177 Auditado + 4 En auditoría, 32 retrabajos; snapshot `_backup_reclamos_auditoria_2026_10_20` con las 181 filas previas, RLS on).

## Cómo quedó (2026-10-20)

- **Backend:** `POST /reclamos/{id}/auditoria` (supervisor de la subárea del reclamo —fuente `agentes.id_subarea`— o admin; solo sobre `Resuelto`; crea la OT de auditoría, opcionalmente asignada a un auditor puntual) · `PUT /ot/{id}/aprobar` → reclamo `Auditado`/`aprobado` · `PUT /ot/{id}/observar` (alias deprecado `/rechazar`) → `Auditado`/`observado` + reclamo NUEVO de retrabajo (`id_reclamo_origen_auditoria`, canal `oficio`, descripción con la observación) · terminar la OT operativa siempre resuelve (`tipo_reclamo.audit` ya no se consulta) · `/estado` rechaza los dos estados de auditoría · editar/OT/subreclamo/cancelar/avisar bloqueados en `En auditoría`/`Auditado` · cancelar la OT de auditoría devuelve el reclamo a `Resuelto` · indicadores: activos/pendientes = `Sin asignar`/`En gestión`/`En espera`; resueltos del BI = `Resuelto`+`En auditoría`+`Auditado`; el mapa del inicio muestra `En auditoría` en violeta y no `Auditado`.
- **Decisiones no previstas en el plan:** (1) **el retrabajo es invisible para el vecino** (no se lista, su detalle da 404, no genera push, aviso ni encuesta): era la única forma de cumplir «el vecino no ve nada» con un reclamo nuevo a su nombre — **REVERTIDA por César el 2026-10-20 al aprobar el plan, ver «F4»**; (2) **una auditoría se puede cancelar** (OT de auditoría → `Cancelada`, por supervisión o el auditor asignado) y el reclamo vuelve a `Resuelto` — aceptada; (3) los **tiempos del BI** cuentan a `En auditoría`/`Auditado` como resueltos con su `fecha_cierre` original — aceptada.

## F4 — Circuito del resultado + retrabajo VISIBLE para el vecino (diseño aprobado por César, 2026-10-20; implementado el mismo día)

> **Estado:** implementado y verificado en local (smoke 86/86 + recorrido en navegador del backoffice y de la PWA). Hallazgo de paso: el historial público mostraba la entrada «Auditoría cancelada» (F1) — corregido.

César al aprobar el plan: el vecino SÍ debe ver el reclamo nuevo que nace de una auditoría observada, y hay que informarle por correo electrónico por qué aparece un reclamo a su nombre: la revisión interna encontró fallas en el trabajo anterior y se reabrió el caso para resolverlo. «Dará mejor reputación a la gestión: el vecino percibe que hubo una acción.» Lo que sigue oculto para el vecino es la auditoría en sí (los estados `En auditoría`/`Auditado` del original se le muestran como `Resuelto`).

Circuito del resultado (pedido de César, misma fecha):

- **Aprobada** → `Auditado` / aprobado: cierre definitivo (ya era así: solo un `Resuelto` se manda a auditoría, un `Auditado` no se reabre ni se edita). Sin aviso al vecino.
- **Observada** → el auditor escribe la observación (obligatoria) y confirma; **surge un pop-up «¿Iniciar un nuevo incidente para rehacer el trabajo?»**:
  - **Sí** → `Auditado` / observado + reclamo NUEVO de retrabajo (como en F1) + **mail al vecino** («revisamos el trabajo de tu reclamo REC-X como control de calidad, no quedó como corresponde, abrimos REC-Y para volver a hacer la tarea; cuando terminemos te vamos a pedir tu opinión»), aviso en la bandeja de la app y push. **Texto genérico: la observación del auditor NO va al mail** (decisión de César: es interna).
  - **No** → `Auditado` / observado sin reclamo nuevo; el vecino no recibe nada (la auditoría sigue interna) — *decisión de Claude, no corregida*.
- **Fin del retrabajo** → al resolverse dispara la **encuesta CSAT, EXENTA de la anti-fatiga** (decisión de César: la auditoría ocurre pocos días después del cierre original, así que la regla de 30 días la bloquearía casi siempre). Sus cambios de estado notifican al vecino (push + bandeja) como cualquier reclamo.

Implementación:

1. **Backend `PUT /ot/{id}/observar`:** body `generar_retrabajo` (bool, **default `true`** para que el bundle anterior, que no pregunta, siga generando el retrabajo hasta que se publique el nuevo). Con `false`: historial «Auditoría observada» con la nota «sin retrabajo» y `id_reclamo_retrabajo: null`. Con `true`: post-commit `push.notificar_retrabajo_auditoria` (mail + aviso + push, best-effort).
2. **Visibilidad:** se quita el filtro `id_reclamo_origen_auditoria IS NULL` de `publico_reclamos.py` (listado y detalle), `publico_portal.py` (`mi-resumen`) y `publico_reclamos_adjuntos.py`; el listado y el detalle públicos exponen `id_reclamo_origen_auditoria` + `origen_auditoria_nro`.
3. **La observación del auditor no le llega al vecino por ninguna vía:** la descripción del retrabajo y su primera entrada de historial la contienen (las necesita la cuadrilla en el backoffice), así que la API pública las **enmascara** para los retrabajos: la descripción que ve el vecino es la de su reclamo original, y la entrada «Reclamo ingresado por auditoría observada» se muestra como «Reclamo reabierto por control de calidad» con una nota genérica.
4. **Notificaciones:** `push.notificar_estado_reclamo` deja de saltear retrabajos (sigue salteando los estados `En auditoría`/`Auditado`); `encuestas_service.crear_envio_para_reclamo` encuesta al retrabajo y le saltea la anti-fatiga.
5. **Backoffice:** `AuditarModal` → al confirmar «Observar» abre el pop-up Sí/No; los dos cierran todo y disparan la mutación (resultado por toast, regla §23). La ficha distingue «Observada (con retrabajo)» / «Observada (sin retrabajo)». La mesa del auditor ya no muestra el SLA (el reclamo ya está resuelto).
6. **PWA `zaris-vecinos`:** el detalle de un retrabajo muestra «Reabierto por control de calidad del reclamo REC-…» con link al original.
7. **Smoke:** `smoke_auditoria_reclamos.py` con los casos 6b/6e/6f/10b invertidos, el camino «No», el mail capturado en MOCK, el enmascarado y la encuesta exenta de anti-fatiga.
8. **Docs:** skills `modulo-reclamos`/`modulo-ot`/`modulo-encuestas`, CLAUDE.md §21, `docs/contrato_api_publica.md`, este plan, manual de Reclamos/OT y guía QA.
9. **Demo:** los 32 retrabajos de prod quedan visibles solos y no reciben mail (el mail sale solo cuando un auditor elige «Sí» desde el backoffice; estos los insertó el generador, y sus vecinos son `example.com`/`vecino.gob.ar`/`vecinos-demo`, ninguno con cuenta en la app — verificado en prod). El generador demo ahora también encuesta los retrabajos resueltos (como `enviada`, nunca `pendiente`).
- **Frontend:** botón «Enviar a auditoría» en la ficha de un reclamo `Resuelto` (nivel ≤ 2) con modal; bloque «Auditoría» en la ficha (fechas, resultado, link al retrabajo o al reclamo auditado); mesa del auditor con «Aprobar / Observar» y columna «Resuelto el»; badges/filtros/BI con `Auditado`; el modal de cerrar OT ya no habla de auditoría previa.
- **Verificación:** smoke in-process `backend/smoke_auditoria_reclamos.py` (71 casos) + recorrido en navegador local.

## Definición de César (2026-10-19)

«En auditoría» no es un estado en proceso: la gestión se mide desde que se abre el
reclamo hasta que se cierra. La auditoría es posterior: se elige un reclamo ya cerrado,
se reabre y pasa a «En auditoría» como un pendiente; después pasa a «Auditado», que es
el nuevo cierre. **La cuenta de tiempos de gestión termina en el primer cierre.**

## Cómo es HOY (verificado en código y DB prod el 2026-10-19)

- La auditoría está ANTES del cierre: al terminar la OT operativa, si `tipo_reclamo.audit`
  es true el reclamo pasa a «En auditoría» y se crea una OT `es_auditoria`; al aprobarla
  pasa a «Resuelto» y recién ahí se fija `fecha_cierre`
  (`ordenes_trabajo.py::_post_cierre_ot_operativa`, `aprobar_ot`, `rechazar_ot`).
- Prod: 1 de 285 tipos con `audit`; 0 OT de auditoría reales; 1 reclamo «En auditoría»
  (#36, manual); 624 reclamos demo con paso por «En auditoría» en el historial (el
  generador simula un 25 %); 3 agentes `es_auditor`.
- Tocan el estado: FSM `reclamos.py` + `CambiarEstadoModal.tsx`, mesa de Auditoría de OT,
  BI (`bi.py` 13 refs, `bi_ejecutivo.py`; tiempos por `fecha_cierre`), encuesta CSAT (sale
  en «Resuelto»), push al vecino, generador demo, mapa del inicio (`ESTADO_COLOR`).

## Decisiones (César, 2026-10-19)

| Tema | Decisión |
|---|---|
| Nombre del cierre de gestión | **Se mantiene «Resuelto»**; se agrega solo «Auditado» |
| Selección de reclamos a auditar | **Solo manual** (no hay sorteo automático) |
| Auditoría desaprobada | **«Auditado» con resultado «observado» + reclamo NUEVO vinculado** para el retrabajo (los tiempos del original no se tocan) |
| Qué ve el vecino | **Nada**: sigue viendo «Resuelto», sin push ni segunda encuesta |

## Diseño propuesto (lo marcado *supuesto* falta confirmar)

```
Sin asignar → En gestión ⇄ En espera → Resuelto   ← fin del tiempo de gestión (fecha_cierre)
                                          │ (manual)
                                          ▼
                                    En auditoría → Auditado (aprobado | observado)
                                                        └─ observado: reclamo NUEVO vinculado, Sin asignar
```

1. Se quita la auditoría previa al cierre: cerrar la OT operativa lleva siempre a
   «Resuelto». `tipo_reclamo.audit` deja de usarse (la columna queda).
2. Acción «Enviar a auditoría» sobre un reclamo «Resuelto»: supervisor de la subárea del
   reclamo + admin *(supuesto)*. Crea la OT de auditoría (mesa del auditor como hoy).
3. Aprobar → «Auditado» / aprobado. Observar → «Auditado» / observado + reclamo nuevo
   (mismo vecino, tipo y dirección, canal «oficio», descripción con la observación del
   auditor *(supuesto)*). `fecha_cierre` no cambia nunca.
4. Vecino: los endpoints públicos muestran «Resuelto» para «En auditoría»/«Auditado».
5. Indicadores: «Reclamos activos» y los pendientes de gestión (inicio y Datos) excluyen
   «En auditoría» y «Auditado»; en el mapa del inicio «En auditoría» sigue en violeta
   como pendiente de auditoría *(supuesto)*.
6. Migración (número al aplicarla, hoy 112+): «Auditado» en `ck_reclamo_estado` y en
   `estado_reclamo`; columnas en `reclamos`: inicio/fin de auditoría, resultado, reclamo
   de origen. El #36 pasa a «Resuelto» con `fecha_cierre` = cuando entró a auditoría
   *(supuesto)*. El historial demo queda como está.

## Fases

- **F1 — backend:** migración (local + prod), FSM, endpoint de envío a auditoría,
  aprobar/observar, ocultamiento al vecino, semántica de indicadores, smoke con authz.
- **F2 — frontend:** botón «Enviar a auditoría», badge/filtros «Auditado», modal FSM,
  mesa del auditor («Aprobar / Observar»), leyenda del mapa.
- **F3 — generador demo + docs:** sin auditoría previa; % chico de auditorías
  posteriores (pendientes, aprobadas, observadas con su retrabajo); skill
  `modulo-reclamos` y CLAUDE.md.
