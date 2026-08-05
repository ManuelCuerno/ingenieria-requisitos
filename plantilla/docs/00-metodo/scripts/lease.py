#!/usr/bin/env python3
"""Autoridad local para operaciones que comparten un workspace.

Los leases viven fuera de git en ``.runtime/leases``. La creación y el
fencing se serializan con un lock del sistema operativo; un proceso muerto no
puede dejar ese lock interno ocupado. Los registros de autoridad sí son
durables y llevan identidad suficiente para distinguir un PID reutilizado.

Esta capa coordina procesos que ven el MISMO filesystem. Un hostname distinto
se considera propietario remoto vivo: nunca se rompe automáticamente ni se
finge coordinación entre clones distintos.
"""

import contextlib
import datetime
import hashlib
import hmac
import json
import os
import socket
import subprocess
import tempfile
import uuid
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - en Windows el candado lo da msvcrt
    fcntl = None
try:
    import msvcrt
except ImportError:
    msvcrt = None


class LeaseError(RuntimeError):
    pass


class LeaseBusy(LeaseError):
    pass


class LeaseLost(LeaseError):
    pass


def ahora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _pid_vivo(pid):
    """True si existe un proceso local con ese PID.

    En Windows NO vale os.kill(pid, 0): allí cualquier señal que no sea de
    consola TERMINA el proceso vía TerminateProcess en vez de sondearlo.
    (Duplicado de control_plane.pid_vivo: este módulo se carga standalone.)
    """
    if os.name == "nt":  # pragma: no cover - rama Windows, la ejercita su CI
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        ERROR_ACCESS_DENIED = 5
        STILL_ACTIVE = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid)
        )
        if not handle:
            return ctypes.get_last_error() == ERROR_ACCESS_DENIED
        try:
            codigo = ctypes.c_ulong()
            if kernel32.GetExitCodeProcess(handle, ctypes.byref(codigo)):
                return codigo.value == STILL_ACTIVE
            return True
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    return True


def _marca_arranque_windows(pid):  # pragma: no cover - rama Windows, la ejercita su CI
    import ctypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return ""
    try:
        # GetProcessTimes rellena cuatro FILETIME de 8 bytes: creación, salida,
        # kernel y usuario. Solo interesa la creación.
        tiempos = (ctypes.c_ulonglong * 4)()
        if kernel32.GetProcessTimes(
            handle,
            ctypes.byref(tiempos, 0),
            ctypes.byref(tiempos, 8),
            ctypes.byref(tiempos, 16),
            ctypes.byref(tiempos, 24),
        ):
            return f"win:{tiempos[0]}"
        return ""
    finally:
        kernel32.CloseHandle(handle)


def process_start_marker(pid):
    """Identidad estable de una encarnación de PID, no solo su número."""
    if os.name == "nt":  # pragma: no cover - rama Windows, la ejercita su CI
        return _marca_arranque_windows(pid) or "desconocido"
    proc = Path("/proc") / str(pid) / "stat"
    try:
        campos = proc.read_text(encoding="utf-8").split()
        if len(campos) > 21:
            return f"proc:{campos[21]}"
    except OSError:
        pass
    try:
        salida = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        ).stdout.strip()
    except OSError:
        salida = ""
    return f"ps:{salida}" if salida else "desconocido"


def session_id_default():
    for clave in ("IR_SESSION_ID", "CODEX_THREAD_ID", "CLAUDE_SESSION_ID"):
        valor = os.environ.get(clave, "").strip()
        if valor:
            return valor
    return str(uuid.uuid4())


def _scope_key(scope):
    return hashlib.sha256(scope.encode("utf-8")).hexdigest()


def _fsync_directory(path):
    """Hace durable un replace/unlink, no solo los bytes del fichero."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(str(path), flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_json_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporal = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporal, path)
        _fsync_directory(path.parent)
    finally:
        if os.path.exists(temporal):
            os.unlink(temporal)


def failpoint(name):
    """Barrera determinista de tests: notifica por un FD y espera por otro."""
    prefix = f"IR_FAILPOINT_{name.upper()}"
    ready = os.environ.get(f"{prefix}_READY_FD")
    wait = os.environ.get(f"{prefix}_WAIT_FD")
    if ready:
        os.write(int(ready), b"1")
    if wait:
        os.read(int(wait), 1)


class LeaseGroup:
    def __init__(self, manager, records):
        self.manager = manager
        self.records = records
        self.tokens = {record["scope"]: record["fencing"] for record in records}

    def assert_owner(self):
        self.manager._assert_records(self.records)

    def release(self):
        self.manager._release_records(self.records)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()


class LeaseManager:
    def __init__(
        self,
        workspace,
        *,
        session_id=None,
        host=None,
        pid=None,
        process_started=None,
    ):
        self.workspace = Path(workspace).resolve()
        self.root = self.workspace / ".runtime/leases"
        self.active = self.root / "active"
        self.fencing = self.root / "fencing"
        self.session_id = session_id or session_id_default()
        self.host = host or socket.gethostname()
        self.pid = int(pid if pid is not None else os.getpid())
        self.process_started = (
            process_started
            if process_started is not None
            else process_start_marker(self.pid)
        )

    @contextlib.contextmanager
    def _coordinator(self):
        self._ensure_directory(self.root, "raíz de leases")
        lock_path = self.root / "coordinator.lock"
        descriptor = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            if fcntl is not None:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                liberar = lambda: fcntl.flock(descriptor, fcntl.LOCK_UN)
            elif msvcrt is not None:
                if os.fstat(descriptor).st_size == 0:
                    os.write(descriptor, b"0")
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
                liberar = lambda: msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                raise LeaseError(
                    "los leases locales requieren un lock exclusivo del sistema "
                    "(flock o msvcrt.locking); este sistema no ofrece ninguno y la "
                    "operación concurrente se bloquea por seguridad"
                )
            try:
                yield
            finally:
                liberar()
        finally:
            os.close(descriptor)

    def _path(self, scope):
        return self.active / f"{_scope_key(scope)}.json"

    @staticmethod
    def _ensure_directory(path, label):
        if path.is_symlink():
            raise LeaseError(f"{label} no puede ser symlink")
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise LeaseError(f"{label} ilegible: {exc}") from exc
        if path.is_symlink() or not path.is_dir():
            raise LeaseError(f"{label} no es un directorio regular")

    @staticmethod
    def _record_integrity(record):
        payload = {key: value for key, value in record.items() if key != "integrity"}
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _validate_record(self, path, record):
        expected_keys = {
            "format", "scope", "operation", "fencing", "created", "owner", "integrity"
        }
        if not isinstance(record, dict) or set(record) != expected_keys:
            raise LeaseError(f"lease corrupto {path.name}: schema inválido")
        scope = record.get("scope")
        if (not isinstance(scope, str) or not scope or scope != scope.strip()
                or any(ord(character) < 32 for character in scope)):
            raise LeaseError(f"lease corrupto {path.name}: scope inválido")
        if path.name != f"{_scope_key(scope)}.json":
            raise LeaseError(f"lease corrupto {path.name}: hash de scope incoherente")
        owner = record.get("owner")
        owner_keys = {"session_id", "host", "pid", "process_started"}
        if (
            record.get("format") != 1
            or type(record.get("fencing")) is not int
            or record["fencing"] < 1
            or not isinstance(record.get("operation"), str)
            or not isinstance(record.get("created"), str)
            or not isinstance(owner, dict)
            or set(owner) != owner_keys
            or type(owner.get("pid")) is not int
            or owner["pid"] < 1
            or any(
                not isinstance(owner.get(key), str) or not owner[key].strip()
                for key in ("session_id", "host", "process_started")
            )
        ):
            raise LeaseError(f"lease corrupto {path.name}: schema/owner inválido")
        try:
            uuid.UUID(record["operation"])
            datetime.datetime.fromisoformat(record["created"])
        except (ValueError, TypeError) as exc:
            raise LeaseError(f"lease corrupto {path.name}: identidad/fecha inválida") from exc
        integrity = record.get("integrity")
        if (
            not isinstance(integrity, str)
            or len(integrity) != 64
            or not hmac.compare_digest(integrity, self._record_integrity(record))
        ):
            raise LeaseError(f"lease corrupto {path.name}: integridad inválida")
        return record

    def _read(self, path):
        if path.is_symlink():
            raise LeaseError(f"lease corrupto {path.name}: symlink no permitido")
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise LeaseError(f"lease ilegible {path.name}: {exc}") from exc
        try:
            record = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LeaseError(f"lease corrupto {path.name}: JSON inválido") from exc
        return self._validate_record(path, record)

    @staticmethod
    def _unlink_durable(path):
        path.unlink(missing_ok=True)
        _fsync_directory(path.parent)

    def _owner_alive(self, owner):
        if owner.get("host") != self.host:
            return None
        pid = owner.get("pid")
        if not isinstance(pid, int):
            return False
        if not _pid_vivo(pid):
            return False
        return process_start_marker(pid) == owner.get("process_started")

    def _active_records(self):
        self._ensure_directory(self.active, "raíz active de leases")
        records = []
        for path in self.active.glob("*.json"):
            record = self._read(path)
            if not record:
                continue
            alive = self._owner_alive(record.get("owner", {}))
            if alive is False:
                self._unlink_durable(path)
                continue
            records.append(record)
        return records

    @staticmethod
    def _conflict(first, second):
        return first == second or first == "workspace" or second == "workspace"

    def _next_fencing(self, scope):
        self._ensure_directory(self.fencing, "raíz fencing de leases")
        path = self.fencing / f"{_scope_key(scope)}.counter"
        if path.is_symlink():
            raise LeaseError(f"contador de fencing corrupto para {scope}: symlink")
        if path.exists():
            try:
                raw = path.read_text(encoding="ascii").strip()
                current = int(raw)
            except (OSError, ValueError) as exc:
                raise LeaseError(f"contador de fencing corrupto para {scope}") from exc
            if current < 1 or raw != str(current):
                raise LeaseError(f"contador de fencing corrupto para {scope}")
        else:
            current = 0
        following = current + 1
        descriptor, temporal = tempfile.mkstemp(prefix=".counter.", dir=str(path.parent))
        try:
            with os.fdopen(descriptor, "w", encoding="ascii") as stream:
                stream.write(f"{following}\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporal, path)
            _fsync_directory(path.parent)
        finally:
            if os.path.exists(temporal):
                os.unlink(temporal)
        return following

    def acquire(self, scopes):
        if isinstance(scopes, str):
            requested = [scopes]
        else:
            requested = list(dict.fromkeys(scopes))
        if not requested or any(
            not isinstance(scope, str)
            or not scope.strip()
            or scope != scope.strip()
            or any(ord(character) < 32 for character in scope)
            for scope in requested
        ):
            raise LeaseError("se necesita al menos un scope de lease no vacío")
        with self._coordinator():
            active = self._active_records()
            for existing in active:
                for wanted in requested:
                    if self._conflict(existing["scope"], wanted):
                        owner = existing.get("owner", {})
                        raise LeaseBusy(
                            f"scope {wanted} ocupado por sesión "
                            f"{owner.get('session_id', '?')} en {owner.get('host', '?')}"
                        )
            operation = str(uuid.uuid4())
            records = []
            owner = {
                "session_id": self.session_id,
                "host": self.host,
                "pid": self.pid,
                "process_started": self.process_started,
            }
            try:
                for scope in requested:
                    record = {
                        "format": 1,
                        "scope": scope,
                        "operation": operation,
                        "fencing": self._next_fencing(scope),
                        "created": ahora(),
                        "owner": owner,
                    }
                    record["integrity"] = self._record_integrity(record)
                    self._validate_record(self._path(scope), record)
                    # Se añade antes de publicar: si replace ya ocurrió pero falló el fsync,
                    # el rollback todavía conoce exactamente qué registro puede retirar.
                    records.append(record)
                    _write_json_atomic(self._path(scope), record)
            except Exception:
                for published in reversed(records):
                    path = self._path(published["scope"])
                    try:
                        current = self._read(path)
                    except LeaseError:
                        continue
                    if self._same_record(current, published):
                        self._unlink_durable(path)
                raise
            return LeaseGroup(self, records)

    @staticmethod
    def _same_record(current, expected):
        return bool(
            current
            and current.get("scope") == expected.get("scope")
            and current.get("fencing") == expected.get("fencing")
            and current.get("operation") == expected.get("operation")
            and current.get("owner") == expected.get("owner")
            and current.get("integrity") == expected.get("integrity")
        )

    def _assert_records(self, records):
        with self._coordinator():
            for expected in records:
                if not self._same_record(self._read(self._path(expected["scope"])), expected):
                    raise LeaseLost(
                        f"autoridad perdida para {expected['scope']} "
                        f"(fencing {expected['fencing']})"
                    )

    def _release_records(self, records):
        with self._coordinator():
            for expected in records:
                path = self._path(expected["scope"])
                if self._same_record(self._read(path), expected):
                    self._unlink_durable(path)
