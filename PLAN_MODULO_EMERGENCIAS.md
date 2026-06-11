# PLAN DE IMPLEMENTACION - MODULO EMERGENCIAS (ZGE)

**Ubicacion canonica:** `docs/modulos/emergencias/PLAN_MODULO_EMERGENCIAS.md`
**Estado:** Fases 1-5 CERRADAS (modulo completo en produccion). Iteraciones futuras en seccion 8.
**Ultima revision:** 2026-06-10 (cierre Fase 5 + pendientes menores + normalizacion OSM)

---

## 0. CONTEXTO Y DECISIONES CERRADAS

### 0.1 Que es el modulo

Modulo de Atencion de Eventos de Emergencia dentro de ZGE (ZARIS Gestion
Estatal). Diferente del modulo Reclamos: aqui los eventos requieren respuesta
rapida, triage por prioridad, despacho, y frecuentemente derivacion a
organismos externos (911 PBA, SAME, Bomberos, Defensa Civil Provincial).

### 0.2 Decisiones cerradas con el usuario

| Decision | Valor |
|---|---|
| Estructura organizacional | AREA "Secretaria de Seguridad" con DOS subareas: "Policia Municipal" y "Defensa Civil" |
| Taxonomia de tipos - Policia | Resolucion RESO-2022-166-GDEBA-MSGP (Ministerio Seguridad PBA), 34 tipos aplicables |
| Taxonomia de tipos - Defensa Civil | Propia, 16 tipos (definidos en seccion 3) |
| Canales de ingreso (MVP) | Llamada telefonica + App Vecinos. Otros canales preparados pero no cargados |
| Grabacion de audio | Campo opcional preparado en la tabla, integracion futura |
| Estados | PENDIENTE, EN_PREPARACION, EN_CAMINO, EN_SITIO, DERIVADO, RESUELTO, DESESTIMADO |
| Identificacion del denunciante | Tres opciones: anonimo / ciudadano BUC / contacto eventual |
| Datos minimos obligatorios del contacto eventual | DNI, Nombre+Apellido, Telefono, Direccion |
| Datos opcionales del contacto eventual | Nombre y Telefono de contacto alternativo |
| Busqueda de denunciante | Por DNI, Telefono y Nombre (consulta unificada BUC + eventuales) |
| Promocion contacto eventual a BUC | Operacion explicita disponible, reasigna eventos previos |

### 0.3 Criterios profesionales aplicados (delegados por el usuario)

| Criterio | Justificacion |
|---|---|
| Estado EN_SITIO obligatorio | Sin marca de arribo no se puede medir tiempo de respuesta, que es el KPI critico de un COM |
| Log append-only con trigger anti-mutacion | Responsabilidad civil municipal: el registro de tiempos puede tener consecuencias legales |
| Direccion del evento separada del domicilio del denunciante | El evento puede ocurrir en un lugar distinto del domicilio de quien llama |
| numero_operativo correlativo visible | Permite al operador y al vecino referenciar el evento sin exponer ID interno |
| Veracidad como campo separado del estado | Permite cerrar como RESUELTO con veracidad CONFIRMADA o como DESESTIMADO con FALSA_ALARMA, distincion necesaria para KPIs |
| Guard de nivel SIEMPRE en backend | Ocultar en sidebar UI es evadible con JWT+curl. Aplica especialmente aqui por sensibilidad de datos |
| Refresh por polling (no WebSocket) | MVP simple. WebSocket queda para iteracion siguiente |
| organismo_derivacion_default por tipo | Acelera el triage del operador; igual puede sobreescribirse caso a caso |

---

## 1. ESTANDARES APLICABLES

Referencia primaria: `CLAUDE.md` (raiz del repo).

Recordatorios criticos para este modulo:

- **Naming de tablas:** prefijo `emergencia_*`
- **Campos estandar en cada tabla:** `id, activo, id_municipio, fecha_alta, fecha_modificacion`
- **Excepcion log append-only:** sin `fecha_modificacion` ni `activo`, con triggers anti-UPDATE y anti-DELETE
- **SQLAlchemy 2.x:** `text()` explicito en raw SQL
- **asyncpg quirks:** `CAST(:p AS tipo)` (NO `:p::tipo`); JSONB con `CAST(:v AS jsonb)` y `json.dumps`
- **Sin caracteres acentuados** en strings Python (CP1252 Windows)
- **Migraciones Alembic** numeradas e idempotentes, aplicadas en LOCAL y PROD en la misma sesion
- **Snapshot `_backup_<tabla>_YYYY_MM_DD`** antes de UPDATE/DELETE masivo en prod
- **CSVs en** `sql/tablas/` con nombre `tabla_emergencia_<entidad>.csv`
- **IDs no son estables:** en seeds resolver FKs por codigo/nombre normalizado, nunca hardcoded
- **Frontend:** SOLO tokens DS (`--z-*`), prefijo de clases `z-*`, sin hex literales, sin emoji
- **`ConfirmModal`** (no `window.confirm`) para acciones destructivas
- **Shell React** no carga `components.css`: usar CSS Modules con tokens
- **Orden de routers** en `main.py`: rutas especificas ANTES que rutas con `{param}` greedy

---

## 2. MODELO DE DATOS COMPLETO

### 2.1 emergencia_organismo_derivacion

Catalogo de organismos a los que se puede derivar un evento.

```
id                       PK serial
codigo                   TEXT UNIQUE NOT NULL
nombre                   TEXT NOT NULL
descripcion              TEXT
telefono_contacto        TEXT
es_municipal             BOOLEAN NOT NULL DEFAULT false
activo                   BOOLEAN NOT NULL DEFAULT true
id_municipio             BIGINT NOT NULL REFERENCES municipio
fecha_alta               TIMESTAMPTZ NOT NULL DEFAULT now()
fecha_modificacion       TIMESTAMPTZ NOT NULL DEFAULT now()
```

### 2.2 emergencia_canal_ingreso

```
id                       PK
codigo                   TEXT UNIQUE NOT NULL
nombre                   TEXT NOT NULL
descripcion              TEXT
requiere_operador        BOOLEAN NOT NULL DEFAULT true
activo, id_municipio, fecha_alta, fecha_modificacion
```

### 2.3 emergencia_prioridad

```
id                       PK
codigo                   TEXT UNIQUE NOT NULL    -- P1, P2, P3
nombre                   TEXT NOT NULL
descripcion              TEXT
sla_minutos_arribo       INT NOT NULL
color_token              TEXT NOT NULL           -- nombre del token DS, no hex
orden_visual             INT NOT NULL
activo, id_municipio, fecha_alta, fecha_modificacion
```

### 2.4 emergencia_estado

```
id                       PK
codigo                   TEXT UNIQUE NOT NULL
nombre                   TEXT NOT NULL
descripcion              TEXT
es_inicial               BOOLEAN NOT NULL DEFAULT false
es_terminal              BOOLEAN NOT NULL DEFAULT false
es_terminal_positivo     BOOLEAN NOT NULL DEFAULT false
orden_visual             INT NOT NULL
activo, id_municipio, fecha_alta, fecha_modificacion
```

### 2.5 emergencia_tipo

```
id                                PK
id_subarea                        BIGINT NOT NULL REFERENCES subarea
codigo_oficial                    INT NULL              -- numero MinSeg PBA si aplica
codigo                            TEXT NOT NULL         -- snake_case
nombre                            TEXT NOT NULL
descripcion                       TEXT
id_prioridad_default              BIGINT NOT NULL REFERENCES emergencia_prioridad
id_organismo_derivacion_default   BIGINT NULL REFERENCES emergencia_organismo_derivacion
requiere_911                      BOOLEAN NOT NULL DEFAULT false
es_emergencia                     BOOLEAN NOT NULL
activo, id_municipio, fecha_alta, fecha_modificacion
UNIQUE (id_subarea, codigo)
INDEX (id_subarea, activo)
```

### 2.6 emergencia_subtipo

```
id                       PK
id_tipo                  BIGINT NOT NULL REFERENCES emergencia_tipo
codigo                   TEXT NOT NULL
nombre                   TEXT NOT NULL
descripcion              TEXT
id_prioridad_override    BIGINT NULL REFERENCES emergencia_prioridad
activo, id_municipio, fecha_alta, fecha_modificacion
UNIQUE (id_tipo, codigo)
```

### 2.7 emergencia_contacto_eventual

Vecinos cargados al vuelo durante la atencion del llamado, cuando NO se los
encuentra en BUC.

```
id                              PK
dni                             TEXT NOT NULL    -- normalizado, solo digitos
nombre_apellido                 TEXT NOT NULL
telefono                        TEXT NOT NULL
direccion                       TEXT NOT NULL
contacto_alt_nombre             TEXT NULL
contacto_alt_telefono           TEXT NULL
convertido_a_buc                BOOLEAN NOT NULL DEFAULT false
id_ciudadano_buc_destino        BIGINT NULL REFERENCES ciudadano
observaciones                   TEXT NULL
activo, id_municipio, fecha_alta, fecha_modificacion
INDEX (dni)
INDEX (telefono)
INDEX (lower(nombre_apellido))
```

### 2.8 emergencia_evento (TABLA PRINCIPAL)

```
id                              PK BIGSERIAL
numero_operativo                TEXT UNIQUE NOT NULL    -- "EM-2026-000123"
id_subarea                      BIGINT NOT NULL REFERENCES subarea
id_tipo                         BIGINT NOT NULL REFERENCES emergencia_tipo
id_subtipo                      BIGINT NULL REFERENCES emergencia_subtipo
id_prioridad                    BIGINT NOT NULL REFERENCES emergencia_prioridad
id_estado                       BIGINT NOT NULL REFERENCES emergencia_estado
id_canal_ingreso                BIGINT NOT NULL REFERENCES emergencia_canal_ingreso
id_organismo_derivacion         BIGINT NULL REFERENCES emergencia_organismo_derivacion
id_operador_receptor            BIGINT NULL REFERENCES usuario
denunciante_anonimo             BOOLEAN NOT NULL DEFAULT false
id_ciudadano_buc                BIGINT NULL REFERENCES ciudadano
id_contacto_eventual            BIGINT NULL REFERENCES emergencia_contacto_eventual
direccion_evento                TEXT NOT NULL
lat                             DOUBLE PRECISION NULL
lon                             DOUBLE PRECISION NULL
referencia_ubicacion            TEXT NULL
audio_grabacion_url             TEXT NULL
observaciones_recepcion         TEXT NULL
observaciones_cierre            TEXT NULL
veracidad                       TEXT NULL CHECK (
                                  veracidad IS NULL OR veracidad IN
                                  ('CONFIRMADA','FALSA_ALARMA','NO_VERIFICABLE'))
fecha_hora_recepcion            TIMESTAMPTZ NOT NULL DEFAULT now()
fecha_hora_despacho             TIMESTAMPTZ NULL
fecha_hora_arribo               TIMESTAMPTZ NULL
fecha_hora_cierre               TIMESTAMPTZ NULL
activo, id_municipio, fecha_alta, fecha_modificacion

CHECK (
  (denunciante_anonimo = true
   AND id_ciudadano_buc IS NULL
   AND id_contacto_eventual IS NULL)
  OR
  (denunciante_anonimo = false
   AND ((id_ciudadano_buc IS NOT NULL AND id_contacto_eventual IS NULL)
        OR (id_ciudadano_buc IS NULL AND id_contacto_eventual IS NOT NULL)))
)

INDEX (id_estado, id_municipio, fecha_hora_recepcion DESC)
INDEX (numero_operativo)
INDEX (id_subarea, id_estado)
INDEX (id_ciudadano_buc)
INDEX (id_contacto_eventual)
```

### 2.9 emergencia_log (APPEND-ONLY)

```
id                       PK
id_evento                BIGINT NOT NULL REFERENCES emergencia_evento
id_usuario               BIGINT NULL REFERENCES usuario
fecha_hora               TIMESTAMPTZ NOT NULL DEFAULT now()
tipo_accion              TEXT NOT NULL CHECK (tipo_accion IN (
                           'CREACION','CAMBIO_ESTADO','CAMBIO_TIPO',
                           'CAMBIO_PRIORIDAD','CAMBIO_SUBTIPO','DERIVACION',
                           'NOTA','ASIGNACION_RECURSO','CIERRE',
                           'PROMOCION_BUC'))
estado_anterior          TEXT NULL
estado_nuevo             TEXT NULL
payload_json             JSONB NULL
observaciones            TEXT NULL
id_municipio             BIGINT NOT NULL REFERENCES municipio
-- SIN fecha_modificacion, SIN activo
```

**Trigger anti-mutacion (obligatorio en la migracion):**

```sql
CREATE OR REPLACE FUNCTION emergencia_log_no_mutate()
RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'emergencia_log es append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER emergencia_log_no_update
BEFORE UPDATE ON emergencia_log
FOR EACH ROW EXECUTE FUNCTION emergencia_log_no_mutate();

CREATE TRIGGER emergencia_log_no_delete
BEFORE DELETE ON emergencia_log
FOR EACH ROW EXECUTE FUNCTION emergencia_log_no_mutate();
```

### 2.10 Secuencia para numero_operativo

```sql
CREATE SEQUENCE emergencia_evento_numero_seq START 1;
```

Formato del numero: `EM-YYYY-NNNNNN` (year actual + zero-padded a 6 digitos).
Resetear secuencia a 1 cada 1 de enero (cron o trigger; queda para Fase 3).

---

## 3. TAXONOMIAS - DATOS SEED

### 3.1 emergencia_canal_ingreso

```
LLAMADA_TEL  | "Llamada telefonica al COM"   | requiere_operador=true
APP_VECINO   | "Aplicacion movil del vecino" | requiere_operador=false
```

### 3.2 emergencia_prioridad

```
P1 | "Vida en riesgo o delito en curso"  | sla=5  | color_token=z-prio-p1 | orden=1
P2 | "Dano material en curso o inminente"| sla=15 | color_token=z-prio-p2 | orden=2
P3 | "Prevencion / informacion"          | sla=60 | color_token=z-prio-p3 | orden=3
```

### 3.3 emergencia_estado

```
PENDIENTE       | "Recibido, en triage"                  | inicial=true,  terminal=false                       | orden=1
EN_PREPARACION  | "Preparando recurso para despacho"     | terminal=false                                      | orden=2
EN_CAMINO       | "Recurso despachado"                   | terminal=false                                      | orden=3
EN_SITIO        | "Recurso en el lugar del evento"       | terminal=false                                      | orden=4
DERIVADO        | "Derivado a organismo externo"         | terminal=false                                      | orden=5
RESUELTO        | "Cerrado con resolucion"               | terminal=true,  terminal_positivo=true              | orden=6
DESESTIMADO     | "Cerrado: falsa alarma / no emergencia"| terminal=true,  terminal_positivo=false             | orden=7
```

### 3.4 emergencia_organismo_derivacion

```
POLICIA_911_PBA      | "911 Policia de la Provincia de Buenos Aires"   | tel=911 | municipal=false
SAME_107             | "Sistema de Atencion Medica de Emergencias"     | tel=107 | municipal=false
BOMBEROS             | "Bomberos Voluntarios"                          | tel=100 | municipal=false
DEFENSA_CIVIL_PROV   | "Defensa Civil Provincial"                      | municipal=false
PREFECTURA           | "Prefectura Naval Argentina"                    | tel=106 | municipal=false
PATRULLA_URB_MUN     | "Patrulla Urbana Municipal"                     | municipal=true
TRANSITO_MUN         | "Direccion de Transito Municipal"               | municipal=true
DEFENSA_CIVIL_MUN    | "Defensa Civil Municipal"                       | municipal=true
SERV_PUB_MUN         | "Servicios Publicos Municipales"                | municipal=true
ZOONOSIS_MUN         | "Zoonosis Municipal"                            | municipal=true
SERV_SOCIAL_MUN      | "Politicas de Genero / Servicio Social"         | municipal=true
FISCALIA             | "Ministerio Publico Fiscal"                     | municipal=false
```

### 3.5 emergencia_tipo - SUBAREA POLICIA MUNICIPAL (34 tipos)

Formato: `codigo_oficial | codigo | nombre | prioridad_default | organismo_default | requiere_911 | es_emergencia`

```
1  | AGRADECIMIENTO              | "Agradecimiento"                          | P3 | -                  | false | false
2  | ALARMAS                     | "Alarmas"                                 | P2 | PATRULLA_URB_MUN   | false | true
3  | BROMA                       | "Broma"                                   | P3 | -                  | false | false
4  | CARTA_ORIGINAL              | "Carta original (eventos multiples)"      | P2 | POLICIA_911_PBA    | false | true
5  | CASOS_CRITICOS              | "Casos criticos"                          | P1 | POLICIA_911_PBA    | true  | true
6  | CONTRAVENTORES              | "Contraventores"                          | P3 | PATRULLA_URB_MUN   | false | true
7  | DELITO_INFORMATICO          | "Delito informatico"                      | P3 | FISCALIA           | false | false
8  | DESAPARICION_PERSONA        | "Desaparicion de persona"                 | P1 | POLICIA_911_PBA    | false | true
9  | DISPAROS                    | "Disparos"                                | P1 | POLICIA_911_PBA    | true  | true
10 | DROGAS_ILICITAS             | "Drogas ilicitas"                         | P2 | POLICIA_911_PBA    | false | true
12 | EMERGENCIA_SALUD            | "Emergencia de salud"                     | P1 | SAME_107           | false | true
14 | ESTAFA                      | "Estafa"                                  | P3 | FISCALIA           | false | false
15 | EVASION_DETENIDOS           | "Evasion de detenidos"                    | P1 | POLICIA_911_PBA    | true  | true
16 | EXPLOSIVOS                  | "Explosivos"                              | P1 | POLICIA_911_PBA    | true  | true
17 | EXTORSION                   | "Extorsion"                               | P2 | POLICIA_911_PBA    | false | true
18 | HALLAZGO                    | "Hallazgo"                                | P3 | PATRULLA_URB_MUN   | false | true
20 | INFORMACION                 | "Informacion"                             | P3 | -                  | false | false
21 | INTEGRIDAD_VIDA             | "Integridad a la vida"                    | P1 | POLICIA_911_PBA    | true  | true
22 | INTEGRIDAD_SEXUAL           | "Integridad sexual"                       | P1 | POLICIA_911_PBA    | true  | true
23 | INTRUSION                   | "Intrusion"                               | P2 | POLICIA_911_PBA    | false | true
24 | MAL_FUNCIONAMIENTO          | "Mal funcionamiento de fuerzas"           | P3 | FISCALIA           | false | false
25 | MALTRATO_ANIMAL             | "Maltrato animal"                         | P3 | ZOONOSIS_MUN       | false | true
26 | NO_CONSTITUYE_EMERGENCIA    | "No constituye emergencia"                | P3 | -                  | false | false
27 | OCCISO                      | "Occiso (fallecimiento constatado)"       | P1 | SAME_107           | false | true
28 | PEDIDO_GENERICO_AUXILIO     | "Pedido generico de auxilio"              | P2 | PATRULLA_URB_MUN   | false | true
29 | PIRATAS_ASFALTO             | "Piratas del asfalto"                     | P1 | POLICIA_911_PBA    | true  | true
30 | PRIVACION_ILEGITIMA_LIBERTAD| "Privacion ilegitima de la libertad"      | P1 | POLICIA_911_PBA    | true  | true
31 | PROFUGO                     | "Profugo"                                 | P2 | POLICIA_911_PBA    | false | true
32 | QUEJA                       | "Queja"                                   | P3 | -                  | false | false
33 | ROBO                        | "Robo"                                    | P1 | POLICIA_911_PBA    | true  | true
34 | ROBO_AUTOMOTOR              | "Robo automotor"                          | P1 | POLICIA_911_PBA    | true  | true
35 | SOSPECHOSO                  | "Sospechoso"                              | P2 | PATRULLA_URB_MUN   | false | true
36 | TERRORISMO                  | "Terrorismo"                              | P1 | POLICIA_911_PBA    | true  | true
37 | TOMA_REHEN                  | "Toma de rehen"                           | P1 | POLICIA_911_PBA    | true  | true
```

**Notas:**
- Se excluyen del original los tipos 11 (Emergencia Civil), 13 (Emergencias Nauticas) y 19 (Incendio) porque corresponden a subarea Defensa Civil en este modelo.
- El codigo_oficial NO es consecutivo (se respetan los numeros oficiales MinSeg PBA).

### 3.6 emergencia_subtipo - SUBAREA POLICIA MUNICIPAL

```
AGRADECIMIENTO                : Operador, Movil, SIE_911
ALARMAS                       : Pulsador, Otros_Sensores, Sensor_No_Verificado, Sensor_Verificado, SPB
BROMA                         : Broma
CARTA_ORIGINAL                : Con_Prioridad, Sin_Prioridad
CASOS_CRITICOS                : Casos_Criticos
CONTRAVENTORES                : Desorden_Via_Publica, Venta_Alcohol
DELITO_INFORMATICO            : Acoso_Menor, Pornografia_Infantil, Otros_Delitos
DESAPARICION_PERSONA          : Desaparicion, Localizacion, Publico_Conocimiento
DISPAROS                      : Disparos, Personas, Procedimiento_Policial
DROGAS_ILICITAS               : Consumo, Transporte, Venta_Elaboracion
EMERGENCIA_SALUD              : Emergencia, Presuncion_Fallecimiento, Coronavirus
ESTAFA                        : Estafa
EVASION_DETENIDOS             : Arresto_Domiciliario, Dependencias_Publicas, Movil_Traslado
EXPLOSIVOS                    : CATE_911, Amenaza_Bomba, Establecimiento_Educativo, Acopio_Fabricacion
EXTORSION                     : Intimidacion, Secuestro_Virtual, Sobre_Persona
HALLAZGO                      : NN_Hospital, Objeto_Dudoso_Peligroso, Persona_Indigente, Persona_Perdida, Restos_Humanos, Vehicular
INFORMACION                   : Informacion, Importancia_Institucional
INTEGRIDAD_VIDA               : Amenaza_Muerte, Suicidio
INTEGRIDAD_SEXUAL             : Abuso, Exhibiciones_Obscenas
INTRUSION                     : Inmueble_Publico, Propiedad_Privada
MAL_FUNCIONAMIENTO            : Policia_Provincia, Otras_Fuerzas, SPB
MALTRATO_ANIMAL               : Maltrato_Animal
NO_CONSTITUYE_EMERGENCIA      : No_Constituye_Emergencia
OCCISO                        : Occiso
PEDIDO_GENERICO_AUXILIO       : PGA
PIRATAS_ASFALTO               : Alerta, Camion_Caudales, Descarga_Mercaderia, En_Progreso, En_Seguimiento
PRIVACION_ILEGITIMA_LIBERTAD  : En_Progreso, Victima_Liberada
PROFUGO                       : Via_Publica
QUEJA                         : Operador, Movil, SIE_911
ROBO                          : Bancario, Comercio, Finca, Edificio_Publico, Saqueo, Transporte_Publico, Via_Publica
ROBO_AUTOMOTOR                : Desguace, Moto, Vehiculo
SOSPECHOSO                    : En_Vehiculo, Persona_Extrana
TERRORISMO                    : Terrorismo
TOMA_REHEN                    : Interior, Via_Publica
```

### 3.7 emergencia_tipo - SUBAREA DEFENSA CIVIL (16 tipos)

```
INCENDIO              | "Incendio"                              | P1 | BOMBEROS              | true
INUNDACION            | "Inundacion"                            | P1 | DEFENSA_CIVIL_MUN     | true
ANEGAMIENTO_PLUVIAL   | "Anegamiento pluvial"                   | P2 | SERV_PUB_MUN          | true
CAIDA_ARBOL           | "Caida de arbol"                        | P2 | SERV_PUB_MUN          | true
CAIDA_TENDIDO         | "Caida de tendido (cables / postes)"    | P2 | SERV_PUB_MUN          | true
FUGA_GAS              | "Fuga de gas"                           | P1 | BOMBEROS              | true
DERRAME_QUIMICO       | "Derrame quimico / sustancia peligrosa" | P1 | DEFENSA_CIVIL_PROV    | true
NUBE_TOXICA           | "Nube toxica / olores toxicos"          | P1 | DEFENSA_CIVIL_PROV    | true
DERRUMBE              | "Derrumbe"                              | P1 | BOMBEROS              | true
RESCATE               | "Rescate de persona o animal"           | P1 | BOMBEROS              | true
ANIMAL_PELIGROSO      | "Animal peligroso suelto"               | P2 | ZOONOSIS_MUN          | true
ACCIDENTE_VIA_PUBLICA | "Accidente en via publica"              | P2 | TRANSITO_MUN          | true
TORMENTA_SEVERA       | "Tormenta severa / fenomeno meteo"      | P2 | DEFENSA_CIVIL_MUN     | true
EMERGENCIA_CLIMATICA  | "Emergencia climatica (ola calor/frio)" | P2 | DEFENSA_CIVIL_MUN     | true
EVACUACION_PREVENTIVA | "Evacuacion preventiva"                 | P1 | DEFENSA_CIVIL_MUN     | true
SIMULACRO             | "Simulacro"                             | P3 | DEFENSA_CIVIL_MUN     | false
```

### 3.8 emergencia_subtipo - SUBAREA DEFENSA CIVIL

```
INCENDIO              : Domiciliario, Comercial, Industrial, Rural, Vehicular, Via_Publica, Forestal, Pastizal
INUNDACION            : Calle, Vivienda, Comercio, Curso_Agua
ANEGAMIENTO_PLUVIAL   : Calle, Vivienda, Sumidero_Obstruido
CAIDA_ARBOL           : Sobre_Calzada, Sobre_Vereda, Sobre_Vivienda, Sobre_Vehiculo, Sobre_Cables
CAIDA_TENDIDO         : Electrico, Telefonico, Postes
FUGA_GAS              : Domiciliaria, Comercial, Via_Publica
DERRAME_QUIMICO       : Via_Publica, Industrial, Combustible
NUBE_TOXICA           : Olores_Toxicos, Humo_Industrial, No_Identificado
DERRUMBE              : Edificio, Pared, Estructura_Precaria, Excavacion
RESCATE               : Persona_Ascensor, Persona_Estructura, Persona_Pozo, Persona_Altura, Animal_Atrapado
ANIMAL_PELIGROSO      : Canino, Equino_Suelto, Bovino_Suelto, Otros
ACCIDENTE_VIA_PUBLICA : Sin_Lesionados, Lesionados_Leves, Lesionados_Graves, Vuelco
TORMENTA_SEVERA       : Granizo, Tornado, Viento_Fuerte, Lluvia_Intensa
EMERGENCIA_CLIMATICA  : Ola_Calor, Ola_Frio, Sequia
EVACUACION_PREVENTIVA : Preventiva, Por_Crecida, Por_Incendio_Cercano
SIMULACRO             : Simulacro
```

---

## 4. ENDPOINTS BACKEND

Router en `backend/app/api/routes/emergencias.py`, prefijo `/api/v1/emergencias`.

### 4.1 Catalogos (lectura, scope agente)

```
GET  /tipos?id_subarea=&activo=true        Tipos por subarea
GET  /tipos/{id}/subtipos                  Subtipos de un tipo
GET  /subtipos?id_tipo=
GET  /organismos
GET  /canales
GET  /prioridades
GET  /estados                              Ordenados por orden_visual
```

### 4.2 Contactos eventuales (scope agente)

```
GET  /contactos-eventuales?dni=                  Busqueda exacta por DNI
GET  /contactos-eventuales?telefono=             Busqueda exacta por telefono
GET  /contactos-eventuales?nombre=               Busqueda LIKE case-insensitive
POST /contactos-eventuales                       Crear (valida 4 obligatorios)
GET  /contactos-eventuales/{id}
PATCH /contactos-eventuales/{id}                 Editar
POST /contactos-eventuales/{id}/promover-a-buc   Promover a ciudadano BUC
```

**Promocion a BUC:**
- Crea o vincula ciudadano en BUC.
- Setea `convertido_a_buc=true` y `id_ciudadano_buc_destino`.
- Reasigna eventos previos: ahora apuntan a BUC via `id_ciudadano_buc`, `id_contacto_eventual` queda en NULL en `emergencia_evento`.
- Registra entrada en `emergencia_log` con `tipo_accion='PROMOCION_BUC'`.

### 4.3 Busqueda unificada de denunciante (CLAVE)

```
GET /denunciantes/buscar?dni=12345678
GET /denunciantes/buscar?telefono=2215551234
GET /denunciantes/buscar?nombre=perez juan
```

**Logica del endpoint:**
1. Buscar en `ciudadano` (BUC) por el campo correspondiente al query (`nro_documento`, `telefono`, `nombre+apellido`).
2. Si encuentra: devolver `{"origen":"BUC", "matches":[{...}]}`.
3. Si no, buscar en `emergencia_contacto_eventual` por el mismo criterio.
4. Si encuentra: devolver `{"origen":"EVENTUAL", "matches":[{...}]}`.
5. Si no esta en ninguno: devolver `{"origen":"NUEVO", "criterio":"dni"|"telefono"|"nombre", "valor":"..."}`.

Devuelve array `matches` (no objeto unico) porque busqueda por nombre o telefono puede tener mas de un resultado.

### 4.4 Eventos (scope agente - operador COM)

```
POST /eventos                              Crear evento
GET  /eventos                              Lista paginada con filtros
GET  /eventos/abiertos                     Lista no terminales (dispatcher)
GET  /eventos/{id}                         Detalle completo (joins)
PATCH /eventos/{id}                        Editar campos no terminales
POST /eventos/{id}/cambiar-estado          {nuevo_estado, observaciones}
POST /eventos/{id}/derivar                 {id_organismo, observaciones}
POST /eventos/{id}/cerrar                  {veracidad, terminal_positivo, observaciones_cierre}
POST /eventos/{id}/marcar-en-sitio         Setea fecha_hora_arribo=now()
POST /eventos/{id}/agregar-nota            Solo log, sin cambio de estado
GET  /eventos/{id}/log                     Historial completo
```

**Payload POST /eventos:**
```json
{
  "id_subarea": <id>,
  "id_tipo": <id>,
  "id_subtipo": <id>,
  "id_prioridad": <id>,
  "id_canal_ingreso": <id>,
  "denunciante_anonimo": false,
  "id_ciudadano_buc": <id>,
  "id_contacto_eventual": <id>,
  "direccion_evento": "...",
  "lat": null, "lon": null,
  "referencia_ubicacion": "...",
  "observaciones_recepcion": "...",
  "audio_grabacion_url": null
}
```

**Validaciones backend del POST:**
- Si `denunciante_anonimo=false`: exactamente uno entre `id_ciudadano_buc` e `id_contacto_eventual` debe estar lleno.
- `id_tipo` debe pertenecer al `id_subarea` indicado.
- Estado se setea automaticamente a `PENDIENTE`.
- Prioridad se autocompleta del tipo si no viene en el payload.
- `numero_operativo` se genera con secuencia + formato `EM-YYYY-NNNNNN`.
- Crear entrada en `emergencia_log` con `tipo_accion='CREACION'`.
- `id_operador_receptor` se setea del JWT.

### 4.5 Endpoint publico para App Vecinos

```
POST /eventos/publico
```
- Scope JWT `"publico"` (App Vecinos Stage 0 ya implementado).
- Identifica al vecino por su credencial publica, resuelve `id_ciudadano_buc`.
- Body simplificado: `{id_tipo, id_subtipo?, direccion_evento, descripcion, lat, lon}`.
- Setea automaticamente:
  - `id_canal_ingreso = APP_VECINO`
  - `id_operador_receptor = NULL`
  - `id_ciudadano_buc` del vecino
  - `id_estado = PENDIENTE`
- Devuelve `numero_operativo` para seguimiento.

### 4.6 Guards de nivel

Todos los endpoints de eventos requieren rol con acceso a la subarea correspondiente. NO basta con ocultar en UI: validar en backend (`nivel_acceso` y `id_subarea` del usuario contra la del evento).

---

## 5. FRONTEND

Tres paginas bajo `/modulos/emergencias/` del shell vanilla (`zge.zaris.com.ar`).

### 5.1 emergencias_recepcion.html (carga rapida de llamado)

Vista del operador atendiendo telefono.

**Estructura:**
- Header con cronometro de la llamada (inicia al abrir la pagina).
- **Bloque 1 - DENUNCIANTE:**
  - Toggle "Denunciante anonimo" (si se activa, oculta el resto del bloque).
  - Tres campos de busqueda en paralelo: DNI / Telefono / Nombre, cada uno con boton "Buscar".
  - Al buscar, llamar `GET /denunciantes/buscar?<criterio>=<valor>`.
  - Si `origen=BUC`: mostrar lista de matches (puede ser >1 en nombre/telefono); operador elige uno; mostrar datos read-only; boton "Usar este ciudadano". Setea `id_ciudadano_buc`.
  - Si `origen=EVENTUAL`: mostrar lista de matches con datos editables; operador puede "Usar este contacto" o "Actualizar y usar".
  - Si `origen=NUEVO`: formulario para crear contacto eventual con 4 obligatorios (DNI pre-llenado si la busqueda fue por DNI, Nombre+Apellido, Telefono, Direccion) y 2 opcionales (Contacto Alt Nombre, Contacto Alt Telefono). Boton "Registrar y usar".
- **Bloque 2 - EVENTO:**
  - Select SUBAREA (Policia Municipal / Defensa Civil) - obligatorio.
  - Select TIPO (filtrado por subarea) - obligatorio.
  - Select SUBTIPO (filtrado por tipo) - opcional.
  - Select PRIORIDAD (auto-completa segun tipo, editable) - obligatorio.
  - Direccion del evento (input) - obligatorio.
  - Referencia ubicacion (input) - opcional.
  - Lat/Lon (opcional, futuro mapa).
  - Observaciones (textarea) - opcional.
  - Toggle "Grabar audio" - opcional (placeholder, integracion futura).
- Boton primario "Crear evento" - habilitado solo con minimos completos.
- Al crear: redirigir a `emergencias_detalle.html?id=...`. Toast con `numero_operativo`.

### 5.2 emergencias_dispatcher.html (listado de eventos abiertos)

Vista de tablero para supervisor/dispatcher.

- Filtros: subarea, prioridad, estado, fecha rango.
- Listado en tarjetas o tabla, ordenado por `prioridad ASC, fecha DESC`.
- Por cada evento:
  - `numero_operativo`, tipo, subtipo, prioridad (color token DS), estado.
  - `direccion_evento`, denunciante (nombre o "Anonimo").
  - `fecha_hora_recepcion` + tiempo transcurrido en vivo.
  - Botones rapidos: Ver, Marcar EN_CAMINO, Marcar EN_SITIO, Derivar, Cerrar.
- Refresh automatico cada 30s (polling, no WebSocket).

### 5.3 emergencias_detalle.html (detalle + acciones)

- Cabecera con `numero_operativo`, prioridad (color), estado actual, tiempos.
- Tabs:
  - "Datos del evento" (todos los campos)
  - "Denunciante" (datos BUC o eventual; si eventual, boton "Promover a BUC")
  - "Historial" (timeline desde `emergencia_log`)
- Panel lateral de acciones segun estado actual:
  - PENDIENTE: EN_PREPARACION, DERIVAR, DESESTIMAR
  - EN_PREPARACION: EN_CAMINO, DERIVAR, DESESTIMAR
  - EN_CAMINO: EN_SITIO, DERIVAR
  - EN_SITIO: RESUELTO, DERIVAR
  - DERIVADO: EN_SITIO (si vuelve a operar), RESUELTO
  - Terminales: solo lectura.
- Toda accion de cambio de estado abre `ConfirmModal` con campo de observaciones; al confirmar llama al endpoint correspondiente.

### 5.4 Estilo

- Solo tokens DS (`--z-*`).
- Prefijo de clases `z-*`.
- Sin emojis.
- Iconos Lucide stroke 1.5.
- Colores de prioridad: tokens `--z-prio-p1`, `--z-prio-p2`, `--z-prio-p3` (agregar al archivo de tokens si no existen). Nunca hex literal.

---

## 6. PLAN DE FASES

### FASE 1 - Verificacion del estado actual y estructura de subareas

**Precondiciones:** ninguna.

**Acciones:**
1. Ejecutar en LOCAL y PROD:
   ```sql
   SELECT table_name FROM information_schema.tables
   WHERE table_schema='public' AND (
     table_name LIKE '%emergencia%'
     OR table_name LIKE '%evento_seguridad%'
     OR table_name LIKE '%tipo_evento%'
     OR table_name LIKE '%com_%'
   );
   ```
2. Reportar tablas existentes vinculadas al COM previo (Phase 1 anterior segun memorias).
3. Definir estrategia de convivencia/migracion (extender, paralelizar, o dropear si vacias).
4. Verificar en tabla `area`: existencia de "Secretaria de Seguridad". Crear si no existe.
5. Verificar en tabla `subarea`: existencia de "Policia Municipal" y "Defensa Civil", AMBAS vinculadas a la misma area "Secretaria de Seguridad". Crear las que falten.
6. Verificar tabla `ciudadano` (BUC) y que `nro_documento` este indexado.
7. Verificar proximo numero Alembic disponible (>=57).

**Entregables:**
- Reporte en chat con tablas pre-existentes y plan elegido.
- Subareas confirmadas con sus IDs (resueltos por nombre, no hardcoded).

**Validaciones de cierre:**
- `SELECT id, codigo, nombre FROM subarea WHERE codigo IN ('POLICIA_MUNICIPAL','DEFENSA_CIVIL');` devuelve 2 filas.
- Ambas con el mismo `id_area` (Secretaria de Seguridad).

**Que NO hacer:** no crear ninguna tabla `emergencia_*` todavia.

---

### FASE 2 - Tablas catalogo + seeds + endpoints de lectura

**Precondiciones:** Fase 1 cerrada y confirmada por el usuario.

**Acciones:**
1. Crear migracion Alembic con las tablas:
   - `emergencia_organismo_derivacion`
   - `emergencia_canal_ingreso`
   - `emergencia_prioridad`
   - `emergencia_estado`
   - `emergencia_tipo`
   - `emergencia_subtipo`
2. Crear CSVs de seed en `sql/tablas/` (6 archivos).
3. Crear `scripts/seed_catalogos_emergencias.py`:
   - `AsyncSessionLocal` + SQLAlchemy 2.x + `text()`
   - Sin acentos
   - Lee los CSVs
   - Idempotente (UPSERT por codigo unique)
   - Resuelve `id_subarea` por nombre normalizado
4. Aplicar migracion en LOCAL, validar conteos, aplicar en PROD.
5. Ejecutar seed en LOCAL y PROD.
6. Crear router `backend/app/api/routes/emergencias.py` con endpoints de **lectura** de seccion 4.1.
7. Registrar el router en `main.py` respetando orden de rutas.

**Entregables:**
- 1 migracion Alembic.
- 6 CSVs.
- 1 script seed.
- 1 router con 7 endpoints de lectura.

**Validaciones de cierre:**
- `SELECT count(*) FROM emergencia_tipo WHERE id_subarea = <policia>;` = 34
- `SELECT count(*) FROM emergencia_tipo WHERE id_subarea = <dc>;` = 16
- `SELECT count(*) FROM emergencia_subtipo;` > 100
- `SELECT count(*) FROM emergencia_organismo_derivacion;` = 12
- `SELECT count(*) FROM emergencia_estado;` = 7
- `SELECT count(*) FROM emergencia_canal_ingreso;` = 2
- `SELECT count(*) FROM emergencia_prioridad;` = 3
- `curl http://localhost:8000/api/v1/emergencias/tipos?id_subarea=<policia>` devuelve 34 tipos.
- `curl http://localhost:8000/api/v1/emergencias/tipos?id_subarea=<dc>` devuelve 16 tipos.

**Que NO hacer:** no crear `emergencia_evento` ni `emergencia_contacto_eventual` todavia.

---

### FASE 3 - Tabla evento + contacto eventual + endpoints escritura + log

**Precondiciones:** Fase 2 cerrada y validada.

**Acciones:**
1. Migracion Alembic con:
   - `emergencia_contacto_eventual`
   - `emergencia_evento`
   - `emergencia_log`
   - Secuencia `emergencia_evento_numero_seq`
   - Trigger `emergencia_log_no_mutate` + triggers UPDATE/DELETE
2. Extender router con endpoints de secciones 4.2, 4.3, 4.4.
3. Implementar generacion de `numero_operativo` en formato `EM-YYYY-NNNNNN`.
4. Implementar validaciones del POST /eventos.
5. Implementar registro automatico en log (CREACION, CAMBIO_ESTADO, etc.).
6. Implementar promocion a BUC con reasignacion de eventos previos.

**Entregables:**
- 1 migracion Alembic.
- Router con todos los endpoints de eventos.
- Logica de log append-only verificada.

**Validaciones de cierre:**
- POST de evento de prueba con denunciante eventual:
  - Evento creado con `numero_operativo` formato `EM-2026-NNNNNN`.
  - Entrada en `emergencia_log` con `tipo_accion='CREACION'`.
- Intento de `UPDATE emergencia_log SET observaciones='hack' WHERE id=1;` -> falla con excepcion.
- Intento de `DELETE FROM emergencia_log WHERE id=1;` -> falla con excepcion.
- `GET /denunciantes/buscar?dni=<dni BUC existente>` -> `origen=BUC`.
- `GET /denunciantes/buscar?telefono=<tel BUC existente>` -> `origen=BUC`.
- `GET /denunciantes/buscar?nombre=<nombre BUC existente>` -> `origen=BUC` con matches.
- `GET /denunciantes/buscar?dni=<dni inexistente>` -> `origen=NUEVO`.
- Crear contacto eventual, crear evento usandolo, promover a BUC, verificar que el evento ahora apunta a `id_ciudadano_buc` y `id_contacto_eventual` quedo en NULL.
- Cambio de estado de evento de PENDIENTE a EN_PREPARACION genera entrada en log.

**Que NO hacer:** no avanzar al frontend en esta fase.

---

### FASE 4 - Frontend recepcion + dispatcher + detalle

**Precondiciones:** Fase 3 cerrada y validada (endpoints funcionando).

**Acciones:**
1. Crear 3 paginas bajo `frontend/modulos/emergencias/` segun seccion 5.
2. Agregar tokens `--z-prio-p1`, `--z-prio-p2`, `--z-prio-p3` al archivo de tokens DS si no existen.
3. Crear modulos JS para cada pagina respetando el patron del shell vanilla.
4. Implementar polling de 30s en `emergencias_dispatcher.html`.
5. Integrar `ConfirmModal` en cambios de estado destructivos (DESESTIMAR, cierre).

**Entregables:**
- 3 paginas HTML + JS modulares.
- Tokens DS de prioridad agregados (si correspondia).

**Validaciones de cierre:**
- Abrir `emergencias_recepcion.html`, completar flujo con denunciante NUEVO, crear evento. Verificar:
  - Toast con `numero_operativo`.
  - Redireccion a detalle.
  - Aparece en dispatcher.
- Abrir `emergencias_recepcion.html` de nuevo, buscar el DNI ya cargado: ahora aparece como `origen=EVENTUAL`.
- Buscar por telefono y por nombre: ambos devuelven el contacto eventual.
- En detalle, promover el eventual a BUC. Buscar de nuevo el DNI: ahora `origen=BUC`.
- Ciclo completo de un evento: PENDIENTE -> EN_PREPARACION -> EN_CAMINO -> EN_SITIO -> RESUELTO. Verificar log con todos los pasos.
- Otro evento: PENDIENTE -> DERIVADO -> RESUELTO.
- Tercer evento: PENDIENTE -> DESESTIMADO con `veracidad=FALSA_ALARMA`.

**Que NO hacer:** no integrar mapa real, no implementar WebSockets, no UI de App Vecinos.

---

### FASE 5 - Endpoint publico App Vecinos

**Precondiciones:** Fase 4 cerrada. App Vecinos Stage 0 desplegado (segun memorias, esto ya esta).

**Acciones:**
1. Extender router con `POST /eventos/publico` segun seccion 4.5.
2. Verificar que el JWT scope `"publico"` esta correctamente aislado del scope `"agente"`.
3. Agregar a `emergencia_log` la `CREACION` desde canal `APP_VECINO`, con `id_usuario=NULL` y un nuevo campo para identificar al vecino emisor en `payload_json`.
4. Test E2E desde un cliente con JWT publico.

**Entregables:**
- Endpoint publico implementado.
- Test E2E pasando.

**Validaciones de cierre:**
- POST con JWT publico crea evento con `canal=APP_VECINO`, `id_operador_receptor=NULL`, `id_ciudadano_buc` resuelto del vecino, `estado=PENDIENTE`.
- POST con JWT publico NO puede crear eventos con `id_canal_ingreso != APP_VECINO`.
- POST con JWT publico NO puede acceder a endpoints de scope `"agente"` (GET /eventos/abiertos, etc.).
- El evento aparece en el dispatcher del operador con marca clara de origen App Vecinos.

**Que NO hacer:** no desarrollar UI de la app aqui; esa es responsabilidad del repo `zaris-vecinos`.

---

## 7. REGISTRO DE DECISIONES TOMADAS DURANTE LA IMPLEMENTACION

(Vacio al inicio. Cada fase, al cerrarse, agrega aqui las decisiones no triviales que se hayan tomado durante la ejecucion: cambios al schema, ajustes de seed, decisiones de UX no previstas, etc.)

### Fase 1 (cerrada 2026-06-10)

- **No es Alembic.** El proyecto usa migraciones SQL numeradas en `backend/migrations/` aplicadas con psql (local) y MCP Supabase (prod). La ultima era la 80; la Fase 1 uso la **81** (`81_emergencias_subareas_seguridad.sql`). La Fase 2 debe usar **82+**. La referencia del plan a "Alembic >=57" queda invalidada.
- **Greenfield confirmado.** 0 tablas `emergencia_*` / `evento_seguridad` / `tipo_evento` / `com_*` en LOCAL y PROD. No hay COM previo que migrar: estrategia = crear todo nuevo en Fase 2, sin convivencia.
- **`subarea` NO tiene columna `codigo`** (PK `id_subarea`, identidad por `nombre`). La validacion de cierre `WHERE codigo IN (...)` se reemplazo por resolucion por **nombre normalizado** (`translate(lower(nombre),'áéíóú','aeiou')`). Implicacion Fase 2: el seed resuelve `id_subarea` por nombre normalizado, no por codigo ni ID.
- **Area "Secretaria de Seguridad" existe DUPLICADA con drift invertido** (consecuencia conocida del cleanup mig 26): local tiene activa la id 8 (sin tilde), prod la id 28 (con tilde). Decision: colgar las subareas nuevas del area **activa de cada entorno**, resuelta por nombre normalizado; las duplicadas inactivas NO se tocaron (consolidarlas excede el alcance y arriesga FKs).
- **Subareas creadas** (mig 81, data-only, idempotente): "Policía Municipal" y "Defensa Civil", con tilde correcta en el nombre visible. IDs resultantes (informativos, nunca hardcodear): LOCAL 90/91 bajo area 8 · PROD 76/77 bajo area 28. Ambas activas, mismo `id_area` por entorno. Validacion de cierre cumplida.
- **BUC: la tabla es `ciudadanos` (plural) y el documento es `doc_nro`**, no `ciudadano`/`nro_documento` como asume el plan (secciones 2.7, 2.8, 4.3). Idem `usuarios` y `municipios` (plural). El indice de documento existente es **UNIQUE compuesto `uq_ciudadano_doc (doc_tipo, doc_nro)`** — una busqueda por `doc_nro` solo no aprovecha el prefijo del btree. Si la busqueda unificada de denunciantes lo requiere, evaluar indice simple sobre `doc_nro` en Fase 3 (hoy `/buc/ciudadanos/buscar` funciona asi y el volumen no lo exige).
- **Conflictos del plan vs CLAUDE.md detectados, a corregir al ejecutar Fase 2** (gana el proyecto, §28): (a) PKs deben ser `id_<tabla>` + campos estandar §10 completos (`id_subarea`, `id_usuario_alta`, `id_usuario_modificacion`) — el plan modela `id` pelado; (b) los tokens `--z-*` y clases `z-*` de la seccion 1/5.4 son el DS **legacy eliminado** (§13/§31) — usar tokens reales (`--zaris-orange`, `--fg-1`, componentes `*-zaris` en vanilla); (c) tablas nuevas nacen con `ENABLE ROW LEVEL SECURITY` (§21); (d) seeds separados del DDL (patron 75b) y CSVs segun convencion del repo, no `sql/tablas/`.

### Fase 2 (cerrada 2026-06-10)

- **Migracion 82** (`backend/migrations/82_emergencias_catalogos.sql`, aplicada en LOCAL y PROD): solo DDL de las 6 tablas catalogo — los seeds van separados (patron 75b, CLAUDE.md §21). Adaptaciones al plan: PKs `id_<tabla>` (ej. `id_emergencia_tipo`), `INTEGER/SERIAL` en vez de `BIGINT` (consistente con `subarea`/`usuarios`), estandar §10 completo, `id_municipio` nullable SIN FK fisica ("FK futura" §10, el plan decia NOT NULL REFERENCES), y **RLS habilitado sin politicas** en las 6 tablas (deny-all).
- **CSVs en `Tablas Iniciales/emergencia_*.csv`** (no `sql/tablas/` como decia el plan — esa carpeta no es la convencion del repo), delimitador `;`, UTF-8. Son la fuente autoritativa de la taxonomia.
- **Seed: `backend/seed_catalogos_emergencias.py`** (no `scripts/`): genera SQL compacto idempotente (un `INSERT ... SELECT FROM (VALUES ...) ON CONFLICT DO UPDATE` por tabla) con TODAS las FKs resueltas por codigo o nombre normalizado. Modo `--emit-sql <archivo>` emite el SQL para aplicarlo en prod via MCP (no hay conexion directa a Supabase desde local). Ejecutado en local (asyncpg multi-statement §5) y prod (3 tandas execute_sql). Conteos identicos en ambos: 34 tipos Policia / 16 DC / 147 subtipos / 12 organismos / 7 estados / 2 canales / 3 prioridades.
- **`color_token` = `prio-p1` / `prio-p2` / `prio-p3`** (la variable CSS `--prio-p1` etc. se creara en Fase 4 sobre los tokens DS actuales). NO se usaron los `z-prio-*` del plan: el namespace `--z-*` es el DS legacy eliminado (§31).
- **Tabla 3.7 del plan (tipos DC) traia 5 columnas vs 7 de Policia**: la ultima columna se interpreto como `es_emergencia` (SIMULACRO=false encaja; un simulacro no es emergencia) y `requiere_911=false` para TODOS los tipos DC (no especificado; la derivacion DC va directa al organismo, no via 911). Ajustable por UPDATE si el municipio lo pide.
- **Nombres visibles con tildes correctas** ("Desaparición de persona", "Vía pública") aunque el plan los traia sin tildes; los `codigo` quedan ASCII upper-snake. Subtipos: el token del plan se humanizo a nombre ("Otros_Sensores" -> "Otros sensores").
- **Router `backend/app/api/routes/emergencias.py`** (7 endpoints GET seccion 4.1) con guard JWT **a nivel router** (`APIRouter(dependencies=[Depends(get_current_user)])`, patron §39). Registrado en `main.py` (prefijo propio `/api/v1/emergencias`, sin colisiones greedy; comentario avisa que Fase 3 debe registrar segmentos fijos antes de `/{id}`).
- **Quirk cazado en smoke**: filtros opcionales `(:param IS NULL OR col = :param)` explotan con `AmbiguousParameterError` de asyncpg — fix `CAST(:param AS boolean/integer) IS NULL` (familia §5/§42).
- **Validaciones de cierre: todas cumplidas.** Conteos en DB local y prod + smoke local de los 7 endpoints con JWT (34/16 tipos, subtipos de ROBO=7, orden de estados correcto, 404 tipo inexistente, 401 sin token). **El router en PROD queda pendiente del proximo `git push`** (Railway autodeploy); la DB prod ya esta lista.

### Fase 3 (cerrada 2026-06-10)

- **Migracion 83** (`backend/migrations/83_emergencias_eventos.sql`, aplicada en LOCAL y PROD; triggers verificados con `pg_trigger` en prod): `emergencia_contacto_eventual` + `emergencia_evento` + `emergencia_log` + secuencia + triggers. Adaptaciones al plan: tablas reales `ciudadanos`/`usuarios`/`subarea`, `latitud`/`longitud NUMERIC(10,7)` (convencion reclamos §22, el plan decia `lat/lon DOUBLE PRECISION`), INTEGER/SERIAL, estandar §10 y RLS deny-all. El log queda exceptuado de §10 a proposito (sin `activo`/`fecha_modificacion`) y sus triggers anti-UPDATE/DELETE se verificaron ejecutando UPDATE y DELETE reales (ambos rechazan con "emergencia_log es append-only").
- **`numero_operativo` lo genera la DB** (secuencia + trigger BEFORE INSERT `trg_numero_emergencia`, patron `trg_nro_reclamo` §18), no el backend como decia el plan — cualquier via de INSERT futura queda numerada. El NOT NULL convive con el trigger (Postgres evalua NOT NULL despues de los BEFORE triggers). Reset anual de la secuencia sigue pendiente (seccion 8).
- **FSM en backend** (`TRANSICIONES` en `emergencias.py`, espeja el panel de acciones 5.3). Reglas extra: `RESUELTO`/`DESESTIMADO` SOLO via `POST /cerrar` (exige `veracidad`) y `DERIVADO` SOLO via `POST /derivar` (exige organismo) — `cambiar-estado` los rechaza con 422 explicativo, para que no se pueda cerrar sin veracidad ni derivar sin destino. Consecuencia del grafo: el cierre negativo (DESESTIMADO) solo es alcanzable desde PENDIENTE/EN_PREPARACION; un evento derivado se cierra RESUELTO.
- **Timestamps de KPI**: `fecha_hora_despacho` al pasar a EN_CAMINO, `fecha_hora_arribo` al pasar a EN_SITIO (o `marcar-en-sitio`), `fecha_hora_cierre` al llegar a terminal — todos con `COALESCE` para no pisar la primera marca.
- **Guard de nivel (4.6)**: todos los endpoints de contactos/denunciantes/eventos exigen `nivel_acceso <= 3` ademas del JWT. Scoping por subarea: el operador (nivel 3) con `usuarios.id_subarea` asignada solo ve/opera eventos de su subarea (listados filtran, detalle y mutaciones devuelven 403); admin/supervisor (<=2) exentos; operador sin subarea = fail-open (§27 — un drift de datos no debe dejar ciego al COM).
- **Promocion a BUC, 3 vias** (en este orden): `id_ciudadano` explicito en el body > **auto-vinculo si ya existe un ciudadano activo con ese DNI** > crear ciudadano nuevo. Crear exige `apellido`+`nombre`+`email` en el body (`ciudadanos.email` es NOT NULL y no se inventa); resto con los placeholders del alta publica §38 (CUIL `20+dni+9`, sexo OTROS, fecha_nac 1900-01-01, nacionalidad 1), `estado_validacion='verificado'`, `ficha_completa=FALSE`, la direccion del contacto va a `calle`. **NO crea cuenta de App Vecinos** (eso es del alta de Padrones §38, fuera del alcance del COM). Reasigna TODOS los eventos del contacto + log `PROMOCION_BUC` por evento + marca `convertido_a_buc`.
- **PATCH de evento**: cambios de tipo/subtipo/prioridad loguean con sus `tipo_accion` propios; las ediciones de otros campos se loguean como `NOTA` con `payload {campos_modificados}` (el CHECK de `tipo_accion` del plan no contempla 'EDICION' y no se amplio). Cambio de tipo exige misma subarea del evento y resetea el subtipo si no viene uno nuevo. Estado terminal: no editable (422).
- **Smoke reproducible `smoke_emergencias.ps1`** (raiz, 43 asserts, 43/43 OK): cubre todas las validaciones de cierre de Fase 3 incluida la promocion y el ciclo completo de estados. Usa DNI/telefono/nombre RANDOM por corrida: las corridas previas promueven contactos a BUC y la busqueda unificada (correctamente) los encuentra primero en BUC.
- **Quirk PS 5.1 en el smoke**: `(pipeline | Where-Object).Count` sobre un unico resultado da NULL — envolver en `@(...)`.
- En PROD solo se verifico lectura (sin sembrar eventos de prueba); el ciclo de escritura completo quedo validado en local con el smoke.

### Fase 4 (cerrada 2026-06-10)

- **Stack: modulo React, NO 3 paginas vanilla.** El plan (seccion 5) pedia HTML vanilla, pero CLAUDE.md §4 manda React para modulos nuevos complejos (form con estado + tablero con polling + detalle con timeline = el caso exacto) y §28 da prioridad al proyecto. Vive en `web-app/src/modules/emergencias/` embebido en el iframe del shell vanilla, como Reclamos/Turnos. Las "3 paginas" del plan son 3 rutas: `/emergencias` (Tablero/dispatcher), `/emergencias/recepcion`, `/emergencias/evento/:id`.
- **Item "Emergencias" PRIMERO en el sidebar** (pedido del usuario 2026-06-10): primer `<a class="nav-flat__item">` del nav en `index.html` (shell vanilla), icono Lucide `siren` SVG inline, label "Emergencias". En el shell React dev va segundo despues de dashboard (dashboard es HOME y no aparece en el sidebar vanilla).
- **Migracion 84**: fila `emergencias` en `modulos` con `min_nivel_acceso=3` (espeja el guard nivel<=3 del backend; sin la fila el item se oculta para todos, §12/§30). Local + prod.
- **Tokens de prioridad: `--prio-p1` `#c62828` / `--prio-p2` `#f57f17` / `--prio-p3` `#1f8a65`**, agregados a `design-system/colors_and_type.css` y espejados en `web-app/src/styles/tokens.css`. NO se uso el namespace `--z-prio-*` del plan (DS legacy eliminado §31). Colores lejos del naranja brand (regla §4). `emergencia_prioridad.color_token` guarda el nombre sin `--` (`prio-p1`); el front hace `var(--${token})`.
- **Dispatcher** (`pages/Dispatcher.tsx`): polling de 30s via `refetchInterval` de react-query (NO WebSocket, plan 0.3), orden prioridad+fecha lo da el backend, "hace Xm" en vivo con tick local de 30s, filtros subarea/prioridad/estado (estado client-side sobre los abiertos), acciones rapidas con los MISMOS modales del detalle (`components/EventoAccionModals.tsx`).
- **Cierre y derivacion SIEMPRE con modal propio** (veracidad obligatoria / organismo obligatorio) — espeja la regla de Fase 3 de que esos pasos no van por `cambiar-estado`. `window.confirm` prohibido (§29): todo con `Modal`/`ConfirmModal` de Agenda (cross-module import permitido).
- **Recepcion**: cronometro mm:ss desde el mount; prioridad autocompletada subtipo.override > tipo.default y editable (flag `prioridadTocada`); aviso rojo si el tipo `requiere_911`; canal hardcodeado `LLAMADA_TEL` (la recepcion ES el canal telefonico; APP_VECINO entra por la Fase 5); boton Crear deshabilitado hasta minimos completos. El form de contacto eventual aparece inline cuando la busqueda da `origen=NUEVO`, con el DNI/telefono buscado pre-llenado.
- **Promocion a BUC desde el detalle** (tab Denunciante): modal que pide apellido/nombre/email (los exige el backend para crear; si el DNI ya esta en BUC vincula solo).
- **Verificado navegando (§41)** en `localhost:5173` + backend local: tablero con los eventos del smoke, flujo completo recepcion (buscar DNI BUC -> usar -> Defensa Civil/Incendio/Forestal -> prioridad auto P1 -> crear `EM-2026-000025` -> detalle) -> EN_PREPARACION via modal -> historial con CREACION + CAMBIO ESTADO. Trampa cazada: el router es `createHashRouter` — navegar `localhost:5173/emergencias` (pathname) cae al catch-all y muestra dashboard; la URL real es `/#/emergencias`.
- Lat/lon y mapa NO se incluyeron en el form (plan 5.1 los marca "futuro mapa"; el backend ya los acepta).

### Fase 5 (cerrada 2026-06-10)

- **Router publico SEPARADO** (`backend/app/api/routes/publico_emergencias.py`, prefijo `/api/v1/publico/emergencias/*`, guard `get_current_ciudadano`), NO el `POST /eventos/publico` del plan dentro del router de agentes: `emergencias.py` tiene guard JWT-agente a NIVEL ROUTER (patron s39) y un endpoint publico adentro lo contradeciria. Sigue la convencion `publico_*` del proyecto (espejo de `publico_reclamos.py`).
- **El body del POST no puede elegir canal ni denunciante**: `id_canal_ingreso` no existe en el schema (APP_VECINO forzado server-side; si el cliente lo manda, pydantic lo ignora — verificado por smoke), `id_ciudadano_buc` sale SIEMPRE del token, `id_operador_receptor=NULL`, `id_usuario_alta=NULL`. Subarea/prioridad/organismo default derivados del tipo (el vecino no clasifica triage).
- **Endpoints extra no pedidos por el plan** (justificados): GET `/tipos` + `/tipos/{id}/subtipos` publicos (sin datos de triage interno — la PWA los necesita para el form) y GET `/eventos` "mis reportes" (seguimiento del vecino; excluye prioridad/organismo/operador). Rate limit 5/min por IP en el POST.
- **Log CREACION** con `id_usuario=NULL` y el vecino identificado en `payload_json` (`{origen:'app_vecinos', id_ciudadano, canal}`) — punto 3 del plan, sin columna nueva.
- **Marca visual**: badge "App Vecinos" (chip oscuro `--fg-1`, componente `CanalAppVecinoBadge` en `lib/ui.tsx`) en tarjeta del tablero y cabecera del detalle cuando `canal_codigo='APP_VECINO'`.
- **Validaciones de cierre: todas cumplidas** — smoke local 64/64 (13 asserts de Fase 5: canal forzado, scopes aislados 401 en ambas direcciones, payload del log) + smoke prod 10/10 + E2E real en prod: vecino demo (DNI 30555444, credencial sembrada) creo `EM-2026-000008` via el endpoint publico y aparece en el tablero con el badge.

### Pendientes menores cerrados en la misma sesion (2026-06-10)

- **Reset anual del numero operativo (mig 85)**: NO se uso cron. La secuencia global se reemplazo por **`emergencia_numerador (anio PK, ultimo_numero)`** con UPSERT atomico dentro de `fn_generar_numero_emergencia` (patron `tipo_tramite_numerador` s35): anio nuevo => fila nueva que arranca en 1, reset implicito sin piezas moviles. Backfill idempotente con GREATEST desde los eventos existentes; `emergencia_evento_numero_seq` dropeada. Verificado: local continuo en 26+, prod arranco en `EM-2026-000001`.
- **QA del scoping nivel 3**: smoke ampliado (8 asserts — /abiertos solo subarea propia, pedir otra subarea explicita devuelve vacio, detalle/mutacion/log cross-subarea 403, admin exento) + verificacion en navegador prod (tablero del operador solo Policia; deep-link a evento DC muestra "El evento pertenece a otra subarea"). Usuario QA/demo `operadorcom@municipio.gob.ar` (nivel 3, subarea Policia) creado en local y prod **con fila `agentes` vinculada** para sobrevivir al cron de integridad de cuentas (mig 77 suspenderia un usuario sin agente ni ciudadano).
- **Manual operativo**: `docs/manual_emergencias.html` (10 capturas reales, 10 secciones, receta s36) + card "EMERGENCIAS (COM)" primera en el modulo Guias.
- **Normalizacion OSM de direcciones** (pedido del usuario al cierre): direccion del EVENTO con `GeocodingSearch` (patron Reclamos — POIs validos: "incendio en el club X"; normaliza display_name + captura lat/lon que el backend ya persistia desde mig 83; editar a mano limpia las coordenadas) y domicilio del CONTACTO EVENTUAL con `AddressSearch` (patron Ciudadanos, `solo_direcciones=true`) pero **editable como fallback** — a diferencia de Ciudadanos (solo-OSM readonly), una emergencia no se frena porque el geocodificador no encuentre el punto. Manual regenerado (capturas 02/04/05 + texto).
- **Bug UX cazado por el QA en navegador prod**: `CerrarModal` inicializaba el radio Resuelto/Desestimado con `useState(permiteResuelto)` del PRIMER mount (el modal vive montado con `open=false`) y ofrecia un cierre que el FSM rechazaba (422 real contra prod). Fix: `useEffect` que re-sincroniza resultado/veracidad/observaciones al abrir. El 422 confirmo de paso que la defensa backend funciona.
- **Datos demo permanentes en prod** (para consulta): eventos `EM-2026-000001..11` cubriendo TODOS los estados (EN_CAMINO, EN_PREPARACION, DERIVADO, PENDIENTE, EN_SITIO, RESUELTO x3, DESESTIMADO x2, APP_VECINO pendiente), contacto eventual promovido a BUC con historial completo, vecino demo `30555444` (pass 123456) y operador COM (pass 123456).

---

## 8. PENDIENTES Y PROXIMAS ITERACIONES

Fuera del alcance de este plan, para iteraciones futuras:

- **Recursos operativos (moviles, equipos):** tabla `emergencia_recurso` con disponibilidad, asignacion, posicion GPS. Endpoint de asignacion. UI de gestion de flota.
- **Mapa real:** integracion Leaflet o Mapbox para visualizar eventos georeferenciados en el dispatcher.
- **WebSockets / push real-time:** reemplazar polling de 30s por notificacion server-sent.
- **Grabacion de audio:** integracion con un servicio (Twilio, S3, otro) para guardar el audio del llamado y vincularlo al evento via `audio_grabacion_url`.
- **KPIs y dashboard:** tiempos promedio de despacho/arribo/cierre por tipo, por subarea, por operador. Mapa de calor de eventos.
- **UI de reporte de emergencia en la PWA `zaris-vecinos`:** el backend publico (Fase 5) ya esta en prod; falta la pantalla en el repo de la PWA (consume `GET /publico/emergencias/tipos` + `POST /publico/emergencias/eventos` + `GET /publico/emergencias/eventos`).
- **Integracion con camaras municipales:** canal `CAMARA` para alertas automaticas.
- **Notificacion automatica al vecino:** SMS/email/push cuando cambia el estado de su evento (si fue creado via App Vecinos).
- **Reportes para autoridades:** export PDF/CSV de eventos por rango de fecha.
- **Cifrado de datos sensibles:** evaluar cifrado columnar para `observaciones` cuando contienen menores, violencia de genero o salud mental.

---

## 9. GLOSARIO OPERATIVO

| Sigla | Significado |
|---|---|
| BUC | Base Unica de Ciudadanos. Padron municipal de ZGE. |
| CATE | Central de Atencion Telefonica de Emergencias (PBA). |
| COM | Centro de Operaciones Municipales. Sala desde donde un municipio atiende llamados de seguridad y emergencias propias. |
| CSAT | Customer Satisfaction. Encuestas de satisfaccion (modulo ZGE). |
| DC | Defensa Civil. |
| DDL | Data Definition Language. SQL de creacion/modificacion de schema. |
| DS | Design System. Sistema de diseno ZARIS (`--z-*` tokens, fuentes, iconos). |
| FSM | Finite State Machine. Maquina de estados. |
| KPI | Key Performance Indicator. |
| MinSeg PBA | Ministerio de Seguridad de la Provincia de Buenos Aires. |
| MSeg | Idem MinSeg. |
| OT | Orden de Trabajo. |
| PBA | Provincia de Buenos Aires. |
| PoC | Proof of Concept. |
| PWA | Progressive Web App. La App Vecinos es una PWA. |
| RESO-2022-166 | Resolucion 166/2022 del MinSeg PBA. Establece la taxonomia oficial de tipos/subtipos del 911. |
| SAEP | Sistema de Atencion de Emergencias Provincial. |
| SAME | Sistema de Atencion Medica de Emergencias. Linea 107. |
| SLA | Service Level Agreement. Tiempo comprometido de respuesta. |
| SNIC | Sistema Nacional de Informacion Criminal. |
| SPB | Servicio Penitenciario Bonaerense. |
| ZGE | ZARIS Gestion Estatal. Suite municipal. |

---

**FIN DEL DOCUMENTO**
