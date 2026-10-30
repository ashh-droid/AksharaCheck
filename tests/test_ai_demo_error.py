"""Regression tests for a diagnostic AI run that fails after a previous success."""
import asyncio
import importlib.util
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("akshara_local_ai_demo", ROOT/"scripts"/"run_ai_demo.py")
assert spec and spec.loader
demo=importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


class FakeScanner:
    def __init__(self,*args,**kwargs):
        pass

    async def scan(self,*args,**kwargs):
        return {"findings":[
            {"id":"first","detector":"wrong-lang","severity":"warning",
             "viewport":390,"selector":'[data-akshara-id="ak-1"]',
             "sample":"यह पाठ है","fix":None},
            {"id":"second","detector":"broken-cluster","severity":"error",
             "viewport":390,"selector":'[data-akshara-id="ak-2"]',
             "sample":"ह िंदी","fix":None}
        ],"summary":{"error":1,"warning":1,"info":0}}


def setup_fake(monkeypatch,tmp_path):
    monkeypatch.setattr(demo,"OUTPUT",tmp_path)
    monkeypatch.setattr(demo,"Scanner",FakeScanner)


def test_401_failure_is_a_readable_error_and_keeps_prior_report(monkeypatch,tmp_path):
    setup_fake(monkeypatch,tmp_path)
    saved=tmp_path/"report.html"
    saved.write_text("previous successful verified AI report",encoding="utf-8")
    (tmp_path/"report.json").write_text('{"previous":true}',encoding="utf-8")

    async def unavailable(report,**options):
        assert options["use_cache"] is False
        report["findings"][0]["fix"]={"status":"unavailable",
            "reason":"HTTP 401: API authentication rejected"}
        # The unprocessed finding deliberately has fix: None.
    monkeypatch.setattr(demo,"explain_and_verify",unavailable)

    def unexpected_report(*args,**kwargs):
        raise AssertionError("Failed run must not overwrite existing report")
    monkeypatch.setattr(demo,"write_reports",unexpected_report)

    with pytest.raises(RuntimeError,match="HTTP 401: API authentication rejected"):
        asyncio.run(demo.test("http://127.0.0.1:55555/index.html",max_findings=5))
    assert saved.read_text(encoding="utf-8")=="previous successful verified AI report"
    assert (tmp_path/"report.json").read_text(encoding="utf-8")=='{"previous":true}'


def test_successful_fresh_ai_run_can_publish_report(monkeypatch,tmp_path):
    setup_fake(monkeypatch,tmp_path)
    observed={}

    async def success(report,**options):
        observed.update(options)
        report["findings"][0].update(
            ai_explanation="Text had an incorrect language tag",
            summary_hi="भाषा का टैग गलत था",
            summary_kn="ಭಾಷಾ ಗುರುತು ತಪ್ಪಾಗಿದೆ",
            fix={"status":"verified","attributes":{"lang":"hi"}})
    monkeypatch.setattr(demo,"explain_and_verify",success)

    def save_report(report,output):
        (output/"report.html").write_text("new verified AI report",encoding="utf-8")
    monkeypatch.setattr(demo,"write_reports",save_report)

    asyncio.run(demo.test("http://127.0.0.1:55555/index.html",max_findings=1))
    assert observed["use_cache"] is False
    assert observed["max_fixes"]==1
    assert (tmp_path/"report.html").read_text(encoding="utf-8")=="new verified AI report"


def test_partial_ai_response_does_not_replace_successful_report(monkeypatch,tmp_path):
    setup_fake(monkeypatch,tmp_path)
    p=tmp_path/"report.html"
    p.write_text("previous good report",encoding="utf-8")

    async def partial(report,**options):
        report["findings"][0].update(
            ai_explanation="One response passed",summary_hi="ठीक",summary_kn="ಸರಿ",
            fix={"status":"verified"})
        report["findings"][1]["fix"]={"status":"unavailable",
                                    "reason":"HTTP 401: API authentication rejected"}
    monkeypatch.setattr(demo,"explain_and_verify",partial)
    monkeypatch.setattr(demo,"write_reports",lambda *args: pytest.fail("Partial run was published"))

    with pytest.raises(RuntimeError,match="401"):
        asyncio.run(demo.test("http://127.0.0.1:55555/index.html",max_findings=5))
    assert p.read_text(encoding="utf-8")=="previous good report"


def test_partial_timeout_saves_progress_without_overwriting_json_then_resumes(monkeypatch,tmp_path):
    """Every completed model explanation is durable; verification is fresh."""
    setup_fake(monkeypatch,tmp_path)
    prior=tmp_path/"report.json"
    prior.write_text('{"successful_old_report":true}',encoding="utf-8")
    (tmp_path/"report.html").write_text("previous report",encoding="utf-8")
    monkeypatch.setenv("BHARATCODE_API_KEY","private-test-key")

    class ScannerThatWritesJSON(FakeScanner):
        async def scan(self,*args,**kwargs):
            result=await super().scan(*args,**kwargs)
            self_path=self.output_dir
            (self_path/"report.json").write_text('{"incomplete_scanner_report":true}',encoding="utf-8")
            (self_path/"page-01-390.png").write_bytes(b"new screenshot")
            return result
        def __init__(self,output_dir,*args,**kwargs):
            self.output_dir=Path(output_dir)

    monkeypatch.setattr(demo,"Scanner",ScannerThatWritesJSON)
    sent=[]

    async def partial(report,**options):
        assert options["use_cache"] is False
        assert options["stream"] is True
        assert options["max_fixes"]==2
        first=report["findings"][0]
        first.update(ai_explanation="Incorrect language tag",
                     summary_hi="भाषा का टैग गलत है",
                     summary_kn="ಭಾಷಾ ಗುರುತು ತಪ್ಪಾಗಿದೆ",
                     fix={"status":"verified","css":{},
                          "attributes":{"lang":"hi"},"viewport":390})
        options["on_completed"](first)
        sent.append("first")
        report["findings"][1]["fix"]={"status":"unavailable","reason":"Network or queue timeout"}

    monkeypatch.setattr(demo,"explain_and_verify",partial)
    with pytest.raises(RuntimeError,match="Network or queue timeout"):
        asyncio.run(demo.test("http://127.0.0.1:12345/index.html",max_findings=2))
    assert prior.read_text(encoding="utf-8")=='{"successful_old_report":true}'
    assert (tmp_path/"report.html").read_text(encoding="utf-8")=="previous report"
    progress=tmp_path/demo.CHECKPOINT_NAME
    data=demo.read_checkpoint(progress,demo.scope_hash())
    assert len(data["findings"])==1
    assert "private-test-key" not in progress.read_text(encoding="utf-8")

    verified=[]
    async def fake_verify(finding,patch,**kwargs):
        verified.append(finding["id"])
        assert patch["attributes"]=={"lang":"hi"}
        return {"status":"verified","css":{},"attributes":{"lang":"hi"},"viewport":390}
    monkeypatch.setattr(demo,"verify_patch",fake_verify)

    async def finish(report,**options):
        assert report["findings"][0]["ai_resumed"] is True
        assert report["findings"][0]["fix"]["status"]=="verified"
        assert options["max_fixes"]==2
        f=report["findings"][1]
        f.update(ai_explanation="Fix the text manually",
                 summary_hi="मूल पाठ बदलें",
                 summary_kn="ಮೂಲ ಪಠ್ಯ ಬದಲಾಯಿಸಿ",
                 fix={"status":"not-applicable"})
        options["on_completed"](f)
        report["ai"]={"model":"qwen-3.8-27b","calls":1}

    def fake_write(report,output):
        (output/"report.json").write_text('{"complete":true}',encoding="utf-8")
        (output/"report.md").write_text("completed",encoding="utf-8")
        (output/"report.html").write_text("new completed report",encoding="utf-8")
    monkeypatch.setattr(demo,"explain_and_verify",finish)
    monkeypatch.setattr(demo,"write_reports",fake_write)
    result=asyncio.run(demo.test("http://127.0.0.1:23456/index.html",max_findings=2))
    assert verified==["first"]
    assert result["ai"]["resumed_findings"]==1
    assert (tmp_path/"report.html").read_text(encoding="utf-8")=="new completed report"
    assert prior.read_text(encoding="utf-8")=='{"complete":true}'
    assert (tmp_path/"page-01-390.png").read_bytes()==b"new screenshot"


def test_checkpoint_invalidated_when_fixture_or_code_scope_differs(tmp_path):
    state={"version":1,"scope":"previous-code-version","model":demo.MODEL,
           "findings":{"previous":{"ai_explanation":"stale"}}}
    p=tmp_path/"checkpoint.json"
    demo.save_checkpoint(p,state)
    assert demo.read_checkpoint(p,"new-code-version")["findings"]=={}
    assert demo.read_checkpoint(p,"previous-code-version")["findings"]==state["findings"]
    p.write_text("not JSON",encoding="utf-8")
    assert demo.read_checkpoint(p,"previous-code-version")["findings"]=={}
