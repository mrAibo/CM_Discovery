from ibm_patchwatch.github_catalog import CatalogSnapshot, UpdateRow
from ibm_patchwatch.update_report import build_host_update_report


def _row(product_id: str, name: str, latest: str) -> UpdateRow:
    return UpdateRow(
        product_id=product_id,
        product_name=name,
        latest=latest,
        maintenance="cumulative",
        build="",
        download_url=None,
        details_url="https://example.invalid/details",
    )


def test_host_report_marks_updates_and_current_products():
    snapshot = CatalogSnapshot(
        repository_ref="origin/main",
        revision="abc123",
        generated_at="2026-09-02T12:00:00+00:00",
        rows=(
            _row("content_manager", "IBM Content Manager", "8.7.00.400 FP4"),
            _row("ibm_java", "IBM SDK, Java Technology Edition", "8.0.8.71"),
            _row("db2", "IBM DB2", "11.5.9.0 special_87984"),
        ),
    )
    catalog = {
        "products": {
            "content_manager": {"available": {"version": "8.7.00.400"}},
            "ibm_java": {"available": {"version": "8.0.8.71"}},
            "db2": {"available": {"version": "11.5.9.0", "special_build": "special_87984"}},
        }
    }
    inventory = {
        "host": {"hostname": "CMTEST01"},
        "products": [
            {"id": "content_manager", "version": "8.7.00.400"},
            {"id": "ibm_java", "version": "8.0.8.51"},
            {
                "id": "db2",
                "version": "11.5.9.0",
                "fix_pack": "0",
                "special_build": "special_63280",
            },
        ],
    }

    report = build_host_update_report("cmtest", inventory, snapshot, catalog)
    statuses = {row.product_id: row.status for row in report.rows}

    assert report.remote_hostname == "CMTEST01"
    assert statuses["content_manager"] == "current"
    assert statuses["ibm_java"] == "update_available"
    assert statuses["db2"] == "update_available"
