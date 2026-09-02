#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from ibm_patchwatch.providers import (
    content_manager,
    content_navigator,
    daeja,
    db2,
    iccsap,
    java,
    websphere,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "ibm" / "catalog.json"


def _entry(result: dict, refreshed_at: str) -> dict:
    entry = {
        "available": result.get("available") or {},
        "cumulative": result.get("cumulative"),
        "scope": result.get("scope"),
        "source_url": result.get("source_url"),
        "ifx_audit": result.get("ifx_audit"),
        "notes": result.get("notes") or [],
        "refreshed_at": refreshed_at,
    }
    # Providers may expose an explicitly verified Fix Central/package URL.
    if result.get("download_url"):
        entry["download_url"] = result["download_url"]
    return entry


def _load_previous() -> dict:
    if not OUTPUT.exists():
        return {}
    try:
        value = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def main() -> None:
    attempted_at = datetime.now(timezone.utc).isoformat()
    previous = _load_previous()
    previous_products = previous.get("products") if isinstance(previous.get("products"), dict) else {}
    previous_generated_at = previous.get("generated_at")

    probes: dict[str, Callable[[], dict]] = {
        "content_manager": lambda: content_manager.check({"version": "0"}),
        "content_navigator": lambda: content_navigator.check({
            "version": "3.1.0",
            "build_level": "icn310.000.000",
        }),
        "daeja_viewone_virtual": lambda: daeja.check({
            "version": "5.0.15",
            "interim_fix": 0,
        }),
        "db2": lambda: db2.check({
            "version": "11.5.9.0",
            "fix_pack": "0",
            "special_build": "catalog_probe",
            "code_release": "SQL11059",
        }),
        "ibm_java": lambda: java.check({"version": "0"}),
        "iccsap": lambda: iccsap.check({
            "version": "4.0.0.4",
            "installed_fixes": [],
        }),
        "websphere": lambda: websphere.check({"version": "0"}),
    }

    products: dict[str, dict] = {}
    refresh_errors: dict[str, str] = {}
    missing_after_failure: list[str] = []

    for product_id, probe in probes.items():
        try:
            products[product_id] = _entry(probe(), attempted_at)
            print(f"[ok] {product_id}")
        except Exception as exc:  # Provider/network failures must be isolated.
            message = f"{type(exc).__name__}: {exc}"
            refresh_errors[product_id] = message
            old = previous_products.get(product_id) if isinstance(previous_products, dict) else None
            if isinstance(old, dict):
                preserved = dict(old)
                preserved.setdefault("refreshed_at", previous_generated_at)
                preserved["refresh_error"] = {
                    "at": attempted_at,
                    "message": message,
                }
                products[product_id] = preserved
                print(f"::warning title=IBM catalog refresh::{product_id}: {message}; previous entry preserved")
            else:
                missing_after_failure.append(product_id)
                print(f"::error title=IBM catalog refresh::{product_id}: {message}; no previous entry exists")

    payload = {
        "schema_version": 2,
        "generated_at": attempted_at,
        "generator": "scripts/update_ibm_catalog.py",
        "refresh_status": "partial" if refresh_errors else "ok",
        "refresh_errors": refresh_errors,
        "products": products,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"updated {OUTPUT} ({payload['refresh_status']})")

    # A transient provider failure is acceptable only if a previous value was
    # preserved.  Never publish a catalog that silently loses a product.
    if missing_after_failure:
        raise SystemExit(
            "catalog refresh incomplete; no previous data for: " + ", ".join(missing_after_failure)
        )


if __name__ == "__main__":
    main()
