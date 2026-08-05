import argparse
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import types
import unittest
import uuid
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ / "plantilla/docs/00-metodo/scripts"
CAJA_NEGRA = SCRIPTS / "caja_negra.py"
VERSION = RAIZ / "plantilla/docs/00-metodo/VERSION"


def cargar_modulo():
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location("caja_negra_envio", CAJA_NEGRA)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
    finally:
        sys.path.remove(str(SCRIPTS))
    return modulo


caja_negra = cargar_modulo()


def incidente_crudo(**extra):
    """Una línea como las que YA existen en cajas negras reales (esquema v1, sin redactar)."""
    datos = {
        "schema": "incidente-metarepo-v1",
        "id": str(uuid.uuid4()),
        "timestamp": "2026-08-05T10:00:00+00:00",
        "host": "portatil-secreto.local",
        "pid": 123,
        "harness": "claude",
        "session_id": "sesion",
        "fase": "despacho",
        "repo_root": "/Users/nate/proyecto-agents",
        "cwd": "/Users/nate/proyecto-agents",
        "worktree_root": "",
        "git_common_dir": "",
        "branch": "main",
        "sintoma": "no conecta con DATABASE_URL=postgres://admin:SENTINEL-DSN@db.interna/prod",
        "esperado": "conectar",
        "actual": "timeout",
        "workaround": "",
        "evidencia": [],
    }
    datos.update(extra)
    return datos


class RedaccionEnvioTest(unittest.TestCase):
    def test_incidente_con_dsn_y_ruta_home_sale_limpio_y_sin_hostname(self):
        limpio = caja_negra.redactar_incidente(incidente_crudo())

        serializado = json.dumps(limpio, ensure_ascii=False)
        self.assertNotIn("SENTINEL-DSN", serializado)
        self.assertNotIn("/Users/", serializado)
        self.assertNotIn("portatil-secreto", serializado)
        self.assertNotIn("host", limpio)
        self.assertEqual(limpio["cwd"], "~/proyecto-agents")

    def test_empaquetar_trunca_conservando_los_mas_recientes(self):
        incidentes = [{"id": f"i{n}", "sintoma": "x" * 200} for n in range(20)]

        paquete, texto = caja_negra.empaquetar(incidentes, "1.1.0", limite=3000)

        self.assertTrue(paquete["truncado"])
        self.assertEqual(paquete["total_registrados"], 20)
        self.assertLess(paquete["incluidos"], 20)
        self.assertGreater(paquete["incluidos"], 0)
        self.assertEqual(paquete["incidentes"][-1]["id"], "i19")
        self.assertNotIn('"i0"', texto)
        self.assertLessEqual(len(texto.encode("utf-8")), 3000)
        entero, _ = caja_negra.empaquetar(incidentes, "1.1.0")
        self.assertFalse(entero["truncado"])
        self.assertEqual(entero["incluidos"], 20)


class EnvioSinGhTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="caja-negra-envio-")
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "demo-agents"
        (self.repo / ".caja-negra").mkdir(parents=True)
        (self.repo / "docs/00-metodo").mkdir(parents=True)
        (self.repo / "docs/00-metodo/VERSION").write_text("1.1.0\n", encoding="utf-8")

    def escribir_jsonl(self, incidentes):
        (self.repo / ".caja-negra/incidentes.jsonl").write_text(
            "".join(json.dumps(i, ensure_ascii=False) + "\n" for i in incidentes),
            encoding="utf-8",
        )

    def enviar_sin_gh(self):
        """Ejecuta `enviar --si` con gh AUSENTE (mock); prohíbe cualquier subproceso."""
        sin_gh = types.SimpleNamespace(which=lambda *_: None)
        def prohibido(*args, **kwargs):
            raise AssertionError(f"enviar no debe lanzar subprocesos sin gh: {args}")
        original = (caja_negra.shutil, caja_negra.subprocess)
        caja_negra.shutil = sin_gh
        caja_negra.subprocess = types.SimpleNamespace(run=prohibido)
        salida = io.StringIO()
        try:
            with contextlib.redirect_stdout(salida):
                codigo = caja_negra.enviar(
                    argparse.Namespace(repo=str(self.repo), si=True)
                )
        finally:
            caja_negra.shutil, caja_negra.subprocess = original
        return codigo, salida.getvalue()

    def test_sin_gh_escribe_el_fichero_redactado_y_lo_dice_en_cristiano(self):
        self.escribir_jsonl([incidente_crudo()])

        codigo, salida = self.enviar_sin_gh()

        self.assertEqual(codigo, 0)
        envios = sorted((self.repo / ".caja-negra").glob("envio-*.json"))
        self.assertEqual(len(envios), 1)
        contenido = envios[0].read_text(encoding="utf-8")
        self.assertNotIn("SENTINEL-DSN", contenido)
        self.assertNotIn("/Users/", contenido)
        self.assertNotIn("portatil-secreto", contenido)
        paquete = json.loads(contenido)
        self.assertEqual(paquete["version_metodo"], "1.1.0")
        self.assertEqual(
            sorted(paquete["plataforma"]), ["python", "sistema", "version_sistema"]
        )
        self.assertNotIn("SENTINEL-DSN", salida)
        self.assertIn(str(envios[0]), salida)
        self.assertIn("voluntario", salida.lower())

    def test_credencial_residual_aborta_sin_ensenar_ni_escribir_nada(self):
        clave = "-----BEGIN RSA PRIVATE KEY-----\nMIIEmuydangerous\n-----END RSA PRIVATE KEY-----"
        self.escribir_jsonl([incidente_crudo(sintoma=f"volcado accidental {clave}")])

        with self.assertRaises(SystemExit) as contexto:
            self.enviar_sin_gh()

        self.assertIn("credencial", str(contexto.exception))
        self.assertNotIn("PRIVATE KEY", str(contexto.exception))
        self.assertEqual(list((self.repo / ".caja-negra").glob("envio-*.json")), [])


class RegistrarYValidarTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="caja-negra-esquema-")
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "demo-agents"
        self.repo.mkdir(parents=True)

    def ejecutar(self, *args):
        return subprocess.run(
            [sys.executable, str(CAJA_NEGRA), *args, "--repo", str(self.repo)],
            text=True,
            capture_output=True,
        )

    def registrar(self, *extra):
        return self.ejecutar(
            "registrar", "--fase", "prueba", "--sintoma", "algo raro",
            "--esperado", "A", "--actual", "B", *extra,
        )

    def lineas(self):
        return [
            json.loads(linea)
            for linea in (self.repo / ".caja-negra/incidentes.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]

    def test_registrar_estampa_severidad_y_version_del_metodo(self):
        (self.repo / "docs/00-metodo").mkdir(parents=True)
        (self.repo / "docs/00-metodo/VERSION").write_text("1.1.0\n", encoding="utf-8")

        con_severidad = self.registrar("--severidad", "P1")
        por_defecto = self.registrar()

        self.assertEqual(con_severidad.returncode, 0,
                         con_severidad.stdout + con_severidad.stderr)
        self.assertEqual(por_defecto.returncode, 0, por_defecto.stdout + por_defecto.stderr)
        primero, segundo = self.lineas()
        self.assertEqual(primero["severidad"], "P1")
        self.assertEqual(primero["version_metodo"], "1.1.0")
        self.assertEqual(segundo["severidad"], "nota")

    def test_sin_fichero_version_la_version_es_desconocida(self):
        resultado = self.registrar()

        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        self.assertEqual(self.lineas()[0]["version_metodo"], "desconocida")

    def test_listar_y_validar_aceptan_las_lineas_v1_sin_severidad_ni_version(self):
        (self.repo / ".caja-negra").mkdir()
        (self.repo / ".caja-negra/incidentes.jsonl").write_text(
            json.dumps(incidente_crudo(), ensure_ascii=False) + "\n", encoding="utf-8"
        )

        lista = self.ejecutar("listar")
        valida = self.ejecutar("validar")

        self.assertEqual(lista.returncode, 0, lista.stdout + lista.stderr)
        self.assertIn("2026-08-05", lista.stdout)
        self.assertIn("nota", lista.stdout)
        self.assertEqual(valida.returncode, 0, valida.stdout + valida.stderr)
        self.assertIn("OK", valida.stdout)

    def test_validar_reporta_lineas_malformadas_y_campos_ausentes(self):
        (self.repo / ".caja-negra").mkdir()
        roto = incidente_crudo()
        del roto["sintoma"]
        (self.repo / ".caja-negra/incidentes.jsonl").write_text(
            "esto no es json\n" + json.dumps(roto, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        resultado = self.ejecutar("validar")

        self.assertEqual(resultado.returncode, 1, resultado.stdout + resultado.stderr)
        self.assertIn("malformado", resultado.stdout)
        self.assertIn("sintoma", resultado.stdout)


if __name__ == "__main__":
    unittest.main()
