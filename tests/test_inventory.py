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
