"""Full rendered frontend QA at nine viewport widths, not just static CSS assertions.

Builds the current frontend for localhost before starting a Vite production
preview. No calls to live websites or BharatCode occur. Generated dist files
are refreshed; the source code and user edits are not changed.
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


def test_production_frontend_at_nine_responsive_widths():
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        pytest.skip("npm not available")
    if not (WEB / "node_modules").is_dir():
        pytest.skip("Frontend packages not installed; run 'npm install' in web/")
    # A previous 'npm run build:pages' writes /AksharaCheck/ asset paths
    # into dist/index.html. Vite preview at localhost / then returns HTML 200,
    # but its JS never mounts React, causing a misleading missing #hero-title.
    # Always build for the local '/' base before previewing. Also picks up
    # any uncommitted frontend fixes without changing their source files.
    build = subprocess.run(
        [npm, "run", "build"],
        cwd=WEB,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert build.returncode == 0, (
        "Local frontend build failed:\n"
        + build.stdout[-5000:] + "\n" + build.stderr[-5000:]
    )
    index = (WEB / "dist" / "index.html")
    assert index.is_file(), "The frontend build did not generate dist/index.html"
    html = index.read_text(encoding="utf-8")
    assert '/AksharaCheck/assets/' not in html, (
        "Local preview contains GitHub Pages asset paths; use 'npm run build' rather than 'npm run build:pages'"
    )
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
