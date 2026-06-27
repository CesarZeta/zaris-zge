---
name: feedback-service-commit-propio
description: "Services llamados DESPUÉS del commit del endpoint deben hacer su propio db.commit(), no flush. Sino las filas se descartan silenciosamente al cerrar la sesión SQLAlchemy."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e77756f2-e217-4421-a18c-df927d47dfb5
---

Si un service async inserta filas DESPUÉS de que el endpoint hizo `await db.commit()`, la sesión SQLAlchemy ya cerró su transacción anterior y abre una nueva implícita al primer INSERT. Si el service usa `await db.flush()` pero no `await db.commit()`, las filas quedan pendientes en esa transacción nueva, y FastAPI cierra la sesión al final del request sin commitear → **se pierden silenciosamente sin error**.

Síntoma típico: el endpoint devuelve 201, el log del service dice "INSERT exitoso", pero un SELECT a la tabla devuelve 0 filas.

**How to apply:** services que se llaman después del commit del endpoint (hook post-commit, BackgroundTask resuelto sincronicamente, etc.) deben terminar con `await db.commit()` no `await db.flush()`. El flush solo sirve cuando alguien más va a commitear después.

Caso real: `services/notificaciones.py::notificar_tramite_a_bandeja` llamado desde `routes/tramites.py::crear_tramite` después del `await db.commit()` del trámite. Primera versión con flush perdía las notifs. Fix: commit explícito (sesión 2026-05-18).
