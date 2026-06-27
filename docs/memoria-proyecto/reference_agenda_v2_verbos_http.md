---
name: Verbos HTTP del router agenda_v2 — leer @router decorators antes de scriptear
description: Los endpoints de cancelar/asistio/resolver del router agenda_v2 son PATCH, no PUT. Antes de scriptear un smoke test, leer los @router decorators del archivo de rutas.
type: reference
---
El router `backend/app/api/routes/agenda_v2.py` usa verbos HTTP que no son obvios. Antes de scriptear cualquier smoke test contra el módulo Agenda, leer los `@router.get/post/put/patch/delete` del archivo.

**When to use:** al escribir un script (PowerShell, bash, Python) que llame a `/api/v1/agenda/*`, o al implementar un cliente nuevo en otro frontend.

**Mapeo verbos al 2026-05-11:**

| Acción | Verbo | Path |
|---|---|---|
| Crear evento | POST | `/eventos` |
| Editar evento (full) | PUT | `/eventos/{id}` |
| Cancelar evento | **PATCH** | `/eventos/{id}/cancelar` |
| Asignar encargado | POST | `/eventos/{id}/encargados` |
| Crear reserva | POST | `/eventos/{id}/reservas` |
| Marcar asistio | **PATCH** | `/reservas/{id}/asistio` |
| Cancelar reserva | **PATCH** | `/reservas/{id}/cancelar` |
| Calendario día | GET | `/calendario` (NO `/calendario/dia`) |
| Calendario mes | GET | `/mes` |
| Resolver conflicto | **PATCH** | `/conflictos/{id}/resolver` |

**How to apply:** primer paso siempre debe ser `grep "@router\." backend/app/api/routes/agenda_v2.py` para confirmar verbos y paths actuales. La doc de PRUEBAS_PENDIENTES.md y los hooks de la web-app NO son fuente autoritativa — el router lo es.

Smoke test reproducible: `smoke_agenda.ps1` en la raíz del repo.
