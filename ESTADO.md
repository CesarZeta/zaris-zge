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

**Última actualización:** 2026-10-20 (Cesar, 3ª sesión). **Reclamos: botón «Ver pendientes»** (`ef318c8` backend + `ac3b321` pantalla, en prod): `GET /reclamos?pendientes=true` trae Sin asignar, En gestión, En espera y **En auditoría** (decisión de César: incluye la auditoría aunque el inicio y el BI no la cuenten como pendiente), del más antiguo al más nuevo, combinado con área/subárea/texto y con el scope por subárea; el listado lo pide con limit 500 y avisa si llega al tope. Opción «Pendientes (sin resolver)» en el filtro Estado; manual de Reclamos y skill al día. **Ciudadanos: la búsqueda decide el modo por lo escrito** (letras → nombre, solo números → DNI/CUIL): antes un apellido buscado con «# DNI / CUIL» marcado (el modo de entrada) daba «no se encontró», y así César no encontró la ficha del funcionario de prueba. Verificado: smoke in-process local (8/8), navegador local (las dos direcciones del arreglo, edición de la ficha) y prod en el iframe (18 pendientes de Alumbrado = DB; el apellido encuentra la ficha). **Prueba real del funcionario avanzada** (ver En curso). (Auditoría F4 y lo anterior en «Hecho reciente», `HISTORIAL_MIGRACIONES.md` y git.)

---

## 🔵 En curso

- **Prueba real del funcionario — a medias (2026-10-20).** La ficha (ciudadano 1868) existía desde el 2026-10-12 con el tilde y sin cuenta (anterior al guardado que la crea); César la editó y la cuenta nació bien: usuario 101 nivel 4, agente 97 1:1 con datos reales, subárea **Arbolado** (id 12), mail recibido, cambio forzado de clave y login hechos (verificado en DB). **Falta:** (1) en la app de agentes, Cuenta → Notificaciones → activar (hoy 0 suscripciones: **ningún agente activó nunca el push en prod**, esta es la primera prueba real); (2) asignarle una OT: Arbolado no tiene OTs abiertas ni reclamos sin asignar → o un admin le reasigna una OT de otra subárea (OT → Mesa del supervisor → Reasignar; la reasignación no pide disponibilidad), o se carga un reclamo de Arbolado y se le crea la OT (para agendarla necesita disponibilidad en Agenda, un agente nuevo no tiene). Después: verificar en DB `usuario_push_subscription` activa + historial de la OT; que llegó el push lo confirma César en el teléfono.
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
- 🟠 **Definir cómo se resuelve la SUBÁREA del funcionario (pregunta de César al cierre del 2026-10-13).** Cómo es HOY (verificado en código y DB): **no se deriva de nada**; el administrador la elige a mano en el buscador «Subárea» que aparece bajo el tilde (solo subáreas activas, busca por nombre de subárea o de área; obligatoria), y al guardar se copia a `usuarios.id_subarea` y a `agentes.id_subarea` del agente 1:1. El scoping de reclamos/OT/turnos lee la del **agente** (§3); después se edita desde Usuarios (usuario) y Maestros → Agentes (agente), y las dos pueden divergir. No sale de la ficha del ciudadano (`ciudadanos.id_subarea` es columna estándar sin uso), ni del cargo, ni de la subárea del admin que la carga. Para decidir: ¿se mantiene manual, se vuelve un dato de la ficha («dónde trabaja»), o se liga al cargo? y ¿una sola fuente entre usuario y agente? **Drift cazado:** el backend solo exige que venga (`UsuarioCreate`), no que exista; **local tiene FK `usuarios.id_subarea`/`agentes.id_subarea` → `subarea` y prod NO** (un id inexistente por API queda guardado). Candidata a una mig futura (FK en prod; la 111 ya la tomó el contorno del municipio) cuando se defina.
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
- 🟡 **Barrido visual de modo oscuro** en los módulos React restantes: **POSPUESTO por César 2026-09-20**. Sumar el mapa del inicio: tras los cambios del 2026-10-19 no se revisó en oscuro, y el contorno pizarra de los reclamos casi no se ve sobre el tile oscuro.

**Decisiones cerradas — NO re-proponer**
- **São Paulo DESCARTADO (César, 2026-09-26, con medición):** Railway ya está co-locado con Supabase `us-east-1` y no ofrece región en Sudamérica. Detalle en CLAUDE.md §9 «Región».
- **"La ubicación" de Buscar actualizaciones (PWA) CERRADA como innecesaria** (2026-09-26): el service worker con `autoUpdate` alcanza.
- `DISPATCHER_TOKEN` no se rota (César 2026-09-06). El vecino NO cambia su email desde la app (2026-08-30).
- Purga del historial git HECHA el 2026-09-20 (mapa en `docs/commit-map-purga-2026-09-20.txt`).
- Fase 3 de roles (mig 92) y la auditoría de seguridad 2026-07 (48/48) COMPLETAS.

---

## ✅ Hecho reciente (últimas sesiones)

- **2026-10-20 (3ª) — Reclamos «Ver pendientes» + búsqueda de Ciudadanos por lo escrito (`ef318c8`, `ac3b321`, en prod).** Ver «Última actualización».
- **2026-10-20 (2ª) — Auditoría F4: circuito del resultado + retrabajo visible + mail (`e548c1e`, PWA `9a98775`, en prod).** Aprobada = cierre definitivo; observada → pop-up «¿Iniciar un nuevo incidente?» (`generar_retrabajo`, default `true`): Sí = retrabajo + mail genérico + aviso + push; No = sin reclamo nuevo ni aviso. El vecino ve el retrabajo con la observación enmascarada; encuesta sin anti-fatiga; mesa del auditor sin SLA; fuga «Auditoría cancelada» del historial público corregida. Detalle en `PLAN_AUDITORIA_RECLAMOS.md` (F4).
- **2026-10-20 — Auditoría de reclamos POSTERIOR al cierre (mig 112, `16ad409` + `a17bb6d`, en prod).** Estados `En auditoría`/`Auditado`, `POST /reclamos/{id}/auditoria`, aprobar/observar, inicio/BI con la semántica nueva, generador demo + backfill en prod (181 auditorías, 32 retrabajos).

- **2026-10-19 — Municipio demo San Andrés en el mapa del inicio (mig 111, `d82ff34` + `8ce6090`).** `services/geo_limite.py` (contorno fail-closed) → `GET /dashboard/resumen` `geo.limite`; máscara exterior naranja; encuadre por zonas libres + modo compacto < 900 px; puntos contorno/centro; generador demo con San Isidro; `reubicar_datos_demo.py` aplicado en local y prod. Verificado en prod con el navegador a 1600×900 y 800×700 (contorno entero, nada encima).
- **2026-10-13 — Cuentas al guardar la ficha, sin botón ni modal (sin migración).** `cuenta_zaris` en `CiudadanoCreate/Update` + `services/cuenta_zaris.py::crear_cuenta_zaris_desde_ficha` (lo usan POST/PUT de la ficha y el endpoint); tilde solo-admin; PUT asegura la cuenta de vecino si no hay ninguna; chips con «Reenviar correo de activación»; `CuentaZarisModal` borrado → `CuentaZarisCampos`. Smoke 54/54, navegador, manual §4, skills `modulo-usuarios`/`modulo-app-vecinos`, plan.

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
