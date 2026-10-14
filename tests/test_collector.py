"""Collector failures must remain failures even when stdout contains a version."""
import ast
import importlib.util
from pathlib import Path

COLLECTOR = Path(__file__).resolve().parents[1] / 'collectors/ibm_discovery.py'
spec = importlib.util.spec_from_file_location('collector', COLLECTOR)
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


def test_collector_remains_python36():
    ast.parse(COLLECTOR.read_text(), feature_version=(3, 6))


def test_db2_nonzero_exit_is_not_reported_ok(monkeypatch):
    monkeypatch.setattr(collector.os, 'access', lambda *a: True)
    monkeypatch.setattr(collector.os.path, 'isfile', lambda *a: False)
    monkeypatch.setattr(collector, 'run', lambda *a: (7, 'DB2 v11.5.9.0 "special_63280"', 'failed', 'direct', None))
    result = {'products': [], 'discovery': {}}
    collector.db2(result)
    assert result['products'][0]['version'] == '11.5.9.0'
    assert result['discovery']['db2']['status'] == 'error'
    assert result['discovery']['db2']['returncode'] == 7


def test_was_zero_exit_with_no_product_is_parse_error(monkeypatch):
    monkeypatch.setattr(collector.os, 'access', lambda *a: True)
    monkeypatch.setattr(collector, 'run', lambda *a: (0, 'Unrecognized output format', '', 'direct', None))
    result = {'products': [], 'discovery': {}}
    collector.was(result)
    assert result['discovery']['websphere']['status'] == 'parse_error'


def test_nonempty_version_files_without_product_version_are_parse_errors(monkeypatch):
    monkeypatch.setattr(collector, 'read', lambda *a: 'unexpected format\nbuild.level=unknown')
    result = {'products': [], 'discovery': {}}
    collector.icn(result)
    collector.iccsap(result)
    assert result['discovery']['content_navigator']['status'] == 'parse_error'
    assert result['discovery']['iccsap']['status'] == 'parse_error'
