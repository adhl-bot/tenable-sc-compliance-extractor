from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_env_file(path: str | Path) -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class TenableConfig:
    url: str
    username: str
    password: str
    verify_ssl: bool
    auth_mode: str
    access_key: str
    secret_key: str
    timeout: int

    @classmethod
    def from_env(cls, timeout: int | None = None) -> "TenableConfig":
        return cls(
            url=os.environ.get("TENABLE_SC_URL", "https://localhost:8443"),
            username=os.environ.get("TENABLE_SC_SECURITY_MANAGER_USERNAME")
            or os.environ.get("TENABLE_SC_USERNAME", ""),
            password=os.environ.get("TENABLE_SC_SECURITY_MANAGER_PASSWORD")
            or os.environ.get("TENABLE_SC_PASSWORD", ""),
            verify_ssl=parse_bool(os.environ.get("TENABLE_SC_VERIFY_SSL"), True),
            auth_mode=os.environ.get("TENABLE_SC_AUTH_MODE", "session").strip().lower(),
            access_key=os.environ.get("TENABLE_SC_ACCESS_KEY", ""),
            secret_key=os.environ.get("TENABLE_SC_SECRET_KEY", ""),
            timeout=timeout or int(os.environ.get("TENABLE_SC_TIMEOUT", "300")),
        )
