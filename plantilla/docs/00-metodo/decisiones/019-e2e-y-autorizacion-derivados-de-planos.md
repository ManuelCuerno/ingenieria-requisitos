# ADR-019 · E2E y autorización se derivan de los planos

**Fecha:** 2026-08-04 · **Estado:** aceptada

## Contexto

Convertir cada criterio en un E2E haría la suite lenta, frágil y combinatoria. Hacer lo
contrario —probar solo pantallas— dejaría sin demostrar que el servidor rechaza a un rol, a
otro propietario o a otra organización. También faltaba una forma segura y repetible de crear
las identidades necesarias sin llevar credenciales ni datos reales a git.

## Decisión

1. Los planos seleccionan comportamiento, no framework: los E2E nacen de recorridos,
   criterios y fronteras críticas ya aprobados; no contienen Playwright, Django, Node ni
   pasos duplicados.
2. Persona, rol, grupo u organización y alcance son conceptos distintos. Cada actor autenticado
   declara `actor.rol` y, si aplican, `actor.organizacion`, `actor.grupos` y `actor.estado`.
   Los permisos base se conceden en `superficie.permisos.roles` o
   `superficie.permisos.grupos`, nunca directamente a una persona salvo política excepcional
   y decisión explícitas. Cada restricción identifica un solo `rol` o `grupo`; propiedad,
   tenant, asignación, estado y separación de funciones son sus condiciones adicionales.
3. La autorización niega por defecto y se comprueba en el servidor. Ocultar un botón no
   demuestra una denegación.
4. La matriz (rol o grupo) × acción × recurso × alcance se cubre exhaustivamente con
   tests rápidos;
   cada entrada protegida tiene integración; el navegador conserva solo un camino feliz por
   rol interactivo y una denegación por frontera crítica distinta.
5. Cuando los planos declaran E2E, la primera unidad de código y CI incluye autenticación
   mínima en greenfield o adopta la existente en brownfield, y crea el harness. La cadena es
   única: `full-suite` llama a `e2e`; `e2e` llama primero a `provision-e2e` y después a los
   tests. Sin stack o sin selección E2E no se inventan usuarios, scripts ni framework.
6. El provisionado es explícito, idempotente y determinista por alias de persona/rol. Se
   niega a escribir fuera de local/test/E2E y exige además una base, tenant o instancia
   inequívocamente de pruebas. Nunca corre como efecto de arranque, migración o deploy.
7. Los datos son sintéticos. Contraseñas y tokens nacen por ejecución y no aparecen en
   planos, specs, git, capturas, artefactos o logs. Los datos de producción no se copian.

## Consecuencias

- La cobertura de permisos crece sin multiplicar navegadores ni ralentizar cada cambio.
- Dos identidades del mismo rol, otra organización, una identidad suspendida y una sesión
  anónima se crean solo cuando las fronteras del plano las necesitan.
- Un fallo de provisión, autorización o E2E propaga rojo a `full-suite`, PR y despliegue.
- Los proyectos anteriores sin `pruebas_e2e` siguen siendo compatibles hasta que sus planos
  adopten el contrato de forma explícita.
