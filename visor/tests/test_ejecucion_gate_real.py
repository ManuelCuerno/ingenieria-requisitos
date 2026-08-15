"""N2: guarda de no-regresión del sandbox de SO retirado (unidad 012).

Este fichero probaba el gate real de identidad del ejecutable de sandbox
(dueño-sistema, mecanismos del SO) sobre el módulo ORIGINAL, sin las mutaciones
de fixture que hacían los E2E del control plane. Unidad 012 (15-08-2026) retiró
el sandbox de SO de `ejecucion.py` (ADR sucesor del 022: el incidente Aurora era
de cwd/entorno mal fijado, no de aislamiento de SO — ver investigacion.md de la
unidad). Los mecanismos que este fichero ejercitaba
(`identidad_ejecutable_sandbox`, `detectar_sandbox`, `SANDBOX_CONFIABLES`,
`EXIGIR_OWNER_SISTEMA`) ya no existen en el módulo.

Se mantiene como guarda de no-regresión: si alguien reintroduce un mecanismo de
sandbox de SO sin pasar por el ADR correspondiente (regla 13, AGENTS.md), este
test lo detecta.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ / "plantilla/docs/00-metodo/scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import ejecucion  # noqa: E402  (el REAL, sin mutar)


class SinSandboxDeSOTest(unittest.TestCase):
    def test_no_hay_mecanismo_de_sandbox_de_so(self):
        retirados = (
            "perfil_sandbox",
            "detectar_sandbox",
            "verificar_sandbox",
            "identidad_ejecutable_sandbox",
            "afirmar_ejecutable_sandbox",
            "sbpl_path",
            "sbpl_regex",
            "SANDBOX_CONFIABLES",
            "EXIGIR_OWNER_SISTEMA",
            "PROBE",
        )
        presentes = [nombre for nombre in retirados if hasattr(ejecucion, nombre)]
        self.assertEqual(
            presentes, [],
            "reintroducir un mecanismo de sandbox de SO exige su propio ADR "
            "(regla 13, AGENTS.md) — no colarlo sin pasar por ahí",
        )

    def test_lanzar_sigue_fijando_cwd_por_codigo_sin_shell(self):
        # La garantía real del incidente Aurora (ADR-022) sigue viva: argv como
        # lista, cwd derivado por resolver_worktree() y pasado explícito a
        # subprocess.run — nunca una cadena de shell.
        import inspect

        fuente = inspect.getsource(ejecucion._lanzar_bajo_lease)
        self.assertIn("cwd=str(worktree)", fuente)
        self.assertNotIn("/bin/sh", fuente)
        self.assertNotIn("shell=True", fuente)


if __name__ == "__main__":
    unittest.main()
