# ADR-023 · Control plane local para sesiones y operaciones compuestas

**Estado:** aceptada · **Fecha:** 2026-08-05

**Nota:** el bloqueo de Modo D por fichas con trabajo en vuelo lo supera ADR-025 (pasa a ser
aviso); el resto sigue vigente.

## Contexto

Dos harnesses trabajaron sobre el mismo metarrepo; Modo D actualizó mientras una auditoría
usaba ese workspace; un segundo monitor nació porque la lista de tareas ocultaba el primero;
y `git add -A` podía convertir trabajo aparecido durante una actualización en parte de su
commit. Las comprobaciones de estado existentes eran correctas por separado, pero dejaban
una carrera entre «he comprobado» y «he escrito».

## Decisión

El método publica `scripts/lease.py`, un control plane para procesos que comparten filesystem.
Cada autoridad incluye UUID de sesión, host, PID, instante de inicio del proceso y fencing
monotónico. Los scopes exclusivos son:

- `workspace`: Modo D y cualquier operación global; entra en conflicto con todos los demás;
- `git-index`: staging y commits del metarrepo;
- `unit-namespace`: asignación NNN y creación de fichas;
- `unit:<NNN-slug>`: despacho de una unidad concreta;
- `resource:<ruta>`: fichero declarado como propiedad de una unidad paralela.

La numeración mantiene `unit-namespace` desde el cálculo hasta que la orden y sus enlaces
existen. El despacho conserva autoridad sobre unidad y recursos desde las precondiciones hasta
que rama, worktree, origen y estado forman un resultado coherente. Un fencing perdido bloquea
la siguiente escritura: liberar un lease antiguo nunca borra el del propietario nuevo.

Modo D toma `workspace` y `git-index` antes de revisar o escribir. Hace `fetch` y bloquea si
el remoto avanzó, si Git ya está sucio o si una ficha declara trabajo en vuelo. Su punto de
retorno es el HEAD limpio; el commit final prepara únicamente las rutas que la operación
calculó, nunca `git add -A`. Antes de copiar escribe en
`.runtime/transactions/modo-d.json` un journal durable con el snapshot de sus rutas. Si el
proceso muere, la siguiente ejecución restaura ese snapshot antes de volver a calcular la
actualización.

## Recuperación y límites

Un PID solo está vivo si coincide también su instante de arranque; así un PID reutilizado no
retiene autoridad. Un propietario de otro host nunca se declara muerto automáticamente.

Esta decisión coordina procesos que ven el MISMO `.runtime/`. No ofrece coordinación entre
dos clones en hosts distintos: Modo D lo detecta indirectamente mediante `fetch` y bloquea la
divergencia remota, pero no existe un lease distribuido. Añadir CAS remoto requiere una ref o
servicio autoritativo y queda fuera hasta poder hacerlo sin depender de configuración privada
de un harness.

Los failpoints `IR_FAILPOINT_*_{READY,WAIT}_FD` (descriptores, POSIX) y
`IR_FAILPOINT_*_{READY,WAIT}_FILE` (ficheros, cualquier plataforma: en Windows los FDs no
cruzan procesos) solo actúan si un test define esas variables; permiten detener procesos en
la ventana exacta sin esperas temporales ni comportamiento en producción.

El cierre de una unidad (`unidad.py cerrar`) toma `unit:<NNN-slug>` y `git-index` mientras
reescribe fichas, archiva y reconcilia: un Modo D o un despacho concurrentes fallan nombrando
al propietario en vez de mezclar escrituras.

## Consecuencias

- Una colisión falla antes de escribir y nombra al propietario actual.
- Un proceso muerto deja journal recuperable, no un método mezclado.
- Las unidades disjuntas siguen pudiendo avanzar en paralelo.
- Un host diferente, un remoto adelantado o trabajo local activo bloquean por seguridad.
