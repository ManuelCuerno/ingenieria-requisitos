"""Bug 004-veredicto-ronda-antigua: `veredicto_elegido()` debía reflejar la ronda de
revisión MÁS RECIENTE de hallazgos.md, pero devolvía la primera coincidencia real del
iterador — el veredicto superado de la 1ª ronda, no el vigente."""

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "plantilla/docs/00-metodo/scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import unidad  # noqa: E402  (el REAL, sin copiar)


class VeredictoElegidoTest(unittest.TestCase):
    def test_tres_rondas_devuelve_la_ultima_no_la_primera(self):
        texto = (
            "## Ronda 1\n**Veredicto:** HUECOS DE CORRECCIÓN\n\n"
            "## Ronda 2\n**Veredicto:** HUECOS DE CORRECCIÓN\n\n"
            "## Ronda 3\n**Veredicto:** LIMPIO\n"
        )

        self.assertEqual(unidad.veredicto_elegido(texto), "LIMPIO")

    def test_caso_inverso_limpio_luego_huecos_tambien_prioriza_la_ultima(self):
        texto = (
            "## Ronda 1\n**Veredicto:** LIMPIO\n\n"
            "## Ronda 2\n**Veredicto:** HUECOS DE CORRECCIÓN\n"
        )

        self.assertEqual(unidad.veredicto_elegido(texto), "HUECOS DE CORRECCIÓN")

    def test_una_sola_ronda_sigue_funcionando(self):
        texto = "**Veredicto:** LIMPIO\n"

        self.assertEqual(unidad.veredicto_elegido(texto), "LIMPIO")

    def test_menu_sin_elegir_se_salta_y_no_rompe_la_busqueda_de_la_ultima(self):
        texto = (
            "**Veredicto:** LIMPIO | HUECOS DE CORRECCIÓN\n\n"  # plantilla sin marcar
            "## Ronda 1\n**Veredicto:** HUECOS DE CORRECCIÓN\n"
        )

        self.assertEqual(unidad.veredicto_elegido(texto), "HUECOS DE CORRECCIÓN")

    def test_sin_ninguna_ronda_devuelve_none(self):
        self.assertIsNone(unidad.veredicto_elegido("# Hallazgos\n\nsin rondas todavía\n"))


if __name__ == "__main__":
    unittest.main()
