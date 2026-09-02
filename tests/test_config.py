from pathlib import Path

from ibm_patchwatch.config import load_config


def test_load_config(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        '''
[storage]
database = "state/test.db"

[hosts.cmtest]
collector = "/root/bin/ibm_discovery.py"
environment = "test"
'''.strip()
    )

    loaded = load_config(config)
    assert loaded.hosts["cmtest"].collector == "/root/bin/ibm_discovery.py"
    assert loaded.hosts["cmtest"].environment == "test"
    assert loaded.database == (tmp_path / "state/test.db").resolve()
