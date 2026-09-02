from __future__ import annotations

import argparse
import json
import sys

from . import __version__
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

    if item.get("code_release"):
        print(f"    Code release: {item['code_release']}")
    if item.get("special_build"):
        print(f"    Special build: {item['special_build']}")
    if item.get("build_token"):
        print(f"    Build token: {item['build_token']}")
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
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(args.func(args))
