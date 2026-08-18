"""Unidad 018: `push: usuario` — el método nunca escribe en el remoto por su cuenta.

Diseño: investigación 007 (`docs/05-trabajo/archivo/007-metodo-sin-tocar-remoto/hallazgos.md`),
tabla R2, puntos 3-6. Los puntos de LECTURA (fetch/clone/pull) y el hook `pre-push` NO cambian
y esta suite no los toca.
"""

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ / "plantilla/docs/00-metodo/scripts"
RUNBOOKS = RAIZ / "plantilla/docs/00-metodo/runbooks"
BOOTSTRAP = RAIZ / "visor/bootstrap.py"

# Los 8 runbooks de tipo con el paso "commit, push y PR" del constructor (007, R2 punto 3).
RUNBOOKS_DE_TIPO = ("feature", "bug", "directo", "migracion", "refactor", "hotfix",
                    "expres", "documentacion")


def cargar(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = modulo
    spec.loader.exec_module(modulo)
    return modulo


class ModoPushEnRepoConfigTest(unittest.TestCase):
    """R4: `repo_config.py` expone la clave con el mismo patrón que `remoto`/`rama_principal`."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="modo-push-")
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name)
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(sys.path.remove, str(SCRIPTS))
        self.repo_config = cargar("repo_config", SCRIPTS / "repo_config.py")

    def escribir(self, texto):
        (self.ws / "repos.yaml").write_text(texto, encoding="utf-8")

    def test_ausente_es_agente(self):
        # R3: ningún workspace existente migra — sin la clave, todo sigue como hoy.
        self.escribir("codigo:\n  ruta_local: main/\n  rama_principal: main\n")
        self.assertEqual(self.repo_config.modo_push(self.ws), "agente")

    def test_usuario_se_lee(self):
        self.escribir("codigo:\n  ruta_local: main/\n  push: usuario\n")
        self.assertEqual(self.repo_config.modo_push(self.ws), "usuario")

    def test_valor_invalido_falla_nombrando_los_validos(self):
        self.escribir("codigo:\n  ruta_local: main/\n  push: banana\n")
        with self.assertRaises(self.repo_config.RepoConfigError) as capturado:
            self.repo_config.modo_push(self.ws)
        mensaje = str(capturado.exception)
        self.assertIn("push", mensaje)
        self.assertIn("agente", mensaje)
        self.assertIn("usuario", mensaje)

    def test_el_comentario_de_ejemplo_no_activa_el_modo(self):
        # `push:` dentro de un comentario es documentación, no configuración.
        self.escribir("codigo:\n  ruta_local: main/\n  #  push: usuario   # ejemplo\n")
        self.assertEqual(self.repo_config.modo_push(self.ws), "agente")

    def test_repo_code_rechaza_el_valor_invalido(self):
        # El valor inválido no puede pasar desapercibido a los consumidores del fichero.
        self.escribir("codigo:\n  ruta_local: main/\n  push: banana\n")
        with self.assertRaises(self.repo_config.RepoConfigError):
            self.repo_config.repo_code(self.ws)


class BootstrapDocumentaPushTest(unittest.TestCase):
    """R4: el `repos.yaml` generado documenta la clave con sus dos valores."""

    def setUp(self):
        sys.path.insert(0, str(RAIZ / "visor"))
        self.addCleanup(sys.path.remove, str(RAIZ / "visor"))
        self.bootstrap = cargar("bootstrap_018", BOOTSTRAP)

    def test_repos_yaml_generado_documenta_push(self):
        texto = self.bootstrap.generar_repos_yaml("demo", "git@example.com:demo/demo.git")
        self.assertRegex(texto, r"(?m)^\s*push:\s*agente")
        self.assertIn("usuario", texto)

    def test_el_defecto_generado_se_comporta_como_hoy(self):
        texto = self.bootstrap.generar_repos_yaml("demo", "git@example.com:demo/demo.git")
        tmp = tempfile.TemporaryDirectory(prefix="repos-generado-")
        self.addCleanup(tmp.cleanup)
        ws = Path(tmp.name)
        (ws / "repos.yaml").write_text(texto, encoding="utf-8")
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(sys.path.remove, str(SCRIPTS))
        repo_config = cargar("repo_config", SCRIPTS / "repo_config.py")
        self.assertEqual(repo_config.modo_push(ws), "agente")


class RunbooksCondicionalesTest(unittest.TestCase):
    """R1/R2: el texto y el código cuentan lo mismo (grep estructural por runbook)."""

    def test_los_ocho_runbooks_condicionan_el_paso_de_push(self):
        for nombre in RUNBOOKS_DE_TIPO:
            with self.subTest(runbook=nombre):
                texto = (RUNBOOKS / f"{nombre}.md").read_text(encoding="utf-8")
                self.assertIn("`push: usuario`", texto)
                self.assertIn("commit local", texto)
                self.assertIn("gh pr create", texto)
                self.assertIn("hallazgos.md", texto)

    def test_cierre_declara_la_excepcion_del_camino_b(self):
        texto = (RUNBOOKS / "cierre.md").read_text(encoding="utf-8")
        self.assertIn("`push: usuario`", texto)
        self.assertIn("SIEMPRE", texto)
        self.assertIn("git -C main push origin main", texto)


class WorkspaceGitTest(unittest.TestCase):
    """Base común: meta-repo con `main/` clonado de un remoto bare local."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="push-usuario-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.ws = self.base / "workspace"
        (self.ws / "docs/05-trabajo").mkdir(parents=True)
        scripts = self.ws / "docs/00-metodo/scripts"
        scripts.mkdir(parents=True)
        for nombre in ("control_plane.py", "lease.py", "lint_ci.py", "lint_metodo.py",
                       "peticion.py", "repo_config.py", "unidad.py", "workspace_paths.py"):
            shutil.copy2(SCRIPTS / nombre, scripts / nombre)
        self.unidad = scripts / "unidad.py"
        self.linter = scripts / "lint_metodo.py"

        self.remoto = self.base / "remoto.git"
        subprocess.run(["git", "init", "--bare", "-b", "main", str(self.remoto)],
                       check=True, capture_output=True)
        semilla = self.base / "semilla"
        semilla.mkdir()
        self.git(semilla, "init", "-b", "main")
        self.git(semilla, "config", "user.name", "Test")
        self.git(semilla, "config", "user.email", "test@example.com")
        (semilla / "app.py").write_text("print('ok')\n", encoding="utf-8")
        self.git(semilla, "add", "-A")
        self.git(semilla, "commit", "-m", "base")
        self.git(semilla, "remote", "add", "origin", str(self.remoto))
        self.git(semilla, "push", "-u", "origin", "main")

        self.repo = self.ws / "main"
        subprocess.run(["git", "clone", str(self.remoto), str(self.repo)],
                       check=True, capture_output=True)
        self.git(self.repo, "config", "user.name", "Test")
        self.git(self.repo, "config", "user.email", "test@example.com")

    def git(self, repo, *args):
        return subprocess.run(["git", "-C", str(repo), *args], check=True,
                              text=True, capture_output=True).stdout.strip()

    def repos_yaml(self, modo=None):
        texto = ("codigo:\n  nombre: demo\n"
                 f"  remoto: {self.remoto}\n"
                 "  rama_principal: main\n  ruta_local: main/\n")
        if modo:
            texto += f"  push: {modo}\n"
        (self.ws / "repos.yaml").write_text(texto, encoding="utf-8")

    def commit_local_sin_empujar(self):
        (self.repo / "app.py").write_text("print('mas')\n", encoding="utf-8")
        self.git(self.repo, "add", "-A")
        self.git(self.repo, "commit", "-m", "trabajo fusionado en local")

    def sha_remoto(self):
        return self.git(self.remoto, "rev-parse", "main")

    def ejecutar(self, script, *args):
        return subprocess.run([sys.executable, str(script), *args], cwd=self.ws,
                              text=True, encoding="utf-8", errors="replace",
                              capture_output=True)


class AvisoPostCierreTest(WorkspaceGitTest):
    """R2/R3: el aviso de la principal sin empujar (007, R2 punto 6).

    Se invoca la función real del cierre (`unidad.py`), no el comando completo: el ritual
    entero exige revisor, recibo y estados; lo que esta unidad cambia son estas ~10 líneas.
    """

    def cargar_unidad(self):
        scripts = str(self.ws / "docs/00-metodo/scripts")
        sys.path.insert(0, scripts)
        self.addCleanup(sys.path.remove, scripts)
        for nombre in ("unidad", "repo_config", "workspace_paths", "control_plane",
                       "lease", "peticion"):
            sys.modules.pop(nombre, None)
        return cargar("unidad", self.unidad)

    def test_con_push_usuario_es_un_recibo_y_el_remoto_no_avanza(self):
        self.repos_yaml("usuario")
        antes = self.sha_remoto()
        self.commit_local_sin_empujar()
        modulo = self.cargar_unidad()

        salida = self.avisar(modulo)

        self.assertEqual(self.sha_remoto(), antes)
        self.assertIn("push: usuario", salida)
        self.assertIn("git -C main push origin main", salida)
        self.assertNotIn("WARN", salida)
        self.assertNotIn("base vieja", salida)

    def test_sin_la_clave_el_warn_es_identico_al_de_hoy(self):
        self.repos_yaml()
        self.commit_local_sin_empujar()
        modulo = self.cargar_unidad()

        salida = self.avisar(modulo)

        self.assertIn("WARN", salida)
        self.assertIn("base vieja", salida)
        self.assertIn("git -C main push origin main", salida)

    def test_sin_commits_pendientes_no_dice_nada(self):
        self.repos_yaml("usuario")
        modulo = self.cargar_unidad()

        self.assertEqual(self.avisar(modulo).strip(), "")

    def avisar(self, modulo):
        import io
        import contextlib

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            modulo.avisar_principal_sin_empujar(self.repo, "main")
        return buffer.getvalue()


class LintModoPushTest(unittest.TestCase):
    """R5: con el modo activo, los commits sin empujar son estado esperado, no error.

    Sobre un workspace REAL recién bootstrapeado (el único que sale verde entero): si el
    modo convirtiera el linter en rojo perpetuo, el aviso dejaría de leerse.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lint-push-usuario-")
        self.addCleanup(lambda: shutil.rmtree(self.tmp.name, ignore_errors=True))
        self.base = Path(self.tmp.name)
        planos = self.base / "planos"
        (planos / "especificaciones/01-constitution").mkdir(parents=True)
        (planos / "especificaciones/02-flows").mkdir()
        (planos / "planos.json").write_text(
            '{"version": 2, "proyecto": "demo", "titulo": "Demo", '
            '"contrato": {"frase": "Una demostración"}, "actividades": []}',
            encoding="utf-8",
        )
        (planos / "especificaciones/01-constitution/constitution.md").write_text(
            "# Constitución\n", encoding="utf-8"
        )
        self.ws = self.base / "demo-agents"
        entorno = dict(os.environ)
        entorno["INGENIERIA_REQUISITOS_REGISTRO"] = str(self.base / "registro.json")
        creado = subprocess.run(
            [sys.executable, str(BOOTSTRAP), "--planos", str(planos),
             "--destino", str(self.ws)],
            cwd=RAIZ, text=True, capture_output=True, env=entorno,
        )
        self.assertEqual(creado.returncode, 0, creado.stdout + creado.stderr)
        self.repo = self.ws / "main"
        self.remoto = self.base / "remoto.git"
        subprocess.run(["git", "init", "--bare", "-b", "main", str(self.remoto)],
                       check=True, capture_output=True)
        self.git("remote", "add", "origin", str(self.remoto))
        # --no-verify: el hook `pre-push` del método vigila el Camino B y aquí solo estamos
        # montando el estado inicial del fixture. El hook no se toca (fuera de alcance).
        self.git("push", "--no-verify", "-u", "origin", "main")

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)

    def declarar(self, modo):
        repos = self.ws / "repos.yaml"
        texto = repos.read_text(encoding="utf-8")
        if modo is None:
            texto = re.sub(r"(?m)^\s*push:.*\n", "", texto)
        else:
            texto = re.sub(r"(?m)^(\s*push:)\s*\S+", rf"\1 {modo}", texto)
        repos.write_text(texto, encoding="utf-8")

    def commit_local_sin_empujar(self):
        (self.repo / "PENDIENTE.md").write_text("trabajo fusionado en local\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-m", "unidad fusionada en local")

    def lint(self):
        return subprocess.run(
            [sys.executable, str(self.ws / "docs/00-metodo/scripts/lint_metodo.py")],
            cwd=self.ws, text=True, encoding="utf-8", errors="replace", capture_output=True,
        )

    def test_informa_el_conteo_sin_fallar(self):
        self.declarar("usuario")
        self.commit_local_sin_empujar()

        resultado = self.lint()

        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        lineas = [l for l in resultado.stdout.splitlines() if "push: usuario" in l]
        self.assertEqual(len(lineas), 1, resultado.stdout)
        self.assertIn("1 commit", lineas[0])
        self.assertIn("git -C main push origin main", lineas[0])
        self.assertIn("OK", lineas[0])
        self.assertNotIn("FAIL", lineas[0])
        self.assertNotIn("WARN", lineas[0])

    def test_sin_la_clave_no_aparece_el_informativo(self):
        # R3: sin la clave, el linter dice exactamente lo de hoy.
        self.declarar(None)
        self.commit_local_sin_empujar()

        resultado = self.lint()

        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        self.assertNotIn("push: usuario", resultado.stdout)

    def test_valor_invalido_falla_en_claro(self):
        self.declarar("banana")

        resultado = self.lint()

        salida = resultado.stdout + resultado.stderr
        self.assertNotEqual(resultado.returncode, 0, salida)
        self.assertIn("push", salida)
        self.assertIn("agente | usuario", salida)


if __name__ == "__main__":
    unittest.main()
