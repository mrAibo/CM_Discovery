from __future__ import annotations

import re
from typing import Any

from ..http import fetch_text
from .common import html_to_text, version_tuple

SOURCE_URL = "https://www.ibm.com/support/pages/fix-list-ibm-websphere-application-server-traditional-v9-0"


def check(installed: dict[str, Any]) -> dict[str, Any]:
    text = html_to_text(fetch_text(SOURCE_URL))
    versions = sorted(
        set(re.findall(r"Fix\s+Pack\s+(9\.0\.5\.\d+)", text, re.I)),
        key=version_tuple,
    )
    if not versions:
        raise ValueError("could not parse latest WebSphere 9.0.5 fix pack")

    latest = versions[-1]
    current = str(installed.get("version") or "")
    status = "current" if version_tuple(current) >= version_tuple(latest) else "update_available"

    return {
        "product_id": "websphere",
        "status": status,
        "installed": {
            "version": installed.get("version"),
            "build_version": installed.get("build_version"),
            "im_internal_version": installed.get("im_internal_version"),
            "installed_fixes": installed.get("installed_fixes", []),
        },
        "available": {"version": latest},
        "cumulative": True,
        "scope": "fix_pack_only",
        "source_url": SOURCE_URL,
        "ifx_audit": "pending",
        "notes": [
            "WebSphere traditional fix packs are cumulative.",
            "CURRENT here means current fix-pack level only; interim fixes are audited separately.",
        ],
    }
