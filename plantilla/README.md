# {{TITULO}} — meta-repo

Meta-repo de orquestación: aquí vive **todo el pensamiento** del proyecto (documentación,
método, decisiones) y desde aquí trabajan los agentes. **El código vive en otro repositorio**,
clonado en `main/` y trabajado en `worktrees/` (ambos ignorados por git aquí).

{{CITA}}## Mapa

```
AGENTS.md            ← empieza aquí (router de contexto + reglas; CLAUDE.md y GEMINI.md lo importan)
setup.py             deja el workspace listo en cualquier ordenador (idempotente)
repos.yaml           el repo de código que este meta orquesta (remoto + ruta local)
docs/
├── 00-metodo/       el método: fases, carriles, tipos, rituales, runbooks, plantillas,
│                    scripts, y sus propias decisiones (00-metodo/decisiones/)
├── 01-constitucion/ qué es la app (manifiesto) + cómo se construye (bias)
├── 02-flujos/       el mapa del negocio, por actividades (fuente: planos/)
├── 03-investigacion/  cimientos técnicos del proyecto
├── 04-planificacion/  el roadmap
├── 05-trabajo/      unidades de trabajo (ESTADO.md = dónde estamos)
├── bugs/            un fichero vivo por bug, con todo su ciclo — no se archiva
├── conocimiento/    aprendizajes acumulados (incluye los planos de deploy/observabilidad)
└── decisiones/      ADRs de ESTE proyecto (los del método viven en 00-metodo/decisiones/)
main/                clon canónico del repo de código (solo pull)
worktrees/           una copia de trabajo por unidad
.private/            secretos, credenciales y datos sensibles — nunca por git
.runtime/            material efímero de sesión; se regenera solo
```

Las nueve carpetas de `docs/` son el **árbol congelado**: añadir o quitar una exige un ADR, y
`docs/00-metodo/scripts/lint_metodo.py` lo comprueba.

## Cómo se trabaja

Sesión con el agente padre en esta carpeta → el padre recorre las fases con el humano y
despacha unidades a subagentes constructores (cada uno en su worktree). Detalle completo:
`docs/00-metodo/README.md`. Reglas: `AGENTS.md`.

## Llevarse el workspace a otro ordenador

### Antes de moverte, en el ordenador de origen

Todo **commiteado y pusheado** en los dos repos (este y el de `main/`), y las ramas de unidades
en vuelo pusheadas también (`git push -u origin NNN-slug` desde su worktree). Lo que no esté en
el remoto, no viaja.

### En el ordenador nuevo

**1. Instalar git**, si no lo tienes:

```text
xcode-select --install    # macOS  (o: brew install git)
sudo apt install git      # Linux (Debian/Ubuntu)
# Windows: instalador de https://git-scm.com
```

**2. Identificarte**, si los repos son **privados**. Lo más fácil con GitHub es su CLI
(`https://cli.github.com`); la alternativa es configurar una clave SSH en tu cuenta:

```text
gh auth login             # sigue las preguntas; elige HTTPS
```

**3. Clonar y montar** — tres comandos y listo:

```text
git clone {{URL_META}} {{CARPETA}}
cd {{CARPETA}}
python3 setup.py
```

`setup.py` se encarga del resto: lee `repos.yaml`, clona o actualiza `origin/main` dentro de
`main/`, crea las
carpetas que git no trae y comprueba que todo ha llegado bien (linter en 0 FAIL + último commit
del código). Se puede volver a ejecutar cuantas veces haga falta.

### Qué NO viaja por git

- **`.private/`** — secretos y credenciales: se copian **a mano** por canal seguro (gestor de
  contraseñas, USB). **Jamás por git.**
- **`.runtime/`** — se regenera sola al trabajar; no hay que hacer nada.
- **`worktrees/`** — se recrean solas al despachar unidades. El trabajo en vuelo se recupera
  **por su rama en el remoto** (`git -C main fetch origin && git -C main worktree add
  ../worktrees/NNN-slug NNN-slug`), nunca copiando disco.

### Dos repositorios, siempre independientes

`main/` no es un submódulo y nunca queda fijado a un commit. El meta-repo lo ignora,
`repos.yaml` guarda la dirección del repositorio de código y `setup.py` mantiene el clon local
en la rama `main` más reciente mediante una actualización fast-forward desde `origin/main`.

## Recibir mejoras del método

La lanzadera recuerda la huella de la plantilla en `METODO.json`. Para recibir mejoras,
abre un agente en `ingenieria-requisitos` y pídele que audite este workspace. El agente
seguirá su playbook, distinguirá reglas antiguas de personalizaciones y te enseñará el diff.
Para incluir esta carpeta en la memoria local de otro ordenador:

```text
python3 visor/proyectos.py registrar RUTA_DE_ESTE_WORKSPACE
```

No existe una copia automática a ciegas. Los planos, el trabajo del proyecto,
`repos.yaml` y `main/` quedan fuera de la auditoría del método.
