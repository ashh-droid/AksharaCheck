"""One-command local scanner plus real BharatCode AI demonstration.

Run: .venv\\Scripts\\python.exe scripts\\run_ai_demo.py
API key entry is hidden and stays in the current process. Successful reports
go into output/ai-demo. A failed request will not replace an earlier report.
The demo always makes fresh model requests (no AI response cache).
Only the bundled public, deliberately broken fixture is scanned.
"""
import argparse
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

async def test(url,max_findings=1):
    report=await Scanner(OUTPUT,allow_local=True,max_pages=1).scan(url,lang="both")
    print("BROWSER SCAN:",report["summary"])
    if not report["findings"]:
        raise RuntimeError("Fixture unexpectedly produced no findings")
    print(f"Sending up to {max_findings} browser finding(s) to BharatCode for an explanation and a potential repair.")
    async def progress(msg):
        print(msg)
    # Never use a cached response as evidence of CURRENT model access.
    await explain_and_verify(report,allow_local=True,max_fixes=max_findings,
                             progress=progress,output_dir=OUTPUT,use_cache=False)
    checked=[f for f in report["findings"] if f.get("ai_explanation")]
    print("AI FINDINGS:",len(checked))
    for finding in report["findings"]:
        label=finding.get("fix") or {}
        if label:
            print("  ",finding["detector"],"|",label.get("status","not attempted"))
            if label.get("status")=="unavailable":
                print("  DIAGNOSTIC:",label.get("reason","Unknown model error"))
    unavailable=next(((f.get("fix") or {}).get("reason") for f in report["findings"]
                       if (f.get("fix") or {}).get("status")=="unavailable"),None)
    if unavailable:
        raise RuntimeError("AI demo stopped without replacing your prior report: "+unavailable)
    if not checked or not any(f.get("summary_hi") and f.get("summary_kn") for f in checked):
        raise RuntimeError("No complete bilingual AI explanation returned; previous report preserved.")
    # Only publish the HTML/JSON/Markdown once the requested AI run succeeded.
    write_reports(report,OUTPUT)
    print("REPORT:",OUTPUT/"report.html")
    print("PASS: live BharatCode explanations were written to the report.")
    return report

def main():
    parser=argparse.ArgumentParser(description="Run a real BharatCode-to-Chromium demonstration")
    parser.add_argument("--max-findings",type=int,choices=range(1,6),default=1,
                        help="Number of browser findings to send (default 1; full demo 5)")
    args=parser.parse_args()
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
        asyncio.run(test(url,max_findings=args.max_findings))
        return 0
    except Exception as exc:
        print("DEMO FAILED:",type(exc).__name__,str(exc)[:200].replace(key,"[REDACTED]"))
        return 2
    finally:
        server.shutdown();server.server_close();worker.join(timeout=3)
        os.environ.pop("BHARATCODE_API_KEY",None)

if __name__=="__main__":
    raise SystemExit(main())
