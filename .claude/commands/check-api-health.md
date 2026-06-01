# check-api-health

Verifica que la API de producción está respondiendo correctamente y que los endpoints críticos de ZARIS devuelven datos válidos.

## Pasos

1. Verificar el health check general:
   ```
   GET https://zaris-api-production-bf0b.up.railway.app/api/health
   ```

2. Hacer login para obtener un token de prueba:
   ```
   POST https://zaris-api-production-bf0b.up.railway.app/api/v1/auth/login
   { "email": "ciudadanovl@municipio.gob.ar", "password": "123456" }
   ```
   (admin nivel 1 — ver CLAUDE.md §32 quirk 10. Los emails dev son `<username>@municipio.gob.ar` con username viniendo de `usuarios.username`, no del rol.)

3. Con el token obtenido, verificar los endpoints críticos:
   - `GET /api/v1/buc/ciudadanos` — BUC ciudadanos
   - `GET /api/v1/buc/empresas` — BUC empresas
   - `GET /api/v1/admin/agentes` — tabla maestros
   - `GET /api/v1/admin/areas` — tabla secretarías
   - `GET /api/v1/admin/estado_reclamo` — estados de reclamo
   - `GET /api/v1/admin/agenda_feriado` — feriados
   - `GET /api/v1/admin/permisos/modulos` — catálogo de módulos (§30, solo admin nivel 1)
   - `GET /api/v1/auth/me` — verifica que el response incluye `modulos_permitidos: list[str]`

4. Para cada endpoint reportar: status code, cantidad de registros devueltos, y si hay error describir exactamente el mensaje.

5. Resumen final: cuántos endpoints OK vs. con error.

## Notas

- Si `/api/health` no responde, Railway puede estar en cold start — reintentar en 30 segundos.
- Si el login falla con 401, las credenciales demo pueden no estar en producción — indicar que hay que correr `seed_auth.py` contra la DB de prod.
- Si `estado_reclamo` falla, es probable que la migración no se haya aplicado en Supabase prod todavía.
