"""Smoke test del helper mask_email — no es pytest, solo asserts."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.utils.log_helpers import mask_email

cases = [
    ("juan@correo.gob.ar",       "j***@correo.gob.ar"),
    ("a@correo.gob.ar",          "*@correo.gob.ar"),
    ("ab@correo.gob.ar",         "a*@correo.gob.ar"),
    ("juan.perez@gmail.com",     "j***@gmail.com"),
    ("",                         "(empty)"),
    (None,                       "(empty)"),
    ("sin-arroba",               "***"),
    ("@dominio.com",             "***"),
    ("usuario@",                 "***"),
]

for input_val, expected in cases:
    actual = mask_email(input_val)
    status = "OK" if actual == expected else "FAIL"
    print(f"[{status}]  mask_email({input_val!r}) = {actual!r} (esperado {expected!r})")
    assert actual == expected, f"FAIL: {input_val!r} -> {actual!r}, esperaba {expected!r}"

print("\nTodos los tests pasaron.")
