from ibm_patchwatch.providers import content_manager, content_navigator, daeja, iccsap


def test_content_manager_fixpack(monkeypatch):
    html = "<h1>IBM Content Manager Version 8.7 Fix Pack 5 Readme</h1><nav>Update name: Fix Pack 1</nav><script>Update name: Fix Pack 4</script><p>Update name: Fix Pack 5</p><p>Version 8.7 Fix Pack 1 history</p>"
    monkeypatch.setattr(content_manager, "fetch_text", lambda url: html)
    result = content_manager.check({"version": "8.7.00.400"})
    assert result["status"] == "update_available"
    assert result["available"] == {"version": "8.7.00.500", "fix_pack": 5}


def test_content_manager_rejects_wrong_or_ambiguous_page(monkeypatch):
    import pytest
    for html in ["Update name: Fix Pack 1", "Version 8.7 Fix Pack 5 Readme", "Update name: Fix Pack 5 Update name: Fix Pack 1"]:
        monkeypatch.setattr(content_manager, "fetch_text", lambda url: html)
        with pytest.raises(ValueError):
            content_manager.check({"version": "8.7.00.500"})


def test_content_navigator_ifix(monkeypatch):
    html = """
    <p>Update name: Interim Fix 12</p>
    <p>Build number: icn310.012.703</p>
    """
    monkeypatch.setattr(content_navigator, "fetch_text", lambda url: html)
    result = content_navigator.check({
        "version": "3.1.0",
        "build_level": "icn310.006.430",
        "build_number": "202509150657",
    })
    assert result["status"] == "update_available"
    assert result["installed"]["interim_fix"] == 6
    assert result["available"]["interim_fix"] == 12
    assert result["available"]["build_level"] == "icn310.012.703"
    assert result["cumulative"] is None


def test_daeja_ifix_stream(monkeypatch):
    html = """
    <p>IBM Daeja ViewONE, 5.0.15 iFix 6 Readme</p>
    <p>Update name: iFix 6</p>
    <h2>Fixes and Features released in previous iFixes and Fix Packs</h2>
    """
    monkeypatch.setattr(daeja, "fetch_text", lambda url: html)
    result = daeja.check({"version": "5.0.15", "interim_fix": 2, "build": "48708"})
    assert result["status"] == "update_available"
    assert result["available"]["interim_fix"] == 6
    assert result["cumulative"] is True


def test_iccsap_embedded_jre_security_fix(monkeypatch):
    html = """
    <p>Use IBM Content Collector for SAP Applications 4.0.0.4-ICCSAP-Base-JRE-8.0.8.70</p>
    <p>12 Aug 2026: Initial Publication</p>
    """
    monkeypatch.setattr(iccsap, "fetch_text", lambda url: html)
    result = iccsap.check({
        "version": "4.0.0.4",
        "installed_fixes": [
            "JRE update (com.ibm.im.iccsap.offering.JRE_fix_20241212)"
        ],
    })
    assert result["status"] == "review_required"
    assert result["installed"]["latest_jre_fix_date"] == "20241212"
    assert result["available"]["jre_version"] == "8.0.8.70"
    assert result["available"]["jre_fix_date"] == "20260812"


def test_iccsap_keeps_base_jre_and_binary_if_separate(monkeypatch):
    monkeypatch.setattr(iccsap, 'fetch_text', lambda url: '4.0.0.4-ICCSAP-Base-JRE-8.0.8.70')
    result = iccsap.check({'version': '4.0.0.4', 'jre_version': '8.0.8.70'})
    assert result['status'] == 'review_required'
    assert result['available']['version'] == '4.0.0.4'
    assert result['available']['jre_version'] == '8.0.8.70'
    assert result['interim_fixes'][0]['fix_id'] == '4004-ICCSAP-FP4-IF21'
    assert result['interim_fixes'][0]['cumulative'] is False
    assert 'platform=Linux+64-bit,x86_64' in result['download_url']
