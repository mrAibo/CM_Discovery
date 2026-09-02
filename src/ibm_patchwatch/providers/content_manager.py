from __future__ import annotations

import re
from typing import Any

from ..http import fetch_text
from .common import html_to_text, version_tuple

SOURCE_URL = (
    "https://www.ibm.com/docs/en/content-manager/8.7.0?topic=fp-"
    "content-manager-version-87-fix-pack-4-readme"
)


def check(installed: dict[str, Any]) -> dict[str, Any]:
    text = html_to_text(fetch_text(SOURCE_URL))
    match = re.search(r"Update name:\s*Fix Pack\s+(\d+)", text, re.I)
    if not match:
        match = re.search(r"Version\s+8\.7\s+Fix Pack\s+(\d+)", text, re.I)
    if not match:
        raise ValueError("could not parse IBM Content Manager 8.7 fix-pack readme")

    fp = int(match.group(1))
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
            "The IBM Fix Pack 4 readme includes the cumulative fix list through Fix Pack 4.",
        ],
    }
