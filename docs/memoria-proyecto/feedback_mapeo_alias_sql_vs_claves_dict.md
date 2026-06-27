---
name: feedback_mapeo_alias_sql_vs_claves_dict
description: "Cuando un helper devuelve un dict con claves largas, no hacer spread directo al dict de parámetros SQL si los alias del query son distintos."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a7c9f3f5-4bea-4684-80ad-901fdeac887e
---

Nunca hacer `**helper_dict` en el dict de parámetros de `text()` cuando las claves del dict no coinciden exactamente con los `:alias` del SQL.

**Why:** `resolver_iniciador` devuelve `{id_ciudadano_iniciador, id_empresa_iniciadora, id_ciudadano_representante, id_subarea_iniciadora}` pero el INSERT usaba `:cid`, `:eid`, `:crep`, `:sub_ini`. SQLAlchemy lanza `InvalidRequestError: A value is required for bind parameter 'cid'` — error no obvio porque el spread sí pasa datos, simplemente con nombres incorrectos. El 500 no menciona el alias esperado hasta mirar el traceback completo.

**How to apply:** siempre mapear explícitamente cuando los nombres del helper y del SQL divergen:

```python
# Mal — falla si las claves del helper no coinciden con los :alias del SQL
{**iniciador_fks, "ag_ini": agente["id_agente"]}

# Bien — mapeo explícito aunque sea más verboso
{
    "cid":     iniciador_fks.get("id_ciudadano_iniciador"),
    "eid":     iniciador_fks.get("id_empresa_iniciadora"),
    "crep":    iniciador_fks.get("id_ciudadano_representante"),
    "sub_ini": iniciador_fks.get("id_subarea_iniciadora"),
    "ag_ini":  agente["id_agente"],
}
```

Alternativa: alinear los alias del SQL con las claves del helper (usar `:id_ciudadano_iniciador` en el SQL). Ambas son válidas; lo que no funciona es mezclar nombres sin el mapeo.

Caso real: `POST /api/v1/tramites` Fase 2, 2026-05-16.
