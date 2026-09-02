"""Desktop launcher.

Starts the grader on a loopback port and opens it in the default browser. Used
as the PyInstaller entry point; `python3 desktop.py` also works for testing.
"""

from __future__ import annotations

import socket
import sys
import threading
import time
import webbrowser

from waitress import create_server

import app as grader

BANNER = r"""
  Canvas Discussion Grader
  ------------------------------------------------
  Running at {url}

  Your browser should have opened automatically.
  If not, paste that address into it.

  To quit: click Quit in the app, or close this window.
"""


def _free_port() -> int:
    """Ask the OS for an unused loopback port."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def main() -> int:
    port = _free_port()
    url = f"http://127.0.0.1:{port}/"

    # waitress rather than gunicorn: pure Python and, unlike gunicorn, it runs
    # on Windows. The Flask dev server is not meant for distribution.
    server = create_server(grader.app, host="127.0.0.1", port=port, threads=8)
    threading.Thread(target=server.run, daemon=True).start()

    # Give the socket a moment before pointing a browser at it.
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            time.sleep(0.1)

    print(BANNER.format(url=url), flush=True)
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001 - headless or no default browser
        pass

    try:
        # Blocks until the page calls /api/quit, or Ctrl-C / window close.
        while not grader.SHUTDOWN.wait(timeout=0.5):
            pass
    except KeyboardInterrupt:
        pass

    print("Shutting down...", flush=True)
    server.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
