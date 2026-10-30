"""Offline engineering demo. No BharatCode model call occurs.

Run from the repo root:
  .venv\\Scripts\\python.exe scripts\\run_offline_demo.py

Starts only the bundled local test website, runs the real Chromium scanner,
tries a few fixed, deterministic sample repairs, verifies them in Chromium,
and exports an HTML/JSON/Markdown report. This is NOT an API substitute for
BharatCode Build League submission.
"""
import asyncio
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from aksharacheck.ai import verify_patch
from aksharacheck.browser import Scanner
from aksharacheck.report import write_reports

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/"fixtures"/"toota-akshar"
OUTPUT=ROOT/"output"/"offline-demo"

class FixtureHandler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(FIXTURE),**kwargs)
    def log_message(self,*args):
        pass


def local_repair(finding):
    """Explicitly human-authored demo rules, not generated model content."""
    detector=finding["detector"]
    if detector=="wrong-lang":
        script=(finding.get("evidence") or {}).get("script")
        return {"attributes":{"lang":"kn" if script=="kannada" else "hi"},
                "explanation":"Local demonstration: add the language attribute matching this text's script."}
    if detector=="possible-clipping":
        return {"css":{"height":"auto","min-height":"fit-content"},
                "explanation":"Local demonstration: let clipped text grow to its intrinsic height."}
    if detector=="mobile-overflow":
        return {"css":{"white-space":"normal","overflow-wrap":"anywhere"},
                "explanation":"Local demonstration: allow the line to break within long words on small screens."}
    if detector=="tight-line-height":
        return {"css":{"line-height":"1.6"},
                "explanation":"Local demonstration: increase line spacing for multi-line Indic text."}
    return None


async def run(base_url):
    report=await Scanner(output_dir=OUTPUT,allow_local=True,max_pages=1,timeout=60).scan(base_url+"/index.html")
    report["demo_mode"]=True
    report["ai_provider"]="none"
    report["demo_notice"]="Offline local-rule examples only. No BharatCode model was called."
    tested=0
    for finding in report["findings"]:
        proposal=local_repair(finding)
        if not proposal:
            finding["fix"]={"status":"not-applicable","reason":"No safe automatic repair is available for this issue."}
            continue
        if tested>=6:
            finding["fix"]={"status":"not-attempted","reason":"Offline demonstration limit reached."}
            continue
        tested+=1
        finding["ai_explanation"]=proposal["explanation"]
        finding["explanation_source"]="local-demo-rule"
        finding["fix"]=await verify_patch(finding,proposal,allow_local=True)
        finding["fix"]["source"]="local-demo-rule"
    write_reports(report,OUTPUT)
    return report,tested


def main():
    server=ThreadingHTTPServer(("127.0.0.1",0),FixtureHandler)
    thread=Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        data,attempts=asyncio.run(run(f"http://127.0.0.1:{server.server_port}"))
        print("OFFLINE DEVELOPMENT DEMO: No BharatCode API was contacted.")
        print("Browser detector summary:",data["summary"])
        print("Browser repair tests:",attempts)
        for finding in data["findings"]:
            if finding.get("fix") and finding["fix"].get("source")=="local-demo-rule":
                print(f"  {finding['detector']}: {finding['fix']['status']}")
        print("HTML report:",OUTPUT/"report.html")
        if attempts==0:
            raise RuntimeError("No applicable browser repairs were found in the bundled fixture.")
        print("PASS: Browser scan and local repair verification ran. Model API integration remains untested.")
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)


if __name__=="__main__":
    main()
