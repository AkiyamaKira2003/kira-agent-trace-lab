"""Optional, local-only Chrome visual QA for the fictional policy contrast.

Run from a Git checkout with Chrome and optional Python websockets installed:
    python scripts/qa_offline_policy_demo.py

No browser extension, user tab, mouse or keyboard is touched. All generated
screenshots and evidence are excluded from the installable wheel and sdist.
This is one-browser visual QA, not independent security validation.
"""
import argparse
import asyncio
import base64
import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from threading import Thread
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
QA_PARENT = ROOT / "artifacts" / "browser-visual-qa"
OUT: Path | None = None
URL = ""
VIEWPORTS = [(1600, 900), (375, 812), (320, 700)]


class DemoOnlyHandler(BaseHTTPRequestHandler):
    """Serve one public synthetic HTML document, never repository files."""

    def do_GET(self) -> None:
        if self.path != "/docs/policy-contrast-research-demo.html":
            self.send_error(404)
            return
        data = (ROOT / "docs" / "policy-contrast-research-demo.html").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        # Avoid printing potentially sensitive local URLs into CI logs.
        return


def validate_layout(result: dict, width: int, height: int) -> None:
    """Pure fail-closed real-DOM contract; independently unit-testable."""
    expected = {
        "total_cases": 1, "changed": 1, "allow_to_deny": 1,
        "deny_to_allow": 0, "unchanged": 0,
        "candidate_ignored_grant_cases": 0,
    }
    if result.get("viewport") != width or result.get("viewportHeight") != height:
        raise ValueError("Chrome viewport size does not match requested QA")
    if result.get("contentWidth", width + 1) > result.get("clientWidth", 0):
        raise ValueError("Demo has horizontal overflow")
    if result.get("anyScripts") != 0 or result.get("externalResources"):
        raise ValueError("Demo loaded active or external resources")
    warning = result.get("warning")
    if not isinstance(warning, str) or not all(
        value in warning for value in (
            "Synthetic-only evidence", "not an authenticated record",
            "No tool actions are executed",
        )
    ):
        raise ValueError("Visible research-only disclaimer is incomplete")
    if result.get("metrics") != expected or result.get("progress") != {"value": 1, "max": 1}:
        raise ValueError("Fictional aggregate counts differ from verified fixture")
    if result.get("verdictColors") != [
        "rgb(126, 232, 183)", "rgb(255, 207, 135)",
    ]:
        raise ValueError("Allow/Deny verdict colors were overridden")
    cards = result.get("cards")
    if not isinstance(cards, list) or len(cards) != 2:
        raise ValueError("Demo card layout is invalid")
    if width < 600:
        if cards[1]["y"] < cards[0]["bottom"] - 1:
            raise ValueError("Mobile decision cards overlap")
    elif abs(cards[0]["y"] - cards[1]["y"]) >= 2:
        raise ValueError("Desktop decision cards are not aligned")


async def inspect(ws, width, height, serial):
    async def cmd(method, params=None):
        nonlocal serial
        serial += 1
        request_id = serial
        await ws.send(json.dumps({"id": request_id, "method": method, "params": params or {}}))
        for _ in range(80):
            incoming = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if incoming.get("id") != request_id:
                continue
            if "error" in incoming:
                raise RuntimeError(f"CDP {method}: {incoming['error']}")
            return incoming.get("result", {}), serial
        raise RuntimeError(f"CDP {method} did not respond")

    _, serial = await cmd("Emulation.setDeviceMetricsOverride", {
        "width": width, "height": height, "deviceScaleFactor": 1, "mobile": width < 600,
    })
    _, serial = await cmd("Page.navigate", {"url": URL})
    for _ in range(35):
        ready, serial = await cmd("Runtime.evaluate", {
            "expression": "document.readyState === 'complete' && location.href.includes('policy-contrast-research-demo.html')",
            "returnByValue": True,
        })
        if ready.get("result", {}).get("value") is True:
            break
        await asyncio.sleep(0.15)
    else:
        raise RuntimeError("Local page did not reach readyState=complete")
    expression = r"""(() => {
        const rect = (x) => {
            const r = x.getBoundingClientRect();
            return {x:r.x,y:r.y,w:r.width,h:r.height,bottom:r.bottom};
        };
        const cards=[...document.querySelectorAll(".card")].map(rect);
        const warning=document.querySelector(".notice");
        const metrics=Object.fromEntries([...document.querySelectorAll("data[data-key]")]
          .map(x=>[x.dataset.key, Number(x.value)]));
        const verdictColors=[...document.querySelectorAll(".card p.verdict")]
          .map(x=>getComputedStyle(x).color);
        const content = document.documentElement;
        return {
          title:document.title,viewport:innerWidth,viewportHeight:innerHeight,
          contentWidth:content.scrollWidth,clientWidth:content.clientWidth,
          contentHeight:content.scrollHeight,warning:warning?.innerText,
          warningBox:warning?rect(warning):null,cards,
          gridTemplate:getComputedStyle(document.querySelector(".grid")).gridTemplateColumns,
          metrics,verdictColors,
          progress:{value:document.querySelector("progress").value,max:document.querySelector("progress").max},
          externalResources:performance.getEntriesByType("resource").map(x=>x.name).filter(x=>!x.startsWith(location.origin + "/")),
          anyScripts:document.scripts.length,
          h1:document.querySelector("h1")?.innerText,
          footer:document.querySelector("footer")?.innerText
        };
    })()"""
    res, serial = await cmd("Runtime.evaluate", {
        "expression": expression, "returnByValue": True, "awaitPromise": False,
    })
    if res.get("exceptionDetails"):
        detail = res["exceptionDetails"]
        raise RuntimeError(f"Browser evaluation threw: {detail.get('text')} {detail.get('exception',{}).get('description', '')[:300]}")
    result = res["result"]["value"]
    validate_layout(result, width, height)
    shot, serial = await cmd("Page.captureScreenshot", {
        "format": "png", "fromSurface": True, "captureBeyondViewport": False,
    })
    pixels = base64.b64decode(shot["data"])
    if (len(pixels) < 10_000 or pixels[:8] != b"\x89PNG\r\n\x1a\n"
            or pixels[12:16] != b"IHDR"
            or int.from_bytes(pixels[16:20], "big") != width
            or int.from_bytes(pixels[20:24], "big") != height):
        raise ValueError("Chrome returned invalid or incorrect viewport screenshot")
    if OUT is None:
        raise RuntimeError("Screenshot output directory is not initialized")
    filename = OUT / f"demo_{width}x{height}.png"
    filename.write_bytes(pixels)
    result["screenshot_file"] = filename.name
    result["screenshot_sha256"] = hashlib.sha256(pixels).hexdigest()
    result["screenshot_bytes"] = len(pixels)
    return result, serial


async def execute(chrome: Path, connect) -> None:
    global URL, OUT
    if not chrome.is_file() or ROOT.name != "kira-agent-trace-lab":
        raise ValueError("Wrong browser or project root")
    QA_PARENT.mkdir(parents=True, exist_ok=True)
    if not QA_PARENT.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Visual QA output parent is outside the project")
    # Every invocation has its own evidence directory; a failed attempt
    # cannot leave a stale success JSON at the path of a future run.
    OUT = Path(tempfile.mkdtemp(prefix="run-", dir=QA_PARENT))
    if not OUT.resolve().is_relative_to(QA_PARENT.resolve()):
        raise ValueError("Visual QA output escaped its approved parent")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), DemoOnlyHandler)
    server_thread = Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    URL = f"http://127.0.0.1:{httpd.server_port}/docs/policy-contrast-research-demo.html"
    profile: Path | None = None
    proc = None
    try:
        # Exactly one ephemeral Chrome process/profile; no desktop input.
        profile = Path(tempfile.mkdtemp(prefix="visual-qa-profile-", dir=OUT))
        if not profile.resolve().is_relative_to(OUT.resolve()):
            raise ValueError("Chrome profile escaped the approved QA directory")
        flags = [
            str(chrome), "--headless=new", "--disable-gpu",
            "--disable-extensions", "--disable-background-networking",
            "--no-first-run", "--no-default-browser-check", "--no-proxy-server",
            "--remote-debugging-port=0", f"--user-data-dir={profile}",
            "--window-size=1600,900", "about:blank",
        ]
        proc = subprocess.Popen(
            flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        active = profile / "DevToolsActivePort"
        for _ in range(100):
            if active.is_file():
                break
            if proc.poll() is not None:
                raise RuntimeError("Chrome headless exited before CDP became ready")
            await asyncio.sleep(0.1)
        if not active.is_file():
            raise RuntimeError("Chrome CDP did not start")
        port = int(active.read_text(encoding="utf-8").splitlines()[0])
        with urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as response:
            tabs = json.load(response)
        tab = next(t for t in tabs if t["type"] == "page")
        async with connect(tab["webSocketDebuggerUrl"], max_size=16_000_000) as ws:
            serial = 0
            for method in ("Page.enable", "Runtime.enable"):
                serial += 1
                await ws.send(json.dumps({"id": serial, "method": method}))
                while True:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                    if msg.get("id") == serial:
                        if "error" in msg:
                            raise RuntimeError(str(msg["error"]))
                        break
            results = []
            for width, height in VIEWPORTS:
                result, serial = await inspect(ws, width, height, serial)
                results.append(result)
            serial += 1
            await ws.send(json.dumps({"id": serial, "method": "Browser.close"}))
        evidence = {
            "status": "LOCAL_REAL_CHROME_HEADLESS_PIXEL_QA_PASS",
            "source": URL,
            "viewports": results,
            "limitations": "Single locally installed Chrome; not independent cross-browser testing or security certification",
        }
        (OUT / "qa_evidence.json").write_text(
            json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({
            "status": evidence["status"],
            "viewports": [
                {
                    "size": f"{r['viewport']}x{r['viewportHeight']}",
                    "contentWidth": r["contentWidth"],
                    "gridTemplate": r["gridTemplate"],
                    "verdictColors": r["verdictColors"],
                    "screenshot": r["screenshot_file"],
                    "sha256": r["screenshot_sha256"],
                } for r in results
            ],
            "evidence": str(OUT / "qa_evidence.json"),
        }, indent=2))
    finally:
        try:
            if proc is not None:
                try:
                    proc.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    proc.terminate()
                    proc.wait(timeout=4)
        finally:
            httpd.shutdown()
            httpd.server_close()
            server_thread.join(timeout=3)
            if profile is not None and profile.exists():
                if not profile.resolve().is_relative_to(OUT.resolve()):
                    raise ValueError("Unsafe Chrome profile cleanup path")
                shutil.rmtree(profile)


def _find_chrome(selected: Path | None) -> Path | None:
    if selected is not None:
        return selected if selected.is_file() else None
    candidates = (
        Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
    )
    for path in candidates:
        if path.is_file():
            return path
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chrome"):
        executable = shutil.which(name)
        if executable:
            return Path(executable)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--chrome", type=Path, help="path to an installed Chrome executable (auto-detect by default)",
    )
    args = parser.parse_args(argv)
    chrome = _find_chrome(args.chrome)
    if chrome is None:
        print(json.dumps({"status": "NOT_VERIFIED", "error_type": "ChromeNotFound"}))
        return 2
    try:
        # Optional dev-only dependency, deliberately not part of runtime
        # wheel/sdist or required just to display this script's --help.
        from websockets.asyncio.client import connect
    except ImportError:
        print(json.dumps({"status": "NOT_VERIFIED", "error_type": "WebsocketsNotInstalled"}))
        return 2
    try:
        asyncio.run(execute(chrome, connect))
    except Exception as exc:
        # Do not echo private local paths, source values or CDP exceptions.
        print(json.dumps({"status": "NOT_VERIFIED", "error_type": type(exc).__name__}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
