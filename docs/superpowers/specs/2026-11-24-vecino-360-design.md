# Vecino 360 — diseño

Fecha: 2026-11-24. Estado: borrador para aprobación de César.
Marcas: **[César]** decidido por César · **[Propuesta]** llamada de Claude, corregible.

## 1. Intención

Ver en un solo lugar todo lo que una persona o una empresa tuvo con el municipio. **[César, 2026-10-27 y 2026-11-24]** Para tres públicos:

| Dónde | Quién | Para qué |
|---|---|---|
| Ficha del vecino y de la empresa | El agente que atiende | Contexto rápido con el vecino enfrente: qué tiene abierto y qué pasó antes |
| Datos | La conducción | Panorama: cuánta gente interactúa, quién tiene asuntos abiertos, quién recurre |
| Portal del vecino, «Historial» | El vecino | Ver su propio historial |

Hoy (San Andrés, prod, 2026-11-24): 3.354 reclamos, 4.578 turnos (3.639 de Salud), 5.070 entradas, 723 trámites (237 de vecinos, 338 de empresas, 148 internos), 281 emergencias (176 con vecino identificado). 841 de 953 vecinos tienen algo; mediana 4, máximo 66. 64 empresas con trámites, una sola representación cargada, ningún reclamo a nombre de empresa.

## 2. Objetivos, no-objetivos, anti-objetivos

**Objetivos**
1. Una línea de tiempo por persona y por empresa: reclamos, turnos, entradas, trámites y emergencias.
2. Una sola regla de permisos, en el servidor, para las tres superficies.
3. «Historial» del portal completo: suma trámites, filtro por tipo y lo de sus empresas.
4. Datos: tablero «Vecino 360», con el control de acceso del módulo.

**No-objetivos**
- Contenido clínico, en cualquiera de las tres. La historia clínica sigue en Turnos con su registro de accesos.
- Cambiar los permisos de los módulos.
- Detalle de los trámites de empresa en el portal (segunda etapa del spec de trámites del vecino).
- Exportar o imprimir el historial de una persona.
- Acciones desde la línea de tiempo: solo abre el asunto en su módulo.
- Unir personas duplicadas o vincular emergencias anónimas.

**Anti-objetivos (aunque funcione, sería un fracaso si…)**
- Alguien se entera por acá de algo que su módulo no le muestra: ni el asunto, ni una cantidad, ni un tipo vacío.
- Un vecino ve algo interno (auditoría, estados ocultos de trámites, triage) o de una empresa que no representa.
- Los números de Datos no coinciden con los de los otros tableros para el mismo alcance.

## 3. Construcción elegida

**A. Un servicio único en el servidor** **[César]**: `backend/app/services/interacciones.py` arma la lista normalizada y aplica permisos; lo usan la ficha, el portal y Datos. Se descartaron: **B**, que cada pantalla consulte a cada módulo (el listado de reclamos no filtra por vecino, sin paginado real, permisos repartidos, sin totales), y **C**, una tabla que registre cada movimiento (duplica el dato real; el volumen no lo justifica).

Sin migración, salvo la de §7.2 si se aprueba.

## 4. La interacción

| Tipo | Persona | Empresa | Fecha de la línea | Abierto si |
|---|---|---|---|---|
| reclamo | `id_ciudadano`, sin relevamientos | `id_empresa` | alta | Sin asignar, En gestión o En espera |
| turno | `id_ciudadano` | — | fecha y hora del turno | reservado o llamado, y fecha ≥ hoy |
| entrada | `id_ciudadano` | — | fecha y hora del evento | reservada, y fecha ≥ hoy |
| trámite | `id_ciudadano_iniciador` o `id_ciudadano_representante` | `id_empresa_iniciadora` | alta | no archivado y estado no final |
| emergencia | `id_ciudadano_buc` | — | recepción | estado no terminal |

- Solo filas activas y del municipio. Los trámites internos no son de ninguna persona.
- Un turno o entrada pasado que quedó sin registrar **no es «abierto»** (hoy hay 23 turnos así): se muestra como «Sin registrar» **[Propuesta]**. «Hoy» es el día local del municipio.
- **Campos comunes:** `tipo`, `id`, `numero`, `titulo`, `estado`, `color`, `abierto`, `fecha`, `fecha_cierre`, `gestion`, `canal`, `calificacion` (1 a 5, de la encuesta respondida de ese asunto), `empresa` (si fue a nombre de una) y `detalle` (lugar y quién atiende, en turnos y entradas).
- **Título:** tipo de reclamo, prestación, nombre del evento, tipo de trámite con su asunto, o en emergencias la opción que eligió el vecino y, si no hay, el tipo del COM.
- **Orden:** fecha descendente, con desempate por tipo e id. Paginado de a 20 en el servidor.
- **Resumen:** abiertos por tipo, total, último contacto (la mayor fecha de alta) y calificación promedio. Se calcula sobre lo que ese usuario puede ver.

## 5. Permisos del backoffice

Regla **[Propuesta aceptada]**: cada uno ve lo mismo que en el módulo, y lo demás no se nombra ni se cuenta. El servicio **reutiliza** los alcances existentes; no los copia.

| Tipo | Requisito | Alcance |
|---|---|---|
| reclamo | módulo `reclamos` | niveles 2 y 4: su subárea (`_subarea_scope_listado`); sin subárea, el tipo no aparece; 1, 3 y 5: todos |
| turno | módulo `turnos` | `_scope_turnos_para_usuario`: hasta nivel 2, todos; el resto, los propios o los de espacios de su subárea |
| entrada | módulo `entradas` | sin recorte, como hoy |
| trámite | módulo `tramites` | sin recorte, como hoy |
| emergencia | módulo `emergencias` **y** nivel ≤ 3 | nivel 3: su subárea (`_filtro_scope_subarea`) |

- «Módulo» es `modulos_permitidos` (nivel mínimo del municipio más excepciones por usuario). El super administrador, con el municipio elegido, como nivel 1.
- **Turnos de Salud [Propuesta]:** quien no pasa `permiso_historia_clinica` los ve como «Turno de Salud», sin prestación, lugar ni agente. Es más restrictivo que el listado de Turnos, porque acá alcanza con abrir una ficha. La calificación de ese turno tampoco se muestra.
- Si el usuario no tiene ningún tipo, la pestaña no existe y el endpoint da 403.
- El endpoint exige además el módulo `padrones`. Ficha de otro municipio o dada de baja: 404.
- No se registra cada apertura **[Propuesta]**: no muestra nada que el usuario no pueda abrir ya. El acceso del super se registra como hoy.

## 6. Ficha del vecino y de la empresa

`GET /api/v1/interacciones/ciudadano/{id}` y `/empresa/{id}` — `tipos`, `solo_abiertos`, `limit` (máx. 100), `offset` → `{resumen, tipos_visibles, total, items}`.

- **Pestañas «Datos | Interacciones»** en la consulta y la edición de las dos fichas; en el alta no. Rutas `/ciudadanos/:id/interacciones` y `/empresas/:id/interacciones`. Con cambios sin guardar, avisa antes de cambiar de pestaña.
- **Arriba:** abiertos por tipo (son filtros), total, último contacto, calificación promedio. Debajo, filtros por tipo y «Solo abiertos».
- **Cada renglón:** fecha, tipo con ícono, número, título, estado, calificación y «por Empresa X» si corresponde.
- **«Abrir»** en reclamos (`/reclamos/:id`), trámites (`/tramites/:numero`) y emergencias (`/emergencias/evento/:id`). Turnos y entradas no tienen página propia: se despliegan en el lugar.
- En la ficha del vecino, sus empresas enlazan a la ficha de cada una, y al revés los representantes.
- En Contactos → Buscar, el resultado suma el botón «Interacciones», para llegar en un clic.
- Solo componentes y tokens existentes; `Skeleton` y `EmptyState`. Modo oscuro.

```
PÉREZ, Juan · DNI 12.345.678             [Datos] [Interacciones]
Abiertos: 2 reclamos · 1 trámite   Último contacto 12/11   Calificó 4,2
[Todos] [Reclamos] [Turnos] [Entradas] [Trámites]   ( ) Solo abiertos
────────────────────────────────────────────────────────────────
12/11  Trámite  POD-…-0098   Poda de árbol   En espera del vecino   Abrir
03/11  Reclamo  REC-…-3480   Bache           Resuelto · 4/5         Abrir
28/10  Turno de Salud                        Cumplido               ▾
```

## 7. Portal: «Historial»

### 7.1 Mío
`GET /api/v1/publico/interacciones` (token del vecino) reemplaza en `HistorialPage` las cuatro consultas. El título sigue siendo «Historial» **[César]**.

- Suma los trámites. Filtros: Todo, Reclamos, Turnos, Entradas, Trámites, Emergencias; «Ver más» de a 20.
- Estados **como los ve el vecino hoy en cada pantalla**: reclamo en auditoría o auditado es «Resuelto» (`_ESTADO_VECINO`), estado oculto de trámite (`_mostrar_estado_visible`), textos visibles. El vecino ve completos sus turnos de Salud: son suyos.
- Tipos de un módulo que el municipio no tiene: no aparecen.
- Toque: abre el detalle (reclamo, trámite) o la lista (emergencias, turnos, entradas), como hoy.
- La consulta vieja sigue viva para las apps con la versión anterior.

### 7.2 De mi empresa
Selector «Míos | {empresa}» si representa alguna: reclamos y trámites de la empresa, sin detalle (número, tipo, estado visible, fecha).

**[Propuesta]** Lo de la empresa lo ve solo quien tenga la **representación confirmada por el municipio**: migración con `ciudadano_empresa.confirmada_en` e `id_usuario_confirma`; las que carga un agente nacen confirmadas, las del portal quedan pendientes y un agente (niveles 1 a 4) las confirma desde la ficha de la empresa. La única que hay hoy queda confirmada por la migración solo si la cargó un agente; si no, pendiente. Mientras está pendiente, el vecino ve «Pendiente de confirmación del municipio».

## 8. Datos

### 8.1 Control de acceso (primero)
Los tres routers de Datos usan `require_modulo("bi")`: 403 sin el módulo. El inicio no los usa (verificado). Smokes que los llaman con otras cuentas, a ajustar.

### 8.2 Tablero «Vecino 360»
Cuarta tarjeta de la landing, ruta `/bi/vecino360`, endpoints `/api/v1/bi/vecino360/*`.

- **Universo:** vecinos con ficha activa; tipos reclamo, turno, entrada y trámite. **Emergencias, relevamientos y Guardia afuera**, como en el modelo de indicadores **[César, 2026-11-23]**. Interruptor «Vecinos | Empresas».
- **Filtros:** período, localidad de la ficha y tipo.
- **Tarjetas:** vecinos con actividad en el período; con algo abierto hoy; recurrentes; satisfacción (% de 4 y 5, la regla de Encuestas y del Ejecutivo).
- **Recurrente:** 10 o más reclamos en los últimos 12 meses (16 hoy; con 3 o más serían 601) **[Propuesta]**. El número va en Configuración → Sistema (`recurrencia_reclamos_12m`, 10).
- **Gráficos:** por tipo; por cantidad de tipos distintos; por localidad; por canal; evolución mensual de los últimos 12 meses. Reglas de la skill `modulo-bi` (etiqueta de total, pastilla, drill-down, CSV).
- **Canal:** en reclamos, `canal_origen`; en turnos y entradas, autoservicio o atención municipal (`origen`); en trámites, portal si lo creó el vecino (movimiento de creación con `id_ciudadano_actor`) y si no, atención municipal.
- **Listas**, ordenables y paginadas en el servidor: «Con más interacciones» y «Con asuntos abiertos más antiguos». Nombre, localidad, cantidades por tipo, abiertos y días del más antiguo. Abren la ficha en «Interacciones», con los permisos de quien mira.
- **CSV:** sí en los gráficos; **no en las listas de personas [Propuesta]**, por ser datos personales.
- Textos del período y medición idénticos a los otros tableros.

## 9. Fases

| Fase | Contenido | Se publica |
|---|---|---|
| 1 | Control de acceso en Datos | sola |
| 2 | Servicio, endpoints y pestañas en las dos fichas | sola |
| 3 | «Historial» del portal y representación confirmada | servidor primero, después la app |
| 4 | Tablero de Datos | sola |

## 10. Verificación

- `smoke_interacciones.py` in-process, con y sin barrera: cada nivel (1 a 5), con y sin subárea, con excepción por usuario, super; turno de Salud enmascarado; lo no visible no se cuenta; otro municipio 404; paginado sin repetidos ni faltantes; abiertos según §4; empresa.
- Portal: auditoría y estados ocultos no se filtran; empresa ajena 404; representación pendiente no ve.
- **Cuadre:** los totales por tipo de una persona coinciden con lo que devuelve cada módulo al mismo usuario, y los de Datos con los tableros existentes.
- `smoke_aislamiento.py`, `smoke_barrera.py`, barridos, y los smokes de Datos con el guard nuevo.
- Recorrida navegando: ficha con un agente de Atención, uno de Gestión y un administrador; portal en 390 px; Datos; modo oscuro.
- Tiempo: una persona con 66 interacciones, menos de 300 ms en el servidor.

## 11. Queda a criterio de quien construye

Íconos por tipo, textos de los vacíos, índices que pida el plan de consulta, nombres internos, y si el resumen viaja con la lista o aparte.
