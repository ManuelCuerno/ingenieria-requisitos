# ADR-024 · Control plane de seguridad y evidencia causal

**Fecha:** 2026-08-05 · **Estado:** aceptada

## Contexto

Un verde no demuestra nada si el test pudo conectar a producción, consumir una imagen `latest`
de otro árbol, aceptar el HTTP 200 de otro preview o describir como target una instalación local.
Los fallos son distintos, pero comparten la ausencia de una identidad verificable anterior a la
mutación. También se observó el fallo inverso: imponer merge, app y OK humano a documentos y
prototipos retrasaba el primer artefacto sin proteger datos ni comportamiento desplegable.

## Decisión

El método publica `scripts/control_plane.py` como autoridad stdlib para cuatro contratos:

- el guard de test valida entorno, DSN, host y base y falla antes de invocar la conexión;
- `RunIdentity(repo, unidad, run)` deriva namespace, DB, puerto, nombre/tag Docker, temporal y log;
- una evidencia liga el claim a la huella del target y exige `legacy rojo → new verde → mutant
  rojo` cuando el control sea determinista; cada pasada conserva comando, exit code y digest;
- una tabla única fija gates y presupuestos por ruta documental/prototipo/exprés/directo/normal.

Los previews exponen la huella de ejecución y el test la compara. Un 200 sin esa identidad es
inconcluso. La huella declarada del target se vuelve a derivar mediante el guard; no es una etiqueta
libre. Docker usa tags derivados, nunca `latest`. Los manifiestos de CI no contienen secretos ni
pueden incluir su propia allowlist: la confianza en hosts remotos llega por parámetro protegido del
CI. `lint_ci.py --require-control-plane` exige manifiesto, wrapper canónico ejecutable, invocación
fail-fast antes de provisionar y recibo causal; si el manifiesto existe se valida incluso sin el
flag. La adopción es opt-in para no romper repositorios ya creados.

Documental conserva revisión fresca pero no fusión ni OK de una app inexistente. Prototipo no se
puede cerrar ni reconciliar como entrega: se conserva descartado y sus procesos se cancelan de
forma explícita. Exprés prueba el área y deja rastro en commit/PR, sin exigir OK de app; directo
prueba el área con revisión y OK; normal añade suite completa. Cuando una ficha opta por
`control_plane: requerido`, `unidad.py cerrar` consume el recibo y lo liga a su ruta y target antes
de aplicar ninguna transición. Riesgo de datos, permisos o seguridad escala la ruta y nunca queda
rebajado por esta tabla.

## Consecuencias y límites

- Los falsos verdes por target ajeno pasan a ser fallos explícitos y redactados.
- Dos árboles obtienen recursos separados y reproducibles; el puerto derivado aún debe reservarse
  y la identidad observable protege ante una colisión real.
- La mutación negativa demuestra sensibilidad de la prueba, no corrección universal del sistema.
- La comprobación estática demuestra el orden en el provisionador canónico, no por reflexión dentro
  de una aplicación externa; cada stack aún debe centralizar allí su primera conexión.
- Los presupuestos observan duraciones registradas; no introducen tests dependientes del reloj.
- El recibo liga y hace consistente la evidencia consumida, pero no es una firma remota inmutable:
  quien controle a la vez código, ficha y workspace podría fabricar un recibo coherente. La
  atestación criptográfica de un ejecutor externo queda fuera de este método local.
