"""
Seed prod: transformar 84 agentes demo + crear 1 usuario por agente.

Transformaciones:
- Agentes: apellido inventado (determinístico por hash), email @gmail.com
- Usuarios: uno por agente (nombre=agente), @municipio.gob.ar para login,
  nivel_acceso distribuido 2/3/4 (nunca 1), buc_acceso=FALSE
- Vínculo: agentes.id_usuario = nuevo usuario creado
- Agentes ya vinculados a usuarios existentes (ids 1-8): se actualiza apellido
  y email del agente, NO se toca su usuario existente (conservar)

Idempotente: detecta por username si el usuario ya existe.
No vicentelopez debe quedar en ningún lado.
"""
import asyncio
import hashlib
import os
import sys

import asyncpg

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:145236@127.0.0.1:5432/zaris_dev",
)
# Password de los usuarios nuevos: en local usa la clave dev estandar; contra
# una DB remota (prod) exige ZARIS_SEED_USERS_PASS (§40 — nada de credenciales
# de prod en artefactos trackeados; viven en credenciales-testing/).
_ES_DB_LOCAL = "127.0.0.1" in DB_URL or "localhost" in DB_URL
SEED_USERS_PASS = os.environ.get("ZARIS_SEED_USERS_PASS") or ("123456" if _ES_DB_LOCAL else None)
if not SEED_USERS_PASS:
    sys.exit("Contra una DB remota setea ZARIS_SEED_USERS_PASS (ver credenciales-testing/, fuera del repo)")

# Pool de apellidos inventados (100+) para no repetir
APELLIDOS = [
    "Fontana", "Villalba", "Rivarola", "Ceballos", "Medrano",
    "Alvarado", "Brandan", "Cáceres", "Delgado", "Espinoza",
    "Ferreyra", "Garibaldi", "Herrera", "Iturriaga", "Jofré",
    "Kinoshita", "Leguizamón", "Marchetti", "Nardelli", "Oviedo",
    "Pacheco", "Quiroga", "Rosales", "Saavedra", "Tapia",
    "Urquiza", "Vallejos", "Waisman", "Ybarra", "Zamora",
    "Acosta", "Brizuela", "Correa", "Dávila", "Escalante",
    "Frías", "Gutiérrez", "Hurtado", "Insaurralde", "Juárez",
    "Kramer", "Ledesma", "Moyano", "Núñez", "Ocampo",
    "Pereyra", "Quesada", "Rodas", "Suárez", "Tolosa",
    "Ugarte", "Varela", "Wenk", "Zapata", "Agüero",
    "Blanco", "Cabral", "Domínguez", "Estrada", "Flores",
    "Granada", "Huanca", "Ibáñez", "Jalil", "Kunz",
    "Liébana", "Monges", "Navarrete", "Ojeda", "Pizarro",
    "Quintero", "Robledo", "Silva", "Terán", "Urdaniz",
    "Vergara", "Wolfram", "Yacob", "Zorrilla", "Alderete",
    "Balderrama", "Carballo", "Dupuy", "Echeverría", "Figueroa",
    "Gómez", "Heras", "Iglesias", "Jurado", "Kuhlman",
    "Llanos", "Moreira", "Noriega", "Olmedo", "Páez",
    "Ragone", "Soriano", "Taborda", "Uncal", "Videla",
    "Waisbord", "Zabala", "Carpio", "Mansilla", "Pelayo",
]

# Niveles de acceso distribuidos (nunca 1=admin)
NIVELES = [2, 3, 3, 4, 4, 3, 4, 4]  # ciclo, proporcional a la realidad

def apellido_para(id_agente: int, nombre: str) -> str:
    """Apellido determinístico basado en hash de id+nombre."""
    key = f"{id_agente}:{nombre}"
    h = int(hashlib.md5(key.encode()).hexdigest(), 16)
    return APELLIDOS[h % len(APELLIDOS)]

def username_para(nombre: str, apellido: str, id_agente: int) -> str:
    """Username único: nombre.apellido en minúsculas sin tildes, con sufijo si hace falta."""
    def _strip(s):
        replacements = {
            'á':'a','é':'e','í':'i','ó':'o','ú':'u',
            'ä':'a','ë':'e','ï':'i','ö':'o','ü':'u',
            'ñ':'n','ç':'c',
        }
        result = s.lower()
        for k, v in replacements.items():
            result = result.replace(k, v)
        # eliminar caracteres no alfanuméricos
        return ''.join(c for c in result if c.isalnum())

    n = _strip(nombre.split()[0] if nombre else 'usuario')
    a = _strip(apellido)
    base = f"{n}{a}"
    return base if base else f"agente{id_agente}"

def nivel_para(idx: int) -> int:
    """Nivel de acceso basado en posición (ciclico, nunca 1)."""
    return NIVELES[idx % len(NIVELES)]

async def run(confirm_prod: bool = False):
    print(f"Conectando a: {DB_URL[:40]}...")
    conn = await asyncpg.connect(DB_URL)

    try:
        # 1. Cargar todos los agentes activos
        agentes = await conn.fetch(
            """SELECT id_agente, nombre, apellido, email, legajo, id_usuario,
                      id_cargo, id_subarea, id_municipio
               FROM agentes
               WHERE activo = TRUE
               ORDER BY id_agente"""
        )
        print(f"\nAgentes activos en DB: {len(agentes)}")

        # 2. Cargar usuarios existentes (para no pisar sus vínculos)
        usuarios_existentes = await conn.fetch(
            "SELECT id_usuario, username, nombre, nivel_acceso FROM usuarios WHERE activo = TRUE"
        )
        ids_usuarios_existentes = {u['id_usuario'] for u in usuarios_existentes}
        usernames_existentes = {u['username'] for u in usuarios_existentes}
        print(f"Usuarios existentes activos: {len(usuarios_existentes)}")
        for u in usuarios_existentes:
            print(f"  id={u['id_usuario']} username={u['username']} nivel={u['nivel_acceso']}")

        if not confirm_prod:
            print("\n[DRY-RUN] Para aplicar en prod, pasar --confirm-prod")
            # Mostrar preview
            agentes_vicentelopez = [a for a in agentes if 'vicentelopez' in (a['email'] or '').lower()]
            print(f"\nAgentes con @vicentelopez.gov.ar: {len(agentes_vicentelopez)}")
            print(f"Agentes ya con id_usuario: {len([a for a in agentes if a['id_usuario']])}")
            print("\nPreview de las primeras 5 transformaciones:")
            for i, ag in enumerate(agentes[:5]):
                nuevo_apellido = apellido_para(ag['id_agente'], ag['nombre'])
                email_base = (ag['email'] or '').split('@')[0]
                nuevo_email = f"{email_base.lower().replace(' ', '.')}@gmail.com"
                us = username_para(ag['nombre'], nuevo_apellido, ag['id_agente'])
                print(f"  [{ag['id_agente']}] {ag['nombre']} {ag['apellido']} -> {ag['nombre']} {nuevo_apellido} / {nuevo_email} / user={us}")
            return

        # 3. Aplicar transformaciones dentro de una transacción
        async with conn.transaction():
            creados = 0
            actualizados = 0
            ya_vinculados_conservados = 0

            for idx, ag in enumerate(agentes):
                id_agente = ag['id_agente']
                nombre = ag['nombre'] or ''
                nuevo_apellido = apellido_para(id_agente, nombre)

                # Email: conservar la parte local, cambiar dominio
                email_actual = ag['email'] or ''
                parte_local = email_actual.split('@')[0].lower().replace(' ', '.').replace('_', '.')
                if not parte_local:
                    parte_local = f"{nombre.lower().replace(' ', '.')}"
                nuevo_email_agente = f"{parte_local}@gmail.com"

                # ¿Este agente ya tiene un usuario existente vinculado?
                if ag['id_usuario'] and ag['id_usuario'] in ids_usuarios_existentes:
                    # Conservar el vínculo con el usuario existente — solo actualizar agente
                    await conn.execute(
                        """UPDATE agentes
                           SET apellido=$1, email=$2, fecha_modificacion=NOW()
                           WHERE id_agente=$3""",
                        nuevo_apellido, nuevo_email_agente, id_agente,
                    )
                    ya_vinculados_conservados += 1
                    print(f"  [{id_agente}] {nombre} -> apellido={nuevo_apellido}, email={nuevo_email_agente} [usuario existente conservado id={ag['id_usuario']}]")
                    continue

                # Crear usuario nuevo para este agente
                nivel = nivel_para(idx)
                username = username_para(nombre, nuevo_apellido, id_agente)

                # Asegurar unicidad de username
                base_username = username
                suffix = 2
                while username in usernames_existentes:
                    username = f"{base_username}{suffix}"
                    suffix += 1
                usernames_existentes.add(username)

                nombre_usuario = f"{nombre} {nuevo_apellido}".strip()
                email_usuario = f"{username}@municipio.gob.ar"

                # Verificar si el usuario ya existe por username (idempotencia)
                existing = await conn.fetchrow(
                    "SELECT id_usuario FROM usuarios WHERE username=$1", username
                )
                if existing:
                    nuevo_id_usuario = existing['id_usuario']
                    print(f"  [{id_agente}] Usuario '{username}' ya existe (id={nuevo_id_usuario}), reutilizando")
                else:
                    import bcrypt
                    hashed = bcrypt.hashpw(SEED_USERS_PASS.encode(), bcrypt.gensalt()).decode()
                    nuevo_id_usuario = await conn.fetchval(
                        """INSERT INTO usuarios
                             (nombre, username, email, nivel_acceso, password_hash,
                              activo, id_municipio, fecha_alta, fecha_modif, buc_acceso)
                           VALUES ($1,$2,$3,$4,$5, TRUE, 1, NOW(), NOW(), FALSE)
                           RETURNING id_usuario""",
                        nombre_usuario, username, email_usuario, nivel, hashed,
                    )
                    creados += 1

                # Actualizar agente: apellido + email + vincular usuario
                await conn.execute(
                    """UPDATE agentes
                       SET apellido=$1, email=$2, id_usuario=$3, fecha_modificacion=NOW()
                       WHERE id_agente=$4""",
                    nuevo_apellido, nuevo_email_agente, nuevo_id_usuario, id_agente,
                )
                actualizados += 1
                print(f"  [{id_agente}] {nombre} {ag['apellido']} -> {nombre} {nuevo_apellido} / {nuevo_email_agente} / user={username} (niv {nivel}, id_usr={nuevo_id_usuario})")

            print(f"\n--- Resumen ---")
            print(f"Agentes transformados: {actualizados}")
            print(f"Agentes con usuario existente conservado: {ya_vinculados_conservados}")
            print(f"Usuarios nuevos creados: {creados}")

        # 4. Verificación final
        print("\n--- Verificación: emails con vicentelopez ---")
        restantes = await conn.fetch(
            "SELECT id_agente, nombre, apellido, email FROM agentes WHERE email ILIKE '%vicentelopez%' AND activo"
        )
        if restantes:
            print(f"  ALERTA: quedan {len(restantes)} agentes con vicentelopez en email!")
            for r in restantes:
                print(f"    [{r['id_agente']}] {r['nombre']} {r['apellido']} — {r['email']}")
        else:
            print("  OK: ningún agente tiene @vicentelopez en email.")

        print("\n--- Verificación: agentes sin id_usuario ---")
        sin_usuario = await conn.fetch(
            "SELECT id_agente, nombre, apellido FROM agentes WHERE id_usuario IS NULL AND activo"
        )
        if sin_usuario:
            print(f"  {len(sin_usuario)} agentes sin usuario vinculado:")
            for r in sin_usuario:
                print(f"    [{r['id_agente']}] {r['nombre']} {r['apellido']}")
        else:
            print("  OK: todos los agentes tienen usuario vinculado.")

        print("\n--- Conteos finales ---")
        totales = await conn.fetchrow(
            "SELECT (SELECT COUNT(*) FROM agentes WHERE activo) as ag, (SELECT COUNT(*) FROM usuarios WHERE activo) as us"
        )
        print(f"  Agentes activos: {totales['ag']}")
        print(f"  Usuarios activos: {totales['us']}")

    finally:
        await conn.close()


if __name__ == "__main__":
    confirm = "--confirm-prod" in sys.argv
    asyncio.run(run(confirm_prod=confirm))
