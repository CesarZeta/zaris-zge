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

**Última actualización:** 2026-10-10 (Cesar). Sesión de **seguridad de datos de salud + revisión del alta de cuentas**: (1) contenido clínico de `GET /turnos/atenciones` detrás del guard de historia clínica (`15eb99e`); (2) canal lateral `turnos.observaciones` cerrado — mig 109 en local y prod (`b338a16`); (3) **bug de prod**: el link de verificación del autoregistro del vecino daba 404 desde junio — arreglado con `API_PUBLIC_BASE_URL` (`a51fbe7` + marcador `2b734d7`). Las tres verificadas en prod (marcador OpenAPI + bundle + SQL). César confirmó el recorrido de las 13 pantallas; cron demo y primer aviso de Trámites verificados.

---

## 🔵 En curso

- **Nada en desarrollo activo.** Próxima sesión (pedido de César 2026-10-10): **prueba en el celular de las dos apps** (vecinos y agentes) con perfiles de prueba — ver Pendientes.
- Proyecto **Atención por ubicación** CERRADO el 2026-09-20; residuos en [`PLAN_MODULO_ATENCION.md`](PLAN_MODULO_ATENCION.md) §4 (los dos de privacidad quedaron resueltos el 2026-10-10).
- **App de agentes** publicada en `https://agentes.zaris.com.ar` (color del municipio, instalación desde «Mi perfil»); el vecino instala la suya desde su portal. Detalle en `zaris-agentes/ESTADO.md`.

> ### 📣 Para quien retome la PWA `zaris-vecinos` (Roy inactivo por ahora — César 2026-09-20)
> **Desde el 2026-09-26 la PWA ya consume TODO lo que el backend entregó el 2026-08-30** (perfil + edición de teléfono/domicilio, bandeja de avisos con badge, `geo/reverse`, foto de perfil en el backend). Lo que falta del lado suite para la PWA es solo backend NUEVO: `GET /publico/noticias` y URLs de redes en `identidad-municipio` (las secciones están ocultas mientras tanto), emergencias en `mi-resumen`, y la baja de cuenta. Contrato en [`docs/contrato_api_publica.md`](docs/contrato_api_publica.md). Cambio de contrato previo (2026-07-15, ya en la tabla): `POST /publico/alta/empresa` exige el vecino logueado (401 sin token) y ya NO toma `id_ciudadano` del body.

---

## 🟠 Pendientes (backoffice / backend)

**Próxima sesión — prueba de las apps (César)**
- 🟡 **Perfiles de prueba:** César tiene que pasar DOS emails distintos y no usados (`cesarzarini@hotmail.com` ya es un usuario de prod; sirve un alias `+vecino`): (a) **funcionario** dado de alta en Usuarios → recibe usuario (email) + clave temporal → cambio forzado en la app de agentes; (b) **vecino** autoregistrado desde la página pública (`url_alta_publica` de `/publico/identidad-municipio`) → primer uso real del link de verificación arreglado. Después: instalar ambas apps, push real, botón de pánico **con el backoffice a la vista** (dispara una alerta REAL al COM).
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
