# ADR-020 · Inbox de peticiones e investigación continua graduada

**Fecha:** 2026-08-04 · **Estado:** aceptada

## Contexto

El método persistía una unidad cuando ya se había decidido ejecutarla, pero no persistía la
petición al llegar. Un encargo que no se atacaba en el momento podía quedar solo en el contexto
de una sesión y desaparecer al resumirse, cambiar de agente o interrumpirse. Las rutas de
ingeniería tampoco tenían un sitio común donde decidir si una petición cambiaba flujos,
necesitaba investigar, ya estaba satisfecha o debía dividirse.

La fase 3 sí investigaba decisiones de plataforma con profundidad, pero aplicar siempre ese
ritual a una feature sería burocracia y no investigar nada durante la obra dejaría puntos
ciegos. Hacía falta graduar la investigación sin inventar un segundo método.

## Decisión

Toda petición accionable se captura antes de cualquier otra escritura en una carpeta propia
`docs/05-trabajo/peticiones/P-ID/`. El JSON es autoridad sobre palabras originales, revisión,
evaluación, estado y relaciones; las unidades y demás procesos siguen siendo autoridad sobre
su ejecución. ROADMAP conserva prioridad y dependencias; ESTADO conserva el digest humano.

La investigación tiene tres perfiles: `ninguna` con anclajes explícitos, `acotada` con 2–4
lentes y síntesis versionada por revisión, y `plataforma` mediante la síntesis global de la
fase 3. Cada respuesta acotada conserva fecha y URL o ruta anclada. Se elige por incertidumbre, novedad,
irreversibilidad y riesgo. Una síntesis no concluyente bloquea únicamente cuando afecta
seguridad, dinero, PII, contrato o pérdida de datos.

Toda orden fija `P-ID@revision`. Las relaciones son muchos-a-muchos: una petición puede abrir
varios procesos y una unidad puede satisfacer varias peticiones. El cierre de procesos
reconcilia la petición. Una orden única puede cerrarla automáticamente; un fan-out exige una
cobertura conjunta explícita después de terminar todas. Las aclaraciones materiales conservan
el enlace anterior como sustituido y obligan a adoptar la nueva revisión e invalidar la
aprobación del contrato.

Los workspaces nuevos nacen estrictos. Los migrados reciben `LEGACY.json` con allowlists
exactas de unidades, bugs y ramas previas, primero en `observacion`; no se inventan P-IDs
retroactivos. El modo `estricto` se activa tras medir tres peticiones reales.

ADR-017 no cambia: exprés/directo los construye el padre y normal/completo un subagente; todos
reciben revisión fresca de alguien que no construyó. El inbox decide el origen y la ruta, no
quién ejecuta cada carril.

## Garantía y límites

AGENTS.md hace de puerta social porque ningún fichero puede observar una frase nunca escrita.
Una vez capturada, `unidad.py`, `lint_metodo.py`, pre-push y CI bloquean órdenes, ramas y cierres
huérfanos. La captura no añade una aprobación del usuario ni interrumpe automáticamente lo que
ya está en vuelo.

## Consecuencias

- Un encargo puede esperar, dividirse, descartarse o demostrar que ya existía sin perderse.
- Investigar una feature añade preguntas concretas, no una fase 3 de diez agentes por defecto.
- Hay algo más de coste al entrar: un comando y un JSON pequeño en los casos simples.
- La cola no es planificación: elegir prioridad sigue siendo una decisión del ROADMAP/usuario.
- Revertir exige retirar los gates y conservar los JSON como historia; nunca borrarlos.
