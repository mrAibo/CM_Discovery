from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from ..http import HTTPError, fetch_text
from .common import html_to_text, version_tuple
from .fix_references import references

BULLETIN_URL = (
    "https://www.ibm.com/support/pages/security-bulletin-multiple-vulnerabilities-"
    "may-affect-ibm%C2%AE-sdk-java%E2%84%A2-technology-edition-ibm-content-collector-"
    "sap-applications-{}"
)
FIRST_BULLETIN = 16
MAX_PROBES = 8  # shortcut: bounded probe, raise if IBM ever publishes more than 8 in a row


def _latest_bulletin() -> tuple[str, str]:
    """Return (url, text) of the highest-numbered bulletin that exists.

    IBM publishes each JRE remediation as a new numbered bulletin, so a pinned
    URL silently goes stale. A missing number ends the probe (IBM answers 404).
    """
    found = None
    for number in range(FIRST_BULLETIN, FIRST_BULLETIN + MAX_PROBES):
        url = BULLETIN_URL.format(number)
        try:
            found = (url, html_to_text(fetch_text(url)))
        except HTTPError:
            if found is None:
                raise
            break
    return found


def _latest_installed_jre_fix(installed: dict[str, Any]) -> str | None:
    dates: list[str] = []
    for item in installed.get("installed_fixes") or []:
        match = re.search(r"JRE_fix_(\d{8})", str(item), re.I)
        if match:
            dates.append(match.group(1))
    return max(dates) if dates else None


def check(installed: dict[str, Any]) -> dict[str, Any]:
    source_url, text = _latest_bulletin()
    target_match = re.search(
        r"4\.0\.0\.4-ICCSAP-Base-JRE-(8\.0\.\d+\.\d+)", text, re.I
    )
    date_match = re.search(r"(\d{1,2}\s+[A-Za-z]{3}\s+\d{4}):\s+Initial Publication", text)
    if not target_match:
        raise ValueError("could not parse ICCSAP Java remediation level")

    target_jre = target_match.group(1)
    bulletin_fix_date = datetime.strptime(date_match.group(1), "%d %b %Y").strftime("%Y%m%d") if date_match else None
    installed_fix_date = _latest_installed_jre_fix(installed)

    measured_jre = str(installed.get("jre_version") or "")
    # A bulletin publication date does not measure the installed Java version.
    status = "update_available" if re.fullmatch(r"8\.0\.\d+\.\d+", measured_jre) and version_tuple(measured_jre) < version_tuple(target_jre) else "review_required"

    return {
        "product_id": "iccsap",
        "status": status,
        "installed": {
            "version": installed.get("version"),
            "build": installed.get("build"),
            "installed_fixes": installed.get("installed_fixes", []),
            "latest_jre_fix_date": installed_fix_date,
        },
        "available": {
            "version": "4.0.0.4",
            "jre_version": target_jre,
            "jre_fix_date": bulletin_fix_date,
            "fix_name": f"4.0.0.4-ICCSAP-Base-JRE-{target_jre}",
        },
        **references("iccsap"),
        "cumulative": None,
        "target_mode": "pinned",
        "scope": "4.0.0.4_base_jre_and_binary_ifixes",
        "source_url": source_url,
        "notes": [
            "This check targets the currently published ICCSAP embedded-JRE security remediation, not every ICCSAP component fix.",
            "JRE dates do not establish installed version. Binary interim fixes must be checked independently; no cumulative replacement is assumed.",
        ],
    }
