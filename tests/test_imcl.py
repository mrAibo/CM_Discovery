from ibm_patchwatch.imcl import normalize_installation_manager, parse_packages


def test_german_imcl_output():
    packages = parse_packages([
        "[Paketgruppe]",
        "Name: IBM WebSphere Application Server V9.0",
        "Installationsverzeichnis: /opt/IBM/WebSphere/AppServer",
        "[Paket]",
        "Name: IBM WebSphere Application Server (com.ibm.websphere.BASE.v90)",
        "Version: 9.0.5.25 (9.0.5025.20250820_1643)",
        "Repository: /software/9.0.5-WS-WAS-FP025.zip",
        "Fixes:",
        "Keine",
        "Rollbackversionen:",
        "9.0.5.22 (9.0.5022.20241118_0055)",
    ])
    assert packages[0]["package_id"] == "com.ibm.websphere.BASE.v90"
    assert packages[0]["version"] == "9.0.5.25"
    assert packages[0]["installation_directory"] == "/opt/IBM/WebSphere/AppServer"
    assert packages[0]["rollback_versions"] == ["9.0.5.22 (9.0.5022.20241118_0055)"]


def test_iccsap_fixes_are_correlated_to_product():
    inventory = {
        "products": [
            {"id": "iccsap", "name": "IBM Content Collector for SAP Applications", "version": "4.0.0.4"}
        ],
        "installation_manager": {
            "packages_raw": [
                "[Paketgruppe]",
                "Installationsverzeichnis: /opt/IBM/iccsap",
                "[Paket]",
                "Name: IBM Content Collector for SAP Applications (com.ibm.im.iccsap.offering)",
                "Version: 4.0.0.4 (4.0.0.4)",
                "Fixes:",
                "GSKit update (com.ibm.im.iccsap.offering.GSKit_fix_20151218)",
                "JRE update (com.ibm.im.iccsap.offering.JRE_fix_20230104)",
                "JRE update (com.ibm.im.iccsap.offering.JRE_fix_20241212)",
                "Rollbackversionen:",
                "4.0.0.0 (4.0.0.0)",
            ]
        },
    }
    normalize_installation_manager(inventory)
    product = inventory["products"][0]
    assert product["im_package_id"] == "com.ibm.im.iccsap.offering"
    assert product["im_version_matches"] is True
    assert len(product["installed_fixes"]) == 3
    assert product["rollback_versions"] == ["4.0.0.0 (4.0.0.0)"]
