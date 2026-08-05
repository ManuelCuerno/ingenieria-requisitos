# ADR-014 · El carril directo, y la puerta de flujos que la abre el delta

**Fecha:** 2026-08-03 · **Estado:** aceptada · **Superada en parte por:** ADR-017 (la
revisión del carril directo la hace SIEMPRE un agente fresco, no el padre)

## Contexto

Medición del camino real de "una feature pequeña" con el método anterior:

| | |
|---|---|
| Método a leer antes de tocar nada | 103.615 caracteres (~1.670 líneas) |
| Puertas que bloquean esperando al usuario | 4 |
| Contextos de agente distintos, cada uno releyendo | 3 (padre → constructor → revisor) |
| Suites completas de test | 2 |
| Documentos escritos o actualizados | 5 |

Y ese precio era **idéntico** para "añadir una columna" y para "migrar la base de datos".

Dos causas estructurales, no de uso:

1. **Había tres carriles en el papel y dos en la práctica.** Exprés sólo admite erratas y
   formateo (`expres.md` prohíbe explícitamente cualquier cambio de comportamiento, y un bug
   "JAMÁS, ni el más pequeño"). Todo lo que una persona llamaría "un cambio pequeño" caía en el
   carril normal, que se diseñó para trabajo arriesgado. No existía escalón intermedio.
2. **La puerta de flujos la abría el cambio, no el delta.** La regla 14 de `AGENTS.md` y el paso
   1 de `feature.md` obligaban, ante CUALQUIER cambio de comportamiento, a asumir el rol de
   analista, abrir un RUNBOOK de 841 líneas, editar `planos.json`, pasar un E2E con navegador
   real, levantar la web y esperar la aprobación del usuario — **antes de escribir una sola línea
   de contrato**. Incluso cuando el flujo ya prometía exactamente eso y no había nada que
   acordar. Era la ceremonia más cara del método, pagada por nada, en el caso más frecuente.

## Decisión

**1. Un cuarto carril: DIRECTO** (`runbooks/directo.md`, molde `plantillas/directo.md`), entre
exprés y normal. Entra el trabajo que cumple las cuatro a la vez: encaja en una actividad que ya
está en el mapa · no lo mueve · 1-3 ficheros sin hotspots · se deshace revirtiendo. Trae ficha de
una pantalla en vez de contrato de cinco, **2 puertas de usuario en vez de 4**, y la revisión la
hace el padre. Es el carril **por defecto del día a día**; normal queda para lo que mueve el mapa.

**2. La puerta de flujos la abre el DELTA.** Sólo si el trabajo añade, quita o contradice algo
del mapa. Si cabe dentro de un flujo ya escrito, no se abre: el delta —si lo hay— se escribe en
el cierre, con el trabajo ya visto funcionando.

**3. El revisor sale del carril, pero nunca desaparece.** En directo revisa el padre, que no
escribe código jamás (regla 1) y por tanto no construyó esto. En normal y completo, subagente
fresco. La regla dura "el revisor no puede ser quien construyó" no la relaja ningún carril.

## Lo que NO se toca, y por qué

Evidencia en verde, revisión firmada por alguien que no construyó, OK del usuario sobre la app
corriendo, no perder datos, no filtrar secretos. Eso no es ceremonia: es lo que impide entregar
algo roto. Los carriles cortos recortan **papeleo y esperas**, jamás garantías.

## Consecuencias

- El coste del trabajo pequeño baja de ~1.670 líneas de método y 4 puertas a ~200 y 2.
- Aparece un riesgo nuevo: clasificar como directo lo que no lo era. Se cubre con tres puertas —
  ante la duda se SUBE de carril; dos directos seguidos sobre lo mismo eran una unidad
  disfrazada; y si a mitad de obra el cambio crece, toca un hotspot o hay que mover el mapa, el
  constructor PARA y se re-abre por `feature.md`.
- `carril: directo` entra en el vocabulario cerrado (`lint_metodo.py`), y `unidad.py nueva
  --directo` elige el molde corto. `plantilla_de()` hace que la puerta de "la spec va antes que
  la rama" compare contra el molde correcto: si comparase contra otro, el texto fijo contaría
  como contrato escrito y la puerta se abriría sola justo en las unidades más ligeras.
