from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .tenable_client import TenableAPIError, TenableSCClient


SEVERITY_COLUMNS = {
    0: "info_count",
    1: "low_count",
    2: "medium_count",
    3: "high_count",
    4: "critical_count",
}


@dataclass
class ComplianceSummaryRow:
    asset_id: str
    asset_name: str
    asset_type: str
    asset_ip_count: int
    audit_file_id: str
    audit_file_name: str
    audit_file_filename: str
    audit_file_type: str
    passed_controls: int
    failed_controls: int
    total_controls: int
    compliance_percent: float | None
    info_count: int
    low_count: int
    medium_count: int
    high_count: int
    critical_count: int


def filter_assets(
    assets: list[dict[str, Any]],
    *,
    asset_ids: list[int] | None = None,
    asset_name_contains: list[str] | None = None,
    include_zero_ip: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    selected = assets
    if asset_ids:
        wanted = {str(asset_id) for asset_id in asset_ids}
        selected = [asset for asset in selected if str(asset.get("id")) in wanted]
    if asset_name_contains:
        needles = [value.lower() for value in asset_name_contains]
        selected = [
            asset
            for asset in selected
            if any(needle in str(asset.get("name", "")).lower() for needle in needles)
        ]
    if not include_zero_ip and not asset_ids:
        selected = [asset for asset in selected if int(asset.get("ipCount") or 0) > 0]
    if limit is not None:
        selected = selected[:limit]
    return selected


def filter_audit_files(
    audit_files: list[dict[str, Any]],
    *,
    audit_file_ids: list[int] | None = None,
    audit_file_name_contains: list[str] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    selected = audit_files
    if audit_file_ids:
        wanted = {str(audit_id) for audit_id in audit_file_ids}
        selected = [audit for audit in selected if str(audit.get("id")) in wanted]
    if audit_file_name_contains:
        needles = [value.lower() for value in audit_file_name_contains]
        selected = [
            audit
            for audit in selected
            if any(needle in str(audit.get("name", "")).lower() for needle in needles)
        ]
    if limit is not None:
        selected = selected[:limit]
    return selected


def extract_compliance_summary(
    client: TenableSCClient,
    *,
    asset_ids: list[int] | None = None,
    asset_name_contains: list[str] | None = None,
    audit_file_ids: list[int] | None = None,
    audit_file_name_contains: list[str] | None = None,
    include_zero_ip: bool = False,
    include_empty: bool = False,
    limit_assets: int | None = None,
    limit_audit_files: int | None = None,
) -> tuple[list[ComplianceSummaryRow], list[dict[str, Any]]]:
    assets = filter_assets(
        client.list_assets(),
        asset_ids=asset_ids,
        asset_name_contains=asset_name_contains,
        include_zero_ip=include_zero_ip,
        limit=limit_assets,
    )
    audit_files = filter_audit_files(
        client.list_audit_files(),
        audit_file_ids=audit_file_ids,
        audit_file_name_contains=audit_file_name_contains,
        limit=limit_audit_files,
    )

    rows: list[ComplianceSummaryRow] = []
    errors: list[dict[str, Any]] = []

    for asset in assets:
        for audit_file in audit_files:
            try:
                response = client.compliance_sumseverity(
                    asset_id=asset["id"],
                    audit_file_id=audit_file["id"],
                )
            except TenableAPIError as exc:
                if is_empty_audit_result_error(exc):
                    if include_empty:
                        rows.append(build_summary_row(asset, audit_file, []))
                    continue
                errors.append(
                    {
                        "asset_id": str(asset.get("id", "")),
                        "asset_name": str(asset.get("name", "")),
                        "audit_file_id": str(audit_file.get("id", "")),
                        "audit_file_name": str(audit_file.get("name", "")),
                        "status": exc.status,
                        "error_code": exc.error_code,
                        "message": str(exc),
                    }
                )
                continue

            row = build_summary_row(asset, audit_file, response.results)
            if include_empty or row.total_controls > 0:
                rows.append(row)

    return rows, errors


def is_empty_audit_result_error(exc: TenableAPIError) -> bool:
    message = str(exc)
    return "AuditFile #" in message and "not found" in message


def build_summary_row(
    asset: dict[str, Any],
    audit_file: dict[str, Any],
    severity_results: list[dict[str, Any]],
) -> ComplianceSummaryRow:
    severity_counts = {severity_id: 0 for severity_id in SEVERITY_COLUMNS}
    for item in severity_results:
        severity = item.get("severity") or {}
        severity_id = int(severity.get("id") or 0)
        count = int(item.get("count") or 0)
        if severity_id in severity_counts:
            severity_counts[severity_id] += count

    passed = severity_counts[0]
    failed = sum(severity_counts[severity_id] for severity_id in (1, 2, 3, 4))
    total = passed + failed
    compliance_percent = round((passed / total) * 100, 2) if total else None

    return ComplianceSummaryRow(
        asset_id=str(asset.get("id", "")),
        asset_name=str(asset.get("name", "")),
        asset_type=str(asset.get("type", "")),
        asset_ip_count=int(asset.get("ipCount") or 0),
        audit_file_id=str(audit_file.get("id", "")),
        audit_file_name=str(audit_file.get("name", "")),
        audit_file_filename=str(audit_file.get("filename", "")),
        audit_file_type=str(audit_file.get("type", "")),
        passed_controls=passed,
        failed_controls=failed,
        total_controls=total,
        compliance_percent=compliance_percent,
        info_count=severity_counts[0],
        low_count=severity_counts[1],
        medium_count=severity_counts[2],
        high_count=severity_counts[3],
        critical_count=severity_counts[4],
    )


def write_rows(
    rows: list[ComplianceSummaryRow],
    *,
    output_path: str | Path | None,
    output_format: str,
    pretty: bool = False,
) -> str:
    data = [asdict(row) for row in rows]
    if output_format == "json":
        rendered = json.dumps(data, indent=2 if pretty else None, ensure_ascii=False)
    elif output_format == "csv":
        rendered = render_csv(data)
    else:
        raise ValueError(f"Unsupported output format: {output_format}")

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
    return rendered


def write_errors(errors: list[dict[str, Any]], output_path: str | Path | None) -> None:
    if not output_path or not errors:
        return
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(errors, indent=2, ensure_ascii=False), encoding="utf-8")


def render_csv(data: list[dict[str, Any]]) -> str:
    if not data:
        return ""
    from io import StringIO

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(data[0].keys()), lineterminator="\n")
    writer.writeheader()
    writer.writerows(data)
    return buffer.getvalue()
