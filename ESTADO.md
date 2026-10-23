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

**Última actualización:** 2026-10-23 (Cesar). **SLA de los tipos de reclamo en minutos** (mig 120: número + unidad en Maestros, vencimiento y % del BI exactos; demo rebalanceada, BI en 66,6 %) y **asignación automática general del municipio** (mig 121: interruptor en Configuración → Sistema + excepción «Asigna a mano» por gestión; se tradujo el estado anterior, sigue asignando sola solo Alumbrado). Además: buscador de Ciudadanos/Empresas con un solo campo, encabezados de Maestros con tildes. Prueba del funcionario cerrada (OT asignada → push → terminada desde la app de agentes con resolución, aviso y encuesta al vecino). Verificado en local con smokes y clics, y en prod por API/SQL; la parte de Maestros y Configuración solo la puede mirar un admin (pregunta 1).

---

## ❓ Preguntas abiertas para César — se plantean en la PRIMERA respuesta de la próxima sesión

> Regla de César (2026-10-20): al cerrar se anota todo lo abierto; al arrancar se pregunta primero. Lo sensible (seguridad) tiene el detalle en la memoria privada de Cesar, no acá (este archivo es público).

1. **Mirar en prod con la sesión de admin (2026-10-23):** Maestros → Tipos de Reclamo (columna «SLA» y el campo número + unidad; probar guardar uno en horas), Maestros → Subáreas (columna y tilde «Asigna a mano»), Configuración → Sistema (interruptor «Asignación automática de reclamos») y Contactos → Ciudadanos/Empresas (buscador de un solo campo). En local está todo probado con clics; en prod solo por API/SQL.
2. **Asignación automática general:** quedó prendida con 81 gestiones como excepción «a mano» (traducción exacta de cómo estaba: solo Alumbrado asigna sola). ¿Le sacamos la excepción a las 17 gestiones que tienen un agente de nivel Gestión? Las 25 sin agentes conviene dejarlas a mano (si no, cada reclamo avisa «sin candidatos»). Alumbrado: revisar la carga de su único agente ~2026-10-29 (hasta hoy solo le entraron reclamos demo).
3. **Mail real del retrabajo (auditoría):** probarlo con REC-2026-003079 (Resuelto, el vecino es César): Reclamos → Enviar a auditoría → OT → Auditoría → Observar → «Sí». Crea un reclamo de retrabajo real en Arbolado.
4. **Commits viejos de las dos purgas:** César mandó el pedido a GitHub Support el 2026-10-22; sin respuesta al 2026-10-23 → volver a preguntar el lunes 2026-10-26 (detalle en la memoria privada de Cesar).
5. **Super administrador multi-municipio (IT-01):** ¿cuándo arrancamos el diseño? Recomendación: ahora, junto con las áreas fijas.
6. **Base de conocimiento de ayudas:** César la quiere tratar en una sesión completa (2026-10-23). Mientras tanto no se tocan manuales.
7. Sin respuesta de sesiones anteriores: PWA modo escritorio (falta plan) · propuesta app de agentes (reclamos de oficio + control de entradas) · ¿app del vecino con email además de DNI? · mapa del inicio en oscuro.

---

## 🔵 En curso

- **Auditoría de reclamos — circuito completo en prod (F1-F4, 2026-10-20).** Queda solo la **prueba real del mail en prod** (pregunta 3).
- **Limpieza pendiente (mig 122, cuando César lo confirme):** borrar `subarea.asignacion_automatica` (sin uso desde la 121; prod ya corre el código nuevo) y evaluar `tipo_reclamo.duracion_estimada_min` (sin uso desde 2026-10-21). Ojo: el permiso del MCP rechaza `DROP` en `apply_migration`; hace falta que César lo apruebe.
- **PWA `zaris-vecinos` — modo escritorio del portal: diseño aprobado el 2026-10-12 (3ª), falta plan + código.** Solo toca el repo de la PWA; spec y pasos en su `ESTADO.md` → En curso.
- **PROPUESTA sin aprobar — app de agentes: reclamos de oficio + «Control de entradas» (QR).** Pedido de César al cierre del 2026-10-12; las 4 decisiones de alcance ya están tomadas (de oficio · niveles 1-4 · acreditar niveles 1-4 · nombre «Control de entradas») y el diseño está escrito en [`PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md`](PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md). **Próxima sesión: César confirma o corrige el diseño y recién ahí F1 (backend sin migración + smoke).** No hay código.
- **App de agentes** publicada en `https://agentes.zaris.com.ar` (color del municipio, instalación desde «Mi perfil»); el vecino instala la suya desde su portal. Detalle en `zaris-agentes/ESTADO.md`.

> ### 📣 Para quien retome la PWA `zaris-vecinos` (Roy inactivo por ahora — César 2026-09-20)
> **Desde el 2026-09-26 la PWA ya consume TODO lo que el backend entregó el 2026-08-30** (perfil + edición de teléfono/domicilio, bandeja de avisos con badge, `geo/reverse`, foto de perfil en el backend). Lo que falta del lado suite para la PWA es solo backend NUEVO: `GET /publico/noticias` y URLs de redes en `identidad-municipio` (las secciones están ocultas mientras tanto), emergencias en `mi-resumen`, y la baja de cuenta. Contrato en [`docs/contrato_api_publica.md`](docs/contrato_api_publica.md). Cambio de contrato previo (2026-07-15, ya en la tabla): `POST /publico/alta/empresa` exige el vecino logueado (401 sin token) y ya NO toma `id_ciudadano` del body.

---

## 🟠 Pendientes (backoffice / backend)

**Próxima sesión — prueba de las apps (César)**
- 🟡 **Perfiles de prueba** (emails en la memoria privada de Cesar): vecino HECHO (2026-10-12; el botón de pánico no se probó, dispara una alerta REAL); funcionario HECHO (2026-10-23: OT asignada → push → terminada desde la app de agentes).
- 🟢 **Circuito funcionario → agente: HECHO (2026-10-20/21).** Datos personales solo de la ficha; cargo/horario/equipo los completa el supervisor de la gestión (mig 113); una sola gestión y email por persona, la del agente (mig 116); toda persona con usuario tiene ficha (mig 118, fichas demo con DNI 99.000.000 + id_agente; desde el 2026-10-22 no reciben cuenta de App Vecinos hasta cargar el DNI real). Pendiente de IT-01: el super administrador multi-municipio.

**Decisiones de negocio pendientes (César)**
- 🟢 **Alta — huecos menores detectados en la revisión 2026-10-10:** la clave temporal del funcionario no vence si nunca la usa; la app de agentes no tiene «olvidé mi contraseña» (hoy se recupera desde el login del backoffice, link 24 h). El vecino NO recibe clave por mail (elige la suya por link) — recomendado mantenerlo.
- 🟠 **Atención — residuos del plan (§4):** "ocupación vs disponibilidad efectiva" en el BI de atención · etapa 2 de HC (vista admin de `historia_clinica_acceso`, break-the-glass, ficha ampliada) · walk-in de Guardia sin evento de Emergencias.
- 🟠 **Trámites — 2 residuos:** (a) las transiciones finales de los seeds usan `tipo_accion='avanzar'` (solo 6 tienen `aprobar`/`rechazar`) → el resultado automático y la encuesta CSAT no se disparan solos en la mayoría de los tipos (se puede mapear por estado destino); (b) los 4 tipos sin circuito (exención de tasas, permiso de espacio público, arbolado urbano, inscripción profesional) tienen la gestión asignada por criterio de Claude, cambiable desde el builder.
- 🟠 **Áreas fijas por regla de negocio** (planteado 2026-08-30): Seguridad, Salud, Servicios Públicos… precargadas y NO removibles (renombrables sí) porque atienden módulos. Sin código todavía: analizar junto con seeds, admin_tablas, baja lógica y IT-01.
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

- **2026-10-23 — SLA en minutos (mig 120) + asignación automática general (mig 121) (`4c9f5ee`), buscador de un solo campo (`f42181d`), encabezados de Maestros (`2266b72`).** Smokes `smoke_sla_asignacion_general.py` 27/27, auditoría 86/86, demo SLA 44/44. Prod: backups `_backup_tipo_reclamo_sla_2026_10_23`, `_backup_subarea_asignacion_2026_10_23` y `_backup_rebalanceo_sla_*_2026_10_23`; rebalanceo demo 322 reclamos (BI 55,1 % → 66,6 %, meses 61-74 %). Prueba del funcionario cerrada (REC-2026-003079). Ciudadano 1618 = prueba de Roy (no se toca).

- **2026-10-20/22 — Orden por columnas en toda la suite (F1 `ad61530`, F2 `e9103a1`, F3 `97fb3bf`).** Helper `utils/orden.py` (lista cerrada, 422) + `ui/orden.tsx`; el detalle de cada pantalla vive en CLAUDE.md §23 y en las skills. F3: Ciudadanos/Empresas buscan, ordenan y paginan en el servidor (`q`/`desde`/`hasta`/`orden`/`dir` + `X-Total-Count`); filtro «Trámites» en Envíos. Smoke `smoke_orden_listados.py` 122/122; verificado en local con clics y en prod.
- **2026-10-22 — Ficha demo sin App Vecinos + mig 119** (FK de la gestión) **y lista de arranque:** 32 reclamos viejos de prueba cerrados (backups `_backup_reclamos_qa_2026_10_22` / `_backup_ot_qa_2026_10_22`), autoasignación de Alumbrado, links profundos del shell (CLAUDE.md §14), «VER PENDIENTES», recuadro «Resolución» en la PWA, logins sin `email`, fuera los endpoints de OT con agenda.
- **2026-10-21 — Generador demo diario con SLA y trámites; Tomar/Resolver desde Reclamos (mig 117); coherencia de cuentas (migs 116, 118); seguridad del CRUD de Maestros; reclamos sin agenda (mig 115); purga de `agente.csv`.** Todo en prod; detalle en git y `HISTORIAL_MIGRACIONES.md`.
- **2026-10-20 — Auditoría de reclamos posterior al cierre (mig 112, `PLAN_AUDITORIA_RECLAMOS.md`), orden por columnas F1, autoasignación (mig 114), supervisor en Maestros → Agentes (mig 113).** En prod.

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
| Qué migración hace qué / cuándo se aplicó | [`HISTORIAL_MIGRACIONES.md`](HISTORIAL_MIGRACIONES.md) |
| Contrato de la API pública que consume la PWA | [`docs/contrato_api_publica.md`](docs/contrato_api_publica.md) |
| Cómo arrancar local / colaborar | [`ONBOARDING.md`](ONBOARDING.md) · [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Quirks/patrones/decisiones (foto de las memorias) | [`docs/memoria-proyecto/`](docs/memoria-proyecto/) |
