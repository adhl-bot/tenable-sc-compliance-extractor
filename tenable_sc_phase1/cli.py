from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any

from .compliance import extract_compliance_summary, write_errors, write_rows
from .config import TenableConfig, load_env_file
from .details import extract_compliance_details, write_details_output
from .tenable_client import TenableAPIError, TenableSCClient


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    load_env_file(args.env)
    config = TenableConfig.from_env(timeout=args.timeout)

    try:
        with TenableSCClient(config) as client:
            if args.command == "assets":
                print_json(client.list_assets(), pretty=args.pretty)
            elif args.command == "audit-files":
                print_json(client.list_audit_files(), pretty=args.pretty)
            elif args.command == "extract":
                rows, errors = extract_compliance_summary(
                    client,
                    asset_ids=args.asset_id,
                    asset_name_contains=args.asset_name_contains,
                    audit_file_ids=args.audit_file_id,
                    audit_file_name_contains=args.audit_file_name_contains,
                    include_zero_ip=args.include_zero_ip,
                    include_empty=args.include_empty,
                    limit_assets=args.limit_assets,
                    limit_audit_files=args.limit_audit_files,
                )
                rendered = write_rows(
                    rows,
                    output_path=args.output,
                    output_format=args.format,
                    pretty=args.pretty,
                )
                write_errors(errors, args.errors_output)
                if args.output:
                    print(
                        json.dumps(
                            {
                                "rows": len(rows),
                                "errors": len(errors),
                                "output": args.output,
                                "errors_output": args.errors_output if errors else None,
                            },
                            indent=2,
                        )
                    )
                else:
                    print(rendered)
                    if errors:
                        print_json({"errors": errors}, pretty=True, file=sys.stderr)
            elif args.command == "details":
                data = extract_compliance_details(
                    client,
                    asset_ids=args.asset_id,
                    asset_names=args.asset_name,
                    asset_name_contains=args.asset_name_contains,
                    audit_file_ids=args.audit_file_id,
                    page_size=args.page_size,
                    max_records=args.max_records,
                )
                rendered = write_details_output(
                    data,
                    output_path=args.output,
                    pretty=args.pretty,
                )
                if args.output:
                    print(
                        json.dumps(
                            {
                                "phase": data["phase"],
                                "record_count": data["record_count"],
                                "asset_count": len(data["assets"]),
                                "errors": len(data["errors"]),
                                "output": args.output,
                            },
                            indent=2,
                        )
                    )
                else:
                    print(rendered)
            else:
                parser.print_help()
                return 2
    except TenableAPIError as exc:
        print(f"Tenable.sc API error: {exc}", file=sys.stderr)
        if exc.status is not None or exc.error_code is not None:
            print(
                f"status={exc.status or ''} error_code={exc.error_code or ''}",
                file=sys.stderr,
            )
        return 1

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract Tenable.sc compliance data for phase 1."
    )
    parser.add_argument("--env", default=".env", help="Path to env file")
    parser.add_argument("--timeout", type=int, default=None, help="HTTP timeout seconds")
    subparsers = parser.add_subparsers(dest="command")

    assets = subparsers.add_parser("assets", help="List usable Asset Lists")
    assets.add_argument("--pretty", action="store_true", help="Pretty-print JSON")

    audit_files = subparsers.add_parser("audit-files", help="List usable audit files")
    audit_files.add_argument("--pretty", action="store_true", help="Pretty-print JSON")

    extract = subparsers.add_parser("extract", help="Extract compliance summary")
    extract.add_argument("--asset-id", type=int, action="append", help="Asset List ID")
    extract.add_argument(
        "--asset-name-contains",
        action="append",
        help="Case-insensitive Asset List name substring",
    )
    extract.add_argument(
        "--audit-file-id",
        type=int,
        action="append",
        help="Audit file ID",
    )
    extract.add_argument(
        "--audit-file-name-contains",
        action="append",
        help="Case-insensitive audit file name substring",
    )
    extract.add_argument(
        "--include-zero-ip",
        action="store_true",
        help="Include Asset Lists with ipCount=0",
    )
    extract.add_argument(
        "--include-empty",
        action="store_true",
        help="Include asset/audit combinations with no compliance records",
    )
    extract.add_argument("--limit-assets", type=int, help="Limit selected assets")
    extract.add_argument("--limit-audit-files", type=int, help="Limit selected audits")
    extract.add_argument(
        "--format",
        choices=["json", "csv"],
        default="json",
        help="Output format",
    )
    extract.add_argument("--output", help="Output path")
    extract.add_argument(
        "--errors-output",
        default="outputs/compliance_errors.json",
        help="Path to write per-asset/audit API errors",
    )
    extract.add_argument("--pretty", action="store_true", help="Pretty-print JSON")

    details = subparsers.add_parser(
        "details",
        help="Extract phase 1A compliance details grouped by Asset List",
    )
    details.add_argument("--asset-id", type=int, action="append", help="Asset List ID")
    details.add_argument(
        "--asset-name",
        action="append",
        help="Exact Asset List name. Can be supplied multiple times",
    )
    details.add_argument(
        "--asset-name-contains",
        action="append",
        help="Case-insensitive Asset List name substring",
    )
    details.add_argument(
        "--audit-file-id",
        type=int,
        action="append",
        help="Optional audit file ID filter",
    )
    details.add_argument(
        "--page-size",
        type=int,
        default=200,
        help="Tenable.sc analysis page size",
    )
    details.add_argument(
        "--max-records",
        type=int,
        help="Optional cap for validation runs",
    )
    details.add_argument("--output", help="Output JSON path")
    details.add_argument("--pretty", action="store_true", help="Pretty-print JSON")

    return parser


def print_json(data: Any, *, pretty: bool, file=sys.stdout) -> None:
    if hasattr(data, "__dataclass_fields__"):
        data = asdict(data)
    print(json.dumps(data, indent=2 if pretty else None, ensure_ascii=False), file=file)
