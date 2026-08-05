# Spec: Pedidos del almacén

Proyecto `almacen-de-paco`. Generado desde `planos.json` (la fuente de verdad): no editar a mano.

**Estado del diseño:** listo para revisar · **modo:** entrevista.

**Cobertura observada en el código actual:** no implementado.

## 1. Propósito

La app del almacén de piensos: los pedidos que hoy llegan por WhatsApp y se copian a mano al Excel pasarán a registrarse y facturarse solos. La IA lee el mensaje y monta un borrador, María lo confirma, el código factura y avisa, y Jorge aprueba las excepciones desde el móvil.

Cuando llega un pedido por WhatsApp, María necesita registrarlo y facturarlo sin copiarlo a mano para que el despacho medio baje de 40 a 10 minutos.

Criterios de éxito:
- en un mes, el tiempo medio entre que llega el mensaje y sale el pedido baja de 40 a 10 minutos, y ningún pedido se pierde.

## 2. Actores y vocabulario

- **Paco · cliente**
- **María · operadora · estado: activa**
- **Carmen · operadora · estado: activa**
- **Jorge · supervisor · estado: activa**
- **Teresa · preparadora · estado: activa**

- "pedido": lo que un cliente pide de una vez, con sus sacos y su fecha; no es lo mismo que la factura
- "deuda": dinero pendiente de facturas anteriores; con deuda (o con un pedido de más de 1.000€, ver G-1) hace falta visto bueno de Jorge

## 3. El proceso (flujos)

La versión gráfica vive en el visor local del paquete (visor/servir.py).

Lo que se construye son los flujos "con la app"; los flujos "hoy" son la foto del antes y se incluyen como contexto.

### El mismo pedido, con la app [con la app · origen: usuario]

El reparto del trabajo: qué queda en personas, qué hace código normal y qué hace un modelo de IA. La IA propone, María confirma: nada se factura sin ojos humanos.

- [persona] Llegó un pedido por WhatsApp · Paco
- [automático: IA] La app leyó el mensaje y montó un borrador de pedido
- ⚠ Excepción: ¿la app entendió el mensaje?
    - si no (audio raro, remitente desconocido, texto ambiguo):
        - [automático: código] Se dejó como pendiente de revisión y se avisó a María por WhatsApp
        - [persona] Lo registró a mano o lo descartó · María
        - …y vuelve al flujo
    - camino normal: sí lo entendió
- [persona] Revisó el borrador y lo confirmó · María
- [automático: código] Se comprobó el stock
- ⚠ Excepción: ¿había stock?
    - si no había:
        - [automático: código] Se avisó a María por WhatsApp
        - [persona] Llamó al proveedor · María
        - …y vuelve al flujo
    - camino normal: sí había
- ⚑ Regla: ¿hacía falta el visto bueno de Jorge? (deuda o más de 1.000€)
    - si sí, y Jorge aprobó:
        - [persona] Aprobó desde el móvil · Jorge
        - …y vuelve al flujo
    - si sí, y Jorge rechazó:
        - [persona] Rechazó desde el móvil, escribiendo el motivo · Jorge
        - [automático: código] Se dejó el pedido como anulado y María vio el motivo en su panel
        - aquí termina este camino
    - camino normal: no hacía falta
- [automático: código] Se generó la factura
- [automático: código] Se avisó al almacén por WhatsApp
- [persona] Preparó el pedido y lo marcó como enviado · Teresa

### Un pedido, de la llamada al envío [hoy · origen: usuario]

Cómo funciona el negocio ahora mismo, sin la app.

- [persona] Llegó un pedido por WhatsApp · Paco
- [persona] Lo pasó al Excel · María
- ⚠ Excepción: ¿había stock?
    - si no había:
        - [persona] Llamó al proveedor · María
        - …y vuelve al flujo
    - camino normal: sí había
- [persona] Hizo la factura en Word · María
- ⚑ Regla: ¿hacía falta el visto bueno de Jorge?
    - si sí: debía dinero o el pedido pasaba de 1.000€:
        - [persona] Aprobó el pedido · Jorge
        - …y vuelve al flujo
    - camino normal: no hacía falta
- [persona] Preparó y envió el pedido · Teresa

## 4. Recorridos, requisitos y criterios de aceptación

El orden es el orden de entrega. El primero es el esqueleto: recorre el camino feliz de punta a punta.

### REC-1: Esqueleto: un pedido normal, de WhatsApp a enviado (pendiente · 1ª entrega)

Recorrer todo el camino feliz aunque sea en fino: entra el mensaje, María confirma, se factura, Teresa envía.

- **R-1**: Cuando llegue un mensaje de pedido por WhatsApp de un cliente conocido, el sistema deberá montar un borrador de pedido con cliente, líneas y fecha, y guardar el mensaje original. · origen: usuario · código actual: no implementado
  - Evidencia: Proyecto nuevo sin código.
  - Prueba: Pendiente de construcción.
- **R-2**: Cuando María confirme un borrador con stock y sin necesidad de visto bueno (G-1), el sistema deberá generar la factura, apuntar su importe a la cuenta del cliente y avisar al almacén por WhatsApp. · regla G-1 · origen: usuario · código actual: no implementado
  - Evidencia: Proyecto nuevo sin código.
  - Prueba: Pendiente de construcción.
- **R-3**: Cuando Teresa responda al aviso marcando el pedido como enviado, el sistema deberá registrar la hora del envío. · origen: usuario · código actual: no implementado
  - Evidencia: Proyecto nuevo sin código.
  - Prueba: Pendiente de construcción.
- **R-6**: Si el modelo no entendió el mensaje o el remitente era un número desconocido, entonces el sistema deberá guardar el mensaje sin crear ningún borrador y avisar a María en su panel para que lo registre a mano. · origen: usuario · código actual: no implementado
  - Evidencia: Proyecto nuevo sin código.
  - Prueba: Pendiente de construcción.

- **C-1**: Dado que Paco no debe nada y hay 100 sacos de harina en stock / Cuando escribe "40 sacos de harina de 25kg para el jueves" y María confirma el borrador / Entonces se genera la factura, Teresa recibe el aviso por WhatsApp y el pedido queda como facturado · cubre R-2
- **C-2**: Dado que Paco escribe desde su número conocido y pide 20 sacos para el viernes / Cuando la app lee el mensaje / Entonces se crea un borrador con Paco, los 20 sacos, la fecha y el mensaje original guardado · cubre R-1
- **C-6**: Dado un pedido de Paco facturado esta mañana / Cuando Teresa responde LISTO al aviso / Entonces el pedido queda como enviado, con su hora de llegada y su hora de envío guardadas · cubre R-3
- **C-7**: Dado que el número 611 223 344 no está en la lista de clientes / Cuando escribe "hola?? precio harina" y el modelo no reconoce ningún pedido / Entonces no se crea ningún borrador, el mensaje queda guardado tal cual y María ve el aviso "mensaje sin entender" en su panel · cubre R-6

### REC-2: El visto bueno de Jorge: deuda o pedido gordo (pendiente)

Que ningún pedido con deuda o de más de 1.000€ salga sin aprobación (regla G-1).

- **R-4**: Cuando María confirme un borrador de un cliente con deuda pendiente o por importe mayor de 1.000€, el sistema deberá retenerlo y pedir aprobación al jefe por WhatsApp, enseñándole la deuda y el importe. · regla G-1 · origen: usuario · código actual: no implementado
  - Evidencia: Proyecto nuevo sin código.
  - Prueba: Pendiente de construcción.
- **R-5**: Cuando Jorge apruebe un pedido retenido, el sistema deberá continuar hacia la factura. · origen: usuario · código actual: no implementado
  - Evidencia: Proyecto nuevo sin código.
  - Prueba: Pendiente de construcción.
- **R-7**: Si una operadora intenta confirmar un borrador asignado a otra operadora, entonces el sistema deberá rechazar la petición y conservar el borrador pendiente sin generar factura. · origen: inferido · código actual: no implementado
  - Evidencia: Proyecto nuevo sin código.
  - Prueba: Pendiente de construcción.
- **R-8**: Si un supervisor intenta aprobar un pedido que no está retenido, entonces el sistema deberá rechazar la petición y conservar el pedido sin cambios. · origen: inferido · código actual: no implementado
  - Evidencia: Proyecto nuevo sin código.
  - Prueba: Pendiente de construcción.
- **R-9**: Si una persona sin rol supervisor intenta aprobar un pedido retenido, entonces el sistema deberá rechazar la petición, mantener el pedido retenido y no generar factura. · origen: inferido · código actual: no implementado
  - Evidencia: Proyecto nuevo sin código.
  - Prueba: Pendiente de construcción.
- **R-10**: Cuando Jorge rechace un pedido retenido escribiendo el motivo, el sistema deberá dejar el pedido como anulado y avisar a María con el motivo. · origen: usuario · código actual: no implementado
  - Evidencia: Proyecto nuevo sin código.
  - Prueba: Pendiente de construcción.
- **R-11**: Si una operadora intenta borrar el historial de un cliente, entonces el sistema deberá rechazar la petición y conservar el historial sin modificar. · origen: inferido · código actual: no implementado
  - Evidencia: Proyecto nuevo sin código.
  - Prueba: Pendiente de construcción.
- **R-12**: Si un supervisor intenta editar un pedido, entonces el sistema deberá rechazar la petición y conservar el pedido sin modificar. · origen: inferido · código actual: no implementado
  - Evidencia: Proyecto nuevo sin código.
  - Prueba: Pendiente de construcción.
- **R-13**: Si un supervisor intenta ver un pedido que no está retenido, entonces el sistema no deberá devolver ningún dato del pedido. · origen: inferido · código actual: no implementado
  - Evidencia: Proyecto nuevo sin código.
  - Prueba: Pendiente de construcción.
- **R-14**: Si una preparadora intenta ver la deuda de un cliente, entonces el sistema no deberá devolver ningún dato de deuda. · origen: inferido · código actual: no implementado
  - Evidencia: Proyecto nuevo sin código.
  - Prueba: Pendiente de construcción.
- **R-15**: Si una preparadora intenta ver los precios de un cliente, entonces el sistema no deberá devolver ningún precio. · origen: inferido · código actual: no implementado
  - Evidencia: Proyecto nuevo sin código.
  - Prueba: Pendiente de construcción.

- **C-3**: Dado que Paco debe 300€ / Cuando María confirma su pedido de 40 sacos / Entonces el pedido queda retenido y al jefe le llega la petición con la deuda visible · cubre R-4
- **C-4**: Dado que Paco no debe nada / Cuando María confirma un pedido suyo de 60 sacos por 1.200€ / Entonces el pedido queda retenido por pasar de 1.000€ · cubre R-4
- **C-5**: Dado un pedido retenido de Paco / Cuando Jorge lo rechaza escribiendo el motivo / Entonces el pedido queda anulado y María ve el motivo en su panel · cubre R-10
- **C-8**: Dado un borrador de Paco asignado a Carmen y pendiente de confirmación / Cuando María intenta confirmarlo mediante su enlace directo / Entonces se rechaza la petición, el borrador sigue asignado a Carmen y no se genera ninguna factura · cubre R-7
- **C-9**: Dado un pedido de Paco ya facturado y Jorge con rol supervisor / Cuando Jorge intenta aprobarlo mediante su enlace directo / Entonces se rechaza la petición y el pedido sigue facturado sin ningún cambio · cubre R-8
- **C-10**: Dado un pedido de Paco retenido y María con rol operadora / Cuando María intenta aprobarlo mediante el enlace directo del pedido / Entonces se rechaza la petición, el pedido sigue retenido y no se genera ninguna factura · cubre R-9
- **C-11**: Dado un pedido de Paco retenido por deuda y Jorge con rol supervisor / Cuando Jorge lo aprueba / Entonces se genera la factura y el pedido deja de estar retenido · cubre R-5
- **C-12**: Dado el historial de Paco y María con rol operadora / Cuando María intenta borrarlo mediante la entrada directa / Entonces se rechaza la petición y el historial queda sin modificar · cubre R-11
- **C-13**: Dado un pedido retenido de Paco y Jorge con rol supervisor / Cuando Jorge intenta cambiar una línea del pedido mediante la entrada directa / Entonces se rechaza la petición y el pedido queda sin modificar · cubre R-12
- **C-14**: Dado un pedido facturado de Paco y Jorge con rol supervisor / Cuando Jorge intenta abrirlo mediante la entrada directa / Entonces no se devuelve ningún dato del pedido · cubre R-13
- **C-15**: Dado un pedido de Paco con 300€ de deuda y Teresa con rol preparadora / Cuando Teresa consulta el pedido mediante la entrada directa / Entonces no se devuelve ningún dato de deuda · cubre R-14
- **C-16**: Dado un pedido de Paco con precios de venta y Teresa con rol preparadora / Cuando Teresa consulta el pedido mediante la entrada directa / Entonces no se devuelve ningún precio · cubre R-15

### Episodios reales que sustentan los requisitos

- El 3 de julio Paco pidió 40 sacos debiendo 300€; el pedido esperó 2 horas a que Jorge volviera de la obra y Teresa cerró sin prepararlo. [G-1, R-4]
- En vendimia entraron 52 pedidos en un día y María dejó de contestar el teléfono para poder copiarlos al Excel. [Q-1]

## 5. Reglas de negocio

### G-1: Cuándo necesita un pedido el visto bueno de Jorge

| ¿Debe dinero? | ¿Pedido mayor de 1.000€? | Qué pasa |
|---|---|---|
| no | no | sale directo |
| no | sí | aprueba Jorge |
| sí | lo que sea | aprueba Jorge |

## 6. Estados

### pedido

| Estado | Qué se puede hacer (quién, y a qué estado pasa) |
|---|---|
| pendiente de revisión | registrarlo a mano (María) → pasa a 'borrador' · descartarlo (María) → pasa a 'anulado' |
| borrador | editar líneas (María) · confirmar, sin necesidad de visto bueno (María) → pasa a 'facturado' · confirmar, con deuda o más de 1.000€ (María) → pasa a 'retenido' · anular (María) → pasa a 'anulado' |
| retenido | aprobar (Jorge) → pasa a 'facturado' · rechazar con motivo (Jorge) → pasa a 'anulado' |
| facturado | marcar como enviado (Teresa) → pasa a 'enviado' |
| enviado | nada: solo consultar |
| anulado | nada: solo consultar |

## 7. Datos e integraciones

| Cosa | Qué se guarda | De dónde viene |
|---|---|---|
| cliente | nombre, teléfono de WhatsApp, deuda pendiente en euros | se importa del Excel de María |
| pedido | cliente, líneas (producto y cantidad), fecha de entrega, estado, mensaje original de WhatsApp, motivo de rechazo si lo hay, hora de llegada y hora de envío | se empieza de cero |
| producto | nombre, precio, stock del día | lo carga María cada mañana desde su Excel |
| factura | número correlativo, pedido, importe, fecha | la genera la app |

Números del negocio:

| Qué | Cuánto |
|---|---|
| pedidos al día | unos 30, con picos de 50 en vendimia |
| clientes con ficha | unos 200, 40 activos cada semana |

- Habla con **WhatsApp**: recibir pedidos y mandar todos los avisos

## 8. Superficie de uso

### El panel de María

| Campo | Valor |
|---|---|
| Quién entra | María |
| Por dónde llega | ordenador del despacho |
| Cuándo lo usa | cada vez que entra un pedido nuevo o hay un aviso |
| Qué ve nada más entrar | los pedidos de hoy, con los pendientes de revisión y retenidos arriba en naranja |
| Qué puede hacer | confirmar un borrador · corregir un borrador mal leído · registrar un pedido a mano (los de teléfono) · anular un borrador · marcar deuda como pagada |
| Qué NO debe poder jamás | aprobar pedidos retenidos (R-9 · C-10) · borrar el historial de un cliente (R-11 · C-12) |

### El móvil de Jorge

| Campo | Valor |
|---|---|
| Quién entra | Jorge |
| Por dónde llega | móvil, por WhatsApp |
| Cuándo lo usa | solo cuando un pedido queda retenido |
| Qué ve nada más entrar | el pedido, la deuda del cliente, el importe y dos botones: aprobar o rechazar |
| Qué puede hacer | aprobar · rechazar con motivo |
| Qué NO debe poder jamás | editar el pedido (R-12 · C-13) · ver pedidos que no están retenidos (R-13 · C-14) |

### El WhatsApp de Teresa

| Campo | Valor |
|---|---|
| Quién entra | Teresa |
| Por dónde llega | móvil, por WhatsApp |
| Cuándo lo usa | cuando hay un pedido facturado listo para preparar |
| Qué ve nada más entrar | las líneas del pedido y la dirección de entrega |
| Qué puede hacer | marcar como enviado respondiendo LISTO |
| Qué NO debe poder jamás | ver deudas de los clientes (R-14 · C-15) · ver precios de los clientes (R-15 · C-16) |

### Matriz de permisos

|  | registrar un pedido a mano (los de teléfono) | confirmar un borrador | corregir un borrador mal leído | anular un borrador | aprobar | rechazar con motivo | marcar deuda como pagada | marcar como enviado respondiendo LISTO |
|---|---|---|---|---|---|---|---|---|
| operadora | ✓ | ✓ | ✓ | ✓ |  |  | ✓ |  |
| supervisor |  |  |  |  | ✓ | ✓ |  |  |
| preparadora |  |  |  |  |  |  |  | ✓ |

### Restricciones de permisos

| ID | Sujeto | Acción | Recurso | Alcance | Condición | Promesa | Prueba |
|---|---|---|---|---|---|---|---|
| P-1 | rol: operadora | confirmar un borrador | pedido | asignado | el borrador está pendiente de confirmación | R-7 | C-8 |
| P-2 | rol: supervisor | aprobar | pedido |  | el pedido está retenido | R-8 | C-9 |
| P-3 | rol: supervisor | aprobar | pedido |  | la identidad conserva el rol supervisor | R-9 | C-10 |

### Avisos

| Quién se entera | De qué | Por dónde | Cuándo |
|---|---|---|---|
| Teresa | pedido listo para preparar | WhatsApp | al facturarse |
| Jorge | pedido retenido (deuda o más de 1.000€) | WhatsApp | al retenerse |
| María | mensaje que la app no entendió | WhatsApp | al quedar pendiente de revisión |
| María | pedido rechazado por Jorge, con su motivo | el panel | al rechazarse |

### Condiciones de uso

- María registra pedidos con el cliente al teléfono: nada puede tardar más de 5 segundos.
- Si se corta internet media mañana, no se pierde ningún pedido ya registrado.
- La deuda de los clientes solo la ven María y Jorge.

### Pruebas E2E seleccionadas

- **E2E-1** · criterios: C-1, C-6 · personas: María, Teresa · fronteras: camino feliz
- **E2E-2** · criterios: C-11 · personas: Jorge · fronteras: rol
- **E2E-3** · criterios: C-8 · personas: María, Carmen · fronteras: asignación
- **E2E-4** · criterios: C-9, C-10 · personas: María, Jorge · fronteras: estado, rol

## 9. Calidad y límites

- **Q-1**: Con 30 pedidos en un día, del mensaje de WhatsApp al borrador listo para confirmar pasan menos de 10 segundos.
- **Q-2**: Si la app se cae, al volver no falta ningún pedido ya registrado ni se duplica ninguno.
- **Q-3**: Cada pedido guarda hora de llegada y hora de envío, y el panel enseña el tiempo medio de despacho del mes (así se mide el criterio de éxito).

## 10. Fuera de alcance

- Cobros y pasarela de pago: se sigue cobrando como hasta ahora.
- Control de stock en tiempo real: el stock se comprueba contra la cifra que carga María cada mañana.

## 11. Preguntas abiertas

Buzón del constructor: sus dudas se apuntan aquí, nunca se responden de palabra.

- (Ninguna por ahora.)

