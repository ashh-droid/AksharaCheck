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


def test_failed_stream_explains_capacity_without_mislabeling_browser_or_key():
    reason="BharatCode response failed"
    message=demo.explain_provider_failure(reason)
    assert "response.failed" in message
    assert "busy-capacity" in message
    assert "possible" in message
    assert "no incomplete output was accepted" in message
    assert "invalid API key" not in message.lower()
    assert "verified fix failed" not in message.lower()
    assert demo.explain_provider_failure("HTTP 401: API authentication rejected") == "HTTP 401: API authentication rejected"
    assert demo.explain_provider_failure("Network or queue timeout") == "Network or queue timeout"


def test_partial_report_is_separate_from_last_complete_report(monkeypatch,tmp_path):
    """The CLI can show current browser evidence without replacing a prior PASS."""
    setup_fake(monkeypatch,tmp_path)
    completed=tmp_path/"report.html"
    completed.write_text("LAST COMPLETE PASS",encoding="utf-8")
    (tmp_path/"report.json").write_text('{"complete":true}',encoding="utf-8")
    saved_partial=[]

    async def provider_fails_after_first(report,**options):
        first,second=report["findings"]
        first.update(ai_explanation="This is tagged incorrectly.",
                     summary_hi="भाषा का टैग गलत है।",
                     summary_kn="ಭಾಷಾ ಗುರುತು ತಪ್ಪಾಗಿದೆ.",
                     fix={"status":"verified","attributes":{"lang":"hi"}})
        options["on_completed"](first)
        second["fix"]={"status":"unavailable","reason":"BharatCode response failed (3 attempts); request ID: req-77"}
        report["ai"]={"model":demo.MODEL,"calls":1}

    def write_partial(report,stage):
        saved_partial.append(report["ai"].copy())
        assert report["ai"]["partial"] is True
        assert report["ai"]["completed_findings"]==1
        assert report["ai"]["requested_findings"]==2
        (stage/"report.html").write_text("PARTIAL AI REPORT",encoding="utf-8")
        (stage/"report.json").write_text('{"partial":true}',encoding="utf-8")

    monkeypatch.setattr(demo,"explain_and_verify",provider_fails_after_first)
    monkeypatch.setattr(demo,"write_reports",write_partial)
    with pytest.raises(RuntimeError,match="BharatCode response failed"):
        asyncio.run(demo.test("http://127.0.0.1:8080/index.html",max_findings=2,
                              partial_on_failure=True))
    assert completed.read_text(encoding="utf-8")=="LAST COMPLETE PASS"
    assert (tmp_path/"report.json").read_text(encoding="utf-8")=='{"complete":true}'
    assert (tmp_path/"partial"/"report.html").read_text(encoding="utf-8")=="PARTIAL AI REPORT"
    assert len(saved_partial)==1
    assert len(demo.read_checkpoint(tmp_path/demo.CHECKPOINT_NAME,demo.scope_hash())["findings"])==1


def test_checkpoint_identity_distinguishes_same_rule_at_different_elements():
    first={"detector":"wrong-lang","severity":"warning",
           "selector":'[data-akshara-id="ak-one"]',"sample":"नमस्ते","viewport":390}
    second={**first,"selector":'[data-akshara-id="ak-two"]'}
    third={**first,"viewport":1440}
    assert demo.identity(first)!=demo.identity(second)
    assert demo.identity(first)!=demo.identity(third)
    assert demo.identity(first)==demo.identity(dict(first))


def test_pre_retry_checkpoint_is_migrated_after_fresh_browser_verification(monkeypatch,tmp_path):
    """Networking-only changes must not lose the user's two verified findings."""
    setup_fake(monkeypatch,tmp_path)
    previous_scope=demo.scope_hash(previous_client=True)
    assert previous_scope and previous_scope!=demo.scope_hash()
    old_finding={"detector":"wrong-lang","severity":"warning","viewport":390,
                 "selector":'[data-akshara-id="ak-1"]',"sample":"यह पाठ है"}
    state={"version":1,"scope":previous_scope,"model":demo.MODEL,
           "findings":{demo.identity(old_finding):{
               "ai_explanation":"The language tag is wrong.",
               "summary_hi":"भाषा का टैग गलत है।",
               "summary_kn":"ಭಾಷಾ ಗುರುತು ತಪ್ಪಾಗಿದೆ.",
               "fix":{"status":"verified","css":{},"attributes":{"lang":"hi"}}}}}
    demo.save_checkpoint(tmp_path/demo.CHECKPOINT_NAME,state)
    verifications=[]

    async def recheck(finding,patch,**kwargs):
        verifications.append(finding["id"])
        return {"status":"verified","css":{},"attributes":{"lang":"hi"}}
    monkeypatch.setattr(demo,"verify_patch",recheck)

    async def skip_completed(report,**options):
        assert report["findings"][0].get("ai_resumed") is True
        assert report["findings"][0]["fix"]["status"]=="verified"
        report["ai"]={"model":demo.MODEL,"calls":0}

    monkeypatch.setattr(demo,"explain_and_verify",skip_completed)
    monkeypatch.setattr(demo,"write_reports",
                        lambda report,folder:(folder/"report.html").write_text("RESUMED PASS",encoding="utf-8"))
    asyncio.run(demo.test("http://127.0.0.1:8080/index.html",max_findings=1))
    migrated=demo.read_checkpoint(tmp_path/demo.CHECKPOINT_NAME,demo.scope_hash())
    assert len(migrated["findings"])==1
    assert verifications==["first"]
    assert (tmp_path/"report.html").read_text(encoding="utf-8")=="RESUMED PASS"
