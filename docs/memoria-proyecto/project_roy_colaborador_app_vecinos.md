---
name: project_roy_colaborador_app_vecinos
description: Roy se incorporó como colaborador trabajando la App Vecinos (PWA) y luego la del funcionario.
metadata: 
  node_type: memory
  type: project
  originSessionId: 90464e03-c2cf-4437-8948-7f195cbd5d28
---

**Roy** (no "Arroy") es un desarrollador que se incorporó al proyecto ZARIS (decisión del usuario 2026-06-27) para trabajar **por módulos en paralelo**. Su módulo es la **App Vecinos** (PWA del ciudadano, repo separado `CesarZeta/zaris-vecinos`) y luego seguirá con la **app del funcionario**.

Es distinto del "Roy/Royman" que aparece en CLAUDE.md/HISTORIAL como autor de informes de QA externos — acá Roy es **desarrollador colaborador**, no QA.

**Acceso acordado:** completo a producción (Railway + Supabase + Vercel, con su propia cuenta) + colaborador (rol Write) en los repos `zaris-vecinos` y `zaris-zge`, con workflow de ramas/PRs a `main`. Las invitaciones las hace el usuario manualmente (son sus cuentas).

**Preparado para la colaboración (commit `226eaeb` en main, 2026-06-27):**
- `backend/.env.example` completado (24 vars, solo placeholders)
- `ONBOARDING.md` — arranque local
- `CONTRIBUTING.md` — workflow de ramas + coordinación entre los dos repos
- `docs/contrato_api_publica.md` — los 13 routers `/api/v1/publico/*` que consume la PWA
- README de `zaris-vecinos` con sección "Primeros pasos (colaborador nuevo)" + checklist de primer commit (commit `61622f0` en ese repo, 2026-06-27 j2)

**ONBOARDING COMPLETO — Roy puede arrancar (verificado 2026-06-27 j2):** colaborador `write` en `zaris-zge` Y `zaris-vecinos` (este último **invitación ya aceptada**, no hay pendiente). El dump de la DB local **ya se lo pasó el usuario** (era el último bloqueante). Accesos a prod (Railway/Supabase/Vercel) acordados con su cuenta. No queda nada del lado del repo para habilitarlo.

**Herramientas de colaboración que Roy hereda (verificado 2026-06-27 j2):** Roy **usa Claude Code** apuntando al repo. Las skills `/estado-proyecto` y `/cierre-sesion` están **commiteadas** en `.claude/skills/` de `zaris-zge` (NO ignoradas) → las hereda al clonar/pull y las ve como slash-commands. Requiere `gh` CLI autenticado para los chequeos de GitHub. **Rol y permisos:** Roy es `write`, NO `admin` — los pasos admin-only de esas skills (ver invitaciones pendientes, alta/baja de colaboradores con `gh api`) le darán error/vacío; es el rol, no un bug. Ambas skills ya documentan esos pasos como "requiere admin (tarea de Cesar)" (commit `ef38f2f`, 2026-06-27 j2). Lo que SÍ puede correr con `write`: deploys/salud, Actions, lista de colaboradores, sync de git, y todo el flujo de cierre/bitácora.

**Recordatorios pendientes para el usuario:** rotar todos los secretos de prod (Supabase service_role, RESEND_API_KEY, DISPATCHER_TOKEN, VAPID_PRIVATE_KEY, SECRET_KEY) el día que Roy deje el proyecto; cubrirlo con acuerdo de confidencialidad por Ley 25.326 (acceso a datos personales reales de municipios).

La PWA consume el backend de `zaris-zge` vía `/api/v1/publico/*` — cambios de contrato son backend y se mergean primero. Ver [[project_portal_ciudadano_pwa]].
