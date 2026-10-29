"""Minimal guarded background scan API; the UI can poll for progress."""
import asyncio
import os
import re
import time
import uuid
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .browser import Scanner
from .ai import explain_and_verify
from .report import write_reports
from .security import validate_url, UnsafeURL

ROOT=Path(os.getenv('AKSHARA_OUTPUT','output')).resolve()
ROOT.mkdir(parents=True,exist_ok=True)
app=FastAPI(title='AksharaCheck',version='0.1.0')
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('AKSHARA_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(','),allow_methods=['GET','POST'],allow_headers=['Content-Type'])
JOBS={}
ACTIVE_LIMIT=2
class ScanRequest(BaseModel):
    url:str=Field(min_length=10,max_length=2048)
    lang:str='both'
    use_ai:bool=False

async def run_scan(scan_id:str,request:ScanRequest):
    job=JOBS[scan_id]
    async def progress(message):
        job['events'].append(message)
    try:
        output=ROOT/scan_id
        data=await Scanner(output_dir=output,max_pages=1).scan(request.url,request.lang,progress)
        if request.use_ai and os.getenv('BHARATCODE_API_KEY'):
            await explain_and_verify(data,progress=progress,max_fixes=5)
        write_reports(data,output)
        job.update(status='complete',summary=data['summary'])
    except Exception as exc:
        job.update(status='error',error=str(exc)[:250])
    finally:job['ended']=time.time()

@app.get('/api/health')
def health():return {"ok":True,"name":"AksharaCheck","version":"0.1.0","ai_available":bool(os.getenv("BHARATCODE_API_KEY"))}

@app.post('/api/scans',status_code=202)
async def start(req:ScanRequest,request:Request):
    if req.lang not in {'both','hi','kn'}:raise HTTPException(400,'Invalid language')
    try:validate_url(req.url)
    except (UnsafeURL,ValueError) as exc:raise HTTPException(400,str(exc))
    if sum(j['status']=='running' for j in JOBS.values())>=ACTIVE_LIMIT:
        raise HTTPException(429,'Demo is busy; try again later')
    client=request.client.host if request.client else 'unknown'
    recent=[j for j in JOBS.values() if j['ip']==client and time.time()-j['created']<3600]
    if len(recent)>=5:raise HTTPException(429,'Limit: five scans per hour per visitor')
    scan_id=uuid.uuid4().hex[:16]
    JOBS[scan_id]={"status":"running","events":["Scan queued"],"created":time.time(),"ip":client}
    asyncio.create_task(run_scan(scan_id,req))
    return {"id":scan_id,"status":"running"}

@app.get('/api/scans/{scan_id}')
def status(scan_id:str):
    if not re.fullmatch(r'[0-9a-f]{16}',scan_id):raise HTTPException(404,'Unknown scan')
    job=JOBS.get(scan_id)
    if not job:raise HTTPException(404,'Unknown scan')
    return {k:v for k,v in job.items() if k not in {'ip'}}

@app.get('/api/scans/{scan_id}/report')
def report(scan_id:str):
    if not re.fullmatch(r'[0-9a-f]{16}',scan_id):raise HTTPException(404,'Unknown scan')
    path=ROOT/scan_id/'report.json'
    if not path.is_file():raise HTTPException(404,'Scan report not ready')
    return FileResponse(path,media_type='application/json')

@app.get('/api/scans/{scan_id}/artifacts/{name}')
def artifact(scan_id:str,name:str):
    if not re.fullmatch(r'[0-9a-f]{16}',scan_id):raise HTTPException(404,'Unknown scan')
    if '/' in name or '\\' in name or name not in {'report.html','report.md','report.json'} and not (name.startswith('page-') and name.endswith('.png')):
        raise HTTPException(400,'Invalid artifact')
    path=ROOT/scan_id/name
    if not path.is_file():raise HTTPException(404,'Artifact not found')
    return FileResponse(path)

WEB_DIST=Path(__file__).resolve().parents[1]/'web'/'dist'
if WEB_DIST.is_dir():app.mount('/',StaticFiles(directory=WEB_DIST,html=True),name='web')
