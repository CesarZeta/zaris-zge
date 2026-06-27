---
name: feedback_el_backend_puede_mentir
description: "El backend puede 'mentir' de 3 formas (shape del JSON ≠ tipo TS · import OK pero openapi() crashea · SELECT explícito omite columna que el schema declara). Mismo principio: el código es hipótesis, la respuesta HTTP/runtime es el hecho — verificar el JSON crudo, no el tipo ni el import."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: db12f794-d376-425b-9339-953265cd6368
---

"El backend importa / compila / responde 200" NO prueba que hace lo que el código sugiere. Tres caras del mismo principio: **el código (tipo TS, `import app`, schema Pydantic) es una promesa; el hecho es la respuesta HTTP cruda o el arranque real de uvicorn.** Antes de declarar resuelto un bug de "datos que no aparecen", "botón mudo" o "feature que no carga" en un módulo que cruza front↔back, **leer el JSON crudo del endpoint** (curl/PowerShell con token, o el log de runtime), no el código.

**Cara 1 — la shape del JSON ≠ el tipo TS (runtime, frontend).** Un endpoint que responde 200 rompe la UI si la shape no coincide con el tipo TS declarado. TS no valida en runtime: acceder a una propiedad que el backend pone en otro nivel devuelve `undefined` sin error, y un `?? []` defensivo lo convierte en "feature que silenciosamente no hace nada".
- Caso (Trámites alta, 2026-05-29): `GET /tramites/tipos/{id}` devolvía `campos`/`estados` a nivel raíz, pero el tipo TS los declaraba anidados en `version` → `tipo.version.campos` `undefined` → paso 4 mostraba "no requiere datos" y `validarDatos(undefined,…)` tiraba TypeError antes del try/catch → botón "Crear" mudo, sin toast. Segunda capa el mismo día: el POST armaba body plano (`iniciador_tipo`, `datos_jsonb`) cuando el backend esperaba `iniciador` anidado + `datos` → 422 en todo alta.
- Aplicar: comparar campo por campo el JSON real vs el tipo TS; para POST/PUT comparar el body que arma el front vs el schema `*In` (anidado vs plano, `datos` vs `datos_jsonb`). El contrato real es el Pydantic del backend, no el TS; si divergen, gana el backend (o se cambian ambos a la vez, conscientemente).

**Cara 2 — `import app` OK pero `app.openapi()` crashea (runtime, backend al arrancar).** FastAPI evalúa las anotaciones de tipo de los endpoints (`body: FooIn`) al **construir el OpenAPI schema**, no al importar el módulo. Un schema usado como anotación pero no importado en el router (o forward-ref sin resolver) pasa el `import app` y crashea recién en `app.openapi()` — que es lo que uvicorn hace al arrancar. Síntoma prod: `PydanticUndefinedAnnotation: name 'XxxIn' is not defined`.
- Caso (2026-06-01): `tramites_admin.py` usaba `AprobacionRequeridaIn` como tipo en 3 endpoints sin importarlo. Crasheó uvicorn en Railway al arrancar → rollback automático al deploy viejo (prod respondía health 200 con código viejo). `import app` local dio falso OK.
- Agravante de versión: local pydantic 2.12.5 resuelve el namespace sin el import; prod 2.7.1 NO. Lo que local tolera, prod rompe (cara de [[feedback_verificar_drift_completo_prod]] en versiones de libs).
- Check correcto antes de pushear backend que toca schemas/anotaciones de endpoints — borrar `.pyc` (evita falso OK por cache) + `app.openapi()`:
  ```powershell
  Get-ChildItem -Path app -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
  $env:ENV_FILE=".env.local"
  python -c "from app.main import app; s=app.openapi(); print('OPENAPI OK', len(s['paths']))"
  ```
  Si pasa, el arranque de uvicorn en prod también. Tras el push, verificar prod arrancó (health + un path que solo exista en el commit nuevo — el rollback de Railway oculta el crash, §9).

**Cara 3 — un SELECT explícito omite la columna que el schema Out declara (runtime, backend).** Agregar una columna obliga a auditar **todos los `SELECT` con lista explícita** que lean la tabla, no solo la migración + schemas + INSERT/UPDATE. Un `SELECT col1, col2` que no la incluye la deja fuera de la respuesta aunque el Out la declare y la DB la tenga; el `dict(r._mapping)` solo expone lo que el SELECT trajo. Bug silencioso: campo `undefined`, sin error, y el typecheck del front no lo caza porque el campo es opcional.
- Caso (mig 68, editor de tipos de trámite): agregué `tipo_accion`/`mensaje_iniciador` a `tipo_tramite_transicion`; toqué migración/schemas/INSERT/UPDATE/`_copiar_estructura` pero `detalle_version` en `tramites_admin.py` tenía SELECTs explícitos que no las incluían → transiciones sin `tipo_accion`. Lo delató leer el JSON real. (Recurrente: en mig 73 / aprobaciones por etapa, el handler `GET /{numero_o_id}` arma su propio `TramiteDetalleOut` aparte de `_tramite_detalle_out` — dos rutas construyen el mismo response; hay que tocar las dos, §35.)
- Aplicar: tras agregar la columna, `grep` la tabla en `backend/app/` y revisar cada `SELECT ... FROM <tabla>` que no sea `SELECT *`. Los `*` la traen solos; los explícitos no.

**Why:** las tres comparten la raíz — confiar en el artefacto estático (tipo, import, schema) en vez del comportamiento real. Hermana de [[feedback_verificar_siempre_antes_de_opinar]], [[feedback_verificar_forms_navegando_mandatorio]] y [[feedback_verificar_runtime_antes_de_agente]]: el código es hipótesis, la respuesta HTTP / el arranque real es el hecho.
