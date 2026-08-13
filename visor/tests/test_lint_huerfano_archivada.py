"""Bug 003-falso-huerfano-al-cerrar: el linter no debe denunciar como huérfano un
worktree cuya unidad YA fue archivada (el orden real de cmd_cerrar: archivar la ficha
→ correr el linter → borrar el worktree). El chequeo de huérfanos (sección 5) solo
conocía docs/05-trabajo/*, saltándose archivo/, así que en ese instante intermedio
del cierre veía un worktree "sin unidad" y revertía un cierre legítimo."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent.parent / "plantilla/docs/00-metodo/scripts/lint_metodo.py"
DENUNCIA = "worktree huérfano sin unidad"
AVISO_RESTO = "sigue en disco"


class LintHuerfanoArchivadaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lint-huerfano-")
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        (self.raiz / "worktrees/044-mux").mkdir(parents=True)
        (self.raiz / "docs/05-trabajo").mkdir(parents=True)

    def ficha_archivada(self):
        carpeta = self.raiz / "docs/05-trabajo/archivo/044-mux"
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / "especificacion.md").write_text(
            "---\n"
            "unidad: 044-mux\n"
            "tipo: feature\n"
            "carril: normal\n"
            "estado: mergeada\n"
            "aprobado: 2026-08-06\n"
            "ficheros: []\n"
            "peticiones: []\n"
            "actualizado: 2026-08-06\n"
            "---\n\n# 044 · mux\n",
            encoding="utf-8",
        )

    def lint(self):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--raiz", str(self.raiz)],
            text=True, encoding="utf-8", errors="replace", capture_output=True,
        )

    def test_worktree_de_unidad_ya_archivada_no_es_huerfano(self):
        # Ni FAIL (el cierre en curso no debe revertirse) NI silencio total: si el
        # borrado del worktree falló de verdad (proceso vivo, error de git) y el padre
        # avisó y siguió, ese resto debe seguir siendo visible — como WARN, no como OK
        # (revisión ronda 1 del bug: un silencio total lo esconde para siempre).
        self.ficha_archivada()

        resultado = self.lint()
        salida = resultado.stdout + resultado.stderr

        self.assertNotIn(DENUNCIA, salida)
        self.assertIn(AVISO_RESTO, salida)
        self.assertNotIn("worktrees coherentes con unidades", salida)

    def test_worktree_de_unidad_activa_sigue_dando_ok_limpio(self):
        # El camino feliz normal (worktree + unidad en obra, sin archivar) no debe
        # ganar ni un WARN de propina por el arreglo del bug.
        carpeta = self.raiz / "docs/05-trabajo/044-mux"
        carpeta.mkdir(parents=True)
        (carpeta / "especificacion.md").write_text(
            "---\nunidad: 044-mux\ntipo: feature\ncarril: normal\nestado: en_obra\n"
            "aprobado: 2026-08-06\nficheros: []\npeticiones: []\n"
            "actualizado: 2026-08-06\n---\n\n# 044 · mux\n",
            encoding="utf-8",
        )

        resultado = self.lint()
        salida = resultado.stdout + resultado.stderr

        self.assertNotIn(DENUNCIA, salida)
        self.assertNotIn(AVISO_RESTO, salida)
        self.assertIn("worktrees coherentes con unidades", salida)

    def test_worktree_sin_ficha_alguna_sigue_siendo_huerfano(self):
        # Ni en docs/05-trabajo/ ni en archivo/: el caso real de cierre a medias
        # (constructor caído) no debe dejar de detectarse.
        resultado = self.lint()
        salida = resultado.stdout + resultado.stderr

        self.assertIn(DENUNCIA, salida)


if __name__ == "__main__":
    unittest.main()
