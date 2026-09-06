#!/usr/bin/env python3
"""Build one portable HTML file. Python 3.6+, standard library, no network.

The default public build never contains inventory. --inventory is an explicit
private-report export and must not overwrite the tracked public artifact.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_OUTPUT = ROOT / "docs" / "IBM-Patchwatch.html"


def script_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace(
        "<", "\\u003c"
    ).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def csp_hash(text):
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return "'sha256-" + base64.b64encode(digest).decode("ascii") + "'"


def build(catalog, inventory=None, notes=None):
    if not isinstance(catalog, dict) or catalog.get("schema_version") != 2:
        raise ValueError("expected catalog schema_version 2")
    if not isinstance(catalog.get("products"), dict):
        raise ValueError("catalog.products must be an object")
    if inventory is not None:
        if not isinstance(inventory, dict) or inventory.get("schema_version") != 1:
            raise ValueError("expected inventory schema_version 1")
        if not isinstance(inventory.get("products"), list) or not isinstance(inventory.get("host"), dict):
            raise ValueError("inventory needs products list and host object")
    assets = ROOT / "web"
    css = (assets / "styles.css").read_text(encoding="utf-8")
    js = (assets / "app.js").read_text(encoding="utf-8")
    policy = "default-src 'none'; base-uri 'none'; object-src 'none'; form-action 'none'; connect-src 'none'; style-src " + csp_hash(css) + "; script-src " + csp_hash(js)
    replacements = {
        "__CSP__": policy,
        "__CSS__": css,
        "__CATALOG__": script_json(catalog),
        "__INVENTORY__": script_json(inventory),
        "__NOTES__": script_json(notes if notes is not None else read_json(assets / "verified-notes.json")),
        "__JS__": js,
    }
    # One pass: data containing template-like strings cannot replace another slot.
    import re
    return re.sub(r"__(?:CSP|CSS|CATALOG|INVENTORY|NOTES|JS)__", lambda m: replacements[m.group(0)], (assets / "page.html").read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=ROOT / "data" / "ibm" / "catalog.json")
    parser.add_argument("--inventory", type=Path, help="optional private inventory; never commit the resulting report")
    parser.add_argument("--output", type=Path, default=PUBLIC_OUTPUT)
    args = parser.parse_args()
    if args.inventory and args.output.resolve() == PUBLIC_OUTPUT.resolve():
        parser.error("--inventory requires --output outside the tracked public HTML")
    catalog = read_json(args.catalog)
    inventory = read_json(args.inventory) if args.inventory else None
    html = build(catalog, inventory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print("Built {} ({} bytes; {})".format(args.output, len(html.encode("utf-8")), "private inventory embedded" if inventory else "catalog only"))


if __name__ == "__main__":
    main()
