"""A rejected repair goes back to BharatCode with Chromium's reason, and every attempt is kept."""
import asyncio

import aksharacheck.ai as ai


def finding(**changes):
    base = {"id": "f1", "url": "https://example.org", "viewport": 390, "selector": '[data-akshara-id="ak-1"]',
            "sample": "कृपया", "detector": "possible-clipping", "severity": "warning", "evidence": {}}
    base.update(changes)
    return base


class ScriptedClient:
    """Answers in order; records what it was told about earlier attempts."""
    replies = []
    seen = []

    def __init__(self, *args, **kwargs):
        self.key = "test"

    async def propose(self, f, previous=None):
        ScriptedClient.seen.append(previous)
        reply = dict(ScriptedClient.replies.pop(0))
        reply.setdefault("status", "proposed")
        reply.setdefault("usage", {"input_tokens": 100, "output_tokens": 20, "seconds": 1.5})
        return reply


def run(monkeypatch, replies, verdicts, f=None, max_attempts=3):
    ScriptedClient.replies = list(replies)
    ScriptedClient.seen = []
    queue = list(verdicts)

    async def fake_verify(finding, patch, *, allow_local=False, after_shot=None):
        return queue.pop(0)

    monkeypatch.setattr(ai, "BharatCodeClient", ScriptedClient)
    monkeypatch.setattr(ai, "verify_patch", fake_verify)
    report = {"findings": [f or finding()]}
    asyncio.run(ai.explain_and_verify(report, max_attempts=max_attempts))
    return report


def reply(css, text="Box too short"):
    return {"explanation": text, "summary_hi": "छोटा", "summary_kn": "ಚಿಕ್ಕದು", "css": css, "attributes": {}}


def test_second_attempt_wins_and_first_is_kept(monkeypatch):
    report = run(monkeypatch,
                 [reply({"height": "1px"}), reply({"height": "auto"})],
                 [{"status": "unverified", "reason": "Visible text area shrunk"}, {"status": "verified", "css": {"height": "auto"}}])
    fix = report["findings"][0]["fix"]
    assert fix["status"] == "verified"
    assert [a["status"] for a in fix["attempts"]] == ["unverified", "verified"]
    assert fix["attempts"][0]["reason"] == "Visible text area shrunk"
    # The model was told what failed and why.
    assert ScriptedClient.seen[1] == [{"css": {"height": "1px"}, "attributes": {}, "reason": "Visible text area shrunk"}]
    assert report["findings"][0]["summary_hi"] == "छोटा"
    assert report["ai"]["calls"] == 2 and report["ai"]["input_tokens"] == 200 and report["ai"]["seconds"] == 3.0


def test_stops_after_max_attempts(monkeypatch):
    bad = {"status": "unverified", "reason": "Original issue still present"}
    report = run(monkeypatch, [reply({"line-height": "1.2"}), reply({"line-height": "1.3"})], [bad, bad], max_attempts=2)
    fix = report["findings"][0]["fix"]
    assert fix["status"] == "unverified" and len(fix["attempts"]) == 2


def test_text_errors_are_not_patched(monkeypatch):
    report = run(monkeypatch, [reply({})], [], f=finding(detector="broken-cluster", severity="error"))
    assert report["findings"][0]["fix"]["status"] == "not-applicable"
    assert report["findings"][0]["ai_explanation"] == "Box too short"


def test_unavailable_model_is_reported_not_shown_as_explanation(monkeypatch):
    report = run(monkeypatch, [{"explanation": "HTTP 402", "css": {}, "attributes": {}, "status": "unavailable"}], [])
    f = report["findings"][0]
    assert f["fix"]["status"] == "unavailable"
    assert not f.get("ai_explanation")
    assert report["ai"]["calls"] == 0
