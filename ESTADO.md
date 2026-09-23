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

**Última actualización:** 2026-09-22 (Cesar). Poda de este archivo (63 KB → ~12 KB, pedido de César del 20/09) + **cron de datos demo robusto** (`POST /demo/poblar` asíncrono con 202 + polling, ver Hecho reciente). Foto de la infra al 22/09: todo verde — GH Pages en `6043255` sirviendo `index-YwhghPq4.js`, Railway con `/bi/atencion/*` (F6) aplicado, PWA 200, crons de encuestas/integridad/trámites en `success`. El único rojo era el cron "Datos demo BI" del lunes 21/09: **falso negativo** (el edge de Railway cortó la respuesta a los 300 s; el backend terminó igual y los datos de la semana 15-21/09 quedaron correctos y en una sola capa; NO se re-dispatchó). Decisiones vigentes de César (2026-09-20): modo oscuro pospuesto · Roy inactivo por ahora · próxima sesión **São Paulo + "la ubicación"** (a precisar con César).

---

## 🔵 En curso

- **Nada en desarrollo activo.** El proyecto **Atención por ubicación** (6 fases: ubicación obligatoria, Mesa del día, colero, Guardia, historia clínica, BI de atención) quedó **CERRADO el 2026-09-20** con el QA de César en prod. Roadmap, decisiones por fase y residuos en [`PLAN_MODULO_ATENCION.md`](PLAN_MODULO_ATENCION.md) (§4 Pendientes).
- **Próximo (acordado con César 2026-09-20/22):** São Paulo (mover backend Y DB a `sa-east-1`, sesión dedicada con backup — ver Pendientes) y "la ubicación" (a precisar con César; probablemente la ubicación externa de "Buscar actualizaciones" de la PWA, reunión 2026-07-14 §4).

> ### 📣 Para quien retome la PWA `zaris-vecinos` (Roy inactivo por ahora — César 2026-09-20)
> El backend ya entregó EN PROD (2026-08-30) todo lo que la PWA tenía como `TODO(backend)`: `GET/PUT /publico/perfil`, `GET/PATCH/POST /publico/avisos` (+ `mi-resumen.avisos.no_leidos`), `GET /publico/reclamos/geo/reverse` y la foto de perfil (`POST/DELETE /publico/perfil/foto`, mig 102). Contrato en [`docs/contrato_api_publica.md`](docs/contrato_api_publica.md) §4/§5/§10/§11; el detalle de qué consumir y dónde, en `zaris-vecinos/ESTADO.md` → Pendientes. Cambio de contrato previo (2026-07-15, ya en la tabla del contrato): `POST /publico/alta/empresa` exige el vecino logueado (401 sin token) y ya NO toma `id_ciudadano` del body.

---

## 🟠 Pendientes (backoffice / backend)

**Verificaciones humanas (César)**
- 🟡 **Recorrido en PROD (iframe real) de las 13 pantallas con búsqueda diferida (§23):** Reclamos, OT ×3, Trámites ×2 (Buscar deja `?buscar=1`; un deep link con filtros arranca buscado), Agenda ×3 ("Ver agenda" antes de la grilla; navegar fechas después re-pide), Entradas, Encuestas → Envíos, Ciudadanos/Empresas → Listado (el botón "Listado" del buscador llega ya buscado). Verificado en local pantalla por pantalla el 2026-09-20; falta solo la mirada humana en prod.
- 🟡 **Cron "Datos demo BI" del lunes 2026-09-28:** primera corrida con el flujo 202 + polling. Esperado: run `success` y el JSON de `generado` / `generado_atencion` / `avanzado` / `avanzado_atencion` en el log. Si falla, **verificar la DB antes de re-dispatchar** (regla del incidente 2026-08-31; memoria `project_cron_demo_502_railway_timeout_5min`).
- 🟡 **Trámites — primer aviso REAL del ciclo de vida ~2026-10-06:** los 2 expedientes con mail real (`HAB-LPL-2026-0001`, `CAR-LPL-2026-0002`) tienen el reloj en cero desde el 2026-09-06; verificar entonces que el cron mande UN aviso y nada más.

**Decisiones de negocio pendientes (César)**
- 🟠 **Atención — residuos del plan (§4):** export PDF "Prestaciones realizadas" de Consultas saca intervención/recomendaciones sin el guard de historia clínica (quitar / gatear por `/permiso` / dejar) · marcar `registra_atencion=true` en TODAS las prestaciones de Salud (dato de negocio, prod no verificado) · "ocupación vs disponibilidad efectiva" en el BI de atención (hoy ocupación = turnos + horas atendidas, sin % sobre la agenda) · etapa 2 de HC (vista admin de `historia_clinica_acceso`, break-the-glass, ficha ampliada) · walk-in de Guardia sin evento de Emergencias.
- 🟠 **Trámites — 2 residuos:** (a) las transiciones finales de los seeds usan `tipo_accion='avanzar'` (solo 6 tienen `aprobar`/`rechazar`) → el resultado automático y la encuesta CSAT no se disparan solos en la mayoría de los tipos (se puede mapear por estado destino); (b) los 4 tipos sin circuito (exención de tasas, permiso de espacio público, arbolado urbano, inscripción profesional) tienen la gestión asignada por criterio de Claude, cambiable desde el builder.
- 🟠 **Áreas fijas por regla de negocio** (planteado 2026-08-30): Seguridad, Salud, Servicios Públicos… precargadas y NO removibles (renombrables sí) porque atienden módulos (Emergencias→Seguridad, Turnos→Salud, Reclamos→Servicios Públicos). Sin código todavía: establecer la regla y analizarla junto con seeds, admin_tablas, baja lógica y IT-01.
- 🟠 **Config/UX — reunión 2026-07-06** (informe en la tarea "Informe Bug" de la lista CONFIGURACION y UX de ClickUp): **IT-01** multi-tenant + super administrador + selector de municipio — proyecto de arquitectura (consolidar la identidad repartida entre `municipios` y `configuracion_general`; diseñar por fases con César; DESPUÉS del seed demo, decisión 2026-08-30) · **IT-08** botón SOS de la PWA (definir qué acción dispara) · **IT-07** accesibilidad móvil (PWA, otro repo) · **IT-09** módulo de Obras (backlog sin alcance).
- 🟢 **Baja de cuenta del vecino:** sin endpoint ni definición; obligatoria si la app va a las stores.

**Infra / operativo**
- 🟠 **São Paulo (`sa-east-1`) — próxima sesión.** Supabase `ZARIS GESTION ESTADO` (`lshfwsscvfsklrmbvkwl`) está en `us-east-1`; la org ya tiene `zaris-news-bot` en `sa-east-1`. Mover un proyecto Supabase de región = proyecto nuevo + migrar datos + repuntar connection strings/env vars → **sesión dedicada con backup y ventana**. **Antes:** mirar la región de compute de Railway en el dashboard (Settings → Region; desde afuera solo se ve el edge `gru1`) — mudar solo la DB no gana nada si Railway sigue en US; el objetivo es backend Y DB en `sa-east-1`. Pedido de César 2026-07-15, reconfirmado 2026-09-20.
- 🟡 **Vercel: los deploys de Roy quedan BLOCKED** (autor fuera del team; `ZARIS TEAM WEB` está en plan Hobby, sumar miembros exige Pro — decisión de facturación de César). **EN PAUSA** mientras Roy no esté activo; mitigación `git merge --no-ff` o commit vacío de re-trigger.
- 🟡 **Barrido visual de modo oscuro** en los módulos React restantes (solo Dashboard y Guías verificados en dark): **POSPUESTO por César 2026-09-20**, retomar cuando lo pida.

**Decisiones cerradas — NO re-proponer**
- `DISPATCHER_TOKEN` no se rota ("eso queda así", César 2026-09-06); el secret sobrante `ZARIS_DISPATCHER_TOKEN` también queda.
- El vecino NO cambia su email desde la app (2026-08-30).
- Purga del historial git HECHA el 2026-09-20 (mapa de SHAs en `docs/commit-map-purga-2026-09-20.txt`); el residuo (commits viejos accesibles por SHA en GitHub hasta que Support los purgue) no se pide.
- Fase 3 de roles (mig 92, niveles 1-5) y la auditoría de seguridad 2026-07 (48/48) están COMPLETAS; residuos conscientes en la skill `modulo-tramites`.

---

## ✅ Hecho reciente (últimas sesiones)

- **2026-09-22 — Poda de este archivo + cron de datos demo robusto.** Verificado que el `failure` del cron del 21/09 fue el proxy de Railway (502 "upstream error" a los 300 s exactos) con el backend terminando igual: 4 pasos commiteados hasta las 15:22 UTC, reclamos 15-21/09 y turnos 22-28/09 en una sola capa. `POST /demo/poblar` pasa a **encolar la corrida en un BackgroundTask y responder 202** con `id_corrida`; `GET /demo/poblar/{id_corrida}` devuelve `en_curso | ok | error` + el JSON de conteos (parcial si falló a mitad); **409 si ya hay una corrida en curso** (anti doble capa). El workflow acepta 200 (deploy viejo) o 202 + polling cada 20 s hasta 40 min, y falla con aviso "verificar DB" si la instancia se reinició (404). Smoke in-process `backend/smoke_demo_poblar.py` (15/15) + uvicorn local (202 en 4 ms, 409 en simultáneo; la misma semana tarda 1 s en local vs 14,5 min en prod → el cuello es la latencia Railway↔Supabase, argumento para São Paulo). **Verificado en PROD** (commit `14f125e`, Railway aplicó a los 80 s): dispatch manual del workflow con `desde=hasta=2026-09-20, modulos=atencion` → run `35801035544` `success`, 202 → `ok` a los 27 s con el JSON en el log; conteos demo antes/después idénticos (turnos 3044, reclamos 2448, eventos 47, derivaciones 185) y el `avanzar` resolvió los 47 turnos vencidos del 21-22/09.
- **2026-09-20 — Búsqueda diferida (§23) como estándar de la suite — EN PROD** (`4c7e615` + dist CI `24921a4`): 13 pantallas de listado sin precarga; helper `web-app/src/ui/busqueda.tsx`. Mismo día: **Atención CERRADO** (QA de César OK en F3-F6), **purga del historial git** (`git filter-repo` quirúrgico, árbol de `main` intacto, bundle pre-purga en `backups/`), disponibilidad L-V 08-16 al agente 89 (prestación "Inscripción Profesional", Gobierno), planilla `credenciales-testing/` al día (médicos 99/100, Pestto, Kramer, `cesar@`).
- **2026-09-19 — Atención F6: BI de atención por gestión + generador demo de atención — EN PROD** (`89b5382`, dist `522e34d`, `bc78746`/`ea2f539`/`88bf553`): `/bi/atencion` (19 rutas, sin migración, smoke 85/85) y `demo_atencion.py` (turnos/colero/llamados/Guardia/eventos; `POST /demo/poblar modulos=[reclamos,atencion]`; cron semanal; idempotente por recurso/día). Prod cargada abril → 19/09.
- **2026-09-13 — Atención F5: historia clínica mínima viable (migs 107 + 107b) — EN PROD.** `GET /turnos/atenciones/historia` (turnos ∪ Guardia), guard Salud + nivel 1 por `agentes.id_subarea` y clave `id_area_salud`, log append-only `historia_clinica_acceso`, UI gateada por `/permiso`. Smoke 61/61. **Próxima migración: 108.**
- **2026-09-06 — Atención F3 (colero, mig 105) + F4 (Guardia, migs 106/106b) — EN PROD**; búsqueda diferida en Turnos; agrupación de Trámites por gestión (mig 104, área "Secretaría de Gobierno"); ciclo de vida hacia el vecino ACTIVADO (6 estados `espera_iniciador`, SLA en 15/15 tipos, relojes de los 2 expedientes reales en cero; backup `_backup_ciclo_vida_2026_09_06`); color de marca `#1f8a65`. Médicos de guardia demo (usuarios 99/100) el 2026-09-12.
- **2026-09-01 — 5ª tanda del BI + QA del BI cerrado por César; Atención F1 + F2 + F2b** (mig 103: ubicación obligatoria en toda prestación, Turnos ubicación-primero con Mesa del día, Agenda "Por ubicación").

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
