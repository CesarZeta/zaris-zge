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
   { "email": "<admin de prod>", "password": "<ver credenciales-testing/>" }
   ```
   (Las credenciales de PROD viven en `credenciales-testing/` FUERA del repo — §40, nunca incrustarlas acá. El login de prod es por email EXACTO de `usuarios.email`, que puede no seguir el patrón `<username>@municipio.gob.ar` — ver memoria `reference_login_email_prod_no_es_patron_doc`.)

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
