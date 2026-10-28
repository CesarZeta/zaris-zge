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

**Última actualización:** 2026-10-28 (Cesar). **Prueba de cierre de F4+F5, primera parte:** César dio de alta «Municipio de Prueba» (id 6, `PRUE`, `prueba.*`) en prod, entró con segundo factor y probó el tope y el email duplicado. Lo que encontró quedó arreglado y en prod el mismo día (zona de búsqueda validada, asistente que dice qué falta, mapas sin Vicente López). César aprobó tres trabajos para la próxima sesión (pendiente 🔴 de abajo).

---

## ❓ Preguntas abiertas para César — se plantean en la PRIMERA respuesta de la próxima sesión

> Regla de César (2026-10-20): al cerrar se anota todo lo abierto; al arrancar se pregunta primero. Lo sensible (seguridad) tiene el detalle en la memoria privada de Cesar, no acá (este archivo es público).

1. **IT-01 F4+F5 — próximo: los tres trabajos aprobados el 2026-10-28 (pendiente 🔴) y después el resto de la prueba de cierre con César.** Para la prueba, César primero carga el radio `0.1` del municipio de prueba en Configuración → Sistema → «Guardar zona» (en prod el radio sigue vacío: sin él, el buscador de direcciones da 409 y los mapas muestran la Argentina). Recomendación de Claude: arrancar por la invitación (es chica) y el GeoJSON, y retomar la prueba con el contorno ya cargado.
1b. **Catálogo de partidos incompleto (decisión de César):** ahora el municipio ES el partido, pero el catálogo tiene 50 de los 135 partidos de Buenos Aires y entre 1 y 15 en el resto de las provincias. Fuera de Buenos Aires, el segundo nivel es el departamento, que contiene varios municipios y comunas (Córdoba, Santa Fe…), así que «municipio = partido» no vale tal cual. Un municipio real que no esté en el catálogo hoy solo entra como ficticio. Recomendación de Claude: completar el catálogo desde Georef (datos.gob.ar) y definir para las provincias con departamentos si se elige el municipio o el departamento.
1c. **Vercel:** César activa el 2FA de su cuenta de Vercel; después Claude quita `agentes.` y `vecinos.` de los proyectos viejos y los pausa (decidido el 2026-10-27).
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
- 🔴 **Prueba de cierre de F4+F5 (2026-10-28) — lo que queda.** Arreglado y en prod el mismo día (`99c3f2f`, `6b6aabc`, `08babf7`): zona de búsqueda validada (API 422 + pantalla que acepta pegar «lat, lon»), aviso del alta corregido, «qué falta» en el asistente, resumen del subdominio en el último paso, botones deshabilitados que se ven deshabilitados, y los tres mapas del backoffice arrancan en contorno → zona → Argentina (`GET /geo/encuadre`), sin ningún Vicente López en el código. Verificados en la prueba: entrar por `prueba.zge`, el tope (409) y el email duplicado (409). **Aprobado por César el 2026-10-28, a implementar:**
  1. **Invitación desde la ficha, no desde el alta.** El alta deja de mandarla. La ficha tiene el botón «Enviar invitación», habilitado recién cuando «Verificar» da las tres direcciones en verde. Una vez enviada, el botón muestra la fecha y hora del envío y su título pasa a «Reintentar envío» (persistir la fecha del último envío; hoy `usuario_invitacion` tiene la fila, ver si alcanza). Quitar las notas de «reenviala desde la ficha» del asistente.
  2. **Circuito del contorno en GeoJSON.** Diseñarlo (brainstorming primero): subir el archivo en el alta, la ficha y Configuración; validar Polygon/MultiPolygon y coordenadas razonables; previsualizar sobre el mapa; guardar en `geo_limite_geojson` y derivar la zona de búsqueda (`geo_bbox_*`) del contorno. Además, César pidió: **un GeoJSON de prueba** para cargar en el municipio de prueba (zona de Pergamino, centro −33.695, −60.634) y **un instructivo para el usuario** que tenga que crearlo (cómo dibujarlo, por ejemplo con geojson.io, y exportarlo). El instructivo va a la ayuda del producto, no a `docs/manual_*` (CLAUDE §36).
  3. **App del vecino (`zaris-vecinos`):** su `MapaPicker` todavía tiene Vicente López fijo. Hacer una versión pública de `/geo/encuadre` (municipio de origen, `municipio_de_origen`) y que la PWA arranque en contorno → zona → país, igual que el backoffice.
  - **Sin verificar en prod:** `08babf7` (el geocoding sin respaldo de Vicente López) no deja una marca pública; Railway sirve el commit siguiente con marca (`6b6aabc`), así que debería estar, pero no se comprobó el comportamiento.
- 🟡 **Botón de pánico de la PWA:** sin probar con el vecino de prueba (dispara una alerta REAL al COM). Las pruebas de vecino y funcionario están hechas (2026-10-12 y 2026-10-23).
- 🟢 **Alta — huecos menores (revisión 2026-10-10):** la clave temporal del funcionario no vence si nunca la usa; la app de agentes no tiene «olvidé mi contraseña» (se recupera desde el login del backoffice).
- 🟠 **Atención — residuos del plan (§4):** "ocupación vs disponibilidad efectiva" en el BI de atención · etapa 2 de HC (vista admin de `historia_clinica_acceso`, break-the-glass, ficha ampliada) · walk-in de Guardia sin evento de Emergencias.
- 🟠 **Trámites — residuo:** los 4 tipos sin circuito (exención de tasas, permiso de espacio público, arbolado urbano, inscripción profesional) tienen la gestión asignada por criterio de Claude, cambiable desde el builder.
- 🟠 **Config/UX — reunión 2026-07-06** (ClickUp, lista CONFIGURACION y UX): **IT-01** (ver En curso) · **IT-08** botón SOS de la PWA · **IT-07** accesibilidad móvil (PWA) · **IT-09** módulo de Obras (backlog sin alcance).
- 🟢 **Baja de cuenta del vecino:** sin endpoint ni definición; obligatoria si la app va a las stores.
- 🟠 **IT-01 — menores diferidos de las revisiones finales (F1+F2, F3, F3b, F4+F5):** lista en [`PLAN_MULTI_MUNICIPIO.md`](PLAN_MULTI_MUNICIPIO.md) → «Menores diferidos». Ninguno afecta a San Andrés solo.
- 🟢 **`smoke_publico_turnos.py` en rojo por datos locales:** el vecino de prueba ya tiene turnos en los días hábiles siguientes y el 6.º intento choca con el límite de 5 reservas por minuto. No es del código: limpiar esos turnos o empezar más adelante.
- 🟢 **PWA — `/configuracion` no maneja el 401** con un token vencido (se queda en la página; sin bucle). Repo `zaris-vecinos`.

**Infra / operativo**
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

- **2026-10-28 — Prueba de cierre de F4+F5 (primera parte) y arreglos en prod** (`99c3f2f`, `6b6aabc`, `08babf7`): zona de búsqueda validada en la API (422) y editada junta en Configuración → Sistema con «Guardar zona»; asistente de alta con «Para seguir falta: …» y resumen del subdominio; botones deshabilitados visibles en toda la suite; `GET /geo/encuadre` y los tres mapas del backoffice en contorno → zona → Argentina; sin Vicente López como respaldo del geocoding. Smokes: alta 286/0, super administrador 121/0, municipio por request 46/0.
- **2026-10-27 (3ª sesión) — IT-01 F4+F5, corte B en prod:** migs 130-131, bucket `exportaciones`, merge de los tres repos, cron «Municipios mantenimiento», «Modelo ZARIS» (id 5), dominios `prueba.*`; vaciado bloqueado para San Andrés, clonador sin filas excluidas ni de baja, asistente con partido, zona horaria y código de 4 letras.

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
