from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .providers.common import version_tuple

DEFAULT_CATALOG = Path(__file__).resolve().parents[2] / "data" / "ibm" / "catalog.json"
MAX_CATALOG_AGE_HOURS = 72.0


def load_catalog(path: Path = DEFAULT_CATALOG) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("products"), dict):
        raise ValueError(f"invalid IBM catalog: {path}")
    return data


def age_hours(timestamp: str | None) -> float | None:
    """Return age of an ISO-8601 timestamp in hours."""
    if not timestamp:
        return None
    try:
        stamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds() / 3600.0)
    except ValueError:
        return None


def entry_timestamp(entry: dict[str, Any], catalog: dict[str, Any]) -> str | None:
    value = entry.get("refreshed_at") or catalog.get("generated_at")
    return str(value) if value else None


def _icn_ifix(build_level: object) -> int | None:
    match = re.search(r"icn310\.(\d{3})\.", str(build_level or ""), re.I)
    return int(match.group(1)) if match else None


def _latest_iccsap_jre_fix_date(installed: dict[str, Any]) -> str | None:
    dates: list[str] = []
    for item in installed.get("installed_fixes") or []:
        match = re.search(r"JRE_fix_(\d{8})", str(item), re.I)
        if match:
            dates.append(match.group(1))
    return max(dates) if dates else None


def compare_installed(product_id: str, installed: dict[str, Any], available: dict[str, Any]) -> str:
    """Compare one installed product with one normalized catalog entry.

    Returns one of ``current``, ``update_available`` or ``review_required``.
    The comparison is intentionally conservative for maintenance streams where
    a simple semantic version comparison would be unsafe.
    """
    current_version = str(installed.get("version") or "")

    if product_id in {"websphere", "ibm_java", "content_manager"}:
        latest = str(available.get("version") or "")
        if not latest:
            raise ValueError(f"catalog has no available version for {product_id}")
        return "current" if version_tuple(current_version) >= version_tuple(latest) else "update_available"

    if product_id == "db2":
        installed_special = str(installed.get("special_build") or "")
        latest_special = str(available.get("special_build") or "")
        if not latest_special:
            raise ValueError("catalog has no Db2 special build")
        return "current" if installed_special == latest_special else "update_available"

    if product_id == "content_navigator":
        installed_ifix = _icn_ifix(installed.get("build_level"))
        latest_ifix = available.get("interim_fix")
        if installed_ifix is None or latest_ifix is None:
            return "review_required"
        return "current" if installed_ifix >= int(latest_ifix) else "update_available"

    if product_id == "daeja_viewone_virtual":
        try:
            installed_ifix = int(installed.get("interim_fix"))
            latest_ifix = int(available.get("interim_fix"))
        except (TypeError, ValueError):
            return "review_required"
        return "current" if installed_ifix >= latest_ifix else "update_available"

    if product_id == "iccsap":
        installed_date = _latest_iccsap_jre_fix_date(installed)
        target_date = str(available.get("jre_fix_date") or "")
        if not installed_date or not target_date:
            return "review_required"
        return "current" if installed_date >= target_date else "update_available"

    raise KeyError(f"catalog comparison not implemented for {product_id}")


def fallback_result(
    product_id: str,
    installed: dict[str, Any],
    live_error: Exception,
    *,
    path: Path = DEFAULT_CATALOG,
) -> dict[str, Any]:
    catalog = load_catalog(path)
    entry = (catalog.get("products") or {}).get(product_id)
    if not isinstance(entry, dict):
        raise KeyError(f"product {product_id!r} missing from IBM catalog")

    available = entry.get("available") or {}
    status = compare_installed(product_id, installed, available)

    refreshed_at = entry_timestamp(entry, catalog)
    age = age_hours(refreshed_at)
    stale = age is None or age > MAX_CATALOG_AGE_HOURS

    return {
        "product_id": product_id,
        "status": "error" if stale else status,
        "installed": dict(installed),
        "available": available,
        "cumulative": entry.get("cumulative"),
        "scope": entry.get("scope"),
        "source_url": entry.get("source_url"),
        "ifx_audit": entry.get("ifx_audit"),
        "notes": list(entry.get("notes") or []),
        "source_mode": "catalog",
        "catalog_generated_at": refreshed_at,
        "catalog_age_hours": age,
        "catalog_stale": stale,
        "catalog_refresh_error": entry.get("refresh_error"),
        "live_error": f"{type(live_error).__name__}: {live_error}",
        **({"error": f"IBM catalog entry is stale ({age!r} hours)"} if stale else {}),
    }
