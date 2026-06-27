---
name: ps-var-dos-puntos-es-drive
description: "En PowerShell, $var seguido de ':' dentro de un string se parsea como referencia a un PSDrive ($var:) y da ParserError. Usar ${var}: para delimitar."
metadata:
  type: feedback
---

En PowerShell, `"$id:"` o `"intento $i:"` dentro de un string da **ParserError: "La referencia de variable no es válida. El carácter ':' no va seguido de un carácter de nombre de variable válido"**. PowerShell interpreta `$id:` como una referencia a un PSDrive llamado `id` (sintaxis `$env:`, `$HKLM:`, etc.).

**Fix:** delimitar el nombre con llaves: `"${id}:"`, `"intento ${i}: HTTP ${sc}"`.

**Cazado dos veces en la sesión 2026-05-27** armando loops de polling con logging tipo `"intento $i: ..."`. Patrón a evitar de entrada en cualquier string PS que tenga `$variable` inmediatamente seguida de `:`.

Relacionado (otros operadores PS5.1 ausentes que también tumban scripts, cazados la misma sesión): `??` (null-coalescing) NO existe en PowerShell 5.1 → da "Token '??' inesperado". Usar `if/else` explícito. Ver también la nota del entorno sobre PS 5.1 en el system prompt (ternario, `?.`, `&&`/`||` tampoco existen).
