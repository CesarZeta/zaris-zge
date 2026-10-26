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

**Última actualización:** 2026-10-26 (Cesar). **IT-01 F1+F2 en prod desde el 2026-10-25** (todos vuelven a ingresar una vez). **F3, super administrador: tareas 1 a 9 hechas en la rama `it01-f3-super-admin`** (`29abaad`, sin merge; 127 y 127b solo en local). En local pasaron la suite (22/22), los barridos y el recorrido en el navegador. Faltan los arreglos de la revisión final y el corte en prod (pregunta 1).

---

## ❓ Preguntas abiertas para César — se plantean en la PRIMERA respuesta de la próxima sesión

> Regla de César (2026-10-20): al cerrar se anota todo lo abierto; al arrancar se pregunta primero. Lo sensible (seguridad) tiene el detalle en la memoria privada de Cesar, no acá (este archivo es público).

1. **IT-01 F3 (super administrador), antes del corte:**
   - **Revisión final de la rama: HECHA el 2026-10-26, veredicto «con arreglos».** Encontró 1 crítico y 4 importantes:
     - crítico: una pantalla de Turnos le muestra contenido clínico al super administrador sin pedirle el motivo;
     - un parámetro global se puede pisar desde un municipio;
     - el selector no se sincroniza entre pestañas;
     - hay guards del frontend que dejan al super administrador sin funciones de nivel 1;
     - dos ediciones globales se registran después de guardarse.
     Además hay 6 menores. El detalle está en el registro local del plan (`progress.md`, líneas `Final:`, en el worktree de la rama). **La pasada de arreglos va antes del corte** (test que falla primero, suite verde).
   - **Decisión — arreglo del sidebar:** en prod, los ítems que el usuario no tiene permitidos se ven igual, porque el `display: flex` del ítem pisa el `hidden`. Pasa desde antes de F3. El arreglo es una línea de CSS que ya está en la rama (`.nav-flat__item[hidden] { display: none }`, `frontend/css/menu.css`). **Recomendación: pasarlo ya a `main` como arreglo aparte**, sin esperar el corte.
   - **Corte en prod (tarea 10, con César):**
     - César da el email de la cuenta nueva, que no se escribe en el repo.
     - César corre la 127 en el SQL Editor (lleva DROP) y la 127b se aplica por MCP.
     - Antes de la 127b, revisar en prod las columnas NOT NULL sin default de `modulos` (la 127b inserta una fila).
     - Merge y deploy; marcador: el path exacto `/api/v1/super/municipios` en `/openapi.json`.
     - Alta de la cuenta con `seed_super_admin.py --imprimir-sql` y `execute_sql`.
     - César elige la clave con «Olvidé mi contraseña».
     - Verificar el login, el selector «Operando en» y el registro de accesos.
   - Después: **F3b (segundo factor)** antes del primer municipio real; el **lote de limpieza** (DROP de los únicos globales viejos, en el SQL Editor) y los menores de Pendientes antes de F4.
   - Hoy, lunes 2026-10-26: revisar los logs de los 3 crons diarios (trámites, integridad, datos demo). Es la primera madrugada que corren por municipio en prod; al cierre todavía no habían corrido.
2. **Asignación automática — revisar ~2026-10-29:** carga de los agentes de las 17 gestiones que asignan solas (en varias, UN solo agente de nivel Gestión recibe todo).
3. **Commits viejos de las dos purgas:** César mandó el pedido a GitHub Support el 2026-10-22; sin respuesta al 2026-10-23 → volver a preguntar el lunes 2026-10-26 (detalle en la memoria privada de Cesar).
4. **Base de conocimiento de ayudas:** la próxima sesión completa es para eso (César, 2026-10-23). Mientras tanto no se tocan manuales.
5. Para otra sesión (César, 2026-10-23): PWA modo escritorio (falta plan) · propuesta app de agentes (reclamos de oficio + control de entradas) · ¿app del vecino con email además de DNI? · mapa del inicio en oscuro.
6. **Primer cierre real de un trámite de vecino en prod:** confirma el aviso de resultado y la encuesta (probados solo en local). Va con los próximos smokes con cuentas reales; César pasa los trámites.

---

## 🔵 En curso

- **IT-01 multi-municipio.** F1+F2 están en prod desde el 2026-10-25 ([`PLAN_MULTI_MUNICIPIO_F1_F2.md`](PLAN_MULTI_MUNICIPIO_F1_F2.md)).
  - **F3, super administrador** ([`PLAN_MULTI_MUNICIPIO_F3.md`](PLAN_MULTI_MUNICIPIO_F3.md)): tareas 1 a 9 en la rama `it01-f3-super-admin`; faltan los arreglos de la revisión final y el corte (pregunta 1). Trae nivel 0 sin municipio con selector «Operando en» (`X-Municipio`), registro `super_admin_acceso` inalterable que ve el administrador del municipio, módulo Municipios, «Parámetros globales» e historia clínica con motivo.
  - Orden para después: F3b (segundo factor) → lote de limpieza → F4 → F5 (antes hay que elegir el hosting del shell: Vercel o Cloudflare Pages) → F6. Recién con F1-F6 hechas puede entrar un segundo municipio real.
- **PWA `zaris-vecinos` — modo escritorio del portal: diseño aprobado el 2026-10-12 (3ª), falta plan + código.** Solo toca el repo de la PWA; spec y pasos en su `ESTADO.md` → En curso.
- **PROPUESTA sin aprobar — app de agentes: reclamos de oficio + «Control de entradas» (QR).** Diseño en [`PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md`](PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md); César lo confirma o corrige antes de F1. No hay código.
- **App de agentes** publicada en `https://agentes.zaris.com.ar` (color del municipio, instalación desde «Mi perfil»); el vecino instala la suya desde su portal. Detalle en `zaris-agentes/ESTADO.md`.

> ### 📣 Para quien retome la PWA `zaris-vecinos` (Roy inactivo por ahora — César 2026-09-20)
> La PWA ya consume todo lo que el backend entregó (desde el 2026-09-26). Falta solo backend NUEVO: `GET /publico/noticias`, URLs de redes en `identidad-municipio` (secciones ocultas mientras tanto), emergencias en `mi-resumen` y la baja de cuenta. Contrato en [`docs/contrato_api_publica.md`](docs/contrato_api_publica.md).

---

## 🟠 Pendientes (backoffice / backend)

**Decisiones de negocio pendientes (César)**
- 🟡 **Botón de pánico de la PWA:** sin probar con el vecino de prueba (dispara una alerta REAL al COM). Las pruebas de vecino y funcionario están hechas (2026-10-12 y 2026-10-23).
- 🟢 **Alta — huecos menores (revisión 2026-10-10):** la clave temporal del funcionario no vence si nunca la usa; la app de agentes no tiene «olvidé mi contraseña» (se recupera desde el login del backoffice).
- 🟠 **Atención — residuos del plan (§4):** "ocupación vs disponibilidad efectiva" en el BI de atención · etapa 2 de HC (vista admin de `historia_clinica_acceso`, break-the-glass, ficha ampliada) · walk-in de Guardia sin evento de Emergencias.
- 🟠 **Trámites — residuo:** los 4 tipos sin circuito (exención de tasas, permiso de espacio público, arbolado urbano, inscripción profesional) tienen la gestión asignada por criterio de Claude, cambiable desde el builder.
- 🟠 **Áreas fijas por regla de negocio:** precargadas y no removibles (renombrables sí) porque atienden módulos; son las 6 áreas activas de San Andrés. Diseño en [`PLAN_MULTI_MUNICIPIO.md`](PLAN_MULTI_MUNICIPIO.md), sin código.
- 🟠 **Config/UX — reunión 2026-07-06** (ClickUp, lista CONFIGURACION y UX): **IT-01** (ver En curso) · **IT-08** botón SOS de la PWA · **IT-07** accesibilidad móvil (PWA) · **IT-09** módulo de Obras (backlog sin alcance).
- 🟢 **Baja de cuenta del vecino:** sin endpoint ni definición; obligatoria si la app va a las stores.
- 🟠 **IT-01 — menores diferidos de la revisión final de F1+F2.** Ninguno afecta a San Andrés solo.
  - **Antes de F4, con el lote de limpieza** (solo aparecen con un segundo municipio): con los únicos globales viejos, un DNI, CUIL o CUIT que ya existe en otro municipio da 500 en el alta de la BUC, en el registro público y en el placeholder de CUIL de Emergencias, y un 409 engañoso («el horario acaba de ser tomado») en el alta por DNI de Agenda. El límite de intentos del login por mail lo comparten todos los municipios.
  - **UX:** un token válido usado desde un subdominio desconocido responde «Sesión vencida» en vez de «Municipio no encontrado» (va con F5).
  - **Preexistentes:** Maestros da 500 con una fecha inválida (`_coerce_types`) y 400 con el texto crudo de la base al crear. El revisor recomienda un manejador global de FK violada → 422.
  - **Herramientas:** el barrido cuenta un 429 como «sin probar» sin fallar. Los placeholders «Ej: REC-2026-000001» de las mesas de OT muestran todavía el formato viejo.
  - **F3 (rama):** en el registro del super administrador (Usuarios), ordenar por «Acción» usa el código interno y no la etiqueta que se ve.
- 🟢 **PWA — Configuración con sesión vieja:** si el vecino entra directo a `/configuracion` con un token vencido, la página se queda ahí (no borra la sesión ni manda al login). No hay bucle, y al volver al inicio cae en el login. Esa página no maneja el 401 por su cuenta, como sí lo hacen las demás (visto en el corte del 2026-10-25; repo `zaris-vecinos`).

**Infra / operativo**
- 🟡 **Vercel: los deploys de Roy quedan BLOCKED** (autor fuera del team; sumar miembros exige plan Pro). **EN PAUSA** mientras Roy no esté activo; se destraba con un commit vacío.
- 🟡 **Barrido visual de modo oscuro** en los módulos React restantes: **POSPUESTO por César 2026-09-20**. Sumar el mapa del inicio: tras los cambios del 2026-10-19 no se revisó en oscuro, y el contorno pizarra de los reclamos casi no se ve sobre el tile oscuro.

**Decisiones cerradas — NO re-proponer**
- **Ayudas: una sola página de base de conocimiento con preguntas, no manuales por módulo** (César, 2026-10-22). No se crean ni actualizan `docs/manual_*.html` mientras tanto (CLAUDE.md §36). Diseño pendiente (pregunta 4).
- **Multi-municipio: UNA base para todos con `id_municipio`** (César, 2026-10-23); decisiones de F2 aceptadas (2026-10-24): tablas globales de Maestros solo para el administrador del municipio base hasta F3; 409 al guardar la identidad sin claves propias; 409 en el alta pública con un documento de otro municipio; `/demo/poblar` con JWT solo para el administrador del municipio demo. **Documentos de identidad por país: tema reservado**, lo trae César (`docs/investigacion_documentos_identidad.md`).
- **Orden por columnas: quedan afuera** las colas operativas, las tablas con orden propio y la configuración (César, 2026-10-22; lista en CLAUDE.md §23).
- **São Paulo DESCARTADO (César, 2026-09-26, con medición):** Railway ya está co-locado con Supabase `us-east-1` y no ofrece región en Sudamérica. Detalle en CLAUDE.md §9 «Región».
- **"La ubicación" de Buscar actualizaciones (PWA) CERRADA como innecesaria** (2026-09-26): el service worker con `autoUpdate` alcanza.
- `DISPATCHER_TOKEN` no se rota (César 2026-09-06). El vecino NO cambia su email desde la app (2026-08-30).
- Purgas del historial git HECHAS el 2026-09-20 y el 2026-10-21 (mapas en `docs/commit-map-purga-*.txt`; un SHA viejo que no resuelve se busca ahí). Roy tiene que re-clonar.
- Claves de las notificaciones push: **no se rotan** (César, 2026-10-21).
- Los reclamos **no se agendan**: la agenda es solo para turnos (César, 2026-10-21).
- Fase 3 de roles (mig 92) y la auditoría de seguridad 2026-07 (48/48) COMPLETAS.

---

## ✅ Hecho reciente (últimas sesiones)

- **2026-10-25/26 — IT-01 F3 en la rama.** Plan escrito (`e080207`, decisiones de César: segundo factor en F3b, cuenta nueva, parámetros globales en Configuración → Sistema). Tareas 1 a 9 hechas y subidas (`29abaad`); la 127 y la 127b solo en local.
- **2026-10-25 — IT-01 F1+F2 en prod (corte, Tarea 20).** Backup completo antes. Migs 125-125d, merge `6c92cb6`, deploy de Railway y mig 126. Verificado: conteos, 401 de los tokens viejos, las 4 superficies en el navegador, `REC-SAN-2026-003161` y el dispatcher por municipio. Rama vieja `it01-multi-municipio` borrada del remoto. Detalle en `HISTORIAL_MIGRACIONES.md`.

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
| Multi-municipio y super administrador (IT-01: decisiones de César + fases) | [`PLAN_MULTI_MUNICIPIO.md`](PLAN_MULTI_MUNICIPIO.md) |
| Qué migración hace qué / cuándo se aplicó | [`HISTORIAL_MIGRACIONES.md`](HISTORIAL_MIGRACIONES.md) |
| Contrato de la API pública que consume la PWA | [`docs/contrato_api_publica.md`](docs/contrato_api_publica.md) |
| Cómo arrancar local / colaborar | [`ONBOARDING.md`](ONBOARDING.md) · [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Quirks/patrones/decisiones (foto de las memorias) | [`docs/memoria-proyecto/`](docs/memoria-proyecto/) |
