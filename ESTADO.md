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

**Última actualización:** 2026-10-12 (Cesar, 2ª sesión). **Autogestión del alta del vecino — huecos cerrados, EN PROD** (`1556406` + PWA `fd5268c`): al repasar el circuito con César se vio que ni la pantalla «alta registrada», ni el mail de verificación, ni la página «Correo verificado» le decían al vecino a dónde seguir. Ahora: botón **«Ir al Portal del Ciudadano»** en las dos pantallas finales de `alta-vecino.html` (`GET /publico/alta/identidad` expone `app_vecinos_url`), en la página de verificación (ciudadano y empresa) y como línea extra del mail (HTML y texto); la página de **enlace vencido** manda a la página de alta («Activar mi cuenta» con el DNI); el **login de la PWA** suma «¿No tenés cuenta? Creala acá». `backend/app/core/urls.py` = fuente única de URLs públicas (fail-closed: con basura en la env var no se pinta nada). Smoke in-process `smoke_alta_portal_links.py` 24/24 (SIGUE el link del mail), navegador local (las 4 pantallas) y prod (OpenAPI de Railway + Pages + bundle de Vercel). **César ya pasó los dos emails de la prueba** (viven en la memoria privada de Cesar, no en este archivo público; verificados libres en prod). Sesión anterior (2026-10-12, 1ª): **Circuito de alta de cuentas ZARIS desde la ficha del ciudadano — EN PROD** ([`PLAN_CUENTAS_FUNCIONARIO.md`](PLAN_CUENTAS_FUNCIONARIO.md), mig 110 local + prod): tilde «Este ciudadano es funcionario del municipio» en la ficha; el botón del pie pasa a **«Crear cuenta aplicación ZARIS»** (sin tilde = cuenta de App Vecinos como antes; con tilde = cuenta ZARIS, solo Administrador, mini-modal nivel/subárea/usuario) → usuario vinculado (`usuarios.id_ciudadano`) + agente 1:1 con datos reales + mail con clave temporal y link a la app de agentes; chips «Cuentas» en la ficha; **login de ZARIS y de la app de agentes por email O DNI** (`identificador`); bloque «La app en tu teléfono» en «Mi cuenta» de la app de agentes. Manuales: `docs/manual_alta_ciudadanos.html` §4 (regenerado, 8 capturas) + **`docs/manual_app_agentes.html`** (nuevo, en Guías). Verificado: smoke 36/36, navegador local (admin / nivel 2 / login por DNI en los 3 logins), prod (OpenAPI + bundle + Vercel + `curl` de los dos links del mail).

---

## 🔵 En curso

- **Todo listo para la prueba real en el celular** (pedido de César 2026-10-10, circuito implementado 2026-10-12): ver Pendientes → «Próxima sesión». Nada en desarrollo activo.
- **PROPUESTA sin aprobar — app de agentes: reclamos de oficio + «Control de entradas» (QR).** Pedido de César al cierre del 2026-10-12; las 4 decisiones de alcance ya están tomadas (de oficio · niveles 1-4 · acreditar niveles 1-4 · nombre «Control de entradas») y el diseño está escrito en [`PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md`](PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md). **Próxima sesión: César confirma o corrige el diseño y recién ahí F1 (backend sin migración + smoke).** No hay código.
- Proyecto **Atención por ubicación** CERRADO el 2026-09-20; residuos en [`PLAN_MODULO_ATENCION.md`](PLAN_MODULO_ATENCION.md) §4 (los dos de privacidad quedaron resueltos el 2026-10-10).
- **App de agentes** publicada en `https://agentes.zaris.com.ar` (color del municipio, instalación desde «Mi perfil»); el vecino instala la suya desde su portal. Detalle en `zaris-agentes/ESTADO.md`.

> ### 📣 Para quien retome la PWA `zaris-vecinos` (Roy inactivo por ahora — César 2026-09-20)
> **Desde el 2026-09-26 la PWA ya consume TODO lo que el backend entregó el 2026-08-30** (perfil + edición de teléfono/domicilio, bandeja de avisos con badge, `geo/reverse`, foto de perfil en el backend). Lo que falta del lado suite para la PWA es solo backend NUEVO: `GET /publico/noticias` y URLs de redes en `identidad-municipio` (las secciones están ocultas mientras tanto), emergencias en `mi-resumen`, y la baja de cuenta. Contrato en [`docs/contrato_api_publica.md`](docs/contrato_api_publica.md). Cambio de contrato previo (2026-07-15, ya en la tabla): `POST /publico/alta/empresa` exige el vecino logueado (401 sin token) y ya NO toma `id_ciudadano` del body.

---

## 🟠 Pendientes (backoffice / backend)

**Próxima sesión — prueba de las apps (César)**
- 🟡 **Perfiles de prueba:** César ya pasó los dos emails el 2026-10-12 (quedaron en la memoria privada de Cesar, NO acá — este archivo es público; verificados libres en prod). Circuito a recorrer: (a) **funcionario**: alta en Ciudadanos con el tilde «funcionario del municipio» → «Crear cuenta aplicación ZARIS» (admin) → mail con usuario (email o DNI) + clave temporal + link de la app de agentes → instalar la app → login con DNI → cambio forzado → push real al asignarle una OT; (b) **vecino** autoregistrado desde la página pública (`url_alta_publica` de `/publico/identidad-municipio`) → primer uso real del link de verificación arreglado → instalar la app del vecino → botón de pánico **con el backoffice a la vista** (dispara una alerta REAL al COM). Guías para acompañar: `manual_alta_ciudadanos.html` §4 y `manual_app_agentes.html`.
- 🟢 **Decisión pendiente (no bloquea):** si la app del vecino también acepta email además del DNI (hoy el contrato público es DNI + clave; es un cambio chico de backend + etiqueta de la PWA).
- 🟡 **Entrega de mails en prod NO verificada** (Resend): no hay acceso a sus logs desde acá. La prueba de arriba la confirma (o César mira el dashboard de Resend).
- 🟠 **Vecino trabado por el link roto:** 1 ciudadano `auto_registrado` con clave elegida y credencial sin activar desde el 2026-06-12 (prod). Decisión de César: reenviarle la activación (implica escribirle a una persona real) o dejarlo.

**Decisiones de negocio pendientes (César)**
- 🟢 **Alta — huecos menores detectados en la revisión 2026-10-10:** la clave temporal del funcionario no vence si nunca la usa; la app de agentes no tiene «olvidé mi contraseña» (hoy se recupera desde el login del backoffice, link 24 h). El vecino NO recibe clave por mail (elige la suya por link) — recomendado mantenerlo.
- 🟠 **Atención — residuos del plan (§4):** "ocupación vs disponibilidad efectiva" en el BI de atención · etapa 2 de HC (vista admin de `historia_clinica_acceso`, break-the-glass, ficha ampliada) · walk-in de Guardia sin evento de Emergencias.
- 🟠 **Trámites — 2 residuos:** (a) las transiciones finales de los seeds usan `tipo_accion='avanzar'` (solo 6 tienen `aprobar`/`rechazar`) → el resultado automático y la encuesta CSAT no se disparan solos en la mayoría de los tipos (se puede mapear por estado destino); (b) los 4 tipos sin circuito (exención de tasas, permiso de espacio público, arbolado urbano, inscripción profesional) tienen la gestión asignada por criterio de Claude, cambiable desde el builder.
- 🟠 **Áreas fijas por regla de negocio** (planteado 2026-08-30): Seguridad, Salud, Servicios Públicos… precargadas y NO removibles (renombrables sí) porque atienden módulos. Sin código todavía: analizar junto con seeds, admin_tablas, baja lógica y IT-01.
- 🟠 **Config/UX — reunión 2026-07-06** (tarea "Informe Bug" de la lista CONFIGURACION y UX de ClickUp): **IT-01** multi-tenant + super administrador + selector de municipio (proyecto de arquitectura, por fases con César) · **IT-08** botón SOS de la PWA · **IT-07** accesibilidad móvil (PWA) · **IT-09** módulo de Obras (backlog sin alcance).
- 🟢 **Baja de cuenta del vecino:** sin endpoint ni definición; obligatoria si la app va a las stores.

**Infra / operativo**
- 🟡 **Vercel: los deploys de Roy quedan BLOCKED** (autor fuera del team; plan Hobby, sumar miembros exige Pro — decisión de facturación de César). **EN PAUSA** mientras Roy no esté activo; mitigación `git merge --no-ff` o commit vacío de re-trigger.
- 🟡 **Barrido visual de modo oscuro** en los módulos React restantes: **POSPUESTO por César 2026-09-20**.

**Decisiones cerradas — NO re-proponer**
- **São Paulo DESCARTADO (César, 2026-09-26, con medición):** Railway ya está co-locado con Supabase `us-east-1` y no ofrece región en Sudamérica. Detalle en CLAUDE.md §9 «Región».
- **"La ubicación" de Buscar actualizaciones (PWA) CERRADA como innecesaria** (2026-09-26): el service worker con `autoUpdate` alcanza.
- `DISPATCHER_TOKEN` no se rota (César 2026-09-06). El vecino NO cambia su email desde la app (2026-08-30).
- Purga del historial git HECHA el 2026-09-20 (mapa en `docs/commit-map-purga-2026-09-20.txt`).
- Fase 3 de roles (mig 92) y la auditoría de seguridad 2026-07 (48/48) COMPLETAS.

---

## ✅ Hecho reciente (últimas sesiones)

- **2026-10-12 (2ª) — Autogestión del alta del vecino: el circuito le dice a dónde seguir (`1556406`, PWA `fd5268c`, sin migración).** Botón «Ir al Portal del Ciudadano» en las pantallas finales de la página de alta, en la página de verificación y en el mail; «Volver a la página de alta» cuando el enlace venció; link de registro también en el login de la PWA. `core/urls.py` (fuente única, fail-closed). Smoke `smoke_alta_portal_links.py` 24/24 + navegador + prod.
- **2026-10-12 — Circuito de alta de cuentas ZARIS (mig 110, F1-F5 del plan, en prod).** Backend: `services/cuenta_zaris.py` compartido por `POST /buc/usuarios` y el nuevo `POST /buc/ciudadanos/{id}/cuenta-zaris` (solo admin; agente 1:1 con nombre/apellido/DNI/CUIL/email/teléfono reales; asegura la cuenta de vecino si no existía); `GET /buc/ciudadanos/{id}/cuentas`; login por `identificador` (email o DNI; `email` sigue como alias); mail de credenciales con «email o DNI» + link de la app de agentes; cron de integridad también por `id_ciudadano`. Front: sección «Funcionario municipal», botón único con cuatro estados, `CuentaZarisModal`, `CuentasChips`; `login.html`/LoginPage dev «Correo electrónico o DNI». App de agentes (`zaris-agentes` `ed52ea9`/`50a04cd`): login email o DNI + `BloqueInstalar` en «Mi cuenta». Smoke `smoke_cuentas_funcionario.py` 36/36. Decisiones y alcance en `PLAN_CUENTAS_FUNCIONARIO.md`; reglas en la skill `modulo-usuarios`.
- **2026-10-10 — Contenido clínico de `GET /turnos/atenciones` detrás del guard de historia clínica** (decisión de César: gatear). El endpoint alimentaba la pantalla de Consultas, el detalle del turno y el PDF, y en prod dejaba leer las 1.301 atenciones de Odontología a cualquier nivel ≤ 2 de cualquier área, sin registro. Ahora: sin permiso → `reservado=true` sin intervención/recomendaciones; Salud/nivel 1 → contenido + fila en `historia_clinica_acceso` (el PDF con `origen='export'`). Sin migración. Verificado: smoke local, navegador (n2 fuera de Salud / supervisor de Salud) y prod (13/13 reservadas para un n2 fuera de Salud, sin filas en el log).
- **2026-10-10 — Canal lateral `turnos.observaciones` cerrado (mig 109, local + prod).** Toda prestación de atención de Salud registra historia (prod: Clínica general, 786 turnos cumplidos sin registro clínico); la marca se fuerza al crear/editar y cumplir rechaza `observaciones` en esas prestaciones. La UI avisa "lo ve el vecino". Smoke 9/9 + navegador.
- **2026-10-10 — Autoregistro del vecino: el link de verificación del mail daba 404 en prod** (se armaba con `FRONTEND_BASE_URL` = GitHub Pages). Setting nuevo `API_PUBLIC_BASE_URL` (default la URL de Railway, sin env var nueva). Los mails del vecino dicen que se ingresa con el **DNI**; la versión texto ya no lleva etiquetas HTML. Smoke in-process en MOCK 6/6 (alta → link → verificar → login con DNI). Regla nueva en CLAUDE.md §5 (links en mails).
- **2026-09-26/27 — App de agentes + «Mi perfil» + canales de instalación.** `zaris-agentes` (OT en la calle, push de usuarios internos mig 108) publicada en `agentes.zaris.com.ar`; «Mi perfil» (`#/perfil`) con foto, cambio voluntario de clave y tarjeta «App de agentes» (`APP_AGENTES_FRONTEND_URL`); portal del vecino con «La app en tu teléfono».

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
