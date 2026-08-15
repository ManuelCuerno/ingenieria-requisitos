import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
LAUNCHER = RAIZ / "plantilla/docs/00-metodo/scripts/ejecucion.py"
WORKSPACE_PATHS = RAIZ / "plantilla/docs/00-metodo/scripts/workspace_paths.py"


class ControlPlaneE2ETest(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory(prefix="control-plane-")
        self.addCleanup(self.temporal.cleanup)
        self.base = Path(self.temporal.name)
        self.ws = self.base / "demo-agents"
        self.ws.mkdir()
        scripts = self.ws / "docs/00-metodo/scripts"
        scripts.mkdir(parents=True)
        self.assertTrue(LAUNCHER.is_file(), "falta el launcher canónico ejecucion.py")
        shutil.copy2(LAUNCHER, scripts / "ejecucion.py")
        shutil.copy2(LAUNCHER.with_name("control_plane.py"), scripts / "control_plane.py")
        shutil.copy2(LAUNCHER.with_name("lease.py"), scripts / "lease.py")
        shutil.copy2(WORKSPACE_PATHS, scripts / "workspace_paths.py")
        self.launcher = scripts / "ejecucion.py"

        self.unidad = "001-demo"
        ficha = self.ws / "docs/05-trabajo" / self.unidad / "especificacion.md"
        ficha.parent.mkdir(parents=True)
        ficha.write_text(
            "---\nnumero: 001\ntipo: feature\nestado: en_obra\ncarril: normal\n"
            "ficheros: [app/demo.py]\n---\n"
            "# Demo\n",
            encoding="utf-8",
        )
        (ficha.parent / "hallazgos.md").write_text("# Hallazgos\n", encoding="utf-8")
        (self.ws / ".runtime").mkdir()

        self.main = self.ws / "main"
        self.main.mkdir()
        self.git("init", "-b", "main", cwd=self.main)
        self.git("config", "user.name", "Test", cwd=self.main)
        self.git("config", "user.email", "test@example.com", cwd=self.main)
        (self.main / "README.md").write_text("# demo\n", encoding="utf-8")
        self.git("add", "README.md", cwd=self.main)
        self.git("commit", "-m", "base", cwd=self.main)
        (self.ws / "worktrees").mkdir()
        self.worktree = self.ws / "worktrees" / self.unidad
        self.git(
            "worktree", "add", str(self.worktree), "-b", self.unidad, "main",
            cwd=self.main,
        )

        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.crear_doble_harness("claude")
        self.crear_doble_harness("codex")

        self.home = self.base / "home-real"
        tecnica = self.home / ".agents/skills/vue-best-practices"
        proceso = self.home / ".agents/skills/using-superpowers"
        plugin = self.home / ".codex/plugins/cache/plugin-de-proceso"
        for ruta in (tecnica, proceso, plugin):
            ruta.mkdir(parents=True)
        (tecnica / "SKILL.md").write_text(
            "---\nname: vue-best-practices\n---\nCONTENIDO_TECNICO_PERMITIDO\n",
            encoding="utf-8",
        )
        (proceso / "SKILL.md").write_text(
            "---\nname: using-superpowers\n---\nCONTENIDO_PROCESO_PROHIBIDO\n",
            encoding="utf-8",
        )
        (plugin / "plugin.json").write_text('{"name":"proceso"}\n', encoding="utf-8")
        # HOME "real" de fixture con identidad de git configurada: unidad 012, Claude
        # hereda este HOME tal cual (ya no lo aísla), así que necesita lo que un HOME
        # real ya tendría.
        (self.home / ".gitconfig").write_text(
            "[user]\n\tname = Tester De Campo\n\temail = tester@example.com\n",
            encoding="utf-8",
        )

        self.env = os.environ.copy()
        self.env.update(
            {
                "PATH": str(self.bin) + os.pathsep + self.env.get("PATH", ""),
                "HOME": str(self.home),
                "SHELL": "/bin/fish",
                "SCRATCH": "",
                "BASH_ENV": str(self.base / "bash-env-peligroso"),
                "ENV": str(self.base / "sh-env-peligroso"),
                "ZDOTDIR": str(self.base / "zsh-peligroso"),
                "CDPATH": str(self.main),
                "PYTHONPATH": str(self.base / "python-peligroso"),
                "NODE_OPTIONS": "--require=/tmp/plugin-peligroso.js",
            }
        )

    def git(self, *args, cwd):
        resultado = subprocess.run(
            ["git", *args], cwd=cwd, text=True, capture_output=True
        )
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        return resultado

    def hacer_ejecutable(self, ruta, texto):
        ruta.write_text(texto, encoding="utf-8")
        ruta.chmod(ruta.stat().st_mode | stat.S_IXUSR)

    def crear_doble_harness(self, nombre):
        self.hacer_ejecutable(
            self.bin / nombre,
            """#!/usr/bin/env python3
import json, os, pathlib, stat, subprocess, sys
tmp = pathlib.Path(os.environ['TMPDIR'])
record = {
    'argv': sys.argv[1:],
    'cwd': os.getcwd(),
    'pwd': os.environ.get('PWD'),
    'branch': subprocess.run(['git', 'branch', '--show-current'], text=True,
                             capture_output=True).stdout.strip(),
    'tmp': str(tmp),
    'tmp_mode': stat.S_IMODE(tmp.stat().st_mode),
    'home': os.environ.get('HOME'),
    'codex_home': os.environ.get('CODEX_HOME'),
    'poison': {k: os.environ.get(k) for k in
               ('SCRATCH','BASH_ENV','ENV','ZDOTDIR','CDPATH','PYTHONPATH','NODE_OPTIONS')},
}
pathlib.Path('.harness-record.json').write_text(json.dumps(record))
""",
        )

    def argumentos(self, harness="claude", rol="constructor", skills=(),
                   prompt="Haz la tarea", unidad=None):
        args = [
            sys.executable,
            str(self.launcher),
            "lanzar",
            unidad or self.unidad,
            "--harness",
            harness,
            "--rol",
            rol,
        ]
        for skill in skills:
            args.extend(("--skill-tecnica", skill))
        args.extend(("--prompt", prompt))
        return args

    def ejecutar(self, harness="claude", rol="constructor", skills=(), prompt="Haz la tarea",
                 unidad=None, env=None):
        return subprocess.run(
            self.argumentos(harness, rol, skills, prompt, unidad),
            cwd=self.main, env=env or self.env, text=True, capture_output=True
        )

    def proceso_en_barrera(self, nombre="ejecucion_antes_harness", unidad=None):
        ready_read, ready_write = os.pipe()
        wait_read, wait_write = os.pipe()
        env = self.env.copy()
        prefijo = f"IR_FAILPOINT_{nombre.upper()}"
        env[f"{prefijo}_READY_FD"] = str(ready_write)
        env[f"{prefijo}_WAIT_FD"] = str(wait_read)
        env["IR_SESSION_ID"] = "ejecucion-a"
        proceso = subprocess.Popen(
            self.argumentos(unidad=unidad), cwd=self.main, env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            pass_fds=(ready_write, wait_read),
        )
        os.close(ready_write)
        os.close(wait_read)
        self.addCleanup(lambda: proceso.poll() is None and proceso.kill())
        import select
        legibles, _, _ = select.select([ready_read], [], [], 5)
        self.assertEqual(legibles, [ready_read], "el launcher no alcanzó la barrera")
        self.assertEqual(os.read(ready_read, 1), b"1")
        os.close(ready_read)
        return proceso, wait_write

    def crear_unidad_paralela(self, nombre, recurso):
        ficha = self.ws / "docs/05-trabajo" / nombre / "especificacion.md"
        ficha.parent.mkdir(parents=True)
        ficha.write_text(
            "---\nnumero: 002\ntipo: feature\nestado: en_obra\ncarril: normal\n"
            f"ficheros: [{recurso}]\n---\n# Paralela\n",
            encoding="utf-8",
        )
        (ficha.parent / "hallazgos.md").write_text("# Hallazgos\n", encoding="utf-8")
        destino = self.ws / "worktrees" / nombre
        self.git("worktree", "add", str(destino), "-b", nombre, "main", cwd=self.main)
        return destino

    def registros(self):
        return json.loads((self.worktree / ".harness-record.json").read_text())

    def test_claude_arranca_en_worktree_con_entorno_saneado_y_skill_tecnica(self):
        resultado = self.ejecutar(skills=("vue-best-practices",))

        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        harness = self.registros()
        self.assertEqual(harness["cwd"], str(self.worktree.resolve()))
        self.assertEqual(harness["pwd"], str(self.worktree.resolve()))
        self.assertEqual(harness["branch"], self.unidad)
        self.assertEqual(harness["tmp_mode"], 0o700)
        self.assertTrue(all(value is None for value in harness["poison"].values()))
        self.assertIn("--safe-mode", harness["argv"])
        self.assertIn("--disable-slash-commands", harness["argv"])
        self.assertIn("--add-dir", harness["argv"])
        self.assertIn(str((self.ws / "docs/05-trabajo/001-demo").resolve()), harness["argv"])
        prompt = harness["argv"][-1]
        self.assertIn("CONTENIDO_TECNICO_PERMITIDO", prompt)
        self.assertNotIn("CONTENIDO_PROCESO_PROHIBIDO", prompt)

    def test_codex_usa_home_efimero_y_no_descubre_plugins_instalados(self):
        resultado = self.ejecutar(harness="codex")

        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        harness = self.registros()
        self.assertNotEqual(harness["home"], str(self.home))
        self.assertEqual(harness["home"], harness["codex_home"])
        self.assertTrue(harness["home"].startswith(harness["tmp"]))
        self.assertIn("--ignore-user-config", harness["argv"])
        self.assertIn("--ignore-rules", harness["argv"])
        self.assertIn("--ephemeral", harness["argv"])
        self.assertNotIn("plugin-de-proceso", " ".join(harness["argv"]))

    def test_prompt_con_flags_peligrosos_sigue_siendo_un_solo_argumento_literal(self):
        # Unidad 012: sin sandbox de SO de por medio, la garantía la da por completo
        # que ejecucion.py invoque argv como LISTA (subprocess.run, nunca shell=True):
        # esto se verifica en el argv que el propio harness recibió, no en un wrapper.
        prompt = "explica --dangerously-skip-permissions; touch /mut048"
        resultado = self.ejecutar(prompt=prompt)

        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        harness = self.registros()
        self.assertEqual(harness["argv"][-1].splitlines()[-1], prompt)
        self.assertNotIn("/bin/sh", harness["argv"])
        self.assertNotIn("-c", harness["argv"])
        self.assertEqual(sum(prompt in arg for arg in harness["argv"]), 1)

    def test_rechaza_skill_de_proceso_aunque_se_solicite(self):
        resultado = self.ejecutar(skills=("using-superpowers",))

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("skill de proceso", resultado.stderr.lower())
        self.assertFalse((self.worktree / ".harness-record.json").exists())

    def test_rechaza_alias_symlink_a_skill_de_proceso(self):
        alias = self.home / ".agents/skills/alias-tecnico"
        alias.symlink_to(self.home / ".agents/skills/using-superpowers",
                         target_is_directory=True)

        resultado = self.ejecutar(skills=("alias-tecnico",))

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("symlink", resultado.stderr.lower())
        self.assertFalse((self.worktree / ".harness-record.json").exists())

    def test_rechaza_alias_cuyo_frontmatter_declara_skill_de_proceso(self):
        alias = self.home / ".agents/skills/alias-real"
        alias.mkdir()
        (alias / "SKILL.md").write_text(
            "---\nname: using-superpowers\n---\nCONTENIDO_PROCESO_PROHIBIDO\n",
            encoding="utf-8",
        )

        resultado = self.ejecutar(skills=("alias-real",))

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("proceso", resultado.stderr.lower())
        self.assertFalse((self.worktree / ".harness-record.json").exists())

    def test_rechaza_rama_distinta_antes_de_ejecutar_harness(self):
        self.git("checkout", "-b", "rama-intrusa", cwd=self.worktree)

        resultado = self.ejecutar()

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("rama", resultado.stderr.lower())
        self.assertFalse((self.worktree / ".harness-record.json").exists())

    def test_rechaza_carril_directo_sin_lanzar_otro_llm(self):
        ficha = self.ws / "docs/05-trabajo" / self.unidad / "especificacion.md"
        ficha.write_text(ficha.read_text().replace("carril: normal", "carril: directo"))

        resultado = self.ejecutar()

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("padre", resultado.stderr.lower())
        self.assertFalse((self.worktree / ".harness-record.json").exists())

    def test_rechaza_hallazgos_symlink_antes_de_lanzar_harness(self):
        hallazgos = self.ws / "docs/05-trabajo" / self.unidad / "hallazgos.md"
        exterior = self.ws / ".hallazgos-exterior.md"
        contenido = hallazgos.read_bytes()
        exterior.write_bytes(contenido)
        hallazgos.unlink()
        hallazgos.symlink_to(exterior)

        resultado = self.ejecutar()

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("symlink", resultado.stderr.lower())
        self.assertEqual(exterior.read_bytes(), contenido)
        self.assertFalse((self.worktree / ".harness-record.json").exists())

    def test_dos_launchers_de_la_misma_unidad_no_solapan(self):
        primero, gate = self.proceso_en_barrera()
        segundo = self.ejecutar(env={**self.env, "IR_SESSION_ID": "ejecucion-b"})

        self.assertNotEqual(segundo.returncode, 0)
        self.assertIn("ocupado", segundo.stderr.lower())
        os.write(gate, b"1")
        os.close(gate)
        salida, error = primero.communicate(timeout=10)
        self.assertEqual(primero.returncode, 0, salida + error)
        recibos = list((self.ws / ".runtime/ejecuciones").glob("001-demo-*.json"))
        self.assertEqual(len(recibos), 1)

    def test_dos_unidades_con_el_mismo_recurso_no_solapan(self):
        segunda = "002-paralela"
        self.crear_unidad_paralela(segunda, "app/demo.py")
        primero, gate = self.proceso_en_barrera()

        resultado = self.ejecutar(
            unidad=segunda, env={**self.env, "IR_SESSION_ID": "ejecucion-b"}
        )

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("resource:app/demo.py", resultado.stderr)
        os.write(gate, b"1")
        os.close(gate)
        salida, error = primero.communicate(timeout=10)
        self.assertEqual(primero.returncode, 0, salida + error)
        self.assertFalse(
            (self.ws / "worktrees" / segunda / ".harness-record.json").exists()
        )

    def test_publica_resultado_con_checkpoints_verificables(self):
        resultado = self.ejecutar()

        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        recibos = list((self.ws / ".runtime/ejecuciones").glob("001-demo-*.json"))
        self.assertEqual(len(recibos), 1)
        recibo = json.loads(recibos[0].read_text(encoding="utf-8"))
        self.assertEqual(recibo["schema"], "ejecucion/v1")
        self.assertEqual(recibo["unidad"], self.unidad)
        self.assertEqual(recibo["cwd"], str(self.worktree.resolve()))
        self.assertEqual(recibo["rama"], self.unidad)
        self.assertEqual(recibo["exit_code"], 0)
        self.assertEqual(
            set(recibo["lease"]["fencing"]),
            {"unit:001-demo", "resource:app/demo.py"},
        )
        self.assertEqual(recibo["git"]["inicial"]["head"], recibo["git"]["final"]["head"])
        self.assertRegex(recibo["git"]["inicial"]["diff_sha256"], r"^[0-9a-f]{64}$")
        self.assertIn("status_porcelain", recibo["git"]["final"])
        # Unidad 012: sin sandbox de SO no hay campo sandbox/sandbox_ejecutable ni
        # checkpoint "sandbox" — el recibo pasa directo de "identidad" a "harness".
        self.assertNotIn("sandbox", recibo)
        self.assertNotIn("sandbox_ejecutable", recibo)
        self.assertEqual(
            [item["nombre"] for item in recibo["checkpoints"]],
            ["lease", "identidad", "harness"],
        )
        self.assertTrue(all(item["estado"] == "ok" for item in recibo["checkpoints"]))
        self.assertIn("RESULTADO", resultado.stdout)

    def test_aurora_old_new_y_mutante_de_cwd(self):
        # OLD: un proceso heredado desde main ve el cwd equivocado y una variable vacía
        # convierte `$SCRATCH/mut048` en la ruta raíz observada en Aurora.
        old = subprocess.run(
            [sys.executable, "-c",
             "import json,os; print(json.dumps({'cwd':os.getcwd(), "
             "'target':(os.environ.get('SCRATCH','') + '/mut048')}))"],
            cwd=self.main, env=self.env, text=True, capture_output=True,
        )
        observado_old = json.loads(old.stdout)
        self.assertEqual(observado_old, {"cwd": str(self.main.resolve()), "target": "/mut048"})

        # NEW: el control plane corrige cwd antes de ejecutar el harness — por código,
        # sin sandbox de SO de por medio (unidad 012: esta es la garantía que se
        # mantiene íntegra).
        nuevo = self.ejecutar()
        self.assertEqual(nuevo.returncode, 0, nuevo.stdout + nuevo.stderr)
        harness = self.registros()
        self.assertEqual(harness["cwd"], str(self.worktree.resolve()))

        # Unidad 012 retira el tercer tramo (MUTANTE) de este test: verificaba que un
        # `cwd` de arranque incorrecto fallara en claro, pero esa verificación vivía en
        # el probe DENTRO del sandbox de SO (`verificar_sandbox`), que corría el probe
        # como proceso aparte y comparaba su `os.getcwd()` observado contra el
        # `worktree` esperado — una comprobación independiente del propio valor de la
        # variable `cwd` que se le pasaba a `subprocess.run`. Sin sandbox, esa segunda
        # verificación independiente ya no existe: `resolver_worktree()` sigue siendo
        # la única fuente de verdad, auditada por lectura de código, no por un runtime
        # check redundante. Documentado como hallazgo en docs/05-trabajo/
        # 012-quitar-sandbox-so-lanzador/hallazgos.md — es una pérdida de
        # defensa-en-profundidad real, distinta del riesgo de escritura ya aceptado en
        # el contrato, y candidata a una unidad de seguimiento si se quiere recuperar
        # sin volver al sandbox de SO.


class LanzadorHarnessClaudeDeFabricaTest(ControlPlaneE2ETest):
    """Bug 001-lanzador-harness-claude: el camino claude no funciona de fábrica.

    Cada test reproduce uno de los defectos de la ficha docs/bugs/001-… del
    workspace que reportó la caja negra de campo (12-08-2026). E2E sobre el
    fixture donde el defecto es observable en argv/entorno; a nivel de módulo
    (el fichero ORIGINAL) donde el defecto vive en la preparación del entorno.

    Unidad 012 (15-08-2026) retiró los defectos 1, 5 (mitad estado del CLI) y 10, que
    vivían en el perfil seatbelt y el probe de sandbox — ya no existen, así que sus
    tests (`test_seatbelt_*`, `test_probe_ejercita_el_guardado_atomico`) se retiran
    con ellos. El defecto 4 se invierte: ya NO se aísla el HOME de claude a propósito
    (`test_claude_hereda_home_real` sustituye a `test_claude_usa_home_aislado`).
    """

    def modulo_original(self):
        import importlib.util

        origen = RAIZ / "plantilla/docs/00-metodo/scripts"
        spec = importlib.util.spec_from_file_location(
            "ejecucion_original", origen / "ejecucion.py"
        )
        modulo = importlib.util.module_from_spec(spec)
        anterior = sys.path[:]
        sys.path.insert(0, str(origen))
        try:
            spec.loader.exec_module(modulo)
        finally:
            sys.path[:] = anterior
        return modulo

    # --- Defecto 2: el CLI rechaza --mcp-config {} (exige la clave mcpServers)

    def test_mcp_config_declara_mcpservers(self):
        resultado = self.ejecutar()
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        harness = self.registros()
        argv = harness["argv"]
        mcp = json.loads(argv[argv.index("--mcp-config") + 1])
        self.assertIn("mcpServers", mcp, "el CLI de claude rechaza un mcp-config sin la clave mcpServers")

    # --- Defecto 6: dontAsk deniega Write/Edit en headless; debe ser bypassPermissions

    def test_permission_mode_no_es_dontask(self):
        resultado = self.ejecutar()
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        harness = self.registros()
        argv = harness["argv"]
        modo = argv[argv.index("--permission-mode") + 1]
        self.assertEqual(
            modo, "bypassPermissions",
            "dontAsk deniega Write/Edit/Bash por defecto en headless",
        )

    # --- Defecto 4 (unidad 012, invertido): claude hereda el HOME real, no uno aislado

    def test_claude_hereda_home_real(self):
        resultado = self.ejecutar()
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        harness = self.registros()
        self.assertEqual(
            harness["home"], str(self.home.resolve()),
            "unidad 012: claude ya no recibe un HOME aislado — hereda la sesión real "
            "del usuario (llavero incluido), que es lo que resuelve la autenticación "
            "sin token manual",
        )

    # --- Defecto 5 (mitad lecturas): el constructor debe poder leer docs/ del meta-repo

    def test_add_dir_incluye_docs_del_workspace(self):
        resultado = self.ejecutar()
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        harness = self.registros()
        argv = harness["argv"]
        directorios = [argv[i + 1] for i, arg in enumerate(argv) if arg == "--add-dir"]
        self.assertIn(
            str((self.ws / "docs").resolve()), directorios,
            "el contrato manda leer bias/flujos/síntesis: docs/ del meta-repo debe ir en --add-dir",
        )

    # --- Defecto 11: el revisor exige modelo DISTINTO (regla 10); falta --modelo

    def test_lanzar_acepta_modelo_explicito(self):
        argv = self.argumentos()
        argv[argv.index("--rol"):argv.index("--rol")] = ["--modelo", "claude-opus-5"]
        resultado = subprocess.run(
            argv, cwd=self.main, env=self.env, text=True, capture_output=True
        )
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        harness = self.registros()
        registrado = harness["argv"]
        self.assertIn("--model", registrado)
        self.assertEqual(registrado[registrado.index("--model") + 1], "claude-opus-5")

    # --- Defectos 3 y 8: credenciales de suscripción y de GitHub deben heredarse

    def test_heredar_env_incluye_credenciales_de_claude_y_github(self):
        modulo = self.modulo_original()
        for variable in ("CLAUDE_CODE_OAUTH_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
            self.assertIn(
                variable, modulo.HEREDAR_ENV,
                f"{variable} sigue disponible para CI/hosts sin sesión interactiva "
                "(unidad 012: ya no es la única vía, pero sigue siendo válida)",
            )

    def test_heredar_env_incluye_user_y_logname_para_el_llavero(self):
        # R1: heredar HOME NO basta para que el llavero de macOS sirva la credencial
        # de Claude — verificado en sesión con `claude auth status` real: sin USER/
        # LOGNAME el resultado es loggedIn=false pese a HOME correcto.
        modulo = self.modulo_original()
        for variable in ("USER", "LOGNAME"):
            self.assertIn(variable, modulo.HEREDAR_ENV)

    # --- Defecto 9 (unidad 012: adaptado a HOME real, ya no aislado)

    def test_preparar_claude_home_configura_gh_con_token(self):
        modulo = self.modulo_original()
        self.assertTrue(
            hasattr(modulo, "preparar_claude_home"),
            "falta preparar_claude_home()",
        )
        gh_registro = Path(self.temporal.name) / "gh-setup-git.json"
        self.hacer_ejecutable(
            self.bin / "gh",
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, sys\n"
            f"pathlib.Path({str(gh_registro)!r}).write_text(json.dumps(\n"
            "    {'argv': sys.argv[1:], 'home': os.environ.get('HOME')}))\n",
        )
        env = {
            "HOME": str(self.home),
            "PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", ""),
            "GH_TOKEN": "gho_token_de_prueba",
        }
        modulo.preparar_claude_home(env, self.home)
        self.assertEqual(env["HOME"], str(self.home), "unidad 012: HOME no se aísla")
        self.assertTrue(gh_registro.is_file(), "con GH_TOKEN presente debe correr gh auth setup-git")
        registro = json.loads(gh_registro.read_text())
        self.assertEqual(registro["argv"][:2], ["auth", "setup-git"])
        self.assertEqual(registro["home"], str(self.home))

    def test_preparar_claude_home_para_en_claro_sin_identidad_de_git(self):
        # Caso límite (R1): sin sandbox de SO que dé igual un HOME vacío, un HOME real
        # sin identidad de git configurada debe fallar en claro, no arrastrar el
        # problema hasta que el harness intente comitear a medio trabajo.
        modulo = self.modulo_original()
        home_vacio = Path(self.temporal.name) / "home-sin-git"
        home_vacio.mkdir()
        env = {"HOME": str(home_vacio), "PATH": os.environ.get("PATH", "")}
        with self.assertRaises(modulo.ErrorEjecucion) as contexto:
            modulo.preparar_claude_home(env, home_vacio)
        self.assertIn("user.name", str(contexto.exception))

    def test_codex_no_recibe_lecturas_como_escribibles(self):
        resultado = self.ejecutar(harness="codex")
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        harness = self.registros()
        argv = harness["argv"]
        directorios = [argv[i + 1] for i, arg in enumerate(argv) if arg == "--add-dir"]
        # En codex --add-dir significa "directorio ESCRIBIBLE adicional" (su --help):
        # las lecturas de docs/ son un asunto exclusivo del harness claude.
        self.assertNotIn(
            str((self.ws / "docs").resolve()), directorios,
            "docs/ entero no debe declararse escribible en la capa codex",
        )


class RevisorEnCarrilDirectoTest(ControlPlaneE2ETest):
    """Bug 002-revisor-carril-directo: el revisor fresco debe poder lanzarse por el
    control plane en carril directo/exprés (AGENTS.md regla 1); solo el
    CONSTRUCTOR debe quedar rechazado en esos carriles."""

    def crear_unidad_directo(self, nombre="002-demo"):
        ficha = self.ws / "docs/05-trabajo" / nombre / "especificacion.md"
        ficha.parent.mkdir(parents=True)
        ficha.write_text(
            "---\nnumero: 002\ntipo: feature\nestado: en_obra\ncarril: directo\n"
            "ficheros: [app/demo.py]\n---\n# Demo directo\n",
            encoding="utf-8",
        )
        (ficha.parent / "hallazgos.md").write_text("# Hallazgos\n", encoding="utf-8")
        destino = self.ws / "worktrees" / nombre
        self.git("worktree", "add", str(destino), "-b", nombre, "main", cwd=self.main)
        return destino

    def test_revisor_se_lanza_en_carril_directo(self):
        worktree = self.crear_unidad_directo()
        resultado = self.ejecutar(rol="revisor", unidad="002-demo")
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        harness = json.loads((worktree / ".harness-record.json").read_text())
        self.assertEqual(harness["branch"], "002-demo")

    def test_constructor_sigue_rechazado_en_carril_directo(self):
        self.crear_unidad_directo()
        resultado = self.ejecutar(rol="constructor", unidad="002-demo")
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn(
            "el carril directo lo construye el padre",
            resultado.stdout + resultado.stderr,
        )


if __name__ == "__main__":
    unittest.main()
