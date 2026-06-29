# ESTADO — zaris-zge (backoffice + backend)

> **Hilo conductor común Cesar ↔ Roy.** Este archivo es la **fuente de verdad compartida y versionada** del estado de avance. Es lo PRIMERO que se lee al retomar y lo que se ACTUALIZA al cerrar cada sesión (regla CLAUDE.md §45). Es un documento **vivo y corto** — foto del estado actual, NO bitácora histórica (esa vive en [`HISTORIAL_MIGRACIONES.md`](HISTORIAL_MIGRACIONES.md) y, para Cesar, en su memoria privada de Claude Code).
>
> **Reglas de mantenimiento:**
> - Actualizar al cerrar sesión (la skill `/cierre-sesion` lo hace antes de tocar la memoria privada).
> - "En curso" y "Pendientes" reflejan lo REAL — si terminás algo, movelo a "Hecho reciente" (y podá lo viejo de ahí: máx ~10 líneas).
> - Convertir fechas relativas a absolutas.
> - Verificar contra git/prod antes de declarar algo hecho (`feedback_verificar_siempre_antes_de_opinar`).
> - La PWA App Vecinos tiene su **propio** `ESTADO.md` en el repo `zaris-vecinos`. Acá va solo backoffice/backend.

**Última actualización:** 2026-06-29 (Cesar) · rama `main` — sesión "roles por nivel" (Fase 1+2)

---

## 🔵 En curso

_(nada en curso ahora mismo — backoffice estable, todo lo abierto es de la PWA, ver su ESTADO.md)_

---

## 🟠 Pendientes (backoffice / backend)

> El grueso del trabajo abierto del proyecto hoy está en la **PWA** (ver `zaris-vecinos/ESTADO.md` → Etapa G). Acá quedan solo cosas de backoffice/infra.

- **🟠 Fase 3 roles — UX de supervisión (NO empezada).** Las vistas de gestión (OT / Gestión de Turnos / Gestión de Trámites) deben dar al supervisor: ver lo de su **subárea + agentes a cargo**, y **búsqueda por número** individual *y* por **rango desde/hasta** (y/o fechas) para trabajar desde el listado. Falta definir con el usuario el modelo "supervisor→agentes" (¿por subárea compartida, o relación explícita?) — quedó pendiente de una `AskUserQuestion` que no se respondió. Es el pedido original de la sesión que todavía no se atacó.
- **🟠 Fase 3 — "Avisar al supervisor" desde Reclamos (NO empezada).** El operador (nivel 3) ya NO cambia estado de reclamos (Fase 1); falta darle la acción de **generar un aviso/notificación al supervisor** de la subárea para que gestione el cambio. Funcionalidad nueva (usa el sistema de notificaciones in-app/email, mig 51).
- **🟡 BI Ejecutivo** — pendiente de PRODUCTO. El usuario define las visualizaciones (como hizo con el Operativo); NO inventarlas. Tarjeta "Ejecutivo" en `DatosLanding.tsx` es placeholder. (CLAUDE.md §43.)
- **🟡 Barrido visual modo oscuro** de módulos React restantes. Solo Dashboard y Guías verificados en dark. Literales claros conocidos (1 c/u): `bi/views/{Resumen,Resueltos,Pendientes,Subreclamos}View.tsx`, `emergencias/pages/Recepcion.tsx`, `config/views/IdentidadView.tsx` → reemplazar por tokens/`--surface-overlay` cuando se los vea en dark. Vanilla (admin_tablas/usuarios) tienen el bootstrap pero sin verificación visual dark.
- **🟢 Higiene (requiere al usuario, no se puede desde Claude Code):** rotar `DISPATCHER_TOKEN` (visible en historial git): valor nuevo → Railway env var → GitHub secret (lo usan 3 crons: encuestas, trámites, integridad) → borrar el secret sobrante `ZARIS_DISPATCHER_TOKEN`.

---

## ✅ Hecho reciente (últimas sesiones)

- **2026-06-29** — **Sidebar reagrupado por rol + permisos finos (Fase 1+2, en prod).** Modelo de roles según nivel: 🟢 Atención (n3) · 🟣 Supervisión (n2) · 🔵 Común · ⚫ Administración (n1). Cambios:
  - Niveles en tabla `modulos` (local+prod): `reclamos` 1→**3** (ahora lo ve el operador), `bi`(Datos)+`encuestas` 2→**1** (solo admin). Sidebar vanilla (`index.html`) + React (`shell/Sidebar`) con secciones `.nav-flat__section`; `menu.js` oculta secciones vacías por permisos (`d266dc0`/`68356a2`).
  - **Reclamos: el operador NO cambia estado** — guard `_require_supervisor` (nivel ≤2) en `PUT /reclamos/{id}/estado`, `/cancelar`, `POST /subreclamo` (`reclamos.py`). El operador crea/consulta/edita datos+observaciones+adjuntos; el cambio de estado es Supervisión (la gestión = Órdenes de Trabajo). UI `DetailView.tsx` espeja (Editar vs acciones de estado). Smoke: op→403, sup→200.
  - **Fase 2:** ítems "Gestión de Turnos" → vista nueva `MisTurnos.tsx` (`/turnos/mis-turnos`, tabs Pendientes/Hoy/Todos, scopeada por backend) y "Gestión de Trámites" → `/tramites/mi-bandeja` (reusa lo existente). NO hay "Gestión de Reclamos" (= OT). (`d823bd0`.)
  - **Bugfix:** `/tramites/mi-bandeja` daba 500 (`AmbiguousParameterError` en `:mun IS NULL`) → `CAST(:mun AS integer)` (`327e863`, en prod, verificado 200). Quedó expuesto al darle entrada directa desde el sidebar; bug latente previo.
- **2026-06-29** — **Refactor `CLAUDE.md` → skills on-demand** (`b1f8117`…`9cb4c8f`). Detalle por módulo (§15/18/22/26/27/30/33/34/35/36/37/38/39/41/42/43/44) → **14 skills `.claude/skills/modulo-*`**. CLAUDE.md 1992→1024 líneas. Anclas `## N.` y refs `§N` se conservan. Plan en `PLAN_REFACTOR_SKILLS.md`.
- **2026-06-27** — Mail de confirmación al crear reclamo del vecino (`a4ab19d`, prod, verificado). Onboarding de Roy. Etapa G de la PWA en `PLAN_APP_VECINOS.md` (`f4ad557`).
- **2026-06-13** — Recovery de credenciales usuarios internos (mig 90) + 6 catálogos Emergencias en Maestros + filtros FK en admin_tablas (`5d81080`, prod).
- **2026-06-12** — Shell: menú de usuario + foto de perfil (mig 88) + modo oscuro + statusbar inferior. Revisión integral de Agenda (mig 89/91).

> Detalle histórico completo: `HISTORIAL_MIGRACIONES.md` + tabla "Histórico breve" de la bitácora.

---

## 🔗 Mapa de fuentes de verdad (para no buscar a ciegas)

| Querés saber… | Mirá… |
|---|---|
| Reglas de cómo se trabaja (mandatorias, transversales) | [`CLAUDE.md`](CLAUDE.md) |
| Detalle de UN módulo (tablas/endpoints/FSM/quirks) | la skill `.claude/skills/modulo-<nombre>/` — carga sola al tocar ese módulo (ver `PLAN_REFACTOR_SKILLS.md`) |
| Estado de avance / pendientes HOY (backoffice) | **este archivo** |
| Estado de avance / pendientes HOY (PWA) | `zaris-vecinos/ESTADO.md` |
| Roadmap detallado de la App Vecinos | [`PLAN_APP_VECINOS.md`](PLAN_APP_VECINOS.md) |
| Roadmap detallado de Emergencias | [`PLAN_MODULO_EMERGENCIAS.md`](PLAN_MODULO_EMERGENCIAS.md) |
| Qué migración hace qué / cuándo se aplicó | [`HISTORIAL_MIGRACIONES.md`](HISTORIAL_MIGRACIONES.md) |
| Contrato de la API pública que consume la PWA | [`docs/contrato_api_publica.md`](docs/contrato_api_publica.md) |
| Cómo arrancar local / colaborar | [`ONBOARDING.md`](ONBOARDING.md) · [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Quirks/patrones/decisiones (foto de las memorias) | [`docs/memoria-proyecto/`](docs/memoria-proyecto/) |
