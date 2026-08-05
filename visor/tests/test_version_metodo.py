import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
BOOTSTRAP = RAIZ / "visor/bootstrap.py"
ACTUALIZAR = RAIZ / "visor/actualizar.py"
VERSION = RAIZ / "plantilla/docs/00-metodo/VERSION"


class VersionMetodoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="version-metodo-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.entorno = dict(os.environ)
        self.entorno["INGENIERIA_REQUISITOS_REGISTRO"] = str(
            self.base / "registro-suite.json"
        )
        self.version = VERSION.read_text(encoding="utf-8").strip()

    def ejecutar(self, script, *args):
        return subprocess.run(
            [sys.executable, str(script), *args],
            cwd=RAIZ,
            text=True,
            capture_output=True,
            env=self.entorno,
        )

    def planos_minimos(self):
        proyecto = self.base / "planos"
        (proyecto / "especificaciones/01-constitution").mkdir(parents=True)
        (proyecto / "especificaciones/02-flows").mkdir()
        (proyecto / "planos.json").write_text(
            json.dumps(
                {
                    "version": 2,
                    "proyecto": "demo",
                    "titulo": "Demo",
                    "contrato": {"frase": "Una demostración"},
                    "actividades": [],
                }
            ),
            encoding="utf-8",
        )
        (proyecto / "especificaciones/01-constitution/constitution.md").write_text(
            "# Constitución\n", encoding="utf-8"
        )
        return proyecto

    def workspace_antiguo(self, *, sin_bugs=False):
        """Workspace anterior al versionado: sin METODO.json y sin el método publicado."""
        ws = self.base / ("antiguo-sin-bugs" if sin_bugs else "antiguo")
        carpetas = [
            "00-metodo",
            "01-constitucion",
            "02-flujos",
            "03-investigacion",
            "04-planificacion",
            "05-trabajo/archivo",
            "conocimiento",
            "decisiones",
        ]
        if not sin_bugs:
            carpetas.append("bugs")
        for nombre in carpetas:
            (ws / "docs" / nombre).mkdir(parents=True)
        (ws / "AGENTS.md").write_text(
            "# AGENTS.md — Antiguo (meta-repo)\n", encoding="utf-8"
        )
        (ws / "docs/05-trabajo/ESTADO.md").write_text("# Estado\n", encoding="utf-8")
        if not sin_bugs:
            (ws / "docs/bugs/INDICE.md").write_text("001-antigua\n", encoding="utf-8")
        (ws / "docs/02-flujos/planos").mkdir()
        (ws / "docs/02-flujos/planos/planos.json").write_text(
            '{"version": 2, "titulo": "Antiguo"}\n', encoding="utf-8"
        )
        subprocess.run(["git", "init", "-b", "main"], cwd=ws, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=ws, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=ws, check=True
        )
        subprocess.run(["git", "add", "-A"], cwd=ws, check=True)
        subprocess.run(
            ["git", "commit", "-m", "estado antiguo"],
            cwd=ws,
            check=True,
            capture_output=True,
        )
        return ws

    def test_version_declarada_es_semver(self):
        self.assertRegex(self.version, r"^\d+\.\d+\.\d+$")

    def test_bootstrap_escribe_version_en_metodo_json_y_publica_el_fichero(self):
        destino = self.base / "demo-agents"

        resultado = self.ejecutar(
            BOOTSTRAP, "--planos", str(self.planos_minimos()), "--destino", str(destino)
        )

        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        metodo = json.loads((destino / "METODO.json").read_text(encoding="utf-8"))
        self.assertEqual(metodo["version"], self.version)
        self.assertEqual(
            (destino / "docs/00-metodo/VERSION").read_text(encoding="utf-8").strip(),
            self.version,
        )

    def test_aplicar_muestra_el_salto_de_version_y_la_escribe(self):
        ws = self.workspace_antiguo()

        resultado = self.ejecutar(ACTUALIZAR, "aplicar", str(ws))

        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        self.assertIn("método sin versión", resultado.stdout)
        self.assertIn(self.version, resultado.stdout)
        metodo = json.loads((ws / "METODO.json").read_text(encoding="utf-8"))
        self.assertEqual(metodo["version"], self.version)
        revision = self.ejecutar(ACTUALIZAR, "revisar", str(ws))
        self.assertEqual(revision.returncode, 0, revision.stdout + revision.stderr)
        self.assertIn(f"método {self.version} (al día)", revision.stdout)

    def test_aplicar_repone_el_esqueleto_de_bugs_ausente_y_el_linter_pasa(self):
        ws = self.workspace_antiguo(sin_bugs=True)

        resultado = self.ejecutar(ACTUALIZAR, "aplicar", str(ws))

        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        self.assertIn("docs/bugs", resultado.stdout)
        self.assertTrue((ws / "docs/bugs/.gitkeep").is_file())
        indice = (ws / "docs/bugs/INDICE.md").read_text(encoding="utf-8")
        self.assertIn("# Índice de bugs", indice)
        commiteados = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "HEAD"],
            cwd=ws, text=True, capture_output=True, check=True,
        ).stdout.splitlines()
        self.assertIn("docs/bugs/INDICE.md", commiteados)
        lint = self.ejecutar(ws / "docs/00-metodo/scripts/lint_metodo.py")
        self.assertEqual(lint.returncode, 0, lint.stdout + lint.stderr)

    def test_aplicar_no_repone_esqueleto_sobre_carpeta_existente(self):
        ws = self.workspace_antiguo()

        resultado = self.ejecutar(ACTUALIZAR, "aplicar", str(ws))

        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        # El índice de bugs del workspace tenía contenido propio: Modo D no lo toca.
        self.assertEqual(
            (ws / "docs/bugs/INDICE.md").read_text(encoding="utf-8"), "001-antigua\n"
        )

    def test_aplicar_ignora_pycache_sucio_y_no_lo_commitea(self):
        ws = self.workspace_antiguo()
        pycache = ws / "docs/00-metodo/scripts/__pycache__"
        pycache.mkdir(parents=True)
        pyc = pycache / "repo_config.cpython-311.pyc"
        pyc.write_bytes(b"\x00bytecode")

        resultado = self.ejecutar(ACTUALIZAR, "aplicar", str(ws))

        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        self.assertNotIn("sucio", (resultado.stdout + resultado.stderr).lower())
        self.assertTrue(pyc.is_file())
        commiteados = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "HEAD"],
            cwd=ws, text=True, capture_output=True, check=True,
        ).stdout
        self.assertNotIn("__pycache__", commiteados)
        # El .gitignore repartido ya ignora el bytecode: el árbol queda limpio de verdad.
        estado = subprocess.run(
            ["git", "status", "--porcelain"], cwd=ws, text=True,
            capture_output=True, check=True,
        ).stdout
        self.assertNotIn("__pycache__", estado)


if __name__ == "__main__":
    unittest.main()
