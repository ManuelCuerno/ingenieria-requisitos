# Auditoría del método — playbook del REVISOR DEL MÉTODO

> Manual de un agente **FRESCO** (sin contexto previo de las unidades que audita: no puede
> revisar con cariño lo que ayudó a construir) y de **SOLO LECTURA**. Su pregunta única:
> ¿este workspace cumple el método a rajatabla? No arregla nada — sus violaciones paren
> unidades. Rol: OBSERVABILIDAD (`roles.md`); la ficha del tipo de unidad:
> `runbooks/auditoria.md`.

## Cuándo se lanza

- **Programado**: revisión periódica; punto de partida razonable, tras cada N cierres
  (N=5) o una vez por iteración del roadmap. La cadencia exacta la fija el humano.
- **Bajo sospecha**: cualquier señal de drift justifica lanzarlo sin esperar al calendario —
  un WARN del linter, un "hecho" sin evidencia, un merge que nadie recuerda, un ESTADO.md
  que no cuadra con la realidad.

Se ejecuta desde la raíz del meta-repo, con `main/` presente y al día (`git -C main pull`).
El revisor escribe ÚNICAMENTE su informe en la carpeta de su unidad (tipo `auditoria`);
jamás toca código, docs compartidos, ni hace git.

## El checklist

Cada check: el comando exacto, y qué constituye violación. La evidencia es SIEMPRE output
literal pegado — un check sin su output no cuenta como pasado (regla 12: evidencia, no
afirmación).

### 1. El linter del método en verde

```
python3 docs/00-metodo/scripts/lint_metodo.py
```

**Violación:** cualquier FAIL (0 FAIL es obligatorio). Los WARN no son violación, pero se
listan en el informe: son las pistas de dónde mirar más fuerte (en especial los de drift).

### 2. Unidades archivadas completas y con evidencia real

```
ls docs/05-trabajo/archivo/*/
head -11 docs/05-trabajo/archivo/*/especificacion.md
ls docs/bugs/*.md
```

y leer el `hallazgos.md` (y la sección Verificación) de cada unidad archivada, más la
sección 5 · Resolución y 6 · Cierre de cada ficha de `docs/bugs/` (los bugs NO se archivan,
ADR-006).

**Violación:** una unidad archivada sin `especificacion.md` con frontmatter completo
(las 8 claves: unidad, tipo, carril, estado, aprobado, actividad, ficheros, actualizado), sin
la sección **Plan de trabajo** en esa misma especificación (ADR-005: spec y tareas son un
solo documento), o cuya evidencia de cierre sea una AFIRMACIÓN ("los tests pasan",
"verificado") en lugar de output REAL pegado (la salida del runner de tests, el comando y su
resultado, capturas si hay UI). En un bug, además: sin el par ROJO→VERDE pegado y sin
"Validación del usuario: OK".

### 3. Tests jamás debilitados

```
git -C main log --diff-filter=M -p -- tests/ | grep '^-'
```

(filtrar el ruido de cabeceras `^---`; lo que importa son líneas de test borradas, sobre
todo asserts).

**Violación:** asserts o comprobaciones eliminados sin una unidad que lo justifique
explícitamente (buscar el commit con `git -C main log -S '<assert borrado>' -- tests/` y
comprobar que su mensaje traza a una unidad NNN-slug cuya especificación lo contempla).
Doctrina: reforzar tests sí; debilitarlos, jamás. Los tests de regresión de bugs no se
borran nunca.

### 4. Todo merge de main traza a una unidad

```
git -C main log --format=%s
```

**Violación:** merges/squashes en main sin `NNN-slug` en el título. No cuentan como
violación: el commit inicial ("establece main") y los commits de CI/bootstrap.

### 5. ESTADO.md pequeño y veraz

```
wc -l docs/05-trabajo/ESTADO.md
ls worktrees/
git -C main worktree list
```

**Violación:** más de 100 líneas; o una tabla de unidades incoherente con la realidad —
toda unidad `en_obra`/`en_revision` de la tabla debe tener su worktree, y todo worktree
existente su unidad en la tabla (el inventario real de worktrees lo da git, no la memoria).

### 6. Deltas de unidades archivadas aplicados al mapa

```
grep -A4 '## Deltas al mapa' docs/05-trabajo/archivo/*/especificacion.md
```

Para cada unidad archivada con deltas declarados (AÑADIDO/MODIFICADO/ELIMINADO distintos
de "—"): comprobar que `docs/02-flujos/INDICE.md` (y el fichero de la actividad, si el
delta lo nombra) reflejan ese cambio.

**Violación:** un delta declarado que el mapa no refleja (cierre a medias: el merge entró
pero el mapa quedó mintiendo).

### 7. Git del meta con rutas explícitas (nunca `git add -A`)

```
git log --stat -15
```

**Violación:** commits del meta que arrastran ficheros ajenos a su propósito — la firma
del `add -A`: temporales, artefactos generados, papeles de otra unidad o ficheros sin
relación con el mensaje del commit, todo mezclado en un mismo commit.

### 8. WIP respetado (nunca más de 2-3 unidades en vuelo)

```
ls worktrees/ | grep -v README.md | wc -l
git log --format=%h -- docs/05-trabajo/ESTADO.md | while read c; do
  echo "$c $(git show "$c:docs/05-trabajo/ESTADO.md" | grep -c en_obra)"
done
```

(la segunda orden recorre el histórico de ESTADO.md contando unidades en obra en cada
versión).

**Violación:** más de 3 worktrees simultáneos ahora, o cualquier versión reciente de
ESTADO.md con más de 3 unidades en obra a la vez. El default del método es UNA; 2-3 solo
para unidades que no comparten ficheros.

## Formato del informe

Un veredicto por check, con la evidencia LITERAL (output pegado y recortado a lo
relevante — nunca parafraseado):

```
### Check N — <nombre>
- Veredicto: CUMPLE | VIOLACIÓN
- Comando: <el ejecutado>
- Evidencia: <output literal>
```

Y al final:

```
## Veredicto final
LIMPIO (8/8 CUMPLE)  |  CON VIOLACIONES: <lista numerada, cada una con su check y evidencia>
```

**Las violaciones NO se arreglan en caliente.** Cada violación aceptada por el humano pare
una unidad (tipo `bug` — el bug está en el proceso, no en la aplicación) que entra al
ROADMAP por el cauce normal. El revisor entrega el informe en la carpeta de su unidad de
auditoría y termina ahí su trabajo.
