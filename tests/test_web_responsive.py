"""Full rendered frontend QA at nine viewport widths, not just static CSS assertions.

Runs against a local Vite production preview. No calls to live websites or
BharatCode occur. The source project must already have been built.
"""
from __future__ import annotations
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
QA = ROOT / "scripts" / "check_web_ui.py"


@pytest.mark.skipif(
    not (WEB / "dist" / "index.html").exists(),
    reason="Run 'npm run build' in web/ to enable production-preview browser QA",
)
def test_production_frontend_at_nine_responsive_widths():
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        pytest.skip("npm not available")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}/"
    process = subprocess.Popen(
        [npm, "run", "preview", "--", "--host", "127.0.0.1",
         "--port", str(port), "--strictPort"],
        cwd=WEB,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    try:
        ready = False
        for _ in range(60):
            if process.poll() is not None:
                raise AssertionError("Vite preview terminated before serving the built frontend")
            try:
                with urllib.request.urlopen(url, timeout=1) as response:
                    ready = response.status == 200
                    if ready:
                        break
            except (OSError, urllib.error.URLError):
                time.sleep(0.25)
        assert ready, "Vite production preview never became available"
        checked = subprocess.run(
            [sys.executable, str(QA), "--url", url],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=150,
            check=False,
        )
        assert checked.returncode == 0, (
            "Rendered responsive QA failed:\n" +
            checked.stdout[-8000:] + "\n" + checked.stderr[-8000:]
        )
        assert "All 9 viewports passed." in checked.stdout
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
