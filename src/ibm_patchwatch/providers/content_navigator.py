from __future__ import annotations

import re
from typing import Any

from ..http import HTTPError, fetch_text
from .common import html_to_text

README_URL = "https://www.ibm.com/support/pages/ibm-content-navigator-version-310-interim-fix-{}-readme"
BASELINE_IFIX = 12  # last readme known to exist; the n+1 probe starts after it
MAX_PROBE = 20  # safety cap for the n+1 probe


def _readme(number: int) -> tuple[str, str] | None:
    """Return (ifix, build) only if the page really is the readme for this number.

    IBM answers unknown readme URLs with HTTP 200 and a search page, so the
    title, "Update name" and build number must all match the requested number.
    """
    try:
        text = html_to_text(fetch_text(README_URL.format(number)))
    except HTTPError:
        return None
    ifix = re.search(r"Update name:\s*Interim Fix\s+(\d+)", text, re.I)
    build = re.search(r"Build number:\s*(icn310\.(\d+)\.\d+)", text, re.I)
    if not ifix or not build or int(ifix.group(1)) != number or int(build.group(2)) != number:
        return None
    return ifix.group(1), build.group(1)


def _ifix_from_build(value: object) -> int | None:
    match = re.search(r"icn310\.(\d{3})\.", str(value or ""), re.I)
    return int(match.group(1)) if match else None


def check(installed: dict[str, Any]) -> dict[str, Any]:
    found = _readme(BASELINE_IFIX)
    if not found:
        raise ValueError("could not parse IBM Content Navigator 3.1 interim-fix readme")
    latest_ifix, latest_build = BASELINE_IFIX, found[1]
    for number in range(BASELINE_IFIX + 1, BASELINE_IFIX + 1 + MAX_PROBE):
        found = _readme(number)
        if not found:
            break
        latest_ifix, latest_build = number, found[1]
    source_url = README_URL.format(latest_ifix)
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
        "target_mode": "pinned",
        "scope": "3.1.0_interim_fix_stream",
        "source_url": source_url,
        "download_url": 'https://www.ibm.com/support/fixcentral/swg/selectFixes?parent=Enterprise%20Content%20Management&product=ibm/Other+software/Content+Navigator&release=3.1.0&platform=Linux&function=all',
        "notes": [
            "The target is restricted to the installed 3.1.0 maintenance stream; no 3.2 major upgrade is inferred.",
            "Supersedence/cumulative semantics remain conservative until explicitly proven from IBM metadata.",
        ],
    }
