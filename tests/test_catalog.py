import json
from datetime import datetime, timezone

from ibm_patchwatch.catalog import fallback_result


def test_catalog_fallback_compares_websphere(tmp_path):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "products": {
            "websphere": {
                "available": {"version": "9.0.5.28"},
                "cumulative": True,
                "scope": "fix_pack_only",
                "source_url": "https://www.ibm.com/example",
                "ifx_audit": "pending",
                "notes": [],
            }
        },
    }), encoding="utf-8")

    result = fallback_result(
        "websphere",
        {"version": "9.0.5.25"},
        RuntimeError("proxy blocked"),
        path=catalog,
    )

    assert result["status"] == "update_available"
    assert result["source_mode"] == "catalog"
    assert result["catalog_stale"] is False
    assert result["available"]["version"] == "9.0.5.28"
