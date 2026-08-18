"""Unidad 028: R1/R2 — el lease no se roba a un dueño VIVO cuando su marcador de
arranque es indeterminable, y sigue liberándose cuando el dueño está muerto de verdad
(adversarial 12-08, hallazgo 8 del análisis de cajas negras del 18-08)."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ / "plantilla/docs/00-metodo/scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import lease  # noqa: E402  (el REAL, sin mutar)


class OwnerAliveMarcadorIndeterminableTest(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory(prefix="lease-028-")
        self.addCleanup(self.temporal.cleanup)
        self.ws = Path(self.temporal.name)
        # Sube el tope del coordinador para no pagar 60s reales si algo se queda colgado.
        os.environ["IR_TOPE_COORDINADOR_SEGUNDOS"] = "5"
        self.addCleanup(os.environ.pop, "IR_TOPE_COORDINADOR_SEGUNDOS", None)

    def test_marcador_indeterminable_con_pid_vivo_no_libera_el_lease(self):
        # R1, EL fallo adversarial: el dueño guardó un marcador REAL al adquirir, pero el
        # sondeo posterior del mismo PID (vivo de verdad: es este propio proceso de test) no
        # puede determinarlo ("desconocido") — antes eso se leía como "está muerto" y el
        # lease se robaba a un dueño vivo.
        dueno = lease.LeaseManager(
            self.ws, session_id="sesion-dueno", host="mismo-host",
            pid=os.getpid(), process_started="proc:marcador-real-guardado",
        )
        grupo = dueno.acquire("unit:028-demo")
        self.addCleanup(lambda: grupo.release() if _lease_vivo(dueno, "unit:028-demo") else None)

        with mock.patch.object(lease, "process_start_marker", return_value="desconocido"):
            aspirante = lease.LeaseManager(
                self.ws, session_id="sesion-aspirante", host="mismo-host", pid=os.getpid() + 1,
            )
            with self.assertRaises(lease.LeaseBusy) as contexto:
                aspirante.acquire("unit:028-demo")

        mensaje = str(contexto.exception)
        ruta_lease = dueno._path("unit:028-demo")
        self.assertIn(str(os.getpid()), mensaje, mensaje)
        self.assertIn(str(ruta_lease), mensaje, mensaje)
        self.assertIn("desbloquear", mensaje.lower(), mensaje)
        self.assertTrue(ruta_lease.is_file(), "el lease del dueño vivo no debía borrarse")

    def test_marcador_indeterminable_en_owner_alive_devuelve_none_no_false(self):
        # Prueba unitaria directa de la función (sin pasar por acquire()): None es "no lo
        # sé" y _active_records() lo trata como vivo; False lo habría liberado.
        manager = lease.LeaseManager(self.ws, session_id="s", host="h", pid=os.getpid())
        owner = {
            "session_id": "s", "host": "h", "pid": os.getpid(),
            "process_started": "proc:lo-que-sea",
        }
        with mock.patch.object(lease, "process_start_marker", return_value="desconocido"):
            self.assertIsNone(manager._owner_alive(owner))

    def test_host_remoto_sigue_devolviendo_none_como_hoy(self):
        # No debe cambiar: un host distinto ya era "no lo sé" antes de esta unidad.
        manager = lease.LeaseManager(self.ws, session_id="s", host="aqui", pid=os.getpid())
        owner = {
            "session_id": "s", "host": "alla", "pid": os.getpid(),
            "process_started": "proc:x",
        }
        self.assertIsNone(manager._owner_alive(owner))

    def test_dueno_muerto_de_verdad_sigue_liberando_el_lease(self):
        # R2 (caso límite): el comportamiento bueno de hoy no se pierde. Un proceso hijo que
        # ya terminó da un PID real pero muerto de verdad — _pid_vivo() debe cortar ahí,
        # antes siquiera de mirar el marcador de arranque.
        proceso = subprocess.Popen([sys.executable, "-c", "pass"])
        proceso.wait()
        pid_muerto = proceso.pid

        dueno_viejo = lease.LeaseManager(
            self.ws, session_id="sesion-vieja", host="mismo-host",
            pid=pid_muerto, process_started="proc:marcador-de-un-muerto",
        )
        # Escribe el registro directamente (no via acquire(), que fallaría con
        # _pid_vivo(mi-propio-pid); el objetivo es fabricar un lease ya publicado de un
        # dueño muerto, tal y como lo encontraría una sesión nueva).
        grupo = _publicar_lease_directo(dueno_viejo, "unit:028-demo-2")

        aspirante = lease.LeaseManager(
            self.ws, session_id="sesion-nueva", host="mismo-host", pid=os.getpid(),
        )
        nuevo_grupo = aspirante.acquire("unit:028-demo-2")
        self.addCleanup(nuevo_grupo.release)

        self.assertEqual(nuevo_grupo.records[0]["owner"]["session_id"], "sesion-nueva")
        self.assertFalse(
            lease.LeaseManager._same_record(
                aspirante._read(aspirante._path("unit:028-demo-2")), grupo.records[0]
            ),
            "el registro del dueño muerto debía haber sido sustituido, no conservado",
        )


def _lease_vivo(manager, scope):
    return manager._read(manager._path(scope)) is not None


def _publicar_lease_directo(manager, scope):
    """Publica un lease saltándose acquire() (que comprobaría el PID del propio test, no
    el del dueño simulado). Reusa la mecánica interna real de LeaseManager."""
    import uuid

    operation = str(uuid.uuid4())
    owner = {
        "session_id": manager.session_id,
        "host": manager.host,
        "pid": manager.pid,
        "process_started": manager.process_started,
    }
    record = {
        "format": 1,
        "scope": scope,
        "operation": operation,
        "fencing": manager._next_fencing(scope),
        "created": lease.ahora(),
        "owner": owner,
    }
    record["integrity"] = manager._record_integrity(record)
    manager._validate_record(manager._path(scope), record)
    lease._write_json_atomic(manager._path(scope), record)
    return lease.LeaseGroup(manager, [record])


if __name__ == "__main__":
    unittest.main()
