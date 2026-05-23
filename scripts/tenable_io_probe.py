from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


class TenableIOError(RuntimeError):
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


class TenableIOClient:
    def __init__(self, *, base_url: str, access_key: str, secret_key: str, timeout: int = 120) -> None:
        if not access_key or not secret_key:
            raise TenableIOError("Missing TENABLE_IO_ACCESS_KEY or TENABLE_IO_SECRET_KEY")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "holcim-tenable-io-probe/0.1",
            "X-ApiKeys": f"accessKey={access_key}; secretKey={secret_key}",
        }

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", path, params=params)

    def post(self, path: str, body: dict[str, Any]) -> Any:
        return self.request("POST", path, body=body)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        url = self.url(path, params)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(url, data=data, headers=self.headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise self.http_error(exc) from exc
        except urllib.error.URLError as exc:
            raise TenableIOError(f"Tenable IO connection error: {exc}") from exc

        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    def url(self, path: str, params: dict[str, Any] | None = None) -> str:
        clean_path = path if path.startswith("/") else f"/{path}"
        url = f"{self.base_url}{clean_path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"
        return url

    def http_error(self, exc: urllib.error.HTTPError) -> TenableIOError:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw
        return TenableIOError(f"Tenable IO API error {exc.code}", status=exc.code, body=payload)


def find_tag(client: TenableIOClient, category: str, value: str) -> dict[str, Any] | None:
    payload = client.get("/tags/values", {"limit": 5000})
    values = payload.get("values", []) if isinstance(payload, dict) else []
    for item in values:
        if item.get("category_name") == category and item.get("value") == value:
            return item
    return None


def list_assets_by_tag(client: TenableIOClient, category: str, value: str) -> list[dict[str, Any]]:
    payload = client.get(
        "/workbenches/assets",
        {
            "filter.0.filter": f"tag.{category}",
            "filter.0.quality": "eq",
            "filter.0.value": value,
        },
    )
    return payload.get("assets", []) if isinstance(payload, dict) else []


def get_asset_info(client: TenableIOClient, asset_id: str) -> dict[str, Any]:
    payload = client.get(f"/workbenches/assets/{asset_id}/info", {"all_fields": "full"})
    return payload.get("info", {}) if isinstance(payload, dict) else {}


def list_asset_vulnerabilities(
    client: TenableIOClient,
    asset_id: str,
    *,
    plugin_id: int | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {}
    if plugin_id is not None:
        params = {
            "filter.0.filter": "plugin.id",
            "filter.0.quality": "eq",
            "filter.0.value": str(plugin_id),
        }
    payload = client.get(f"/workbenches/assets/{asset_id}/vulnerabilities", params)
    return payload.get("vulnerabilities", []) if isinstance(payload, dict) else []


def export_compliance_for_asset(
    client: TenableIOClient,
    asset_id: str,
    *,
    poll_seconds: int = 2,
    attempts: int = 30,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    job = client.post("/compliance/export", {"num_findings": 50, "asset": [asset_id]})
    export_uuid = job.get("export_uuid") or job.get("uuid")
    if not export_uuid:
        raise TenableIOError("Compliance export did not return an export UUID", body=job)

    status: dict[str, Any] = {}
    for _ in range(attempts):
        time.sleep(poll_seconds)
        status = client.get(f"/compliance/export/{export_uuid}/status")
        if status.get("status") in {"READY", "FINISHED", "ERROR", "CANCELLED"}:
            break

    findings: list[dict[str, Any]] = []
    for chunk_id in status.get("chunks_available", []):
        chunk = client.get(f"/compliance/export/{export_uuid}/chunks/{chunk_id}")
        if isinstance(chunk, list):
            findings.extend(chunk)
    return status, findings


def summarize_reference_variants(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_full_id: dict[str, list[dict[str, Any]]] = {}
    for finding in findings:
        full_id = finding.get("compliance_full_id")
        if full_id:
            by_full_id.setdefault(full_id, []).append(finding)

    variants: list[dict[str, Any]] = []
    for full_id, group in by_full_id.items():
        ref_shapes = {json.dumps(item.get("reference"), sort_keys=True) for item in group}
        audit_files = sorted({str(item.get("audit_file")) for item in group})
        if len(group) > 1 and len(ref_shapes) > 1:
            variants.append(
                {
                    "compliance_full_id": full_id,
                    "compliance_functional_ids": sorted(
                        {str(item.get("compliance_functional_id")) for item in group}
                    ),
                    "compliance_informational_ids": sorted(
                        {str(item.get("compliance_informational_id")) for item in group}
                    ),
                    "audit_files": audit_files,
                    "reference_variants": len(ref_shapes),
                    "check_names": sorted({str(item.get("check_name")) for item in group}),
                }
            )
    return variants


def shorten(value: Any, max_len: int) -> Any:
    if not isinstance(value, str) or len(value) <= max_len:
        return value
    return f"{value[:max_len]}... [truncated {len(value) - max_len} chars]"


def compact_finding(finding: dict[str, Any], *, max_text_len: int) -> dict[str, Any]:
    return {
        "asset_uuid": finding.get("asset_uuid"),
        "plugin_id": finding.get("plugin_id"),
        "plugin_name": finding.get("plugin_name"),
        "check_name": finding.get("check_name"),
        "status": finding.get("status"),
        "state": finding.get("state"),
        "audit_file": finding.get("audit_file"),
        "actual_value": shorten(finding.get("actual_value"), max_text_len),
        "expected_value": finding.get("expected_value"),
        "reference": finding.get("reference"),
        "compliance_full_id": finding.get("compliance_full_id"),
        "compliance_functional_id": finding.get("compliance_functional_id"),
        "compliance_informational_id": finding.get("compliance_informational_id"),
        "last_observed": finding.get("last_observed"),
        "last_seen": finding.get("last_seen"),
    }


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    load_env_file(Path(args.env))
    client = TenableIOClient(
        base_url=os.environ.get("TENABLE_IO_URL", "https://cloud.tenable.com/"),
        access_key=os.environ.get("TENABLE_IO_ACCESS_KEY", ""),
        secret_key=os.environ.get("TENABLE_IO_SECRET_KEY", ""),
        timeout=args.timeout,
    )

    tag = find_tag(client, args.tag_category, args.tag_value)
    assets = list_assets_by_tag(client, args.tag_category, args.tag_value)
    selected_asset = next((asset for asset in assets if asset.get("id")), None)

    asset_info: dict[str, Any] = {}
    vulnerabilities: list[dict[str, Any]] = []
    plugin_filtered: list[dict[str, Any]] = []
    compliance_status: dict[str, Any] = {}
    compliance_findings: list[dict[str, Any]] = []

    if selected_asset:
        asset_id = str(selected_asset["id"])
        asset_info = get_asset_info(client, asset_id)
        vulnerabilities = list_asset_vulnerabilities(client, asset_id)
        if vulnerabilities:
            plugin_id = int(vulnerabilities[0]["plugin_id"])
            plugin_filtered = list_asset_vulnerabilities(client, asset_id, plugin_id=plugin_id)
        compliance_status, compliance_findings = export_compliance_for_asset(client, asset_id)

    return {
        "tag_lookup": {
            "category": args.tag_category,
            "value": args.tag_value,
            "found": tag is not None,
            "tag": {
                "uuid": tag.get("uuid"),
                "category_name": tag.get("category_name"),
                "value": tag.get("value"),
                "type": tag.get("type"),
            }
            if tag
            else None,
        },
        "asset_filter": {
            "returned": len(assets),
            "selected_asset": {
                "id": selected_asset.get("id"),
                "ipv4": selected_asset.get("ipv4"),
                "hostname": selected_asset.get("hostname"),
                "operating_system": selected_asset.get("operating_system"),
                "last_seen": selected_asset.get("last_seen"),
            }
            if selected_asset
            else None,
        },
        "asset_info": {
            "id": asset_info.get("id"),
            "counts": asset_info.get("counts"),
            "tags": [
                {
                    "tag_key": tag_item.get("tag_key"),
                    "tag_value": tag_item.get("tag_value"),
                    "source": tag_item.get("source"),
                }
                for tag_item in asset_info.get("tags", [])
            ],
        },
        "findings_filter": {
            "asset_vulnerability_count": len(vulnerabilities),
            "plugin_filtered_count": len(plugin_filtered),
            "plugin_filtered_sample": plugin_filtered[:3],
        },
        "host_audits": {
            "export_status": compliance_status.get("status"),
            "chunks_available": compliance_status.get("chunks_available", []),
            "empty_chunks_count": compliance_status.get("empty_chunks_count"),
            "finding_count": len(compliance_findings),
            "sample": [
                compact_finding(item, max_text_len=args.max_text_len)
                for item in compliance_findings[: args.sample_size]
            ],
            "reference_variants_same_full_id": summarize_reference_variants(compliance_findings),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe Tenable IO VM API for lab validation.")
    parser.add_argument("--env", default=".env", help="Path to local env file.")
    parser.add_argument("--tag-category", default="Operating_System")
    parser.add_argument("--tag-value", default="Windows Workstation")
    parser.add_argument("--sample-size", type=int, default=5)
    parser.add_argument("--max-text-len", type=int, default=300)
    parser.add_argument("--timeout", type=int, default=120)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = build_summary(args)
    except TenableIOError as exc:
        error = {"error": str(exc), "status": exc.status, "body": exc.body}
        print(json.dumps(error, indent=2, ensure_ascii=False))
        return 1
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
