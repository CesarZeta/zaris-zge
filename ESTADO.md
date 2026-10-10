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

**Última actualización:** 2026-09-27 (Cesar, cierre de la 3ª sesión del 26/27-09). Sesión: **canales de instalación de las dos apps** cerrados en código y en prod (decisión de César: el funcionario instala la app de agentes desde «Mi perfil»; el vecino, la suya desde su portal) y **app de agentes PUBLICADA** en `https://agentes.zaris.com.ar` con el color del municipio (proyecto Vercel desde el navegador integrado, CNAME en Cloudflare por César, certificado emitido, 200 verificado). `app_agentes_url` en `/config/identidad`. **Cierre definitivo 18:13:** `APP_AGENTES_FRONTEND_URL=https://agentes.zaris.com.ar` en Railway, verificada en `/config/identidad` (antes hubo un valor mal pegado; el backend quedó fail-closed en `9a415a1`). Sin pendientes de infra. Detalle en «En curso» y «Hecho reciente».

---

## 🔵 En curso

- **Canales de instalación de las dos apps — HECHO en código y verificado en local (2026-09-27, decisión de César):** *el funcionario instala la app de agentes desde «Mi perfil» en ZARIS; el vecino instala la del vecino desde su perfil en el portal del vecino (no entra a ZARIS).* (1) «Mi perfil» **reemplazó** la tarjeta «Portal del Ciudadano» por la tarjeta «App de agentes» (QR + link + pasos; URL = `GET /config/identidad.app_agentes_url` ← env `APP_AGENTES_FRONTEND_URL`, default `http://localhost:5175`; `.env.example` actualizado). Railway tiene `APP_AGENTES_FRONTEND_URL` (verificado en `/config/identidad`), así que la tarjeta en prod ya muestra el QR. ✅ **`APP_AGENTES_FRONTEND_URL=https://agentes.zaris.com.ar` en Railway (César, 2026-09-27 18:13, verificado en `/config/identidad`).** Antes hubo un valor mal pegado (la línea entera `NOMBRE=valor`); el backend quedó fail-closed (`9a415a1`, `_url_publica`). La tarjeta de «Mi perfil» en prod apunta al dominio propio. (2) El portal del vecino (`zaris-vecinos`, pantalla Configuración = su perfil) sumó el bloque «La app en tu teléfono» (instalación nativa si Chrome la ofrece + link + QR del portal + pasos; componente `BloqueInstalar` compartido con la bienvenida). La página pública de alta `frontend/alta-vecino.html` NO se tocó. Verificación humana pendiente: César en prod (Mi perfil → escanear el QR con el celular → abre la app de agentes; portal del vecino → Cuenta → bloque con QR).
- **Nada en desarrollo activo.** El proyecto **Atención por ubicación** (6 fases: ubicación obligatoria, Mesa del día, colero, Guardia, historia clínica, BI de atención) quedó **CERRADO el 2026-09-20** con el QA de César en prod. Roadmap, decisiones por fase y residuos en [`PLAN_MODULO_ATENCION.md`](PLAN_MODULO_ATENCION.md) (§4 Pendientes).
- **App de agentes — PUBLICADA (2026-09-27): `https://zaris-agentes.vercel.app`**, primer frente (OT en la calle) completo; **toma el color del municipio** (decisión de César 2026-09-27, `zaris-agentes` `d46f767`); César la probó en el celular: OK. Lado suite HECHO (mig 108 en prod, backend pusheado, CORS verificado). Proyecto Vercel creado desde el navegador integrado (el MCP de Vercel da 403 al crear proyectos y agregar dominios). **Dominio `https://agentes.zaris.com.ar` ACTIVO** (CNAME creado por César el 2026-09-27, certificado emitido por Vercel, 200 verificado). Detalle en `zaris-agentes/ESTADO.md`. Plan original: (`zaris-agentes`, repo nuevo clonando la estructura de la PWA de vecinos, ya cerrada el 2026-09-26; login con credenciales de ZARIS, home por rol; **primer frente: OT en la calle** — mesa del agente, tomar, cambiar estado, foto de evidencia, mapa del reclamo). Backend pendiente: origen nuevo en CORS + push para agentes (tabla nueva, mig 108, VAPID reusado).

> ### 📣 Para quien retome la PWA `zaris-vecinos` (Roy inactivo por ahora — César 2026-09-20)
> **Desde el 2026-09-26 la PWA ya consume TODO lo que el backend entregó el 2026-08-30** (perfil + edición de teléfono/domicilio, bandeja de avisos con badge, `geo/reverse`, foto de perfil en el backend). Lo que falta del lado suite para la PWA es solo backend NUEVO: `GET /publico/noticias` y URLs de redes en `identidad-municipio` (las secciones están ocultas mientras tanto), emergencias en `mi-resumen`, y la baja de cuenta. Contrato en [`docs/contrato_api_publica.md`](docs/contrato_api_publica.md). Cambio de contrato previo (2026-07-15, ya en la tabla): `POST /publico/alta/empresa` exige el vecino logueado (401 sin token) y ya NO toma `id_ciudadano` del body.

---

## 🟠 Pendientes (backoffice / backend)

**Verificaciones humanas (César)**
- 🟡 **PRÓXIMA SESIÓN — prueba en el celular de las DOS apps** (vecinos y agentes), pedido de César 2026-10-10. Antes: revisar el proceso de alta de cuentas (vecino y funcionario: mail con usuario + clave temporal, cambio obligatorio de clave) y preparar perfiles de prueba.
- ✅ Recorrido en prod de las 13 pantallas con búsqueda diferida: **hecho por César** (confirmado 2026-10-10).
- ✅ Cron "Datos demo BI" con el flujo 202 + polling: runs `schedule` del 2026-09-28 y 2026-10-05 en `success`, el del 05/10 con `"estado":"ok"` en el log.
- ✅ Trámites — primer aviso real del ciclo de vida: `HAB-LPL-2026-0001` y `CAR-LPL-2026-0002` recibieron UN aviso nivel 1 el 2026-10-07 10:59 UTC (verificado en `tramite_movimiento`). La entrega del mail (Resend) no se verificó.

**Decisiones de negocio pendientes (César)**
- 🟠 **Atención — residuos del plan (§4):** "ocupación vs disponibilidad efectiva" en el BI de atención (hoy ocupación = turnos + horas atendidas, sin % sobre la agenda) · etapa 2 de HC (vista admin de `historia_clinica_acceso`, break-the-glass, ficha ampliada) · walk-in de Guardia sin evento de Emergencias.
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

- **2026-10-10 — Contenido clínico de `GET /turnos/atenciones` detrás del guard de historia clínica** (residuo §4 del plan Atención, decisión de César: gatear). No era solo el PDF: el endpoint alimentaba la pantalla de Consultas, el detalle del turno y el PDF, y en prod dejaba leer las 1.301 atenciones de Odontología a cualquier nivel ≤ 2 de cualquier área, sin registro. Ahora: fuera de Salud/nivel 1 → `reservado=true` sin intervención/recomendaciones; Salud/nivel 1 → contenido + fila en `historia_clinica_acceso` (el PDF con `origen='export'`). Sin migración. Smoke in-process local + recorrido en el navegador (administrativo@ n2 ve "reservado" y exporta sin contenido; f5supsalud@ ve y exporta, 2 filas en el log).
- **2026-10-10 — Autoregistro del vecino: el link de verificación del mail daba 404 en prod** (se armaba con `FRONTEND_BASE_URL` = GitHub Pages). Ahora usa el setting nuevo `API_PUBLIC_BASE_URL` (default la URL de Railway, sin env var nueva). Los mails de activación y verificación dicen que se ingresa con el **DNI**; la versión texto de los mails ya no lleva etiquetas HTML. Smoke local in-process en MOCK 6/6 (alta → link → verificar → login con DNI).
- **2026-10-10 — Canal lateral `turnos.observaciones` cerrado (mig 109, local + prod).** Toda prestación de atención de Salud registra historia (prod: Clínica general, que tenía 786 turnos cumplidos sin registro clínico); la marca se fuerza al crear/editar prestaciones de Salud y cumplir rechaza `observaciones` en esas prestaciones (lo clínico va a intervención/recomendaciones). La UI avisa "lo ve el vecino" en los campos de observación. Smoke local 9/9 + navegador (el cumplir de Clínica general abre "Registrar atención").

- **2026-09-27 — Canales de instalación de las apps + app de agentes en Vercel con el color del municipio.** Backend: `app_agentes_url` en `/config/identidad` (`APP_AGENTES_FRONTEND_URL`). «Mi perfil»: tarjeta «App de agentes» en lugar de la del vecino. Portal del vecino: bloque «La app en tu teléfono» en Configuración (repo `zaris-vecinos`). App de agentes publicada en `zaris-agentes.vercel.app` (proyecto creado desde el navegador integrado; el MCP de Vercel da 403 para mutar), dominio `agentes.zaris.com.ar` agregado a la espera del CNAME en Cloudflare (Turnstile no corre en el navegador integrado: el login de Cloudflare hay que hacerlo desde un navegador normal). DNS de `zaris.com.ar` = Cloudflare (verificado por NS). Verificado en prod al cierre: «Mi perfil» con la tarjeta y el QR (iframe con bundle `index-D1yYhakr.js`, sesión de un agente n4), `agentes.zaris.com.ar` 200 con el mismo bundle que Vercel, portal del vecino con el bloque nuevo.
- **2026-09-26 — App de agentes (`zaris-agentes`, `dd559f5`) + backend de push para usuarios internos (mig 108).** PWA nueva con login de ZARIS, mesa del agente, detalle de OT (mapa, cómo llegar, vecino, evidencia con cámara, cambio de estado), Cuenta (foto, push, clave). Backend: tabla `usuario_push_subscription`, router `/auth/push/*`, hook `notificar_ot_asignada` en alta/reasignación de OT, CORS de la app. Verificado en local contra la DB (estado de OT y evidencia).
- **2026-09-26 — «Mi perfil» del usuario — EN MAIN (`4be8773`)**: módulo React `web-app/src/modules/perfil/` (`#/perfil`, sin permiso, oculto del sidebar) con cabecera (foto/nombre/rol/cargo/gestión + cambiar/quitar foto), tarjeta «Portal del Ciudadano» (QR 220 px + link + copiar + pasos Android/iPhone; URL desde `GET /config/identidad.app_vecinos_url` = env `APP_VECINOS_FRONTEND_URL`, sin migración), cambio voluntario de clave (fetch directo: el 401 «actual incorrecta» NO desloguea) y «Módulos a los que accedés». Ítem «Mi perfil» + bloque de nombre clickeable en el menú del avatar (`menu.js` escucha `storage` → topbar con la foto nueva sin recargar). Verificado en local con navegador (shell 8080 + dev 5173, usuario n3): clave 401/OK con DB, foto Storage+DB+topbar, dark OK.

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
