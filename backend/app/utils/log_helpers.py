# -*- coding: utf-8 -*-
"""
Helpers de sanitización para logging.
Centraliza enmascaramiento de PII (Personal Identifiable Information).
"""


def mask_email(email: str | None) -> str:
    """
    Enmascara una dirección de email para logging seguro.

    Reglas:
    - None o "" → "(empty)"
    - Sin "@" → "***" (formato inválido, no se loguea el contenido)
    - Con "@": <primer_char_usuario>***@<dominio_completo>
      - Usuario de 1 char → "*@dominio"
      - Usuario de 2 chars → "a*@dominio"
      - Usuario de 3+ chars → "a***@dominio"

    El número de asteriscos es FIJO (3 para 3+ chars) para no leakear longitud.

    Ejemplos:
        mask_email("juan@correo.gob.ar")       → "j***@correo.gob.ar"
        mask_email("a@correo.gob.ar")          → "*@correo.gob.ar"
        mask_email("ab@correo.gob.ar")         → "a*@correo.gob.ar"
        mask_email("juan.perez@gmail.com")     → "j***@gmail.com"
        mask_email("")                         → "(empty)"
        mask_email(None)                       → "(empty)"
        mask_email("sin-arroba")               → "***"
    """
    if not email:
        return "(empty)"

    if "@" not in email:
        return "***"

    usuario, _, dominio = email.partition("@")

    if not usuario or not dominio:
        return "***"

    if len(usuario) == 1:
        return f"*@{dominio}"
    if len(usuario) == 2:
        return f"{usuario[0]}*@{dominio}"
    return f"{usuario[0]}***@{dominio}"
