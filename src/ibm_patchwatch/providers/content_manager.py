from __future__ import annotations

import re
from typing import Any

from ..http import fetch_text
from .common import html_to_text, version_tuple

SOURCE_URL = (
    "https://www.ibm.com/docs/en/content-manager/8.7.0?topic=fp-"
    "content-manager-version-87-fix-pack-5-readme"
)


def check(installed: dict[str, Any]) -> dict[str, Any]:
    text = html_to_text(fetch_text(SOURCE_URL))
    # Historical fix lists and navigation are not release metadata.
    levels = {int(value) for value in re.findall(r"Update name:\s*Fix Pack\s+(\d+)", text, re.I)}
    if levels != {5} or not re.search(r"Content Manager Version\s+8\.7\s+Fix Pack\s+5\s+Readme", text, re.I):
        raise ValueError("expected unambiguous FP5 update metadata in IBM CM readme")
    fp = levels.pop()
    latest = f"8.7.00.{fp * 100:03d}"
    current = str(installed.get("version") or "")
    status = "current" if version_tuple(current) >= version_tuple(latest) else "update_available"

    return {
        "product_id": "content_manager",
        "status": status,
        "installed": {
            "version": installed.get("version"),
            "fix_level": installed.get("fix_level"),
            "build": installed.get("build"),
        },
        "available": {"version": latest, "fix_pack": fp},
        "cumulative": True,
        "scope": "8.7_fix_pack_level",
        "source_url": SOURCE_URL,
        "ifx_audit": "pending",
        "notes": [
            "Fix-pack comparison only; interim/security fixes are audited separately.",
            "Known FP5 baseline; this release-specific readme does not discover future fix packs.",
        ],
    }
