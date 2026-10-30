"""Safely check BharatCode API authorization and structured-output compatibility.

Run from the repository root:
  python scripts/check_bharatcode.py
The script privately prompts for the key unless BHARATCODE_API_KEY is already set. Never commit or paste the key into chats.
This makes one GET request and one short generation request.
"""
import json
import os
import sys
from getpass import getpass
import httpx

BASE="https://bharatcode.ai/api/model/v1"
MODEL="qwen-3.8-27b"

def run():
    key=os.environ.get("BHARATCODE_API_KEY","").strip()
    if not key:
        try:
            key=getpass("Enter your BharatCode API key (typing is hidden): ").strip()
        except (EOFError,KeyboardInterrupt):
            print("\nCancelled without sending a request.")
            return 2
        if not key:
            print("No API key entered.")
            return 2
    headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"}
    try:
        with httpx.Client(timeout=45,follow_redirects=False) as client:
            models=client.get(f"{BASE}/models",headers=headers)
            if models.status_code!=200:
                print(f"MODEL CATALOG: HTTP {models.status_code}. Verify your API access.")
                return 2
            catalog=models.json()
            available=[m.get("id","") for m in catalog.get("data",[]) if isinstance(m,dict)]
            print("MODEL CATALOG: authenticated")
            if available and MODEL not in available:
                print(f"MODEL WARNING: {MODEL} is not listed for this account")
            schema={
                "type":"object",
                "properties":{
                    "finding_id":{"type":"string"},
                    "explanation":{"type":"string"},
                    "summary_hi":{"type":"string"},
                    "summary_kn":{"type":"string"},
                    "css":{"type":"object","additionalProperties":{"type":"string"}},
                    "attributes":{"type":"object","additionalProperties":{"type":"string"}}
                },
                "required":["finding_id","explanation","summary_hi","summary_kn","css","attributes"],
                "additionalProperties":False
            }
            payload={
                "model":MODEL,"store":False,"max_output_tokens":1500,
                "reasoning":{"effort":"none"},
                "input":"Return JSON for finding_id demo-001. Explain that Hindi vowel sign after a space is a typing error, so no CSS or attribute repair is possible. Provide brief English, Hindi and Kannada explanations.",
                "text":{"format":{"type":"json_schema","name":"fix","strict":True,"schema":schema}}
            }
            response=client.post(f"{BASE}/responses",headers=headers,json=payload)
            print(f"STRUCTURED GENERATION: HTTP {response.status_code}")
            if response.status_code!=200:
                if response.status_code in (429,503):
                    print("Capacity is busy. Retry later without changing the key.")
                else:
                    print("API response (sanitized, up to 550 characters):")
                    body=response.text[:550].replace(key,"[REDACTED]")
                    print(body)
                return 2
            data=response.json()
            if data.get("status") in {"failed","incomplete"}:
                print("Request ended without full output:",data.get("status"),data.get("incomplete_details"))
                return 2
            texts=[]
            for item in data.get("output",[]):
                for part in item.get("content",[]):
                    if isinstance(part.get("text"),str):texts.append(part["text"])
            obj=json.loads("\n".join(texts))
            if obj.get("finding_id")!="demo-001":
                print("UNEXPECTED OUTPUT: model did not preserve the requested finding ID")
                return 2
            if not all(k in obj for k in ("explanation","summary_hi","summary_kn","css","attributes")):
                print("UNEXPECTED OUTPUT: missing requested language or repair fields")
                return 2
            print("PASS: BharatCode Qwen structured output and multilingual fields are compatible")
            print("No API credentials were printed or stored by this script.")
            return 0
    except (httpx.HTTPError,ValueError,KeyError) as exc:
        print(f"API TEST FAILED: {type(exc).__name__}. Check connectivity and response format.")
        return 2

if __name__=="__main__":
    sys.exit(run())
