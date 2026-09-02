from __future__ import annotations

from .github_catalog import CatalogSnapshot
from .update_report import HostUpdateReport


def _link_text(label: str, url: str):
    from rich.text import Text

    return Text(label, style=f"bold cyan link {url}")


def _links(download_url: str | None, details_url: str | None):
    from rich.text import Text

    text = Text()
    if download_url:
        text.append_text(_link_text("download", download_url))
        if details_url and details_url != download_url:
            text.append("  ")
            text.append_text(_link_text("details", details_url))
    elif details_url:
        text.append_text(_link_text("details", details_url))
    else:
        text.append("-")
    return text


def render_update_table(snapshot: CatalogSnapshot, *, console=None) -> None:
    """Render the global latest-level catalog without host comparison."""
    try:
        from rich.console import Console
        from rich.table import Table
    except ModuleNotFoundError as exc:
        raise RuntimeError("Rich is required for table rendering: install package 'rich'") from exc

    console = console or Console()
    table = Table(
        title="IBM Patchwatch – latest update catalog",
        caption=(
            f"GitHub ref: {snapshot.repository_ref}  "
            f"revision: {snapshot.revision}  "
            f"generated: {snapshot.generated_at or 'unknown'}"
        ),
        header_style="bold",
        show_lines=False,
    )
    table.add_column("Product", no_wrap=False)
    table.add_column("Latest", no_wrap=True)
    table.add_column("Maintenance", no_wrap=True)
    table.add_column("Build / Fix ID", no_wrap=False)
    table.add_column("Download / Details", no_wrap=False)

    for row in snapshot.rows:
        table.add_row(
            row.product_name,
            row.latest,
            row.maintenance,
            row.build or "-",
            _links(row.download_url, row.details_url),
        )

    console.print(table)


def render_host_update_table(report: HostUpdateReport, *, console=None) -> None:
    """Render the useful server view: installed levels versus catalog targets."""
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.text import Text
    except ModuleNotFoundError as exc:
        raise RuntimeError("Rich is required for table rendering: install package 'rich'") from exc

    console = console or Console()
    table = Table(
        title=f"IBM Patchwatch – updates for {report.host_alias} ({report.remote_hostname})",
        caption=(
            f"GitHub ref: {report.repository_ref}  revision: {report.revision}  "
            f"catalog generated: {report.generated_at or 'unknown'}"
        ),
        header_style="bold",
        show_lines=True,
    )
    table.add_column("Status", no_wrap=True)
    table.add_column("Product", no_wrap=False)
    table.add_column("Installed", no_wrap=False)
    table.add_column("Target", no_wrap=False)
    table.add_column("Maintenance", no_wrap=True)
    table.add_column("Build / Fix ID", no_wrap=False)
    table.add_column("Download / Details", no_wrap=False)

    labels = {
        "current": ("CURRENT", "green"),
        "update_available": ("UPDATE", "bold yellow"),
        "review_required": ("REVIEW", "bold magenta"),
    }

    for row in report.rows:
        label, style = labels.get(row.status, (row.status.upper(), "red"))
        table.add_row(
            Text(label, style=style),
            row.product_name,
            row.installed,
            row.target,
            row.maintenance,
            row.build or "-",
            _links(row.download_url, row.details_url),
        )

    console.print(table)
