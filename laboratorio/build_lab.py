from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


LAB_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = LAB_DIR.parent
COMPOSE_FILE = LAB_DIR / "docker-compose.yml"
FORBIDDEN_BACKUP_DIR = LAB_DIR / "backups"
DEFAULT_ENV_FILE = LAB_DIR / ".env"
ROOT_ENV_FILE = PROJECT_ROOT / ".env"
NETWORK_NAME = "docker_labbox_default-ol8"

TENABLESC_CONTAINER = "tenablesc-labbox-ol8"
NESSUS_CONTAINER = "nessus_8835"

LAB_CONTAINERS = {
    TENABLESC_CONTAINER: {
        "image": "tenablesc-labbox-image-ol8",
        "url": "https://localhost:8443",
        "data_path": "/opt/sc",
    },
    NESSUS_CONTAINER: {
        "image": "tenable/nessus:latest-ubuntu",
        "url": "https://localhost:8835",
        "data_path": "/opt/nessus",
    },
}

LAB_IMAGES = {
    "tenablesc-labbox-image-ol8": "tenablesc-labbox-image-ol8.tar",
    "tenable/nessus:latest-ubuntu": "tenable-nessus-latest-ubuntu.tar",
}
LABBOX_ZIP_IMAGE = "labbox-docker/tenablesc-labbox-image-ol8.image"
LABBOX_ZIP_UTILS_PREFIX = "labbox-docker/utils/"
DEFAULT_LABBOX_ZIP = LAB_DIR / "labbox-docker.zip"
LABBOX_UTILS_DIR = LAB_DIR / "labbox-utils"

INCIDENT_CATALOG = {
    "docker_unavailable": {
        "severity": "critical",
        "repair": "manual",
        "description": "Docker no responde o Docker Desktop no esta arrancado.",
    },
    "network_missing": {
        "severity": "critical",
        "repair": "up",
        "description": f"La red Docker externa {NETWORK_NAME} no existe.",
    },
    "image_missing": {
        "severity": "critical",
        "repair": "load-images",
        "description": "Falta una imagen requerida del laboratorio.",
    },
    "container_missing": {
        "severity": "critical",
        "repair": "up",
        "description": "Falta un contenedor esperado del laboratorio.",
    },
    "container_stopped": {
        "severity": "critical",
        "repair": "up",
        "description": "Un contenedor esperado existe pero no esta corriendo.",
    },
    "tenablesc_shm_small": {
        "severity": "critical",
        "repair": "recreate-with-compose",
        "description": "Tenable.sc necesita /dev/shm >= 1GB para Postgres/importaciones.",
    },
    "tenablesc_user_invalid": {
        "severity": "critical",
        "repair": "runtime",
        "description": "El usuario tns no existe o no tiene UID/GID 250.",
    },
    "tenablesc_locale_missing": {
        "severity": "critical",
        "repair": "runtime",
        "description": "Falta la locale en_US.UTF-8 requerida por PostgreSQL.",
    },
    "tenablesc_supervisor_bad": {
        "severity": "critical",
        "repair": "runtime",
        "description": "Supervisor no tiene Apache y Jobd en RUNNING.",
    },
    "tenablesc_postgres_down": {
        "severity": "critical",
        "repair": "postgres",
        "description": "PostgreSQL interno de Tenable.sc no responde.",
    },
    "tenablesc_redis_down": {
        "severity": "critical",
        "repair": "runtime",
        "description": "Redis interno no responde en 127.0.0.1:6379.",
    },
    "tenablesc_websocket_down": {
        "severity": "warning",
        "repair": "runtime",
        "description": "WebSocket interno no esta levantado en Tenable.sc.",
    },
    "tenablesc_asset_service_down": {
        "severity": "critical",
        "repair": "runtime",
        "description": "sc-asset-svc no esta corriendo.",
    },
    "tenablesc_asset_artifacts_missing": {
        "severity": "critical",
        "repair": "assets",
        "description": "Faltan artefactos internos de Asset Lists.",
    },
    "tenablesc_api_unavailable": {
        "severity": "critical",
        "repair": "runtime",
        "description": "La API de Tenable.sc no responde o no autentica.",
    },
    "tenablesc_analysis_asset_filter_bad": {
        "severity": "critical",
        "repair": "assets",
        "description": "Analysis falla al filtrar por assetID.",
    },
    "tenablesc_scan_import_errors": {
        "severity": "warning",
        "repair": "inspect",
        "description": "Hay scan results con importStatus=Error o error similar.",
    },
    "nessus_service_down": {
        "severity": "critical",
        "repair": "nessus",
        "description": "Nessus no tiene nessus-service/nessusd corriendo.",
    },
    "nessus_port_closed": {
        "severity": "critical",
        "repair": "nessus",
        "description": "El puerto local 8835 de Nessus no acepta conexiones.",
    },
    "recent_known_errors": {
        "severity": "warning",
        "repair": "inspect",
        "description": "Los logs recientes contienen patrones de error conocidos.",
    },
}


class LabError(RuntimeError):
    pass


def run(
    args: list[str],
    *,
    cwd: Path = PROJECT_ROOT,
    capture: bool = True,
    check: bool = True,
    stdin_text: str | None = None,
    stdin_file: Path | None = None,
    stdout_file: Path | None = None,
) -> subprocess.CompletedProcess[bytes]:
    stdout_target: int | Any = subprocess.PIPE if capture else None
    stdout_handle = None
    stdin_handle = None
    if stdin_text is not None and stdin_file is not None:
        raise LabError("stdin_text and stdin_file are mutually exclusive")
    if stdout_file is not None:
        stdout_file.parent.mkdir(parents=True, exist_ok=True)
        stdout_handle = stdout_file.open("wb")
        stdout_target = stdout_handle
    stdin_target: int | Any = None
    stdin_bytes = stdin_text.encode("utf-8") if stdin_text is not None else None
    if stdin_file is not None:
        stdin_handle = stdin_file.open("rb")
        stdin_target = stdin_handle
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd),
            input=stdin_bytes,
            stdin=stdin_target,
            stdout=stdout_target,
            stderr=subprocess.PIPE,
            check=False,
        )
    finally:
        if stdout_handle is not None:
            stdout_handle.close()
        if stdin_handle is not None:
            stdin_handle.close()
    if check and completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace")
        raise LabError(f"Command failed ({completed.returncode}): {' '.join(args)}\n{stderr}")
    return completed


def text(completed: subprocess.CompletedProcess[bytes]) -> str:
    return completed.stdout.decode("utf-8", errors="replace").strip()


def decoded(completed: subprocess.CompletedProcess[bytes]) -> dict[str, Any]:
    return {
        "ok": completed.returncode == 0,
        "stdout": text(completed),
        "stderr": completed.stderr.decode("utf-8", errors="replace").strip(),
    }


def docker_available() -> bool:
    try:
        run(["docker", "version", "--format", "{{.Server.Version}}"], check=True)
    except (OSError, LabError):
        return False
    return True


def docker_exec(
    container: str,
    command: str,
    *,
    user: str | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    args = ["docker", "exec"]
    if user:
        args += ["-u", user]
    args += [container, "sh", "-lc", command]
    return run(args, check=check)


def docker_exec_script(
    container: str,
    script: str,
    *,
    user: str | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    args = ["docker", "exec", "-i"]
    if user:
        args += ["-u", user]
    args += [container, "/bin/bash"]
    return run(args, stdin_text=script, check=check)


def image_exists(image: str) -> bool:
    return run(["docker", "image", "inspect", image], check=False).returncode == 0


def network_exists(name: str) -> bool:
    return run(["docker", "network", "inspect", name], check=False).returncode == 0


def ensure_network() -> None:
    if not network_exists(NETWORK_NAME):
        run(["docker", "network", "create", NETWORK_NAME], capture=False)


def container_inspect(name: str) -> dict[str, Any] | None:
    completed = run(["docker", "inspect", name], check=False)
    if completed.returncode != 0:
        return None
    payload = json.loads(text(completed))
    return payload[0] if payload else None


def container_state(name: str) -> dict[str, Any]:
    inspect = container_inspect(name)
    if inspect is None:
        return {"name": name, "exists": False, "running": False}
    state = inspect.get("State", {})
    return {
        "name": name,
        "exists": True,
        "running": bool(state.get("Running")),
        "status": state.get("Status"),
        "image": inspect.get("Config", {}).get("Image"),
        "ports": inspect.get("NetworkSettings", {}).get("Ports"),
        "mounts": [
            {
                "type": mount.get("Type"),
                "name": mount.get("Name"),
                "source": mount.get("Source"),
                "destination": mount.get("Destination"),
            }
            for mount in inspect.get("Mounts", [])
        ],
    }


def compose_command() -> list[str]:
    if run(["docker", "compose", "version"], check=False).returncode == 0:
        return ["docker", "compose"]
    if run(["docker-compose", "version"], check=False).returncode == 0:
        return ["docker-compose"]
    raise LabError("Docker Compose is not available")


def env_file_for_compose() -> Path:
    if DEFAULT_ENV_FILE.exists():
        return DEFAULT_ENV_FILE
    if ROOT_ENV_FILE.exists():
        return ROOT_ENV_FILE
    return LAB_DIR / ".env.example"


def ensure_portable_env() -> dict[str, Any]:
    if DEFAULT_ENV_FILE.exists():
        return {"path": str(DEFAULT_ENV_FILE), "created": False, "source": str(DEFAULT_ENV_FILE)}
    source = ROOT_ENV_FILE if ROOT_ENV_FILE.exists() else LAB_DIR / ".env.example"
    if not source.exists():
        raise LabError(f"Missing env template/source: {source}")
    lines = source.read_text(encoding="utf-8").splitlines()
    output: list[str] = []
    replaced = False
    for line in lines:
        if line.startswith("LABBOX_UTILS_PATH="):
            output.append("LABBOX_UTILS_PATH=./labbox-utils")
            replaced = True
        else:
            output.append(line)
    if not replaced:
        output.append("LABBOX_UTILS_PATH=./labbox-utils")
    DEFAULT_ENV_FILE.write_text("\n".join(output) + "\n", encoding="utf-8")
    return {"path": str(DEFAULT_ENV_FILE), "created": True, "source": str(source)}


def tcp_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def add_incident(incidents: list[dict[str, Any]], code: str, detail: str = "") -> None:
    meta = INCIDENT_CATALOG.get(code, {})
    incidents.append(
        {
            "code": code,
            "severity": meta.get("severity", "warning"),
            "repair": meta.get("repair", "inspect"),
            "description": meta.get("description", ""),
            "detail": detail,
        }
    )


def supervisor_ok(stdout: str) -> bool:
    expected = {"TenableSC:Apache": False, "TenableSC:Jobd": False}
    for line in stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] in expected and parts[1] == "RUNNING":
            expected[parts[0]] = True
    return all(expected.values())


def load_env(path: Path | None = None) -> dict[str, str]:
    env_path = path or env_file_for_compose()
    result: dict[str, str] = {}
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip().strip('"').strip("'")
    merged = dict(os.environ)
    merged.update({k: v for k, v in result.items() if k not in os.environ})
    return merged


class TenableSCAPI:
    def __init__(self, env: dict[str, str]) -> None:
        self.base_url = env.get("TENABLE_SC_URL", "https://localhost:8443").rstrip("/")
        self.auth_mode = env.get("TENABLE_SC_AUTH_MODE", "session").strip().lower()
        self.username = env.get("TENABLE_SC_USERNAME", "")
        self.password = env.get("TENABLE_SC_PASSWORD", "")
        self.access_key = env.get("TENABLE_SC_ACCESS_KEY", "")
        self.secret_key = env.get("TENABLE_SC_SECRET_KEY", "")
        self.verify_ssl = env.get("TENABLE_SC_VERIFY_SSL", "true").lower() in {"1", "true", "yes", "on"}
        self.timeout = int(env.get("TENABLE_SC_TIMEOUT", "120") or "120")
        self.token: str | None = None
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "holcim-lab-doctor/1.0",
        }
        self.cookie_jar = http.cookiejar.CookieJar()
        handlers: list[urllib.request.BaseHandler] = [urllib.request.HTTPCookieProcessor(self.cookie_jar)]
        if self.base_url.startswith("https://"):
            context = ssl.create_default_context()
            if not self.verify_ssl:
                context = ssl._create_unverified_context()
            handlers.append(urllib.request.HTTPSHandler(context=context))
        self.opener = urllib.request.build_opener(*handlers)

    def __enter__(self) -> "TenableSCAPI":
        self.login()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.logout()

    def login(self) -> None:
        if self.auth_mode == "api_keys":
            if not self.access_key or not self.secret_key:
                raise LabError("Tenable.sc API keys are missing")
            self.headers["X-APIKey"] = f"accessKey={self.access_key}; secretKey={self.secret_key}"
            return
        if not self.username or not self.password:
            raise LabError("Tenable.sc username/password are missing")
        payload = self.request(
            "POST",
            "token",
            json_body={"username": self.username, "password": self.password},
            authenticated=False,
        )
        token = payload.get("response", {}).get("token")
        if token is None:
            raise LabError("Tenable.sc did not return an auth token")
        self.token = str(token)
        self.headers["X-SecurityCenter"] = self.token

    def logout(self) -> None:
        if self.auth_mode == "session" and self.token:
            try:
                self.request("DELETE", "token")
            except LabError:
                pass

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        clean_path = path.strip("/")
        url = f"{self.base_url}/rest/{clean_path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        data = json.dumps(json_body).encode("utf-8") if json_body is not None else None
        headers = dict(self.headers)
        if not authenticated:
            headers.pop("X-APIKey", None)
            headers.pop("X-SecurityCenter", None)
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise LabError(f"Tenable.sc HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise LabError(f"Tenable.sc connection error: {exc}") from exc
        if payload.get("error_code") not in (None, 0, "0"):
            raise LabError(payload.get("error_msg") or "Tenable.sc API returned an error")
        return payload


def analysis_payload(asset_id: int | str, *, tool: str = "sumip", end_offset: int = 50) -> dict[str, Any]:
    return {
        "type": "vuln",
        "sourceType": "cumulative",
        "query": {
            "type": "vuln",
            "tool": tool,
            "startOffset": 0,
            "endOffset": end_offset,
            "filters": [
                {"filterName": "pluginType", "operator": "=", "value": "compliance"},
                {"filterName": "assetID", "operator": "=", "value": str(asset_id)},
                {"filterName": "repositoryIDs", "operator": "=", "value": "6,8,9,10"},
            ],
        },
    }


def summarize_resource(payload: dict[str, Any], *, sample_size: int = 10) -> dict[str, Any]:
    response = payload.get("response")
    if isinstance(response, list):
        return {"count": len(response), "sample": response[:sample_size]}
    if not isinstance(response, dict):
        return {"type": type(response).__name__, "value": response}
    summary: dict[str, Any] = {}
    for key in ("usable", "manageable"):
        value = response.get(key)
        if isinstance(value, list):
            summary[f"{key}_count"] = len(value)
            summary[f"{key}_sample"] = value[:sample_size]
    for key in ("totalRecords", "returnedRecords"):
        if key in response:
            summary[key] = response.get(key)
    if not summary:
        summary["keys"] = sorted(response.keys())
    return summary


def safe_api_get(client: TenableSCAPI, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        payload = client.request("GET", path, params=params)
    except LabError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, **summarize_resource(payload)}


def api_diagnostics(incidents: list[dict[str, Any]]) -> dict[str, Any]:
    report: dict[str, Any] = {}
    try:
        with TenableSCAPI(load_env()) as client:
            assets = client.request("GET", "asset", params={"fields": "id,name,type,status,ipCount,canUse"})
            audit_files = client.request("GET", "auditFile", params={"fields": "id,name,type,status,uuid"})
            usable_assets = assets.get("response", {}).get("usable", [])
            report["assets_usable_count"] = len(usable_assets)
            report["assets_calculating_like_count"] = len([a for a in usable_assets if "calcul" in str(a).lower()])
            report["audit_files_usable_count"] = len(audit_files.get("response", {}).get("usable", []))
            report["resources"] = {
                "repository": safe_api_get(client, "repository", {"fields": "id,name,type,status,dataFormat,ipCount,running"}),
                "policy": safe_api_get(client, "policy", {"fields": "id,name,type,status,policyTemplate"}),
                "scan": safe_api_get(client, "scan", {"fields": "id,name,status,policy,repository,ipList,assets"}),
                "scanResult": safe_api_get(
                    client,
                    "scanResult",
                    {"fields": "id,name,status,importStatus,importErrorDetails,finishTime,repository"},
                ),
                "scanner": safe_api_get(client, "scanner", {"fields": "id,name,status,ip,port,type,version"}),
            }

            scan_result_summary = report["resources"].get("scanResult", {})
            scan_result_samples: list[dict[str, Any]] = []
            if scan_result_summary.get("ok"):
                scan_result_samples.extend(scan_result_summary.get("usable_sample", []))
                scan_result_samples.extend(scan_result_summary.get("manageable_sample", []))
            import_errors = [
                item
                for item in scan_result_samples
                if "error" in str(item.get("importStatus", "")).lower()
                or str(item.get("importErrorDetails", "")).strip()
            ]
            report["scan_result_import_error_sample"] = import_errors[:10]
            if import_errors:
                add_incident(
                    incidents,
                    "tenablesc_scan_import_errors",
                    f"{len(import_errors)} scan result samples show import errors",
                )

            analysis_results = []
            for asset_id in (14, 24, 118):
                data = client.request("POST", "analysis", json_body=analysis_payload(asset_id))
                response = data.get("response", {})
                analysis_results.append(
                    {
                        "asset_id": asset_id,
                        "tool": "sumip",
                        "total_records": response.get("totalRecords"),
                        "returned_records": response.get("returnedRecords"),
                    }
                )
            details = client.request(
                "POST",
                "analysis",
                json_body=analysis_payload(118, tool="vulndetails", end_offset=50),
            )
            details_response = details.get("response", {})
            analysis_results.append(
                {
                    "asset_id": 118,
                    "tool": "vulndetails",
                    "total_records": details_response.get("totalRecords"),
                    "returned_records": details_response.get("returnedRecords"),
                }
            )
            report["analysis"] = analysis_results
            try:
                details_total = int(details_response.get("totalRecords") or 0)
            except (TypeError, ValueError):
                details_total = 0
            if details_total <= 0:
                add_incident(
                    incidents,
                    "tenablesc_analysis_asset_filter_bad",
                    f"assetID=118 vulndetails returned no records: {details_response.get('totalRecords')}",
                )
    except LabError as exc:
        report["error"] = str(exc)
        add_incident(incidents, "tenablesc_api_unavailable", str(exc))
    return report


def collect_tenablesc_diagnostics(incidents: list[dict[str, Any]]) -> dict[str, Any]:
    report: dict[str, Any] = {"container": container_state(TENABLESC_CONTAINER)}
    container = report["container"]
    if not container.get("exists"):
        add_incident(incidents, "container_missing", TENABLESC_CONTAINER)
        return report
    if not container.get("running"):
        add_incident(incidents, "container_stopped", TENABLESC_CONTAINER)
        return report

    inspect = container_inspect(TENABLESC_CONTAINER) or {}
    shm_size = inspect.get("HostConfig", {}).get("ShmSize")
    report["shm_size_bytes"] = shm_size
    if not shm_size or int(shm_size) < 1024**3:
        add_incident(incidents, "tenablesc_shm_small", str(shm_size))

    commands = {
        "tns_user": "id tns && test \"$(id -u tns)\" = 250 && test \"$(id -g tns)\" = 250",
        "locale_en_us": "locale -a | grep -Eiq '^en_US\\.(utf8|UTF-8)$'",
        "supervisor": "supervisorctl -c /etc/supervisord-tenablesc.conf status",
        "postgres_status": "su -s /bin/bash tns -c 'env LD_LIBRARY_PATH=/opt/sc/support/lib /opt/sc/support/bin/pg_ctl -D /opt/sc/data/postgresql status'",
        "postgres_query": "env LD_LIBRARY_PATH=/opt/sc/support/lib /opt/sc/support/bin/psql -h 127.0.0.1 -p 5432 -U tns -d SecurityCenter -Atc 'select 1'",
        "redis": "/opt/sc/support/bin/redis-cli -h 127.0.0.1 -p 6379 ping",
        "websocket_process": "pgrep -af '/opt/sc/src/WebSocketServer.php'",
        "asset_service_process": "pgrep -af '/opt/sc/bin/services/sc-asset-svc'",
        "microservice_supervisor": "pgrep -af '/opt/sc/bin/services/microservice-supervisor.sh'",
        "asset_artifacts": "test \"$(find /opt/sc/orgs/1/assets -type f -name '*.uuidd' | wc -l)\" -gt 0",
        "repository_files": "find /opt/sc/repositories -maxdepth 2 -type f \\( -name '*.db' -o -name '*.raw' \\) | wc -l",
        "filesystems": "df -h /dev/shm /tmp /opt/sc",
        "process_inventory": "ps -eo user,pid,ppid,stat,comm,args | egrep 'supervisord|httpd|Jobd|postgres|redis-server|WebSocketServer|sc-asset-svc|microservice-supervisor' | grep -v egrep",
        "recent_known_log_errors": "tail -n 500 /opt/sc/admin/logs/202605.log 2>/dev/null | grep -Ei 'Error loading uuid file|redis ping failed|127.0.0.1:5432|127.0.0.1:6379|127.0.0.1:9080' | tail -40 || true",
    }
    checks = {name: decoded(docker_exec(TENABLESC_CONTAINER, command)) for name, command in commands.items()}
    checks["supervisor"]["ok"] = bool(checks["supervisor"]["ok"] and supervisor_ok(checks["supervisor"]["stdout"]))
    report["checks"] = checks

    if not checks["tns_user"]["ok"]:
        add_incident(incidents, "tenablesc_user_invalid", checks["tns_user"]["stderr"])
    if not checks["locale_en_us"]["ok"]:
        add_incident(incidents, "tenablesc_locale_missing")
    if not checks["supervisor"]["ok"]:
        add_incident(incidents, "tenablesc_supervisor_bad", checks["supervisor"]["stdout"])
    if not checks["postgres_status"]["ok"] or not checks["postgres_query"]["ok"]:
        add_incident(incidents, "tenablesc_postgres_down", checks["postgres_status"]["stderr"])
    if not checks["redis"]["ok"] or checks["redis"]["stdout"] != "PONG":
        add_incident(incidents, "tenablesc_redis_down", checks["redis"]["stdout"] or checks["redis"]["stderr"])
    if not checks["websocket_process"]["ok"]:
        add_incident(incidents, "tenablesc_websocket_down")
    if not checks["asset_service_process"]["ok"]:
        add_incident(incidents, "tenablesc_asset_service_down")
    if not checks["asset_artifacts"]["ok"]:
        add_incident(incidents, "tenablesc_asset_artifacts_missing")
    if checks["recent_known_log_errors"]["stdout"]:
        add_incident(incidents, "recent_known_errors", "Recent Tenable.sc log contains known error patterns")

    report["api"] = api_diagnostics(incidents)
    return report


def collect_nessus_diagnostics(incidents: list[dict[str, Any]]) -> dict[str, Any]:
    report: dict[str, Any] = {"container": container_state(NESSUS_CONTAINER)}
    container = report["container"]
    if not container.get("exists"):
        add_incident(incidents, "container_missing", NESSUS_CONTAINER)
        return report
    if not container.get("running"):
        add_incident(incidents, "container_stopped", NESSUS_CONTAINER)
        return report
    commands = {
        "processes": "ps -eo user,pid,ppid,stat,comm,args | egrep 'nessus-service|nessusd' | grep -v egrep",
        "nessuscli_version": "/opt/nessus/sbin/nessuscli --version",
        "logs": "ls -lah /opt/nessus/var/nessus/logs 2>/dev/null | head -80",
        "recent_errors": "tail -n 200 /opt/nessus/var/nessus/logs/nessusd.messages 2>/dev/null | grep -Ei 'error|critical|failed' | tail -30 || true",
    }
    checks = {name: decoded(docker_exec(NESSUS_CONTAINER, command)) for name, command in commands.items()}
    report["checks"] = checks
    if not checks["processes"]["ok"] or "nessusd" not in checks["processes"]["stdout"]:
        add_incident(incidents, "nessus_service_down", checks["processes"]["stdout"])
    if not tcp_open("127.0.0.1", 8835):
        add_incident(incidents, "nessus_port_closed")
    report["host_port_8835_open"] = tcp_open("127.0.0.1", 8835)
    return report


def collect_doctor_report() -> tuple[dict[str, Any], bool]:
    incidents: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "lab_dir": str(LAB_DIR),
        "compose_file": str(COMPOSE_FILE),
        "docker_available": docker_available(),
        "network_exists": False,
        "images": {},
        "containers": {},
        "tenablesc": {},
        "nessus": {},
        "incidents": incidents,
        "incident_catalog": INCIDENT_CATALOG,
    }
    if not report["docker_available"]:
        add_incident(incidents, "docker_unavailable")
        return report, False

    report["network_exists"] = network_exists(NETWORK_NAME)
    if not report["network_exists"]:
        add_incident(incidents, "network_missing")
    report["images"] = {image: image_exists(image) for image in LAB_IMAGES}
    for image, exists in report["images"].items():
        if not exists:
            add_incident(incidents, "image_missing", image)
    report["containers"] = {name: container_state(name) for name in LAB_CONTAINERS}
    report["tenablesc"] = collect_tenablesc_diagnostics(incidents)
    report["nessus"] = collect_nessus_diagnostics(incidents)

    critical = [incident for incident in incidents if incident["severity"] == "critical"]
    return report, not critical


def print_report(report: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2))
        return
    print(f"Laboratorio: {report['lab_dir']}")
    print(f"Docker: {'OK' if report['docker_available'] else 'FAIL'}")
    print(f"Network {NETWORK_NAME}: {'OK' if report['network_exists'] else 'FAIL'}")
    print("Imagenes:")
    for image, ok in report.get("images", {}).items():
        print(f"  - {image}: {'OK' if ok else 'MISSING'}")
    print("Incidencias:")
    if not report.get("incidents"):
        print("  - Ninguna incidencia critica detectada.")
    for incident in report.get("incidents", []):
        print(f"  - [{incident['severity']}] {incident['code']} repair={incident['repair']} {incident['detail']}")


def doctor(args: argparse.Namespace) -> int:
    report, ok = collect_doctor_report()
    print_report(report, as_json=args.json)
    return 0 if ok else 1


def status(args: argparse.Namespace) -> int:
    report = {
        "docker_available": docker_available(),
        "network_exists": network_exists(NETWORK_NAME) if docker_available() else False,
        "compose_file": str(COMPOSE_FILE),
        "images": {image: image_exists(image) for image in LAB_IMAGES} if docker_available() else {},
        "containers": {name: container_state(name) for name in LAB_CONTAINERS} if docker_available() else {},
    }
    print(json.dumps(report, indent=2))
    return 0 if report["docker_available"] else 1


def repair_runtime() -> None:
    script = """set -eu
echo "ensure-tns-user"
if ! getent group tns >/dev/null 2>&1; then groupadd -g 250 tns; fi
if ! id tns >/dev/null 2>&1; then useradd -u 250 -g tns -d /opt/sc -s /bin/bash tns; fi
if [ "$(id -u tns)" != "250" ] || [ "$(id -g tns)" != "250" ]; then
  echo "ERROR: tns must be uid/gid 250" >&2
  exit 2
fi
mkdir -p /opt/sc/admin/logs /opt/sc/admin/logs/services /opt/sc/data/postgresql /opt/sc/data/redis
chown -R tns:tns /opt/sc/admin/logs /opt/sc/data/postgresql /opt/sc/data/redis
echo "ensure-locale"
if ! locale -a | grep -Eiq '^en_US\\.(utf8|UTF-8)$'; then
  if command -v dnf >/dev/null 2>&1; then
    dnf install -y glibc-langpack-en glibc-locale-source >/tmp/tenablesc-locale-install.log 2>&1 || {
      cat /tmp/tenablesc-locale-install.log >&2
      exit 3
    }
  fi
  localedef -i en_US -f UTF-8 en_US.UTF-8 || true
fi
echo "ensure-supervisord"
if ! supervisorctl -c /etc/supervisord-tenablesc.conf status >/tmp/tenablesc-supervisor-status.log 2>&1; then
  if ! pgrep -f 'supervisord.*supervisord-tenablesc.conf' >/dev/null 2>&1; then
    /usr/bin/supervisord -c /etc/supervisord-tenablesc.conf
    sleep 2
  fi
fi
echo "repair-postgres"
if [ -f /opt/sc/data/postgresql/postmaster.pid ]; then
  pid=$(head -1 /opt/sc/data/postgresql/postmaster.pid)
  if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
    cp -p /opt/sc/data/postgresql/postmaster.pid /opt/sc/data/postgresql/postmaster.pid.stale.$(date +%Y%m%d%H%M%S)
    rm -f /opt/sc/data/postgresql/postmaster.pid
  fi
fi
if ! su -s /bin/bash tns -c "env LD_LIBRARY_PATH=/opt/sc/support/lib /opt/sc/support/bin/pg_ctl -D /opt/sc/data/postgresql status" >/dev/null 2>&1; then
  su -s /bin/bash tns -c "env LD_LIBRARY_PATH=/opt/sc/support/lib /opt/sc/support/bin/pg_ctl -D /opt/sc/data/postgresql -l /opt/sc/admin/logs/postgresql.log start"
fi
sleep 3
echo "repair-supervised-services"
for svc in TenableSC:Apache TenableSC:Jobd; do
  state=$(supervisorctl -c /etc/supervisord-tenablesc.conf status "$svc" 2>/dev/null | awk '{print $2}' || true)
  if [ "$state" = "RUNNING" ]; then
    supervisorctl -c /etc/supervisord-tenablesc.conf restart "$svc" || true
  else
    supervisorctl -c /etc/supervisord-tenablesc.conf start "$svc" || true
  fi
done
echo "repair-redis"
if ! /opt/sc/support/bin/redis-cli -h 127.0.0.1 -p 6379 ping >/dev/null 2>&1; then
  su -s /bin/bash tns -c "/opt/sc/support/bin/redis-server --bind 127.0.0.1 --port 6379 --dir /opt/sc/data/redis --pidfile /opt/sc/daemons/redis.pid --logfile /opt/sc/admin/logs/redis.log --daemonize yes"
fi
echo "repair-websocket"
if ! pgrep -f '/opt/sc/src/WebSocketServer.php' >/dev/null 2>&1; then
  su -s /bin/bash tns -c 'nohup /opt/sc/support/bin/php /opt/sc/src/WebSocketServer.php > /opt/sc/admin/logs/websocket.log 2>&1 & echo $! > /opt/sc/daemons/websocket.pid'
fi
echo "repair-asset-service"
if ! pgrep -f '/opt/sc/bin/services/microservice-supervisor.sh' >/dev/null 2>&1; then
  rm -f /opt/sc/daemons/microservice-supervisor.pid /opt/sc/daemons/sc-asset-svc.pid
  su -s /bin/bash tns -c "nohup /opt/sc/bin/services/microservice-supervisor.sh > /opt/sc/admin/logs/services/microservice-supervisor.stdout.log 2>&1 &"
fi
sleep 5
supervisorctl -c /etc/supervisord-tenablesc.conf status
/opt/sc/support/bin/redis-cli -h 127.0.0.1 -p 6379 ping
pgrep -af '/opt/sc/src/WebSocketServer.php'
pgrep -af '/opt/sc/bin/services/sc-asset-svc'
"""
    completed = docker_exec_script(TENABLESC_CONTAINER, script, check=True)
    print(text(completed))
    if completed.stderr:
        print(completed.stderr.decode("utf-8", errors="replace"), file=sys.stderr)


def prepare_assets(args: argparse.Namespace) -> int:
    repos = [repo.strip() for repo in args.repositories.split(",") if repo.strip()]
    if not repos:
        raise LabError("At least one repository id is required")
    for repo in repos:
        if not repo.isdigit():
            raise LabError(f"Invalid repository id: {repo}")
    script = "\n".join(
        [
            "set -eu",
            "TS=$(date +%s)",
            f"CONTEXT={int(args.context)}",
            *[
                (
                    f"echo prepareassets repo={repo} context=$CONTEXT ts=$TS\n"
                    f"/opt/sc/support/bin/php /opt/sc/src/tools/prepareassetsWrapper.php --debug 1 {repo} all all $CONTEXT $TS"
                )
                for repo in repos
            ],
        ]
    )
    completed = docker_exec_script(TENABLESC_CONTAINER, script + "\n", user="tns", check=True)
    print(text(completed))
    if completed.stderr:
        print(completed.stderr.decode("utf-8", errors="replace"), file=sys.stderr)
    return 0


def repair_nessus() -> None:
    state = container_state(NESSUS_CONTAINER)
    if not state.get("exists"):
        run(compose_command() + ["--env-file", str(env_file_for_compose()), "-f", str(COMPOSE_FILE), "up", "-d", "nessus"], capture=False)
        return
    if not state.get("running"):
        run(["docker", "start", NESSUS_CONTAINER], capture=False)
        return
    processes = docker_exec(NESSUS_CONTAINER, "pgrep -af 'nessus-service|nessusd'", check=False)
    if processes.returncode != 0 or "nessusd" not in text(processes):
        run(["docker", "restart", NESSUS_CONTAINER], capture=False)


def repair(args: argparse.Namespace) -> int:
    case = args.case
    if case == "auto":
        report, _ = collect_doctor_report()
        repair_cases = {incident["repair"] for incident in report["incidents"] if incident["repair"] not in {"manual", "inspect", "load-images", "recreate-with-compose"}}
        if not repair_cases:
            print("No automatic repair cases detected.")
            return 0
        if "up" in repair_cases:
            up(argparse.Namespace())
        if "runtime" in repair_cases or "postgres" in repair_cases:
            repair_runtime()
        if "assets" in repair_cases:
            prepare_assets(argparse.Namespace(repositories=args.repositories, context=args.context))
        if "nessus" in repair_cases:
            repair_nessus()
    elif case in {"all", "runtime", "postgres"}:
        repair_runtime()
        if case == "all":
            prepare_assets(argparse.Namespace(repositories=args.repositories, context=args.context))
            repair_nessus()
    elif case == "assets":
        prepare_assets(argparse.Namespace(repositories=args.repositories, context=args.context))
    elif case == "nessus":
        repair_nessus()
    else:
        raise LabError(f"Unknown repair case: {case}")
    report, ok = collect_doctor_report()
    print_report(report, as_json=args.json)
    return 0 if ok else 1


def stage_labbox_zip(zip_path: Path, *, extract_utils: bool) -> dict[str, Any]:
    if not zip_path.exists():
        raise LabError(f"Labbox Docker ZIP not found: {zip_path}")

    staged: dict[str, Any] = {
        "source_zip": str(zip_path),
        "zip_image": LABBOX_ZIP_IMAGE,
        "utils_dir": str(LABBOX_UTILS_DIR),
        "utils_extracted": 0,
    }

    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        if LABBOX_ZIP_IMAGE not in names:
            raise LabError(f"{zip_path} does not contain {LABBOX_ZIP_IMAGE}")

        if extract_utils:
            for entry in archive.infolist():
                if entry.is_dir():
                    continue
                if entry.filename.startswith("__MACOSX/"):
                    continue
                if not entry.filename.startswith(LABBOX_ZIP_UTILS_PREFIX):
                    continue
                relative = entry.filename[len(LABBOX_ZIP_UTILS_PREFIX) :]
                if not relative or relative == ".DS_Store":
                    continue
                target = LABBOX_UTILS_DIR / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    continue
                with archive.open(entry) as source, target.open("wb") as handle:
                    shutil.copyfileobj(source, handle)
                staged["utils_extracted"] += 1

    return staged


def load_tenablesc_image_from_zip(zip_path: Path) -> None:
    print(f"Loading tenablesc-labbox-image-ol8 from {zip_path}")
    with zipfile.ZipFile(zip_path) as archive:
        if LABBOX_ZIP_IMAGE not in set(archive.namelist()):
            raise LabError(f"{zip_path} does not contain {LABBOX_ZIP_IMAGE}")
        with tempfile.TemporaryDirectory(prefix="holcim-labbox-") as temp_dir:
            temp_image = Path(temp_dir) / "tenablesc-labbox-image-ol8.tar"
            with archive.open(LABBOX_ZIP_IMAGE) as source, temp_image.open("wb") as target:
                shutil.copyfileobj(source, target)
            run(["docker", "load", "-i", str(temp_image)], capture=False)


def default_labbox_zip() -> Path | None:
    configured = os.environ.get("LABBOX_DOCKER_ZIP")
    if configured:
        return Path(configured)
    if DEFAULT_LABBOX_ZIP.exists():
        return DEFAULT_LABBOX_ZIP
    return None


def load_images(args: argparse.Namespace) -> int:
    labbox_zip = getattr(args, "labbox_zip", None) or default_labbox_zip()
    staged = None
    if labbox_zip:
        staged = stage_labbox_zip(
            Path(labbox_zip),
            extract_utils=not bool(getattr(args, "no_extract_utils", False)),
        )

    loaded = []
    missing = []
    for image in LAB_IMAGES:
        if image_exists(image):
            continue
        if image == "tenablesc-labbox-image-ol8" and labbox_zip:
            load_tenablesc_image_from_zip(Path(labbox_zip))
            loaded.append(image)
            continue
        print(f"Pulling public image {image}")
        pulled = run(["docker", "pull", image], capture=False, check=False)
        if pulled.returncode == 0:
            loaded.append(image)
        else:
            missing.append({"image": image, "hint": "Load it locally or allow Docker to pull it."})
    print(json.dumps({"staged": staged, "loaded": loaded, "missing": missing}, indent=2))
    return 0 if not missing else 2


def up(_: argparse.Namespace) -> int:
    if not docker_available():
        raise LabError("Docker is not available")
    ensure_network()
    load_images(argparse.Namespace())
    if not image_exists("tenablesc-labbox-image-ol8"):
        raise LabError(
            f"Missing custom Tenable.sc image. Keep {DEFAULT_LABBOX_ZIP} in the lab folder."
        )
    states = {name: container_state(name) for name in LAB_CONTAINERS}
    existing = [name for name, state in states.items() if state.get("exists")]
    missing = [name for name, state in states.items() if not state.get("exists")]
    if existing and not missing:
        for name, state in states.items():
            if not state.get("running"):
                print(f"Starting existing container {name}")
                run(["docker", "start", name], capture=False)
        print("Expected lab containers already exist; reused them instead of recreating with Compose.")
        return 0
    if existing and missing:
        raise LabError(
            "Partial lab container state detected. Existing containers: "
            f"{', '.join(existing)}. Missing containers: {', '.join(missing)}. "
            "Start from a clean PC/package or resolve the Docker containers manually."
        )
    run(compose_command() + ["--env-file", str(env_file_for_compose()), "-f", str(COMPOSE_FILE), "up", "-d"], capture=False)
    return 0


def package_status(args: argparse.Namespace) -> int:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str = "", required: bool = True) -> None:
        checks.append({"name": name, "ok": ok, "required": required, "detail": detail})

    add("docker-compose.yml", COMPOSE_FILE.exists(), str(COMPOSE_FILE))
    add("build_lab.py", (LAB_DIR / "build_lab.py").exists(), str(LAB_DIR / "build_lab.py"))
    add(".env.example", (LAB_DIR / ".env.example").exists(), str(LAB_DIR / ".env.example"))
    add("portable .env", DEFAULT_ENV_FILE.exists(), str(DEFAULT_ENV_FILE))

    zip_ok = False
    zip_detail = str(DEFAULT_LABBOX_ZIP)
    if DEFAULT_LABBOX_ZIP.exists():
        try:
            with zipfile.ZipFile(DEFAULT_LABBOX_ZIP) as archive:
                names = set(archive.namelist())
                zip_ok = LABBOX_ZIP_IMAGE in names
                if not zip_ok:
                    zip_detail = f"{DEFAULT_LABBOX_ZIP} missing {LABBOX_ZIP_IMAGE}"
        except zipfile.BadZipFile:
            zip_detail = f"{DEFAULT_LABBOX_ZIP} is not a valid ZIP"
    add("labbox-docker.zip", zip_ok, zip_detail)

    add("labbox-utils", LABBOX_UTILS_DIR.exists(), str(LABBOX_UTILS_DIR))
    add("labbox-utils license", (LABBOX_UTILS_DIR / "license.key").exists(), str(LABBOX_UTILS_DIR / "license.key"))
    add("sin backups locales", not FORBIDDEN_BACKUP_DIR.exists(), str(FORBIDDEN_BACKUP_DIR))

    complete = all(item["ok"] for item in checks if item["required"])
    result = {
        "complete": complete,
        "lab_dir": str(LAB_DIR),
        "mode": "image-only",
        "checks": checks,
    }
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Laboratorio portable: {'COMPLETO' if complete else 'INCOMPLETO'}")
        print(f"Carpeta: {LAB_DIR}")
        print("Modo: image-only, sin backups de datos")
        for item in checks:
            mark = "OK" if item["ok"] else "FALTA"
            print(f"- {mark}: {item['name']} ({item['detail']})")
    return 0 if complete else 2


def setup(args: argparse.Namespace) -> int:
    env_info = ensure_portable_env()
    print(json.dumps({"portable_env": env_info}, indent=2))

    load_result = load_images(
        argparse.Namespace(labbox_zip=args.labbox_zip, no_extract_utils=args.no_extract_utils)
    )
    if load_result != 0:
        return load_result

    up(argparse.Namespace())

    if not args.skip_repair:
        repair_result = repair(
            argparse.Namespace(
                case="auto",
                repositories=args.repositories,
                context=args.context,
                json=False,
            )
        )
        if repair_result != 0:
            return repair_result
    return doctor(argparse.Namespace(json=args.json))


def validate(args: argparse.Namespace) -> int:
    doctor_result = doctor(argparse.Namespace(json=True))
    if doctor_result != 0:
        return doctor_result
    extract = run(
        [
            sys.executable,
            str(PROJECT_ROOT / "extract_compliance.py"),
            "details",
            "--asset-name",
            "compliance_example",
            "--output",
            str(PROJECT_ROOT / "outputs" / "compliance_example_details.json"),
            "--pretty",
        ],
        check=False,
    )
    print(text(extract))
    if extract.returncode != 0:
        print(extract.stderr.decode("utf-8", errors="replace"), file=sys.stderr)
    return extract.returncode


def incidents(_: argparse.Namespace) -> int:
    print(json.dumps(INCIDENT_CATALOG, indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build, diagnose and repair the Tenable.sc + Nessus lab.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p = subparsers.add_parser("status", help="Show Docker/image/container state.")
    p.set_defaults(func=status)

    p = subparsers.add_parser("package-status", help="Check if the portable lab package is complete.")
    p.add_argument("--json", action="store_true", help="Emit full JSON report.")
    p.set_defaults(func=package_status)

    p = subparsers.add_parser("doctor", help="Run a complete lab diagnostic and incident report.")
    p.add_argument("--json", action="store_true", help="Emit full JSON report.")
    p.set_defaults(func=doctor)

    p = subparsers.add_parser("repair", help="Repair known lab incident cases.")
    p.add_argument("--case", default="auto", choices=["auto", "all", "runtime", "postgres", "assets", "nessus"])
    p.add_argument("--repositories", default="6,8,9,10")
    p.add_argument("--context", type=int, default=37)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=repair)

    p = subparsers.add_parser("prepare-assets", help="Regenerate Asset List artifacts.")
    p.add_argument("--repositories", default="6,8,9,10")
    p.add_argument("--context", type=int, default=37)
    p.set_defaults(func=prepare_assets)

    p = subparsers.add_parser("load-images", help="Load Docker images from labbox ZIP or public registry.")
    p.add_argument(
        "--labbox-zip",
        default=None,
        help="Optional path to labbox-docker.zip. Defaults to LABBOX_DOCKER_ZIP or laboratorio/labbox-docker.zip.",
    )
    p.add_argument(
        "--no-extract-utils",
        action="store_true",
        help="Do not extract labbox-docker/utils from --labbox-zip into labbox-utils.",
    )
    p.set_defaults(func=load_images)

    p = subparsers.add_parser("up", help="Start the lab conservatively.")
    p.set_defaults(func=up)

    p = subparsers.add_parser("setup", help="Prepare, start, repair and diagnose the portable lab.")
    p.add_argument(
        "--labbox-zip",
        default=None,
        help="Optional path to labbox-docker.zip. Defaults to LABBOX_DOCKER_ZIP or laboratorio/labbox-docker.zip.",
    )
    p.add_argument("--no-extract-utils", action="store_true", help="Do not extract labbox-docker/utils.")
    p.add_argument("--skip-repair", action="store_true", help="Skip automatic repair.")
    p.add_argument("--repositories", default="6,8,9,10")
    p.add_argument("--context", type=int, default=37)
    p.add_argument("--json", action="store_true", help="Emit final doctor report as JSON.")
    p.set_defaults(func=setup)

    p = subparsers.add_parser("validate", help="Run doctor plus the minimal extractor validation.")
    p.set_defaults(func=validate)

    p = subparsers.add_parser("incidents", help="Print known incident catalog.")
    p.set_defaults(func=incidents)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return int(args.func(args))
    except LabError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
