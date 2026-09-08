from __future__ import annotations

import re
from typing import Any
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from ..http import fetch_text
from .common import version_tuple
from .fix_references import references

SOURCE_URL = "https://www.ibm.com/support/pages/fix-list-ibm-websphere-application-server-traditional-v9-0"


class _DownloadLinks(HTMLParser):
    """Only release download links, not dates, headings or APAR target mentions."""
    def __init__(self):
        super().__init__()
        self.href = None
        self.label = []
        self.releases = {}

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.href = dict(attrs).get('href')
            self.label = []

    def handle_data(self, data):
        if self.href is not None:
            self.label.append(data)

    def handle_endtag(self, tag):
        if tag != 'a' or self.href is None:
            return
        match = re.fullmatch(r'Download\s+Fix\s+Pack\s+(9\.0\.5\.\d+)', ' '.join(self.label).strip(), re.I)
        if not match:
            self.href = None
            return
        url = urljoin(SOURCE_URL, self.href)
        parsed = urlsplit(url)
        if match and parsed.scheme == 'https' and parsed.hostname == 'www.ibm.com' and not parsed.username and not parsed.password and parsed.port in (None, 443) and parsed.path.startswith('/support/') and not self.href.startswith('#'):
            self.releases[match[1]] = url
        self.href = None


def check(installed: dict[str, Any]) -> dict[str, Any]:
    parser = _DownloadLinks()
    parser.feed(fetch_text(SOURCE_URL))
    if not parser.releases:
        raise ValueError("could not parse published WebSphere 9.0.5 download links")
    latest = max(parser.releases, key=version_tuple)
    selected_source = SOURCE_URL
    fix_pack_url = parser.releases[latest]
    evidence = {'kind': 'ibm_download_index', 'source_url': SOURCE_URL}
    # A separately confirmed package must not disappear when IBM indexes lag.
    # Confirmation dates never advance just because the index was fetched again.
    refs = references('websphere')
    for release in refs.pop('confirmed_fix_packs', []):
        if version_tuple(release['version']) > version_tuple(latest):
            latest = release['version']
            selected_source = fix_pack_url = release['source_url']
            evidence = dict(release)
    current = str(installed.get("version") or "")
    status = "review_required" if version_tuple(current) >= version_tuple(latest) else "update_available"

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
        **refs,
        "fix_pack_url": fix_pack_url,
        "availability_evidence": evidence,
        "index_source_url": SOURCE_URL,
        "cumulative": True,
        "scope": "fix_pack_and_reviewed_independent_ifixes",
        "source_url": selected_source,
        "ifx_audit": "pending",
        "notes": [
            "WebSphere traditional fix packs are cumulative.",
            "CURRENT here means current fix-pack level only; interim fixes are audited separately.",
        ],
    }
