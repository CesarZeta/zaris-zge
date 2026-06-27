---
name: agenda-semana-disponibilidad-key
description: "El response GET /api/v1/agenda/semana devuelve disponibilidad_por_recurso con clave formato \"tipo:id\" (con dos puntos), no \"tipo-id\" con guion. Confundirlo no rompe — silenciosamente no encuentra disponibilidad."
metadata: 
  node_type: memory
  type: reference
  originSessionId: ba8c5bce-d171-4427-a27f-16245ac2b25e
---

Shape exacto del response `GET /api/v1/agenda/semana`:

```jsonc
{
  "desde": "2026-05-13",
  "hasta": "2026-05-19",
  "id_municipio": 1,
  "recursos": [ { "tipo": "agente", "id_recurso": 1, "nombre": "..." }, ... ],
  "dias": [
    {
      "fecha": "2026-05-13",
      "ocupaciones": [...],
      "ausencias": [...],
      "eventos": [...],
      "disponibilidad_por_recurso": {
        "agente:1": [ { "hora_inicio": "09:00:00", "hora_fin": "17:00:00", "etiqueta": null }, ... ],
        "agente:2": [...],
        "equipo:5": [...],
        "espacio:3": [...]
      }
    },
    ...
  ]
}
```

Clave del dict: **`"{tipo}:{id}"` con dos puntos**, no `"{tipo}-{id}"` con guion ni `"{tipo}_{id}"` con guion bajo. Fuente: `backend/app/api/routes/agenda_v2.py:1491` — `key = f"{rec['tipo']}:{rec['id_recurso']}"`.

**Riesgo silencioso:** si el frontend arma la clave con guion (siguiendo la convención de `useDroppable` que sí usa `row-${tipo}-${id}`), `disp[mykey]` devuelve `undefined`, `?? []` lo silencia, y la grilla pinta toda la fila como "fuera de horario" sin error. Caso real: el formato fue confirmado leyendo el código del backend antes de implementar `WeeklyDayCell` en `web-app/src/modules/agenda/views/WeeklyView.tsx` — pero hubiera sido fácil errarle.

**Cómo aplicar:** cuando consumas `/semana`, armá la clave **exactamente** así:
```ts
const key = `${rec.tipo}:${rec.id_recurso}`
const rangos = dia.disponibilidad_por_recurso[key] ?? []
```

Si en una sesión futura se unifica el formato (ej. todo el módulo usa guion), hay que cambiar el backend en `agenda_v2.py:1491` **y** todos los consumers a la vez.

Relacionado: [[reference_agenda_v2_verbos_http]], [[project_agenda_espacios_disponibilidad]].
