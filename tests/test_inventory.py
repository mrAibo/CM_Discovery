from ibm_patchwatch.inventory import patch_targets, product_version


def test_patch_targets_filters_embedded_clients() -> None:
    inventory = {
        "products": [
            {"id": "websphere", "version": "9.0.5.25"},
            {"id": "filenet_ce_client", "version": "5.5.7.0"},
            {"id": "daeja_viewone_virtual", "version": "5.0.15", "interim_fix": 2},
        ]
    }
    targets = patch_targets(inventory)
    assert [item["id"] for item in targets] == ["websphere", "daeja_viewone_virtual"]
    assert product_version(targets[1]) == "5.0.15 iFix 2"


def test_db2_maintenance_fingerprint() -> None:
    item = {
        "id": "db2",
        "version": "11.5.9.0",
        "fix_pack": "0",
        "special_build": "special_63280",
        "build_token": "DYN2507310822AMD64_63280",
    }
    assert product_version(item) == (
        "11.5.9.0 FP0 special_63280 DYN2507310822AMD64_63280"
    )


def test_installed_fix_count_is_visible() -> None:
    item = {
        "id": "iccsap",
        "version": "4.0.0.4",
        "installed_fixes": ["fix-a", "fix-b", "fix-c"],
    }
    assert product_version(item) == "4.0.0.4 +3 installed fixes"
