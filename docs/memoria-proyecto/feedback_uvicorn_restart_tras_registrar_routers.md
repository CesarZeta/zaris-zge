---
name: uvicorn-restart-tras-registrar-routers
description: "Uvicorn sin --reload sirve código viejo: routers ausentes (404), TABLE_CONFIG viejo (POST 201 pero guarda DEFAULT), o InvalidCachedStatementError tras ALTER TABLE. Matar por PUERTO (Stop-Process por StartTime no mata el uvicorn lanzado vía cmd.exe) y relanzar."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1a59de23-b5dc-4929-a71b-47033fecf69e
---

Síntoma: smoke contra `localhost:8000/<endpoint-nuevo>` devuelve `404 Not Found` aunque el código local lo registre. `Invoke-RestMethod /openapi.json | paths` muestra menos endpoints de los esperados.

**Causa**: uvicorn arrancado sin `--reload` no recarga el módulo Python cuando cambia el archivo. El proceso en memoria sigue con la versión vieja de `app.main`.

**Cómo verificar**:
```powershell
(Invoke-RestMethod -UseBasicParsing http://127.0.0.1:8000/openapi.json).paths.PSObject.Properties.Name.Count
# Si la cuenta no coincide con lo esperado tras tu cambio, el server tiene código viejo.
```

**Fix**: matar uvicorn + relanzar.
```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Process -FilePath "python" `
  -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000" `
  -WorkingDirectory "c:\...\backend" `
  -WindowStyle Hidden `
  -RedirectStandardOutput "_uv.log" -RedirectStandardError "_uv.err.log"
```

**Why**: en sesión 2026-05-13 B1 Agenda, tras registrar 2 routers nuevos en `main.py`, el smoke devolvió 404 en `/agenda/espacios`. Diagnostiqué primero como problema de path, después como problema de import. Verificar `/openapi.json` count me hubiera ahorrado el rodeo.

**How to apply**:
- Tras editar `main.py` o cualquier `routes/*.py`, **siempre** verificar `/openapi.json` antes de smoke.
- Si el count no matchea, restart antes de seguir debuggeando.
- Considerar usar `uvicorn --reload` durante desarrollo cuando se prevé editar múltiples veces; el costo es que se reinicia con cada save y rompe el smoke en vuelo.
- `python -c "from app.main import app; print(len(app.routes))"` cuenta rutas del código actual, NO del server vivo. No confiar en eso para diagnosticar runtime.

**No confundir con**: hot-reload de Vite (web-app frontend) que sí actualiza solo. Uvicorn sin `--reload` no se entera.

**PERO: un `pnpm dev` viejo de otra sesión también sirve código viejo** (2026-06-10): el puerto 5173 ya respondía 200, mi script no relanzó (`if (-not $conn)`), y `/#/emergencias` caía al catch-all porque ese vite había arrancado antes de crear el módulo (HMR no siempre recoge módulos/registros nuevos limpio). Antes de verificar un módulo React nuevo en 5173: chequear `StartTime` del proceso que escucha el puerto; si es anterior a tus cambios, matar por puerto y relanzar — mismo criterio que uvicorn. Y al navegar el shell React: **el router es hash** (`createHashRouter`) — `localhost:5173/emergencias` (pathname) NO matchea la ruta y muestra dashboard en silencio; la URL real es `localhost:5173/#/emergencias`.

**Otros dos síntomas del MISMO problema (uvicorn corriendo con estado viejo), cazados 2026-05-27 con `equipos.tipo_grupo`:**

1. **Cambié `TABLE_CONFIG["equipos"].cols` (en `admin_tablas.py`) para sumar `tipo_grupo`, pero el POST seguía guardando el DEFAULT** en vez del valor enviado. El frontend mandaba `tipo_grupo='trabajo_reclamos'`, `readForm()` lo incluía, el POST devolvía 201 — pero la DB guardaba `mesa_tramites` (el DEFAULT). Causa: el uvicorn vivo tenía la versión vieja de `cols` (sin `tipo_grupo`), entonces el filtro `data = {k:v for k,v if k in allowed}` lo descartaba del INSERT. **Síntoma engañoso: 201 OK + columna con DEFAULT.** No es bug del frontend ni del INSERT — es código viejo en memoria. El GET sí devolvía la columna (la lee `SELECT *`), lo que despista.

2. **Tras un `ALTER TABLE` con uvicorn corriendo → `sqlalchemy.exc.NotSupportedError: InvalidCachedStatementError` ("cached statement plan is invalid due to a database schema change").** asyncpg cacheó el plan del statement viejo. Se auto-recupera en la request siguiente, pero igual conviene reiniciar para evitar el primer fallo. Si agregás una columna a una tabla en uso, reiniciá uvicorn.

**Quirk del kill en Windows (importante):** cuando uvicorn se lanza con `Start-Process cmd.exe /c "...uvicorn..."` (receta para preservar logs), el `Stop-Process` filtrado por `StartTime` **NO mata el uvicorn** (el python real es hijo del cmd, con otro árbol). Matar **por puerto** es lo confiable:
```powershell
$procId = (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue).OwningProcess
if ($procId) { Stop-Process -Id $procId -Force }
```
Verificar SIEMPRE que el puerto quedó libre antes de relanzar, o el relanzado choca con `[Errno 10048]` o (peor) seguís hablando con el viejo.

**Regla operativa ampliada:** tras editar CUALQUIER `.py` del backend (routers, `TABLE_CONFIG`, services) **o** cambiar schema de DB de una tabla en uso → reiniciar uvicorn (matando por puerto) antes de smoke/verificación. El "201 OK pero la columna trae el DEFAULT" es el tell más sutil de código viejo en memoria.

**Variante: cambiar `.env.local` con uvicorn corriendo** → las settings en memoria siguen viejas (`pydantic_settings.BaseSettings` lee el `.env` UNA VEZ al import). Mismo fix (kill+restart). Caso real 2026-05-18: cambié `SMTP_PASS` 3 veces y los smokes seguían con la password vieja — el uvicorn había arrancado 49 min antes. Chequeo rápido: `Get-Process python | Select Id, StartTime` — si `StartTime` es anterior al cambio del `.env`, matar y relanzar. La receta canónica para lanzar detached con `ENV_FILE` (Start-Process no hereda env vars en PS 5.1) está en la skill `win-quirks` (Q17).
