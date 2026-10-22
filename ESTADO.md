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

**Última actualización:** 2026-10-22, 3ª sesión (Cesar). Orden por columnas **F3 HECHO** (Ciudadanos, Empresas, Usuarios, Encuestas, Agenda, Maestros): con eso **el estándar §23 queda aplicado en toda la suite**. Ciudadanos y Empresas pasan a filtrar, ordenar y paginar en el servidor (el listado traía hasta 1000 filas y en prod ya hay 956 ciudadanos); el filtro «Tipo» de Encuestas → Envíos ahora ofrece Trámites. Verificado en local (smoke 122/122 + las 13 pantallas recorridas con clics).

---

## ❓ Preguntas abiertas para César — se plantean en la PRIMERA respuesta de la próxima sesión

> Regla de César (2026-10-20): al cerrar se anota todo lo abierto; al arrancar se pregunta primero. Lo sensible (seguridad) tiene el detalle en la memoria privada de Cesar, no acá (este archivo es público).

1. **Funcionario de prueba:** César asigna REC-2026-003079 (Arbolado, sin asignar) al funcionario de prueba desde la mesa (Ver → PLANIFICAR) y confirma si el push llega. Yo no tengo credenciales de un supervisor de Arbolado (y no se prueban claves).
2. **Autoasignación en Alumbrado Público (prendida 2026-10-22):** la gestión tiene UN solo agente de nivel Gestión, así que recibe todo lo que entre. Mirar una semana y decidir si se suma gente o se prende en otras gestiones.
3. **Commits viejos de las dos purgas (2026-09-20 y 2026-10-21): César mandó el pedido a GitHub Support el 2026-10-22.** No preguntar antes del 2026-10-23 (24 h, pedido de César). Después: si GitHub contestó, verificar que los commits viejos ya no abran por SHA (el 2026-10-22 seguían en 200; detalle en la memoria privada de Cesar).
5. **Super administrador multi-municipio (IT-01):** ¿cuándo arrancamos el diseño? (F3 ya está hecho.)
5b. **Base de conocimiento de ayudas** (reemplaza a los manuales, César 2026-10-22): ¿cuándo la diseñamos? Recomendación: una sesión de diseño primero (formato de pregunta/respuesta, búsqueda, si reemplaza al módulo Guías y qué pasa con los `docs/manual_*.html` actuales).
6. **Ciudadano 1618** (alta por agente del 2026-06-15, cuenta de App Vecinos pendiente, sin clave, token vencido): es la única cuenta de vecino pendiente que no es una prueba nuestra conocida. ¿Es una persona real (le reenvío la activación) o una prueba de Roy (no se toca)?
7. Sin respuesta de sesiones anteriores: mail real del retrabajo (¿lo pruebo con tu vecino de prueba?) · PWA modo escritorio (falta plan) · propuesta app de agentes (reclamos de oficio + control de entradas) · ¿app del vecino con email además de DNI? · mapa del inicio en oscuro.

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
- 🟢 **Circuito funcionario → agente: HECHO (2026-10-20/21).** Datos personales solo de la ficha; cargo/horario/equipo los completa el supervisor de la gestión (mig 113); una sola gestión y email por persona, la del agente (mig 116); toda persona con usuario tiene ficha (mig 118, fichas demo con DNI 99.000.000 + id_agente; desde el 2026-10-22 no reciben cuenta de App Vecinos hasta cargar el DNI real). Pendiente de IT-01: el super administrador multi-municipio.

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
- **Ayudas: una sola página de base de conocimiento con preguntas, no manuales por módulo** (César, 2026-10-22). No se crean ni actualizan `docs/manual_*.html` mientras tanto (CLAUDE.md §36). Diseño pendiente (pregunta 5b).
- **Orden por columnas: quedan afuera** las colas operativas (Mesa del día, Guardia, Conflictos, Pendientes de contacto), las tablas con orden propio (historia clínica, historial de accesos, builder de trámites) y la configuración (Catálogo de módulos, Plantillas); Entradas usa selector «Ordenar por»; el desplegable «Ordenar» viejo se reemplazó por encabezados + columna «Alta» (César, 2026-10-22).
- **São Paulo DESCARTADO (César, 2026-09-26, con medición):** Railway ya está co-locado con Supabase `us-east-1` y no ofrece región en Sudamérica. Detalle en CLAUDE.md §9 «Región».
- **"La ubicación" de Buscar actualizaciones (PWA) CERRADA como innecesaria** (2026-09-26): el service worker con `autoUpdate` alcanza.
- `DISPATCHER_TOKEN` no se rota (César 2026-09-06). El vecino NO cambia su email desde la app (2026-08-30).
- Purgas del historial git HECHAS el 2026-09-20 y el 2026-10-21 (mapas en `docs/commit-map-purga-*.txt`; un SHA viejo que no resuelve se busca ahí). Roy tiene que re-clonar.
- Claves de las notificaciones push: **no se rotan** (César, 2026-10-21).
- Los reclamos **no se agendan**: la agenda es solo para turnos (César, 2026-10-21).
- Fase 3 de roles (mig 92) y la auditoría de seguridad 2026-07 (48/48) COMPLETAS.

---

## ✅ Hecho reciente (últimas sesiones)

- **2026-10-22 (3ª) — Orden por columnas F3.** Backend: `GET /buc/ciudadanos` y `/buc/empresas` con `q` (AND multi-palabra) + `desde`/`hasta` + `orden`/`dir` + `X-Total-Count`; `orden` en `/admin/encuestas/envios`; `/agenda/eventos` suma horario y estado. Front: Ciudadanos/Empresas (búsqueda en el servidor, de a 100, columna Alta), Usuarios, Envíos (aviso de tope + filtro Trámites), CSAT por área, Agenda (Eventos, Feriados, Novedades, Espacios, Disponibilidad; `Table` de `ui/` ordenable), Maestros vanilla (por la etiqueta visible de la FK). Smoke `smoke_orden_listados.py` 122/122 + typecheck + recorrido con clics en local.
- **2026-10-22 (2ª) — Orden por columnas F2.** Backend (`utils/orden.py`, lista cerrada, 422): bandejas de Trámites, `GET /turnos`, `GET /agenda/eventos`; además `GET /tramites` acepta `id_tipo_tramite` (el filtro «Tipo» no filtraba). Front: Bandeja (orden en la URL), Mi bandeja, Tipos de trámite, Turnos, Atendidos, Mis turnos y Consultas (en pantalla), Prestaciones, Entradas (selector «Ordenar por»); aviso de tope donde corresponde. Afuera a propósito: Mesa del día, Guardia, historia clínica, builder. Smoke `smoke_orden_listados.py` 64/64 + typecheck + las 9 pantallas recorridas con clics en local.
- **2026-10-22 (2ª) — Ficha demo sin App Vecinos + mig 119.** Guard en `asegurar_cuenta_vecino` (`es_ficha_demo`): alta, PUT de la ficha, `activar-existente` y cuenta ZARIS no crean la credencial; `POST /cuenta-vecino` da 422; chip «no aplica (DNI de prueba)». Smoke `smoke_cuentas_funcionario.py` 63/63 en local + typecheck. Mig 119 en local (no-op) y prod (FK validadas).
- **2026-10-22 — Lista de arranque: datos de prod + 5 cambios chicos.** Cierre de 32 reclamos viejos de prueba (backup `_backup_reclamos_qa_2026_10_22` + `_backup_ot_qa_2026_10_22`, sin mails ni encuestas), autoasignación de Alumbrado, links profundos del shell (`/#/…` y `?modulo=` sobreviven al login; CLAUDE.md §14), «VER PENDIENTES», recuadro «Resolución» en la PWA, logins sin `email`, retiro de los endpoints de OT con agenda. Verificado en local (navegador: 4 casos de link, las 3 apps).
- **2026-10-21 — Generador demo diario con SLA y trámites; Tomar/Resolver desde Reclamos (mig 117); coherencia de cuentas (migs 116, 118); seguridad del CRUD de Maestros; reclamos sin agenda (mig 115); purga de `agente.csv`.** Todo en prod; detalle en git y `HISTORIAL_MIGRACIONES.md`.
- **2026-10-20 — Auditoría de reclamos posterior al cierre (mig 112, `PLAN_AUDITORIA_RECLAMOS.md`), orden por columnas F1, autoasignación (mig 114), supervisor en Maestros → Agentes (mig 113).** En prod.

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
