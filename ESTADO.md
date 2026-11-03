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

**Última actualización:** 2026-11-03 (Cesar). Prueba de cierre de F4+F5 terminada en prod, salvo quitar los dominios de `prueba`: claves cruzadas, exportación, vaciado, módulos vacíos, recarga desde cero, tope de cuentas, San Andrés intacto y municipio 6 en baja. Arreglados en el camino: vaciado con trámites numerados, ventana visible del vaciado y encuestas fijas (mig 135). Quedan los arreglos de la prueba (pendientes) y diseñar el versionado.

---

## ❓ Preguntas abiertas para César — se plantean en la PRIMERA respuesta de la próxima sesión

> Regla de César (2026-10-20): al cerrar se anota todo lo abierto; al arrancar se pregunta primero. Lo sensible (seguridad) tiene el detalle en la memoria privada de Cesar, no acá (este archivo es público).

1. **IT-01 F4+F5 — último paso de la prueba de cierre:** autorizar a Claude a quitar los dominios de `prueba` (`tools/dominios_municipio.py prueba --quitar`): cambia DNS y el control de permisos lo frena sin una autorización expresa. El municipio 6 ya está en baja y su API responde 404.
   - **Versionado:** César pidió empezar a manejarlo (2026-11-03). Hoy la versión está escrita a mano (`v0.1` en el login y en la barra inferior, `1.0.0` en la API, `0.1.0` en la App Vecinos) y el repo no tiene tags. Falta definir el alcance con César.
2. **Vercel:** César activa el 2FA de su cuenta de Vercel; después Claude quita `agentes.` y `vecinos.` de los proyectos viejos y los pausa (decidido el 2026-10-27).
3. **Commits viejos de `agente.csv`:** el pedido del 2026-10-22 no había quedado registrado; el ticket se abrió el 2026-10-30 por el asistente de GitHub Support. Si hacia el 2026-11-06 el commit sigue publicado, reclamar en el mismo ticket (detalle en la memoria privada de Cesar).
4. **Bloque del vecino — después de F4 (orden de César, 2026-10-27):**
   1. La web del ciudadano con todo lo que tiene la app (supuesto de Claude, sin confirmar: es el modo escritorio del portal, ver En curso).
   2. Todas las prestaciones del vecino; falta **iniciar un trámite** desde el portal (ni endpoint ni pantalla). Turnos y entradas ya se reservan desde la app (verificado en el código).
   3. **Vecino 360 para el vecino** (perfil o donde convenga).
   4. **Vecino 360 para el municipio:** en Datos y como pestaña de la ficha del ciudadano y de la empresa, con todas sus interacciones; por persona o por empresa representada.
   5. **Base de conocimiento de ayudas**, con dos capítulos: canales del vecino y gestión interna. Ya hay un relevamiento inicial de los canales del vecino (2026-10-27). Mientras tanto no se tocan manuales. César la adelantó el 2026-10-30 empezando por el material de venta (pregunta 7).
5. Para otra sesión (César, 2026-10-23): PWA modo escritorio (falta plan) · propuesta app de agentes (reclamos de oficio + control de entradas) · ¿app del vecino con email además de DNI? · mapa del inicio en oscuro.
6. **Arreglos que dejó la prueba de cierre:** confirmar el orden recomendado en `PLAN_MULTI_MUNICIPIO_F4_F5.md` → «Prueba de cierre — hallazgos». Lo primero es el clonador con los ids dentro de JSON, porque bloquea el alta de un municipio real. Dos piden diseño antes de codear: la pantalla para que el super elija municipio y el catálogo de emergencias del vecino.
7. **Base de conocimiento — material de venta por circuito** (2026-10-30): borrador `docs/base_conocimiento/resumen_circuitos.md`, **solo en la máquina de César, sin commitear** (lleva notas internas; el repo es público). César revisa los (\*) de los tableros (varios son propuesta de Claude), dice si su «punto 2» era esta estructura o es otra pieza (supuesto de Claude: ficha técnica por circuito) y aprueba el texto. Recomendación: commitearlo sin «Notas internas».

---

## 🔵 En curso

- **IT-01 multi-municipio.** En prod: F1+F2 (2026-10-25), F3 super administrador, F3b segundo factor y lote de limpieza (2026-10-26); planes en los `PLAN_MULTI_MUNICIPIO*.md` y reglas en CLAUDE.md §1/§3/§10.
  - **Para quien trabaje en local (Roy incluido):** sumar a `backend/.env.local` `SEGUNDO_FACTOR_OBLIGATORIO=false` y una `SEGUNDO_FACTOR_CLAVE` de desarrollo (comando en `backend/.env.example`). Sin eso, las cuentas de nivel 0/1 reciben 503 y los smokes que entran con un administrador fallan.
  - **F4+F5 en prod desde el 2026-10-27** (corte A: Cloudflare Pages; corte B: alta de municipios, ficha, super administradores, tope, áreas fijas, exportación y vaciado). Falta la prueba de cierre (pregunta 1). Después, F6. Recién con F1-F6 hechas puede entrar un segundo municipio real.
  - Decisiones de César en el corte B: en [`PLAN_MULTI_MUNICIPIO_F4_F5.md`](PLAN_MULTI_MUNICIPIO_F4_F5.md).
- **PWA `zaris-vecinos` — modo escritorio del portal: diseño aprobado el 2026-10-12 (3ª), falta plan + código.** Solo toca el repo de la PWA; spec y pasos en su `ESTADO.md` → En curso.
- **PROPUESTA sin aprobar — app de agentes: reclamos de oficio + «Control de entradas» (QR).** Diseño en [`PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md`](PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md); César lo confirma o corrige antes de F1. No hay código.
- **App de agentes** publicada en `https://agentes.zaris.com.ar` (color del municipio, instalación desde «Mi perfil»); el vecino instala la suya desde su portal. Detalle en `zaris-agentes/ESTADO.md`.

> **PWA `zaris-vecinos`:** consume todo lo que el backend entregó. Falta backend nuevo: noticias, redes, emergencias en `mi-resumen` y baja de cuenta ([`docs/contrato_api_publica.md`](docs/contrato_api_publica.md)).

---

## 🟠 Pendientes (backoffice / backend)

**Decisiones de negocio pendientes (César)**
- 🔴 **Prueba de cierre de F4+F5 — lo que queda:** pregunta 1 (quitar los dominios de `prueba`).
- 🔴 **Prueba de cierre — hallazgos del 2026-11-02 y 2026-11-03 para arreglar**, con detalle y orden en [`PLAN_MULTI_MUNICIPIO_F4_F5.md`](PLAN_MULTI_MUNICIPIO_F4_F5.md) → «Prueba de cierre — hallazgos»: (1) **el clonador y `contar_cruces` no ven ids dentro de JSON** (bloquea un municipio real; datos ya corregidos con la mig 134), (2) 6 campos de trámites con opciones en formato viejo que el validador rechaza, (3) mensaje de trámites para el super, (4) nombre del municipio oculto a ≤ 900 px, (5) «ver contraseña» en el login del backoffice, (6) pantalla para que el super elija municipio, (7) encuestas en «Promociones» de Gmail, (9) App Vecinos, (10) tres verificaciones pendientes, (11) menores.
- 🟢 **Contorno — 9 menores de la revisión final (2026-10-28), ninguno rompe:** lista en [`PLAN_CONTORNO_MUNICIPIO.md`](PLAN_CONTORNO_MUNICIPIO.md) → «Menores diferidos» (el más visible: la fecha del origen en UTC).
- 🟡 **Botón de pánico de la PWA:** sin probar con el vecino de prueba (dispara una alerta REAL al COM). Las pruebas de vecino y funcionario están hechas (2026-10-12 y 2026-10-23).
- 🟢 **Alta (2026-10-10):** la clave temporal del funcionario no vence si no la usa; la app de agentes no tiene «olvidé mi contraseña».
- 🟠 **Atención — residuos del plan (§4):** "ocupación vs disponibilidad efectiva" en el BI de atención · etapa 2 de HC (vista admin de `historia_clinica_acceso`, break-the-glass, ficha ampliada) · walk-in de Guardia sin evento de Emergencias.
- 🟠 **Trámites — residuo:** los 4 tipos sin circuito (exención de tasas, permiso de espacio público, arbolado urbano, inscripción profesional) tienen la gestión asignada por criterio de Claude, cambiable desde el builder.
- 🟠 **Config/UX — reunión 2026-07-06** (ClickUp, lista CONFIGURACION y UX): **IT-01** (ver En curso) · **IT-08** botón SOS de la PWA · **IT-07** accesibilidad móvil (PWA) · **IT-09** módulo de Obras (backlog sin alcance).
- 🟢 **Baja de cuenta del vecino:** sin endpoint ni definición; obligatoria si la app va a las stores.
- 🟠 **IT-01 — menores diferidos de las revisiones finales (F1+F2, F3, F3b, F4+F5):** lista en [`PLAN_MULTI_MUNICIPIO.md`](PLAN_MULTI_MUNICIPIO.md) → «Menores diferidos». Ninguno afecta a San Andrés solo.
- 🟢 **`smoke_publico_turnos.py` en rojo por datos locales** (el 6.º intento choca con el límite de 5 reservas por minuto); no es del código.
- 🟢 **PWA — `/configuracion` no maneja el 401** con un token vencido (se queda en la página; sin bucle). Repo `zaris-vecinos`.
- 🟠 **Encuestas — contacto pedido en una encuesta de trámite:** `registrar_respuesta` (paso 5) no tiene la rama de `id_tramite` y el aviso al área diría «Reserva de evento #None» (verificado 2026-10-30).
- 🟢 **Encuestas → Resumen** filtra solo por fechas (el backend ya acepta circuito y área); «Satisfacción por área» cuenta solo reclamos.
- 🟢 **Docs desactualizadas** (2026-10-30): `docs/flujos_operativos_zge.md` (estados de OT, turnos y eventos) y las skills `modulo-encuestas`, `modulo-permisos`, `modulo-usuarios`; revisar al tocar cada módulo. Textos de la PWA que prometen de más: `zaris-vecinos/ESTADO.md`.

**Infra / operativo**
- 🟡 **Barrido visual de modo oscuro** en los módulos React restantes y el mapa del inicio (el contorno de los reclamos casi no se ve): **POSPUESTO por César 2026-09-20**.

**Decisiones cerradas — NO re-proponer**
- **Ayudas: una sola página de base de conocimiento con preguntas, no manuales por módulo** (César, 2026-10-22). No se crean ni actualizan `docs/manual_*.html` mientras tanto (CLAUDE.md §36). Diseño pendiente (preguntas 4 y 7).
- **Multi-municipio: UNA base para todos con `id_municipio`** (César, 2026-10-23; decisiones de cada fase en los `PLAN_MULTI_MUNICIPIO*.md`). **Documentos de identidad por país: tema reservado**, lo trae César.
- **Orden por columnas: quedan afuera** las colas operativas, las tablas con orden propio y la configuración (César, 2026-10-22; lista en CLAUDE.md §23).
- **São Paulo DESCARTADO** (2026-09-26, CLAUDE.md §9) · «la ubicación» de Buscar actualizaciones (PWA) innecesaria · no se rotan `DISPATCHER_TOKEN` ni las claves push · el vecino no cambia su email desde la app · los reclamos **no se agendan**.
- Purgas del historial git HECHAS el 2026-09-20 y el 2026-10-21 (mapas en `docs/commit-map-purga-*.txt`). Roy tiene que re-clonar.
- **Cuentas de administrador sin segundo factor:** la de Roy se habilita cuando César lo indique (no preguntar); la otra cuenta de administrador de César (id 1) queda sin habilitar (César, 2026-10-26).
- **Asignación automática: sin cambios** (César, 2026-10-30); volver a mirarla con un segundo municipio o volumen real.
- **Santa Cruz y Santiago del Estero sin gobiernos locales en Georef: se espera** a que un municipio real lo pida (César, 2026-10-30).
- **Guardia: el motivo de derivación sigue visible en la mesa** (César, 2026-10-26).
- **El super administrador no opera trámites** (César, 2026-11-02): cadena de custodia; solo se corrige el mensaje.
- **Encuestas fijas hasta nuevo aviso** (César, 2026-11-03): todo municipio arranca con las preguntas por defecto, en el formato de dos positivas, la neutra y dos negativas, y no se editan. El alta las copia siempre y el vaciado no las toca. Sin editor por municipio y sin completar ramas.
- Fase 3 de roles (mig 92) y la auditoría de seguridad 2026-07 (48/48) COMPLETAS.

---

## ✅ Hecho reciente (últimas sesiones)

- **2026-11-03 — Prueba de cierre de F4+F5, parte final:** claves cruzadas; exportación y vaciado de los cuatro grupos (1056 filas; San Andrés y modelo sin cambios); módulos vacíos y 178 `GET` sin ningún 5xx; recarga desde cero con el mismo DNI y email; tope de cuentas en 409; barrido de San Andrés y `smoke_publico_turnos` 12 OK; municipio 6 en baja; guía privada en `credenciales-testing/`. Arreglados: vaciado con trámites numerados (`5933ac8`), ventana visible del vaciado (`9ddf362`), mig 135 (`14f2bf6`) y encuestas obligatorias en el alta.
- **2026-11-02 — Prueba de cierre de F4+F5, pasos 1-5 en prod con César** (municipio 6, «Municipio de Prueba»): alta del vecino con el DNI de uno de San Andrés (mail y links con `PRUE`) · REC-PRUE-2026-000001 → OT-PRUE-2026-000001 a mikeamigo → resuelta desde `prueba.agentes` · EM-PRUE-2026-000001 desde la App Vecinos, cerrada desde el tablero · turno reservado desde la App Vecinos y cumplido · evento con reserva por Agenda · POD-PRUE-2026-0001 hasta «Archivado / Aprobado», con aviso al vecino y encuesta (**primer cierre real de un trámite de vecino en prod**) · tres encuestas enviadas y respondidas · Entradas deshabilitado: fuera del menú y 404 en la API del vecino · 0 registros que crucen de municipio. Arreglados en el camino: **mig 134** (gestiones dentro de JSON de las transiciones; local y prod, backup `_backup_cruces_transicion_2026_11_02`) y el **formulario de encuestas** (`3da4086`).
- **2026-10-30 —** migs 133/133b (gestiones y tipos de reclamo que cruzaban de municipio) y mapa de la App Vecinos por municipio (`9d1f8ad`). Claves de las cuentas de prueba de prod renovadas, fuera del repo: pedíselas a César.

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
