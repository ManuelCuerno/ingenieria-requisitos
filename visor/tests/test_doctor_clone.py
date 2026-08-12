"""El doctor de primer arranque (visor/doctor.py): informa y solo bloquea lo roto."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "visor/doctor.py"


class DoctorCloneTest(unittest.TestCase):
    def ejecutar(self, script, env=None):
        entorno = dict(os.environ)
        entorno.pop("INGENIERIA_REQUISITOS_REGISTRO", None)
        if env:
            entorno.update(env)
        return subprocess.run(
            [sys.executable, str(script)],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            env=entorno,
        )

    def test_en_el_clone_real_sale_limpio(self):
        resultado = self.ejecutar(DOCTOR)
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        self.assertIn("Doctor del primer arranque", resultado.stdout)
        self.assertIn("El clone", resultado.stdout)
        self.assertIn("El ejemplo", resultado.stdout)

    def test_registro_fuera_del_clone_no_es_un_fail(self):
        """Un clone de solo lectura con el registro apuntado fuera es usable:
        el doctor no debe salir con FAIL por no poder escribir dentro del clone."""
        with tempfile.TemporaryDirectory(prefix="doctor-registro-") as tmp:
            registro = Path(tmp) / "sub" / "registro.json"
            resultado = self.ejecutar(
                DOCTOR, env={"INGENIERIA_REQUISITOS_REGISTRO": str(registro)}
            )
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        self.assertIn(str(registro.parent), resultado.stdout)

    def test_un_clone_a_medias_es_un_fail_que_dice_que_falta(self):
        with tempfile.TemporaryDirectory(prefix="doctor-clone-roto-") as tmp:
            roto = Path(tmp) / "clon-roto"
            (roto / "visor").mkdir(parents=True)
            shutil.copy2(DOCTOR, roto / "visor/doctor.py")

            resultado = self.ejecutar(roto / "visor/doctor.py")

        self.assertEqual(resultado.returncode, 1, resultado.stdout + resultado.stderr)
        self.assertIn("clone incompleto", resultado.stdout)
        self.assertIn("RUNBOOK.md", resultado.stdout)


if __name__ == "__main__":
    unittest.main()
