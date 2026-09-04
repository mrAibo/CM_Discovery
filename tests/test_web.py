import base64
import json
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from ibm_patchwatch.cli import build_parser
import pytest

from ibm_patchwatch.web import DEFAULT_CATALOG_URL, JS_TEMPLATE, make_handler


def _request(url: str, authenticated: bool = False):
    request = urllib.request.Request(url)
    if authenticated:
        token = base64.b64encode(b"admin:admin").decode("ascii")
        request.add_header("Authorization", f"Basic {token}")
    return urllib.request.urlopen(request)


def test_central_web_checker_requires_auth_and_serves_inventory():
    inventory = {
        "timestamp": "2026-09-04T08:00:00Z",
        "host": {"hostname": "cm<&>"},
        "products": [{"id": "websphere", "name": "IBM WAS <script>", "version": "9.0.5.25"}],
    }
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(inventory, "admin", "admin"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        try:
            _request(base + "/")
            assert False, "unauthenticated request must fail"
        except urllib.error.HTTPError as error:
            assert error.code == 401
            assert error.headers["WWW-Authenticate"] == 'Basic realm="IBM Update Checker"'

        with _request(base + "/", True) as response:
            html = response.read().decode()
            assert "IBM WAS <script>" not in html
            assert response.headers["X-Frame-Options"] == "DENY"
            assert response.headers["Referrer-Policy"] == "no-referrer"

        with _request(base + "/inventory.json", True) as response:
            assert json.load(response) == inventory
            assert response.headers["Cache-Control"] == "no-store"

        with _request(base + "/styles.css", True) as response:
            assert response.headers["Content-Type"] == "text/css; charset=utf-8"
            assert b"@media" in response.read()

        with _request(base + "/app.js", True) as response:
            script = response.read().decode()
            assert DEFAULT_CATALOG_URL in script
            for status in (
                "CURRENT",
                "UPDATE_AVAILABLE",
                "NEWER_THAN_CATALOG",
                "CHECK_REQUIRED",
                "NOT_SUPPORTED",
            ):
                assert status in script
            assert 'id==="db2"' in script
            assert 'return "CHECK_REQUIRED"' in script

        try:
            _request(base + "/missing", True)
            assert False, "unknown path must return 404"
        except urllib.error.HTTPError as error:
            assert error.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_serve_cli_defaults_to_localhost():
    args = build_parser().parse_args(["serve", "cmtest"])
    assert args.host == "cmtest"
    assert args.bind == "127.0.0.1"
    assert args.port == 8765


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is only needed for the browser-logic self-check")
def test_browser_comparison_is_fail_closed():
    cases = r'''
const cases=[
 [compare("websphere",{version:"9.0.5.25"},{available:{version:"9.0.5.28"}}),"UPDATE_AVAILABLE"],
 [compare("websphere",{version:"9.0.5.29"},{available:{version:"9.0.5.28"}}),"NEWER_THAN_CATALOG"],
 [compare("content_navigator",{version:"3.1.0",build_level:"icn310.006.430"},{available:{version:"3.1.0",interim_fix:12}}),"UPDATE_AVAILABLE"],
 [compare("content_navigator",{version:"3.2.0",build_level:"icn320.001.1"},{available:{version:"3.1.0",interim_fix:12}}),"NEWER_THAN_CATALOG"],
 [compare("daeja_viewone_virtual",{version:"5.0.15"},{available:{version:"5.0.15",interim_fix:6}}),"CHECK_REQUIRED"],
 [compare("db2",{special_build:"special_87984"},{available:{version:"11.5.9.0",special_build:"special_87984"}}),"CHECK_REQUIRED"],
 [compare("db2",{version:"11.5.9.0",special_build:"special_63280"},{available:{version:"11.5.9.0",special_build:"special_87984"}}),"CHECK_REQUIRED"],
 [compare("db2",{version:"11.5.9.0",special_build:"special_87984"},{available:{version:"11.5.9.0",special_build:"special_87984"}}),"CURRENT"],
 [compare("iccsap",{version:"3.0",installed_fixes:["JRE_fix_20260812"]},{available:{version:"4.0.0.4",jre_fix_date:"20260812"}}),"UPDATE_AVAILABLE"]
];
if(cases.some(([actual,expected])=>actual!==expected)){console.error(cases);process.exit(1)}
'''
    script = JS_TEMPLATE.replace("__CATALOG_URL__", json.dumps(DEFAULT_CATALOG_URL)).split("Promise.all", 1)[0] + cases
    completed = subprocess.run(["node"], input=script, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
