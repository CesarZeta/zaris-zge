---
name: project_tramites_destinatario_agente_y_mi_bandeja
description: "Trámites ahora soportan destinatario directo a un agente + vista \"Mi bandeja\" con pases inline."
metadata: 
  node_type: memory
  type: project
  originSessionId: 0b8be9a0-524a-471e-b26d-759866001799
---

Sesión 2026-05-27. Dos features sobre el módulo Trámites (§35).

**Destinatario directo = agente (mig 66, local+prod):**
- `tramite.id_agente_actual` (FK agentes). `destinatario_actual_tipo` ahora ∈ `subarea|equipo|agente`. CHECK `ck_tramite_destinatario` tiene 4 ramas (NULL/subarea/equipo/agente), exactamente una FK por tipo.
- Pasar a un agente lo asigna a ESA persona (aparece en su bandeja, nadie más lo toma). Modelo fiel a Mesa Digital (origin/destination con tipo user|area|subarea|group). PDFs de referencia en `C:\Users\Cesar\Google Drive\DATAWORK\MVL\Innovación\Mesa Digital\`.
- Mesa = `equipos` existente (no se creó concepto nuevo).
- Tocados para soportar 'agente': `services/tramites/auth.py` (pertenece_al_colectivo + puede_tomar), `services/notificaciones.py` (_datos_tramite COALESCE de las 3 FKs + dispatcher _resolver_destinatarios_usuarios), y el UPDATE de `transicionar_tramite` (que ahora setea id_agente_actual; antes lo omitía → habría violado el CHECK al cambiar de agente a subárea).

**Mi bandeja:**
- `GET /api/v1/tramites/mi-bandeja`: resuelve server-side los colectivos del agente (mi subárea + mis equipos + asignado-a-mí + tomado-por-mí). El `GET /tramites` general NO puede expresar "cualquiera de mis colectivos" (solo filtra destinatario_tipo+id único). El tab "Mis trámites" de `BandejaTramites` mandaba `mis_tramites:true` que el backend IGNORA — esa vista nunca filtró bien; la real es mi-bandeja.
- `GET /api/v1/tramites/destinatarios?q=`: opciones de pase (agentes/equipos/subáreas). Quirk asyncpg: `:q IS NULL` da AmbiguousParameterError → usar `CAST(:q AS text) IS NULL`. Familia de [[feedback_asyncpg_extract_cast_date]].
- Ambos registrados ANTES de `/{numero_o_id}` (param greedy, §5).
- Frontend: pág `MiBandeja.tsx` = tab nuevo en `TramitesLayout` (no ítem de sidebar nuevo — comparte módulo/permiso `tramites`). `ModalPase` ampliado a 3 tabs (Agente/Mesa/Subárea) con buscador sobre `/destinatarios`.

**Fix colateral:** `ModalShell` (admin tipos de trámite) no scrolleaba — body sin `overflow-y`. Fix: body `flex:1 + minHeight:0 + overflowY:auto`. Aplica a los 6 modales admin.

Verificado: smoke backend local (pase a agente OK, mi-bandeja por colectivo OK) + navegación browser (3 tabs del modal pueblan). Prod: endpoints viven (openapi) pero el smoke autenticado no se corrió (no tengo el pass del admin prod, ver [[reference_login_email_prod_no_es_patron_doc]]).
