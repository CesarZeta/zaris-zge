# Plan — Refactor CLAUDE.md → skills on-demand

> **Objetivo:** mover la referencia por módulo de `CLAUDE.md` a skills que cargan on-demand, dejando en `CLAUDE.md` solo las reglas transversales (always-on). Reducir el tamaño del archivo sin perder garantías ni romper refs cruzadas.
>
> **Principio rector:** lo que aplica *toques lo que toques* queda en CLAUDE.md. Lo que solo importa al trabajar UN módulo va a una skill.

## Estado de fases

- **Fase 0 (inventario + plan):** ✅ completada — commit `b1f8117`.
- **Fase 1 (piloto §44 Emergencias):** ✅ **migrado** — skill `modulo-emergencias` creada, puntero en CLAUDE.md, ancla `## 44.` conservada. CLAUDE.md 1992→1981 líneas. **Pendiente: validación manual del usuario (auto-invocación en sesión nueva).**
- **Fase 2 (replicar):** en curso. Piloto validado (auto-invocó en sesión nueva). Bloque 1 (§42, §43, §34) migrado. CLAUDE.md 1981→1814 líneas.

## Reglas inviolables del refactor

1. **No renumerar secciones.** Cada sección movida conserva su ancla `## N. <título>` en CLAUDE.md, reemplazada por un puntero. `(§44)` debe seguir resolviendo.
2. **No tocar las secciones "QUEDA".**
3. **No `git push`** — commits por fase, push lo hace el usuario.
4. **No borrar nada fuera de lo planificado.** El cuerpo movido se traslada íntegro a la skill (no se recorta).
5. **Un commit por unidad de trabajo.**
6. **STOP en cada checkpoint** marcado, reportar y esperar OK.

## Métrica base

- `CLAUDE.md` actual: **1992 líneas**.
- Total de ocurrencias `§N` en archivos `.md` apuntando a secciones que se mueven: **216** (todas siguen resolviendo porque el ancla `## N.` se conserva — **0 refs rotas esperadas**).

---

## Clasificación (validada leyendo el archivo completo)

### QUEDA en CLAUDE.md (transversal — always-on)

| § | Título | Por qué queda |
|---|---|---|
| §1 | Autenticación JWT (SSO) | Aplica a todo endpoint/módulo. |
| §2 | Base Única de Ciudadanos (BUC) | Regla de modelo de datos para cualquier módulo con personas. |
| §3 | Roles y Permisos | `nivel_acceso` lo usa todo endpoint. |
| §4 | Stack Tecnológico | Define shell único, stacks, mapas, tipografía — base de todo. |
| §5 | Convenciones de Código | SQL/API/timestamps/quirks de columnas/orden de routers — transversal. |
| §6 | URLs del Proyecto | Tabla de entornos — referencia constante. |
| §7 | Workflow de Desarrollo | Gate typecheck, push solo a pedido — transversal. |
| §9 | Deploy Railway | Verificar prod tras push backend — transversal. |
| §10 | Campos Estándar por Tabla | Toda tabla nueva. |
| §11 | Horario en Tablas de Servicio | Convención de schema. |
| §12 | Agregar un módulo React al producto | Reglas que TODO módulo React debe respetar (router, API base, sesión, iframe). |
| §13 | Design System Visual | Obligatorio para toda UI. |
| §14 | Shell del producto — iframe único | Reglas de iframe/guard/navegación — todo módulo. |
| §17 | Slash Commands del Proyecto | Índice de comandos. |
| §19 | Patrón de Baja Lógica | Patrón transversal API+frontend. |
| §20 | Modelos SQLAlchemy — Stubs | Aplica a cualquier modelo nuevo con FK. |
| §21 | Estado de Migraciones en Prod | Reglas vivas de migración + índice "dónde vive cada mig" (apunta a las secciones de módulo). |
| §23 | Patrones de UI ya validados | Defaults de UI para cualquier form/listado. |
| §24 | Workflow de seed desde CSVs | Regla crítica: verificar prod con `execute_sql` (todo backend). |
| §28 | Recibir prompts armados afuera | Checklist transversal de validación. |
| §29 | Patrones de la web-app React | Auth/storage/diagnóstico/forms — cualquier módulo React. |
| §31 | Limpieza de estilos legacy (CERRADA) | Corta; reglas de estilo legacy transversales. |
| §32 | Build de web-app/dist | Ya es puntero a skill `win-quirks` + reglas always-on. |
| §40 | Reportes vs guías de QA | Política de versionado — transversal. |
| §45 | Hilo conductor común ESTADO.md | Proceso de colaboración — transversal. |

### A SKILL (referencia por módulo — on-demand)

| § | Título | Skill | Refs entrantes (total / interna CLAUDE.md / externa otros .md) | Estado |
|---|---|---|---|---|
| §44 | Módulo Emergencias (COM) | `modulo-emergencias` | 7 / 5 / 2 | **PILOTO — migrado** ✅ |
| §42 | Módulo Encuestas (CSAT) | `modulo-encuestas` | 18 / 8 / 10 | **migrado** ✅ |
| §43 | Módulo Datos (BI) | `modulo-bi` | 5 / 2 / 3 | **migrado** ✅ |
| §39 | Módulo Usuarios | `modulo-usuarios` | 11 / 5 / 6 | propuesto |
| §41 | Módulo Config (React) | `modulo-config` | 10 / 2 / 8 | propuesto |
| §37 | Módulo Guías | `modulo-guias` | 6 / 6 / 0 | propuesto |
| §36 | Generación de manuales | (ver nota↓) | 4 / 2 / 2 | propuesto |
| §34 | Módulo OT | `modulo-ot` | 5 / 2 / 3 | **migrado** ✅ |
| §33 | Módulos Turnos y Entradas | `modulo-turnos-entradas` | 17 / 7 / 10 | propuesto |
| §35 | Módulo Trámites / Expedientes | `modulo-tramites` | 33 / 6 / 27 | propuesto |
| §38 | Auth público de ciudadanos (App Vecinos) | `modulo-app-vecinos` | 23 / 8 / 15 | propuesto |
| §30 | Permisos por módulo | `modulo-permisos` | 18 / 3 / 15 | propuesto |
| §27 | Módulo Agenda | `modulo-agenda` | 26 / 14 / 12 | propuesto |
| §26 | Adjuntos de Reclamos (Storage) | `modulo-reclamos` (junto con §18/§22) | 12 / 6 / 6 | propuesto |
| §22 | Geolocalización, Activos y Adjuntos | `modulo-reclamos` | 8 / 4 / 4 | propuesto |
| §18 | Módulo Reclamos | `modulo-reclamos` | 6 / 1 / 5 | propuesto |
| §15 | Admin Tablas — CRUD Genérico | (ver nota↓ — split) | 7 / 3 / 4 | propuesto |

**Notas de criterio (discrepancias / matices vs la propuesta original):**

- **§15 — split, no mover entero.** §15 mezcla dos naturalezas:
  - *Transversal (QUEDA):* el "Estándar visual obligatorio — panel de búsqueda" aplica a **todo** frontend de tabla maestra, no solo a admin_tablas. Esto se queda en CLAUDE.md (o se absorbe en §23 que ya es "patrones de UI validados").
  - *Referencia del módulo (→ skill `modulo-admin-tablas`):* el procedimiento "Agregar una tabla nueva" (`TABLE_CONFIG`, pasos backend/frontend/shell), las "Tablas actualmente configuradas" y las reglas de forms inline (`agentes`/`equipos`/`tipo_grupo`). A confirmar en Fase 2 el corte exacto.

- **§18 + §22 + §26 → una sola skill `modulo-reclamos`.** Son el mismo módulo (Reclamos: tablas/estados/endpoints + geo/activos/adjuntos + storage). Tres anclas conservadas (`## 18.`, `## 22.`, `## 26.`), tres punteros, un solo SKILL.md. Evita fragmentar el contexto del módulo más referenciado por otros.

- **§36 (Generación de manuales) — ya tiene skill `generar-manual`.** El cuerpo de §36 son *reglas de criterio* (sin fechas/nombres, manual como entregable, una sola fuente) + el inventario de manuales. La receta mecánica ya vive en la skill `generar-manual`. Opción A: dejar §36 como puntero a `generar-manual` (igual que §32→win-quirks) moviendo el inventario ahí. Opción B: skill nueva `modulo-guias` que absorba §36+§37. **Recomendación:** fusionar §36+§37 en `modulo-guias` (Guías es el front-end de los manuales; van juntos) y que `generar-manual` (existente) siga siendo la receta de generación. A confirmar en Fase 2.

- **§27 (Agenda) y §35 (Trámites) son sustratos muy referenciados** (26 y 33 refs). Mover su cuerpo a skill es correcto — las refs apuntan a sub-conceptos (`disponibilidad_efectiva`, `equipo_agentes`, destinatario polimórfico) que el puntero + ancla resuelven. NO son always-on: solo se necesita el detalle al tocar ese módulo. El riesgo es bajo porque las refs son de lectura cruzada, no de carga obligatoria.

### A HOOK (fuera de alcance de este refactor — pendiente anotado)

Mecanizable por script (no se hace ahora):
- Grep de secrets/passwords en texto plano (§1).
- Patrones prohibidos: `createBrowserRouter` (§12), hex hardcodeado en vez de tokens DS (§13).

### A SUBAGENTE (fuera de alcance — pendiente anotado)

- Un `qa-reviewer` que corra `/audit-shell` + verificación en interfaz (§41) + reporte QA (§40).

---

## Archivos que referencian secciones a mover (refs que NO se rompen)

Todas estas refs siguen resolviendo porque el ancla `## N.` se conserva en CLAUDE.md. Lista de fuentes externas (fuera de CLAUDE.md):

- **Planes / docs raíz:** `ESTADO.md`, `HISTORIAL_MIGRACIONES.md`, `ONBOARDING.md`, `PLAN_APP_VECINOS.md`, `PLAN_MODULO_EMERGENCIAS.md`, `docs/contrato_api_publica.md`.
- **Skills existentes:** `.claude/skills/estado-proyecto/`, `.claude/skills/nuevo-modulo-react/`, `.claude/skills/win-quirks/`.
- **Commands:** `.claude/commands/audit-shell.md`, `check-api-health.md`, `migrate-vanilla-to-react.md`, `seed-table.md`.
- **Memorias (`docs/memoria-proyecto/`):** ~20 archivos `feedback_*` y `project_*` (Trámites, Turnos, notificaciones, usuario-vs-ciudadano, etc.).

---

## Módulo piloto

**§44 Emergencias (COM).** Motivos:
- **Cerrado/estable:** Fases 1-5 CERRADAS, en prod, verificado por navegador.
- **Cuerpo bien acotado y autocontenido** (~13 líneas densas de bullets, líneas 1965–1978): DB, FSM, denunciante, permisos, frontend, endpoint público, smoke.
- **`description` fácil de calibrar:** archivos concretos (`routes/emergencias.py`, `web-app/src/modules/emergencias/`, `publico_emergencias.py`), tablas claras (`emergencia_*`), entidades (eventos, contactos eventuales, log append-only).
- **Pocas refs entrantes (7)** → bajo riesgo si algo sale mal.

(§42 Encuestas era el otro candidato; más largo. Se deja para Fase 2 una vez validada la mecánica.)

---

## Orden de migración (Fase 2+)

Primero los CERRADOS/ENTREGADOS, después los activos. STOP cada 3 módulos para reportar progreso y tamaño del archivo.

1. **(Piloto)** §44 Emergencias → `modulo-emergencias`
2. §42 Encuestas → `modulo-encuestas`
3. §43 BI → `modulo-bi`
4. §34 OT → `modulo-ot`
5. §39 Usuarios → `modulo-usuarios`
6. §41 Config → `modulo-config`
7. §33 Turnos/Entradas → `modulo-turnos-entradas`
8. §35 Trámites → `modulo-tramites`
9. §38 App Vecinos → `modulo-app-vecinos`
10. §30 Permisos → `modulo-permisos`
11. §27 Agenda → `modulo-agenda`
12. §18+§22+§26 Reclamos → `modulo-reclamos`
13. §15 Admin Tablas (split) → `modulo-admin-tablas`
14. §36+§37 Manuales/Guías → `modulo-guias` (coordinar con skill `generar-manual` existente)
