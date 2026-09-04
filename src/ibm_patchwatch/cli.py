from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .config import AppConfig, load_config
from .inventory import validate_inventory
from .ssh import SSHScanError, collect_inventory


def _config(path: str) -> AppConfig:
    try:
        return load_config(path)
    except Exception as exc:
        raise SystemExit(f"config error: {exc}") from exc


def cmd_serve(args: argparse.Namespace) -> int:
    from .web import serve

    cfg = _config(args.config)
    if args.host not in cfg.hosts:
        print(f"unknown host: {args.host}", file=sys.stderr)
        return 2
    try:
        inventory = collect_inventory(cfg.hosts[args.host], cfg.ssh)
        validate_inventory(inventory)
    except (SSHScanError, ValueError) as exc:
        print(f"{args.host}: ERROR: {exc}", file=sys.stderr)
        return 1

    user = os.environ.get("IBM_CHECK_USER", "admin")
    password = os.environ.get("IBM_CHECK_PASSWORD", "admin")
    if (user, password) == ("admin", "admin"):
        print("WARNING: using default LAN-only credentials admin/admin", file=sys.stderr)
    serve(inventory, args.bind, args.port, user, password)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ibm-patchwatch")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--config", default="config.toml", help="path to TOML config")
    sub = parser.add_subparsers(dest="command", required=True)

    web = sub.add_parser("serve", help="fresh remote scan plus temporary authenticated LAN UI")
    web.add_argument("host", help="configured SSH alias")
    web.add_argument("--bind", default="127.0.0.1", help="LAN address to listen on")
    web.add_argument("--port", type=int, default=8765)
    web.set_defaults(func=cmd_serve)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    raise SystemExit(args.func(args))
