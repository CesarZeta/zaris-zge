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

**Última actualización:** 2026-10-21 (Cesar, sesión larga). Seguridad de Maestros y de la lectura de cuentas; reclamos sin agenda (asignación por menor carga); Tomar/Resolver desde Reclamos con la resolución que ve el vecino (migs 115-118: baja de «Emergencia Climática», coherencia usuario/agente/ficha); `agente.csv` con datos reales fuera del repo y del historial (2ª purga: los SHA desde mayo cambiaron, mapa en `docs/`); generador de datos demo con SLA 60-85 %, trámites, OT y cron diario, corrido en prod (abril-octubre entre 60,4 % y 77,6 % dentro del SLA).

---

## ❓ Preguntas abiertas para César — se plantean en la PRIMERA respuesta de la próxima sesión

> Regla de César (2026-10-20): al cerrar se anota todo lo abierto; al arrancar se pregunta primero. Lo sensible (seguridad) tiene el detalle en la memoria privada de Cesar, no acá (este archivo es público).

1. ✅ Seguridad del 2026-10-21: la parte (a) está en prod y verificada; la parte (b) **la descartó César** (no se hace, no re-proponer).
2. ✅ Subárea usuario ≠ agente: **resuelto 2026-10-21** (mig 116 + el cierre de reclamos lee la gestión del agente).
3. **Autoasignación:** ya NO necesita horarios y elige por menor carga (2026-10-21). ¿En qué gestiones la prendo (Maestros → Subáreas)? *Recomendación:* empezar por Alumbrado Público (tiene agentes de Gestión y reclamos sin asignar) y mirar una semana.
4. **Funcionario de prueba:** César asigna REC-2026-003079 (Arbolado, sin asignar) al funcionario de prueba desde la mesa (Ver → PLANIFICAR) y confirma si el push llega. Yo no tengo credenciales de un supervisor de Arbolado (y no se prueban claves).
5. ✅ Agentes sin ficha: **resuelto 2026-10-21** (mig 118, fichas demo; 0 personas sin ficha).
5b. **34 reclamos viejos abiertos que NO son del generador** (QA de abril-agosto y vecinos de prueba con cuenta, `@zaris.com.ar`/gmail): el cierre del atraso los dejó como estaban. Entre ellos REC-2026-000058/059, que `docs/guion_demo_reclamos_ot.html` usa «congelados en el paso 8». ¿Los cierro también (salvo los del guion), o se quedan? *Recomendación:* cerrarlos salvo 058/059 (`modo=cerrar_atraso` no excluye ids: hacerlo con una corrida acotada o por SQL replicando el plan).
5c. **PWA del vecino:** la resolución ya le llega como nota del paso «Resuelto» del historial (sin cambiar la PWA). ¿Querés además un recuadro «Resolución» destacado en el detalle del reclamo de la app? *Recomendación:* sí (cambio chico en `zaris-vecinos`, el backend ya manda `resolucion`).
5d. **Encuesta de mayo trabada:** el envío #6 (reclamo 35) sigue `pendiente` desde el 2026-05-25 y el despachador nunca lo mandó. *Recomendación:* revisar por qué (¿falta de email válido? ¿delay?) y cerrarla o mandarla.
5e. **Commits viejos de la purga del 2026-10-21:** GitHub los conserva accesibles por SHA directo hasta que su soporte los borre. *Recomendación:* pedirlo (detalle en la memoria privada de Cesar).
6. **Orden por columnas F2** (trámites, turnos, entradas) **y F3** (resto): ¿avanzo?
7. **Links de los mails de notificación** abren el inicio en vez del trámite/reclamo (el shell ignora el `#/…`): ¿lo arreglo?
8. **Super administrador multi-municipio (IT-01):** ¿cuándo arrancamos el diseño?
9. Sin respuesta de sesiones anteriores: mail real del retrabajo (¿lo pruebo con tu vecino de prueba?) · PWA modo escritorio (falta plan) · propuesta app de agentes (reclamos de oficio + control de entradas) · vecino trabado desde junio (¿reenviar activación?) · ¿app del vecino con email además de DNI? · quitar el alias `email` de los logins · borrar `_cuentas_caps/` · mapa del inicio en oscuro · «Ver pendientes» en mayúsculas.

---

## 🔵 En curso

- **Prueba real del funcionario — a medias (2026-10-20).** Ciudadano 1868 → usuario 101 (nivel 4), agente 97 con datos reales, subárea Arbolado (12); mail, cambio de clave, login y **push activado** (primera suscripción de prod). **Falta:** asignarle una OT (REC-2026-003079 pasó a Arbolado con la mig 115 y está sin asignar) y que César confirme que el aviso llega al teléfono y a `/avisos`.
- **Auditoría de reclamos — circuito completo en prod (F1-F4, 2026-10-20).** Queda solo la **prueba real del mail en prod**: no se observó ninguna auditoría real con «Sí» (el mail se verificó en MOCK, y el link del botón → `https://vecinos.zaris.com.ar/reclamos` da 200). Se puede hacer con el vecino de prueba de César (manda un correo real a su casilla) o esperar el primer uso real.
- **PWA `zaris-vecinos` — modo escritorio del portal: diseño aprobado el 2026-10-12 (3ª), falta plan + código.** Solo toca el repo de la PWA; spec y pasos en su `ESTADO.md` → En curso.
- **PROPUESTA sin aprobar — app de agentes: reclamos de oficio + «Control de entradas» (QR).** Pedido de César al cierre del 2026-10-12; las 4 decisiones de alcance ya están tomadas (de oficio · niveles 1-4 · acreditar niveles 1-4 · nombre «Control de entradas») y el diseño está escrito en [`PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md`](PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md). **Próxima sesión: César confirma o corrige el diseño y recién ahí F1 (backend sin migración + smoke).** No hay código.
- **App de agentes** publicada en `https://agentes.zaris.com.ar` (color del municipio, instalación desde «Mi perfil»); el vecino instala la suya desde su portal. Detalle en `zaris-agentes/ESTADO.md`.

> ### 📣 Para quien retome la PWA `zaris-vecinos` (Roy inactivo por ahora — César 2026-09-20)
> **Desde el 2026-09-26 la PWA ya consume TODO lo que el backend entregó el 2026-08-30** (perfil + edición de teléfono/domicilio, bandeja de avisos con badge, `geo/reverse`, foto de perfil en el backend). Lo que falta del lado suite para la PWA es solo backend NUEVO: `GET /publico/noticias` y URLs de redes en `identidad-municipio` (las secciones están ocultas mientras tanto), emergencias en `mi-resumen`, y la baja de cuenta. Contrato en [`docs/contrato_api_publica.md`](docs/contrato_api_publica.md). Cambio de contrato previo (2026-07-15, ya en la tabla): `POST /publico/alta/empresa` exige el vecino logueado (401 sin token) y ya NO toma `id_ciudadano` del body.

---

## 🟠 Pendientes (backoffice / backend)

**Próxima sesión — prueba de las apps (César)**
- 🟡 **Perfiles de prueba** (emails en la memoria privada de Cesar): vecino HECHO (2026-10-12; el botón de pánico no se probó, dispara una alerta REAL); funcionario: falta el push (ver En curso).
- 🟢 **Retirar `GET /ot/slots-recurso`, `POST /ot/con-agenda` y `services/ot_slots.py`** (sin uso desde 2026-10-21, quedaron por compatibilidad con el bundle anterior) en una sesión posterior, verificando antes que ningún cliente los llame.
- 🟢 **Circuito funcionario → agente: HECHO (2026-10-20/21).** Datos personales solo de la ficha; cargo/horario/equipo los completa el supervisor de la gestión (mig 113); una sola gestión y email por persona, la del agente (mig 116); toda persona con usuario tiene ficha (mig 118, fichas demo con DNI 99.000.000 + id_agente). Ojo: guardar una de esas fichas por la API crea la cuenta de App Vecinos y manda la activación al email de la cuenta (`@municipio.gob.ar`, que no existe). Pendiente de IT-01: el super administrador multi-municipio.
- 🟢 **Drift de FK:** `usuarios.id_subarea`/`agentes.id_subarea` → `subarea` existe en local y NO en prod (candidata a mig 119+).

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
- **São Paulo DESCARTADO (César, 2026-09-26, con medición):** Railway ya está co-locado con Supabase `us-east-1` y no ofrece región en Sudamérica. Detalle en CLAUDE.md §9 «Región».
- **"La ubicación" de Buscar actualizaciones (PWA) CERRADA como innecesaria** (2026-09-26): el service worker con `autoUpdate` alcanza.
- `DISPATCHER_TOKEN` no se rota (César 2026-09-06). El vecino NO cambia su email desde la app (2026-08-30).
- Purgas del historial git HECHAS el 2026-09-20 y el 2026-10-21 (mapas en `docs/commit-map-purga-*.txt`; un SHA viejo que no resuelve se busca ahí). Roy tiene que re-clonar.
- Claves de las notificaciones push: **no se rotan** (César, 2026-10-21).
- Los reclamos **no se agendan**: la agenda es solo para turnos (César, 2026-10-21).
- Fase 3 de roles (mig 92) y la auditoría de seguridad 2026-07 (48/48) COMPLETAS.

---

## ✅ Hecho reciente (últimas sesiones)

- **2026-10-21 (noche) — Generador de datos demo con SLA, trámites, OT y cron diario; corrido en prod.** Smoke 44/44 re-verificado; resultado por SQL en «Última actualización».
- **2026-10-21 (tarde) — Tomar/Resolver desde Reclamos + resolución para el vecino (mig 117), coherencia de cuentas (migs 116 y 118), purga de `agente.csv`.** Smokes 22/22 y 5/5 en local; Tomar → Resolver verificado en prod con un Gestión de Alumbrado (REC-2026-002927).
- **2026-10-21 — Seguridad del CRUD de Maestros (`f90b894`); mesa del supervisor con fecha y PLANIFICAR en «Ver» (`bcb1b13`, `bd69fe2`); reclamos sin agenda + mig 115 (`fdca998`).** Smokes 38/38 y 11/11 en local; seguridad y mesa verificadas en prod (API + navegador).
- **2026-10-20 (4ª, noche) — Ficha → agente, supervisor en Maestros → Agentes (mig 113), aviso «agente nuevo»; autoasignación (mig 114).** Smokes 16/16 y 7/7; en prod salvo el backend de la autoasignación (pregunta 2).
- **2026-10-20 (4ª, tarde) — Destinatario de OT validado, aviso a la cuadrilla, mesa del supervisor, orden por columnas F1, `/avisos` en la app de agentes.** Smoke 9/9 + navegador; en prod.
- **2026-10-20 — Auditoría de reclamos POSTERIOR al cierre (migs 112, F1-F4) y «Ver pendientes».** Detalle en `PLAN_AUDITORIA_RECLAMOS.md`.

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
