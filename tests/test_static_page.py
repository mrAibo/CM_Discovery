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
    assert "outside the tracked public HTML" in completed.stderr
