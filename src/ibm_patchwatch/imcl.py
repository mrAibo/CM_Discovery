from __future__ import annotations

import re
from typing import Any


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


def normalize_installation_manager(inventory: dict[str, Any]) -> None:
    im = inventory.get("installation_manager")
    if not isinstance(im, dict):
        return
    raw = im.get("packages_raw")
    if isinstance(raw, list) and not isinstance(im.get("packages"), list):
        im["packages"] = parse_packages([str(line) for line in raw])
