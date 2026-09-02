from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    host_alias TEXT NOT NULL,
    environment TEXT NOT NULL,
    remote_hostname TEXT,
    collector_version TEXT,
    collected_at TEXT NOT NULL,
    inventory_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scans_host_id ON scans(host_alias, id DESC);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def save_scan(
    db: sqlite3.Connection,
    host_alias: str,
    environment: str,
    inventory: dict[str, Any],
) -> int:
    host = inventory.get("host") or {}
    collected_at = str(inventory.get("timestamp") or datetime.now(timezone.utc).isoformat())
    cursor = db.execute(
        """
        INSERT INTO scans(
            host_alias, environment, remote_hostname,
            collector_version, collected_at, inventory_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            host_alias,
            environment,
            host.get("hostname"),
            inventory.get("collector_version"),
            collected_at,
            json.dumps(inventory, ensure_ascii=False, separators=(",", ":")),
        ),
    )
    db.commit()
    return int(cursor.lastrowid)


def latest_scans(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT s.*
        FROM scans s
        JOIN (
            SELECT host_alias, MAX(id) AS max_id
            FROM scans
            GROUP BY host_alias
        ) latest ON latest.max_id = s.id
        ORDER BY s.host_alias
        """
    ).fetchall()
