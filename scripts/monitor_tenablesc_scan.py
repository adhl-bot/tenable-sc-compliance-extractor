from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tenable_sc_phase1.config import TenableConfig, load_env_file
from tenable_sc_phase1.tenable_client import TenableSCClient


FIELDNAMES = [
    "timestamp",
    "scan_result_id",
    "status",
    "import_status",
    "running",
    "created_time",
    "start_time",
    "finish_time",
    "import_start",
    "import_finish",
    "pre_start_seconds",
    "scan_seconds_so_far",
    "post_scan_to_import_start_seconds",
    "import_seconds_so_far",
    "completed_checks",
    "total_checks",
    "completed_ips",
    "total_ips",
    "scanned_ips",
    "scanning_ips",
    "awaiting_download_ips",
    "scanner_name",
    "scanner_load_avg",
    "jobd_running",
    "postgres_ok",
    "redis_ok",
    "latest_log_event",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor a Tenable.sc scan result.")
    parser.add_argument("--scan-name", default="win_10_MODIFICADO")
    parser.add_argument("--env", default=".env")
    parser.add_argument("--output", required=True)
    parser.add_argument("--interval", type=int, default=10)
    parser.add_argument("--max-samples", type=int, default=180)
    args = parser.parse_args()

    load_env_file(args.env)
    config = TenableConfig.from_env(timeout=30)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for sample_index in range(args.max_samples):
            try:
                with TenableSCClient(config) as client:
                    scan_result, detail = newest_scan(client, args.scan_name)
                    if scan_result is None:
                        row = empty_row(f"scan result not found: {args.scan_name}")
                    else:
                        row = row_from(scan_result, detail)
                    writer.writerow(row)
                    handle.flush()
                    if sample_index >= 2 and is_terminal(row):
                        break
            except Exception as exc:  # noqa: BLE001 - monitor should record and continue
                writer.writerow(empty_row(f"monitor error: {type(exc).__name__}: {exc}"))
                handle.flush()
            time.sleep(args.interval)

    return 0


def newest_scan(
    client: TenableSCClient, scan_name: str
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    data = client.request(
        "GET",
        "scanResult",
        params={
            "fields": (
                "id,name,status,importStatus,importStart,importFinish,"
                "importErrorDetails,startTime,finishTime,createdTime,running,"
                "completedChecks,totalChecks,repository"
            )
        },
    )
    rows = [
        item
        for item in data.get("response", {}).get("usable", [])
        if item.get("name") == scan_name
    ]
    rows.sort(key=lambda item: to_int(item.get("createdTime")), reverse=True)
    if not rows:
        return None, {}
    scan_result = rows[0]
    detail = client.request("GET", f"scanResult/{scan_result['id']}").get(
        "response", {}
    )
    return scan_result, detail


def row_from(scan_result: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    progress = detail.get("progress") or {}
    scanners = progress.get("scanners") or []
    scanner = scanners[0] if scanners else {}

    created = to_int(scan_result.get("createdTime"))
    start = to_int(scan_result.get("startTime"))
    finish = to_int(scan_result.get("finishTime"))
    import_start = to_int(scan_result.get("importStart"))
    import_finish = to_int(scan_result.get("importFinish"))
    now = int(time.time())
    jobd, postgres, redis = health()

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "scan_result_id": scan_result.get("id"),
        "status": scan_result.get("status"),
        "import_status": scan_result.get("importStatus"),
        "running": scan_result.get("running"),
        "created_time": scan_result.get("createdTime"),
        "start_time": scan_result.get("startTime"),
        "finish_time": scan_result.get("finishTime"),
        "import_start": scan_result.get("importStart"),
        "import_finish": scan_result.get("importFinish"),
        "pre_start_seconds": start - created if created and start else "",
        "scan_seconds_so_far": elapsed(start, finish, now),
        "post_scan_to_import_start_seconds": (
            import_start - finish if finish and import_start else ""
        ),
        "import_seconds_so_far": elapsed(import_start, import_finish, now),
        "completed_checks": scan_result.get("completedChecks")
        or progress.get("completedChecks"),
        "total_checks": scan_result.get("totalChecks") or progress.get("totalChecks"),
        "completed_ips": progress.get("completedIPs"),
        "total_ips": progress.get("totalIPs"),
        "scanned_ips": progress.get("scannedIPs"),
        "scanning_ips": progress.get("scanningIPs"),
        "awaiting_download_ips": progress.get("awaitingDownloadIPs"),
        "scanner_name": scanner.get("name"),
        "scanner_load_avg": scanner.get("loadAvg"),
        "jobd_running": jobd,
        "postgres_ok": postgres,
        "redis_ok": redis,
        "latest_log_event": latest_log_event(),
    }


def elapsed(start: int, finish: int, now: int) -> int | str:
    if start and finish:
        return finish - start
    if start:
        return now - start
    return ""


def is_terminal(row: dict[str, Any]) -> bool:
    return row.get("status") in {"Completed", "Error", "Partial", "Canceled", "No Scanner"} and row.get(
        "import_status"
    ) in {"Finished", "No Results", "Error"}


def empty_row(message: str) -> dict[str, Any]:
    row = {field: "" for field in FIELDNAMES}
    row["timestamp"] = datetime.now().isoformat(timespec="seconds")
    row["latest_log_event"] = message
    return row


def to_int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def health() -> tuple[str, str, str]:
    jobd_ok, jobd_out, _ = run_sc("pgrep -af 'Jobd.php' >/dev/null && echo yes || echo no")
    pg_ok, pg_out, _ = run_sc(
        "PGPASSWORD=tns /opt/sc/support/bin/psql -h 127.0.0.1 -U tns "
        "-d SecurityCenter -tAc 'select 1' 2>/dev/null"
    )
    redis_ok, redis_out, _ = run_sc(
        "/opt/sc/support/bin/redis-cli -h 127.0.0.1 ping 2>/dev/null"
    )
    return (
        "yes" if jobd_ok and jobd_out.strip() == "yes" else "no",
        "yes" if pg_ok and pg_out.strip() == "1" else "no",
        "yes" if redis_ok and redis_out.strip() == "PONG" else "no",
    )


def latest_log_event() -> str:
    pattern = (
        "Scan job|pluginSync|refreshPostgresMaterializedViews|Import beginning|"
        "Import successful|prepareassets|clearVulnerabilityCache|riskRules|"
        "calculateAssetsRBVM|scannerStatus|scanProgress"
    )
    ok, stdout, stderr = run_sc(
        f"tail -100 /opt/sc/admin/logs/202605.log | grep -E '{pattern}' | tail -1"
    )
    return (stdout if ok else stderr or stdout).replace("\n", " ")


def run_sc(command: str) -> tuple[bool, str, str]:
    return run(["docker", "exec", "tenablesc-labbox-ol8", "sh", "-lc", command])


def run(command: list[str]) -> tuple[bool, str, str]:
    proc = subprocess.run(command, text=True, capture_output=True, timeout=8)
    return proc.returncode == 0, (proc.stdout or "").strip(), (proc.stderr or "").strip()


if __name__ == "__main__":
    raise SystemExit(main())
