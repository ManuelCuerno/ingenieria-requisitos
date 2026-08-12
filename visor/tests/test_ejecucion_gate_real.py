"""N2: el gate REAL del sandbox, ejercitado sin mutar ejecucion.py.

Los E2E del control plane reescriben SANDBOX_CONFIABLES y EXIGIR_OWNER_SISTEMA
en la COPIA del workspace para poder inyectar un srt de fixture; eso deja al
gate real (dueño-sistema, mecanismos del SO) sin ejercitar jamás. Estos tests
importan el fichero ORIGINAL y prueban ese gate tal cual se distribuye.
"""

import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath

RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ / "plantilla/docs/00-metodo/scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import ejecucion  # noqa: E402  (el REAL, sin mutar)


class GateSandboxRealTest(unittest.TestCase):
    def test_el_fichero_distribuido_lleva_el_gate_armado(self):
        """La mutación de los E2E es de su copia; el original queda armado."""
        self.assertTrue(ejecucion.EXIGIR_OWNER_SISTEMA)
        texto = (SCRIPTS / "ejecucion.py").read_text(encoding="utf-8")
        self.assertIn("EXIGIR_OWNER_SISTEMA = True", texto)
        for plataforma in ("darwin", "linux"):
            mecanismos = ejecucion.SANDBOX_CONFIABLES[plataforma]
            self.assertTrue(mecanismos)
            for _, ruta in mecanismos:
                # Rutas POSIX (darwin/linux); en Windows Path.is_absolute daría
                # falso sobre una ruta sin letra de unidad, así que se juzga como POSIX.
                self.assertTrue(PurePosixPath(ruta).is_absolute(), ruta)

    @unittest.skipIf(os.name == "nt", "en Windows st_uid es 0 para todo: "
                                      "la distinción de dueño no existe")
    def test_owner_sistema_rechaza_un_ejecutable_del_usuario(self):
        with tempfile.TemporaryDirectory(prefix="gate-real-") as tmp:
            falso = Path(tmp) / "srt"
            falso.write_text("#!/bin/sh\n", encoding="utf-8")
            falso.chmod(0o755)
            with self.assertRaises(ejecucion.ErrorEjecucion) as contexto:
                ejecucion.identidad_ejecutable_sandbox(
                    "srt", str(falso), exigir_owner_sistema=True
                )
        self.assertIn("no pertenece al sistema", str(contexto.exception))

    @unittest.skipIf(os.name == "nt", "sin binarios del sistema con uid 0")
    def test_owner_sistema_acepta_un_binario_del_sistema(self):
        binario = "/bin/ls"
        datos = os.stat(binario)
        if datos.st_uid != 0 or datos.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            self.skipTest("/bin/ls no es de root con permisos estrictos aquí")
        identidad = ejecucion.identidad_ejecutable_sandbox(
            "srt", binario, exigir_owner_sistema=True
        )
        self.assertEqual(identidad["owner_uid"], 0)
        self.assertRegex(identidad["sha256"], r"^[a-f0-9]{64}$")
        self.assertTrue(identidad["owner_sistema_exigido"])

    def test_sin_mecanismo_para_la_plataforma_rechaza_en_claro(self):
        original = ejecucion.SANDBOX_CONFIABLES
        ejecucion.SANDBOX_CONFIABLES = {}
        try:
            with self.assertRaises(ejecucion.ErrorEjecucion) as contexto:
                ejecucion.detectar_sandbox()
        finally:
            ejecucion.SANDBOX_CONFIABLES = original
        self.assertIn("sandbox", str(contexto.exception))


if __name__ == "__main__":
    unittest.main()
