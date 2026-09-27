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

**Última actualización:** 2026-09-27 (Cesar, cierre de la segunda sesión del 26/09; la decisión sobre los canales de instalación de las apps está en «En curso»). Sesión: **Vista «Mi perfil» HECHA y pusheada** (`4be8773`, ver Hecho reciente): módulo React `perfil` + ítem en el menú del avatar + `app_vecinos_url` en `/config/identidad`. **Verificado en prod** (sondeos independientes): Railway sirve el commit y `GET /config/identidad` devuelve `app_vecinos_url = https://vecinos.zaris.com.ar` (la env var ya estaba); GH Pages sirve `index.html` con `#btn-perfil` y el bundle `index-BlNQp9aM.js` con la vista. **Después, en la misma sesión: nace la App de agentes** — repo `zaris-agentes` (`dd559f5`, privado, clonado de la estructura de la PWA del vecino) con el primer frente **OT en la calle** completo y verificado en local (login con credenciales ZARIS, mesa, detalle con mapa + «Cómo llegar», evidencia con cámara, cambio de estado, Cuenta con push); backend acá: **mig 108** `usuario_push_subscription` + `/api/v1/auth/push/*` + hook «OT asignada» + CORS. Falta: proyecto Vercel + dominio y la prueba humana en el celular (ver `zaris-agentes/ESTADO.md`). Primera sesión del día, tres frentes: (1) **São Paulo → DESCARTADO con medición** (ver Decisiones cerradas): Railway ya está co-locado con Supabase (round-trip 4-5 ms), Railway no tiene región en Sudamérica y el piso de ~150 ms por request desde Argentina solo se baja saliendo de Railway; backup de prod previo (`backups/zaris_prod_2026-09-26_1835.sql`, 7,1 MB, 111 tablas). (2) **PWA de vecinos CERRADA** (`e9bbb6a` en `zaris-vecinos`, publicado en Vercel): consume perfil/avisos/geo-reverse/foto y oculta los mocks. (3) **Plan de la vista «Mi perfil»** escrito para la próxima sesión (`PLAN_MI_PERFIL.md`). Aparte: los 2 crons del bot de noticias (`zaris-news-bot`, otro repo) quedaron desactivados a pedido de César (fallaban a diario: modelo de Groq inexistente + token vencido del repo del sitio). Infra al cierre: todo verde (GH Pages en `7b5ff89`, bundle `index-YwhghPq4.js` sin cambios, Railway OK, PWA en Vercel con `index-CUMc5glM.js`, crons en `success`). Vigente: modo oscuro pospuesto · Roy inactivo por ahora.

---

## 🔵 En curso

- **PRIMERA TAREA DE LA PRÓXIMA SESIÓN — canales de instalación de las dos apps (decisión de César, 2026-09-27):** *los funcionarios bajan la app de agentes desde su perfil dentro de ZARIS; los vecinos bajan la app del vecino desde el portal del vecino (no entran a ZARIS, acceden a información por el portal)*. Qué implica: (1) **«Mi perfil» en ZARIS suma la tarjeta «App de agentes»** con QR + link a la app de agentes (backend: `app_agentes_url` en `GET /config/identidad` desde una env var `APP_AGENTES_FRONTEND_URL`, mismo patrón que `app_vecinos_url`; la vista ya tiene el hueco para la tarjeta gemela) — requiere la URL definitiva de la app (Vercel, pendiente). (2) **La app del vecino se ofrece desde el portal del vecino**: definir dónde (la bienvenida de la PWA ya tiene el bloque de instalación; ¿también la página pública de alta `frontend/alta-vecino.html` y el «perfil» del portal?). (3) **A confirmar con César:** si la tarjeta del vecino que hoy está en «Mi perfil» se queda (útil para que el agente en ventanilla le muestre el QR al vecino) o se reemplaza por la de agentes.
- **Nada en desarrollo activo.** El proyecto **Atención por ubicación** (6 fases: ubicación obligatoria, Mesa del día, colero, Guardia, historia clínica, BI de atención) quedó **CERRADO el 2026-09-20** con el QA de César en prod. Roadmap, decisiones por fase y residuos en [`PLAN_MODULO_ATENCION.md`](PLAN_MODULO_ATENCION.md) (§4 Pendientes).
- **Vista «Mi perfil»: HECHA (2026-09-26, `4be8773`).** Queda solo la mirada humana de César en prod (menú del avatar → Mi perfil; escanear el QR con el celular → debe abrir `vecinos.zaris.com.ar`; «Copiar link» exige click humano, no se pudo probar con browser-MCP). Plan y decisiones en [`PLAN_MI_PERFIL.md`](PLAN_MI_PERFIL.md).
- **App de agentes — EN MARCHA (2026-09-26): repo `zaris-agentes` creado con el primer frente (OT en la calle) completo en código.** Lado suite HECHO (mig 108 aplicada en prod y verificada; backend pusheado). Del lado app: Vercel (**manual, el MCP dio 403 al crear el proyecto**; pasos en `zaris-agentes/ESTADO.md`) + dominio `agentes.zaris.com.ar` + prueba en celular. Estado y decisiones a confirmar (look ZARIS vs color del municipio) en `zaris-agentes/ESTADO.md`. Plan original: (`zaris-agentes`, repo nuevo clonando la estructura de la PWA de vecinos, ya cerrada el 2026-09-26; login con credenciales de ZARIS, home por rol; **primer frente: OT en la calle** — mesa del agente, tomar, cambiar estado, foto de evidencia, mapa del reclamo). Backend pendiente: origen nuevo en CORS + push para agentes (tabla nueva, mig 108, VAPID reusado).

> ### 📣 Para quien retome la PWA `zaris-vecinos` (Roy inactivo por ahora — César 2026-09-20)
> **Desde el 2026-09-26 la PWA ya consume TODO lo que el backend entregó el 2026-08-30** (perfil + edición de teléfono/domicilio, bandeja de avisos con badge, `geo/reverse`, foto de perfil en el backend). Lo que falta del lado suite para la PWA es solo backend NUEVO: `GET /publico/noticias` y URLs de redes en `identidad-municipio` (las secciones están ocultas mientras tanto), emergencias en `mi-resumen`, y la baja de cuenta. Contrato en [`docs/contrato_api_publica.md`](docs/contrato_api_publica.md). Cambio de contrato previo (2026-07-15, ya en la tabla): `POST /publico/alta/empresa` exige el vecino logueado (401 sin token) y ya NO toma `id_ciudadano` del body.

---

## 🟠 Pendientes (backoffice / backend)

**Verificaciones humanas (César)**
- 🟡 **Recorrido en PROD (iframe real) de las 13 pantallas con búsqueda diferida (§23):** Reclamos, OT ×3, Trámites ×2 (Buscar deja `?buscar=1`; un deep link con filtros arranca buscado), Agenda ×3 ("Ver agenda" antes de la grilla; navegar fechas después re-pide), Entradas, Encuestas → Envíos, Ciudadanos/Empresas → Listado (el botón "Listado" del buscador llega ya buscado). Verificado en local pantalla por pantalla el 2026-09-20; falta solo la mirada humana en prod (César confirmó el 2026-09-26 que todavía no lo hizo; links por módulo entregados en esa sesión).
- 🟡 **Cron "Datos demo BI" del lunes 2026-09-28:** primera corrida con el flujo 202 + polling. Esperado: run `success` y el JSON de `generado` / `generado_atencion` / `avanzado` / `avanzado_atencion` en el log. Si falla, **verificar la DB antes de re-dispatchar** (regla del incidente 2026-08-31; memoria `project_cron_demo_502_railway_timeout_5min`).
- 🟡 **Trámites — primer aviso REAL del ciclo de vida ~2026-10-06:** los 2 expedientes con mail real (`HAB-LPL-2026-0001`, `CAR-LPL-2026-0002`) tienen el reloj en cero desde el 2026-09-06; verificar entonces que el cron mande UN aviso y nada más.

**Decisiones de negocio pendientes (César)**
- 🟠 **Atención — residuos del plan (§4):** export PDF "Prestaciones realizadas" de Consultas saca intervención/recomendaciones sin el guard de historia clínica (quitar / gatear por `/permiso` / dejar) · marcar `registra_atencion=true` en TODAS las prestaciones de Salud (dato de negocio, prod no verificado) · "ocupación vs disponibilidad efectiva" en el BI de atención (hoy ocupación = turnos + horas atendidas, sin % sobre la agenda) · etapa 2 de HC (vista admin de `historia_clinica_acceso`, break-the-glass, ficha ampliada) · walk-in de Guardia sin evento de Emergencias.
- 🟠 **Trámites — 2 residuos:** (a) las transiciones finales de los seeds usan `tipo_accion='avanzar'` (solo 6 tienen `aprobar`/`rechazar`) → el resultado automático y la encuesta CSAT no se disparan solos en la mayoría de los tipos (se puede mapear por estado destino); (b) los 4 tipos sin circuito (exención de tasas, permiso de espacio público, arbolado urbano, inscripción profesional) tienen la gestión asignada por criterio de Claude, cambiable desde el builder.
- 🟠 **Áreas fijas por regla de negocio** (planteado 2026-08-30): Seguridad, Salud, Servicios Públicos… precargadas y NO removibles (renombrables sí) porque atienden módulos (Emergencias→Seguridad, Turnos→Salud, Reclamos→Servicios Públicos). Sin código todavía: establecer la regla y analizarla junto con seeds, admin_tablas, baja lógica y IT-01.
- 🟠 **Config/UX — reunión 2026-07-06** (informe en la tarea "Informe Bug" de la lista CONFIGURACION y UX de ClickUp): **IT-01** multi-tenant + super administrador + selector de municipio — proyecto de arquitectura (consolidar la identidad repartida entre `municipios` y `configuracion_general`; diseñar por fases con César; DESPUÉS del seed demo, decisión 2026-08-30) · **IT-08** botón SOS de la PWA (definir qué acción dispara) · **IT-07** accesibilidad móvil (PWA, otro repo) · **IT-09** módulo de Obras (backlog sin alcance).
- 🟢 **Baja de cuenta del vecino:** sin endpoint ni definición; obligatoria si la app va a las stores.

**Infra / operativo**
- 🟡 **Vercel: los deploys de Roy quedan BLOCKED** (autor fuera del team; `ZARIS TEAM WEB` está en plan Hobby, sumar miembros exige Pro — decisión de facturación de César). **EN PAUSA** mientras Roy no esté activo; mitigación `git merge --no-ff` o commit vacío de re-trigger.
- 🟡 **Barrido visual de modo oscuro** en los módulos React restantes (solo Dashboard y Guías verificados en dark): **POSPUESTO por César 2026-09-20**, retomar cuando lo pida.

**Decisiones cerradas — NO re-proponer**
- **São Paulo DESCARTADO (César, 2026-09-26, con medición).** Railway ya está co-locado con Supabase `us-east-1` (round-trip 4-5 ms; la DB ejecuta en 1-3 ms) y NO ofrece región en Sudamérica. Mover SOLO la DB **empeora**; bajar el piso de ~150 ms por request desde Argentina exige salir de Railway + Supabase nuevo (~150 → ~40 ms, no justificado). Cifras, cómo medir sin engañarse y qué haría falta: CLAUDE.md §9 «Región» y memoria `project_migrar_region_sao_paulo`.
- **"La ubicación" de Buscar actualizaciones (PWA, reunión 2026-07-14 §4) CERRADA como innecesaria** (César, 2026-09-26): la PWA ya se actualiza sola con el service worker (`registerType: 'autoUpdate'`); no hay chequeo externo que definir. Si algún día va a tiendas, ahí se revisa.
- `DISPATCHER_TOKEN` no se rota ("eso queda así", César 2026-09-06); el secret sobrante `ZARIS_DISPATCHER_TOKEN` también queda.
- El vecino NO cambia su email desde la app (2026-08-30).
- Purga del historial git HECHA el 2026-09-20 (mapa de SHAs en `docs/commit-map-purga-2026-09-20.txt`); el residuo (commits viejos accesibles por SHA en GitHub hasta que Support los purgue) no se pide.
- Fase 3 de roles (mig 92, niveles 1-5) y la auditoría de seguridad 2026-07 (48/48) están COMPLETAS; residuos conscientes en la skill `modulo-tramites`.

---

## ✅ Hecho reciente (últimas sesiones)

- **2026-09-26 — App de agentes (`zaris-agentes`, `dd559f5`) + backend de push para usuarios internos (mig 108).** PWA nueva con login de ZARIS, mesa del agente, detalle de OT (mapa, cómo llegar, vecino, evidencia con cámara, cambio de estado), Cuenta (foto, push, clave). Backend: tabla `usuario_push_subscription`, router `/auth/push/*`, hook `notificar_ot_asignada` en alta/reasignación de OT, CORS de la app. Verificado en local contra la DB (estado de OT y evidencia).
- **2026-09-26 — «Mi perfil» del usuario — EN MAIN (`4be8773`)**: módulo React `web-app/src/modules/perfil/` (`#/perfil`, sin permiso, oculto del sidebar) con cabecera (foto/nombre/rol/cargo/gestión + cambiar/quitar foto), tarjeta «Portal del Ciudadano» (QR 220 px + link + copiar + pasos Android/iPhone; URL desde `GET /config/identidad.app_vecinos_url` = env `APP_VECINOS_FRONTEND_URL`, sin migración), cambio voluntario de clave (fetch directo: el 401 «actual incorrecta» NO desloguea) y «Módulos a los que accedés». Ítem «Mi perfil» + bloque de nombre clickeable en el menú del avatar (`menu.js` escucha `storage` → topbar con la foto nueva sin recargar). Verificado en local con navegador (shell 8080 + dev 5173, usuario n3): clave 401/OK con DB, foto Storage+DB+topbar, dark OK.
- **2026-09-26 — São Paulo medido y descartado** (ver Decisiones cerradas): backup de prod (`zaris_prod_2026-09-26_1835.sql`), sondeo de solo lectura de prod (32 MB, PG 17.6, 111 tablas, 3 buckets/17 objetos, 2 URLs absolutas del proyecto Supabase en filas), línea base de latencia por endpoint y `pg_stat_statements`. Sin cambios de código ni de infra. El dato "14,5 min del generador demo en prod" queda **descartado** por César (caso aislado, sin reuso): no citarlo como evidencia de latencia ni investigarlo.
- **2026-09-22 — Poda de este archivo + cron de datos demo robusto** (`14f125e`): el `failure` del 21/09 fue el edge de Railway cortando a los 300 s con el backend terminando igual (datos en una sola capa, no se re-dispatchó). `POST /demo/poblar` pasa a **202 + `id_corrida`**, `GET /demo/poblar/{id_corrida}` = `en_curso | ok | error` + conteos, **409 si ya hay corrida** (anti doble capa); el workflow hace polling 20 s hasta 40 min. Smoke `backend/smoke_demo_poblar.py` 15/15; verificado en prod con un dispatch manual sobre un día ya poblado (run `35801035544`, `ok` en 27 s, conteos idénticos).
- **2026-09-20 — Búsqueda diferida (§23) como estándar de la suite — EN PROD** (`4c7e615` + dist CI `24921a4`): 13 pantallas de listado sin precarga; helper `web-app/src/ui/busqueda.tsx`. Mismo día: **Atención CERRADO** (QA de César OK en F3-F6), **purga del historial git** (`git filter-repo` quirúrgico, árbol de `main` intacto, bundle pre-purga en `backups/`), disponibilidad L-V 08-16 al agente 89 (prestación "Inscripción Profesional", Gobierno), planilla `credenciales-testing/` al día (médicos 99/100, Pestto, Kramer, `cesar@`).

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
| Qué migración hace qué / cuándo se aplicó | [`HISTORIAL_MIGRACIONES.md`](HISTORIAL_MIGRACIONES.md) |
| Contrato de la API pública que consume la PWA | [`docs/contrato_api_publica.md`](docs/contrato_api_publica.md) |
| Cómo arrancar local / colaborar | [`ONBOARDING.md`](ONBOARDING.md) · [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Quirks/patrones/decisiones (foto de las memorias) | [`docs/memoria-proyecto/`](docs/memoria-proyecto/) |
