---
name: smoke-listar-users-primero
description: "Antes de un smoke test con condiciones por usuario (overrides, permisos, ownership), listar usuarios y guardar email↔id↔nivel. Evita perseguir falsos bugs por confundir cuál es cuál."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 018adadb-6bb9-4190-af10-c4b4dfb651d1
---

**Regla:** antes de correr un smoke test que aplica condiciones a un `id_usuario` específico (override de permisos, asignación de OT, ownership de algo), **listar los usuarios activos primero** y tener a mano el mapeo email↔id↔nivel. No asumir que recordás el id correcto.

**Why:** sesión 2026-05-12 perseguí un falso bug durante 20 minutos en el feature de permisos por módulo (§30). Apliqué un override bloqueante de `reclamos` al `id_usuario=3` (Roy Manoss). Después logueé con `<USUARIO-DEMO>@municipio.gob.ar` esperando ver el bloqueo. Login devolvía 4 módulos incluyendo `reclamos`. Diagnostiqué cache de SQLAlchemy, `expire_on_commit`, `.pyc` viejos, hasta que un log de debug temporal mostró `uid=2` (Juan Pestto), no `uid=3`. Nunca hubo bug — el helper `modulos_permitidos()` funcionaba perfecto. Yo estaba probando contra el usuario equivocado.

**How to apply:**

Al inicio de cualquier smoke test con scoping por usuario, correr una query como esta y dejarla en el output:

```sql
SELECT id_usuario, nombre, email, nivel_acceso
  FROM usuarios
 WHERE activo = TRUE
 ORDER BY nivel_acceso, id_usuario;
```

Después escribir los casos del smoke usando **id_usuario**, no email. El email es para login (humano-friendly); las queries de scoping van por id (DB-friendly).

Si el smoke es interactivo via curl, hacerlo así:

```bash
# Mapeo fijo de la sesión (anotar al principio):
# id=1 admin1@x.com nivel=1
# id=2 juan@x.com   nivel=3
# id=3 roy@x.com    nivel=3

# Probar override en id=2:
curl -X PUT .../admin/permisos/usuarios/2/modulos ...

# Login con el email correspondiente a id=2:
curl -X POST /login -d '{"email":"juan@x.com",...}'
```

**Cómo detectar el problema rápido cuando aparece:** si el resultado del smoke no coincide con lo esperado **y el código del helper se ve correcto**, agregar un log de debug que imprima los argumentos reales (`logger.warning(f"uid={uid!r} nivel={nivel!r}")`). Los argumentos te dicen instantáneamente si el problema es "código mal" o "test mal".

Antes de embarcarse en debugging de cache/sesión/pyc/etc, **verificar primero los inputs**.
