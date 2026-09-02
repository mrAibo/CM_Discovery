from __future__ import annotations

import re
from typing import Any

from ..http import fetch_text
from .common import html_to_text, version_tuple

SOURCE_URL = "https://www.ibm.com/support/pages/ibm-sdk-java-technology-edition-refreshes"


def check(installed: dict[str, Any]) -> dict[str, Any]:
    text = html_to_text(fetch_text(SOURCE_URL))

    matches = re.findall(
        r"Service\s+Refresh\s+(\d+)\s+Fix\s+Pack\s+(\d+).*?\((8\.0\.\d+\.\d+)\)",
        text,
        re.I | re.S,
    )
    if not matches:
        # The page also exposes the canonical dotted version directly.
        dotted = re.findall(r"\b8\.0\.8\.\d+\b", text)
        if not dotted:
            raise ValueError("could not parse latest IBM Java 8 release")
        latest = max(set(dotted), key=version_tuple)
        sr = None
        fp = latest.split(".")[-1]
    else:
        sr_s, fp_s, latest = max(matches, key=lambda row: version_tuple(row[2]))
        sr, fp = int(sr_s), int(fp_s)

    current = str(installed.get("version") or "")
    status = "current" if version_tuple(current) >= version_tuple(latest) else "update_available"

    return {
        "product_id": "ibm_java",
        "status": status,
        "installed": {
            "version": installed.get("version"),
            "build_version": installed.get("build_version"),
            "im_internal_version": installed.get("im_internal_version"),
        },
        "available": {
            "version": latest,
            "service_refresh": sr,
            "fix_pack": fp,
        },
        "cumulative": True,
        "scope": "java8_refresh_stream",
        "source_url": SOURCE_URL,
    }
