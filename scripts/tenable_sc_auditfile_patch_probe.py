from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any


class TenableSCProbeError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def parse_bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


class TenableSCClient:
    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        access_key: str,
        secret_key: str,
        auth_mode: str,
        verify_ssl: bool,
        timeout: int,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.auth_mode = auth_mode
        self.token: str | None = None
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "holcim-tenable-sc-auditfile-probe/0.1",
        }
        self.username = username
        self.password = password
        self.access_key = access_key
        self.secret_key = secret_key
        self.cookie_jar = http.cookiejar.CookieJar()
        handlers: list[urllib.request.BaseHandler] = [
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        ]
        if self.base_url.lower().startswith("https://"):
            context = ssl.create_default_context()
            if not verify_ssl:
                context = ssl._create_unverified_context()
            handlers.append(urllib.request.HTTPSHandler(context=context))
        self.opener = urllib.request.build_opener(*handlers)

    def __enter__(self) -> "TenableSCClient":
        self.login()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.logout()

    def login(self) -> None:
        if self.auth_mode == "api_keys":
            if not self.access_key or not self.secret_key:
                raise TenableSCProbeError("Missing Tenable.sc API keys")
            self.headers["X-APIKey"] = (
                f"accessKey={self.access_key}; secretKey={self.secret_key}"
            )
            return
        if not self.username or not self.password:
            raise TenableSCProbeError("Missing Tenable.sc username/password")
        payload = self.request(
            "POST",
            "/rest/token",
            json_body={"username": self.username, "password": self.password},
            authenticated=False,
        )
        token = payload.get("response", {}).get("token")
        if token is None:
            raise TenableSCProbeError("Login did not return a token", body=payload)
        self.token = str(token)
        self.headers["X-SecurityCenter"] = self.token

    def logout(self) -> None:
        if self.auth_mode != "session" or not self.token:
            return
        try:
            self.request("DELETE", "/rest/token")
        except TenableSCProbeError:
            pass
        self.token = None

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        authenticated: bool = True,
        accept: str = "application/json",
    ) -> Any:
        url = self.url(path, params)
        data = json.dumps(json_body).encode("utf-8") if json_body is not None else None
        headers = dict(self.headers)
        headers["Accept"] = accept
        if not authenticated:
            headers.pop("X-SecurityCenter", None)
            headers.pop("X-APIKey", None)
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise self.http_error(exc) from exc
        except urllib.error.URLError as exc:
            raise TenableSCProbeError(f"Tenable.sc connection error: {exc}") from exc

        content_type = response.headers.get("Content-Type", "")
        if accept != "application/json" or "json" not in content_type.lower():
            return raw.decode("utf-8", errors="replace")
        payload = json.loads(raw.decode("utf-8"))
        error_code = payload.get("error_code")
        if error_code not in (None, 0, "0"):
            raise TenableSCProbeError(
                payload.get("error_msg") or "Tenable.sc API error",
                body=payload,
            )
        return payload

    def upload_file(self, *, filename: str, content: str, context: str = "auditfile") -> dict[str, Any]:
        boundary = f"----codex-{uuid.uuid4().hex}"
        body = self.multipart_body(
            boundary,
            fields={"context": context, "returnContent": "false"},
            files={"Filedata": (filename, "text/plain", content.encode("utf-8"))},
        )
        headers = dict(self.headers)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        headers["Accept"] = "application/json"
        request = urllib.request.Request(
            self.url("/rest/file/upload"),
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise self.http_error(exc) from exc
        error_code = payload.get("error_code")
        if error_code not in (None, 0, "0"):
            raise TenableSCProbeError(payload.get("error_msg") or "Upload failed", body=payload)
        return payload.get("response", {})

    def export_audit_file(self, audit_file_id: str) -> str:
        return self.request(
            "GET",
            f"/rest/auditFile/{audit_file_id}/export",
            accept="application/octet-stream",
        )

    def get_audit_file(self, audit_file_id: str) -> dict[str, Any]:
        data = self.request("GET", f"/rest/auditFile/{audit_file_id}")
        return data.get("response", {})

    def create_audit_file(self, *, name: str, upload: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "name": name,
            "description": "Temporary Codex probe; safe to delete",
            "type": "",
            "auditFileTemplate": {"id": -1},
            "variables": [],
            "filename": upload["filename"],
            "originalFilename": upload.get("originalFilename") or f"{name}.audit",
        }
        data = self.request("POST", "/rest/auditFile", json_body=payload)
        return data.get("response", {})

    def patch_audit_file(self, audit_file_id: str, *, upload: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "filename": upload["filename"],
            "originalFilename": upload.get("originalFilename") or "patched.audit",
            "auditFileTemplate": {"id": -1},
            "variables": [],
        }
        data = self.request("PATCH", f"/rest/auditFile/{audit_file_id}", json_body=payload)
        return data.get("response", {})

    def delete_audit_file(self, audit_file_id: str) -> None:
        self.request("DELETE", f"/rest/auditFile/{audit_file_id}")

    def url(self, path: str, params: dict[str, Any] | None = None) -> str:
        clean_path = path if path.startswith("/") else f"/{path}"
        url = f"{self.base_url}{clean_path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"
        return url

    def http_error(self, exc: urllib.error.HTTPError) -> TenableSCProbeError:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw
        return TenableSCProbeError(f"Tenable.sc API error {exc.code}", status=exc.code, body=payload)

    @staticmethod
    def multipart_body(
        boundary: str,
        *,
        fields: dict[str, str],
        files: dict[str, tuple[str, str, bytes]],
    ) -> bytes:
        chunks: list[bytes] = []
        for name, value in fields.items():
            chunks.append(f"--{boundary}\r\n".encode("utf-8"))
            chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
            chunks.append(value.encode("utf-8") + b"\r\n")
        for field, (filename, content_type, content) in files.items():
            chunks.append(f"--{boundary}\r\n".encode("utf-8"))
            chunks.append(
                (
                    f'Content-Disposition: form-data; name="{field}"; '
                    f'filename="{filename}"\r\n'
                ).encode("utf-8")
            )
            chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
            chunks.append(content + b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
        return b"".join(chunks)


def build_probe_audit(marker: str) -> str:
    return f"""<check_type:"Unix">
<group_policy:"Codex temporary audit patch probe">
<custom_item>
type        : CMD_EXEC
description : "Codex temporary audit patch probe"
cmd         : "echo {marker}"
expect      : "{marker}"
reference   : "CODEX|{marker}"
</custom_item>
</group_policy>
</check_type>
"""


def overwrite_uploaded_audit_file(
    *,
    container: str,
    org_id: str,
    filename: str,
    content: str,
) -> dict[str, Any]:
    if not filename.startswith("scfile_") or "/" in filename or "\\" in filename:
        raise TenableSCProbeError(f"Refusing unexpected upload filename: {filename}")
    path = f"/opt/sc/orgs/{org_id}/uploads/{filename}"
    before = docker_exec(container, f"stat -c '%U:%G %a %s' {path}")
    docker_exec(container, f"cat > {path}", stdin=content)
    after = docker_exec(container, f"stat -c '%U:%G %a %s' {path}")
    return {"path": path, "stat_before": before, "stat_after": after}


def docker_exec(container: str, command: str, *, stdin: str | None = None) -> str:
    argv = ["docker", "exec"]
    if stdin is not None:
        argv.append("-i")
    argv.extend([container, "sh", "-lc", command])
    try:
        completed = subprocess.run(
            argv,
            input=stdin.encode("utf-8") if stdin is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise TenableSCProbeError(f"Docker exec failed: {exc}") from exc
    if completed.returncode != 0:
        raise TenableSCProbeError(
            "Docker exec returned a non-zero exit code",
            body={
                "command": command,
                "returncode": completed.returncode,
                "stdout": completed.stdout.decode("utf-8", errors="replace"),
                "stderr": completed.stderr.decode("utf-8", errors="replace"),
            },
        )
    return completed.stdout.decode("utf-8", errors="replace").strip()


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    load_env_file(Path(args.env))
    client_kwargs = {
        "base_url": os.environ.get("TENABLE_SC_URL", "https://localhost:8443"),
        "username": os.environ.get("TENABLE_SC_SECURITY_MANAGER_USERNAME")
        or os.environ.get("TENABLE_SC_USERNAME", ""),
        "password": os.environ.get("TENABLE_SC_SECURITY_MANAGER_PASSWORD")
        or os.environ.get("TENABLE_SC_PASSWORD", ""),
        "access_key": os.environ.get("TENABLE_SC_ACCESS_KEY", ""),
        "secret_key": os.environ.get("TENABLE_SC_SECRET_KEY", ""),
        "auth_mode": os.environ.get("TENABLE_SC_AUTH_MODE", "session").strip().lower(),
        "verify_ssl": parse_bool(os.environ.get("TENABLE_SC_VERIFY_SSL"), False),
        "timeout": args.timeout,
    }
    name = f"codex_patch_probe_{int(time.time())}"
    first_marker = f"{name}_v1"
    second_marker = f"{name}_v2"
    created_id: str | None = None
    cleanup_error: str | None = None

    with TenableSCClient(**client_kwargs) as client:
        first_upload = client.upload_file(
            filename=f"{name}_v1.audit",
            content=build_probe_audit(first_marker),
        )
        created = client.create_audit_file(name=name, upload=first_upload)
        created_id = str(created["id"])
        exported_before = client.export_audit_file(created_id)

        filesystem_patch: dict[str, Any] | None = None
        if args.mode == "api":
            second_upload = client.upload_file(
                filename=f"{name}_v2.audit",
                content=build_probe_audit(second_marker),
            )
            patched = client.patch_audit_file(created_id, upload=second_upload)
        else:
            filesystem_patch = overwrite_uploaded_audit_file(
                container=args.docker_container,
                org_id=args.org_id,
                filename=str(created["filename"]),
                content=build_probe_audit(second_marker),
            )
            patched = client.get_audit_file(created_id)

        patched_id = str(patched["id"])
        exported_after = client.export_audit_file(created_id)

        try:
            client.delete_audit_file(created_id)
        except TenableSCProbeError as exc:
            cleanup_error = str(exc)

    return {
        "created_id": created_id,
        "patched_id": patched_id,
        "id_preserved": created_id == patched_id,
        "filename_before": created.get("filename"),
        "filename_after": patched.get("filename"),
        "mode": args.mode,
        "filesystem_patch": filesystem_patch,
        "marker_before_found_before_patch": first_marker in exported_before,
        "marker_after_found_after_patch": second_marker in exported_after,
        "old_marker_still_found_after_patch": first_marker in exported_after,
        "cleanup_error": cleanup_error,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create, patch, export, and delete a temporary Tenable.sc audit file."
    )
    parser.add_argument("--env", default=".env")
    parser.add_argument("--mode", choices=["api", "filesystem"], default="api")
    parser.add_argument("--docker-container", default="tenablesc-labbox-ol8")
    parser.add_argument("--org-id", default="1")
    parser.add_argument("--timeout", type=int, default=120)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = run_probe(args)
    except TenableSCProbeError as exc:
        print(json.dumps({"error": str(exc), "status": exc.status, "body": exc.body}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
