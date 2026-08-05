import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
CONTROL_PLANE = (
    RAIZ / "plantilla" / "docs" / "00-metodo" / "scripts" / "control_plane.py"
)


def cargar_control_plane():
    spec = importlib.util.spec_from_file_location("control_plane_bajo_prueba", CONTROL_PLANE)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class GuardTestTargetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cp = cargar_control_plane()

    def test_rechaza_produccion_antes_de_invocar_la_conexion_y_redacta(self):
        llamadas = []
        entorno = {
            "APP_ENV": "production",
            "DATABASE_URL": "postgres://admin:super-secreto@db.prod.example/clientes",
            "API_TOKEN": "token-que-no-debe-salir",
        }

        with self.assertRaises(self.cp.UnsafeTestTarget) as contexto:
            self.cp.connect_if_safe(lambda: llamadas.append("conexion"), entorno)

        self.assertEqual(llamadas, [])
        mensaje = str(contexto.exception)
        self.assertNotIn("super-secreto", mensaje)
        self.assertNotIn("token-que-no-debe-salir", mensaje)

    def test_rechaza_dsn_libpq_host_publico_y_base_productiva(self):
        casos = (
            {"APP_ENV": "test", "DATABASE_URL": "host=db.example.org dbname=app_test"},
            {"APP_ENV": "e2e", "DB_HOST": "127.0.0.1", "DB_NAME": "clientes_prod"},
            {"APP_ENV": "live", "DB_HOST": "localhost", "DB_NAME": "app_test"},
        )
        for entorno in casos:
            with self.subTest(entorno=entorno):
                with self.assertRaises(self.cp.UnsafeTestTarget):
                    self.cp.assert_safe_test_target(entorno)

    def test_rechaza_prod_numerado_aunque_el_host_figure_en_allowlist(self):
        for marcador in ("prod2", "production01", "live7", "principal3"):
            host = f"db-{marcador}.internal"
            with self.subTest(marcador=marcador):
                with self.assertRaises(self.cp.UnsafeTestTarget):
                    self.cp.assert_safe_test_target(
                        {
                            "APP_ENV": "test",
                            "DB_HOST": host,
                            "DB_NAME": f"app_{marcador}_test_run",
                        },
                        allow_hosts={host},
                    )

    def test_acepta_local_con_nombre_de_test_y_allowlist_remota_explicita(self):
        local = self.cp.assert_safe_test_target({
            "APP_ENV": "test",
            "DATABASE_URL": "postgres://tester:clave@127.0.0.1/app_test_run42",
        })
        remoto = self.cp.assert_safe_test_target(
            {"APP_ENV": "e2e", "DB_HOST": "e2e.internal", "DB_NAME": "app_e2e_run42"},
            allow_hosts={"e2e.internal"},
        )

        self.assertNotEqual(local.fingerprint, remoto.fingerprint)
        self.assertNotIn("clave", local.describe())

    def test_namespace_esperado_debe_aparecer_en_la_base(self):
        with self.assertRaises(self.cp.UnsafeTestTarget):
            self.cp.assert_safe_test_target(
                {"APP_ENV": "test", "DB_HOST": "localhost", "DB_NAME": "app_test_otro"},
                expected_namespace="repo-unidad-a1b2c3",
            )

    def test_redactor_cubre_url_query_libpq_y_asignaciones(self):
        crudo = (
            "postgres://ana:clave@localhost/app_test?token=abc&sslmode=disable "
            "password='otra clave' API_KEY=xyz usuario=visible"
        )
        limpio = self.cp.redact_secrets(crudo)

        for secreto in ("clave", "abc", "otra clave", "xyz"):
            self.assertNotIn(secreto, limpio)
        self.assertIn("usuario=visible", limpio)

    def test_error_y_redactor_no_filtran_cabeceras_cookies_dsn_ni_userinfo(self):
        sentinel = "SENTINEL-ULTRAPRIVADO"
        entorno = {
            "APP_ENV": "production",
            "DATABASE_URL": f"postgres://admin:{sentinel}@prod/db",
            "AUTHORIZATION": f"Bearer {sentinel}",
            "COOKIE": f"session={sentinel}",
            "SET_COOKIE": f"session={sentinel}; HttpOnly",
            "PRIVATE_DSN": f"host=prod password='{sentinel} con espacios'",
        }

        with self.assertRaises(self.cp.UnsafeTestTarget) as contexto:
            self.cp.assert_safe_test_target(entorno)
        self.assertNotIn(sentinel, str(contexto.exception))

        texto = (
            f"Authorization: Bearer {sentinel} Cookie: sid={sentinel} "
            f"Set-Cookie: sid={sentinel}; HttpOnly "
            f"DATABASE_URL=postgres://admin:{sentinel}@prod/db "
            f"password='{sentinel} con espacios'"
        )
        self.assertNotIn(sentinel, self.cp.redact_secrets(texto))


class RunIdentityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cp = cargar_control_plane()

    def test_identidad_es_reproducible_y_separa_repos_unidades_y_runs(self):
        base = self.cp.RunIdentity("Mi Repo", "042-Pago", "CI 17")
        igual = self.cp.RunIdentity("mi-repo", "042-pago", "ci-17")
        variantes = (
            self.cp.RunIdentity("otro", "042-pago", "ci-17"),
            self.cp.RunIdentity("mi-repo", "043-pago", "ci-17"),
            self.cp.RunIdentity("mi-repo", "042-pago", "ci-18"),
        )

        self.assertEqual(base.namespace, igual.namespace)
        self.assertEqual(base.fingerprint, igual.fingerprint)
        self.assertTrue(all(base.namespace != item.namespace for item in variantes))

    def test_deriva_recursos_acotados_y_no_usa_latest(self):
        identidad = self.cp.RunIdentity("repo-muy-largo-" * 8, "123-unidad", "run-1")

        self.assertLessEqual(len(identidad.database("aplicacion")), 63)
        self.assertRegex(identidad.database(), r"^[a-z][a-z0-9_]+$")
        self.assertTrue(20000 <= identidad.port() <= 39999)
        self.assertRegex(identidad.docker_name("web"), r"^web-[a-z0-9-]+$")
        self.assertRegex(identidad.docker_tag("mi-app"), r"^mi-app:test-[a-z0-9-]+$")
        self.assertNotIn("latest", identidad.docker_tag())
        self.assertEqual(identidad.temp_path("/tmp"), identidad.temp_path("/tmp"))
        self.assertEqual(identidad.log_path("logs").suffix, ".log")

    def test_preview_exige_identidad_observable_completa(self):
        identidad = self.cp.RunIdentity("repo", "001-login", "run-a")

        identidad.assert_preview_identity({"fingerprint": identidad.fingerprint})
        with self.assertRaises(self.cp.IdentityMismatch):
            identidad.assert_preview_identity({"status": 200})
        with self.assertRaises(self.cp.IdentityMismatch):
            identidad.assert_preview_identity({"fingerprint": "otra"})


class EvidenceContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cp = cargar_control_plane()

    def test_acepta_legacy_rojo_nuevo_verde_mutante_rojo_mismo_target(self):
        contrato = self.cp.EvidenceContract("login no acepta token revocado", "target-abc")
        runs = (
            self.cp.EvidenceRun("legacy", "target-abc", False),
            self.cp.EvidenceRun("new", "target-abc", True),
            self.cp.EvidenceRun("mutant", "target-abc", False),
        )

        contrato.verify(runs)

    def test_rechaza_evidencia_circular_target_distinto_y_mutante_verde(self):
        contrato = self.cp.EvidenceContract("claim", "target-abc")
        casos = (
            (
                self.cp.EvidenceRun("legacy", "target-abc", True),
                self.cp.EvidenceRun("new", "target-abc", True),
                self.cp.EvidenceRun("mutant", "target-abc", False),
            ),
            (
                self.cp.EvidenceRun("legacy", "target-abc", False),
                self.cp.EvidenceRun("new", "otro-target", True),
                self.cp.EvidenceRun("mutant", "target-abc", False),
            ),
            (
                self.cp.EvidenceRun("legacy", "target-abc", False),
                self.cp.EvidenceRun("new", "target-abc", True),
                self.cp.EvidenceRun("mutant", "target-abc", True),
            ),
        )
        for runs in casos:
            with self.subTest(runs=runs):
                with self.assertRaises(self.cp.InvalidEvidence):
                    contrato.verify(runs)

    def test_evidence_run_exige_bool_exacto(self):
        for falso_bool in ("", "false", 0, 1, None, []):
            with self.subTest(valor=falso_bool):
                with self.assertRaises(self.cp.InvalidEvidence):
                    self.cp.EvidenceRun("legacy", "target-abc", falso_bool)

    def test_recibo_ejecutable_liga_target_scope_mutacion_y_presupuesto(self):
        recibo = {
            "version": 1,
            "claim": "token revocado no autoriza",
            "target_fingerprint": "target-abc",
            "route": "directo",
            "test_scope": "area",
            "runs": [
                {"phase": "legacy", "target_fingerprint": "target-abc", "passed": False,
                 "command": "pytest legacy", "exit_code": 1, "output_digest": "a" * 64},
                {"phase": "new", "target_fingerprint": "target-abc", "passed": True,
                 "command": "pytest new", "exit_code": 0, "output_digest": "b" * 64},
                {"phase": "mutant", "target_fingerprint": "target-abc", "passed": False,
                 "command": "pytest mutant", "exit_code": 1, "output_digest": "c" * 64},
            ],
            "metrics": {
                "first_artifact_seconds": 299,
                "close_seconds": 899,
                "method_seconds": 100,
                "total_seconds": 600,
            },
        }

        self.cp.validate_close_receipt(
            recibo, route="directo", expected_target_fingerprint="target-abc"
        )
        for key, value in (
            ("target_fingerprint", "inventado"),
            ("test_scope", "smoke"),
        ):
            mutado = json.loads(json.dumps(recibo))
            mutado[key] = value
            with self.subTest(key=key):
                with self.assertRaises(self.cp.InvalidEvidence):
                    self.cp.validate_close_receipt(
                        mutado, route="directo", expected_target_fingerprint="target-abc"
                    )
        lento = json.loads(json.dumps(recibo))
        lento["metrics"]["first_artifact_seconds"] = 301
        with self.assertRaises(self.cp.InvalidEvidence):
            self.cp.validate_close_receipt(lento, route="directo")
        no_finito = json.loads(json.dumps(recibo))
        no_finito["metrics"]["method_seconds"] = float("nan")
        with self.assertRaises(self.cp.InvalidEvidence):
            self.cp.validate_close_receipt(no_finito, route="directo")
        with self.assertRaises(self.cp.InvalidEvidence):
            self.cp.validate_close_receipt(recibo, route="inventada")


class ClosePolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cp = cargar_control_plane()

    def test_matriz_de_gates_es_proporcional(self):
        documental = self.cp.close_policy("documental")
        prototipo = self.cp.close_policy("prototipo")
        directo = self.cp.close_policy("directo")
        normal = self.cp.close_policy("normal")

        self.assertFalse(documental.require_merge)
        self.assertFalse(documental.require_user_ok)
        self.assertTrue(documental.require_fresh_review)
        self.assertFalse(prototipo.require_merge)
        self.assertFalse(prototipo.require_user_ok)
        self.assertTrue(prototipo.require_discard)
        self.assertTrue(directo.require_merge and directo.require_user_ok)
        self.assertFalse(self.cp.close_policy("expres").require_user_ok)
        self.assertEqual(directo.test_scope, "area")
        self.assertEqual(normal.test_scope, "area+full")

    def test_presupuesto_evalua_datos_sin_reloj_real(self):
        directo = self.cp.close_policy("directo")
        self.assertEqual(directo.budget_violations(
            first_artifact_seconds=299,
            close_seconds=899,
            method_seconds=100,
            total_seconds=600,
        ), [])
        violaciones = directo.budget_violations(
            first_artifact_seconds=301,
            close_seconds=901,
            method_seconds=130,
            total_seconds=600,
        )
        self.assertEqual({item.code for item in violaciones}, {
            "first_artifact", "method_close", "method_overhead",
        })

    def test_manifiesto_seguro_valida_identidad_target_y_no_acepta_secretos(self):
        identidad = self.cp.RunIdentity("repo", "001-login", "run-a")
        manifiesto = {
            "version": 1,
            "identity": identidad.as_dict(),
            "targets": [{
                "env": "test",
                "host": "localhost",
                "database": identidad.database(),
                "fingerprint": self.cp.assert_safe_test_target({
                    "APP_ENV": "test",
                    "DB_HOST": "localhost",
                    "DB_NAME": identidad.database(),
                }, expected_namespace=identidad.namespace).fingerprint,
            }],
        }
        self.cp.validate_manifest(manifiesto)

        inventado = json.loads(json.dumps(manifiesto))
        inventado["targets"][0]["fingerprint"] = "target-abc"
        with self.assertRaises(self.cp.InvalidManifest):
            self.cp.validate_manifest(inventado)

        contaminado = json.loads(json.dumps(manifiesto))
        contaminado["password"] = "valor-privado-123"
        with self.assertRaises(self.cp.InvalidManifest) as contexto:
            self.cp.validate_manifest(contaminado)
        self.assertNotIn("valor-privado-123", str(contexto.exception))

    def test_allowlist_del_manifiesto_no_es_autorizacion_de_confianza(self):
        identidad = self.cp.RunIdentity("repo", "001-login", "run-a")
        host = "e2e.internal"
        target = self.cp.assert_safe_test_target(
            {"APP_ENV": "e2e", "DB_HOST": host, "DB_NAME": identidad.database()},
            expected_namespace=identidad.namespace,
            allow_hosts={host},
        )
        manifiesto = {
            "version": 1,
            "identity": identidad.as_dict(),
            "targets": [{
                "env": "e2e", "host": host, "database": identidad.database(),
                "fingerprint": target.fingerprint, "allow_hosts": [host],
            }],
        }
        with self.assertRaises(self.cp.InvalidManifest):
            self.cp.validate_manifest(manifiesto)
        manifiesto["targets"][0].pop("allow_hosts")
        self.cp.validate_manifest(manifiesto, trusted_allow_hosts={host})


if __name__ == "__main__":
    unittest.main()
