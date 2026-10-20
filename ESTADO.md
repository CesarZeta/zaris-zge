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

**Última actualización:** 2026-10-20 (Cesar, 4ª sesión, larga). Pedidos de César del día, todo en prod salvo lo que se indica: campana con ✓ y «Marcar todas» (shell + app de agentes `/avisos`); perfil con secretaría y equipos (topbar, menú, Mi perfil, app); tipos de reclamo con subárea en los buscadores; OT con destinatario validado (equipo sin integrantes / Consultor → 422) y aviso a cada integrante de la cuadrilla; mesa del supervisor rediseñada; orden por columnas F1 (`ui/orden.tsx`); ficha → agente, supervisor en Maestros → Agentes (mig 113) y aviso «agente nuevo»; **autoasignación por gestión (mig 114)**, apagada hasta que César la prenda. Railway tuvo builds pausados ~4 h (incidente de plataforma): se verificó cada deploy con llamadas reales.

---

## 🔵 En curso

- **Prueba real del funcionario — a medias (2026-10-20).** La ficha (ciudadano 1868) existía desde el 2026-10-12 con el tilde y sin cuenta (anterior al guardado que la crea); César la editó y la cuenta nació bien: usuario 101 nivel 4, agente 97 1:1 con datos reales, subárea **Arbolado** (id 12), mail recibido, cambio forzado de clave y login hechos (verificado en DB). **Push ACTIVADO** (primera suscripción de la historia de prod: usuario 101, 2026-10-20 17:45 UTC, verificado en `usuario_push_subscription`). **Falta:** asignarle una OT: Arbolado no tiene OTs abiertas ni reclamos sin asignar → o un admin le reasigna una OT de otra subárea (OT → Mesa del supervisor → Reasignar; la reasignación no pide disponibilidad), o se carga un reclamo de Arbolado y se le crea la OT (para agendarla necesita disponibilidad en Agenda, un agente nuevo no tiene). Después: verificar en DB `usuario_push_subscription` activa + historial de la OT; que llegó el push lo confirma César en el teléfono.
- **Auditoría de reclamos — circuito completo en prod (F1-F4, 2026-10-20).** Queda solo la **prueba real del mail en prod**: no se observó ninguna auditoría real con «Sí» (el mail se verificó en MOCK, y el link del botón → `https://vecinos.zaris.com.ar/reclamos` da 200). Se puede hacer con el vecino de prueba de César (manda un correo real a su casilla) o esperar el primer uso real.
- **PWA `zaris-vecinos` — modo escritorio del portal: diseño aprobado el 2026-10-12 (3ª), falta plan + código.** Solo toca el repo de la PWA; spec y pasos en su `ESTADO.md` → En curso.
- **PROPUESTA sin aprobar — app de agentes: reclamos de oficio + «Control de entradas» (QR).** Pedido de César al cierre del 2026-10-12; las 4 decisiones de alcance ya están tomadas (de oficio · niveles 1-4 · acreditar niveles 1-4 · nombre «Control de entradas») y el diseño está escrito en [`PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md`](PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md). **Próxima sesión: César confirma o corrige el diseño y recién ahí F1 (backend sin migración + smoke).** No hay código.
- **App de agentes** publicada en `https://agentes.zaris.com.ar` (color del municipio, instalación desde «Mi perfil»); el vecino instala la suya desde su portal. Detalle en `zaris-agentes/ESTADO.md`.

> ### 📣 Para quien retome la PWA `zaris-vecinos` (Roy inactivo por ahora — César 2026-09-20)
> **Desde el 2026-09-26 la PWA ya consume TODO lo que el backend entregó el 2026-08-30** (perfil + edición de teléfono/domicilio, bandeja de avisos con badge, `geo/reverse`, foto de perfil en el backend). Lo que falta del lado suite para la PWA es solo backend NUEVO: `GET /publico/noticias` y URLs de redes en `identidad-municipio` (las secciones están ocultas mientras tanto), emergencias en `mi-resumen`, y la baja de cuenta. Contrato en [`docs/contrato_api_publica.md`](docs/contrato_api_publica.md). Cambio de contrato previo (2026-07-15, ya en la tabla): `POST /publico/alta/empresa` exige el vecino logueado (401 sin token) y ya NO toma `id_ciudadano` del body.

---

## 🟠 Pendientes (backoffice / backend)

**Próxima sesión — prueba de las apps (César)**
- 🟡 **Perfiles de prueba** (emails en la memoria privada de Cesar, NO acá — archivo público): **(b) vecino HECHO el 2026-10-12** (autoregistro → mail → verificación → portal → aviso de emergencia EM-2026-000223 en el COM; el botón de pánico «Seguridad» no se probó, dispara una alerta REAL). **(a) funcionario: EN CURSO** — alta, mail, login y cambio de clave hechos el 2026-10-20; falta el push (ver En curso). Guías: `manual_alta_ciudadanos.html` §4 y `manual_app_agentes.html`.
- 🟢 **Autoasignación HECHA (mig 114, 2026-10-20) — falta que César la prenda.** Se activa por gestión en Maestros → Subáreas («Asignación automática de reclamos»); a quién (agente/cuadrilla) y cuánto se agenda, en Maestros → Tipos de reclamo. Sin horarios cargados no asigna (deja aviso al supervisor). Reglas en la skill `modulo-ot`.
- 🟠 **DECIDIDO (cuestionario 2026-10-20) — circuito funcionario → agente HECHO (a-c), autoasignación (d) HECHA (ítem anterior).** (a) Datos personales del agente: **solo de la ficha** (sync al guardar; solo lectura en Maestros → Agentes salvo agentes viejos sin ficha) — HECHO. (b) Puesto = cargo (sin campo nuevo). (c) Cargo, horario y equipo los completa el **supervisor en Maestros → Agentes**, solo para su gestión (mig 113 `agentes_gestion`), con sección «Equipos» en el perfil; aviso «agente nuevo» a los supervisores — HECHO. Falta: vincular los 92 agentes viejos a su ficha. (d) **Autoasignación por gestión** (tilde en la subárea, mig 113): candidatos nivel 4 + cuadrillas con integrantes, disponibilidad → menor carga → rotación; si un día está completo pasa al siguiente (horizonte 30 días, criterio de Claude); sin hueco → Sin asignar + aviso al supervisor; agente o cuadrilla según `tipo_reclamo.asignacion_a`. (e) **Super administrador multi-municipio** que crea los admins de cada municipio → va con IT-01. Hecho el mismo día: destinatario de OT validado, aviso a la cuadrilla, campana en la app de agentes, mesa del supervisor rediseñada y orden por columnas (F1). Hallazgos que siguen valiendo: el agente no se resincroniza con la ficha (92/93 sin DNI, nacieron por Maestros → Usuarios o seed); Maestros → Agentes es solo admin y oculta DNI/CUIL/email/teléfono a otros niveles; solo 14/93 agentes y 1/7 cuadrillas tienen horario; `ordenes_trabajo.id_supervisor_asigna` es NOT NULL; `tipo_reclamo.asignacion_a`/`duracion_estimada_min` existen sin uso.
- 🟠 **Subárea del funcionario (pregunta de César 2026-10-13, la cubre el ítem anterior).** Hoy el admin la elige bajo el tilde y se copia a `usuarios.id_subarea` y `agentes.id_subarea`; el scoping lee la del agente y las dos pueden divergir. **Drift:** local tiene FK `usuarios.id_subarea`/`agentes.id_subarea` → `subarea` y **prod NO** (un id inexistente por API queda guardado) — candidata a mig 113+ cuando se defina.
- 🟢 **Decisión pendiente (no bloquea):** si la app del vecino también acepta email además del DNI (hoy el contrato público es DNI + clave; es un cambio chico de backend + etiqueta de la PWA).
- 🟠 **Vecino trabado por el link roto:** 1 ciudadano `auto_registrado` con clave elegida y credencial sin activar desde el 2026-06-12 (prod). Decisión de César: reenviarle la activación (implica escribirle a una persona real) o dejarlo.

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
- Purga del historial git HECHA el 2026-09-20 (mapa en `docs/commit-map-purga-2026-09-20.txt`).
- Fase 3 de roles (mig 92) y la auditoría de seguridad 2026-07 (48/48) COMPLETAS.

---

## ✅ Hecho reciente (últimas sesiones)

- **2026-10-20 (4ª, noche) — Perfil de agente: ficha → agente, supervisor en Maestros → Agentes (mig 113), aviso «agente nuevo».** Smoke local 16/16 + navegador local (supervisor y admin). Gestión única: cambiar la subárea en Usuarios mueve al agente.
- **2026-10-20 (4ª, tarde) — OT con destinatario validado + mesa del supervisor + orden por columnas + campana en la app de agentes.** `_validar_destinatario_ot` (equipo sin integrantes / Consultor / sin usuario → 422), `notificar_ot_asignada` escribe la campana y avisa a cada integrante de la cuadrilla; mesa a todo el ancho con panel lateral y barra «Asignar (N)»; `ui/orden.tsx` + `GET /reclamos?orden=&dir=`; app de agentes con `/avisos`. Smoke local 9/9 + navegador local. En prod (Railway reanudó los builds el mismo día; verificado con llamadas reales).
- **2026-10-20 (3ª) — Reclamos «Ver pendientes» + búsqueda de Ciudadanos por lo escrito (`ef318c8`, `ac3b321`, en prod).** `GET /reclamos?pendientes=true` (incluye En auditoría, decisión de César); la búsqueda de Ciudadanos decide nombre vs DNI/CUIL por lo escrito.
- **2026-10-20 (2ª) — Auditoría F4: resultado + retrabajo visible + mail (`e548c1e`, PWA `9a98775`, en prod).** Detalle en `PLAN_AUDITORIA_RECLAMOS.md` (F4).
- **2026-10-20 — Auditoría de reclamos POSTERIOR al cierre (mig 112, `16ad409` + `a17bb6d`, en prod).** Estados `En auditoría`/`Auditado`, `POST /reclamos/{id}/auditoria`, aprobar/observar, inicio/BI con la semántica nueva, generador demo + backfill en prod (181 auditorías, 32 retrabajos).

- **2026-10-19 — Municipio demo San Andrés en el mapa del inicio (mig 111).** Contorno + máscara exterior, encuadre por zonas libres, generador demo con San Isidro. Detalle en `HISTORIAL_MIGRACIONES.md`.
- **2026-10-13 — Cuentas al guardar la ficha, sin botón ni modal.** Reglas en la skill `modulo-usuarios`.

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
