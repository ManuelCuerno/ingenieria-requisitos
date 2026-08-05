# ADR-010 — El estado que faltaba, los guardianes que miraban de menos y el entorno del worktree

## Decisión vigente

Cuatro reglas, salidas de la fricción real de dos workspaces trabajando en paralelo de verdad.

1. **Existe `en_validacion`, y no cuenta como trabajo en vuelo.** Una unidad cuya rama ya está
   fusionada y cuyo trabajo de construcción terminó, pendiente solo de que el usuario pruebe la
   aplicación corriendo, no consume atención de nadie: consumía cupo. Con tres unidades así, el
   tope de paralelismo se agotaba sin que hubiera un solo constructor trabajando, y la salida
   era subir el tope —tocar el guardián para poder seguir— cuando el problema nunca fue el
   número. `unidad.py cerrar` sin `--ok-usuario` aplica todas las puertas que dependen de un
   agente y, si están en verde, deja la unidad en `en_validacion`: libera el sitio, no archiva
   nada, no borra rama ni worktree, y el linter la enseña en cada arranque hasta que se
   termina. El cierre sigue siendo indivisible (regla dura 7); lo que se ha separado es la
   única parte que un agente no puede hacer.

2. **El paralelismo se comprueba, no se recuerda.** La regla "dos unidades en paralelo jamás
   comparten ficheros" la vigilaba un WARN dirigido a un humano, o sea a nadie, mientras el
   linter tenía la comprobación buena pero ciega: el parser de frontmatter leía línea a línea,
   así que una lista `ficheros:` multilínea se quedaba en cadena vacía y las comparaciones se
   hacían entre conjuntos vacíos. Pasaban siempre, en todos los proyectos, desde el primer día.
   Ahora el parser entiende listas en las dos formas y `despachar` **bloquea** la colisión, con
   dos consecuencias buscadas: despachar en paralelo exige declarar `ficheros:` (sin
   declaración no hay nada que comprobar) y una unidad `--documental`, que no toca el repo de
   código, queda fuera de la comprobación en vez de estrellarse contra ella.

   Un guardián que comprueba de menos es peor que ninguno: da permiso con cara de haber mirado.

3. **El entorno del worktree se prepara al crearlo.** Un worktree recién creado es código sin
   entorno: sin dependencias instaladas, sin base de datos de pruebas, sin lo que pida el
   stack. El constructor que aterriza ahí ve fallar tests que en la rama principal pasan, y los
   usa como vara de medir durante horas antes de descubrir que estaba midiendo el entorno. El
   método no sabe montar eso —depende del stack— y nunca instala dependencias por su cuenta.
   Si el proyecto deja un único `worktree-listo` (o `worktree-listo.py`) regular y confinado a
   la raíz, `unidad.py despachar` lo ejecuta con el worktree recién creado. El rojo bloquea y
   deshace rama/worktree; un symlink se rechaza. Con hook verde deja estado `preparado`; sin
   hook deja `sin_hook` y `preparacion_verificada: false`: ambos son recibos JSON verificables
   en `.runtime/worktree-readiness/`, nunca un aviso que haga pasar «creado» por «listo».

4. **La identidad de git se comprueba en cada arranque, no una vez.** Sin `user.name` y
   `user.email` ningún commit se completa, y cada intento falla por su cuenta y en silencio.
   El bootstrap ya avisaba, pero un aviso de una sola vez entre veinte líneas de salida no es
   una comprobación: el fallo se descubría días después, cuando alguien iba a hacer push. El
   linter comprueba ahora la identidad y que el meta-repo tenga al menos un commit, y lo repite
   en cada sesión hasta que esté arreglado.

## Lo que NO se ha hecho

No se ha subido el tope de trabajo en vuelo. Con `en_validacion` fuera del recuento y la
colisión de ficheros bloqueada de verdad, el tope vuelve a medir lo que decía medir: unidades
con un constructor dentro. Si aun así se queda corto, eso es una conversación sobre atención
humana, no un número que se sube a mitad de sesión con un ADR improvisado.

Tampoco se ha añadido vocabulario para "esperando una sesión de DEPLOY": es el mismo estado
—terminado, pendiente de una persona— y dos nombres para lo mismo es ceremonia.
