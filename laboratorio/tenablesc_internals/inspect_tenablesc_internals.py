from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_CONTAINER = "tenablesc-labbox-ol8"
ORG_ID = "1"
MAX_CAPTURE_CHARS = 20_000

SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(accesskey\s*=\s*)[^;\s]+"),
    re.compile(r"(?i)(secretkey\s*=\s*)[^;\s]+"),
    re.compile(r"(?i)(password\s*[:=]\s*)[^;\s]+"),
    re.compile(r"(?i)(secret\s*[:=]\s*)[^;\s]+"),
    re.compile(r"(?i)(token\s*[:=]\s*)[^;\s]+"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[^;\s]+"),
]

SKIP_PATH_MARKERS = (
    "license.key",
    "/opt/sc/daemons/license",
    "/opt/sc/support/conf/nessus",
)


def redact_text(value: str) -> str:
    redacted = value
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub(lambda match: f"{match.group(1)}<redacted>", redacted)
    return redacted


def truncate_text(value: str) -> str:
    if len(value) <= MAX_CAPTURE_CHARS:
        return value
    omitted = len(value) - MAX_CAPTURE_CHARS
    return f"{value[:MAX_CAPTURE_CHARS]}\n...[truncated {omitted} chars]"


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def run(args: list[str], timeout: int = 60) -> dict[str, Any]:
    completed = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
    )
    stdout = completed.stdout.decode("utf-8", errors="replace").strip()
    stderr = completed.stderr.decode("utf-8", errors="replace").strip()
    stdout = truncate_text(stdout)
    stderr = truncate_text(stderr)
    return redact(
        {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
    )


def docker_exec(container: str, command: str, timeout: int = 60) -> dict[str, Any]:
    if any(marker in command for marker in SKIP_PATH_MARKERS):
        return {"ok": False, "returncode": None, "stdout": "", "stderr": "blocked sensitive path"}
    return run(["docker", "exec", container, "sh", "-lc", command], timeout=timeout)


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def parse_pipe_table(result: dict[str, Any]) -> list[list[str]]:
    if not result.get("ok") or not result.get("stdout"):
        return []
    return [line.split("|") for line in str(result["stdout"]).splitlines() if line.strip()]


def pg_sql(container: str, sql: str, timeout: int = 60) -> dict[str, Any]:
    command = (
        "env LD_LIBRARY_PATH=/opt/sc/support/lib "
        "/opt/sc/support/bin/psql -h 127.0.0.1 -p 5432 -U tns "
        "-d SecurityCenter -At -F '|' -c "
        f"{shell_quote(sql)}"
    )
    return docker_exec(container, command, timeout=timeout)


def sqlite_sql(container: str, db_path: str, sql: str, timeout: int = 60) -> dict[str, Any]:
    command = (
        "/opt/sc/support/bin/sqlite3 -readonly -separator '|' "
        f"{shell_quote(db_path)} {shell_quote(sql)}"
    )
    return docker_exec(container, command, timeout=timeout)


def collect_processes(container: str) -> dict[str, Any]:
    return {
        "process_inventory": docker_exec(
            container,
            "ps -eo user,pid,ppid,stat,comm,args | "
            "awk '/supervisord|httpd|Jobd|postgres|redis-server|WebSocketServer|sc-asset-svc|microservice-supervisor/ && !/awk/ {print}'",
        ),
        "supervisor_status": docker_exec(container, "supervisorctl -c /etc/supervisord-tenablesc.conf status"),
        "listening_ports": docker_exec(
            container,
            "if command -v ss >/dev/null 2>&1; then ss -ltnp; "
            "elif command -v netstat >/dev/null 2>&1; then netstat -ltnp; fi | "
            "awk 'NR==1 || /:443|:5432|:6379|:8840|:9080/'",
        ),
    }


def collect_service_probes(container: str) -> dict[str, Any]:
    return {
        "postgres_select_1": pg_sql(container, "select 1;"),
        "redis_ping": docker_exec(container, "/opt/sc/support/bin/redis-cli -h 127.0.0.1 -p 6379 ping"),
        "api_status_no_auth": docker_exec(
            container,
            "curl -k -sS -o - -w '\\nHTTP_STATUS=%{http_code}\\n' https://127.0.0.1/rest/status",
        ),
        "asset_service_http": docker_exec(
            container,
            "curl -sS -o - -w '\\nHTTP_STATUS=%{http_code}\\n' http://127.0.0.1:8840/",
        ),
        "java_version": docker_exec(container, "java -version 2>&1 | head -3"),
        "fop_command_probe": docker_exec(
            container,
            "SC_ROOT=/opt/sc /opt/sc/fop/fop 2>/dev/null | head -1 | cut -c 1-320",
        ),
    }


def collect_filesystem(container: str) -> dict[str, Any]:
    repo_files = docker_exec(
        container,
        "find /opt/sc/repositories -maxdepth 2 -type f "
        "\\( -name '*.db' -o -name '*.raw' -o -name '*.lck' \\) "
        "-printf '%p|%s\\n' 2>/dev/null | sort",
        timeout=120,
    )
    asset_counts = docker_exec(
        container,
        f"find /opt/sc/orgs/{ORG_ID}/assets -type f -printf '%f|%s\\n' 2>/dev/null | "
        "awk -F'|' '{n++; suffix=\"<none>\"; if ($1 ~ /\\./) {suffix=$1; sub(/^.*\\./,\".\",suffix)} "
        "count[suffix]++; if ($2 == 0) zero[suffix]++} "
        "END {print \"total_files|\" n; for (s in count) print \"suffix|\" s \"|\" count[s] \"|\" zero[s]+0}'",
        timeout=120,
    )
    asset_sample = docker_exec(
        container,
        f"find /opt/sc/orgs/{ORG_ID}/assets -type f -printf '%f|%s|%p\\n' 2>/dev/null | sort | head -120",
        timeout=120,
    )
    scan_progress = docker_exec(
        container,
        "find /opt/sc/data/scans -maxdepth 2 -name progress.db -printf '%h|%s\\n' 2>/dev/null | sort",
        timeout=120,
    )
    return {
        "df": docker_exec(container, "df -h /dev/shm /tmp /opt/sc 2>/dev/null"),
        "du_key_paths": docker_exec(
            container,
            "du -sh /opt/sc/admin /opt/sc/bin /opt/sc/data /opt/sc/orgs /opt/sc/repositories "
            "/opt/sc/src /opt/sc/support /opt/sc/fop /opt/sc/www 2>/dev/null",
            timeout=120,
        ),
        "repository_files": repo_files,
        "repository_file_summary": summarize_repository_files(repo_files.get("stdout", "")),
        "asset_artifact_counts": asset_counts,
        "asset_artifacts_sample": asset_sample,
        "asset_artifact_summary": parse_asset_counts(asset_counts.get("stdout", "")),
        "scan_progress_dbs": scan_progress,
        "scan_progress_summary": summarize_scan_progress(scan_progress.get("stdout", "")),
    }


def summarize_repository_files(stdout: str) -> dict[str, Any]:
    summary: dict[str, Any] = {"repositories": {}, "total_files": 0, "total_bytes": 0}
    for line in stdout.splitlines():
        parts = line.split("|")
        if len(parts) != 2:
            continue
        path, size_text = parts
        try:
            size = int(size_text)
        except ValueError:
            size = 0
        repo_id = path.split("/repositories/", 1)[-1].split("/", 1)[0]
        repo = summary["repositories"].setdefault(repo_id, {"files": 0, "bytes": 0, "key_files": {}})
        repo["files"] += 1
        repo["bytes"] += size
        summary["total_files"] += 1
        summary["total_bytes"] += size
        basename = path.rsplit("/", 1)[-1]
        if basename in {
            "hdb.db",
            "hdb.raw",
            "hdb-patched.db",
            "hdb-patched.raw",
            "namedb.db",
            "namedb.raw",
            "vulns.db",
            "compliance_plugins.db",
        }:
            repo["key_files"][basename] = size
    return summary


def summarize_asset_files(stdout: str) -> dict[str, Any]:
    summary: dict[str, Any] = {"by_suffix": {}, "zero_byte_by_suffix": {}, "total_files": 0}
    for line in stdout.splitlines():
        parts = line.split("|")
        if len(parts) != 3:
            continue
        name, size_text, _path = parts
        try:
            size = int(size_text)
        except ValueError:
            size = 0
        suffix = "." + name.rsplit(".", 1)[-1] if "." in name else "<none>"
        summary["by_suffix"][suffix] = summary["by_suffix"].get(suffix, 0) + 1
        if size == 0:
            summary["zero_byte_by_suffix"][suffix] = summary["zero_byte_by_suffix"].get(suffix, 0) + 1
        summary["total_files"] += 1
    return summary


def parse_asset_counts(stdout: str) -> dict[str, Any]:
    summary: dict[str, Any] = {"by_suffix": {}, "zero_byte_by_suffix": {}, "total_files": 0}
    for line in stdout.splitlines():
        parts = line.split("|")
        if not parts:
            continue
        if parts[0] == "total_files" and len(parts) == 2:
            try:
                summary["total_files"] = int(parts[1])
            except ValueError:
                summary["total_files"] = 0
        elif parts[0] == "suffix" and len(parts) == 4:
            suffix = parts[1]
            try:
                summary["by_suffix"][suffix] = int(parts[2])
                summary["zero_byte_by_suffix"][suffix] = int(parts[3])
            except ValueError:
                continue
    return summary


def summarize_scan_progress(stdout: str) -> dict[str, Any]:
    rows = [line for line in stdout.splitlines() if line.strip()]
    return {
        "progress_db_count": len(rows),
        "latest_paths": rows[-10:],
    }


def collect_postgres(container: str) -> dict[str, Any]:
    key_tables = [
        "public.asset",
        "public.finding_nessus",
        "public.finding_nessus_output",
        "public.plugin",
        "public.pluginxref",
        "public.repository",
        "public.complianceplugin",
        "jobqueue.jobqueue",
    ]
    table_counts = {}
    for table in key_tables:
        table_counts[table] = pg_sql(container, f"select count(*) from {table};")
    column_tables = ["asset", "finding_nessus", "finding_nessus_output", "plugin", "repository"]
    columns = {
        table: pg_sql(
            container,
            "select column_name || ':' || data_type "
            "from information_schema.columns "
            f"where table_schema='public' and table_name='{table}' "
            "order by ordinal_position;",
        )
        for table in column_tables
    }
    return {
        "version": pg_sql(container, "select current_database(), current_user, version();"),
        "schema_table_counts": pg_sql(
            container,
            "select schemaname, count(*) from pg_tables "
            "where schemaname in ('public','jobqueue') group by schemaname order by schemaname;",
        ),
        "key_table_counts": table_counts,
        "key_table_sizes": pg_sql(
            container,
            "select n.nspname || '.' || c.relname, pg_total_relation_size(c.oid) "
            "from pg_class c join pg_namespace n on n.oid=c.relnamespace "
            "where n.nspname in ('public','jobqueue') "
            "and c.relname in ('asset','finding_nessus','finding_nessus_output','plugin','pluginxref','repository','complianceplugin','jobqueue') "
            "order by 1;",
        ),
        "columns": columns,
        "asset_distribution_by_repository": pg_sql(
            container,
            "select repository_id, count(*) from public.asset group by repository_id order by repository_id;",
        ),
        "finding_distribution_by_repository_plugin_state": pg_sql(
            container,
            "select repository_id, plugin_id, risk_factor_num, state, count(*) "
            "from public.finding_nessus "
            "group by repository_id, plugin_id, risk_factor_num, state "
            "order by repository_id, plugin_id, risk_factor_num, state;",
        ),
        "jobqueue_count": pg_sql(container, "select count(*) from jobqueue.jobqueue;"),
    }


def sqlite_count(container: str, db_path: str, table: str) -> dict[str, Any]:
    return sqlite_sql(container, db_path, f"select count(*) from {table};")


def collect_sqlite(container: str) -> dict[str, Any]:
    dbs = {
        "application": "/opt/sc/application.db",
        "organization_1": f"/opt/sc/orgs/{ORG_ID}/organization.db",
        "assets_1": f"/opt/sc/orgs/{ORG_ID}/assets.db",
        "jobqueue": "/opt/sc/jobqueue.db",
        "tvdb": "/opt/sc/data/tvdb/tvdb.db",
    }
    application_counts = {
        table: sqlite_count(container, dbs["application"], table)
        for table in ("Repository", "OrgRepository", "Scanner", "PolicyTemplate")
    }
    organization_counts = {
        table: sqlite_count(container, dbs["organization_1"], table)
        for table in ("Scan", "ScanResult", "Policy", "AuditFile", "PolicyAuditFile", "ReportDefinition", "ReportResult", "Query")
    }
    assets_counts = {
        table: sqlite_count(container, dbs["assets_1"], table)
        for table in ("Asset", "AssetClause", "AssetIPCount", "IPList", "DNSNameList")
    }
    return {
        "database_files": docker_exec(
            container,
            "find /opt/sc -maxdepth 4 -type f -name '*.db' "
            "-printf '%p|%s\\n' 2>/dev/null | grep -v '/VDB/' | sort | head -120",
            timeout=120,
        ),
        "vdb_db_count": docker_exec(
            container,
            f"find /opt/sc/orgs/{ORG_ID}/VDB -type f -name '*.db' 2>/dev/null | wc -l",
            timeout=120,
        ),
        "application": {
            "path": dbs["application"],
            "version": sqlite_sql(
                container,
                dbs["application"],
                "select value from Configuration where name='Version';",
            ),
            "table_count": sqlite_sql(
                container,
                dbs["application"],
                "select count(*) from sqlite_master where type='table';",
            ),
            "key_counts": application_counts,
            "repositories": sqlite_sql(
                container,
                dbs["application"],
                "select id,name,type,dataFormat,vulnCount,running,downloadFormat from Repository order by id;",
            ),
            "scanners": sqlite_sql(
                container,
                dbs["application"],
                "select id,name,ip,port,status,version from Scanner order by id;",
            ),
        },
        "organization_1": {
            "path": dbs["organization_1"],
            "table_count": sqlite_sql(
                container,
                dbs["organization_1"],
                "select count(*) from sqlite_master where type='table';",
            ),
            "key_counts": organization_counts,
            "recent_scan_results": sqlite_sql(
                container,
                dbs["organization_1"],
                "select id,name,status,importStatus,repositoryID,jobID,startTime,finishTime "
                "from ScanResult order by id desc limit 10;",
            ),
            "policies_audit_files": sqlite_sql(
                container,
                dbs["organization_1"],
                "select policyID,auditFileID from PolicyAuditFile order by policyID,auditFileID limit 50;",
            ),
            "audit_files": sqlite_sql(
                container,
                dbs["organization_1"],
                "select id,name,type,status,filename,originalFilename from AuditFile order by id desc limit 20;",
            ),
        },
        "assets_1": {
            "path": dbs["assets_1"],
            "table_count": sqlite_sql(
                container,
                dbs["assets_1"],
                "select count(*) from sqlite_master where type='table';",
            ),
            "key_counts": assets_counts,
            "asset_ip_counts": sqlite_sql(
                container,
                dbs["assets_1"],
                "select assetID,groupID,repID,ipCount from AssetIPCount order by assetID,groupID,repID limit 120;",
            ),
        },
        "jobqueue_legacy": {
            "path": dbs["jobqueue"],
            "table_count": sqlite_sql(
                container,
                dbs["jobqueue"],
                "select count(*) from sqlite_master where type='table';",
            ),
            "tables": sqlite_sql(
                container,
                dbs["jobqueue"],
                "select name from sqlite_master where type='table' order by name;",
            ),
        },
    }


def collect_code_references(container: str) -> dict[str, Any]:
    return {
        "analysis_engine": docker_exec(
            container,
            "grep -R --exclude=Configuration.php "
            "\"SHOW_VULNS_BIN\\|GO_VULNS_BIN\\|AnalysisV2\\|sourceType\" "
            "-n /opt/sc/src/lib /opt/sc/src/rest 2>/dev/null | head -80 | cut -c 1-260",
        ),
        "asset_preparation": docker_exec(
            container,
            "grep -R --exclude=Configuration.php "
            "\"prepareassetsWrapper\\|getViewableUUIDsForRep\\|uuidd\\|ipd\" "
            "-n /opt/sc/src /opt/sc/bin 2>/dev/null | head -100 | cut -c 1-260",
        ),
        "reports_fop": docker_exec(
            container,
            "grep -R --exclude=Configuration.php \"fop/fop\\|ReportGenerateLib\\|Java heap\" "
            "-n /opt/sc/src/lib /opt/sc/src/tools 2>/dev/null | head -80 | cut -c 1-260",
        ),
        "microservice_supervisor": docker_exec(
            container,
            "sed -n '1,220p' /opt/sc/bin/services/microservice-supervisor.sh 2>/dev/null",
        ),
    }


def collect_logs(container: str) -> dict[str, Any]:
    pattern = "ERROR|CRITICAL|connection refused|Error loading uuid file|memory exhausted|failed|refused"
    return {
        "recent_error_patterns": docker_exec(
            container,
            "for f in /opt/sc/admin/logs/$(date +%Y%m).log "
            "/opt/sc/admin/logs/sc-error.log /opt/sc/admin/logs/postgresql.log "
            "/opt/sc/admin/logs/redis.log /opt/sc/admin/logs/services/microservice-supervisor.log; do "
            "[ -f \"$f\" ] || continue; "
            "echo \"== $f ==\"; "
            f"tail -n 300 \"$f\" | grep -Ei '{pattern}' | tail -20 | cut -c 1-360 || true; "
            "done",
            timeout=120,
        ),
        "parity_check_patterns": docker_exec(
            container,
            "grep -R \"vulnerabilityParityCheck\\|showvulns=.*goVulns\" "
            "-n /opt/sc/admin/logs 2>/dev/null | tail -40 | cut -c 1-360 || true",
            timeout=120,
        ),
    }


def build_health_summary(report: dict[str, Any]) -> dict[str, Any]:
    probes = report["service_probes"]
    processes = report["processes"]
    filesystem = report["filesystem"]
    pg = report["postgres"]
    sqlite = report["sqlite"]

    supervisor_out = processes["supervisor_status"].get("stdout", "")
    api_out = probes["api_status_no_auth"].get("stdout", "")
    asset_svc_out = probes["asset_service_http"].get("stdout", "")
    fop_out = probes["fop_command_probe"].get("stdout", "")
    uuidd_count = filesystem["asset_artifact_summary"].get("by_suffix", {}).get(".uuidd", 0)

    return {
        "apache_and_jobd_under_supervisor": (
            "TenableSC:Apache" in supervisor_out
            and "RUNNING" in supervisor_out
            and "TenableSC:Jobd" in supervisor_out
        ),
        "postgres_accepts_queries": probes["postgres_select_1"].get("ok") and "1" in probes["postgres_select_1"].get("stdout", ""),
        "redis_accepts_ping": probes["redis_ping"].get("stdout") == "PONG",
        "api_route_reachable_without_auth": "HTTP_STATUS=" in api_out,
        "asset_service_reachable": "HTTP_STATUS=" in asset_svc_out,
        "fop_java_wrapper_available": "/usr/bin/java" in fop_out or "java" in fop_out.lower(),
        "asset_uuidd_artifacts_present": uuidd_count > 0,
        "postgres_schema_seen": bool(pg["schema_table_counts"].get("stdout")),
        "sqlite_application_db_seen": bool(sqlite["application"]["version"].get("stdout")),
        "interpretation": (
            "Tenable.sc 6.8 uses PostgreSQL for modern finding/asset/plugin storage while this lab still has "
            "SQLite databases for application, organization, asset-list and legacy/local state. This is expected "
            "because the container was previously on a 6.6-era SQLite-backed release."
        ),
    }


def collect_report(container: str) -> dict[str, Any]:
    report: dict[str, Any] = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "container": container,
        "scope": "read-only Tenable.sc internals inspection; no secrets, license files or scan outputs are intentionally read",
        "docker": {
            "ps": run(["docker", "ps", "--filter", f"name={container}", "--format", "{{json .}}"]),
            "inspect_state": run(["docker", "inspect", container, "--format", "{{json .State}}"]),
            "inspect_shm_size": run(["docker", "inspect", container, "--format", "{{.HostConfig.ShmSize}}"]),
            "inspect_port_bindings": run(
                ["docker", "inspect", container, "--format", "{{json .HostConfig.PortBindings}}"]
            ),
        },
        "processes": collect_processes(container),
        "service_probes": collect_service_probes(container),
        "filesystem": collect_filesystem(container),
        "postgres": collect_postgres(container),
        "sqlite": collect_sqlite(container),
        "code_references": collect_code_references(container),
        "logs": collect_logs(container),
    }
    report["health_summary"] = build_health_summary(report)
    return redact(report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect Tenable.sc internals in the local Docker lab.")
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    parser.add_argument("--output", type=Path, help="Optional JSON output path.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    parser.add_argument("--quiet", action="store_true", help="Do not print the JSON when --output is used.")
    args = parser.parse_args(argv)

    report = collect_report(args.container)
    json_text = json.dumps(report, indent=2 if args.pretty else None, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json_text + "\n", encoding="utf-8")
    if not args.quiet:
        print(json_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
