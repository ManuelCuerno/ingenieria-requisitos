import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
VALIDAR = RAIZ / "visor" / "validar.py"


def cargar_validar():
    spec = importlib.util.spec_from_file_location("validar_bajo_prueba", VALIDAR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class GuardKeywordsEsquemaTest(unittest.TestCase):
    """_errores_esquema implementa un SUBCONJUNTO de Draft 7. Cualquier keyword fuera de él
    se ignoraba EN SILENCIO: un esquema con `if/then` o `patternProperties` validaba todo
    como bueno sin mirar nada. El guard recorre esquema.json entero (anidados y definitions
    incluidos) y convierte esa ceguera en error ruidoso — distinguiendo posición de keyword
    de posición de nombre de campo, porque un campo puede llamarse `if`."""

    def setUp(self):
        self.validar = cargar_validar()

    def hallazgos(self, esquema):
        return self.validar._keywords_no_soportadas(esquema)

    def test_if_then_produce_error(self):
        esquema = {
            "type": "object",
            "if": {"properties": {"x": {"const": 1}}},
            "then": {"required": ["y"]},
        }

        hallazgos = self.hallazgos(esquema)

        self.assertTrue(any("#/if" in h for h in hallazgos), hallazgos)
        self.assertTrue(any("#/then" in h for h in hallazgos), hallazgos)

    def test_patternproperties_produce_error(self):
        hallazgos = self.hallazgos({"type": "object", "patternProperties": {"^x": {}}})

        self.assertTrue(any("patternProperties" in h for h in hallazgos), hallazgos)

    def test_un_campo_puede_llamarse_como_una_keyword(self):
        # `if`, `then` y `patternProperties` aquí son NOMBRES de campo, no keywords.
        esquema = {
            "type": "object",
            "properties": {
                "if": {"type": "string"},
                "then": {"type": "string"},
                "patternProperties": {"type": "object"},
            },
        }

        self.assertEqual(self.hallazgos(esquema), [])

    def test_caza_keywords_en_anidados_y_definitions(self):
        esquema = {
            "definitions": {
                "cosa": {
                    "type": "array",
                    "items": {"anyOf": [{"type": "string", "maxLength": 3}]},
                }
            },
            "properties": {"lista": {"$ref": "#/definitions/cosa"}},
        }

        hallazgos = self.hallazgos(esquema)

        self.assertEqual(len(hallazgos), 1, hallazgos)
        self.assertIn("#/definitions/cosa/items/anyOf[0]/maxLength", hallazgos[0])

    def test_formas_no_implementadas_de_keywords_soportadas(self):
        esquema = {
            "type": ["object", "null"],
            "items": [{"type": "string"}],
            "additionalProperties": {"type": "string"},
        }

        hallazgos = self.hallazgos(esquema)

        self.assertEqual(len(hallazgos), 3, hallazgos)

    def test_el_esquema_real_pasa_el_guard(self):
        esquema = json.loads((RAIZ / "visor" / "esquema.json").read_text(encoding="utf-8"))

        self.assertEqual(self.hallazgos(esquema), [])

    def test_validar_esquema_hace_error_ruidoso_y_no_finge_validar(self):
        with tempfile.TemporaryDirectory(prefix="esquema-guard-") as tmp:
            (Path(tmp) / "esquema.json").write_text(
                json.dumps({
                    "type": "object",
                    "if": {"properties": {"x": {"const": 1}}},
                    "then": {"required": ["campo_que_faltaria"]},
                }),
                encoding="utf-8",
            )
            self.validar.BASE = Path(tmp)

            # Sin el guard, este documento pasaría por válido sin validarse.
            self.validar.validar_esquema({"x": 1})

        errores = self.validar.errores
        self.assertTrue(any("keyword" in e for e in errores), errores)
        self.assertTrue(any("NO se validó nada" in e for e in errores), errores)


if __name__ == "__main__":
    unittest.main()
