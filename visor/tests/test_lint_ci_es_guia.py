"""Unidad 015: el contrato de CI es un aviso, nunca un bloqueo de cierre (ADR-028, que
aplica ADR-026 a este control concreto). Ausencia de CI no pierde trabajo, no pisa
producción, no filtra secretos y no absorbe cambios ajenos: por la propia regla de
ADR-026 nunca debió ser un fail() en `lint_metodo.py`, sección "7b"."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "plantilla/docs/00-metodo/scripts"
DETALLE_INCOMPLETO = "la materialización del CI está incompleta"
DETALLE_SIN_MATERIALIZAR = "CI real aún sin materializar"
DETALLE_SIN_REPO = "no se pudo comprobar el contrato de CI"


class LintCiEsGuiaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lint-ci-guia-")
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name)
        scripts = self.ws / "docs/00-metodo/scripts"
        scripts.mkdir(parents=True)
        for nombre in ("lint_metodo.py", "repo_config.py", "workspace_paths.py",
                       "lint_ci.py", "control_plane.py"):
            shutil.copy2(SCRIPTS / nombre, scripts / nombre)
        (self.ws / "repos.yaml").write_text(
            "ruta_local: main/\nrama_principal: main\n", encoding="utf-8"
        )
        (self.ws / "docs/05-trabajo").mkdir(parents=True)
        self.repo = self.ws / "main"

    def repo_con_codigo_sin_ci(self):
        """Repo de código real (con historia git) pero sin ninguna pieza del contrato CI."""
        self.repo.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.com")
        (self.repo / "app.py").write_text("print('hola')\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-m", "base")

    def declarar_e2e(self):
        carpeta = self.ws / "docs/02-flujos/planos"
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / "planos.json").write_text('{"pruebas_e2e": true}\n', encoding="utf-8")

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)

    def lint(self):
        return subprocess.run(
            [sys.executable, str(self.ws / "docs/00-metodo/scripts/lint_metodo.py")],
            cwd=self.ws, text=True, encoding="utf-8", errors="replace",
            capture_output=True,
        )

    # R1: sin ninguna pieza de CI materializada → aviso, nunca bloqueo.
    def test_repo_sin_ninguna_pieza_de_ci_avisa_y_no_bloquea(self):
        self.repo_con_codigo_sin_ci()

        resultado = self.lint()
        salida = resultado.stdout + resultado.stderr

        self.assertIn(f"WARN {DETALLE_SIN_MATERIALIZAR}", salida)
        self.assertNotIn(f"FAIL {DETALLE_SIN_MATERIALIZAR}", salida)
        self.assertNotIn(f"FAIL {DETALLE_INCOMPLETO}", salida)

    # R2: un plano declara pruebas_e2e y faltan scripts/ci/e2e y provision-e2e → aviso, no bloqueo.
    def test_e2e_declarado_sin_piezas_avisa_y_no_bloquea(self):
        self.repo_con_codigo_sin_ci()
        self.declarar_e2e()

        resultado = self.lint()
        salida = resultado.stdout + resultado.stderr

        self.assertIn(f"WARN {DETALLE_INCOMPLETO}", salida)
        self.assertNotIn(f"FAIL {DETALLE_INCOMPLETO}", salida)
        self.assertIn("lint_ci.py", salida)
        self.assertIn("--require-e2e", salida)

    # R3: con piezas parciales/mal formadas el sistema sigue señalando el detalle, solo
    # baja de FAIL a WARN.
    def test_piezas_parciales_sigue_senalando_el_detalle_como_aviso(self):
        self.repo_con_codigo_sin_ci()
        (self.repo / "scripts/ci").mkdir(parents=True)
        (self.repo / "scripts/ci/lint").write_text("<pega aquí tu lint>\n", encoding="utf-8")

        resultado = self.lint()
        salida = resultado.stdout + resultado.stderr

        self.assertIn(f"WARN {DETALLE_INCOMPLETO}", salida)
        self.assertNotIn(f"FAIL {DETALLE_INCOMPLETO}", salida)
        self.assertIn("para ver el detalle", salida)

    # R4 (caso límite): si lint_ci.py no puede ejecutarse porque el repo de código no
    # existe, avisa y sigue el resto de la ronda de lint, nunca aborta por esto.
    def test_repo_de_codigo_inexistente_avisa_y_sigue_el_resto_del_lint(self):
        # self.repo NO se crea: repos.yaml apunta a main/ y no hay nada ahí.
        resultado = self.lint()
        salida = resultado.stdout + resultado.stderr

        self.assertIn(DETALLE_SIN_REPO, salida)
        self.assertIn("FAIL ·", salida)  # el linter llegó al resumen final, no reventó a medias
        self.assertNotIn("Traceback", salida)


if __name__ == "__main__":
    unittest.main()
