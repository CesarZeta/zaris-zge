"""
Seed: empatar agentes con usuarios (5 c/u).

Transformaciones:
- Agentes existentes: apellido inventado + email @gmail.com
- Cada agente vinculado a un usuario de nombre similar
- 1 agente nuevo creado para cubrir el usuario sin agente
- Niveles de acceso de usuarios resultantes: 2, 3, 3, 4, 4 (sin admin)
- El usuario admin (nivel 1, id=1) queda desvinculado de agentes
  (sigue siendo admin del sistema, no es un "agente operativo")

Idempotente: detecta por nombre+apellido si ya existe.
"""
import asyncio
import os
import sys

import asyncpg

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:145236@127.0.0.1:5432/zaris_dev",
)

# Mapa de transformaciones para agentes existentes:
# (nombre, apellido_actual_like) -> (apellido_nuevo, email_nuevo, id_usuario_a_vincular)
# Los usuarios disponibles (no admin):
#   id=2  Juan Pestto      nivel 3
#   id=3  Roy Manoss       nivel 3
#   id=4  Roberto Filad    nivel 2
#   id=5  IA Atencion      nivel 2
#
# Agentes existentes:
#   id=1  Juan  Perez/Suarez  -> vincular a id=2 Juan Pestto  (mismo nombre)
#   id=2  Laura Martinez      -> vincular a id=5 IA Atencion  (ambas femeninas/operativas)
#   id=3  Maria Gonzalez      -> vincular a id=3 Roy Manoss   (operador disponible)
#   id=4  Carlos Demo         -> vincular a id=4 Roberto Filad (supervisor disponible)
#
# Agente NUEVO para usuario sobrante: no queda ninguno sobrante con este mapeo.
# Pero hay 5 usuarios y 4 agentes => necesitamos 1 agente nuevo.
# El admin (id=1) no cuenta como "agente operativo" => liberamos id_usuario=1 del agente 1
# y asignamos el usuario 1 a nadie. Los 5 usuarios no-admin son 2,3,4,5 = 4 usuarios.
# Recontando: 5 usuarios totales, 4 agentes. Para empatar: 1 nuevo agente vinculado
# al usuario que quede libre. Con el mapeo arriba los 4 no-admin quedan cubiertos.
# => necesito un 5to agente vinculado al usuario admin (id=1)?
# No: la instrucción dice "excepto admin" para permisos, pero el agente igual puede existir.
# Mejor: creo 1 usuario nuevo de nivel 4 (Consultor) y lo vinculo al nuevo agente.

AGENTES_UPDATE = [
    # (id_agente, apellido_nuevo, email_nuevo, id_usuario_vincular, nivel_usuario)
    (1, "Fontana",  "juan.fontana@gmail.com",   2, None),   # Juan -> Juan Pestto (ya nivel 3)
    (2, "Villalba", "laura.villalba@gmail.com",  5, None),   # Laura -> IA Atencion (nivel 2)
    (3, "Rivarola", "maria.rivarola@gmail.com",  3, None),   # Maria -> Roy Manoss (nivel 3)
    (4, "Ceballos", "carlos.ceballos@gmail.com", 4, None),   # Carlos -> Roberto Filad (nivel 2)
]

NUEVO_USUARIO = {
    "nombre":       "Sofia Medrano",
    "username":     "sofiamedrano",
    "email":        "sofiamedrano@municipio.gob.ar",
    "nivel_acceso": 4,   # Consultor
}

NUEVO_AGENTE = {
    "nombre":   "Sofia",
    "apellido": "Medrano",
    "legajo":   "LEG-005",
    "email":    "sofia.medrano@gmail.com",
}


async def run():
    print("Conectando a", DB_URL)
    conn = await asyncpg.connect(DB_URL)

    try:
        async with conn.transaction():
            # 1. Actualizar apellidos y emails de agentes existentes
            print("\n--- Actualizando agentes existentes ---")
            for id_agente, apellido, email, id_usuario, _ in AGENTES_UPDATE:
                row = await conn.fetchrow(
                    "SELECT id_agente, nombre, apellido FROM agentes WHERE id_agente=$1", id_agente
                )
                if not row:
                    print(f"  Agente id={id_agente} no encontrado, saltando")
                    continue

                await conn.execute(
                    """UPDATE agentes
                       SET apellido=$1, email=$2, id_usuario=$3, fecha_modificacion=NOW()
                       WHERE id_agente=$4""",
                    apellido, email, id_usuario, id_agente,
                )
                print(f"  Agente {id_agente}: {row['nombre']} {row['apellido']} "
                      f"-> apellido={apellido}, email={email}, id_usuario={id_usuario}")

            # 2. Crear usuario nuevo (idempotente por username)
            print("\n--- Creando usuario nuevo ---")
            existing_user = await conn.fetchrow(
                "SELECT id_usuario FROM usuarios WHERE username=$1", NUEVO_USUARIO["username"]
            )
            if existing_user:
                nuevo_id_usuario = existing_user["id_usuario"]
                print(f"  Usuario '{NUEVO_USUARIO['username']}' ya existe (id={nuevo_id_usuario}), omitiendo INSERT")
            else:
                # Hash de password '123456' con bcrypt
                import bcrypt
                hashed = bcrypt.hashpw(b"123456", bcrypt.gensalt()).decode()
                nuevo_id_usuario = await conn.fetchval(
                    """INSERT INTO usuarios
                         (nombre, username, email, nivel_acceso, password_hash,
                          activo, id_municipio, fecha_alta, fecha_modif, buc_acceso)
                       VALUES ($1,$2,$3,$4,$5, TRUE, 1, NOW(), NOW(), FALSE)
                       RETURNING id_usuario""",
                    NUEVO_USUARIO["nombre"], NUEVO_USUARIO["username"],
                    NUEVO_USUARIO["email"], NUEVO_USUARIO["nivel_acceso"], hashed,
                )
                print(f"  Usuario creado: {NUEVO_USUARIO['nombre']} (id={nuevo_id_usuario}, nivel={NUEVO_USUARIO['nivel_acceso']})")

            # 3. Crear agente nuevo vinculado al usuario nuevo (idempotente por nombre+apellido)
            print("\n--- Creando agente nuevo ---")
            existing_agente = await conn.fetchrow(
                "SELECT id_agente FROM agentes WHERE nombre=$1 AND apellido=$2",
                NUEVO_AGENTE["nombre"], NUEVO_AGENTE["apellido"],
            )
            if existing_agente:
                print(f"  Agente '{NUEVO_AGENTE['nombre']} {NUEVO_AGENTE['apellido']}' "
                      f"ya existe (id={existing_agente['id_agente']}), actualizando vinculo")
                await conn.execute(
                    "UPDATE agentes SET id_usuario=$1, fecha_modificacion=NOW() WHERE id_agente=$2",
                    nuevo_id_usuario, existing_agente["id_agente"],
                )
            else:
                new_id_agente = await conn.fetchval(
                    """INSERT INTO agentes
                         (nombre, apellido, legajo, email, activo, id_municipio,
                          fecha_alta, fecha_modificacion, id_usuario)
                       VALUES ($1,$2,$3,$4, TRUE, 1, NOW(), NOW(), $5)
                       RETURNING id_agente""",
                    NUEVO_AGENTE["nombre"], NUEVO_AGENTE["apellido"],
                    NUEVO_AGENTE["legajo"], NUEVO_AGENTE["email"], nuevo_id_usuario,
                )
                print(f"  Agente creado: {NUEVO_AGENTE['nombre']} {NUEVO_AGENTE['apellido']} "
                      f"(id={new_id_agente}, email={NUEVO_AGENTE['email']}, id_usuario={nuevo_id_usuario})")

            # 4. Asegurarse que el admin (id=1) no queda vinculado a un agente
            #    (el agente id=1 ahora apunta a id_usuario=2)
            admin_agente = await conn.fetchrow(
                "SELECT id_agente, nombre, apellido FROM agentes WHERE id_usuario=1 AND activo"
            )
            if admin_agente:
                await conn.execute(
                    "UPDATE agentes SET id_usuario=NULL, fecha_modificacion=NOW() WHERE id_agente=$1",
                    admin_agente["id_agente"],
                )
                print(f"\n  Desvinculado usuario admin (id=1) del agente "
                      f"{admin_agente['nombre']} {admin_agente['apellido']}")

            # 5. Resumen final
            print("\n--- Estado final ---")
            agentes = await conn.fetch(
                """SELECT a.id_agente, a.nombre, a.apellido, a.email,
                          u.id_usuario, u.nombre as u_nombre, u.nivel_acceso
                   FROM agentes a
                   LEFT JOIN usuarios u ON u.id_usuario = a.id_usuario
                   WHERE a.activo
                   ORDER BY a.id_agente"""
            )
            print(f"{'ID':>3}  {'Agente':<22}  {'Email agente':<30}  {'Usuario vinculado':<20}  {'Nivel'}")
            print("-" * 90)
            for r in agentes:
                u_info = f"{r['u_nombre']} (niv {r['nivel_acceso']})" if r['id_usuario'] else "—"
                print(f"{r['id_agente']:>3}  {r['apellido']+', '+r['nombre']:<22}  "
                      f"{r['email'] or '—':<30}  {u_info:<25}")

            usuarios = await conn.fetch(
                "SELECT id_usuario, nombre, nivel_acceso FROM usuarios WHERE activo ORDER BY id_usuario"
            )
            print(f"\nTotal agentes activos: {len(agentes)}")
            print(f"Total usuarios activos: {len(usuarios)}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
