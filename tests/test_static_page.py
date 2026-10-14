import ast
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_static_page.py"
spec = importlib.util.spec_from_file_location("build_static_page", BUILDER)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_portable_builder_is_python36_and_offline():
    ast.parse(BUILDER.read_text(), feature_version=(3, 6))
    html = builder.build(json.loads((ROOT / "data/ibm/catalog.json").read_text()))
    assert '<script id="inventory-data" type="application/json">null</script>' in html
    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "connect-src 'none'" in html
    assert not re.search(r'<(?:script|link)[^>]+(?:src|href)=', html)
    for tag in ("style", "script"):
        inline = re.search(r"<" + tag + r">(.*?)</" + tag + ">", html, re.S).group(1)
        digest = base64.b64encode(hashlib.sha256(inline.encode()).digest()).decode()
        assert "'sha256-" + digest + "'" in html


def test_private_inventory_is_safely_embedded_without_template_replacement():
    catalog = {"schema_version": 2, "products": {}}
    inv = {"schema_version":1, "host":{"hostname":"</script><script>alert(1)</script> __JS__"}, "products":[]}
    html = builder.build(catalog, inv)
    assert "<script>alert(1)</script>" not in html
    payload = re.search(r'<script id="inventory-data" type="application/json">(.*?)</script>', html, re.S).group(1)
    assert json.loads(payload) == inv


def test_private_inventory_cannot_overwrite_public_artifact(tmp_path):
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps({"schema_version":1,"host":{},"products":[]}))
    completed = subprocess.run([sys.executable, str(BUILDER), "--inventory", str(inventory)], capture_output=True, text=True)
    assert completed.returncode == 2
    assert "outside the public output/ folder" in completed.stderr


def test_output_folder_contains_matching_html_json_and_collector(tmp_path):
    catalog_path = tmp_path / "input-catalog.json"
    catalog_path.write_text(json.dumps({"schema_version":2,"products":{"test":{"available":{"version":"1.2"}}}}))
    destination = tmp_path / "bundle"
    names = builder.export_directory(destination, catalog_path)
    assert set(names) == {"IBM-Patchwatch.html", "catalog.json", "verified-notes.json", "ibm_discovery.py", "README.md"}
    html = (destination / "IBM-Patchwatch.html").read_text()
    for slot, name in [("catalog-data", "catalog.json"), ("notes-data", "verified-notes.json")]:
        embedded = re.search(r'<script id="' + slot + r'" type="application/json">(.*?)</script>', html, re.S).group(1)
        assert json.loads(embedded) == json.loads((destination / name).read_text())
    assert (destination / "catalog.json").read_bytes() == catalog_path.read_bytes()
    assert (destination / "verified-notes.json").read_bytes() == builder.NOTES_SOURCE.read_bytes()
    assert (destination / "ibm_discovery.py").read_bytes() == builder.COLLECTOR_SOURCE.read_bytes()
    assert not (destination / "inventory.json").exists()
    before = {p.name:p.read_bytes() for p in destination.iterdir()}
    builder.export_directory(destination, catalog_path)
    assert {p.name:p.read_bytes() for p in destination.iterdir()} == before
    catalog_path.write_text('{"schema_version":2,"products":{}}')
    builder.export_directory(destination, catalog_path)
    assert json.loads((destination / "catalog.json").read_text())["products"] == {}
    assert '"products":{}' in (destination / "IBM-Patchwatch.html").read_text()


def test_private_bundle_keeps_inventory_together_and_outside_public_output(tmp_path):
    inventory_path = tmp_path / "input.json"
    inventory_path.write_text(json.dumps({"schema_version":1,"host":{"hostname":"private-host"},"products":[]}))
    destination = tmp_path / "private-bundle"
    result = subprocess.run([sys.executable, str(BUILDER), "--inventory", str(inventory_path), "--output-dir", str(destination)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (destination / "inventory.json").read_bytes() == inventory_path.read_bytes()
    assert "private-host" in (destination / "IBM-Patchwatch.html").read_text()
    assert "Nicht in das öffentliche Repository" in (destination / "README.md").read_text()
    result = subprocess.run([sys.executable, str(BUILDER), "--inventory", str(inventory_path), "--output", str(builder.PUBLIC_DIRECTORY / "other.html")], capture_output=True, text=True)
    assert result.returncode == 2
    assert not (builder.PUBLIC_DIRECTORY / "other.html").exists()


def test_private_bundle_cannot_follow_symlinks_into_public_output(tmp_path, monkeypatch):
    import pytest
    public = tmp_path / "public"
    public.mkdir()
    monkeypatch.setattr(builder, "PUBLIC_DIRECTORY", public)
    target = public / "page.html"
    target.write_text("public data")
    destination = tmp_path / "private"
    destination.mkdir()
    (destination / "IBM-Patchwatch.html").symlink_to(target)
    inventory = tmp_path / "inventory.json"
    inventory.write_text('{"schema_version":1,"host":{},"products":[]}')
    with pytest.raises(ValueError, match="outside"):
        builder.export_directory(destination, builder.CATALOG_SOURCE, inventory)
    assert target.read_text() == "public data"
    assert not (destination / "inventory.json").exists()


def test_bundle_rejects_invalid_input_before_writing_output(tmp_path):
    import pytest
    source = tmp_path / "invalid.json"
    source.write_text('{"schema_version":99,"products":{}}')
    destination = tmp_path / "output"
    with pytest.raises(ValueError, match="schema_version"):
        builder.export_directory(destination, source)
    assert not destination.exists()
