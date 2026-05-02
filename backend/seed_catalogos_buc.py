# -*- coding: utf-8 -*-
"""
Seed de catálogos BUC (Base Única de Ciudadanos) — ZARIS Gestión Estatal.

Inserta los datos maestros en las tablas:
  - nacionalidades        (65 registros)
  - tipo_representacion  (3 registros)
  - actividades           (25 registros — nomenclador CLAE simplificado)

Idempotente: usar ON CONFLICT (id) DO NOTHING para permitir re-ejecuciones.

Uso:
    cd backend/
    python seed_catalogos_buc.py

Requisitos previos:
  - Las tablas destino deben existir en Supabase.
  - RLS debe estar DESACTIVADO en las tablas destino (son catálogos internos),
    o bien el rol postgres debe tener policies de INSERT permisivas.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.core.database import AsyncSessionLocal

NACIONALIDADES = [
    (1, "Afganistan", "Otros"),
    (2, "Algeria", "Otros"),
    (3, "Alemania", "Europa"),
    (4, "Argentina", "America"),
    (5, "Australia", "Otros"),
    (6, "Austria", "Europa"),
    (7, "Belgica", "Europa"),
    (8, "Bolivia", "America"),
    (9, "Brasil", "America"),
    (10, "Canada", "America"),
    (11, "Chile", "America"),
    (12, "China", "Otros"),
    (13, "Colombia", "America"),
    (14, "Corea del Sur", "Otros"),
    (15, "Costa Rica", "America"),
    (16, "Croacia", "Europa"),
    (17, "Cuba", "America"),
    (18, "Dinamarca", "Europa"),
    (19, "Ecuador", "America"),
    (20, "Egipto", "Otros"),
    (21, "El Salvador", "America"),
    (22, "Espana", "Europa"),
    (23, "Estados Unidos", "America"),
    (24, "Filipinas", "Otros"),
    (25, "Finlandia", "Europa"),
    (26, "Francia", "Europa"),
    (27, "Grecia", "Europa"),
    (28, "Guatemala", "America"),
    (29, "Haiti", "America"),
    (30, "Honduras", "America"),
    (31, "Hungria", "Europa"),
    (32, "India", "Otros"),
    (33, "Iran", "Otros"),
    (34, "Irlanda", "Europa"),
    (35, "Israel", "Otros"),
    (36, "Italia", "Europa"),
    (37, "Jamaica", "America"),
    (38, "Japon", "Otros"),
    (39, "Marruecos", "Otros"),
    (40, "Mexico", "America"),
    (41, "Nicaragua", "America"),
    (42, "Nigeria", "Otros"),
    (43, "Noruega", "Europa"),
    (44, "Paises Bajos", "Europa"),
    (45, "Pakistan", "Otros"),
    (46, "Panama", "America"),
    (47, "Paraguay", "America"),
    (48, "Peru", "America"),
    (49, "Polonia", "Europa"),
    (50, "Portugal", "Europa"),
    (51, "Puerto Rico", "America"),
    (52, "Republica Dominicana", "America"),
    (53, "Rumania", "Europa"),
    (54, "Rusia", "Europa"),
    (55, "Senegal", "Otros"),
    (56, "Siria", "Otros"),
    (57, "Sudafrica", "Otros"),
    (58, "Suecia", "Europa"),
    (59, "Suiza", "Europa"),
    (60, "Tailandia", "Otros"),
    (61, "Trinidad y Tobago", "America"),
    (62, "Turquia", "Otros"),
    (63, "Uruguay", "America"),
    (64, "Venezuela", "America"),
    (65, "Vietnam", "Otros"),
]

TIPO_REPRESENTACION = [
    (1, "Representante Legal", "Titular o socio con maxima autoridad juridica y responsabilidad penal/tributaria total."),
    (2, "Apoderado Especial",  "Rol gerencial con poder notarial limitado para gestionar y aprobar en areas especificas."),
    (3, "Contacto Autorizado", "Personal operativo para carga de datos y gestiones diarias rutinarias sin poder de decision."),
]

ACTIVIDADES = [
    (1,  471110, "Venta al por menor en almacenes y minimercados", "comercio"),
    (2,  471120, "Venta al por menor en supermercados y hipermercados", "comercio"),
    (3,  472110, "Venta al por menor de productos de panaderia y pasteleria", "comercio"),
    (4,  473000, "Venta al por menor de combustibles para vehiculos", "comercio"),
    (5,  477110, "Venta al por menor de prendas y accesorios de vestir", "comercio"),
    (6,  478100, "Venta al por menor en puestos de feria", "comercio"),
    (7,  561010, "Restaurantes y cantinas", "servicios"),
    (8,  561020, "Servicios de comidas por encargo y otros", "servicios"),
    (9,  562000, "Servicios de catering", "servicios"),
    (10, 551000, "Servicios de hoteleria", "servicios"),
    (11, 611010, "Telefonia fija", "servicios"),
    (12, 620100, "Desarrollo de software y consultoria informatica", "servicios"),
    (13, 641100, "Bancos y entidades financieras", "servicios"),
    (14, 651100, "Seguros de vida", "servicios"),
    (15, 681010, "Alquiler de inmuebles propios", "servicios"),
    (16, 711100, "Actividades de arquitectura e ingenieria", "servicios"),
    (17, 731100, "Publicidad", "servicios"),
    (18, 861000, "Servicios de salud y consultorios", "servicios"),
    (19, 932100, "Gimnasios y actividad fisica", "servicios"),
    (20, 960210, "Peluquerias y salones de belleza", "servicios"),
    (21, 101100, "Produccion y procesamiento de carne", "industria"),
    (22, 102000, "Elaboracion de pescado", "industria"),
    (23, 107100, "Fabricacion de productos de panaderia", "industria"),
    (24, 110100, "Destilacion y rectificacion de bebidas alcoholicas", "industria"),
    (25, 131100, "Preparacion e hilatura de fibras textiles", "industria"),
]


async def seed():
    async with AsyncSessionLocal() as session:
        print("Seeding nacionalidades...", end=" ")
        for id_, pais, region in NACIONALIDADES:
            await session.execute(
                text("INSERT INTO nacionalidades (id, pais, region) VALUES (:id, :pais, :region) ON CONFLICT (id) DO NOTHING"),
                {"id": id_, "pais": pais, "region": region},
            )
        print("OK")

        print("Seeding tipo_representacion...", end=" ")
        for id_, tipo, descripcion in TIPO_REPRESENTACION:
            await session.execute(
                text("INSERT INTO tipo_representacion (id, tipo, descripcion) VALUES (:id, :tipo, :descripcion) ON CONFLICT (id) DO NOTHING"),
                {"id": id_, "tipo": tipo, "descripcion": descripcion},
            )
        print("OK")

        print("Seeding actividades...", end=" ")
        for id_, codigo_clae, descripcion, categoria_tasa in ACTIVIDADES:
            await session.execute(
                text("INSERT INTO actividades (id, codigo_clae, descripcion, categoria_tasa) VALUES (:id, :codigo_clae, :descripcion, :categoria_tasa) ON CONFLICT (id) DO NOTHING"),
                {"id": id_, "codigo_clae": codigo_clae, "descripcion": descripcion, "categoria_tasa": categoria_tasa},
            )
        print("OK")

        await session.commit()
        print("Seed de catalogos BUC completo.")


if __name__ == "__main__":
    asyncio.run(seed())