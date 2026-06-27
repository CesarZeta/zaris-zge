---
name: reference_fastapi_router_dependencies_no_override
description: "FastAPI: dependencies=[] en el decorador del path NO anula las del APIRouter (son aditivas)"
metadata: 
  node_type: memory
  type: reference
  originSessionId: c90a3545-3afb-4e9e-be8d-0ee54fc10b59
---

En FastAPI, las `dependencies=[...]` declaradas a nivel `APIRouter(...)` se aplican a
**todas** las rutas del router y **NO se pueden anular** poniendo `dependencies=[]` en el
decorador `@router.post(...)`. Las dependencies del decorador se **suman** a las del router,
no las reemplazan.

Consecuencia: si un router tiene `APIRouter(dependencies=[Depends(get_current_user)])`
(guard JWT global, patrón §39), NO se puede hacer un endpoint "público" dentro de ese
router con `@router.post("/x", dependencies=[])` — el guard JWT sigue activo → 401.

**Solución:** crear un router SEPARADO sin el guard global, con el mismo prefix si se
quiere conservar la URL. Registrarlo aparte en main.py (cuidando el orden vs `/{tabla}`
greedy de admin_tablas, §5).

```python
router = APIRouter(prefix="/api/v1/admin/encuestas", dependencies=[Depends(get_current_user)])
# endpoint público (auth por header, no JWT) -> router propio SIN dependencies:
dispatcher_router = APIRouter(prefix="/api/v1/admin/encuestas")
@dispatcher_router.post("/dispatcher/ejecutar")
async def ejecutar_dispatcher(...): ...
```

Cazado 2026-05-22 en encuestas_admin.py (dispatcher 2E.B). El prompt externo asumía que
`dependencies=[]` overrideaba — no es así. Síntoma: el endpoint con header válido daba 401
porque el guard JWT del router seguía corriendo antes que la validación del header.
