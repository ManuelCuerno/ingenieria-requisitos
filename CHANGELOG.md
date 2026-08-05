# Novedades del método

La versión del método viaja con cada proyecto (en su `METODO.json`). Para llevar
estas mejoras a tus proyectos ya creados: abre tu agente aquí y dile «pon al día
mis proyectos».

## 1.1.0 — 2026-08-05

Primera versión numerada. Qué trae:

- **El método tiene versión.** Cada proyecto sabe con qué versión se montó, y al
  actualizar se te dice de cuál a cuál pasas.
- **Pruebas más seguras.** Antes de tocar una base de datos o un servicio, los
  agentes comprueban que es el de prueba y no el de verdad.
- **Caja negra completa.** Los tropiezos de los agentes quedan registrados en tu
  proyecto, sin secretos; ahora se pueden listar, revisar y —solo si tú quieres—
  compartir con el autor de la herramienta para mejorarla.
- **Textos alineados.** Las reglas del método que se contradecían entre sí
  quedaron con una sola fuente de verdad.
- **Comprobaciones automáticas.** Los proyectos nacen con una comprobación (CI)
  que vigila el método en cada cambio.
- **Actualizar es más robusto.** Poner al día un proyecto repone las carpetas de
  su estructura que falten y ya no se bloquea por restos inofensivos, como los
  ficheros temporales de Python.
