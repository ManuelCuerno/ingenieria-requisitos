import json
import os
import hashlib
import re
import select
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



SOLO_POSIX = unittest.skipIf(
    os.name == "nt",
    "E2E con sandbox POSIX (srt/seatbelt/bwrap): en Windows no existe mecanismo "
    "confiable y lanzar rechaza limpio — eso sí se prueba en "
    "test_rechaza_sandbox_ausente_sin_bypass",
)

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
        self.crear_doble_srt()
        self.fijar_sandbox_de_fixture()
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

    def crear_doble_srt(self):
        self.hacer_ejecutable(
            self.bin / "srt",
            """#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys
args = sys.argv[1:]
settings = pathlib.Path(args[args.index('--settings') + 1])
policy = json.loads(settings.read_text())
command = args[args.index('--') + 1:]
if len(command) >= 3 and command[1] == '-c' and 'CONTROL_PLANE_PROBE' in command[2]:
    paths = json.loads(command[3])
    allowed = policy['filesystem']['allowWrite']
    worktree_writable = any(paths['worktree'].startswith(path.rstrip('/') + '/')
                            for path in allowed)
    branch = subprocess.run(['git', 'branch', '--show-current'], text=True,
                            capture_output=True).stdout.strip()
    evidence = {'outside': False, 'worktree': worktree_writable, 'tmp': True,
                'cwd': os.getcwd(), 'pwd': os.environ.get('PWD'), 'branch': branch}
    for name, path in paths.items():
        if name.startswith('doc'):
            evidence[name] = path in allowed
    print(json.dumps(evidence))
    raise SystemExit(0)
pathlib.Path('.sandbox-record.json').write_text(json.dumps({
    'command': command,
    'policy': policy,
    'cwd': os.getcwd(),
}))
raise SystemExit(subprocess.run(command, env=os.environ.copy()).returncode)
""",
        )

    def fijar_sandbox_de_fixture(self):
        texto = self.launcher.read_text(encoding="utf-8")
        lineas = []
        reemplazada = False
        for linea in texto.splitlines():
            if linea.startswith("SANDBOX_CONFIABLES = "):
                configuracion = {
                    "darwin": (("srt", str((self.bin / "srt").resolve())),),
                    "linux": (("srt", str((self.bin / "srt").resolve())),),
                }
                lineas.append(f"SANDBOX_CONFIABLES = {configuracion!r}")
                reemplazada = True
            elif linea == "EXIGIR_OWNER_SISTEMA = True":
                lineas.append("EXIGIR_OWNER_SISTEMA = False")
            else:
                lineas.append(linea)
        self.assertTrue(reemplazada)
        self.launcher.write_text("\n".join(lineas) + "\n", encoding="utf-8")

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
        harness = json.loads((self.worktree / ".harness-record.json").read_text())
        sandbox = json.loads((self.worktree / ".sandbox-record.json").read_text())
        return harness, sandbox

    @SOLO_POSIX
    def test_claude_arranca_en_worktree_con_entorno_saneado_y_skill_tecnica(self):
        resultado = self.ejecutar(skills=("vue-best-practices",))

        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        harness, sandbox = self.registros()
        self.assertEqual(harness["cwd"], str(self.worktree.resolve()))
        self.assertEqual(harness["pwd"], str(self.worktree.resolve()))
        self.assertEqual(harness["branch"], self.unidad)
        self.assertEqual(harness["tmp_mode"], 0o700)
        self.assertTrue(all(value is None for value in harness["poison"].values()))
        self.assertIn("--safe-mode", harness["argv"])
        self.assertIn("--disable-slash-commands", harness["argv"])
        self.assertIn("--add-dir", harness["argv"])
        self.assertIn(str((self.ws / "docs/05-trabajo/001-demo").resolve()), harness["argv"])
        comando = sandbox["command"]
        self.assertNotIn("/bin/sh", comando)
        self.assertNotIn("-c", comando)
        prompt = harness["argv"][-1]
        self.assertIn("CONTENIDO_TECNICO_PERMITIDO", prompt)
        self.assertNotIn("CONTENIDO_PROCESO_PROHIBIDO", prompt)
        self.assertEqual(sandbox["policy"]["filesystem"]["allowWrite"][0],
                         str(self.worktree.resolve()))
        permitidas = sandbox["policy"]["filesystem"]["allowWrite"]
        self.assertIn(
            str((self.ws / "docs/05-trabajo/001-demo/especificacion.md").resolve()),
            permitidas,
        )
        self.assertIn(
            str((self.ws / "docs/05-trabajo/001-demo/hallazgos.md").resolve()),
            permitidas,
        )
        self.assertNotIn(str((self.ws / "docs/05-trabajo/ESTADO.md").resolve()), permitidas)

    @SOLO_POSIX
    def test_codex_usa_home_efimero_y_no_descubre_plugins_instalados(self):
        resultado = self.ejecutar(harness="codex")

        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        harness, _ = self.registros()
        self.assertNotEqual(harness["home"], str(self.home))
        self.assertEqual(harness["home"], harness["codex_home"])
        self.assertTrue(harness["home"].startswith(harness["tmp"]))
        self.assertIn("--ignore-user-config", harness["argv"])
        self.assertIn("--ignore-rules", harness["argv"])
        self.assertIn("--ephemeral", harness["argv"])
        self.assertNotIn("plugin-de-proceso", " ".join(harness["argv"]))

    @SOLO_POSIX
    def test_prompt_con_flags_peligrosos_sigue_siendo_un_solo_argumento_literal(self):
        prompt = "explica --dangerously-skip-permissions; touch /mut048"
        resultado = self.ejecutar(prompt=prompt)

        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        harness, sandbox = self.registros()
        self.assertEqual(harness["argv"][-1].splitlines()[-1], prompt)
        self.assertEqual(sandbox["command"].count(prompt), 0)
        self.assertEqual(sum(prompt in arg for arg in sandbox["command"]), 1)

    @SOLO_POSIX
    def test_rechaza_skill_de_proceso_aunque_se_solicite(self):
        resultado = self.ejecutar(skills=("using-superpowers",))

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("skill de proceso", resultado.stderr.lower())
        self.assertFalse((self.worktree / ".harness-record.json").exists())

    @SOLO_POSIX
    def test_rechaza_alias_symlink_a_skill_de_proceso(self):
        alias = self.home / ".agents/skills/alias-tecnico"
        alias.symlink_to(self.home / ".agents/skills/using-superpowers",
                         target_is_directory=True)

        resultado = self.ejecutar(skills=("alias-tecnico",))

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("symlink", resultado.stderr.lower())
        self.assertFalse((self.worktree / ".harness-record.json").exists())

    @SOLO_POSIX
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

    @SOLO_POSIX
    def test_rechaza_rama_distinta_antes_de_ejecutar_harness(self):
        self.git("checkout", "-b", "rama-intrusa", cwd=self.worktree)

        resultado = self.ejecutar()

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("rama", resultado.stderr.lower())
        self.assertFalse((self.worktree / ".harness-record.json").exists())

    @SOLO_POSIX
    def test_rechaza_carril_directo_sin_lanzar_otro_llm(self):
        ficha = self.ws / "docs/05-trabajo" / self.unidad / "especificacion.md"
        ficha.write_text(ficha.read_text().replace("carril: normal", "carril: directo"))

        resultado = self.ejecutar()

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("padre", resultado.stderr.lower())
        self.assertFalse((self.worktree / ".harness-record.json").exists())

    @SOLO_POSIX
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

    def test_rechaza_sandbox_ausente_sin_bypass(self):
        (self.bin / "srt").rename(self.bin / "srt-ausente")
        solo_harness = self.base / "solo-harness"
        solo_harness.mkdir()
        shutil.copy2(self.bin / "claude", solo_harness / "claude")
        for programa in ("git", "python3"):
            origen = shutil.which(programa)
            self.assertIsNotNone(origen)
            (solo_harness / programa).symlink_to(origen)
        env = self.env.copy()
        env["PATH"] = str(solo_harness)

        resultado = subprocess.run(
            [sys.executable, str(self.launcher), "lanzar", self.unidad,
             "--harness", "claude", "--prompt", "Haz la tarea"],
            cwd=self.main, env=env, text=True, capture_output=True,
        )

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("sandbox", resultado.stderr.lower())
        self.assertFalse((self.worktree / ".harness-record.json").exists())

    @SOLO_POSIX
    def test_rechaza_wrapper_srt_symlink_antes_del_probe(self):
        original = self.bin / "srt"
        real = self.bin / "srt-real"
        original.rename(real)
        original.symlink_to(real)

        resultado = self.ejecutar()

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("symlink", resultado.stderr.lower())
        self.assertFalse((self.worktree / ".harness-record.json").exists())

    @SOLO_POSIX
    def test_rechaza_wrapper_srt_escribible_por_grupo(self):
        srt = self.bin / "srt"
        srt.chmod(srt.stat().st_mode | stat.S_IWGRP)

        resultado = self.ejecutar()

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("permisos", resultado.stderr.lower())
        self.assertFalse((self.worktree / ".harness-record.json").exists())

    @SOLO_POSIX
    def test_ignora_srt_falso_0755_que_aparece_antes_en_path(self):
        falso_bin = self.base / "falso-bin"
        falso_bin.mkdir()
        marca = self.base / "srt-falso-ejecutado"
        falso = falso_bin / "srt"
        self.hacer_ejecutable(
            falso,
            "#!/usr/bin/env python3\n"
            "from pathlib import Path\n"
            f"Path({str(marca)!r}).write_text('ejecutado')\n",
        )
        falso.chmod(0o755)
        env = self.env.copy()
        env["PATH"] = str(falso_bin) + os.pathsep + env["PATH"]

        resultado = self.ejecutar(env=env)

        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        self.assertFalse(marca.exists())
        recibo = json.loads(next(
            (self.ws / ".runtime/ejecuciones").glob("001-demo-*.json")
        ).read_text(encoding="utf-8"))
        self.assertEqual(
            recibo["sandbox_ejecutable"]["ruta"], str((self.bin / "srt").resolve())
        )

    @SOLO_POSIX
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

    @SOLO_POSIX
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

    @SOLO_POSIX
    def test_revisor_solo_puede_firmar_hallazgos_de_su_unidad(self):
        resultado = self.ejecutar(rol="revisor")

        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        harness, sandbox = self.registros()
        self.assertEqual(sandbox["policy"]["filesystem"]["allowWrite"],
                         [
                             harness["tmp"],
                             str((self.ws / "docs/05-trabajo/001-demo/hallazgos.md").resolve()),
                         ])
        self.assertNotIn(str(self.worktree),
                         sandbox["policy"]["filesystem"]["allowWrite"])

    @SOLO_POSIX
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
        sandbox = recibo["sandbox_ejecutable"]
        self.assertEqual(sandbox["ruta"], str((self.bin / "srt").resolve()))
        self.assertEqual(
            sandbox["sha256"], hashlib.sha256((self.bin / "srt").read_bytes()).hexdigest()
        )
        self.assertEqual(
            [item["nombre"] for item in recibo["checkpoints"]],
            ["lease", "identidad", "sandbox", "harness"],
        )
        self.assertTrue(all(item["estado"] == "ok" for item in recibo["checkpoints"]))
        self.assertIn("RESULTADO", resultado.stdout)

    @SOLO_POSIX
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

        # NEW: el control plane corrige cwd antes de ejecutar el harness.
        nuevo = self.ejecutar()
        self.assertEqual(nuevo.returncode, 0, nuevo.stdout + nuevo.stderr)
        harness, _ = self.registros()
        self.assertEqual(harness["cwd"], str(self.worktree.resolve()))

        # MUTANTE: si alguien vuelve a ejecutar todo desde main, el probe de identidad
        # debe fallar antes de que el harness pueda arrancar.
        (self.worktree / ".harness-record.json").unlink()
        texto = self.launcher.read_text(encoding="utf-8")
        mutado = texto.replace("cwd=str(worktree), env=env", "cwd=str(MAIN), env=env")
        self.assertNotEqual(texto, mutado)
        self.launcher.write_text(mutado, encoding="utf-8")

        resultado_mutante = self.ejecutar()

        self.assertNotEqual(resultado_mutante.returncode, 0)
        self.assertIn("cwd", resultado_mutante.stderr.lower())
        self.assertFalse((self.worktree / ".harness-record.json").exists())


class LanzadorHarnessClaudeDeFabricaTest(ControlPlaneE2ETest):
    """Bug 001-lanzador-harness-claude: el camino claude no funciona de fábrica.

    Cada test reproduce uno de los defectos de la ficha docs/bugs/001-… del
    workspace que reportó la caja negra de campo (12-08-2026). E2E sobre el
    fixture donde el defecto es observable en argv/entorno/política; a nivel de
    módulo (el fichero ORIGINAL, patrón de test_ejecucion_gate_real) donde el
    defecto vive en el perfil seatbelt o en el probe.
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

    def perfil_seatbelt(self, modulo, harness="claude"):
        base = Path(self.temporal.name) / "perfil-seatbelt"
        worktree = base / "worktrees/009-demo"
        gitdir = base / "main/.git/worktrees/009-demo"
        common = base / "main/.git"
        tmp_privado = base / "tmp"
        documento = base / "docs/bugs/009-demo.md"
        for ruta in (worktree, gitdir, common, tmp_privado, documento.parent):
            ruta.mkdir(parents=True, exist_ok=True)
        documento.write_text("# doc\n", encoding="utf-8")
        politica, _ = modulo.perfil_sandbox(
            "seatbelt", "/usr/bin/sandbox-exec", worktree, gitdir, common,
            tmp_privado, "constructor", harness, documentos=(documento,),
        )
        texto = (tmp_privado / "seatbelt.sb").read_text(encoding="utf-8")
        return politica, texto, documento, common

    # --- Defecto 2: el CLI rechaza --mcp-config {} (exige la clave mcpServers)

    @SOLO_POSIX
    def test_mcp_config_declara_mcpservers(self):
        resultado = self.ejecutar()
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        harness, _ = self.registros()
        argv = harness["argv"]
        mcp = json.loads(argv[argv.index("--mcp-config") + 1])
        self.assertIn("mcpServers", mcp, "el CLI de claude rechaza un mcp-config sin la clave mcpServers")

    # --- Defecto 6: dontAsk deniega Write/Edit en headless; debe ser bypassPermissions

    @SOLO_POSIX
    def test_permission_mode_no_es_dontask(self):
        resultado = self.ejecutar()
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        harness, _ = self.registros()
        argv = harness["argv"]
        modo = argv[argv.index("--permission-mode") + 1]
        self.assertEqual(
            modo, "bypassPermissions",
            "dontAsk deniega por defecto en headless; la seguridad real la impone el sandbox de SO",
        )

    # --- Defecto 4: claude debe arrancar con HOME aislado y escribible (como codex)

    @SOLO_POSIX
    def test_claude_usa_home_aislado(self):
        resultado = self.ejecutar()
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        harness, _ = self.registros()
        self.assertNotEqual(
            harness["home"], str(self.home),
            "el HOME real del usuario no es escribible dentro del sandbox: claude necesita un HOME aislado",
        )
        # Comparar solo desigualdad era vacuo (resolve() ya las hacía distintas):
        # lo que aprieta es que el HOME viva DENTRO del tmp privado, como en codex.
        self.assertTrue(
            harness["home"].startswith(harness["tmp"]),
            f"el HOME aislado debe vivir dentro del tmp privado: {harness['home']} vs {harness['tmp']}",
        )

    # --- Defecto 5 (mitad lecturas): el constructor debe poder leer docs/ del meta-repo

    @SOLO_POSIX
    def test_add_dir_incluye_docs_del_workspace(self):
        resultado = self.ejecutar()
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        harness, _ = self.registros()
        argv = harness["argv"]
        directorios = [argv[i + 1] for i, arg in enumerate(argv) if arg == "--add-dir"]
        self.assertIn(
            str((self.ws / "docs").resolve()), directorios,
            "el contrato manda leer bias/flujos/síntesis: docs/ del meta-repo debe ir en --add-dir",
        )

    # --- Defecto 7: sin el almacén común escribible no hay commit/push

    @SOLO_POSIX
    def test_politica_permite_el_almacen_git_comun(self):
        resultado = self.ejecutar()
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        _, sandbox = self.registros()
        permitidas = sandbox["policy"]["filesystem"]["allowWrite"]
        self.assertIn(
            str((self.main / ".git").resolve()), permitidas,
            "objetos y refs viven en main/.git (common): sin él, git commit/push fallan con EPERM",
        )

    # --- Defecto 11: el revisor exige modelo DISTINTO (regla 10); falta --modelo

    @SOLO_POSIX
    def test_lanzar_acepta_modelo_explicito(self):
        argv = self.argumentos()
        argv[argv.index("--rol"):argv.index("--rol")] = ["--modelo", "claude-opus-5"]
        resultado = subprocess.run(
            argv, cwd=self.main, env=self.env, text=True, capture_output=True
        )
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        harness, _ = self.registros()
        registrado = harness["argv"]
        self.assertIn("--model", registrado)
        self.assertEqual(registrado[registrado.index("--model") + 1], "claude-opus-5")

    # --- Defectos 3 y 8: credenciales de suscripción y de GitHub deben heredarse

    def test_heredar_env_incluye_credenciales_de_claude_y_github(self):
        modulo = self.modulo_original()
        for variable in ("CLAUDE_CODE_OAUTH_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
            self.assertIn(
                variable, modulo.HEREDAR_ENV,
                f"sin {variable} el subagente no puede autenticarse dentro del sandbox",
            )

    # --- Defecto 9: un HOME recién creado no tiene credential helper de git

    @SOLO_POSIX
    def test_preparar_claude_home_existe_y_configura_git(self):
        modulo = self.modulo_original()
        self.assertTrue(
            hasattr(modulo, "preparar_claude_home"),
            "falta preparar_claude_home(), simétrica a preparar_codex_home()",
        )
        gh_registro = Path(self.temporal.name) / "gh-setup-git.json"
        self.hacer_ejecutable(
            self.bin / "gh",
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, sys\n"
            f"pathlib.Path({str(gh_registro)!r}).write_text(json.dumps(\n"
            "    {'argv': sys.argv[1:], 'home': os.environ.get('HOME')}))\n",
        )
        tmp_privado = Path(self.temporal.name) / "tmp-claude-home"
        tmp_privado.mkdir()
        (self.home / ".gitconfig").write_text(
            "[user]\n\tname = Tester De Campo\n\temail = tester@example.com\n",
            encoding="utf-8",
        )
        env = {"PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", ""),
               "GH_TOKEN": "gho_token_de_prueba"}
        modulo.preparar_claude_home(env, tmp_privado, self.home)
        self.assertNotEqual(env["HOME"], str(self.home))
        self.assertTrue(Path(env["HOME"]).is_dir())
        self.assertTrue(gh_registro.is_file(), "con GH_TOKEN presente debe correr gh auth setup-git")
        registro = json.loads(gh_registro.read_text())
        self.assertEqual(registro["argv"][:2], ["auth", "setup-git"])
        self.assertEqual(registro["home"], env["HOME"])
        # Sin identidad, git firmaría con un ident autodetectado falso (o moriría en
        # hosts sin FQDN, WSL2 incluido): la identidad del HOME original debe viajar.
        ident = subprocess.run(
            ["git", "config", "--get", "user.name"],
            env={"HOME": env["HOME"], "PATH": env["PATH"]},
            capture_output=True, text=True,
        )
        self.assertEqual(
            ident.stdout.strip(), "Tester De Campo",
            "la identidad de git del usuario debe copiarse al HOME aislado",
        )

    # --- Defecto 1: el perfil seatbelt no declara /dev/null y git muere (exit 128)

    def test_seatbelt_declara_dev_null(self):
        modulo = self.modulo_original()
        _, texto, _, _ = self.perfil_seatbelt(modulo)
        self.assertIn(
            '(literal "/dev/null")', texto,
            "git necesita leer y escribir /dev/null; sin la regla, branch --show-current devuelve vacío",
        )

    # --- Defecto 5 (mitad estado del CLI): la ruta fija /private/tmp/claude-<uid>

    @unittest.skipUnless(
        sys.platform == "darwin",
        "la ruta /private/tmp/claude-<uid> es un contrato del CLI en macOS; en el "
        "resto de plataformas el bloque ni se ejecuta (seatbelt solo existe en darwin)",
    )
    def test_seatbelt_incluye_estado_del_cli_claude(self):
        modulo = self.modulo_original()
        politica, _, _, _ = self.perfil_seatbelt(modulo, harness="claude")
        permitidas = politica["filesystem"]["allowWrite"]
        estado = [ruta for ruta in permitidas if f"/tmp/claude-{os.getuid()}" in ruta]
        self.assertTrue(
            estado,
            f"el CLI guarda estado de sesión en /private/tmp/claude-{os.getuid()}/…: sin esa ruta, EPERM al arrancar",
        )
        self.addCleanup(shutil.rmtree, estado[0], True)
        # Con (deny default), permitir una hoja que no existe no sirve: el padre
        # claude-<uid> no es escribible, así que la hoja se pre-crea fuera del sandbox.
        self.assertTrue(
            Path(estado[0]).is_dir(),
            "la ruta de estado debe pre-crearse fuera del sandbox (su padre no es escribible)",
        )

    # --- Defecto 10: guardado atómico de documentos (temporal hermano + rename)

    def test_seatbelt_permite_guardado_atomico_de_documentos(self):
        modulo = self.modulo_original()
        _, texto, documento, _ = self.perfil_seatbelt(modulo)
        # Mirar solo que exista "(regex" dejó pasar una regla inerte (revisión ronda 1):
        # aquí se comprueba la SEMÁNTICA — el patrón debe casar con el temporal hermano
        # y no con un fichero sin relación del mismo directorio.
        patrones = [p.replace('\\"', '"')
                    for p in re.findall(r'\(regex #"([^"]+)"\)', texto)]
        self.assertTrue(patrones, "falta la regla de hermanos por documento en el perfil")
        hermano = str(documento) + ".tmp1234"
        ajeno = str(documento.parent / "otro-fichero.md")
        self.assertTrue(
            any(re.fullmatch(patron, hermano) for patron in patrones),
            f"la regla debe CASAR con el temporal hermano del guardado atómico: {patrones}",
        )
        self.assertFalse(
            any(re.fullmatch(patron, ajeno) for patron in patrones),
            "la regla no debe abrir el directorio a ficheros sin relación",
        )

    @SOLO_POSIX
    def test_codex_no_recibe_lecturas_como_escribibles(self):
        resultado = self.ejecutar(harness="codex")
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        harness, _ = self.registros()
        argv = harness["argv"]
        directorios = [argv[i + 1] for i, arg in enumerate(argv) if arg == "--add-dir"]
        # En codex --add-dir significa "directorio ESCRIBIBLE adicional" (su --help):
        # las lecturas de docs/ son un asunto exclusivo del harness claude.
        self.assertNotIn(
            str((self.ws / "docs").resolve()), directorios,
            "docs/ entero no debe declararse escribible en la capa codex",
        )

    def test_probe_ejercita_el_guardado_atomico(self):
        modulo = self.modulo_original()
        self.assertNotIn(
            ".open('a')", modulo.PROBE,
            "abrir en modo append pasa con el permiso viejo y no detecta el hueco",
        )
        self.assertIn(
            "with_name(", modulo.PROBE,
            "el probe debe crear y borrar un temporal hermano del documento, el patrón real de guardado",
        )


class RevisorEnCarrilDirectoTest(ControlPlaneE2ETest):
    """Bug 002-revisor-carril-directo: el revisor fresco debe poder lanzarse por el
    control plane en carril directo/exprés (ADR-022, AGENTS.md regla 1); solo el
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

    @SOLO_POSIX
    def test_revisor_se_lanza_en_carril_directo(self):
        worktree = self.crear_unidad_directo()
        resultado = self.ejecutar(rol="revisor", unidad="002-demo")
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        harness = json.loads((worktree / ".harness-record.json").read_text())
        self.assertEqual(harness["branch"], "002-demo")

    @SOLO_POSIX
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
