import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
import pytest
from aksharacheck.browser import Scanner

@pytest.mark.asyncio
async def test_fixture_can_scan(tmp_path):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        if not os.getenv('AKSHARA_CHROMIUM_PATH') and not (Path.home()/'.cache/ms-playwright').exists():
            pytest.skip('Chromium not installed')
    fixture=Path(__file__).parents[1]/'fixtures'/'toota-akshar'
    server=subprocess.Popen([sys.executable,'-m','http.server','18767','--bind','127.0.0.1','--directory',str(fixture)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        time.sleep(.5)
        result=await Scanner(output_dir=tmp_path,allow_local=True,timeout=45).scan('http://127.0.0.1:18767/index.html')
        kinds={f['detector'] for f in result['findings']}
        assert 'wrong-lang' in kinds
        assert 'broken-cluster' in kinds
        assert 'possible-clipping' in kinds
        assert 'mobile-overflow' in kinds
        assert (tmp_path/'page-01-390.png').exists()
    finally:server.terminate();server.wait(timeout=3)
