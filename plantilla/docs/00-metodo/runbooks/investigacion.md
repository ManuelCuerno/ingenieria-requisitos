# Runbook · INVESTIGACIÓN (fase 3)

**Frontera con el inbox:** esta fase es investigación de `plataforma`, fundacional o
transversal. La investigación `acotada` de una petición vive en su P-ID y corre durante la
preparación/desarrollo con 2–4 lentes; no vuelve a ejecutar diez informes por feature.

**Cuándo:** proyecto recién provisionado — hay constitución y flujos (los dejó la herramienta
de ingeniería de requisitos) y aún no hay código (`main/` solo tiene el README). También
**tras cerrar una adopción brownfield**, en versión ACOTADA (`runbooks/adopcion.md` §6: no se
re-elige stack; se investiga lo desconocido/arriesgado del gap-map y las versiones y
vulnerabilidades del stack existente), y cuando el roadmap o una unidad exigen responder
preguntas nuevas.
**Produce:** los informes de los investigadores + `SINTESIS.md`, todo en `03-investigacion/`.
**Contrato de cierre:** **exactamente 10 ficheros `informe-NN-*.md` en
`03-investigacion/` para un proyecto de cero** (salvo la
versión acotada, cuyo número lo fija el gap-map) + `SINTESIS.md` escrita, todo con fuentes
fechadas y su nivel. Una investigación que no deja documento no existió.

## Paso a paso (el padre-CONSTRUCTOR)

1. **Preparar el encargo.** Leer `01-constitucion/manifiesto.md` (qué se construye),
   `01-constitucion/bias.md` (perfil del usuario, tecnologías preferidas, filosofía:
   sin SaaS, stack preferido salvo que el proyecto pida otra cosa) y los flujos de
   `02-flujos/`. El encargo = qué es este proyecto + qué acota el bias.

   **Lo primero que responde esta fase es QUÉ ES esto** —aplicación web, cadena de procesado
   de datos, automatización, agente…— **y dónde va a correr**. No se presupone. Si el bias que
   viajó es el genérico, es que nadie lo ha decidido todavía: no se rellena con "lo de
   siempre", se decide aquí, con la investigación delante y preguntándole al usuario a quién
   sirve y en qué máquina («¿lo va a usar más gente a la vez, o lo corres tú en la tuya?»).
2. **Diseñar los enfoques: 10 subagentes investigadores**, cada uno con un objetivo
   y una estrategia de búsqueda DISTINTOS. **El encargo de CADA investigador lleva el bias
   delante** (`01-constitucion/bias.md`): sin él busca en el vacío. (Único caso con otro
   número: la fase 3 acotada de brownfield — `runbooks/adopcion.md` §6.) Si la plataforma
   limita la concurrencia, se ejecutan por tandas, pero siguen siendo 10 encargos y 10
   informes independientes. Esos diez son el mínimo fundacional: investigaciones posteriores
   se numeran a continuación y se añaden, nunca invalidan ni reemplazan los diez primeros.
   Enfoques estándar (ajustar al proyecto):
   casos y proyectos parecidos (open source primero) · el ecosistema del stack del bias ·
   la alternativa simple (¿basta un script/automatización?) · el escéptico del stack ·
   integraciones/hardware que los flujos exigen · modelo de datos · despliegue self-hosted ·
   seguridad · frontend (¿estático basta o hace falta React?) · estado del arte: cómo lo
   hacen las empresas famosas y las startups más grandes, y qué proponen las organizaciones
   reputadas.
3. Enseñar la lista de enfoques al usuario (un vistazo, no un ritual) y lanzar.
4. **Búsqueda ONLINE exhaustiva.** Cada investigador busca en internet con su estrategia,
   **priorizando siempre lo más reciente** y lo reputado: docs oficiales, blogs de
   ingeniería de empresas grandes, foros y blogs técnicos de entidades reputadas. **TODOS
   los investigadores se lanzan con la lista blanca de fuentes de abajo** — es el criterio
   único, no una opción de algunos (para no tragar basura). Los niveles bajos se pueden usar,
   pero con prioridad menor y **marcados con su nivel en el informe**. Toda afirmación con
   URL, fecha y nivel; sin fuente = se declara opinión. Ante conflicto gana el más oficial y
   reciente.
5. **Cada investigador deja SU informe** en `03-investigacion/informe-NN-<enfoque>.md`
   (plantilla `informe.md`). Es el ÚNICO fichero que ese subagente escribe; no toca nada más.
6. **Sintetizar (el padre).** Leer TODOS los informes y escribir `SINTESIS.md` (plantilla
   `sintesis.md`): qué se usa, por qué, con qué fuentes. Desviación del bias → ADR primero.
7. **Cerrar la fase:** actualizar `ESTADO.md` → pasar a la fase 4 (runbook `planificacion.md`).
   La fase no se re-hace: enfoques nuevos se AÑADEN cuando haga falta, por este mismo ritual.

## Lista blanca de fuentes (prioridad de arriba abajo)

Genérica: vale para cualquier proyecto y para TODOS los investigadores. El nivel se declara en
el informe junto a URL y fecha (campo `nivel` de `plantillas/informe.md`).

1. **Documentación oficial** del proyecto/framework/producto y sus **notas de versión**.
2. **Repositorio oficial** (código, issues, discusiones) y **especificaciones o estándares**
   (RFC, W3C, PEP, ISO…).
3. **Blogs de ingeniería** de empresas grandes y de las startups punteras del sector.
4. **Publicaciones de organizaciones reputadas** (OWASP, CNCF, Linux Foundation, ACM/IEEE…).
5. **Foros y comunidades técnicas de referencia** (Stack Overflow, Hacker News, subreddits
   especializados): útiles para detectar problemas reales y trampas — **NO** para afirmar
   hechos.
6. **Todo lo demás:** se puede usar, pero se marca en el informe como **fuente débil** y no
   sostiene por sí sola ninguna decisión.

Dos reglas más: **contenido generado por IA sin fuente citada no vale** (ni como nivel 6);
y ante conflicto entre fuentes, se aplica el criterio del paso 4 — gana el más oficial y
reciente.

## Anti-patrones

- La exploración infinita: el presupuesto (nº de fuentes / tiempo) se declara antes de lanzar.
- Informes sin fechas o sin URLs: no valen como evidencia.
- Un solo punto de vista: los enfoques deben incluir SIEMPRE al escéptico y al simplificador.

## Nivel unidad (fuera de la fase 3)

- Unidad tipo `investigacion` (pregunta suelta): `especificacion.md` adaptada (Qué =
  preguntas exactas; Criterios = qué hace válida una respuesta); el resultado se promueve a
  `conocimiento/` en el cierre. NO necesita worktree.
- `investigacion.md` de un carril completo: se rellena ANTES de la spec (plantilla
  `investigacion.md`); sus respuestas alimentan el Cómo y los criterios.
