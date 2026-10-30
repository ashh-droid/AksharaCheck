"""BharatCode SSE keeps queued requests alive; only terminal completion is valid."""
import asyncio
import json

import httpx
import pytest

import aksharacheck.ai as ai


def finding():
    return {"id":"finding-test", "detector":"wrong-lang", "severity":"warning",
            "selector":'[data-akshara-id="ak-test"]',
            "sample":"हिंदी","viewport":390,"evidence":{}}


def provider(monkeypatch, tmp_path, body, *, status=200):
    monkeypatch.setenv("BHARATCODE_API_KEY","test-key-private")
    original=httpx.AsyncClient
    sent=[]
    def handler(request):
        payload=json.loads(request.content)
        sent.append(payload)
        assert payload["stream"] is True
        assert payload["model"]=="qwen-3.8-27b"
        return httpx.Response(status,headers={"content-type":"text/event-stream",
            "x-request-id":"req-test-123"},content=body)
    monkeypatch.setattr(ai.httpx,"AsyncClient",lambda **options:
                        original(transport=httpx.MockTransport(handler),**options))
    return ai.BharatCodeClient(cache_dir=tmp_path,stream=True),sent


def sse(name,data):
    return "event: "+name+"\n"+"data: "+json.dumps({"type":name,**data},
              ensure_ascii=False)+"\n\n"


def structured_result():
    return {"finding_id":"finding-test","explanation":"This text needs lang hi.",
            "summary_hi":"भाषा का टैग बदलें।",
            "summary_kn":"ಭಾಷಾ ಗುರುತು ಬದಲಾಯಿಸಿ.",
            "css":{},"attributes":{"lang":"hi"}}


def test_streaming_completion_after_keepalive_is_accepted(monkeypatch,tmp_path):
    output=json.dumps(structured_result(),ensure_ascii=False)
    stream=": queued\n\n"+sse("response.created",{"response":{"status":"in_progress"}})
    stream+=sse("response.output_text.delta",{"delta":output[:15]})
    stream+=": capacity keepalive\n\n"
    stream+=sse("response.output_text.delta",{"delta":output[15:]})
    stream+=sse("response.completed",{"response":{"status":"completed"}})
    client,sent=provider(monkeypatch,tmp_path,stream.encode())
    result=asyncio.run(client.propose(finding()))
    assert result["status"]=="proposed"
    assert result["attributes"]=={"lang":"hi"}
    assert result["summary_kn"]=="ಭಾಷಾ ಗುರುತು ಬದಲಾಯಿಸಿ."
    assert len(sent)==1 and sent[0]["text"]["format"]["type"]=="json_schema"


def test_streaming_completion_reads_terminal_output(monkeypatch,tmp_path):
    data={"status":"completed","output":[{"content":[{"type":"output_text",
          "text":json.dumps(structured_result(),ensure_ascii=False)}]}]}
    stream=sse("response.completed",{"response":data})
    client,sent=provider(monkeypatch,tmp_path,stream.encode())
    result=asyncio.run(client.propose(finding()))
    assert result["status"]=="proposed"
    assert len(sent)==1


@pytest.mark.parametrize("name",["response.failed","response.incomplete"])
def test_stream_never_accepts_failed_or_incomplete_output(monkeypatch,tmp_path,name):
    stream=sse("response.output_text.delta",{"delta":json.dumps(structured_result())})
    if name=="response.incomplete":
        response={"status":"incomplete","incomplete_details":{"reason":"max_output_tokens"}}
    else:
        response={"status":"failed"}
    stream+=sse(name,{"response":response})
    client,sent=provider(monkeypatch,tmp_path,stream.encode())
    result=asyncio.run(client.propose(finding()))
    assert result["status"]=="unavailable"
    assert name.split(".")[1] in result["error_code"]
    assert "test-key-private" not in repr(result)
    assert len(sent)==1


def test_stream_ending_after_partial_output_does_not_pass(monkeypatch,tmp_path):
    stream=sse("response.output_text.delta",{"delta":json.dumps(structured_result())})
    client,sent=provider(monkeypatch,tmp_path,stream.encode())
    result=asyncio.run(client.propose(finding()))
    assert result["status"]=="unavailable"
    assert "without response.completed" in result["error_code"]
    assert len(sent)==1


def test_streaming_http_401_carries_safe_request_id(monkeypatch,tmp_path):
    client,sent=provider(monkeypatch,tmp_path,b'{"error":"private"}',status=401)
    result=asyncio.run(client.propose(finding()))
    assert result["status"]=="unavailable"
    assert "HTTP 401" in result["error_code"]
    assert "req-test-123" in result["error_code"]
    assert "private" not in result["error_code"]


def test_read_timeout_is_not_mislabeled_as_bad_key(monkeypatch,tmp_path):
    monkeypatch.setenv("BHARATCODE_API_KEY","test-key-private")
    original=httpx.AsyncClient
    def handler(request):
        raise httpx.ReadTimeout("raw error may include sensitive transport info")
    monkeypatch.setattr(ai.httpx,"AsyncClient",lambda **options:
                        original(transport=httpx.MockTransport(handler),**options))
    result=asyncio.run(ai.BharatCodeClient(cache_dir=tmp_path,stream=True).propose(finding()))
    assert result["status"]=="unavailable"
    assert "Read timeout" in result["error_code"]
    assert "raw error" not in result["error_code"]
    assert "401" not in result["error_code"]
