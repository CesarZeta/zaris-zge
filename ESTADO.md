# ESTADO — zaris-zge (backoffice + backend)

> **Hilo conductor común Cesar ↔ Roy.** Este archivo es la **fuente de verdad compartida y versionada** del estado de avance. Es lo PRIMERO que se lee al retomar y lo que se ACTUALIZA al cerrar cada sesión (regla CLAUDE.md §45). Es un documento **vivo y corto** — foto del estado actual, NO bitácora histórica (esa vive en [`HISTORIAL_MIGRACIONES.md`](HISTORIAL_MIGRACIONES.md) y, para Cesar, en su memoria privada de Claude Code).
>
> **Reglas de mantenimiento:**
> - Actualizar al cerrar sesión (la skill `/cierre-sesion` lo hace antes de tocar la memoria privada).
> - "En curso" y "Pendientes" reflejan lo REAL — si terminás algo, movelo a "Hecho reciente" (y podá lo viejo de ahí: máx ~10 líneas).
> - Convertir fechas relativas a absolutas.
> - Verificar contra git/prod antes de declarar algo hecho (`feedback_verificar_siempre_antes_de_opinar`).
> - La PWA App Vecinos tiene su **propio** `ESTADO.md` en el repo `zaris-vecinos`. Acá va solo backoffice/backend.

**Última actualización:** 2026-06-29 (Cesar) · rama `main`

---

## 🔵 En curso

_(nada en curso ahora mismo — backoffice estable, todo lo abierto es de la PWA, ver su ESTADO.md)_

---

## 🟠 Pendientes (backoffice / backend)

> El grueso del trabajo abierto del proyecto hoy está en la **PWA** (ver `zaris-vecinos/ESTADO.md` → Etapa G). Acá quedan solo cosas de backoffice/infra.

- **🟡 BI Ejecutivo** — pendiente de PRODUCTO. El usuario define las visualizaciones (como hizo con el Operativo); NO inventarlas. Tarjeta "Ejecutivo" en `DatosLanding.tsx` es placeholder. (CLAUDE.md §43.)
- **🟡 Barrido visual modo oscuro** de módulos React restantes. Solo Dashboard y Guías verificados en dark. Literales claros conocidos (1 c/u): `bi/views/{Resumen,Resueltos,Pendientes,Subreclamos}View.tsx`, `emergencias/pages/Recepcion.tsx`, `config/views/IdentidadView.tsx` → reemplazar por tokens/`--surface-overlay` cuando se los vea en dark. Vanilla (admin_tablas/usuarios) tienen el bootstrap pero sin verificación visual dark.
- **🟢 Higiene (requiere al usuario, no se puede desde Claude Code):** rotar `DISPATCHER_TOKEN` (visible en historial git): valor nuevo → Railway env var → GitHub secret (lo usan 3 crons: encuestas, trámites, integridad) → borrar el secret sobrante `ZARIS_DISPATCHER_TOKEN`.

---

## ✅ Hecho reciente (últimas sesiones)

- **2026-06-29** — **Refactor `CLAUDE.md` → skills on-demand** (`b1f8117`…`9cb4c8f`, en `main`). La referencia por módulo (§15/18/22/26/27/30/33/34/35/36/37/38/39/41/42/43/44) se movió a **14 skills `.claude/skills/modulo-*`** que cargan solas cuando trabajás ese módulo. CLAUDE.md pasó de 1992→1024 líneas (−48.6%); solo quedan las reglas transversales (always-on). **Las anclas `## N.` y todas las refs `§N` se conservan** — nada se rompe. Plan/decisiones en `PLAN_REFACTOR_SKILLS.md`. **Roy:** al tocar un módulo, su skill se invoca automáticamente; si editás CLAUDE.md, recordá que el detalle de cada módulo ya NO está ahí sino en su skill.
- **2026-06-27** — Mail de confirmación al crear reclamo del vecino (`a4ab19d`, en prod, verificado con mail real). Onboarding de Roy redondeado. Etapa G de la PWA documentada en `PLAN_APP_VECINOS.md` (`f4ad557`).
- **2026-06-13** — Recovery de credenciales usuarios internos (mig 90) + 6 catálogos Emergencias en Maestros + filtros FK en listado admin_tablas (`5d81080`, prod).
- **2026-06-12** — Shell: menú de usuario + foto de perfil (mig 88) + modo oscuro + statusbar inferior. Revisión integral de Agenda (mig 89/91) + manual.
- **2026-06-10/11** — Módulo Emergencias (COM) completo, Fases 1-5 (migs 81-85), en prod.

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
