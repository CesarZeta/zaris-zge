---
name: feedback-guard-a-nivel-router-vs-por-handler
description: "Para proteger TODO un router FastAPI (todos los verbos + endpoints futuros) usar APIRouter(dependencies=[Depends(get_current_user)]), no Depends por-handler. Solo dejar sin guard lo genuinamente público, y eso va en un router separado."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c0686d84-5411-438f-9006-4373e9d0fe24
---

Cuando un router entero debe exigir auth, el guard va en el `APIRouter`, no repetido en cada handler:

```python
router = APIRouter(
    prefix="/api/v1/buc",
    tags=["BUC"],
    dependencies=[Depends(get_current_user)],   # cubre TODOS los endpoints, GET incluidos
)
```

**Why:** sesión 2026-05-22, cerrando la deuda del router BUC. Primero protegí solo escritura con `_user: dict = Depends(get_current_user)` por-handler (9 endpoints). Quedaban 16 GET sin auth y, peor, cualquier endpoint nuevo nacía desprotegido (fue exactamente cómo nació el bug original: 28 endpoints sin un solo `Depends`). El guard a nivel router resolvió los 28 de una y blinda los futuros. Quité los 10 `_user: Depends(...)` por-handler (redundantes).

**How to apply:**
1. **Default seguro:** si más de la mitad de los endpoints de un router necesitan auth, ponelo en el `APIRouter(..., dependencies=[...])`. Es más robusto contra regresiones que recordar agregar `Depends` en cada handler nuevo.
2. **Lo genuinamente público va en OTRO router.** No mezcles endpoints sin auth en un router protegido. En ZARIS la App Vecinos usa `/api/v1/publico/*` (router separado, §38) — por eso el guard del router BUC no la afectó. Si tenés que exceptuar 1-2 endpoints de un router protegido, es señal de que van en su propio router.
3. **`dependencies=[...]` vs param en la firma:** usar `dependencies=[Depends(x)]` cuando NO necesitás el valor que devuelve (solo el efecto: validar/rechazar). Usar `_user: dict = Depends(x)` en la firma solo cuando el handler usa `current_user` (ej: inyectar `id_usuario_alta`, chequear nivel). En BUC los handlers no usan el user → `dependencies` es lo correcto.
4. **Verificá que ningún consumidor sea público antes de aplicar guard router-wide:** grep los call sites (en ZARIS: `web-app/src/**` usa `lib/api.ts` que adjunta token siempre; `usuarios.html` usa `ZUtils.apiFetch` con token). Si todos mandan token, el guard no rompe nada.

Relacionado: [[guard-nivel-endpoint-no-solo-ui]] (ocultar en UI ≠ proteger backend) y CLAUDE.md §3.
