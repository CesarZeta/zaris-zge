---
name: estado-proyecto
description: Reporte de estado del proyecto ZARIS en colaboración — revisa memorias para verificar pendientes y CLAUDE.md para los lineamientos mandatorios, luego colaboradores del repo GitHub e invitaciones pendientes, último deploy de GH Pages, salud del API en Railway (CR=Centro de cómputo / backend), deploy de la PWA en Vercel, y estado de los workflows de GitHub Actions (deploy + 3 crons). Incluye el procedimiento de onboarding de un colaborador nuevo (GitHub automatizado por gh CLI + pasos manuales de Railway y Vercel). Invocar cuando el usuario pide "estado del proyecto/repo", "cómo está todo", "quién tiene acceso", o quiere agregar un colaborador.
---

# Estado del proyecto ZARIS (modo colaboración)

> Trabajamos **en colaboración** (al menos Cesar `CesarZeta` + Roy `roymanrafael`). Antes de afirmar nada sobre el estado, **verificar contra la fuente real** (gh API, curl, git) — nunca reportar de memoria. Familia de `feedback_verificar_siempre_antes_de_opinar`.

> **Esta skill la corre cualquier colaborador, pero algunos pasos exigen rol `admin` del repo.** Cesar (`CesarZeta`) es `admin`; Roy (`roymanrafael`) es `write`. Pasos que **requieren admin** y le darán error/vacío a un colaborador `write` — **no es un bug, es el rol**: ver invitaciones pendientes (`gh api .../invitations`), y TODO el bloque "Onboarding de un colaborador nuevo" (alta/baja con `gh api -X PUT/DELETE .../collaborators`). Lo que un `write` SÍ puede correr: salud/deploys (curl), Actions y lista de colaboradores (`gh api .../collaborators`), sync de git. Si un paso admin falla por permisos, reportarlo como "requiere admin (tarea de Cesar)", no como caída del servicio.

Datos fijos del proyecto:
- **Repo:** `CesarZeta/zaris-zge` (público, sirve GH Pages).
- **API prod (Railway):** `https://zaris-api-production-bf0b.up.railway.app` — proyecto `inspiring-empathy`, servicio `zaris-api`, branch `main`, root `/backend`.
- **Shell del producto (GH Pages):** `https://cesarzeta.github.io/zaris-zge/index.html` (dominio propio `https://zge.zaris.com.ar`).
- **PWA App Vecinos (Vercel):** `https://vecinos.zaris.com.ar` — repo SEPARADO `CesarZeta/zaris-vecinos`.

## Contexto del proyecto — antes del estado técnico

Antes de mirar servicios/repo, revisar el estado conceptual del proyecto:

- **Revisar memorias para verificar pendientes.** Leer `MEMORY.md` (índice) y, en
  particular, la bitácora `project_estado_sesion_y_pendientes` — qué quedó a
  medias o sin verificar de la sesión anterior. Surfacear esos pendientes en el
  reporte.
- **Revisar `CLAUDE.md` para verificar lineamientos mandatorios del proyecto.**
  Es el contrato de cómo se trabaja (verificar drift en prod §24, migraciones
  92+ §21, guards de seguridad en backend no solo UI §30, etc.). Si la tarea en
  curso toca alguna de esas áreas, traer la regla aplicable al reporte para no
  violarla.

## Reporte de estado — comandos

Correr esto (Bash tool) y armar el reporte. Todo es de solo lectura.

### 1. GitHub — colaboradores, invitaciones, Actions

```bash
echo "=== Colaboradores ==="
gh api repos/CesarZeta/zaris-zge/collaborators --jq '.[] | "\(.login) -> \(.role_name)"'
echo "=== Invitaciones pendientes ==="
gh api repos/CesarZeta/zaris-zge/invitations --jq '.[] | "\(.invitee.login) -> \(.permissions) (desde \(.created_at))"'
echo "=== Últimos runs de Actions ==="
gh api "repos/CesarZeta/zaris-zge/actions/runs?per_page=8" \
  --jq '.workflow_runs[] | "\(.name): \(.status)/\(.conclusion) — \(.head_branch) @ \(.head_sha[0:7]) (\(.updated_at))"'
```

- Sin `gh` o sin auth → `gh auth status`. Hace falta scope `repo` (alta de colaboradores) y `read:org`.
- **Invitaciones vacías + el usuario YA en colaboradores = acceso activo** (la invitación se consumió o fue auto-aceptada). No es un error.

### 2. GH Pages — qué bundle está publicado

```bash
echo "=== Último deploy de GH Pages ==="
gh api "repos/CesarZeta/zaris-zge/pages/builds/latest" \
  --jq '"\(.status) — commit \(.commit[0:7]) (\(.updated_at))"' 2>/dev/null || echo "Pages API no disponible (revisar Settings→Pages)"
echo "=== Commit servido en el bundle (hash del index del iframe) ==="
curl -s -m 10 "https://zge.zaris.com.ar/web-app/dist/index.html" | grep -o 'index-[a-z0-9]*\.js' | head -1
```

### 3. Railway (CR = backend) — salud y si el commit de main aplicó

> Railway **no expone API de members** desde el CLI/gh — los colaboradores de Railway se gestionan a mano (ver onboarding). Acá solo verificamos **salud y deploy**.

```bash
echo "=== Health prod ==="
curl -s -m 10 https://zaris-api-production-bf0b.up.railway.app/api/health
echo
echo "=== ¿El backend tiene el código nuevo? (path que solo exista en el último commit) ==="
# El health 200 puede ser un deploy VIEJO (§9). Para confirmar que aplicó un push reciente,
# chequear que un path nuevo aparezca en openapi.json:
curl -s -m 15 https://zaris-api-production-bf0b.up.railway.app/openapi.json | grep -o '"/api/v1/[^"]*"' | sort -u | head -20
```

- Health 200 **no** garantiza que el último push aplicó (§9 de CLAUDE.md — el deploy viejo sigue 200). Para confirmar un push backend reciente, chequear un path/feature que **solo exista en ese commit**.
- Railway no autodeploya confiable: si un endpoint nuevo da 404 tras ~5 min, **pedirle al usuario que mire el dashboard Railway** (`inspiring-empathy → zaris-api → Deployments`).

### 4. Vercel (App Vecinos) — deploy de la PWA

La PWA vive en **otro repo** (`CesarZeta/zaris-vecinos`). Verificación liviana por HTTP:

```bash
echo "=== PWA App Vecinos viva ==="
curl -s -o /dev/null -w "%{http_code}\n" -m 10 https://vecinos.zaris.com.ar
```

- Si hay MCP de Vercel conectado, se puede listar deploys con más detalle (`list_deployments`), pero requiere auth del usuario y puede no estar en runs headless.

### 5. Git local — sync con el equipo

```bash
cd /c/Users/Cesar/Documents/ZARIS/Desarrollo/ZGE
git fetch origin --quiet
echo "=== Rama y posición vs origin ==="
git status -sb | head -1
echo "=== Commits locales sin pushear ==="
git log --oneline origin/main..HEAD
echo "=== Commits remotos sin traer (¿Roy pusheó?) ==="
git log --oneline HEAD..origin/main
echo "=== Working tree ==="
git status --porcelain | head -20
```

## Armar el reporte

Reportar al usuario en bloques claros, marcando ✅/⚠️/❌:
- **Repo & accesos:** colaboradores + roles, invitaciones pendientes.
- **Deploys:** GH Pages (commit publicado), Railway (health + si aplicó el último push), Vercel (PWA viva).
- **Actions:** último run de cada workflow (deploy + los 3 crons: encuestas, integridad-cuentas, tramites-mantenimiento). ⚠️ si alguno está en `failure`.
- **Sync:** si hay commits sin pushear, si main local está detrás (Roy pusheó), o working tree sucio.

Solo reportar lo que verificaste. Si un chequeo no se pudo correr, decirlo explícito — no rellenar.

---

## Onboarding de un colaborador nuevo

### GitHub — automatizado (lo hago yo con gh CLI)

Roles válidos para `permission`: `pull` (read), `triage`, `push` (write — **default para un dev**), `maintain`, `admin`.

```bash
# Agregar / invitar:
gh api -X PUT repos/CesarZeta/zaris-zge/collaborators/USUARIO -f permission=push
# Verificar:
gh api repos/CesarZeta/zaris-zge/collaborators --jq '.[] | "\(.login) -> \(.role_name)"'
gh api repos/CesarZeta/zaris-zge/invitations  # pendientes
```

- El usuario es el **handle de GitHub** (ej. `roymanrafael`), no el email.
- Si la respuesta sale vacía y el usuario ya figura en colaboradores → acceso ya activo.
- Quitar un colaborador: `gh api -X DELETE repos/CesarZeta/zaris-zge/collaborators/USUARIO`.

### Railway (CR) — MANUAL (no hay CLI/API de members)

Yo **no puedo** automatizar esto. Indicarle al usuario:
1. `https://railway.app/dashboard` → proyecto **`inspiring-empathy`**.
2. **Settings del proyecto → Members** (o, según el plan, **workspace → Settings → Members**).
3. **Invite** con el **email** de la cuenta Railway del colaborador. Rol **Member** (deploy/ver) o **Admin** (settings/billing).
4. El colaborador acepta el email de invitación.
- Invitar miembros suele requerir **plan pago** (Hobby/Pro).

### Vercel (App Vecinos) — MANUAL

Solo si el colaborador toca la PWA:
1. `https://vercel.com/dashboard` → equipo/proyecto de `zaris-vecinos`.
2. **Settings → Members → Invite** con su email.
3. Además, darle acceso al repo **`CesarZeta/zaris-vecinos`** en GitHub (mismo procedimiento `gh api` pero contra ese repo).

> Roy (`roymanrafael`) ya es colaborador `write` de `zaris-zge` (memoria `project_roy_colaborador_app_vecinos`). Si pide acceso a algo nuevo, chequear primero qué ya tiene.
