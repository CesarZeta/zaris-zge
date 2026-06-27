---
name: cierre-sesion
description: Rutina de cierre de sesión de trabajo en ZARIS (modo colaboración con Roy). Corre el chequeo de estado del proyecto (repo + deploys + Actions), verifica el sync con el equipo (commits sin pushear, main local detrás del remoto si Roy pusheó, working tree sucio), resume qué se hizo en la sesión y qué quedó pendiente, hace una reflexión de hallazgos/bugs/correcciones y dónde anotarlos (CLAUDE.md, skills, memorias, verificaciones pendientes), y actualiza la bitácora de sesión en memoria para que la próxima arranque al día. Invocar cuando el usuario dice "cerremos la sesión", "cierre de sesión", "dejemos esto cerrado", "antes de terminar", o al final de una jornada de trabajo.
---

# Cierre de sesión ZARIS (modo colaboración)

Rutina de fin de jornada. Trabajamos **en colaboración** (Cesar `CesarZeta` + Roy `roymanrafael`), así que el cierre prioriza **dejar el repo sincronizado y la bitácora al día** para que cualquiera retome sin sorpresas.

> No declarar nada "cerrado/sincronizado" sin verificarlo con git/gh/curl. Familia de `feedback_verificar_siempre_antes_de_opinar`.

> **La corre cualquier colaborador, pero algunos chequeos exigen rol `admin`.** Cesar (`CesarZeta`) es `admin`; Roy (`roymanrafael`) es `write`. Si el paso 1 reusa `estado-proyecto`, los pasos admin-only (invitaciones pendientes, alta de colaboradores) le darán error/vacío a un `write` — es el rol, no un bug; reportarlos como "requiere admin (tarea de Cesar)". El resto del cierre (sync de git, resumen, bitácora, reflexión) funciona igual para cualquiera.

Ejecutar los 5 pasos en orden y reportar al final.

## 1. Chequeo de estado

Correr el reporte de la skill **`estado-proyecto`** (repo + colaboradores + GH Pages + Railway + Vercel + Actions). Si esa skill está disponible, reusar sus comandos; lo mínimo imprescindible:

```bash
echo "=== Health prod ==="; curl -s -m 10 https://zaris-api-production-bf0b.up.railway.app/api/health
echo; echo "=== Últimos runs de Actions ==="
gh api "repos/CesarZeta/zaris-zge/actions/runs?per_page=6" \
  --jq '.workflow_runs[] | "\(.name): \(.status)/\(.conclusion) @ \(.head_sha[0:7])"'
```

⚠️ si un workflow (deploy o los 3 crons) cerró en `failure`, o si el health no responde.

## 2. Sync con el equipo (CRÍTICO en colaboración)

```bash
cd /c/Users/Cesar/Documents/ZARIS/Desarrollo/ZGE
git fetch origin --quiet
echo "=== Posición vs origin ==="; git status -sb | head -1
echo "=== Commits LOCALES sin pushear ==="; git log --oneline origin/main..HEAD
echo "=== Commits REMOTOS sin traer (¿Roy pusheó?) ==="; git log --oneline HEAD..origin/main
echo "=== Working tree ==="; git status --porcelain
```

Interpretar y avisar:
- **Commits locales sin pushear** → preguntar al usuario si pushear (push directo a main es OK con todo en verde — `feedback_push_directo_a_main`; si hay un error/intervención pendiente, PARAR y avisar).
- **main local detrás del remoto** (Roy pusheó) → avisar; ofrecer `git pull --rebase`. Ojo con el bot de CI que commitea `dist/` (`win-quirks` Q18).
- **Working tree sucio** → listar los archivos cambiados; decidir con el usuario si commitear, stashear o descartar. NUNCA `git checkout` masivo sin confirmar (`feedback_git_checkout_destruye_ediciones_sesion`).
- ⚠️ Reportes de QA con PoCs no se commitean (§40); confirmar que ningún `.md`/`.html` de QA con payloads activos entró al stage.

## 3. Resumen de la sesión

Redactar un resumen breve (para que Roy o el propio usuario retomen):
- **Qué se hizo:** features/fixes tocados, módulos afectados.
- **Qué se pusheó / qué falta pushear.**
- **Qué quedó pendiente / a medias:** con suficiente contexto para retomar (archivo, función, próximo paso).
- **Decisiones tomadas** que no son obvias del código.

Convertir fechas relativas a absolutas (hoy es la fecha de `currentDate`).

## 4. Actualizar el hilo conductor común (`ESTADO.md`) — ANTES que la memoria privada

> **El orden importa (CLAUDE.md §45):** primero el `ESTADO.md` versionado (lo ve el otro colaborador), después la memoria privada (solo la veo yo). Un pendiente que solo quede en la memoria privada el otro NO lo ve → desincronización.

**4.A — `ESTADO.md` del/los repo(s) afectado(s) (FUENTE DE VERDAD COMPARTIDA):**

- Abrir `ESTADO.md` en la raíz del repo (`ZGE/ESTADO.md`; si la sesión tocó la PWA, **también** `zaris-vecinos/ESTADO.md`).
- Actualizar las secciones **En curso / Pendientes / Hecho reciente** con el estado de cierre de HOY:
  - Lo terminado y pusheado → mover a "Hecho reciente" (podar lo viejo de ahí, máx ~10 líneas).
  - Lo nuevo que quedó abierto → agregar a "Pendientes" con contexto para retomar (archivo, función, próximo paso).
  - Lo que se está trabajando a medias → "En curso".
- Bumpear "Última actualización" (fecha absoluta + quién).
- **Roadmaps detallados** (Etapas de la PWA, fases de un módulo) van a `PLAN_*.md`, no al `ESTADO.md` — el `ESTADO.md` los apunta.
- Estos cambios se **commitean y pushean** (son del repo, no de la memoria) — ver paso 2 / reporte final.

**4.B — Memoria privada (complemento personal, solo Cesar):**

Volcar el mismo resumen a la memoria **`project_estado_sesion_y_pendientes`** (índice `MEMORY.md`). Es el detalle ampliado/personal — NO reemplaza al `ESTADO.md`, lo complementa.

- Leer y actualizar `…/memory/project_estado_sesion_y_pendientes.md` (foto del estado actual, no log infinito).
- Gestión de memorias **autorizada sin pedir permiso** (CLAUDE.md, header de gestión autónoma): editar/reescribir y ajustar `MEMORY.md`, informando qué cambié.
- Si surgió un patrón reutilizable (no un incidente puntual), considerar una memoria `feedback`/`reference` propia.
- **Roy (`write`) corre esta skill sin memoria privada de Cesar** — para él el paso 4.B no aplica (su Claude Code tiene su propia memoria); su hilo conductor con el equipo es el `ESTADO.md` del 4.A. Por eso 4.A es obligatorio y 4.B es opcional según quién cierra.

## 5. Reflexión de cierre — hallazgos y aprendizajes

Antes de cerrar, repasar la sesión y plantearse explícitamente:

> Vamos a cerrar la sesión. ¿Encontraste inconsistencias, bugs, debiste corregir
> algo? ¿Tomaste nota de hallazgos para no repetir el error y adoptar nuevos
> criterios? ¿Cosas para anotar en `CLAUDE.md`, en skills o en guías de
> referencia? ¿Verificaciones pendientes?

Para cada hallazgo, decidir **dónde** vive (no dejarlo solo en la cabeza):
- **Regla mandatoria del proyecto** (qué hacer siempre) → `CLAUDE.md` (sección
  correspondiente; respetar la numeración `§N`, no renumerar).
- **Patrón/aprendizaje reutilizable o corrección de criterio** → memoria
  `feedback`/`reference` (+ línea en `MEMORY.md`). Gestión de memorias autorizada
  sin pedir permiso (informar qué se creó/editó).
- **Receta operativa de una tarea** → la skill correspondiente.
- **Verificación pendiente** (algo que no se pudo confirmar hoy) → anotarla en la
  bitácora del paso 4 como pendiente explícito, no como hecho.

Si no hubo hallazgos, decirlo — pero recién después de pensarlo, no por defecto.

## Reporte final al usuario

Cerrar con un bloque compacto:
- ✅/⚠️ Estado: repo, deploys, Actions.
- 🔄 Sync: pusheado / pendiente / si hay que traer commits de Roy.
- 📝 Resumen de lo hecho + pendientes.
- 🧵 `ESTADO.md` actualizado y pusheado (cuál/es repos) — el hilo conductor común.
- 🗂️ Bitácora privada actualizada (sí/no — solo Cesar).

Si algo quedó sin resolver (un push que el usuario no autorizó, un workflow en rojo), **dejarlo explícito como pendiente para la próxima** — no maquillarlo como cerrado.
