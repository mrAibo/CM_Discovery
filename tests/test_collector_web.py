import importlib.util
import json
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "ibm_discovery", Path(__file__).parents[1] / "collectors" / "ibm_discovery.py"
)
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


def test_web_checker_serves_static_ui_and_inventory():
    snapshot = {
        "host": {"hostname": "cm<&>"},
        "products": [{"id": "websphere", "name": "IBM WAS <script>", "version": "9.0.5.25"}],
    }
    server = HTTPServer(("127.0.0.1", 0), collector.make_web_handler(snapshot))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = "http://127.0.0.1:{}".format(server.server_port)
    try:
        with urllib.request.urlopen(base + "/") as response:
            html = response.read().decode("utf-8")
            assert response.headers["Cache-Control"] == "no-store"
            assert "Content-Security-Policy" in response.headers
            assert '<script src="/app.js" defer></script>' in html
            assert "IBM WAS <script>" not in html
        with urllib.request.urlopen(base + "/app.js") as response:
            script = response.read().decode("utf-8")
            assert "manualTarget" in script
            assert "noopener,noreferrer" in script
            assert "https:" in script and "http:" in script
        with urllib.request.urlopen(base + "/inventory.json") as response:
            assert json.load(response) == snapshot
            assert response.headers["Cache-Control"] == "no-store"
        try:
            urllib.request.urlopen(base + "/missing")
            assert False, "unknown path must return 404"
        except urllib.error.HTTPError as error:
            assert error.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
