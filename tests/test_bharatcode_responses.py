"""BharatCode API response handling must not misrepresent failed requests."""
import json
import pytest
from aksharacheck.ai import parse_response

def response(status="completed"):
    return {"status":status,"output":[{"content":[{"type":"output_text",
        "text":json.dumps({"finding_id":"demo-001","explanation":"A broken mark","css":{}})}]}]}

def test_completed_response_parses_json():
    assert parse_response(response())["finding_id"]=="demo-001"

@pytest.mark.parametrize("state",["incomplete","failed"])
def test_incomplete_or_failed_response_rejected(state):
    with pytest.raises(ValueError,match=f"BharatCode response {state}"):
        parse_response(response(state))

def test_empty_model_output_cannot_pass():
    with pytest.raises(ValueError):
        parse_response({"status":"completed","output":[]})


def test_incomplete_response_reports_output_budget_without_prompt_text():
    with pytest.raises(ValueError,match="incomplete \\(max_output_tokens\\)"):
        parse_response({"status":"incomplete",
                        "incomplete_details":{"reason":"max_output_tokens",
                                              "secret_prompt":"should never be logged"},
                        "output":[]})


def test_response_supports_aggregate_output_text():
    obj={"finding_id":"f1","explanation":"Rendered glyph","css":{}}
    assert parse_response({"status":"completed","output_text":json.dumps(obj)})["finding_id"]=="f1"


def test_model_client_diagnoses_http_error_without_exposing_key(monkeypatch,tmp_path):
    import asyncio
    import httpx
    import aksharacheck.ai as ai
    monkeypatch.setenv("BHARATCODE_API_KEY","test-secret-123")
    real_client=httpx.AsyncClient
    seen=[]
    def handler(request):
        seen.append(request)
        return httpx.Response(400,json={"error":{"message":"bad input"}})
    transport=httpx.MockTransport(handler)
    monkeypatch.setattr(ai.httpx,"AsyncClient",lambda **kwargs:real_client(transport=transport,**kwargs))
    finding={"id":"f-1","detector":"wrong-lang","viewport":390,"sample":"हिंदी",
             "selector":'[data-akshara-id="ak-1"]',"severity":"warning","evidence":{}}
    result=asyncio.run(ai.BharatCodeClient(cache_dir=tmp_path).propose(finding))
    assert result["status"]=="unavailable"
    assert "HTTP 400" in result["error_code"]
    assert "test-secret-123" not in str(result)
    assert len(seen)==1


def test_valid_multilingual_model_response_remains_supported(monkeypatch,tmp_path):
    import asyncio
    import httpx
    import aksharacheck.ai as ai
    monkeypatch.setenv("BHARATCODE_API_KEY","test-secret-123")
    real_client=httpx.AsyncClient
    def handler(request):
        prompt=json.loads(request.content.decode())["input"]
        assert "DATA_BEGIN" in prompt
        assert json.loads(request.content.decode())["max_output_tokens"]>=1500
        output={"finding_id":"f-1","explanation":"Incorrect language tag",
                "summary_hi":"भाषा गलत है","summary_kn":"ಭಾಷಾ ಗುರುತು ತಪ್ಪಾಗಿದೆ",
                "css":{},"attributes":{"lang":"hi"}}
        return httpx.Response(200,json={"status":"completed","output":[
            {"content":[{"type":"output_text","text":json.dumps(output,ensure_ascii=False)}]}]})
    monkeypatch.setattr(ai.httpx,"AsyncClient",lambda **kwargs:real_client(transport=httpx.MockTransport(handler),**kwargs))
    finding={"id":"f-1","detector":"wrong-lang","viewport":390,"sample":"हिंदी",
             "selector":'[data-akshara-id="ak-1"]',"severity":"warning","evidence":{}}
    proposed=asyncio.run(ai.BharatCodeClient(cache_dir=tmp_path).propose(finding))
    assert proposed["status"]=="proposed"
    assert proposed["attributes"]=={"lang":"hi"}
    assert proposed["summary_hi"]=="भाषा गलत है"
    assert proposed["summary_kn"]=="ಭಾಷಾ ಗುರುತು ತಪ್ಪಾಗಿದೆ"
