"""
seed_geo_argentina.py — Seed de provincias, partidos y localidades.

Carga el árbol provincia → partido → localidad para Argentina, con foco en:
- Provincia de Buenos Aires (135 partidos)
- CABA (15 comunas como "partidos")
- Resto de provincias (solo capital + 1-2 ciudades grandes para que el dataset
  sea utilizable sin ser exhaustivo).

Idempotente: usa ON CONFLICT (UPSERT) — se puede correr varias veces sin duplicar.
"""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:145236@127.0.0.1:5432/zaris_dev"
)
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Estructura: { provincia: { partido: [localidades] } }
GEO_DATA: dict[str, dict[str, list[str]]] = {
    "Ciudad Autónoma de Buenos Aires": {
        "Comuna 1": ["Retiro", "San Nicolás", "Puerto Madero", "San Telmo", "Monserrat", "Constitución"],
        "Comuna 2": ["Recoleta"],
        "Comuna 3": ["Balvanera", "San Cristóbal"],
        "Comuna 4": ["La Boca", "Barracas", "Parque Patricios", "Nueva Pompeya"],
        "Comuna 5": ["Almagro", "Boedo"],
        "Comuna 6": ["Caballito"],
        "Comuna 7": ["Flores", "Parque Chacabuco"],
        "Comuna 8": ["Villa Soldati", "Villa Riachuelo", "Villa Lugano"],
        "Comuna 9": ["Liniers", "Mataderos", "Parque Avellaneda"],
        "Comuna 10": ["Villa Real", "Monte Castro", "Versalles", "Floresta", "Vélez Sarsfield", "Villa Luro"],
        "Comuna 11": ["Villa General Mitre", "Villa Devoto", "Villa del Parque", "Villa Santa Rita"],
        "Comuna 12": ["Coghlan", "Saavedra", "Villa Urquiza", "Villa Pueyrredón"],
        "Comuna 13": ["Belgrano", "Núñez", "Colegiales"],
        "Comuna 14": ["Palermo"],
        "Comuna 15": ["Chacarita", "Villa Crespo", "La Paternal", "Villa Ortúzar", "Agronomía", "Parque Chas"],
    },
    "Buenos Aires": {
        "Vicente López": ["Olivos", "Florida", "La Lucila", "Munro", "Vicente López", "Villa Adelina", "Villa Martelli", "Carapachay", "Florida Oeste"],
        "San Isidro": ["San Isidro", "Acassuso", "Beccar", "Boulogne Sur Mer", "Martínez", "Villa Adelina"],
        "Tigre": ["Tigre", "Don Torcuato", "El Talar", "General Pacheco", "Benavídez", "Dique Luján", "Rincón de Milberg", "Ricardo Rojas", "Troncos del Talar"],
        "San Fernando": ["San Fernando", "Victoria", "Virreyes"],
        "Pilar": ["Pilar", "Derqui", "Del Viso", "Manzanares", "Manuel Alberti", "Presidente Derqui", "Villa Astolfi", "Villa Rosa", "Zelaya"],
        "Escobar": ["Belén de Escobar", "Garín", "Ingeniero Maschwitz", "Loma Verde", "Matheu", "Maquinista Savio"],
        "San Miguel": ["San Miguel", "Bella Vista", "Muñiz", "Campo de Mayo", "Santa María"],
        "Malvinas Argentinas": ["Los Polvorines", "Grand Bourg", "Pablo Nogués", "Tortuguitas", "Villa de Mayo", "Tierras Altas", "Ingeniero Adolfo Sourdeaux"],
        "José C. Paz": ["José C. Paz", "Tres de Febrero"],
        "Tres de Febrero": ["Caseros", "Sáenz Peña", "Santos Lugares", "Ciudadela", "Pablo Podestá", "José Ingenieros", "Loma Hermosa", "Churruca", "Villa Bosch", "Villa Raffo", "Martín Coronado", "11 de Septiembre"],
        "Hurlingham": ["Hurlingham", "Villa Tesei", "William Morris"],
        "Ituzaingó": ["Ituzaingó", "Villa Udaondo"],
        "Morón": ["Morón", "El Palomar", "Castelar", "Haedo", "Villa Sarmiento"],
        "La Matanza": ["San Justo", "Ramos Mejía", "Villa Madero", "Tapiales", "Lomas del Mirador", "Aldo Bonzi", "Ciudad Evita", "Rafael Castillo", "Isidro Casanova", "Gregorio de Laferrere", "González Catán", "Virrey del Pino", "20 de Junio"],
        "Lomas de Zamora": ["Lomas de Zamora", "Banfield", "Temperley", "Turdera", "Llavallol", "Villa Centenario", "Villa Fiorito", "Ingeniero Budge"],
        "Lanús": ["Lanús", "Lanús Oeste", "Remedios de Escalada", "Monte Chingolo", "Valentín Alsina", "Gerli"],
        "Avellaneda": ["Avellaneda", "Sarandí", "Wilde", "Villa Domínico", "Crucecita", "Gerli", "Dock Sud", "Piñeyro"],
        "Quilmes": ["Quilmes", "Bernal", "Don Bosco", "Ezpeleta", "San Francisco Solano", "Villa La Florida"],
        "Berazategui": ["Berazategui", "Hudson", "Plátanos", "Ranelagh", "Sourigues", "Villa España", "Pereyra"],
        "Florencio Varela": ["Florencio Varela", "Bosques", "Gobernador Costa", "Ingeniero Allan", "Villa Vatteone", "Zeballos"],
        "Almirante Brown": ["Adrogué", "Burzaco", "Claypole", "Glew", "José Mármol", "Longchamps", "Malvinas Argentinas", "Ministro Rivadavia", "Rafael Calzada", "San José", "San Francisco de Asís"],
        "Esteban Echeverría": ["Monte Grande", "9 de Abril", "Canning", "El Jagüel", "Luis Guillón"],
        "Ezeiza": ["Ezeiza", "Tristán Suárez", "Carlos Spegazzini", "La Unión", "Canning"],
        "Presidente Perón": ["Guernica"],
        "San Vicente": ["San Vicente", "Alejandro Korn", "Domselaar"],
        "Cañuelas": ["Cañuelas", "Máximo Paz", "Uribelarrea", "Vicente Casares"],
        "Marcos Paz": ["Marcos Paz"],
        "Merlo": ["Merlo", "Libertad", "Mariano Acosta", "Pontevedra", "San Antonio de Padua"],
        "Moreno": ["Moreno", "Cuartel V", "Francisco Álvarez", "La Reja", "Paso del Rey", "Trujui"],
        "General Rodríguez": ["General Rodríguez"],
        "Luján": ["Luján", "Carlos Keen", "Cortínez", "Jáuregui", "Open Door", "Olivera", "Torres"],
        "Mercedes": ["Mercedes", "Tomás Jofré", "Goldney", "Agote"],
        "La Plata": ["La Plata", "Tolosa", "Villa Elisa", "City Bell", "Gonnet", "Ringuelet", "Los Hornos", "San Carlos", "Olmos", "Etcheverry", "Hernández", "Melchor Romero", "Lisandro Olmos"],
        "Berisso": ["Berisso", "Los Talas"],
        "Ensenada": ["Ensenada", "Punta Lara", "Villa Catela"],
        "Mar del Plata (General Pueyrredón)": ["Mar del Plata", "Batán", "Sierra de los Padres", "Estación Camet", "Estación Chapadmalal"],
        "Bahía Blanca": ["Bahía Blanca", "Ingeniero White", "General Daniel Cerri", "Cabildo"],
        "Tandil": ["Tandil", "María Ignacia (Vela)", "Gardey", "Iraola"],
        "Olavarría": ["Olavarría", "Sierras Bayas", "Loma Negra", "Hinojo"],
        "Junín": ["Junín", "Agustín Roca", "Agustina"],
        "Pergamino": ["Pergamino", "Acevedo", "Mariano Benítez", "Manuel Ocampo"],
        "Zárate": ["Zárate", "Lima", "Escalada", "Villa Fox"],
        "Campana": ["Campana", "Otamendi"],
        "Necochea": ["Necochea", "Quequén", "Juan N. Fernández"],
        "Azul": ["Azul", "Cacharí", "Chillar"],
        "Chascomús": ["Chascomús"],
        "Dolores": ["Dolores"],
        "Pinamar": ["Pinamar", "Cariló", "Ostende", "Valeria del Mar"],
        "Villa Gesell": ["Villa Gesell", "Mar de las Pampas", "Las Gaviotas", "Mar Azul"],
        "La Costa": ["Mar del Tuyú", "San Bernardo", "Mar de Ajó", "Santa Teresita", "San Clemente del Tuyú", "Las Toninas", "Costa del Este", "Aguas Verdes"],
    },
    "Catamarca": {"Capital": ["San Fernando del Valle de Catamarca"]},
    "Chaco": {"San Fernando": ["Resistencia", "Barranqueras", "Fontana", "Puerto Vilelas"]},
    "Chubut": {"Rawson": ["Rawson", "Trelew", "Playa Unión"], "Escalante": ["Comodoro Rivadavia"]},
    "Córdoba": {"Capital": ["Córdoba"], "Punilla": ["Villa Carlos Paz", "La Falda", "Cosquín"], "Río Cuarto": ["Río Cuarto"]},
    "Corrientes": {"Capital": ["Corrientes"]},
    "Entre Ríos": {"Paraná": ["Paraná"], "Concordia": ["Concordia"], "Gualeguaychú": ["Gualeguaychú"]},
    "Formosa": {"Formosa": ["Formosa"]},
    "Jujuy": {"Dr. Manuel Belgrano": ["San Salvador de Jujuy"]},
    "La Pampa": {"Capital": ["Santa Rosa"]},
    "La Rioja": {"Capital": ["La Rioja"]},
    "Mendoza": {"Capital": ["Mendoza"], "Godoy Cruz": ["Godoy Cruz"], "Guaymallén": ["Guaymallén"], "San Rafael": ["San Rafael"]},
    "Misiones": {"Capital": ["Posadas"], "Iguazú": ["Puerto Iguazú"]},
    "Neuquén": {"Confluencia": ["Neuquén"], "Los Lagos": ["San Martín de los Andes", "Villa La Angostura"]},
    "Río Negro": {"General Roca": ["General Roca", "Cipolletti"], "Bariloche": ["San Carlos de Bariloche"]},
    "Salta": {"Capital": ["Salta"]},
    "San Juan": {"Capital": ["San Juan"]},
    "San Luis": {"Capital": ["San Luis"]},
    "Santa Cruz": {"Río Gallegos": ["Río Gallegos"], "Lago Argentino": ["El Calafate"]},
    "Santa Fe": {"La Capital": ["Santa Fe"], "Rosario": ["Rosario"], "San Lorenzo": ["San Lorenzo"]},
    "Santiago del Estero": {"Capital": ["Santiago del Estero", "La Banda"]},
    "Tierra del Fuego": {"Ushuaia": ["Ushuaia"], "Río Grande": ["Río Grande"]},
    "Tucumán": {"Capital": ["San Miguel de Tucumán"]},
}


async def main() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    n_prov = n_part = n_loc = 0
    async with SessionLocal() as session:
        for provincia, partidos in GEO_DATA.items():
            r = await session.execute(text("""
                INSERT INTO provincias (nombre)
                VALUES (:nombre)
                ON CONFLICT (nombre) DO UPDATE SET nombre = EXCLUDED.nombre
                RETURNING id_provincia
            """), {"nombre": provincia})
            id_prov = r.scalar()
            n_prov += 1

            for partido, localidades in partidos.items():
                r = await session.execute(text("""
                    INSERT INTO partidos (id_provincia, nombre)
                    VALUES (:id_prov, :nombre)
                    ON CONFLICT (id_provincia, nombre) DO UPDATE SET nombre = EXCLUDED.nombre
                    RETURNING id_partido
                """), {"id_prov": id_prov, "nombre": partido})
                id_part = r.scalar()
                n_part += 1

                for localidad in localidades:
                    await session.execute(text("""
                        INSERT INTO localidades (id_partido, nombre)
                        VALUES (:id_part, :nombre)
                        ON CONFLICT (id_partido, nombre) DO NOTHING
                    """), {"id_part": id_part, "nombre": localidad})
                    n_loc += 1

        await session.commit()

    await engine.dispose()
    print(f"OK: {n_prov} provincias, {n_part} partidos, {n_loc} localidades cargadas.")


if __name__ == "__main__":
    asyncio.run(main())
