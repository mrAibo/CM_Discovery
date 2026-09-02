from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PRODUCT_NAMES = {
    "content_manager": "IBM Content Manager",
    "content_navigator": "IBM Content Navigator",
    "daeja_viewone_virtual": "IBM Daeja ViewONE Virtual",
    "db2": "IBM DB2",
    "ibm_java": "IBM SDK, Java Technology Edition",
    "iccsap": "IBM Content Collector for SAP Applications",
    "websphere": "IBM WebSphere Application Server",
}


@dataclass(frozen=True)
class UpdateRow:
    """Normalized row used by the presentation layer.

    Keeping this model independent from Rich makes the GitHub/catalog fetching
    code easy to test and reusable from JSON, web, or other front ends later.
    """

    product_id: str
    product_name: str
    latest: str
    maintenance: str
    build: str
    download_url: str | None
    details_url: str | None


@dataclass(frozen=True)
class CatalogSnapshot:
    repository_ref: str
    revision: str
    generated_at: str | None
    rows: tuple[UpdateRow, ...]


class GitCatalogError(RuntimeError):
    pass


class GitCatalogSource:
    """Read the IBM update catalog from a GitHub-backed local Git checkout.

    The central server already has working access to github.com.  Rather than
    introducing another API hostname, this source uses the existing Git remote:

      git fetch origin main -> git show origin/main:data/ibm/catalog.json

    The working tree is never reset or modified.  Only the remote-tracking ref
    is refreshed, so locally maintained config.toml and runtime data are safe.
    """

    def __init__(
        self,
        repo_path: Path,
        *,
        remote: str = "origin",
        branch: str = "main",
        catalog_path: str = "data/ibm/catalog.json",
    ) -> None:
        self.repo_path = repo_path.resolve()
        self.remote = remote
        self.branch = branch
        self.catalog_path = catalog_path

    @property
    def remote_ref(self) -> str:
        return f"refs/remotes/{self.remote}/{self.branch}"

    @property
    def display_ref(self) -> str:
        return f"{self.remote}/{self.branch}"

    def _git(self, *args: str) -> str:
        cmd = ["git", "-C", str(self.repo_path), *args]
        try:
            completed = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            detail = getattr(exc, "stderr", None) or str(exc)
            raise GitCatalogError(f"git command failed: {' '.join(cmd)}: {detail.strip()}") from exc
        return completed.stdout.strip()

    def fetch(self) -> None:
        """Refresh only the configured remote-tracking branch."""
        refspec = f"refs/heads/{self.branch}:{self.remote_ref}"
        self._git("fetch", "--quiet", self.remote, refspec)

    def read_catalog(self) -> dict[str, Any]:
        raw = self._git("show", f"{self.display_ref}:{self.catalog_path}")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GitCatalogError(f"invalid JSON in {self.display_ref}:{self.catalog_path}: {exc}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("products"), dict):
            raise GitCatalogError("catalog has no products object")
        return payload

    def revision(self) -> str:
        return self._git("rev-parse", "--short=12", self.display_ref)

    def snapshot(self, *, fetch: bool = True) -> CatalogSnapshot:
        if fetch:
            self.fetch()
        payload = self.read_catalog()
        return CatalogSnapshot(
            repository_ref=self.display_ref,
            revision=self.revision(),
            generated_at=str(payload.get("generated_at")) if payload.get("generated_at") else None,
            rows=tuple(normalize_catalog(payload)),
        )


def _latest_label(product_id: str, available: dict[str, Any]) -> str:
    version = str(available.get("version") or "?")
    suffixes: list[str] = []

    if product_id == "content_manager" and available.get("fix_pack") is not None:
        suffixes.append(f"FP{available['fix_pack']}")
    if available.get("interim_fix") is not None:
        suffixes.append(f"iFix {available['interim_fix']}")
    if available.get("special_build"):
        suffixes.append(str(available["special_build"]))
    if available.get("jre_version"):
        suffixes.append(f"JRE {available['jre_version']}")

    return " ".join([version, *suffixes])


def _maintenance_label(value: object) -> str:
    if value is True:
        return "cumulative"
    if value is False:
        return "non-cumulative"
    return "not assumed"


def _build_label(available: dict[str, Any]) -> str:
    for key in ("build_level", "ptf", "fix_name", "update_number"):
        if available.get(key):
            return str(available[key])
    return ""


def normalize_catalog(payload: dict[str, Any]) -> list[UpdateRow]:
    """Convert catalog JSON into presentation-neutral update rows.

    Direct download links are shown only when the catalog explicitly contains a
    verified ``download_url``.  We deliberately do not invent Fix Central URLs.
    ``source_url`` remains a separate details/readme link.
    """
    products = payload.get("products") or {}
    rows: list[UpdateRow] = []

    for product_id, entry in products.items():
        if not isinstance(entry, dict):
            continue
        available = entry.get("available") or {}
        if not isinstance(available, dict):
            available = {}

        download_url = available.get("download_url") or entry.get("download_url")
        details_url = entry.get("source_url")
        rows.append(
            UpdateRow(
                product_id=str(product_id),
                product_name=PRODUCT_NAMES.get(str(product_id), str(product_id)),
                latest=_latest_label(str(product_id), available),
                maintenance=_maintenance_label(entry.get("cumulative")),
                build=_build_label(available),
                download_url=str(download_url) if download_url else None,
                details_url=str(details_url) if details_url else None,
            )
        )

    order = {product_id: index for index, product_id in enumerate(PRODUCT_NAMES)}
    rows.sort(key=lambda row: (order.get(row.product_id, 999), row.product_name.lower()))
    return rows
