# PLAN — Registro previo del vecino y de la empresa en toda transacción

> **Estado: definiciones de César tomadas el 2026-11-23; falta su respuesta a §4 antes de codear.**
> Avance en [`ESTADO.md`](ESTADO.md).

## 1. Definiciones de César (2026-11-21 y 2026-11-23)

1. **Todo empieza por el registro de la persona** y después, eventualmente, de sus empresas. Vale igual cuando el
   vecino se autogestiona y cuando lo atiende un agente municipal.
2. Para cargar **cualquier transacción** (reclamo, turno, entrada, trámite) el dato del vecino es obligatorio y tiene
   que estar **previamente cargado** en el sistema.
3. **Call center:** el agente exige los datos, da de alta a la persona y recién ahí registra el reclamo.
4. **Única excepción: las emergencias.** También pueden buscar al vecino (es recomendable), pero por el apremio se
   permite seguir sin ese dato.
5. **El alta de persona humana y jurídica** se hace con una interfaz similar en el backoffice y del lado del vecino,
   ocultando algún dato si hiciera falta (no se espera que haga falta).
6. **Vocabulario:** reclamo, relevamiento, turno, entrada y trámite son **tipos de transacción**. El **canal** es la
   interfaz por la que se registra: call center, app del vecino, web del portal del vecino, app de agentes.

## 2. Realidad verificada (2026-11-23, código y producción)

| Circuito | Persona obligatoria | Exige cuenta del portal |
|---|---|---|
| Trámites (backoffice y portal) | Sí | **Sí** (`services/tramites/alta.py`) |
| Reclamos (backoffice) | Sí (`POST /reclamos` pide `id_ciudadano`) | No |
| Turnos (backoffice) | Sí (0 turnos sin persona) | No |
| Entradas (backoffice) | Sí (0 reservas sin persona) | No |
| Reclamos, turnos y entradas (app del vecino) | Sí, sale del token | Sí, por definición |
| **Página pública de turnos** (`#/turnos-autoservicio`) | **La crea con solo el DNI y datos de relleno** | No |
| **Página pública de un evento** (`#/autoservicio/<token>`) | **La crea con solo el DNI y datos de relleno** | No |
| Relevamientos | No lleva vecino | No corresponde |
| Emergencias | Opcional | Exceptuadas |

- En producción no hay ningún reclamo, turno ni reserva sin persona. Los que no tienen cuenta son fichas anteriores:
  de 953 vecinos activos de San Andrés, 7 tienen cuenta (250 son del generador demo y 91 fichas demo de funcionarios,
  que por regla no reciben cuenta nunca).
- Las dos páginas públicas usan `buscar_o_crear_ciudadano_por_dni` (fecha 1900-01-01, CUIL = DNI, correo inventado).
  En producción crearon **1** vecino así.
- **Alta de persona:** los mismos datos de los dos lados, salvo el tipo de documento (solo en el backoffice) y la
  contraseña (solo del lado del vecino). El alta del backoffice crea la cuenta y manda el correo de activación.
- **Alta de empresa:** existe en el backoffice. Del lado del vecino **no hay pantalla** (el endpoint
  `POST /publico/alta/empresa` está en el backend y ninguna app lo usa).

## 3. Fases propuestas

- **F1 — Cerrar el alta con solo el DNI.** Las dos páginas públicas dejan de reservar: muestran la prestación o el
  evento y llevan a ingresar o a registrarse en el portal del vecino. El backend responde 410 en los dos POST anónimos
  y se retira `buscar_o_crear_ciudadano_por_dni`. Los links ya emitidos para ver o cancelar un turno o una reserva
  siguen funcionando. Los botones «copiar enlace» de Turnos, Entradas y Agenda pasan a dar la URL del portal.
- **F2 — Backoffice: atender empieza por el registro.** En reclamos, turnos, entradas y trámites, el buscador de
  vecino ofrece dar de alta a la persona **sin perder lo que se estaba cargando** (modal, no otra pantalla) y vuelve
  con el vecino elegido. Mismo control en el backend para los cuatro circuitos (según §4).
- **F3 — Alta de empresa del lado del vecino** (portal y app), con los mismos datos que el backoffice, para el vecino
  ya registrado.
- **F4 — Igualar las dos altas de persona** (tipo de documento, textos y validaciones) y documentar.

**No cambia:** emergencias (incluidos SOS y pánico), Guardia (viene de una emergencia), relevamientos, subreclamos y
retrabajos (heredan el vecino del reclamo original). Lo ya cargado no se toca.

## 4. Decisión que falta

**Una ficha vieja, con la persona cargada pero sin cuenta del portal, ¿puede hacer un reclamo, un turno o una reserva?**
- **A (recomendada):** sí; alcanza con que la persona esté registrada, y al atenderla se ofrece completar la ficha (al
  guardarla se crea la cuenta). Los trámites siguen exigiendo la cuenta, como hoy.
- **B:** no; se exige la cuenta en los cuatro circuitos. En San Andrés bloquea a 946 de los 953 vecinos hasta abrir y
  guardar su ficha, y los vecinos demo no podrían usarse para mostrar el sistema.
