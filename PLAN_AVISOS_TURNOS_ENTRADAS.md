# Avisos de turnos y entradas al vecino — propuesta

> **Estado (2026-11-24):** César aprobó el tema el 2026-11-23; el detalle de abajo espera su visto bueno. Sin código todavía.

## Situación verificada

- Hoy no sale **ningún** aviso al sacar, cambiar o cancelar un turno o una entrada. Los reclamos, las emergencias y los trámites sí avisan (bandeja «Alertas», notificación y, según el caso, correo).
- Toda transacción nueva ya exige la cuenta del vecino, así que siempre hay a quién avisarle.
- **Datos de demostración (producción, San Andrés, 2026-11-24):** unos 45 turnos reservados por día hábil, todos de vecinos con correo ficticio y cuenta sin activar. De 953 vecinos activos, 4 tienen la cuenta activada. Un recordatorio sin filtro mandaría unos 45 correos diarios a casillas inexistentes y dañaría la reputación del remitente.

## Qué se le avisa al vecino

| Momento | Bandeja «Alertas» | Notificación | Correo |
|---|---|---|---|
| Se reserva el turno o la entrada | sí | sí, si la cargó un agente | sí |
| El municipio cambia la fecha o la hora | sí | sí | sí |
| El municipio cancela el turno, la reserva o el evento | sí | sí | sí |
| El vecino cancela desde la app | no (la pantalla ya se lo confirma) | no | no |
| Recordatorio el día anterior, a la mañana | sí | sí | sí |

- **A quién le sale el correo:** solo a quien tiene la cuenta activada, es decir, el correo confirmado. La notificación ya depende de que la persona la haya activado en su teléfono. Quien no activó la cuenta encuentra el aviso en su bandeja cuando entra. La regla vale igual para los datos reales y los de demostración, sin excepciones por dominio de correo.
- **Reserva para el mismo día, o para el siguiente con el recordatorio ya enviado:** solo la confirmación.
- **Contenido:** qué, cuándo, dónde y el enlace a «Mis turnos» o «Mis entradas» del portal de su municipio. Un turno de la gestión Salud **no nombra la prestación** en el correo ni en la notificación: es un dato de salud que queda a la vista en la pantalla bloqueada.
- Si el municipio no tiene habilitado el módulo, no sale nada.

## Cómo se hace

1. **Migración (la corre César, lleva `DROP CONSTRAINT`):** tipos `turno` y `entrada` en `ck_ciudadano_aviso_tipo`; `turnos.recordado_en` y `evento_reservas.recordado_en`, que garantizan un solo recordatorio. Al reprogramar, la marca vuelve a vacío.
2. **`services/avisos_turnos.py`:** una función por momento, después del commit y sin frenar la operación. Vías a cubrir: turnos (alta del backoffice, alta del vecino, reprogramar, cancelar, cancelar por enlace) y entradas (alta del backoffice, alta del vecino, cancelar la reserva, y cambiar, cancelar o eliminar el evento).
3. **Recordatorio:** tarea diaria a las 9:00 de Argentina, por municipio, con el resumen habitual de las tareas programadas.
4. **PWA:** los avisos nuevos abren «Mis turnos» o «Mis entradas».

**Fases:** F1 migración, confirmaciones y cambios (backend y prueba automática) · F2 recordatorio y tarea programada · F3 PWA, recorrida y material de marketing (sacar el «Próximamente»).

## Decisiones para César

1. ¿El cuadro de momentos queda así? **Recomendación: sí.** Suma el aviso de cambio y de cancelación, que no estaba en el pedido y es el que más le importa al vecino.
2. ¿El correo va solo a cuentas activadas? **Recomendación: sí.**
3. ¿Un solo recordatorio, el día anterior a las 9:00? **Recomendación: sí.**
4. ¿Se omite la prestación en los turnos de Salud? **Recomendación: sí.**
