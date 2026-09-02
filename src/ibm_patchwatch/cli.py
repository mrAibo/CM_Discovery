from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .checks import run_checks
from .config import AppConfig, load_config
from .inventory import patch_targets, product_version, validate_inventory
from .ssh import SSHScanError, collect_inventory
from .storage import connect, latest_scans, save_scan


def _config(path: str) -> AppConfig:
    try:
        return load_config(path)
    except Exception as exc:
        raise SystemExit(f"config error: {exc}") from exc


def _print_product(item: dict, *, details: bool = False) -> None:
    print(f"  {item.get('name', item.get('id')):<46} {product_version(item)}")
    if not details:
        return

    for key, label in (
        ("build", "Build"),
        ("fix_level", "Fix level"),
        ("build_level", "Build level"),
        ("build_number", "Build number"),
        ("build_version", "Build version"),
        ("build_date", "Build date"),
        ("code_release", "Code release"),
        ("special_build", "Special build"),
        ("build_token", "Build token"),
    ):
        if item.get(key) is not None:
            print(f"    {label}: {item[key]}")

    if item.get("im_internal_version"):
        print(f"    IM internal version: {item['im_internal_version']}")
    if item.get("im_version_matches") is False:
        print(f"    WARNING: Installation Manager reports {item.get('im_version')}")

    fixes = item.get("installed_fixes")
    if isinstance(fixes, list) and fixes:
        print("    Installed fixes:")
        for fix in fixes:
            print(f"      - {fix}")

    rollback = item.get("rollback_versions")
    if isinstance(rollback, list) and rollback:
        print("    Rollback levels (history, not additionally installed fixes):")
        for version in rollback:
            print(f"      - {version}")


def _fresh_inventory(cfg: AppConfig, alias: str):
    if alias not in cfg.hosts:
        raise ValueError(f"unknown host: {alias}")
    host = cfg.hosts[alias]
    inventory = collect_inventory(host, cfg.ssh)
    validate_inventory(inventory)
    return host, inventory


def cmd_scan(args: argparse.Namespace) -> int:
    cfg = _config(args.config)
    aliases = list(cfg.hosts) if args.host == "all" else [args.host]
    unknown = [alias for alias in aliases if alias not in cfg.hosts]
    if unknown:
        print(f"unknown host(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    db = connect(cfg.database)
    rc = 0
    outputs = []
    for alias in aliases:
        host = cfg.hosts[alias]
        try:
            inventory = collect_inventory(host, cfg.ssh)
            validate_inventory(inventory)
            scan_id = save_scan(db, alias, host.environment, inventory)
        except (SSHScanError, ValueError) as exc:
            print(f"{alias}: ERROR: {exc}", file=sys.stderr)
            rc = 1
            continue

        if args.json:
            outputs.append({
                "host_alias": alias,
                "environment": host.environment,
                "scan_id": scan_id,
                "inventory": inventory,
            })
            continue

        remote = (inventory.get("host") or {}).get("hostname", "?")
        print(f"{alias} ({host.environment}) -> {remote}  scan={scan_id}")
        for item in patch_targets(inventory):
            _print_product(item, details=args.details)

    if args.json:
        print(json.dumps(outputs, ensure_ascii=False, indent=2 if args.pretty else None))
    return rc


def cmd_inventory(args: argparse.Namespace) -> int:
    cfg = _config(args.config)
    db = connect(cfg.database)
    rows = latest_scans(db)

    if args.json:
        payload = []
        for row in rows:
            payload.append({
                "scan_id": row["id"],
                "host_alias": row["host_alias"],
                "environment": row["environment"],
                "remote_hostname": row["remote_hostname"],
                "collector_version": row["collector_version"],
                "collected_at": row["collected_at"],
                "inventory": json.loads(row["inventory_json"]),
            })
        print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
        return 0

    if not rows:
        print("No scans stored yet.")
        return 0

    for row in rows:
        inventory = json.loads(row["inventory_json"])
        print(f"{row['host_alias']} ({row['environment']}) {row['remote_hostname'] or '?'}  {row['collected_at']}")
        for item in patch_targets(inventory):
            _print_product(item, details=args.details)
    return 0


def _available_label(result: dict) -> str:
    available = result.get("available") or {}
    product_id = result.get("product_id")
    if product_id == "db2":
        return " ".join(
            str(x) for x in (
                available.get("version"),
                available.get("special_build"),
                available.get("ptf"),
            ) if x
        )
    if product_id == "content_manager":
        version = str(available.get("version") or "?")
        fp = available.get("fix_pack")
        return f"{version} (FP{fp})" if fp is not None else version
    if product_id == "content_navigator":
        version = str(available.get("version") or "?")
        ifix = available.get("interim_fix")
        build = available.get("build_level")
        parts = [version]
        if ifix is not None:
            parts.append(f"IF{ifix}")
        if build:
            parts.append(str(build))
        return " ".join(parts)
    if product_id == "daeja_viewone_virtual":
        version = str(available.get("version") or "?")
        ifix = available.get("interim_fix")
        return f"{version} iFix {ifix}" if ifix is not None else version
    if product_id == "iccsap":
        version = str(available.get("version") or "?")
        jre = available.get("jre_version")
        return f"{version} / embedded JRE {jre}" if jre else version
    return str(available.get("version") or "?")


def cmd_check(args: argparse.Namespace) -> int:
    cfg = _config(args.config)
    try:
        host, inventory = _fresh_inventory(cfg, args.host)
    except (SSHScanError, ValueError) as exc:
        print(f"{args.host}: ERROR: {exc}", file=sys.stderr)
        return 1

    db = connect(cfg.database)
    scan_id = save_scan(db, args.host, host.environment, inventory)
    results = run_checks(inventory)

    payload = {
        "host_alias": args.host,
        "environment": host.environment,
        "scan_id": scan_id,
        "inventory": inventory,
        "checks": results,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
        return 1 if any(r.get("status") == "error" for r in results) else 0

    names = {
        item.get("id"): item.get("name", item.get("id"))
        for item in inventory.get("products", [])
        if isinstance(item, dict)
    }
    remote = (inventory.get("host") or {}).get("hostname", "?")
    print(f"{args.host} ({host.environment}) -> {remote}  scan={scan_id}")
    for result in results:
        product_id = result.get("product_id")
        name = str(names.get(product_id, product_id))
        status = result.get("status", "unknown")
        installed = (result.get("installed") or {}).get("version", "?")

        if status == "not_checked":
            print(f"  {name:<46} {installed:<18} NOT CHECKED")
            continue
        if status == "error":
            print(f"  {name:<46} {installed:<18} ERROR")
            print(f"    {result.get('error', 'unknown error')}")
            continue

        available = _available_label(result)
        marker = {
            "current": "CURRENT",
            "update_available": "UPDATE AVAILABLE",
            "review_required": "REVIEW REQUIRED",
        }.get(str(status), str(status).upper())
        print(f"  {name:<46} {installed:<18} {marker}")
        print(f"    IBM available: {available}")
        if result.get("cumulative") is True:
            print("    Maintenance stream: cumulative")
        elif result.get("cumulative") is None:
            print("    Maintenance stream: cumulative status not assumed")
        if result.get("ifx_audit"):
            print(f"    Interim-fix audit: {str(result['ifx_audit']).upper()}")
        if result.get("source_mode") == "catalog":
            stamp = result.get("catalog_generated_at") or "unknown"
            stale = " STALE" if result.get("catalog_stale") else ""
            print(f"    Source mode: GitHub IBM catalog ({stamp}){stale}")
            if result.get("live_error"):
                print(f"    Live IBM: unavailable ({result['live_error']})")
        else:
            print("    Source mode: live IBM")
        if result.get("source_url"):
            print(f"    IBM source: {result['source_url']}")

    errors = any(r.get("status") == "error" for r in results)
    stale = any(r.get("catalog_stale") for r in results)
    return 1 if errors or stale else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ibm-patchwatch")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--config", default="config.toml", help="path to TOML config")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="run remote discovery and store a snapshot")
    scan.add_argument("host", help="configured SSH alias or 'all'")
    scan.add_argument("--json", action="store_true")
    scan.add_argument("--pretty", action="store_true")
    scan.add_argument("--details", action="store_true", help="show installed fixes and rollback history")
    scan.set_defaults(func=cmd_scan)

    inventory = sub.add_parser("inventory", help="show latest stored inventory")
    inventory.add_argument("--json", action="store_true")
    inventory.add_argument("--pretty", action="store_true")
    inventory.add_argument("--details", action="store_true", help="show installed fixes and rollback history")
    inventory.set_defaults(func=cmd_inventory)

    check = sub.add_parser("check", help="fresh scan plus IBM maintenance check (live with catalog fallback)")
    check.add_argument("host", help="configured SSH alias")
    check.add_argument("--json", action="store_true")
    check.add_argument("--pretty", action="store_true")
    check.set_defaults(func=cmd_check)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(args.func(args))
