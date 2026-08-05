# DP-NNN · <la decisión en una frase, no el tema>

**Estado: ACEPTADA — YYYY-MM-DD. Decisor: <quién y de dónde salió: sesión, auditoría, ADR previo>.**

> Esqueleto de las decisiones de `docs/decisiones/` (fichero `NNN-slug.md`, numeración
> propia, nunca se renumera; se citan como `DP-NNN`, nunca como `ADR-NNN` — eso nombra
> siempre un ADR del método). Una decisión registra un porqué que el código no cuenta solo.
> Solo lo escribe el padre; las decisiones de contrato las toma un humano (AGENTS.md).
> Un ADR **no se edita para cambiar de opinión**: se escribe otro que lo supere.

## Contexto

<Qué había antes y qué presión obligó a decidir. Hechos, con referencias a fichero:línea o
documento. Suficiente para que alguien dentro de un año entienda el problema sin preguntar.>

## Decisión

<Lo que se hace a partir de ahora. Numerado, imperativo, sin condicionales. Cada punto debe
poder incumplirse o cumplirse: si no se puede comprobar, no es una decisión, es un deseo.>

1. **<qué>** — <detalle mínimo>.

## Consecuencias

<Lo que esta decisión arrastra: qué ficheros hay que tocar, qué queda prohibido, qué se
descartó y por qué, qué deuda queda abierta. Lo malo también — un ADR sin coste es sospechoso.>

- <consecuencia>

## Verificación

<Cómo se comprueba que la decisión está viva y no solo escrita: regla del linter, test,
comando, o el fichero cuya existencia lo demuestra. Si nada la verifica, dilo explícitamente.>

- `python3 docs/00-metodo/scripts/lint_metodo.py` → <qué debe salir>
