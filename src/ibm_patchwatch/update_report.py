from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .catalog import compare_installed
from .github_catalog import CatalogSnapshot, UpdateRow
from .inventory import product_version


@dataclass(frozen=True)
class HostUpdateRow:
    """One installed-vs-catalog comparison row.

    This model deliberately contains no Rich objects and performs no network
    access.  It can therefore be reused by terminal, JSON or future web UIs.
    """

    product_id: str
    product_name: str
    installed: str
    target: str
    status: str
    maintenance: str
    build: str
    download_url: str | None
    details_url: str | None


@dataclass(frozen=True)
class HostUpdateReport:
    host_alias: str
    remote_hostname: str
    repository_ref: str
    revision: str
    generated_at: str | None
    rows: tuple[HostUpdateRow, ...]


def build_host_update_report(
    host_alias: str,
    inventory: dict[str, Any],
    snapshot: CatalogSnapshot,
    catalog_payload: dict[str, Any],
) -> HostUpdateReport:
    """Join an IBM discovery inventory with the GitHub maintenance catalog."""

    installed_products = {
        str(item.get("id")): item
        for item in inventory.get("products", [])
        if isinstance(item, dict) and item.get("id")
    }
    catalog_products = catalog_payload.get("products") or {}
    snapshot_rows: dict[str, UpdateRow] = {row.product_id: row for row in snapshot.rows}

    rows: list[HostUpdateRow] = []
    for product_id, catalog_row in snapshot_rows.items():
        installed = installed_products.get(product_id)
        if not installed:
            continue

        entry = catalog_products.get(product_id)
        if not isinstance(entry, dict):
            status = "review_required"
        else:
            available = entry.get("available") or {}
            if not isinstance(available, dict):
                available = {}
            try:
                status = compare_installed(product_id, installed, available)
            except (KeyError, TypeError, ValueError):
                status = "review_required"

        rows.append(
            HostUpdateRow(
                product_id=product_id,
                product_name=catalog_row.product_name,
                installed=product_version(installed),
                target=catalog_row.latest,
                status=status,
                maintenance=catalog_row.maintenance,
                build=catalog_row.build,
                download_url=catalog_row.download_url,
                details_url=catalog_row.details_url,
            )
        )

    remote_hostname = str((inventory.get("host") or {}).get("hostname") or "?")
    return HostUpdateReport(
        host_alias=host_alias,
        remote_hostname=remote_hostname,
        repository_ref=snapshot.repository_ref,
        revision=snapshot.revision,
        generated_at=snapshot.generated_at,
        rows=tuple(rows),
    )
