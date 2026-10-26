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

**Última actualización:** 2026-10-26, 2ª sesión (Cesar). **IT-01 F3b implementado y probado en local; el corte en prod quedó para la próxima sesión.** Prod sin cambios hoy, todo en verde.

---

## ❓ Preguntas abiertas para César — se plantean en la PRIMERA respuesta de la próxima sesión

> Regla de César (2026-10-20): al cerrar se anota todo lo abierto; al arrancar se pregunta primero. Lo sensible (seguridad) tiene el detalle en la memoria privada de Cesar, no acá (este archivo es público).

1. **Corte de F3b en prod** (Tarea 10 de [`PLAN_MULTI_MUNICIPIO_F3B.md`](PLAN_MULTI_MUNICIPIO_F3B.md)), con César.
   - **Lo que hace César:** generar y cargar `SEGUNDO_FACTOR_CLAVE` en Railway, correr la mig 128 en el SQL Editor, dar el email de la cuenta 102 y vincular su celular.
   - **Orden:** backup → variable de entorno → 128b por MCP y 128 en el Editor → `login.html` (cherry-pick a main) y la app de agentes a main → merge del backend → verificación.
   - **Después del merge:** agregar al `.env.local` de cada checkout las dos variables nuevas (ver `backend/.env.example`).
   - **Recomendación:** hacerlo al arrancar la próxima sesión, antes que cualquier otra cosa de IT-01.
2. **IT-01 después de F3:**
   - **Verificaciones que solo puede hacer César en prod** (en la base ya están verificados el login, la selección del municipio 1 y los requests):
     - pedir de nuevo «Olvidé mi contraseña» con la cuenta del super: el mail tiene que llegar como ZARIS (asunto, encabezado, texto, pie y remitente), sin San Andrés. El arreglo `2f48a55` está desplegado, pero no se probó con un mail real;
     - con `cesar@`, Usuarios → «Registro del super administrador» muestra las filas de la cuenta nueva;
     - como super administrador, Reclamos → listado trae lo mismo que con `cesar@`.
   - Después de F3b: el **lote de limpieza** (DROP de los únicos globales viejos en el SQL Editor; desde ahí la 127c es la que frena que un municipio pise una clave global) y los menores de Pendientes, antes de F4.
3. **Asignación automática — revisar ~2026-10-29:** carga de los agentes de las 17 gestiones que asignan solas (en varias, UN solo agente de nivel Gestión recibe todo).
4. **Commits viejos de las dos purgas:** César mandó el pedido a GitHub Support el 2026-10-22. El 2026-10-26 los commits seguían publicados; si siguen así hacia el 2026-11-05, reclamar el ticket (detalle en la memoria privada de Cesar).
5. **Base de conocimiento de ayudas:** la próxima sesión completa es para eso (César, 2026-10-23). Mientras tanto no se tocan manuales.
6. Para otra sesión (César, 2026-10-23): PWA modo escritorio (falta plan) · propuesta app de agentes (reclamos de oficio + control de entradas) · ¿app del vecino con email además de DNI? · mapa del inicio en oscuro.
7. **Primer cierre real de un trámite de vecino en prod:** confirma el aviso de resultado y la encuesta (probados solo en local). Va con los próximos smokes con cuentas reales; César pasa los trámites.

---

## 🔵 En curso

- **IT-01 multi-municipio.** F1+F2 en prod desde el 2026-10-25 ([`PLAN_MULTI_MUNICIPIO_F1_F2.md`](PLAN_MULTI_MUNICIPIO_F1_F2.md)). **F3 (super administrador) en prod desde el 2026-10-26** ([`PLAN_MULTI_MUNICIPIO_F3.md`](PLAN_MULTI_MUNICIPIO_F3.md); reglas en CLAUDE.md §1/§3).
  - Orden para después: F3b (segundo factor) → lote de limpieza → F4 → F5 (antes hay que elegir el hosting del shell: Vercel o Cloudflare Pages) → F6. Recién con F1-F6 hechas puede entrar un segundo municipio real.
  - **F3b (segundo factor): diseño aprobado por César el 2026-10-26** ([`PLAN_MULTI_MUNICIPIO_F3B_DISENO.md`](PLAN_MULTI_MUNICIPIO_F3B_DISENO.md)); plan en [`PLAN_MULTI_MUNICIPIO_F3B.md`](PLAN_MULTI_MUNICIPIO_F3B.md), con 10 tareas y el corte en la 10:
    - código de una app de autenticación, obligatorio para los niveles 0 y 1;
    - la vinculación la habilita el super;
    - códigos de emergencia;
    - también en la app de agentes.

    **Implementado y probado en local el 2026-10-26** (Tareas 1-9 y revisión final con sus arreglos; rama `it01-f3b-segundo-factor`, y la app de agentes en la rama `segundo-factor` de su repo). **Falta el corte en prod (Tarea 10) con César.**
    - **Para quien trabaje en local después del merge (Roy incluido):** sumar a `backend/.env.local` `SEGUNDO_FACTOR_OBLIGATORIO=false` y una `SEGUNDO_FACTOR_CLAVE` de desarrollo (comando en `backend/.env.example`). Sin eso, las cuentas de nivel 0/1 reciben 503 y los smokes que entran con un administrador fallan.
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
  - **Antes de F4, con el lote de limpieza** (solo con un segundo municipio): por los únicos globales viejos, un DNI, CUIL o CUIT de otro municipio da 500 en la BUC, el registro público y Emergencias, y un 409 engañoso en el alta por DNI de Agenda; el límite de intentos del login por mail es común a todos.
  - Otros: «Sesión vencida» en vez de «Municipio no encontrado» con un subdominio desconocido (F5) · Maestros da 500 con una fecha inválida y 400 con el texto crudo de la base (falta FK → 422) · el barrido cuenta un 429 como «sin probar» · placeholders de OT con el formato viejo.
  - **F3:** únicos parciales del email/usuario de nivel 0 · 403 antes que el texto del módulo en Maestros → municipios · la query en la fila `request` · cache de 60 s de municipios · el inicio del super carga antes de elegir municipio · aviso al cambiar el subdominio · orden por «Acción» en el registro del super · retención de `super_admin_acceso` (F4).
  - **F3b:** dígitos de ancho completo dan 500 en vez de 401 · `smoke_publico_adjuntos` puede dejar una imagen de prueba si falla el login · la marca de revocación y el `iat` usan relojes distintos · «bloqueo» y «habilitado» sin IP ni user agent · el panel no muestra «bloqueado» en una cuenta sin vincular · falta avisar que el QR nuevo reemplaza al anterior · bcrypt sincrónico al vincular · un chequeo trivial en `smoke_alta_un_paso`.
- 🟢 **`smoke_publico_turnos.py` en rojo por datos locales:** el vecino de prueba ya tiene turnos en los días hábiles siguientes y el 6.º intento choca con el límite de 5 reservas por minuto. No es del código: limpiar esos turnos o empezar más adelante.
- 🟢 **PWA — `/configuracion` no maneja el 401** con un token vencido (se queda en la página; sin bucle). Repo `zaris-vecinos`.

**Infra / operativo**
- 🟡 **Vercel: los deploys de Roy quedan BLOCKED** (autor fuera del team; sumar miembros exige plan Pro). **EN PAUSA** mientras Roy no esté activo; se destraba con un commit vacío.
- 🟡 **Barrido visual de modo oscuro** en los módulos React restantes: **POSPUESTO por César 2026-09-20**. Sumar el mapa del inicio: tras los cambios del 2026-10-19 no se revisó en oscuro, y el contorno pizarra de los reclamos casi no se ve sobre el tile oscuro.

**Decisiones cerradas — NO re-proponer**
- **Ayudas: una sola página de base de conocimiento con preguntas, no manuales por módulo** (César, 2026-10-22). No se crean ni actualizan `docs/manual_*.html` mientras tanto (CLAUDE.md §36). Diseño pendiente (pregunta 5).
- **Multi-municipio: UNA base para todos con `id_municipio`** (César, 2026-10-23; decisiones de cada fase en los `PLAN_MULTI_MUNICIPIO*.md`). **Documentos de identidad por país: tema reservado**, lo trae César.
- **Orden por columnas: quedan afuera** las colas operativas, las tablas con orden propio y la configuración (César, 2026-10-22; lista en CLAUDE.md §23).
- **São Paulo DESCARTADO** (2026-09-26, CLAUDE.md §9) · «la ubicación» de Buscar actualizaciones (PWA) innecesaria · no se rotan `DISPATCHER_TOKEN` ni las claves push · el vecino no cambia su email desde la app · los reclamos **no se agendan**.
- Purgas del historial git HECHAS el 2026-09-20 y el 2026-10-21 (mapas en `docs/commit-map-purga-*.txt`). Roy tiene que re-clonar.
- **Guardia: el motivo de derivación sigue visible en la mesa** para todos los que ven la Guardia (César, 2026-10-26). Lo escribe el COM y sirve para el triage; lo clínico ya pasa por el guard de historia clínica.
- Fase 3 de roles (mig 92) y la auditoría de seguridad 2026-07 (48/48) COMPLETAS.

---

## ✅ Hecho reciente (últimas sesiones)

- **2026-10-26 (2ª sesión) — IT-01 F3b implementado en local** (falta el corte): rama `it01-f3b-segundo-factor` (`45b03e5`) y app de agentes `segundo-factor` (`609b004`); migs 128/128b solo en local. Smoke 106/106, suite 22/23 (la roja es la de turnos, por datos), aislamiento 0 fallas, recorrido en el navegador y revisión final con sus arreglos. Además: decisión de la Guardia y borrado del worktree de F3.
- **2026-10-26 — IT-01 F3 en prod** (migs 127/127b/127c, merge `658542e`, con la pasada de arreglos de su revisión final; después, el mail de recuperación del super como ZARIS, `2f48a55`). Detalle en `HISTORIAL_MIGRACIONES.md`.
- **2026-10-25 — IT-01 F1+F2 en prod** (migs 125-126, merge `6c92cb6`; detalle en `HISTORIAL_MIGRACIONES.md`).

> Lo anterior: `HISTORIAL_MIGRACIONES.md` y las skills de cada módulo.

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
