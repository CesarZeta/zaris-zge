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

**Última actualización:** 2026-10-30 (Cesar, cierre de la 2ª sesión). César postergó la prueba de cierre (necesita su teléfono, sus casillas y sus códigos) y adelantó la base de conocimiento: borrador del material de venta por circuito (pregunta 7). Antes, en el día: mapa de la App Vecinos en prod y falla de aislamiento entre municipios arreglada (ver Hecho reciente).

---

## ❓ Preguntas abiertas para César — se plantean en la PRIMERA respuesta de la próxima sesión

> Regla de César (2026-10-20): al cerrar se anota todo lo abierto; al arrancar se pregunta primero. Lo sensible (seguridad) tiene el detalle en la memoria privada de Cesar, no acá (este archivo es público).

1. **IT-01 F4+F5 — próximo: el resto de la prueba de cierre con César** (postergada por César el 2026-10-30 a favor de la base de conocimiento; sigue igual) (spec §5 de `PLAN_MULTI_MUNICIPIO_F4_F5_DISENO.md`; hechos el alta, la invitación, el tope, el contorno y el arreglo de los cruces). Orden propuesto, con quién hace cada paso:
   1. César, en el teléfono: vecino en `prueba.vecinos.zaris.com.ar` con el **DNI 30123456** (el mismo de un vecino de San Andrés) y su Gmail; mirar que el link del mail vaya a `prueba.…`; cargar un reclamo «Árbol/tocón/rama con peligro de caída» y una emergencia desde «Nueva emergencia» (no el botón de pánico).
   2. César entra como **admin.prue** (clave + código) en la pestaña del navegador de VS Code; Claude maneja el backoffice: OT a mikeamigo (Arbolado asigna a mano), espacio + prestación + disponibilidad, turno y evento con reserva para el vecino, un trámite, Entradas 404 (backoffice y vecino).
   3. César, en el teléfono: **mikeamigo** en `prueba.agentes.zaris.com.ar` (clave temporal en su Hotmail) resuelve la OT.
   4. Claude: cada vecino con el mismo DNI ve solo lo suyo.
   5. Encuesta respondida → vaciado con exportación y re-carga (super) → recorrido sin 500 → San Andrés en verde → baja + `tools/dominios_municipio.py prueba --quitar` + guía privada.
   - **Decisión pendiente: la encuesta sale 24 h después del cierre** (`HORAS_DELAY_ENVIO`). Recomendación de Claude: adelantar 24 h la fecha de ese único `encuesta_envio` del municipio 6 para terminar en el día (el envío diario ya funciona en San Andrés; lo que se prueba es el link a `prueba.…` y que la respuesta quede en su municipio). La otra opción es esperar al día siguiente.
2. **Vercel:** César activa el 2FA de su cuenta de Vercel; después Claude quita `agentes.` y `vecinos.` de los proyectos viejos y los pausa (decidido el 2026-10-27).
3. **Commits viejos de `agente.csv`:** el pedido del 2026-10-22 no había quedado registrado; el ticket se abrió el 2026-10-30 por el asistente de GitHub Support. Si hacia el 2026-11-06 el commit sigue publicado, reclamar en el mismo ticket (detalle en la memoria privada de Cesar).
4. **Bloque del vecino — después de F4 (orden de César, 2026-10-27):**
   1. La web del ciudadano con todo lo que tiene la app (supuesto de Claude, sin confirmar: es el modo escritorio del portal, ver En curso).
   2. Todas las prestaciones del vecino; falta **iniciar un trámite** desde el portal (ni endpoint ni pantalla). Turnos y entradas ya se reservan desde la app (verificado en el código).
   3. **Vecino 360 para el vecino** (perfil o donde convenga).
   4. **Vecino 360 para el municipio:** en Datos y como pestaña de la ficha del ciudadano y de la empresa, con todas sus interacciones; por persona o por empresa representada.
   5. **Base de conocimiento de ayudas**, con dos capítulos: canales del vecino y gestión interna. Ya hay un relevamiento inicial de los canales del vecino (2026-10-27). Mientras tanto no se tocan manuales. César la adelantó el 2026-10-30 empezando por el material de venta (pregunta 7).
5. Para otra sesión (César, 2026-10-23): PWA modo escritorio (falta plan) · propuesta app de agentes (reclamos de oficio + control de entradas) · ¿app del vecino con email además de DNI? · mapa del inicio en oscuro.
6. **Primer cierre real de un trámite de vecino en prod:** confirma el aviso de resultado y la encuesta (probados solo en local). Va con los próximos smokes con cuentas reales; César pasa los trámites.
7. **Base de conocimiento — material de venta por circuito** (pedido de César, 2026-10-30): borrador en `docs/base_conocimiento/resumen_circuitos.md`, **solo en la máquina de César, sin commitear** (lleva notas internas y el repo es público). Estructura de César: de cara al vecino · a la gestión · a los altos mandos y la jefatura de gabinete · encuestas y su análisis · tableros de todas las áreas con la matriz volumen / cierre / SLA / satisfacción / seguimiento; lo no implementado va con (\*). Queda que César:
   - revise los (\*) de los tableros: varios son propuesta de Claude, no pedidos anotados (encuesta después de una emergencia, productividad por agente, tablero integral);
   - confirme si su «punto 2» (el pedido decía «dos cosas» y traía una sola) era esta estructura o es otra pieza (supuesto de Claude: una ficha técnica por circuito);
   - apruebe el texto. Recomendación de Claude: commitear sin la sección «Notas internas», que pasa a este archivo.

---

## 🔵 En curso

- **IT-01 multi-municipio.** En prod: F1+F2 (2026-10-25), F3 super administrador, F3b segundo factor y lote de limpieza (2026-10-26); planes en los `PLAN_MULTI_MUNICIPIO*.md` y reglas en CLAUDE.md §1/§3/§10.
  - **Para quien trabaje en local (Roy incluido):** sumar a `backend/.env.local` `SEGUNDO_FACTOR_OBLIGATORIO=false` y una `SEGUNDO_FACTOR_CLAVE` de desarrollo (comando en `backend/.env.example`). Sin eso, las cuentas de nivel 0/1 reciben 503 y los smokes que entran con un administrador fallan.
  - **F4+F5 en prod desde el 2026-10-27** (corte A: Cloudflare Pages; corte B: alta de municipios, ficha, super administradores, tope, áreas fijas, exportación y vaciado). Falta la prueba de cierre (pregunta 1). Después, F6. Recién con F1-F6 hechas puede entrar un segundo municipio real.
  - **Decisiones de César en el corte B:** San Andrés (direcciones sin prefijo) no se puede vaciar; la exportación no lleva secretos (una restauración futura obliga a reiniciar clave y segundo factor); el modelo excluye «inscripción Profesional» (sus aprobaciones apuntan a un agente de San Andrés); partido obligatorio salvo ficticio, un municipio vigente por partido, y un ficticio no pasa a producción; código corto de 4 letras.
- **PWA `zaris-vecinos` — modo escritorio del portal: diseño aprobado el 2026-10-12 (3ª), falta plan + código.** Solo toca el repo de la PWA; spec y pasos en su `ESTADO.md` → En curso.
- **PROPUESTA sin aprobar — app de agentes: reclamos de oficio + «Control de entradas» (QR).** Diseño en [`PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md`](PLAN_APP_AGENTES_RECLAMOS_ENTRADAS.md); César lo confirma o corrige antes de F1. No hay código.
- **App de agentes** publicada en `https://agentes.zaris.com.ar` (color del municipio, instalación desde «Mi perfil»); el vecino instala la suya desde su portal. Detalle en `zaris-agentes/ESTADO.md`.

> ### 📣 Para quien retome la PWA `zaris-vecinos` (Roy inactivo por ahora — César 2026-09-20)
> La PWA ya consume todo lo que el backend entregó (desde el 2026-09-26). Falta solo backend NUEVO: `GET /publico/noticias`, URLs de redes en `identidad-municipio` (secciones ocultas mientras tanto), emergencias en `mi-resumen` y la baja de cuenta. Contrato en [`docs/contrato_api_publica.md`](docs/contrato_api_publica.md).

---

## 🟠 Pendientes (backoffice / backend)

**Decisiones de negocio pendientes (César)**
- 🔴 **Prueba de cierre de F4+F5 — lo que queda** (invitación desde la ficha, contorno, mapa de la PWA y el arreglo de los cruces entre municipios ya están en prod: ver Hecho reciente).
  1. **El resto de la prueba de cierre con César** (pregunta 1, con el orden y quién hace cada paso).
  - 🟢 **Drift menor de FK entre local y prod:** unas 30 FK (agenda, eventos, ocupaciones, reservas, `conflictos_log`, `municipios`) difieren solo en la acción al borrar (en prod sin `ON DELETE`). No afecta al clonador; alinear cuando se toquen esas tablas. Diff con el script de la sesión del 2026-10-30 (comparar `pg_get_constraintdef` de las dos bases).
  - **Sin verificar en prod:** `08babf7` (el geocoding sin respaldo de Vicente López) no deja una marca pública; Railway sirve commits posteriores con marca, así que debería estar, pero el comportamiento no se probó.
- 🟢 **Contorno — 9 menores de la revisión final (2026-10-28), ninguno rompe:** lista en [`PLAN_CONTORNO_MUNICIPIO.md`](PLAN_CONTORNO_MUNICIPIO.md) → «Menores diferidos» (el más visible: la fecha del origen en UTC).
- 🟡 **Botón de pánico de la PWA:** sin probar con el vecino de prueba (dispara una alerta REAL al COM). Las pruebas de vecino y funcionario están hechas (2026-10-12 y 2026-10-23).
- 🟢 **Alta — huecos menores (revisión 2026-10-10):** la clave temporal del funcionario no vence si nunca la usa; la app de agentes no tiene «olvidé mi contraseña» (se recupera desde el login del backoffice).
- 🟠 **Atención — residuos del plan (§4):** "ocupación vs disponibilidad efectiva" en el BI de atención · etapa 2 de HC (vista admin de `historia_clinica_acceso`, break-the-glass, ficha ampliada) · walk-in de Guardia sin evento de Emergencias.
- 🟠 **Trámites — residuo:** los 4 tipos sin circuito (exención de tasas, permiso de espacio público, arbolado urbano, inscripción profesional) tienen la gestión asignada por criterio de Claude, cambiable desde el builder.
- 🟠 **Config/UX — reunión 2026-07-06** (ClickUp, lista CONFIGURACION y UX): **IT-01** (ver En curso) · **IT-08** botón SOS de la PWA · **IT-07** accesibilidad móvil (PWA) · **IT-09** módulo de Obras (backlog sin alcance).
- 🟢 **Baja de cuenta del vecino:** sin endpoint ni definición; obligatoria si la app va a las stores.
- 🟠 **IT-01 — menores diferidos de las revisiones finales (F1+F2, F3, F3b, F4+F5):** lista en [`PLAN_MULTI_MUNICIPIO.md`](PLAN_MULTI_MUNICIPIO.md) → «Menores diferidos». Ninguno afecta a San Andrés solo.
- 🟢 **`smoke_publico_turnos.py` en rojo por datos locales:** el vecino de prueba ya tiene turnos en los días hábiles siguientes y el 6.º intento choca con el límite de 5 reservas por minuto. No es del código: limpiar esos turnos o empezar más adelante.
- 🟢 **PWA — `/configuracion` no maneja el 401** con un token vencido (se queda en la página; sin bucle). Repo `zaris-vecinos`.
- 🟠 **Encuestas — pedido de contacto en una encuesta de trámite** (`encuestas_service.py`, `registrar_respuesta`, paso 5): la referencia solo distingue reclamo, turno y evento, así que el aviso al área diría «Reserva de evento #None». Sumar la rama de `id_tramite`. Verificado en el código el 2026-10-30.
- 🟢 **Encuestas → Resumen:** la pantalla filtra solo por fechas; el backend ya acepta circuito (`tipo`) y área. La «Satisfacción por área» cuenta solo reclamos.
- 🟢 **Documentación desactualizada** (relevada el 2026-10-30 para el material de venta): `docs/flujos_operativos_zge.md` (la OT nace «En gestión», los turnos tienen 5 estados, el ciclo de los eventos) y las skills `modulo-encuestas`, `modulo-permisos` y `modulo-usuarios`; revisarlas contra el código al tocar cada módulo. La de `modulo-bi` ya se corrigió.
- 🟢 **Textos de la PWA que prometen más de lo que hace** (trámites, notificaciones, noticias): detalle en `zaris-vecinos/ESTADO.md`.

**Infra / operativo**
- 🟡 **Barrido visual de modo oscuro** en los módulos React restantes: **POSPUESTO por César 2026-09-20**. Sumar el mapa del inicio: tras los cambios del 2026-10-19 no se revisó en oscuro, y el contorno pizarra de los reclamos casi no se ve sobre el tile oscuro.

**Decisiones cerradas — NO re-proponer**
- **Ayudas: una sola página de base de conocimiento con preguntas, no manuales por módulo** (César, 2026-10-22). No se crean ni actualizan `docs/manual_*.html` mientras tanto (CLAUDE.md §36). Diseño pendiente (pregunta 5).
- **Multi-municipio: UNA base para todos con `id_municipio`** (César, 2026-10-23; decisiones de cada fase en los `PLAN_MULTI_MUNICIPIO*.md`). **Documentos de identidad por país: tema reservado**, lo trae César.
- **Orden por columnas: quedan afuera** las colas operativas, las tablas con orden propio y la configuración (César, 2026-10-22; lista en CLAUDE.md §23).
- **São Paulo DESCARTADO** (2026-09-26, CLAUDE.md §9) · «la ubicación» de Buscar actualizaciones (PWA) innecesaria · no se rotan `DISPATCHER_TOKEN` ni las claves push · el vecino no cambia su email desde la app · los reclamos **no se agendan**.
- Purgas del historial git HECHAS el 2026-09-20 y el 2026-10-21 (mapas en `docs/commit-map-purga-*.txt`). Roy tiene que re-clonar.
- **Cuentas de administrador sin segundo factor:** la de Roy se habilita cuando César lo indique (no preguntar); la otra cuenta de administrador de César (id 1) queda sin habilitar (César, 2026-10-26).
- **Asignación automática revisada el 2026-10-30: sin cambios** (César). Desde el 23/10, 88 OT asignadas solas en 14 gestiones; la rotación reparte bien donde hay dos agentes y donde hay uno solo el volumen es bajo (≤ 7 por semana). Volver a mirarla con un segundo municipio o volumen real.
- **Santa Cruz y Santiago del Estero sin gobiernos locales en Georef: se espera** a que un municipio real de esas provincias lo pida, y se carga con archivo (César, 2026-10-30).
- **Guardia: el motivo de derivación sigue visible en la mesa** para todos los que ven la Guardia (César, 2026-10-26). Lo escribe el COM y sirve para el triage; lo clínico ya pasa por el guard de historia clínica.
- Fase 3 de roles (mig 92) y la auditoría de seguridad 2026-07 (48/48) COMPLETAS.

---

## ✅ Hecho reciente (últimas sesiones)

- **2026-10-30 — Referencias que cruzaban de municipio, arregladas** (`6d1308b`, migs 133/133b en prod; detalle en `HISTORIAL_MIGRACIONES.md`): el modelo y el Municipio de Prueba tenían gestiones y tipos de reclamo colgando de San Andrés (en prod faltaban FK que en local existían). Reapuntados por nombre, FK creadas, el clonador reapunta `id_subarea`/`id_area` sin FK y el alta no se hace si queda un cruce (`contar_cruces`). Smoke alta 304/0; prod con 0 cruces. Sin datos operativos afectados.
- **2026-10-30 — Mapa de la App Vecinos y claves de prueba** (`9d1f8ad` acá, `5b30d1f` en `zaris-vecinos`): `GET /api/v1/publico/encuadre-mapa` (sin token, municipio del `Origin`) devuelve el mismo encuadre que `/geo/encuadre`; el mapa de «Nuevo reclamo» y «Nueva emergencia» de la PWA arranca ahí y no en Vicente López. Solo el recuadro, sin contorno (César). Smoke alta 298/0; en prod, cada dirección devuelve su municipio. **Las claves de las cuentas de prueba de prod se renovaron el 2026-10-30:** cada una tiene clave propia, guardada fuera del repo; pedíselas a César. La clave dev de los seeds y smokes sigue siendo solo local.

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
