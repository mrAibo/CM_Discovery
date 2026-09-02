from __future__ import annotations

import re
from typing import Any

from ..http import fetch_text
from .common import html_to_text

SOURCE_URL = "https://delivery04.dhe.ibm.com/sar/CMA/OSA/0dx21/0/5.0.15_DAEJA_VIEWONE_IFIX006_Readme.htm"


def check(installed: dict[str, Any]) -> dict[str, Any]:
    text = html_to_text(fetch_text(SOURCE_URL))
    match = re.search(r"Update name:\s*iFix\s+(\d+)", text, re.I)
    if not match:
        match = re.search(r"5\.0\.15\s+iFix\s+(\d+)", text, re.I)
    if not match:
        raise ValueError("could not parse Daeja ViewONE 5.0.15 iFix readme")

    latest_ifix = int(match.group(1))
    try:
        installed_ifix = int(installed.get("interim_fix"))
    except (TypeError, ValueError):
        installed_ifix = None

    if installed_ifix is None:
        status = "review_required"
    else:
        status = "current" if installed_ifix >= latest_ifix else "update_available"

    return {
        "product_id": "daeja_viewone_virtual",
        "status": status,
        "installed": {
            "version": installed.get("version"),
            "interim_fix": installed_ifix,
            "build": installed.get("build"),
        },
        "available": {
            "version": "5.0.15",
            "interim_fix": latest_ifix,
        },
        "cumulative": True,
        "scope": "5.0.15_ifix_stream",
        "source_url": SOURCE_URL,
        "notes": [
            "The iFix 6 readme explicitly carries forward fixes/features from previous 5.0.15 iFixes.",
            "IBM Daeja 26.0.0 is a newer release, but Patchwatch does not infer a major-version upgrade from a maintenance check.",
        ],
    }
