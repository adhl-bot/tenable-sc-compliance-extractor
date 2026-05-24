from __future__ import annotations

import html
import ipaddress
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .compliance import filter_assets
from .tenable_client import TenableAPIError, TenableSCClient


TAG_PATTERN_TEMPLATE = r"<cm:{tag}>(.*?)</cm:{tag}>"


def extract_compliance_details(
    client: TenableSCClient,
    *,
    asset_ids: list[int] | None = None,
    asset_names: list[str] | None = None,
    asset_name_contains: list[str] | None = None,
    audit_file_ids: list[int] | None = None,
    page_size: int = 200,
    max_records: int | None = None,
) -> dict[str, Any]:
    assets = select_assets(
        client,
        asset_ids=asset_ids,
        asset_names=asset_names,
        asset_name_contains=asset_name_contains,
    )
    extracted_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    output_assets: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for asset in assets:
        asset_detail = client.get_asset(asset["id"])
        query_filters = build_detail_filters(
            asset_detail,
            audit_file_ids=audit_file_ids,
            use_asset_id=True,
        )
        fallback_used = False
        records: list[dict[str, Any]] = []

        try:
            raw_records = fetch_all_detail_records(
                client,
                filters=query_filters,
                page_size=page_size,
                max_records=max_records,
            )
        except TenableAPIError as exc:
            if not is_missing_asset_uuid_error(exc):
                errors.append(asset_error(asset_detail, exc, fallback_used=False))
                raw_records = []
            else:
                fallback_filters = build_detail_filters(
                    asset_detail,
                    audit_file_ids=audit_file_ids,
                    use_asset_id=False,
                )
                fallback_used = True
                try:
                    raw_records = fetch_all_detail_records(
                        client,
                        filters=fallback_filters,
                        page_size=page_size,
                        max_records=max_records,
                    )
                except TenableAPIError as fallback_exc:
                    errors.append(
                        asset_error(asset_detail, fallback_exc, fallback_used=True)
                    )
                    raw_records = []

        for raw_record in raw_records:
            records.append(normalize_detail_record(asset_detail, raw_record))

        records.sort(key=lambda record: ip_sort_key(record.get("ip", "")))
        output_assets.append(
            {
                "asset": normalize_asset(asset_detail),
                "query": {
                    "source_type": "cumulative",
                    "tool": "vulndetails",
                    "used_ip_fallback": fallback_used,
                },
                "records": records,
            }
        )

    return {
        "extracted_at": extracted_at,
        "phase": "1A",
        "record_count": sum(len(asset["records"]) for asset in output_assets),
        "assets": output_assets,
        "errors": errors,
    }


def select_assets(
    client: TenableSCClient,
    *,
    asset_ids: list[int] | None,
    asset_names: list[str] | None,
    asset_name_contains: list[str] | None,
) -> list[dict[str, Any]]:
    assets = client.list_assets()
    if asset_names:
        wanted = {asset_name.lower() for asset_name in asset_names}
        assets = [asset for asset in assets if str(asset.get("name", "")).lower() in wanted]
    return filter_assets(
        assets,
        asset_ids=asset_ids,
        asset_name_contains=asset_name_contains,
        include_zero_ip=True,
    )


def build_detail_filters(
    asset: dict[str, Any],
    *,
    audit_file_ids: list[int] | None,
    use_asset_id: bool,
) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = [
        {"filterName": "pluginType", "operator": "=", "value": "compliance"},
    ]
    if use_asset_id:
        filters.append(
            {"filterName": "assetID", "operator": "=", "value": str(asset["id"])}
        )
    else:
        defined_ips = str((asset.get("typeFields") or {}).get("definedIPs") or "")
        if not defined_ips:
            raise TenableAPIError(
                f"Asset {asset.get('name')} cannot fallback to ip filter: missing definedIPs"
            )
        filters.append({"filterName": "ip", "operator": "=", "value": defined_ips})

    for audit_file_id in audit_file_ids or []:
        filters.append(
            {
                "filterName": "auditFileID",
                "operator": "=",
                "value": str(audit_file_id),
            }
        )
    return filters


def fetch_all_detail_records(
    client: TenableSCClient,
    *,
    filters: list[dict[str, Any]],
    page_size: int,
    max_records: int | None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    start_offset = 0
    while True:
        if max_records is not None and len(records) >= max_records:
            return records[:max_records]
        current_page_size = page_size
        if max_records is not None:
            current_page_size = min(page_size, max_records - len(records))
        response = client.compliance_details(
            filters=filters,
            start_offset=start_offset,
            end_offset=start_offset + current_page_size,
        )
        records.extend(response.results)
        if response.returned_records == 0 or len(records) >= response.total_records:
            break
        start_offset += response.returned_records
    return records[:max_records] if max_records is not None else records


def normalize_detail_record(
    asset: dict[str, Any],
    record: dict[str, Any],
) -> dict[str, Any]:
    plugin_text = str(record.get("pluginText") or "")
    last_seen_epoch = str(record.get("lastSeen") or "")
    actual_values = compliance_tag_values(plugin_text, "compliance-actual-value")
    compliance_results = compliance_tag_values(plugin_text, "compliance-result")
    observed_audit_files = compliance_tag_values(plugin_text, "compliance-audit-file")
    policy_values = compliance_tag_values(plugin_text, "compliance-policy-value")
    references = compliance_tag_values(plugin_text, "compliance-reference")
    return {
        "asset": str(asset.get("name", "")),
        "ip": str(record.get("ip") or ""),
        "plugin_id": str(record.get("pluginID") or ""),
        "vuln_uuid": str(record.get("vulnUUID") or ""),
        "control_name": compliance_tag(plugin_text, "compliance-check-name")
        or str(record.get("pluginName") or record.get("name") or ""),
        "compliance_results": compliance_results,
        "actual_values": actual_values,
        "actual_value": first_non_empty(actual_values) or "",
        "observed_audit_files": observed_audit_files,
        "policy_values": policy_values,
        "references": references,
        "last_observed": epoch_to_iso(last_seen_epoch),
        "last_observed_epoch": int(last_seen_epoch) if last_seen_epoch.isdigit() else None,
    }


def normalize_asset(asset: dict[str, Any]) -> dict[str, Any]:
    type_fields = asset.get("typeFields") or {}
    return {
        "id": str(asset.get("id", "")),
        "name": str(asset.get("name", "")),
        "type": str(asset.get("type", "")),
        "defined_ips": str(type_fields.get("definedIPs") or ""),
    }


def compliance_tag(plugin_text: str, tag: str) -> str | None:
    values = compliance_tag_values(plugin_text, tag)
    return first_non_empty(values)


def first_non_empty(values: list[str]) -> str | None:
    if not values:
        return None
    for value in values:
        if value.strip():
            return value.strip()
    return values[0].strip()


def compliance_tag_values(plugin_text: str, tag: str) -> list[str]:
    pattern = TAG_PATTERN_TEMPLATE.format(tag=re.escape(tag))
    values = re.findall(pattern, plugin_text, flags=re.DOTALL)
    return [html.unescape(value).strip() for value in values]


def epoch_to_iso(value: str) -> str | None:
    if not value.isdigit():
        return None
    return datetime.fromtimestamp(int(value), UTC).isoformat().replace("+00:00", "Z")


def is_missing_asset_uuid_error(exc: TenableAPIError) -> bool:
    return "Error loading uuid file into UUID list" in str(exc)


def asset_error(
    asset: dict[str, Any],
    exc: TenableAPIError,
    *,
    fallback_used: bool,
) -> dict[str, Any]:
    return {
        "asset_id": str(asset.get("id", "")),
        "asset_name": str(asset.get("name", "")),
        "fallback_used": fallback_used,
        "status": exc.status,
        "error_code": exc.error_code,
        "message": str(exc),
    }


def ip_sort_key(ip: str) -> tuple[int, int | str]:
    try:
        return (0, int(ipaddress.ip_address(ip)))
    except ValueError:
        return (1, ip)


def write_details_output(
    data: dict[str, Any],
    *,
    output_path: str | Path | None,
    pretty: bool,
) -> str:
    rendered = json.dumps(data, indent=2 if pretty else None, ensure_ascii=False)
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
    return rendered
