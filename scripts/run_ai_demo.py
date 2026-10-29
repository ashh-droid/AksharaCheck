"""One-command local scanner plus real BharatCode AI demonstration.

Run: .venv\\Scripts\\python.exe scripts\\run_ai_demo.py
API key entry is hidden and stays in the current process. Reports go into
output/ai-demo. Only the bundled public, deliberately broken fixture is scanned.
"""
import asyncio
import os
from getpass import getpass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from aksharacheck.ai import explain_and_verify
from aksharacheck.browser import Scanner
from aksharacheck.report import write_reports

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/"fixtures"/"toota-akshar"
OUTPUT=ROOT/"output"/"ai-demo"

class QuietHandler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(FIXTURE),**kwargs)
    def log_message(self,*args):
        pass

async def test(url):
    report=await Scanner(OUTPUT,allow_local=True,max_pages=1).scan(url,lang="both")
    print("BROWSER SCAN:",report["summary"])
    if not report["findings"]:
        raise RuntimeError("Fixture unexpectedly produced no findings")
    print("Sending up to five browser findings to BharatCode for explanations and suggested repairs.")
    async def progress(msg):
        print(msg)
    await explain_and_verify(report,allow_local=True,max_fixes=5,progress=progress,output_dir=OUTPUT)
    write_reports(report,OUTPUT)
    checked=[f for f in report["findings"] if f.get("ai_explanation")]
    print("AI FINDINGS:",len(checked))
    for finding in checked:
        label=finding.get("fix") or {}
        print("  ",finding["detector"],"|",label.get("status","not attempted"))
    print("REPORT:",OUTPUT/"report.html")
    if not any(f.get("summary_hi") and f.get("summary_kn") for f in checked):
        raise RuntimeError("No bilingual AI explanation returned. See the report and API smoke test.")
    if not any(f.get("ai_explanation") for f in checked):
        raise RuntimeError("No valid BharatCode explanation returned.")
    print("PASS: real AI explanations were written to the report.")
    return report

def main():
    key=os.environ.get("BHARATCODE_API_KEY","").strip()
    if not key:
        try:key=getpass("BharatCode API key (typing hidden): ").strip()
        except (EOFError,KeyboardInterrupt):
            print("\\nCancelled without saving a key.");return 2
    if not key:
        print("No key supplied.");return 2
    os.environ["BHARATCODE_API_KEY"]=key
    server=ThreadingHTTPServer(("127.0.0.1",0),QuietHandler)
    worker=Thread(target=server.serve_forever,daemon=True)
    worker.start()
    try:
        url=f"http://127.0.0.1:{server.server_port}/index.html"
        asyncio.run(test(url))
        return 0
    except Exception as exc:
        print("DEMO FAILED:",type(exc).__name__,str(exc)[:200].replace(key,"[REDACTED]"))
        return 2
    finally:
        server.shutdown();server.server_close();worker.join(timeout=3)
        os.environ.pop("BHARATCODE_API_KEY",None)

if __name__=="__main__":
    raise SystemExit(main())
