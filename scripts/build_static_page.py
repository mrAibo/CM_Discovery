#!/usr/bin/env python3
"""Build a portable output folder. Python 3.6+, standard library, no network.

The default public build never contains inventory. --inventory is an explicit
private-report export and must not overwrite the tracked public artifact.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIRECTORY = ROOT / "output"
PUBLIC_OUTPUT = PUBLIC_DIRECTORY / "IBM-Patchwatch.html"
CATALOG_SOURCE = ROOT / "data" / "ibm" / "catalog.json"
NOTES_SOURCE = ROOT / "web" / "verified-notes.json"
COLLECTOR_SOURCE = ROOT / "collectors" / "ibm_discovery.py"


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


def public_path(path):
    path = Path(path).resolve()
    return (path == PUBLIC_DIRECTORY.resolve() or PUBLIC_DIRECTORY.resolve() in path.parents
            or path == (ROOT / "docs" / "IBM-Patchwatch.html").resolve())


def export_directory(output_dir, catalog_path, inventory_path=None):
    """Copy exactly the data embedded in the page, with no network or host scan."""
    output_dir = Path(output_dir)
    if inventory_path is not None and public_path(output_dir):
        raise ValueError("Private inventories require an output directory outside the public output/ folder")
    # Read and validate everything before writing files, including custom inputs.
    catalog_text = Path(catalog_path).read_text(encoding="utf-8-sig")
    notes_text = NOTES_SOURCE.read_text(encoding="utf-8-sig")
    inventory_text = Path(inventory_path).read_text(encoding="utf-8-sig") if inventory_path is not None else None
    html = build(json.loads(catalog_text), json.loads(inventory_text) if inventory_text is not None else None, json.loads(notes_text))
    files = {
        "IBM-Patchwatch.html": html,
        "catalog.json": catalog_text,
        "verified-notes.json": notes_text,
        "ibm_discovery.py": COLLECTOR_SOURCE.read_text(encoding="utf-8"),
        "README.md": """# IBM Patchwatch – fertige Dateien

Dieser Ordner enthält das vollständige portable Paket:

- `IBM-Patchwatch.html`: im Windows-Browser öffnen.
- `catalog.json`: dieselben Katalogdaten, die in der HTML-Datei eingebettet sind.
- `verified-notes.json`: dieselben datierten Hinweise wie in der HTML-Datei.
- `ibm_discovery.py`: auf den IBM-Server kopieren und dort das Inventar erzeugen:

```bash
python3 ibm_discovery.py --json > inventory.json
```

`inventory.json` vom IBM-Server in den lokalen Arbeitsordner übertragen und in
HTML über **Inventar öffnen** laden. Das öffentliche Paket enthält keine
Serverinventare. Der Collector benötigt Linux und Python 3.6+; der Browservergleich
benötigt keine Installation auf Windows. IBM-Pakete werden manuell heruntergeladen.

**Aktualisierung:** Den ganzen Ordner erneut herunterladen. Zum Import eines
neueren Katalogs in eine bereits geöffnete Seite **Katalog aktualisieren** verwenden.
Für neue Hinweise ebenfalls die neue HTML-Datei öffnen.

Die JSON-Kopien werden beim Build übernommen; Änderungen an den Quelldateien
werden erst durch einen erneuten Build in diesen Ordner übertragen. Die Hinweise
behalten ihr fachliches Prüfdatum unabhängig vom Katalogabruf.
""",
    }
    if inventory_text is not None:
        files["inventory.json"] = inventory_text
        files["README.md"] = files["README.md"].replace(
            "Das öffentliche Paket enthält keine\nServerinventare.",
            "Dieses private Paket enthält auch inventory.json und ein eingebettetes Inventar.\nNicht in das öffentliche Repository übernehmen."
        )
    protected_sources = {CATALOG_SOURCE.resolve(), NOTES_SOURCE.resolve(), COLLECTOR_SOURCE.resolve(), (ROOT / "README.md").resolve(), Path(catalog_path).resolve()}
    for name in files:
        target = (output_dir / name).resolve()
        if target in protected_sources:
            raise ValueError("Output files must not overwrite repository source files")
        if inventory_text is not None and public_path(target):
            raise ValueError("Private inventories require an output directory outside the public output/ folder")
    output_dir.mkdir(parents=True, exist_ok=True)
    if inventory_text is not None:
        output_dir.chmod(0o700)
    for name, content in files.items():
        target = output_dir / name
        target.write_text(content, encoding="utf-8")
        if inventory_text is not None:
            target.chmod(0o600)
    return list(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=CATALOG_SOURCE)
    parser.add_argument("--inventory", type=Path, help="optional private inventory; never commit the resulting report")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--output-dir", type=Path, help="complete folder; default: output/ in the repository")
    output.add_argument("--output", type=Path, help="legacy export: write only a single HTML file")
    args = parser.parse_args()
    if args.output is not None:
        if args.inventory and public_path(args.output):
            parser.error("--inventory requires --output outside the tracked public HTML/output folder")
        html = build(read_json(args.catalog), read_json(args.inventory) if args.inventory else None)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(html, encoding="utf-8")
        print("Built {}".format(args.output))
    else:
        directory = args.output_dir if args.output_dir is not None else PUBLIC_DIRECTORY
        try:
            names = export_directory(directory, args.catalog, args.inventory)
        except ValueError as exc:
            parser.error(str(exc))
        print("Built {}: {}".format(directory, ", ".join(names)))


if __name__ == "__main__":
    main()
