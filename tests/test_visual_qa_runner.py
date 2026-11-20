"""ATL-004AQ: deterministic browser-QA contracts without requiring Chrome in CI."""

from __future__ import annotations

import copy
from http.server import ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen
import unittest

from scripts.qa_offline_policy_demo import DemoOnlyHandler, validate_layout


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "qa_offline_policy_demo.py"


def sample_mobile() -> dict:
    return {
        "viewport": 375, "viewportHeight": 812,
        "contentWidth": 375, "clientWidth": 375,
        "anyScripts": 0, "externalResources": [],
        "warning": (
            "Synthetic-only evidence. This is not an authenticated record. "
            "No tool actions are executed."
        ),
        "metrics": {
            "total_cases": 1, "changed": 1, "allow_to_deny": 1,
            "deny_to_allow": 0, "unchanged": 0,
            "candidate_ignored_grant_cases": 0,
        },
        "progress": {"value": 1, "max": 1},
        "verdictColors": ["rgb(126, 232, 183)", "rgb(255, 207, 135)"],
        "cards": [{"y": 100, "bottom": 200}, {"y": 220, "bottom": 320}],
    }


class BrowserVisualQaContractTests(unittest.TestCase):
    def test_valid_375_320_and_1600_layouts(self):
        mobile = sample_mobile()
        validate_layout(mobile, 375, 812)
        small = copy.deepcopy(mobile)
        small.update({"viewport": 320, "viewportHeight": 700,
                      "contentWidth": 320, "clientWidth": 320})
        validate_layout(small, 320, 700)
        desktop = copy.deepcopy(mobile)
        desktop.update({"viewport": 1600, "viewportHeight": 900,
                        "contentWidth": 1585, "clientWidth": 1585,
                        "cards": [{"y": 100, "bottom": 220},
                                  {"y": 100, "bottom": 240}]})
        validate_layout(desktop, 1600, 900)

    def test_fails_closed_on_privacy_and_visual_regressions(self):
        bad_changes = (
            ("horizontal overflow", {"contentWidth": 376}),
            ("external resource", {"externalResources": ["https://external.invalid/pixel"]}),
            ("script", {"anyScripts": 1}),
            ("disclaimer", {"warning": "Synthetic-only evidence only"}),
            ("wrong counts", {"metrics": {"total_cases": 1}}),
            ("wrong progress", {"progress": {"value": 0, "max": 1}}),
            ("wrong colors", {"verdictColors": ["rgb(195, 210, 231)"] * 2}),
            ("overlapping cards", {"cards": [{"y": 100, "bottom": 200},
                                            {"y": 170, "bottom": 300}]}),
            ("wrong viewport", {"viewport": 1600}),
        )
        for label, changes in bad_changes:
            with self.subTest(label=label):
                data = sample_mobile()
                data.update(changes)
                with self.assertRaises(ValueError):
                    validate_layout(data, 375, 812)

    def test_local_http_handler_never_serves_repository_files(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), DemoOnlyHandler)
        server_thread = Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(url + "/docs/policy-contrast-research-demo.html", timeout=5) as res:
                self.assertEqual(res.status, 200)
                self.assertIn(b"Synthetic-only evidence", res.read())
            for route in ("/README.md", "/project.state.json", "/artifacts/",
                          "/docs/images/policy-contrast-qa-1600.png", "/"):
                with self.subTest(route=route):
                    with self.assertRaises(HTTPError) as err:
                        urlopen(url + route, timeout=5)
                    self.assertEqual(err.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=3)

    def test_help_does_not_import_optional_websocket_dependency(self):
        process = subprocess.run(
            [sys.executable, "-I", str(RUNNER), "--help"],
            text=True, capture_output=True, timeout=12,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("--chrome", process.stdout)
        self.assertIn("optional Python websockets", process.stdout)

    def test_missing_chrome_reports_not_verified_without_starting_server(self):
        process = subprocess.run(
            [sys.executable, "-I", str(RUNNER),
             "--chrome", str(ROOT / "nonexistent_qa_chrome.exe")],
            text=True, capture_output=True, timeout=12,
        )
        self.assertEqual(process.returncode, 2)
        self.assertIn('"status": "NOT_VERIFIED"', process.stdout)
        self.assertIn('"error_type": "ChromeNotFound"', process.stdout)
        self.assertNotIn(str(ROOT), process.stdout + process.stderr)


if __name__ == "__main__":
    unittest.main()
