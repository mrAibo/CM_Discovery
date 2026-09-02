from ibm_patchwatch.imcl import parse_packages


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
