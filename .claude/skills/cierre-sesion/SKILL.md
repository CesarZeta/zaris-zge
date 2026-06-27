---
name: cierre-sesion
description: Rutina de cierre de sesión de trabajo en ZARIS (modo colaboración con Roy). Corre el chequeo de estado del proyecto (repo + deploys + Actions), verifica el sync con el equipo (commits sin pushear, main local detrás del remoto si Roy pusheó, working tree sucio), resume qué se hizo en la sesión y qué quedó pendiente, y actualiza la bitácora de sesión en memoria para que la próxima arranque al día. Invocar cuando el usuario dice "cerremos la sesión", "cierre de sesión", "dejemos esto cerrado", "antes de terminar", o al final de una jornada de trabajo.
---

# Cierre de sesión ZARIS (modo colaboración)

Rutina de fin de jornada. Trabajamos **en colaboración** (Cesar `CesarZeta` + Roy `roymanrafael`), así que el cierre prioriza **dejar el repo sincronizado y la bitácora al día** para que cualquiera retome sin sorpresas.

> No declarar nada "cerrado/sincronizado" sin verificarlo con git/gh/curl. Familia de `feedback_verificar_siempre_antes_de_opinar`.

Ejecutar los 4 pasos en orden y reportar al final.

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

## 4. Actualizar la bitácora

Volcar el resumen del paso 3 a la memoria **`project_estado_sesion_y_pendientes`** (el índice `MEMORY.md` ya la lista como bitácora — "LEER al preguntar por pendientes"):

- Leer el archivo actual en `…/memory/project_estado_sesion_y_pendientes.md`.
- Actualizar el cuerpo con el estado de cierre de HOY (reemplazar lo viejo si ya no aplica; no acumular infinito — mantenerlo como foto del estado actual, no log histórico).
- Gestión de memorias **autorizada sin pedir permiso** (CLAUDE.md, header de gestión autónoma): puedo editar/reescribir y ajustar `MEMORY.md`, informando qué cambié.
- Si en la sesión surgió un patrón reutilizable (no un incidente puntual), considerar una memoria `feedback`/`reference` propia además de la bitácora.

## Reporte final al usuario

Cerrar con un bloque compacto:
- ✅/⚠️ Estado: repo, deploys, Actions.
- 🔄 Sync: pusheado / pendiente / si hay que traer commits de Roy.
- 📝 Resumen de lo hecho + pendientes.
- 🗂️ Bitácora actualizada (sí/no).

Si algo quedó sin resolver (un push que el usuario no autorizó, un workflow en rojo), **dejarlo explícito como pendiente para la próxima** — no maquillarlo como cerrado.
