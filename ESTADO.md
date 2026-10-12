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

**Última actualización:** 2026-10-12 (Cesar, 3ª sesión — solo PWA). **Modo escritorio del Portal del Ciudadano: diseño aprobado, sin código.** César vio en su PC que el portal se ve como un teléfono centrado (columna de 480 px en todas las páginas) y pidió un formato web bien diferenciado. Cinco decisiones cerradas (todo el portal · ancho ≥ 900 px · encabezado web horizontal · CSS responsivo sobre los mismos componentes · tarjetas en la home + pestañas en las secciones) y especificación en `zaris-vecinos/docs/superpowers/specs/2026-10-12-modo-escritorio-design.md`; **próximo paso: plan de implementación**. Nada del backoffice ni del backend cambió; detalle en `zaris-vecinos/ESTADO.md`. Sesión anterior (2026-10-12, 2ª): **Prueba real del VECINO HECHA por César en prod**: alta desde la página pública → mail «Verificá tu alta» recibido en Gmail (entrega de Resend en prod confirmada) → verificación → login en el portal → aviso de emergencia **EM-2026-000223** recibido en el COM (canal app). Queda la prueba del funcionario. **Ajustes pedidos tras la prueba, EN PROD** (`e83711f`, PWA `53183a6`, agentes `613b55a`): CUIL calculado con DNI + sexo en la página de alta (el sexo va justo después del DNI; prefijo 20/27, 23 si el verificador da 10; «Otro» no calcula; lo tipeado no se pisa), ver/ocultar contraseña en la página de alta y en todo campo de clave de las dos apps (componente `Input`), títulos de la PWA («Acceso al Portal del Ciudadano» en la bienvenida, «Iniciar sesión» en el login — César corrigió la primera lectura) y sin «Volver» en el login. **Autogestión del alta del vecino — huecos cerrados, EN PROD** (`1556406` + PWA `fd5268c`): al repasar el circuito con César se vio que ni la pantalla «alta registrada», ni el mail de verificación, ni la página «Correo verificado» le decían al vecino a dónde seguir. Ahora: botón **«Ir al Portal del Ciudadano»** en las dos pantallas finales de `alta-vecino.html` (`GET /publico/alta/identidad` expone `app_vecinos_url`), en la página de verificación (ciudadano y empresa) y como línea extra del mail (HTML y texto); la página de **enlace vencido** manda a la página de alta («Activar mi cuenta» con el DNI); el **login de la PWA** suma «¿No tenés cuenta? Creala acá». `backend/app/core/urls.py` = fuente única de URLs públicas (fail-closed: con basura en la env var no se pinta nada). Smoke in-process `smoke_alta_portal_links.py` 24/24 (SIGUE el link del mail), navegador local (las 4 pantallas) y prod (OpenAPI de Railway + Pages + bundle de Vercel). **César ya pasó los dos emails de la prueba** (viven en la memoria privada de Cesar, no en este archivo público; verificados libres en prod). Sesión anterior (2026-10-12, 1ª): **Circuito de alta de cuentas ZARIS desde la ficha del ciudadano — EN PROD** ([`PLAN_CUENTAS_FUNCIONARIO.md`](PLAN_CUENTAS_FUNCIONARIO.md), mig 110 local + prod): tilde «Este ciudadano es funcionario del municipio» en la ficha; el botón del pie pasa a **«Crear cuenta aplicación ZARIS»** (sin tilde = cuenta de App Vecinos como antes; con tilde = cuenta ZARIS, solo Administrador, mini-modal nivel/subárea/usuario) → usuario vinculado (`usuarios.id_ciudadano`) + agente 1:1 con datos reales + mail con clave temporal y link a la app de agentes; chips «Cuentas» en la ficha; **login de ZARIS y de la app de agentes por email O DNI** (`identificador`); bloque «La app en tu teléfono» en «Mi cuenta» de la app de agentes. Manuales: `docs/manual_alta_ciudadanos.html` §4 (regenerado, 8 capturas) + **`docs/manual_app_agentes.html`** (nuevo, en Guías). Verificado: smoke 36/36, navegador local (admin / nivel 2 / login por DNI en los 3 logins), prod (OpenAPI + bundle + Vercel + `curl` de los dos links del mail).

---

## 🔵 En curso

- **PWA `zaris-vecinos` — modo escritorio del portal: diseño aprobado el 2026-10-12 (3ª), falta plan + código.** Solo toca el repo de la PWA; spec y pasos en su `ESTADO.md` → En curso.
- **Todo listo para la prueba real en el celular** (pedido de César 2026-10-10, circuito implementado 2026-10-12): ver Pendientes → «Próxima sesión». Nada en desarrollo activo.
- **PROPUESTA sin aprobar — app de agentes: reclamos de oficio + «Control de entradas» (QR).** Pedido de César al cierre del 2026-10-12; las 4 decisiones de alcance ya están tomadas (de oficio · niveles 1-4 · acreditar niveles 1-4 · nombre «Control de entradas») y el diseño está escrito en [`PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md`](PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md). **Próxima sesión: César confirma o corrige el diseño y recién ahí F1 (backend sin migración + smoke).** No hay código.
- Proyecto **Atención por ubicación** CERRADO el 2026-09-20; residuos en [`PLAN_MODULO_ATENCION.md`](PLAN_MODULO_ATENCION.md) §4 (los dos de privacidad quedaron resueltos el 2026-10-10).
- **App de agentes** publicada en `https://agentes.zaris.com.ar` (color del municipio, instalación desde «Mi perfil»); el vecino instala la suya desde su portal. Detalle en `zaris-agentes/ESTADO.md`.

> ### 📣 Para quien retome la PWA `zaris-vecinos` (Roy inactivo por ahora — César 2026-09-20)
> **Desde el 2026-09-26 la PWA ya consume TODO lo que el backend entregó el 2026-08-30** (perfil + edición de teléfono/domicilio, bandeja de avisos con badge, `geo/reverse`, foto de perfil en el backend). Lo que falta del lado suite para la PWA es solo backend NUEVO: `GET /publico/noticias` y URLs de redes en `identidad-municipio` (las secciones están ocultas mientras tanto), emergencias en `mi-resumen`, y la baja de cuenta. Contrato en [`docs/contrato_api_publica.md`](docs/contrato_api_publica.md). Cambio de contrato previo (2026-07-15, ya en la tabla): `POST /publico/alta/empresa` exige el vecino logueado (401 sin token) y ya NO toma `id_ciudadano` del body.

---

## 🟠 Pendientes (backoffice / backend)

**Próxima sesión — prueba de las apps (César)**
- 🟡 **Perfiles de prueba** (emails en la memoria privada de Cesar, NO acá — archivo público): **(b) vecino HECHO el 2026-10-12** (autoregistro → mail → verificación → portal → aviso de emergencia EM-2026-000223 en el COM; el botón de pánico «Seguridad» no se probó, dispara una alerta REAL). Queda **(a) funcionario**: alta en Ciudadanos con el tilde «funcionario del municipio» → «Crear cuenta aplicación ZARIS» (admin) → mail con usuario (email o DNI) + clave temporal + link de la app de agentes → instalar la app → login con DNI → cambio forzado → push real al asignarle una OT. Guías: `manual_alta_ciudadanos.html` §4 y `manual_app_agentes.html`.
- 🟢 **Decisión pendiente (no bloquea):** si la app del vecino también acepta email además del DNI (hoy el contrato público es DNI + clave; es un cambio chico de backend + etiqueta de la PWA).
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

- **2026-10-12 (2ª) — Prueba real del vecino OK en prod + ajustes pedidos (`e83711f`, PWA `53183a6`, agentes `613b55a`).** Resend entrega en prod (mail en Gmail); emergencia desde la app EM-2026-000223. CUIL calculado con DNI + sexo, ver/ocultar contraseña (alta + `Input` de las dos apps), PWA: bienvenida «Acceso al Portal del Ciudadano», login «Iniciar sesión» y sin «Volver». Verificado en navegador contra referencia en Python (casos 20/27/23) y en prod.
- **2026-10-12 (2ª) — Autogestión del alta del vecino: el circuito le dice a dónde seguir (`1556406`, PWA `fd5268c`, sin migración).** Botón «Ir al Portal del Ciudadano» en las pantallas finales de la página de alta, en la página de verificación y en el mail; «Volver a la página de alta» cuando el enlace venció; link de registro también en el login de la PWA. `core/urls.py` (fuente única, fail-closed). Smoke `smoke_alta_portal_links.py` 24/24 + navegador + prod.
- **2026-10-12 — Circuito de alta de cuentas ZARIS (mig 110, en prod).** `services/cuenta_zaris.py` compartido por `POST /buc/usuarios` y `POST /buc/ciudadanos/{id}/cuenta-zaris` (solo admin; agente 1:1 con datos reales); `GET /buc/ciudadanos/{id}/cuentas`; login por `identificador` (email o DNI, `email` sigue como alias); mail con clave temporal + link de la app de agentes. Front: tilde «funcionario», botón único, `CuentaZarisModal`, `CuentasChips`. Smoke 36/36. Detalle en `PLAN_CUENTAS_FUNCIONARIO.md` y la skill `modulo-usuarios`.
- **2026-10-10 — Datos de salud blindados + bug del autoregistro.** Contenido clínico de `GET /turnos/atenciones` detrás del guard de historia clínica (sin permiso → `reservado=true`; Salud/nivel 1 → contenido + fila en `historia_clinica_acceso`); mig 109: toda prestación de Salud registra historia y `turnos.observaciones` deja de ser canal lateral; el link de verificación del autoregistro daba 404 en prod (`FRONTEND_BASE_URL`) → setting `API_PUBLIC_BASE_URL` + regla CLAUDE.md §5.

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
