# ADR-016 · Nadie espera a ciegas, y cada carril paga lo que cuesta

**Fecha:** 2026-08-03 · **Estado:** aceptada

## Contexto

El dueño del método lo dijo así: *"la IA se pasa 40 minutos trabajando para hacer cualquier cosa
y no tengo ni puta idea de qué hace"*.

Eso **no era un problema de velocidad**, y por eso ADR-014 y ADR-015 —que atacaron la ceremonia—
no lo tocaron. Era un problema de **visibilidad y de control**: cuarenta minutos de silencio son
insoportables aunque el resultado sea bueno, y hacen imposible cortar cuando el agente se
equivocó de camino en el minuto tres.

El diagnóstico, medido sobre el propio método:

- El método **ya fabrica la señal de avance**: obliga a marcar las casillas `[x]` del plan según
  se completan y a escribir `hallazgos.md` sobre la marcha ("se escribe según se hace").
- **Y la tira a la basura**: esos ficheros no los mira nadie hasta el cierre.
- Había una sección entera sobre **cómo** hablarle al usuario y **ni una línea sobre cuándo**.
- Dato de base: ~1 de cada 3 trayectorias de agentes de código se descarrila (*Wink*, arXiv
  2602.17037, feb 2026). La ansiedad tiene tasa base; no es manía.

En paralelo, la auditoría encontró tres costes que se pagaban siempre sin elegirlos: la suite
completa en cada cierre (que Anthropic desaconseja explícitamente: *"Running the full suite when
Claude changed one service causes timeouts and wastes context on irrelevant output"*), ningún rol
con modelo ni esfuerzo asignado (`xhigh` cuesta 3-5× que `low`), y ningún criterio de parada para
la exploración.

## Decisión

**1. Regla dura 16: nadie espera a ciegas.** Parte de avance de una línea por cada casilla del
plan, en cuanto se marca. Previsión antes de empezar (cuántos pasos, cuánto va a durar).
**Silencio máximo 5 minutos**; si se van a superar, se avisa ANTES. Atascado se dice, no se
disimula. Si el silencio no cabe en la paciencia del usuario, **la unidad es demasiado grande y
se trocea**: el tamaño de la unidad ES la frecuencia del parte.

**2. Pasos, no porcentajes; y jamás "ya casi".** Un porcentaje que no se sabe calcular es una
mentira con cifras (NN/g sobre indicadores de progreso de duración desconocida).

**3. Los tests al cerrar, al nivel que el cambio merece.** Exprés y directo: el área tocada.
Normal: área tocada más suite completa. Completo, migración y hotfix: end-to-end. Si el proyecto
no puede saber qué depende de qué, se corre entera y se anota la deuda — no se adivina.

**4. Modelo y esfuerzo por carril y por rol** (regla 10). El revisor usa un modelo **distinto**
al que construyó.

**5. Criterio de parada de exploración** (regla 11): antes de buscar se dice qué se busca y
cuándo se para. Encontrado lo que contesta la pregunta, se para y se construye. (El *presupuesto
de tokens* sigue descartado por simplicidad: eso sí era burocracia. El criterio de parada es una
frase.)

**6. Los outputs largos se referencian, no se pegan** (regla 12): ruta en `.runtime/` más el
veredicto y las líneas que lo prueban.

## Consecuencias

- El coste de la visibilidad es **casi cero**: la señal ya se producía; lo único que se añade es
  la obligación de sacarla.
- Riesgo declarado y medido: enseñar el trabajo hace preferir la espera larga **pero el efecto se
  invierte si el resultado es malo** (Buell & Norton, 2011). Contar bien sube la apuesta, no
  sustituye a acertar.
- No existe literatura sobre esperas de 40 minutos ni sobre la frecuencia óptima de reporte
  (Nielsen cubre de 0,1 a 10 segundos). **Los 5 minutos son criterio, no hallazgo**, y se dice.
- El escalón de tests por área exige saber qué depende de qué. Donde no se sabe, la regla manda
  correr todo: el ahorro nunca se compra con un falso verde.
