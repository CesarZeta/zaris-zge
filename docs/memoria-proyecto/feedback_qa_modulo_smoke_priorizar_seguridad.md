---
name: feedback-qa-modulo-smoke-priorizar-seguridad
description: "En smoke QA de cualquier modulo CRUD, agregar siempre 3 casos: endpoint sin JWT, XSS persistente en campo string libre, y login real con el user recien creado. Estos sacan los CRITICAL que happy-path no encuentra."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b7b8e93f-b7b1-4d36-b628-60ccedf00bf2
---

Cuando hago un smoke QA "completo" de un modulo CRUD, los CRITICAL casi nunca aparecen siguiendo el happy path. Tres casos que SI los sacan y que valen su minuto de codear:

**Caso 1 — Endpoint sin JWT.** Un curl directo al POST de alta sin header Authorization. Si responde 201, hay auth bypass. CLAUDE.md §3 dice que todo endpoint con identidad/permisos usa get_current_user, pero esto se viola en silencio. Caso real: `/api/v1/buc/usuarios` cree admin nivel 1 sin token, BUG-USU-02. Es 30 segundos de PowerShell.

**Caso 2 — XSS persistente en campo string libre.** Crear un usuario/cliente/lo-que-sea con `nombre = '<img src=x onerror="window._xss=true">QA'`. Despues abrir un listado o resultados de busqueda y verificar `window._xss`. Caso real: BUG-USU-01 en usuarios.js mostrarResultados — el render usa innerHTML con interpolacion directa, mientras que cargarVistaPrevia del mismo archivo si usa esc(). El bug es facil de pasar por alto leyendo codigo (un esc() de mas y se ve igual), pero se confirma trivial con el payload. Si el modulo se renderiza dentro del shell, el XSS toca `window.parent` y accede al JWT del shell — escalamiento total.

**Caso 3 — Login real con el user que acabo de crear.** No alcanza con "201 Created + aparece en la lista". Llamar a POST /auth/login con las credenciales armadas. Caso real: BUG-USU-03 — el form no captura email, la columna queda NULL, y como login busca por email, ningun user creado por UI puede entrar. Solo se descubre intentando entrar.

**Por que vale la pena el costo:**
- Los tres son ~3 min sumados. El smoke completo de Usuarios (22 casos) tardo ~15 min — incrementar 20% para cazar lo critico es ganancia obvia.
- Sin estos, el reporte termina como "todo PASS en green" mientras la auth esta rota. Reporte falsamente positivo = peor que no haber hecho QA.
- Acoplamiento real cazado: BUG-02 (auth bypass) + BUG-01 (XSS) = atacante externo crea admin con XSS en nombre y dispara JS en el shell de cualquier admin que busque. Casos sueltos no se ven, encadenados son catastroficos.

**Cuando NO aplica:**
- Modulos puramente de consulta (sin POST/PUT) — saltear caso 1 y 3.
- Modulos React que ya tienen ProtectedRoute + escape automatico de JSX — el riesgo de XSS por interpolacion baja mucho, pero el caso 1 (backend) sigue valiendo.

Ver tambien [[feedback_smoke_cleanup_prod]] para limpieza obligatoria de los users de test creados al final.
