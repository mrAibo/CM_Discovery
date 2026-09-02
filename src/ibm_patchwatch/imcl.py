from __future__ import annotations

import re
from typing import Any


PACKAGE_TO_PRODUCT = {
    "com.ibm.websphere.BASE.v90": "websphere",
    "com.ibm.java.jdk.v8": "ibm_java",
    "com.ibm.im.iccsap.offering": "iccsap",
}


def parse_packages(lines: list[str]) -> list[dict[str, Any]]:
    """Parse English or German `imcl listInstalledPackages -verbose` output."""
    package_headers = {"[package]", "[paket]"}
    group_headers = {"[package group]", "[paketgruppe]"}
    install_labels = {"installation directory", "installationsverzeichnis"}
    rollback_headers = {"rollback versions:", "rollbackversionen:"}
    feature_headers = {"features:", "komponenten:"}

    packages: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    group_dir: str | None = None
    section: str | None = None

    for raw in lines:
        line = raw.strip()
        low = line.lower()
        if low in group_headers:
            if current:
                packages.append(current)
                current = None
            group_dir = None
            section = "group"
            continue
        if low in package_headers:
            if current:
                packages.append(current)
            current = {"fixes": [], "rollback_versions": []}
            if group_dir:
                current["installation_directory"] = group_dir
            section = "package"
            continue
        if low == "fixes:":
            section = "fixes"
            continue
        if low in rollback_headers:
            section = "rollback"
            continue
        if low in feature_headers:
            section = "features"
            continue

        if ":" in line:
            key, value = line.split(":", 1)
            key, value = key.strip().lower(), value.strip()
            if section == "group" and key in install_labels:
                group_dir = value
            elif current is not None and key == "name":
                current["name"] = value
                match = re.search(r"\(([^()]+)\)\s*$", value)
                if match:
                    current["package_id"] = match.group(1)
            elif current is not None and key == "version":
                match = re.match(r"([^\s]+)(?:\s+\(([^)]+)\))?", value)
                if match:
                    current["version"] = match.group(1)
                    if match.group(2):
                        current["internal_version"] = match.group(2)
            elif current is not None and key == "repository":
                current["repository"] = value
            continue

        if current is not None and low not in {"none", "keine"}:
            if section == "fixes":
                current["fixes"].append(line)
            elif section == "rollback":
                current["rollback_versions"].append(line)

    if current:
        packages.append(current)
    return packages


def enrich_products(inventory: dict[str, Any], packages: list[dict[str, Any]]) -> None:
    products = inventory.get("products")
    if not isinstance(products, list):
        return

    by_id = {
        item.get("id"): item
        for item in products
        if isinstance(item, dict) and item.get("id")
    }

    for package in packages:
        package_id = package.get("package_id")
        product_id = PACKAGE_TO_PRODUCT.get(str(package_id))
        product = by_id.get(product_id)
        if not isinstance(product, dict):
            continue

        product["im_package_id"] = package_id
        if package.get("internal_version"):
            product["im_internal_version"] = package["internal_version"]
        if package.get("repository"):
            product["im_repository"] = package["repository"]
        if package.get("installation_directory"):
            product["installation_directory"] = package["installation_directory"]

        fixes = package.get("fixes")
        if isinstance(fixes, list):
            product["installed_fixes"] = list(fixes)

        rollback = package.get("rollback_versions")
        if isinstance(rollback, list):
            product["rollback_versions"] = list(rollback)

        if package.get("version"):
            product["im_version"] = package["version"]
            product["im_version_matches"] = str(package["version"]) == str(product.get("version"))


def normalize_installation_manager(inventory: dict[str, Any]) -> None:
    im = inventory.get("installation_manager")
    if not isinstance(im, dict):
        return
    raw = im.get("packages_raw")
    if isinstance(raw, list) and not isinstance(im.get("packages"), list):
        im["packages"] = parse_packages([str(line) for line in raw])
    packages = im.get("packages")
    if isinstance(packages, list):
        enrich_products(inventory, packages)
