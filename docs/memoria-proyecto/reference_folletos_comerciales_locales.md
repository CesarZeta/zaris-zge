---
name: reference_folletos_comerciales_locales
description: "Folletos comerciales de la Suite viven en folletos/ (gitignored, NUNCA a docs/ que es público). Convenciones de diseño y datos de contacto correctos."
metadata: 
  node_type: memory
  type: reference
  originSessionId: b58ec7ef-817f-47b8-9475-344a9e533f3a
---

Los folletos/material comercial de ZARIS viven en `folletos/` (raíz del repo ZGE), carpeta **en `.gitignore`** — material local, NO se publica en GH Pages (a diferencia de `docs/`, que sí es público). Primer folleto: `folletos/folleto_suite_zaris.html` (2026-06-09, glosario integral de la Suite, al usuario le gustó mucho el diseño — usarlo de plantilla).

**Datos de marca/contacto correctos (los dio el usuario):**
- Empresa: **ZARIS Consultora** · Producto: **ZARIS Gestión Estado**. Destacar ambos lockups (isologo `zaris-mark-flat.svg` inline + wordmark) en portada y contratapa.
- Web: `www.zaris.com.ar` · Email: **`info@zaris.com.ar`** (SIN "c" — `info@zarisc.com.ar` fue un error dictado y corregido).

**Why:** `docs/` se sirve en `zge.zaris.com.ar` — un folleto con frases comerciales no debe mezclarse con los manuales del producto; y el dato de contacto equivocado en material comercial es costoso.

**How to apply (convenciones del folleto, verificadas navegando):**
- Páginas A4 exactas (`.page` 210×297mm, `break-after:page`, `@page{size:A4;margin:0}`) + botón `.noprint` "Imprimir / Guardar PDF". PDF: Ctrl+P, márgenes Ninguno, "Gráficos de fondo" ON.
- Estilo ZARIS: tokens DS inline + `<link href="../design-system/fonts/fonts.css">` (funciona porque `folletos/` está a la misma profundidad que `docs/`). Space Grotesk + Fraunces itálica para frases. Sin emojis (§13).
- Fotos de stock: Unsplash por URL (`images.unsplash.com/photo-<id>?auto=format&fit=crop&w=1400&q=70`). **Verificar cada ID con HEAD 200 ANTES de embeber, y el CONTENIDO mirándolo en el browser** (un ID de memoria resultó ser una sala de servidores en vez de una persona). Requieren internet al abrir/imprimir.
- Frases vendedoras = stickers `.stk` naranjas (`--zaris-orange`) rotados ~-2.4°, con bajada serif itálica, superpuestos a la foto. Variante blanca `.stk--light`.
- Chequear desborde por página antes de cerrar: `[...document.querySelectorAll('.page')].filter(p=>p.scrollHeight>p.clientHeight)` debe dar vacío.

Relacionado: [[reference_gh_pages_publica_todo_lo_commiteado]], [[feedback_verificar_forms_navegando_mandatorio]].
