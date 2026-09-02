from __future__ import annotations

import re
from typing import Any

from ..http import fetch_text
from .common import html_to_text

SOURCE_URL = "https://www.ibm.com/support/pages/ibm-content-navigator-version-310-interim-fix-12-readme"


def _ifix_from_build(value: object) -> int | None:
    match = re.search(r"icn310\.(\d{3})\.", str(value or ""), re.I)
    return int(match.group(1)) if match else None


def check(installed: dict[str, Any]) -> dict[str, Any]:
    text = html_to_text(fetch_text(SOURCE_URL))
    ifix_match = re.search(r"Update name:\s*Interim Fix\s+(\d+)", text, re.I)
    build_match = re.search(r"Build number:\s*(icn310\.\d+\.\d+)", text, re.I)
    if not ifix_match or not build_match:
        raise ValueError("could not parse IBM Content Navigator 3.1 interim-fix readme")

    latest_ifix = int(ifix_match.group(1))
    latest_build = build_match.group(1)
    installed_ifix = _ifix_from_build(installed.get("build_level"))
    if installed_ifix is None:
        status = "review_required"
    else:
        status = "current" if installed_ifix >= latest_ifix else "update_available"

    return {
        "product_id": "content_navigator",
        "status": status,
        "installed": {
            "version": installed.get("version"),
            "build_level": installed.get("build_level"),
            "build_number": installed.get("build_number"),
            "interim_fix": installed_ifix,
        },
        "available": {
            "version": "3.1.0",
            "interim_fix": latest_ifix,
            "build_level": latest_build,
        },
        "cumulative": None,
        "scope": "3.1.0_interim_fix_stream",
        "source_url": SOURCE_URL,
        "notes": [
            "The target is restricted to the installed 3.1.0 maintenance stream; no 3.2 major upgrade is inferred.",
            "Supersedence/cumulative semantics remain conservative until explicitly proven from IBM metadata.",
        ],
    }
