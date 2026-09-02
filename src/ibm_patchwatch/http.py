from __future__ import annotations

import urllib.error
import urllib.request


class HTTPError(RuntimeError):
    pass


def fetch_text(url: str, timeout: int = 30) -> str:
    """Fetch a public IBM page using stdlib urllib.

    urllib's default opener honors HTTP_PROXY/HTTPS_PROXY/NO_PROXY from the
    environment, which is important for the central scanner in enterprise
    networks.
    """
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ibm-patchwatch/0.2 (+https://github.com/mrAibo/CM_Discovery)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            return data.decode(charset, errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise HTTPError(f"failed to fetch {url}: {exc}") from exc
