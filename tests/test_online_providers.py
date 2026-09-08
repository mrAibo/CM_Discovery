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
    <a href="https://www.ibm.com/support/pages/fp27">Download Fix Pack 9.0.5.27</a>
    <a href="https://www.ibm.com/support/pages/fp28">Download Fix Pack 9.0.5.28</a>
    """
    monkeypatch.setattr(websphere, "fetch_text", lambda url: html)
    monkeypatch.setattr(websphere, "references", lambda product: {})
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


def test_websphere_confirmed_package_survives_lagging_index(monkeypatch):
    monkeypatch.setattr(websphere, 'fetch_text', lambda url: '<a href="/support/pages/fp28">Download Fix Pack 9.0.5.28</a>')
    result = websphere.check({'version': '9.0.5.25'})
    assert result['available']['version'] == '9.0.5.29'
    assert result['availability_evidence']['kind'] == 'operator_confirmed'
    assert result['availability_evidence']['checked_at'] == '2026-09-08'
    assert '9.0.5-WS-WAS-FP029' in result['fix_pack_url']
    assert result['cumulative'] is True
    assert all(f['cumulative'] is False for f in result['interim_fixes'])


def test_websphere_future_mentions_are_not_releases(monkeypatch):
    html = ('<a href="/support/pages/fp28">Download Fix Pack 9.0.5.28</a>'
            '<h2>Fix Pack 9.0.5.30</h2><p>Estimated future release date: 8 December 2026</p>'
            '<a href="#future">Download Fix Pack 9.0.5.31</a>'
            '<a href="https://evil.example/fp32">Download Fix Pack 9.0.5.32</a>')
    monkeypatch.setattr(websphere, 'fetch_text', lambda url: html)
    assert websphere.check({})['available']['version'] == '9.0.5.29'


def test_websphere_new_published_release_supersedes_confirmation(monkeypatch):
    monkeypatch.setattr(websphere, 'fetch_text', lambda url: '<a href="/support/pages/fp30">Download <b>Fix Pack 9.0.5.30</b></a>')
    result = websphere.check({})
    assert result['available']['version'] == '9.0.5.30'
    assert result['availability_evidence']['kind'] == 'ibm_download_index'
    assert result['fix_pack_url'] == 'https://www.ibm.com/support/pages/fp30'


def test_websphere_unparseable_index_is_not_a_successful_refresh(monkeypatch):
    import pytest
    monkeypatch.setattr(websphere, 'fetch_text', lambda url: '<h1>Login</h1>')
    with pytest.raises(ValueError, match='published'):
        websphere.check({})
