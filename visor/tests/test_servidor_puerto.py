"""El puerto del visor es exclusivo: un segundo visor no puede robarlo.

Bug de campo (PR #1, Windows): con SO_REUSEADDR heredado de ThreadingHTTPServer,
un segundo visor en paralelo se quedaba con el puerto 8765 y las conexiones del
primero. En Windows el bind ahora usa SO_EXCLUSIVEADDRUSE; en el resto de
plataformas el robo nunca fue posible y SO_REUSEADDR se conserva para poder
rearrancar sin esperar el TIME_WAIT. Este test es el camino rojo real en la
pata Windows del CI: sin el fix, el segundo bind NO falla allí.
"""

import http.server
import importlib.util
import sys
import unittest
from pathlib import Path

SERVIR = Path(__file__).resolve().parent.parent / "servir.py"


def cargar_servir():
    if str(SERVIR.parent) not in sys.path:
        sys.path.insert(0, str(SERVIR.parent))
    spec = importlib.util.spec_from_file_location("servir_bajo_prueba", SERVIR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class Manejador(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass


class PuertoExclusivoTest(unittest.TestCase):
    def test_un_segundo_visor_no_puede_quedarse_el_puerto(self):
        servir = cargar_servir()
        primero = servir.ServidorVisor(("127.0.0.1", 0), Manejador)
        self.addCleanup(primero.server_close)
        puerto = primero.server_address[1]

        with self.assertRaises(OSError):
            segundo = servir.ServidorVisor(("127.0.0.1", puerto), Manejador)
            segundo.server_close()


if __name__ == "__main__":
    unittest.main()
