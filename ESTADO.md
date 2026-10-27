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

**Última actualización:** 2026-10-27 (Cesar). **IT-01 F4+F5: corte A en prod** (los tres frontends en Cloudflare Pages; GitHub Pages apagado); F4 sigue en local en la rama `it01-f4-f5`. Bloque del vecino y base de conocimiento anotados para después. Antes, 2026-10-26: **IT-01 F3b (segundo factor) en prod**: migs 128/128b, login del shell, app de agentes y backend; vinculadas la cuenta del super y `cesar@`. Las otras dos cuentas de administrador activas no entran hasta que el super las habilite. **Lote de limpieza de IT-01 en prod** (migs 129/129b): sin únicos globales viejos, tablas legado ni `id_municipio` en las globales.

---

## ❓ Preguntas abiertas para César — se plantean en la PRIMERA respuesta de la próxima sesión

> Regla de César (2026-10-20): al cerrar se anota todo lo abierto; al arrancar se pregunta primero. Lo sensible (seguridad) tiene el detalle en la memoria privada de Cesar, no acá (este archivo es público).

1. **IT-01 — próximo: F4 y F5 juntas** (decisión de César, 2026-10-27): alta de municipios (estado, modelo, primer administrador, módulos por municipio, tope, vaciado) y subdominios por municipio, para que la prueba final sea en prod. Hoy el administrador de un municipio nuevo no puede entrar en prod sin subdominio. **Los tres frontends (shell, app del vecino, app de agentes) se mudan a Cloudflare Pages**: costo cero y el DNS ya está ahí; Vercel Hobby no admite uso comercial. **Diseño y plan aprobados el 2026-10-27:** [`PLAN_MULTI_MUNICIPIO_F4_F5_DISENO.md`](PLAN_MULTI_MUNICIPIO_F4_F5_DISENO.md) y [`PLAN_MULTI_MUNICIPIO_F4_F5.md`](PLAN_MULTI_MUNICIPIO_F4_F5.md) (20 tareas, dos cortes en prod). **Próximo: ejecutar desde la Tarea 1 en una sesión nueva.** En la Tarea 2, César hace en el panel de Cloudflare (desde Chrome) el token y la conexión de los tres repos. Las verificaciones de F3/F3b en prod quedaron hechas el 2026-10-27: el mail de recuperación del super sale como ZARIS, el super ve el mismo total de reclamos que `cesar@` y el ingreso con código deja su evento.
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
  - Orden para después: F4+F5 juntas (hosting elegido: Cloudflare Pages para los tres frontends) → F6. Recién con F1-F6 hechas puede entrar un segundo municipio real.
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
  - **Antes de F4** (solo con un segundo municipio): el límite de intentos del login por mail es común a todos los municipios. `seed_catalogos_emergencias.py` y `seed_activos_local.py` no mandan el municipio y fallan desde la mig 126: la carga de catálogos de un municipio nuevo se define en F4.
  - Otros: «Sesión vencida» en vez de «Municipio no encontrado» con un subdominio desconocido (F5) · Maestros da 500 con una fecha inválida y 400 con el texto crudo de la base (falta FK → 422) · el barrido cuenta un 429 como «sin probar» · placeholders de OT con el formato viejo.
  - **F3:** único parcial del email de nivel 0 (el del usuario lo puso la 129) · 403 antes que el texto del módulo en Maestros → municipios · la query en la fila `request` · cache de 60 s de municipios · el inicio del super carga antes de elegir municipio · aviso al cambiar el subdominio · orden por «Acción» en el registro del super · retención de `super_admin_acceso` (F4).
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
- **Cuentas de administrador sin segundo factor:** la de Roy se habilita cuando César lo indique (no preguntar); la otra cuenta de administrador de César (id 1) queda sin habilitar (César, 2026-10-26).
- **Guardia: el motivo de derivación sigue visible en la mesa** para todos los que ven la Guardia (César, 2026-10-26). Lo escribe el COM y sirve para el triage; lo clínico ya pasa por el guard de historia clínica.
- Fase 3 de roles (mig 92) y la auditoría de seguridad 2026-07 (48/48) COMPLETAS.

---

## ✅ Hecho reciente (últimas sesiones)

- **2026-10-27 — IT-01 F4+F5, corte A en prod: los tres frontends en Cloudflare Pages.** Backup previo; CORS por patrón (`*.zge|vecinos|agentes.zaris.com.ar` y los `zaris-*.pages.dev`) y shell sin suponer subpath (`7293cee`); dominios movidos de a uno (`agentes.`, `vecinos.`, `zge.`) con el CNAME proxied a `<proyecto>.pages.dev`; GitHub Pages apagado y `web-app/dist` fuera del repo (`4e7538d`): ahora lo buildea Cloudflare. Verificado: login, listados y link profundo en los tres, push al celular con la app instalada, `?recovery=`/`?m=`/`?t=` conservados (Pages redirige `x.html` → `x`). Configuración en [`docs/cloudflare_pages.md`](docs/cloudflare_pages.md). Pendiente menor: quitar `agentes.` y `vecinos.` de los proyectos de Vercel y pausar esos proyectos. Sigue F4 en local (rama `it01-f4-f5`; Tareas 1, 2 y 4 hechas).
- **2026-10-26 (3ª sesión) — IT-01, lote de limpieza en prod** (migs 129/129b, código `00acd0b`): borrados los 13 únicos globales viejos, las tablas legado (catálogo viejo de reclamos, numerador viejo de Emergencias) y el `id_municipio` de las 10 tablas globales; antes, el código dejó de usarlos. Local: suite 23/24 (turnos, por datos) y aislamiento 406 rutas sin fallas. En prod, 24 pantallas sin 5xx después del único 500 de la caché de asyncpg (regla en CLAUDE.md §21).
- **2026-10-26 (3ª sesión) — IT-01 F3b en prod.** Backup, `SEGUNDO_FACTOR_CLAVE` en Railway, 128 (César, SQL Editor) y 128b (MCP), login del shell (`0065b27`) y app de agentes (`609b004`) antes que el backend (merge `449f7f6`). Un nivel 2 sigue entrando sin código. Vinculadas la cuenta del super y `cesar@`; el registro del super muestra la habilitación. Además: con una sesión inutilizable el shell mostraba adentro el login de desarrollo (citaba localhost:8080); ahora va al login del shell (`6f71d8c`).
- **2026-10-26 — IT-01 F3 en prod** (migs 127/127b/127c, merge `658542e`, con la pasada de arreglos de su revisión final; después, el mail de recuperación del super como ZARIS, `2f48a55`). Detalle en `HISTORIAL_MIGRACIONES.md`.

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
