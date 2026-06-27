---
name: feedback-powershell-execution-policy-pnpm
description: "Tool PowerShell falla con UnauthorizedAccess al ejecutar pnpm/npm/npx. Workaround verificado: invocar el binario directo desde Bash (./node_modules/.bin/tsc)."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5c09709a-c98e-47c6-ad6e-b77d0e2b7153
---

La tool PowerShell de Claude Code en esta máquina tiene **execution policy restringido**: `pnpm`, `npm`, `npx` fallan con `UnauthorizedAccess: cannot load pnpm.ps1`.

**Why:** sesión 2026-05-13. Necesitaba correr `pnpm typecheck` desde web-app/. PowerShell explotó con `SecurityError`. Probar el Quirk 11 de CLAUDE.md §32 (`cmd /c "pnpm typecheck"`) compiló pero **no devolvió output útil** (la tool capturó el prompt de cmd pero perdió el stdout del subproceso).

**How to apply:**
- **Preferir Bash** para CLIs Node en este proyecto: `cd web-app && ./node_modules/.bin/tsc -b --noEmit`. Exit code limpio. stdout/stderr capturados.
- El binario `./node_modules/.bin/<cli>` lo crea `pnpm install`. Funciona con todos los CLIs del scaffold (tsc, vite, eslint, etc.).
- Cuando *sí* necesitás PowerShell (env vars de PS, `Start-Process` para detached, cmdlets nativos), seguir usándolo — el bloqueo es específico a invocar `.ps1` shims de pnpm/npm.
- **NO usar el Quirk 11 `cmd /c "pnpm ..."` desde PowerShell** sin verificar que el output llega. En sesión 2026-05-13 el comando salió, pero no devolvió las líneas de error de tsc, generando falsos positivos. Si tenés que pasar por cmd, **redirigir a archivo** (`cmd /c "pnpm typecheck > _tc.log 2>&1"`) y leerlo después.
- Para `pnpm dev` detached (vite server), Quirk 11 con redirección sí funciona — ahí no necesitás el stdout en vivo.

**Comandos verificados en sesión:**
- ✅ Bash + binario directo: `./node_modules/.bin/tsc -b --noEmit; echo "EXIT=$?"` → exit 0.
- ❌ PS + pnpm: `pnpm typecheck` → UnauthorizedAccess.
- ⚠️ PS + cmd /c: `cmd /c "pnpm typecheck"` → corre pero stdout vacío al volver al tool.
