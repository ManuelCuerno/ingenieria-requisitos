# Seguridad por stack — la hoja de detectores enrutada

**Qué es:** la capa por lenguaje/framework de la auditoría de seguridad. El núcleo
(`auditoria-seguridad.md`) es fijo y agnóstico — las diez categorías OWASP 2025 con QUÉ se
comprueba. Esta hoja convierte cada pregunta agnóstica en un **detector concreto**:
herramienta, comando y qué cuenta como hallazgo, por stack.

**Cómo se enruta:** se declara **lenguaje + framework + gestor de paquetes** en la
`especificacion.md` de la unidad de auditoría (ej. `{ lenguaje: python, framework: flask,
deps: pip }`), igual que se declara el bias — un dato explícito, no adivinado. El agente carga
solo la sección de su stack y la corre encima de la capa transversal del núcleo (Semgrep OSS +
escaneo de secretos + `/security-review`).

**Dos patas por stack:** (1) **SAST** — analiza tu propio código; (2) **SCA** — busca CVE en
tus dependencias (esto es A03:2025, Supply Chain). Ambas por lenguaje, más el **hardening del
framework** (lo que trae de serie vs. lo que debe poner el dev).

## Salida obligatoria de la primera unidad (ADR-018)

La sección elegida de esta hoja se materializa en `scripts/ci/security`; la suite real vive
en `scripts/ci/full-suite` y los linters de calidad en `scripts/ci/lint`. Los tres preparan su
entorno, fijan versiones de herramientas y devuelven código distinto de cero ante cualquier
hallazgo bloqueante. El workflow `quality-security` llama a lint y seguridad en paralelo en
pull requests, al entrar en `main` y semanalmente. Dependabot propone versiones nuevas; el
SCA bloquea una vulnerabilidad conocida. **Nueva no significa vulnerable**: no se rompe el
desarrollo solo porque exista una actualización.

## Transversal a TODOS los stacks: el secreto que se publica sin mostrarse

El método vigila que un secreto no se MUESTRE (regla de oro: nunca secretos ni PII). Estos
dos canales lo PUBLICAN sin mostrarlo nunca en pantalla, y aplican a cualquier lenguaje:

- **Horneado en la imagen.** `Dockerfile` con `COPY . .` + `.env` al lado = secreto dentro de
  una capa, que viaja con la imagen a donde vaya. Se corta con un `.dockerignore` que excluya
  el `.env`, el entorno virtual, `.git/` y los datos locales. `lint_metodo.py` da FAIL si hay
  Dockerfile sin `.dockerignore`, o si el `.dockerignore` no menciona el `.env`.
- **Escupido en los logs.** Scripts de datos de ejemplo que crean un usuario administrador y
  escriben su contraseña por salida estándar. Regla: ningún seed se ejecuta solo, y ninguno
  imprime credenciales: se generan por ejecución o llegan por un canal efímero fuera de logs.

## Autorización y datos E2E: contrato común (ADR-019)

El framework cambia el detector, no la política. Los permisos base se conceden a roles o
grupos, representados en `superficie.permisos.roles` y `superficie.permisos.grupos`; cada
restricción apunta a un solo `rol` o `grupo`. Propiedad, asignación, organización y estado
son condiciones adicionales. Cada entrada protegida niega por defecto y valida en el servidor: ocultar controles en la interfaz
no cuenta. Los tests nativos del stack recorren exhaustivamente la matriz y las restricciones
en una capa rápida, incluidas identidad anónima/suspendida, acceso propio/ajeno y entre
organizaciones cuando apliquen. La integración llama directamente a cada entrada protegida;
los E2E se limitan a los recorridos y fronteras críticas seleccionados en los planos.

`scripts/ci/provision-e2e` crea datos sintéticos deterministas por alias de persona/rol y
credenciales efímeras por ejecución. Debe ser explícito, idempotente y negarse a escribir
salvo que tanto el entorno como la base/tenant/instancia demuestren ser de pruebas. Nunca se
ejecuta durante arranque, migración o deploy; nunca copia producción ni publica secretos en
git, planos, capturas, artefactos o logs. Cuando los planos declaran E2E, la única secuencia
es `full-suite → e2e → provision-e2e → tests E2E`, para que ningún test corra con datos
viejos o sin preparar.

## El principio de la falsa cobertura invertida

En Django, encontrar `CsrfViewMiddleware` es señal de "bien". En **Flask, FastAPI y Express NO
encontrar CSRF/cabeceras es lo esperable y peligroso**: esos frameworks delegan esas
protecciones en el desarrollador. Por eso, en un stack que no las regala, **"el detector no
encuentra la protección" no es cobertura: es el hallazgo**. Cada sección marca qué trae el
framework de serie (verificar activado) y qué debe haber añadido el dev (el vacío es hallazgo).

## Todo OSS — y qué queda deliberadamente fuera

El bias es **100% open source**. Todas las herramientas de abajo lo son. Decisiones tomadas
para respetarlo:

- **Ruleset Pro de Semgrep: FUERA.** `p/owasp-top-ten` trae ~2360 reglas, de las que ~1800 son
  "Pro" (requieren login/plan de pago). Usamos solo la **porción OSS** del registry (`--config=auto`
  y la parte libre de `p/owasp-top-ten`). Si la cobertura libre de una categoría queda fina, se
  cubre con `/security-review` y revisión manual — **no** comprando el ruleset de pago.
- **Amazon CodeGuru Security: FUERA (descontinuado 2025-11-20).** Consola, recursos y docs
  retirados. No recomendar.
- **GitHub CodeQL / Advanced Security: fuera del set por defecto.** Gratis solo en repos
  públicos; de pago en privados, y nuestros repos son privados (bias autoalojado). Queda como
  extra opcional únicamente si un repo es público. No PHP ni Scala en CodeQL, además.
- **Amazon Inspector: no es SAST.** Vivo, pero es gestión de vulnerabilidades de
  workloads/dependencias (EC2/ECR/Lambda), no análisis del código fuente. Solo aplica como capa
  SCA de infra si se despliega en AWS.
- **Higiene de la herramienta:** fijar versión/hash de cada escáner y verificar firmas de
  binarios/imágenes (lección del compromiso de cadena de suministro de Trivy, marzo 2026). El
  propio escáner es superficie de A03.

---

## Python (base — cualquier framework Python)

- **SAST → Bandit** (PyCQA, Apache-2.0). Comando: `bandit -r .`
  Hallazgo: secretos hardcodeados, cripto débil (md5/sha1), llamadas peligrosas
  (`eval`/`exec`, `subprocess(..., shell=True)`, `yaml.load` inseguro, `pickle` sobre datos
  externos), `assert` usado para control en producción.
- **SCA → pip-audit** (PyPA + Trail of Bits, con apoyo de Google). Comando: `pip-audit` o
  `pip-audit -r requirements.txt` (`--fix` remedia).
  Hallazgo: cualquier paquete instalado con CVE conocido; dependencias sin fijar (sin lockfile/pin).

Encima de esta base, añadir la sección del framework Python concreto:

### Django (sobre Python)

- **Hardening → `python3 manage.py check --deploy`** (system check framework; solo lectura).
  Comando: `python3 main/manage.py check --deploy` (si el entorno lo permite).
  Hallazgo: `SECRET_KEY` débil/por defecto, `DEBUG=True` alcanzable, `ALLOWED_HOSTS` mal
  configurado (`['*']`), cookies sin `Secure`/`HttpOnly`, `SECURE_SSL_REDIRECT`/HSTS ausentes.
- **De serie (verificar activado):** autoescape en plantillas, `CsrfViewMiddleware`, ORM
  parametrizado, `XFrameOptionsMiddleware`, validación de Host, sesiones firmadas.
  Hallazgo = alguien lo **desactivó**: `csrf_exempt`, `|safe`/`mark_safe` sobre contenido del
  usuario, `.raw()`/`.extra()` con interpolación, `CORS_ALLOW_ALL_ORIGINS=True`.

### Flask / FastAPI (sobre Python) — OJO: protecciones a mano

Misma base `bandit` + `pip-audit`. Aquí **no hay `check --deploy`**: la verificación es manual,
guiada por la doc de seguridad oficial del framework, y **el vacío es hallazgo** (falsa
cobertura invertida).

- **Flask** — no trae CSRF ni cabeceras de serie.
  Hallazgo: endpoints de formulario que mutan estado **sin CSRF** (debe estar Flask-WTF); sin
  cabeceras de seguridad (debe estar Flask-Talisman: HSTS/CSP/X-Content-Type-Options/X-Frame-Options);
  flags de cookie sin poner (`SESSION_COOKIE_SECURE`/`HTTPONLY`/`SAMESITE`); hosts sin validar
  (`TRUSTED_HOSTS`). Que el detector "no encuentre CSRF" = hallazgo, no cobertura.
- **FastAPI** — es API JSON: sin autoescape HTML ni CSRF por diseño, pero el hashing de
  contraseñas, la emisión/validación de JWT y la lógica de authz son del dev; CORS/cabeceras
  vienen de Starlette y las configura el dev.
  Hallazgo: authz o validación de token implementadas a mano y con fallos; CORS abierto; sin
  hashing fuerte de contraseñas.

---

## Ruby on Rails

- **SAST → Brakeman** (Rails-aware, zero-config, falsos positivos muy bajos).
  Comando: `gem install brakeman` → `brakeman main/` (o `brakeman` en la raíz del repo Rails).
  Hallazgo: SQLi, XSS, command injection, mass assignment y decenas de tipos más que reporta.
- **SCA → bundler-audit** (offline, sobre `Gemfile.lock`, rubysec advisory DB).
  Comando: `bundle-audit check --update`.
  Hallazgo: gema con CVE conocido en la versión fijada.
- **De serie (verificar activado):** `protect_from_forgery` (CSRF, ON por defecto),
  ActiveRecord parametrizado, autoescape en ERB, strong parameters, `CookieStore` cifrado.
  Hallazgo = desactivado/eludido: interpolación en `where`, `force_ssl` off, `html_safe` sobre
  entrada del usuario.

---

## Go (net/http, Gin, Echo…)

- **SAST → gosec** (escanea AST/SSA, mapea cada hallazgo a CWE).
  Comando: `gosec ./...` (desde la raíz del módulo).
  Hallazgo: inyección (SQL/comando/plantilla), secretos hardcodeados, cripto/TLS débil, path
  traversal, errores sin manejar, permisos de fichero laxos.
- **SCA → govulncheck** (equipo oficial de Go; **reachability-aware** — solo reporta si la
  función vulnerable se llama de verdad → muy poco ruido).
  Comando: `go install golang.org/x/vuln/cmd/govulncheck@latest` → `govulncheck ./...`.
  Hallazgo: vulnerabilidad conocida **alcanzable** en tu código.

---

## Node / Express

- **SAST → Semgrep OSS** (la capa transversal cubre JS/TS y Express con reglas libres; no hay
  un especialista de framework OSS equivalente a Brakeman). Opcional, también OSS: `njsscan` y
  `eslint-plugin-security`.
  Comando: `semgrep scan --config=auto` (ya en la capa transversal).
  Hallazgo: taint de entrada a sink (SQLi, command injection, XSS reflejado…).
- **SCA → npm audit** (nativo, npm ≥6). Comando: `npm audit`, `npm audit --audit-level=high`
  en CI, `npm audit fix` para remediar.
  Hallazgo: dependencia con advisory conocido.
- **Hardening — aviso: Express trae prácticamente nada de serie.** *"La responsabilidad de
  validar y manejar correctamente la entrada del usuario es tuya."* El vacío es hallazgo:
  - **Helmet** — `app.use(helmet())` pone 12+ cabeceras (CSP, HSTS, X-Frame-Options,
    X-Content-Type-Options) y quita `X-Powered-By`. Hallazgo: sin Helmet (cabeceras ausentes),
    `X-Powered-By` expuesto.
  - **CSRF no viene** — hallazgo: rutas que mutan estado sin protección CSRF.
  - Cookies con flags y nombre de sesión no-default; rate limiting; usar Express ≥4 (2.x/3.x
    sin soporte). Hallazgo: config de sesión por defecto, sin rate-limit en login.

---

## Otros ecosistemas (fuera del bias — nota breve)

Si un proyecto se desvía a Java/Kotlin, .NET, Rust o PHP (requiere ADR, no es el stack por
defecto), el enrutado es el mismo patrón con herramientas OSS:

| Stack | SAST | SCA (deps) |
|---|---|---|
| Java / Kotlin | Semgrep OSS (+ SpotBugs+FindSecBugs) | OWASP Dependency-Check |
| .NET / C# | Semgrep OSS | `dotnet list package --vulnerable` / OWASP Dependency-Check |
| Rust | Semgrep OSS + `cargo clippy` | `cargo audit` / `cargo deny` (RustSec DB) |
| PHP (Laravel/Symfony) | Semgrep OSS (+ Psalm/PHPStan taint) | `composer audit` |

En todos, la capa transversal del núcleo (Semgrep OSS + secretos + `/security-review`) sigue
aplicando; esta tabla solo añade el especialista y el SCA nativo del ecosistema.
