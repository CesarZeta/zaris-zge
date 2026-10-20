# Plan — Auditoría de reclamos POSTERIOR al cierre

> Estado: **diseño propuesto el 2026-10-19, esperando el OK de César para F1.** Sin código.

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
