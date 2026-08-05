# Auditoría de calidad de código — playbook del auditor

**Rol:** agente FRESCO (sin contexto de construcción previa), **SOLO LECTURA**. Se ejecuta
como unidad tipo `auditoria` (ver `runbooks/auditoria.md`: sin worktree de escritura, lee
`main/`). **Periodicidad:** cada 5-10 cierres o SIEMPRE antes de un deploy.

**Doctrina que audita** (dictada, no negociable): KISS a rajatabla · sin funciones muy
largas · modularidad — cada cosa en su sitio, en su módulo · CERO lógica duplicada ·
el proyecto se mantiene limpio ANTES de llegar a la tarea · todo bug arreglado deja
test de regresión vivo.

## 1 · Cuándo y cómo se lanza

El padre despacha una unidad `auditoria` con esta página como especificación de checks; el
auditor ejecuta la checklist completa desde `main/` (código) y la raíz del workspace (docs)
y entrega el informe en la carpeta de la unidad.

**Regla dura: los hallazgos NO se arreglan en caliente.** El auditor no toca ni una línea.
Cada hallazgo aceptado por el humano PARE una unidad (`refactor` o `bug`) con su severidad,
que entra al ROADMAP por el cauce normal. Auditar y arreglar son unidades distintas, siempre.

**El auditor pega outputs, no opina.** Todo veredicto lleva debajo el output del comando que
lo demuestra (regla 12: evidencia, no afirmación). Antes de reportar, cada hallazgo se
intenta refutar (verificado > plausible). Cobertura total con severidad; filtrar es trabajo
del padre, nunca del auditor.

> Los comandos asumen Python (≥3.8 para los scripts `ast`). En otro stack, el auditor
> traduce cada check a la herramienta equivalente del stack (mismo umbral, misma lente)
> y lo declara en el informe.

## 2 · Checklist (en orden; ningún check se salta)

Todos los comandos de código se ejecutan **desde la raíz de `main/`**. El check 2.5 se
ejecuta desde la raíz del workspace (necesita `docs/` y `main/` a la vez).

### 2.1 Lint mecánico — complejidad (KISS medible)

Usa la config del proyecto si existe (`ruff` lee `pyproject.toml`/`ruff.toml` solo;
`--select` sustituye la selección pero respeta los `exclude`). Primero el resumen, luego
el detalle con fichero:línea:

```bash
ruff check . --select C901,PLR0912,PLR0915,PLR0913 --statistics
ruff check . --select C901,PLR0912,PLR0915,PLR0913 --output-format concise
```

(C901 complejidad ciclomática · PLR0912 demasiadas ramas · PLR0915 demasiadas sentencias ·
PLR0913 demasiados argumentos.)

Si `ruff` no está instalado, venv temporal **FUERA del repo** (el auditor no escribe dentro):

```bash
python3 -m venv /tmp/venv-auditoria && /tmp/venv-auditoria/bin/pip install -q ruff
/tmp/venv-auditoria/bin/ruff check . --select C901,PLR0912,PLR0915,PLR0913 --statistics
```

Severidad orientativa: función con complejidad >15 o >18 ramas = GRAVE; el resto de avisos
= MEDIA en masa (se agrupan por módulo), LEVE si son casos sueltos y razonables.

### 2.2 Funciones y módulos gordos

Funciones de más de 50 líneas (ordenadas de peor a mejor):

```bash
python3 - <<'EOF'
import ast, pathlib
EXCL = {'venv', '.venv', 'migrations', 'node_modules', '.git', 'static', 'media'}
hits = []
for p in sorted(pathlib.Path('.').rglob('*.py')):
    if EXCL & set(p.parts): continue
    try: tree = ast.parse(p.read_text(encoding='utf-8'))
    except (SyntaxError, UnicodeDecodeError): continue
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ln = n.end_lineno - n.lineno + 1
            if ln > 50: hits.append((ln, f'{p}:{n.lineno}', n.name))
for ln, loc, name in sorted(hits, reverse=True): print(f'{ln:4d}  {loc}  {name}')
EOF
```

Ficheros de más de 400 líneas:

```bash
find . -name '*.py' -not -path '*/venv/*' -not -path '*/.venv/*' \
  -not -path '*/migrations/*' -not -path '*/node_modules/*' \
  -exec wc -l {} + | awk '$2 != "total" && $1 > 400' | sort -rn
```

Severidad: función >100 líneas o fichero >800 = GRAVE; por encima del umbral = MEDIA.
Los tests gordos son LEVE (longitud en tests es tolerable; duplicación no).

### 2.3 Duplicación de lógica de negocio — el check estrella

La regla es CERO lógica duplicada: **un concepto de negocio se implementa en UN sitio**.
El caso canónico que este check existe para cazar: un pago que se crea en dos sitios con
dos sistemas distintos — dos rutas de código distintas llamando a la pasarela/creando el
registro de cobro. Dos implementaciones divergen SIEMPRE: una recibe el fix y la otra no.

Método en 3 pasos:

**(a) Identificar los conceptos críticos.** Lee `docs/02-flujos/INDICE.md` y lista los
conceptos con consecuencias (dinero, identidad, comunicación): pagos, cobros, facturas,
altas/bajas de usuario, envío de emails, sincronizaciones con servicios externos.

**(b) Por cada concepto, mapear QUÉ módulos lo implementan.** Grep de sus señales: nombres
de modelos, dominios de APIs externas, verbos clave. Dos comandos tipo (sustituir señales):

```bash
# ¿Qué módulos tocan el concepto? (ej.: facturación con Holded)
grep -rln --include='*.py' -iE 'holded|invoice|factura' . | grep -v migrations

# ¿Desde dónde se llama a APIs externas? (llamadas HTTP por módulo)
grep -rn --include='*.py' -E 'requests\.(get|post|put|patch|delete)|urlopen' . \
  | grep -vE 'venv|migrations|tests' | cut -d: -f1 | sort | uniq -c | sort -rn
```

**(c) Veredicto.** Que un concepto aparezca en varios módulos no es hallazgo (modelo en un
sitio, vista en otro es normal). El hallazgo es **dos rutas que EJECUTAN la misma acción**:
dos `objects.create` del mismo modelo de negocio en módulos distintos, dos sitios que
llaman al mismo endpoint externo, dos funciones que calculan la misma regla. Abre los
ficheros del paso (b) y confírmalo leyendo. Dos implementaciones del mismo concepto =
**hallazgo GRAVE siempre**, citando AMBAS rutas con fichero:línea.

### 2.4 Cada cosa en su módulo

Señales de lógica fuera de sitio (cada una: comando → leer los top → veredicto):

```bash
# Reglas de negocio en views: escrituras ORM por fichero de vistas
# (muchas escrituras en una vista = lógica que pertenece a models/servicios)
grep -rn --include='views.py' -E '\.objects\.(create|update|get_or_create|bulk_create)|\.save\(\)' . \
  | grep -v venv | cut -d: -f1 | sort | uniq -c | sort -rn

# Reglas de negocio en templates: condicionales compuestos
grep -rn --include='*.html' -cE '\{% *if .+ (and|or) .+ *%\}' . 2>/dev/null \
  | grep -v ':0$' | grep -vE 'venv|node_modules' | sort -t: -k2 -rn | head

# utils.py cajón de sastre: tamaño hoy…
find . \( -name 'utils.py' -o -name 'helpers.py' -o -name 'misc.py' \) \
  -not -path '*/venv/*' -exec wc -l {} + | sort -rn
# …y si además CRECE (commits recientes que lo tocan), es imán de deuda:
git log --oneline --since='3 months ago' -- '*utils*' '*helpers*' | wc -l
```

Imports circulares (detector estático; cada ciclo impreso se verifica leyendo los ficheros):

```bash
python3 - <<'EOF' | sort -u
import ast, pathlib
EXCL = {'venv', '.venv', 'migrations', 'node_modules', '.git', 'static', 'media'}
mods = {}
for p in pathlib.Path('.').rglob('*.py'):
    if EXCL & set(p.parts): continue
    parts = p.with_suffix('').parts
    if parts[-1] == '__init__': parts = parts[:-1]
    if parts: mods['.'.join(parts)] = p
def resolve(name):
    while name:
        if name in mods: return name
        name = name.rpartition('.')[0]
deps = {}
for name, p in mods.items():
    try: tree = ast.parse(p.read_text(encoding='utf-8'))
    except (SyntaxError, UnicodeDecodeError): continue
    pkg = name if p.name == '__init__.py' else name.rpartition('.')[0]
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import): out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            base = n.module or ''
            if n.level:
                up = pkg.split('.') if pkg else []
                up = up[:len(up) - n.level + 1]
                base = '.'.join(up + ([n.module] if n.module else []))
            out.add(base)
            out |= {base + '.' + a.name for a in n.names if base}
    deps[name] = {r for r in map(resolve, out) if r and r != name}
def find(node, path):
    for nxt in sorted(deps.get(node, ())):
        if nxt == path[0] and path[0] == min(path): print(' -> '.join(path + [nxt]))
        elif nxt not in path and len(path) < 5: find(nxt, path + [nxt])
for m in sorted(deps): find(m, [m])
EOF
```

Severidad: import circular confirmado o regla de negocio calculada en template = GRAVE;
escrituras ORM masivas en views o utils creciendo = MEDIA.

### 2.5 Regresión viva — todo bug arreglado conserva su test

Doctrina: el test de un bug es de REGRESIÓN permanente, jamás se borra. Por cada unidad
tipo `bug` en `docs/05-trabajo/archivo/`, el test citado en su spec/hallazgos debe existir
HOY en la suite. **Desde la raíz del workspace** (donde están `docs/` y `main/`):

```bash
for u in docs/05-trabajo/archivo/*/; do
  grep -q '^tipo: bug' "$u/especificacion.md" 2>/dev/null || continue
  tests=$(grep -rhoE 'test_[a-zA-Z0-9_]+' "$u"/especificacion.md "$u"/hallazgos.md 2>/dev/null | sort -u)
  [ -z "$tests" ] && echo "VIOLACION $u: unidad bug sin test citado" && continue
  for t in $tests; do
    grep -rql --include='*.py' "def $t" main/ >/dev/null 2>&1 \
      && echo "OK    $u -> $t vivo" \
      || echo "VIOLACION $u -> $t NO existe en la suite"
  done
done
```

Toda línea `VIOLACION` = hallazgo **GRAVE** (un bug sin test vivo puede volver en
silencio). Si no hay unidades bug archivadas, el check reporta CUMPLE (vacío) y se dice
explícitamente en el informe.

### 2.6 Limpieza — el repo se mantiene limpio ANTES de llegar a la tarea

Ficheros muertos — módulos que nadie importa ni referencia (imprime CANDIDATOS; verificar
cada uno antes de reportar: cron, README, `Procfile`, docs de deploy):

```bash
python3 - <<'EOF'
import ast, pathlib
EXCL = {'venv', '.venv', 'migrations', 'node_modules', '.git', 'static', 'media'}
mods, imported = {}, set()
for p in pathlib.Path('.').rglob('*.py'):
    if EXCL & set(p.parts): continue
    parts = p.with_suffix('').parts
    if parts[-1] == '__init__': continue
    mods['.'.join(parts)] = p
for p in pathlib.Path('.').rglob('*.py'):
    if EXCL & set(p.parts): continue
    try: tree = ast.parse(p.read_text(encoding='utf-8'))
    except (SyntaxError, UnicodeDecodeError): continue
    pkg = '.'.join(p.parts[:-1])
    for n in ast.walk(tree):
        if isinstance(n, ast.Import): imported |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            base = n.module or ''
            if n.level:
                up = pkg.split('.') if pkg else []
                up = up[:len(up) - n.level + 1]
                base = '.'.join(up + ([n.module] if n.module else []))
            imported.add(base)
            imported |= {base + '.' + a.name for a in n.names if base}
textual = ' '.join(f.read_text(errors='ignore')
    for pat in ('*.html', '*.sh', '*.yml', '*.yaml', '*.toml', '*.cfg', '*.ini', '*.txt')
    for f in pathlib.Path('.').rglob(pat) if not EXCL & set(f.parts))
SKIP = {'manage', 'wsgi', 'asgi', 'settings', 'urls', 'admin', 'apps', 'models', 'views',
        'forms', 'serializers', 'signals', 'middleware', 'context_processors', 'conftest', 'setup'}
for name, p in sorted(mods.items()):
    last = name.rsplit('.', 1)[-1]
    if last in SKIP or last.startswith('test') or 'management' in name: continue
    if name not in imported and last not in imported and last not in textual:
        print(p)
EOF
```

Código comentado a bloques y TODOs fósiles:

```bash
# Líneas de código muerto comentado (candidatas; ignorar comentarios explicativos)
grep -rn --include='*.py' -E '^\s*#\s*(def |class |import |from .+ import|if .+:|for .+:|return |[a-zA-Z_]+\([^)]*\)\s*$)' . \
  | grep -vE 'venv|migrations' | head -30

# TODOs por fichero; la fecha de uno concreto: git blame -L <n>,<n> <fichero>
grep -rnc --include='*.py' -E 'TODO|FIXME|XXX|HACK' . 2>/dev/null \
  | grep -v ':0$' | grep -vE 'venv|migrations' | sort -t: -k2 -rn | head
```

Severidad: fichero muerto confirmado o bloque comentado de un modelo/clase entera = MEDIA
(git ya lo recuerda; el fichero no debe); TODOs fósiles (>3 meses por `git blame`) = LEVE
en masa, salvo que el TODO esconda un bug conocido (entonces es un bug sin unidad: MEDIA).

## 3 · Formato del informe

El informe vive en la carpeta de la unidad (contrato de cierre del runbook de auditoría).
Estructura fija:

**1. Un bloque por check (2.1 → 2.6),** cada uno con:
- Veredicto: `CUMPLE` o `HALLAZGO(S)`.
- El output pegado del comando (recortado a lo relevante, nunca omitido).
- Por hallazgo: evidencia `fichero:línea` (en duplicación: AMBAS rutas) y una frase de
  por qué viola la doctrina.

**2. Tabla final de hallazgos:**

| ID | Hallazgo (una frase) | Severidad | Evidencia | Unidad propuesta |
|----|----------------------|-----------|-----------|------------------|
| H1 | Cobro creado en `api/views.py:412` y `billing/tasks.py:88` | GRAVE | ambas rutas | `refactor` unificar cobro |

Severidades: **GRAVE** (duplicación de lógica de negocio, regresión sin test vivo, ciclo
de imports, complejidad desbocada) · **MEDIA** (módulos gordos, lógica fuera de sitio,
ficheros muertos) · **LEVE** (TODOs fósiles, avisos sueltos de lint).

**3. Candidatas a unidad:** por cada GRAVE y MEDIA, tipo propuesto (`refactor` o `bug`) y
alcance en una frase. El padre y el humano deciden cuáles paren unidad; el auditor jamás
las ejecuta.
