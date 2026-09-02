#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from ibm_patchwatch.config import load_config
from ibm_patchwatch.github_catalog import CatalogSnapshot, GitCatalogError, GitCatalogSource
from ibm_patchwatch.inventory import validate_inventory
from ibm_patchwatch.rich_updates import render_host_update_table, render_update_table
from ibm_patchwatch.ssh import SSHScanError, collect_inventory
from ibm_patchwatch.update_report import HostUpdateReport, build_host_update_report


ROOT = Path(__file__).resolve().parents[1]


def _source(args: argparse.Namespace) -> GitCatalogSource:
    return GitCatalogSource(
        Path(args.repo_path),
        remote=args.remote,
        branch=args.branch,
        catalog_path=args.catalog_path,
    )


def _snapshot_key(snapshot: CatalogSnapshot) -> str:
    data = {
        "revision": snapshot.revision,
        "generated_at": snapshot.generated_at,
        "rows": [row.__dict__ for row in snapshot.rows],
    }
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _report_key(report: HostUpdateReport) -> str:
    data = {
        "revision": report.revision,
        "generated_at": report.generated_at,
        "host": report.host_alias,
        "remote": report.remote_hostname,
        "rows": [row.__dict__ for row in report.rows],
    }
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _inventory(args: argparse.Namespace) -> dict:
    if not args.host:
        raise ValueError("host alias is required for an installed-vs-target report")

    cfg = load_config(args.config)
    if args.host not in cfg.hosts:
        raise ValueError(f"unknown host {args.host!r}; configured: {', '.join(cfg.hosts) or '(none)'}")

    inventory = collect_inventory(cfg.hosts[args.host], cfg.ssh)
    validate_inventory(inventory)
    return inventory


def _host_report(args: argparse.Namespace, source: GitCatalogSource, snapshot: CatalogSnapshot) -> HostUpdateReport:
    # snapshot() already refreshed origin/main.  read_catalog() reads exactly the
    # same remote-tracking ref, so the comparison uses one coherent catalog.
    payload = source.read_catalog()
    inventory = _inventory(args)
    return build_host_update_report(args.host, inventory, snapshot, payload)


def show_once(args: argparse.Namespace) -> int:
    source = _source(args)
    try:
        snapshot = source.snapshot(fetch=not args.no_fetch)
        if args.host:
            render_host_update_table(_host_report(args, source, snapshot))
        else:
            render_update_table(snapshot)
            print("\nTip: add '--host <alias>' to compare these targets with an IBM server.")
    except (GitCatalogError, SSHScanError, OSError, RuntimeError, ValueError) as exc:
        print(f"github update table: ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


def watch(args: argparse.Namespace) -> int:
    """Poll GitHub and optionally rescan a host, redrawing only on changes."""
    source = _source(args)
    previous_key: str | None = None

    try:
        while True:
            try:
                snapshot = source.snapshot(fetch=True)
                if args.host:
                    report = _host_report(args, source, snapshot)
                    key = _report_key(report)
                    if key != previous_key or args.always:
                        render_host_update_table(report)
                        previous_key = key
                else:
                    key = _snapshot_key(snapshot)
                    if key != previous_key or args.always:
                        render_update_table(snapshot)
                        previous_key = key
            except (GitCatalogError, SSHScanError, OSError, RuntimeError, ValueError) as exc:
                print(f"github update table: ERROR: {exc}", file=sys.stderr)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


def _add_host_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--host",
        default=os.environ.get("PATCHWATCH_HOST"),
        help="configured IBM host alias; enables installed-vs-target comparison",
    )
    parser.add_argument(
        "--config",
        default=os.environ.get("PATCHWATCH_CONFIG", str(ROOT / "config.toml")),
        help="ibm-patchwatch TOML config used for the SSH inventory scan",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch the latest IBM maintenance catalog from the GitHub-backed "
            "CM_Discovery repository and render it with Rich."
        )
    )
    parser.add_argument("--repo-path", default=str(ROOT), help="local Git checkout")
    parser.add_argument("--remote", default="origin", help="Git remote name")
    parser.add_argument("--branch", default="main", help="GitHub branch to read")
    parser.add_argument(
        "--catalog-path",
        default="data/ibm/catalog.json",
        help="catalog path inside the Git repository",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    show = sub.add_parser("show", help="manual one-shot refresh and display")
    _add_host_options(show)
    show.add_argument(
        "--no-fetch",
        action="store_true",
        help="do not contact GitHub; use the existing origin/<branch> ref",
    )
    show.set_defaults(func=show_once)

    watcher = sub.add_parser("watch", help="periodically refresh while running")
    _add_host_options(watcher)
    watcher.add_argument(
        "--interval",
        type=int,
        default=900,
        help="poll/scan interval in seconds (default: 900)",
    )
    watcher.add_argument(
        "--always",
        action="store_true",
        help="render every interval even when neither catalog nor inventory changed",
    )
    watcher.set_defaults(func=watch)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "interval", 1) < 1:
        parser.error("--interval must be at least 1 second")
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
