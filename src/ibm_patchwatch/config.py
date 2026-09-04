from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tomllib


@dataclass(frozen=True)
class SSHConfig:
    command: str = "ssh"
    connect_timeout: int = 15
    collector_timeout: int = 60


@dataclass(frozen=True)
class HostConfig:
    alias: str
    collector: str


@dataclass(frozen=True)
class AppConfig:
    path: Path
    ssh: SSHConfig
    hosts: dict[str, HostConfig]


def load_config(path: str | Path = "config.toml") -> AppConfig:
    config_path = Path(path).expanduser().resolve()
    with config_path.open("rb") as handle:
        raw: dict[str, Any] = tomllib.load(handle)

    ssh_raw = raw.get("ssh", {})
    hosts_raw = raw.get("hosts", {})
    ssh = SSHConfig(
        command=str(ssh_raw.get("command", "ssh")),
        connect_timeout=int(ssh_raw.get("connect_timeout", 15)),
        collector_timeout=int(ssh_raw.get("collector_timeout", 60)),
    )

    hosts: dict[str, HostConfig] = {}
    for alias, item in hosts_raw.items():
        if not isinstance(item, dict):
            raise ValueError(f"hosts.{alias} must be a TOML table")
        collector = str(item.get("collector", "")).strip()
        if not collector:
            raise ValueError(f"hosts.{alias}.collector is required")
        hosts[alias] = HostConfig(alias=alias, collector=collector)

    return AppConfig(path=config_path, ssh=ssh, hosts=hosts)
