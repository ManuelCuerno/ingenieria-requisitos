#!/usr/bin/env python3
"""Control plane hermético para tests, recursos efímeros y evidencia causal.

Solo stdlib. La aplicación llama a :func:`assert_safe_test_target` (o usa
``connect_if_safe``) *antes* de abrir sockets. La CLI permite reutilizar el mismo contrato desde
scripts de CI sin duplicar regex permisivas.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shlex
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SAFE_ENVS = {"local", "test", "testing", "e2e", "ci"}
PRODUCTION_MARKERS = {"prod", "production", "live", "principal"}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}
SECRET_KEY = re.compile(
    r"(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|"
    r"authorization|cookie|set[_-]?cookie|dsn|database[_-]?url|db[_-]?url)", re.I
)
TEST_NAME = re.compile(r"(?:^|[-_])(test|testing|e2e|ci)(?:[-_]|$)", re.I)
PRODUCTION_NAME = re.compile(
    r"(?:^|[-_.])(?:prod(?:uction)?|live|principal)\d*(?:[-_.]|$)", re.I
)


def pid_vivo(pid):
    """True si existe un proceso local con ese PID.

    En Windows NO vale os.kill(pid, 0): allí cualquier señal que no sea de
    consola TERMINA el proceso vía TerminateProcess en vez de sondearlo.
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


class ControlPlaneError(ValueError):
    pass


class UnsafeTestTarget(ControlPlaneError):
    pass


class IdentityMismatch(ControlPlaneError):
    pass


class InvalidEvidence(ControlPlaneError):
    pass


class InvalidManifest(ControlPlaneError):
    pass


def _redact_url(match):
    raw = match.group(0)
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return "<url-redacted>"
    hostname = parsed.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    try:
        port = parsed.port
    except ValueError:
        return "<url-redacted>"
    if port:
        hostname += f":{port}"
    netloc = f"***@{hostname}" if parsed.username is not None else hostname
    query = urlencode([
        (key, "***" if SECRET_KEY.search(key) else value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
    ])
    fragment = "***" if SECRET_KEY.search(parsed.fragment) else parsed.fragment
    return urlunsplit((parsed.scheme, netloc, parsed.path, query, fragment))


def redact_secrets(value):
    """Redacta secretos frecuentes sin exigir que el texto sea una URL válida."""
    text = str(value)
    text = re.sub(r"[a-z][a-z0-9+.-]*://[^\s]+", _redact_url, text, flags=re.I)
    nombres = (
        r"authorization|cookie|set[-_]?cookie|password|passwd|pwd|secret|token|"
        r"api[-_]?key|access[-_]?key|private[-_]?key|(?:database|db)[-_]?(?:url|dsn)|dsn"
    )
    # Cabeceras concatenadas en una sola línea: para antes de la siguiente clave sensible.
    text = re.sub(
        rf"(?i)\b({nombres})\s*:\s*.*?(?=\s+\b(?:{nombres})\s*[:=]|$)",
        lambda match: f"{match.group(1)}: ***",
        text,
    )
    text = re.sub(
        rf'(?i)(["\']?(?:{nombres})["\']?\s*:\s*)["\'][^"\']*["\']',
        lambda match: f'{match.group(1)}"***"',
        text,
    )
    text = re.sub(
        rf"(?i)\b({nombres})\s*=\s*(?:'[^']*'|\"[^\"]*\"|[^\s&;]+)",
        lambda match: f"{match.group(1)}=***",
        text,
    )
    text = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+", "Bearer ***", text)
    return text


class _SalidaRedactada:
    """Envoltorio de un stream de texto que pasa todo lo escrito por redact_secrets.

    Es el embudo único: con él instalado, ningún print de un script puede sacar
    una credencial por consola aunque el texto venga de datos del usuario.
    Redacta línea a línea (bufferiza la línea incompleta) para que los patrones
    multi-token de redact_secrets vean unidades coherentes."""

    def __init__(self, original):
        self._original = original
        self._pendiente = ""

    def write(self, texto):
        self._pendiente += str(texto)
        *completas, self._pendiente = self._pendiente.split("\n")
        for linea in completas:
            self._original.write(redact_secrets(linea) + "\n")
        return len(texto)

    def flush(self):
        if self._pendiente:
            self._original.write(redact_secrets(self._pendiente))
            self._pendiente = ""
        self._original.flush()

    def __getattr__(self, nombre):
        return getattr(self._original, nombre)


def redactar_salidas():
    """Instala el redactor en stdout y stderr del proceso (idempotente)."""
    for nombre in ("stdout", "stderr"):
        actual = getattr(sys, nombre)
        if not isinstance(actual, _SalidaRedactada):
            setattr(sys, nombre, _SalidaRedactada(actual))


def _slug(value, fallback="run"):
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")
    return normalized or fallback


def _canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class TargetFingerprint:
    def __init__(self, environment, host, database, fingerprint):
        self.environment = environment
        self.host = host
        self.database = database
        self.fingerprint = fingerprint

    def describe(self):
        return f"env={self.environment} host={self.host} database={self.database} fingerprint={self.fingerprint}"


def _dsn_parts(raw):
    raw = (raw or "").strip()
    if not raw:
        return "", ""
    if "://" in raw:
        parsed = urlsplit(raw)
        return (parsed.hostname or ""), parsed.path.lstrip("/").split("/", 1)[0]
    try:
        tokens = shlex.split(raw)
    except ValueError:
        tokens = raw.split()
    pairs = {}
    for token in tokens:
        if "=" in token:
            key, value = token.split("=", 1)
            pairs[key.lower()] = value
    return pairs.get("host", ""), pairs.get("dbname", pairs.get("database", ""))


def _first(env, names):
    for name in names:
        value = env.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def assert_safe_test_target(env, *, expected_namespace="", allow_hosts=()):
    """Valida un destino antes de conectar y devuelve una huella sin credenciales.

    Un host remoto necesita allowlist exacta. La allowlist no puede convertir un entorno o una
    base productivos en target de test.
    """
    safe_env = {str(key): str(value) for key, value in dict(env).items()}
    environment = _first(safe_env, ("APP_ENV", "ENV", "ENVIRONMENT", "STAGE", "NODE_ENV"))
    dsn = _first(safe_env, ("DATABASE_URL", "DB_URL", "DATABASE_DSN", "DB_DSN", "DSN"))
    dsn_host, dsn_database = _dsn_parts(dsn)
    host = _first(safe_env, ("DB_HOST", "DATABASE_HOST", "PGHOST")) or dsn_host
    database = _first(safe_env, ("DB_NAME", "DATABASE_NAME", "PGDATABASE")) or dsn_database
    problems = []
    env_normalized = environment.lower()
    if env_normalized not in SAFE_ENVS:
        problems.append(f"entorno no seguro: {environment or '<vacío>'}")
    if env_normalized in PRODUCTION_MARKERS or PRODUCTION_NAME.search(env_normalized):
        problems.append("entorno productivo")
    host_normalized = host.lower().rstrip(".")
    allowed = {str(item).lower().rstrip(".") for item in allow_hosts}
    if not host_normalized:
        problems.append("host ausente")
    elif PRODUCTION_NAME.search(host_normalized):
        problems.append(f"host productivo: {host}")
    elif host_normalized not in LOCAL_HOSTS and host_normalized not in allowed:
        problems.append(f"host remoto sin allowlist: {host}")
    if not database:
        problems.append("base ausente")
    elif PRODUCTION_NAME.search(database):
        problems.append(f"base productiva: {database}")
    elif not TEST_NAME.search(database):
        problems.append(f"base sin marcador test/e2e/ci: {database}")
    if expected_namespace:
        expected = _slug(expected_namespace)
        comparable = _slug(database)
        if expected not in comparable:
            problems.append(f"base fuera del namespace esperado: {expected}")
    if problems:
        # Nunca serializa el entorno completo: puede contener cookies, cabeceras o secretos con
        # nombres aún desconocidos. Solo salen los tres campos que el guard ha interpretado.
        context = redact_secrets(_canonical_json({
            "environment": environment,
            "host": host,
            "database": database,
        }))
        raise UnsafeTestTarget(redact_secrets("; ".join(problems) + f"; target={context}"))
    target = {
        "environment": env_normalized,
        "host": host_normalized,
        "database": database.lower(),
    }
    fingerprint = hashlib.sha256(_canonical_json(target).encode()).hexdigest()[:20]
    return TargetFingerprint(env_normalized, host_normalized, database.lower(), fingerprint)


def connect_if_safe(connector, env, **guard_options):
    """Ejecuta el conector únicamente después de que el guard haya terminado en verde."""
    target = assert_safe_test_target(env, **guard_options)
    return connector(), target


class RunIdentity:
    def __init__(self, repo, unit, run):
        self.repo = _slug(repo, "repo")
        self.unit = _slug(unit, "unit")
        self.run = _slug(run, "run")
        canonical = _canonical_json({"repo": self.repo, "unit": self.unit, "run": self.run})
        self.fingerprint = hashlib.sha256(canonical.encode()).hexdigest()[:20]
        readable = f"{self.repo}-{self.unit}-{self.run}"
        room = 48 - 1 - 10
        self.namespace = f"{readable[:room].strip('-')}-{self.fingerprint[:10]}"

    def database(self, base="app"):
        prefix = re.sub(r"[^a-z0-9_]+", "_", _slug(base).replace("-", "_"))
        namespace = self.namespace.replace("-", "_")
        suffix = f"_{self.fingerprint[:10]}"
        body = f"{prefix}_test_{namespace}"
        return (body[:63 - len(suffix)].rstrip("_") + suffix)[:63]

    def port(self, low=20000, high=39999):
        if low < 1 or high > 65535 or low > high:
            raise ValueError("rango de puertos inválido")
        return low + (int(self.fingerprint[:12], 16) % (high - low + 1))

    def docker_name(self, service="app"):
        service = _slug(service, "app")
        suffix = f"-{self.fingerprint[:10]}"
        body = f"{service}-{self.namespace}"
        return body[:63 - len(suffix)].rstrip("-") + suffix

    def docker_tag(self, image="app"):
        image = str(image).strip()
        if not image or image.endswith(":latest"):
            raise ValueError("la imagen debe tener nombre y nunca usar :latest")
        image = image.rsplit(":", 1)[0] if ":" in image.rsplit("/", 1)[-1] else image
        return f"{image}:test-{self.namespace}"

    def temp_path(self, root):
        return Path(root) / f"control-plane-{self.namespace}"

    def log_path(self, root):
        return Path(root) / f"control-plane-{self.namespace}.log"

    def as_dict(self):
        return {
            "repo": self.repo,
            "unit": self.unit,
            "run": self.run,
            "namespace": self.namespace,
            "fingerprint": self.fingerprint,
        }

    def assert_preview_identity(self, observed):
        actual = dict(observed).get("fingerprint")
        if actual != self.fingerprint:
            raise IdentityMismatch(
                f"preview ajeno: esperado {self.fingerprint}, observado {actual or '<ausente>'}"
            )


class EvidenceRun:
    def __init__(self, phase, target_fingerprint, passed):
        if type(passed) is not bool:
            raise InvalidEvidence("passed debe ser bool exacto")
        self.phase = phase
        self.target_fingerprint = target_fingerprint
        self.passed = passed

    def __repr__(self):
        return f"EvidenceRun({self.phase!r}, {self.target_fingerprint!r}, {self.passed!r})"


class EvidenceContract:
    EXPECTED = {"legacy": False, "new": True, "mutant": False}

    def __init__(self, claim, target_fingerprint):
        self.claim = str(claim).strip()
        self.target_fingerprint = str(target_fingerprint).strip()
        if not self.claim or not self.target_fingerprint:
            raise InvalidEvidence("claim y target fingerprint son obligatorios")

    def verify(self, runs):
        indexed = {}
        for run in runs:
            if run.phase in indexed or run.phase not in self.EXPECTED:
                raise InvalidEvidence(f"fase de evidencia inválida o repetida: {run.phase}")
            if run.target_fingerprint != self.target_fingerprint:
                raise InvalidEvidence(f"{run.phase}: target fingerprint distinto")
            indexed[run.phase] = run
        if set(indexed) != set(self.EXPECTED):
            raise InvalidEvidence("se requieren exactamente legacy, new y mutant")
        wrong = [phase for phase, expected in self.EXPECTED.items()
                 if indexed[phase].passed is not expected]
        if wrong:
            raise InvalidEvidence("control causal inválido: " + ", ".join(wrong))
        return True


class BudgetViolation:
    def __init__(self, code, observed, limit):
        self.code = code
        self.observed = observed
        self.limit = limit


class ClosePolicy:
    def __init__(self, name, require_merge, require_user_ok, require_fresh_review,
                 require_discard, test_scope, first_artifact_seconds, close_seconds,
                 max_overhead_ratio):
        self.name = name
        self.require_merge = require_merge
        self.require_user_ok = require_user_ok
        self.require_fresh_review = require_fresh_review
        self.require_discard = require_discard
        self.test_scope = test_scope
        self.first_artifact_seconds = first_artifact_seconds
        self.close_seconds = close_seconds
        self.max_overhead_ratio = max_overhead_ratio

    def budget_violations(self, *, first_artifact_seconds, close_seconds,
                          method_seconds, total_seconds):
        violations = []
        if first_artifact_seconds > self.first_artifact_seconds:
            violations.append(BudgetViolation(
                "first_artifact", first_artifact_seconds, self.first_artifact_seconds))
        if close_seconds > self.close_seconds:
            violations.append(BudgetViolation("method_close", close_seconds, self.close_seconds))
        ratio = method_seconds / total_seconds if total_seconds > 0 else float("inf")
        if ratio > self.max_overhead_ratio:
            violations.append(BudgetViolation(
                "method_overhead", ratio, self.max_overhead_ratio))
        return violations


_POLICIES = {
    "documental": ClosePolicy("documental", False, False, True, False,
                               "document", 30, 120, 0.25),
    "prototipo": ClosePolicy("prototipo", False, False, False, True,
                              "smoke", 300, 600, 0.20),
    "expres": ClosePolicy("expres", False, False, False, False,
                           "area", 30, 120, 0.20),
    "directo": ClosePolicy("directo", True, True, True, False,
                            "area", 300, 900, 0.20),
    "normal": ClosePolicy("normal", True, True, True, False,
                           "area+full", 900, 1800, 0.25),
}


def close_policy(route):
    normalized = _slug(route)
    try:
        return _POLICIES[normalized]
    except KeyError as exc:
        raise ValueError(f"ruta desconocida: {route}") from exc


def validate_close_receipt(receipt, *, route, expected_target_fingerprint=""):
    """Valida evidencia ejecutable y presupuesto antes de permitir un cierre opt-in."""
    if not isinstance(receipt, dict) or receipt.get("version") != 1:
        raise InvalidEvidence("recibo: version 1 obligatoria")
    try:
        policy = close_policy(route)
    except ValueError as exc:
        raise InvalidEvidence("recibo: ruta desconocida") from exc
    if receipt.get("route") != policy.name:
        raise InvalidEvidence("recibo: ruta distinta de la unidad")
    if receipt.get("test_scope") != policy.test_scope:
        raise InvalidEvidence("recibo: scope de pruebas insuficiente")
    raw_target = receipt.get("target_fingerprint")
    target = raw_target.strip() if isinstance(raw_target, str) else ""
    if not target or (expected_target_fingerprint and target != expected_target_fingerprint):
        raise InvalidEvidence("recibo: target fingerprint distinto o ausente")
    raw_runs = receipt.get("runs")
    if not isinstance(raw_runs, list):
        raise InvalidEvidence("recibo: runs obligatorios")
    runs = []
    for raw in raw_runs:
        if not isinstance(raw, dict):
            raise InvalidEvidence("recibo: run inválido")
        raw_command = raw.get("command")
        raw_digest = raw.get("output_digest")
        command = raw_command.strip() if isinstance(raw_command, str) else ""
        digest = raw_digest.strip().lower() if isinstance(raw_digest, str) else ""
        exit_code = raw.get("exit_code")
        if not command or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise InvalidEvidence("recibo: command y output_digest SHA-256 son obligatorios")
        if type(exit_code) is not int:
            raise InvalidEvidence("recibo: exit_code debe ser entero")
        run = EvidenceRun(raw.get("phase"), raw.get("target_fingerprint"), raw.get("passed"))
        if run.passed != (exit_code == 0):
            raise InvalidEvidence(f"recibo: {run.phase} contradice su exit_code")
        runs.append(run)
    EvidenceContract(receipt.get("claim", ""), target).verify(runs)
    metrics = receipt.get("metrics")
    if not isinstance(metrics, dict):
        raise InvalidEvidence("recibo: metrics obligatorias")
    names = ("first_artifact_seconds", "close_seconds", "method_seconds", "total_seconds")
    if any(
        type(metrics.get(name)) not in {int, float}
        or not math.isfinite(metrics[name])
        or metrics[name] < 0
        for name in names
    ):
        raise InvalidEvidence("recibo: métricas finitas no negativas obligatorias")
    violations = policy.budget_violations(**{name: metrics[name] for name in names})
    if violations:
        raise InvalidEvidence(
            "recibo fuera de presupuesto: " + ", ".join(item.code for item in violations)
        )
    return True


def _find_secret_key(value, path=""):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if SECRET_KEY.search(str(key)):
                return child_path
            found = _find_secret_key(child, child_path)
            if found:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _find_secret_key(child, f"{path}[{index}]")
            if found:
                return found
    return ""


def validate_manifest(manifest, *, trusted_allow_hosts=()):
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        raise InvalidManifest("manifiesto: version 1 obligatoria")
    secret_path = _find_secret_key(manifest)
    if secret_path:
        raise InvalidManifest(f"manifiesto contiene campo secreto: {secret_path}")
    identity = manifest.get("identity")
    if not isinstance(identity, dict):
        raise InvalidManifest("manifiesto: identity obligatoria")
    try:
        expected = RunIdentity(identity["repo"], identity["unit"], identity["run"])
    except (KeyError, TypeError) as exc:
        raise InvalidManifest("manifiesto: identity incompleta") from exc
    if identity.get("namespace") != expected.namespace or identity.get("fingerprint") != expected.fingerprint:
        raise InvalidManifest("manifiesto: identidad no reproducible")
    targets = manifest.get("targets")
    if not isinstance(targets, list) or not targets:
        raise InvalidManifest("manifiesto: targets no puede estar vacío")
    for index, target in enumerate(targets):
        if not isinstance(target, dict) or not str(target.get("fingerprint", "")).strip():
            raise InvalidManifest(f"manifiesto: target {index} sin fingerprint")
        if target.get("allow_hosts"):
            raise InvalidManifest(
                f"manifiesto: target {index} no puede autorizar su propio host"
            )
        try:
            observed = assert_safe_test_target({
                "APP_ENV": target.get("env", ""),
                "DB_HOST": target.get("host", ""),
                "DB_NAME": target.get("database", ""),
            }, expected_namespace=expected.namespace,
               allow_hosts=set(trusted_allow_hosts))
        except UnsafeTestTarget as exc:
            raise InvalidManifest(f"manifiesto: target {index} inseguro: {exc}") from exc
        if target.get("fingerprint") != observed.fingerprint:
            raise InvalidManifest(f"manifiesto: target {index} fingerprint no corresponde")
    return True


def _main_guard(args):
    env = json.loads(Path(args.env_json).read_text(encoding="utf-8"))
    target = assert_safe_test_target(
        env, expected_namespace=args.namespace, allow_hosts=set(args.allow_host))
    print(target.fingerprint)
    return 0


def _main_identity(args):
    print(json.dumps(RunIdentity(args.repo, args.unit, args.run).as_dict(), sort_keys=True))
    return 0


def _main_manifest(args):
    manifest = json.loads(Path(args.path).read_text(encoding="utf-8"))
    validate_manifest(manifest, trusted_allow_hosts=set(args.allow_host))
    print("OK control-plane")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Guard e identidad herméticos para test/CI")
    sub = parser.add_subparsers(dest="command", required=True)
    guard = sub.add_parser("guard-test")
    guard.add_argument("--env-json", required=True)
    guard.add_argument("--namespace", default="")
    guard.add_argument("--allow-host", action="append", default=[])
    guard.set_defaults(func=_main_guard)
    identity = sub.add_parser("identity")
    identity.add_argument("--repo", required=True)
    identity.add_argument("--unit", required=True)
    identity.add_argument("--run", required=True)
    identity.set_defaults(func=_main_identity)
    manifest = sub.add_parser("validate-manifest")
    manifest.add_argument("path")
    manifest.add_argument("--allow-host", action="append", default=[])
    manifest.set_defaults(func=_main_manifest)
    args = parser.parse_args()
    try:
        return args.func(args)
    except (ControlPlaneError, OSError, json.JSONDecodeError) as exc:
        print(f"FAIL {redact_secrets(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
