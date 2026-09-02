#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ibm_patchwatch.providers import (
    content_manager,
    content_navigator,
    daeja,
    db2,
    iccsap,
    java,
    websphere,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "ibm" / "catalog.json"


def _entry(result: dict) -> dict:
    return {
        "available": result.get("available") or {},
        "cumulative": result.get("cumulative"),
        "scope": result.get("scope"),
        "source_url": result.get("source_url"),
        "ifx_audit": result.get("ifx_audit"),
        "notes": result.get("notes") or [],
    }


def main() -> None:
    checks = {
        "content_manager": content_manager.check({"version": "0"}),
        "content_navigator": content_navigator.check({
            "version": "3.1.0",
            "build_level": "icn310.000.000",
        }),
        "daeja_viewone_virtual": daeja.check({
            "version": "5.0.15",
            "interim_fix": 0,
        }),
        "db2": db2.check({
            "version": "11.5.9.0",
            "fix_pack": "0",
            "special_build": "catalog_probe",
            "code_release": "SQL11059",
        }),
        "ibm_java": java.check({"version": "0"}),
        "iccsap": iccsap.check({
            "version": "4.0.0.4",
            "installed_fixes": [],
        }),
        "websphere": websphere.check({"version": "0"}),
    }

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "scripts/update_ibm_catalog.py",
        "products": {product_id: _entry(result) for product_id, result in checks.items()},
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"updated {OUTPUT}")


if __name__ == "__main__":
    main()
