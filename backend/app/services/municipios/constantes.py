"""
Constantes de IT-01 F4+F5 (PLAN_MULTI_MUNICIPIO_F4_F5.md, «Restricciones globales»).
Los estados, grupos y acciones tienen su espejo en los CHECK de las migs 130 y 130b.
"""
ESTADOS = ("puesta_en_marcha", "produccion", "demo", "modelo", "baja")
# Login de funcionarios y vecinos, páginas públicas y procesos programados.
ESTADOS_OPERABLES = frozenset({"puesta_en_marcha", "produccion", "demo"})
# Además del estado, el vaciado exige municipios.fue_produccion = false.
ESTADOS_VACIABLES = frozenset({"puesta_en_marcha", "demo"})

GRUPOS = ("operativo", "contactos", "maestros", "usuarios", "configuracion")

# Módulos que no se deshabilitan: el municipio no funciona sin ellos.
MODULOS_FIJOS = frozenset({"usuarios", "admin_tablas", "padrones", "municipios"})
# Habilitar la clave exige sus valores; deshabilitar un valor exige deshabilitar antes la clave.
# La Guardia vive dentro de `turnos` y además exige `emergencias`: se controla en el servicio.
DEPENDENCIAS_MODULOS: dict[str, frozenset[str]] = {
    "turnos": frozenset({"agenda"}),
    "entradas": frozenset({"agenda"}),
    "ot_supervisor": frozenset({"reclamos"}),
    "ot_agente": frozenset({"reclamos"}),
    "ot_auditoria": frozenset({"reclamos"}),
    "agentes_gestion": frozenset({"padrones"}),
}

INVITACION_HORAS = 72
EXPORTACION_RETENCION_DIAS = 90
TOPE_AVISO = 0.9

# El mismo patrón que _PATRON_HOST de app/core/municipio.py y tools/dominios_municipio.py.
PATRON_SUBDOMINIO = r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
SUBDOMINIOS_RESERVADOS = frozenset({"www", "api", "zge", "vecinos", "agentes", "admin", "app", "mail",
                                    "soporte", "status", "demo", "modelo"})
# Código corto de un municipio nuevo: 4 letras (César, 2026-10-27). municipios.codigo_corto es VARCHAR(4)
# y los números (REC-<código>-AAAA-NNNNNN) VARCHAR(24) desde la mig 131; San Andrés conserva SAN.
CODIGO_CORTO_LARGO = 4
PATRON_CODIGO_CORTO = rf"[A-Z]{{{CODIGO_CORTO_LARGO}}}"
