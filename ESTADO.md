# ESTADO — zaris-zge (backoffice + backend)

> **Hilo conductor común Cesar ↔ Roy.** Este archivo es la **fuente de verdad compartida y versionada** del estado de avance. Es lo PRIMERO que se lee al retomar y lo que se ACTUALIZA al cerrar cada sesión (regla CLAUDE.md §45). Es un documento **vivo y corto** — foto del estado actual, NO bitácora histórica (esa vive en [`HISTORIAL_MIGRACIONES.md`](HISTORIAL_MIGRACIONES.md) y, para Cesar, en su memoria privada de Claude Code).
>
> **Reglas de mantenimiento:**
> - Actualizar al cerrar sesión (la skill `/cierre-sesion` lo hace antes de tocar la memoria privada).
> - "En curso" y "Pendientes" reflejan lo REAL — si terminás algo, movelo a "Hecho reciente" (y podá lo viejo de ahí: máx ~10 líneas).
> - Convertir fechas relativas a absolutas.
> - Verificar contra git/prod antes de declarar algo hecho (`feedback_verificar_siempre_antes_de_opinar`).
> - La PWA App Vecinos tiene su **propio** `ESTADO.md` en el repo `zaris-vecinos`. Acá va solo backoffice/backend.
> - **Tamaño objetivo: ~12 KB.** Si "Última actualización" o "Hecho reciente" crecen más de eso, se podan (lo viejo ya está en el historial y en los `PLAN_*.md`).

**Última actualización:** 2026-10-23, 2ª sesión (Cesar). **Mig 122 aplicada en prod** (la corrió César desde el SQL Editor de Supabase; verificada). **Trámites: el cierre ahora sella el resultado** — mig 123 (25 transiciones finales con aprobar/rechazar) y mig 124 (8 decisiones intermedias): al cerrarse un trámite se avisa al vecino «terminó: APROBADO/RECHAZADO» y sale la encuesta; sin doble aviso al archivar desde un estado que ya es final. `GET /tramites/tipos/{id}` devolvía siempre «avanzar» (corregido). Editor de circuitos: aviso y marca «sin resultado». Botones del agente coloreados según la acción. **Borradores en prod de Aviso de Obra v3 y Recurso administrativo v2, para que César los publique** (pregunta 8). Verificado: smoke 16/16 en local, clics en local, API y SQL en prod; ningún cierre real en prod todavía. Antes, el mismo día: SLA en minutos y asignación automática general (migs 120-121) y revisión de PHP2Shell (ZARIS no afectado).

---

## ❓ Preguntas abiertas para César — se plantean en la PRIMERA respuesta de la próxima sesión

> Regla de César (2026-10-20): al cerrar se anota todo lo abierto; al arrancar se pregunta primero. Lo sensible (seguridad) tiene el detalle en la memoria privada de Cesar, no acá (este archivo es público).

1. **Multi-municipio y super administrador (IT-01):** diseño en [`PLAN_MULTI_MUNICIPIO.md`](PLAN_MULTI_MUNICIPIO.md) con las decisiones de César del 2026-10-23 (una base para todos con `id_municipio`, super administrador en el mismo shell, subdominio por municipio, también otros países, RLS antes de un segundo municipio real). Falta su aprobación y tres preguntas del plan (fila id 2 de `municipios`, lista de áreas fijas, direcciones actuales). Implementación en una sesión dedicada (F1+F2 en un solo corte).
2. **Asignación automática — revisar ~2026-10-29:** carga de los agentes de las 18 gestiones que asignan solas (en varias hay UN solo agente de nivel Gestión que recibe todo; en Arbolado es el funcionario de prueba). Decidir si se suma gente o se vuelve a poner alguna a mano.
3. **Commits viejos de las dos purgas:** César mandó el pedido a GitHub Support el 2026-10-22; sin respuesta al 2026-10-23 → volver a preguntar el lunes 2026-10-26 (detalle en la memoria privada de Cesar).
4. **Base de conocimiento de ayudas:** la próxima sesión completa es para eso (César, 2026-10-23). Mientras tanto no se tocan manuales.
5. Para otra sesión (César, 2026-10-23): PWA modo escritorio (falta plan) · propuesta app de agentes (reclamos de oficio + control de entradas) · ¿app del vecino con email además de DNI? · mapa del inicio en oscuro.
6. **Primer cierre real de un trámite de vecino en prod:** confirma el aviso «terminó: APROBADO/RECHAZADO» y la encuesta (probados solo en local). Agendado por César: en los próximos smokes con cuentas reales de reclamos se cierran también trámites; César pasa algunos trámites para eso.

---

## 🔵 En curso

- **PWA `zaris-vecinos` — modo escritorio del portal: diseño aprobado el 2026-10-12 (3ª), falta plan + código.** Solo toca el repo de la PWA; spec y pasos en su `ESTADO.md` → En curso.
- **PROPUESTA sin aprobar — app de agentes: reclamos de oficio + «Control de entradas» (QR).** Pedido de César al cierre del 2026-10-12; las 4 decisiones de alcance ya están tomadas (de oficio · niveles 1-4 · acreditar niveles 1-4 · nombre «Control de entradas») y el diseño está escrito en [`PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md`](PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md). **Próxima sesión: César confirma o corrige el diseño y recién ahí F1 (backend sin migración + smoke).** No hay código.
- **App de agentes** publicada en `https://agentes.zaris.com.ar` (color del municipio, instalación desde «Mi perfil»); el vecino instala la suya desde su portal. Detalle en `zaris-agentes/ESTADO.md`.

> ### 📣 Para quien retome la PWA `zaris-vecinos` (Roy inactivo por ahora — César 2026-09-20)
> **Desde el 2026-09-26 la PWA ya consume TODO lo que el backend entregó el 2026-08-30** (perfil + edición de teléfono/domicilio, bandeja de avisos con badge, `geo/reverse`, foto de perfil en el backend). Lo que falta del lado suite para la PWA es solo backend NUEVO: `GET /publico/noticias` y URLs de redes en `identidad-municipio` (las secciones están ocultas mientras tanto), emergencias en `mi-resumen`, y la baja de cuenta. Contrato en [`docs/contrato_api_publica.md`](docs/contrato_api_publica.md). Cambio de contrato previo (2026-07-15, ya en la tabla): `POST /publico/alta/empresa` exige el vecino logueado (401 sin token) y ya NO toma `id_ciudadano` del body.

---

## 🟠 Pendientes (backoffice / backend)

**Decisiones de negocio pendientes (César)**
- 🟡 **Botón de pánico de la PWA:** sin probar con el vecino de prueba (dispara una alerta REAL al COM). Las pruebas de vecino y funcionario están hechas (2026-10-12 y 2026-10-23).
- 🟢 **Alta — huecos menores detectados en la revisión 2026-10-10:** la clave temporal del funcionario no vence si nunca la usa; la app de agentes no tiene «olvidé mi contraseña» (hoy se recupera desde el login del backoffice, link 24 h). El vecino NO recibe clave por mail (elige la suya por link) — recomendado mantenerlo.
- 🟠 **Atención — residuos del plan (§4):** "ocupación vs disponibilidad efectiva" en el BI de atención · etapa 2 de HC (vista admin de `historia_clinica_acceso`, break-the-glass, ficha ampliada) · walk-in de Guardia sin evento de Emergencias.
- 🟠 **Trámites — residuo:** los 4 tipos sin circuito (exención de tasas, permiso de espacio público, arbolado urbano, inscripción profesional) tienen la gestión asignada por criterio de Claude, cambiable desde el builder.
- 🟠 **Áreas fijas por regla de negocio** (planteado 2026-08-30): Seguridad, Salud, Servicios Públicos… precargadas y NO removibles (renombrables sí) porque atienden módulos. Sin código todavía: diseño dentro de [`PLAN_MULTI_MUNICIPIO.md`](PLAN_MULTI_MUNICIPIO.md) (se crean en el alta de cada municipio con marca de sistema); falta la lista exacta.
- 🟠 **Config/UX — reunión 2026-07-06** (tarea "Informe Bug" de la lista CONFIGURACION y UX de ClickUp): **IT-01** multi-tenant + super administrador + selector de municipio (proyecto de arquitectura, por fases con César; 2026-10-20: el super administrador crea los municipios, los parámetros globales y los administradores de cada municipio, y el administrador queda como superusuario de SU municipio) · **IT-08** botón SOS de la PWA · **IT-07** accesibilidad móvil (PWA) · **IT-09** módulo de Obras (backlog sin alcance).
- 🟢 **Baja de cuenta del vecino:** sin endpoint ni definición; obligatoria si la app va a las stores.

**Infra / operativo**
- 🟡 **Vercel: los deploys de Roy quedan BLOCKED** (autor fuera del team; plan Hobby, sumar miembros exige Pro — decisión de facturación de César). **EN PAUSA** mientras Roy no esté activo; mitigación `git merge --no-ff` o commit vacío de re-trigger.
- 🟡 **Barrido visual de modo oscuro** en los módulos React restantes: **POSPUESTO por César 2026-09-20**. Sumar el mapa del inicio: tras los cambios del 2026-10-19 no se revisó en oscuro, y el contorno pizarra de los reclamos casi no se ve sobre el tile oscuro.

**Decisiones cerradas — NO re-proponer**
- **Ayudas: una sola página de base de conocimiento con preguntas, no manuales por módulo** (César, 2026-10-22). No se crean ni actualizan `docs/manual_*.html` mientras tanto (CLAUDE.md §36). Diseño pendiente (pregunta 5).
- **Orden por columnas: quedan afuera** las colas operativas (Mesa del día, Guardia, Conflictos, Pendientes de contacto), las tablas con orden propio (historia clínica, historial de accesos, builder de trámites) y la configuración (Catálogo de módulos, Plantillas); Entradas usa selector «Ordenar por»; el desplegable «Ordenar» viejo se reemplazó por encabezados + columna «Alta» (César, 2026-10-22).
- **São Paulo DESCARTADO (César, 2026-09-26, con medición):** Railway ya está co-locado con Supabase `us-east-1` y no ofrece región en Sudamérica. Detalle en CLAUDE.md §9 «Región».
- **"La ubicación" de Buscar actualizaciones (PWA) CERRADA como innecesaria** (2026-09-26): el service worker con `autoUpdate` alcanza.
- `DISPATCHER_TOKEN` no se rota (César 2026-09-06). El vecino NO cambia su email desde la app (2026-08-30).
- Purgas del historial git HECHAS el 2026-09-20 y el 2026-10-21 (mapas en `docs/commit-map-purga-*.txt`; un SHA viejo que no resuelve se busca ahí). Roy tiene que re-clonar.
- Claves de las notificaciones push: **no se rotan** (César, 2026-10-21).
- Los reclamos **no se agendan**: la agenda es solo para turnos (César, 2026-10-21).
- Fase 3 de roles (mig 92) y la auditoría de seguridad 2026-07 (48/48) COMPLETAS.

---

## ✅ Hecho reciente (últimas sesiones)

- **2026-10-23 (3ª) — Borradores de Trámites publicados** (Aviso de Obra v3, Recurso administrativo v2, con la sesión de César) y verificados en prod con clics el aviso «sin resultado», los botones coloreados y lo de la 1ª sesión (SLA número + unidad con guardado en horas, «Asigna a mano», interruptor de Sistema, buscador de un campo). `www.zaris.com.ar` redirige al sitio con certificado válido. Smoke `smoke_tramites_ciclo_vida.py` aislado del resto de la base (`e49b41e`, 24/24). Diseño de IT-01 en `PLAN_MULTI_MUNICIPIO.md`.

- **2026-10-23 (2ª) — Trámites: el cierre sella el resultado (migs 123 + 124, `f9eef11` · `0faebe7` · `a49ef4b` · `03e39c7`).** Sin doble aviso al archivar desde un estado final; `GET /tramites/tipos/{id}` con el `tipo_accion` real; aviso «sin resultado» en el editor; botones del agente coloreados; borradores de Aviso de Obra v3 y Recurso v2 en prod (sin publicar). Smoke `smoke_tramites_resultado_final.py` 16/16. Mig 122 aplicada en prod por César.
- **2026-10-23 — SLA en minutos (mig 120) + asignación automática general (mig 121, 18 gestiones asignan solas) (`4c9f5ee`), buscador de un solo campo (`f42181d`), encabezados de Maestros (`2266b72`), mig 122 (local y prod; en prod la corrió César desde el SQL Editor).** Smokes 27/27 · 86/86 · 44/44. Rebalanceo demo: 322 reclamos (BI 55,1 % → 66,6 %). Backups y detalle en `HISTORIAL_MIGRACIONES.md`. Rama «estados, asignaciones y mesas» cerrada por César (la auditoría F1-F4 queda sin la prueba real del mail del retrabajo: verificado en MOCK). Ciudadano 1618 = prueba de Roy.
- **2026-10-20/22 — Orden por columnas en toda la suite (F1-F3, último `97fb3bf`);** fichas demo sin App Vecinos + mig 119; links profundos del shell (§14); «VER PENDIENTES»; logins sin `email`; fuera los endpoints de OT con agenda. Detalle en CLAUDE.md §23 y las skills.
- **2026-10-23 — Revisión de PHP2Shell (CVE-2026-109618/109619, parche de PHP del 2026-10-21):** ZARIS no está afectado. Ninguno de los repos (zge, vecinos, agentes, ZGC, sitio + ZARIS News) tiene PHP, y todos los dominios públicos sirven estático (Vercel, GitHub Pages) o Python (Railway). Sin cambios.

> Detalle por migración en `HISTORIAL_MIGRACIONES.md`; reglas de cada módulo en su skill; lo anterior a septiembre (julio-agosto 2026: auditoría de seguridad 48/48, migs 95-102, BI Operativo/Ejecutivo, PWA de Roy a prod, Usuarios en React) en `HISTORIAL_MIGRACIONES.md` y la memoria privada de César.

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
| Roadmap de Atención por ubicación (Turnos, colero, Guardia, historia clínica, BI) + decisiones por fase | [`PLAN_MODULO_ATENCION.md`](PLAN_MODULO_ATENCION.md) |
| Auditoría de reclamos posterior al cierre (decisiones de César + fases) | [`PLAN_AUDITORIA_RECLAMOS.md`](PLAN_AUDITORIA_RECLAMOS.md) |
| Multi-municipio y super administrador (IT-01: decisiones de César + fases) | [`PLAN_MULTI_MUNICIPIO.md`](PLAN_MULTI_MUNICIPIO.md) |
| Qué migración hace qué / cuándo se aplicó | [`HISTORIAL_MIGRACIONES.md`](HISTORIAL_MIGRACIONES.md) |
| Contrato de la API pública que consume la PWA | [`docs/contrato_api_publica.md`](docs/contrato_api_publica.md) |
| Cómo arrancar local / colaborar | [`ONBOARDING.md`](ONBOARDING.md) · [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Quirks/patrones/decisiones (foto de las memorias) | [`docs/memoria-proyecto/`](docs/memoria-proyecto/) |
