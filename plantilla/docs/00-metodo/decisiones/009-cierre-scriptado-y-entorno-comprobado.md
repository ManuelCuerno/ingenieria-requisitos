# ADR-009 — El cierre se scripta, el entorno se comprueba y el revisor tiene frontera

## Decisión vigente

Cuatro reglas, salidas de construir y cerrar la primera unidad real de un workspace.

1. **El cierre es un comando, no prosa.** `unidad.py cerrar NNN-slug --ok-usuario
   YYYY-MM-DD` aplica las puertas (OK del usuario con fecha, revisión firmada por alguien
   distinto del constructor, worktree sin nada sin guardar, rama fusionada de verdad) y hace
   lo mecánico: estado, archivo, worktree y rama local **y remota**. Lo que exige criterio
   —deltas al mapa, promoción de hallazgos, `ESTADO.md`— sigue siendo del padre. Es la regla
   de confianza del método (script > plantilla > prosa) aplicada al ritual que más se olvida,
   igual que ya se hizo con el despacho.

2. **`main/` tiene UNA excepción nombrada.** Sigue siendo de solo lectura, salvo el merge del
   paso 3 del cierre cuando la máquina no tiene `gh` (`runbooks/cierre.md`, camino B). El
   método no tenía camino sin GitHub y obligaba a improvisar en el paso más delicado; una
   regla absoluta que el ritual rompe es una regla que alguien va a romper sin dejar rastro.

3. **El entorno se comprueba antes de prometerlo.** `scripts/doctor.py` mira qué hay de
   verdad en la máquina (Python, git y su identidad, `gh`, Docker, Node) y el ROADMAP no
   puede fijar una herramienta que no haya visto en verde (`runbooks/planificacion.md`).
   Decidir en la fase 4 "se desarrolla con contenedores" sin saber si hay contenedores se
   paga con un ROADMAP corregido, un ADR y una unidad reespecificada a mitad.

4. **El revisor fresco tiene frontera.** Devuelven el trabajo al constructor los
   incumplimientos del contrato de ESA unidad, los fallos de seguridad y lo que pierda datos.
   Los riesgos de flujos futuros y las mejoras se anotan como trabajo descubierto y no
   reabren nada; solo un fallo crítico permite una segunda ronda. Sin esta frontera, una
   rebanada pequeña se convierte en diseño preventivo y el usuario tarda mucho más en poder
   probar la aplicación, que es lo único que enseña algo de verdad.

No se crea un carril nuevo para esto: los carriles siguen siendo exprés, normal y completo.
Añadir vocabulario para combatir la ceremonia sería más ceremonia.
