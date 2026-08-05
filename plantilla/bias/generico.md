# Bias tecnológico — GENÉRICO (este tipo de proyecto aún no tiene receta cerrada)

**Función:** acotar la fase 3 (Investigación). Este proyecto no es una aplicación web de
gestión, así que no viaja el stack por defecto del método: **el stack se decide en la fase 3,
con investigación y un ADR que lo justifique**, guiado por estos principios universales.

## Los principios (aplican a CUALQUIER tipo de software)

1. **100% open source.** Nada propietario en el stack de desarrollo.
2. **Mínimo código posible.** La mejor línea es la que no se escribe.
   Reutilizar > configurar > escribir. Reinventar la rueda: prohibido salvo ADR.
3. **Máxima adherencia a la herramienta elegida.** Se hace como su documentación oficial
   dice ("the framework way"). Desviarse exige ADR.
4. **Mínima invención de la IA.** Elegir tecnología aburrida, estable y con máxima huella
   de documentación y ejemplos; el mínimo espacio para que el agente invente.
5. **SaaS: la línea es "¿puedo irme en una tarde?"** — protocolo portable sí, plataforma
   que captura datos o lógica no.
6. **Lo más pequeño que arranque, primero.** El punto de partida es una máquina —la del
   usuario— y un entorno nativo (venv o equivalente). Contenedores, orquestación y servidores
   se añaden cuando haya una razón que el usuario haya dicho («lo va a usar más gente a la
   vez», «corre en otra máquina»), nunca por defecto. En un proyecto de una sola máquina, "el
   stack decidido" puede ser una línea: lenguaje + fichero de dependencias.

## Qué debe producir la fase 3 con esto

`03-investigacion/SINTESIS.md` con: el stack elegido y por qué (fuentes oficiales y
recientes), qué regala cada pieza (menos código propio), y un ADR por cada decisión
que se aparte de los principios. Sin stack decidido no se especifica ninguna unidad. La
primera unidad materializa para ESE stack las tres entradas de ADR-018 (suite completa, lint y
seguridad), sus workflows y Dependabot; el bias genérico jamás inventa los comandos antes.

## Cómo se diseña el código (vale para TODA unidad — ADR-015)

Esto se escribe aquí UNA vez y vale siempre. Ninguna especificación lo repite, lo re-argumenta
ni lo pone a votación: una spec que discute arquitectura es una spec que ha dejado de ser un
contrato para convertirse en un rediseño, y eso es lo que hace que una tarea pequeña dure horas.

1. **Una funcionalidad vive en SU módulo.** No desperdigada por la aplicación. El motivo no es
   estético: es que el agente encuentre lo que toca leyendo poco, y eso se paga en tokens y en
   tiempo cada vez que alguien abre esa parte del código.
2. **Responsabilidad única y KISS.** La pieza más simple que cumpla el contrato de hoy.
3. **Se encaja donde ya vive, no se duplica.** Antes de escribir, se busca en el código si esto
   ya existe o algo parecido. Si existe, se extiende.
4. **Si no cabe en el módulo que le corresponde, se PARA.** Eso es un refactor, con su propia
   unidad y su propia aprobación — nunca un rodeo dentro de otra tarea.
5. **Se resuelve el problema de hoy.** Ni capas de abstracción "para cuando haga falta", ni
   configuración que nadie ha pedido, ni generalizar sobre un solo caso. Preparar hoy problemas
   que aún no existen retrasa lo único que enseña de verdad: que el usuario use la aplicación.
