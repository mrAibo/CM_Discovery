import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('catalog_refresh', Path(__file__).resolve().parents[1] / 'scripts/update_ibm_catalog.py')
refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh)


def test_cm_refresh_cannot_overwrite_fp5_with_historical_fp1(monkeypatch, tmp_path):
    output = tmp_path / 'catalog.json'
    old = {'available': {'version': '8.7.00.500', 'fix_pack': 5}, 'source_url': 'confirmed FP5'}
    output.write_text(json.dumps({'products': {'content_manager': old}}))
    monkeypatch.setattr(refresh, 'OUTPUT', output)
    for provider in (refresh.content_navigator, refresh.daeja, refresh.db2, refresh.java, refresh.iccsap, refresh.websphere):
        monkeypatch.setattr(provider, 'check', lambda installed: {'available': {'version': '1'}})
    monkeypatch.setattr(refresh.content_manager, 'check', lambda installed: {'available': {'version': '8.7.00.100', 'fix_pack': 1}})
    refresh.main()
    result = json.loads(output.read_text())
    assert result['products']['content_manager']['available'] == old['available']
    assert 'regressed' in result['products']['content_manager']['refresh_error']['message']
    assert result['refresh_status'] == 'partial'


def test_refresh_preserves_independent_ifixes_and_their_review_date():
    from ibm_patchwatch.providers.fix_references import references
    result = {'available': {'version': '9.0.5.28'}, **references('websphere')}
    entry = refresh._entry(result, '2026-09-08T00:00:00Z')
    assert entry['fix_pack_cumulative'] is True
    assert all(f['cumulative'] is False for f in entry['interim_fixes'])
    assert all(f['checked_at'] == '2026-09-07' for f in entry['interim_fixes'])
