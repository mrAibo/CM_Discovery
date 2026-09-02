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
    environment: str = "unknown"


@dataclass(frozen=True)
class AppConfig:
    path: Path
    database: Path
    ssh: SSHConfig
    hosts: dict[str, HostConfig]


def _resolve_relative(base: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base / path).resolve()


def load_config(path: str | Path = "config.toml") -> AppConfig:
    config_path = Path(path).expanduser().resolve()
    with config_path.open("rb") as handle:
        raw: dict[str, Any] = tomllib.load(handle)

    base = config_path.parent
    storage = raw.get("storage", {})
    ssh_raw = raw.get("ssh", {})
    hosts_raw = raw.get("hosts", {})

    database = _resolve_relative(base, storage.get("database", "data/patchwatch.db"))
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
        hosts[alias] = HostConfig(
            alias=alias,
            collector=collector,
            environment=str(item.get("environment", "unknown")),
        )

    return AppConfig(path=config_path, database=database, ssh=ssh, hosts=hosts)
