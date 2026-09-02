from __future__ import annotations

import json
import subprocess
from typing import Any

from .config import HostConfig, SSHConfig
from .imcl import normalize_installation_manager


class SSHScanError(RuntimeError):
    pass


def collect_inventory(host: HostConfig, ssh: SSHConfig) -> dict[str, Any]:
    command = [
        ssh.command,
        "-T",
        "-o", "BatchMode=yes",
        "-o", f"ConnectTimeout={ssh.connect_timeout}",
        host.alias,
        host.collector,
        "--json",
    ]

    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=ssh.collector_timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SSHScanError(
            f"collector timed out after {ssh.collector_timeout}s on {host.alias}"
        ) from exc
    except OSError as exc:
        raise SSHScanError(f"failed to execute SSH: {exc}") from exc

    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise SSHScanError(
            f"collector failed on {host.alias} with rc={completed.returncode}: {stderr}"
        )

    payload = completed.stdout.strip()
    if not payload:
        raise SSHScanError(f"collector returned empty stdout on {host.alias}")

    try:
        inventory = json.loads(payload)
    except json.JSONDecodeError as exc:
        preview = payload[:500].replace("\n", "\\n")
        raise SSHScanError(
            f"collector returned invalid JSON on {host.alias}: {preview}"
        ) from exc

    if not isinstance(inventory, dict):
        raise SSHScanError(f"collector returned non-object JSON on {host.alias}")

    normalize_installation_manager(inventory)
    return inventory
