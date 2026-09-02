from ibm_patchwatch.providers import db2, java, websphere


def test_db2_latest_published_update(monkeypatch):
    html = """
    <h2>Db2 Update 87984*</h2>
    <p>*This is the most recent Db2 Update</p>
    <p>2026-08-06</p>
    <p>Linux x86 PTF: DYN2607151721AMD64_87984 Build level: s2607151021</p>
    """
    monkeypatch.setattr(db2, "fetch_text", lambda url: html)
    result = db2.check({"version": "11.5.9.0", "fix_pack": "0", "special_build": "special_63280"})
    assert result["status"] == "update_available"
    assert result["available"]["update_number"] == "87984"
    assert result["available"]["special_build"] == "special_87984"
    assert result["available"]["ptf"] == "DYN2607151721AMD64_87984"
    assert result["cumulative"] is True


def test_websphere_latest_fixpack(monkeypatch):
    html = """
    <h2>Fix Pack 9.0.5.27</h2>
    <h2>Fix Pack 9.0.5.28</h2>
    """
    monkeypatch.setattr(websphere, "fetch_text", lambda url: html)
    result = websphere.check({"version": "9.0.5.25"})
    assert result["status"] == "update_available"
    assert result["available"]["version"] == "9.0.5.28"
    assert result["ifx_audit"] == "pending"


def test_java_latest_refresh(monkeypatch):
    html = """
    <p>Version 8, Service Refresh 8 Fix Pack 70 (8.0.8.70)</p>
    <p>Version 8, Service Refresh 8 Fix Pack 71 (8.0.8.71)</p>
    """
    monkeypatch.setattr(java, "fetch_text", lambda url: html)
    result = java.check({"version": "8.0.8.51"})
    assert result["status"] == "update_available"
    assert result["available"]["version"] == "8.0.8.71"
    assert result["available"]["service_refresh"] == 8
    assert result["available"]["fix_pack"] == 71
