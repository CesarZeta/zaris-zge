# push-and-verify

Flujo completo de deploy: commit → push → esperar Railway → verificar API prod. Un solo comando para cerrar el ciclo de desarrollo.

## Uso

```
/push-and-verify [mensaje de commit opcional]
```

## Pasos

### 1. Pre-flight local

Verificar que el estado local es deployable:
- `git status` — mostrar archivos modificados
- `git diff --stat HEAD` — resumen de cambios
- Alertar si hay archivos `.env*` o `*.local` staged accidentalmente

### 2. Commit

Si hay cambios sin commitear:
- Stagear archivos relevantes (nunca `.env*`, `__pycache__/`, `*.pyc`, `.env.local`)
- Si se proporcionó mensaje: usarlo directamente
- Si no: generar un mensaje descriptivo basado en los diffs, mostrarlo al usuario y confirmar antes de commitear
- Formato del commit: convención del proyecto (feat/fix/docs/refactor + scope)

### 3. Push

```bash
git push origin main
```

### 4. Esperar deploy Railway

Railway detecta el push y redespliega automáticamente. Tiempo estimado: 1-3 minutos.

Hacer polling del health check cada 20 segundos, máximo 10 intentos:
```
GET https://zaris-api-production-bf0b.up.railway.app/api/health
```

Reportar en cada intento: `[intento N/10] status: XXX`

### 5. Verificar endpoints críticos

Una vez que el health check responde 200, ejecutar el mismo conjunto de verificaciones que `/check-api-health` (pasos 2-4).

### 6. Resultado final

Reportar:
- Hash del commit pusheado
- Tiempo total hasta deploy OK
- Estado de cada endpoint verificado
- Si algo falló: qué falló y próximos pasos sugeridos

## Notas

- Nunca hacer force push a `main`.
- Si el deploy falla repetidamente, sugerir revisar Railway → Deployments → logs del build.
- El frontend (GitHub Pages) se actualiza automáticamente con el push — no requiere pasos adicionales.
- `seed_demo.py` no debe commitearse a producción — verificar que está en `.gitignore` o ignorarlo en el staging.
