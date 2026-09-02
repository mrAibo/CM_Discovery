#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from ibm_patchwatch.github_catalog import CatalogSnapshot, GitCatalogError, GitCatalogSource
from ibm_patchwatch.rich_updates import render_update_table


ROOT = Path(__file__).resolve().parents[1]


def _source(args: argparse.Namespace) -> GitCatalogSource:
    return GitCatalogSource(
        Path(args.repo_path),
        remote=args.remote,
        branch=args.branch,
        catalog_path=args.catalog_path,
    )


def _snapshot_key(snapshot: CatalogSnapshot) -> str:
    """Stable change detector for watch mode."""
    data = {
        "revision": snapshot.revision,
        "generated_at": snapshot.generated_at,
        "rows": [row.__dict__ for row in snapshot.rows],
    }
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def show_once(args: argparse.Namespace) -> int:
    source = _source(args)
    try:
        snapshot = source.snapshot(fetch=not args.no_fetch)
        render_update_table(snapshot)
    except (GitCatalogError, RuntimeError) as exc:
        print(f"github update table: ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


def watch(args: argparse.Namespace) -> int:
    """Poll GitHub periodically and redraw only when the catalog changes.

    This is useful for an interactive terminal.  For unattended operation,
    prefer the systemd timer shipped in systemd/.
    """
    source = _source(args)
    previous_key: str | None = None

    try:
        while True:
            try:
                snapshot = source.snapshot(fetch=True)
                key = _snapshot_key(snapshot)
                if key != previous_key or args.always:
                    render_update_table(snapshot)
                    previous_key = key
            except (GitCatalogError, RuntimeError) as exc:
                print(f"github update table: ERROR: {exc}", file=sys.stderr)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch the latest IBM update catalog from the GitHub-backed "
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
    show.add_argument(
        "--no-fetch",
        action="store_true",
        help="do not contact GitHub; use the existing origin/<branch> ref",
    )
    show.set_defaults(func=show_once)

    watcher = sub.add_parser("watch", help="periodically refresh while running")
    watcher.add_argument(
        "--interval",
        type=int,
        default=900,
        help="poll interval in seconds (default: 900)",
    )
    watcher.add_argument(
        "--always",
        action="store_true",
        help="render every interval even when the catalog did not change",
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
