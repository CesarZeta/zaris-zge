---
name: verificar-runtime-antes-de-agente
description: "Antes de pasar un prompt a un agente externo de QA (Claude Chrome u otro), verificar que el runtime ya tenga el codigo nuevo, no solo el repositorio. Verificar codigo NO equivale a verificar runtime."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 9f22ae1e-23dd-4dae-9ee4-6c68e1a34b76
---

Cambiar codigo no es suficiente. El servidor backend puede seguir corriendo el codigo viejo si no se reinicio (uvicorn sin --reload, o uvicorn corriendo desde antes de tus cambios). Si paso al usuario un prompt para que su agente de QA pruebe, y el backend esta desactualizado, el agente frena en preconditions y se pierde tiempo.

**Why:** sesion 2026-05-11, sub-fase 3.B Agenda. Modifique `OcupacionUpdate` para aceptar `tipo_recurso`/`id_recurso`. Pase el prompt al agente Chrome. El agente verifico `/openapi.json` y reporto FAIL: solo 6 props en lugar de 8. Uvicorn estaba corriendo el codigo viejo (PID 1648 sin --reload). El usuario tuvo que reiniciar manualmente. Pude haberlo detectado yo antes de pasarle el prompt.

**How to apply:**

Antes de pasar al usuario un prompt para un agente de QA externo, hacer estos checks segun lo que toque el cambio:

1. **Cambio en schemas/endpoints backend:**
   ```bash
   curl http://127.0.0.1:8000/openapi.json | python -c "import sys,json; d=json.load(sys.stdin); s=d['components']['schemas']['<MiSchema>']; print(list(s.get('properties',{}).keys()))"
   ```
   Verificar que aparezcan los campos nuevos. Si no, uvicorn corre codigo viejo.

2. **Cambio en frontend (web-app/ con Vite):**
   - En dev (`pnpm dev`): hot reload corre solo, no hay que verificar.
   - En prod (GitHub Pages): verificar que el HTML servido apunte al hash nuevo del JS/CSS:
   ```bash
   curl -sS https://cesarzeta.github.io/zaris-zge/web-app/dist/index.html | grep -o 'index-[A-Za-z0-9_]*\.\(js\|css\)'
   ```
   Comparar con el hash generado por el ultimo `pnpm build`. Si difieren, GitHub Pages aun no publico o el commit del dist no llego.

3. **Cambio en DB (migracion):**
   ```sql
   -- Verificar que la columna/tabla nueva existe
   SELECT to_regclass('public.<tabla_nueva>') AS existe;
   SELECT column_name FROM information_schema.columns WHERE table_name='<tabla>' AND column_name='<columna_nueva>';
   ```

4. **Cambio en variables de entorno:**
   - Backend: el proceso reinicio? `tasklist | grep uvicorn` y comparar PID. Si es el mismo, no reinicio.
   - Frontend: `.env.production` se aplica solo en `pnpm build`. Si solo cambie el .env, el dist viejo no tiene los nuevos valores.

5. **Regla general:** si el cambio toca algo que el agente externo va a verificar en preconditions, **simular esa verificacion yo primero**. El agente externo cuesta tiempo y atencion del usuario; un curl previo cuesta 5 segundos.

Adicional: si el reinicio es necesario y soy yo quien tiene que hacerlo, **no matar el proceso sin avisar** (puede haber trabajo abierto). Pasarle al usuario los comandos exactos y esperar confirmacion. Caso real: PID 1648 en esa misma sesion, le pase los comandos a el porque era riesgoso decidir solo.
