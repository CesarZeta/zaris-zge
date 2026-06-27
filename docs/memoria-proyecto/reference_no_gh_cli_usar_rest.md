---
name: no-gh-cli-usar-rest
description: "GitHub CLI (`gh`) NO está instalado en este entorno Windows. Para listar workflow runs / PRs / releases usar Invoke-RestMethod contra api.github.com directo. No volver a probar `gh` primero."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 730ba002-bb4e-4ffc-a6c4-7067ae9362ab
---

Verificado sesión 2026-05-14: `gh run list ...` devolvió `command not found` tanto en Bash como en PowerShell. **El binario no está en PATH y no vale la pena reintentar**.

**Patrón verificado para listar workflows:**
```powershell
Invoke-RestMethod -Uri "https://api.github.com/repos/CesarZeta/zaris-zge/actions/runs?per_page=5" -TimeoutSec 10 |
  Select-Object -ExpandProperty workflow_runs |
  ForEach-Object {
    "$($_.created_at) | $($_.name) | $($_.status) | $($_.conclusion) | $($_.head_sha.Substring(0,7))"
  }
```

Devuelve directo lo mismo que `gh run list`. No requiere auth para repos públicos. Para repos privados, agregar header `Authorization: token <PAT>` y env var `$env:GITHUB_TOKEN`.

**Endpoints útiles:**
- Runs: `/repos/{owner}/{repo}/actions/runs?per_page=N`
- PRs: `/repos/{owner}/{repo}/pulls?state=open`
- Issues: `/repos/{owner}/{repo}/issues?state=open`
- Releases: `/repos/{owner}/{repo}/releases/latest`

Si una nueva sesión necesita `gh` y este memo está vigente, ir directo a REST. Si decidís instalar `gh` con `winget install GitHub.cli`, actualizá este memo después.
