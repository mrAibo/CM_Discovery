from __future__ import annotations

import re
from typing import Any

from ..http import fetch_text
from .common import html_to_text

SOURCE_URL = "https://www.ibm.com/support/pages/node/7087189"


def check(installed: dict[str, Any]) -> dict[str, Any]:
    text = html_to_text(fetch_text(SOURCE_URL))

    # IBM marks the newest entry explicitly as the most recent Db2 Update.
    match = re.search(
        r"Db2\s+Update\s+(\d+)\*?.{0,400}?most\s+recent\s+Db2\s+Update.{0,500}?"
        r"Linux\s+x86\s+PTF:\s*([^\s]+)",
        text,
        re.I | re.S,
    )
    if not match:
        # Fallback: the IBM page is ordered newest first. Do not compare update
        # numbers numerically; IBM explicitly warns that they are not a
        # chronological sequence.
        match = re.search(
            r"Db2\s+Update\s+(\d+)\*?.{0,800}?Linux\s+x86\s+PTF:\s*([^\s]+)",
            text,
            re.I | re.S,
        )
    if not match:
        raise ValueError("could not parse latest Db2 11.5.9 published update")

    update_number = match.group(1)
    ptf = match.group(2).strip()
    installed_special = str(installed.get("special_build") or "")
    expected_special = f"special_{update_number}"

    if installed_special == expected_special:
        status = "current"
    else:
        status = "update_available"

    return {
        "product_id": "db2",
        "status": status,
        "installed": {
            "version": installed.get("version"),
            "fix_pack": installed.get("fix_pack"),
            "special_build": installed.get("special_build"),
            "code_release": installed.get("code_release"),
        },
        "available": {
            "version": "11.5.9.0",
            "update_number": update_number,
            "special_build": expected_special,
            "ptf": ptf,
        },
        "cumulative": True,
        "scope": "published_cumulative_updates",
        "source_url": SOURCE_URL,
        "notes": [
            "IBM states that Db2 11.5.9 published updates are cumulative.",
            "Update numbers are not treated as chronological version numbers; IBM page order/most-recent marker is authoritative.",
        ],
    }
