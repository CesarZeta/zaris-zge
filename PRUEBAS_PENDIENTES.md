# Pruebas — Estado y referencias

> **Este documento ya no es un checklist vivo.** Desde la sesión 2026-05-11 las pruebas
> se cierran via reportes QA formales con la convención del slash command
> `/qa-report-template` (`reporte_pruebas_<bloque>_YYYY-MM-DD.md` en la raíz del repo).
>
> Lo que sigue es un índice histórico + el listado original a modo de archivo. No marcar
> casos acá — generar un reporte QA nuevo si vas a correr una tanda de pruebas.

## URLs y arranque local

- **Local API:** http://127.0.0.1:8000 — Swagger: http://127.0.0.1:8000/docs
- **Local web-app React standalone:** http://localhost:5173
- **Local shell vanilla + bundle embebido:** http://localhost:8080
- **Prod API:** https://zaris-api-production-bf0b.up.railway.app
- **Prod shell:** https://cesarzeta.github.io/zaris-zge/index.html

```powershell
# Backend (desde backend/)
$env:ENV_FILE=".env.local"; uvicorn app.main:app --host 127.0.0.1 --port 8000

# Shell vanilla + módulos React embebidos (desde la raíz)
python -m http.server 8080

# Web-app React standalone (solo dev, desde web-app/)
pnpm dev
```

Credenciales dev: `ciudadanovl@municipio.gob.ar` / `123456` (admin nivel 1).

## Reportes QA históricos

| Fecha | Bloque | Archivo | Resumen |
|---|---|---|---|
| 2026-05-11 | A — Agenda React (Fase 3.A + 3.B) | [reporte_pruebas_bloque_A_2026-05-11.md](reporte_pruebas_bloque_A_2026-05-11.md) | ~70 casos, 0 FAIL |
| 2026-05-11 | D + C — OTs vanilla + Reclamos vanilla | [reporte_pruebas_bloques_D_y_C_2026-05-11.md](reporte_pruebas_bloques_D_y_C_2026-05-11.md) | 22 casos, 0 FAIL |
| 2026-05-11 | Multi-bloque (prod, Antigravity Browser) | [reporte_pruebas_2026-05-11.md](reporte_pruebas_2026-05-11.md) | 94 casos, 25 PASS / 4 FAIL / 68 bloqueados por servicios down |

## Bloques originalmente planificados

| Bloque | Origen | Total casos | Estado |
|---|---|---|---|
| A. Módulo Agenda (React) | Fase 3.A | 47 | Cerrado en reportes 2026-05-11 |
| B. Login con usuarios nuevos (prod) | seed 2026-05-10 | 8 | Parcial — 2 FAIL en multi-bloque |
| C. Módulo Reclamos | Fases 1-3 reclamos vanilla | 22 | Cerrado vanilla 2026-05-11. **Módulo migrado a React 2026-05-12** — re-testear si hay cambios |
| D. Módulo OT (3 mesas vanilla) | OT V1 | 11 | Cerrado en reporte D+C |
| E. Admin tablas — drill-down inline | sub-fase admin | 6 | 5/6 PASS en multi-bloque |
| F. Breadcrumb + accesos | migración DS | 10 | 10/10 PASS en multi-bloque |
| G. Topbar y sesión | shell | 4 | 4/4 PASS en multi-bloque |

## Cómo correr una tanda de pruebas nueva

1. Decidir el bloque y los casos a cubrir.
2. Generar el reporte siguiendo `/qa-report-template` — archivo `reporte_pruebas_<bloque>_YYYY-MM-DD.md` en la raíz.
3. Bugs detectados → IDs con prefijo `BUG-<bloque>-NNN` o `OBS-<bloque>-NNN`.
4. Actualizar memoria `project_estado_sesion_y_pendientes.md` con bugs sin resolver.

---

## Archivo histórico — checklist original (2026-05-10)

Conservado como referencia de qué se planificó originalmente. No marcar `[x]` acá —
los resultados ya están en los reportes formales arriba listados.

<details>
<summary>Ver checklist completo de 108 casos originales</summary>

> El contenido original con todos los casos sin marcar quedó preservado en git history
> (último commit con el detalle: `d9e4e43` y anteriores). Si necesitás recuperar un caso
> específico para volver a probarlo:
>
> ```bash
> git show d9e4e43:PRUEBAS_PENDIENTES.md
> ```
>
> O directamente generar un reporte nuevo de QA con los casos que importan hoy — la lista
> original incluye módulos que ya fueron migrados a React (Reclamos, BUC), donde los IDs
> de casos vanilla pueden no aplicar tal cual.

</details>
