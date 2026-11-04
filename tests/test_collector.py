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


def test_timeout_is_its_own_status(monkeypatch):
    import subprocess
    def boom(*a, **k): raise subprocess.TimeoutExpired('x', 1)
    monkeypatch.setattr(collector.subprocess, 'run', boom)
    assert collector.run(['x'], 1)[3] == 'timeout'
    monkeypatch.setattr(collector.os, 'access', lambda *a: True)
    result = {'products': [], 'discovery': {}}
    collector.was(result)
    assert result['discovery']['websphere']['status'] == 'timeout'


def test_db2profile_derived_from_path_and_called_without_string_formatting(monkeypatch):
    calls = []
    monkeypatch.setattr(collector.os, 'access', lambda *a: True)
    monkeypatch.setattr(collector.os.path, 'isfile', lambda *a: True)
    def fake(cmd, *a):
        calls.append(cmd)
        return (1, '', '', 'direct', None) if len(calls) == 1 else (0, 'DB2 v11.5.9.0', '', 'direct', None)
    monkeypatch.setattr(collector, 'run', fake)
    monkeypatch.setitem(collector.P, 'db2', "/data/x y/sqllib/bin/db2level")
    collector.db2({'products': [], 'discovery': {}})
    assert calls[1][1:] == ['-c', '. "$1" && exec "$2"', 'collector', '/data/x y/sqllib/db2profile', '/data/x y/sqllib/bin/db2level']


def test_path_option_only_known_keys_and_output_file(monkeypatch, tmp_path, capsys):
    import pytest
    monkeypatch.setattr(collector, 'P', dict(collector.P))
    with pytest.raises(SystemExit):
        collector.main(['--path', 'bogus=/x'])
    with pytest.raises(SystemExit):
        collector.main(['--version'])
    assert collector.COLLECTOR_VERSION in capsys.readouterr().out
    out = tmp_path / 'inv.json'
    collector.main(['--skip-im', '--path', 'was=/nonexistent/vi', '--output', str(out)])
    import json
    data = json.loads(out.read_text())
    assert data['discovery']['websphere'] == {**data['discovery']['websphere'], 'status': 'not_found', 'path': '/nonexistent/vi'}


def test_root_warning(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(collector.os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setattr(collector, 'P', dict(collector.P))
    collector.main(['--skip-im', '--output', str(tmp_path / 'x.json')])
    assert 'root' in capsys.readouterr().err
