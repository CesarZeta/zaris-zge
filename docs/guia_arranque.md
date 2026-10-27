# Guía de arranque de un municipio nuevo

Para el administrador o la administradora de un municipio que acaba de darse de alta en ZARIS. Dice
qué cargar primero y en qué pantalla, circuito por circuito. El detalle técnico de cada tabla y de lo
que pasa si falta algo está en [`guia_arranque_tablas.md`](guia_arranque_tablas.md).

## Lo que ya está hecho al recibir la invitación

- El municipio, con sus direcciones (`<municipio>.zge.zaris.com.ar` para el equipo municipal,
  `<municipio>.vecinos.zaris.com.ar` para los vecinos y `<municipio>.agentes.zaris.com.ar` para la
  app de agentes).
- Las **6 áreas fijas** (secretarías). Se pueden renombrar; no se pueden dar de baja.
- Los catálogos que se eligieron en el alta, copiados del modelo (subáreas, tipos de reclamo,
  trámites, encuestas, feriados…).
- La configuración del sistema, con valores por defecto.
- Los módulos habilitados para el municipio.
- Tu cuenta de administrador, tu ficha y tu agente. Al aceptar la invitación elegís la clave y
  vinculás la app de códigos del celular (Google Authenticator, Microsoft Authenticator o similar).

## Orden de carga

Lo que está en negrita es lo que bloquea a lo que sigue.

1. **Configuración → Identidad:** nombre, logo y colores del municipio.
2. **Configuración → Sistema:** la **zona de búsqueda de direcciones** (centro y radio). Sin ella, el
   buscador de direcciones de todos los formularios responde «El municipio no tiene configurada su
   zona de búsqueda». Revisá también encuestas y asignación automática. Una clave que figura como
   «No está cargada» usa su valor por defecto hasta que la guardes.
3. **Maestros → Áreas y Subáreas:** las gestiones de cada área. Cada cuenta interna necesita una
   subárea, y de las subáreas cuelgan los tipos de reclamo, las prestaciones y los trámites.
4. **Usuarios:** las cuentas del equipo (supervisores, atención, gestión), con su subárea. Si el
   municipio tiene un tope de cuentas, la pantalla muestra «N de M cuentas activas».
5. **Maestros → Agentes y Equipos:** cargos, auditores y equipos de trabajo.
6. Por circuito, según los módulos que use el municipio:
   - **Reclamos:** tipos de reclamo con su subárea y su tiempo de resolución (Maestros → Tipos de
     reclamo). Para que las órdenes de trabajo se asignen solas, agentes de nivel Gestión en cada
     subárea y la asignación automática encendida en Configuración → Sistema.
   - **Turnos:** primero **Agenda → Espacios** (las ubicaciones de atención) y su
     **disponibilidad**; después **Turnos → Prestaciones**. Sin disponibilidad no se puede dar un
     turno. La Guardia necesita además el espacio «Guardia» y el módulo Emergencias.
   - **Trámites:** Trámites → Tipos de trámite: crear el tipo, sus estados, transiciones, campos y
     documentos, y **publicar la versión**. Sin versión publicada no se puede iniciar un trámite.
   - **Emergencias:** tipos y subtipos de emergencia por subárea (Policía Municipal, Defensa Civil).
   - **Entradas y Agenda:** espacios, y eventos con cupo.
   - **Encuestas:** las plantillas vienen del modelo; se encienden en Configuración → Sistema.
7. **Contactos:** las fichas de ciudadanos y empresas se cargan solas a medida que se atiende, o desde
   Contactos. Los vecinos pueden darse de alta en el portal del municipio.

## Si algo no anda

- Un módulo que no aparece en el menú no está habilitado para el municipio: lo habilita el soporte de
  ZARIS.
- «Llegó al tope de cuentas activas»: dar de baja una cuenta o pedir al soporte que amplíe el tope.
- Una invitación vencida o usada: pedir al soporte que la reenvíe.
