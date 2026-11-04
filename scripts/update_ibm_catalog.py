#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from ibm_patchwatch.providers.common import version_tuple

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
    for key in ("target_mode", "interim_fixes", "fix_pack_cumulative", "fix_pack_url", "availability_evidence", "index_source_url"):
        if key in result:
            entry[key] = result[key]
    return entry


def _load_previous() -> dict:
    if not OUTPUT.exists():
        return {}
    try:
        value = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


MAX_UNCHANGED_AGE = timedelta(hours=40)  # below the page's 72 h freshness limit even if one daily run is skipped


def _content(catalog: dict) -> dict:
    """Catalog without refresh timestamps, to tell real changes from reruns."""
    value = json.loads(json.dumps(catalog))
    for key in ("generated_at",):
        value.pop(key, None)
    for entry in (value.get("products") or {}).values():
        if isinstance(entry, dict):
            entry.pop("refreshed_at", None)
            if isinstance(entry.get("refresh_error"), dict):
                entry["refresh_error"].pop("at", None)
    return value


def _unchanged_and_fresh(previous: dict, payload: dict, now: datetime) -> bool:
    try:
        age = now - datetime.fromisoformat(previous["generated_at"])
    except (KeyError, TypeError, ValueError):
        return False
    return _content(previous) == _content(payload) and age < MAX_UNCHANGED_AGE


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
            candidate = _entry(probe(), attempted_at)
            old = previous_products.get(product_id, {})
            # Never replace a confirmed CM/WAS fix pack with a lagging source.
            if product_id in ("content_manager", "websphere") and version_tuple(candidate["available"].get("version", "")) < version_tuple(old.get("available", {}).get("version", "")):
                raise ValueError(f"{product_id} source regressed below the previously confirmed fix pack")
            products[product_id] = candidate
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

    # Only timestamps would change: keep the committed file (fewer daily commits).
    if _unchanged_and_fresh(previous, payload, datetime.fromisoformat(attempted_at)):
        print("catalog content unchanged; keeping the committed file")
        return

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
