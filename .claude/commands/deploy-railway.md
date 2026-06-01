# deploy-railway

Hace commit de todos los cambios pendientes, push a `main`, y verifica que Railway desplegó correctamente.

## Pasos

1. Mostrar el `git status` y `git diff --stat` para que el usuario confirme qué se va a commitear.
2. Pedir al usuario un mensaje de commit (o usar uno generado basado en los cambios).
3. Hacer `git add` de los archivos relevantes (nunca `.env*`, nunca `*.local`).
4. Hacer `git commit` con el mensaje confirmado.
5. Hacer `git push origin main`.
6. Esperar ~30 segundos y verificar el health check de Railway:
   ```
   GET https://zaris-api-production-bf0b.up.railway.app/api/health
   ```
7. Si el health check responde 200, reportar "Deploy OK". Si falla, reportar el error y sugerir revisar los logs de Railway.

## Notas

- Railway despliega automáticamente desde `main` branch, root `/backend`.
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- El deploy tarda entre 1 y 3 minutos normalmente.
- Si el health check falla después de 3 intentos, el deploy puede estar fallando — revisar en Railway dashboard.
