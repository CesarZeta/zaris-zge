# Plan — Auditoría de reclamos POSTERIOR al cierre

> Estado: **F1 (backend + mig 112), F2 (frontend) y F3 (generador demo + backfill en prod) implementadas el 2026-10-20 y en prod** (`16ad409`, `a17bb6d`). Los puntos *supuesto* de abajo se aplicaron tal cual están escritos, más dos decisiones que el plan no cubría (ver «Cómo quedó»); César puede corregirlas. Falta solo la doc de usuario (manual/guía QA de Reclamos y OT).
>
> **F3 (2026-10-20):** `services/demo_datos.py` ya no simula la auditoría previa; sortea auditorías posteriores (~8 % de los resueltos, 1-10 días tras el cierre, revisión de 1-7 días, 80 % aprobada / 20 % observada con retrabajo de oficio) con su OT e historial, y `avanzar_pendientes` las envejece (cierra ~60 % de las pendientes por corrida, manda ~3 % de los resueltos recientes). Sobre la demo cargada antes de la mig 112 se corrió una vez `backend/backfill_auditorias_demo.py` en local y en prod (prod: 2.517 candidatos → 177 Auditado + 4 En auditoría, 32 retrabajos; snapshot `_backup_reclamos_auditoria_2026_10_20` con las 181 filas previas, RLS on).

## Cómo quedó (2026-10-20)

- **Backend:** `POST /reclamos/{id}/auditoria` (supervisor de la subárea del reclamo —fuente `agentes.id_subarea`— o admin; solo sobre `Resuelto`; crea la OT de auditoría, opcionalmente asignada a un auditor puntual) · `PUT /ot/{id}/aprobar` → reclamo `Auditado`/`aprobado` · `PUT /ot/{id}/observar` (alias deprecado `/rechazar`) → `Auditado`/`observado` + reclamo NUEVO de retrabajo (`id_reclamo_origen_auditoria`, canal `oficio`, descripción con la observación) · terminar la OT operativa siempre resuelve (`tipo_reclamo.audit` ya no se consulta) · `/estado` rechaza los dos estados de auditoría · editar/OT/subreclamo/cancelar/avisar bloqueados en `En auditoría`/`Auditado` · cancelar la OT de auditoría devuelve el reclamo a `Resuelto` · indicadores: activos/pendientes = `Sin asignar`/`En gestión`/`En espera`; resueltos del BI = `Resuelto`+`En auditoría`+`Auditado`; el mapa del inicio muestra `En auditoría` en violeta y no `Auditado`.
- **Decisiones no previstas en el plan:** (1) **el retrabajo es invisible para el vecino** (no se lista, su detalle da 404, no genera push, aviso ni encuesta): era la única forma de cumplir «el vecino no ve nada» con un reclamo nuevo a su nombre — **REVERTIDA por César el 2026-10-20 al aprobar el plan, ver «F4»**; (2) **una auditoría se puede cancelar** (OT de auditoría → `Cancelada`, por supervisión o el auditor asignado) y el reclamo vuelve a `Resuelto` — aceptada; (3) los **tiempos del BI** cuentan a `En auditoría`/`Auditado` como resueltos con su `fecha_cierre` original — aceptada.

## F4 — Retrabajo VISIBLE para el vecino + correo explicativo (decisión de César, 2026-10-20; sin código)

César al aprobar el plan: el vecino SÍ debe ver el reclamo nuevo que nace de una auditoría observada, y hay que informarle por correo electrónico por qué aparece un reclamo a su nombre: la revisión interna encontró fallas en el trabajo anterior y se reabrió el caso para resolverlo. «Dará mejor reputación a la gestión: el vecino percibe que hubo una acción.» Lo que sigue oculto para el vecino es la auditoría en sí (los estados `En auditoría`/`Auditado` del original se le muestran como `Resuelto`).

1. **Visibilidad:** quitar el filtro `id_reclamo_origen_auditoria IS NULL` de `publico_reclamos.py` (listado y detalle), `publico_portal.py` (`mi-resumen`) y `publico_reclamos_adjuntos.py`; agregar `origen_auditoria_nro` al detalle público para que la PWA pueda decir «Reabierto por auditoría del reclamo REC-…».
2. **Notificaciones:** `push.notificar_estado_reclamo` deja de saltear retrabajos (sus cambios de estado avisan como cualquier reclamo). Encuesta CSAT al resolver el retrabajo: **a decidir** (propuesta: sí; la anti-fatiga de 30 días ya evita la doble encuesta).
3. **Correo al crear el retrabajo** (en `observar_ot`, post-commit y best-effort como el push): `services/email.enviar_mail` con la explicación, el número nuevo y el link al portal (`core/urls.url_portal_vecino`), más aviso en la bandeja (`registrar_aviso_ciudadano`) y push. Redacción a validar con César antes de salir. Verificar el link del mail con `curl` en prod (regla §5).
4. **Smoke:** invertir los casos 6b/6e/10b de `smoke_auditoria_reclamos.py` y capturar el mail en MOCK (patrón `smoke_cuentas_funcionario.py`).
5. **Docs:** skill `modulo-reclamos` (bullet «Para el vecino…»), CLAUDE.md §21, este plan.
6. **Demo:** los 32 retrabajos de prod quedan visibles solos; no se les manda mail (vecinos `@vecinos-demo`). El generador no cambia.
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
