---
name: Aprendizajes del proyecto ZARIS
description: Archivo único consolidado con todos los errores cometidos y reglas aprendidas a lo largo del proyecto, organizado por tema. Releer al inicio de cada sesión que toque DB, migraciones, scripts, frontend o deploy.
type: feedback
---
Catálogo permanente de aprendizajes y reglas del proyecto. Organizado por **tema**, no por sesión: si una regla se confirma o evoluciona, se actualiza en su sección, no se agrega una nueva entrada.

**Cuándo actualizar este archivo:**
- Si caigo en un error que ya estaba documentado acá → no agregar entrada nueva, **reforzar la existente** con la fecha de la recaída.
- Si el error es genuinamente nuevo → agregar a la sección temática correspondiente (o crear una nueva sección).
- Si una regla queda obsoleta (porque cambió el código o el workflow) → marcar como `[ARCHIVADO YYYY-MM-DD: motivo]`, no borrar.

---

## A. Datos, migraciones y DB

### A1. Hardcodear IDs entre entornos
**Regla:** nunca usar IDs literales en SQL que va a correr en local y prod. Operar siempre por nombre normalizado, email, código único u otro atributo estable.

**Why:** IDs autoincrementales no son estables entre DBs. Cualquier seed o orden de inserción los cambia. En ZARIS, `id_area=1` es "Salud" en local y "Gobierno" en prod; `id=22` es "Servicios Públicos" en prod e inexistente o distinto en local.

**Recaídas conocidas:**
- 2026-05-09: seed inicial de subáreas con `AREA_GOB=1` hardcoded → todos los tipos de Salud terminaron bajo Gobierno.
- 2026-05-10: migración 26 v1 con `UPDATE reclamos SET id_area=22 WHERE id_area=9` copiado del reporte de un subagent que auditó prod. En local soft-deleteó áreas activas. Casi pierdo la DB intentando revertir (ver C2).

**How to apply:**
- Antes de cualquier `WHERE id = N` literal, verificar que ese ID valga en ambos entornos. Si no estoy 100% seguro, reescribir.
- Patrón seguro: `WHERE LOWER(nombre) LIKE 'gobierno%'` o `WHERE codigo = 'X'`.
- Si una migración debe re-routear FKs entre IDs, hacerlo dinámicamente con un grupo (DO block que detecta canónicos por nombre normalizado). Ver `backend/migrations/26_cleanup_areas_duplicadas.sql` como referencia.

### A2. Migrar VARCHAR a FK requiere sincronizar el catálogo primero
**Regla:** antes de agregar una FK contra una tabla maestro, verificar que los valores actualmente en uso (`SELECT DISTINCT col FROM tabla`) matcheen los nombres del catálogo. Si difieren, sincronizar el catálogo **antes** del UPDATE de FK.

**Why:** migración 22, `reclamos.estado` estaba en v1.2 con tildes (`Sin asignar`, `En gestión`) pero `estado_reclamo` tenía los nombres viejos sin tildes. El UPDATE `id_estado_fk = e.id WHERE r.estado = e.nombre` matcheó solo 7 de 20 reclamos.

**How to apply:**
1. Listar valores distintos en uso de la columna VARCHAR.
2. Comparar contra `nombre` del catálogo.
3. Si hay diferencias: insertar las filas faltantes y/o marcar las viejas como `activo=FALSE`.
4. Recién después correr el UPDATE de la FK.
5. Verificar conteo final: filas con FK NULL debe ser 0 (o el motivo conocido).

### A3. Estado real de prod vs lo que dice CLAUDE.md (o lo que veo en local)
**Regla:** antes de aplicar/re-aplicar cualquier migración o de codear backend que **referencie una columna o tabla**, verificar el estado real en prod con `to_regclass()` + `COUNT(*)` + `information_schema.columns`. No confiar en CLAUDE.md ni en la simetría con local.

**Why:** la doc puede quedar atrás Y local puede tener cambios manuales sin migración. Recaídas:
- 2026-05-09: Migración 22 figuraba como "pendiente en prod" cuando ya estaba aplicada con 1000 activos seedeados. Si confiaba en la doc, hubiera duplicado data.
- 2026-05-10: Asumí que `agentes.es_auditor` existía en prod porque estaba en local. **Falso**: local fue modificado manualmente en sesión vieja sin migración. Pusheé backend `/ot/auditor/me` que referenciaba la columna; en prod habría crasheado. Detectado de casualidad al hacer SELECT desde Supabase para un seed.
- 2026-05-10: Asumí que `agentes` tenía 3 filas en prod porque local las tenía. **Falso**: prod estaba vacío. Mesas Agente y Auditoría en prod habrían estado inútiles silenciosamente.

**How to apply:**
```sql
-- Existencia de tabla y filas
SELECT to_regclass('public.tabla') AS existe,
       (SELECT COUNT(*) FROM tabla WHERE activo) AS filas_activas;

-- Existencia de columnas referenciadas
SELECT column_name FROM information_schema.columns
WHERE table_name='tabla' AND column_name IN ('col1','col2');
```
Hacer esto ANTES de codear el backend que las consulta. Si la columna no existe en prod, crear migración formal incluso si "ya está en local". CLAUDE.md §24 lo formaliza.

### A4. Aplicar migraciones en local Y prod en la misma sesión
**Regla:** toda migración de datos (no solo schema) tiene que correr en local **y** prod antes de cerrar la tarea. Una DB sin sincronizar arruina el próximo debugging.

**Why:** apliqué migración 23 a prod via MCP, seguí la sesión sin replicar en local. Al testear local, los IDs no coincidían y bugs raros aparecieron.

**How to apply:** scripts de seed reciben `DATABASE_URL`; las migraciones SQL las aplico explícitamente en ambos lados (psql local + MCP `apply_migration` para prod) y documento el doble paso en el commit.

### A5. "Fuente de verdad" no se decide sin mirar casos concretos
**Regla:** ante datos inconsistentes entre dos columnas que podrían ser fuente de verdad, **ver ejemplos** antes de elegir. Considerar que ninguna sea fuente de verdad y haya que cruzarlas (ej: la moda, JOIN con tercera tabla).

**Why:** ante 123 filas inconsistentes entre `tipo_reclamo.id_area` y `subarea.id_area`, propuse "usar `subarea.id_area` siempre". Resultó que `subarea.id_area` estaba peor poblado. El usuario pidió migración 23 para arreglarlo.

**How to apply:** `SELECT con JOIN LIMIT 8` para ver casos, mostrarle al usuario, no asumir.

### A6. Tablas hijas inferidas mal son riesgo de pérdida de datos
**Regla:** cualquier `DELETE` o `TRUNCATE` sobre una tabla padre puede encadenar tablas hijas vía CASCADE. Listar las tablas dependientes antes de ejecutar:
```sql
SELECT conrelid::regclass FROM pg_constraint
WHERE confrelid = 'tabla_padre'::regclass AND contype = 'f';
```

### A7. CSVs con placeholders y huérfanos
- **Placeholders:** en `Tablas Iniciales/` (Vicente López), códigos como `cod:A`, `cod:B`, `len ≤ 3` o `^cod:` son repetidos cientos de veces, **no** son identificadores únicos. Tratarlos como vacíos y generar uno sintético basado en otra columna estable.
- **IDs huérfanos:** `tipo_reclamo.csv` referenciaba `id_area_servicio` que no estaban en `subarea.csv`. No descartar silenciosamente — inferir nombres del contexto e insertarlos como entidades nuevas.

### A8. Idempotencia obligatoria en seeds y migraciones
**Regla:** todo seed o migración con UPDATE/DELETE debe poder correr 2+ veces sin duplicar ni romper. Patrón:
1. Snapshot defensivo: `CREATE TABLE IF NOT EXISTS _backup_X_YYYY_MM_DD AS SELECT * FROM X`.
2. Operación condicional: `WHERE activo = TRUE` o `WHERE ... AND NOT EXISTS (subquery)`.
3. La segunda corrida debe encontrar 0 cambios pendientes.

Ver migración 26 (cleanup áreas) como referencia: detecta grupos duplicados, si no hay → no hace nada.

---

## C. Reverts y operaciones destructivas

### C1. Snapshot defensivo SIEMPRE antes de UPDATE/DELETE masivo
**Regla:** antes de ejecutar cualquier `UPDATE`/`DELETE` que afecte > 5 filas, crear snapshot `_backup_<tabla>_<YYYY_MM_DD>` en la primera instrucción de la migración. Sin snapshot, no se aplica.

**How to apply:**
```sql
CREATE TABLE IF NOT EXISTS _backup_<tabla>_2026_05_10 AS
SELECT * FROM <tabla>;
```
Patrón usado en migraciones 23, 24, 26. Permite revert sin point-in-time recovery.

### C2. **TRUNCATE CASCADE — NUNCA para revert**
**Regla:** para revertir un UPDATE, usar `UPDATE tabla SET col = b.col FROM _backup_tabla b WHERE tabla.pk = b.pk;` por columna específica. **Nunca** `TRUNCATE tabla CASCADE` ni `DELETE FROM tabla` con riesgo de cascade.

**Why:** 2026-05-10. Para revertir migración 26 v1 en local, intenté `TRUNCATE area RESTART IDENTITY CASCADE`. El CASCADE iba a truncar 30+ tablas hijas (ciudadanos, reclamos, subareas, tipos, ordenes_trabajo, empresas, etc.). **Solo me salvó** que el here-doc de psql cerró sin `COMMIT` y hubo rollback automático.

**How to apply:**
- Para revertir UPDATE: `UPDATE FROM _backup` por las columnas que cambiaron.
- Para revertir INSERT: `DELETE FROM tabla WHERE pk IN (SELECT pk FROM nueva_data) AND pk NOT IN (SELECT pk FROM _backup)`.
- Antes de ejecutar TRUNCATE/DELETE: confirmar el comando 2 veces, mostrarle al usuario qué tablas se tocan vía `pg_constraint`.

### C3. Confirmar antes de actos destructivos en prod
**Regla** (CLAUDE.md global): nunca correr operaciones destructivas (`DROP`, `TRUNCATE`, `DELETE` masivo, `git push --force`) sin confirmación explícita del usuario.

---

## D. Entornos, encoding, shell

### D1. Encoding cp1252 en Python+PowerShell
**Regla:** antes de correr Python en PowerShell, setear `$env:PYTHONIOENCODING="utf-8"`. Mejor aún: evitar caracteres unicode decorativos en `print()` (usar `->`, `[OK]`, `[FAIL]` en vez de `→`, `✓`, `═`).

**Why:** Python en Windows usa cp1252 para stdout por default; revienta con tildes, emojis, símbolos box-drawing.

### D2. PowerShell → psql con SQL inline
**Regla:** para SQL con tildes/ñ desde PowerShell, usar `psql -f archivo.sql` (no `-c "..."`).

**Why:** PowerShell pasa strings en UTF-16/cp1252, psql espera UTF-8. `-c` literal falla con `secuencia de bytes no válida para codificación UTF8`.

**Alternativas:**
- Bash en vez de PowerShell: `PGCLIENTENCODING=UTF8 psql -c "..."` funciona.
- Si tiene que ser PowerShell + `-c`: usar `-f` con un temp file.

### D3. Lectura de CSVs en Windows
**Regla:** `open(path, encoding="utf-8-sig")` para incluir BOM removal. Sin esto, el primer header del CSV viene con `﻿`.

### D4. Start-Process -Environment no existe en PS 5.1
**Regla:** para levantar un proceso en background desde PowerShell 5.1 con env vars custom, setear `$env:VAR = "valor"` en el shell padre **antes** de `Start-Process`. El subproceso hereda automáticamente. El parámetro `-Environment` solo existe desde PowerShell 7.

**Why:** 2026-05-10. Intenté `Start-Process python -ArgumentList ... -Environment @{ENV_FILE=".env.local"}` para levantar uvicorn local. Falló con "No se encuentra ningún parámetro que coincida con el nombre del parámetro 'Environment'".

**How to apply:**
```powershell
# Bien (PS 5.1 + 7.x):
$env:ENV_FILE = ".env.local"
Start-Process python -ArgumentList "-m","uvicorn","app.main:app","--port","8000" -WorkingDirectory $bd -WindowStyle Hidden
# Mal en PS 5.1:
Start-Process python -ArgumentList ... -Environment @{ENV_FILE=".env.local"}
```
También: `-WorkingDirectory` requiere path absoluto; uno relativo desde un CWD distinto rompe.

---

## E. Backend (FastAPI, SQLAlchemy)

### E1. CORS y headers custom
**Regla:** cuando un endpoint devuelve un header custom (ej. `X-Total-Count`), agregar también `response.headers["Access-Control-Expose-Headers"] = "NombreHeader"`. Si no, navegadores cross-origin lo bloquean.

**Why:** 2026-05-10. Agregué `X-Total-Count` en `/buc/ciudadanos/buscar`, casi me olvido del expose. Sin él, GitHub Pages → Railway no lo lee.

### E2. Modelos SQLAlchemy stubs
**Regla:** toda tabla referenciada por `ForeignKey()` en un modelo debe tener al menos un stub en Python (CLAUDE.md §20). Sin stub, la app crashea al startup con `NoReferencedTableError`.

### E3. Validación al boundary, no internamente
**Regla** (CLAUDE.md global): validar datos solo en boundaries (input de usuario, APIs externas). Trust de framework + código interno. No agregar validaciones defensivas redundantes.

### E4. Vincular tablas por FK (id), no por matching de strings
**Regla:** cuando dos tablas se relacionan, el vínculo se modela con `id_<otra>` + FK formal. Nunca por `LOWER(email) = LOWER(email)` ni matching de nombre/legajo.

**Why:** 2026-05-10. Primer diseño de `/ot/agente/me` matcheaba `agentes.email = usuarios.email`. El usuario me corrigió: "siempre por id". Tuve que crear mig 28 que agregó `agentes.id_usuario` UNIQUE FK. El matching por strings rompe en silencio si un email cambia, si hay duplicados por mayúsculas o si la columna se renombra.

**How to apply:**
- Si dos tablas deben relacionarse y la columna FK no existe, crear migración primero, después codear el backend.
- Backfill por matching de string puede correrse **una vez** como parte de la migración (para poblar la nueva columna), no como lógica permanente.
- Ver `backend/migrations/28_agentes_id_usuario.sql` como referencia.
- Documentado también en `feedback_vincular_por_id.md`.

### E5. JSONB con asyncpg — `::jsonb` shorthand no funciona en prepared statements

**Regla:** en queries ejecutadas con SQLAlchemy `text()` + asyncpg, **nunca** pasar un `dict` Python como parámetro JSONB ni usar el cast `::jsonb` (PostgreSQL shorthand). asyncpg rechaza ambos en prepared statements.

**Patrón correcto:**
```python
# Mal: falla con "dict object has no attribute 'encode'" o "error de sintaxis en «:»"
conn.execute(text("INSERT INTO t (col) VALUES (:v::jsonb)"), {"v": {"k": "v"}})

# Bien: serializar + CAST SQL estándar
conn.execute(
    text("INSERT INTO t (col) VALUES (CAST(:v AS jsonb))"),
    {"v": json.dumps(val) if val is not None else None}
)
```

**Why:** 2026-05-16, seed_tramites.py. El `::jsonb` en `$N::jsonb` es syntax error para asyncpg (prepared stmt, no raw). El `dict` Python sin serializar explota con `AttributeError: 'dict' has no attribute 'encode'`. Documentado también en CLAUDE.md §35 y aplicado en `tramite_campo`, `tramite_transicion`, `tramite_movimiento`.

**Excepción:** el `::jsonb` SÍ funciona en scripts que van por `asyncpg_conn.execute(sql)` directo (raw, no prepared — patrón §5 multi-statement). Solo falla en prepared statements (SQLAlchemy `text()` + bind params).

**How to apply:**
- Al ver columna `JSONB` + `text()` + bind params: serializar con `json.dumps()` + `CAST(:p AS jsonb)`.
- Al ver `::jsonb` en un `text()` con params: reemplazar por `CAST(:p AS jsonb)`.
- NULL es seguro: `CAST(NULL AS jsonb)` funciona; también pasar `None` sin cast (asyncpg infiere NULL para cualquier tipo).

### E7. Defaults de IDs de entorno en schemas Pydantic

**Regla:** ningún schema Pydantic debe tener `Field(<id_numerico>)` como default para campos FK que dependen del entorno (municipio, área, subárea, etc.). Si el campo tiene un default razonable, usar `Field(default=None, ...)` o hacerlo requerido.

**Why:** 2026-05-17. `UsuarioCreate.id_municipio = Field(377)` — el municipio 377 existe en prod pero no en local (local solo tiene id=1). `POST /buc/usuarios` fallaba con 500 en local por FK violation, enmascarado por el bug de passlib que ocurría antes. Al corregir passlib el segundo error afloró. El default de 377 sobrevivió sin detectarse porque passlib explotaba primero.

**How to apply:**
- Al crear un schema con FK a tabla de catálogo, verificar que el default (si existe) sea válido en local Y prod. Si no se puede garantizar, poner `None` o hacer el campo requerido.
- Al ver `Field(<int>)` en un schema para campos `id_municipio`, `id_area`, `id_subarea`, `id_cargo`, etc.: dudar, verificar que ese ID exista en ambos entornos.
- Patrón seguro para municipio: `id_municipio: int = Field(1)` (municipio 1 existe en todos los entornos de ZARIS) o hacerlo opcional `Optional[int] = None`.

### E6. Crash silencioso de uvicorn local tras edits
**Regla:** si uvicorn está corriendo en background y un endpoint deja de responder, **no asumir** que está vivo por el background process. Confirmar con `curl /api/health` o leer las últimas 30 líneas del log.

**Why:** 2026-05-10. Uvicorn local crasheó después de un edit a `reclamos.html` (HTML, no debería triggerear reload). Seguí confiando en que estaba arriba; el login devolvía vacío. Tardé varios minutos en darme cuenta. La causa raíz quedó sin resolver — posiblemente combinación de --reload + crash en otro request.

**How to apply:**
- Después de cualquier batch de edits, antes del próximo curl: `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/health`.
- Si dudo, reiniciar uvicorn explícitamente con TaskStop + relanzar.
- Evitar `--reload` salvo que el ciclo de iteración lo justifique.

---

## F. UI y frontend

### F1. Info visual redundante
**Regla:** antes de agregar un badge/contador/número nuevo, **listar mentalmente** qué info ya está visible en la misma pantalla. Si el dato aparece aunque sea con otro formato cerca, no agregarlo.

**Why:** 2026-05-09. Agregué `4 subáreas` como badge al lado del nombre de un área en el listado, sin notar que el panel inline debajo ya mostraba `SUBÁREAS ASOCIADAS (4)`. Redundancia.

### F2. XSS en resultados de búsqueda dinámica
**Regla** (CLAUDE.md §18): nunca interpolar datos del servidor en `onclick` inline. Usar `data-id` + event delegation, y escapar HTML del texto visible.

### F3. Patrones de UI ya validados (CLAUDE.md §23)
Antes de inventar variantes, revisar los patrones documentados:
- Buscador con autocompletar (≥30 opciones): input + dropdown + endpoint con `?q=`.
- Drill-down jerárquico inline (≤50 padres): mostrar hijos debajo sin botón.
- Modal anidado para alta inline.
- Breadcrumb consistente con `.zaris-breadcrumb` (tokens nuevos, no `--z-*` legacy).

Si no aplica, justificar por qué.

### F4. Shell + iframe + módulos
**Regla** (CLAUDE.md §14): los módulos en `frontend/*.html` se cargan en iframe del shell `index.html`. Detalles ya documentados en §14, no replicar acá.

**Nuevo (2026-05-10):** acceso standalone redirige al shell con `?modulo=<path>`. Cada módulo tiene script en `<head>` que hace `if (window.self === window.top) window.location.replace('../index.html?modulo=...')`. El shell lee `?modulo=` con whitelist y setea `src` del iframe.

---

## G. Workflow y proceso

### G1. Deploy: local primero, push cuando el usuario pide
**Regla:** después de cualquier cambio, primero verificar técnicamente (lint, sanity, smoke test) y dejar todo listo. Push **solo cuando** (a) el usuario lo pide explícitamente, o (b) es operativamente necesario (ej: Railway necesita el código para que el usuario testee online).

**Why:** el usuario prefiere testear online en vez de levantar local. Cada fix técnico → commit + push tras validación propia, sin esperar confirmación adicional para tareas chicas.

**Status:** confirmado en sesiones 2026-05-04, 2026-05-09, 2026-05-10.

### G2. Uso de subagentes — solo si justifica
**Regla:** subagent solo si la tarea tiene **≥3 lookups distintos** o **≥2 archivos a leer** o requiere síntesis multi-fuente. Para ≤3 queries SQL o búsquedas simples, hacer inline.

**Why:** 2026-05-10. Mandé subagent para chequear 2 cosas en prod (tabla + bucket). 90s, 8 tool uses. Una sola query SQL hubiera tomado 5s.

**Excepción válida:** consolidar un reporte largo para no contaminar mi contexto principal (decisiones con muchos datos intermedios).

### G3. Auditorías por subagent valen solo para el entorno auditado
**Regla:** si un subagent audita prod, su reporte **vale solo para prod**. Si la decisión afecta ambos entornos, auditar ambos o diseñar la migración **idempotente por nombre** para que aplique en cualquier entorno.

**Why:** 2026-05-10. Subagent auditó áreas en prod, asumí que aplicaba a local. Falso: local tenía 5 áreas activas con IDs distintos.

### G4. TodoWrite para tareas multi-paso
**Regla:** usar TodoWrite cuando la tarea tiene ≥3 pasos distintos. Marcar `in_progress` exactamente uno a la vez. Completar inmediatamente, no en batch.

### G5. Actualizar la bitácora de pendientes al cierre
**Regla:** antes de cerrar sesión, actualizar `project_estado_sesion_y_pendientes.md` con:
- Qué se hizo (resumido).
- Qué pendientes se cerraron (mover a histórico).
- Qué pendientes nuevos aparecieron.
- Decisiones diferidas que esperan input del usuario.

### G7. Limpiar scripts `_tmp_*.py` antes de cerrar sesión
**Regla:** todo script temporal creado en `backend/_tmp_*.py` debe borrarse antes del commit final. Si necesito un patrón reutilizable, agregarlo como helper permanente o slash command — no dejar el `_tmp_` y olvidarme.

**Why:** 2026-05-10. Creé `_tmp_check_*.py`, `_tmp_seed_*.py`, `_tmp_apply*.py`, `_tmp_link_admin.py`, `_tmp_match_agent.py`, `_tmp_create_jperez.py`, `_tmp_seed_audit.py` durante la sesión. Algunos los borré al cierre, otros casi quedan trackeados. El `git status` los muestra como untracked y son fácil de commitear por accidente con `git add -A`.

**How to apply:**
- Convención: solo crear `_tmp_*.py` para queries de diagnóstico/seed one-shot, no para tareas recurrentes.
- Antes del commit final, correr `git status` y borrar todo `_tmp_*` listado como untracked.
- Si la consulta es algo que voy a repetir en futuras sesiones, agregarlo como skill o helper en `backend/scripts/`.

### G8. Probar el contrato (API) antes de leer código de la capa sospechada
**Regla:** ante un bug reportado, antes de leer código, **probar el contrato** entre las capas con un curl/Invoke-RestMethod o query directa a DB. Si el contrato funciona, el bug está más arriba; si falla, está más abajo. Salta varias horas de lectura en frío.

**Why:** 2026-05-11. BUG-A-001 ("autoservicio se desmarca al reabrir evento"). Empecé leyendo `EventoModal.tsx` y `useEffect`s. Después de 3-4 reads me acordé de probar el endpoint con `Invoke-RestMethod`: backend persistía OK. Eso *descartó* el backend de un solo golpe y me llevó al verdadero bug (`useEffect` con `defaultDate` en deps reseteaba el form). Si arrancaba por ahí, ahorraba todo lo anterior.

**How to apply:**
- Bug en form → `curl POST` con payload conocido + `SELECT` directo en DB para confirmar persistencia. 30 segundos.
- Bug en lectura → `curl GET` y comparar la respuesta con lo que se ve en pantalla.
- Bug en redirect/auth → ya documentado en `feedback_diagnosticar_redirect_login.md` (primer sospechoso: `web-app/src/lib/api.ts`).
- Solo después leer el código de la capa que el contrato implica como culpable.

### G9. Antes de planear un fix, grep para confirmar que el bug existe
**Regla:** ante una OBS reportada por un tester, **antes de poner el fix en el plan**, hacer 1 grep en el código relevante para confirmar que la causa raíz coincide con lo reportado. A veces el "bug" ya está fixeado y la observación viene de un malentendido del tester.

**Why:** 2026-05-11. OBS-D-SUP-01: "búsqueda Mesa Supervisor no es reactiva". La puse en mi todo list para fixear. Cuando finalmente la fui a tocar, grepeé `f-texto.*addEventListener` y encontré que **ya tenía debounce 150ms on input** desde antes (`ot_supervisor.html:703`). El tester probablemente confundió "Refrescar" (refetch) con "filtrar" (que ya era reactivo). Si grepeaba primero, no la metía en la lista.

**How to apply:**
- Antes de planear N fixes, dedicar 30s a grepear cada uno.
- Si el código ya tiene el comportamiento esperado, marcar como "no-bug, verificado" sin tocar nada.
- Documentar en commit/reporte que la observación fue triageada como no-bug, citando la línea de código que prueba que está implementado.

### G10. Convenciones del proyecto pueden parecer bugs a un tester externo
**Regla:** cuando un tester (humano o agente IA) reporta una "discrepancia" entre dos campos del usuario / config / nombre de tabla, antes de investigar, **chequear si es una convención documentada en CLAUDE.md**. Si lo es, cerrar como no-bug y aclarar al tester.

**Why:** 2026-05-11. OBS-D-MISC-01: "header dice 'Cesar Zeta' pero email es `<USUARIO-DEMO>@municipio.gob.ar`". El tester lo marcó como discrepancia. Pero CLAUDE.md §1 documenta la convención: el email es `<username>@municipio.gob.ar` y el nombre real está en `usuarios.nombre`. No es bug, es por diseño. Si no lo verificaba contra DB primero, podía haber arrancado un fix innecesario.

**How to apply:**
- En reportes que llegan de afuera (ChatGPT, otros agentes, testers humanos no-familiarizados con el proyecto), tratar las "discrepancias entre campos del mismo dominio" como sospechosas de convención no-conocida.
- Verificar contra DB y CLAUDE.md antes de planear fix.
- Documentar la aclaración en el reporte/commit para que el próximo tester no caiga en lo mismo.

### G11. cwd de PowerShell/Bash se confunde entre tools distintas
**Regla:** el cwd persiste **dentro** de la misma tool (PowerShell o Bash) pero **no necesariamente** se sincroniza entre ambas. Para comandos que dependan del directorio (uvicorn, pnpm), usar **paths absolutos** o re-`Set-Location` explícito en cada llamada.

**Why:** 2026-05-11. Después de `Set-Location web-app` en una PowerShell, lancé un Bash que estaba en raíz. Después un nuevo PowerShell mantenía `web-app` como cwd. Levanté uvicorn con `Set-Location backend` → terminó buscando `web-app/backend` (no existe), `ModuleNotFoundError: No module named 'app'`. También: pnpm con cwd erróneo dio `ERR_PNPM_RECURSIVE_EXEC_NO_PACKAGE`.

**How to apply:**
- Para servicios long-running (uvicorn, vite, http.server): usar `Set-Location "<path absoluto>"` siempre.
- Si veo errores de "no se encuentra ruta" o "module not found", primer chequeo: `Get-Location` o `pwd` antes de re-lanzar.
- Para la próxima vez que arranque servicios desde cero en una sesión, usar paths absolutos desde el primer momento.

### G6. Respuestas internamente contradictorias en AskUserQuestion
**Regla:** cuando uso `AskUserQuestion` con varias preguntas en la misma llamada y las respuestas combinadas son lógicamente inconsistentes (ej: A1+A2 implica X, pero también implica no-X), **no inventar la síntesis**. Volver a preguntar haciendo explícito el conflicto y ofreciendo las salidas reales.

**Why:** 2026-05-10. Pregunté "¿alcance del modal Editar?" + "¿estado dentro o fuera del modal?". Respuestas: "edición por niveles según estado" + "estado se cambia desde otro lado". Si "Editar reclamo" reemplaza al botón "Cambiar estado" pero no incluye estado, entonces ¿desde dónde? Antes de elegir por mi cuenta, re-pregunté con las 3 salidas posibles (mantener botón separado / sumar dropdown estado adentro / hacer clickable el badge de estado). El usuario eligió la primera y quedó coherente.

**How to apply:**
- Tras recibir respuestas multi-pregunta, hacer una pasada mental de coherencia antes de implementar.
- Si la combinación tiene > 1 interpretación razonable, re-preguntar con AskUserQuestion mostrando las interpretaciones.
- Costo de re-preguntar (1 turn) << costo de implementar la interpretación equivocada (refactor + reset de contexto).

---

## H. Persistencia de aprendizajes (meta)

### H1. Este archivo es la fuente única
**Regla:** errores y reglas del proyecto van **acá**, organizados por tema. No crear archivos `feedback_<sesion>.md` nuevos.

**Why:** dispersar aprendizajes en 7+ archivos sueltos los hace inencontrables. La memoria solo sirve si en cada sesión se relee desde un único punto.

### H2. Releer al inicio cuando aplique
**Regla:** al inicio de una sesión que vaya a tocar DB, migraciones, scripts Python o frontend nuevo, releer este archivo (al menos las secciones A, C, D para lo primero; F, G para lo segundo).

### H3. Recaídas se documentan en la regla existente
**Regla:** si caigo en un error que ya estaba documentado acá, **no agregar entrada nueva**: actualizar la sección existente con la fecha de la recaída. Eso da señal de qué reglas siguen siendo difíciles de internalizar y merecen más énfasis.
