"""Capture the SOP's screenshots by driving the real app.

Figures are taken from the running UI rather than pasted in by hand, so they
cannot drift out of date. Run this, then tools/make_sop.py.

    python3 tools/capture_figures.py
"""

from __future__ import annotations

import asyncio
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "docs" / "figures"
DEMO_PORT, LIVE_PORT, MOCK_PORT = 5155, 5156, 5199


def _wait(port: int, timeout: float = 40) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return
        except OSError:
            time.sleep(0.3)
    raise RuntimeError(f"nothing came up on port {port}")


def _spawn(args: list[str], env: dict) -> subprocess.Popen:
    return subprocess.Popen(args, cwd=ROOT, env={**os.environ, **env},
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


async def capture() -> None:
    from playwright.async_api import async_playwright

    FIG.mkdir(parents=True, exist_ok=True)

    async def shot(page, selector: str, name: str) -> None:
        el = await page.query_selector(selector)
        await el.screenshot(path=str(FIG / f"{name}.png"))
        print("  captured", name)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": 1500, "height": 1100},
                                      device_scale_factor=2)

        # --- panels and results, against the demo backend --------------
        await page.goto(f"http://127.0.0.1:{DEMO_PORT}/")
        await page.wait_for_timeout(900)
        await shot(page, "#secConn", "fig_connect")

        await page.evaluate("""async () => {
            document.getElementById('canvasUrl').value='https://canvas.harvard.edu';
            document.getElementById('accessToken').value='demo-token';
            document.getElementById('courseId').value='288901';
            await connectCanvas();
        }""")
        await page.wait_for_timeout(1200)
        for sel, name in (("#secFilters", "fig_filters"), ("#secWeights", "fig_weights"),
                          ("#secScheme", "fig_scheme"), ("#secTopics", "fig_topics"),
                          ("#secStudents", "fig_students")):
            await shot(page, sel, name)

        await page.evaluate("runAnalysis()")
        await page.wait_for_selector("#resultsView:not(.hidden)", timeout=90000)
        await page.wait_for_timeout(2500)
        for sel, name in (("#statCards", "fig_cards"), ("#fileList", "fig_files"),
                          (".tbl-wrap", "fig_table")):
            await shot(page, sel, name)

        # --- the failure diagnostics need a NON-demo app -------------------
        # In demo mode every connection succeeds, so the 403 panel never renders.
        await page.goto(f"http://127.0.0.1:{LIVE_PORT}/")
        await page.wait_for_timeout(700)
        await page.evaluate(f"""async () => {{
            document.getElementById('canvasUrl').value='http://127.0.0.1:{MOCK_PORT}';
            document.getElementById('accessToken').value='faketoken';
            document.getElementById('courseId').value='999999';
            await connectCanvas();
        }}""")
        await page.wait_for_timeout(2500)
        text = await page.inner_text("#connDiag")
        if "token works" not in text:
            raise RuntimeError("diagnostics panel did not render; is the mock Canvas up?")
        await shot(page, "#secConn", "fig_diagnostics")

        await browser.close()


def capture_charts() -> None:
    """Pull the matplotlib figures straight from a demo run."""
    import json

    base = f"http://127.0.0.1:{DEMO_PORT}"

    def post(path, payload):
        req = urllib.request.Request(base + path, json.dumps(payload).encode(),
                                     {"Content-Type": "application/json"})
        return json.load(urllib.request.urlopen(req))

    meta = post("/api/validate", {"canvas_url": "x", "token": "y", "course_id": "1"})
    run = dict(course_id="1",
               included_topic_ids=[t["id"] for t in meta["topics"]],
               included_student_ids=[s["id"] for s in meta["students"]],
               grading_scheme=[])
    job = post("/api/run", run)["job_id"]
    while json.load(urllib.request.urlopen(f"{base}/api/status/{job}"))["status"] == "running":
        time.sleep(0.1)
    done = json.load(urllib.request.urlopen(f"{base}/api/status/{job}"))

    for name in done["files"]:
        if name.endswith(".png"):
            tag = "dist" if "analysis" in name else "comp"
            data = urllib.request.urlopen(f"{base}/api/download/{job}/{name}").read()
            (FIG / f"fig_chart_{tag}.png").write_bytes(data)
            print(f"  captured fig_chart_{tag}")

    # Same class, replies discounted, to show the grade bands tilting.
    weighted = post(f"/api/recompute/{job}", {**run, "beta_posts": 1, "beta_replies": 0.25})
    comp = next(f for f in weighted["files"] if "composition" in f)
    data = urllib.request.urlopen(f"{base}/api/download/{job}/{comp}").read()
    (FIG / "fig_chart_comp_weighted.png").write_bytes(data)
    print("  captured fig_chart_comp_weighted")


def main() -> int:
    procs = [
        _spawn([sys.executable, "app.py"], {"DEMO_MODE": "1", "PORT": str(DEMO_PORT)}),
        _spawn([sys.executable, "app.py"], {"PORT": str(LIVE_PORT), "DEMO_MODE": ""}),
        _spawn([sys.executable, "tools/mock_canvas.py"], {"MOCK_PORT": str(MOCK_PORT)}),
    ]
    try:
        for port in (DEMO_PORT, LIVE_PORT, MOCK_PORT):
            _wait(port)
        print("capturing figures ->", FIG)
        asyncio.run(capture())
        capture_charts()
        print("\nDone. Now run: python3 tools/make_sop.py")
        return 0
    finally:
        for p in procs:
            p.send_signal(signal.SIGTERM)


if __name__ == "__main__":
    sys.exit(main())
