import os
"""End-to-end fixture checks. No external websites or credentials are used."""
import asyncio
import sys
from pathlib import Path
from threading import Thread
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

import pytest
from playwright.async_api import async_playwright
from aksharacheck.browser import Scanner

FIXTURE=Path(__file__).resolve().parents[1]/"fixtures"/"toota-akshar"


@pytest.fixture(scope="module")
def fixture_url():
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,directory=str(FIXTURE),**kwargs)
        def log_message(self,*args):
            pass
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    worker=Thread(target=server.serve_forever,daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


@pytest.fixture(scope="module")
def chromium_available():
    # Test actual executable launch, not the Unix-only Playwright cache path.
    async def probe():
        async with async_playwright() as p:
            try:
                options={"headless":True}
                # Same launch options as the scanner, so CI and custom installs are not skipped.
                if os.getenv("AKSHARA_CHROMIUM_PATH"):
                    options["executable_path"]=os.environ["AKSHARA_CHROMIUM_PATH"]
                browser=await p.chromium.launch(**options)
            except Exception as exc:
                pytest.skip(f"Chromium launch unavailable: {type(exc).__name__}: {str(exc)[:100]}")
            else:
                await browser.close()
    asyncio.run(probe())
    return True


@pytest.mark.asyncio
async def test_broken_page_reports_expected_categories(tmp_path,fixture_url,chromium_available):
    result=await Scanner(output_dir=tmp_path,allow_local=True,timeout=60).scan(f"{fixture_url}/index.html")
    kinds={f["detector"] for f in result["findings"]}
    for detector in ("broken-cluster","wrong-lang","possible-clipping","mobile-overflow"):
        assert detector in kinds,f"{detector} was not found; actual categories: {sorted(kinds)}"
    assert (tmp_path/"page-01-390.png").is_file()
    assert (tmp_path/"page-01-1440.png").is_file()
    assert result["summary"]["error"]>0
    assert len({f["id"] for f in result["findings"]})==len(result["findings"])
    assert any(len(f.get("viewports",[]))>1 for f in result["findings"])


@pytest.mark.asyncio
async def test_clean_page_has_no_errors_or_warnings(tmp_path,fixture_url,chromium_available):
    result=await Scanner(output_dir=tmp_path,allow_local=True,timeout=60).scan(f"{fixture_url}/clean.html")
    serious=[f for f in result["findings"] if f["severity"] in {"error","warning"}]
    assert not serious,[(f["detector"],f["sample"][:80]) for f in serious]
    assert (tmp_path/"report.json").is_file()
