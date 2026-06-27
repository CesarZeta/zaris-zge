---
name: feedback_verificar_superficies_externas_y_recuerdo_usuario
description: "Algunas verdades viven solo en superficies externas que mis herramientas NO alcanzan (dashboard Cloudflare/Vercel, bandeja de mail, paneles de terceros) y en el recuerdo del usuario sobre etapas previas que no dejaron rastro en git. Verificar contra código/DB no basta; pedir/mirar la superficie y tratar el recuerdo del usuario como evidencia válida."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: db12f794-d376-425b-9339-953265cd6368
---

`feedback_verificar_siempre_antes_de_opinar` dice "verificar antes de opinar" contra DB/código/runtime/navegador. Esta es una cara que faltaba: **hay verdades que NO están en ninguna de mis herramientas** — viven en paneles de terceros (dashboard de Cloudflare, Vercel, Railway, la bandeja de Gmail del usuario) o en cosas que el usuario configuró fuera del repo. Verificar solo contra git/código/DB y concluir "no existe" es un error: lo que no veo no es lo que no existe.

**Caso real (2026-06-01, integración Cloudflare):** me equivoqué 3 veces seguidas, todas por la misma raíz:
1. Afirmé "no existe ningún proyecto Cloudflare" tras grepear el repo — pero SÍ existía un Worker real (`zaris-frontend`) que vivía en el dashboard de Cloudflare, NO en el git. Un Worker de assets no necesariamente deja archivos en el repo.
2. Mandé al usuario a la página equivocada de GitHub (settings del repo) cuando la app estaba a nivel cuenta (otra URL).
3. Dije "yo nunca propuse Cloudflare" porque no había rastro en git/memorias — pero el usuario lo recordaba con certeza (fue una etapa temprana del correo, mar/abr, que se reemplazó por Resend y no dejó commits porque el Worker vivía en Cloudflare).

En las 3 el usuario me frenó con "fijate bien" / "verificá" / "yo recuerdo perfectamente" y tenía razón.

**Why:** mis herramientas (grep, git, execute_sql, el navegador apuntado a UNA url) tienen un alcance finito. Confundir "no aparece en lo que puedo ver" con "no existe" lleva a recomendaciones peligrosas (ej. casi recomiendo desinstalar/borrar algo creyéndolo inexistente). Y el recuerdo del usuario sobre decisiones/etapas previas es **evidencia de primera mano** sobre cosas que pueden no haber dejado huella en el repo — no es algo a refutar con "no encuentro registro".

**How to apply:**
- Cuando el tema toca un servicio de terceros (Cloudflare, Vercel, Railway, Resend, GitHub Apps, DNS, mail): NO concluir "no existe / no se usa" solo por grep del repo. La fuente de verdad es el **dashboard del servicio** — pedirle al usuario que lo abra, o medir externamente (ej. headers HTTP para saber quién sirve un dominio: `Server: GitHub.com` vs Cloudflare).
- Si el usuario dice "yo recuerdo que X" y mi git/memoria no lo tiene: **creerle y tratar su recuerdo como dato**, no contradecirlo de plano. Decir "no tengo registro" está bien como aclaración, pero la conclusión operativa no debe depender de que YO lo vea — debe depender de los hechos verificables (que pueden estar fuera de mi alcance).
- Antes de recomendar BORRAR/DESCONECTAR algo de un servicio externo: medir qué depende de eso con una prueba que no requiera mis herramientas internas (un curl de headers, pedir la captura del panel). Lo irreversible exige la superficie real, no la inferencia desde el repo.
- Hermana de [[feedback_el_backend_puede_mentir]] (el artefacto estático miente vs el runtime) y [[feedback_verificar_forms_navegando_mandatorio]] (la interfaz es la realidad). Familia completa: el código/git/DB son hipótesis; el hecho vive en runtime, en la interfaz, en el panel del servicio, o en lo que el usuario presenció.
