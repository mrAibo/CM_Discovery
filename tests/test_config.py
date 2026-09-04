from pathlib import Path

from ibm_patchwatch.config import load_config


def test_load_config(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        '''
[hosts.cmtest]
collector = "/root/bin/ibm_discovery.py"
'''.strip()
    )

    loaded = load_config(config)
    assert loaded.hosts["cmtest"].collector == "/root/bin/ibm_discovery.py"
    assert loaded.ssh.command == "ssh"
    assert loaded.ssh.connect_timeout == 15
    assert loaded.ssh.collector_timeout == 60
