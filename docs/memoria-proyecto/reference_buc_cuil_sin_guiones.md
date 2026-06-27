---
name: buc-cuil-sin-guiones
description: "Backend BUC guarda CUIL/CUIT SIN guiones porque _validar_modulo11 retorna `limpio`. DB tiene filas con ambos formatos. Frontend debe aceptar ambos y formatear al mostrar."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 4ed10f75-1110-405b-a93b-8ba08aa79fe3
---

`backend/app/schemas/buc.py:13-35` (`_validar_modulo11`) valida CUIL/CUIT y **retorna el valor limpio (sin guiones)**:

```python
def _validar_modulo11(valor: str) -> str:
    limpio = re.sub(r"[-\s]", "", valor)
    # ... validación ...
    return limpio  # guardar sin guiones
```

Consecuencia: cuando el frontend envía `"20-99887700-9"`, Pydantic valida y guarda `"20998877009"`. Pero filas antiguas (importadas desde CSVs legacy) en `ciudadanos` y `empresas` están con guiones.

**Estado real en prod (verificado 2026-05-12):**
- 354 MUJER + 133 HOMBRE + 15 OTROS en `ciudadanos.sexo` (uppercase OK).
- CUIL: mezcla. Ej `id=509` test creado en sesión muestra `cuil: "20998877009"`. Ciudadanos antiguos del padrón muestran `cuil: "20-13410914-5"`.

**How to apply:**
- **Mostrar CUIL en UI**: aceptar ambos formatos (`with`/`without` guiones) y formatear con `formatCuilInput()` (web-app/src/modules/ciudadanos/lib/cuilUtils.ts) o equivalente vanilla antes de renderizar. Nunca asumir que vienen con guiones.
- **Búsqueda numérica**: ya está bien resuelto en backend — `digits_expr(col)` normaliza removiendo no-dígitos antes de matchear (`backend/app/api/routes/buc.py:217`). Search por "1164295018" matchea "(11) 6429-5018".
- **Si en el futuro decidimos normalizar a un solo formato**: es un ALTER + UPDATE masivo. Sugerencia: dejarlo como está y normalizar al mostrar. La DB es la fuente, el formato visual es responsabilidad del frontend.

**Local `zaris_dev` adicional:** tiene ciudadano `id=506` con `sexo='femenino'` (lowercase español) que viola el CHECK uppercase actual. Drift histórico, no existe en prod. NO renderiza en `<select>` con opciones HOMBRE|MUJER|OTROS. Si molesta, `UPDATE ciudadanos SET sexo='MUJER' WHERE sexo='femenino'`.

Relacionado: §22 CLAUDE.md (geolocalización + activos), §29 (patrones web-app).
