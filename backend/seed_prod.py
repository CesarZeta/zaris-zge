"""Seed demo data into Railway prod (idempotent — skips populated tables)."""
import asyncio
import httpx

BASE = "https://zaris-api-production-bf0b.up.railway.app/api/v1/admin"
LOGIN_URL = "https://zaris-api-production-bf0b.up.railway.app/api/v1/auth/login"
CREDENTIALS = {"email": "administrativo@municipio.gob.ar", "password": "123456"}

SEED_DATA = {
    "area": [
        {"nombre": "Gobierno", "descripcion": "Area de gobierno municipal"},
        {"nombre": "Hacienda", "descripcion": "Administracion financiera"},
        {"nombre": "Obras Publicas", "descripcion": "Infraestructura y obras"},
        {"nombre": "Desarrollo Social", "descripcion": "Programas sociales"},
        {"nombre": "Salud", "descripcion": "Salud publica municipal"},
    ],
    "cargos": [
        {"nombre": "Director", "descripcion": "Director de area o secretaria"},
        {"nombre": "Coordinador", "descripcion": "Coordinador de equipo o proyecto"},
        {"nombre": "Tecnico", "descripcion": "Profesional tecnico especializado"},
        {"nombre": "Administrativo", "descripcion": "Personal administrativo"},
        {"nombre": "Operario", "descripcion": "Personal operativo"},
    ],
    "tipo_usuario": [
        {"nombre": "Administrativo", "descripcion": "Usuario con acceso administrativo general"},
        {"nombre": "Tecnico", "descripcion": "Usuario tecnico especializado"},
        {"nombre": "Supervisor", "descripcion": "Usuario con rol de supervision"},
        {"nombre": "Consultor", "descripcion": "Usuario con acceso de solo lectura"},
    ],
    "reclamos_area": [
        {"nombre": "Espacios Verdes"},
        {"nombre": "Transito y Vialidad"},
        {"nombre": "Obras Publicas"},
        {"nombre": "Higiene Urbana"},
        {"nombre": "Iluminacion"},
    ],
    "reclamos_subarea": [
        {"nombre": "Plazas y Parques", "id_area": 1},
        {"nombre": "Arbolado Publico", "id_area": 1},
        {"nombre": "Semaforos", "id_area": 2},
        {"nombre": "Calzada y Veredas", "id_area": 2},
        {"nombre": "Corte de servicio", "id_area": 3},
        {"nombre": "Rotura de calzada", "id_area": 3},
        {"nombre": "Residuos en via publica", "id_area": 4},
        {"nombre": "Luminarias apagadas", "id_area": 5},
    ],
    "estado_reclamo": [
        {"nombre": "Ingresado", "descripcion": "Reclamo recibido, pendiente de revision", "color": "#6B7280", "es_final": False, "orden": 1},
        {"nombre": "En revision", "descripcion": "Reclamo bajo analisis", "color": "#D97706", "es_final": False, "orden": 2},
        {"nombre": "En gestion", "descripcion": "Reclamo en proceso de resolucion", "color": "#2563EB", "es_final": False, "orden": 3},
        {"nombre": "Resuelto", "descripcion": "Reclamo atendido satisfactoriamente", "color": "#16A34A", "es_final": True, "orden": 4},
        {"nombre": "Rechazado", "descripcion": "Reclamo no procedente", "color": "#DC2626", "es_final": True, "orden": 5},
        {"nombre": "Cerrado", "descripcion": "Reclamo cerrado administrativamente", "color": "#374151", "es_final": True, "orden": 6},
    ],
    "areas": [
        {"nombre": "Secretaria de Gobierno", "descripcion": "Coordinacion general del ejecutivo municipal"},
        {"nombre": "Secretaria de Hacienda", "descripcion": "Administracion financiera y presupuestaria"},
        {"nombre": "Secretaria de Obras Publicas", "descripcion": "Planificacion y ejecucion de infraestructura"},
        {"nombre": "Secretaria de Desarrollo Social", "descripcion": "Programas sociales y asistencia ciudadana"},
        {"nombre": "Secretaria de Salud", "descripcion": "Atencion primaria y politicas sanitarias"},
        {"nombre": "Secretaria de Cultura", "descripcion": "Gestion cultural y patrimonio municipal"},
    ],
    "lugares_atencion": [
        {"nombre": "Casa Municipal", "direccion": "Av. San Martin 100", "es_atencion": True, "capacidad_servicios": 10, "id_area": 1},
        {"nombre": "Delegacion Norte", "direccion": "Av. Belgrano 540", "es_atencion": True, "capacidad_servicios": 4, "id_area": 1},
        {"nombre": "Delegacion Sur", "direccion": "Ruta 5 km 12", "es_atencion": True, "capacidad_servicios": 3, "id_area": 1},
        {"nombre": "Centro de Salud N1", "direccion": "Mitre 230", "es_atencion": True, "capacidad_servicios": 6, "id_area": 5},
        {"nombre": "Centro Cultural Municipal", "direccion": "Rivadavia 88", "es_atencion": True, "capacidad_servicios": 2, "id_area": 6},
    ],
    "agenda_clase": [
        {"nombre": "Turno Ventanilla", "descripcion": "Atencion presencial", "visible_ciudadano": True, "requiere_rrhh": True, "requiere_servicio": True, "requiere_lugar": True, "duracion_slot_minutos": 20, "id_area": 1},
        {"nombre": "Inspeccion Tecnica", "descripcion": "Visita tecnica a domicilio", "visible_ciudadano": False, "requiere_rrhh": True, "requiere_servicio": False, "requiere_lugar": False, "duracion_slot_minutos": 60, "id_area": 3},
        {"nombre": "Consulta Medica", "descripcion": "Atencion en centro de salud", "visible_ciudadano": True, "requiere_rrhh": True, "requiere_servicio": True, "requiere_lugar": True, "duracion_slot_minutos": 15, "id_area": 5},
        {"nombre": "Tramite Documental", "descripcion": "Presentacion y seguimiento de documentacion", "visible_ciudadano": True, "requiere_rrhh": True, "requiere_servicio": True, "requiere_lugar": True, "duracion_slot_minutos": 30, "id_area": 1},
    ],
    "agenda_feriado": [
        {"fecha": "2026-01-01", "descripcion": "Anio Nuevo", "ambito": "NACIONAL"},
        {"fecha": "2026-03-24", "descripcion": "Dia de la Memoria", "ambito": "NACIONAL"},
        {"fecha": "2026-04-02", "descripcion": "Dia del Veterano", "ambito": "NACIONAL"},
        {"fecha": "2026-05-01", "descripcion": "Dia del Trabajo", "ambito": "NACIONAL"},
        {"fecha": "2026-05-25", "descripcion": "Dia de la Patria", "ambito": "NACIONAL"},
        {"fecha": "2026-07-09", "descripcion": "Dia de la Independencia", "ambito": "NACIONAL"},
        {"fecha": "2026-08-17", "descripcion": "Paso a la Inmortalidad del Gral. San Martin", "ambito": "NACIONAL"},
        {"fecha": "2026-10-12", "descripcion": "Dia de la Diversidad Cultural", "ambito": "NACIONAL"},
        {"fecha": "2026-11-20", "descripcion": "Dia de la Soberania Nacional", "ambito": "NACIONAL"},
        {"fecha": "2026-12-08", "descripcion": "Inmaculada Concepcion", "ambito": "NACIONAL"},
        {"fecha": "2026-12-25", "descripcion": "Navidad", "ambito": "NACIONAL"},
        {"fecha": "2026-06-15", "descripcion": "Aniversario del Municipio", "ambito": "MUNICIPAL"},
    ],
    "servicios": [
        {"nombre": "Atencion al Vecino", "descripcion": "Servicio de atencion presencial general", "id_area": 1, "id_usuario_responsable": None, "capacidad_agentes": 5, "dias_semana": "lunes,martes,miercoles,jueves,viernes", "hora_inicio": "08:00", "hora_fin": "14:00"},
        {"nombre": "Tramites en Linea", "descripcion": "Gestion de tramites via plataforma digital", "id_area": 1, "id_usuario_responsable": None, "capacidad_agentes": 2, "dias_semana": "lunes,martes,miercoles,jueves,viernes", "hora_inicio": "00:00", "hora_fin": "23:59"},
        {"nombre": "Mesa de Entradas", "descripcion": "Recepcion y derivacion de documentacion", "id_area": 1, "id_usuario_responsable": None, "capacidad_agentes": 3, "dias_semana": "lunes,martes,miercoles,jueves,viernes", "hora_inicio": "08:00", "hora_fin": "13:00"},
        {"nombre": "Atencion Medica Primaria", "descripcion": "Consultas y controles en centros de salud", "id_area": 5, "id_usuario_responsable": None, "capacidad_agentes": 8, "dias_semana": "lunes,martes,miercoles,jueves,viernes", "hora_inicio": "07:00", "hora_fin": "19:00"},
        {"nombre": "Habilitaciones Comerciales", "descripcion": "Tramites de habilitacion y renovacion de comercios", "id_area": 2, "id_usuario_responsable": None, "capacidad_agentes": 4, "dias_semana": "lunes,martes,miercoles,jueves,viernes", "hora_inicio": "08:30", "hora_fin": "13:30"},
    ],
    "actividades": [
        {"codigo_clae": "4711", "descripcion": "Venta al por menor en almacenes", "categoria_tasa": "A"},
        {"codigo_clae": "4751", "descripcion": "Venta al por menor de telas y articulos de merceria", "categoria_tasa": "B"},
        {"codigo_clae": "5610", "descripcion": "Restaurantes y servicios de comidas", "categoria_tasa": "A"},
        {"codigo_clae": "5630", "descripcion": "Elaboracion y venta de bebidas", "categoria_tasa": "A"},
        {"codigo_clae": "6201", "descripcion": "Programacion informatica", "categoria_tasa": "B"},
        {"codigo_clae": "7010", "descripcion": "Actividades de casas centrales", "categoria_tasa": "C"},
        {"codigo_clae": "8610", "descripcion": "Servicios de hospitales y clinicas", "categoria_tasa": "C"},
        {"codigo_clae": "8621", "descripcion": "Servicios de medicos y odontologos", "categoria_tasa": "B"},
        {"codigo_clae": "9313", "descripcion": "Servicios de acondicionamiento fisico (gimnasios)", "categoria_tasa": "A"},
    ],
    "tipo_representacion": [
        {"tipo": "Titular", "descripcion": "Propietario o titular del bien o actividad"},
        {"tipo": "Apoderado", "descripcion": "Persona con poder notarial"},
        {"tipo": "Gestor", "descripcion": "Profesional habilitado para gestionar tramites"},
        {"tipo": "Heredero", "descripcion": "Sucesor legal del titular fallecido"},
        {"tipo": "Representante Legal", "descripcion": "Representante legal de persona juridica"},
    ],
    "nacionalidades": [
        {"pais": "Argentina", "region": "America del Sur"},
        {"pais": "Brasil", "region": "America del Sur"},
        {"pais": "Uruguay", "region": "America del Sur"},
        {"pais": "Paraguay", "region": "America del Sur"},
        {"pais": "Bolivia", "region": "America del Sur"},
        {"pais": "Chile", "region": "America del Sur"},
        {"pais": "Peru", "region": "America del Sur"},
        {"pais": "Colombia", "region": "America del Sur"},
        {"pais": "Venezuela", "region": "America del Sur"},
        {"pais": "Espania", "region": "Europa"},
        {"pais": "Italia", "region": "Europa"},
        {"pais": "Portugal", "region": "Europa"},
        {"pais": "China", "region": "Asia"},
        {"pais": "Corea del Sur", "region": "Asia"},
        {"pais": "Otra", "region": "Otro"},
    ],
}


async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(LOGIN_URL, json=CREDENTIALS)
        r.raise_for_status()
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"Login OK — Railway prod")

        for tabla, registros in SEED_DATA.items():
            r = await client.get(f"{BASE}/{tabla}", headers=headers)
            current = r.json() if r.status_code == 200 else []
            if isinstance(current, list) and len(current) > 0:
                print(f"[SKIP] {tabla}: ya tiene {len(current)} registros")
                continue

            print(f"[SEED] {tabla}: insertando {len(registros)} registros...")
            ok = 0
            for rec in registros:
                r = await client.post(f"{BASE}/{tabla}", headers=headers, json=rec)
                if r.status_code in (200, 201):
                    ok += 1
                else:
                    print(f"  ERROR {tabla}: {r.status_code} — {r.text[:120]}")
            print(f"  -> {ok}/{len(registros)} OK")

        print("\nSeed prod completado.")


if __name__ == "__main__":
    asyncio.run(main())
