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
