from __future__ import annotations

import json
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


def _age_hours(generated_at: str | None) -> float | None:
    if not generated_at:
        return None
    try:
        stamp = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds() / 3600.0)
    except ValueError:
        return None


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
    current_version = str(installed.get("version") or "")

    if product_id in {"websphere", "ibm_java"}:
        latest = str(available.get("version") or "")
        if not latest:
            raise ValueError(f"catalog has no available version for {product_id}")
        status = "current" if version_tuple(current_version) >= version_tuple(latest) else "update_available"
    elif product_id == "db2":
        installed_special = str(installed.get("special_build") or "")
        latest_special = str(available.get("special_build") or "")
        if not latest_special:
            raise ValueError("catalog has no Db2 special build")
        status = "current" if installed_special == latest_special else "update_available"
    else:
        raise KeyError(f"catalog comparison not implemented for {product_id}")

    generated_at = catalog.get("generated_at")
    age = _age_hours(str(generated_at) if generated_at else None)
    stale = age is None or age > MAX_CATALOG_AGE_HOURS

    return {
        "product_id": product_id,
        "status": status,
        "installed": dict(installed),
        "available": available,
        "cumulative": entry.get("cumulative"),
        "scope": entry.get("scope"),
        "source_url": entry.get("source_url"),
        "ifx_audit": entry.get("ifx_audit"),
        "notes": list(entry.get("notes") or []),
        "source_mode": "catalog",
        "catalog_generated_at": generated_at,
        "catalog_age_hours": age,
        "catalog_stale": stale,
        "live_error": f"{type(live_error).__name__}: {live_error}",
    }
