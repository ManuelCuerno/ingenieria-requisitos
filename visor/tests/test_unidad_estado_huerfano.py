"""Bug 003-falso-huerfano-al-cerrar (revisión ronda 1): `unidad.py estado` tenía el
mismo chequeo de huérfanos que `lint_metodo.py` antes del arreglo — sin restar
`docs/05-trabajo/archivo/` — y ambos tools quedaban contradiciéndose sobre el mismo
disco. Importa el módulo ORIGINAL (patrón de test_ejecucion_gate_real.py) y monkeypatch
solo lo imprescindible: las constantes de ruta y las dos llamadas finales que exigen un
repo de código real, ajenas a la sección de coherencia que este test ejercita."""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "plantilla/docs/00-metodo/scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import unidad  # noqa: E402  (el REAL, sin copiar)

DENUNCIA = "worktree sin unidad"
AVISO_RESTO = "sigue en disco"


class EstadoHuerfanoArchivadaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="estado-huerfano-")
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        (self.raiz / "worktrees/044-mux").mkdir(parents=True)
        (self.raiz / "docs/bugs").mkdir(parents=True)

        parcheos = [
            mock.patch.object(unidad, "RAIZ", self.raiz),
            mock.patch.object(unidad, "TRABAJO", self.raiz / "docs/05-trabajo"),
            mock.patch.object(unidad, "ARCHIVO", self.raiz / "docs/05-trabajo/archivo"),
            mock.patch.object(unidad, "BUGS", self.raiz / "docs/bugs"),
            mock.patch.object(unidad, "WORKTREES", self.raiz / "worktrees"),
            mock.patch.object(unidad, "siguiente_nnn", lambda: ("999", {})),
            mock.patch.object(unidad, "repo_codigo", lambda: (self.raiz, "main")),
        ]
        for p in parcheos:
            p.start()
            self.addCleanup(p.stop)

    def ficha_archivada(self):
        carpeta = self.raiz / "docs/05-trabajo/archivo/044-mux"
        carpeta.mkdir(parents=True)
        (carpeta / "especificacion.md").write_text(
            "---\nunidad: 044-mux\ntipo: feature\ncarril: normal\nestado: mergeada\n"
            "aprobado: 2026-08-06\nficheros: []\npeticiones: []\n"
            "actualizado: 2026-08-06\n---\n\n# 044 · mux\n",
            encoding="utf-8",
        )

    def estado(self):
        salida, errores = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(errores):
            codigo = unidad.cmd_estado(None)
        return codigo, salida.getvalue() + errores.getvalue()

    def test_worktree_de_unidad_archivada_no_es_huerfano_en_estado(self):
        self.ficha_archivada()

        codigo, salida = self.estado()

        self.assertEqual(codigo, 0)
        self.assertNotIn(DENUNCIA, salida)
        self.assertIn(AVISO_RESTO, salida)
        self.assertNotIn("worktrees y unidades casan", salida)

    def test_worktree_sin_ficha_alguna_sigue_denunciandose_en_estado(self):
        (self.raiz / "docs/05-trabajo").mkdir(parents=True)

        codigo, salida = self.estado()

        self.assertEqual(codigo, 0)
        self.assertIn(DENUNCIA, salida)


if __name__ == "__main__":
    unittest.main()
