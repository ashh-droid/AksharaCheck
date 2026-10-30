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
            {"id":"first","detector":"wrong-lang","severity":"warning","fix":None},
            {"id":"second","detector":"broken-cluster","severity":"error","fix":None}
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
