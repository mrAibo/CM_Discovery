from __future__ import annotations

from typing import Any


PATCH_TARGET_IDS = {
    "content_manager",
    "content_navigator",
    "daeja_viewone_virtual",
    "db2",
    "ibm_java",
    "iccsap",
    "websphere",
}


def validate_inventory(inventory: dict[str, Any]) -> None:
    if "schema_version" not in inventory:
        raise ValueError("inventory has no schema_version")
    if not isinstance(inventory.get("host"), dict):
        raise ValueError("inventory has no host object")
    if not isinstance(inventory.get("products"), list):
        raise ValueError("inventory has no products list")


def patch_targets(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in inventory.get("products", [])
        if isinstance(item, dict) and item.get("id") in PATCH_TARGET_IDS
    ]


def product_version(item: dict[str, Any]) -> str:
    """Return a human maintenance fingerprint, not merely the base version."""
    version = str(item.get("version", "?"))

    if item.get("id") == "db2":
        parts = [version]
        if item.get("fix_pack") is not None:
            parts.append(f"FP{item['fix_pack']}")
        if item.get("special_build"):
            parts.append(str(item["special_build"]))
        if item.get("build_token"):
            parts.append(str(item["build_token"]))
        return " ".join(parts)

    if item.get("interim_fix") is not None:
        version += f" iFix {item['interim_fix']}"

    fixes = item.get("installed_fixes")
    if isinstance(fixes, list) and fixes:
        version += f" +{len(fixes)} installed fixes"

    return version
