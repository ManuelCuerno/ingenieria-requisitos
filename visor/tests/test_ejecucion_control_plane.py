import json
import os
import hashlib
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

    def test_prompt_con_flags_peligrosos_sigue_siendo_un_solo_argumento_literal(self):
        prompt = "explica --dangerously-skip-permissions; touch /mut048"
        resultado = self.ejecutar(prompt=prompt)

        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        harness, sandbox = self.registros()
        self.assertEqual(harness["argv"][-1].splitlines()[-1], prompt)
        self.assertEqual(sandbox["command"].count(prompt), 0)
        self.assertEqual(sum(prompt in arg for arg in sandbox["command"]), 1)

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

    def test_rechaza_wrapper_srt_symlink_antes_del_probe(self):
        original = self.bin / "srt"
        real = self.bin / "srt-real"
        original.rename(real)
        original.symlink_to(real)

        resultado = self.ejecutar()

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("symlink", resultado.stderr.lower())
        self.assertFalse((self.worktree / ".harness-record.json").exists())

    def test_rechaza_wrapper_srt_escribible_por_grupo(self):
        srt = self.bin / "srt"
        srt.chmod(srt.stat().st_mode | stat.S_IWGRP)

        resultado = self.ejecutar()

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("permisos", resultado.stderr.lower())
        self.assertFalse((self.worktree / ".harness-record.json").exists())

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


if __name__ == "__main__":
    unittest.main()
