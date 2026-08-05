import importlib.util
import unittest
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[3]
CONTROL_PLANE = RAIZ / "plantilla/docs/00-metodo/scripts/control_plane.py"
FIXTURES = RAIZ / "visor/tests/fixtures/control_plane"


def cargar(ruta, nombre):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class AdversarialControlPlaneTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cp = cargar(CONTROL_PLANE, "control_plane_adversarial")

    def test_legacy_nuevo_mutante_acredita_el_claim_en_el_mismo_target(self):
        identidad = self.cp.RunIdentity("repo", "042-auth", "nightly-17")
        contrato = self.cp.EvidenceContract(
            "un token revocado no autoriza", identidad.fingerprint
        )
        runs = []
        for phase in ("legacy", "new", "mutant"):
            implementation = cargar(FIXTURES / f"{phase}.py", f"fixture_{phase}")
            passed = implementation.authorize(revoked=True) is False
            runs.append(self.cp.EvidenceRun(phase, identidad.fingerprint, passed))

        self.assertTrue(contrato.verify(runs))

    def test_matriz_de_dsn_productivos_jamas_invoca_el_conector(self):
        calls = []
        cases = (
            "postgres://root:uno@prod.db.example/clientes_test",
            "mysql://root:dos@127.0.0.1/clientes_prod",
            "host=production.db.internal dbname=clientes_e2e password=tres",
            "host=localhost dbname=production password=cuatro",
        )
        for dsn in cases:
            with self.subTest(dsn=dsn):
                with self.assertRaises(self.cp.UnsafeTestTarget) as context:
                    self.cp.connect_if_safe(
                        lambda: calls.append(dsn),
                        {"APP_ENV": "test", "DATABASE_URL": dsn},
                    )
                for secret in ("uno", "dos", "tres", "cuatro"):
                    self.assertNotIn(secret, str(context.exception))
        self.assertEqual(calls, [])

    def test_dos_arboles_no_comparten_namespace_recursos_o_preview(self):
        first = self.cp.RunIdentity("repo-a", "042-auth", "run-1")
        second = self.cp.RunIdentity("repo-b", "042-auth", "run-1")

        self.assertNotEqual(first.database(), second.database())
        self.assertNotEqual(first.port(), second.port())
        self.assertNotEqual(first.docker_name(), second.docker_name())
        self.assertNotEqual(first.docker_tag(), second.docker_tag())
        self.assertNotEqual(first.temp_path("/tmp"), second.temp_path("/tmp"))
        self.assertNotEqual(first.log_path("logs"), second.log_path("logs"))
        with self.assertRaises(self.cp.IdentityMismatch):
            first.assert_preview_identity({"fingerprint": second.fingerprint, "status": 200})


if __name__ == "__main__":
    unittest.main()
