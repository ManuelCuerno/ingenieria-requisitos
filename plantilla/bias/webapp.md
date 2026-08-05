# Bias tecnológico — la estrategia ganadora para el no-técnico

**v1 — 2026-07-26. Decidido por Nate.**
Función: **acotar el espacio de búsqueda de la
fase 3 (Investigación)** — la investigación parte de estos principios y solo se desvía de ellos
justificando por qué; los agentes nunca eligen tecnología en el vacío.

## El porqué raíz (de Nate, literal)

Los usuarios del método son **totalmente novatos: no leen código y no tienen criterio técnico**.
Este bias es **una estrategia ganadora pensada para que el no-técnico pueda tener el máximo
éxito posible**: todas las decisiones tecnológicas se sesgan hacia lo que minimiza la cantidad
de código propio, la cantidad de decisiones técnicas, y la cantidad de cosas que la IA tenga
que inventar por su cuenta.

## Los principios

1. **100% open source.** Frameworks y software de código abierto para todo. Nada propietario
   en el stack de desarrollo.

2. **Frameworks que regalen lo máximo posible:**
   - **Seguridad de serie** (auth, sesiones, protección CSRF/XSS/SQL-injection resueltas por
     el framework, no por código propio).
   - **Scaffolding**: generación de estructura, admin, migraciones, ORM — lo prehecho que
     funciona bien.
   - Convenciones fuertes: que el framework decida por nosotros todo lo decidible.

3. **SaaS: evitar a toda costa.** Autoimplementamos/autoalojamos lo nuestro. Condición: con
   **diseños estándar y sencillos**, formas estándar de hacer las cosas — autoalojar no es
   excusa para inventar.

4. **Mínimo código posible.** La mejor línea es la que no se escribe. Reutilizar > configurar >
   escribir. Reinventar la rueda: prohibido salvo justificación explícita.

5. **Máxima adherencia al framework.** Se hace como el framework dice que se hace ("the
   framework way"). Desviarse del camino oficial requiere justificación escrita (ADR).

6. **Mínima invención de la IA.** Las tecnologías se eligen para que el agente tenga el máximo
   de ejemplos, documentación y patrones establecidos — y el mínimo espacio para inventar
   sistemas nuevos por su cuenta.

## El stack por defecto — v1

Evolución acordada en conversación: la propuesta inicial de Nate era Django+React+REST; tras
comparar 4 candidatos (Django puro, Django+React, Rails 8, Laravel) contra los principios del
manifiesto, se eligió **Django-first con React como escalada** — mantiene la elección de Nate
(Django, Python) y maximiza scaffolding/mínimo código.

| Capa | Elección | Justificación |
|---|---|---|
| Backend + frontend | **Django full-stack** (plantillas + forms + auth + **admin**) | Un lenguaje (Python, el más universal), el admin de regalo = back-office sin código, seguridad de serie |
| Interactividad | **HTMX** | Interactividad sin SPA; patrones server-rendered que los agentes dominan |
| Estilos | **Tailwind** | Dictado por Nate; universal |
| Base de datos | **PostgreSQL** | El default de Django; aburrida y universal |
| API + SPA | **React + Django REST Framework, SOLO como escalada** | Si un flujo exige interactividad rica; requiere ADR que lo justifique |
| Mobile | **Web responsive + PWA** | Cero stack nuevo; instalable desde navegador (aclarado: Tailwind es CSS, no mobile) |
| Tareas en 2º plano | **Celery + Redis**, con **django-celery-results** (estados/resultados/tracebacks visibles en el admin) y **django-celery-beat** (tareas periódicas editables desde el admin) | Dictado por Nate: la cola más universal de Python; el usuario novato ve y gestiona las tareas desde su admin. Config clave: `task_track_started = True` |
| Caché | Redis (ya presente por Celery) | Cero piezas adicionales |
| Búsqueda | PostgreSQL full-text | Sin Elasticsearch salvo ADR |
| Estáticos / config | WhiteNoise / django-environ | Sin piezas extra; 12-factor |
| Testing | **pytest + Playwright** | Los tests de aceptación son los gates del modo novato; Playwright genera las capturas-evidencia |
| Linters | **ruff + djlint**, en hook y CI | "Lo verificable por linter va al linter" |
| Observabilidad | **Uptime Kuma + GlitchTip** (autoalojados en el mismo Compose) | Datos para el rol de observabilidad del padre |
| Backups | **pg_dump diario automático + copia en OTRO sitio** (otro disco en local; almacén externo si hay internet) | Innegociable autoalojando (lección Replit aplicada a infra) |
| Versiones | **LTS/estable de cada pieza, fijada al arrancar** | Queda escrita en `03-investigacion/SINTESIS.md`; actualizar = unidad `migracion` con rollback; revisión cada 6 meses o ante vulnerabilidad |

**Ejecución por etapas (el deploy NO se presupone — es decisión de cada proyecto y su momento):**

El mismo Docker Compose corre idéntico en cualquier máquina. Cada etapa solo AÑADE piezas:

| Etapa | Dónde corre | Qué añade |
|---|---|---|
| **0 · Local** (punto de partida por defecto) | Un ordenador (el del usuario, o uno de la oficina) | Nada: Compose + navegador (o el peldaño mínimo, abajo). Sin dominio, sin HTTPS público, sin email (recuperación de contraseña vía admin), backups a otro disco |
| **1 · Red local (LAN)** | Un mini-PC/servidor de la oficina | Acceso desde los móviles/equipos de la casa (la PWA funciona en LAN); sigue sin internet |
| **2 · Internet (VPS)** | VPS autoalojado (dictado por Nate para esta etapa) | Caddy + dominio + HTTPS, SES para email, copia de backups fuera de la máquina |

Subir de etapa = unidad de trabajo del tipo que toque (normalmente "migración"), con su spec.
El método no obliga a llegar a la etapa 2: hay negocios que viven perfectamente en la 0 o la 1.

**El entorno local de desarrollo, en dos peldaños (para que NINGÚN PC quede fuera):**

- **Peldaño mínimo (el punto de partida por defecto):** Django no necesita Docker para
  desarrollar — venv + `manage.py runserver` + **SQLite** (el default de Django) corren en
  cualquier máquina de los últimos 15 años. Mismo código, misma app en el navegador. El paso
  SQLite→Postgres es una unidad de migración pequeña cuando el proyecto o el PC lo permitan
  (el ORM aísla casi todo; se hace ANTES de la etapa 1).
- **Peldaño Compose (cuando lo use más gente a la vez o corra fuera de tu máquina):** el
  esqueleto andante genera el `docker-compose.yml` del proyecto — Django + PostgreSQL (y
  Celery + Redis SOLO cuando el proyecto tenga tareas en segundo plano; antes, no existen).
  La app corre en contenedores y se prueba en el navegador local; los e2e de Playwright
  atacan ese servidor. Pide un PC razonable (~8 GB RAM, o Linux donde Docker es casi gratis).

Cuál de los dos toca no lo decide el agente: sale de la respuesta del usuario a **«¿esto lo va
a usar más gente a la vez, o lo corres tú en tu máquina?»**.
**Higiene obligatoria del esqueleto andante** (lo genera la primera unidad; el linter del
método comprueba la primera y el revisor fresco las otras dos):

- **`.dockerignore` ANTES del primer build, sin excepción.** El Dockerfile que sale por
  defecto lleva `COPY . .`, y al lado vive el `.env` que el propio método exige. Sin
  `.dockerignore` el primer `docker compose build` hornea la `SECRET_KEY` dentro de una capa
  de la imagen, y de ahí ya no se borra. Mínimo: `.env`, el entorno virtual, `.git/`, la base
  de datos local, `node_modules/`, `.runtime/`.
- **Dependencias de producción y de desarrollo, separadas** (`requirements.txt` /
  `requirements-dev.txt` o equivalente): pytest y Playwright no viajan a la imagen de
  producción.
- **El seed de datos de ejemplo no se ejecuta solo ni imprime credenciales.** Un entrypoint
  que crea el superusuario en cada arranque y escribe su contraseña en los logs es una puerta
  abierta escrita en un fichero que todo el mundo lee.
- **CI real, no verde decorativo (ADR-018).** La misma primera unidad crea y prueba
  `scripts/ci/{full-suite,lint,security}`, workflows `tests` y `quality-security`, y
  Dependabot para los manifiestos reales. Las Actions van por SHA y una CVE bloquea; una
  actualización ordinaria solo propone un pull request.

- **Regla de tests en ambos peldaños:** pytest corre SIEMPRE en el venv (rápido, sin
  Docker); Playwright corre headless contra el servidor local que haya. Si ni el peldaño
  mínimo entra (PC realmente imposible): entorno de desarrollo remoto — un VPS barato o
  GitHub Codespaces — como decisión consciente y portable ("¿puedo irme en una tarde?" sí:
  es solo el entorno, el código vive en git).

**Refinamiento del principio anti-SaaS (regla de portabilidad):**
- **SaaS de protocolo — PERMITIDO**: servicios detrás de un estándar portable donde cambiar de
  proveedor es cambiar 3 líneas de config y se puede uno ir en una tarde: relay SMTP para email
  transaccional (autoalojar correo = infierno de deliverability documentado; **referencia:
  AWS SES** — SMTP puro, ~$0,10/1.000 emails, portable a cualquier otro relay), almacén
  S3-compatible para la copia externa de backups, CI de GitHub (donde ya vive el repo).
- **SaaS de plataforma — PROHIBIDO**: lo que captura datos o lógica (backend-as-a-service,
  auth de terceros, BD gestionadas propietarias).
- La línea no es "SaaS sí/no": es **"¿puedo irme en una tarde?"**.

**Lo que se resiste añadir salvo ADR**: Elasticsearch, Kubernetes, microservicios, más bases de
datos. PostgreSQL hace de BD, buscador y almacén de resultados; Redis solo cola+caché.

**Efecto sobre la fase 3 (Investigación)**: con el bias fijado, la investigación de cada
proyecto se reduce a (a) lo específico del dominio (librerías open source para necesidades
concretas) y (b) justificar con ADR cualquier desviación del stack. Mínima invención.

## Decisiones cerradas (v1)

1. **Mobile → web responsive + PWA.** Cero stack nuevo: la misma app Django+Tailwind,
   instalable desde el navegador (Tailwind es CSS, no una solución mobile). Capacitor solo si
   algún día se exige presencia en las tiendas de apps, y entonces con ADR. React Native
   descartado: un stack paralelo entero y la máxima invención posible para los agentes.
2. **React vs Django puro → la UI más simple que satisfaga los flujos.** Django plantillas +
   forms + admin + HTMX por defecto; **React + DRF solo cuando un flujo exija interactividad
   rica, y con ADR que lo justifique**. Es lo que maximiza scaffolding y minimiza código propio
   (principios 2 y 4): un React por defecto añade un segundo stack — build, estado, tokens de
   auth — que Django regala gratis en su camino server-rendered.
3. **Coste del anti-SaaS → asumido conscientemente.** Autoalojar traslada carga al rol de
   deploy/observabilidad (backups, actualizaciones, seguridad del servidor). Se compensa
   exigiendo que el stack de operación sea también aburrido y estándar — Docker Compose + un
   VPS — para que el mismo bias cubra deploy y observabilidad sin piezas nuevas.
4. **Versiones → la LTS/estable de cada pieza, fijada al arrancar.** Se fija en el momento de
   arrancar el proyecto y queda escrita en `03-investigacion/SINTESIS.md`. Actualizar es
   SIEMPRE una unidad de tipo `migracion` con su rollback. Se revisa al menos una vez cada
   6 meses, o inmediatamente ante una vulnerabilidad conocida.

Cerradas el 2026-07-29 con el criterio que el propio bias defiende, para desbloquear la v1;
cualquiera es revertible con un ADR.

## Defensa del bias — "¿por qué no Next.js/Prisma?" (argumentario para docencia)

Respuesta preparada para la objeción más previsible ("yo quiero usar Next.js y Prisma").
Cinco golpes + una concesión honesta.

### 1. "Mejor" ¿para quién? — reencuadre

Next.js+Prisma es un buen stack **para developers de JavaScript que leen código**. Nuestro
usuario no lee código. El criterio de evaluación cambia entero: no gana el stack con mejor
experiencia de desarrollo, gana el que **más decisiones toma por ti y menos deja inventar a
la IA**.

### 2. Cuenta las decisiones — pilas incluidas vs kit de montaje

| Necesitas | Django | Next.js |
|---|---|---|
| Auth | incluida | elige: Auth.js, Lucia, Clerk (SaaS)… |
| Admin/back-office | **incluido, gratis** | no existe: constrúyelo o paga un SaaS |
| ORM + migraciones | incluido | elige: Prisma, Drizzle… |
| Formularios + validación | incluido | elige: react-hook-form + Zod + … |
| Protección CSRF/XSS/SQLi | activada por defecto | ensámblala tú |

Cada hueco = una decisión + código pegamento escrito por la IA = superficie de error que el
usuario no puede auditar. ~6-8 decisiones contra ~1. El admin gratis es el back-office de la
persona de negocio desde el día uno, con cero líneas.

### 3. El churn mata a la IA — y lo midió el propio Vercel

**Vercel midió que los agentes solo aprobaban el 53% de tareas sobre las APIs de Next.js 16**;
necesitaron incrustar un índice de docs de 8KB en el contexto para llegar al 100%
(`fuentes/vendors/vercel-agents-md-evals.md`, 27-ene-2026). Next.js cambia de forma cada año
(Pages Router → App Router → Server Components…): el modelo tiene varias eras incompatibles
mezcladas en la cabeza. Django lleva ~20 años con la misma forma. Para una IA, datos de
entrenamiento COHERENTES valen más que abundantes-pero-contradictorios. Su propio fabricante
documenta que el agente necesita muletas con su framework; Django no las necesita.

### 4. El VPS no es el terreno de Next.js — es el terreno de Django

Next.js está optimizado para desplegarse en Vercel (su modelo de negocio); autoalojarlo en un
VPS es el camino de segunda clase de su propia documentación. Django en un VPS es su historia
nativa desde hace dos décadas: un proceso + un Postgres. Con requisito anti-SaaS y autoalojado,
un stack rema a favor y el otro en contra de su propio fabricante.

### 5. Seguridad para quien no puede revisarla

La seguridad de Django viene activada por defecto y lleva 20 años de batalla. En el mundo JS
la seguridad se ENSAMBLA (sesión en una librería, CSRF en otra, pegamento de la IA). Para un
usuario que no puede leer el código: "lo hace el framework" es una garantía; "lo pegó el
agente" es una esperanza.

### La concesión honesta (decirla antes de que te la digan)

Next.js no es malo. Si el producto es una interfaz altamente interactiva (dashboard en tiempo
real, editor), la capa React importa — por eso el método la contempla **como escalada
justificada con ADR**, no la prohíbe. Y para un dev de JS que disfruta ensamblando su stack,
Next.js es legítimo — *para él*. Este método no está diseñado para él: está diseñado para que
una persona que no programa tenga un sistema funcionando, seguro y aburrido, con el mínimo
número de decisiones y de inventos de la IA entre ella y su negocio.

**Remate en una frase:** "Tu stack optimiza la experiencia del programador; el mío optimiza la
supervivencia del no-programador. Y hasta Vercel ha medido que su framework necesita muletas
para que la IA no se pierda — el mío no."

## Triple justificación

- **Ingeniería**: tecnologías mainstream y aburridas = densidad máxima de documentación y
  ejemplos = menos alucinación y menos invención del agente; seguridad delegada al framework
  = menos superficie de error en manos de quien no puede auditarla.
- **Método Nate**: el usuario no puede evaluar decisiones técnicas → se le quita la decisión
  de encima; el framework decide, el bias lo deja escrito, y la IA obedece al framework.
- **Corpus**: la constitución de Spec Kit tiene literalmente artículos "Library-First",
  "Anti-Abstraction" y "Simplicity" como gates del plan (`fuentes/vendors/spec-kit-spec-driven.md`,
  plantilla de constitución) — mismo espíritu: framework primero, abstracción propia prohibida
  sin justificar. La evidencia Vercel (agentes fallan sobre APIs fuera de su entrenamiento —
  `fuentes/vendors/vercel-agents-md-evals.md`) respalda elegir tecnología con máxima huella de
  entrenamiento. El anti-SaaS es decisión propia de Nate [sin posición del corpus]; el
  "mínimo código/adherencia al framework" conecta con la doctrina de contexto mínimo y la
  advertencia de Anthropic sobre andamiaje propio que se vuelve overhead
  (`fuentes/anthropic/large-codebases.md`).

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
