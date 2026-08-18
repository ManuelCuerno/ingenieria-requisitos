"""Unidad 029: lint_ci.py y lint_deploy.py dejan de fallar eternamente por un contrato de
CI que el repo nunca tuvo (`scripts/ci/` + workflows del método). Ausente → WARN con deuda
nombrada, exit 0 (R1, R5). Parcial (empezado y a medias) → FAIL como siempre (R2). Completo
→ ni un cambio de comportamiento (R3). `--require-e2e`/`--require-control-plane` siguen
exigiendo su pieza aunque el contrato general no exista (R6). `lint_deploy.py` no duplica la
detección: delega en `lint_ci.py` como subproceso, así que su veredicto es coherente por
construcción (R4).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
LINT_CI = RAIZ / "plantilla" / "docs" / "00-metodo" / "scripts" / "lint_ci.py"
LINT_DEPLOY = RAIZ / "plantilla" / "docs" / "00-metodo" / "scripts" / "lint_deploy.py"
MARCADOR_DEUDA = "DEUDA-CI"


class RepoJugueteTest(unittest.TestCase):
    """Repos de juguete contra `lint_ci.py` directamente: vacío, parcial, completo."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lint-ci-deploy-")
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        (self.repo / "README.md").write_text("# Demo\n", encoding="utf-8")
        (self.repo / "app.py").write_text("print('demo')\n", encoding="utf-8")

    def crear_script(self, nombre, contenido="#!/bin/sh\nset -eu\nprintf 'OK\\n'\n"):
        ruta = self.repo / "scripts" / "ci" / nombre
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(contenido, encoding="utf-8")
        ruta.chmod(ruta.stat().st_mode | 0o111)

    def crear_contrato_completo(self):
        sha = "a" * 40
        for nombre in ("full-suite", "lint", "security"):
            self.crear_script(nombre)
        (self.repo / "AGENTS.md").write_text(
            "# AGENTS.md\n\n- Suite: `scripts/ci/full-suite`\n"
            "- Lint: `scripts/ci/lint`\n- Seguridad: `scripts/ci/security`\n",
            encoding="utf-8",
        )
        workflows = self.repo / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "tests.yml").write_text(
            "name: tests\non:\n  pull_request:\n"
            "jobs:\n  tests:\n    runs-on: ubuntu-latest\n    steps:\n"
            f"      - uses: actions/checkout@{sha}\n"
            "      - run: scripts/ci/full-suite\n",
            encoding="utf-8",
        )
        (workflows / "quality-security.yml").write_text(
            "name: quality-security\non:\n  pull_request:\n  push:\n    branches: [main]\n"
            "  schedule:\n    - cron: '17 4 * * 1'\n"
            "jobs:\n  lint:\n    runs-on: ubuntu-latest\n    steps:\n"
            f"      - uses: actions/checkout@{sha}\n      - run: scripts/ci/lint\n"
            "  security:\n    runs-on: ubuntu-latest\n    steps:\n"
            f"      - uses: actions/checkout@{sha}\n      - run: scripts/ci/security\n"
            "  quality-security:\n    runs-on: ubuntu-latest\n    needs: [lint, security]\n"
            "    steps:\n      - run: |\n"
            "          test \"${{ needs.lint.result }}\" = success\n"
            "          test \"${{ needs.security.result }}\" = success\n",
            encoding="utf-8",
        )
        (self.repo / ".github" / "dependabot.yml").write_text(
            "version: 2\nupdates:\n  - package-ecosystem: pip\n"
            "    directory: /\n    schedule:\n      interval: weekly\n",
            encoding="utf-8",
        )

    def ejecutar(self, *opciones):
        return subprocess.run(
            [sys.executable, str(LINT_CI), "--repo", str(self.repo), *opciones],
            text=True, encoding="utf-8", errors="replace", capture_output=True,
        )

    # R1 + R5: repo vacío de contrato → WARN con deuda nombrada, exit 0.
    def test_repo_vacio_de_contrato_avisa_con_deuda_nombrada_y_exit_0(self):
        resultado = self.ejecutar()
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        self.assertIn(MARCADOR_DEUDA, resultado.stdout)
        self.assertIn("WARN", resultado.stdout)

    # R5: el WARN nombra los checks alternativos que sí declara el AGENTS.md del repo.
    def test_deuda_nombra_los_checks_alternativos_del_agents_md(self):
        (self.repo / "AGENTS.md").write_text(
            "# AGENTS.md\n\n- Tests: `make test`\n", encoding="utf-8"
        )
        resultado = self.ejecutar()
        self.assertEqual(resultado.returncode, 0)
        self.assertIn("make test", resultado.stdout)

    # R2: contrato PARCIAL (el directorio existe, falta una pieza) sigue siendo FAIL.
    def test_contrato_parcial_sigue_siendo_fail(self):
        self.crear_script("lint")
        resultado = self.ejecutar()
        self.assertEqual(resultado.returncode, 1)
        self.assertIn("FAIL", resultado.stdout)
        self.assertNotIn(MARCADOR_DEUDA, resultado.stdout)

    # R2 (variante): solo un workflow presente, sin `scripts/ci/`, también cuenta como
    # contrato empezado (parcial), no ausente.
    def test_solo_un_workflow_presente_tambien_es_parcial_no_ausente(self):
        (self.repo / ".github" / "workflows").mkdir(parents=True)
        (self.repo / ".github" / "workflows" / "tests.yml").write_text(
            "name: tests\n", encoding="utf-8"
        )
        resultado = self.ejecutar()
        self.assertEqual(resultado.returncode, 1)
        self.assertNotIn(MARCADOR_DEUDA, resultado.stdout)

    # R3: contrato COMPLETO, ni un cambio de comportamiento.
    def test_contrato_completo_sigue_en_verde(self):
        self.crear_contrato_completo()
        resultado = self.ejecutar()
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        self.assertNotIn(MARCADOR_DEUDA, resultado.stdout)
        self.assertIn("OK", resultado.stdout)

    # R6: --require-e2e exige su pieza aunque el contrato general no exista — sin WARN.
    def test_require_e2e_exige_su_pieza_pese_a_contrato_ausente(self):
        resultado = self.ejecutar("--require-e2e")
        self.assertEqual(resultado.returncode, 1)
        self.assertNotIn(MARCADOR_DEUDA, resultado.stdout)
        self.assertIn("scripts/ci/e2e", resultado.stdout)

    # R6: --require-control-plane igual, sin degradar a WARN (el resto del contrato base
    # sigue exigido primero, así que el detalle es el mismo FAIL de siempre).
    def test_require_control_plane_exige_su_pieza_pese_a_contrato_ausente(self):
        resultado = self.ejecutar("--require-control-plane")
        self.assertEqual(resultado.returncode, 1)
        self.assertNotIn(MARCADOR_DEUDA, resultado.stdout)

        self.crear_contrato_completo()
        resultado = self.ejecutar("--require-control-plane")
        self.assertEqual(resultado.returncode, 1)
        self.assertIn("control-plane.json", resultado.stdout)


class GateDeployJugueteTest(unittest.TestCase):
    """R4: el gate de deploy, contra el mismo repo de juguete, con veredicto coherente."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lint-deploy-029-")
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name)
        scripts = self.ws / "docs" / "00-metodo" / "scripts"
        scripts.mkdir(parents=True)
        origen = RAIZ / "plantilla" / "docs" / "00-metodo" / "scripts"
        for nombre in ("lint_deploy.py", "lint_ci.py", "control_plane.py",
                       "repo_config.py", "workspace_paths.py"):
            (scripts / nombre).write_bytes((origen / nombre).read_bytes())
        (self.ws / "docs" / "conocimiento").mkdir(parents=True)
        (self.ws / "docs" / "conocimiento" / "plano-deploy.md").write_text(
            "# Plano de deploy\n\n| Clave | Valor |\n|---|---|\n"
            "| etapa | local |\n| camino | scripts/deploy |\n"
            "| vuelta_atras | git revert HEAD |\n| datos | SIN DATOS |\n"
            "| vigilancia | logs locales |\n",
            encoding="utf-8",
        )
        self.main = self.ws / "main"
        self.main.mkdir()
        self.git_env = os.environ.copy()
        self.git_env.update({
            "GIT_AUTHOR_NAME": "Pruebas CI", "GIT_AUTHOR_EMAIL": "pruebas@example.invalid",
            "GIT_COMMITTER_NAME": "Pruebas CI", "GIT_COMMITTER_EMAIL": "pruebas@example.invalid",
        })
        self.git("init", "-b", "main")
        (self.main / "README.md").write_text("# Demo\n", encoding="utf-8")
        (self.main / "app.py").write_text("print('demo')\n", encoding="utf-8")

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.main), *args], check=True,
                       capture_output=True, env=self.git_env)

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "-m", "estado del repo de juguete")

    def ejecutar_deploy(self):
        return subprocess.run(
            [sys.executable, str(self.ws / "docs/00-metodo/scripts/lint_deploy.py")],
            cwd=self.ws, text=True, encoding="utf-8", errors="replace",
            capture_output=True, env=self.git_env,
        )

    # Sin scripts/ci/ en absoluto: lint_ci.py degradaría a WARN, pero deploy sigue en FAIL
    # por su propia razón —no hay suite/security ejecutable antes de desplegar—, no por un
    # "contrato incompleto" duplicado. Coherente: ambos linters distinguen la falta real.
    def test_deploy_sin_contrato_falla_por_falta_de_suite_no_por_contrato_incompleto(self):
        self.commit()
        resultado = self.ejecutar_deploy()
        self.assertEqual(resultado.returncode, 1)
        self.assertIn("suite completa ejecutable", resultado.stdout)
        self.assertNotIn("contrato CI incompleto", resultado.stdout)

    # Contrato PARCIAL con las piezas mínimas del gate presentes (full-suite y security)
    # pero falta el resto (lint, workflows, dependabot): mismo veredicto FAIL en ambos, vía
    # el mismo subproceso de lint_ci.py — sin tercera copia divergente (R4).
    def test_deploy_con_contrato_parcial_falla_por_el_mismo_veredicto_de_lint_ci(self):
        for nombre in ("full-suite", "security"):
            ruta = self.main / "scripts" / "ci" / nombre
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text("#!/bin/sh\nset -eu\nprintf 'OK\\n'\n", encoding="utf-8")
            ruta.chmod(ruta.stat().st_mode | 0o111)
        self.commit()
        resultado = self.ejecutar_deploy()
        self.assertEqual(resultado.returncode, 1)
        self.assertIn("contrato CI incompleto", resultado.stdout)


if __name__ == "__main__":
    unittest.main()
