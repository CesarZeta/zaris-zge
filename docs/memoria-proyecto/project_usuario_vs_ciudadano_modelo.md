---
name: project_usuario_vs_ciudadano_modelo
description: Usuario = credencial (define el tipo de uso del sistema); Ciudadano = entidad formal gestionable contra prestaciones/turnos/reclamos/trámites.
metadata: 
  node_type: memory
  type: project
  originSessionId: ec9140d5-f707-4775-bbed-8aeda8a5bcaf
---

Definición conceptual del usuario (confirmada por Cesar, 2026-06-01):

1. **"Usuario" = credenciales.** Las credenciales son las que definen el tipo de uso del sistema (con qué scope/permisos se entra). En ZARIS hay dos familias de credencial:
   - `usuarios` (empleados municipales / agentes) → JWT scope `agente`, con `nivel_acceso`. Acceso al backoffice.
   - `ciudadano_credencial` (vecinos) → JWT scope `publico`. NO da acceso al backoffice; es la cuenta del vecino para autoservicio (reclamos, turnos, gestiones).
   - (Nueva en alta pública) `empresa_credencial` → solo verificación de email de la empresa, sin login por ahora.

2. **"Ciudadano" = la entidad formal con todos los datos** (`ciudadanos`, la BUC §2). Es la entidad **gestionable que SIEMPRE acompaña** a la prestación, el turno, el reclamo, el trámite, etc. No es una cuenta: es el sujeto de negocio.

**Implicación de diseño:** la cuenta del vecino (`ciudadano_credencial`) y su ficha (`ciudadanos`) son cosas distintas pero 1:1. En el alta pública de vecinos (§ alta-vecino.html) se crean **juntas en una transacción**; el mail de verificación activa la credencial (`activado=TRUE`) y marca la ficha (`email_chk=TRUE`, `estado_validacion='verificado'`). El vecino NO es un `usuarios` — eso le daría backoffice. Ver [[project_alta_publica_vecinos]].

**Alta del vecino en DOS PASOS (confirmado Cesar 2026-06-09, Fase 4, mig 79):** el modelo quedó **separado** (vecino NO se unifica en `usuarios`; sigue en `ciudadanos`+`ciudadano_credencial`, scope `publico`). El autoregistro se separó en dos momentos (antes era cuenta+ficha juntas): **Paso 1** = crear cuenta con el mínimo real (DNI+nombre+apellido+email+password) → `ciudadanos` con placeholders en los NOT NULL faltantes + `ciudadano_credencial`, `ficha_completa=FALSE`. **Verificar email.** **Paso 2** = el vecino verificado+logueado completa su ficha real (`POST /publico/auth/completar-ficha`, JWT publico) → reemplaza placeholders, `ficha_completa=TRUE`. Marca `ciudadanos.ficha_completa` distingue "cuenta creada" de "ficha completa"; el portal la consulta en `me`/`login` para mandar a completar. **Camino B (alta por agente):** mantiene activación-por-token (el vecino elige su clave al activar; NO clave-temporal-forzada — eso es solo para internos, Fase 3). **Empresa fuera del alta pública**: la carga el vecino logueado con ficha completa (sigue exigiendo ciudadano previo, BUC §2). Detalle en CLAUDE.md §38.

**Permisos del vecino (confirmado Cesar 2026-06-01):** la cuenta del ciudadano debe poder hacer **las mismas ACCIONES de autoservicio que un operador (call center, nivel 3) haría en su nombre** — crear/ver SUS reclamos, sacar/ver SUS turnos, iniciar trámites, ver su historial — pero **acotado a sus propios datos** (no backoffice, no datos de terceros). NO se le da `nivel_acceso` de agente ni cuenta en `usuarios` (eso sería personal municipal y un autoregistro público no puede otorgar acceso interno). El scope `publico` ya separa esto a nivel JWT (`get_current_ciudadano` rechaza tokens `agente` y viceversa). Cesar dejó abierta la puerta a "diferenciarlo por las dudas" más adelante (perfil de permisos propio del vecino), pero en principio = paridad de acciones con el operador, acotado a lo suyo. **Estado al 2026-06-01:** los endpoints de autoservicio del vecino NO existen aún (`get_current_ciudadano` solo se usa en `/me`); son la Etapa 2+ de App Vecinos (§38). El alta pública ya crea la cuenta correcta; falta construir esos endpoints scopeados al `id_ciudadano` del token.
