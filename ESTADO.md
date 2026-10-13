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

**Última actualización:** 2026-10-13 (Cesar). **Cuentas del ciudadano SIN botón: se crean al guardar la ficha.** Pedido de César al arrancar: el botón «Crear cuenta aplicación ZARIS» sobraba. Ahora, con el tilde «funcionario del municipio» puesto, nivel/subárea/usuario aparecen **debajo del tilde** (`CuentaZarisCampos`, usuario propuesto `nombre.apellido`) y viajan en `cuenta_zaris` del `POST`/`PUT /buc/ciudadanos`: la cuenta ZARIS (usuario + agente 1:1 con datos reales + mail con clave temporal) nace en la **misma transacción del guardado**. Consecuencia: **el tilde es solo de Administrador** (UI deshabilitada para nivel 2-5; backend 403 si lo pasan a true, 422 si un admin guarda el tilde sin los tres datos; si ya tiene cuenta, se ignora). Para el vecino: **guardar la ficha** (`PUT`) crea la credencial de App Vecinos + mail si la persona no tiene ninguna (fichas anteriores a junio; nunca reenvía si existe), y los chips ofrecen **«Reenviar correo de activación»** cuando quedó pendiente (reusa `POST /cuenta-vecino`). El endpoint `POST /cuenta-zaris` queda para la API. Sin migración. Smoke `smoke_cuentas_funcionario.py` 54/54, navegador local (alta como admin → cuenta creada; edición con chips + Reenviar; nivel 2 con el tilde bloqueado), manual `manual_alta_ciudadanos.html` §4 regenerado (2 capturas nuevas, 2 quitadas), skills y plan al día. **Ojo en prod: hay 854 ciudadanos activos sin credencial y con email; editar cualquiera de esas fichas le manda el mail de activación real** (es la regla pedida: «una vez dado de alta, ya tiene la cuenta»). Sesión anterior (2026-10-12, 3ª — solo PWA): **modo escritorio del Portal del Ciudadano, diseño aprobado, sin código** (spec en `zaris-vecinos/docs/superpowers/specs/2026-10-12-modo-escritorio-design.md`; próximo paso: plan de implementación; detalle en `zaris-vecinos/ESTADO.md`). Antes ese día: prueba real del VECINO hecha en prod (Resend entrega, EM-2026-000223), ajustes tras la prueba (`e83711f`), autogestión del alta con links al portal (`1556406`) y circuito de alta de cuentas ZARIS con mig 110 — todo en «Hecho reciente» y en [`PLAN_CUENTAS_FUNCIONARIO.md`](PLAN_CUENTAS_FUNCIONARIO.md).

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
- 🟡 **Perfiles de prueba** (emails en la memoria privada de Cesar, NO acá — archivo público): **(b) vecino HECHO el 2026-10-12** (autoregistro → mail → verificación → portal → aviso de emergencia EM-2026-000223 en el COM; el botón de pánico «Seguridad» no se probó, dispara una alerta REAL). Queda **(a) funcionario**: alta en Ciudadanos como Administrador con el tilde «funcionario del municipio» + nivel/subárea/usuario → **Guardar** (la cuenta nace ahí, sin botón) → mail con usuario (email o DNI) + clave temporal + link de la app de agentes → instalar la app → login con DNI → cambio forzado → push real al asignarle una OT. Guías: `manual_alta_ciudadanos.html` §4 y `manual_app_agentes.html`.
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

- **2026-10-13 — Cuentas al guardar la ficha, sin botón ni modal (sin migración).** `cuenta_zaris` en `CiudadanoCreate/Update` + `services/cuenta_zaris.py::crear_cuenta_zaris_desde_ficha` (lo usan POST/PUT de la ficha y el endpoint); tilde solo-admin; PUT asegura la cuenta de vecino si no hay ninguna; chips con «Reenviar correo de activación»; `CuentaZarisModal` borrado → `CuentaZarisCampos`. Smoke 54/54, navegador, manual §4, skills `modulo-usuarios`/`modulo-app-vecinos`, plan.
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
