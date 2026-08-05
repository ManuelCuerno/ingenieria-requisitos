# Bias tecnológico — BROWNFIELD (el código ya existe)

**Función:** acotar la fase 3 (Investigación). El stack de este proyecto NO se elige:
**ya está elegido — es el que vive en `main/`**. Aquí mandan tres reglas:

## 1. Adherencia total al stack existente

Se construye como ya se construye en ese repo: mismos frameworks, mismas convenciones,
mismos comandos. Cambiar una pieza del stack no es una unidad normal: es una `migracion`
con su ADR. Reescribir lo que funciona: prohibido sin decisión explícita del humano.

## 2. Primero conocer, después tocar: la ADOPCIÓN (primera unidad, obligatoria)

La primera unidad del workspace es fija — tipo `investigacion` + `auditoria`, carril
completo — y ninguna otra unidad se despacha antes de cerrarla:

- **Inventario extraído del código** (con rutas citadas, no de memoria): estructura del
  repo, stack real y versiones, comandos de build/test/arranque, y toda la documentación
  existente (README, docs/, configs, comentarios clave).
- **Estado de los tests**: ¿hay suite? ¿corre? ¿está en verde? (output real pegado).
  Sin suite = primera deuda declarada: **no se toca comportamiento sin red de tests**.
- **Salidas** (todas al meta-repo — el repo de código no se toca en la adopción):
  `03-investigacion/SINTESIS.md` (el stack existente documentado como bias efectivo, con
  los comandos de build/test/arranque), y el **gap-map código↔flujos**: qué promete el mapa
  de la entrevista que el código no hace, y qué hace el código que el mapa no recoge →
  candidatas al ROADMAP.

La adopción sigue siendo de solo lectura. Su salida abre una primera unidad técnica, antes de
cualquier cambio de comportamiento, que materializa el CI real de ADR-018 reutilizando la
suite y los comandos descubiertos: nada de reemplazarlos por una receta de otro stack.

## 3. Los principios universales siguen valiendo

Open source, mínimo código, mínima invención de la IA, y la regla SaaS ("¿puedo irme en
una tarde?") — como criterio para lo NUEVO que se añada, nunca como excusa para reescribir
lo que ya funciona.

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
