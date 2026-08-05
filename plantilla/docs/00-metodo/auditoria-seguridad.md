# Playbook · Auditoría de seguridad (OWASP Top 10:2025) — núcleo agnóstico

**Qué es:** la revisión de seguridad obligatoria antes de exponer la aplicación a
internet. Se corre como **unidad tipo `auditoria`** (runbook `runbooks/auditoria.md`):
agente FRESCO, **solo lectura** de `main/`, produce un informe — jamás arregla nada.
**Cuándo:** ANTES de cada deploy a etapa 2 (internet/VPS), y periódicamente después.
**Contrato de cierre:** informe con hallazgos VERIFICADOS (severidad + evidencia +
reproducción) en la carpeta de la unidad; los aceptados por el humano PAREN unidades.

Este fichero es el **núcleo agnóstico**: las diez categorías de riesgo del OWASP Top
10:2025, con QUÉ se comprueba en cualquier stack. La pregunta ("¿está mitigado el riesgo
X?") es la misma en Django, Flask, Rails, Go o Node; lo que cambia es **el detector que la
responde**. Ese detector — herramienta + comando concreto por lenguaje/framework — vive en
`seguridad-por-stack.md`, que se enruta declarando **lenguaje + framework + gestor de
paquetes** en la `especificacion.md` de la unidad (igual que se declara el bias). Aquí NO
hay ni un comando específico de un framework: si lees un `grep` de Django en este núcleo,
es un bug del método.

> **Por qué se reescribió (lección):** el playbook anterior implementaba el Top 10 con
> `grep` de patrones Django. En un repo Flask esos patrones no matcheaban y el checklist se
> marcaba "revisado" sin haber revisado nada — **falsa cobertura**. Peor: muchas protecciones
> que Django trae de serie (CSRF, autoescape, validación de Host, cookies seguras) en Flask
> las pone el desarrollador a mano, así que "grep no encuentra nada" no es cobertura, es
> **exactamente la bandera roja** que la auditoría debía levantar. El detector equivocado para
> una pregunta agnóstica es el bug de raíz.

## REGLA DURA — el agente NO es el auditor único

**El agente jamás es el detector primario, ni el juez que archiva en silencio.** La evidencia
(2025-2026) es contundente en las dos direcciones:

- **Como detector solo, alucina y sobre-reporta.** Todo modelo frontera produce **10-50% de
  falsos positivos** en detección white-box (inviable para triaje sin revisión) y se
  documentan **alucinaciones en code review** — hallazgos inventados, líneas que no existen.
- **Como filtro agresivo, sobre-suprime lo que más importa.** El mejor scaffolding de filtrado
  LLM tiró los falsos positivos de un 98% a un 6%… pero **suprimió el ~22% de vulnerabilidades
  reales**, y por categoría **falló >77% en criptografía/política** (CWE-327/328).

De ahí el contrato, innegociable:

1. **La HERRAMIENTA genera los candidatos; el agente TRIAGE con evidencia.** El agente **no
   marca una casilla sin adjuntar el output de la herramienta** que la sustenta. "Revisado"
   sin evidencia = falsa cobertura = el bug que este playbook existe para matar (regla 12 del
   método: evidencia, no afirmación).
2. **Criptografía (A04), control de acceso / authz (A01) y diseño / lógica (A06) NO se
   auto-descartan.** Son justo donde el filtro LLM se come las vulns reales y donde ninguna
   herramienta estática cubre bien. Un hallazgo en estas categorías va SIEMPRE a revisión
   (segundo agente fresco o humano); nunca al descarte automático.
3. **El triaje LLM es fiable para inyección/XSS/SSRF** (grandes caídas de FP con casi 0% de
   pérdida ahí); úsalo para explicar y refutar candidatos de esas categorías, no para las tres
   del punto 2.

## Capa transversal — SIEMPRE, corra el stack que corra

Tres detectores agnósticos por ENCIMA de la hoja de stack. Son la red que no depende de
acertar el stack — precisamente lo que curaba la falsa cobertura:

1. **Semgrep con reglas OSS.** `semgrep scan --config=auto` (autodetecta lenguaje y framework)
   y `semgrep --config p/owasp-top-ten` en su porción libre. Hace **taint/dataflow real inter
   e intra-fichero** — no es `grep`: sigue el input contaminado a través de varias funciones
   hasta el sink. Solo dependemos de las reglas **OSS** del registry; el método es 100% open
   source, así que **no** usamos el ruleset Pro de pago de Semgrep (detalle en
   `seguridad-por-stack.md`).
2. **Escaneo de secretos.** Gitleaks como hook pre-commit (bloquea antes de entrar en git) y/o
   TruffleHog en CI (verifica si la credencial sigue viva → menos falsos positivos). **El
   historial de git cuenta**: un secreto commiteado y luego borrado sigue siendo un hallazgo.
3. **Claude Code `/security-review`** (language-agnostic: entiende intención, no patrones). Es
   el complemento perfecto del núcleo porque no sufre el problema del `grep` Django-first.
   Aviso oficial: no está endurecido contra prompt injection → solo sobre PRs de confianza.

Corra lo que corra, además de la hoja de stack se pasan estos tres. Cada categoría se cierra
con el output de un detector, nunca con un "revisado".

## Mapa de continuidad 2021 → 2025

El núcleo se ancla en **OWASP Top 10:2025** (edición vigente, finalizada enero 2026). Se
mantiene el mapeo a 2021 para no perder trazabilidad con auditorías previas:

| 2025 | Categoría | Venía de 2021 |
|---|---|---|
| A01 | Broken Access Control (ahora **incluye SSRF**) | A01 (+ A10 SSRF) |
| A02 | Security Misconfiguration | A05 |
| A03 | **Software Supply Chain Failures** (nueva; expande "componentes vulnerables") | A06 |
| A04 | Cryptographic Failures | A02 |
| A05 | Injection (incluye XSS) | A03 |
| A06 | Insecure Design | A04 |
| A07 | Authentication Failures | A07 |
| A08 | Software or Data Integrity Failures | A08 |
| A09 | Security Logging & Alerting Failures | A09 |
| A10 | **Mishandling of Exceptional Conditions** (nueva) | — |

---

## A01 · Broken Access Control (incluye SSRF)

- **Qué se comprueba (universal):** toda ruta que lea o mute datos de negocio exige sesión Y
  comprueba el dueño (el usuario logueado solo toca sus propios objetos). Acceso denegado por
  defecto, concedido explícitamente. IDs no adivinables que no expongan objetos ajenos (IDOR).
  **SSRF vive aquí:** toda petición que el servidor hace a una URL que viene — directa o
  indirectamente — del usuario valida esquema/host y bloquea rangos internos.
- **Hallazgo:** cualquier ruta que muestre o mute datos sin auth ni comprobación de propiedad;
  IDOR (cambiar el ID a mano alcanza datos de otro usuario); URL del usuario que llega a una
  petición del servidor sin lista blanca de esquema/host ni bloqueo de rangos internos
  (169.254.x, 10.x, 127.x, endpoint de metadatos del cloud).
- **Ojo:** authz y lógica de acceso las cubre MAL cualquier herramienta estática → revisión
  manual/diseño; **no auto-descartar** (regla dura, punto 2).

## A02 · Security Misconfiguration

- **Qué se comprueba (universal):** config de producción endurecida — modo debug apagado,
  páginas de error genéricas, sin cuentas por defecto/de ejemplo, sin features ni puertos
  innecesarios expuestos, cabeceras de seguridad presentes, paneles de administración no
  expuestos a internet. TLS/HTTPS en etapa 2.
- **Hallazgo:** modo debug alcanzable en producción, host/CORS permisivos (comodín `*`), panel
  de admin expuesto a internet sin segundo factor ni restricción, cabeceras de seguridad
  ausentes, puertos de BD/caché publicados, credenciales por defecto sin cambiar.

## A03 · Software Supply Chain Failures

- **Qué se comprueba (universal):** toda dependencia está fijada (lockfile) y libre de CVE
  conocido; el pipeline de build/CI no ejecuta código de terceros sin fijar ni `curl | bash`;
  los artefactos se verifican. Expande el viejo "componentes vulnerables y desactualizados" a
  **dependencias + build + distribución**.
- **Hallazgo:** dependencia con CVE conocido en la versión instalada, dependencias sin fijar
  (sin lockfile), framework fuera de su ventana de soporte, CI que corre acciones de terceros
  no pineadas a SHA, `curl | bash` de scripts remotos, artefactos sin verificar.
- **Detector:** el escáner SCA de tu hoja de stack (`pip-audit` / `bundler-audit` /
  `govulncheck` / `npm audit`) + `--config=auto` de Semgrep.

## A04 · Cryptographic Failures

- **Qué se comprueba (universal):** datos sensibles (contraseñas, PII, tokens) nunca en claro
  en almacenamiento ni tránsito; contraseñas con hash fuerte, con sal y lento (el del
  framework, no md5/sha1); TLS para datos en tránsito; sin secretos/claves hardcodeados.
- **Hallazgo:** secretos en código o en el historial de git, contraseñas con hash débil o sin
  hash, datos sensibles en claro, cripto débil/obsoleta (md5, sha1, DES, modo ECB), TLS
  desactivado o débil.
- **Ojo:** es la categoría donde el filtro LLM más suprime reales (>77% de fallo en
  CWE-327/328) → **no auto-descartar**; va a revisión (regla dura, punto 2).

## A05 · Injection (incluye XSS)

- **Qué se comprueba (universal):** toda entrada no confiable que llega a un intérprete (SQL,
  comando de SO, LDAP, plantilla, HTML) va parametrizada/escapada, nunca concatenada. Incluye
  **XSS** (dato no confiable renderizado sin escapar) además de SQLi y command injection.
- **Hallazgo:** SQL construido concatenando/interpolando entrada del usuario (el ORM/consulta
  parametrizada no lo es); shell/`eval`/`exec` que recibe datos externos; plantilla que
  renderiza contenido del usuario sin escapar (`|safe`, `mark_safe`, `dangerouslySetInnerHTML`,
  atributo sin comillas, `href="javascript:"`).
- **Detector:** el SAST de tu hoja de stack + Semgrep transversal (taint/dataflow, no `grep`).

## A06 · Insecure Design

- **Qué se comprueba (universal):** las superficies de abuso tienen freno por diseño — login,
  registro y recuperación de contraseña con rate-limit y bloqueo por intentos; operaciones
  destructivas con confirmación y rastro; sin enumeración de usuarios (mismo mensaje para "no
  existe" que para "contraseña mal"); flujos de negocio no abusables (cantidades negativas,
  manipulación de precio…).
- **Hallazgo:** login sin rate-limit ni bloqueo (fuerza bruta gratis), enumeración de usuarios,
  operaciones destructivas sin confirmación ni rastro, lógica de negocio explotable
  manipulando la entrada.
- **Ojo:** diseño y lógica de negocio — ninguna herramienta automática los cubre bien →
  revisión manual/diseño; **no auto-descartar** (regla dura, punto 2).

## A07 · Authentication Failures

- **Qué se comprueba (universal):** la autenticación es LA del framework, no una casera; las
  sesiones/tokens expiran y rotan; MFA donde importa; no se aceptan contraseñas débiles o por
  defecto; hay protección contra ataques automatizados de credenciales.
- **Hallazgo:** auth propia en vez de la del framework, hash de contraseña débil (también cae
  en A04), validadores de contraseña desactivados, sesiones/tokens eternos que no expiran, sin
  protección contra credential stuffing / fuerza bruta.

## A08 · Software or Data Integrity Failures

- **Qué se comprueba (universal):** el código y los datos de fuentes no confiables se verifican
  antes de usarse; sin deserialización insegura de datos no confiables; los mecanismos de
  CI/CD y de actualización verifican integridad (firmado/pineado).
- **Hallazgo:** deserialización insegura (`pickle.loads`, YAML inseguro, `unserialize` de datos
  externos), auto-actualización sin verificar firma, CI que corre acciones sin pinear (solapa
  A03), artefactos sin firmar.

## A09 · Security Logging & Alerting Failures

- **Qué se comprueba (universal):** los eventos de seguridad (logins, fallos, fallos de control
  de acceso, transacciones de alto valor) dejan rastro; los logs se monitorizan y **ALERTAN**
  (el renombrado 2025 enfatiza el *alerting*); los logs no contienen secretos ni PII en claro.
- **Hallazgo:** errores 500 que no llegan al registro de errores, logins fallidos sin log, logs
  que ESCRIBEN secretos o PII en claro (también es hallazgo), monitorización declarada que no
  existe en el código, ausencia de alertas ante eventos de seguridad.

## A10 · Mishandling of Exceptional Conditions

- **Qué se comprueba (universal):** los errores se manejan deliberadamente — **fail closed, no
  fail open**; los mensajes de error no filtran internals (trazas, consultas, rutas) al
  usuario; los caminos excepcionales (timeouts, fallos parciales, race/TOCTOU) no dejan el
  sistema en estado inseguro.
- **Hallazgo:** fail-open ante error (p.ej. una comprobación de auth que, si lanza excepción,
  concede acceso), páginas de error verbosas que filtran internals, excepciones no manejadas
  que revelan traza/config, estado inconsistente tras un fallo parcial.

---

## El informe y su destino

Un fichero `informe.md` en la carpeta de la unidad: un bloque por categoría OWASP (A01→A10),
cada uno con veredicto (`CUMPLE` / `HALLAZGO(S)`), el **output pegado del detector** (de la
hoja de stack o de la capa transversal — nunca un "revisado" pelado), y por hallazgo:
severidad (alta/media/baja), evidencia (comando + output real), cómo reproducirlo y
refutaciones intentadas. Cobertura total con severidad — nunca "solo lo grave" (hunde el
recall); se filtra después con el humano. Los hallazgos ACEPTADOS paren unidades (`bug`/
`refactor`) que entran al ROADMAP; los asumidos conscientemente quedan anotados en la sección
"Auditoría de seguridad" de DESPLIEGUE.md. La unidad se archiva con su informe: **sin esta
unidad archivada, `lint_deploy.py` bloquea el deploy.**
