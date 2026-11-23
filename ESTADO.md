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

**Última actualización:** 2026-11-23 cierre (Cesar). **Material de marketing** (sumario, presentación de 11 páginas, correo) y, al contrastarlo con el producto: notificaciones del vecino repuestas, vacunación en San Andrés, app del vecino sin tipografía con serifa, acentos en todo el sistema. **Sigue registro previo F2.** Vuelta atrás de la barrera: `DB_BARRERA=false` en Railway.

---

## ❓ Preguntas abiertas para César — se plantean en la PRIMERA respuesta de la próxima sesión

> Regla de César (2026-10-20): al cerrar se anota todo lo abierto; al arrancar se pregunta primero. Lo sensible (seguridad) tiene el detalle en la memoria privada de Cesar, no acá (este archivo es público).

1. **Registro previo del vecino y de la empresa** ([`PLAN_REGISTRO_PREVIO.md`](PLAN_REGISTRO_PREVIO.md)): César definió que la cuenta es requisito en toda transacción (salvo emergencias) y que toda cuenta interna tiene su ficha. F1 hecha el 2026-11-23 (cerradas las dos reservas públicas sin cuenta). Las 853 cuentas pendientes de los vecinos ya cargados se crearon ese día, sin correos (§5). **Sigue F2** (exigir la cuenta en el backoffice y dar de alta sin perder lo cargado); no espera respuesta de César. Trámites del vecino: cerrado; **falta borrar** la rama remota `tramites-vecino-fase1` (sus 13 commits están en `main`, comparados el 2026-11-23): `git push origin --delete tramites-vecino-fase1`, lo corre César.
2. **Bloque del vecino — después de F4 (orden de César, 2026-10-27):**
   1. La web del ciudadano con todo lo que tiene la app (supuesto de Claude, sin confirmar: es el modo escritorio del portal, ver En curso).
   2. Todas las prestaciones del vecino: trámites, turnos y entradas ya se hacen desde la app (trámites desde el 2026-11-22). Quedan los trámites de empresa (segunda etapa del spec).
   3. **Vecino 360 para el vecino** (perfil o donde convenga).
   4. **Vecino 360 para el municipio:** en Datos y como pestaña de la ficha del ciudadano y de la empresa, con todas sus interacciones; por persona o por empresa representada.
   5. **Base de conocimiento de ayudas**, con dos capítulos: canales del vecino y gestión interna. Ya hay un relevamiento inicial de los canales del vecino (2026-10-27). Mientras tanto no se tocan manuales. César la adelantó el 2026-10-30 empezando por el material de venta (pregunta 5).
3. **App de agentes: circuito aprobado por César el 2026-11-23, cerrado** ([`PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md`](PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md)); no pedir más pruebas, lo cubre `smoke_agentes_app.py`. REL-SAN-2026-000001 queda sin asignar («Calles y veredas» asigna a mano y no tiene agentes de nivel Gestión). Para otra sesión (César, 2026-10-23): PWA modo escritorio (falta plan) · ¿app del vecino con email además de DNI? · mapa del inicio en oscuro.
4. **Arreglos que dejó la prueba de cierre:** quedan el 9 (App Vecinos: catálogo de emergencias del vecino, pide diseño) y menores del 10 y 11, en `PLAN_MULTI_MUNICIPIO_F4_F5.md` → «Prueba de cierre — hallazgos» → «2026-11-19».
5. **Material de marketing (2026-11-23):** en `folletos/` (solo en la máquina de César, fuera del repo): sumario, presentación con carátula y cierre, y correo. César lo revisa; falta su respuesta sobre teléfono o WhatsApp en el cierre (recomendación: sumarlo) y probar el QR y una impresión. Pedido nuevo: **relevamiento del mercado**. Sigue abierta la revisión de `docs/base_conocimiento/resumen_circuitos.md` (recomendación: darla por reemplazada por el sumario).

---

## 🔵 En curso

- **IT-01 multi-municipio: completa en prod (F1-F6).** Planes y decisiones en los `PLAN_MULTI_MUNICIPIO*.md`, reglas en CLAUDE.md §1/§3/§10. Quedan los arreglos de la prueba de cierre (pregunta 4) y los menores diferidos.
  - **Para quien trabaje en local (Roy incluido):** sumar a `backend/.env.local` `SEGUNDO_FACTOR_OBLIGATORIO=false` y una `SEGUNDO_FACTOR_CLAVE` de desarrollo (comando en `backend/.env.example`). Sin eso, las cuentas de nivel 0/1 reciben 503 y los smokes que entran con un administrador fallan.
- **PWA `zaris-vecinos` — modo escritorio del portal: diseño aprobado el 2026-10-12 (3ª), falta plan + código.** Solo toca el repo de la PWA; spec y pasos en su `ESTADO.md` → En curso.
- **Registro previo, F2 (próximo trabajo):** en el backoffice, exigir la cuenta del vecino en reclamos (`reclamos.py::crear_reclamo`), turnos (`turnos.py`) y entradas (`agenda_v2.py`) con `services/tramites/alta.py::vecino_tiene_cuenta`, y que `CiudadanoSearch` dé de alta a la persona en un modal sin perder lo cargado. Después F3 (registro en la PWA + número de usuario), F4 y F5.
- **App de agentes** publicada en `https://agentes.zaris.com.ar` (color del municipio, instalación desde «Mi perfil»); el vecino instala la suya desde su portal. Detalle en `zaris-agentes/ESTADO.md`.

> **PWA `zaris-vecinos`:** consume todo lo que el backend entregó. Falta backend nuevo: noticias, redes, emergencias en `mi-resumen` y baja de cuenta ([`docs/contrato_api_publica.md`](docs/contrato_api_publica.md)).

---

## 🟠 Pendientes (backoffice / backend)

**Aprobado por César el 2026-11-23, sin empezar** (salió de contrastar el material de marketing con el producto)
- 🟠 **Confirmación y recordatorio de turnos y entradas al vecino** (aviso, correo y notificación; hoy no se manda ninguno). Pide migración del CHECK de `ciudadano_aviso.tipo`, con `DROP`.
- 🟠 **Tablero de trámites en Datos.**
- 🟠 **KPI de gestión** (lo define César): coeficiente que combina los indicadores de gestión con la encuesta de cierre, solo para las interacciones que tienen un vecino: reclamos, turnos, entradas y trámites. **Emergencias, relevamientos y la Guardia quedan afuera** del modelo de análisis y sin encuesta. Por eso no se proponen ni el tablero ni la encuesta de emergencias.
- 🟢 **Modo escritorio del portal** (ya en «En curso»). La agenda en la app de agentes no se promete.

**Decisiones de negocio pendientes (César)**
- 🟠 **Registro previo:** ver pregunta 1. Siguen F2 (backoffice), F3 (registro del vecino en el portal y la app, y después su usuario: §6), F4 (alta de empresa del lado del vecino) y F5 (igualar las altas).
- 🟠 **Prueba de cierre — hallazgos que quedan**, con detalle en [`PLAN_MULTI_MUNICIPIO_F4_F5.md`](PLAN_MULTI_MUNICIPIO_F4_F5.md) → «Prueba de cierre — hallazgos»: (6) pantalla para que el super elija municipio, (7) encuestas en «Promociones» de Gmail, (9) App Vecinos, (10) tres verificaciones pendientes, (11) menores.
- 🟢 **Contorno — 9 menores de la revisión final (2026-10-28), ninguno rompe:** lista en [`PLAN_CONTORNO_MUNICIPIO.md`](PLAN_CONTORNO_MUNICIPIO.md) → «Menores diferidos» (el más visible: la fecha del origen en UTC).
- 🟡 **Botón de pánico de la PWA:** sin probar con el vecino de prueba (dispara una alerta REAL al COM). Las pruebas de vecino y funcionario están hechas (2026-10-12 y 2026-10-23).
- 🟢 **Alta (2026-10-10):** la clave temporal del funcionario no vence si no la usa; la app de agentes no tiene «olvidé mi contraseña».
- 🟠 **Atención — residuos del plan (§4):** "ocupación vs disponibilidad efectiva" en el BI de atención · etapa 2 de HC (vista admin de `historia_clinica_acceso`, break-the-glass, ficha ampliada) · walk-in de Guardia sin evento de Emergencias.
- 🟠 **Trámites — residuo:** los 4 tipos sin circuito (exención de tasas, permiso de espacio público, arbolado urbano, inscripción profesional) tienen la gestión asignada por criterio de Claude, cambiable desde el builder.
- 🟠 **Config/UX — reunión 2026-07-06** (ClickUp, lista CONFIGURACION y UX): **IT-01** (ver En curso) · **IT-08** botón SOS de la PWA · **IT-07** accesibilidad móvil (PWA) · **IT-09** módulo de Obras (backlog sin alcance).
- 🟢 **Baja de cuenta del vecino:** sin endpoint ni definición; obligatoria si la app va a las stores.
- 🟠 **IT-01 — menores diferidos de las revisiones finales (F1+F2, F3, F3b, F4+F5):** lista en [`PLAN_MULTI_MUNICIPIO.md`](PLAN_MULTI_MUNICIPIO.md) → «Menores diferidos». Ninguno afecta a San Andrés solo.
- 🟠 **`smoke_aislamiento.py` en rojo (4 fallas, 2026-11-23):** rutas nuevas de trámites (`/pedidos/{id_pedido}/cancelar` y `/visto`, mig 139, entre otras) sin mapear en el test; no es un cruce de municipios. Sumar `id_pedido` a sus datos.
- 🟢 **«Permiso de Demostración E2E»** (tipo de trámite de prueba, activo en San Andrés, 28 expedientes): sacarlo de la vista antes de una demostración; sin respuesta de César.
- 🟢 **`smoke_publico_turnos.py` en rojo por datos locales** (el 6.º intento choca con el límite de 5 reservas por minuto); no es del código.
- 🟢 **PWA — `/configuracion` no maneja el 401** con un token vencido (se queda en la página; sin bucle). Repo `zaris-vecinos`.
- 🟢 **Docs desactualizadas** (2026-10-30): `docs/flujos_operativos_zge.md` (estados de OT, turnos y eventos) y las skills `modulo-encuestas`, `modulo-permisos`, `modulo-usuarios`; revisar al tocar cada módulo. Textos de la PWA que prometen de más: `zaris-vecinos/ESTADO.md`.

**Infra / operativo**
- 🟡 **Barrido visual de modo oscuro** en los módulos React restantes y el mapa del inicio (el contorno de los reclamos casi no se ve): **POSPUESTO por César 2026-09-20**.

**Decisiones cerradas — NO re-proponer**
- **Ayudas: una sola página de base de conocimiento con preguntas, no manuales por módulo** (César, 2026-10-22). No se crean ni actualizan `docs/manual_*.html` mientras tanto (CLAUDE.md §36). Diseño pendiente (preguntas 2 y 5).
- **Multi-municipio: UNA base para todos con `id_municipio`** (César, 2026-10-23; decisiones de cada fase en los `PLAN_MULTI_MUNICIPIO*.md`). **Documentos de identidad por país: tema reservado**, lo trae César.
- **Orden por columnas: quedan afuera** las colas operativas, las tablas con orden propio y la configuración (César, 2026-10-22; lista en CLAUDE.md §23).
- **São Paulo DESCARTADO** (2026-09-26, CLAUDE.md §9) · «la ubicación» de Buscar actualizaciones (PWA) innecesaria · no se rotan `DISPATCHER_TOKEN` ni las claves push · el vecino no cambia su email desde la app · los reclamos **no se agendan**.
- Purgas del historial git HECHAS el 2026-09-20 y el 2026-10-21 (mapas en `docs/commit-map-purga-*.txt`). Roy tiene que re-clonar.
- **Cuentas de administrador sin segundo factor:** la de Roy se habilita cuando César lo indique (no preguntar); la otra cuenta de administrador de César (id 1) queda sin habilitar (César, 2026-10-26).
- **Asignación automática: sin cambios** (César, 2026-10-30); volver a mirarla con un segundo municipio o volumen real.
- **Santa Cruz y Santiago del Estero sin gobiernos locales en Georef: se espera** a que un municipio real lo pida (César, 2026-10-30).
- **Guardia: el motivo de derivación sigue visible en la mesa** (César, 2026-10-26).
- **El super administrador no opera trámites** (César, 2026-11-02): cadena de custodia; solo se corrige el mensaje.
- **Encuestas fijas hasta nuevo aviso** (César, 2026-11-03): todo municipio arranca con las preguntas por defecto, en el formato de dos positivas, la neutra y dos negativas, y no se editan. El alta las copia siempre y el vaciado no las toca. Sin editor por municipio. Completar las ramas de la encuesta estándar sí se hace.
- Fase 3 de roles (mig 92) y la auditoría de seguridad 2026-07 (48/48) COMPLETAS.

---

## ✅ Hecho reciente (últimas sesiones)

- **2026-11-23 (tarde):** **notificaciones del vecino repuestas** en la PWA (César; se habían quitado el 2026-07-06 a pedido de Roy: **Roy, avisado por acá**); backend: un dispositivo avisa a un solo vecino y apagar uno no apaga los otros (`smoke_publico_push.py` 10/10). **Vacunación en San Andrés** (`seed_vacunacion_demo.sql`). **Acentos** en catálogos de San Andrés y del modelo (248 filas), pantallas, correos y mensajes; «GESTIÓN ESTADO» en el shell. PWA: títulos sin serifa.
- **2026-11-23:** **App de agentes F2 y F3** cerrada y aprobada; Datos y Reclamos con filtro «Transacción»; registro previo F1 (reservas sin cuenta, 410) y 853 cuentas creadas.
- **2026-11-22 (noche):** App de agentes F1 + F1b (relevamientos `REL-`, control de entradas; mig 141). Trámites del vecino cerrado.

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
| Versionado y «Acerca de» | [`PLAN_VERSIONADO.md`](PLAN_VERSIONADO.md) |
| Qué migración hace qué / cuándo se aplicó | [`HISTORIAL_MIGRACIONES.md`](HISTORIAL_MIGRACIONES.md) |
| Contrato de la API pública que consume la PWA | [`docs/contrato_api_publica.md`](docs/contrato_api_publica.md) |
| Cómo arrancar local / colaborar | [`ONBOARDING.md`](ONBOARDING.md) · [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Quirks/patrones/decisiones (foto de las memorias) | [`docs/memoria-proyecto/`](docs/memoria-proyecto/) |
