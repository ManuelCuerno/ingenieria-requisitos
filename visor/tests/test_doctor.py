"""revisar_plataforma() de visor/doctor.py: en win32 receta WSL2, en Linux sin mecanismo
receta bubblewrap, en macOS no cambia de comportamiento (solo informa qué mecanismo hay)."""

import importlib.util
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DOCTOR_PATH = RAIZ / "visor/doctor.py"

_spec = importlib.util.spec_from_file_location("doctor_bajo_test", DOCTOR_PATH)
doctor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(doctor)


class RevisarPlataformaTest(unittest.TestCase):
    def setUp(self):
        self._sandbox_rutas_original = doctor.SANDBOX_RUTAS
        self._platform_original = sys.platform
        self.addCleanup(self._restaurar)

    def _restaurar(self):
        doctor.SANDBOX_RUTAS = self._sandbox_rutas_original
        sys.platform = self._platform_original

    # R1: win32 receta WSL2 -----------------------------------------------------

    def test_win32_receta_wsl2(self):
        sys.platform = "win32"

        estado, detalle, consecuencia = doctor.revisar_plataforma()

        self.assertEqual(estado, "WARN")
        texto = detalle + " " + consecuencia
        self.assertIn("WSL2", texto)
        self.assertIn("VERSION 2", texto)
        self.assertIn("/mnt/c", texto)

    def test_win32_receta_wsl2_aunque_bash_y_python3_esten_presentes(self):
        sys.platform = "win32"
        which_original = doctor.shutil.which
        doctor.shutil.which = lambda nombre: "/usr/bin/" + nombre  # simula presentes
        self.addCleanup(setattr, doctor.shutil, "which", which_original)

        estado, _, consecuencia = doctor.revisar_plataforma()

        self.assertEqual(estado, "WARN")
        self.assertIn("WSL2", consecuencia)

    # R2: linux sin bwrap/srt receta bubblewrap; con mecanismo, OK --------------

    def test_linux_sin_mecanismo_receta_bubblewrap(self):
        sys.platform = "linux"
        doctor.SANDBOX_RUTAS = {
            "linux": (("bwrap", "/ruta/inexistente/bwrap"),
                      ("srt", "/ruta/inexistente/srt")),
        }

        estado, detalle, consecuencia = doctor.revisar_plataforma()

        self.assertEqual(estado, "WARN")
        self.assertIn("bubblewrap", consecuencia)
        self.assertIn("apt install bubblewrap", consecuencia)

    def test_linux_con_bwrap_presente_es_ok(self):
        sys.platform = "linux"
        doctor.SANDBOX_RUTAS = {
            "linux": (("bwrap", str(DOCTOR_PATH)),  # cualquier fichero real sirve
                      ("srt", "/ruta/inexistente/srt")),
        }

        estado, detalle, consecuencia = doctor.revisar_plataforma()

        self.assertEqual(estado, "OK")
        self.assertIn("bwrap", detalle)
        self.assertEqual(consecuencia, "")

    def test_linux_con_srt_presente_es_ok(self):
        sys.platform = "linux"
        doctor.SANDBOX_RUTAS = {
            "linux": (("bwrap", "/ruta/inexistente/bwrap"),
                      ("srt", str(DOCTOR_PATH))),
        }

        estado, detalle, consecuencia = doctor.revisar_plataforma()

        self.assertEqual(estado, "OK")
        self.assertIn("srt", detalle)

    # R2: darwin no cambia --------------------------------------------------

    def test_darwin_con_sandbox_exec_presente_es_ok_e_informa(self):
        sys.platform = "darwin"
        doctor.SANDBOX_RUTAS = {
            "darwin": (("sandbox-exec", str(DOCTOR_PATH)),
                       ("srt", "/ruta/inexistente/srt")),
        }

        estado, detalle, consecuencia = doctor.revisar_plataforma()

        self.assertEqual(estado, "OK")
        self.assertIn("sandbox-exec", detalle)
        self.assertEqual(consecuencia, "")

    def test_darwin_sin_mecanismo_sigue_siendo_ok(self):
        """En macOS no cambia nada (R2): a diferencia de Linux, la ausencia del
        mecanismo no convierte el informe en un aviso."""
        sys.platform = "darwin"
        doctor.SANDBOX_RUTAS = {
            "darwin": (("sandbox-exec", "/ruta/inexistente/sandbox-exec"),
                       ("srt", "/ruta/inexistente/srt")),
        }

        estado, _, consecuencia = doctor.revisar_plataforma()

        self.assertEqual(estado, "OK")
        self.assertEqual(consecuencia, "")


class LosTresTextosNombranWSL2Test(unittest.TestCase):
    """R3: la misma verdad en manual, RUNBOOK y sandbox.md de la plantilla."""

    def test_manual_faq_funciona_en_windows_nombra_wsl2(self):
        texto = (RAIZ / "manual-ingenieria-requisitos.html").read_text(encoding="utf-8")
        inicio = texto.index("¿Funciona en Windows?")
        fragmento = texto[inicio:inicio + 1500]
        self.assertIn("WSL2", fragmento)

    def test_runbook_nombra_wsl2_y_la_verificacion_de_30_segundos(self):
        texto = (RAIZ / "RUNBOOK.md").read_text(encoding="utf-8")
        self.assertIn("WSL2", texto)
        self.assertIn("VERSION 2", texto)

    def test_sandbox_md_de_la_plantilla_nombra_wsl2(self):
        texto = (RAIZ / "plantilla/docs/00-metodo/sandbox.md").read_text(encoding="utf-8")
        self.assertIn("WSL2", texto)
        self.assertIn("VERSION 2", texto)


if __name__ == "__main__":
    unittest.main()
