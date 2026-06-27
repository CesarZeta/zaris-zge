---
name: verificar-pendientes-antes-de-atacar
description: "Pendientes listados en CLAUDE.md o memoria pueden estar resueltos hace sesiones. Antes de planificar/listar uno, verificar 5-30s contra el código actual. La doc no es fuente de verdad."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8a7ed55b-b83e-4f0a-a792-52d4f2df39fc
---

Cuando el usuario pregunta "qué pendientes hay" o elegís uno de un backlog, **NO leer CLAUDE.md ni la memoria como verdad**. La doc puede estar desactualizada por bloques enteros — el código es la fuente.

## Casos verificados

**2026-05-15 (sub-fase 3.B Agenda):** de 9 pendientes marcados `[ ]` en CLAUDE.md, **5 ya estaban implementados** hacía sesiones (autocompletar OT/evento, QR renderizado, autoservicio público). Costo de verificar: ~minutos con grep. Costo de codear sin verificar: 1-2h de trabajo descartable + posible duplicación de componentes.

**2026-05-19 (limpieza general):** de 6 pendientes que listé al usuario, **4 ya estaban resueltos**:

| Pendiente listado | Realidad |
|---|---|
| Subreclamo UI no expuesto en Reclamos | `SubreclamoModal.tsx` ya existe |
| Badge "⚠ falta vincular agentes" en Espacios | Ya en `EspaciosConfig.tsx:54-56` + backend con `cant_agentes` |
| BUG-001 passlib local sin pushear | Pusheado en `43e310d` (memoria decía "solo en local") |
| Permiso `'turnos'` cubre los 3 módulos | Mig 44 ya separó en `agenda`/`turnos`/`entradas` |
| `frontend/usuarios.html` huérfano | No lo es — vive accesible desde Config>Sistema y `admin_tablas` |

## Por qué pasa

Las memorias se escriben en el momento, las features siguen avanzando, nadie actualiza memorias viejas. La sesión que pregunta "qué pendientes hay?" recibe un mix de pendientes reales y resueltos. Atacar uno fantasma cuesta el round-trip a mitad del trabajo y arruina la confianza del resumen entregado al usuario. Patrón observado: los pendientes recién-creados están al día; los pendientes con > 1 sesión de antigüedad son sospechosos por defecto.

## Checklist 5s por pendiente antes de listarlo

1. **Menciona un archivo:** `Glob` o `Read` confirma existencia + mtime.
2. **Menciona un endpoint:** `Grep` del path o decorador.
3. **Menciona un commit:** `git log --oneline -- path/file` lo confirma.
4. **Menciona DB schema:** `execute_sql` rápido contra la columna/seed.
5. **Menciona un fix "pendiente push":** `git log --oneline --all -- path/file` lo encuentra o no.

Costo total para 6 pendientes ≈ 2-3 minutos. Gana abrumadoramente vs. descubrir fantasmas en medio del trabajo.

## Cuándo NO aplica

- Pendientes obvios del momento (TODO de la sesión actual).
- Pendientes que ya verificaste en esta misma sesión.

Aplica a **herencia entre sesiones** — "según la memoria X de hace N días", "vi que en CLAUDE.md §Y dice...".

## Memorias relacionadas

- [[feedback_verificar_drift_completo_prod]] — antes de codear backend que escriba, verificar drift en prod (CHECKs/defaults/seeds).
- [[feedback_smoke_listar_users_primero]] — antes de smoke con usuarios, listar emails reales en DB.
- [[feedback_grep_DS_antes_de_crear]] — antes de naming nuevo en DS, grep alternativas.
