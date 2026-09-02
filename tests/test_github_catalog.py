from ibm_patchwatch.github_catalog import normalize_catalog


def test_normalize_catalog_preserves_download_and_details_links():
    payload = {
        "generated_at": "2026-09-02T14:00:00+00:00",
        "products": {
            "content_navigator": {
                "available": {
                    "version": "3.1.0",
                    "interim_fix": 12,
                    "build_level": "icn310.012.703",
                    "download_url": "https://example.invalid/icn.zip",
                },
                "cumulative": None,
                "source_url": "https://example.invalid/readme",
            },
            "websphere": {
                "available": {"version": "9.0.5.28"},
                "cumulative": True,
                "source_url": "https://example.invalid/was",
            },
        },
    }

    rows = {row.product_id: row for row in normalize_catalog(payload)}

    icn = rows["content_navigator"]
    assert icn.latest == "3.1.0 iFix 12"
    assert icn.build == "icn310.012.703"
    assert icn.maintenance == "not assumed"
    assert icn.download_url == "https://example.invalid/icn.zip"
    assert icn.details_url == "https://example.invalid/readme"

    was = rows["websphere"]
    assert was.latest == "9.0.5.28"
    assert was.maintenance == "cumulative"
    assert was.download_url is None
    assert was.details_url == "https://example.invalid/was"


def test_normalize_catalog_formats_db2_and_iccsap():
    payload = {
        "products": {
            "db2": {
                "available": {
                    "version": "11.5.9.0",
                    "special_build": "special_87984",
                    "ptf": "DYN2607151721AMD64_87984",
                },
                "cumulative": True,
            },
            "iccsap": {
                "available": {
                    "version": "4.0.0.4",
                    "jre_version": "8.0.8.70",
                    "fix_name": "4.0.0.4-ICCSAP-Base-JRE-8.0.8.70",
                },
                "cumulative": None,
            },
        }
    }

    rows = {row.product_id: row for row in normalize_catalog(payload)}
    assert rows["db2"].latest == "11.5.9.0 special_87984"
    assert rows["db2"].build == "DYN2607151721AMD64_87984"
    assert rows["iccsap"].latest == "4.0.0.4 JRE 8.0.8.70"
    assert rows["iccsap"].build == "4.0.0.4-ICCSAP-Base-JRE-8.0.8.70"
