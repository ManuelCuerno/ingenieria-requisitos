# ADR-027 · Sin tope numérico de paralelismo: el límite es fichero compartido, no un número

**Fecha:** 2026-08-15 · **Estado:** aceptada · Sustituye el tope absoluto de ADR-005/regla 5

## Contexto

La regla 5 fijaba un tope absoluto de 3 unidades de código en vuelo, incluso con
`--paralelo` y ficheros disjuntos declarados. Petición P-20260815-4d55baac: el usuario
pide un lote de 6 unidades de producto y pregunta por qué existe ese número si el propio
script ya verifica, fichero a fichero, que dos unidades en vuelo no se pisan
(`ficheros:` cruzado en `unidad.py`). El número 3 no protegía nada que la comprobación de
disjunción no protegiera ya: era un límite de atención humana puesto a mano, no una
propiedad del sistema.

## Decisión

Se retira el tope absoluto (`TOPE_EN_VUELO`). El único gate real pasa a ser el que ya
existía: **ninguna unidad en paralelo comparte fichero declarado con otra activa**. Con
`--paralelo` y `ficheros:` disjuntos, pueden convivir tantas unidades como quepan sin
chocar — el límite lo pone el propio grafo de ficheros del trabajo pedido, no una
constante. Sin `--paralelo` sigue rigiendo UNA unidad por defecto (regla 5 no cambia ahí).

## Consecuencias aplicadas

- `unidad.py`: se retira la comprobación `len(activas) >= TOPE_EN_VUELO`; se conserva
  intacta la comprobación de ficheros disjuntos (es la que de verdad evita el choque).
- AGENTS.md regla 5: "tope 3" pasa a "sin tope numérico, solo si no comparten ficheros".
- Las `en_validacion` y `--documental` siguen sin contar para el censo de vuelo (sin cambio).

## Límites

Esto no relaja la comprobación de ficheros disjuntos ni el resto de gates duros (regla 1,
revisor fresco; regla 7, cierre indivisible). Un lote grande con hotspots compartidos
sigue yendo en secuencia: la disjunción de ficheros, no el deseo de paralelizar, decide
cuánto cabe a la vez.
