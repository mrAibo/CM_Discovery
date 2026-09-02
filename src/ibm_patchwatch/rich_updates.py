from __future__ import annotations

from typing import Iterable

from .github_catalog import CatalogSnapshot, UpdateRow


def _link_text(label: str, url: str):
    from rich.text import Text

    return Text(label, style=f"bold cyan link {url}")


def render_update_table(snapshot: CatalogSnapshot, *, console=None) -> None:
    """Render one update snapshot as a Rich table.

    Rich is imported lazily so the data/fetching layer remains dependency-free.
    The central server is expected to have Rich installed, as requested.
    """
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.text import Text
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
        links = Text()
        if row.download_url:
            links.append_text(_link_text("download", row.download_url))
            if row.details_url and row.details_url != row.download_url:
                links.append("  ")
                links.append_text(_link_text("details", row.details_url))
        elif row.details_url:
            links.append_text(_link_text("details", row.details_url))
        else:
            links.append("-")

        table.add_row(
            row.product_name,
            row.latest,
            row.maintenance,
            row.build or "-",
            links,
        )

    console.print(table)
