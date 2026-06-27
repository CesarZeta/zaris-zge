---
name: feedback-background-tasks-sesion-nueva
description: BackgroundTasks de FastAPI corren tras cerrar la respuesta. La sesión SQL del request ya está cerrada — abrir una nueva con AsyncSessionLocal() para cualquier UPDATE/INSERT post-send.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8a7ed55b-b83e-4f0a-a792-52d4f2df39fc
---

Patrón verificado en `services/notificaciones.py::_enviar_mail_y_marcar` (2026-05-19, marcar `enviada_mail=TRUE` tras send exitoso de mail).

**Why:** los `background_tasks.add_task(fn, ...)` de FastAPI corren *después* de que la respuesta HTTP se cerró. En ese punto, la sesión SQLAlchemy del request ya está disuelta. Si la background reutiliza la `db` que recibió como cierre/binding, va a explotar con `InterfaceError: cannot operate on a closed database` o silenciosamente no persistir nada (SQLAlchemy puede swallowear).

**How to apply:**

```python
from app.core.database import AsyncSessionLocal

async def mi_background_task(id_recurso: int, ...):
    try:
        ok = await hacer_algo_externo(...)  # send mail, llamar API, etc.
        if not ok:
            return
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE tabla SET flag=TRUE WHERE id=:id"),
                {"id": id_recurso},
            )
            await session.commit()
    except Exception as e:
        logger.error("background fallo (id=%s): %s", id_recurso, e, exc_info=True)
```

Reglas:
1. **Encolar SOLO después de `db.commit()` del caller.** Si el background corre antes de que la fila esté persistida, el `UPDATE` no encuentra nada. Usar `RETURNING id_X`, commitear, después encolar.
2. **Try/except global**. La background task no tiene quien la atrape — los errores van al log y se pierden. Fail-safe SIEMPRE.
3. **Identificar la fila con id, no con FK del usuario.** Si el background recibe `to=email`, no puede ubicar la fila a actualizar. Pasar `id_notificacion` (o equivalente).

**Aplicable a:** cualquier flujo "endpoint commitea cosa → background hace trabajo externo → quiere actualizar la cosa". Ejemplos potenciales: enviar webhook + marcar enviado, generar PDF + actualizar URL del recurso, geocodificar dirección post-creación.

Relacionado: [[feedback_service_commit_propio]] (mismo patrón para services llamados después del commit del endpoint).
