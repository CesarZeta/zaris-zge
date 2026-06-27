---
name: Shell mixing — usar PowerShell para sintaxis PS, no Bash
description: Cuando un comando usa $env:VAR, Set-Location, &call-operator o cualquier sintaxis PowerShell, invocarlo por la tool PowerShell. Bash no expande $env:VAR y el comando "arranca" pero sin las vars.
type: feedback
---
Si un comando usa sintaxis PowerShell (`$env:VAR=...`, `Set-Location`, `& "exe"`, `;` como separador con scope PS), invocarlo por la tool **PowerShell**, NO por Bash.

**Why:** En esta sesión arranqué `uvicorn` con `cd backend && $env:ENV_FILE=".env.local"; uvicorn ...` por la tool Bash. Bash interpretó `$env:ENV_FILE=.env.local` como un comando inválido (`/usr/bin/bash: line 1: :ENV_FILE=.env.local: command not found`) y siguió igual con `uvicorn`, que arrancó **sin** leer `.env.local`. El backend respondió 200 pero apuntaba a la DB equivocada. Tuve que matarlo con TaskStop y reiniciarlo.

**How to apply:**
- Comandos del proyecto ZARIS que requieren PowerShell: `cd backend; $env:ENV_FILE=".env.local"; uvicorn ...`, cualquier `python` que necesite `$env:PYTHONIOENCODING="utf-8"`, scripts `.ps1`.
- Si dudas, mirar CLAUDE.md §6 y §7 — los snippets están escritos en PowerShell y deben ejecutarse así.
- En la tool Bash sí se puede correr `python`, `git`, `curl`, `npm` sin shell-specific syntax. La regla aplica cuando hay `$env:`, `Set-Location`, `&` (call operator), `Get-Content`, etc.
- Como fallback en Bash: `ENV_FILE=.env.local uvicorn ...` (POSIX). Pero si la receta documentada usa PS, mejor respetarla.
