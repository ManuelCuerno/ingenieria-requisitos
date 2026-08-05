# ADR-012 — El entorno por defecto es la máquina del usuario, y el tipo de proyecto no se presupone

## Decisión vigente

Tres reglas, salidas de una sesión real: un laboratorio de datos que corre en una sola máquina
arrancó su primera unidad ("hacerlo reproducible") empujado hacia Docker, docker-compose y
PostgreSQL. Lo cortó el usuario, que es experto. Un alumno no lo habría cortado.

1. **El entorno de ejecución y testing local se decide preguntando, no deduciendo.** La
   pregunta es literal y en cristiano: **«¿esto lo va a usar más gente a la vez, o lo corres tú
   en tu máquina?»**. Si lo corre él en su máquina, el punto de partida por defecto es lo
   mínimo que arranque: entorno nativo (venv o equivalente) y los servicios que esa máquina ya
   tenga instalados. Contenedores y orquestación se PROPONEN, con su porqué escrito, cuando lo
   use más de una persona a la vez, corra en una máquina ajena, o el usuario pida aislamiento.
   Que el código nombre varios servicios no decide por sí solo: un Postgres ya instalado vale.
   (`runbooks/planificacion.md` paso 2 · `runbooks/adopcion.md` regla 5 · `bias/generico.md`
   principio 6 · `bias/webapp.md` §peldaños.)

2. **La complejidad de manejo no es argumento ni a favor ni en contra.** Los comandos los
   ejecuta un agente y al usuario no le llegan. Lo que sí le llega es lo que queda encendido en
   su máquina cuando el agente se va, y eso es lo que se pesa. La versión anterior de la regla
   ("la complejidad de terminal NO es argumento en contra") solo desarmaba una mitad, y con eso
   la infraestructura pesada salía gratis.

3. **Sin `--tipo`, el bootstrap ya no presupone `webapp`: viaja el bias neutro.** El bias entra
   en el encargo de los 10 investigadores de la fase 3 (`runbooks/investigacion.md` paso 2), así
   que un defecto equivocado no se corrige después: envenena toda la investigación. Qué ES el
   proyecto y dónde va a correr lo responde la fase 3, que ya existía para eso.
   (`visor/bootstrap.py` §BIAS_POR_TIPO.)

## Lo que NO cambia

- **El destino de despliegue sigue siendo self-hosted:** un VPS propio o una máquina de la red
  del usuario. Puede quedarse en local si con eso le vale, pero no se presupone servidor ni se
  admite nube ajena ni SaaS.
- **La adherencia al stack del repo en brownfield** (mismos frameworks, mismas convenciones).
  Lo que se separa de eso es la INFRAESTRUCTURA: cómo se levanta en una máquina es decisión
  abierta, no herencia del código.
- **La doctrina de tests, el cierre y sus puertas.** Aquí no se toca nada de eso.

## Por qué, en una frase

Un método que presupone servidor y contenedores le cobra a todo proyecto el precio del proyecto
más grande que podría llegar a ser, y el que lo paga es el que menos sabe defenderse.
