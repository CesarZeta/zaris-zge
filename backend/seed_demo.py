"""Seed demo data for empty admin tables."""
import asyncio
import json
import os
import sys

import httpx

BASE = "http://127.0.0.1:8000/api/v1/admin"
LOGIN_URL = "http://127.0.0.1:8000/api/v1/auth/login"
CREDENTIALS = {"email": "administrativo@municipio.gob.ar", "password": "123456"}

SEED_DATA = {
    "reclamos_area": [
        {"nombre": "Espacios Verdes"},
        {"nombre": "Tránsito y Vialidad"},
        {"nombre": "Obras Públicas"},
        {"nombre": "Higiene Urbana"},
        {"nombre": "Iluminación"},
    ],
    "reclamos_subarea": [
        {"nombre": "Plazas y Parques", "id_area": 1},
        {"nombre": "Arbolado Público", "id_area": 1},
        {"nombre": "Semáforos", "id_area": 2},
        {"nombre": "Calzada y Veredas", "id_area": 2},
        {"nombre": "Corte de servicio", "id_area": 3},
        {"nombre": "Rotura de calzada", "id_area": 3},
        {"nombre": "Residuos en vía pública", "id_area": 4},
        {"nombre": "Luminarias apagadas", "id_area": 5},
    ],
    "estado_reclamo": [
        {"nombre": "Ingresado", "descripcion": "Reclamo recibido, pendiente de revisión", "color": "#6B7280", "es_final": False, "orden": 1},
        {"nombre": "En revisión", "descripcion": "Reclamo bajo análisis por el área responsable", "color": "#D97706", "es_final": False, "orden": 2},
        {"nombre": "En gestión", "descripcion": "Reclamo en proceso de resolución", "color": "#2563EB", "es_final": False, "orden": 3},
        {"nombre": "Resuelto", "descripcion": "Reclamo atendido satisfactoriamente", "color": "#16A34A", "es_final": True, "orden": 4},
        {"nombre": "Rechazado", "descripcion": "Reclamo no procedente o fuera del alcance municipal", "color": "#DC2626", "es_final": True, "orden": 5},
        {"nombre": "Cerrado", "descripcion": "Reclamo cerrado administrativamente", "color": "#374151", "es_final": True, "orden": 6},
    ],
    "areas": [
        {"nombre": "Secretaría de Gobierno", "descripcion": "Coordinación general del ejecutivo municipal"},
        {"nombre": "Secretaría de Hacienda", "descripcion": "Administración financiera y presupuestaria"},
        {"nombre": "Secretaría de Obras Públicas", "descripcion": "Planificación y ejecución de infraestructura"},
        {"nombre": "Secretaría de Desarrollo Social", "descripcion": "Programas sociales y asistencia ciudadana"},
        {"nombre": "Secretaría de Salud", "descripcion": "Atención primaria y políticas sanitarias"},
        {"nombre": "Secretaría de Cultura", "descripcion": "Gestión cultural y patrimonio municipal"},
    ],
    "lugares_atencion": [
        {"nombre": "Casa Municipal", "direccion": "Av. San Martín 100", "es_atencion": True, "capacidad_servicios": 10, "id_area": 1},
        {"nombre": "Delegación Norte", "direccion": "Av. Belgrano 540", "es_atencion": True, "capacidad_servicios": 4, "id_area": 1},
        {"nombre": "Delegación Sur", "direccion": "Ruta 5 km 12", "es_atencion": True, "capacidad_servicios": 3, "id_area": 1},
        {"nombre": "Centro de Salud Nº 1", "direccion": "Mitre 230", "es_atencion": True, "capacidad_servicios": 6, "id_area": 5},
        {"nombre": "Centro Cultural Municipal", "direccion": "Rivadavia 88", "es_atencion": True, "capacidad_servicios": 2, "id_area": 6},
    ],
    "agenda_clase": [
        {"nombre": "Turno Ventanilla", "descripcion": "Atención presencial en dependencias municipales", "visible_ciudadano": True, "requiere_rrhh": True, "requiere_servicio": True, "requiere_lugar": True, "duracion_slot_minutos": 20, "id_area": 1},
        {"nombre": "Inspección Técnica", "descripcion": "Visita técnica a domicilio o local", "visible_ciudadano": False, "requiere_rrhh": True, "requiere_servicio": False, "requiere_lugar": False, "duracion_slot_minutos": 60, "id_area": 3},
        {"nombre": "Consulta Médica", "descripcion": "Atención en centro de salud municipal", "visible_ciudadano": True, "requiere_rrhh": True, "requiere_servicio": True, "requiere_lugar": True, "duracion_slot_minutos": 15, "id_area": 5},
        {"nombre": "Trámite Documental", "descripcion": "Presentación y seguimiento de documentación", "visible_ciudadano": True, "requiere_rrhh": True, "requiere_servicio": True, "requiere_lugar": True, "duracion_slot_minutos": 30, "id_area": 1},
    ],
    "agenda_feriado": [
        {"fecha": "2026-01-01", "descripcion": "Año Nuevo", "ambito": "NACIONAL"},
        {"fecha": "2026-03-24", "descripcion": "Día Nacional de la Memoria por la Verdad y la Justicia", "ambito": "NACIONAL"},
        {"fecha": "2026-04-02", "descripcion": "Día del Veterano y los Caídos en Malvinas", "ambito": "NACIONAL"},
        {"fecha": "2026-05-01", "descripcion": "Día del Trabajo", "ambito": "NACIONAL"},
        {"fecha": "2026-05-25", "descripcion": "Día de la Patria", "ambito": "NACIONAL"},
        {"fecha": "2026-07-09", "descripcion": "Día de la Independencia", "ambito": "NACIONAL"},
        {"fecha": "2026-08-17", "descripcion": "Paso a la Inmortalidad del Gral. San Martín", "ambito": "NACIONAL"},
        {"fecha": "2026-10-12", "descripcion": "Día del Respeto a la Diversidad Cultural", "ambito": "NACIONAL"},
        {"fecha": "2026-11-20", "descripcion": "Día de la Soberanía Nacional", "ambito": "NACIONAL"},
        {"fecha": "2026-12-08", "descripcion": "Inmaculada Concepción de María", "ambito": "NACIONAL"},
        {"fecha": "2026-12-25", "descripcion": "Navidad", "ambito": "NACIONAL"},
        {"fecha": "2026-06-15", "descripcion": "Aniversario del Municipio", "ambito": "MUNICIPAL"},
    ],
    "servicios": [
        {"nombre": "Atención al Vecino", "descripcion": "Servicio de atención presencial general", "id_area": 1, "id_usuario_responsable": None, "capacidad_agentes": 5, "dias_semana": "lunes,martes,miércoles,jueves,viernes", "hora_inicio": "08:00", "hora_fin": "14:00"},
        {"nombre": "Trámites en Línea", "descripcion": "Gestión de trámites vía plataforma digital", "id_area": 1, "id_usuario_responsable": None, "capacidad_agentes": 2, "dias_semana": "lunes,martes,miércoles,jueves,viernes", "hora_inicio": "00:00", "hora_fin": "23:59"},
        {"nombre": "Mesa de Entradas", "descripcion": "Recepción y derivación de documentación", "id_area": 1, "id_usuario_responsable": None, "capacidad_agentes": 3, "dias_semana": "lunes,martes,miércoles,jueves,viernes", "hora_inicio": "08:00", "hora_fin": "13:00"},
        {"nombre": "Atención Médica Primaria", "descripcion": "Consultas y controles en centros de salud", "id_area": 5, "id_usuario_responsable": None, "capacidad_agentes": 8, "dias_semana": "lunes,martes,miércoles,jueves,viernes", "hora_inicio": "07:00", "hora_fin": "19:00"},
        {"nombre": "Habilitaciones Comerciales", "descripcion": "Trámites de habilitación y renovación de comercios", "id_area": 2, "id_usuario_responsable": None, "capacidad_agentes": 4, "dias_semana": "lunes,martes,miércoles,jueves,viernes", "hora_inicio": "08:30", "hora_fin": "13:30"},
    ],
    "actividades": [
        {"codigo_clae": "4711", "descripcion": "Venta al por menor en almacenes con predominio de prod. alimenticios", "categoria_tasa": "A"},
        {"codigo_clae": "4751", "descripcion": "Venta al por menor de telas y artículos de mercería", "categoria_tasa": "B"},
        {"codigo_clae": "5610", "descripcion": "Restaurantes y servicios de comidas", "categoria_tasa": "A"},
        {"codigo_clae": "5630", "descripcion": "Elaboración y venta de bebidas", "categoria_tasa": "A"},
        {"codigo_clae": "6201", "descripcion": "Programación informática", "categoria_tasa": "B"},
        {"codigo_clae": "7010", "descripcion": "Actividades de casas centrales", "categoria_tasa": "C"},
        {"codigo_clae": "8610", "descripcion": "Servicios de hospitales y clínicas", "categoria_tasa": "C"},
        {"codigo_clae": "8621", "descripcion": "Servicios de médicos y odontólogos", "categoria_tasa": "B"},
        {"codigo_clae": "9313", "descripcion": "Servicios de acondicionamiento físico (gimnasios)", "categoria_tasa": "A"},
    ],
    "tipo_representacion": [
        {"tipo": "Titular", "descripcion": "Propietario o titular del bien o actividad"},
        {"tipo": "Apoderado", "descripcion": "Persona con poder notarial para actuar en nombre del titular"},
        {"tipo": "Gestor", "descripcion": "Profesional habilitado para gestionar trámites"},
        {"tipo": "Heredero", "descripcion": "Sucesor legal del titular fallecido"},
        {"tipo": "Representante Legal", "descripcion": "Representante legal de persona jurídica"},
    ],
    "nacionalidades": [
        {"pais": "Argentina", "region": "América del Sur"},
        {"pais": "Brasil", "region": "América del Sur"},
        {"pais": "Uruguay", "region": "América del Sur"},
        {"pais": "Paraguay", "region": "América del Sur"},
        {"pais": "Bolivia", "region": "América del Sur"},
        {"pais": "Chile", "region": "América del Sur"},
        {"pais": "Perú", "region": "América del Sur"},
        {"pais": "Colombia", "region": "América del Sur"},
        {"pais": "Venezuela", "region": "América del Sur"},
        {"pais": "España", "region": "Europa"},
        {"pais": "Italia", "region": "Europa"},
        {"pais": "Portugal", "region": "Europa"},
        {"pais": "China", "region": "Asia"},
        {"pais": "Corea del Sur", "region": "Asia"},
        {"pais": "Otra", "region": "Otro"},
    ],
}


async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        # Login
        r = await client.post(LOGIN_URL, json=CREDENTIALS)
        r.raise_for_status()
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"Login OK — token: {token[:30]}...")

        for tabla, registros in SEED_DATA.items():
            # Check current count
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

        print("\nSeed completado.")


if __name__ == "__main__":
    asyncio.run(main())
