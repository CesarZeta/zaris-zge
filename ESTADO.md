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

**Última actualización:** 2026-10-24, 2ª sesión (Cesar). **IT-01 F1+F2: Tarea 19 cerrada en local** (rama `it01-multi-municipio`, `3dd9c39`, pusheada, sin mergear): mig 126 aplicada en local, barrido de aislamiento completo (393 rutas) en 0 fallas, todos los smokes en verde y recorrido con clics del shell local. Revisión final de la rama en curso; **el corte en prod (Tarea 20) es el domingo 2026-10-25 con César**. En `main`: Config → Sistema ya no muestra `ot_pendiente_dias_vencimiento` (`d2fa720`). En prod: Arbolado pasó a «Asigna a mano».

---

## ❓ Preguntas abiertas para César — se plantean en la PRIMERA respuesta de la próxima sesión

> Regla de César (2026-10-20): al cerrar se anota todo lo abierto; al arrancar se pregunta primero. Lo sensible (seguridad) tiene el detalle en la memoria privada de Cesar, no acá (este archivo es público).

1. **IT-01: corte en prod (Tarea 20) el domingo 2026-10-25 con César.** La Tarea 19 quedó cerrada el 2026-10-24 y la revisión final de la rama está en curso; si encuentra algo grave, se corrige antes del corte. Migs 125-125d antes del deploy y 126 después. Todos vuelven a ingresar porque los tokens viejos no tienen `mun`; avisar a Roy.
2. **Asignación automática — revisar ~2026-10-29:** carga de los agentes de las 17 gestiones que asignan solas (en varias hay UN solo agente de nivel Gestión que recibe todo). Arbolado pasó a «Asigna a mano» el 2026-10-24 (su único agente de nivel Gestión era el funcionario de prueba).
3. **Commits viejos de las dos purgas:** César mandó el pedido a GitHub Support el 2026-10-22; sin respuesta al 2026-10-23 → volver a preguntar el lunes 2026-10-26 (detalle en la memoria privada de Cesar).
4. **Base de conocimiento de ayudas:** la próxima sesión completa es para eso (César, 2026-10-23). Mientras tanto no se tocan manuales.
5. Para otra sesión (César, 2026-10-23): PWA modo escritorio (falta plan) · propuesta app de agentes (reclamos de oficio + control de entradas) · ¿app del vecino con email además de DNI? · mapa del inicio en oscuro.
6. **Primer cierre real de un trámite de vecino en prod:** confirma el aviso «terminó: APROBADO/RECHAZADO» y la encuesta (probados solo en local). Agendado por César: en los próximos smokes con cuentas reales de reclamos se cierran también trámites; César pasa algunos trámites para eso.

---

## 🔵 En curso

- **IT-01 F1+F2 (multi-municipio), rama `it01-multi-municipio`, sin mergear:**
  - Tareas 1-19 de [`PLAN_MULTI_MUNICIPIO_F1_F2.md`](PLAN_MULTI_MUNICIPIO_F1_F2.md) hechas en local: migs 125-126 en `zaris_dev`, todos los routers y procesos por municipio, barrido de aislamiento completo contra un municipio de prueba en 0 fallas, smokes en verde, recorrido con clics.
  - Revisión final de la rama en curso. Tarea 20 = corte en prod con César, domingo 2026-10-25.
  - El registro de la ejecución (decisiones por tarea) está en el worktree de Cesar, fuera del repo.
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
- 🟠 **Áreas fijas por regla de negocio** (planteado 2026-08-30): Seguridad, Salud, Servicios Públicos… precargadas y NO removibles (renombrables sí) porque atienden módulos. Sin código todavía: diseño dentro de [`PLAN_MULTI_MUNICIPIO.md`](PLAN_MULTI_MUNICIPIO.md) (se crean en el alta de cada municipio con marca de sistema); la lista son las 6 áreas activas de San Andrés (César, 2026-10-23).
- 🟠 **Config/UX — reunión 2026-07-06** (tarea "Informe Bug" de la lista CONFIGURACION y UX de ClickUp): **IT-01** multi-tenant + super administrador + selector de municipio — **diseño en [`PLAN_MULTI_MUNICIPIO.md`](PLAN_MULTI_MUNICIPIO.md), aprobado; F1+F2 en curso en la rama `it01-multi-municipio` (ver En curso); fases F3-F7 después del corte** · **IT-08** botón SOS de la PWA · **IT-07** accesibilidad móvil (PWA) · **IT-09** módulo de Obras (backlog sin alcance).
- 🟢 **Baja de cuenta del vecino:** sin endpoint ni definición; obligatoria si la app va a las stores.

**Infra / operativo**
- 🟡 **Vercel: los deploys de Roy quedan BLOCKED** (autor fuera del team; plan Hobby, sumar miembros exige Pro — decisión de facturación de César). **EN PAUSA** mientras Roy no esté activo; mitigación `git merge --no-ff` o commit vacío de re-trigger.
- 🟡 **Barrido visual de modo oscuro** en los módulos React restantes: **POSPUESTO por César 2026-09-20**. Sumar el mapa del inicio: tras los cambios del 2026-10-19 no se revisó en oscuro, y el contorno pizarra de los reclamos casi no se ve sobre el tile oscuro.

**Decisiones cerradas — NO re-proponer**
- **Ayudas: una sola página de base de conocimiento con preguntas, no manuales por módulo** (César, 2026-10-22). No se crean ni actualizan `docs/manual_*.html` mientras tanto (CLAUDE.md §36). Diseño pendiente (pregunta 4).
- **Multi-municipio: UNA base para todos con `id_municipio`** (César, 2026-10-23) — no re-proponer una base por municipio. **Las cuatro decisiones de F2 quedan aceptadas** (César, 2026-10-24): tablas globales de Maestros solo para el administrador del municipio base hasta F3; 409 al guardar la identidad sin claves propias; 409 en el alta pública con un documento de otro municipio; `/demo/poblar` con JWT solo para el administrador del municipio demo. Se revisan en F3, F4 o el lote de limpieza. **Módulo de documentos de identidad por país: tema reservado**; lo trae César cuando quiera (investigación hecha, `docs/investigacion_documentos_identidad.md`).
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

- **2026-10-24 (2ª) — IT-01 Tarea 19 cerrada en local** (mig 126, barrido completo en 0 fallas, smokes y recorrido con clics); Config → Sistema sin `ot_pendiente_dias_vencimiento` (`d2fa720`); Arbolado «Asigna a mano» en prod.
- **2026-10-24 — IT-01 F1+F2 en la rama `it01-multi-municipio` (Tareas 1-18, local).** Cubre Emergencias, Agenda, Turnos, Trámites, Encuestas, portal del vecino, Datos, Configuración, Maestros, los procesos de cron y el generador demo, todo por municipio. `smoke_demo_sla` volvió a verde (45/45). Sin cambios en `main` ni en prod.
- **2026-10-23 (3ª) — Diseño de IT-01** ([`PLAN_MULTI_MUNICIPIO.md`](PLAN_MULTI_MUNICIPIO.md), con la guía de arranque y la investigación de documentos como anexos); borradores de Trámites publicados y verificados en prod; `www.zaris.com.ar` arreglado.

- **2026-10-23 (2ª) — Trámites: el cierre sella el resultado (migs 123 + 124)** y los botones del agente salen coloreados por acción. Detalle en `HISTORIAL_MIGRACIONES.md` y en la skill `modulo-tramites`.
- **2026-10-23 (1ª) — SLA en minutos (mig 120), asignación automática general (mig 121), buscador de un solo campo, mig 122; revisión de PHP2Shell (ZARIS no afectado).** Detalle en `HISTORIAL_MIGRACIONES.md`. Ciudadano 1618 = prueba de Roy.

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
