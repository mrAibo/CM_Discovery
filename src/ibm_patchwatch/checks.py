from __future__ import annotations

from typing import Any, Callable

from .catalog import fallback_result
from .providers import db2, java, websphere

Checker = Callable[[dict[str, Any]], dict[str, Any]]

CHECKERS: dict[str, Checker] = {
    "db2": db2.check,
    "ibm_java": java.check,
    "websphere": websphere.check,
}

PENDING_PRODUCT_IDS = {
    "content_manager",
    "content_navigator",
    "daeja_viewone_virtual",
    "iccsap",
}


def run_checks(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    products = {
        item.get("id"): item
        for item in inventory.get("products", [])
        if isinstance(item, dict) and item.get("id")
    }

    for product_id in ("content_manager", "content_navigator", "daeja_viewone_virtual", "db2", "ibm_java", "iccsap", "websphere"):
        installed = products.get(product_id)
        if not installed:
            continue
        checker = CHECKERS.get(product_id)
        if checker is None:
            results.append({
                "product_id": product_id,
                "status": "not_checked",
                "installed": {"version": installed.get("version")},
                "reason": "online provider not implemented yet",
            })
            continue
        try:
            result = checker(installed)
            result.setdefault("source_mode", "live")
            results.append(result)
        except Exception as exc:
            try:
                results.append(fallback_result(product_id, installed, exc))
            except Exception as fallback_exc:
                results.append({
                    "product_id": product_id,
                    "status": "error",
                    "installed": {"version": installed.get("version")},
                    "error": (
                        f"live check failed: {type(exc).__name__}: {exc}; "
                        f"catalog fallback failed: {type(fallback_exc).__name__}: {fallback_exc}"
                    ),
                })
    return results
