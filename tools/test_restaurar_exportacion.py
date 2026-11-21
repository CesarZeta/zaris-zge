"""Test de las funciones puras de tools/restaurar_exportacion.py (sin base). IT-01 F6.5.

    python tools/test_restaurar_exportacion.py
"""
import io
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import restaurar_exportacion as r  # noqa: E402

fallas = []


def caso(nombre, cond):
    print(("OK   " if cond else "FALLA") + " " + nombre)
    if not cond:
        fallas.append(nombre)


def zip_de(tablas: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for t, filas in tablas.items():
            z.writestr(f"{t}.json", json.dumps(filas))
    return buf.getvalue()


# preparar_filas
f = r.preparar_filas("usuarios", [{"id_usuario": 1, "password_hash": None}, {"id_usuario": 2}], "$2b$x")
caso("usuarios_reciben_el_hash", [x["password_hash"] for x in f] == ["$2b$x", "$2b$x"])
caso("sin_secreto_no_se_cargan", r.preparar_filas("usuario_invitacion", [{"a": 1}], "h") is None)
caso("otras_tablas_sin_cambios", r.preparar_filas("reclamos", [{"id_reclamo": 3}], "h") == [{"id_reclamo": 3}])
f = r.preparar_filas("municipios", [{"id_municipio": 1}, {"id_municipio": 2}], "h", id_municipio=2)
caso("municipios_solo_el_propio", f == [{"id_municipio": 2}])

# referencias_a_usuarios
post = """
ALTER TABLE ONLY public.reclamos
    ADD CONSTRAINT reclamos_id_usuario_alta_fkey FOREIGN KEY (id_usuario_alta) REFERENCES public.usuarios(id_usuario) ON DELETE SET NULL;
ALTER TABLE ONLY public.turno_llamado
    ADD CONSTRAINT x_fkey FOREIGN KEY (id_usuario_llama) REFERENCES public.usuarios(id_usuario);
ALTER TABLE ONLY public.reclamos
    ADD CONSTRAINT reclamos_tipo_fkey FOREIGN KEY (id_tipo_reclamo) REFERENCES public.tipo_reclamo(id_tipo_reclamo);
ALTER TABLE ONLY public.ot
    ADD CONSTRAINT ot_comp_fkey FOREIGN KEY (id_municipio, id_usuario) REFERENCES public.usuarios(id_municipio, id_usuario);
"""
caso("referencias_simples_a_usuarios",
     r.referencias_a_usuarios(post) == [("reclamos", "id_usuario_alta"), ("turno_llamado", "id_usuario_llama")])

# municipio_del_zip
caso("municipio_del_zip", r.municipio_del_zip(zip_de({"reclamos": [{"id_municipio": 3}], "area": [{"id_municipio": 3}],
                                                       "vacia": []})) == 3)
try:
    r.municipio_del_zip(zip_de({"reclamos": [{"id_municipio": 3}], "area": [{"id_municipio": 4}]}))
    caso("zip_con_dos_municipios_falla", False)
except ValueError:
    caso("zip_con_dos_municipios_falla", True)

# sin_clave
caso("url_sin_clave", r.sin_clave("postgresql://u:secreta@h:5432/db") == "postgresql://u@h:5432/db")
caso("url_sin_clave_sin_usuario", r.sin_clave("postgresql://h/db") == "postgresql://h/db")

print(f"\n{'FALLARON: ' + ', '.join(fallas) if fallas else 'todo en verde'}")
sys.exit(1 if fallas else 0)
