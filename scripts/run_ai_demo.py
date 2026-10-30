"""Local, resumable BharatCode demo with browser-verified repairs.

Run: .venv\\Scripts\\python.exe scripts\\run_ai_demo.py --max-findings 5
A real API key is prompted for without echoing; credentials are never saved.
Verified progress is checkpointed after each finding and rechecked in Chromium
on a later run. Existing reports and screenshot assets are published only
after the full requested run succeeds.
"""
import argparse
import asyncio
import hashlib
import json
import os
import shutil
import tempfile
from getpass import getpass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from aksharacheck.ai import MODEL, PATCHABLE, explain_and_verify, verify_patch
from aksharacheck.browser import Scanner
from aksharacheck.report import write_reports

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/"fixtures"/"toota-akshar"
OUTPUT=ROOT/"output"/"ai-demo"
CHECKPOINT_NAME=".ai-progress.json"
# The only ai.py changes between these two builds are API retries and
# diagnostics. Keep that one prior checkpoint compatible without disabling
# normal code/fixture invalidation for future releases.
PRE_RETRY_AI_SHA256="ae6908ce695075861fe7119e8e76c1245cdbb61915019a2dff434657c4af2dc4"
RETRY_AI_SHA256="eb387e13255139690d8d589c6208abaaa5b596bc836bd0c5e8a1b46456521fff"
PRE_RETRY_AI_CRLF_SHA256="6b6b83979815672660f3b1340e2e7e9e337442f30fcfb4d35b9c2fcbe5afccf1"
RETRY_AI_CRLF_SHA256="b848bd47dd422ca7b7e6de1d04bc7647f3d24eab8c3abfdd10178bbd48057897"

class QuietHandler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(FIXTURE),**kwargs)
    def log_message(self,*args):
        pass


def scope_hash(*, previous_client=False):
    """Invalidate changed semantics; allow only the known retry-only ai.py update."""
    digest=hashlib.sha256()
    sources=[ROOT/"aksharacheck"/name for name in ("ai.py","browser.py","detectors.py")]
    sources += sorted(p for p in FIXTURE.rglob("*") if p.is_file())
    for p in sources:
        digest.update(str(p.relative_to(ROOT)).encode("utf-8"))
        file_digest=hashlib.sha256(p.read_bytes()).digest()
        if previous_client and p==ROOT/"aksharacheck"/"ai.py":
            # Do not accept old checkpoints if ai.py changes again.
            known={RETRY_AI_SHA256:PRE_RETRY_AI_SHA256,
                   RETRY_AI_CRLF_SHA256:PRE_RETRY_AI_CRLF_SHA256}
            previous_digest=known.get(file_digest.hex())
            if not previous_digest:
                return None
            file_digest=bytes.fromhex(previous_digest)
        digest.update(file_digest)
    return digest.hexdigest()


def identity(finding):
    """Stable for a fresh scan even when the local fixture server port changes."""
    keys=("detector","severity","selector","sample","viewport")
    payload=[finding.get(k) for k in keys]
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False,
                                    sort_keys=True).encode("utf-8")).hexdigest()


def read_checkpoint(path, scope):
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
        if (isinstance(data,dict) and data.get("version")==1
                and data.get("scope")==scope and data.get("model")==MODEL
                and isinstance(data.get("findings"),dict)):
            return data
    except (OSError,ValueError,TypeError):
        pass
    return {"version":1,"scope":scope,"model":MODEL,"findings":{}}


def save_checkpoint(path, data):
    """Write only public fixture explanations/repairs, never auth headers or keys."""
    path.parent.mkdir(parents=True,exist_ok=True)
    staging=path.with_suffix(".writing")
    staging.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    staging.replace(path)


async def restore_findings(report, checkpoint, stage, *, progress):
    chosen=[f for f in report["findings"] if f.get("severity")!="info"]
    chosen.sort(key=lambda f: (0 if f.get("detector") in PATCHABLE else 1))
    restored=0
    for f in chosen:
        prior=checkpoint["findings"].get(identity(f))
        if not isinstance(prior,dict):
            continue
        if not all(isinstance(prior.get(k),str) and prior[k].strip()
                   for k in ("ai_explanation","summary_hi","summary_kn")):
            continue
        fix=prior.get("fix")
        if not isinstance(fix,dict):
            continue
        status=fix.get("status")
        if status=="verified":
            # A fresh Chromium verification ensures a previous successful
            # result is not reused if the page or finding has changed.
            if f.get("detector") not in PATCHABLE:
                continue
            after=stage/f"element-{f['id']}-{f['viewport']}-fixed.png"
            new_fix=await verify_patch(f,fix,allow_local=True,after_shot=after)
            if new_fix.get("status")!="verified":
                await progress(f"Saved repair for {f['detector']} no longer passes; requesting fresh AI")
                continue
            new_fix["attempts"]=fix.get("attempts") or []
            fix=new_fix
        elif status not in {"not-applicable","unverified"}:
            continue
        # Never copy the prior finding ID, URL, element screenshot, or bounds.
        f.update(ai_explanation=prior["ai_explanation"],
                 summary_hi=prior["summary_hi"],
                 summary_kn=prior["summary_kn"],
                 fix=fix,ai_resumed=True)
        restored+=1
    return restored


def explain_provider_failure(reason):
    """Help users distinguish a provider-ended stream from a failed browser fix.

    This is guidance only; it never invents an error code or a successful model
    output. A provider response.failed may mean shared-capacity contention.
    """
    if reason.startswith("BharatCode response failed"):
        return ("BharatCode ended an already-started model stream (response.failed). "
                "Its documentation lists this as a possible busy-capacity outcome. "
                "The exact provider reason is not available from this diagnostic; "
                "no incomplete output was accepted. "+reason)
    return reason


def publish_report(stage, dest):
    """Do not overwrite previously successful outputs until rendering succeeds."""
    dest.mkdir(parents=True,exist_ok=True)
    files=[p for p in stage.iterdir() if p.is_file()]
    # Transfer images and fonts first; publish HTML, JSON, Markdown last.
    files.sort(key=lambda p:(p.name in {"report.json","report.md","report.html"},
                             {"report.json":0,"report.md":1,"report.html":2}.get(p.name,0)))
    for p in files:
        p.replace(dest/p.name)


def publish_partial_report(stage, report, max_findings, reason):
    """Save a labelled, incomplete report separately from the last full PASS."""
    candidates=[f for f in report["findings"] if f.get("severity")!="info"]
    candidates.sort(key=lambda f:(0 if f.get("detector") in PATCHABLE else 1))
    requested=candidates[:max_findings]
    completed=sum(
        bool(f.get("ai_explanation") and f.get("summary_hi") and f.get("summary_kn"))
        and (f.get("fix") or {}).get("status") in {"verified","unverified","not-applicable"}
        for f in requested
    )
    report.setdefault("ai",{}).update(
        partial=True, requested_findings=max_findings,
        completed_findings=completed,
        resumed_findings=sum(bool(f.get("ai_resumed")) for f in requested),
        failure=str(reason)[:260],
    )
    write_reports(report,stage)
    destination=OUTPUT/"partial"
    publish_report(stage,destination)
    print("PARTIAL REPORT:",destination/"report.html",f"({completed}/{max_findings} explained)")
    print("NOTICE: The previous fully successful report was not replaced.")


async def test(url,max_findings=1, *, resume=True, partial_on_failure=False):
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    scope=scope_hash()
    checkpoint_path=OUTPUT/CHECKPOINT_NAME
    state=read_checkpoint(checkpoint_path,scope) if resume else {
        "version":1,"scope":scope,"model":MODEL,"findings":{}
    }
    migrated=False
    if resume and not state["findings"]:
        old_scope=scope_hash(previous_client=True)
        prior=read_checkpoint(checkpoint_path,old_scope) if old_scope else None
        if prior and prior["findings"]:
            state={**prior,"scope":scope}
            migrated=True
            print("Found checkpoint from pre-retry AI client; verifying saved repairs in Chromium.")
    # Don't persist a new empty checkpoint until there is a completed finding.
    with tempfile.TemporaryDirectory(prefix=".ai-demo-stage-",dir=OUTPUT.parent) as folder:
        stage=Path(folder)
        report=await Scanner(stage,allow_local=True,max_pages=1).scan(url,lang="both")
        print("BROWSER SCAN:",report["summary"])
        if not report["findings"]:
            raise RuntimeError("Fixture unexpectedly produced no findings")
        async def progress(msg):
            print(msg)

        restored=await restore_findings(report,state,stage,progress=progress) if resume else 0
        if migrated and restored:
            # Upgrade only the records actually accepted by this fresh scan.
            valid={identity(f) for f in report["findings"] if f.get("ai_resumed")}
            state["findings"]={k:v for k,v in state["findings"].items() if k in valid}
            save_checkpoint(checkpoint_path,state)
            print("CHECKPOINT MIGRATED:",restored,"finding(s) browser-rechecked.")
        if restored:
            print(f"RESUMED: {restored} prior BharatCode finding(s), with fresh Chromium verification for repairable fixes.")
        print(f"Processing up to {max_findings} browser finding(s) with BharatCode.")

        def on_completed(f):
            status=(f.get("fix") or {}).get("status")
            if status not in {"verified","not-applicable","unverified"}:
                return
            if not all(f.get(k) for k in ("ai_explanation","summary_hi","summary_kn")):
                return
            state["findings"][identity(f)]={
                "ai_explanation":f["ai_explanation"],
                "summary_hi":f["summary_hi"],
                "summary_kn":f["summary_kn"],
                "fix":f["fix"],
            }
            save_checkpoint(checkpoint_path,state)
            print("PROGRESS SAVED:",f["detector"],"|",status,"| finding",identity(f)[:10])

        await explain_and_verify(report,allow_local=True,max_fixes=max_findings,
                                 progress=progress,output_dir=stage,use_cache=False,
                                 on_completed=on_completed,stream=True)
        checked=[f for f in report["findings"] if f.get("ai_explanation")]
        print("AI FINDINGS:",len(checked))
        for finding in report["findings"]:
            fix=finding.get("fix") or {}
            if fix:
                print("  ",finding["detector"],"|",fix.get("status","not attempted"),
                      "| finding",identity(finding)[:10],
                      "| resumed" if finding.get("ai_resumed") else "")
                if fix.get("status")=="unavailable":
                    print("  DIAGNOSTIC:",explain_provider_failure(fix.get("reason","Unknown model error")))
        unavailable=next(((f.get("fix") or {}).get("reason") for f in report["findings"]
                          if (f.get("fix") or {}).get("status")=="unavailable"),None)
        if unavailable:
            if partial_on_failure:
                try:
                    publish_partial_report(stage,report,max_findings,unavailable)
                except Exception as exc:
                    print("PARTIAL REPORT ERROR:",type(exc).__name__)
            if unavailable.startswith("BharatCode response failed"):
                print("NEXT: Your verified AI checkpoint is intact. Retry the same "
                      "--max-findings setting when BharatCode capacity is available.")
            raise RuntimeError("AI demo interrupted; saved progress can be resumed: "+unavailable)
        selected=[f for f in report["findings"] if f.get("severity")!="info"]
        selected.sort(key=lambda f: (0 if f.get("detector") in PATCHABLE else 1))
        selected=selected[:max_findings]
        if (len(selected)!=max_findings or
            not all(f.get("ai_explanation") and f.get("summary_hi") and f.get("summary_kn") and
                    (f.get("fix") or {}).get("status") in {"verified","unverified","not-applicable"}
                    for f in selected)):
            if partial_on_failure:
                try:
                    publish_partial_report(stage,report,max_findings,"Requested AI findings are not complete")
                except Exception as exc:
                    print("PARTIAL REPORT ERROR:",type(exc).__name__)
            raise RuntimeError("Requested AI findings are not complete; saved progress can be resumed.")
        # Report metadata separates this session's actual model calls from
        # successful model explanations reused from previous local sessions.
        report.setdefault("ai",{})["resumed_findings"]=sum(bool(f.get("ai_resumed")) for f in selected)
        write_reports(report,stage)
        publish_report(stage,OUTPUT)
        # Only a successful full run supersedes a previous partial run.
        shutil.rmtree(OUTPUT/"partial",ignore_errors=True)
        print("REPORT:",OUTPUT/"report.html")
        print("PASS:",len(selected),"BharatCode-explained findings;",
              report["ai"]["resumed_findings"],"resumed from earlier API sessions.")
        return report


def main():
    parser=argparse.ArgumentParser(description="Resumable BharatCode-to-Chromium demonstration")
    # The fixture has nine findings to fix or check. Saved progress means a
    # larger number only spends model calls on findings not yet explained.
    parser.add_argument("--max-findings",type=int,choices=range(1,10),default=1,
                        help="Number of browser findings to explain (1 to 9)")
    parser.add_argument("--fresh",action="store_true",
                        help="Ignore saved progress and request fresh model responses for every finding")
    parser.add_argument("--no-partial-report",action="store_true",
                        help="Disable separately labelled partial reports on provider failure")
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
        asyncio.run(test(url,max_findings=args.max_findings,resume=not args.fresh,
                         partial_on_failure=not args.no_partial_report))
        return 0
    except Exception as exc:
        print("DEMO FAILED:",type(exc).__name__,str(exc)[:220].replace(key,"[REDACTED]"))
        return 2
    finally:
        server.shutdown();server.server_close();worker.join(timeout=3)
        os.environ.pop("BHARATCODE_API_KEY",None)


if __name__=="__main__":
    raise SystemExit(main())
