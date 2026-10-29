import pytest
import httpx
from aksharacheck.api import app, WEB_DIST

@pytest.mark.asyncio
async def test_api_health_and_frontend():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://testserver') as client:
        r=await client.get('/api/health');assert r.status_code==200
        assert r.json()['name']=='AksharaCheck'
        page=await client.get('/')
        if WEB_DIST.is_dir():
            assert page.status_code==200
            assert 'AksharaCheck' in page.text
            assert '<div id="root"></div>' in page.text
        else:
            # Fresh clones contain React source, not generated Vite dist files.
            assert page.status_code==404

@pytest.mark.asyncio
async def test_api_rejects_internal_target():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://testserver') as client:
        r=await client.post('/api/scans',json={'url':'http://127.0.0.1:8000','lang':'hi'})
        assert r.status_code==400

@pytest.mark.asyncio
async def test_api_rejects_bad_artifact_id():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://testserver') as client:
        r=await client.get('/api/scans/../../artifacts/report.json')
        assert r.status_code in (400,404)
