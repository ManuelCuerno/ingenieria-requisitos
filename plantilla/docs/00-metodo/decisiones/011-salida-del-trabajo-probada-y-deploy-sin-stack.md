# ADR-011 — La salida del trabajo se prueba, y el despliegue deja de presuponer el stack

## Decisión vigente

Cuatro reglas, salidas de una auditoría adversaria que montó un workspace real y atacó cada
puerta. El método protegía ferozmente la ENTRADA del trabajo (contrato escrito, aprobación del
usuario, prosa mínima) y dejaba sin vigilar la SALIDA: que lo entregado exista de verdad y
llegue a una máquina que el usuario pueda enseñar.

1. **Una rama que no existe NO prueba que se fusionara: prueba que alguien la borró.** El
   cierre daba por fusionada cualquier rama ausente, para poder reanudar un cierre a medias.
   Con eso, un `git worktree remove --force` + `git branch -D` —que es lo que el propio git
   sugiere cuando `-d` se queja— dejaba la unidad archivada como `mergeada`, con el OK del
   usuario escrito, y el trabajo fuera de la rama principal. Pérdida de trabajo con acta
   notarial de entrega, y el linter en verde. Ahora `cerrar` busca prueba: la rama local, si no
   `origin/<rama>`, si no el `fusion:` que el propio cierre anota en la ficha al comprobar el
   merge, y si no un commit de la principal que nombre a la unidad (la huella de un squash,
   que se acepta pero se marca como prueba INDIRECTA). Sin ninguna de las cuatro, FAIL, y la
   única salida es `--fusion <sha>` con un commit que exista y esté de verdad dentro de la
   principal. El linter aplica lo mismo en cada arranque a las unidades `en_revision`.

2. **La rama remota no se borra nunca.** `origin/NNN-slug` es la única copia del trabajo que no
   vive en el disco del usuario; borrarla convertía cualquier accidente local en pérdida
   definitiva. Se conserva, cuesta nada, y es la prueba que mira el punto 1. Que el servidor
   tenga "borrar rama al fusionar" es decisión de ese servidor, no del método.

3. **Las rutas de `ficheros:` se normalizan antes de compararlas.** La puerta de paralelismo
   comparaba cadenas: `api/x.py`, `./api/x.py` y `API/x.py` eran tres ficheros distintos para
   el guardián y el mismo en disco. Tres unidades podían poseer el mismo fichero con el visto
   bueno explícito. Esas variantes no son rebuscadas: las produce un agente que copia rutas de
   contextos distintos. Se normaliza separador, `./` y mayúsculas, en `unidad.py` y en
   `lint_metodo.py`, con la misma implementación a propósito.

4. **El gate de despliegue comprueba que está DEFINIDO, no CÓMO se despliega.** Exigía
   `main/deploy.py` (un script de Python), un `backup.py` o un `pg_dump` dentro de un
   docker-compose, y un `docs/04-planificacion/DESPLIEGUE.md` que no existía en ninguna parte
   del método. Es decir: la receta de una webapp autoalojada aplicada a todos los proyectos —
   una app de móvil, un mod, un proceso por lotes— y para todos ellos un rojo imposible en el
   único paso donde ya no se puede improvisar. Ahora comprueba las cinco decisiones que tiene
   todo despliegue, se despliegue como se despliegue, escritas por el usuario en la ficha del
   `plano-deploy.md`: `etapa`, `camino`, `vuelta_atras`, `datos` (que admite `SIN DATOS` como
   respuesta válida) y `vigilancia`. Y escala con la etapa: la auditoría de seguridad bloquea
   al salir a internet, no en el portátil de la oficina.

   Con ello, el método deja de opinar sobre proveedores y precios —que envejecen dentro de una
   plantilla— y `runbooks/primer-despliegue.md` acompaña al que no ha desplegado nunca desde la
   única pregunta que sí sabe responder: **¿quién tiene que poder usar esto?**

## Por qué, en una frase

Un gate imposible de pasar es peor que ninguno: entrena a trabajar con el rojo puesto. Y un
guardián que mira de menos da permiso con cara de haber mirado.

## Consecuencias

- El frontmatter de una unidad puede llevar `fusion: <sha>`. Lo escribe `unidad.py cerrar`;
  nadie lo teclea.
- Los proyectos que ya despliegan tienen que rellenar la ficha §3bis de su `plano-deploy.md`
  la primera vez que corran el gate. Es la entrevista que ya exigía `roles.md`, escrita.
- `docs/04-planificacion/DESPLIEGUE.md` deja de existir como concepto: nunca lo produjo nadie.
