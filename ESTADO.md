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

**Última actualización:** 2026-10-27 (Cesar, 2ª sesión). **IT-01 F4+F5: Tareas 1 a 18 hechas en la rama `it01-f4-f5`** (local; los tres repos pusheados a su rama `it01-f4-f5`, nada en `main` salvo el corte A): alta de municipios con asistente, ficha, super administradores, tope de cuentas, áreas fijas, exportación con retención y vaciado por grupos, arreglos de pantallas con tablas vacías, documentación y revisión final con sus arreglos. Falta el corte B con César (Tareas 19 y 20). Antes, el mismo día: **corte A en prod** (los tres frontends en Cloudflare Pages; GitHub Pages apagado).

---

## ❓ Preguntas abiertas para César — se plantean en la PRIMERA respuesta de la próxima sesión

> Regla de César (2026-10-20): al cerrar se anota todo lo abierto; al arrancar se pregunta primero. Lo sensible (seguridad) tiene el detalle en la memoria privada de Cesar, no acá (este archivo es público).

1. **IT-01 F4+F5 — próximo: Tarea 19 (revisión de la lista del corte B) y Tarea 20 (corte B en prod), con César.** Código terminado y revisado en la rama `it01-f4-f5` de los tres repos; plan en [`PLAN_MULTI_MUNICIPIO_F4_F5.md`](PLAN_MULTI_MUNICIPIO_F4_F5.md). Para la lista del corte B: migraciones 130 (César, SQL Editor: lleva DROP), 130b y 130c (MCP); crear el bucket privado `exportaciones` en Supabase; verificar en prod que el rol del backend es dueño de `emergencia_log`, `historia_clinica_acceso` y `usuario_segundo_factor_evento` (el vaciado apaga sus triggers dentro de su transacción); crear el municipio modelo en prod y revisar que tenga todas las claves de Configuración → Sistema; merge de las tres ramas; prueba de cierre. Recomendación de Claude: hacerlo en una sesión con tiempo, en ese orden.
1b. **Vaciado del municipio de demo (San Andrés):** hoy se puede vaciar porque está en `demo`, como dice el diseño; la única barrera es escribir el nombre. Recomendación de Claude: bloquear el vaciado del municipio de las direcciones sin prefijo.
1c. **Exportación sin secretos:** la exportación ya no lleva claves, tokens ni secretos del segundo factor (arreglo de la revisión final). Consecuencia: una restauración futura (F6) obliga a esas cuentas a reiniciar clave y segundo factor. Recomendación de Claude: dejarlo así.
1d. **Vercel:** quitar `agentes.` y `vecinos.` de los proyectos de Vercel y pausarlos; el panel muestra un aviso de 2FA de la cuenta de César que no se cerró sin su decisión.
2. **Asignación automática — revisar ~2026-10-29:** carga de los agentes de las 17 gestiones que asignan solas (en varias, UN solo agente de nivel Gestión recibe todo).
3. **Commits viejos de las dos purgas:** César mandó el pedido a GitHub Support el 2026-10-22. El 2026-10-26 los commits seguían publicados; si siguen así hacia el 2026-11-05, reclamar el ticket (detalle en la memoria privada de Cesar).
4. **Bloque del vecino — después de F4 (orden de César, 2026-10-27):**
   1. La web del ciudadano con todo lo que tiene la app (supuesto de Claude, sin confirmar: es el modo escritorio del portal, ver En curso).
   2. Todas las prestaciones del vecino; falta **iniciar un trámite** desde el portal (ni endpoint ni pantalla). Turnos y entradas ya se reservan desde la app (verificado en el código).
   3. **Vecino 360 para el vecino** (perfil o donde convenga).
   4. **Vecino 360 para el municipio:** en Datos y como pestaña de la ficha del ciudadano y de la empresa, con todas sus interacciones; por persona o por empresa representada.
   5. **Base de conocimiento de ayudas** al final, con dos capítulos: canales del vecino y gestión interna. Ya hay un relevamiento inicial de los canales del vecino (2026-10-27). Mientras tanto no se tocan manuales.
5. Para otra sesión (César, 2026-10-23): PWA modo escritorio (falta plan) · propuesta app de agentes (reclamos de oficio + control de entradas) · ¿app del vecino con email además de DNI? · mapa del inicio en oscuro.
6. **Primer cierre real de un trámite de vecino en prod:** confirma el aviso de resultado y la encuesta (probados solo en local). Va con los próximos smokes con cuentas reales; César pasa los trámites.

---

## 🔵 En curso

- **IT-01 multi-municipio.** F1+F2 en prod desde el 2026-10-25 ([`PLAN_MULTI_MUNICIPIO_F1_F2.md`](PLAN_MULTI_MUNICIPIO_F1_F2.md)). **F3 (super administrador) en prod desde el 2026-10-26** ([`PLAN_MULTI_MUNICIPIO_F3.md`](PLAN_MULTI_MUNICIPIO_F3.md); reglas en CLAUDE.md §1/§3).
  - **F3b (segundo factor) en prod desde el 2026-10-26** ([`PLAN_MULTI_MUNICIPIO_F3B.md`](PLAN_MULTI_MUNICIPIO_F3B.md); reglas en CLAUDE.md §1): los niveles 0 y 1 entran con la clave y el código de una app de autenticación; la vinculación la habilita el super (desde Usuarios, o `backend/habilitar_segundo_factor.py` para el nivel 0); hay códigos de emergencia; también en la app de agentes.
    - **Para quien trabaje en local (Roy incluido):** sumar a `backend/.env.local` `SEGUNDO_FACTOR_OBLIGATORIO=false` y una `SEGUNDO_FACTOR_CLAVE` de desarrollo (comando en `backend/.env.example`). Sin eso, las cuentas de nivel 0/1 reciben 503 y los smokes que entran con un administrador fallan.
  - **Lote de limpieza en prod desde el 2026-10-26** (migs 129/129b): el mismo DNI, CUIT o clave de configuración ya puede estar en dos municipios; desde acá la 127c es la que frena que un municipio pise una clave global.
  - **F4+F5: corte A en prod (Cloudflare Pages) y Tareas 1 a 18 en la rama `it01-f4-f5`**, falta el corte B (pregunta 1). Después, F6. Recién con F1-F6 hechas puede entrar un segundo municipio real.
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
- 🟠 **IT-01 — menores diferidos de las revisiones finales (F1+F2, F3, F3b, F4+F5):** lista en [`PLAN_MULTI_MUNICIPIO.md`](PLAN_MULTI_MUNICIPIO.md) → «Menores diferidos». Ninguno afecta a San Andrés solo.
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
- **Cuentas de administrador sin segundo factor:** la de Roy se habilita cuando César lo indique (no preguntar); la otra cuenta de administrador de César (id 1) queda sin habilitar (César, 2026-10-26).
- **Guardia: el motivo de derivación sigue visible en la mesa** para todos los que ven la Guardia (César, 2026-10-26). Lo escribe el COM y sirve para el triage; lo clínico ya pasa por el guard de historia clínica.
- Fase 3 de roles (mig 92) y la auditoría de seguridad 2026-07 (48/48) COMPLETAS.

---

## ✅ Hecho reciente (últimas sesiones)

- **2026-10-27 (2ª sesión) — IT-01 F4+F5, Tareas 1 a 18 en la rama `it01-f4-f5`** (local, verificado en el navegador local): alta de municipios desde el asistente, ficha, super administradores, tope de cuentas, áreas fijas, exportación con retención de 90 días y vaciado por grupos, pantallas con tablas vacías (R3-R10), documentación. Revisión final de la rama por un revisor separado: 5 arreglos (el vaciado podía borrar archivos de otro municipio con una foto armada; un token basura salteaba el 404 de módulo; el vaciado pisaba claves por id; la exportación llevaba secretos; el administrador protegido podía ser uno dado de baja). Suite 21/24 (las 3 fallas son de datos o del servidor local), aislamiento sin fallas en sus 3 modos. En local se borraron dos únicos globales que prod ya no tiene (`ciudadanos_cuil_key`, `empresas_cuit_key`).
- **2026-10-27 — IT-01 F4+F5, corte A en prod: los tres frontends en Cloudflare Pages** (CNAME proxied a `<proyecto>.pages.dev`, CORS por patrón, GitHub Pages apagado y `web-app/dist` fuera del repo: lo buildea Cloudflare). Verificado login, listados, link profundo y push en los tres. Configuración en [`docs/cloudflare_pages.md`](docs/cloudflare_pages.md).

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
